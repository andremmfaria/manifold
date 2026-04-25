from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_retention_task_importable() -> None:
    from manifold.tasks.maintenance import detect_recurrence, run_data_retention_jobs

    assert callable(run_data_retention_jobs)
    assert callable(detect_recurrence)


def test_retention_settings_have_defaults() -> None:
    from manifold.config import settings

    assert settings.sync_run_retention_days > 0
    assert settings.notification_delivery_retention_days > 0
    assert settings.alarm_evaluation_retention_days > 0
    assert settings.event_retention_days > 0
