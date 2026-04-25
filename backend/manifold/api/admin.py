from fastapi import APIRouter, Depends

from manifold.api.deps import require_superadmin
from manifold.config import settings
from manifold.models.user import User
from manifold.tasks.alarms import evaluate_all_alarms
from manifold.tasks.maintenance import detect_recurrence

router = APIRouter()


@router.get("/jobs")
async def list_jobs(_: User = Depends(require_superadmin)) -> dict[str, list[dict[str, str]]]:
    return {
        "jobs": [
            {"name": "sync_all_connections", "cron": settings.sync_cron},
            {"name": "evaluate_all_alarms", "cron": settings.alarm_eval_cron},
            {"name": "detect_recurrence", "cron": settings.recurrence_detect_cron},
            {"name": "run_data_retention_jobs", "cron": settings.cleanup_cron},
        ]
    }


@router.post("/jobs/detect-recurrence/trigger", status_code=202)
async def trigger_detect_recurrence(_: User = Depends(require_superadmin)) -> dict[str, str]:
    await detect_recurrence.kiq()
    return {"status": "queued"}


@router.post("/jobs/evaluate-alarms/trigger", status_code=202)
async def trigger_evaluate_alarms(_: User = Depends(require_superadmin)) -> dict[str, str]:
    await evaluate_all_alarms.kiq()
    return {"status": "queued"}
