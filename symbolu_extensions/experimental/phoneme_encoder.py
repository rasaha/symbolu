#!/usr/bin/env python3
"""
Phoneme Encoder: Text → Phoneme Energy Distribution
====================================================

Converts text input to phoneme-level acoustic representations.
This is the perception layer of Tier 3 ontological training.

Key insight: Phonemes are universal (~600 across all languages)
while tokens are arbitrary (~50K+ and language-specific).

Architecture:
    text → tokenizer → token_ids → phoneme_embeddings → energy_distribution

The phoneme energy distribution represents "what sounds are active"
at each position, enabling cross-lingual transfer and acoustic grounding.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# =============================================================================
# IPA PHONEME INVENTORY
# =============================================================================

# Standard IPA phoneme set (English-focused, extensible)
# Based on CMU Pronouncing Dictionary phoneme set + IPA extensions

IPA_CONSONANTS = [
    # Plosives
    'p', 'b', 't', 'd', 'k', 'g', 'ʔ',
    # Nasals
    'm', 'n', 'ŋ',
    # Fricatives
    'f', 'v', 'θ', 'ð', 's', 'z', 'ʃ', 'ʒ', 'h',
    # Affricates
    'tʃ', 'dʒ',
    # Approximants
    'w', 'j', 'l', 'r', 'ɹ',
]

IPA_VOWELS = [
    # Monophthongs
    'i', 'ɪ', 'e', 'ɛ', 'æ', 'ə', 'ʌ', 'ɑ', 'ɔ', 'o', 'ʊ', 'u',
    # Diphthongs
    'aɪ', 'aʊ', 'ɔɪ', 'eɪ', 'oʊ',
    # R-colored
    'ɝ', 'ɚ',
]

# Special tokens
PHONEME_SPECIAL = [
    '<PAD>',    # Padding
    '<UNK>',    # Unknown phoneme
    '<SIL>',    # Silence
    '<BOS>',    # Beginning of sequence
    '<EOS>',    # End of sequence
    '<WORD>',   # Word boundary
]

# Full inventory
IPA_PHONEMES = PHONEME_SPECIAL + IPA_CONSONANTS + IPA_VOWELS

# Phoneme to index mapping
PHONEME_TO_IDX = {p: i for i, p in enumerate(IPA_PHONEMES)}
IDX_TO_PHONEME = {i: p for i, p in enumerate(IPA_PHONEMES)}

NUM_PHONEMES = len(IPA_PHONEMES)  # ~50 for English, extensible to ~600


# =============================================================================
# PHONEME FEATURES (Articulatory)
# =============================================================================

@dataclass
class ArticulatoryFeatures:
    """
    Articulatory features for a phoneme.

    These features describe HOW the sound is produced:
    - Place: Where in the mouth
    - Manner: How air flows
    - Voicing: Vocal cord vibration
    """
    place: str      # bilabial, labiodental, dental, alveolar, palatal, velar, glottal
    manner: str     # plosive, nasal, fricative, affricate, approximant, vowel
    voiced: bool    # True if vocal cords vibrate
    syllabic: bool  # True if can be syllable nucleus (vowels)

    def to_vector(self) -> torch.Tensor:
        """Convert to feature vector for neural processing."""
        # One-hot encodings
        places = ['bilabial', 'labiodental', 'dental', 'alveolar',
                  'postalveolar', 'palatal', 'velar', 'glottal', 'vowel']
        manners = ['plosive', 'nasal', 'fricative', 'affricate',
                   'approximant', 'lateral', 'vowel']

        place_vec = [1.0 if p == self.place else 0.0 for p in places]
        manner_vec = [1.0 if m == self.manner else 0.0 for m in manners]

        return torch.tensor(
            place_vec + manner_vec + [float(self.voiced), float(self.syllabic)]
        )


# Articulatory feature database (subset for demonstration)
PHONEME_FEATURES: Dict[str, ArticulatoryFeatures] = {
    'p': ArticulatoryFeatures('bilabial', 'plosive', False, False),
    'b': ArticulatoryFeatures('bilabial', 'plosive', True, False),
    't': ArticulatoryFeatures('alveolar', 'plosive', False, False),
    'd': ArticulatoryFeatures('alveolar', 'plosive', True, False),
    'k': ArticulatoryFeatures('velar', 'plosive', False, False),
    'g': ArticulatoryFeatures('velar', 'plosive', True, False),
    'm': ArticulatoryFeatures('bilabial', 'nasal', True, False),
    'n': ArticulatoryFeatures('alveolar', 'nasal', True, False),
    'ŋ': ArticulatoryFeatures('velar', 'nasal', True, False),
    's': ArticulatoryFeatures('alveolar', 'fricative', False, False),
    'z': ArticulatoryFeatures('alveolar', 'fricative', True, False),
    'f': ArticulatoryFeatures('labiodental', 'fricative', False, False),
    'v': ArticulatoryFeatures('labiodental', 'fricative', True, False),
    'i': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'ɪ': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'e': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'ɛ': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'æ': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'ə': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'ʌ': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'ɑ': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'u': ArticulatoryFeatures('vowel', 'vowel', True, True),
    'ʊ': ArticulatoryFeatures('vowel', 'vowel', True, True),
}


# =============================================================================
# GRAPHEME TO PHONEME (G2P) RULES
# =============================================================================

# Simple rule-based G2P for English (production would use neural G2P)
# This maps character sequences to phoneme sequences

G2P_RULES: Dict[str, List[str]] = {
    # Common patterns
    'th': ['θ'],  # or ['ð'] depending on context
    'sh': ['ʃ'],
    'ch': ['tʃ'],
    'ng': ['ŋ'],
    'ph': ['f'],
    'wh': ['w'],
    'ck': ['k'],
    'ee': ['i'],
    'ea': ['i'],  # simplified
    'oo': ['u'],
    'ou': ['aʊ'],
    'ow': ['oʊ'],  # or ['aʊ']
    'ai': ['eɪ'],
    'ay': ['eɪ'],
    'oi': ['ɔɪ'],
    'oy': ['ɔɪ'],

    # Single letters (simplified)
    'a': ['æ'],
    'b': ['b'],
    'c': ['k'],  # simplified
    'd': ['d'],
    'e': ['ɛ'],
    'f': ['f'],
    'g': ['g'],
    'h': ['h'],
    'i': ['ɪ'],
    'j': ['dʒ'],
    'k': ['k'],
    'l': ['l'],
    'm': ['m'],
    'n': ['n'],
    'o': ['ɑ'],
    'p': ['p'],
    'q': ['k'],
    'r': ['ɹ'],
    's': ['s'],
    't': ['t'],
    'u': ['ʌ'],
    'v': ['v'],
    'w': ['w'],
    'x': ['k', 's'],
    'y': ['j'],  # simplified
    'z': ['z'],

    # Space/punctuation
    ' ': ['<WORD>'],
    '.': ['<SIL>'],
    ',': ['<SIL>'],
    '!': ['<SIL>'],
    '?': ['<SIL>'],
}


def simple_g2p(text: str) -> List[str]:
    """
    Simple grapheme-to-phoneme conversion.

    In production, use a neural G2P model or CMU dictionary lookup.
    This is a rule-based approximation for demonstration.
    """
    text = text.lower()
    phonemes = ['<BOS>']
    i = 0

    while i < len(text):
        # Try two-character rules first
        if i + 1 < len(text):
            digraph = text[i:i+2]
            if digraph in G2P_RULES:
                phonemes.extend(G2P_RULES[digraph])
                i += 2
                continue

        # Single character
        char = text[i]
        if char in G2P_RULES:
            phonemes.extend(G2P_RULES[char])
        elif char.isalpha():
            phonemes.append('<UNK>')
        # Skip other characters

        i += 1

    phonemes.append('<EOS>')
    return phonemes


# =============================================================================
# PHONEME ENCODER MODULE
# =============================================================================

class PhonemeEncoder(nn.Module):
    """
    Encodes text into phoneme energy distributions.

    Architecture:
        tokens → embedding → conv layers → phoneme_energy[num_phonemes]

    The output is a probability distribution over phonemes,
    representing "what sounds are active" at each position.

    This enables:
    1. Cross-lingual transfer (phonemes are universal)
    2. Acoustic grounding (sounds, not arbitrary tokens)
    3. Constraint inference (phonotactic rules)
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 256,
        num_phonemes: int = NUM_PHONEMES,
        hidden_dim: int = 512,
        num_layers: int = 3,
        kernel_size: int = 5,
        dropout: float = 0.1,
        use_articulatory: bool = True,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.num_phonemes = num_phonemes
        self.use_articulatory = use_articulatory

        # Token embedding (from pretrained or learned)
        self.token_embed = nn.Embedding(vocab_size, embed_dim)

        # Convolutional layers for local pattern detection
        # Phonemes often depend on surrounding characters
        self.conv_layers = nn.ModuleList()
        in_channels = embed_dim

        for i in range(num_layers):
            out_channels = hidden_dim if i < num_layers - 1 else hidden_dim
            self.conv_layers.append(nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size, padding=kernel_size//2),
                nn.GELU(),
                nn.Dropout(dropout),
            ))
            in_channels = out_channels

        # Projection to phoneme space
        self.phoneme_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_phonemes),
        )

        # Optional articulatory feature integration
        if use_articulatory:
            # Learnable articulatory feature embeddings
            articulatory_dim = 18  # place(9) + manner(7) + voiced(1) + syllabic(1)
            self.articulatory_embed = nn.Parameter(
                torch.randn(num_phonemes, articulatory_dim) * 0.02
            )
            self.articulatory_proj = nn.Linear(articulatory_dim, num_phonemes)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_distribution: bool = True,
    ) -> torch.Tensor:
        """
        Encode tokens to phoneme energy distribution.

        Args:
            input_ids: [B, T] token indices
            return_distribution: If True, apply softmax for probability distribution

        Returns:
            phoneme_energy: [B, T, num_phonemes] energy/probability over phonemes
        """
        B, T = input_ids.shape

        # Token embeddings
        x = self.token_embed(input_ids)  # [B, T, embed_dim]

        # Conv layers expect [B, C, T]
        x = x.transpose(1, 2)  # [B, embed_dim, T]

        for conv in self.conv_layers:
            x = conv(x)  # [B, hidden_dim, T]

        x = x.transpose(1, 2)  # [B, T, hidden_dim]

        # Project to phoneme space
        phoneme_logits = self.phoneme_proj(x)  # [B, T, num_phonemes]

        # Add articulatory bias if enabled
        if self.use_articulatory:
            articulatory_bias = self.articulatory_proj(self.articulatory_embed)
            articulatory_bias = articulatory_bias.mean(dim=0)  # [num_phonemes]
            phoneme_logits = phoneme_logits + articulatory_bias

        if return_distribution:
            return F.softmax(phoneme_logits, dim=-1)
        return phoneme_logits

    def encode_text(self, text: str, tokenizer) -> torch.Tensor:
        """
        Convenience method to encode raw text.

        Args:
            text: Raw text string
            tokenizer: HuggingFace tokenizer

        Returns:
            phoneme_energy: [1, T, num_phonemes]
        """
        tokens = tokenizer.encode(text, return_tensors='pt')
        return self.forward(tokens)

    def get_dominant_phonemes(
        self,
        phoneme_energy: torch.Tensor,
        top_k: int = 3,
    ) -> List[List[str]]:
        """
        Get most active phonemes at each position.

        Args:
            phoneme_energy: [B, T, num_phonemes]
            top_k: Number of top phonemes to return

        Returns:
            List of lists of phoneme strings
        """
        B, T, _ = phoneme_energy.shape
        _, indices = torch.topk(phoneme_energy, top_k, dim=-1)

        results = []
        for b in range(B):
            seq_phonemes = []
            for t in range(T):
                pos_phonemes = [IDX_TO_PHONEME.get(idx.item(), '<UNK>')
                               for idx in indices[b, t]]
                seq_phonemes.append(pos_phonemes)
            results.append(seq_phonemes)

        return results


# =============================================================================
# PHONEME DECODER (for generation)
# =============================================================================

class PhonemeDecoder(nn.Module):
    """
    Decodes phoneme distributions back to token probabilities.

    This is used during generation to convert from phoneme space
    back to token space. Crucially, this is CONSTRAINED:
    only phonemically valid tokens are considered.

    Architecture:
        phoneme_energy[num_phonemes] → hidden → token_logits[vocab_size]

    But with masking: most tokens are zeroed out based on phonemic constraints.
    """

    def __init__(
        self,
        num_phonemes: int = NUM_PHONEMES,
        vocab_size: int = 50257,
        hidden_dim: int = 512,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.num_phonemes = num_phonemes
        self.vocab_size = vocab_size

        # Phoneme to hidden
        self.phoneme_to_hidden = nn.Sequential(
            nn.Linear(num_phonemes, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        # Hidden to vocabulary
        self.hidden_to_vocab = nn.Linear(hidden_dim, vocab_size)

        # Learnable phonemic constraint mask
        # This learns which tokens are phonemically similar
        self.phoneme_token_affinity = nn.Parameter(
            torch.randn(num_phonemes, vocab_size) * 0.01
        )

    def forward(
        self,
        phoneme_energy: torch.Tensor,
        constraint_strength: float = 1.0,
        temperature: float = 1.0,
    ) -> torch.Tensor:
        """
        Decode phoneme energy to token probabilities.

        Args:
            phoneme_energy: [B, T, num_phonemes]
            constraint_strength: How strongly to apply phonemic constraints
            temperature: Softmax temperature

        Returns:
            token_probs: [B, T, vocab_size]
        """
        # Get hidden representation
        hidden = self.phoneme_to_hidden(phoneme_energy)

        # Base token logits
        token_logits = self.hidden_to_vocab(hidden)

        # Apply phonemic constraints
        # Tokens that don't match the phoneme distribution get suppressed
        phoneme_constraint = torch.einsum(
            'btp,pv->btv',
            phoneme_energy,
            self.phoneme_token_affinity
        )

        constrained_logits = token_logits + constraint_strength * phoneme_constraint

        return F.softmax(constrained_logits / temperature, dim=-1)


# =============================================================================
# PHONOTACTIC CONSTRAINT CHECKER
# =============================================================================

class PhonotacticChecker:
    """
    Checks phonotactic constraints - which phoneme sequences are legal.

    English phonotactics examples:
    - /ŋ/ cannot start a word
    - /h/ cannot end a word
    - Certain consonant clusters are illegal

    This is used to constrain the ontological state transitions.
    """

    # Illegal word-initial clusters (English)
    ILLEGAL_INITIAL = {
        'ŋ',      # /ŋ/ never starts English words
        'ʒ',      # /ʒ/ rare initially
    }

    # Illegal word-final phonemes (English)
    ILLEGAL_FINAL = {
        'h',      # /h/ never ends English words
    }

    # Illegal two-phoneme sequences
    ILLEGAL_SEQUENCES = {
        ('ŋ', 'r'),   # /ŋr/ doesn't occur
        ('h', 'ŋ'),   # /hŋ/ doesn't occur
    }

    @classmethod
    def is_valid_sequence(cls, phonemes: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Check if a phoneme sequence is phonotactically valid.

        Returns:
            (is_valid, error_message)
        """
        if not phonemes:
            return True, None

        # Check initial
        first = phonemes[0]
        if first in cls.ILLEGAL_INITIAL:
            return False, f"Illegal word-initial phoneme: {first}"

        # Check final
        last = phonemes[-1]
        if last in cls.ILLEGAL_FINAL:
            return False, f"Illegal word-final phoneme: {last}"

        # Check sequences
        for i in range(len(phonemes) - 1):
            pair = (phonemes[i], phonemes[i+1])
            if pair in cls.ILLEGAL_SEQUENCES:
                return False, f"Illegal phoneme sequence: {pair}"

        return True, None

    @classmethod
    def get_valid_next_phonemes(
        cls,
        current_phoneme: str,
        position: str = 'middle',  # 'initial', 'middle', 'final'
    ) -> List[str]:
        """
        Get phonemes that can legally follow the current one.

        This is used to generate constraint masks for the ontological model.
        """
        valid = []

        for phoneme in IPA_PHONEMES:
            if phoneme.startswith('<'):
                continue  # Skip special tokens

            # Check if sequence is valid
            pair = (current_phoneme, phoneme)
            if pair not in cls.ILLEGAL_SEQUENCES:
                # Check position constraints
                if position == 'final' and phoneme in cls.ILLEGAL_FINAL:
                    continue
                valid.append(phoneme)

        return valid


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_usage():
    """Demonstrate phoneme encoding."""

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Create encoder
    encoder = PhonemeEncoder(
        vocab_size=50257,
        embed_dim=256,
        num_phonemes=NUM_PHONEMES,
    ).to(device)

    # Simulate token input
    B, T = 2, 20
    input_ids = torch.randint(0, 50257, (B, T), device=device)

    # Encode to phoneme space
    phoneme_energy = encoder(input_ids)

    print(f"Input shape: {input_ids.shape}")
    print(f"Phoneme energy shape: {phoneme_energy.shape}")
    print(f"Num phonemes: {NUM_PHONEMES}")

    # Show dominant phonemes for first position
    dominant = encoder.get_dominant_phonemes(phoneme_energy, top_k=3)
    print(f"\nDominant phonemes (first sequence, first 5 positions):")
    for t in range(min(5, T)):
        print(f"  Position {t}: {dominant[0][t]}")

    # Test G2P
    text = "hello world"
    phonemes = simple_g2p(text)
    print(f"\nG2P for '{text}': {phonemes}")

    # Test phonotactic checker
    test_sequences = [
        ['h', 'ɛ', 'l', 'oʊ'],  # Valid
        ['ŋ', 'æ', 't'],        # Invalid (ŋ initial)
    ]

    print("\nPhonotactic validation:")
    for seq in test_sequences:
        valid, error = PhonotacticChecker.is_valid_sequence(seq)
        status = "✓ Valid" if valid else f"✗ Invalid: {error}"
        print(f"  {seq}: {status}")


if __name__ == "__main__":
    example_usage()
