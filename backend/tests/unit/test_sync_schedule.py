from __future__ import annotations

from manifold.domain.sync_schedule import interval_to_minutes


def test_15m_maps_to_15() -> None:
    assert interval_to_minutes("15m") == 15


def test_1h_maps_to_60() -> None:
    assert interval_to_minutes("1h") == 60


def test_6h_maps_to_360() -> None:
    assert interval_to_minutes("6h") == 360


def test_1d_maps_to_1440() -> None:
    assert interval_to_minutes("1d") == 1440


def test_manual_returns_none() -> None:
    assert interval_to_minutes("manual") is None


def test_none_returns_default_60() -> None:
    assert interval_to_minutes(None) == 60


def test_empty_string_returns_default_60() -> None:
    assert interval_to_minutes("") == 60


def test_unknown_value_returns_default_60() -> None:
    assert interval_to_minutes("2w") == 60
