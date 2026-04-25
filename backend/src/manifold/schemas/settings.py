from __future__ import annotations

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class SettingsResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    app_env: str
    sync_cron: str
    alarm_eval_cron: str
    recurrence_detect_cron: str
    cleanup_cron: str
    log_level: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
