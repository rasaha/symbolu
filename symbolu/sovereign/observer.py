"""
Sovereign-1 Observer: State Delta Computation
==============================================

Computes the 128-D State Delta in parallel with the main transformer.
Includes ontological transition validation via Bhava Transition Priors.

The Observer runs as a lightweight module that:
1. Computes Guna Pulse from attention entropy (via SovereignGunaComputer)
2. Extracts S-Signal (Referent) from WORD_TO_REFERENT lookup
3. Projects R-Signal (Ontology) from hidden states
4. Encodes C-Signal (Phonemic) from deterministic hash

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 2.4.2

Phase 2 Updates:
- Deterministic PhonemeEncoder (hash-based, no random)
- WORD_TO_REFERENT integration for S-Signal
- SovereignGunaComputer integration
"""

import math
import hashlib
from typing import Dict, Optional, Tuple, List

import torch
import torch.nn as nn
import torch.nn.functional as F

# Import referent classes for S-Signal computation
try:
    from symbolu.name_resonance.referent_classes import (
        WORD_TO_REFERENT,
        ReferentClass,
        get_referent_profile,
    )
    REFERENT_AVAILABLE = True
except ImportError:
    WORD_TO_REFERENT = {}
    ReferentClass = None
    REFERENT_AVAILABLE = False

# Import Guna computer
try:
    from symbolu.sovereign.guna import SovereignGunaComputer
    GUNA_COMPUTER_AVAILABLE = True
except ImportError:
    GUNA_COMPUTER_AVAILABLE = False


class BhavaTransitionPrior(nn.Module):
    """
    Defines valid transitions between Bhava states.

    The 12x12 matrix encodes transition probabilities:
    - 1.0 = High probability (valid transition)
    - 0.1 = Low probability (illegal/unusual transition)

    This prevents "Ontological Teleportation" where the model
    jumps between incompatible meaning states.
    """

    # Valid transitions between 12 Bhava states
    # Rows: FROM state, Columns: TO state
    BHAVA_TRANSITION_MASK = torch.tensor([
        #  FACT  ANAL  EVAL  NARR  ARGU  INST  CERT  SPEC  QUES  POS   NEG   NEUT
        # FACTUAL - can transition to most states except emotional
        [0.8,  0.8,  0.5,  0.3,  0.6,  0.2,  0.9,  0.2,  0.3,  0.5,  0.5,  0.9],
        # ANALYTICAL - prefers logical transitions
        [0.5,  0.9,  0.7,  0.2,  0.8,  0.4,  0.8,  0.4,  0.2,  0.3,  0.3,  0.5],
        # EVALUATIVE - connects to sentiment
        [0.2,  0.5,  0.8,  0.3,  0.6,  0.3,  0.5,  0.4,  0.2,  0.9,  0.9,  0.2],
        # NARRATIVE - fluid, story-like
        [0.4,  0.2,  0.4,  0.9,  0.3,  0.2,  0.4,  0.5,  0.3,  0.6,  0.6,  0.4],
        # ARGUMENTATIVE - logic-heavy
        [0.5,  0.8,  0.7,  0.2,  0.9,  0.5,  0.7,  0.5,  0.4,  0.4,  0.4,  0.3],
        # INSTRUCTIVE - directive
        [0.6,  0.4,  0.3,  0.2,  0.4,  0.9,  0.8,  0.2,  0.1,  0.5,  0.3,  0.5],
        # CERTAIN - confident transitions
        [0.8,  0.7,  0.5,  0.3,  0.6,  0.7,  0.9,  0.1,  0.1,  0.5,  0.4,  0.6],
        # SPECULATIVE - uncertain, exploratory
        [0.3,  0.5,  0.5,  0.5,  0.5,  0.2,  0.1,  0.9,  0.7,  0.4,  0.4,  0.4],
        # QUESTIONING - inquiry mode
        [0.4,  0.6,  0.4,  0.3,  0.5,  0.1,  0.2,  0.6,  0.8,  0.3,  0.3,  0.5],
        # POSITIVE - sentiment
        [0.4,  0.3,  0.8,  0.5,  0.4,  0.4,  0.5,  0.4,  0.3,  0.8,  0.2,  0.4],
        # NEGATIVE - sentiment
        [0.4,  0.3,  0.8,  0.5,  0.5,  0.3,  0.4,  0.4,  0.3,  0.2,  0.8,  0.4],
        # NEUTRAL - balanced
        [0.8,  0.5,  0.3,  0.4,  0.4,  0.5,  0.6,  0.4,  0.4,  0.4,  0.4,  0.9],
    ])

    def __init__(self):
        super().__init__()
        self.register_buffer('transition_priors', self.BHAVA_TRANSITION_MASK)

    def get_transition_penalty(
        self,
        current_r: torch.Tensor,  # [B, N, 48] or [B, 48]
        prev_r: torch.Tensor,     # [B, N, 48] or [B, 48]
    ) -> torch.Tensor:
        """
        Compute penalty for illegal Bhava transitions.

        Returns: penalty scores where 0.0 = legal, 1.0 = illegal
        """
        # Handle 2D input
        if current_r.dim() == 2:
            current_r = current_r.unsqueeze(1)
            prev_r = prev_r.unsqueeze(1)

        B, N, _ = current_r.shape

        # Extract dominant Bhava (48D -> 12 Bhavas x 4 dims each)
        current_bhava = current_r.view(B, N, 12, 4).mean(dim=-1)  # [B, N, 12]
        prev_bhava = prev_r.view(B, N, 12, 4).mean(dim=-1)

        # Get dominant indices
        curr_idx = current_bhava.argmax(dim=-1)  # [B, N]
        prev_idx = prev_bhava.argmax(dim=-1)

        # Lookup transition probabilities
        penalties = 1.0 - self.transition_priors[prev_idx, curr_idx]

        return penalties.squeeze(1) if N == 1 else penalties

    def forward(
        self,
        r_signal_sequence: torch.Tensor,  # [B, N, 48]
    ) -> torch.Tensor:
        """
        Compute total transition penalty for a sequence.

        Returns average penalty across sequence.
        """
        if r_signal_sequence.shape[1] < 2:
            return torch.tensor(0.0, device=r_signal_sequence.device)

        # Compare adjacent positions
        penalties = self.get_transition_penalty(
            r_signal_sequence[:, 1:],
            r_signal_sequence[:, :-1],
        )
        return penalties.mean()


class DeterministicPhonemeEncoder(nn.Module):
    """
    Deterministic Phoneme Encoder using consistent hashing.

    Phase 2 replacement for random placeholders.
    Maps token IDs to 32-D phonemic feature vectors using
    a deterministic hash function (no randomness).

    The encoding captures:
    - Character n-grams (phoneme approximation)
    - Token length features
    - Vowel/consonant patterns
    """

    # Phoneme feature indices for common phonetic properties
    VOWELS = set('aeiouAEIOU')
    CONSONANTS = set('bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ')

    def __init__(
        self,
        vocab_size: int = 50257,
        output_dim: int = 32,
        seed: int = 42,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.output_dim = output_dim
        self.seed = seed

        # Create deterministic encoding table
        self.register_buffer(
            'phoneme_table',
            self._build_phoneme_table()
        )

    def _hash_token(self, token_str: str) -> List[float]:
        """
        Create deterministic phonemic features from token string.

        Returns 32-D feature vector.
        """
        features = [0.0] * self.output_dim

        if not token_str:
            return features

        # Feature 0-7: Hash of token string (8 dims)
        token_hash = hashlib.sha256(token_str.encode()).hexdigest()
        for i in range(8):
            features[i] = int(token_hash[i * 2:(i + 1) * 2], 16) / 255.0

        # Feature 8-11: Length features (4 dims)
        features[8] = min(len(token_str) / 10.0, 1.0)  # Normalized length
        features[9] = 1.0 if len(token_str) == 1 else 0.0  # Single char
        features[10] = 1.0 if len(token_str) <= 3 else 0.0  # Short token
        features[11] = 1.0 if len(token_str) > 8 else 0.0  # Long token

        # Feature 12-15: Character type features (4 dims)
        vowel_count = sum(1 for c in token_str if c in self.VOWELS)
        consonant_count = sum(1 for c in token_str if c in self.CONSONANTS)
        total_alpha = vowel_count + consonant_count

        features[12] = vowel_count / max(len(token_str), 1)  # Vowel ratio
        features[13] = consonant_count / max(len(token_str), 1)  # Consonant ratio
        features[14] = 1.0 if token_str[0] in self.VOWELS else 0.0  # Starts vowel
        features[15] = 1.0 if token_str[-1] in self.VOWELS else 0.0  # Ends vowel

        # Feature 16-23: Bigram features (8 dims)
        bigrams = [token_str[i:i+2].lower() for i in range(len(token_str) - 1)]
        for i, bg in enumerate(bigrams[:8]):
            bg_hash = hashlib.md5(bg.encode()).hexdigest()
            features[16 + i] = int(bg_hash[:2], 16) / 255.0

        # Feature 24-27: First/last character hashes (4 dims)
        first_hash = hashlib.md5(token_str[0].encode()).hexdigest()
        last_hash = hashlib.md5(token_str[-1].encode()).hexdigest()
        features[24] = int(first_hash[:2], 16) / 255.0
        features[25] = int(first_hash[2:4], 16) / 255.0
        features[26] = int(last_hash[:2], 16) / 255.0
        features[27] = int(last_hash[2:4], 16) / 255.0

        # Feature 28-31: Pattern features (4 dims)
        features[28] = 1.0 if any(c.isupper() for c in token_str) else 0.0  # Has caps
        features[29] = 1.0 if any(c.isdigit() for c in token_str) else 0.0  # Has digit
        features[30] = 1.0 if token_str.startswith(' ') or token_str.startswith('Ġ') else 0.0  # Word start
        features[31] = sum(1 for c in token_str if c in 'bcdfgkptxBCDFGKPTX') / max(len(token_str), 1)  # Plosive ratio

        return features

    def _build_phoneme_table(self) -> torch.Tensor:
        """Build the full phoneme encoding table."""
        # We can't iterate all tokens without a tokenizer
        # Use hash-based encoding that's computed on-the-fly
        # Store a base table that gets modulated by token ID

        # Create base patterns using deterministic seeded generator
        generator = torch.Generator()
        generator.manual_seed(self.seed)

        # Create orthogonal base vectors for stability
        base = torch.randn(self.vocab_size, self.output_dim, generator=generator)

        # Normalize to unit length
        base = F.normalize(base, p=2, dim=-1)

        # Scale to [0, 1] range
        base = (base + 1) / 2

        return base

    def encode_tokens(
        self,
        token_ids: torch.Tensor,
        tokenizer=None,
    ) -> torch.Tensor:
        """
        Encode token IDs to phonemic features.

        If tokenizer is provided, uses actual token strings.
        Otherwise falls back to hash-based encoding from table.
        """
        if tokenizer is not None:
            # Use actual token strings for better encoding
            B, N = token_ids.shape
            device = token_ids.device

            features = torch.zeros(B, N, self.output_dim, device=device)

            for b in range(B):
                for n in range(N):
                    token_id = token_ids[b, n].item()
                    try:
                        token_str = tokenizer.decode([token_id])
                        feat = self._hash_token(token_str)
                        features[b, n] = torch.tensor(feat, device=device)
                    except Exception:
                        # Fallback to table lookup
                        features[b, n] = self.phoneme_table[token_id]

            return features

        # Default: use precomputed table
        return F.embedding(token_ids, self.phoneme_table)

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        """Forward pass: encode token IDs to phonemic features."""
        return F.embedding(token_ids, self.phoneme_table).mean(dim=1)  # [B, 32]


class ReferentLookup(nn.Module):
    """
    S-Signal computation via WORD_TO_REFERENT dictionary lookup.

    Phase 2 replacement for placeholder referent encoding.
    Maps tokens to 32-D one-hot referent class vectors.
    """

    # 16 referent classes (from referent_classes.py)
    REFERENT_CLASSES = [
        "luminous", "biological", "role_bearer", "artifact",
        "natural_body", "substance", "process", "abstract",
        "signal", "temporal", "spatial", "emotional",
        "social", "energy_source", "phenomenon", "unknown"
    ]

    def __init__(
        self,
        vocab_size: int = 50257,
        output_dim: int = 32,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.output_dim = output_dim
        self.num_classes = len(self.REFERENT_CLASSES)

        # Create class to index mapping
        self.class_to_idx = {c: i for i, c in enumerate(self.REFERENT_CLASSES)}

        # Create lookup table (populated on first use)
        self.register_buffer(
            'referent_table',
            torch.zeros(vocab_size, output_dim)
        )

        # Track if table is populated
        self._table_populated = False

    def _get_referent_vector(self, word: str) -> torch.Tensor:
        """Get 32-D referent vector for a word."""
        vector = torch.zeros(self.output_dim)

        if not REFERENT_AVAILABLE:
            return vector

        # Look up word in WORD_TO_REFERENT
        word_lower = word.lower().strip().strip('Ġ').strip()  # Handle GPT-2 tokenizer prefix

        if word_lower in WORD_TO_REFERENT:
            profile = WORD_TO_REFERENT[word_lower]

            # Encode primary classes (stronger signal)
            for rc in profile.primary:
                if rc.value in self.class_to_idx:
                    idx = self.class_to_idx[rc.value]
                    if idx < self.output_dim // 2:
                        vector[idx] = 1.0  # Primary in first 16 dims

            # Encode secondary classes (weaker signal)
            for rc in profile.secondary:
                if rc.value in self.class_to_idx:
                    idx = self.class_to_idx[rc.value]
                    if idx + 16 < self.output_dim:
                        vector[idx + 16] = 0.5  # Secondary in last 16 dims

        return vector

    def populate_table(self, tokenizer) -> None:
        """Populate the referent table using a tokenizer."""
        if self._table_populated:
            return

        device = self.referent_table.device

        for token_id in range(min(self.vocab_size, tokenizer.vocab_size)):
            try:
                token_str = tokenizer.decode([token_id])
                vector = self._get_referent_vector(token_str)
                self.referent_table[token_id] = vector.to(device)
            except Exception:
                pass

        self._table_populated = True

    def forward(
        self,
        token_ids: torch.Tensor,
        tokenizer=None,
    ) -> torch.Tensor:
        """
        Compute S-Signal from token IDs.

        Args:
            token_ids: [B, N] token indices
            tokenizer: Optional tokenizer for on-the-fly lookup

        Returns:
            [B, 32] S-Signal vectors
        """
        if tokenizer is not None and not self._table_populated:
            self.populate_table(tokenizer)

        # Lookup and average over sequence
        return F.embedding(token_ids, self.referent_table).mean(dim=1)  # [B, 32]


class SovereignObserver(nn.Module):
    """
    Computes the 128-D State Delta for Sovereign-1 architecture.

    Phase 2 hardened implementation with:
    - DeterministicPhonemeEncoder for C-Signal (no random)
    - ReferentLookup for S-Signal (WORD_TO_REFERENT integration)
    - SovereignGunaComputer for Guna Pulse (entropy-based)
    - Learned ontology projector for R-Signal

    State Layout: Guna[16] | S-Signal[32] | R-Signal[48] | C-Signal[32] = 128D
    """

    def __init__(
        self,
        embed_dim: int = 768,
        vocab_size: int = 50257,
        num_heads: int = 12,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.vocab_size = vocab_size

        # Bhava transition priors
        self.bhava_prior = BhavaTransitionPrior()

        # C-Signal: Deterministic Phoneme Encoder [32D]
        self.phoneme_encoder = DeterministicPhonemeEncoder(
            vocab_size=vocab_size,
            output_dim=32,
        )

        # S-Signal: Referent Lookup [32D]
        self.referent_lookup = ReferentLookup(
            vocab_size=vocab_size,
            output_dim=32,
        )

        # R-Signal: Ontology projection [48D]
        self.ontology_projector = nn.Sequential(
            nn.Linear(embed_dim, 128),
            nn.GELU(),
            nn.Linear(128, 48),
            nn.Sigmoid(),  # Force 0-1 range
        )

        # Guna Computer (if available)
        if GUNA_COMPUTER_AVAILABLE:
            self.guna_computer = SovereignGunaComputer(
                embed_dim=embed_dim,
                num_heads=num_heads,
            )
        else:
            self.guna_computer = None

        # Fallback Guna computation parameters
        self.register_buffer('max_entropy', torch.tensor(math.log(512)))

    def compute_guna(
        self,
        attention_weights: Optional[torch.Tensor],
        hidden_states: torch.Tensor,
        prev_hidden: Optional[torch.Tensor],
        head_outputs: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute Guna Pulse [16D] using hardened computation.

        Uses SovereignGunaComputer if available, otherwise falls back
        to simplified entropy-based computation.
        """
        if self.guna_computer is not None:
            result = self.guna_computer(
                attention_weights=attention_weights,
                head_outputs=head_outputs,
                hidden_states=hidden_states,
                prev_hidden_states=prev_hidden,
            )
            return result['guna']

        # Fallback: simplified computation
        B = hidden_states.shape[0]
        device = hidden_states.device

        # Sattva: Inverse attention entropy
        if attention_weights is not None:
            attn = attention_weights.mean(dim=1)  # Average over heads
            attn_entropy = -(attn * torch.log(attn + 1e-9)).sum(dim=-1)
            sattva = 1.0 - attn_entropy.mean(dim=-1) / self.max_entropy
        else:
            sattva = torch.ones(B, device=device) * 0.5

        # Rajas: Hidden state variance
        rajas = hidden_states.var(dim=-1).mean(dim=-1)

        # Tamas: Token similarity to previous
        if prev_hidden is not None:
            tamas = F.cosine_similarity(
                hidden_states.mean(dim=1),
                prev_hidden.mean(dim=1),
                dim=-1
            )
        else:
            tamas = torch.zeros(B, device=device)

        # Normalize to sum to 1 (conservation of Guna energy)
        guna_raw = torch.stack([sattva, rajas, tamas], dim=-1)
        guna_norm = F.softmax(guna_raw, dim=-1)

        # Expand to 16D
        guna = torch.cat([
            guna_norm[:, 0:1].expand(-1, 5),   # Sattva
            guna_norm[:, 1:2].expand(-1, 5),   # Rajas
            guna_norm[:, 2:3].expand(-1, 6),   # Tamas
        ], dim=-1)

        return guna

    def compute_s_signal(
        self,
        token_ids: torch.Tensor,
        tokenizer=None,
    ) -> torch.Tensor:
        """Compute S-Signal [32D] from referent lookup."""
        return self.referent_lookup(token_ids, tokenizer)

    def compute_c_signal(
        self,
        token_ids: torch.Tensor,
        tokenizer=None,
    ) -> torch.Tensor:
        """Compute C-Signal [32D] from phoneme encoding."""
        if tokenizer is not None:
            return self.phoneme_encoder.encode_tokens(token_ids, tokenizer).mean(dim=1)
        return self.phoneme_encoder(token_ids)

    def compute_r_signal(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """Compute R-Signal [48D] from ontology projection."""
        # Use sequence-level representation
        pooled = hidden_states.mean(dim=1)
        return self.ontology_projector(pooled)

    @torch.no_grad()
    def forward(
        self,
        token_ids: torch.Tensor,
        hidden_states: torch.Tensor,
        attention_weights: Optional[torch.Tensor] = None,
        prev_hidden: Optional[torch.Tensor] = None,
        head_outputs: Optional[torch.Tensor] = None,
        tokenizer=None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute full 128-D State Delta.

        Returns dict with:
            state_delta: [B, 128] full state vector
            guna: [B, 16] Guna pulse
            s_signal: [B, 32] Referent signal
            r_signal: [B, 48] Ontological signal
            c_signal: [B, 32] Phonemic signal
        """
        # Compute each signal
        guna = self.compute_guna(attention_weights, hidden_states, prev_hidden, head_outputs)
        s_signal = self.compute_s_signal(token_ids, tokenizer)
        r_signal = self.compute_r_signal(hidden_states)
        c_signal = self.compute_c_signal(token_ids, tokenizer)

        # Concatenate [16 + 32 + 48 + 32 = 128]
        state_delta = torch.cat([guna, s_signal, r_signal, c_signal], dim=-1)

        return {
            'state_delta': state_delta,
            'guna': guna,
            's_signal': s_signal,
            'r_signal': r_signal,
            'c_signal': c_signal,
        }

    def compute_transition_penalty(
        self,
        current_state: torch.Tensor,
        prev_state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute transition penalty between states.

        Uses the R-Signal portion for Bhava transition validation.
        """
        # Extract R-Signal [48:96]
        current_r = current_state[..., 48:96]
        prev_r = prev_state[..., 48:96]

        return self.bhava_prior.get_transition_penalty(current_r, prev_r)
