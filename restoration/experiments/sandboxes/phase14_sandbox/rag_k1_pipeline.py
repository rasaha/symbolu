"""
Phase-14: RAG-K1 Pipeline
=========================

Orchestrates the phonemic-ontological accumulation pipeline.

Pipeline:
    1. Text Input (from RAG retrieval)
    2. Word Extraction
    3. Phonemic Analysis → PPV estimate → Phase-11B.3 canonicalization
    4. Layer Assignment
    5. Cross-Layer Character Derivation
    6. K1 Atom Creation
    7. Accumulator Update

This connects:
    - Phase-11B.3: PPV canonicalization
    - Phase-13: K1 store
    - Phase-14: Phonemic analysis + accumulation
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "phase11_sandbox"))
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))

from k1_schema import (
    OntologicalLayer,
    K1Slot,
    DiscourseAct,
    K1Atom,
    create_atom,
)
from k1_store import K1Store, create_empty_store

from phoneme_extractor import (
    PhonemeExtractor,
    PhonemeAnalysis,
    create_extractor,
)
from layer_assigner import (
    LayerAssigner,
    LayerAssignment,
    ContextHint,
    create_assigner,
)
from character_deriver import (
    CharacterDeriver,
    CharacterProfile,
    create_deriver,
)
from accumulator import (
    Accumulator,
    LedgeredAccumulator,
    WordStats,
    StabilityStatus,
    create_accumulator,
    create_ledgered_accumulator,
)

# Import from Phase-11B.3 for PPV canonicalization
try:
    from phase11b3_canonicalization import (
        canonicalize_from_ppv_values,
        CanonicalizationResult,
    )
    HAS_PHASE11B3 = True
except ImportError:
    HAS_PHASE11B3 = False
    CanonicalizationResult = None  # type: ignore


# =============================================================================
# Word Extraction
# =============================================================================

# Common stop words to filter out
STOP_WORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "this", "that", "these", "those", "i", "you", "he", "she", "it",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "its", "our", "their", "mine", "yours", "hers", "ours", "theirs",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "some", "any",
    "no", "not", "only", "very", "just", "also", "now", "then", "here",
    "there", "where", "when", "why", "how", "so", "if", "or", "and",
    "but", "as", "at", "by", "for", "from", "in", "into", "of", "on",
    "to", "with", "about", "after", "before", "between", "under", "over",
}

# Minimum word length for extraction
MIN_WORD_LENGTH = 2


def extract_words(text: str, include_stop_words: bool = False) -> Tuple[str, ...]:
    """
    Extract significant words from text.

    Args:
        text: Input text
        include_stop_words: Whether to include common stop words

    Returns:
        Tuple of extracted words (lowercase)
    """
    # Simple word extraction with basic tokenization
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    # Filter
    filtered = []
    for word in words:
        if len(word) < MIN_WORD_LENGTH:
            continue
        if not include_stop_words and word in STOP_WORDS:
            continue
        filtered.append(word)

    return tuple(filtered)


def extract_words_with_context(
    text: str,
    window_size: int = 2
) -> Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...]:
    """
    Extract words with preceding/following context.

    Returns:
        Tuple of (word, preceding_words, following_words)
    """
    all_words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    results = []
    for i, word in enumerate(all_words):
        if len(word) < MIN_WORD_LENGTH:
            continue

        preceding = tuple(all_words[max(0, i-window_size):i])
        following = tuple(all_words[i+1:i+1+window_size])

        results.append((word, preceding, following))

    return tuple(results)


# =============================================================================
# Pipeline Results
# =============================================================================

@dataclass(frozen=True)
class WordProcessingResult:
    """Result of processing a single word."""
    word: str
    phoneme_analysis: PhonemeAnalysis
    layer_assignment: LayerAssignment
    character_profile: CharacterProfile
    ppv_canonical_signature: Optional[str]  # From Phase-11B.3
    k1_atom_id: Optional[str]               # Created atom ID


@dataclass(frozen=True)
class PipelineResult:
    """Result of pipeline execution."""
    source_text: str
    source_doc_id: str
    words_extracted: int
    words_processed: int
    word_results: Tuple[WordProcessingResult, ...]
    k1_atoms_created: int
    accumulator_updates: int
    pipeline_hash: str


@dataclass(frozen=True)
class AccumulationReport:
    """Report on accumulation state after pipeline run."""
    total_words: int
    total_observations: int
    stable_mappings: int
    emerging_mappings: int
    conflicted_mappings: int
    top_stable_words: Tuple[Tuple[str, str, float], ...]  # (word, layer, confidence)


# =============================================================================
# Pipeline Configuration
# =============================================================================

@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for the RAG-K1 pipeline."""
    include_stop_words: bool = False
    create_k1_atoms: bool = True
    update_accumulator: bool = True
    use_phase11b3_canonicalization: bool = True
    context_window_size: int = 2


# =============================================================================
# RAG-K1 Pipeline
# =============================================================================

@dataclass
class RagK1Pipeline:
    """
    Orchestrates phonemic-ontological accumulation.

    Connects:
    - Phoneme extraction
    - Layer assignment
    - Character derivation
    - K1 atom creation (Phase-13)
    - PPV canonicalization (Phase-11B.3)
    - Pattern accumulation
    """
    _phoneme_extractor: PhonemeExtractor
    _layer_assigner: LayerAssigner
    _character_deriver: CharacterDeriver
    _accumulator: LedgeredAccumulator
    _k1_store: K1Store
    _config: PipelineConfig
    _processed_count: int = 0

    def process_text(
        self,
        text: str,
        source_doc_id: str = "unknown"
    ) -> PipelineResult:
        """
        Process a text chunk through the full pipeline.

        Steps:
            1. Extract words
            2. For each word:
                a. Phonemic analysis → PPV estimate
                b. Layer assignment
                c. Character derivation
                d. PPV canonicalization (Phase-11B.3)
                e. K1 atom creation
                f. Accumulator update
            3. Return results

        Args:
            text: Input text (e.g., from RAG retrieval)
            source_doc_id: Identifier for source document

        Returns:
            PipelineResult with all processing results
        """
        # Step 1: Extract words
        if self._config.context_window_size > 0:
            words_with_context = extract_words_with_context(
                text,
                self._config.context_window_size
            )
        else:
            words = extract_words(text, self._config.include_stop_words)
            words_with_context = tuple((w, (), ()) for w in words)

        # Step 2: Process each word
        word_results: List[WordProcessingResult] = []
        k1_atoms_created = 0
        accumulator_updates = 0

        for word, preceding, following in words_with_context:
            # Skip stop words unless configured otherwise
            if not self._config.include_stop_words and word in STOP_WORDS:
                continue

            # 2a: Phonemic analysis
            phoneme_analysis = self._phoneme_extractor.extract(word)

            # 2b: Layer assignment with context
            context = ContextHint(
                preceding_words=preceding,
                following_words=following,
            )
            layer_assignment = self._layer_assigner.assign(word, context)

            # 2c: Character derivation
            character_profile = self._character_deriver.derive(
                phoneme_analysis,
                layer_assignment.layer
            )

            # 2d: PPV canonicalization (if Phase-11B.3 available)
            ppv_canonical_signature = None
            if self._config.use_phase11b3_canonicalization and HAS_PHASE11B3:
                try:
                    canon_result = canonicalize_from_ppv_values(phoneme_analysis.ppv_estimate)
                    ppv_canonical_signature = canon_result.canonical_signature
                except Exception:
                    pass  # Skip canonicalization on error

            # 2e: K1 atom creation
            k1_atom_id = None
            if self._config.create_k1_atoms:
                atom = self._create_k1_atom(
                    word=word,
                    layer=layer_assignment.layer,
                    phoneme_hash=phoneme_analysis.analysis_hash,
                    source_doc=source_doc_id,
                )
                success, _ = self._k1_store.add_atom(atom)
                if success:
                    k1_atom_id = atom.atom_id
                    k1_atoms_created += 1

            # 2f: Accumulator update
            if self._config.update_accumulator:
                self._accumulator.record(
                    word,
                    layer_assignment.layer,
                    source_doc_id
                )
                accumulator_updates += 1

            # Create result
            result = WordProcessingResult(
                word=word,
                phoneme_analysis=phoneme_analysis,
                layer_assignment=layer_assignment,
                character_profile=character_profile,
                ppv_canonical_signature=ppv_canonical_signature,
                k1_atom_id=k1_atom_id,
            )
            word_results.append(result)

        self._processed_count += 1

        # Compute pipeline hash
        content = f"{source_doc_id}|{len(word_results)}|{self._processed_count}"
        pipeline_hash = hashlib.sha256(content.encode()).hexdigest()[:12]

        return PipelineResult(
            source_text=text[:200] + "..." if len(text) > 200 else text,
            source_doc_id=source_doc_id,
            words_extracted=len(words_with_context),
            words_processed=len(word_results),
            word_results=tuple(word_results),
            k1_atoms_created=k1_atoms_created,
            accumulator_updates=accumulator_updates,
            pipeline_hash=pipeline_hash,
        )

    def _create_k1_atom(
        self,
        word: str,
        layer: OntologicalLayer,
        phoneme_hash: str,
        source_doc: str,
    ) -> K1Atom:
        """Create a K1 atom for a word."""
        # Determine appropriate slot based on layer
        slot = self._get_slot_for_layer(layer)
        discourse_act = DiscourseAct.DECLARE

        # payload_ref is opaque pointer
        payload_ref = f"word:{word}|ph:{phoneme_hash}"
        provenance = f"rag:{source_doc}"

        return create_atom(
            layer=layer,
            slot=slot,
            discourse_act=discourse_act,
            payload_ref=payload_ref,
            provenance=provenance,
        )

    def _get_slot_for_layer(self, layer: OntologicalLayer) -> K1Slot:
        """Map layer to appropriate K1 slot."""
        # Simple mapping - can be refined
        slot_mapping = {
            OntologicalLayer.O5_COGNITION: K1Slot.TARGET,
            OntologicalLayer.O4_STRUCTURE: K1Slot.TARGET,
            OntologicalLayer.O3_EXECUTION: K1Slot.CAUSE,
            OntologicalLayer.O4_TAGGING: K1Slot.TARGET,
            OntologicalLayer.O6_AGENCY: K1Slot.CONSTRAINT,
            OntologicalLayer.O7_REASONING: K1Slot.EVIDENCE,
            OntologicalLayer.O8_PURPOSE: K1Slot.TARGET,
            OntologicalLayer.O9_WITNESSES: K1Slot.REFERENCE,
            OntologicalLayer.O10_UNIFYING: K1Slot.DEPENDENCY,
            OntologicalLayer.O12_ABSOLVING: K1Slot.EFFECT,
        }
        return slot_mapping.get(layer, K1Slot.TARGET)

    def process_batch(
        self,
        texts: Tuple[str, ...],
        source_prefix: str = "batch"
    ) -> Tuple[PipelineResult, ...]:
        """Process multiple text chunks."""
        results = []
        for i, text in enumerate(texts):
            source_doc_id = f"{source_prefix}_{i:04d}"
            result = self.process_text(text, source_doc_id)
            results.append(result)
        return tuple(results)

    def get_accumulation_report(self) -> AccumulationReport:
        """Get report on current accumulation state."""
        snapshot = self._accumulator.snapshot()
        stable_mappings = self._accumulator.get_stable_mappings()

        # Get top stable words
        top_stable = []
        for word, layer in stable_mappings.items():
            stats = self._accumulator.get_stats(word)
            if stats:
                conf = stats.get_confidence()
                top_stable.append((word, layer.value, conf))

        # Sort by confidence and take top 10
        top_stable.sort(key=lambda x: x[2], reverse=True)
        top_stable = top_stable[:10]

        return AccumulationReport(
            total_words=snapshot.total_words,
            total_observations=snapshot.total_observations,
            stable_mappings=snapshot.stable_count,
            emerging_mappings=snapshot.emerging_count,
            conflicted_mappings=snapshot.conflicted_count,
            top_stable_words=tuple(top_stable),
        )

    def get_word_info(self, word: str) -> Optional[Dict]:
        """Get full information about a word."""
        stats = self._accumulator.get_stats(word)
        if not stats:
            return None

        phoneme_analysis = self._phoneme_extractor.extract(word)
        layer_assignment = self._layer_assigner.assign(word)
        character_profile = self._character_deriver.derive(
            phoneme_analysis,
            layer_assignment.layer
        )

        return {
            "word": word,
            "stats": stats.to_dict(),
            "phonemes": phoneme_analysis.phonemes,
            "ppv_estimate": phoneme_analysis.ppv_estimate,
            "primary_layer": layer_assignment.layer.value,
            "layer_confidence": layer_assignment.confidence,
            "character_top_layers": [
                (l.value, s) for l, s in character_profile.get_top_layers(3)
            ],
        }

    @property
    def k1_store(self) -> K1Store:
        """Get the K1 store."""
        return self._k1_store

    @property
    def accumulator(self) -> LedgeredAccumulator:
        """Get the accumulator."""
        return self._accumulator


# =============================================================================
# Factory Functions
# =============================================================================

def create_pipeline(
    config: Optional[PipelineConfig] = None,
) -> RagK1Pipeline:
    """
    Create a new RAG-K1 pipeline with default components.

    Args:
        config: Optional pipeline configuration

    Returns:
        Configured RagK1Pipeline
    """
    if config is None:
        config = PipelineConfig()

    return RagK1Pipeline(
        _phoneme_extractor=create_extractor(),
        _layer_assigner=create_assigner(),
        _character_deriver=create_deriver(),
        _accumulator=create_ledgered_accumulator(),
        _k1_store=create_empty_store(),
        _config=config,
    )


def create_pipeline_with_accumulator(
    accumulator: LedgeredAccumulator,
    k1_store: Optional[K1Store] = None,
    config: Optional[PipelineConfig] = None,
) -> RagK1Pipeline:
    """
    Create pipeline with existing accumulator (for continuity).

    Args:
        accumulator: Existing accumulator to continue from
        k1_store: Optional existing K1 store
        config: Optional configuration

    Returns:
        Configured RagK1Pipeline
    """
    if config is None:
        config = PipelineConfig()

    return RagK1Pipeline(
        _phoneme_extractor=create_extractor(),
        _layer_assigner=create_assigner(),
        _character_deriver=create_deriver(),
        _accumulator=accumulator,
        _k1_store=k1_store if k1_store else create_empty_store(),
        _config=config,
    )


# =============================================================================
# Sample RAG Content (for testing)
# =============================================================================

SAMPLE_RAG_TEXTS: Tuple[str, ...] = (
    "The enzyme catalyzes the reaction between substrate molecules, producing energy.",
    "Scientists think that cellular processes form the basis of biological systems.",
    "The researcher observed how proteins direct molecular interactions in the cell.",
    "Chemical reactions cause changes in molecular structure, creating new compounds.",
    "The purpose of this study is to understand how enzymes function in metabolism.",
    "Results show that the catalyst enables the reaction to proceed more efficiently.",
    "Understanding molecular behavior requires careful analysis of chemical processes.",
    "The team built a model to predict how reactions form under various conditions.",
    "Data suggests that protein folding causes significant changes in cell function.",
    "The mechanism directs energy flow through the metabolic pathway efficiently.",
)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Data classes
    "WordProcessingResult",
    "PipelineResult",
    "AccumulationReport",
    "PipelineConfig",
    # Main class
    "RagK1Pipeline",
    # Functions
    "create_pipeline",
    "create_pipeline_with_accumulator",
    "extract_words",
    "extract_words_with_context",
    # Constants
    "STOP_WORDS",
    "MIN_WORD_LENGTH",
    "SAMPLE_RAG_TEXTS",
    "HAS_PHASE11B3",
]
