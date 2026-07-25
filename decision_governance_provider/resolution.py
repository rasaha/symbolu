"""Provider resolution — configuration-driven selection (no static imports).

An application declares *which* provider it wants per kind as data (a
:class:`ProviderSelection`), and the resolver looks it up in the registry. There
are no imports of concrete providers here — selection is entirely by name,
capability, default, or determinism flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .contracts import Provider
from .errors import ProviderNotFoundError, ProviderResolutionError
from .metadata import ProviderKind
from .registry import ProviderRegistry


@dataclass(frozen=True)
class ProviderSelection:
    """How to select a provider of a given kind.

    Resolution precedence: ``name`` (exact) → ``capability`` (feature match) →
    default for the kind. ``deterministic_only`` restricts the candidate set to
    deterministic providers (e.g. to force a mock in tests).
    """

    kind: ProviderKind
    name: Optional[str] = None
    capability: Optional[str] = None
    deterministic_only: bool = False


@dataclass(frozen=True)
class ProviderConfiguration:
    """A per-kind selection map — the application's provider wiring, as data."""

    selections: tuple[ProviderSelection, ...] = ()

    def for_kind(self, kind: ProviderKind) -> Optional[ProviderSelection]:
        for sel in self.selections:
            if sel.kind is kind:
                return sel
        return None


def resolve_provider(registry: ProviderRegistry, selection: ProviderSelection) -> Provider:
    """Resolve one provider from the registry per a selection."""
    candidates = list(registry.list_descriptors(selection.kind))
    if selection.deterministic_only:
        candidates = [d for d in candidates if d.capabilities.deterministic]
    if not candidates:
        raise ProviderResolutionError(
            f"no provider available for kind {selection.kind.value} "
            f"(deterministic_only={selection.deterministic_only})")

    if selection.name is not None:
        chosen = next((d for d in candidates if d.name == selection.name), None)
        if chosen is None:
            raise ProviderNotFoundError(
                f"no provider named '{selection.name}' for kind {selection.kind.value}"
                + (" among deterministic providers" if selection.deterministic_only else ""))
        return registry.get_provider(chosen.name)

    if selection.capability is not None:
        matches = [d for d in candidates
                   if d.capabilities.supports_feature(selection.capability)]
        if not matches:
            raise ProviderResolutionError(
                f"no provider for kind {selection.kind.value} supports capability "
                f"'{selection.capability}'")
        marked = [d for d in matches if d.default]
        chosen = marked[0] if marked else matches[0]
        return registry.get_provider(chosen.name)

    # default for the kind, restricted to the candidate set
    marked = [d for d in candidates if d.default]
    if marked:
        return registry.get_provider(marked[0].name)
    if len(candidates) == 1:
        return registry.get_provider(candidates[0].name)
    raise ProviderResolutionError(
        f"no default provider for kind {selection.kind.value}; specify name or capability")


def resolve_configuration(registry: ProviderRegistry, config: ProviderConfiguration
                          ) -> dict[ProviderKind, Provider]:
    """Resolve every configured selection into live providers, keyed by kind."""
    return {sel.kind: resolve_provider(registry, sel) for sel in config.selections}
