from fastapi import APIRouter, Depends

from manifold.api.deps import get_current_user
from manifold.config import settings
from manifold.models.user import User
from manifold.schemas.settings import SettingsResponse

router = APIRouter()


@router.get("/settings", operation_id="getSettings", response_model=SettingsResponse)
async def get_settings(current_user: User = Depends(get_current_user)) -> SettingsResponse:
    return {
        "app_env": settings.app_env,
        "sync_cron": settings.sync_cron,
        "alarm_eval_cron": settings.alarm_eval_cron,
        "recurrence_detect_cron": settings.recurrence_detect_cron,
        "cleanup_cron": settings.cleanup_cron,
        "log_level": settings.log_level,
        "access_token_expire_minutes": settings.access_token_expire_minutes,
        "refresh_token_expire_days": settings.refresh_token_expire_days,
    }
