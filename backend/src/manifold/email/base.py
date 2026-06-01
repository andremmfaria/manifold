from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from .message import EmailMessage


@dataclass
class SuppressionEvent:
    address: str
    reason: Literal["bounce", "complaint"]
    provider: str


@runtime_checkable
class EmailTransport(Protocol):
    async def send(self, msg: EmailMessage) -> str: ...

    def validate_config(self, config: dict) -> list[str]: ...

    def verify_webhook(self, headers: dict, body: bytes) -> bool: ...

    def parse_webhook(self, payload: dict) -> list[SuppressionEvent]: ...


__all__ = ["EmailTransport", "SuppressionEvent"]
