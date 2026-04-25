from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any


def evaluate_predicate(
    op: str,
    actual: Any,
    expected: Any,
    *,
    context: dict[str, Any],
) -> bool:
    predicate = _PREDICATES.get(op)
    if predicate is None:
        raise ValueError(f"Unsupported operator: {op}")
    return predicate(actual, expected, context)


def operator_symbol(op: str) -> str:
    return _OPERATOR_SYMBOLS.get(op, op)


def resolve_field(field: str | None, context: dict[str, Any]) -> Any:
    if not field:
        return None
    current: Any = context
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def format_field_value(field: str | None, value: Any, context: dict[str, Any]) -> str:
    if value is None:
        return "null"
    if isinstance(value, Decimal):
        currency = _currency_for_field(field, context)
        return _format_decimal(value, currency)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "[" + ", ".join(format_field_value(field, item, context) for item in value) + "]"
    return str(value)


def format_target_value(field: str | None, value: Any, context: dict[str, Any]) -> str:
    return format_field_value(field, value, context)


def _eq(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    left, right = _coerce_pair(actual, expected)
    return left == right


def _neq(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    left, right = _coerce_pair(actual, expected)
    return left != right


def _gt(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    return _compare(actual, expected, lambda left, right: left > right)


def _gte(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    return _compare(actual, expected, lambda left, right: left >= right)


def _lt(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    return _compare(actual, expected, lambda left, right: left < right)


def _lte(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    return _compare(actual, expected, lambda left, right: left <= right)


def _contains(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    if actual is None or expected is None:
        return False
    return str(expected) in str(actual)


def _starts_with(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    if actual is None or expected is None:
        return False
    return str(actual).startswith(str(expected))


def _matches(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    if actual is None or expected is None:
        return False
    try:
        return re.search(str(expected), str(actual)) is not None
    except re.error:
        return False


def _in_list(actual: Any, expected: Any, _context: dict[str, Any]) -> bool:
    if expected is None:
        return False
    if isinstance(expected, (str, bytes)):
        return actual == expected
    if isinstance(expected, Iterable):
        return actual in expected
    return False


def _is_null(actual: Any, _expected: Any, _context: dict[str, Any]) -> bool:
    return actual is None


def _is_not_null(actual: Any, _expected: Any, _context: dict[str, Any]) -> bool:
    return actual is not None


def _sync_failed(actual: Any, _expected: Any, context: dict[str, Any]) -> bool:
    status = actual if actual is not None else resolve_field("sync_run.status", context)
    return status == "failed"


def _consent_expiring_within_days(actual: Any, expected: Any, context: dict[str, Any]) -> bool:
    consent_expires_at = actual
    if consent_expires_at is None:
        consent_expires_at = resolve_field("provider_connection.consent_expires_at", context)
    if consent_expires_at is None or expected is None:
        return False
    if isinstance(consent_expires_at, str):
        try:
            consent_expires_at = datetime.fromisoformat(consent_expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(consent_expires_at, datetime):
        return False
    if consent_expires_at.tzinfo is None:
        consent_expires_at = consent_expires_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    try:
        days = int(expected)
    except (TypeError, ValueError):
        return False
    return consent_expires_at <= now + timedelta(days=days)


def _compare(actual: Any, expected: Any, comparator: Any) -> bool:
    if actual is None or expected is None:
        return False
    left, right = _coerce_pair(actual, expected)
    try:
        return bool(comparator(left, right))
    except TypeError:
        return False


def _coerce_pair(actual: Any, expected: Any) -> tuple[Any, Any]:
    if isinstance(actual, Decimal) or isinstance(expected, Decimal):
        left = _to_decimal(actual)
        right = _to_decimal(expected)
        if left is None or right is None:
            return actual, expected
        return left, right
    return actual, expected


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _currency_for_field(field: str | None, context: dict[str, Any]) -> str | None:
    if not field:
        return None
    prefix, _, _suffix = field.rpartition(".")
    if not prefix:
        return None
    currency = resolve_field(f"{prefix}.currency", context)
    return str(currency) if currency else None


def _format_decimal(value: Decimal, currency: str | None) -> str:
    quantized = value.quantize(Decimal("0.01"))
    prefix = _CURRENCY_SYMBOLS.get(currency or "", "")
    if prefix:
        return f"{prefix}{quantized}"
    if currency:
        return f"{quantized} {currency}"
    return str(quantized)


_OPERATOR_SYMBOLS = {
    "EQ": "=",
    "NEQ": "!=",
    "GT": ">",
    "GTE": ">=",
    "LT": "<",
    "LTE": "<=",
    "CONTAINS": "contains",
    "STARTS_WITH": "starts_with",
    "MATCHES": "matches",
    "IN_LIST": "in",
    "IS_NULL": "is null",
    "IS_NOT_NULL": "is not null",
    "SYNC_FAILED": "sync_failed",
    "CONSENT_EXPIRING_WITHIN_DAYS": "consent_expires_within_days",
}

_PREDICATES = {
    "EQ": _eq,
    "NEQ": _neq,
    "GT": _gt,
    "GTE": _gte,
    "LT": _lt,
    "LTE": _lte,
    "CONTAINS": _contains,
    "STARTS_WITH": _starts_with,
    "MATCHES": _matches,
    "IN_LIST": _in_list,
    "IS_NULL": _is_null,
    "IS_NOT_NULL": _is_not_null,
    "SYNC_FAILED": _sync_failed,
    "CONSENT_EXPIRING_WITHIN_DAYS": _consent_expiring_within_days,
}

_CURRENCY_SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$"}


__all__ = [
    "evaluate_predicate",
    "format_field_value",
    "format_target_value",
    "operator_symbol",
    "resolve_field",
]
