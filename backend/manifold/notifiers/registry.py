from __future__ import annotations

from manifold.notifiers.base import BaseNotifier


class NotifierRegistry:
    def __init__(self) -> None:
        self._notifiers: dict[str, type[BaseNotifier]] = {}

    def register(self, notifier_cls: type[BaseNotifier]) -> None:
        self._notifiers[notifier_cls.notifier_type] = notifier_cls

    def get(self, notifier_type: str) -> BaseNotifier:
        notifier_cls = self._notifiers.get(notifier_type)
        if notifier_cls is None:
            raise KeyError(f"notifier '{notifier_type}' not registered")
        return notifier_cls()

    def list_types(self) -> list[str]:
        return sorted(self._notifiers)


registry = NotifierRegistry()


def register_all() -> None:
    from manifold.notifiers.email import EmailNotifier
    from manifold.notifiers.slack import SlackNotifier
    from manifold.notifiers.telegram import TelegramNotifier
    from manifold.notifiers.webhook import WebhookNotifier

    registry.register(EmailNotifier)
    registry.register(WebhookNotifier)
    registry.register(SlackNotifier)
    registry.register(TelegramNotifier)


__all__ = ["NotifierRegistry", "registry", "register_all"]
