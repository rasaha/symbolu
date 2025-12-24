"""
Tests for Phase-14 Phoneme Extractor
====================================

Test Categories:
    1. Dictionary Lookup - words in mini dictionary
    2. Fallback Rules - unknown words use rules
    3. PPV Estimation - phonemes → PPV estimate
    4. Determinism - same input → same output
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phoneme_extractor import (
    PhonemeExtractor,
    PhonemeAnalysis,
    PhonemeCategory,
    create_extractor,
    create_extractor_with_dictionary,
    get_phoneme_category,
    estimate_ppv,
    apply_fallback_rules,
    MINI_DICTIONARY,
)


# =============================================================================
# Test: Dictionary Lookup
# =============================================================================

class TestDictionaryLookup:
    """Tests for dictionary-based phoneme extraction."""

    def test_known_word_uses_dictionary(self):
        """Known words use dictionary lookup."""
        extractor = create_extractor()
        analysis = extractor.extract("think")

        assert analysis.source == "dictionary"
        assert analysis.phonemes == ("TH", "IH", "NG", "K")

    def test_catalyze_phonemes(self):
        """Verify 'catalyze' phoneme extraction."""
        extractor = create_extractor()
        analysis = extractor.extract("catalyze")

        assert analysis.source == "dictionary"
        assert "K" in analysis.phonemes
        assert "AE" in analysis.phonemes

    def test_case_insensitive(self):
        """Extraction is case-insensitive."""
        extractor = create_extractor()

        analysis1 = extractor.extract("Think")
        analysis2 = extractor.extract("THINK")
        analysis3 = extractor.extract("think")

        assert analysis1.phonemes == analysis2.phonemes == analysis3.phonemes

    def test_word_stripped(self):
        """Words are stripped of whitespace."""
        extractor = create_extractor()

        analysis1 = extractor.extract("  think  ")
        analysis2 = extractor.extract("think")

        assert analysis1.word == analysis2.word

    def test_has_word(self):
        """has_word checks dictionary."""
        extractor = create_extractor()

        assert extractor.has_word("think")
        assert not extractor.has_word("xyzabc")


# =============================================================================
# Test: Fallback Rules
# =============================================================================

class TestFallbackRules:
    """Tests for rule-based phoneme extraction."""

    def test_unknown_word_uses_rules(self):
        """Unknown words use rule-based extraction."""
        extractor = create_extractor()
        analysis = extractor.extract("xyzquux")

        assert analysis.source == "rules"
        assert len(analysis.phonemes) > 0

    def test_digraph_sh(self):
        """'sh' digraph recognized."""
        phonemes = apply_fallback_rules("shell")
        assert "SH" in phonemes

    def test_digraph_th(self):
        """'th' digraph recognized."""
        phonemes = apply_fallback_rules("thump")
        assert "TH" in phonemes

    def test_digraph_ch(self):
        """'ch' digraph recognized."""
        phonemes = apply_fallback_rules("chip")
        assert "CH" in phonemes

    def test_simple_word(self):
        """Simple word processed correctly."""
        phonemes = apply_fallback_rules("cat")
        assert "K" in phonemes
        assert "AE" in phonemes
        assert "T" in phonemes


# =============================================================================
# Test: PPV Estimation
# =============================================================================

class TestPPVEstimation:
    """Tests for PPV estimation from phonemes."""

    def test_ppv_has_8_dimensions(self):
        """PPV estimate has 8 dimensions."""
        ppv = estimate_ppv(("K", "AE", "T"))
        assert len(ppv) == 8

    def test_ppv_values_in_range(self):
        """PPV values are 0-10."""
        ppv = estimate_ppv(("K", "AE", "T", "AH", "L", "AY", "Z"))
        for v in ppv:
            assert 0 <= v <= 10

    def test_empty_phonemes_returns_neutral(self):
        """Empty phonemes return neutral PPV."""
        ppv = estimate_ppv(())
        assert ppv == (5, 5, 5, 5, 5, 5, 5, 5)

    def test_plosives_have_high_attack(self):
        """Plosive-heavy words have higher attack (dim 0)."""
        plosive_ppv = estimate_ppv(("P", "T", "K", "B", "D", "G"))
        nasal_ppv = estimate_ppv(("M", "N", "NG", "M", "N", "NG"))

        # Plosives should have higher attack
        assert plosive_ppv[0] >= nasal_ppv[0]

    def test_nasals_have_high_resonance(self):
        """Nasal-heavy words have higher resonance (dim 6)."""
        nasal_ppv = estimate_ppv(("M", "N", "NG", "M", "N", "NG"))
        plosive_ppv = estimate_ppv(("P", "T", "K", "B", "D", "G"))

        # Nasals should have higher resonance
        assert nasal_ppv[6] >= plosive_ppv[6]


# =============================================================================
# Test: Phoneme Categories
# =============================================================================

class TestPhonemeCategories:
    """Tests for phoneme category classification."""

    def test_plosives_classified(self):
        """Plosives are correctly classified."""
        plosives = ["P", "B", "T", "D", "K", "G"]
        for p in plosives:
            assert get_phoneme_category(p) == PhonemeCategory.PLOSIVE

    def test_fricatives_classified(self):
        """Fricatives are correctly classified."""
        fricatives = ["F", "V", "S", "Z", "SH"]
        for f in fricatives:
            assert get_phoneme_category(f) == PhonemeCategory.FRICATIVE

    def test_nasals_classified(self):
        """Nasals are correctly classified."""
        nasals = ["M", "N", "NG"]
        for n in nasals:
            assert get_phoneme_category(n) == PhonemeCategory.NASAL

    def test_vowels_classified(self):
        """Vowels are correctly classified."""
        short = ["AH", "EH", "IH"]
        for v in short:
            assert get_phoneme_category(v) == PhonemeCategory.VOWEL_SHORT

        long = ["IY", "AY", "OW"]
        for v in long:
            assert get_phoneme_category(v) == PhonemeCategory.VOWEL_LONG

    def test_unknown_defaults_to_short_vowel(self):
        """Unknown phoneme defaults to short vowel."""
        assert get_phoneme_category("UNKNOWN") == PhonemeCategory.VOWEL_SHORT


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_extraction_deterministic_100_runs(self):
        """Same word produces same result over 100 runs."""
        extractor = create_extractor()

        first_result = extractor.extract("catalyze")
        first_hash = first_result.analysis_hash

        for _ in range(100):
            result = extractor.extract("catalyze")
            assert result.phonemes == first_result.phonemes
            assert result.ppv_estimate == first_result.ppv_estimate
            assert result.analysis_hash == first_hash

    def test_ppv_deterministic(self):
        """PPV estimation is deterministic."""
        phonemes = ("K", "AE", "T", "AH", "L", "AY", "Z")

        ppv1 = estimate_ppv(phonemes)
        for _ in range(100):
            ppv2 = estimate_ppv(phonemes)
            assert ppv1 == ppv2


# =============================================================================
# Test: Analysis Object
# =============================================================================

class TestAnalysisObject:
    """Tests for PhonemeAnalysis dataclass."""

    def test_phoneme_count(self):
        """phoneme_count returns correct count."""
        extractor = create_extractor()
        analysis = extractor.extract("think")

        assert analysis.phoneme_count() == len(analysis.phonemes)

    def test_category_counts(self):
        """category_counts returns correct distribution."""
        extractor = create_extractor()
        analysis = extractor.extract("think")

        counts = analysis.category_counts()
        total = sum(counts.values())
        assert total == analysis.phoneme_count()

    def test_dominant_category(self):
        """dominant_category returns most common."""
        extractor = create_extractor()

        # "mama" has all nasals/vowels
        analysis = extractor.extract("man")
        dominant = analysis.dominant_category()
        assert dominant is not None


# =============================================================================
# Test: Batch Processing
# =============================================================================

class TestBatchProcessing:
    """Tests for batch phoneme extraction."""

    def test_extract_batch(self):
        """Batch extraction works."""
        extractor = create_extractor()
        words = ("think", "make", "run")

        results = extractor.extract_batch(words)

        assert len(results) == 3
        for r in results:
            assert isinstance(r, PhonemeAnalysis)

    def test_batch_order_preserved(self):
        """Batch results preserve input order."""
        extractor = create_extractor()
        words = ("think", "make", "run")

        results = extractor.extract_batch(words)

        assert results[0].word == "think"
        assert results[1].word == "make"
        assert results[2].word == "run"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
