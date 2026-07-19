#!/usr/bin/env python3
"""
Resolver interfaces. Every future resolver — deterministic, HybridPhaseTransformer,
SymbolU — implements these and is measured under identical conditions. The
resolution evaluation never knows which resolver is running.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentic.hybrid_handover.schema import EvidenceSpan

from .graph import GovernanceResolution, ResolvedEvidenceGraph, ResolutionResult


@runtime_checkable
class RelationshipResolverProtocol(Protocol):
    """Stage 2: evidence spans → typed relationship graph."""

    def resolve_relationships(
        self, question: str, evidence: list[EvidenceSpan]
    ) -> ResolvedEvidenceGraph: ...


@runtime_checkable
class GovernanceResolverProtocol(Protocol):
    """Stage 3: typed graph → which nodes govern (or abstain)."""

    def resolve_governance(
        self, question: str, graph: ResolvedEvidenceGraph
    ) -> GovernanceResolution: ...


@runtime_checkable
class ResolverProtocol(RelationshipResolverProtocol, GovernanceResolverProtocol, Protocol):
    """A full resolver: relationship + governance + packet-construction (stage 4)."""

    name: str

    def resolve(self, question: str, evidence: list[EvidenceSpan]) -> ResolutionResult: ...
