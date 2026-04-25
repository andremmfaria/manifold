from __future__ import annotations

from manifold.database import db_session
from manifold.domain.sync_engine import SyncEngine
from manifold.tasks.broker import broker


@broker.task(task_name="sync_all_connections", labels={"queue": "sync"})
async def sync_all_connections() -> list[str]:
    runs = await SyncEngine().sync_all_active()
    return [str(run.id) for run in runs]


@broker.task(task_name="sync_connection", labels={"queue": "manual"})
async def sync_connection(connection_id: str, sync_run_id: str | None = None) -> str:
    async with db_session() as session:
        run = await SyncEngine(session).sync_connection_by_id(connection_id, sync_run_id)
        return str(run.id)
