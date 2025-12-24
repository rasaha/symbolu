"""
Tests for Phase-14 RAG-K1 Pipeline
==================================

Test Categories:
    1. Word Extraction - text tokenization
    2. Pipeline Integration - full flow
    3. K1 Atom Creation - atoms created correctly
    4. Accumulation - patterns tracked
    5. Determinism - same input → same output
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer, K1Query

from rag_k1_pipeline import (
    RagK1Pipeline,
    PipelineConfig,
    PipelineResult,
    WordProcessingResult,
    AccumulationReport,
    create_pipeline,
    extract_words,
    extract_words_with_context,
    SAMPLE_RAG_TEXTS,
    STOP_WORDS,
)


# =============================================================================
# Test: Word Extraction
# =============================================================================

class TestWordExtraction:
    """Tests for word extraction from text."""

    def test_extract_basic(self):
        """Basic word extraction works."""
        text = "The enzyme catalyzes the reaction."
        words = extract_words(text)

        assert "enzyme" in words
        assert "catalyzes" in words
        assert "reaction" in words

    def test_extract_filters_stop_words(self):
        """Stop words are filtered by default."""
        text = "The enzyme catalyzes the reaction."
        words = extract_words(text)

        assert "the" not in words
        assert "enzyme" in words

    def test_extract_includes_stop_words_when_asked(self):
        """Stop words included when requested."""
        text = "The enzyme catalyzes the reaction."
        words = extract_words(text, include_stop_words=True)

        assert "the" in words
        assert "enzyme" in words

    def test_extract_lowercase(self):
        """Words are lowercased."""
        text = "The Enzyme CATALYZES"
        words = extract_words(text)

        assert "enzyme" in words
        assert "catalyzes" in words
        assert "ENZYME" not in words

    def test_extract_with_context(self):
        """Context extraction provides preceding/following."""
        text = "The enzyme catalyzes the reaction."
        results = extract_words_with_context(text, window_size=2)

        # Find "catalyzes" result
        catalyzes_result = next(
            (r for r in results if r[0] == "catalyzes"),
            None
        )
        assert catalyzes_result is not None

        word, preceding, following = catalyzes_result
        assert word == "catalyzes"
        assert "enzyme" in preceding
        assert "the" in following or "reaction" in following


# =============================================================================
# Test: Pipeline Integration
# =============================================================================

class TestPipelineIntegration:
    """Tests for full pipeline flow."""

    def test_process_text_returns_result(self):
        """process_text returns PipelineResult."""
        pipeline = create_pipeline()
        result = pipeline.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        assert isinstance(result, PipelineResult)
        assert result.words_processed > 0

    def test_process_text_creates_word_results(self):
        """Each word gets a processing result."""
        pipeline = create_pipeline()
        result = pipeline.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        assert len(result.word_results) > 0
        for wr in result.word_results:
            assert isinstance(wr, WordProcessingResult)
            assert wr.word
            assert wr.phoneme_analysis is not None
            assert wr.layer_assignment is not None
            assert wr.character_profile is not None

    def test_process_batch(self):
        """Batch processing works."""
        pipeline = create_pipeline()
        results = pipeline.process_batch(SAMPLE_RAG_TEXTS[:3], "batch")

        assert len(results) == 3
        for r in results:
            assert isinstance(r, PipelineResult)


# =============================================================================
# Test: K1 Atom Creation
# =============================================================================

class TestK1AtomCreation:
    """Tests for K1 atom creation."""

    def test_atoms_created(self):
        """K1 atoms are created for words."""
        config = PipelineConfig(create_k1_atoms=True)
        pipeline = create_pipeline(config)

        result = pipeline.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        assert result.k1_atoms_created > 0

    def test_atoms_in_store(self):
        """Created atoms are in K1 store."""
        config = PipelineConfig(create_k1_atoms=True)
        pipeline = create_pipeline(config)

        pipeline.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        store = pipeline.k1_store
        assert store.count() > 0

    def test_atoms_have_correct_layer(self):
        """Atoms have layer matching assignment."""
        config = PipelineConfig(create_k1_atoms=True)
        pipeline = create_pipeline(config)

        result = pipeline.process_text("think", "test_doc")

        # Find think's result
        think_result = next(
            (wr for wr in result.word_results if wr.word == "think"),
            None
        )
        if think_result and think_result.k1_atom_id:
            query = K1Query()
            query_result = pipeline.k1_store.query(query)
            atom = next(
                (a for a in query_result.atoms if a.atom_id == think_result.k1_atom_id),
                None
            )
            if atom:
                assert atom.layer == think_result.layer_assignment.layer

    def test_config_disables_atom_creation(self):
        """Atom creation can be disabled."""
        config = PipelineConfig(create_k1_atoms=False)
        pipeline = create_pipeline(config)

        result = pipeline.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        assert result.k1_atoms_created == 0


# =============================================================================
# Test: Accumulation
# =============================================================================

class TestAccumulation:
    """Tests for pattern accumulation."""

    def test_observations_recorded(self):
        """Observations are recorded in accumulator."""
        pipeline = create_pipeline()

        pipeline.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        assert pipeline.accumulator.observation_count > 0

    def test_accumulation_report(self):
        """Accumulation report is generated."""
        pipeline = create_pipeline()

        pipeline.process_text("think about thinking", "doc1")
        pipeline.process_text("think about thought", "doc2")

        report = pipeline.get_accumulation_report()
        assert isinstance(report, AccumulationReport)
        assert report.total_observations > 0

    def test_multiple_docs_accumulate(self):
        """Multiple documents accumulate observations."""
        pipeline = create_pipeline()

        for i, text in enumerate(SAMPLE_RAG_TEXTS[:5]):
            pipeline.process_text(text, f"doc_{i}")

        assert pipeline.accumulator.word_count > 0
        assert pipeline.accumulator.observation_count >= pipeline.accumulator.word_count

    def test_config_disables_accumulation(self):
        """Accumulation can be disabled."""
        config = PipelineConfig(update_accumulator=False)
        pipeline = create_pipeline(config)

        pipeline.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        assert pipeline.accumulator.observation_count == 0


# =============================================================================
# Test: Word Info
# =============================================================================

class TestWordInfo:
    """Tests for word information retrieval."""

    def test_get_word_info(self):
        """get_word_info returns full info."""
        pipeline = create_pipeline()

        pipeline.process_text("think about thinking", "doc1")

        info = pipeline.get_word_info("think")
        assert info is not None
        assert info["word"] == "think"
        assert "phonemes" in info
        assert "ppv_estimate" in info
        assert "primary_layer" in info
        assert "stats" in info

    def test_get_word_info_unknown(self):
        """get_word_info returns None for unknown word."""
        pipeline = create_pipeline()

        info = pipeline.get_word_info("xyznotaword")
        assert info is None


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_pipeline_deterministic(self):
        """Same input produces same output."""
        config = PipelineConfig()

        # Process same text twice with fresh pipelines
        pipeline1 = create_pipeline(config)
        result1 = pipeline1.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        pipeline2 = create_pipeline(config)
        result2 = pipeline2.process_text(
            "The enzyme catalyzes the reaction.",
            "test_doc"
        )

        # Same words extracted
        assert result1.words_processed == result2.words_processed

        # Same layers assigned
        layers1 = [wr.layer_assignment.layer for wr in result1.word_results]
        layers2 = [wr.layer_assignment.layer for wr in result2.word_results]
        assert layers1 == layers2

    def test_word_results_deterministic(self):
        """Word processing results are deterministic."""
        pipeline = create_pipeline()

        result1 = pipeline.process_text("catalyze", "doc1")

        # Reset pipeline
        pipeline2 = create_pipeline()
        result2 = pipeline2.process_text("catalyze", "doc2")

        wr1 = result1.word_results[0]
        wr2 = result2.word_results[0]

        assert wr1.phoneme_analysis.phonemes == wr2.phoneme_analysis.phonemes
        assert wr1.phoneme_analysis.ppv_estimate == wr2.phoneme_analysis.ppv_estimate
        assert wr1.layer_assignment.layer == wr2.layer_assignment.layer


# =============================================================================
# Test: Sample RAG Texts
# =============================================================================

class TestSampleRAGTexts:
    """Tests using sample RAG content."""

    def test_process_all_samples(self):
        """All sample texts can be processed."""
        pipeline = create_pipeline()

        for i, text in enumerate(SAMPLE_RAG_TEXTS):
            result = pipeline.process_text(text, f"sample_{i}")
            assert result.words_processed > 0

    def test_samples_build_vocabulary(self):
        """Processing samples builds vocabulary."""
        pipeline = create_pipeline()

        for i, text in enumerate(SAMPLE_RAG_TEXTS):
            pipeline.process_text(text, f"sample_{i}")

        # Should have reasonable vocabulary
        assert pipeline.accumulator.word_count >= 20

    def test_scientific_terms_extracted(self):
        """Scientific terms are extracted from samples."""
        pipeline = create_pipeline()

        for i, text in enumerate(SAMPLE_RAG_TEXTS):
            pipeline.process_text(text, f"sample_{i}")

        # Check for scientific vocabulary
        scientific_words = ["enzyme", "catalyzes", "reaction", "molecular", "protein"]
        found = [w for w in scientific_words if pipeline.accumulator.get_stats(w)]

        assert len(found) >= 2  # At least some scientific terms found


# =============================================================================
# Test: Pipeline Hash
# =============================================================================

class TestPipelineHash:
    """Tests for pipeline result hashing."""

    def test_result_has_hash(self):
        """Pipeline result has hash."""
        pipeline = create_pipeline()
        result = pipeline.process_text("test", "doc")

        assert len(result.pipeline_hash) == 12

    def test_different_docs_different_hash(self):
        """Different source docs produce different hashes."""
        pipeline = create_pipeline()

        result1 = pipeline.process_text("test", "doc1")
        result2 = pipeline.process_text("test", "doc2")

        assert result1.pipeline_hash != result2.pipeline_hash


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
