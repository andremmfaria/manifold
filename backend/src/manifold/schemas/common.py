from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StatusResponse(SchemaModel):
    status: str


class DeletedResponse(SchemaModel):
    deleted: bool


class HealthResponse(SchemaModel):
    status: str
