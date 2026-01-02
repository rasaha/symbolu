"""
Sovereign-1 Observer: State Delta Computation
==============================================

Computes the 128-D State Delta in parallel with the main transformer.
Includes ontological transition validation via Bhava Transition Priors.

The Observer runs as a lightweight module that:
1. Computes Guna Pulse from attention entropy
2. Extracts S-Signal (Referent) from token lookup
3. Projects R-Signal (Ontology) from hidden states
4. Encodes C-Signal (Phonemic) from token features

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 2.4.2
"""

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


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


class SovereignObserver(nn.Module):
    """
    Computes the 128-D State Delta for Sovereign-1 architecture.

    This module runs in parallel with the main transformer to compute
    the "ground truth" cognitive state from:
    - Token identity -> C-Signal (phonemic)
    - Token identity -> S-Signal (referent)
    - Hidden states -> R-Signal (ontological)
    - Attention weights -> Guna Pulse

    The Observer provides the target state for PID Governor control
    and self-supervised training.
    """

    def __init__(
        self,
        embed_dim: int = 768,
        vocab_size: int = 50257,
        num_referent_classes: int = 32,
        use_pretrained_phonemes: bool = False,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.vocab_size = vocab_size

        # Bhava transition priors
        self.bhava_prior = BhavaTransitionPrior()

        # C-Signal: Phoneme encoding [32D]
        # Static lookup table (no gradients)
        self.register_buffer(
            'phoneme_table',
            self._init_phoneme_table(vocab_size, 32, use_pretrained_phonemes)
        )

        # S-Signal: Referent class encoding [32D]
        # One-hot encoding of referent classes
        self.register_buffer(
            'referent_table',
            torch.zeros(vocab_size, 32)  # Sparse, filled lazily
        )

        # R-Signal: Ontology projection [48D]
        # Learned projection from hidden states
        self.ontology_projector = nn.Sequential(
            nn.Linear(embed_dim, 128),
            nn.GELU(),
            nn.Linear(128, 48),
            nn.Sigmoid(),  # Force 0-1 range
        )

        # Guna computation parameters
        self.register_buffer('max_entropy', torch.tensor(math.log(512)))

    def _init_phoneme_table(
        self,
        vocab_size: int,
        output_dim: int,
        use_pretrained: bool,
    ) -> torch.Tensor:
        """Initialize phoneme feature table."""
        if use_pretrained:
            # Would load from CMU dict
            pass

        # Default: Random features (placeholder)
        # In production, load from CMU Pronouncing Dictionary
        table = torch.randn(vocab_size, output_dim) * 0.1
        return table

    @torch.no_grad()
    def compute_guna(
        self,
        attention_weights: Optional[torch.Tensor],  # [B, H, N, N]
        hidden_states: torch.Tensor,                 # [B, N, D]
        prev_hidden: Optional[torch.Tensor],         # [B, N, D]
    ) -> torch.Tensor:
        """
        Compute Guna Pulse [16D] from attention patterns.

        - Sattva (clarity): Inverse attention entropy
        - Rajas (motion): Hidden state variance
        - Tamas (inertia): Token similarity to previous
        """
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

        # Expand to 16D (redundant encoding)
        guna = torch.cat([
            guna_norm[:, 0:1].expand(-1, 5),   # Sattva
            guna_norm[:, 1:2].expand(-1, 5),   # Rajas
            guna_norm[:, 2:3].expand(-1, 6),   # Tamas
        ], dim=-1)

        return guna

    def compute_s_signal(self, token_ids: torch.Tensor) -> torch.Tensor:
        """Compute S-Signal [32D] from referent lookup."""
        return F.embedding(token_ids, self.referent_table).mean(dim=1)

    def compute_c_signal(self, token_ids: torch.Tensor) -> torch.Tensor:
        """Compute C-Signal [32D] from phoneme lookup."""
        return F.embedding(token_ids, self.phoneme_table).mean(dim=1)

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
        guna = self.compute_guna(attention_weights, hidden_states, prev_hidden)
        s_signal = self.compute_s_signal(token_ids)
        r_signal = self.compute_r_signal(hidden_states)
        c_signal = self.compute_c_signal(token_ids)

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
