from __future__ import annotations

from typing import Any

from manifold.alarm_engine.predicates import (
    format_field_value,
    format_target_value,
    operator_symbol,
    resolve_field,
)


class AlarmExplainer:
    def explain(
        self, condition: dict[str, Any], context: dict[str, Any], result: bool
    ) -> str:
        """Generate human-readable explanation of why alarm fired/didn't fire."""
        _ = result
        return self._explain_node(condition, context)

    def _explain_node(self, condition: dict[str, Any], context: dict[str, Any]) -> str:
        op = str(condition.get("op", "")).upper()
        if op == "AND":
            return " AND ".join(
                self._wrap(self._explain_node(arg, context)) for arg in condition["args"]
            )
        if op == "OR":
            return " OR ".join(
                self._wrap(self._explain_node(arg, context)) for arg in condition["args"]
            )
        if op == "NOT":
            return f"NOT {self._wrap(self._explain_node(condition['args'][0], context))}"
        return self._explain_leaf(op, condition, context)

    def _explain_leaf(self, op: str, condition: dict[str, Any], context: dict[str, Any]) -> str:
        field = condition.get("field")
        field_name = field or self._default_field_name(op)
        actual = resolve_field(field, context)
        expected = condition.get("value")
        if op in {"IS_NULL", "IS_NOT_NULL"}:
            return (
                f"{field_name} ({format_field_value(field, actual, context)}) "
                f"{operator_symbol(op)}"
            )
        if op == "SYNC_FAILED":
            return f"{field_name} ({format_field_value(field, actual, context)}) = failed"
        return (
            f"{field_name} ({format_field_value(field, actual, context)}) "
            f"{operator_symbol(op)} {format_target_value(field, expected, context)}"
        )

    def _default_field_name(self, op: str) -> str:
        if op == "SYNC_FAILED":
            return "sync_run.status"
        if op == "CONSENT_EXPIRING_WITHIN_DAYS":
            return "provider_connection.consent_expires_at"
        return "value"

    def _wrap(self, explanation: str) -> str:
        if " AND " in explanation or " OR " in explanation:
            return f"({explanation})"
        return explanation


__all__ = ["AlarmExplainer"]
