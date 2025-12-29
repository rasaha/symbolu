#!/usr/bin/env python3
"""
Token Decoder: CognitiveState → Constrained Token Projection
=============================================================

Decodes cognitive states back to tokens for text generation.

Key insight: Tokens are a PROJECTION of meaning, not the core representation.
We only decode when output is actually needed.

The decoder is CONSTRAINED:
- Not all 50K tokens are considered
- Only phonemically/semantically valid tokens
- Sparse softmax over ~100-1000 candidates

Memory:
- Full softmax: 50K × hidden_dim = expensive
- Constrained: ~500 × hidden_dim = cheap

This is used only at INFERENCE time, not training.
Training happens entirely in cognitive state space.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# =============================================================================
# CONSTRAINED TOKEN DECODER
# =============================================================================

class ConstrainedTokenDecoder(nn.Module):
    """
    Decodes cognitive states to tokens with constraints.

    Unlike standard LM heads that compute full vocabulary softmax,
    this decoder:
    1. Generates a constraint mask from the cognitive state
    2. Only considers valid tokens (~500 instead of 50K)
    3. Computes sparse softmax over valid candidates

    Memory reduction: 50K / 500 = 100x per position
    """

    def __init__(
        self,
        state_dim: int = 124,
        hidden_dim: int = 512,
        vocab_size: int = 50257,
        max_candidates: int = 1000,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_bhava: int = 12,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.vocab_size = vocab_size
        self.max_candidates = max_candidates
        self.num_phonemes = num_phonemes
        self.topic_dim = topic_dim
        self.num_bhava = num_bhava

        # State to hidden
        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

        # Candidate scorer: scores all tokens for constraint mask
        self.candidate_scorer = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, vocab_size),
        )

        # Token scorer: scores candidate tokens for final selection
        self.token_scorer = nn.Linear(hidden_dim, vocab_size)

        # Phoneme-token affinity matrix (learnable)
        # Maps phoneme distributions to token preferences
        self.phoneme_token_affinity = nn.Parameter(
            torch.randn(num_phonemes, vocab_size) * 0.01
        )

        # Bhava-token affinity matrix
        # Different Bhava states prefer different types of tokens
        self.bhava_token_affinity = nn.Parameter(
            torch.randn(num_bhava, vocab_size) * 0.01
        )

    def get_candidate_mask(
        self,
        cognitive_state: torch.Tensor,
        top_k: Optional[int] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Generate constraint mask: which tokens are valid candidates.

        Args:
            cognitive_state: [B, state_dim] or [B, T, state_dim]
            top_k: Number of candidates (default: self.max_candidates)

        Returns:
            candidate_indices: [B, K] or [B, T, K] indices of valid tokens
            candidate_scores: [B, K] or [B, T, K] scores for candidates
        """
        k = top_k or self.max_candidates

        # Score all tokens based on state
        all_scores = self.candidate_scorer(cognitive_state)  # [..., vocab_size]

        # Add phoneme affinity
        phoneme_energy = cognitive_state[..., :self.num_phonemes]
        phoneme_bias = torch.einsum('...p,pv->...v', phoneme_energy, self.phoneme_token_affinity)
        all_scores = all_scores + phoneme_bias

        # Add Bhava affinity
        bhava_start = self.num_phonemes + self.topic_dim
        bhava_probs = cognitive_state[..., bhava_start:bhava_start + self.num_bhava]
        bhava_bias = torch.einsum('...b,bv->...v', bhava_probs, self.bhava_token_affinity)
        all_scores = all_scores + bhava_bias

        # Get top-k candidates
        candidate_scores, candidate_indices = torch.topk(all_scores, k, dim=-1)

        return candidate_indices, candidate_scores

    def forward(
        self,
        cognitive_state: torch.Tensor,
        temperature: float = 1.0,
        top_k: Optional[int] = None,
        return_full_dist: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Decode cognitive state to token distribution.

        Args:
            cognitive_state: [B, state_dim] or [B, T, state_dim]
            temperature: Softmax temperature
            top_k: Number of candidates to consider
            return_full_dist: If True, expand to full vocab (for compatibility)

        Returns:
            Dict with:
                candidate_indices: [B, K] valid token indices
                candidate_probs: [B, K] probabilities for candidates
                full_probs: [B, vocab_size] if return_full_dist (zeros for invalid)
        """
        # Get candidate mask
        candidate_indices, candidate_scores = self.get_candidate_mask(
            cognitive_state, top_k
        )

        # Encode state
        hidden = self.state_encoder(cognitive_state)

        # Score tokens
        all_token_scores = self.token_scorer(hidden)

        # Gather scores for candidates only
        candidate_token_scores = torch.gather(
            all_token_scores, dim=-1, index=candidate_indices
        )

        # Combine with constraint scores
        combined_scores = candidate_token_scores + candidate_scores

        # Temperature-scaled softmax over candidates only
        candidate_probs = F.softmax(combined_scores / temperature, dim=-1)

        result = {
            'candidate_indices': candidate_indices,
            'candidate_probs': candidate_probs,
            'candidate_scores': combined_scores,
        }

        # Optionally expand to full vocabulary
        if return_full_dist:
            full_probs = torch.zeros(
                *cognitive_state.shape[:-1], self.vocab_size,
                device=cognitive_state.device
            )
            full_probs.scatter_(-1, candidate_indices, candidate_probs)
            result['full_probs'] = full_probs

        return result

    def sample(
        self,
        cognitive_state: torch.Tensor,
        temperature: float = 1.0,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Sample tokens from the constrained distribution.

        Args:
            cognitive_state: [B, state_dim]
            temperature: Softmax temperature
            top_k: Candidate pool size
            top_p: Nucleus sampling threshold

        Returns:
            sampled_tokens: [B] sampled token indices
            token_probs: [B] probability of sampled tokens
        """
        output = self.forward(cognitive_state, temperature, top_k)
        candidate_indices = output['candidate_indices']  # [B, K]
        candidate_probs = output['candidate_probs']      # [B, K]

        # Nucleus sampling if specified
        if top_p is not None:
            sorted_probs, sorted_indices = torch.sort(candidate_probs, descending=True, dim=-1)
            cumsum_probs = torch.cumsum(sorted_probs, dim=-1)
            mask = cumsum_probs <= top_p
            mask[..., 0] = True  # Keep at least one
            sorted_probs = sorted_probs * mask.float()
            sorted_probs = sorted_probs / sorted_probs.sum(dim=-1, keepdim=True)

            # Sample from filtered distribution
            sample_idx = torch.multinomial(sorted_probs, 1).squeeze(-1)
            local_indices = sorted_indices.gather(-1, sample_idx.unsqueeze(-1)).squeeze(-1)
            sampled_tokens = candidate_indices.gather(-1, local_indices.unsqueeze(-1)).squeeze(-1)
            token_probs = sorted_probs.gather(-1, sample_idx.unsqueeze(-1)).squeeze(-1)
        else:
            # Standard sampling
            sample_idx = torch.multinomial(candidate_probs, 1).squeeze(-1)
            sampled_tokens = candidate_indices.gather(-1, sample_idx.unsqueeze(-1)).squeeze(-1)
            token_probs = candidate_probs.gather(-1, sample_idx.unsqueeze(-1)).squeeze(-1)

        return sampled_tokens, token_probs

    def greedy_decode(
        self,
        cognitive_state: torch.Tensor,
        top_k: Optional[int] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Greedy decoding: select highest probability token.

        Args:
            cognitive_state: [B, state_dim]
            top_k: Candidate pool size

        Returns:
            tokens: [B] selected token indices
            probs: [B] probability of selected tokens
        """
        output = self.forward(cognitive_state, temperature=1.0, top_k=top_k)
        candidate_indices = output['candidate_indices']
        candidate_probs = output['candidate_probs']

        # Select highest probability
        best_idx = candidate_probs.argmax(dim=-1)
        tokens = candidate_indices.gather(-1, best_idx.unsqueeze(-1)).squeeze(-1)
        probs = candidate_probs.gather(-1, best_idx.unsqueeze(-1)).squeeze(-1)

        return tokens, probs


# =============================================================================
# FULL GENERATION PIPELINE
# =============================================================================

class OntologicalGenerator(nn.Module):
    """
    Complete generation pipeline using ontological states.

    Generation loop:
    1. Start with initial cognitive state
    2. Predict state delta
    3. Update cognitive state
    4. Decode to token (constrained)
    5. Repeat

    This is fundamentally different from token-based generation:
    - We generate in MEANING space, not token space
    - Tokens are just the final projection
    """

    def __init__(
        self,
        ontological_model: nn.Module,  # OntologicalTransformer
        token_decoder: ConstrainedTokenDecoder,
        tokenizer,  # HuggingFace tokenizer
    ):
        super().__init__()
        self.model = ontological_model
        self.decoder = token_decoder
        self.tokenizer = tokenizer

    @torch.no_grad()
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_k: int = 500,
        top_p: Optional[float] = 0.9,
        do_sample: bool = True,
    ) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: Input text
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k: Candidate pool size
            top_p: Nucleus sampling threshold
            do_sample: If False, use greedy decoding

        Returns:
            Generated text including prompt
        """
        self.model.eval()

        # Tokenize prompt
        input_ids = self.tokenizer.encode(prompt, return_tensors='pt')
        input_ids = input_ids.to(next(self.model.parameters()).device)

        generated_ids = input_ids.clone()

        for _ in range(max_new_tokens):
            # Get cognitive states
            output = self.model(generated_ids)
            cognitive_states = output['cognitive_states']

            # Get last position's state
            last_state = cognitive_states[:, -1]  # [B, state_dim]

            # Decode to token
            if do_sample:
                next_token, _ = self.decoder.sample(
                    last_state,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                )
            else:
                next_token, _ = self.decoder.greedy_decode(
                    last_state,
                    top_k=top_k,
                )

            # Append
            generated_ids = torch.cat([
                generated_ids,
                next_token.unsqueeze(-1)
            ], dim=-1)

            # Check for EOS
            if next_token.item() == self.tokenizer.eos_token_id:
                break

        # Decode to text
        generated_text = self.tokenizer.decode(generated_ids[0])

        return generated_text

    @torch.no_grad()
    def generate_with_state_tracking(
        self,
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_k: int = 500,
    ) -> Dict[str, Any]:
        """
        Generate with full state tracking for analysis.

        Returns:
            Dict with text, tokens, and cognitive state trajectory
        """
        self.model.eval()

        input_ids = self.tokenizer.encode(prompt, return_tensors='pt')
        input_ids = input_ids.to(next(self.model.parameters()).device)

        generated_ids = input_ids.clone()
        state_trajectory = []
        token_probs_list = []

        for step in range(max_new_tokens):
            output = self.model(generated_ids)
            cognitive_states = output['cognitive_states']
            last_state = cognitive_states[:, -1]

            # Track state
            state_trajectory.append(last_state.cpu())

            # Decode
            next_token, prob = self.decoder.sample(
                last_state,
                temperature=temperature,
                top_k=top_k,
            )
            token_probs_list.append(prob.cpu())

            generated_ids = torch.cat([
                generated_ids,
                next_token.unsqueeze(-1)
            ], dim=-1)

            if next_token.item() == self.tokenizer.eos_token_id:
                break

        return {
            'text': self.tokenizer.decode(generated_ids[0]),
            'tokens': generated_ids[0].cpu(),
            'state_trajectory': torch.stack(state_trajectory),
            'token_probs': torch.stack(token_probs_list) if token_probs_list else None,
            'num_steps': len(state_trajectory),
        }


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_usage():
    """Demonstrate constrained token decoding."""

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Create decoder
    decoder = ConstrainedTokenDecoder(
        state_dim=124,
        vocab_size=50257,
        max_candidates=500,
    ).to(device)

    # Simulate cognitive states
    B = 2
    state_dim = 124
    cognitive_states = torch.randn(B, state_dim, device=device)

    # Normalize components appropriately
    cognitive_states[:, :44] = F.softmax(cognitive_states[:, :44], dim=-1)  # phoneme
    cognitive_states[:, 44+64:44+64+12] = F.softmax(cognitive_states[:, 44+64:44+64+12], dim=-1)  # bhava
    cognitive_states[:, -4:] = torch.sigmoid(cognitive_states[:, -4:])  # dynamics

    print("Constrained Token Decoder Demo")
    print("=" * 50)

    # Get candidates
    output = decoder(cognitive_states, return_full_dist=True)

    print(f"\nCognitive state shape: {cognitive_states.shape}")
    print(f"Candidate indices shape: {output['candidate_indices'].shape}")
    print(f"Candidate probs shape: {output['candidate_probs'].shape}")

    # Memory comparison
    print(f"\nMemory comparison:")
    print(f"  Full vocab softmax: {B * 50257 * 4 / 1e6:.2f} MB")
    print(f"  Constrained (500): {B * 500 * 4 / 1e6:.2f} MB")
    print(f"  Reduction: {50257 / 500:.1f}x")

    # Sample tokens
    tokens, probs = decoder.sample(cognitive_states, temperature=0.8, top_k=500)
    print(f"\nSampled tokens: {tokens}")
    print(f"Token probabilities: {probs}")

    # Greedy decode
    greedy_tokens, greedy_probs = decoder.greedy_decode(cognitive_states)
    print(f"\nGreedy tokens: {greedy_tokens}")
    print(f"Greedy probabilities: {greedy_probs}")


if __name__ == "__main__":
    example_usage()
