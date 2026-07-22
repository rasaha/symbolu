"""
Multi-signal, interpretable candidate ranking for TAP-E2.

Ranking combines independent, interpretable signals — no opaque single-score model.
Every candidate keeps its per-signal `RankingSignals`, so a downstream consumer (or a
human) can see WHY a unit ranked where it did.

Signals:
  lexical                 — idf-weighted token overlap (from the index)
  semantic                — concept-vector cosine (from the index)
  authority               — source authority rank, normalized
  freshness               — newer effective year preferred; deprecated penalized
  provenance_completeness — 1.0 iff full provenance
  specificity             — shorter, entity-bearing units are more specific
  redundancy_penalty      — subtracted for near-duplicate content already ranked

The weights are fixed and documented; simpler baselines zero out subsets of signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    AUTHORITY_RANK, EvidenceUnit,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import RankingSignals

CURRENT_YEAR = 2026


@dataclass(frozen=True)
class RankingWeights:
    lexical: float
    semantic: float
    authority: float
    freshness: float
    provenance: float
    specificity: float
    redundancy: float

    @staticmethod
    def lexical_only() -> "RankingWeights":
        return RankingWeights(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def semantic_only() -> "RankingWeights":
        return RankingWeights(0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def hybrid() -> "RankingWeights":
        # lexical weighted above semantic: exact term overlap is a more reliable
        # precision signal than a coarse concept cosine, which can peak spuriously
        # for a single shared concept.
        return RankingWeights(0.6, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def full() -> "RankingWeights":
        # documented full-pipeline weighting
        return RankingWeights(0.45, 0.25, 0.15, 0.08, 0.05, 0.07, 0.25)


def authority_signal(unit: EvidenceUnit) -> float:
    return AUTHORITY_RANK[unit.authority] / 4.0


def freshness_signal(unit: EvidenceUnit) -> float:
    if unit.is_deprecated:
        return 0.0
    if unit.effective_year is None:
        return 0.5
    age = max(0, CURRENT_YEAR - unit.effective_year)
    return max(0.0, 1.0 - age / 10.0)


def specificity_signal(unit: EvidenceUnit, n_tokens: int) -> float:
    # entity-bearing, moderately short units are the most specific evidence
    ent = 0.5 if unit.entities else 0.0
    length_term = 1.0 / (1.0 + max(0, n_tokens - 8) / 8.0)
    return round(0.5 * length_term + ent, 4)


def combine(w: RankingWeights, s: RankingSignals) -> float:
    return round(
        w.lexical * s.lexical
        + w.semantic * s.semantic
        + w.authority * s.authority
        + w.freshness * s.freshness
        + w.provenance * s.provenance_completeness
        + w.specificity * s.specificity
        - w.redundancy * s.redundancy_penalty, 6)
