"""
Sovereign Tokenizer - Data Preprocessing with Signal Extraction.

This module implements the SovereignTokenizer that wraps a standard tokenizer
and enriches each token with C-Signal (sound), S-Signal (referent), R-Signal
(intent), and Guna state.

The key insight is to "inoculate the data with truth before the model sees it"
by moving disambiguation from the neural network to the data pipeline.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

# NLTK imports with graceful fallback
try:
    import nltk
    from nltk.corpus import wordnet
    from nltk.wsd import lesk

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


def setup_nltk() -> bool:
    """
    Download required NLTK resources.

    Returns:
        True if setup successful, False otherwise.
    """
    if not NLTK_AVAILABLE:
        print("WARNING: NLTK not installed. Install with: pip install nltk")
        return False

    resources = [
        ("corpora", "wordnet"),
        ("taggers", "averaged_perceptron_tagger"),
        ("corpora", "omw-1.4"),
        ("tokenizers", "punkt"),
        ("tokenizers", "punkt_tab"),
    ]

    for category, resource in resources:
        try:
            nltk.data.find(f"{category}/{resource}")
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception as e:
                print(f"WARNING: Failed to download {resource}: {e}")
                return False

    return True


# S-Signal Categories (WordNet Lexicographer Files → Sovereign Categories)
S_SIGNAL_MAP: Dict[str, int] = {
    # Unknown / Default
    "unknown": 0,
    # Biological
    "person": 1,
    "animal": 2,
    "plant": 3,
    # Physical
    "artifact": 4,
    "structure": 5,
    "body": 5,
    "object": 5,
    # Mental
    "communication": 6,
    "cognition": 7,
    # Dynamic
    "phenomenon": 8,
    "event": 9,
    "act": 10,
    "process": 10,
    # Abstract
    "quantity": 11,
    "time": 12,
    # Social
    "location": 13,
    "group": 14,
    # Property
    "possession": 15,
    "attribute": 16,
    "state": 16,
    "feeling": 16,
    "motive": 7,
    "relation": 1,
    "shape": 16,
    "substance": 5,
    "food": 4,
    "tops": 0,
}

# Vritti Mapping (POS + Context → Cognitive Modes)
# 0=Pramāṇa (Truth), 1=Viparyaya (Error), 2=Vikalpa (Imagination),
# 3=Smṛti (Memory), 4=Nidrā (Dormancy)
VRITTI_FROM_POS: Dict[str, int] = {
    # Nouns → Pramāṇa (Truth/Facts)
    "NN": 0, "NNS": 0, "NNP": 0, "NNPS": 0,
    # Verbs of being/state → Pramāṇa
    "VB": 3, "VBD": 3, "VBG": 2, "VBN": 0, "VBP": 3, "VBZ": 3,
    # Adjectives → Vikalpa (Imagination/Quality)
    "JJ": 2, "JJR": 2, "JJS": 2,
    # Adverbs → Vikalpa (Modification/Creative)
    "RB": 2, "RBR": 2, "RBS": 2,
    # Connectors → Nidrā (Transition/Filler)
    "IN": 4, "TO": 4, "CC": 4,
    # Pronouns/Determiners → Smṛti (Memory/Reference)
    "DT": 3, "PRP": 3, "PRP$": 3, "WP": 3, "WP$": 3, "WDT": 3, "WRB": 3,
    # Numbers → Pramāṇa (Facts)
    "CD": 0,
    # Modals → Vikalpa (Hypothetical)
    "MD": 2,
    # Punctuation → Nidrā (Dormancy)
    ".": 4, ",": 4, ":": 4, ";": 4, "!": 4, "?": 4,
    # Default
    "DEFAULT": 4,
}

# Words that indicate specific Vritti states (context override)
VRITTI_KEYWORDS: Dict[str, int] = {
    # Pramāṇa (Truth) indicators
    "is": 0, "are": 0, "was": 0, "were": 0, "fact": 0, "true": 0,
    "actually": 0, "indeed": 0, "certainly": 0, "definitely": 0,
    # Viparyaya (Error/Correction) indicators
    "not": 1, "never": 1, "wrong": 1, "incorrect": 1, "false": 1,
    "but": 1, "however": 1, "although": 1, "mistake": 1,
    # Vikalpa (Imagination) indicators
    "imagine": 2, "perhaps": 2, "maybe": 2, "could": 2, "might": 2,
    "would": 2, "should": 2, "dream": 2, "wish": 2, "if": 2,
    # Smṛti (Memory) indicators
    "remember": 3, "recall": 3, "before": 3, "previous": 3, "earlier": 3,
    "he": 3, "she": 3, "it": 3, "they": 3, "this": 3, "that": 3,
    # Nidrā (Dormancy) indicators - handled by punctuation
}


# R-Signal Mapping (POS Tags → Ontology Layers)
R_SIGNAL_MAP: Dict[str, int] = {
    # Verbs → Execution layers
    "VB": 0,  # O1_ACTION (base verb)
    "VBD": 0,  # O1_ACTION (past tense)
    "VBG": 2,  # O3_EXECUTION (gerund)
    "VBN": 4,  # O5_DIRECTING (past participle)
    "VBP": 2,  # O3_EXECUTION (present)
    "VBZ": 2,  # O3_EXECUTION (3rd person)
    # Nouns → Structure
    "NN": 3,  # O4_STRUCTURE
    "NNS": 3,  # O4_STRUCTURE (plural)
    "NNP": 3,  # O4_STRUCTURE (proper)
    "NNPS": 3,  # O4_STRUCTURE (proper plural)
    # Adjectives → Quality
    "JJ": 5,  # O6_QUALITY
    "JJR": 5,  # O6_QUALITY (comparative)
    "JJS": 5,  # O6_QUALITY (superlative)
    # Adverbs → Modification
    "RB": 6,  # O7_MODIFICATION
    "RBR": 6,  # O7_MODIFICATION (comparative)
    "RBS": 6,  # O7_MODIFICATION (superlative)
    # Connectors
    "IN": 1,  # O2_CONNECTION (preposition)
    "TO": 1,  # O2_CONNECTION
    "CC": 1,  # O2_CONNECTION (conjunction)
    # Determiners/Pronouns → Reference
    "DT": 9,  # O10_REFERENCE
    "PRP": 9,  # O10_REFERENCE
    "PRP$": 9,  # O10_REFERENCE
    "WP": 7,  # O8_REASONING
    "WP$": 7,  # O8_REASONING
    "WDT": 7,  # O8_REASONING
    "WRB": 7,  # O8_REASONING
    # Numbers
    "CD": 8,  # O9_QUANTITY
    # Modals → Directing
    "MD": 4,  # O5_DIRECTING
    # Punctuation
    ".": 10,  # O11_PUNCTUATION
    ",": 10,
    ":": 10,
    ";": 10,
    "!": 10,
    "?": 10,
    # Default
    "DEFAULT": 11,  # O12_NEUTRAL
}


@dataclass(frozen=True)
class SovereignSignals:
    """Immutable container for sovereign signal outputs."""

    input_ids: torch.Tensor  # [B, Seq]
    attention_mask: torch.Tensor  # [B, Seq]
    c_signals: torch.Tensor  # [B, Seq, 32] - Sound/physics
    s_signals: torch.Tensor  # [B, Seq] - Referent category
    r_signals: torch.Tensor  # [B, Seq] - Intent/ontology
    g_states: torch.Tensor  # [B, Seq, 3] - Guna entropy


class SovereignTokenizer:
    """
    Tokenizer that enriches tokens with Sovereign signals.

    Wraps a standard HuggingFace tokenizer and adds:
    - C-Signal: SHA256 hash of word (deterministic sound signature)
    - S-Signal: WordNet category with Lesk disambiguation (referent)
    - R-Signal: POS-based ontology layer (intent)
    - Guna: Attention entropy state (dynamic)
    """

    def __init__(
        self,
        base_tokenizer: Any = None,
        use_context_disambiguation: bool = True,
        cache_size: int = 100000,
    ):
        """
        Initialize SovereignTokenizer.

        Args:
            base_tokenizer: HuggingFace tokenizer (defaults to GPT-2)
            use_context_disambiguation: Use Lesk algorithm for S-Signal
            cache_size: Maximum cache entries for signal lookups
        """
        if base_tokenizer is None:
            try:
                from transformers import GPT2Tokenizer

                base_tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
                base_tokenizer.pad_token = base_tokenizer.eos_token
            except ImportError:
                raise ImportError(
                    "transformers package required. Install with: pip install transformers"
                )

        self.tokenizer = base_tokenizer
        self.use_context = use_context_disambiguation
        self.cache_size = cache_size

        # Signal caches
        self._c_cache: Dict[str, np.ndarray] = {}
        self._s_cache: Dict[Tuple[str, str], int] = {}  # (word, context_hash) -> signal
        self._r_cache: Dict[str, int] = {}

        # Setup NLTK if available
        self._nltk_ready = setup_nltk() if NLTK_AVAILABLE else False

    def get_c_signal(self, word: str) -> np.ndarray:
        """
        Compute C-Signal (sound/physics signature).

        Uses SHA256 hash to create a deterministic 32-byte signature.
        The same word always produces the same C-Signal regardless of context.

        Args:
            word: The word to hash

        Returns:
            32-element float array in range [-1, 1]
        """
        word_lower = word.lower()

        if word_lower in self._c_cache:
            return self._c_cache[word_lower]

        hash_bytes = hashlib.sha256(word_lower.encode("utf-8")).digest()
        signal = np.frombuffer(hash_bytes, dtype=np.uint8).copy().astype(np.float32)
        signal = signal / 127.5 - 1.0  # Normalize to [-1, 1]

        # Cache management
        if len(self._c_cache) < self.cache_size:
            self._c_cache[word_lower] = signal

        return signal

    def get_s_signal(
        self, word: str, context_words: Optional[List[str]] = None
    ) -> Tuple[int, str]:
        """
        Compute S-Signal (referent/reality lock).

        Uses WordNet with Lesk disambiguation to determine the semantic
        category of a word in context.

        Args:
            word: The word to classify
            context_words: Surrounding words for disambiguation

        Returns:
            Tuple of (signal_id, category_name)
        """
        if not self._nltk_ready:
            return 0, "UNKNOWN"

        word_lower = word.lower()

        # Create context hash for caching
        context_key = ""
        if context_words and self.use_context:
            context_key = "_".join(sorted(set(w.lower() for w in context_words[:10])))

        cache_key = (word_lower, context_key)
        if cache_key in self._s_cache:
            signal = self._s_cache[cache_key]
            return signal, self._get_category_name(signal)

        try:
            # Try Lesk disambiguation if context available
            synset = None
            if context_words and self.use_context:
                synset = lesk(context_words, word_lower)

            # Fallback to most common sense
            if synset is None:
                synsets = wordnet.synsets(word_lower)
                synset = synsets[0] if synsets else None

            if synset is None:
                return 0, "UNKNOWN"

            # Extract lexicographer file name
            lex_name = synset.lexname()
            if "." in lex_name:
                category = lex_name.split(".")[1]
            else:
                category = lex_name

            signal = S_SIGNAL_MAP.get(category, 0)

            # Cache management
            if len(self._s_cache) < self.cache_size:
                self._s_cache[cache_key] = signal

            return signal, category.upper()

        except Exception:
            return 0, "UNKNOWN"

    def get_r_signal(self, word: str) -> Tuple[int, str]:
        """
        Compute R-Signal (intent/ontology layer).

        Uses POS tagging to map words to ontological layers.

        Args:
            word: The word to classify

        Returns:
            Tuple of (signal_id, layer_name)
        """
        word_lower = word.lower()

        if word_lower in self._r_cache:
            signal = self._r_cache[word_lower]
            return signal, self._get_layer_name(signal)

        if not self._nltk_ready:
            return 11, "O12_NEUTRAL"

        try:
            pos_tags = nltk.pos_tag([word])
            pos = pos_tags[0][1] if pos_tags else "DEFAULT"
            signal = R_SIGNAL_MAP.get(pos, R_SIGNAL_MAP["DEFAULT"])

            # Cache management
            if len(self._r_cache) < self.cache_size:
                self._r_cache[word_lower] = signal

            return signal, self._get_layer_name(signal)

        except Exception:
            return 11, "O12_NEUTRAL"

    def get_vritti_signal(
        self, word: str, context_words: Optional[List[str]] = None
    ) -> Tuple[int, str]:
        """
        Compute Vritti signal (cognitive mode).

        Maps words to one of 5 cognitive states:
        0 = Pramāṇa (Truth/Logic)
        1 = Viparyaya (Error/Correction)
        2 = Vikalpa (Imagination/Creative)
        3 = Smṛti (Memory/Reference)
        4 = Nidrā (Dormancy/Filler)

        Args:
            word: The word to classify
            context_words: Surrounding words for context

        Returns:
            Tuple of (vritti_id, vritti_name)
        """
        word_lower = word.lower()

        # Check keyword overrides first
        if word_lower in VRITTI_KEYWORDS:
            vritti = VRITTI_KEYWORDS[word_lower]
        else:
            # Fall back to POS-based mapping
            if self._nltk_ready:
                try:
                    pos_tags = nltk.pos_tag([word])
                    pos = pos_tags[0][1] if pos_tags else "DEFAULT"
                except Exception:
                    pos = "DEFAULT"
            else:
                pos = "DEFAULT"

            vritti = VRITTI_FROM_POS.get(pos, VRITTI_FROM_POS["DEFAULT"])

        # Context-aware adjustments
        if context_words:
            context_lower = [w.lower() for w in context_words]

            # If negation nearby, shift toward Viparyaya
            negation_words = {"not", "never", "no", "neither", "nor", "but"}
            if any(neg in context_lower for neg in negation_words):
                # Only shift if within window
                if word_lower not in negation_words:
                    vritti = max(vritti, 1)  # Lean toward Viparyaya

            # If hypothetical words nearby, shift toward Vikalpa
            hypothetical_words = {"if", "maybe", "perhaps", "could", "might", "imagine"}
            if any(hyp in context_lower for hyp in hypothetical_words):
                if word_lower not in hypothetical_words:
                    vritti = 2  # Vikalpa

        vritti_names = ["PRAMANA", "VIPARYAYA", "VIKALPA", "SMRITI", "NIDRA"]
        return vritti, vritti_names[vritti]

    def get_guna_state(self, attention_entropy: float = 0.5) -> np.ndarray:
        """
        Compute Guna state from attention entropy.

        Maps entropy to Sattva (clarity), Rajas (activity), Tamas (inertia).

        Args:
            attention_entropy: Current attention entropy [0, 1]

        Returns:
            3-element float array [Sattva, Rajas, Tamas]
        """
        # Low entropy → high Sattva (focused)
        # Medium entropy → high Rajas (exploring)
        # High entropy → high Tamas (scattered)

        if attention_entropy < 0.33:
            return np.array([0.8, 0.15, 0.05], dtype=np.float32)
        elif attention_entropy < 0.66:
            return np.array([0.2, 0.7, 0.1], dtype=np.float32)
        else:
            return np.array([0.1, 0.2, 0.7], dtype=np.float32)

    def process_batch(
        self,
        texts: List[str],
        max_length: int = 512,
        return_tensors: str = "pt",
    ) -> Dict[str, torch.Tensor]:
        """
        Process a batch of texts into Sovereign tensors.

        Args:
            texts: List of text strings
            max_length: Maximum sequence length
            return_tensors: Tensor format ("pt" for PyTorch)

        Returns:
            Dictionary containing:
            - input_ids: [B, Seq]
            - attention_mask: [B, Seq]
            - c_signals: [B, Seq, 32]
            - s_signals: [B, Seq]
            - r_signals: [B, Seq]
            - g_states: [B, Seq, 3]
        """
        # Standard tokenization
        encodings = self.tokenizer(
            texts,
            return_tensors=return_tensors,
            padding=True,
            truncation=True,
            max_length=max_length,
        )

        input_ids = encodings["input_ids"]
        attention_mask = encodings.get(
            "attention_mask", torch.ones_like(input_ids)
        )

        B, Seq = input_ids.shape

        # Initialize signal tensors
        c_signals = torch.zeros(B, Seq, 32, dtype=torch.float32)
        s_signals = torch.zeros(B, Seq, dtype=torch.long)
        r_signals = torch.zeros(B, Seq, dtype=torch.long)
        g_states = torch.zeros(B, Seq, 3, dtype=torch.float32)
        v_signals = torch.zeros(B, Seq, dtype=torch.long)  # Vritti signals

        # Process each sequence
        for b in range(B):
            tokens = self.tokenizer.convert_ids_to_tokens(input_ids[b])

            # Get context words for disambiguation
            context_words = [
                self._clean_token(t) for t in tokens if self._clean_token(t)
            ]

            for i, token in enumerate(tokens):
                clean_word = self._clean_token(token)

                if not clean_word:
                    continue

                # C-Signal (always computed)
                c_signals[b, i] = torch.tensor(self.get_c_signal(clean_word))

                # S-Signal (context-aware)
                s_signal, _ = self.get_s_signal(clean_word, context_words)
                s_signals[b, i] = s_signal

                # R-Signal (POS-based)
                r_signal, _ = self.get_r_signal(clean_word)
                r_signals[b, i] = r_signal

                # Vritti signal (cognitive mode)
                vritti, _ = self.get_vritti_signal(clean_word, context_words)
                v_signals[b, i] = vritti

                # Guna state (position-based entropy estimate)
                entropy = i / max(Seq - 1, 1)  # Simple positional entropy
                g_states[b, i] = torch.tensor(self.get_guna_state(entropy))

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "c_signals": c_signals,
            "s_signals": s_signals,
            "r_signals": r_signals,
            "g_states": g_states,
            "v_signals": v_signals,  # Vritti cognitive modes
        }

    def analyze_sentence(self, sentence: str, verbose: bool = True) -> Dict[str, Any]:
        """
        Analyze a single sentence and optionally print detailed breakdown.

        Args:
            sentence: The sentence to analyze
            verbose: Whether to print detailed output

        Returns:
            Dictionary with analysis results
        """
        if not self._nltk_ready:
            if verbose:
                print("WARNING: NLTK not available. Using fallback signals.")

        try:
            words = nltk.word_tokenize(sentence) if self._nltk_ready else sentence.split()
        except Exception:
            words = sentence.split()

        results = []

        if verbose:
            print(f"\n{'='*70}")
            print(f"ANALYZING: \"{sentence}\"")
            print(f"{'='*70}")
            print(
                f"{'TOKEN':<15} | {'C-SIGNAL':<10} | {'S-SIGNAL':<18} | {'R-SIGNAL':<15}"
            )
            print(f"{'-'*70}")

        for word in words:
            if len(word) < 2 and word.lower() not in ["i", "a"]:
                continue

            c_sig = self.get_c_signal(word)[:4]  # First 4 bytes for display
            c_hex = c_sig.tobytes()[:4].hex() if hasattr(c_sig, "tobytes") else "N/A"

            s_signal, s_name = self.get_s_signal(word, words)
            r_signal, r_name = self.get_r_signal(word)

            results.append(
                {
                    "word": word,
                    "c_signal_hex": c_hex,
                    "s_signal": s_signal,
                    "s_name": s_name,
                    "r_signal": r_signal,
                    "r_name": r_name,
                }
            )

            if verbose:
                print(f"{word:<15} | {c_hex:<10} | {s_name:<18} | {r_name:<15}")

        if verbose:
            print(f"{'='*70}\n")

        return {"sentence": sentence, "tokens": results}

    def _clean_token(self, token: str) -> str:
        """Remove tokenizer artifacts (like GPT-2's Ġ prefix)."""
        if token is None:
            return ""
        # Remove BPE artifacts
        cleaned = token.replace("Ġ", "").replace("##", "").strip()
        # Remove special tokens
        if cleaned in ["<|endoftext|>", "<pad>", "<unk>", "<s>", "</s>"]:
            return ""
        return cleaned.lower()

    def _get_category_name(self, signal: int) -> str:
        """Get category name from S-Signal value."""
        names = [
            "UNKNOWN",
            "PERSON",
            "ANIMAL",
            "PLANT",
            "ARTIFACT",
            "STRUCTURE",
            "COMMUNICATION",
            "COGNITION",
            "PHENOMENON",
            "EVENT",
            "ACT",
            "QUANTITY",
            "TIME",
            "LOCATION",
            "GROUP",
            "POSSESSION",
            "ATTRIBUTE",
        ]
        return names[signal] if signal < len(names) else "UNKNOWN"

    def _get_layer_name(self, signal: int) -> str:
        """Get layer name from R-Signal value."""
        names = [
            "O1_ACTION",
            "O2_CONNECTION",
            "O3_EXECUTION",
            "O4_STRUCTURE",
            "O5_DIRECTING",
            "O6_QUALITY",
            "O7_MODIFICATION",
            "O8_REASONING",
            "O9_QUANTITY",
            "O10_REFERENCE",
            "O11_PUNCTUATION",
            "O12_NEUTRAL",
        ]
        return names[signal] if signal < len(names) else "O12_NEUTRAL"


def test_disambiguation() -> None:
    """Test that disambiguation works correctly for homonyms."""
    print("\n" + "=" * 70)
    print("SOVEREIGN TOKENIZER - DISAMBIGUATION TEST")
    print("=" * 70)

    tagger = SovereignTokenizer()

    # Test Case 1: Bank (Financial)
    print("\n[TEST 1] Financial Context:")
    tagger.analyze_sentence("I went to the bank to deposit my money.")

    # Test Case 2: Bank (River)
    print("\n[TEST 2] Geological Context:")
    tagger.analyze_sentence("I sat on the bank of the river and fished.")

    # Test Case 3: Lead (Metal) vs Lead (Action)
    print("\n[TEST 3] Metal Context:")
    tagger.analyze_sentence("The lead pipe was heavy.")

    print("\n[TEST 4] Action Context:")
    tagger.analyze_sentence("He will lead the team to victory.")

    print("\n" + "=" * 70)
    print("KEY INSIGHT:")
    print("- C-Signal (Sound): Same word = Same hash (deterministic)")
    print("- S-Signal (Referent): Context changes category (disambiguation)")
    print("- R-Signal (Intent): POS determines ontology layer")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_disambiguation()
