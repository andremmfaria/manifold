from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from manifold.notifiers.base import BaseNotifier, NotificationPayload, NotificationType

_template_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent / "templates")),
    autoescape=False,
)


def get_template_environment() -> Environment:
    return _template_env


__all__ = [
    "BaseNotifier",
    "NotificationPayload",
    "NotificationType",
    "get_template_environment",
]
