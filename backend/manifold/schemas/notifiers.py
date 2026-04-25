from pydantic import BaseModel


class NotifierCreateRequest(BaseModel):
    name: str
    type: str
    config: dict
    is_enabled: bool = True


class NotifierUpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
