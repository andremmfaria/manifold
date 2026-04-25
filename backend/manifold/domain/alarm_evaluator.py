from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.models.account import Account
from manifold.models.alarm import (
    AlarmAccountAssignment,
    AlarmDefinition,
    AlarmEvaluationResult,
    AlarmFiringEvent,
    AlarmState,
)
from manifold.models.balance import Balance
from manifold.models.provider_connection import ProviderConnection
from manifold.models.sync_run import SyncRun
from manifold.models.user import User
from manifold.security.encryption import EncryptionService


class AlarmEvaluatorService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def evaluate_all_active(self) -> None:
        """Evaluate all active alarm definitions. Called by background task."""
        result = await self._session.execute(
            select(AlarmDefinition.__table__.c.id, AlarmDefinition.__table__.c.user_id).where(
                AlarmDefinition.__table__.c.status == "active"
            )
        )
        alarm_ids_by_user: dict[str, list[str]] = defaultdict(list)
        for alarm_id, user_id in result.all():
            alarm_ids_by_user[str(user_id)].append(str(alarm_id))

        for user_id, alarm_ids in alarm_ids_by_user.items():
            await self._evaluate_user_alarms(user_id, alarm_ids)

    async def _evaluate_user_alarms(self, user_id: str, alarm_ids: list[str]) -> None:
        owner = await self._session.get(User, user_id)
        if owner is None:
            return
        dek = EncryptionService().decrypt_dek(owner.encrypted_dek)
        with EncryptionService().user_dek_context(dek):
            alarms = await self._load_alarms(user_id, alarm_ids)
            for alarm in alarms:
                await self._evaluate_alarm(alarm)

    async def _load_alarms(self, user_id: str, alarm_ids: list[str]) -> list[AlarmDefinition]:
        result = await self._session.execute(
            select(AlarmDefinition)
            .where(AlarmDefinition.user_id == user_id)
            .where(AlarmDefinition.id.in_(alarm_ids))
            .where(AlarmDefinition.status == "active")
            .order_by(AlarmDefinition.created_at.asc())
        )
        return list(result.scalars().all())

    async def _evaluate_alarm(self, alarm: AlarmDefinition) -> None:
        from manifold.alarm_engine.evaluator import AlarmEvaluator
        from manifold.alarm_engine.explainer import AlarmExplainer
        from manifold.alarm_engine.state_machine import AlarmStateMachine
        from manifold.tasks.notifications import dispatch_alarm_notifications

        now = datetime.now(UTC)
        assignment_ids = await self._load_assignment_ids(str(alarm.id))
        evaluations = []
        evaluator = AlarmEvaluator()
        explainer = AlarmExplainer()

        for account_id in assignment_ids:
            account = await self._session.get(Account, account_id)
            if account is None:
                continue
            context = await self._build_context(account)
            result, _ = evaluator.evaluate(dict(alarm.condition or {}), context)
            explanation = explainer.explain(dict(alarm.condition or {}), context, result)
            evaluations.append(
                {
                    "account_id": str(account.id),
                    "result": result,
                    "context": context,
                    "explanation": explanation,
                }
            )

        aggregate = self._aggregate_evaluations(evaluations)
        current_state = await self._load_current_state(str(alarm.id))
        new_state, should_notify = AlarmStateMachine().transition(
            alarm,
            current_state,
            aggregate["result"],
            now,
        )

        evaluation_row = AlarmEvaluationResult(
            alarm_id=str(alarm.id),
            evaluated_at=now,
            result=bool(aggregate["result"]),
            previous_state=current_state.state if current_state is not None else None,
            new_state=new_state,
            condition_version=alarm.condition_version,
            context_snapshot=self._serialize_json(aggregate["context_snapshot"]),
            explanation=str(aggregate["explanation"]),
        )
        self._session.add(evaluation_row)

        state = current_state or AlarmState(alarm_id=str(alarm.id), state="ok")
        if current_state is None:
            self._session.add(state)
        self._apply_state_update(
            state=state,
            previous_state=current_state.state if current_state is not None else "ok",
            new_state=new_state,
            eval_result=bool(aggregate["result"]),
            alarm=alarm,
            now=now,
            should_notify=should_notify,
        )

        if should_notify:
            firing_event = AlarmFiringEvent(
                alarm_id=str(alarm.id),
                fired_at=now if new_state == "firing" else state.last_fired_at,
                resolved_at=now if new_state == "resolved" else None,
                explanation=str(aggregate["explanation"]),
                condition_snapshot=self._serialize_json(dict(alarm.condition or {})),
                context_snapshot=self._serialize_json(aggregate["context_snapshot"]),
            )
            self._session.add(firing_event)
            await self._session.flush()
            await dispatch_alarm_notifications.kiq(alarm_firing_event_id=str(firing_event.id))

        await self._session.commit()

    async def _load_assignment_ids(self, alarm_id: str) -> list[str]:
        result = await self._session.execute(
            select(AlarmAccountAssignment.account_id).where(
                AlarmAccountAssignment.alarm_id == alarm_id
            )
        )
        return [str(account_id) for account_id in result.scalars().all()]

    async def _load_current_state(self, alarm_id: str) -> AlarmState | None:
        result = await self._session.execute(
            select(AlarmState).where(AlarmState.alarm_id == alarm_id)
        )
        return result.scalar_one_or_none()

    async def _build_context(self, account: Account) -> dict[str, Any]:
        balance = await self._load_latest_balance(str(account.id))
        connection = await self._session.get(
            ProviderConnection,
            str(account.provider_connection_id),
        )
        sync_run = await self._load_latest_sync_run(str(account.provider_connection_id))
        return {
            "account": {
                "id": str(account.id),
                "balance": balance.current if balance is not None else None,
                "currency": (
                    balance.currency
                    if balance is not None and balance.currency is not None
                    else account.currency
                ),
            },
            "sync_run": {
                "status": sync_run.status if sync_run is not None else None,
                "error_code": sync_run.error_code if sync_run is not None else None,
            },
            "provider_connection": {
                "auth_status": connection.auth_status if connection is not None else None,
                "consent_expires_at": (
                    connection.consent_expires_at if connection is not None else None
                ),
            },
        }

    async def _load_latest_balance(self, account_id: str) -> Balance | None:
        result = await self._session.execute(
            select(Balance)
            .where(Balance.account_id == account_id)
            .order_by(Balance.recorded_at.desc(), Balance.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _load_latest_sync_run(self, provider_connection_id: str) -> SyncRun | None:
        result = await self._session.execute(
            select(SyncRun)
            .where(SyncRun.provider_connection_id == provider_connection_id)
            .order_by(SyncRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _aggregate_evaluations(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        if not evaluations:
            return {
                "result": False,
                "explanation": "No assigned accounts.",
                "context_snapshot": {"account": None, "evaluations": []},
            }

        matched = [item for item in evaluations if item["result"]]
        selected = matched[0] if matched else evaluations[0]
        explanation_parts = matched if matched else evaluations
        return {
            "result": bool(matched),
            "explanation": " OR ".join(str(item["explanation"]) for item in explanation_parts),
            "context_snapshot": {
                "account_id": selected["account_id"],
                "account": self._serialize_json(selected["context"]),
                "evaluations": [
                    {
                        "account_id": item["account_id"],
                        "result": item["result"],
                        "explanation": item["explanation"],
                    }
                    for item in evaluations
                ],
            },
        }

    def _apply_state_update(
        self,
        *,
        state: AlarmState,
        previous_state: str,
        new_state: str,
        eval_result: bool,
        alarm: AlarmDefinition,
        now: datetime,
        should_notify: bool,
    ) -> None:
        previous_consecutive = state.consecutive_true or 0
        state.state = new_state
        state.last_evaluated_at = now
        if new_state == "muted":
            pass
        elif previous_state == "muted":
            state.mute_until = None

        if eval_result:
            if previous_state in {"pending", "firing"}:
                state.consecutive_true = previous_consecutive + 1
            elif previous_state == "resolved":
                state.consecutive_true = 1
            else:
                state.consecutive_true = 1
        else:
            state.consecutive_true = 0

        if new_state == "resolved":
            state.last_resolved_at = now

        if should_notify and new_state == "firing":
            state.last_fired_at = now
        elif previous_state == "muted" and new_state == "firing" and alarm.cooldown_minutes <= 0:
            state.last_fired_at = now

    def _serialize_json(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._serialize_json(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize_json(item) for item in value]
        if isinstance(value, tuple):
            return [self._serialize_json(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value


__all__ = ["AlarmEvaluatorService"]
