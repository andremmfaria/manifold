from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api.deps import get_current_user, get_session, require_superadmin
from manifold.domain.users import create_user_record, deactivate_user
from manifold.models.user import AccountAccess, User
from manifold.schemas.users import (
    AccessGrantCreateRequest,
    AccessGrantResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter()


def _serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )


@router.get("", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> list[UserResponse]:
    result = await session.execute(select(User))
    return [_serialize_user(user) for user in result.scalars().all()]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    payload: UserCreateRequest,
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await create_user_record(
        username=payload.username,
        password=payload.password,
        role=payload.role,
        email=payload.email,
        session=session,
    )
    return _serialize_user(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return _serialize_user(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    if payload.is_active is False:
        await deactivate_user(session, user)
        await session.refresh(user)
        return _serialize_user(user)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role is not None:
        user.role = payload.role
    if payload.must_change_password is not None:
        user.must_change_password = payload.must_change_password
    await session.commit()
    await session.refresh(user)
    return _serialize_user(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    await deactivate_user(session, user)
    return Response(status_code=204)


@router.get("/me/access", response_model=list[AccessGrantResponse])
async def list_access_grants(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AccessGrantResponse]:
    result = await session.execute(
        select(AccountAccess).where(AccountAccess.owner_user_id == current_user.id)
    )
    grants = result.scalars().all()
    return [
        AccessGrantResponse(
            id=str(item.id),
            owner_user_id=str(item.owner_user_id),
            grantee_user_id=str(item.grantee_user_id),
            role=item.role,
            granted_at=item.granted_at.isoformat(),
            granted_by=str(item.granted_by) if item.granted_by else None,
        )
        for item in grants
    ]


@router.post("/me/access", response_model=AccessGrantResponse, status_code=201)
async def create_access_grant(
    payload: AccessGrantCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccessGrantResponse:
    if payload.grantee_user_id == str(current_user.id):
        raise HTTPException(status_code=422, detail={"error": "self_grant_forbidden"})
    grant = AccountAccess(
        owner_user_id=current_user.id,
        grantee_user_id=payload.grantee_user_id,
        role=payload.role,
        granted_by=current_user.id,
    )
    session.add(grant)
    await session.commit()
    await session.refresh(grant)
    return AccessGrantResponse(
        id=str(grant.id),
        owner_user_id=str(grant.owner_user_id),
        grantee_user_id=str(grant.grantee_user_id),
        role=grant.role,
        granted_at=grant.granted_at.isoformat(),
        granted_by=str(grant.granted_by) if grant.granted_by else None,
    )


@router.delete("/me/access/{grant_id}", status_code=204)
async def delete_access_grant(
    grant_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    grant = await session.get(AccountAccess, grant_id)
    if grant is None or str(grant.owner_user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    await session.delete(grant)
    await session.commit()
    return Response(status_code=204)
