from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    html_body: str
    text_body: str | None = None
    from_address: str | None = None
    reply_to: str | None = None
    tags: list[str] = field(default_factory=list)


__all__ = ["EmailMessage"]
