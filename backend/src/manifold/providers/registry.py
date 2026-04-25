from __future__ import annotations

from manifold.providers.base import BaseProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, type[BaseProvider]] = {}

    def register(self, provider_cls: type[BaseProvider]) -> None:
        self._providers[provider_cls.provider_type] = provider_cls

    def get(self, provider_type: str) -> BaseProvider:
        provider_cls = self._providers.get(provider_type)
        if provider_cls is None:
            raise KeyError(f"provider '{provider_type}' not registered")
        return provider_cls()

    def list_types(self) -> list[str]:
        return sorted(self._providers)


registry = ProviderRegistry()


def register_all() -> None:
    from manifold.providers.json_provider.adapter import JsonProvider
    from manifold.providers.truelayer.adapter import TrueLayerProvider

    registry.register(TrueLayerProvider)
    registry.register(JsonProvider)
