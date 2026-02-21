"""
Counterfactual Perturbation Module
===================================

Creates controlled perturbations of input context to test belief invariance.

Three perturbation modes:
  (a) Single-token synonym substitution via curated near-token map
  (b) Dropout-style masking on a small span (2-4 tokens)
  (c) Named entity swap with another entity of same type

All perturbations preserve broad syntax but alter local semantics.
Perturbation type and rate are logged.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn


@dataclass
class CFConfig:
    """Configuration for counterfactual perturbation."""
    mode: str = "mixed"  # "synonym", "mask", "entity_swap", "mixed"
    mask_span_min: int = 2
    mask_span_max: int = 4
    mask_token_id: int = 0  # Will be set to tokenizer's mask/unk token
    perturbation_rate: float = 0.3  # fraction of eligible positions to perturb
    positions_per_sample: int = 4  # number of CF positions per sample

    # For synonym mode: top-k nearest tokens by embedding similarity
    synonym_top_k: int = 10
    synonym_min_similarity: float = 0.5


class CounterfactualPerturber(nn.Module):
    """
    Generate counterfactual perturbations of input sequences.

    Each method preserves broad syntax but alters local semantics.
    """

    def __init__(self, config: CFConfig, vocab_size: int):
        super().__init__()
        self.config = config
        self.vocab_size = vocab_size

        # Pre-compute synonym map from embedding similarity (lazy)
        self._synonym_map: Optional[Dict[int, List[int]]] = None

        # Stats tracking
        self._stats = {
            "synonym": 0,
            "mask": 0,
            "entity_swap": 0,
            "total": 0,
        }

    def build_synonym_map(self, embedding_weight: torch.Tensor):
        """
        Build synonym map from token embedding similarity.
        embedding_weight: [vocab_size, embed_dim]
        """
        with torch.no_grad():
            # Normalize embeddings
            normed = F.normalize(embedding_weight, dim=-1)
            # Process in chunks to avoid OOM
            chunk_size = 1000
            self._synonym_map = {}
            for start in range(0, self.vocab_size, chunk_size):
                end = min(start + chunk_size, self.vocab_size)
                chunk = normed[start:end]  # [chunk, dim]
                sim = chunk @ normed.T  # [chunk, vocab]
                # Zero out self-similarity
                for i in range(end - start):
                    sim[i, start + i] = -1.0
                # Get top-k
                topk_vals, topk_ids = sim.topk(
                    self.config.synonym_top_k, dim=-1
                )
                for i in range(end - start):
                    token_id = start + i
                    mask = topk_vals[i] >= self.config.synonym_min_similarity
                    if mask.any():
                        self._synonym_map[token_id] = topk_ids[i][mask].tolist()

    def _perturb_synonym(
        self,
        input_ids: torch.Tensor,
        positions: List[int],
    ) -> Tuple[torch.Tensor, List[int]]:
        """Single-token synonym substitution."""
        cf_ids = input_ids.clone()
        used_positions = []

        for pos in positions:
            for b in range(input_ids.shape[0]):
                token = input_ids[b, pos].item()
                if self._synonym_map and token in self._synonym_map:
                    synonyms = self._synonym_map[token]
                    if synonyms:
                        replacement = random.choice(synonyms)
                        cf_ids[b, pos] = replacement
                        if pos not in used_positions:
                            used_positions.append(pos)
                else:
                    # Fallback: replace with random token (different from original)
                    replacement = random.randint(1, self.vocab_size - 1)
                    while replacement == token:
                        replacement = random.randint(1, self.vocab_size - 1)
                    cf_ids[b, pos] = replacement
                    if pos not in used_positions:
                        used_positions.append(pos)

        self._stats["synonym"] += len(used_positions)
        return cf_ids, used_positions

    def _perturb_mask(
        self,
        input_ids: torch.Tensor,
        positions: List[int],
    ) -> Tuple[torch.Tensor, List[int]]:
        """Dropout-style masking on small spans."""
        cf_ids = input_ids.clone()
        T = input_ids.shape[1]
        used_positions = []

        for pos in positions:
            span_len = random.randint(
                self.config.mask_span_min, self.config.mask_span_max
            )
            start = max(0, pos - span_len // 2)
            end = min(T, start + span_len)

            cf_ids[:, start:end] = self.config.mask_token_id
            used_positions.append(pos)

        self._stats["mask"] += len(used_positions)
        return cf_ids, used_positions

    def _perturb_entity_swap(
        self,
        input_ids: torch.Tensor,
        positions: List[int],
    ) -> Tuple[torch.Tensor, List[int]]:
        """
        Swap tokens at selected positions with other tokens from the same batch.
        Approximation of named entity swap without a full NER system.
        """
        cf_ids = input_ids.clone()
        B, T = input_ids.shape
        used_positions = []

        for pos in positions:
            if B > 1:
                # Swap with token from a different batch element at same position
                for b in range(B):
                    donor = (b + 1) % B
                    cf_ids[b, pos] = input_ids[donor, pos]
            else:
                # Single batch: swap with a nearby token
                offset = random.choice([-3, -2, -1, 1, 2, 3])
                src = max(0, min(T - 1, pos + offset))
                cf_ids[0, pos] = input_ids[0, src]

            used_positions.append(pos)

        self._stats["entity_swap"] += len(used_positions)
        return cf_ids, used_positions

    def perturb(
        self,
        input_ids: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, float]]:
        """
        Generate counterfactual version of input.

        Args:
            input_ids: [B, T]

        Returns:
            cf_ids: [B, T] perturbed input
            cf_positions: [N] positions where perturbation was applied
            stats: perturbation statistics
        """
        B, T = input_ids.shape

        # Select positions to perturb (avoid first/last few tokens)
        margin = 4
        eligible = list(range(margin, T - margin))
        n_positions = min(
            self.config.positions_per_sample,
            int(len(eligible) * self.config.perturbation_rate),
        )
        n_positions = max(1, n_positions)

        positions = sorted(random.sample(eligible, min(n_positions, len(eligible))))

        # Choose perturbation mode
        mode = self.config.mode
        if mode == "mixed":
            mode = random.choice(["synonym", "mask", "entity_swap"])

        if mode == "synonym":
            cf_ids, used_pos = self._perturb_synonym(input_ids, positions)
        elif mode == "mask":
            cf_ids, used_pos = self._perturb_mask(input_ids, positions)
        elif mode == "entity_swap":
            cf_ids, used_pos = self._perturb_entity_swap(input_ids, positions)
        else:
            raise ValueError(f"Unknown perturbation mode: {mode}")

        self._stats["total"] += len(used_pos)

        cf_positions = torch.tensor(used_pos, device=input_ids.device, dtype=torch.long)

        stats = {
            "cf_mode": mode,
            "cf_n_positions": len(used_pos),
            "cf_rate": len(used_pos) / max(1, T),
            "cf_synonym_count": self._stats["synonym"],
            "cf_mask_count": self._stats["mask"],
            "cf_entity_swap_count": self._stats["entity_swap"],
            "cf_total_count": self._stats["total"],
        }

        return cf_ids, cf_positions, stats

    def reset_stats(self):
        self._stats = {k: 0 for k in self._stats}


# Need to import F for synonym map building
import torch.nn.functional as F
