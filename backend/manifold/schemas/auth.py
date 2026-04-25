from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: str
    username: str
    role: str
    mustChangePassword: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SessionResponse(BaseModel):
    id: str
    device_label: str | None = None
    user_agent: str | None = None
    ip_first: str | None = None
    ip_last: str | None = None
    last_seen_at: str
    created_at: str
    revoked_at: str | None = None
