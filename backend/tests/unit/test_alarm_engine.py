from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from manifold.alarm_engine.evaluator import AlarmEvaluator
from manifold.alarm_engine.explainer import AlarmExplainer
from manifold.alarm_engine.state_machine import AlarmStateMachine


def _make_alarm(**overrides):
    data = {
        "repeat_count": 1,
        "cooldown_minutes": 60,
        "notify_on_resolve": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _make_state(state: str, **overrides):
    data = {
        "state": state,
        "mute_until": None,
        "consecutive_true": 0,
        "last_fired_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.parametrize(
    ("condition", "context", "expected"),
    [
        (
            {"op": "GT", "field": "account.balance", "value": 100},
            {"account": {"balance": 200}},
            True,
        ),
        (
            {"op": "GT", "field": "account.balance", "value": 100},
            {"account": {"balance": 50}},
            False,
        ),
        (
            {"op": "LT", "field": "account.balance", "value": 100},
            {"account": {"balance": 50}},
            True,
        ),
        (
            {"op": "EQ", "field": "account.currency", "value": "GBP"},
            {"account": {"currency": "GBP"}},
            True,
        ),
        (
            {"op": "NEQ", "field": "account.currency", "value": "GBP"},
            {"account": {"currency": "USD"}},
            True,
        ),
        (
            {"op": "GTE", "field": "account.balance", "value": 100},
            {"account": {"balance": 100}},
            True,
        ),
        (
            {"op": "LTE", "field": "account.balance", "value": 100},
            {"account": {"balance": 100}},
            True,
        ),
    ],
)
def test_leaf_predicates(condition: dict, context: dict, expected: bool) -> None:
    result, _ = AlarmEvaluator().evaluate(condition, context)

    assert result is expected


def test_and_all_true() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {
            "op": "AND",
            "args": [
                {"op": "GT", "field": "account.balance", "value": 0},
                {"op": "EQ", "field": "account.currency", "value": "GBP"},
            ],
        },
        {"account": {"balance": 100, "currency": "GBP"}},
    )

    assert result is True


def test_and_one_false() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {
            "op": "AND",
            "args": [
                {"op": "GT", "field": "account.balance", "value": 0},
                {"op": "EQ", "field": "account.currency", "value": "GBP"},
            ],
        },
        {"account": {"balance": 100, "currency": "USD"}},
    )

    assert result is False


def test_or_one_true() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {
            "op": "OR",
            "args": [
                {"op": "EQ", "field": "account.currency", "value": "GBP"},
                {"op": "GT", "field": "account.balance", "value": 100},
            ],
        },
        {"account": {"balance": 150, "currency": "USD"}},
    )

    assert result is True


def test_not_inverts() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {"op": "NOT", "args": [{"op": "EQ", "field": "account.currency", "value": "GBP"}]},
        {"account": {"currency": "USD"}},
    )

    assert result is True


def test_nested_and_or() -> None:
    result, explanation = AlarmEvaluator().evaluate(
        {
            "op": "AND",
            "args": [
                {"op": "GT", "field": "account.balance", "value": 0},
                {
                    "op": "OR",
                    "args": [
                        {"op": "EQ", "field": "account.currency", "value": "GBP"},
                        {"op": "EQ", "field": "account.currency", "value": "EUR"},
                    ],
                },
            ],
        },
        {"account": {"balance": 10, "currency": "EUR"}},
    )

    assert result is True
    assert "AND" in explanation
    assert "OR" in explanation


def test_missing_field_returns_false() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {"op": "EQ", "field": "nonexistent.field", "value": "x"},
        {},
    )

    assert result is False


def test_is_null_true() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {"op": "IS_NULL", "field": "account.balance"},
        {"account": {"balance": None}},
    )

    assert result is True


def test_is_not_null_true() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {"op": "IS_NOT_NULL", "field": "account.balance"},
        {"account": {"balance": 10}},
    )

    assert result is True


def test_contains_string() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {"op": "CONTAINS", "field": "transaction.description", "value": "rent"},
        {"transaction": {"description": "monthly rent payment"}},
    )

    assert result is True


def test_in_list() -> None:
    result, _ = AlarmEvaluator().evaluate(
        {"op": "IN_LIST", "field": "account.currency", "value": ["GBP", "EUR"]},
        {"account": {"currency": "EUR"}},
    )

    assert result is True


def test_explanation_includes_field_and_value() -> None:
    _, explanation = AlarmEvaluator().evaluate(
        {"op": "LT", "field": "account.balance", "value": 100},
        {"account": {"balance": 50}},
    )

    assert "account.balance" in explanation
    assert "50" in explanation
    assert "100" in explanation


def test_explainer_formats_nested_condition() -> None:
    explanation = AlarmExplainer().explain(
        {
            "op": "OR",
            "args": [
                {"op": "EQ", "field": "account.currency", "value": "GBP"},
                {"op": "GT", "field": "account.balance", "value": 100},
            ],
        },
        {"account": {"currency": "USD", "balance": 150}},
        result=True,
    )

    assert "account.currency" in explanation
    assert "account.balance" in explanation
    assert "OR" in explanation


def test_ok_to_pending_on_true() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)

    new_state, should_notify = AlarmStateMachine().transition(
        _make_alarm(repeat_count=2), None, True, now
    )

    assert new_state == "pending"
    assert should_notify is False


def test_ok_to_firing_when_repeat_1() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)

    new_state, should_notify = AlarmStateMachine().transition(
        _make_alarm(repeat_count=1), None, True, now
    )

    assert new_state == "firing"
    assert should_notify is True


def test_pending_to_firing_after_repeat_count() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    state = _make_state("pending", consecutive_true=1)

    new_state, should_notify = AlarmStateMachine().transition(
        _make_alarm(repeat_count=2), state, True, now
    )

    assert new_state == "firing"
    assert should_notify is True


def test_firing_to_resolved_on_false() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    state = _make_state("firing")

    new_state, should_notify = AlarmStateMachine().transition(_make_alarm(), state, False, now)

    assert new_state == "resolved"
    assert should_notify is False


def test_firing_stays_firing_on_true() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    state = _make_state("firing")

    new_state, should_notify = AlarmStateMachine().transition(_make_alarm(), state, True, now)

    assert new_state == "firing"
    assert should_notify is False


def test_muted_stays_muted_within_window() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    state = _make_state("muted", mute_until=now + timedelta(minutes=10))

    new_state, should_notify = AlarmStateMachine().transition(_make_alarm(), state, True, now)

    assert new_state == "muted"
    assert should_notify is False


def test_muted_expires_and_re_evaluates() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    state = _make_state("muted", mute_until=now - timedelta(minutes=1))

    new_state, should_notify = AlarmStateMachine().transition(
        _make_alarm(repeat_count=1), state, True, now
    )

    assert new_state == "firing"
    assert should_notify is True


def test_cooldown_prevents_notify() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    state = _make_state("pending", consecutive_true=1, last_fired_at=now - timedelta(minutes=5))

    new_state, should_notify = AlarmStateMachine().transition(
        _make_alarm(repeat_count=2, cooldown_minutes=30),
        state,
        True,
        now,
    )

    assert new_state == "firing"
    assert should_notify is False


def test_notify_on_resolve_flag() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    state = _make_state("firing", last_fired_at=now - timedelta(hours=2))

    new_state, should_notify = AlarmStateMachine().transition(
        _make_alarm(notify_on_resolve=True, cooldown_minutes=30),
        state,
        False,
        now,
    )

    assert new_state == "resolved"
    assert should_notify is True
