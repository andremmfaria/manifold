from __future__ import annotations

import re
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.models.account import Account
from manifold.models.account_identifier import AccountIdentifier
from manifold.models.account_identity import AccountIdentity
from manifold.models.account_identity_assertion import AccountIdentityAssertion
from manifold.models.event import Event
from manifold.providers.types import AccountData
from manifold.security.fingerprint import compute_identifier_hmac

logger = structlog.get_logger(__name__)

# Providers that expose multi-currency accounts sharing a single IBAN across
# per-currency wallets.  For these, ``currency`` participates in the match key
# so that a GBP Wise wallet and a USD Wise wallet remain distinct identities
# even when they carry the same IBAN.
# Populate this set before any Wise / Revolut adapter ships (§6 gate).
MULTI_CURRENCY_PROVIDERS: frozenset[str] = frozenset()

# Sentinel used in ``account_identifier.currency`` for single-currency providers
# so that the column is never NULL inside the UNIQUE index.
CURRENCY_SENTINEL = "-"


# ---------------------------------------------------------------------------
# Identifier-value type alias used by Phase 3.
# Each tuple: (id_type, value_hmac, currency)
# ---------------------------------------------------------------------------
IdentifierRow = tuple[str, str, str]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize_iban(raw: str | None) -> str | None:
    """Return a canonicalized IBAN or *None* if the value is absent or invalid.

    Steps:
    1. Strip all non-alphanumeric characters and uppercase.
    2. Validate the mod-97 checksum (ISO 7064).

    Logs a debug message when an invalid IBAN is skipped so we can audit bad
    provider data without raising.
    """
    if not raw:
        return None

    candidate = re.sub(r"[^A-Z0-9]", "", raw.upper())

    if len(candidate) < 5:
        logger.debug("iban_too_short_skipped", raw=raw)
        return None

    # Rearrange: move first 4 chars to end, then convert letters to digits
    # (A=10, B=11, … Z=35) and check that the resulting integer mod 97 == 1.
    rearranged = candidate[4:] + candidate[:4]
    numeric_str = "".join(str(ord(c) - ord("A") + 10) if c.isalpha() else c for c in rearranged)
    if int(numeric_str) % 97 != 1:
        logger.debug("iban_invalid_mod97_skipped", raw=raw, candidate=candidate)
        return None

    return candidate


def normalize_scan(sort_code: str | None, account_number: str | None) -> str | None:
    """Return a canonical ``sortcode:number`` string or *None* if either field is absent.

    * ``sort_code`` — strip all non-digit characters, must yield exactly 6 digits.
    * ``account_number`` — strip all non-digit characters, zero-pad to 8 digits.

    Both fields are required; a bare ``account_number`` without a ``sort_code``
    is not globally unique and therefore forms no identifier (§5).
    """
    if not sort_code or not account_number:
        return None

    sc_digits = re.sub(r"\D", "", sort_code)
    an_digits = re.sub(r"\D", "", account_number)

    if len(sc_digits) != 6:
        logger.debug("scan_sort_code_invalid_skipped", sort_code=sort_code)
        return None

    if not an_digits:
        logger.debug("scan_account_number_empty_skipped", account_number=account_number)
        return None

    an_padded = an_digits.zfill(8)
    return f"{sc_digits}:{an_padded}"


def normalize_aba(routing: str | None, account_number: str | None) -> str | None:
    """Return a canonical ``routing:number`` string or *None* if either field is absent.

    Both fields are required; digits only.
    """
    if not routing or not account_number:
        return None

    rt_digits = re.sub(r"\D", "", routing)
    an_digits = re.sub(r"\D", "", account_number)

    if not rt_digits or not an_digits:
        return None

    return f"{rt_digits}:{an_digits}"


def normalize_currency(currency: str | None) -> str:
    """Return an uppercase, trimmed currency code, or the sentinel ``'-'`` for absent/empty."""
    if not currency or not currency.strip():
        return CURRENCY_SENTINEL
    return currency.strip().upper()


# ---------------------------------------------------------------------------
# Main extraction function — public API for Phase 3
# ---------------------------------------------------------------------------


def extract_identifiers(
    account: AccountData,
    user_id: str,
    provider_type: str,
    secret_key: str | None = None,
) -> list[IdentifierRow]:
    """Compute the list of ``(id_type, value_hmac, currency)`` rows for *account*.

    Rules (§5, §6):
    * Emit an ``iban`` identifier when the IBAN normalizes and passes mod-97.
    * Emit a ``scan`` identifier when both ``sort_code`` and ``account_number``
      are present and well-formed.
    * Emit an ``aba`` identifier when both ``routing`` and ``account_number``
      are present (``AccountData`` has no routing field today, so this branch
      never fires for current providers — the function is designed to support it).
    * ``currency`` participates in the identifier only for providers in
      ``MULTI_CURRENCY_PROVIDERS``; all others get the sentinel ``'-'``.
    * Accounts that yield zero identifiers (Wise no-details, number-only accounts)
      return an empty list.  Phase 3 will log this and fall back to the
      per-connection unique constraint.

    The returned ``value_hmac`` is a 64-char hex HMAC-SHA256 anchored to
    ``user_id``, ``id_type``, and the normalized value (§5).
    """
    currency_dim = (
        normalize_currency(account.currency)
        if provider_type in MULTI_CURRENCY_PROVIDERS
        else CURRENCY_SENTINEL
    )

    rows: list[IdentifierRow] = []

    # --- IBAN ---
    norm_iban = normalize_iban(account.iban)
    if norm_iban is not None:
        hmac_val = compute_identifier_hmac(user_id, "iban", norm_iban, secret_key)
        rows.append(("iban", hmac_val, currency_dim))

    # --- SCAN (UK sort_code + account_number) ---
    norm_scan = normalize_scan(account.sort_code, account.account_number)
    if norm_scan is not None:
        hmac_val = compute_identifier_hmac(user_id, "scan", norm_scan, secret_key)
        rows.append(("scan", hmac_val, currency_dim))

    # --- ABA (US routing + account_number) ---
    # AccountData has no routing field today; include the branch so Phase 3 can
    # call this function unchanged when a routing-aware DTO variant arrives.
    routing: str | None = getattr(account, "routing_number", None)
    norm_aba = normalize_aba(routing, account.account_number if routing else None)
    if norm_aba is not None:
        hmac_val = compute_identifier_hmac(user_id, "aba", norm_aba, secret_key)
        rows.append(("aba", hmac_val, currency_dim))

    if not rows:
        logger.debug(
            "account_zero_identifiers",
            provider_account_id=account.provider_account_id,
            provider_type=provider_type,
            user_id=user_id,
        )

    return rows


# ---------------------------------------------------------------------------
# Phase 3 — identity matching + merge
# ---------------------------------------------------------------------------


async def _merge_identities(
    session: AsyncSession,
    survivor_id: str,
    loser_ids: list[str],
    trigger: str,
    user_id: str,
) -> None:
    """Merge *loser_ids* into *survivor_id* in-place (no return value).

    Steps (§3.1):
    1. Re-point each loser's ``account_identifier`` rows to the survivor,
       stamping ``merged_from_identity`` (only when currently null — preserves
       deepest origin across chained merges).
    2. On ``UNIQUE`` collision (survivor already owns that identifier):
       retire the loser row (``retired_at = now()``, stamp
       ``merged_from_identity``) rather than deleting it so unmerge can
       resurrect it (§3.1 step 3).
    3. Re-point ``accounts.identity_id`` rows that point at a loser → survivor.
    4. Recompute ``survivor.master_account_id`` = oldest Account by
       ``created_at``; tie-break by smallest Account UUID.
    5. Tombstone loser identities (``merged_into``, ``merged_at``).
    6. Emit an ``identity_merged`` Event.

    Runs inside the caller's transaction — a crash rolls back cleanly.
    Called by both the sync resolver (trigger=``auto``) and Phase 6 manual
    merge (trigger=``manual``).
    """
    now = datetime.now(UTC)

    for loser_id in loser_ids:
        # --- Step 1 + 2: re-point identifier rows ---
        # Fetch all non-retired loser identifiers.
        result = await session.execute(
            select(AccountIdentifier).where(
                AccountIdentifier.identity_id == loser_id,
                AccountIdentifier.retired_at.is_(None),
            )
        )
        loser_identifiers = result.scalars().all()

        for ident in loser_identifiers:
            # Check whether the survivor already owns this (user_id, id_type,
            # value_hmac, currency) tuple.
            conflict_result = await session.execute(
                select(AccountIdentifier).where(
                    AccountIdentifier.user_id == ident.user_id,
                    AccountIdentifier.id_type == ident.id_type,
                    AccountIdentifier.value_hmac == ident.value_hmac,
                    AccountIdentifier.currency == ident.currency,
                    AccountIdentifier.identity_id == survivor_id,
                    AccountIdentifier.retired_at.is_(None),
                )
            )
            survivor_has = conflict_result.scalar_one_or_none()

            if survivor_has is not None:
                # Collision — retire the loser row; keep the survivor's row active.
                ident.retired_at = now
                if ident.merged_from_identity is None:
                    ident.merged_from_identity = loser_id
                session.add(ident)
            else:
                # Safe to re-point.
                ident.identity_id = survivor_id
                if ident.merged_from_identity is None:
                    ident.merged_from_identity = loser_id
                session.add(ident)

        # --- Step 3: re-point account rows ---
        await session.execute(
            update(Account).where(Account.identity_id == loser_id).values(identity_id=survivor_id)
        )

        # --- Step 5: tombstone the loser ---
        result = await session.execute(
            select(AccountIdentity).where(AccountIdentity.id == loser_id)
        )
        loser_identity = result.scalar_one_or_none()
        if loser_identity is not None:
            loser_identity.merged_into = survivor_id
            loser_identity.merged_at = now
            session.add(loser_identity)

    await session.flush()

    # --- Step 4: recompute survivor's master_account_id ---
    # Oldest Account by created_at among all members; tie-break: smallest UUID.
    member_result = await session.execute(
        select(Account)
        .where(Account.identity_id == survivor_id)
        .order_by(Account.created_at.asc(), Account.id.asc())
    )
    members = member_result.scalars().all()
    if members:
        result = await session.execute(
            select(AccountIdentity).where(AccountIdentity.id == survivor_id)
        )
        survivor = result.scalar_one_or_none()
        if survivor is not None:
            survivor.master_account_id = members[0].id
            session.add(survivor)

    await session.flush()

    # --- Step 6: emit identity_merged event ---
    # Fetch any account_id bound to the survivor to use as the event anchor.
    first_account_result = await session.execute(
        select(Account).where(Account.identity_id == survivor_id).limit(1)
    )
    anchor_account = first_account_result.scalar_one_or_none()

    await session.execute(
        Event.__table__.insert().values(
            id=_new_uuid(),
            event_type="identity_merged",
            source_type="observed",
            account_id=anchor_account.id if anchor_account else None,
            user_id=user_id,
            payload={"survivor": survivor_id, "absorbed": loser_ids, "trigger": trigger},
            occurred_at=now,
            recorded_at=now,
        )
    )

    logger.info(
        "identity_merged",
        survivor_id=survivor_id,
        absorbed=loser_ids,
        trigger=trigger,
        user_id=user_id,
    )


async def _get_or_insert_identifier(
    session: AsyncSession,
    identity_id: str,
    user_id: str,
    id_type: str,
    value_hmac: str,
    currency: str,
    now: datetime,
) -> AccountIdentifier:
    """Portable get-or-create for an AccountIdentifier row.

    SELECT-then-INSERT pattern (no savepoints required):
    1. SELECT the existing row by (user_id, id_type, value_hmac, currency),
       excluding retired rows.
    2. If found, return it — the caller compares its identity_id to detect a
       cross-identity collision (§4.2).
    3. If not found, INSERT.  In the concurrent-first-sight race (two tasks
       see the same identifier simultaneously), exactly one INSERT wins; the
       loser catches IntegrityError and falls through to a second SELECT.

    Works on SQLite, PostgreSQL, and MariaDB — does NOT rely on
    ``INSERT ... ON CONFLICT ... RETURNING`` (PostgreSQL-only) or savepoints
    that behave differently across async DBAPI drivers.
    """
    # Step 1: try SELECT first (cheap; avoids a write on the common re-sync path).
    existing = await _select_identifier(session, user_id, id_type, value_hmac, currency)
    if existing is not None:
        return existing

    # Step 2: INSERT (new identifier — or concurrent race winner).
    new_id = _new_uuid()
    new_row = AccountIdentifier(
        id=new_id,
        identity_id=identity_id,
        user_id=user_id,
        id_type=id_type,
        value_hmac=value_hmac,
        currency=currency,
        last_seen_at=now,
        retired_at=None,
        merged_from_identity=None,
        created_at=now,
    )
    try:
        sp = await session.begin_nested()
        session.add(new_row)
        await session.flush()
        await sp.commit()
        return new_row
    except IntegrityError:
        await sp.rollback()
        try:
            session.expunge(new_row)
        except Exception:
            pass
        # Race: another task inserted the same identifier between our SELECT
        # and INSERT.  SELECT again to get the winner's row.
        existing = await _select_identifier(session, user_id, id_type, value_hmac, currency)
        if existing is not None:
            return existing
        # Should never reach here; guard defensively.
        raise


async def _select_identifier(
    session: AsyncSession,
    user_id: str,
    id_type: str,
    value_hmac: str,
    currency: str,
) -> AccountIdentifier | None:
    """SELECT the live (non-retired) identifier row, or None if absent."""
    result = await session.execute(
        select(AccountIdentifier).where(
            AccountIdentifier.user_id == user_id,
            AccountIdentifier.id_type == id_type,
            AccountIdentifier.value_hmac == value_hmac,
            AccountIdentifier.currency == currency,
            AccountIdentifier.retired_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


def _new_uuid() -> str:
    from uuid import uuid4

    return str(uuid4())


async def resolve_account_identity(
    session: AsyncSession,
    account: Account,
    identifier_rows: list[IdentifierRow],
    user_id: str,
) -> None:
    """Bind *account* to an AccountIdentity via its extracted identifier rows.

    Implements §3.1 (0 / 1 / ≥2 match resolution) including:
    - Step 0: do_not_merge assertion check.
    - Identifier get-or-create with read-after-conflict (§4.2 portability).
    - Cross-identity collision detection → merge.
    - ``last_seen_at`` bump on re-observed identifiers.

    Modifies *account.identity_id* in place; the caller must flush/commit.
    """
    now = datetime.now(UTC)

    if not identifier_rows:
        # Zero identifiers — falls back to per-connection unique constraint.
        # Account stays identity-less until a backfill or manual merge (§3 / §5 note).
        logger.debug(
            "account_zero_identifiers_no_identity_assigned",
            account_id=account.id,
            user_id=user_id,
        )
        return

    # -----------------------------------------------------------------------
    # Phase A: insert-or-get each identifier; collect matched identity_ids.
    # -----------------------------------------------------------------------
    # We need a provisional identity_id for the insert path.  We will create it
    # lazily: start with None, create on first identifier that lands in a new
    # identity (0-match path).
    provisional_identity_id: str | None = None
    matched_identity_ids: set[str] = set()
    live_identifier_rows: list[AccountIdentifier] = []

    for id_type, value_hmac, currency in identifier_rows:
        # Determine which identity_id to attempt inserting against.
        # If the account already has an identity (from a previous loop iteration
        # that found a match), use that; otherwise use the provisional one.
        target_identity_id = account.identity_id or provisional_identity_id

        if target_identity_id is None:
            # We haven't created a provisional identity yet.  Create it now so
            # the insert has something to point at.  If the insert fails (collision),
            # we discard this identity later.
            provisional_identity_id = _new_uuid()
            target_identity_id = provisional_identity_id

            new_identity = AccountIdentity(
                id=provisional_identity_id,
                user_id=user_id,
                master_account_id=account.id,
                origin="auto",
            )
            session.add(new_identity)
            await session.flush()

        ident_row = await _get_or_insert_identifier(
            session,
            target_identity_id,
            user_id,
            id_type,
            value_hmac,
            currency,
            now,
        )

        if ident_row.retired_at is not None:
            # Retired identifier — skip; acts as if absent (§4.4).
            continue

        # Bump last_seen_at regardless of whether we just inserted.
        ident_row.last_seen_at = now
        session.add(ident_row)

        matched_identity_ids.add(ident_row.identity_id)
        live_identifier_rows.append(ident_row)

    if not live_identifier_rows:
        # All identifiers were retired — treat as zero-identifier.
        if provisional_identity_id:
            # Clean up the provisional identity we created.
            result = await session.execute(
                select(AccountIdentity).where(AccountIdentity.id == provisional_identity_id)
            )
            prov = result.scalar_one_or_none()
            if prov is not None:
                await session.delete(prov)
        return

    await session.flush()

    # -----------------------------------------------------------------------
    # Phase B: resolve based on matched_identity_ids count.
    # -----------------------------------------------------------------------
    # Remove any tombstoned identity_ids (merged_into non-null) from the set —
    # they are absorbed identities; their successors are the live ones.
    live_identity_ids: set[str] = set()
    for iid in matched_identity_ids:
        result = await session.execute(
            select(AccountIdentity).where(
                AccountIdentity.id == iid,
                AccountIdentity.merged_into.is_(None),
            )
        )
        if result.scalar_one_or_none() is not None:
            live_identity_ids.add(iid)
        else:
            # Follow the merge chain to the survivor.
            result2 = await session.execute(
                select(AccountIdentity).where(AccountIdentity.id == iid)
            )
            identity = result2.scalar_one_or_none()
            if identity is not None and identity.merged_into is not None:
                live_identity_ids.add(identity.merged_into)

    if len(live_identity_ids) == 0:
        # Shouldn't happen — we just inserted/read identifiers — but guard it.
        logger.warning(
            "identity_resolution_no_live_identity",
            account_id=account.id,
            user_id=user_id,
        )
        return

    if len(live_identity_ids) == 1:
        # 0-match (we created a new identity) OR 1-match (bound to existing).
        winner_id = next(iter(live_identity_ids))

        # If we created a provisional identity that is different from the winner,
        # delete the provisional one (the winner is the existing match).
        if provisional_identity_id is not None and provisional_identity_id != winner_id:
            result = await session.execute(
                select(AccountIdentity).where(AccountIdentity.id == provisional_identity_id)
            )
            prov = result.scalar_one_or_none()
            if prov is not None:
                await session.delete(prov)
            await session.flush()

            # Accrete any new identifiers (those that pointed to provisional)
            # onto the winner instead.
            await session.execute(
                update(AccountIdentifier)
                .where(AccountIdentifier.identity_id == provisional_identity_id)
                .values(identity_id=winner_id)
            )

        account.identity_id = winner_id
        session.add(account)

        # Recompute master_account_id for the winner.
        await _recompute_master(session, winner_id)
        await session.flush()
        return

    # ≥2 live identities matched — merge required.
    # ------------------------------------------------------------------
    # Step 0: honour do_not_merge assertions.
    # Check all pairs; if ANY pair is blocked, log and skip auto-merge
    # for that entire cluster (conservative — if any pair is blocked we
    # leave all separate to avoid partial merges creating a new split).
    # ------------------------------------------------------------------
    account_ids_per_identity: dict[str, list[str]] = {}
    for iid in live_identity_ids:
        result = await session.execute(
            select(Account.id).where(Account.identity_id == iid, Account.user_id == user_id)
        )
        account_ids_per_identity[iid] = [str(r) for r in result.scalars().all()]

    suppressed = False
    identity_list = sorted(live_identity_ids)  # deterministic iteration
    for i, iid_a in enumerate(identity_list):
        for iid_b in identity_list[i + 1 :]:
            for acct_a in account_ids_per_identity.get(iid_a, []):
                for acct_b in account_ids_per_identity.get(iid_b, []):
                    # Canonical order: smaller UUID first.
                    a_canonical = min(acct_a, acct_b)
                    b_canonical = max(acct_a, acct_b)
                    assertion_result = await session.execute(
                        select(AccountIdentityAssertion).where(
                            AccountIdentityAssertion.user_id == user_id,
                            AccountIdentityAssertion.kind == "do_not_merge",
                            AccountIdentityAssertion.account_a_id == a_canonical,
                            AccountIdentityAssertion.account_b_id == b_canonical,
                        )
                    )
                    if assertion_result.scalar_one_or_none() is not None:
                        logger.info(
                            "auto_merge_suppressed_by_assertion",
                            account_id=account.id,
                            identity_a=iid_a,
                            identity_b=iid_b,
                            blocked_pair=(acct_a, acct_b),
                            user_id=user_id,
                        )
                        suppressed = True
                        break
                if suppressed:
                    break
            if suppressed:
                break
        if suppressed:
            break

    if suppressed:
        # Leave identities separate; bind account to its existing identity
        # (or the provisional one if it has no prior identity).
        if account.identity_id is None and provisional_identity_id is not None:
            account.identity_id = provisional_identity_id
            session.add(account)
            await _recompute_master(session, provisional_identity_id)
        await session.flush()
        return

    # ------------------------------------------------------------------
    # Step 1: survivor = identity of oldest Account by created_at; tie-break
    # smallest identity UUID.
    # ------------------------------------------------------------------
    oldest_account: Account | None = None
    oldest_identity_id: str | None = None

    for iid in live_identity_ids:
        acct_result = await session.execute(
            select(Account)
            .where(Account.identity_id == iid, Account.user_id == user_id)
            .order_by(Account.created_at.asc(), Account.id.asc())
        )
        candidate = acct_result.scalars().first()
        if candidate is not None:
            if (
                oldest_account is None
                or candidate.created_at < oldest_account.created_at
                or (
                    candidate.created_at == oldest_account.created_at
                    and str(iid) < str(oldest_identity_id)
                )
            ):
                oldest_account = candidate
                oldest_identity_id = iid

    if oldest_identity_id is None:
        # No member accounts — fall back to smallest UUID as survivor.
        oldest_identity_id = sorted(live_identity_ids)[0]

    survivor_id = oldest_identity_id
    loser_ids = [iid for iid in live_identity_ids if iid != survivor_id]

    # If provisional identity exists and is the survivor, keep it.
    # If it is a loser, it will be merged in _merge_identities.
    # If it is not in live_identity_ids at all, delete it.
    if provisional_identity_id is not None and provisional_identity_id not in live_identity_ids:
        result = await session.execute(
            select(AccountIdentity).where(AccountIdentity.id == provisional_identity_id)
        )
        prov = result.scalar_one_or_none()
        if prov is not None:
            await session.delete(prov)
        await session.flush()

    await _merge_identities(session, survivor_id, loser_ids, trigger="auto", user_id=user_id)

    # Bind the incoming account to the survivor.
    account.identity_id = survivor_id
    session.add(account)
    await session.flush()


async def _recompute_master(session: AsyncSession, identity_id: str) -> None:
    """Recompute ``master_account_id`` for *identity_id* as the oldest member account."""
    result = await session.execute(
        select(Account)
        .where(Account.identity_id == identity_id)
        .order_by(Account.created_at.asc(), Account.id.asc())
    )
    members = result.scalars().all()

    identity_result = await session.execute(
        select(AccountIdentity).where(AccountIdentity.id == identity_id)
    )
    identity = identity_result.scalar_one_or_none()
    if identity is not None:
        identity.master_account_id = members[0].id if members else None
        session.add(identity)


# ---------------------------------------------------------------------------
# Phase 6 — aggregation gate
# ---------------------------------------------------------------------------

# Set to True in Phase 5 when transaction dedup is identity-aware.
# Until then, any read that would sum across identity_id returns per-member
# with aggregated=False.
IDENTITY_AGGREGATION_ENABLED: bool = False


# ---------------------------------------------------------------------------
# Phase 6 — assertion writers
# ---------------------------------------------------------------------------


async def _write_assertion(
    session: AsyncSession,
    user_id: str,
    kind: str,
    account_a_id: str,
    account_b_id: str,
) -> None:
    """Idempotently write an assertion of *kind* for the canonical-ordered pair.

    Canonical order: account_a_id = min(uuid), account_b_id = max(uuid).
    Deletes any contradicting assertion of the opposite kind before inserting.
    """
    a = min(account_a_id, account_b_id)
    b = max(account_a_id, account_b_id)
    opposite_kind = "do_not_merge" if kind == "same" else "same"

    # Delete the contradicting assertion if present.
    existing_opposite = await session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user_id,
            AccountIdentityAssertion.kind == opposite_kind,
            AccountIdentityAssertion.account_a_id == a,
            AccountIdentityAssertion.account_b_id == b,
        )
    )
    for row in existing_opposite.scalars().all():
        await session.delete(row)

    # Check for existing same-kind assertion (dedup).
    existing_same = await session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user_id,
            AccountIdentityAssertion.kind == kind,
            AccountIdentityAssertion.account_a_id == a,
            AccountIdentityAssertion.account_b_id == b,
        )
    )
    if existing_same.scalar_one_or_none() is None:
        now = datetime.now(UTC)
        session.add(
            AccountIdentityAssertion(
                id=_new_uuid(),
                user_id=user_id,
                kind=kind,
                account_a_id=a,
                account_b_id=b,
                created_at=now,
            )
        )
    await session.flush()


async def _ensure_singleton_identity(
    session: AsyncSession,
    account: Account,
    user_id: str,
) -> str:
    """Return account.identity_id, creating a singleton identity if null."""
    if account.identity_id is not None:
        # Verify it's not a tombstone; follow chain to live identity.
        result = await session.execute(
            select(AccountIdentity).where(AccountIdentity.id == account.identity_id)
        )
        identity = result.scalar_one_or_none()
        if identity is not None and identity.merged_into is None:
            return str(account.identity_id)
        # Tombstoned — follow chain.
        if identity is not None and identity.merged_into is not None:
            account.identity_id = identity.merged_into
            session.add(account)
            await session.flush()
            return str(account.identity_id)

    # Mint a fresh singleton identity.
    now = datetime.now(UTC)
    new_id = _new_uuid()
    session.add(
        AccountIdentity(
            id=new_id,
            user_id=user_id,
            master_account_id=account.id,
            origin="manual",
            created_at=now,
            updated_at=now,
        )
    )
    account.identity_id = new_id
    session.add(account)
    await session.flush()
    return new_id


# ---------------------------------------------------------------------------
# Phase 6 — IdentityMergeService
# ---------------------------------------------------------------------------


class IdentityMergeService:
    """Merge ≥2 accounts into one identity (manual user action, §13.3)."""

    async def merge(
        self,
        session: AsyncSession,
        user_id: str,
        account_ids: list[str],
    ) -> str:
        """Merge *account_ids* into one identity; return the survivor identity id.

        Steps:
        1. Load + validate accounts (all must belong to user_id).
        2. Mint singleton identities for any null-identity accounts.
        3. Write 'same' assertion for each unordered pair (delete contradicting
           'do_not_merge' first).
        4. Survivor = identity of the oldest account by created_at.
        5. Run _merge_identities(trigger='manual').
        6. Set survivor.origin = 'manual'.
        7. Recompute master_account_id.
        8. Emit identity_merged event.
        """
        if len(account_ids) < 2:
            raise ValueError("merge requires at least 2 accounts")

        # --- Load accounts ---
        accounts: list[Account] = []
        for aid in account_ids:
            result = await session.execute(
                select(Account).where(Account.id == aid, Account.user_id == user_id)
            )
            acct = result.scalar_one_or_none()
            if acct is None:
                raise ValueError(f"account {aid} not found for user {user_id}")
            accounts.append(acct)

        # --- Ensure singleton identities ---
        identity_ids: list[str] = []
        for acct in accounts:
            iid = await _ensure_singleton_identity(session, acct, user_id)
            identity_ids.append(iid)

        # --- Write 'same' assertions for each pair ---
        for i, acct_i in enumerate(accounts):
            for acct_j in accounts[i + 1 :]:
                await _write_assertion(session, user_id, "same", str(acct_i.id), str(acct_j.id))

        # --- Determine survivor: identity of oldest account ---
        oldest_acct = min(accounts, key=lambda a: (a.created_at, str(a.id)))
        # Refresh identity_id in case it was just set.
        survivor_id = str(oldest_acct.identity_id)

        # Collect distinct loser identity ids (deduplicate — two accounts may
        # already share one identity).
        all_identity_ids = {str(acct.identity_id) for acct in accounts}
        loser_ids = [iid for iid in all_identity_ids if iid != survivor_id]

        if loser_ids:
            await _merge_identities(
                session, survivor_id, loser_ids, trigger="manual", user_id=user_id
            )

        # --- Set origin = 'manual' on survivor ---
        result = await session.execute(
            select(AccountIdentity).where(AccountIdentity.id == survivor_id)
        )
        survivor = result.scalar_one_or_none()
        if survivor is not None:
            survivor.origin = "manual"
            session.add(survivor)

        await _recompute_master(session, survivor_id)
        await session.flush()

        logger.info(
            "manual_merge_complete",
            survivor_id=survivor_id,
            account_ids=account_ids,
            user_id=user_id,
        )
        return survivor_id


# ---------------------------------------------------------------------------
# Phase 6 — IdentityUnmergeService
# ---------------------------------------------------------------------------


class IdentityUnmergeService:
    """Peel one pre-merge origin group out of a merged identity (§13.4)."""

    async def unmerge(
        self,
        session: AsyncSession,
        user_id: str,
        account_id: str,
        secret_key: str | None = None,
    ) -> str:
        """Unmerge *account_id* from its current identity.

        Returns a caveat string about imperfect reversibility.

        Algorithm:
        1. Load account + current identity.  Identity must be live (not tombstone).
        2. Group the identity's non-retired identifiers by
           coalesce(merged_from_identity, identity_id) → pre-merge origin groups.
        3. Identify which group 'account_id' belongs to by re-deriving its live
           identifiers (decrypt + extract_identifiers) and matching value_hmacs
           against each group.  Bridge accounts (spanning groups) stay with survivor.
        4. Resurrect the origin tombstone for the peel group (clear merged_into/
           merged_at); re-point that group's identifier rows back (clear
           merged_from_identity on immediately-homed rows; clear retired_at on
           rows that were retired-on-collision from that origin).
        5. Re-point peel-set accounts.identity_id to resurrected identity.
        6. Recompute master_account_id for both identities.
        7. Write do_not_merge between peel-side account and each stay-side account.
        8. Delete any contradicting 'same' assertions (log assertion_superseded).
        """
        # --- Load account ---
        acct_result = await session.execute(
            select(Account).where(Account.id == account_id, Account.user_id == user_id)
        )
        account = acct_result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"account {account_id} not found for user {user_id}")

        if account.identity_id is None:
            raise ValueError(f"account {account_id} has no identity to unmerge from")

        identity_id = str(account.identity_id)

        # --- Load identity (must be live) ---
        id_result = await session.execute(
            select(AccountIdentity).where(
                AccountIdentity.id == identity_id,
                AccountIdentity.merged_into.is_(None),
            )
        )
        current_identity = id_result.scalar_one_or_none()
        if current_identity is None:
            raise ValueError(f"identity {identity_id} is a tombstone — cannot unmerge")

        # --- Load all non-retired identifiers for this identity ---
        ident_result = await session.execute(
            select(AccountIdentifier).where(
                AccountIdentifier.identity_id == identity_id,
                AccountIdentifier.retired_at.is_(None),
            )
        )
        live_identifiers: list[AccountIdentifier] = list(ident_result.scalars().all())

        # --- Group identifiers by origin ---
        # Origin key = merged_from_identity if set, else the current identity_id
        # (meaning the identifier was born in this identity, i.e. "native").
        origin_groups: dict[str, list[AccountIdentifier]] = {}
        for ident in live_identifiers:
            origin_key = (
                str(ident.merged_from_identity) if ident.merged_from_identity else identity_id
            )
            origin_groups.setdefault(origin_key, []).append(ident)

        # Also load RETIRED identifiers that were retired-on-collision from merged origins,
        # so we can resurrect them during unmerge.
        retired_result = await session.execute(
            select(AccountIdentifier).where(
                AccountIdentifier.identity_id == identity_id,
                AccountIdentifier.retired_at.is_not(None),
                AccountIdentifier.merged_from_identity.is_not(None),
            )
        )
        retired_collision_rows: list[AccountIdentifier] = list(retired_result.scalars().all())

        # --- Determine which origin group account belongs to ---
        # Re-derive live identifiers from the account's encrypted fields.
        from manifold.providers.types import AccountData as _AccountData

        account_data = _AccountData(
            provider_account_id=str(account.provider_account_id),
            account_type=str(account.account_type),
            currency=str(account.currency),
            display_name=account.display_name,
            iban=account.iban,
            sort_code=account.sort_code,
            account_number=account.account_number,
        )
        # provider_type hard-coded to "json" for HMAC — only the user_id + values
        # matter for matching (MULTI_CURRENCY_PROVIDERS is empty).
        account_id_rows = extract_identifiers(account_data, user_id, "json", secret_key=secret_key)
        account_hmacs: set[str] = {hmac_val for _, hmac_val, _ in account_id_rows}

        # Find the peel group: the origin whose value_hmacs intersect the account's hmacs.
        # If zero overlap, use the native group (the account accreted into this identity
        # without identifier evidence — e.g. manual merge of no-identifier accounts).
        peel_origin_key: str | None = None
        bridge_origins: set[str] = set()

        if account_hmacs:
            group_hit: dict[str, set[str]] = {}
            for origin_key, group_idents in origin_groups.items():
                group_hmacs = {g.value_hmac for g in group_idents}
                overlap = account_hmacs & group_hmacs
                if overlap:
                    group_hit[origin_key] = overlap

            if len(group_hit) == 1:
                peel_origin_key = next(iter(group_hit))
            elif len(group_hit) > 1:
                # Account straddles multiple groups → bridge account; stays with survivor.
                logger.info(
                    "unmerge_bridge_account_retained",
                    account_id=account_id,
                    identity_id=identity_id,
                    bridge_groups=list(group_hit.keys()),
                    user_id=user_id,
                )
                return (
                    "Account is a bridge across multiple groups and cannot be unmerged "
                    "without splitting evidence. It remains with the current identity."
                )

        if peel_origin_key is None:
            # No identifier overlap (zero-identifier account or no group hit).
            # Use a special sentinel to mean "mint fresh".
            peel_origin_key = "__native__"

        # --- Collect all accounts in the merged identity ---
        all_accounts_result = await session.execute(
            select(Account).where(Account.identity_id == identity_id, Account.user_id == user_id)
        )
        all_accounts: list[Account] = list(all_accounts_result.scalars().all())

        # Determine which accounts belong to the peel group and which stay.
        peel_accounts: list[Account] = []
        stay_accounts: list[Account] = []

        for acct in all_accounts:
            # Re-derive identifiers for this account (needs DEK context set by caller).
            acct_data = _AccountData(
                provider_account_id=str(acct.provider_account_id),
                account_type=str(acct.account_type),
                currency=str(acct.currency),
                display_name=acct.display_name,
                iban=acct.iban,
                sort_code=acct.sort_code,
                account_number=acct.account_number,
            )
            acct_hmacs: set[str] = {
                hv
                for _, hv, _ in extract_identifiers(
                    acct_data, user_id, "json", secret_key=secret_key
                )
            }

            if peel_origin_key == "__native__":
                # Special case: the target account goes to peel; all others stay.
                if str(acct.id) == account_id:
                    peel_accounts.append(acct)
                else:
                    stay_accounts.append(acct)
                continue

            group_hmacs = {g.value_hmac for g in origin_groups.get(peel_origin_key, [])}

            if not acct_hmacs:
                # Zero-identifier account — assign to stay unless it IS the target account.
                if str(acct.id) == account_id:
                    peel_accounts.append(acct)
                else:
                    stay_accounts.append(acct)
                continue

            overlap = acct_hmacs & group_hmacs
            other_group_overlap = acct_hmacs - group_hmacs

            if overlap and other_group_overlap:
                # Bridge account — stays with survivor.
                logger.info(
                    "unmerge_bridge_account_retained",
                    account_id=str(acct.id),
                    identity_id=identity_id,
                    user_id=user_id,
                )
                bridge_origins.add(str(acct.id))
                stay_accounts.append(acct)
            elif overlap:
                peel_accounts.append(acct)
            else:
                stay_accounts.append(acct)

        # --- Determine the resurrected identity for the peel group ---
        now = datetime.now(UTC)

        if peel_origin_key == "__native__" or peel_origin_key == identity_id:
            # Genuinely native group — mint a fresh identity.
            resurrected_id = _new_uuid()
            session.add(
                AccountIdentity(
                    id=resurrected_id,
                    user_id=user_id,
                    master_account_id=None,
                    origin="manual",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
        else:
            # Resurrect the tombstone: clear merged_into / merged_at.
            tombstone_result = await session.execute(
                select(AccountIdentity).where(AccountIdentity.id == peel_origin_key)
            )
            tombstone = tombstone_result.scalar_one_or_none()
            if tombstone is None:
                # Tombstone missing (shouldn't happen) — mint fresh.
                resurrected_id = _new_uuid()
                session.add(
                    AccountIdentity(
                        id=resurrected_id,
                        user_id=user_id,
                        master_account_id=None,
                        origin="manual",
                        created_at=now,
                        updated_at=now,
                    )
                )
                await session.flush()
            else:
                tombstone.merged_into = None
                tombstone.merged_at = None
                session.add(tombstone)
                resurrected_id = peel_origin_key
                await session.flush()

            # Re-point the peel group's live identifier rows back to the resurrected identity
            # and clear merged_from_identity for immediately-homed rows (their home is back).
            for ident in origin_groups.get(peel_origin_key, []):
                ident.identity_id = resurrected_id
                # Only clear merged_from_identity if it points directly to this peel_origin_key
                # (i.e. the identifier was immediately homed there; deeper provenance stays).
                if str(ident.merged_from_identity) == peel_origin_key:
                    ident.merged_from_identity = None
                session.add(ident)

            # Resurrect retired-on-collision rows that originated from this peel group.
            for ret_row in retired_collision_rows:
                if str(ret_row.merged_from_identity) == peel_origin_key:
                    ret_row.retired_at = None
                    ret_row.identity_id = resurrected_id
                    ret_row.merged_from_identity = None
                    session.add(ret_row)

            await session.flush()

        # --- Re-point peel accounts to resurrected identity ---
        for acct in peel_accounts:
            acct.identity_id = resurrected_id
            session.add(acct)
        await session.flush()

        # --- Recompute master_account_id for both identities ---
        await _recompute_master(session, resurrected_id)
        await _recompute_master(session, identity_id)
        await session.flush()

        # --- Write do_not_merge between peel and stay accounts ---
        peel_ids = [str(a.id) for a in peel_accounts]
        stay_ids = [str(a.id) for a in stay_accounts]

        for pid in peel_ids:
            for sid in stay_ids:
                # Delete any contradicting 'same' first (log superseded).
                a_can = min(pid, sid)
                b_can = max(pid, sid)
                same_result = await session.execute(
                    select(AccountIdentityAssertion).where(
                        AccountIdentityAssertion.user_id == user_id,
                        AccountIdentityAssertion.kind == "same",
                        AccountIdentityAssertion.account_a_id == a_can,
                        AccountIdentityAssertion.account_b_id == b_can,
                    )
                )
                for same_row in same_result.scalars().all():
                    logger.info(
                        "assertion_superseded",
                        superseded_kind="same",
                        by_kind="do_not_merge",
                        account_a=a_can,
                        account_b=b_can,
                        user_id=user_id,
                    )
                    await session.delete(same_row)
                await session.flush()

                await _write_assertion(session, user_id, "do_not_merge", pid, sid)

        logger.info(
            "identity_unmerge_complete",
            original_identity_id=identity_id,
            resurrected_identity_id=resurrected_id,
            peel_accounts=peel_ids,
            stay_accounts=stay_ids,
            user_id=user_id,
        )

        caveat = (
            "Unmerge is best-effort. Identifiers accreted while merged, "
            "and any Phase-5 transaction-dedup decisions, may not fully re-split. "
            "Review balances after unmerge."
        )
        return caveat


# ---------------------------------------------------------------------------
# Phase 6 — Suggestions
# ---------------------------------------------------------------------------


def _name_similarity(a: str | None, b: str | None) -> float:
    """Simple character-overlap similarity between two display names."""
    if not a or not b:
        return 0.0
    a = a.lower().strip()
    b = b.lower().strip()
    if a == b:
        return 1.0

    # Jaccard over trigrams.
    def trigrams(s: str) -> set[str]:
        return {s[i : i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}

    tg_a = trigrams(a)
    tg_b = trigrams(b)
    union = tg_a | tg_b
    if not union:
        return 0.0
    return len(tg_a & tg_b) / len(union)


async def suggest_merges(
    session: AsyncSession,
    user_id: str,
) -> list[dict]:
    """Score candidate account pairs for a potential manual merge (§13.6).

    Rules:
    - Only pairs within the same user.
    - Require matching provider_id (provider institution) — fetched from the
      ProviderConnection.  Today all connections share 'json' or 'truelayer';
      same provider_type is used as a proxy for same institution.
    - Score on display_name similarity (trigram Jaccard) + account_type match
      + currency match + provider_type match.
    - Threshold: combined score ≥ 0.8.
    - Never suggest a pair that has a do_not_merge assertion.
    - Never mutate any identity.
    - Returns list of {account_a_id, account_b_id, score, reasons}.
    """
    from manifold.models.provider_connection import ProviderConnection

    # Load all accounts + their connection provider_type for this user.
    acct_result = await session.execute(
        select(Account, ProviderConnection.provider_type)
        .join(
            ProviderConnection,
            Account.provider_connection_id == ProviderConnection.id,
        )
        .where(Account.user_id == user_id, Account.is_active == True)  # noqa: E712
    )
    rows = acct_result.all()

    if len(rows) < 2:
        return []

    # Load all do_not_merge assertions for this user (for fast suppression).
    dnm_result = await session.execute(
        select(AccountIdentityAssertion).where(
            AccountIdentityAssertion.user_id == user_id,
            AccountIdentityAssertion.kind == "do_not_merge",
        )
    )
    dnm_pairs: set[tuple[str, str]] = set()
    for assertion in dnm_result.scalars().all():
        dnm_pairs.add((str(assertion.account_a_id), str(assertion.account_b_id)))

    suggestions: list[dict] = []

    for i, (acct_i, pt_i) in enumerate(rows):
        for acct_j, pt_j in rows[i + 1 :]:
            a_id = min(str(acct_i.id), str(acct_j.id))
            b_id = max(str(acct_i.id), str(acct_j.id))

            # Skip do_not_merge pairs.
            if (a_id, b_id) in dnm_pairs:
                continue

            # Skip pairs already sharing an identity (already merged).
            if (
                acct_i.identity_id is not None
                and acct_j.identity_id is not None
                and acct_i.identity_id == acct_j.identity_id
            ):
                continue

            # Score components.
            reasons: list[str] = []
            score = 0.0

            # Provider institution must match (required gate, not scored).
            if pt_i != pt_j:
                continue

            # display_name similarity (weight 0.5).
            name_sim = _name_similarity(acct_i.display_name, acct_j.display_name)
            score += name_sim * 0.5
            if name_sim >= 0.7:
                reasons.append(f"similar_name ({name_sim:.2f})")

            # account_type match (weight 0.2).
            if acct_i.account_type and acct_j.account_type:
                if acct_i.account_type == acct_j.account_type:
                    score += 0.2
                    reasons.append("same_account_type")

            # currency match (weight 0.2).
            if acct_i.currency and acct_j.currency:
                if acct_i.currency == acct_j.currency:
                    score += 0.2
                    reasons.append("same_currency")

            # provider_type match (weight 0.1 — already gated above).
            score += 0.1
            reasons.append("same_provider")

            if score >= 0.8:
                suggestions.append(
                    {
                        "account_a_id": a_id,
                        "account_b_id": b_id,
                        "score": round(score, 4),
                        "reasons": reasons,
                    }
                )

    # Sort by score descending.
    suggestions.sort(key=lambda s: s["score"], reverse=True)
    return suggestions


__all__ = [
    "CURRENCY_SENTINEL",
    "IDENTITY_AGGREGATION_ENABLED",
    "MULTI_CURRENCY_PROVIDERS",
    "IdentifierRow",
    "IdentityMergeService",
    "IdentityUnmergeService",
    "extract_identifiers",
    "normalize_aba",
    "normalize_currency",
    "normalize_iban",
    "normalize_scan",
    "suggest_merges",
    "_merge_identities",
    "resolve_account_identity",
]
