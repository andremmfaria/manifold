from __future__ import annotations

from datetime import datetime, timedelta

from manifold.models.alarm import AlarmDefinition, AlarmState


class AlarmStateMachine:
    def transition(
        self,
        alarm: AlarmDefinition,
        current_state: AlarmState | None,
        eval_result: bool,
        now: datetime,
    ) -> tuple[str, bool]:
        """Returns (new_state: str, should_notify: bool)."""
        previous_state = current_state.state if current_state is not None else "ok"

        if previous_state == "muted":
            mute_until = current_state.mute_until if current_state is not None else None
            if mute_until is not None and mute_until > now:
                return "muted", False
            previous_state = "ok"

        new_state = self._resolve_next_state(alarm, current_state, previous_state, eval_result)
        should_notify = self._should_notify(alarm, current_state, previous_state, new_state, now)
        return new_state, should_notify

    def _resolve_next_state(
        self,
        alarm: AlarmDefinition,
        current_state: AlarmState | None,
        previous_state: str,
        eval_result: bool,
    ) -> str:
        repeat_count = max(alarm.repeat_count, 1)
        consecutive_true = current_state.consecutive_true if current_state is not None else 0

        if previous_state == "ok":
            if not eval_result:
                return "ok"
            return "firing" if repeat_count <= 1 else "pending"

        if previous_state == "pending":
            if not eval_result:
                return "ok"
            next_consecutive = consecutive_true + 1
            return "firing" if next_consecutive >= repeat_count else "pending"

        if previous_state == "firing":
            return "firing" if eval_result else "resolved"

        if previous_state == "resolved":
            return "pending" if eval_result else "ok"

        return "firing" if eval_result else "ok"

    def _should_notify(
        self,
        alarm: AlarmDefinition,
        current_state: AlarmState | None,
        previous_state: str,
        new_state: str,
        now: datetime,
    ) -> bool:
        if new_state == "firing" and previous_state != "firing":
            return not self._within_cooldown(alarm, current_state, now)
        if (
            previous_state == "firing"
            and new_state == "resolved"
            and alarm.notify_on_resolve
        ):
            return not self._within_cooldown(alarm, current_state, now)
        return False

    def _within_cooldown(
        self, alarm: AlarmDefinition, current_state: AlarmState | None, now: datetime
    ) -> bool:
        if current_state is None or current_state.last_fired_at is None:
            return False
        cooldown_minutes = max(alarm.cooldown_minutes, 0)
        if cooldown_minutes <= 0:
            return False
        return current_state.last_fired_at + timedelta(minutes=cooldown_minutes) > now


__all__ = ["AlarmStateMachine"]
