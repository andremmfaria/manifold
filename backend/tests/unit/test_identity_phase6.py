"""Phase 6 tests — manual merge, unmerge, suggestions, aggregation gate.

All tests run against an in-memory SQLite session (db_session fixture).

Load-bearing scenarios:
  - Merge: two zero-identifier (Wise-style) accounts → shared identity
  - Merge: accounts that already have identities merge correctly
  - Merge: 'do_not_merge' pair deleted before writing 'same'
  - Unmerge bridge test: seed identity A (SCAN-only) + identity B (IBAN-only);
    sync a bridge account → auto-merge into A (B tombstoned, B's identifier
    stamped merged_from_identity=B); unmerge account from B → B peels to the
    resurrected original B id, its IBAN identifier back with merged_from_identity
    cleared, bridge account stays on A, do_not_merge written, subsequent bridging
    sync does NOT re-merge (step 0 honoured).
  - Suggestions: do_not_merge pairs suppressed; already-merged pairs not surfaced
  - Aggregation gate: IDENTITY_AGGREGATION_ENABLED is False
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.domain.account_identity import (
    IDENTITY_AGGREGATION_ENABLED,
    IdentityMergeService,
    IdentityUnmergeService,
    _write_assertion,
    extract_identifiers,
    resolve_account_identity,
    suggest_merges,
)
from manifold.models.account import Account
from manifold.models.account_identifier import AccountIdentifier
from manifold.models.account_identity import AccountIdentity
from manifold.models.account_identity_assertion import AccountIdentityAssertion
from manifold.models.provider_connection import ProviderConnection
from manifold.models.user import User
from manifold.providers.types import AccountData
from manifold.security.encryption import EncryptionService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECRET = "test-secret-key-for-unit-tests-only-32chars"
VALID_IBAN_A = "GB29NWBK60161331926819"
VALID_IBAN_B = "DE89370400440532013000"
SORT_CODE = "601613"
ACCOUNT_NUM = "31926819"


def _uuid() -> str:
    return str(uuid4())


def _dek_context(user: User):
    svc = EncryptionService(SECRET)
    dek = svc.decrypt_dek(user.encrypted_dek)
    return svc.user_dek_context(dek)


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


async def _make_connection(session: AsyncSession, user: User) -> ProviderConnection:
    with _dek_context(user):
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


async def _make_account_row(
    session: AsyncSession,
    user: User,
    connection_id: str,
    provider_account_id: str = "acct-001",
    iban: str | None = None,
    sort_code: str | None = None,
    account_number: str | None = None,
    display_name: str = "Test Account",
    account_type: str = "TRANSACTION",
    currency: str = "GBP",
    created_at: datetime | None = None,
) -> Account:
    with _dek_context(user):
        acct = Account(
            id=_uuid(),
            user_id=user.id,
            provider_connection_id=connection_id,
            provider_account_id=provider_account_id,
            account_type=account_type,
            currency=currency,
            display_name=display_name,
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


async def _resolve(
    session: AsyncSession,
    account: Account,
    account_data: AccountData,
    user: User,
) -> None:
    with _dek_context(user):
        rows = extract_identifiers(account_data, user.id, "json", secret_key=SECRET)
        await resolve_account_identity(session, account, rows, user_id=user.id)
        await session.flush()


def _make_account_data(
    provider_account_id: str = "acct-001",
    iban: str | None = None,
    sort_code: str | None = None,
    account_number: str | None = None,
    display_name: str = "Test Account",
    account_type: str = "TRANSACTION",
    currency: str = "GBP",
) -> AccountData:
    return AccountData(
        provider_account_id=provider_account_id,
        account_type=account_type,
        currency=currency,
        display_name=display_name,
        iban=iban,
        sort_code=sort_code,
        account_number=account_number,
    )


# ---------------------------------------------------------------------------
# Aggregation gate
# ---------------------------------------------------------------------------


def test_aggregation_gate_is_disabled():
    """Phase 5 must flip IDENTITY_AGGREGATION_ENABLED; it must be False now."""
    assert IDENTITY_AGGREGATION_ENABLED is False


# ---------------------------------------------------------------------------
# Merge: two zero-identifier (Wise-style) accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_two_zero_identifier_accounts(db_session: AsyncSession):
    """Two no-identifier accounts get a shared identity after manual merge."""
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)

    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    t1 = datetime(2024, 1, 2, tzinfo=UTC)
    acct_a = await _make_account_row(
        db_session, user, conn.id, provider_account_id="wise-a", created_at=t0
    )
    acct_b = await _make_account_row(
        db_session, user, conn.id, provider_account_id="wise-b", created_at=t1
    )

    # Neither has an identity yet (no identifiers → no auto-assignment).
    assert acct_a.identity_id is None
    assert acct_b.identity_id is None

    svc = IdentityMergeService()
    with _dek_context(user):
        survivor_id = await svc.merge(
            session=db_session,
            user_id=user.id,
            account_ids=[str(acct_a.id), str(acct_b.id)],
        )
    await db_session.flush()

    # Re-query identity_id directly (non-encrypted column; avoids DEK context).
    a_iid = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_a.id)
    )).scalar_one()
    b_iid = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_b.id)
    )).scalar_one()

    assert a_iid is not None
    assert b_iid is not None
    assert str(a_iid) == str(b_iid)
    assert str(a_iid) == survivor_id

    # Survivor is oldest (acct_a) — identity itself is not encrypted.
    id_result = await db_session.execute(
        select(AccountIdentity).where(AccountIdentity.id == survivor_id)
    )
    identity = id_result.scalar_one()
    assert str(identity.master_account_id) == str(acct_a.id)
    assert identity.origin == "manual"

    # 'same' assertion written.
    a_can = min(str(acct_a.id), str(acct_b.id))
    b_can = max(str(acct_a.id), str(acct_b.id))
    ass_result = await db_session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user.id,
            AccountIdentityAssertion.kind == "same",
            AccountIdentityAssertion.account_a_id == a_can,
            AccountIdentityAssertion.account_b_id == b_can,
        )
    )
    assert ass_result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Merge: do_not_merge pair gets deleted before writing same
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_clears_do_not_merge_assertion(db_session: AsyncSession):
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)
    acct_a = await _make_account_row(db_session, user, conn.id, provider_account_id="a")
    acct_b = await _make_account_row(db_session, user, conn.id, provider_account_id="b")

    # Pre-seed a do_not_merge assertion.
    await _write_assertion(db_session, user.id, "do_not_merge", str(acct_a.id), str(acct_b.id))
    await db_session.flush()

    svc = IdentityMergeService()
    with _dek_context(user):
        await svc.merge(
            session=db_session,
            user_id=user.id,
            account_ids=[str(acct_a.id), str(acct_b.id)],
        )
    await db_session.flush()

    # do_not_merge must be gone.
    a_can = min(str(acct_a.id), str(acct_b.id))
    b_can = max(str(acct_a.id), str(acct_b.id))
    dnm_result = await db_session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user.id,
            AccountIdentityAssertion.kind == "do_not_merge",
            AccountIdentityAssertion.account_a_id == a_can,
            AccountIdentityAssertion.account_b_id == b_can,
        )
    )
    assert dnm_result.scalar_one_or_none() is None

    # 'same' assertion must be present.
    same_result = await db_session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user.id,
            AccountIdentityAssertion.kind == "same",
            AccountIdentityAssertion.account_a_id == a_can,
            AccountIdentityAssertion.account_b_id == b_can,
        )
    )
    assert same_result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# LOAD-BEARING UNMERGE BRIDGE TEST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unmerge_bridge_account_retained_resurrected_identity(db_session: AsyncSession):
    """
    Scenario (§13.4 headline test):
      1. Seed identity A (SCAN-only account, oldest).
      2. Seed identity B (IBAN-only account).
      3. Sync a bridge account exposing BOTH SCAN + IBAN → auto-merge into A
         (oldest); B tombstoned, B's IBAN identifier re-pointed to A with
         merged_from_identity = B.
      4. Unmerge the IBAN-only account (acct_b) from the merged identity:
         - B peels to the RESURRECTED original B id (clear merged_into/merged_at).
         - B's IBAN identifier re-pointed back to B with merged_from_identity
           cleared.
         - Bridge account stays on A (straddles both groups).
         - do_not_merge assertion written between acct_b and acct_bridge.
      5. A subsequent bridging sync does NOT re-merge (step-0 honored).
    """
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)

    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    t1 = datetime(2024, 1, 2, tzinfo=UTC)
    t2 = datetime(2024, 1, 3, tzinfo=UTC)

    # --- Step 1: SCAN-only account (oldest = survivor of future merge) ---
    acct_a = await _make_account_row(
        db_session,
        user,
        conn.id,
        provider_account_id="acct-scan",
        sort_code=SORT_CODE,
        account_number=ACCOUNT_NUM,
        created_at=t0,
    )
    data_scan = _make_account_data(sort_code=SORT_CODE, account_number=ACCOUNT_NUM)
    await _resolve(db_session, acct_a, data_scan, user)
    identity_a_id = str(acct_a.identity_id)
    assert identity_a_id is not None

    # --- Step 2: IBAN-only account ---
    acct_b = await _make_account_row(
        db_session,
        user,
        conn.id,
        provider_account_id="acct-iban",
        iban=VALID_IBAN_A,
        created_at=t1,
    )
    data_iban = _make_account_data(iban=VALID_IBAN_A)
    await _resolve(db_session, acct_b, data_iban, user)
    identity_b_id = str(acct_b.identity_id)
    assert identity_b_id is not None
    assert identity_b_id != identity_a_id

    # --- Step 3: Bridge account exposes BOTH → auto-merge ---
    acct_bridge = await _make_account_row(
        db_session,
        user,
        conn.id,
        provider_account_id="acct-bridge",
        iban=VALID_IBAN_A,
        sort_code=SORT_CODE,
        account_number=ACCOUNT_NUM,
        created_at=t2,
    )
    data_bridge = _make_account_data(
        provider_account_id="acct-bridge",
        iban=VALID_IBAN_A,
        sort_code=SORT_CODE,
        account_number=ACCOUNT_NUM,
    )
    await _resolve(db_session, acct_bridge, data_bridge, user)
    await db_session.flush()

    # After bridge sync: all three accounts must share identity A.
    # Re-query identity_id directly (non-encrypted column).
    def _iid(acct: Account):
        return str(acct.identity_id) if acct.identity_id else None

    acct_a_iid = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_a.id)
    )).scalar_one()
    acct_b_iid = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_b.id)
    )).scalar_one()
    acct_bridge_iid = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_bridge.id)
    )).scalar_one()

    assert str(acct_a_iid) == identity_a_id
    assert str(acct_b_iid) == identity_a_id, (
        f"Expected acct_b on identity_a after bridge sync, got {acct_b_iid}"
    )
    assert str(acct_bridge_iid) == identity_a_id

    # Identity B must be tombstoned.
    id_b_result = await db_session.execute(
        select(AccountIdentity).where(AccountIdentity.id == identity_b_id)
    )
    id_b = id_b_result.scalar_one()
    assert id_b.merged_into == identity_a_id, "Identity B must be tombstoned into A"

    # B's IBAN identifier must have merged_from_identity = B and point to A.
    iban_rows = await db_session.execute(
        select(AccountIdentifier).where(
            AccountIdentifier.user_id == user.id,
            AccountIdentifier.id_type == "iban",
        )
    )
    iban_identifier = iban_rows.scalar_one()
    assert str(iban_identifier.identity_id) == identity_a_id
    assert str(iban_identifier.merged_from_identity) == identity_b_id

    # --- Step 4: Unmerge acct_b from the merged identity ---
    unmerge_svc = IdentityUnmergeService()
    with _dek_context(user):
        caveat = await unmerge_svc.unmerge(
            session=db_session,
            user_id=user.id,
            account_id=str(acct_b.id),
            secret_key=SECRET,
        )
    await db_session.flush()

    # Caveat must be a non-empty string about reversibility.
    assert isinstance(caveat, str) and len(caveat) > 0

    acct_b_iid_post = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_b.id)
    )).scalar_one()
    acct_bridge_iid_post = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_bridge.id)
    )).scalar_one()

    # acct_b must be on the RESURRECTED original B identity.
    assert str(acct_b_iid_post) == identity_b_id, (
        f"Expected acct_b on resurrected identity_b ({identity_b_id}), "
        f"got {acct_b_iid_post}"
    )

    # Identity B must be resurrected (merged_into cleared).
    id_b_result2 = await db_session.execute(
        select(AccountIdentity).where(AccountIdentity.id == identity_b_id)
    )
    id_b2 = id_b_result2.scalar_one()
    assert id_b2.merged_into is None, "Identity B tombstone must be cleared after unmerge"
    assert id_b2.merged_at is None

    # B's IBAN identifier must be re-pointed to B, merged_from_identity cleared.
    iban_rows2 = await db_session.execute(
        select(AccountIdentifier).where(
            AccountIdentifier.user_id == user.id,
            AccountIdentifier.id_type == "iban",
            AccountIdentifier.retired_at.is_(None),
        )
    )
    iban_identifier2 = iban_rows2.scalar_one()
    assert str(iban_identifier2.identity_id) == identity_b_id, (
        "IBAN identifier must be re-pointed to resurrected B"
    )
    assert iban_identifier2.merged_from_identity is None, (
        "merged_from_identity must be cleared on resurrected identifier"
    )

    # Bridge account STAYS with A (it straddles both groups).
    assert str(acct_bridge_iid_post) == identity_a_id, (
        "Bridge account must remain with identity A"
    )

    # do_not_merge written between acct_b and acct_bridge.
    a_can = min(str(acct_b.id), str(acct_bridge.id))
    b_can = max(str(acct_b.id), str(acct_bridge.id))
    dnm_result = await db_session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user.id,
            AccountIdentityAssertion.kind == "do_not_merge",
            AccountIdentityAssertion.account_a_id == a_can,
            AccountIdentityAssertion.account_b_id == b_can,
        )
    )
    assert dnm_result.scalar_one_or_none() is not None, (
        "do_not_merge assertion must be written between acct_b and acct_bridge"
    )

    # --- Step 5: Subsequent bridge sync does NOT re-merge (step-0 honored) ---
    # Re-sync the bridge account (IBAN + SCAN); the do_not_merge between acct_b
    # and acct_bridge must block auto-merge between their identities.
    await _resolve(db_session, acct_bridge, data_bridge, user)
    await db_session.flush()

    acct_b_iid_final = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_b.id)
    )).scalar_one()
    acct_bridge_iid_final = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_bridge.id)
    )).scalar_one()

    # acct_b must STILL be on identity B (not re-merged into A).
    assert str(acct_b_iid_final) == identity_b_id, (
        "acct_b must not be re-merged after unmerge + do_not_merge"
    )
    # acct_bridge remains on A.
    assert str(acct_bridge_iid_final) == identity_a_id


# ---------------------------------------------------------------------------
# Suggestions: do_not_merge pairs suppressed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggestions_suppress_do_not_merge(db_session: AsyncSession):
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)

    acct_a = await _make_account_row(
        db_session,
        user,
        conn.id,
        provider_account_id="sug-a",
        display_name="My Savings",
        account_type="SAVINGS",
        currency="GBP",
    )
    acct_b = await _make_account_row(
        db_session,
        user,
        conn.id,
        provider_account_id="sug-b",
        display_name="My Savings",
        account_type="SAVINGS",
        currency="GBP",
    )

    # Without do_not_merge, identical names + type + currency → suggestion.
    with _dek_context(user):
        suggestions_before = await suggest_merges(db_session, user.id)

    has_pair = any(
        (s["account_a_id"] in (str(acct_a.id), str(acct_b.id)) and
         s["account_b_id"] in (str(acct_a.id), str(acct_b.id)))
        for s in suggestions_before
    )
    assert has_pair, "Expected suggestion before do_not_merge"

    # Write do_not_merge.
    await _write_assertion(db_session, user.id, "do_not_merge", str(acct_a.id), str(acct_b.id))
    await db_session.flush()

    with _dek_context(user):
        suggestions_after = await suggest_merges(db_session, user.id)

    has_pair_after = any(
        (s["account_a_id"] in (str(acct_a.id), str(acct_b.id)) and
         s["account_b_id"] in (str(acct_a.id), str(acct_b.id)))
        for s in suggestions_after
    )
    assert not has_pair_after, "do_not_merge pair must be suppressed from suggestions"


# ---------------------------------------------------------------------------
# Suggestions: already-merged pair not surfaced
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggestions_skip_already_merged(db_session: AsyncSession):
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)

    acct_a = await _make_account_row(
        db_session, user, conn.id, provider_account_id="mg-a",
        display_name="Test Bank", account_type="TRANSACTION", currency="GBP",
    )
    acct_b = await _make_account_row(
        db_session, user, conn.id, provider_account_id="mg-b",
        display_name="Test Bank", account_type="TRANSACTION", currency="GBP",
    )

    svc = IdentityMergeService()
    with _dek_context(user):
        await svc.merge(db_session, user.id, [str(acct_a.id), str(acct_b.id)])
    await db_session.flush()

    with _dek_context(user):
        suggestions = await suggest_merges(db_session, user.id)

    has_pair = any(
        (s["account_a_id"] in (str(acct_a.id), str(acct_b.id)) and
         s["account_b_id"] in (str(acct_a.id), str(acct_b.id)))
        for s in suggestions
    )
    assert not has_pair, "Already-merged pair must not appear in suggestions"


# ---------------------------------------------------------------------------
# Unmerge: native (no-provenance) group mints a fresh identity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unmerge_native_group_mints_fresh_identity(db_session: AsyncSession):
    """Manually merged zero-identifier accounts unmerge to a fresh identity."""
    user = await _make_user(db_session)
    conn = await _make_connection(db_session, user)

    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    t1 = datetime(2024, 1, 2, tzinfo=UTC)
    acct_a = await _make_account_row(
        db_session, user, conn.id, provider_account_id="native-a", created_at=t0
    )
    acct_b = await _make_account_row(
        db_session, user, conn.id, provider_account_id="native-b", created_at=t1
    )

    svc = IdentityMergeService()
    with _dek_context(user):
        survivor_id = await svc.merge(
            db_session, user.id, [str(acct_a.id), str(acct_b.id)]
        )
    await db_session.flush()

    # Both should be on survivor (re-query to avoid DEK context).
    a_iid_pre = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_a.id)
    )).scalar_one()
    b_iid_pre = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_b.id)
    )).scalar_one()
    assert str(a_iid_pre) == survivor_id
    assert str(b_iid_pre) == survivor_id

    # Unmerge acct_b.
    unmerge_svc = IdentityUnmergeService()
    with _dek_context(user):
        caveat = await unmerge_svc.unmerge(
            db_session, user.id, str(acct_b.id), secret_key=SECRET
        )
    await db_session.flush()

    a_iid_post = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_a.id)
    )).scalar_one()
    b_iid_post = (await db_session.execute(
        select(Account.identity_id).where(Account.id == acct_b.id)
    )).scalar_one()

    assert isinstance(caveat, str)
    # acct_b gets a fresh identity (not the survivor).
    assert b_iid_post is not None
    assert str(b_iid_post) != survivor_id
    # acct_a still on survivor.
    assert str(a_iid_post) == survivor_id

    # do_not_merge written between the two.
    a_can = min(str(acct_a.id), str(acct_b.id))
    b_can = max(str(acct_a.id), str(acct_b.id))
    dnm = await db_session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user.id,
            AccountIdentityAssertion.kind == "do_not_merge",
            AccountIdentityAssertion.account_a_id == a_can,
            AccountIdentityAssertion.account_b_id == b_can,
        )
    )
    assert dnm.scalar_one_or_none() is not None
