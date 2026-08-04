"""Candidate discovery.

Discovery pairs each model in the registry with its provider. It reads ONLY the
in-memory registry snapshot — it never queries a provider, enumerates a remote model
catalog, or refreshes anything over the network. Dynamic catalog refresh, if ever
needed, belongs OUTSIDE this advisory core (see ``PROVIDER_EXECUTION_BOUNDARY.md``).
"""

from __future__ import annotations

from typing import List, Tuple

from .contracts import ModelCandidate, ProviderCandidate, SteeringRequest
from .registry import CandidateRegistry


def discover(registry: CandidateRegistry, request: SteeringRequest
             ) -> List[Tuple[ModelCandidate, ProviderCandidate]]:
    """Return every ``(model, provider)`` pair, in deterministic ``model_id`` order.

    Discovery is intentionally inclusive: it does not pre-filter on constraints (that is
    the constraint stage's job) so the evidence records every candidate considered.
    """
    pairs: List[Tuple[ModelCandidate, ProviderCandidate]] = []
    for model in registry.models:  # already sorted by model_id
        provider = registry.provider(model.provider_id)
        pairs.append((model, provider))
    return pairs


__all__ = ["discover"]
