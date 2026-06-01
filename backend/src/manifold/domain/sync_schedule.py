from __future__ import annotations

_INTERVAL_MAP: dict[str, int] = {
    "15m": 15,
    "1h": 60,
    "6h": 360,
    "1d": 1440,
}

_DEFAULT_MINUTES = 60


def interval_to_minutes(value: str | None) -> int | None:
    """Map a sync_interval config value to minutes.

    Returns None for "manual" (never auto-sync) or an unknown/falsy value that
    should fall back to manual.  Returns _DEFAULT_MINUTES when the value is
    absent (None / empty string) so that connections without an explicit
    interval still get synced on the default hourly cadence.
    """
    if not value:
        return _DEFAULT_MINUTES
    if value == "manual":
        return None
    return _INTERVAL_MAP.get(value, _DEFAULT_MINUTES)
