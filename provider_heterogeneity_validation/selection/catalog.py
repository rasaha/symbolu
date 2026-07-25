"""Provider catalog + state (benchmark-owned, provider-neutral).

A catalog entry carries a provider's identity, declared capabilities, injected
runtime state, and a *builder* callable. The neutral selection layer reasons over
entries only; the composition layer supplies the builders (and thus the concrete
providers). No provider is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class ProviderState:
    enabled: bool = True
    health: str = "AVAILABLE"           # AVAILABLE / DEGRADED / UNAVAILABLE
    compatible: bool = True
    contract_version: str = "1.0.0"


@dataclass(frozen=True)
class CatalogEntry:
    provider_id: str
    kind: str                            # "ASSERTION_GOVERNANCE" / "ACTION_GOVERNANCE"
    version: str
    capabilities: frozenset
    state: ProviderState = field(default_factory=ProviderState)
    build: Optional[Callable] = None     # () -> provider instance (composition-supplied)


@dataclass
class ProviderCatalog:
    entries: list = field(default_factory=list)

    def add(self, entry: CatalogEntry) -> None:
        self.entries.append(entry)

    def list_by_kind(self, kind: str) -> list:
        return [e for e in self.entries if e.kind == kind]

    def get(self, provider_id: str) -> Optional[CatalogEntry]:
        for e in self.entries:
            if e.provider_id == provider_id:
                return e
        return None

    def has_duplicate_ids(self, kind: str) -> bool:
        ids = [e.provider_id for e in self.list_by_kind(kind)]
        return len(ids) != len(set(ids))
