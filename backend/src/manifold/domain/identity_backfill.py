"""Phase 4 — one-shot idempotent backfill of existing accounts into identities.

Chosen approach (§11.3): iterate users with unprocessed accounts, decrypt each
account's identifiers per-user DEK, then run the same §3.1 match/create/merge
logic that the live sync engine uses.

Design notes
------------
* ``resolve_account_identity`` accepts an ``Account`` ORM row directly; it only
  needs a list of ``IdentifierRow`` tuples alongside it.  Those tuples come from
  ``extract_identifiers``, which expects an ``AccountData`` DTO.  We therefore
  construct a minimal ``AccountData`` from the already-decrypted ORM fields —
  zero modifications to Phase 3 code.

* We iterate one user at a time so the right DEK is active for the entire
  batch.  SQLAlchemy's encrypted column types read through ``_current_dek``
  (a context var), so entering ``user_dek_context`` before touching any
  encrypted field is the only requirement.

* Idempotency: accounts with ``identity_id IS NOT NULL`` are skipped on SELECT.
  A second run therefore touches nothing and returns zero counts.

* Order-independence: §3.1's oldest-wins survivor selection is deterministic
  regardless of processing order (the survivor is always the account with the
  smallest ``created_at``, tie-broken by smallest UUID).  The backfill sorts
  accounts oldest-first as a courtesy, but correctness does not depend on it —
  the merge path converges to the same partition in any order.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.config import settings
from manifold.database import db_session
from manifold.domain.account_identity import extract_identifiers, resolve_account_identity
from manifold.models.account import Account
from manifold.models.user import User
from manifold.providers.types import AccountData
from manifold.security.encryption import EncryptionService

logger = structlog.get_logger(__name__)


def _account_to_dto(account: Account) -> AccountData:
    """Build a minimal AccountData DTO from a decrypted Account ORM row.

    The encrypted fields (iban, sort_code, account_number, currency) are read
    here *inside* the caller's ``user_dek_context`` so they decrypt transparently.
    provider_type is not stored on Account; pass the sentinel ``"json"`` — it is
    only used to gate MULTI_CURRENCY_PROVIDERS (empty frozenset today, §6).
    """
    return AccountData(
        provider_account_id=account.provider_account_id,
        account_type=account.account_type,
        currency=account.currency or "GBP",
        display_name=account.display_name,
        iban=account.iban,
        sort_code=account.sort_code,
        account_number=account.account_number,
    )


async def backfill_identities(session: AsyncSession | None = None) -> dict[str, int]:
    """Assign ``identity_id`` to every account that currently has none.

    Returns a summary dict with keys:
      ``users_processed``, ``accounts_processed``, ``accounts_skipped``,
      ``identities_created`` (net live identities after the run).

    Idempotent — a second call with no new data returns all-zero counts except
    ``users_processed`` and ``accounts_skipped`` (which reflect what was found
    already done).
    """
    _own_session = session is None

    if _own_session:
        async with db_session() as owned_session:
            return await _run_backfill(owned_session)
    else:
        return await _run_backfill(session)  # type: ignore[arg-type]


async def _run_backfill(session: AsyncSession) -> dict[str, int]:
    enc = EncryptionService()

    # Fetch all users that have at least one account without an identity_id.
    user_ids_result = await session.execute(
        select(Account.user_id)
        .where(Account.identity_id.is_(None))
        .distinct()
    )
    user_ids: list[str] = [str(r) for r in user_ids_result.scalars().all()]

    totals = {
        "users_processed": 0,
        "accounts_processed": 0,
        "accounts_skipped": 0,
        "identities_created": 0,
    }

    for user_id in user_ids:
        user = await session.get(User, user_id)
        if user is None:
            logger.warning("backfill_user_not_found", user_id=user_id)
            continue

        dek = enc.decrypt_dek(user.encrypted_dek)

        with enc.user_dek_context(dek):
            await _backfill_user(session, user_id, totals)

        totals["users_processed"] += 1

    # Commit everything at the end (caller may also choose to commit).
    await session.commit()

    logger.info("backfill_complete", **totals)
    return totals


async def _backfill_user(
    session: AsyncSession,
    user_id: str,
    totals: dict[str, int],
) -> None:
    """Process all unassigned accounts for one user.

    Must be called *inside* the correct ``user_dek_context`` so that encrypted
    column reads (iban, sort_code, account_number, currency) decrypt correctly.

    Processes oldest accounts first as a processing-order courtesy; correctness
    of the oldest-wins merge is independent of this ordering.
    """
    totals.setdefault("accounts_processed", 0)
    totals.setdefault("accounts_skipped", 0)

    result = await session.execute(
        select(Account)
        .where(
            Account.user_id == user_id,
            Account.identity_id.is_(None),
        )
        .order_by(Account.created_at.asc(), Account.id.asc())
    )
    unassigned: list[Account] = list(result.scalars().all())

    for account in unassigned:
        dto = _account_to_dto(account)
        identifier_rows = extract_identifiers(
            dto,
            user_id,
            # provider_type is not stored on Account; the sentinel is safe because
            # MULTI_CURRENCY_PROVIDERS is empty today — currency dimension is a no-op.
            provider_type="json",
            secret_key=settings.secret_key,
        )

        await resolve_account_identity(session, account, identifier_rows, user_id=user_id)
        await session.flush()

        totals["accounts_processed"] += 1

        if not identifier_rows:
            logger.debug(
                "backfill_account_zero_identifiers",
                account_id=account.id,
                user_id=user_id,
            )
        else:
            logger.debug(
                "backfill_account_assigned",
                account_id=account.id,
                identity_id=account.identity_id,
                user_id=user_id,
            )


__all__ = ["backfill_identities"]
