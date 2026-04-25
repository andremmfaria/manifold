from pydantic import BaseModel


class ConnectionCreateRequest(BaseModel):
    provider_type: str
    display_name: str | None = None
    credentials: dict | None = None
    config: dict | None = None


class ConnectionUpdateRequest(BaseModel):
    display_name: str | None = None
    status: str | None = None
    auth_status: str | None = None
    credentials: dict | None = None
    config: dict | None = None
