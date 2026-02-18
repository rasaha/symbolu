"""
Test 1: HybridG2P Determinism & Coverage
=========================================

Validates that the grapheme-to-phoneme system is:
    1. Deterministic — same input → same phonemes, every run
    2. Complete — never returns empty for real words
    3. Correct — known words match expected ARPABET sequences
    4. Stable — custom vocab, char fallback, and OOV all work
    5. Valid — all returned phonemes exist in ARPABET inventory

If G2P is non-deterministic or crashes, the entire phoneme pipeline is noise.

These tests do NOT require nltk/CMUdict/g2p_en to be installed.
They test whatever tiers are available, including the char fallback.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root on path
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from csr_phoneme_provider import (
    HybridG2P,
    ARPABET_TO_VARNA,
    PHONEME_MAP_ARPABET,
    _strip_stress,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture(scope="module")
def g2p():
    """HybridG2P instance, lazy-initialized (uses whatever tiers are available)."""
    return HybridG2P(use_neural=False, lazy_init=True)


# Valid ARPABET phoneme set (the universe of acceptable outputs)
VALID_ARPABET = set(PHONEME_MAP_ARPABET.keys())


# =========================================================================
# Test 1.1: Determinism — same word → same phonemes across calls
# =========================================================================


class TestG2PDeterminism:
    """G2P must be a pure function: same input → same output."""

    WORDS = [
        "the", "hello", "karma", "transformer", "calibration",
        "embedding", "phoneme", "ubuntu", "machine", "language",
    ]

    def test_deterministic_across_calls(self, g2p):
        """Calling get_phonemes twice on the same word returns identical results."""
        for word in self.WORDS:
            first = g2p.get_phonemes(word)
            second = g2p.get_phonemes(word)
            assert first == second, (
                f"G2P non-deterministic for '{word}': {first} != {second}"
            )

    def test_deterministic_across_instances(self):
        """Two fresh HybridG2P instances produce the same output."""
        g2p_a = HybridG2P(use_neural=False, lazy_init=True)
        g2p_b = HybridG2P(use_neural=False, lazy_init=True)

        for word in self.WORDS:
            a = g2p_a.get_phonemes(word)
            b = g2p_b.get_phonemes(word)
            assert a == b, (
                f"G2P non-deterministic across instances for '{word}': {a} != {b}"
            )

    def test_case_insensitive(self, g2p):
        """G2P is case-insensitive: 'Hello' == 'hello' == 'HELLO'."""
        for word in ["hello", "karma", "machine"]:
            lower = g2p.get_phonemes(word.lower())
            upper = g2p.get_phonemes(word.upper())
            title = g2p.get_phonemes(word.title())
            assert lower == upper == title, (
                f"G2P case-sensitive for '{word}': "
                f"lower={lower}, upper={upper}, title={title}"
            )


# =========================================================================
# Test 1.2: Completeness — never returns empty
# =========================================================================


class TestG2PCompleteness:
    """G2P must always return at least one phoneme for any non-empty string."""

    def test_common_words_non_empty(self, g2p):
        """Common English words produce non-empty phoneme lists."""
        words = [
            "the", "and", "is", "was", "for", "that", "with",
            "this", "have", "from", "are", "but", "not", "you",
            "all", "can", "her", "one", "our", "out",
        ]
        for word in words:
            phonemes = g2p.get_phonemes(word)
            assert len(phonemes) > 0, f"Empty phonemes for '{word}'"
            assert phonemes != ["SIL"], f"Got SIL (empty input marker) for '{word}'"

    def test_technical_words_non_empty(self, g2p):
        """Technical/ML terms produce phonemes (via custom vocab or fallback)."""
        words = [
            "embedding", "tokenizer", "transformer", "attention",
            "gradient", "backpropagation", "softmax", "logit",
        ]
        for word in words:
            phonemes = g2p.get_phonemes(word)
            assert len(phonemes) > 0, f"Empty phonemes for '{word}'"

    def test_sanskrit_terms_non_empty(self, g2p):
        """Sanskrit/CSR terms produce phonemes (via custom vocab)."""
        words = ["varna", "vritti", "phoneme", "symbolu", "csr", "arpabet"]
        for word in words:
            phonemes = g2p.get_phonemes(word)
            assert len(phonemes) > 0, f"Empty phonemes for '{word}'"

    def test_empty_string_returns_sil(self, g2p):
        """Empty string → SIL marker, not crash."""
        assert g2p.get_phonemes("") == ["SIL"]

    def test_punctuation_only_returns_sil(self, g2p):
        """Punctuation-only string → SIL (chars stripped to empty)."""
        assert g2p.get_phonemes("!@#$%") == ["SIL"]

    def test_single_character_non_empty(self, g2p):
        """Single characters produce at least one phoneme."""
        for ch in "abcdefghijklmnopqrstuvwxyz":
            phonemes = g2p.get_phonemes(ch)
            assert len(phonemes) > 0, f"Empty phonemes for '{ch}'"


# =========================================================================
# Test 1.3: Correctness — known words match expected phonemes
# =========================================================================


class TestG2PCorrectness:
    """Validate known phoneme decompositions from custom vocab."""

    EXPECTED = {
        # These are defined in custom_vocab — should be exact
        "varna": ["V", "AA", "R", "N", "AH"],
        "vritti": ["V", "R", "IH", "T", "IY"],
        "phoneme": ["F", "OW", "N", "IY", "M"],
        "symbolu": ["S", "IH", "M", "B", "OW", "L", "UW"],
        "bert": ["B", "ER", "T"],
        "llama": ["L", "AA", "M", "AH"],
    }

    def test_custom_vocab_exact_match(self, g2p):
        """Custom vocabulary entries return their defined phoneme sequences."""
        for word, expected in self.EXPECTED.items():
            actual = g2p.get_phonemes(word)
            assert actual == expected, (
                f"Custom vocab mismatch for '{word}': "
                f"expected {expected}, got {actual}"
            )

    def test_add_custom_word(self, g2p):
        """Adding a custom word overrides future lookups."""
        g2p.add_custom_word("testword", ["T", "EH", "S", "T"])
        result = g2p.get_phonemes("testword")
        assert result == ["T", "EH", "S", "T"]


# =========================================================================
# Test 1.4: Output Validity — all phonemes in ARPABET inventory
# =========================================================================


class TestG2PValidity:
    """All returned phonemes must be in the known ARPABET set."""

    WORDS = [
        "hello", "world", "transformer", "calibration", "embedding",
        "karma", "varna", "machine", "learning", "neural",
        "network", "gradient", "backprop", "softmax", "attention",
        "language", "model", "token", "sequence", "prediction",
    ]

    def test_all_phonemes_in_arpabet(self, g2p):
        """Every phoneme returned by G2P exists in PHONEME_MAP_ARPABET."""
        for word in self.WORDS:
            phonemes = g2p.get_phonemes(word)
            for p in phonemes:
                assert p in VALID_ARPABET, (
                    f"Unknown phoneme '{p}' from word '{word}' — "
                    f"not in ARPABET inventory ({len(VALID_ARPABET)} phonemes)"
                )

    def test_no_stress_markers(self, g2p):
        """Stress markers (0, 1, 2) should be stripped."""
        for word in self.WORDS:
            phonemes = g2p.get_phonemes(word)
            for p in phonemes:
                assert not p[-1].isdigit() or p in VALID_ARPABET, (
                    f"Stress marker not stripped from '{p}' (word '{word}')"
                )


# =========================================================================
# Test 1.5: Stress Stripping Utility
# =========================================================================


class TestStressStripping:
    """_strip_stress removes CMUdict stress markers correctly."""

    def test_strip_vowels(self):
        assert _strip_stress(["AH0", "N", "IY1"]) == ["AH", "N", "IY"]

    def test_strip_no_stress(self):
        assert _strip_stress(["K", "AA", "R"]) == ["K", "AA", "R"]

    def test_strip_secondary_stress(self):
        assert _strip_stress(["AH2", "B", "AW2", "T"]) == ["AH", "B", "AW", "T"]


# =========================================================================
# Test 1.6: Character Fallback Path
# =========================================================================


class TestCharFallback:
    """Character-level fallback (Tier 4) must produce reasonable output."""

    def test_nonsense_word_produces_phonemes(self, g2p):
        """Completely made-up words still produce phonemes via char fallback."""
        # This word won't be in CMUdict or custom vocab
        result = g2p.get_phonemes("xyzqwkjf")
        assert len(result) > 0
        for p in result:
            assert p in VALID_ARPABET or p == "UNK", (
                f"Char fallback produced invalid phoneme: {p}"
            )

    def test_fallback_respects_length_limit(self, g2p):
        """Very long words are capped (char fallback uses [:10])."""
        long_word = "a" * 100
        result = g2p.get_phonemes(long_word)
        # Char fallback caps at 10 chars
        assert len(result) <= 10, (
            f"Char fallback exceeded length limit: {len(result)} phonemes"
        )


# =========================================================================
# Test 1.7: Caching Consistency
# =========================================================================


class TestG2PCaching:
    """G2P cache must not corrupt results."""

    def test_cache_hit_matches_fresh(self, g2p):
        """Cached result == fresh computation."""
        word = "calibration"
        # First call populates cache
        first = g2p.get_phonemes(word)
        # Second call hits cache
        cached = g2p.get_phonemes(word)
        assert first == cached

    def test_cache_stats(self, g2p):
        """After lookups, cache size > 0."""
        g2p.get_phonemes("hello")
        g2p.get_phonemes("world")
        stats = g2p.get_stats()
        assert stats["cache_size"] >= 2
        assert stats["custom_vocab_size"] > 0


# =========================================================================
# Test 1.8: ARPABET Inventory Coverage
# =========================================================================


class TestARPABETCoverage:
    """The ARPABET inventory in PHONEME_MAP_ARPABET is complete."""

    EXPECTED_CONSONANTS = {
        "P", "T", "K", "B", "D", "G",    # Plosives
        "F", "TH", "S", "SH", "HH",      # Voiceless fricatives
        "V", "DH", "Z", "ZH",            # Voiced fricatives
        "CH", "JH",                        # Affricates
        "M", "N", "NG",                   # Nasals
        "L", "R",                          # Liquids
        "W", "Y",                          # Approximants
    }

    EXPECTED_VOWELS = {
        "AA", "AH", "AE", "IH", "IY", "UH", "UW", "EH", "ER",
        "EY", "AY", "OW", "AO", "OY", "AW",
    }

    def test_all_consonants_present(self):
        for c in self.EXPECTED_CONSONANTS:
            assert c in PHONEME_MAP_ARPABET, f"Missing consonant: {c}"

    def test_all_vowels_present(self):
        for v in self.EXPECTED_VOWELS:
            assert v in PHONEME_MAP_ARPABET, f"Missing vowel: {v}"

    def test_all_have_12d_affinity(self):
        """Each phoneme has a 12D ontological affinity vector."""
        for phoneme, affinity in PHONEME_MAP_ARPABET.items():
            assert len(affinity) == 12, (
                f"Phoneme '{phoneme}' has {len(affinity)}D affinity, expected 12D"
            )

    def test_special_tokens_present(self):
        for s in ["SIL", "SP", "UNK"]:
            assert s in PHONEME_MAP_ARPABET, f"Missing special token: {s}"
