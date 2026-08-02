"""Provider registry — an explicit, injected map of provider id -> provider.

The registry is never populated implicitly at import time. Callers register
providers explicitly through configuration or ``register_provider``, keeping the
package free of import-time side effects and global provider state.
"""
from __future__ import annotations

from typing import Dict, Iterator, Optional

from ..runtime.errors import ProviderNotFoundError, RuntimeConfigurationError
from .interfaces import Provider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        pid = getattr(provider, "provider_id", None)
        if not pid or not isinstance(pid, str):
            raise RuntimeConfigurationError(
                "provider must expose a non-empty string provider_id"
            )
        if pid in self._providers:
            raise RuntimeConfigurationError(f"provider {pid!r} already registered")
        self._providers[pid] = provider

    def get(self, provider_id: str) -> Provider:
        try:
            return self._providers[provider_id]
        except KeyError:
            raise ProviderNotFoundError(f"no provider registered for {provider_id!r}")

    def try_get(self, provider_id: str) -> Optional[Provider]:
        return self._providers.get(provider_id)

    def __contains__(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def __iter__(self) -> Iterator[str]:
        return iter(self._providers)

    def ids(self) -> tuple:
        return tuple(self._providers)
