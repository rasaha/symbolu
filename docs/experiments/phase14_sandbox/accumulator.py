"""
Phase-14: Accumulator
=====================

Tracks word-to-layer mappings over time and determines stability.

Core Concept:
    Instead of training weights (like transformers), we ACCUMULATE observations
    of how words map to ontological layers. Patterns that stabilize become
    "known mappings". Patterns that don't stabilize get flagged for review.

Stability States:
    - UNSTABLE: < 10 observations
    - EMERGING: 10-50 observations, confidence < 0.7
    - STABLE: 50+ observations, confidence > 0.8
    - CONFLICTED: 50+ observations, confidence < 0.5

This is the key differentiator from transformers:
    - Transformers: statistical patterns frozen in weights
    - Accumulator: explicit vote counts, auditable, editable, partial knowledge useful
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer


# =============================================================================
# Stability States
# =============================================================================

class StabilityStatus(Enum):
    """Stability status for word mappings."""
    UNSTABLE = "UNSTABLE"       # < 10 observations - too little data
    EMERGING = "EMERGING"       # 10-50 obs, confidence < 0.7 - pattern forming
    STABLE = "STABLE"           # 50+ obs, confidence > 0.8 - reliable mapping
    CONFLICTED = "CONFLICTED"   # 50+ obs, confidence < 0.5 - flag for review


# Stability thresholds
MIN_OBSERVATIONS_UNSTABLE = 10
MIN_OBSERVATIONS_STABLE = 50
CONFIDENCE_STABLE_THRESHOLD = 0.8
CONFIDENCE_CONFLICTED_THRESHOLD = 0.5


# =============================================================================
# Word Statistics
# =============================================================================

@dataclass
class WordStats:
    """
    Statistics for a single word's layer mappings.

    This is the "learned" knowledge about how this word maps to layers.
    Unlike transformer weights, these are explicit counts that can be:
    - Audited: You can see exactly why word → layer
    - Edited: You can manually adjust if wrong
    - Partial: Even 5 observations provide useful signal
    """
    word: str
    observations: int = 0
    layer_votes: Dict[str, int] = field(default_factory=dict)  # layer.value → count
    last_layer: Optional[str] = None
    source_documents: Set[str] = field(default_factory=set)

    def record_observation(
        self,
        layer: OntologicalLayer,
        source_doc: str = ""
    ) -> None:
        """Record a layer assignment observation."""
        self.observations += 1
        layer_key = layer.value
        self.layer_votes[layer_key] = self.layer_votes.get(layer_key, 0) + 1
        self.last_layer = layer_key
        if source_doc:
            self.source_documents.add(source_doc)

    def get_dominant_layer(self) -> Optional[OntologicalLayer]:
        """Get the most voted layer."""
        if not self.layer_votes:
            return None
        max_layer = max(self.layer_votes.items(), key=lambda x: x[1])
        return OntologicalLayer(max_layer[0])

    def get_confidence(self) -> float:
        """
        Compute confidence in dominant layer mapping.

        Confidence = votes_for_dominant / total_votes
        """
        if self.observations == 0:
            return 0.0
        if not self.layer_votes:
            return 0.0

        max_votes = max(self.layer_votes.values())
        return max_votes / self.observations

    def get_stability_status(self) -> StabilityStatus:
        """Determine stability status based on observations and confidence."""
        if self.observations < MIN_OBSERVATIONS_UNSTABLE:
            return StabilityStatus.UNSTABLE

        confidence = self.get_confidence()

        if self.observations >= MIN_OBSERVATIONS_STABLE:
            if confidence >= CONFIDENCE_STABLE_THRESHOLD:
                return StabilityStatus.STABLE
            elif confidence < CONFIDENCE_CONFLICTED_THRESHOLD:
                return StabilityStatus.CONFLICTED

        return StabilityStatus.EMERGING

    def get_vote_distribution(self) -> Dict[OntologicalLayer, float]:
        """Get normalized vote distribution across layers."""
        if self.observations == 0:
            return {}
        return {
            OntologicalLayer(layer): count / self.observations
            for layer, count in self.layer_votes.items()
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "word": self.word,
            "observations": self.observations,
            "layer_votes": self.layer_votes,
            "last_layer": self.last_layer,
            "source_documents": list(self.source_documents),
            "confidence": self.get_confidence(),
            "status": self.get_stability_status().value,
        }


# =============================================================================
# Accumulator Snapshot
# =============================================================================

@dataclass(frozen=True)
class AccumulatorSnapshot:
    """
    Immutable snapshot of accumulator state.

    Used for auditing and replay.
    """
    total_words: int
    total_observations: int
    stable_count: int
    emerging_count: int
    unstable_count: int
    conflicted_count: int
    snapshot_hash: str
    snapshot_version: int


# =============================================================================
# Accumulator
# =============================================================================

@dataclass
class Accumulator:
    """
    Tracks word-layer mappings over time.

    The central hypothesis: through repeated exposure (RAG retrieval),
    patterns will emerge showing how words map to ontological layers.
    These patterns are explicit (vote counts), auditable, and editable.

    Unlike transformer training:
    - No gradient descent
    - No frozen weights
    - Partial knowledge is useful
    - Mappings can be reviewed and corrected
    """
    _word_stats: Dict[str, WordStats] = field(default_factory=dict)
    _version: int = 0
    _total_observations: int = 0

    def record(
        self,
        word: str,
        layer: OntologicalLayer,
        source_doc: str = ""
    ) -> WordStats:
        """
        Record an observation of word → layer mapping.

        Args:
            word: The word being mapped
            layer: The ontological layer it was assigned to
            source_doc: Optional source document identifier

        Returns:
            Updated WordStats for the word
        """
        word_lower = word.strip().lower()

        if word_lower not in self._word_stats:
            self._word_stats[word_lower] = WordStats(word=word_lower)

        self._word_stats[word_lower].record_observation(layer, source_doc)
        self._version += 1
        self._total_observations += 1

        return self._word_stats[word_lower]

    def record_batch(
        self,
        mappings: Tuple[Tuple[str, OntologicalLayer], ...],
        source_doc: str = ""
    ) -> Tuple[WordStats, ...]:
        """Record multiple word-layer mappings."""
        results = []
        for word, layer in mappings:
            stats = self.record(word, layer, source_doc)
            results.append(stats)
        return tuple(results)

    def get_stats(self, word: str) -> Optional[WordStats]:
        """Get statistics for a word."""
        return self._word_stats.get(word.strip().lower())

    def get_all_words(self) -> Tuple[str, ...]:
        """Get all tracked words."""
        return tuple(sorted(self._word_stats.keys()))

    def get_words_by_status(self, status: StabilityStatus) -> Tuple[str, ...]:
        """Get words with a specific stability status."""
        return tuple(
            word for word, stats in self._word_stats.items()
            if stats.get_stability_status() == status
        )

    def get_stable_mappings(self) -> Dict[str, OntologicalLayer]:
        """Get all stable word → layer mappings."""
        result = {}
        for word, stats in self._word_stats.items():
            if stats.get_stability_status() == StabilityStatus.STABLE:
                dominant = stats.get_dominant_layer()
                if dominant:
                    result[word] = dominant
        return result

    def get_conflicted_words(self) -> Tuple[Tuple[str, Dict[OntologicalLayer, float]], ...]:
        """Get conflicted words with their vote distributions."""
        result = []
        for word, stats in self._word_stats.items():
            if stats.get_stability_status() == StabilityStatus.CONFLICTED:
                distribution = stats.get_vote_distribution()
                result.append((word, distribution))
        return tuple(result)

    def get_layer_vocabulary(self, layer: OntologicalLayer) -> Tuple[str, ...]:
        """Get words that predominantly map to a specific layer."""
        return tuple(
            word for word, stats in self._word_stats.items()
            if stats.get_dominant_layer() == layer
        )

    def override_mapping(
        self,
        word: str,
        layer: OntologicalLayer,
        votes: int = 100
    ) -> WordStats:
        """
        Manually override a word's mapping.

        This is the "editable" advantage over transformers.
        You can correct mistakes without retraining.
        """
        word_lower = word.strip().lower()

        if word_lower not in self._word_stats:
            self._word_stats[word_lower] = WordStats(word=word_lower)

        stats = self._word_stats[word_lower]

        # Add override votes
        layer_key = layer.value
        stats.layer_votes[layer_key] = stats.layer_votes.get(layer_key, 0) + votes
        stats.observations += votes
        stats.last_layer = layer_key

        self._version += 1
        self._total_observations += votes

        return stats

    def snapshot(self) -> AccumulatorSnapshot:
        """Create an immutable snapshot of current state."""
        stable = len(self.get_words_by_status(StabilityStatus.STABLE))
        emerging = len(self.get_words_by_status(StabilityStatus.EMERGING))
        unstable = len(self.get_words_by_status(StabilityStatus.UNSTABLE))
        conflicted = len(self.get_words_by_status(StabilityStatus.CONFLICTED))

        # Compute hash
        content = f"v{self._version}|obs:{self._total_observations}|words:{len(self._word_stats)}"
        snapshot_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        return AccumulatorSnapshot(
            total_words=len(self._word_stats),
            total_observations=self._total_observations,
            stable_count=stable,
            emerging_count=emerging,
            unstable_count=unstable,
            conflicted_count=conflicted,
            snapshot_hash=snapshot_hash,
            snapshot_version=self._version,
        )

    def get_metrics(self) -> Dict[str, float]:
        """Get accumulator metrics."""
        snapshot = self.snapshot()
        total = snapshot.total_words or 1

        return {
            "total_words": snapshot.total_words,
            "total_observations": snapshot.total_observations,
            "avg_observations_per_word": snapshot.total_observations / total,
            "stable_rate": snapshot.stable_count / total,
            "emerging_rate": snapshot.emerging_count / total,
            "unstable_rate": snapshot.unstable_count / total,
            "conflicted_rate": snapshot.conflicted_count / total,
        }

    @property
    def version(self) -> int:
        """Get current version."""
        return self._version

    @property
    def word_count(self) -> int:
        """Get number of tracked words."""
        return len(self._word_stats)

    @property
    def observation_count(self) -> int:
        """Get total observations."""
        return self._total_observations


# =============================================================================
# Accumulator Ledger Entry
# =============================================================================

@dataclass(frozen=True)
class AccumulatorLedgerEntry:
    """Ledger entry for accumulator operations."""
    operation: str  # "RECORD", "OVERRIDE", "BATCH_RECORD"
    word: str
    layer: str
    source_doc: str
    before_observations: int
    after_observations: int
    status_before: str
    status_after: str
    version: int
    entry_hash: str

    @staticmethod
    def create(
        operation: str,
        word: str,
        layer: OntologicalLayer,
        source_doc: str,
        before_obs: int,
        after_obs: int,
        status_before: StabilityStatus,
        status_after: StabilityStatus,
        version: int,
    ) -> AccumulatorLedgerEntry:
        """Create a ledger entry."""
        content = f"{operation}|{word}|{layer.value}|{version}"
        entry_hash = hashlib.sha256(content.encode()).hexdigest()[:12]

        return AccumulatorLedgerEntry(
            operation=operation,
            word=word,
            layer=layer.value,
            source_doc=source_doc,
            before_observations=before_obs,
            after_observations=after_obs,
            status_before=status_before.value,
            status_after=status_after.value,
            version=version,
            entry_hash=entry_hash,
        )


# =============================================================================
# Ledgered Accumulator
# =============================================================================

@dataclass
class LedgeredAccumulator:
    """
    Accumulator with full ledger recording.

    Every operation is logged for audit trail and replay.
    """
    _accumulator: Accumulator = field(default_factory=Accumulator)
    _ledger: List[AccumulatorLedgerEntry] = field(default_factory=list)

    def record(
        self,
        word: str,
        layer: OntologicalLayer,
        source_doc: str = ""
    ) -> WordStats:
        """Record with ledger entry."""
        word_lower = word.strip().lower()
        stats_before = self._accumulator.get_stats(word_lower)
        before_obs = stats_before.observations if stats_before else 0
        status_before = stats_before.get_stability_status() if stats_before else StabilityStatus.UNSTABLE

        stats = self._accumulator.record(word, layer, source_doc)

        entry = AccumulatorLedgerEntry.create(
            operation="RECORD",
            word=word_lower,
            layer=layer,
            source_doc=source_doc,
            before_obs=before_obs,
            after_obs=stats.observations,
            status_before=status_before,
            status_after=stats.get_stability_status(),
            version=self._accumulator.version,
        )
        self._ledger.append(entry)

        return stats

    def record_batch(
        self,
        mappings: Tuple[Tuple[str, OntologicalLayer], ...],
        source_doc: str = ""
    ) -> Tuple[WordStats, ...]:
        """Record batch with ledger entries."""
        results = []
        for word, layer in mappings:
            stats = self.record(word, layer, source_doc)
            results.append(stats)
        return tuple(results)

    def override_mapping(
        self,
        word: str,
        layer: OntologicalLayer,
        votes: int = 100
    ) -> WordStats:
        """Override with ledger entry."""
        word_lower = word.strip().lower()
        stats_before = self._accumulator.get_stats(word_lower)
        before_obs = stats_before.observations if stats_before else 0
        status_before = stats_before.get_stability_status() if stats_before else StabilityStatus.UNSTABLE

        stats = self._accumulator.override_mapping(word, layer, votes)

        entry = AccumulatorLedgerEntry.create(
            operation="OVERRIDE",
            word=word_lower,
            layer=layer,
            source_doc="manual_override",
            before_obs=before_obs,
            after_obs=stats.observations,
            status_before=status_before,
            status_after=stats.get_stability_status(),
            version=self._accumulator.version,
        )
        self._ledger.append(entry)

        return stats

    def get_ledger(self) -> Tuple[AccumulatorLedgerEntry, ...]:
        """Get full ledger."""
        return tuple(self._ledger)

    def get_stats(self, word: str) -> Optional[WordStats]:
        """Delegate to underlying accumulator."""
        return self._accumulator.get_stats(word)

    def snapshot(self) -> AccumulatorSnapshot:
        """Delegate to underlying accumulator."""
        return self._accumulator.snapshot()

    def get_metrics(self) -> Dict[str, float]:
        """Delegate to underlying accumulator."""
        return self._accumulator.get_metrics()

    def get_stable_mappings(self) -> Dict[str, OntologicalLayer]:
        """Delegate to underlying accumulator."""
        return self._accumulator.get_stable_mappings()

    def get_conflicted_words(self) -> Tuple[Tuple[str, Dict[OntologicalLayer, float]], ...]:
        """Delegate to underlying accumulator."""
        return self._accumulator.get_conflicted_words()

    def get_words_by_status(self, status: StabilityStatus) -> Tuple[str, ...]:
        """Delegate to underlying accumulator."""
        return self._accumulator.get_words_by_status(status)

    @property
    def word_count(self) -> int:
        return self._accumulator.word_count

    @property
    def observation_count(self) -> int:
        return self._accumulator.observation_count

    @property
    def version(self) -> int:
        return self._accumulator.version


# =============================================================================
# Factory Functions
# =============================================================================

def create_accumulator() -> Accumulator:
    """Create empty accumulator."""
    return Accumulator()


def create_ledgered_accumulator() -> LedgeredAccumulator:
    """Create empty ledgered accumulator."""
    return LedgeredAccumulator()


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Enums
    "StabilityStatus",
    # Data classes
    "WordStats",
    "AccumulatorSnapshot",
    "AccumulatorLedgerEntry",
    # Main classes
    "Accumulator",
    "LedgeredAccumulator",
    # Functions
    "create_accumulator",
    "create_ledgered_accumulator",
    # Constants
    "MIN_OBSERVATIONS_UNSTABLE",
    "MIN_OBSERVATIONS_STABLE",
    "CONFIDENCE_STABLE_THRESHOLD",
    "CONFIDENCE_CONFLICTED_THRESHOLD",
]
