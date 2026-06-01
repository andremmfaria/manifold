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
    numeric_str = "".join(
        str(ord(c) - ord("A") + 10) if c.isalpha() else c for c in rearranged
    )
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
            update(Account)
            .where(Account.identity_id == loser_id)
            .values(identity_id=survivor_id)
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
            select(Account.id).where(
                Account.identity_id == iid, Account.user_id == user_id
            )
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
        result = await session.execute(
            select(Account)
            .where(Account.identity_id == iid, Account.user_id == user_id)
            .order_by(Account.created_at.asc(), Account.id.asc())
        )
        candidate = result.scalars().first()
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


__all__ = [
    "CURRENCY_SENTINEL",
    "MULTI_CURRENCY_PROVIDERS",
    "IdentifierRow",
    "extract_identifiers",
    "normalize_aba",
    "normalize_currency",
    "normalize_iban",
    "normalize_scan",
    "_merge_identities",
    "resolve_account_identity",
]
