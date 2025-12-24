"""
Phase-12: PPV Conditioning Encoder
==================================

This module implements the PPV → conditioning signal conversion.

Architecture:
    PPV Values (8 dims, 0-7 each)
           ↓
    Canonical Signature (from Phase-11B.3)
           ↓
    PPVConditioningEncoder (FROZEN weights)
           ↓
    PPVConditioningSignal (for LLM)

CRITICAL INVARIANT:
    Encoder weights are FROZEN. No training at inference time.
    Same PPV + same signature → identical conditioning signal.

Supported Strategies:
    - EMBEDDING: PPV → fixed-dimension embedding vector
    - SOFT_PROMPT: PPV → sequence of token IDs
    - ADAPTER: PPV → adapter identifier string
    - TEXT_PREFIX: PPV → human-readable text prefix

Design Decisions:
    1. Embedding uses deterministic projection (not learned for PoC)
    2. Soft prompt uses signature-based token mapping
    3. Adapter uses canonical signature directly as identifier
    4. Text prefix is human-readable for interpretability
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from phase12_schema import (
    CANONICAL_SUBBANDS,
    PPV_DIM_COUNT,
    PPV_VALUE_RANGE,
    PPVConditioningConfig,
    PPVConditioningSignal,
    PPVEncoder,
    PPVEncodingStrategy,
)


# =============================================================================
# Constants
# =============================================================================

# Subband to index mapping for embedding
SUBBAND_INDEX: Dict[str, int] = {
    "L0": 0, "L2": 1,
    "M0": 2, "M2": 3,
    "H0": 4, "H1": 5,
}

# Token vocabulary base for soft prompts (arbitrary but deterministic)
SOFT_PROMPT_VOCAB_BASE = 50000

# Embedding dimension default
DEFAULT_EMBEDDING_DIM = 64


# =============================================================================
# Embedding Strategy Implementation
# =============================================================================

def _compute_embedding(
    ppv_values: Tuple[int, ...],
    canonical_signature: str,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> Tuple[float, ...]:
    """
    Convert PPV to embedding vector using deterministic projection.

    Strategy:
        1. Parse canonical signature into subband indices
        2. Use subband indices + position as seed for each dimension
        3. Apply deterministic hash-based projection

    Properties:
        - Deterministic: same input → same embedding
        - Position-aware: dimension positions matter
        - Subband-aware: distinguishes between canonical representatives
    """
    # Parse canonical signature (e.g., "L0_M2_H1_L0_M0_H0_L2_M2")
    subbands = canonical_signature.split("_")
    if len(subbands) != PPV_DIM_COUNT:
        raise ValueError(f"Invalid signature: expected {PPV_DIM_COUNT} parts, got {len(subbands)}")

    # Create embedding vector
    embedding: List[float] = []

    for dim_idx in range(embedding_dim):
        # Deterministic seed from signature + dimension index
        seed_str = f"{canonical_signature}|dim:{dim_idx}"
        seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()

        # Convert hash to float in [-1, 1]
        hash_int = int(seed_hash[:8], 16)
        value = (hash_int / (2**32 - 1)) * 2 - 1

        # Modulate by PPV values for position-specific influence
        ppv_influence = 0.0
        for pos, ppv_val in enumerate(ppv_values):
            # Each PPV dimension contributes based on its value and position
            pos_weight = math.sin((pos + 1) * (dim_idx + 1) * 0.1)
            ppv_influence += pos_weight * (ppv_val / 7.0)  # Normalize to [0, 1]

        ppv_influence /= PPV_DIM_COUNT  # Average influence

        # Combine base value with PPV influence
        final_value = value * 0.7 + ppv_influence * 0.3
        final_value = max(-1.0, min(1.0, final_value))  # Clamp to [-1, 1]

        embedding.append(round(final_value, 6))  # Round for determinism

    return tuple(embedding)


# =============================================================================
# Soft Prompt Strategy Implementation
# =============================================================================

def _compute_soft_prompt(
    ppv_values: Tuple[int, ...],
    canonical_signature: str,
    num_tokens: int = 8,
) -> Tuple[int, ...]:
    """
    Convert PPV to soft prompt token sequence.

    Strategy:
        1. Each PPV dimension maps to a token
        2. Token ID = base + (subband_index * 8) + ppv_value
        3. Vocabulary partitioned by subband type

    Properties:
        - Deterministic: same input → same tokens
        - Invertible: can recover PPV from tokens (for debugging)
        - Bounded vocabulary: predictable token range
    """
    subbands = canonical_signature.split("_")
    if len(subbands) != PPV_DIM_COUNT:
        raise ValueError(f"Invalid signature: expected {PPV_DIM_COUNT} parts")

    tokens: List[int] = []

    for pos in range(min(num_tokens, PPV_DIM_COUNT)):
        subband = subbands[pos]
        ppv_val = ppv_values[pos]

        # Get subband index
        subband_idx = SUBBAND_INDEX.get(subband, 0)

        # Compute token ID: base + (subband * 64) + (position * 8) + ppv_value
        # This creates unique tokens for each (subband, position, value) triple
        token_id = (
            SOFT_PROMPT_VOCAB_BASE +
            subband_idx * 64 +
            pos * 8 +
            ppv_val
        )

        tokens.append(token_id)

    # Pad with deterministic tokens if num_tokens > PPV_DIM_COUNT
    while len(tokens) < num_tokens:
        pad_hash = hashlib.sha256(f"{canonical_signature}|pad:{len(tokens)}".encode()).hexdigest()
        pad_token = SOFT_PROMPT_VOCAB_BASE + 384 + (int(pad_hash[:4], 16) % 128)
        tokens.append(pad_token)

    return tuple(tokens)


# =============================================================================
# Adapter Strategy Implementation
# =============================================================================

def _compute_adapter_id(
    ppv_values: Tuple[int, ...],
    canonical_signature: str,
) -> str:
    """
    Compute adapter identifier from PPV.

    Strategy:
        - Use canonical signature as adapter family
        - Hash for unique but reproducible identifier

    Properties:
        - Deterministic: same input → same adapter ID
        - Readable: includes canonical signature for interpretability
        - Hashable: suitable as dictionary key
    """
    # Create deterministic hash
    content = f"adapter:{canonical_signature}|ppv:{ppv_values}"
    hash_suffix = hashlib.sha256(content.encode()).hexdigest()[:8]

    return f"ppv_adapter_{canonical_signature}_{hash_suffix}"


# =============================================================================
# Text Prefix Strategy Implementation
# =============================================================================

def _compute_text_prefix(
    ppv_values: Tuple[int, ...],
    canonical_signature: str,
    template: str = "[PPV:{signature}]",
) -> str:
    """
    Compute text prefix from PPV.

    Strategy:
        - Human-readable format for interpretability
        - Includes canonical signature and raw values

    Properties:
        - Deterministic: same input → same prefix
        - Human-readable: can be understood in prompt
        - Parseable: can be extracted from generated text
    """
    # Format the template
    prefix = template.replace("{signature}", canonical_signature)
    prefix = prefix.replace("{ppv}", str(ppv_values))

    # Add expanded format if using simple template
    if template == "[PPV:{signature}]":
        # Also include raw values in a compact format
        raw_str = "".join(str(v) for v in ppv_values)
        prefix = f"[PPV:{canonical_signature}|RAW:{raw_str}]"

    return prefix


# =============================================================================
# PPV Encoder Implementation
# =============================================================================

@dataclass(frozen=True)
class FrozenPPVEncoder:
    """
    Frozen PPV encoder - weights cannot change after initialization.

    INVARIANT: Encoding is deterministic.
        Same (ppv_values, canonical_signature, config) → same PPVConditioningSignal

    CONSTRAINT: No training or fine-tuning.
        The encoder does not learn from generation output.
    """

    _config: PPVConditioningConfig

    @property
    def config(self) -> PPVConditioningConfig:
        return self._config

    def encode(
        self,
        ppv_values: Tuple[int, ...],
        canonical_signature: str,
    ) -> PPVConditioningSignal:
        """
        Encode PPV values into conditioning signal.

        Args:
            ppv_values: 8-tuple of integers (0-7 each)
            canonical_signature: Canonical signature from Phase-11B.3

        Returns:
            PPVConditioningSignal with strategy-appropriate data

        Raises:
            ValueError: If ppv_values or signature is invalid
        """
        # Validate inputs
        if len(ppv_values) != PPV_DIM_COUNT:
            raise ValueError(f"ppv_values must have {PPV_DIM_COUNT} elements")

        for i, v in enumerate(ppv_values):
            if not (PPV_VALUE_RANGE[0] <= v <= PPV_VALUE_RANGE[1]):
                raise ValueError(
                    f"ppv_values[{i}] = {v} out of range "
                    f"[{PPV_VALUE_RANGE[0]}, {PPV_VALUE_RANGE[1]}]"
                )

        # Validate canonical signature format
        parts = canonical_signature.split("_")
        if len(parts) != PPV_DIM_COUNT:
            raise ValueError(
                f"canonical_signature must have {PPV_DIM_COUNT} parts, "
                f"got {len(parts)}"
            )

        for part in parts:
            if part not in CANONICAL_SUBBANDS:
                raise ValueError(
                    f"Invalid subband '{part}' in signature. "
                    f"Expected one of {CANONICAL_SUBBANDS}"
                )

        # Compute conditioning data based on strategy
        strategy = self._config.strategy

        if strategy == PPVEncodingStrategy.EMBEDDING:
            data = _compute_embedding(
                ppv_values,
                canonical_signature,
                self._config.embedding_dim,
            )

        elif strategy == PPVEncodingStrategy.SOFT_PROMPT:
            data = _compute_soft_prompt(
                ppv_values,
                canonical_signature,
                self._config.num_prompt_tokens,
            )

        elif strategy == PPVEncodingStrategy.ADAPTER:
            data = _compute_adapter_id(ppv_values, canonical_signature)

        elif strategy == PPVEncodingStrategy.TEXT_PREFIX:
            data = _compute_text_prefix(
                ppv_values,
                canonical_signature,
                self._config.prefix_template,
            )

        else:
            raise ValueError(f"Unsupported encoding strategy: {strategy}")

        return PPVConditioningSignal(
            raw_ppv=ppv_values,
            canonical_signature=canonical_signature,
            strategy=strategy,
            conditioning_data=data,
        )


# =============================================================================
# Factory Functions
# =============================================================================

def create_embedding_encoder(
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> FrozenPPVEncoder:
    """Create encoder using EMBEDDING strategy."""
    config = PPVConditioningConfig(
        strategy=PPVEncodingStrategy.EMBEDDING,
        embedding_dim=embedding_dim,
        frozen=True,
    )
    return FrozenPPVEncoder(_config=config)


def create_soft_prompt_encoder(
    num_tokens: int = 8,
) -> FrozenPPVEncoder:
    """Create encoder using SOFT_PROMPT strategy."""
    config = PPVConditioningConfig(
        strategy=PPVEncodingStrategy.SOFT_PROMPT,
        num_prompt_tokens=num_tokens,
        frozen=True,
    )
    return FrozenPPVEncoder(_config=config)


def create_adapter_encoder(
    adapter_rank: int = 8,
) -> FrozenPPVEncoder:
    """Create encoder using ADAPTER strategy."""
    config = PPVConditioningConfig(
        strategy=PPVEncodingStrategy.ADAPTER,
        adapter_rank=adapter_rank,
        frozen=True,
    )
    return FrozenPPVEncoder(_config=config)


def create_text_prefix_encoder(
    template: str = "[PPV:{signature}]",
) -> FrozenPPVEncoder:
    """Create encoder using TEXT_PREFIX strategy."""
    config = PPVConditioningConfig(
        strategy=PPVEncodingStrategy.TEXT_PREFIX,
        prefix_template=template,
        frozen=True,
    )
    return FrozenPPVEncoder(_config=config)


# =============================================================================
# Default Encoder (for PoC)
# =============================================================================

def get_default_encoder() -> FrozenPPVEncoder:
    """
    Get default encoder for Phase-12 PoC.

    Uses TEXT_PREFIX strategy for:
        - Interpretability (can see PPV in prompts)
        - Simplicity (no learned weights needed)
        - Debuggability (easy to trace)
    """
    return create_text_prefix_encoder()


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Encoder implementation
    "FrozenPPVEncoder",
    # Factory functions
    "create_embedding_encoder",
    "create_soft_prompt_encoder",
    "create_adapter_encoder",
    "create_text_prefix_encoder",
    "get_default_encoder",
    # Constants
    "SUBBAND_INDEX",
    "SOFT_PROMPT_VOCAB_BASE",
    "DEFAULT_EMBEDDING_DIM",
]
