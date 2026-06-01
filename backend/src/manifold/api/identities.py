from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.account_identity import (
    IDENTITY_AGGREGATION_ENABLED,
    IdentityMergeService,
    IdentityUnmergeService,
    _write_assertion,
    suggest_merges,
)
from manifold.domain.ownership import get_accessible_scope
from manifold.models.account import Account
from manifold.models.account_identity import AccountIdentity
from manifold.models.user import User
from manifold.schemas.identities import (
    DismissSuggestionRequest,
    DismissSuggestionResponse,
    IdentityResponse,
    MergeRequest,
    MergeResponse,
    SuggestionItem,
    SuggestionsResponse,
    UnmergeRequest,
    UnmergeResponse,
)

router = APIRouter()

_merge_service = IdentityMergeService()
_unmerge_service = IdentityUnmergeService()


async def _identity_or_404(session: AsyncSession, identity_id: str) -> AccountIdentity:
    result = await session.execute(
        select(AccountIdentity).where(AccountIdentity.id == parse_uuid(identity_id))
    )
    identity = result.scalar_one_or_none()
    if identity is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return identity


async def _check_identity_access(
    identity: AccountIdentity,
    current_user: User,
    session: AsyncSession,
) -> None:
    scope = await get_accessible_scope(current_user, session)
    if str(identity.user_id) not in scope:
        # 404-not-403 to avoid leaking existence of cross-user resources.
        raise HTTPException(status_code=404, detail={"error": "not_found"})


def _serialize_member(acct: Account) -> dict:
    return {
        "id": str(acct.id),
        "user_id": str(acct.user_id),
        "provider_account_id": acct.provider_account_id,
        "account_type": acct.account_type,
        "currency": acct.currency,
        "display_name": acct.display_name,
        "identity_id": str(acct.identity_id) if acct.identity_id else None,
        "created_at": acct.created_at.isoformat(),
    }


@router.post("/merge", operation_id="mergeIdentities", response_model=MergeResponse)
async def merge_identities(
    body: MergeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MergeResponse:
    """Merge ≥2 accounts into one identity (manual user action, §13.3).

    All accounts must belong to the authenticated user (or a user in their
    accessible scope).  Uses the oldest account as the survivor (master rule).
    """
    # Verify all accounts are accessible to the current user.
    scope = await get_accessible_scope(current_user, session)

    # Determine owner user_id from the first account (all must share one owner).
    # Validate each account exists and belongs to scope.
    owner_user_id: str | None = None
    for aid in body.account_ids:
        result = await session.execute(
            select(Account.__table__.c.id, Account.__table__.c.user_id).where(
                Account.__table__.c.id == parse_uuid(aid)
            )
        )
        row = result.one_or_none()
        if row is None or str(row.user_id) not in scope:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        if owner_user_id is None:
            owner_user_id = str(row.user_id)
        elif owner_user_id != str(row.user_id):
            raise HTTPException(
                status_code=422, detail={"error": "accounts_must_share_owner"}
            )

    if owner_user_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _do_merge() -> str:
        survivor_id = await _merge_service.merge(
            session=session,
            user_id=owner_user_id,
            account_ids=body.account_ids,
        )
        await session.commit()
        return survivor_id

    survivor_id = await with_user_dek(session, owner_user_id, _do_merge)
    return MergeResponse(identity_id=survivor_id, account_ids=body.account_ids)


@router.post("/unmerge", operation_id="unmergeIdentity", response_model=UnmergeResponse)
async def unmerge_identity(
    body: UnmergeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UnmergeResponse:
    """Peel one pre-merge origin group back out of a merged identity (§13.4).

    The account identified by account_id is peeled to its origin identity
    (resurrected tombstone) or a new identity if genuinely native.
    Bridge accounts spanning multiple groups stay with the survivor.
    """
    scope = await get_accessible_scope(current_user, session)

    result = await session.execute(
        select(Account.__table__.c.id, Account.__table__.c.user_id).where(
            Account.__table__.c.id == parse_uuid(body.account_id)
        )
    )
    row = result.one_or_none()
    if row is None or str(row.user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    owner_user_id = str(row.user_id)

    async def _do_unmerge() -> str:
        from manifold.config import settings

        caveat = await _unmerge_service.unmerge(
            session=session,
            user_id=owner_user_id,
            account_id=body.account_id,
            secret_key=settings.secret_key,
        )
        await session.commit()
        return caveat

    caveat = await with_user_dek(session, owner_user_id, _do_unmerge)
    return UnmergeResponse(caveat=caveat)


@router.get(
    "/suggestions",
    operation_id="getIdentitySuggestions",
    response_model=SuggestionsResponse,
)
async def get_suggestions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuggestionsResponse:
    """Return weak-signal merge suggestions for the current user (§13.6).

    Read-only — never mutates any identity.  Suppresses do_not_merge pairs.
    Requires Phase 5 for read-time aggregation; returns aggregated=False until
    IDENTITY_AGGREGATION_ENABLED is True.
    """
    # Suggestions are personal (not scope-expanded) — only the user's own accounts.
    async def _get() -> list[dict]:
        return await suggest_merges(session, str(current_user.id))

    raw = await with_user_dek(session, str(current_user.id), _get)
    items = [SuggestionItem(**s) for s in raw]
    return SuggestionsResponse(
        suggestions=items,
        aggregated=IDENTITY_AGGREGATION_ENABLED,
    )


@router.post(
    "/suggestions/dismiss",
    operation_id="dismissSuggestion",
    response_model=DismissSuggestionResponse,
)
async def dismiss_suggestion(
    body: DismissSuggestionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DismissSuggestionResponse:
    """Dismiss a suggestion for account_a_id / account_b_id.

    Optionally writes a do_not_merge assertion (default True) so the pair
    does not resurface in suggestions.
    """
    scope = await get_accessible_scope(current_user, session)

    for aid in (body.account_a_id, body.account_b_id):
        result = await session.execute(
            select(Account.__table__.c.id, Account.__table__.c.user_id).where(
                Account.__table__.c.id == parse_uuid(aid)
            )
        )
        row = result.one_or_none()
        if row is None or str(row.user_id) not in scope:
            raise HTTPException(status_code=404, detail={"error": "not_found"})

    if body.write_do_not_merge:
        # All accounts must share one owner.
        result_a = await session.execute(
            select(Account.__table__.c.user_id).where(
                Account.__table__.c.id == parse_uuid(body.account_a_id)
            )
        )
        owner_id = str(result_a.scalar_one())
        await _write_assertion(
            session, owner_id, "do_not_merge", body.account_a_id, body.account_b_id
        )
        await session.commit()

    return DismissSuggestionResponse(dismissed=True)


@router.get("/{identity_id}", operation_id="getIdentity", response_model=IdentityResponse)
async def get_identity(
    identity_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IdentityResponse:
    """Return an identity and its member accounts."""
    identity = await _identity_or_404(session, identity_id)
    await _check_identity_access(identity, current_user, session)

    async def _get() -> dict:
        members_result = await session.execute(
            select(Account).where(Account.identity_id == identity.id)
        )
        members = members_result.scalars().all()
        return {
            "id": str(identity.id),
            "user_id": str(identity.user_id),
            "origin": identity.origin,
            "master_account_id": str(identity.master_account_id)
            if identity.master_account_id
            else None,
            "merged_into": str(identity.merged_into) if identity.merged_into else None,
            "merged_at": identity.merged_at.isoformat() if identity.merged_at else None,
            "created_at": identity.created_at.isoformat(),
            "updated_at": identity.updated_at.isoformat(),
            "members": [_serialize_member(m) for m in members],
            "aggregated": IDENTITY_AGGREGATION_ENABLED,
        }

    return await with_user_dek(session, str(identity.user_id), _get)


__all__ = ["router"]
