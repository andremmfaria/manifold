from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.models.user import AccountAccess, User


async def get_accessible_scope(current_user: User, session: AsyncSession) -> set[str]:
    scope = {str(current_user.id)}
    result = await session.execute(
        select(AccountAccess.owner_user_id).where(AccountAccess.grantee_user_id == current_user.id)
    )
    scope.update(str(user_id) for user_id in result.scalars().all())
    return scope


def resolve_owner_user_id(resource: object) -> str | None:
    for attr in ("user_id", "owner_user_id"):
        value = getattr(resource, attr, None)
        if value is not None:
            return str(value)
    return None
