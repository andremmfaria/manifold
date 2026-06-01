"""Phase 4 acceptance tests — identity_backfill.

Covered (§9 Phase 4 acceptance):
  (a) Rerun = zero new identities/identifiers (idempotency).
  (b) Order-independence: forward / reversed / shuffled account order produces
      an identical identity partition (connected-component comparison).
  (c) Seeded duplicates collapse: same IBAN across two connections → 1 identity;
      SCAN+IBAN bridge over SCAN-only/IBAN-only halves → 1 identity.
  (d) Zero-identifier accounts (Wise shape) get a singleton identity OR remain
      null per spec, do not crash.

All tests run against an in-memory SQLite session (conftest.py db_session).
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.domain.identity_backfill import _backfill_user, backfill_identities
from manifold.models.account import Account
from manifold.models.account_identifier import AccountIdentifier
from manifold.models.account_identity import AccountIdentity
from manifold.models.provider_connection import ProviderConnection
from manifold.models.user import User
from manifold.security.encryption import EncryptionService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECRET = "test-secret-key-for-unit-tests-only-32chars"
VALID_IBAN_A = "GB29NWBK60161331926819"
VALID_IBAN_B = "DE89370400440532013000"
SORT_CODE = "601613"
ACCOUNT_NUM = "31926819"


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in test_account_identity_matching.py)
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid4())


async def _make_user(session: AsyncSession) -> User:
    svc = EncryptionService(SECRET)
    dek = svc.generate_dek()
    encrypted_dek = svc.encrypt_dek(dek)
    user = User(
        id=_uuid(),
        username=f"user-{_uuid()}",
        password_hash="x",
        role="regular",
        encrypted_dek=encrypted_dek,
    )
    session.add(user)
    await session.flush()
    return user


def _dek_ctx(user: User):
    svc = EncryptionService(SECRET)
    dek = svc.decrypt_dek(user.encrypted_dek)
    return svc.user_dek_context(dek)


async def _make_connection(session: AsyncSession, user: User) -> ProviderConnection:
    with _dek_ctx(user):
        conn = ProviderConnection(
            id=_uuid(),
            user_id=user.id,
            provider_type="json",
            status="active",
            auth_status="connected",
            credentials_encrypted={},
            config={},
        )
        session.add(conn)
        await session.flush()
    return conn


async def _make_account(
    session: AsyncSession,
    user: User,
    connection_id: str,
    *,
    provider_account_id: str | None = None,
    iban: str | None = None,
    sort_code: str | None = None,
    account_number: str | None = None,
    created_at: datetime | None = None,
) -> Account:
    """Insert an Account row in unassigned state (identity_id=NULL)."""
    with _dek_ctx(user):
        acct = Account(
            id=_uuid(),
            user_id=user.id,
            provider_connection_id=connection_id,
            provider_account_id=provider_account_id or _uuid(),
            account_type="TRANSACTION",
            currency="GBP",
            display_name="Test",
            iban=iban,
            sort_code=sort_code,
            account_number=account_number,
            is_active=True,
            raw_payload={},
        )
        if created_at is not None:
            acct.created_at = created_at
        session.add(acct)
        await session.flush()
    return acct


async def _count_live_identities(session: AsyncSession, user_id: str) -> int:
    result = await session.execute(
        select(AccountIdentity).where(
            AccountIdentity.user_id == user_id,
            AccountIdentity.merged_into.is_(None),
        )
    )
    return len(result.scalars().all())


async def _count_live_identifiers(session: AsyncSession, user_id: str) -> int:
    result = await session.execute(
        select(AccountIdentifier).where(
            AccountIdentifier.user_id == user_id,
            AccountIdentifier.retired_at.is_(None),
        )
    )
    return len(result.scalars().all())


def _identity_partition(accounts: list[Account]) -> frozenset[frozenset[str]]:
    """Return the connected-component partition of *accounts* by identity_id.

    Accounts with ``identity_id is None`` each form their own singleton
    component keyed on ``account.id`` (the per-connection fallback).
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for acct in accounts:
        key = acct.identity_id if acct.identity_id is not None else f"__null__{acct.id}"
        groups[key].append(acct.id)
    return frozenset(frozenset(ids) for ids in groups.values())


# ---------------------------------------------------------------------------
# (a) Idempotency — rerun produces zero new identities/identifiers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_rerun_is_noop(db_session: AsyncSession):
    """Running backfill twice produces no new identities or identifiers on the second run."""
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)

    await _make_account(db_session, user, conn.id, iban=VALID_IBAN_A)
    await _make_account(db_session, user, conn.id, sort_code=SORT_CODE, account_number=ACCOUNT_NUM)

    # First run.
    with _dek_ctx(user):
        counts1: dict[str, int] = {}
        counts1["identities"] = 0  # placeholder
        await _backfill_user(db_session, user.id, counts1)
        await db_session.flush()

    identities_after_1 = await _count_live_identities(db_session, user.id)
    identifiers_after_1 = await _count_live_identifiers(db_session, user.id)

    # Second run — all accounts now have identity_id set, so nothing to process.
    with _dek_ctx(user):
        counts2: dict[str, int] = {}
        await _backfill_user(db_session, user.id, counts2)
        await db_session.flush()

    identities_after_2 = await _count_live_identities(db_session, user.id)
    identifiers_after_2 = await _count_live_identifiers(db_session, user.id)

    assert identities_after_2 == identities_after_1, (
        f"Second run changed identity count: {identities_after_1} → {identities_after_2}"
    )
    assert identifiers_after_2 == identifiers_after_1, (
        f"Second run changed identifier count: {identifiers_after_1} → {identifiers_after_2}"
    )
    # Second run processes zero accounts (all already assigned).
    assert counts2.get("accounts_processed", 0) == 0


# ---------------------------------------------------------------------------
# (b) Order-independence — partition identical regardless of processing order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_order_independent(db_session: AsyncSession):
    """Forward, reversed, and shuffled processing of the same account set produce
    the same identity partition (connected-component comparison)."""
    user = await _make_user(db_session)
    conn_a = await _make_connection(db_session, user)
    conn_b = await _make_connection(db_session, user)
    conn_c = await _make_connection(db_session, user)

    t0 = datetime.now(UTC) - timedelta(days=10)

    # Three accounts; the IBAN links acct_1 and acct_2; acct_3 is SCAN-only
    # and separate.
    acct_1 = await _make_account(db_session, user, conn_a.id, iban=VALID_IBAN_A, created_at=t0)
    acct_2 = await _make_account(
        db_session, user, conn_b.id, iban=VALID_IBAN_A, created_at=t0 + timedelta(hours=1)
    )
    acct_3 = await _make_account(
        db_session,
        user,
        conn_c.id,
        sort_code=SORT_CODE,
        account_number=ACCOUNT_NUM,
        created_at=t0 + timedelta(hours=2),
    )
    all_accounts = [acct_1, acct_2, acct_3]

    # Helper: reset identity_id on all three accounts, wipe identities and
    # identifiers, then re-run backfill in a given order.
    async def _reset_and_backfill(order: list[Account]) -> frozenset[frozenset[str]]:
        # Wipe state.
        for acct in all_accounts:
            acct.identity_id = None
            db_session.add(acct)
        # Delete all identity/identifier rows for this user.
        ident_result = await db_session.execute(
            select(AccountIdentifier).where(AccountIdentifier.user_id == user.id)
        )
        for row in ident_result.scalars().all():
            await db_session.delete(row)
        id_result = await db_session.execute(
            select(AccountIdentity).where(AccountIdentity.user_id == user.id)
        )
        for row in id_result.scalars().all():
            await db_session.delete(row)
        await db_session.flush()

        # Re-run in the requested order.
        from manifold.config import settings as cfg
        from manifold.domain.account_identity import extract_identifiers, resolve_account_identity

        for acct in order:
            with _dek_ctx(user):
                from manifold.domain.identity_backfill import _account_to_dto

                dto = _account_to_dto(acct)
                rows = extract_identifiers(dto, user.id, "json", secret_key=cfg.secret_key)
                await resolve_account_identity(db_session, acct, rows, user_id=user.id)
                await db_session.flush()

        # Re-fetch identity_id values (ORM objects may be stale after bulk updates).
        refreshed = []
        for acct in all_accounts:
            result = await db_session.execute(
                select(Account.identity_id).where(Account.id == acct.id)
            )

            # Build a lightweight stand-in to avoid encrypted-column access.
            class _Stub:
                pass

            s = _Stub()
            s.id = acct.id
            s.identity_id = result.scalar_one_or_none()
            refreshed.append(s)

        return _identity_partition(refreshed)

    partition_forward = await _reset_and_backfill(all_accounts)
    partition_reversed = await _reset_and_backfill(list(reversed(all_accounts)))

    shuffled = all_accounts.copy()
    random.seed(42)
    random.shuffle(shuffled)
    partition_shuffled = await _reset_and_backfill(shuffled)

    assert partition_forward == partition_reversed, (
        f"Forward vs reversed differ:\n  forward:  {partition_forward}"
        f"\n  reversed: {partition_reversed}"
    )
    assert partition_forward == partition_shuffled, (
        f"Forward vs shuffled differ:\n  forward:  {partition_forward}"
        f"\n  shuffled: {partition_shuffled}"
    )

    # Confirm expected structure: acct_1 + acct_2 share an identity; acct_3 is separate.
    ids_1_2 = frozenset([acct_1.id, acct_2.id])
    ids_3 = frozenset([acct_3.id])
    assert ids_1_2 in partition_forward, f"Expected {ids_1_2} in partition {partition_forward}"
    assert ids_3 in partition_forward, f"Expected {ids_3} in partition {partition_forward}"


# ---------------------------------------------------------------------------
# (c) Seeded duplicates collapse to one identity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_iban_two_connections_one_identity(db_session: AsyncSession):
    """Two accounts (different connections) sharing the same IBAN collapse to
    exactly one live identity after backfill."""
    user = await _make_user(db_session)
    conn_a = await _make_connection(db_session, user)
    conn_b = await _make_connection(db_session, user)

    await _make_account(db_session, user, conn_a.id, iban=VALID_IBAN_A)
    await _make_account(db_session, user, conn_b.id, iban=VALID_IBAN_A)

    with _dek_ctx(user):
        totals: dict[str, int] = {}
        await _backfill_user(db_session, user.id, totals)
        await db_session.flush()

    live = await _count_live_identities(db_session, user.id)
    assert live == 1, f"Expected 1 live identity, got {live}"


@pytest.mark.asyncio
async def test_scan_iban_bridge_collapses_three_to_one_identity(db_session: AsyncSession):
    """SCAN-only + IBAN-only + bridge (SCAN+IBAN) accounts collapse to exactly one
    identity — the bridge merges the two disjoint halves."""
    user = await _make_user(db_session)
    conn_scan = await _make_connection(db_session, user)
    conn_iban = await _make_connection(db_session, user)
    conn_bridge = await _make_connection(db_session, user)

    t0 = datetime.now(UTC) - timedelta(days=5)

    # acct_scan is oldest → will be master.
    await _make_account(
        db_session,
        user,
        conn_scan.id,
        sort_code=SORT_CODE,
        account_number=ACCOUNT_NUM,
        created_at=t0,
    )
    await _make_account(
        db_session,
        user,
        conn_iban.id,
        iban=VALID_IBAN_A,
        created_at=t0 + timedelta(hours=1),
    )
    # Bridge — carries both identifiers → merges the two identities.
    await _make_account(
        db_session,
        user,
        conn_bridge.id,
        iban=VALID_IBAN_A,
        sort_code=SORT_CODE,
        account_number=ACCOUNT_NUM,
        created_at=t0 + timedelta(hours=2),
    )

    with _dek_ctx(user):
        totals: dict[str, int] = {}
        await _backfill_user(db_session, user.id, totals)
        await db_session.flush()

    live = await _count_live_identities(db_session, user.id)
    assert live == 1, f"Expected 1 live identity after bridge, got {live}"

    # All 3 accounts share the same identity_id.
    result = await db_session.execute(select(Account.identity_id).where(Account.user_id == user.id))
    identity_ids = {row for row in result.scalars().all()}
    assert None not in identity_ids, "Some accounts still have identity_id=NULL after backfill"
    assert len(identity_ids) == 1, f"Expected 1 distinct identity_id, got {identity_ids}"


# ---------------------------------------------------------------------------
# (d) Zero-identifier accounts — no crash; singular identity or null per spec
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_identifier_account_no_crash(db_session: AsyncSession):
    """An account with no IBAN / sort_code / account_number (Wise no-details shape)
    must not crash.  Per §3 / §5, it falls back to the per-connection unique
    constraint: identity_id remains NULL (no identifier = no cross-connection match)."""
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)

    acct = await _make_account(
        db_session,
        user,
        conn.id,
        # No identifiers at all — mirrors zero-identifier.json fixture shape.
        iban=None,
        sort_code=None,
        account_number=None,
    )

    # Must not raise.
    with _dek_ctx(user):
        totals: dict[str, int] = {}
        await _backfill_user(db_session, user.id, totals)
        await db_session.flush()

    # Per spec: zero identifiers → identity_id stays NULL (no match possible).
    result = await db_session.execute(select(Account.identity_id).where(Account.id == acct.id))
    identity_id = result.scalar_one_or_none()
    assert identity_id is None, (
        f"Zero-identifier account should remain unassigned; got identity_id={identity_id}"
    )

    # No identity rows created for this user.
    live = await _count_live_identities(db_session, user.id)
    assert live == 0, f"Expected 0 identities for zero-identifier account, got {live}"


@pytest.mark.asyncio
async def test_zero_identifier_mixed_with_identifier_accounts(db_session: AsyncSession):
    """Zero-identifier account alongside accounts that DO have identifiers.
    The identifier accounts get an identity; the zero-identifier one stays NULL;
    no crash."""
    user = await _make_user(db_session)
    conn_a = await _make_connection(db_session, user)
    conn_b = await _make_connection(db_session, user)

    acct_zero = await _make_account(
        db_session,
        user,
        conn_a.id,
        iban=None,
        sort_code=None,
        account_number=None,
    )
    acct_iban = await _make_account(db_session, user, conn_b.id, iban=VALID_IBAN_A)

    with _dek_ctx(user):
        totals: dict[str, int] = {}
        await _backfill_user(db_session, user.id, totals)
        await db_session.flush()

    # acct_zero → NULL
    zero_result = await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_zero.id)
    )
    assert zero_result.scalar_one_or_none() is None

    # acct_iban → assigned
    iban_result = await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_iban.id)
    )
    iban_identity = iban_result.scalar_one_or_none()
    assert iban_identity is not None

    # Exactly one live identity.
    live = await _count_live_identities(db_session, user.id)
    assert live == 1


# ---------------------------------------------------------------------------
# Full backfill_identities() integration — exercises the session + commit path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_backfill_function(db_session: AsyncSession):
    """Call backfill_identities(session=…) to exercise the public API end-to-end."""
    user = await _make_user(db_session)
    conn_a = await _make_connection(db_session, user)
    conn_b = await _make_connection(db_session, user)

    await _make_account(db_session, user, conn_a.id, iban=VALID_IBAN_A)
    await _make_account(db_session, user, conn_b.id, iban=VALID_IBAN_A)

    # Pass the existing test session so we stay in the same in-memory DB.
    result = await backfill_identities(session=db_session)

    assert result["users_processed"] >= 1
    assert result["accounts_processed"] >= 2

    live = await _count_live_identities(db_session, user.id)
    assert live == 1, f"Expected 1 live identity after full backfill, got {live}"
