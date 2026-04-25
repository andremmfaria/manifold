from __future__ import annotations

from typing import Any

from manifold.alarm_engine.predicates import (
    evaluate_predicate,
    format_field_value,
    format_target_value,
    operator_symbol,
    resolve_field,
)


class AlarmEvaluator:
    def evaluate(self, condition: dict[str, Any], context: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate condition tree. Returns (result, explanation_string)."""
        if not isinstance(condition, dict):
            raise ValueError("Alarm condition must be a dict")
        op = str(condition.get("op", "")).upper()
        if op == "AND":
            return self._evaluate_and(condition, context)
        if op == "OR":
            return self._evaluate_or(condition, context)
        if op == "NOT":
            return self._evaluate_not(condition, context)
        return self._evaluate_leaf(op, condition, context)

    def _evaluate_and(
        self, condition: dict[str, Any], context: dict[str, Any]
    ) -> tuple[bool, str]:
        args = self._require_args(condition)
        results = [self.evaluate(arg, context) for arg in args]
        explanation = " AND ".join(self._wrap(exp) for _, exp in results)
        return all(result for result, _ in results), explanation

    def _evaluate_or(
        self, condition: dict[str, Any], context: dict[str, Any]
    ) -> tuple[bool, str]:
        args = self._require_args(condition)
        results = [self.evaluate(arg, context) for arg in args]
        explanation = " OR ".join(self._wrap(exp) for _, exp in results)
        return any(result for result, _ in results), explanation

    def _evaluate_not(
        self, condition: dict[str, Any], context: dict[str, Any]
    ) -> tuple[bool, str]:
        args = self._require_args(condition)
        if len(args) != 1:
            raise ValueError("NOT requires exactly one argument")
        inner_result, inner_explanation = self.evaluate(args[0], context)
        return (not inner_result), f"NOT {self._wrap(inner_explanation)}"

    def _evaluate_leaf(
        self, op: str, condition: dict[str, Any], context: dict[str, Any]
    ) -> tuple[bool, str]:
        field = condition.get("field")
        field_value = resolve_field(field, context)
        target = condition.get("value")
        result = evaluate_predicate(op, field_value, target, context=context)
        explanation = self._build_leaf_explanation(op, field, field_value, target, context)
        return result, explanation

    def _build_leaf_explanation(
        self,
        op: str,
        field: str | None,
        field_value: Any,
        target: Any,
        context: dict[str, Any],
    ) -> str:
        field_name = field or self._default_field_name(op)
        if op in {"IS_NULL", "IS_NOT_NULL"}:
            return (
                f"{field_name} ({format_field_value(field, field_value, context)}) "
                f"{operator_symbol(op)}"
            )
        if op == "SYNC_FAILED":
            return f"{field_name} ({format_field_value(field, field_value, context)}) = failed"
        if op == "CONSENT_EXPIRING_WITHIN_DAYS":
            return (
                f"{field_name} ({format_field_value(field, field_value, context)}) "
                f"{operator_symbol(op)} {format_target_value(field, target, context)}"
            )
        return (
            f"{field_name} ({format_field_value(field, field_value, context)}) "
            f"{operator_symbol(op)} {format_target_value(field, target, context)}"
        )

    def _default_field_name(self, op: str) -> str:
        if op == "SYNC_FAILED":
            return "sync_run.status"
        if op == "CONSENT_EXPIRING_WITHIN_DAYS":
            return "provider_connection.consent_expires_at"
        return "value"

    def _require_args(self, condition: dict[str, Any]) -> list[dict[str, Any]]:
        args = condition.get("args")
        if not isinstance(args, list) or not args:
            raise ValueError("Logical operator requires non-empty args list")
        return args

    def _wrap(self, explanation: str) -> str:
        if " AND " in explanation or " OR " in explanation:
            return f"({explanation})"
        return explanation


__all__ = ["AlarmEvaluator"]
