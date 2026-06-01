from __future__ import annotations

from typing import Any

_session: Any | None = None


def set_aiobotocore_session(s: Any | None) -> None:
    global _session
    _session = s


def get_aiobotocore_session() -> Any | None:
    return _session
