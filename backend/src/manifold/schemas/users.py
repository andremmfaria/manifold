from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str
    email: str | None = None


class UserUpdateRequest(BaseModel):
    is_active: bool | None = None
    role: str | None = None
    must_change_password: bool | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None = None
    role: str
    is_active: bool
    must_change_password: bool


class AccessGrantCreateRequest(BaseModel):
    grantee_user_id: str
    role: str


class AccessGrantResponse(BaseModel):
    id: str
    owner_user_id: str
    grantee_user_id: str
    role: str
    granted_at: str
    granted_by: str | None = None
