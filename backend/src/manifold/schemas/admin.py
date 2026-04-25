from __future__ import annotations

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class JobInfo(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    cron: str


class JobListResponse(SchemaModel):
    jobs: list[JobInfo]


class TriggerResponse(SchemaModel):
    status: str
