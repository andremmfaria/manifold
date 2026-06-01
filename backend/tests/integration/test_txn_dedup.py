"""Integration tests for Phase 5 — identity-scoped transaction dedup.

Tests exercise _sync_transactions directly with real DB sessions (SQLite in-memory),
covering:

  TC1: Same txn via two connections under same identity → ONE row (Tier 1 dedup).
  TC2: Two distinct txns (same amount/date, different descriptions) → TWO rows (Tier 2 off).
  TC3: Single-connection account (no identity_id) → legacy dedup path unchanged.
  TC4: Tier 2 disabled by default → two rows inserted when Tier 1 misses
       (different provider_transaction_id, same content).
  TC5: Different identities, same content → NOT collapsed.
  TC6: New columns present and nullable by default.
  TC7: Re-sync after identity assigned — no UNIQUE violation, row count stays 1,
       identity_dedup_hash backfilled.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.domain.sync_engine import SyncEngine
from manifold.domain.transaction_fingerprint import compute_tier1_hash
from manifold.models.account import Account
from manifold.models.account_identity import AccountIdentity
from manifold.models.provider_connection import ProviderConnection
from manifold.models.transaction import Transaction
from manifold.models.user import User  # noqa: F401 — used via _make_user return type annotation
from manifold.security.encryption import EncryptionService

# ── helpers ──────────────────────────────────────────────────────────────────

SECRET_KEY = "test-secret-key-for-unit-tests-only-32chars"

# Single shared DEK for all test fixtures; consistent within each test session.
_enc = EncryptionService(SECRET_KEY)
_TEST_DEK = _enc.generate_dek()


def _uuid() -> str:
    return str(uuid4())


def _make_txn_item(
    provider_transaction_id: str,
    amount: Decimal = Decimal("4.50"),
    transaction_date: str = "2024-01-15",
    description: str = "STARBUCKS LONDON",
    currency: str = "GBP",
):
    """Return a minimal transaction DTO that _sync_transactions expects."""
    item = MagicMock()
    item.provider_transaction_id = provider_transaction_id
    item.amount = amount
    item.currency = currency
    item.transaction_type = "debit"
    item.transaction_category = None
    item.description = description
    item.merchant_name = None
    item.merchant_category = None
    item.transaction_date = transaction_date
    item.settled_date = None
    item.running_balance = None
    item.raw_payload = {}
    return item


async def _make_user(session: AsyncSession) -> User:
    from manifold.domain.users import create_user_record

    return await create_user_record(
        username=f"txntest-{_uuid()[:8]}",
        password="pass123",
        role="regular",
        session=session,
        email=f"txntest-{_uuid()[:8]}@example.com",
    )


async def _make_connection(session: AsyncSession, user: User) -> ProviderConnection:
    """Create a ProviderConnection.  Must be called inside a DEK context.

    credentials_encrypted and config are EncryptedJSON — pass plain dicts;
    SQLAlchemy's type processor encrypts them via the current DEK context.
    """
    conn = ProviderConnection(
        id=_uuid(),
        user_id=user.id,
        provider_type="json",
        display_name="Test Bank",
        status="active",
        auth_status="connected",
        credentials_encrypted={},
        config={},
    )
    session.add(conn)
    await session.flush()
    return conn


async def _make_identity(session: AsyncSession, user: User) -> AccountIdentity:
    identity = AccountIdentity(
        id=_uuid(),
        user_id=user.id,
        origin="auto",
    )
    session.add(identity)
    await session.flush()
    return identity


async def _make_account(
    session: AsyncSession,
    user: User,
    connection: ProviderConnection,
    identity: AccountIdentity | None = None,
) -> Account:
    """Create an Account.  Must be called inside a DEK context."""
    account_id = _uuid()
    acct = Account(
        id=account_id,
        user_id=user.id,
        provider_connection_id=connection.id,
        provider_account_id=f"prov-acct-{account_id[:8]}",
        account_type="personal",
        currency="GBP",
        display_name="Test Account",
        is_active=True,
        identity_id=identity.id if identity else None,
    )
    session.add(acct)
    await session.flush()
    return acct


async def _do_sync_transactions(
    session: AsyncSession,
    connection: ProviderConnection,
    account: Account,
    txn_items: list,
) -> int:
    """Run _sync_transactions.  Must be called inside a DEK context."""
    engine = SyncEngine(session=session)
    return await engine._sync_transactions(
        session,
        connection_id=str(connection.id),
        account=account,
        transactions=txn_items,
    )


# ── TC1: Same txn via two connections under same identity → ONE row ──────────


@pytest.mark.asyncio
async def test_same_txn_two_connections_one_identity_produces_one_row(
    db_session: AsyncSession,
) -> None:
    """TC1: Tier 1 dedup — same provider_transaction_id, same identity → no duplicate row."""
    with _enc.user_dek_context(_TEST_DEK):
        user = await _make_user(db_session)
        conn_a = await _make_connection(db_session, user)
        conn_b = await _make_connection(db_session, user)
        identity = await _make_identity(db_session, user)
        account_a = await _make_account(db_session, user, conn_a, identity)
        account_b = await _make_account(db_session, user, conn_b, identity)

        txn_id = "TXN-SHARED-001"
        txn = _make_txn_item(txn_id)

        # Sync via connection A
        inserted_a = await _do_sync_transactions(db_session, conn_a, account_a, [txn])
        assert inserted_a == 1

        # Sync via connection B — same physical transaction, same identity → MUST NOT insert
        inserted_b = await _do_sync_transactions(db_session, conn_b, account_b, [txn])
        assert inserted_b == 0, "Tier 1 dedup: second connection must not produce a new row"

        # Verify exactly ONE transaction row exists with this identity_dedup_hash
        expected_hash = compute_tier1_hash(str(identity.id), txn_id, secret_key=SECRET_KEY)
        result = await db_session.execute(
            select(Transaction).where(Transaction.identity_dedup_hash == expected_hash)
        )
        rows = result.scalars().all()
        assert len(rows) == 1, f"Expected 1 row, found {len(rows)}"


# ── TC2: Two genuinely-distinct transactions → TWO rows ─────────────────────


@pytest.mark.asyncio
async def test_distinct_transactions_same_amount_date_not_collapsed(
    db_session: AsyncSession,
) -> None:
    """TC2: Two distinct txns (same amount/date, different descriptions) → 2 rows.

    Tier 2 is DISABLED by default; they must NOT be collapsed.
    """
    with _enc.user_dek_context(_TEST_DEK):
        user = await _make_user(db_session)
        conn = await _make_connection(db_session, user)
        identity = await _make_identity(db_session, user)
        account = await _make_account(db_session, user, conn, identity)

        # Two genuinely different transactions: same amount/date, different descriptions
        txn_a = _make_txn_item("TXN-A", amount=Decimal("9.99"), description="NETFLIX MONTHLY")
        txn_b = _make_txn_item("TXN-B", amount=Decimal("9.99"), description="SPOTIFY MONTHLY")

        inserted = await _do_sync_transactions(db_session, conn, account, [txn_a, txn_b])
        assert inserted == 2, f"Expected 2 inserted, got {inserted}"

        result = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 2, f"Expected 2 rows, found {len(rows)}"


# ── TC3: Single-connection account (no identity_id) → legacy path ───────────


@pytest.mark.asyncio
async def test_single_connection_no_identity_uses_legacy_dedup(
    db_session: AsyncSession,
) -> None:
    """TC3: Account without identity_id falls back to MD5(connection_id:txn_id) dedup.

    Existing behavior must be preserved unchanged.
    """
    with _enc.user_dek_context(_TEST_DEK):
        user = await _make_user(db_session)
        conn = await _make_connection(db_session, user)
        # No identity — simulates an unresolved account
        account = await _make_account(db_session, user, conn, identity=None)
        assert account.identity_id is None

        txn = _make_txn_item("TXN-LEGACY-001")

        # First sync → insert
        inserted_1 = await _do_sync_transactions(db_session, conn, account, [txn])
        assert inserted_1 == 1

        # Second sync → same connection, same txn → no duplicate
        inserted_2 = await _do_sync_transactions(db_session, conn, account, [txn])
        assert inserted_2 == 0

        result = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1

        # identity_dedup_hash must be null (legacy path)
        assert rows[0].identity_dedup_hash is None

        # Legacy dedup_hash must be set — MD5 hex is 32 chars
        assert rows[0].dedup_hash is not None
        assert len(rows[0].dedup_hash) == 32


# ── TC4: Tier 2 disabled — different provider ids, same content → 2 rows ────


@pytest.mark.asyncio
async def test_tier2_disabled_different_txn_ids_same_content_inserts_two_rows(
    db_session: AsyncSession,
) -> None:
    """TC4: Tier 2 DISABLED by default.

    Two transactions from the same identity with DIFFERENT provider_transaction_ids
    but SAME amount/date/description should produce TWO rows (not collapsed), because
    Tier 2 (content-hash fallback) is off by default.  The content_hash column is
    populated for future use but not used as a dedup key.
    """
    with _enc.user_dek_context(_TEST_DEK):
        user = await _make_user(db_session)
        conn_a = await _make_connection(db_session, user)
        conn_b = await _make_connection(db_session, user)
        identity = await _make_identity(db_session, user)
        account_a = await _make_account(db_session, user, conn_a, identity)
        account_b = await _make_account(db_session, user, conn_b, identity)

        # Same content, DIFFERENT provider_transaction_id
        txn_a = _make_txn_item(
            "TXN-CONN-A-001", amount=Decimal("4.50"), description="STARBUCKS LONDON"
        )
        txn_b = _make_txn_item(
            "TXN-CONN-B-999",  # different id — the Tier 2 reconnection scenario
            amount=Decimal("4.50"),
            description="STARBUCKS LONDON",
        )

        inserted_a = await _do_sync_transactions(db_session, conn_a, account_a, [txn_a])
        assert inserted_a == 1

        # Tier 2 is disabled — different provider_transaction_id → Tier 1 misses → new row
        inserted_b = await _do_sync_transactions(db_session, conn_b, account_b, [txn_b])
        assert inserted_b == 1, (
            "Tier 2 must be DISABLED by default: different provider ids must produce separate rows"
        )

        # Both rows exist
        result_a = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account_a.id)
        )
        result_b = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account_b.id)
        )
        rows_a = result_a.scalars().all()
        rows_b = result_b.scalars().all()
        assert len(rows_a) == 1
        assert len(rows_b) == 1

        # content_hash IS populated (for future opt-in) even though it wasn't used for dedup
        assert rows_a[0].content_hash is not None
        assert rows_b[0].content_hash is not None
        # The two content hashes should match (same content, same identity)
        assert rows_a[0].content_hash == rows_b[0].content_hash, (
            "content_hash values should match for same content even though Tier 2 is off"
        )


# ── TC5: Different identities, same content → NOT collapsed ──────────────────


@pytest.mark.asyncio
async def test_different_identities_same_content_not_collapsed(
    db_session: AsyncSession,
) -> None:
    """TC5: identity_id boundary — same txn content under two different identities
    must produce two separate rows (cross-identity dedup is never done)."""
    with _enc.user_dek_context(_TEST_DEK):
        user = await _make_user(db_session)
        conn_a = await _make_connection(db_session, user)
        conn_b = await _make_connection(db_session, user)
        identity_a = await _make_identity(db_session, user)
        identity_b = await _make_identity(db_session, user)
        account_a = await _make_account(db_session, user, conn_a, identity_a)
        account_b = await _make_account(db_session, user, conn_b, identity_b)

        txn = _make_txn_item("TXN-SAME-001")

        inserted_a = await _do_sync_transactions(db_session, conn_a, account_a, [txn])
        inserted_b = await _do_sync_transactions(db_session, conn_b, account_b, [txn])

        assert inserted_a == 1
        assert inserted_b == 1, "Different identities must NEVER be collapsed by dedup"

        # identity_dedup_hash must differ (different identity_id in preimage)
        result_a = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account_a.id)
        )
        result_b = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account_b.id)
        )
        row_a = result_a.scalar_one()
        row_b = result_b.scalar_one()
        assert row_a.identity_dedup_hash != row_b.identity_dedup_hash


# ── TC6: Migration round-trip — new columns present + nullable ───────────────


@pytest.mark.asyncio
async def test_new_columns_present_and_nullable_by_default(
    db_session: AsyncSession,
) -> None:
    """TC6: After migration, new columns exist with correct defaults."""
    with _enc.user_dek_context(_TEST_DEK):
        user = await _make_user(db_session)
        conn = await _make_connection(db_session, user)
        account = await _make_account(db_session, user, conn)
        txn = _make_txn_item("TXN-COLS-001")

        await _do_sync_transactions(db_session, conn, account, [txn])

        result = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
        row = result.scalar_one()

        # No identity → legacy path → identity_dedup_hash and content_hash are null
        assert row.identity_dedup_hash is None
        assert row.content_hash is None
        # is_cross_connection_duplicate defaults to False
        assert row.is_cross_connection_duplicate is False


# ── TC7: Re-sync after identity assigned — no crash, one row, hash backfilled ─


@pytest.mark.asyncio
async def test_resync_after_identity_assigned_backfills_hash_no_duplicate(
    db_session: AsyncSession,
) -> None:
    """TC7: Regression — UNIQUE constraint violation when re-syncing a transaction
    whose account gains an identity_id after the first sync.

    Trigger scenario:
      1. Sync txn-0001 with NO identity → stored via legacy path (identity_dedup_hash NULL).
      2. Account is assigned an identity_id (simulating backfill-identities / merge).
      3. Re-sync txn-0001 → Tier 1 path now runs but the identity_dedup_hash lookup
         misses (existing row has NULL).  Without the fix this raises
         sqlite3.IntegrityError: UNIQUE constraint failed:
         transactions.account_id, transactions.provider_transaction_id.

    Expected post-fix behaviour:
      - No exception raised.
      - Exactly ONE transaction row for this account.
      - identity_dedup_hash is now populated on that row.
    """
    with _enc.user_dek_context(_TEST_DEK):
        user = await _make_user(db_session)
        conn = await _make_connection(db_session, user)

        # Step 1: account has NO identity — legacy path.
        account = await _make_account(db_session, user, conn, identity=None)
        assert account.identity_id is None

        txn = _make_txn_item("TXN-BACKFILL-0001")
        inserted_1 = await _do_sync_transactions(db_session, conn, account, [txn])
        assert inserted_1 == 1

        # Confirm legacy row has no identity_dedup_hash.
        result = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
        legacy_row = result.scalar_one()
        assert legacy_row.identity_dedup_hash is None

        # Step 2: assign identity_id to the account (simulating backfill-identities).
        identity = await _make_identity(db_session, user)
        account.identity_id = identity.id
        await db_session.flush()

        # Step 3: re-sync the same transaction — must NOT raise, must NOT insert a duplicate.
        inserted_2 = await _do_sync_transactions(db_session, conn, account, [txn])
        assert inserted_2 == 0, "Re-sync of existing row must not count as a new insert"

        # Exactly ONE row remains.
        result2 = await db_session.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
        rows = result2.scalars().all()
        assert len(rows) == 1, f"Expected 1 row after re-sync, got {len(rows)}"

        # identity_dedup_hash must now be populated (backfilled by the re-sync).
        expected_hash = compute_tier1_hash(
            str(identity.id), "TXN-BACKFILL-0001", secret_key=SECRET_KEY
        )
        assert rows[0].identity_dedup_hash == expected_hash, (
            "identity_dedup_hash must be backfilled on the existing row after re-sync"
        )
