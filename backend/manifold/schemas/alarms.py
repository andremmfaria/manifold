from pydantic import BaseModel, Field, field_validator


class AlarmCreateRequest(BaseModel):
    name: str
    condition: dict
    account_ids: list[str] = Field(min_length=1)
    notifier_ids: list[str] = Field(default_factory=list)
    repeat_count: int = 1
    for_duration_minutes: int = 0
    cooldown_minutes: int = 60
    notify_on_resolve: bool = False


class AlarmUpdateRequest(BaseModel):
    name: str | None = None
    condition: dict | None = None
    account_ids: list[str] | None = None
    notifier_ids: list[str] | None = None
    repeat_count: int | None = None
    for_duration_minutes: int | None = None
    cooldown_minutes: int | None = None
    notify_on_resolve: bool | None = None
    status: str | None = None

    @field_validator("account_ids")
    @classmethod
    def validate_account_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) == 0:
            raise ValueError("account_ids must not be empty")
        return value


class MuteRequest(BaseModel):
    mute_until: str


class AlarmResponse(BaseModel):
    id: str
    user_id: str
    name: str
    condition: dict | None
    condition_version: int
    status: str
    repeat_count: int
    for_duration_minutes: int
    cooldown_minutes: int
    notify_on_resolve: bool
    account_ids: list[str]
    notifier_ids: list[str]
    state: str
    mute_until: str | None = None
    last_evaluated_at: str | None = None
    last_fired_at: str | None = None
    created_at: str
    updated_at: str


class AlarmListResponse(BaseModel):
    items: list[AlarmResponse]
    total: int
    page: int
    page_size: int


class AlarmEvaluationHistoryItem(BaseModel):
    id: str
    evaluated_at: str
    result: bool
    previous_state: str | None = None
    new_state: str | None = None
    explanation: str | None = None
    created_at: str


class AlarmEvaluationHistoryResponse(BaseModel):
    items: list[AlarmEvaluationHistoryItem]
    total: int
    page: int
    page_size: int


class AlarmFiringEventItem(BaseModel):
    id: str
    alarm_id: str
    fired_at: str | None = None
    resolved_at: str | None = None
    explanation: str | None = None
    notifications_sent: int
    created_at: str


class AlarmFiringEventResponse(BaseModel):
    items: list[AlarmFiringEventItem]
    total: int
    page: int
    page_size: int
