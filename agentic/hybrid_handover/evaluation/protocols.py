#!/usr/bin/env python3
"""
Plug-in interfaces for the evaluation framework.

The whole framework depends only on these protocols — never on the concrete
deterministic extractor in the frozen package. A future
`HybridPhaseTransformer`-backed extractor, a different frontier model, or a new
packet validator can be dropped in by satisfying these interfaces, and every
metric, injector, and report continues to work unchanged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentic.hybrid_handover.schema import (
    Corpus,
    EvidencePacket,
    RedactedPacket,
    ResolvedAnswer,
)


@runtime_checkable
class ExtractorProtocol(Protocol):
    """The in-house (sovereign) tier under test. The frozen ``InHouseExtractor``
    satisfies this; so must any future neural extractor."""

    def extract(self, question: str, corpus: Corpus) -> EvidencePacket: ...

    def resolve(self, question: str, corpus: Corpus) -> ResolvedAnswer: ...


@runtime_checkable
class FrontierProtocol(Protocol):
    """The downstream reasoning tier (a stand-in for the quadratic-model API)."""

    def reason(self, packet: RedactedPacket) -> str: ...


@runtime_checkable
class ValidatorProtocol(Protocol):
    """An independent packet validator. Runs after packet construction and may
    block handover. Independence is the point: it must not simply re-run the
    extractor's own consistency check."""

    name: str

    def validate(self, case, packet: EvidencePacket, corpus: Corpus): ...
