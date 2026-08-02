"""Deterministic, auditable provider resolution.

Resolution never silently picks among multiple equally-eligible providers. The
precedence is fixed and reproducible:

    explicit provider id
      → configured domain default
        → configured global default
          → the single compatible provider
            → resolution failure

Every resolution returns a structured :class:`ResolutionRecord` (the candidates,
their compatibility, the selected provider, the rule applied, and the failure
reason when unresolved) so selection is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .contracts import Provider
from .errors import ProviderResolutionError
from .metadata import ProviderKind
from .registry import ProviderRegistry


class SelectionRule(str, Enum):
    EXPLICIT_ID = "EXPLICIT_ID"
    DOMAIN_DEFAULT = "DOMAIN_DEFAULT"
    GLOBAL_DEFAULT = "GLOBAL_DEFAULT"
    SINGLE_COMPATIBLE = "SINGLE_COMPATIBLE"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class ResolutionRequest:
    kind: ProviderKind
    provider_id: Optional[str] = None
    capability: Optional[str] = None
    domain_default: Optional[str] = None
    global_default: Optional[str] = None


@dataclass(frozen=True)
class ResolutionRecord:
    kind: ProviderKind
    requested_capability: Optional[str]
    candidate_ids: tuple[str, ...]
    compatibility: dict[str, bool]
    selected_id: Optional[str]
    selection_rule: SelectionRule
    failure_reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.selected_id is not None


def resolve(registry: ProviderRegistry, request: ResolutionRequest
            ) -> tuple[Provider, ResolutionRecord]:
    """Resolve a provider deterministically; raise with the record on failure."""
    candidates = list(registry.list_by_kind(request.kind))
    if request.capability is not None:
        candidates = [d for d in candidates
                      if d.capabilities.supports_feature(request.capability)]
    compat = {d.provider_id: registry.is_compatible(d) for d in candidates}
    eligible = [d for d in candidates if compat[d.provider_id]]
    candidate_ids = tuple(d.provider_id for d in candidates)

    def record(selected, rule, reason=""):
        return ResolutionRecord(
            kind=request.kind, requested_capability=request.capability,
            candidate_ids=candidate_ids, compatibility=compat,
            selected_id=selected, selection_rule=rule, failure_reason=reason)

    def pick(provider_id, rule):
        rec = record(provider_id, rule)
        return registry.get_provider(provider_id), rec

    eligible_ids = {d.provider_id for d in eligible}

    # 1) explicit id
    if request.provider_id is not None:
        if request.provider_id in eligible_ids:
            return pick(request.provider_id, SelectionRule.EXPLICIT_ID)
        reason = (f"explicit provider '{request.provider_id}' not eligible for "
                  f"kind {request.kind.value}")
        raise ProviderResolutionError(reason)

    # 2) domain default
    if request.domain_default is not None and request.domain_default in eligible_ids:
        return pick(request.domain_default, SelectionRule.DOMAIN_DEFAULT)
    # 3) global default
    if request.global_default is not None and request.global_default in eligible_ids:
        return pick(request.global_default, SelectionRule.GLOBAL_DEFAULT)
    # registered default marker (treated as global default)
    marked = [d for d in eligible if d.default]
    if len(marked) == 1:
        return pick(marked[0].provider_id, SelectionRule.GLOBAL_DEFAULT)

    # 4) single compatible
    if len(eligible) == 1:
        return pick(eligible[0].provider_id, SelectionRule.SINGLE_COMPATIBLE)

    # 5) failure — never guess among multiple
    if not eligible:
        reason = f"no compatible provider for kind {request.kind.value}"
    else:
        reason = (f"ambiguous: {len(eligible)} eligible providers for kind "
                  f"{request.kind.value}; specify an id or a default")
    raise ProviderResolutionError(reason)
