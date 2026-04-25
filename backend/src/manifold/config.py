from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "production"
    secret_key: str = Field(default="dev-secret-key")
    allowed_origins: list[str] = ["http://localhost:5173"]
    timezone: str = "UTC"
    frontend_url: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_format: str = "json"

    database_url: str = "sqlite+aiosqlite:///data/manifold.db"

    admin_username: str = ""
    admin_password: str = ""

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    truelayer_client_id: str = ""
    truelayer_client_secret: str = ""
    truelayer_redirect_uri: str = ""
    truelayer_sandbox: bool = False

    redis_url: str = "redis://manifold-redis:6379/0"
    taskiq_result_ttl: int = 3600

    sync_cron: str = "0 * * * *"
    alarm_eval_cron: str = "*/5 * * * *"
    recurrence_detect_cron: str = "0 3 * * *"
    cleanup_cron: str = "0 4 * * *"

    sync_run_retention_days: int = 90
    notification_delivery_retention_days: int = 90
    alarm_evaluation_retention_days: int = 30
    event_retention_days: int = 365

    db_pool_size: int = 3
    db_pool_max_overflow: int = 2
    db_pool_timeout: int = 30

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    slack_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    system_notifier_id: str = ""

    @property
    def secure_cookies(self) -> bool:
        return self.app_env != "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
