"""Provider descriptor — the registry's registration unit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .contracts import Provider
from .metadata import ProviderCapabilities, ProviderKind, ProviderMetadata


@dataclass(frozen=True)
class ProviderDescriptor:
    """Everything the registry needs to register, describe, and build a provider.

    ``factory`` is a zero-arg callable returning a provider instance (so the
    registry controls instantiation and lifecycle). ``default`` marks the
    default provider for its kind when several are registered.
    """

    metadata: ProviderMetadata
    capabilities: ProviderCapabilities
    factory: Callable[[], Provider]
    default: bool = False

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def kind(self) -> ProviderKind:
        return self.metadata.kind
