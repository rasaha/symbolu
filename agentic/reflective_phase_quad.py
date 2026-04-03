#!/usr/bin/env python3
"""
Reflective Phase-Quad Architecture (V10.9)
==========================================

Self-reflective extension to Phase-Quad enabling autonomous solution refinement
without external prompting. The model internally evaluates its outputs and
revises them until a quality threshold is met.

ARCHITECTURE:
    Generator (Phase-Quad Core) -> Critic (Quality Estimator) -> Decision Gate
    -> [Revise or Output]

LOOP BEHAVIOR:
    1. Generate candidate with Phase-Quad
    2. Evaluate quality with neural critic
    3. If quality < threshold and revisions < max:
       - Encode revision context
       - Loop back with revision guidance
    4. Return best response

KEY ADVANTAGES OVER TOKEN-BASED REASONING (o1-style):
    - O(N) per revision vs O(N^2) for token-based
    - Constant memory (Phase state) vs linear growth (context)
    - Latent-space revision (efficient) vs token-space (expensive)

INVARIANTS:
    - INV-RPQ-1: Always returns best quality response seen
    - INV-RPQ-2: Never exceeds max_revisions
    - INV-RPQ-3: Revision count tracks actual revisions performed
    - INV-RPQ-4: Quality history preserves all scores

Author: Claude (Architecture Implementation)
Date: February 2026
Version: 1.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class ReflectivePhaseQuadConfig:
    """
    Configuration for Reflective Phase-Quad components.

    Attributes:
        d_model: Model dimension
        num_heads: Number of attention heads
        d_ff: FFN dimension (default: 4 * d_model)
        max_revisions: Maximum revision attempts
        threshold_high: Quality threshold for immediate acceptance
        threshold_low: Quality threshold below which major revision needed
        num_quality_dims: Number of quality dimensions (coherence, correctness, completeness)
        critic_num_layers: Number of transformer layers in critic
        adaptive_threshold: Whether to use learned adaptive thresholds
        dropout: Dropout probability
        device: Target device
    """
    d_model: int = 128
    num_heads: int = 8
    d_ff: Optional[int] = None
    max_revisions: int = 3
    threshold_high: float = 0.85
    threshold_low: float = 0.50
    num_quality_dims: int = 3
    critic_num_layers: int = 2
    adaptive_threshold: bool = False
    dropout: float = 0.1
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    def __post_init__(self):
        if self.d_ff is None:
            self.d_ff = 4 * self.d_model


# =============================================================================
# REFLECTIVE PHASE STATE
# =============================================================================


@dataclass
class ReflectivePhaseState:
    """
    Extended phase state for self-reflective generation.

    Contains standard Phase-Quad state plus reflective extensions
    for tracking confidence, revision history, and focus areas.

    Attributes:
        content_memory: [B, N, D] - accumulated content from generation
        binding_cache: [B, K, D] - quad retrieval cache (optional)
        confidence: [B, 1] - current confidence estimate
        revision_count: [B, 1] - number of revisions performed
        quality_history: [B, max_revisions] - past quality scores
        previous_attempts: List of previous output tensors
        revision_mode: [B, 1] - 0=generate, 1=minor_revise, 2=major_revise
        focus_mask: [B, N] - which positions need revision attention
    """
    content_memory: Tensor
    binding_cache: Optional[Tensor] = None
    confidence: Optional[Tensor] = None
    revision_count: Optional[Tensor] = None
    quality_history: Optional[Tensor] = None
    previous_attempts: List[Tensor] = field(default_factory=list)
    revision_mode: Optional[Tensor] = None
    focus_mask: Optional[Tensor] = None

    @classmethod
    def create(
        cls,
        batch_size: int,
        seq_len: int,
        d_model: int,
        max_revisions: int = 3,
        device: str = "cpu",
    ) -> "ReflectivePhaseState":
        """Factory method to create initialized state."""
        return cls(
            content_memory=torch.zeros(batch_size, seq_len, d_model, device=device),
            binding_cache=None,
            confidence=torch.zeros(batch_size, 1, device=device),
            revision_count=torch.zeros(batch_size, 1, dtype=torch.long, device=device),
            quality_history=torch.zeros(batch_size, max_revisions + 1, device=device),
            previous_attempts=[],
            revision_mode=torch.zeros(batch_size, 1, dtype=torch.long, device=device),
            focus_mask=torch.ones(batch_size, seq_len, device=device),
        )

    def clone(self) -> "ReflectivePhaseState":
        """Create a copy of this state."""
        return ReflectivePhaseState(
            content_memory=self.content_memory.clone() if self.content_memory is not None else None,
            binding_cache=self.binding_cache.clone() if self.binding_cache is not None else None,
            confidence=self.confidence.clone() if self.confidence is not None else None,
            revision_count=self.revision_count.clone() if self.revision_count is not None else None,
            quality_history=self.quality_history.clone() if self.quality_history is not None else None,
            previous_attempts=[t.clone() for t in self.previous_attempts],
            revision_mode=self.revision_mode.clone() if self.revision_mode is not None else None,
            focus_mask=self.focus_mask.clone() if self.focus_mask is not None else None,
        )


# =============================================================================
# QUALITY CRITIQUE OUTPUT
# =============================================================================


@dataclass
class QualityCritique:
    """
    Quality assessment from the neural critic.

    Contains overall score, per-dimension scores, and revision guidance.
    """
    quality_score: Tensor  # [B, 1] overall quality
    quality_dims: Tensor  # [B, num_dims] per-dimension scores
    revision_type: Tensor  # [B, 3] softmax over revision types
    focus_mask: Tensor  # [B, N] attention over positions needing revision
    revision_logits: Tensor  # [B, 3] raw logits for revision type

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "quality_score": self.quality_score.mean().item(),
            "quality_dims": self.quality_dims.mean(0).tolist(),
            "revision_type_probs": self.revision_type.mean(0).tolist(),
            "focus_mask_mean": self.focus_mask.mean().item(),
        }


# =============================================================================
# REFLECTIVE CRITIC (Process Reward Model)
# =============================================================================


class ReflectiveCritic(nn.Module):
    """
    Learned quality estimator for self-reflection.

    A neural network that evaluates the quality of generated outputs
    given the input. Returns multi-dimensional quality scores and
    revision guidance.

    Training sources:
    - Human feedback (RLHF style)
    - Automated verification (code execution, math checking)
    - Outcome signals (task success/failure)
    - Self-consistency (multiple samples, agreement = quality)

    Architecture:
    - Pair encoder: TransformerEncoder over [input; sep; output]
    - Quality heads: Per-dimension score predictors
    - Revision classifier: Predicts revision type needed
    - Focus attention: Identifies positions needing revision
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        num_layers: int = 2,
        num_quality_dims: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.num_quality_dims = num_quality_dims

        # Separator embedding between input and output
        self.separator_embed = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)

        # Pair encoder: encodes [input; separator; output]
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=num_heads,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
        )
        self.pair_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # CLS token for pooling
        self.cls_embed = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)

        # Quality dimension heads (coherence, correctness, completeness)
        self.quality_heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, d_model // 2),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(d_model // 2, 1),
                nn.Sigmoid(),
            )
            for _ in range(num_quality_dims)
        ])

        # Learnable weights for aggregating quality dimensions
        self.aggregate_weights = nn.Parameter(
            torch.ones(num_quality_dims) / num_quality_dims
        )

        # Revision type classifier: [no_revision, minor, major]
        self.revision_classifier = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 3),
        )

        # Focus attention: identifies positions needing revision
        self.focus_query = nn.Linear(d_model, d_model)
        self.focus_key = nn.Linear(d_model, d_model)
        self.focus_value = nn.Linear(d_model, d_model)

    def forward(
        self,
        input_embeds: Tensor,
        output_embeds: Tensor,
        output_mask: Optional[Tensor] = None,
    ) -> QualityCritique:
        """
        Evaluate quality of output given input.

        Args:
            input_embeds: [B, N_in, D] - input embeddings
            output_embeds: [B, N_out, D] - output embeddings to evaluate
            output_mask: [B, N_out] - optional mask for output positions

        Returns:
            QualityCritique with scores and revision guidance
        """
        B = input_embeds.shape[0]
        device = input_embeds.device

        # Expand CLS and separator for batch
        cls_token = self.cls_embed.expand(B, -1, -1)
        separator = self.separator_embed.expand(B, -1, -1)

        # Combine: [CLS; input; separator; output]
        combined = torch.cat([cls_token, input_embeds, separator, output_embeds], dim=1)

        # Encode pair
        encoded = self.pair_encoder(combined)

        # Pool using CLS token
        pooled = encoded[:, 0, :]  # [B, D]

        # Compute quality dimensions
        quality_dims = torch.stack([
            head(pooled) for head in self.quality_heads
        ], dim=-1).squeeze(-2)  # [B, num_dims]

        # Aggregate to overall quality score
        weights = F.softmax(self.aggregate_weights, dim=0)
        quality_score = (quality_dims * weights).sum(dim=-1, keepdim=True)  # [B, 1]

        # Classify revision type
        revision_logits = self.revision_classifier(pooled)  # [B, 3]
        revision_type = F.softmax(revision_logits, dim=-1)

        # Compute focus mask (which output positions need revision)
        output_start_idx = 1 + input_embeds.shape[1] + 1  # CLS + input + separator
        output_encoded = encoded[:, output_start_idx:, :]  # [B, N_out, D]

        # Attention-based focus
        query = self.focus_query(pooled).unsqueeze(1)  # [B, 1, D]
        key = self.focus_key(output_encoded)  # [B, N_out, D]
        value = self.focus_value(output_encoded)  # [B, N_out, D]

        # Scaled dot-product attention
        scale = math.sqrt(self.d_model)
        attn_scores = torch.bmm(query, key.transpose(1, 2)) / scale  # [B, 1, N_out]

        if output_mask is not None:
            attn_scores = attn_scores.masked_fill(
                output_mask.unsqueeze(1) == 0, float("-inf")
            )

        focus_mask = torch.sigmoid(attn_scores.squeeze(1))  # [B, N_out]

        return QualityCritique(
            quality_score=quality_score,
            quality_dims=quality_dims,
            revision_type=revision_type,
            focus_mask=focus_mask,
            revision_logits=revision_logits,
        )


# =============================================================================
# DECISION GATE
# =============================================================================


class DecisionGate(nn.Module):
    """
    Decides whether to output, revise, or flag uncertainty.

    Thresholds can be:
    - Fixed (simple, interpretable)
    - Learned (adaptive, task-dependent)
    - Dynamic (based on compute budget)

    Actions:
    - 0: OUTPUT (quality >= threshold_high)
    - 1: MINOR_REVISE (threshold_low <= quality < threshold_high, can revise)
    - 2: MAJOR_REVISE (quality < threshold_low, can revise)
    - 3: OUTPUT_WITH_FLAG (can't revise anymore, quality not high)
    """

    def __init__(
        self,
        threshold_high: float = 0.85,
        threshold_low: float = 0.50,
        max_revisions: int = 3,
        adaptive_threshold: bool = False,
        d_model: Optional[int] = None,
    ):
        super().__init__()
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self.max_revisions = max_revisions
        self.adaptive_threshold = adaptive_threshold

        if adaptive_threshold:
            if d_model is None:
                raise ValueError("d_model required for adaptive threshold")
            # Network to predict thresholds based on context
            self.threshold_net = nn.Sequential(
                nn.Linear(d_model + 2, 64),  # +2 for quality and revision_count
                nn.GELU(),
                nn.Linear(64, 2),  # [threshold_high, threshold_low]
                nn.Sigmoid(),
            )

    def forward(
        self,
        quality_score: Tensor,
        revision_count: Tensor,
        context_embed: Optional[Tensor] = None,
    ) -> Dict[str, Tensor]:
        """
        Decide action for each sample in batch.

        Args:
            quality_score: [B, 1] - quality score from critic
            revision_count: [B, 1] - number of revisions so far
            context_embed: [B, D] - context embedding for adaptive threshold

        Returns:
            Dictionary with:
            - action: [B, 1] - 0=output, 1=minor_revise, 2=major_revise, 3=output_with_flag
            - should_output: [B, 1] - boolean
            - should_revise: [B, 1] - boolean
            - is_minor_revise: [B, 1] - boolean
            - is_major_revise: [B, 1] - boolean
            - has_uncertainty_flag: [B, 1] - boolean
            - threshold_high: [B, 1] - effective high threshold
            - threshold_low: [B, 1] - effective low threshold
        """
        B = quality_score.shape[0]
        device = quality_score.device

        # Get thresholds
        if self.adaptive_threshold and context_embed is not None:
            threshold_input = torch.cat([
                context_embed,
                quality_score,
                revision_count.float() / self.max_revisions,
            ], dim=-1)
            thresholds = self.threshold_net(threshold_input)
            # Scale to reasonable range [0.3, 0.95]
            threshold_high = 0.3 + 0.65 * thresholds[:, 0:1]
            threshold_low = 0.2 + 0.5 * thresholds[:, 1:2]
            # Ensure high > low
            threshold_low = torch.minimum(threshold_low, threshold_high - 0.1)
        else:
            threshold_high = torch.full((B, 1), self.threshold_high, device=device)
            threshold_low = torch.full((B, 1), self.threshold_low, device=device)

        # Check if can still revise
        can_revise = revision_count < self.max_revisions

        # Initialize action tensor
        action = torch.zeros(B, 1, dtype=torch.long, device=device)

        # Compute conditions
        high_quality = quality_score >= threshold_high
        medium_quality = (quality_score >= threshold_low) & (quality_score < threshold_high)
        low_quality = quality_score < threshold_low

        # Assign actions
        # Default: output with flag (3) for anything not handled
        action = torch.full((B, 1), 3, dtype=torch.long, device=device)

        # High quality → output (0)
        action = torch.where(high_quality, torch.zeros_like(action), action)

        # Medium quality + can revise → minor revise (1)
        action = torch.where(
            medium_quality & can_revise,
            torch.ones_like(action),
            action,
        )

        # Low quality + can revise → major revise (2)
        action = torch.where(
            low_quality & can_revise,
            torch.full_like(action, 2),
            action,
        )

        # Create boolean masks
        should_output = (action == 0) | (action == 3)
        should_revise = (action == 1) | (action == 2)

        return {
            "action": action,
            "should_output": should_output,
            "should_revise": should_revise,
            "is_minor_revise": action == 1,
            "is_major_revise": action == 2,
            "has_uncertainty_flag": action == 3,
            "threshold_high": threshold_high,
            "threshold_low": threshold_low,
        }


# =============================================================================
# REVISION ENCODER
# =============================================================================


class RevisionEncoder(nn.Module):
    """
    Encodes context for revision: what was wrong and what to fix.

    Produces a revision embedding that guides the generator
    to produce a better output on the next attempt.

    Components:
    - Revision type embedding (none/minor/major)
    - Quality feedback encoding (what dimensions need improvement)
    - Focus-weighted previous output (where to focus)
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        num_quality_dims: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_quality_dims = num_quality_dims

        # Embed revision type: [none, minor, major]
        self.revision_type_embed = nn.Embedding(3, d_model)

        # Encode quality feedback
        self.quality_encoder = nn.Sequential(
            nn.Linear(num_quality_dims + 1, d_model),  # +1 for overall score
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
        )

        # Cross-attention for focus-weighted previous output encoding
        self.focus_cross_attn = nn.MultiheadAttention(
            d_model,
            num_heads,
            dropout=dropout,
            batch_first=True,
        )

        # Combine all revision signals
        self.combiner = nn.Sequential(
            nn.Linear(d_model * 3, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
        )

        # Gate for blending revision signal with original input
        self.blend_gate = nn.Sequential(
            nn.Linear(d_model * 2, d_model),
            nn.Sigmoid(),
        )

    def forward(
        self,
        original_input: Tensor,
        previous_output: Tensor,
        quality_dims: Tensor,
        quality_score: Tensor,
        focus_mask: Tensor,
        revision_type: int,
    ) -> Tensor:
        """
        Encode revision context.

        Args:
            original_input: [B, N_in, D] - original input embeddings
            previous_output: [B, N_out, D] - previous attempt embeddings
            quality_dims: [B, num_dims] - per-dimension quality scores
            quality_score: [B, 1] - overall quality score
            focus_mask: [B, N_out] - attention weights for focus areas
            revision_type: 1=minor, 2=major

        Returns:
            revision_context: [B, N_in, D] - revision-aware input embedding
        """
        B, N_in, D = original_input.shape
        device = original_input.device

        # 1. Revision type embedding
        rev_type_tensor = torch.full(
            (B,), revision_type, dtype=torch.long, device=device
        )
        rev_embed = self.revision_type_embed(rev_type_tensor)  # [B, D]

        # 2. Quality feedback embedding
        quality_input = torch.cat([quality_score, quality_dims], dim=-1)  # [B, num_dims+1]
        quality_embed = self.quality_encoder(quality_input)  # [B, D]

        # 3. Focus-weighted representation of previous output
        # Use focus_mask as attention weights
        focus_weights = focus_mask.unsqueeze(-1)  # [B, N_out, 1]
        focus_weights = focus_weights / (focus_weights.sum(dim=1, keepdim=True) + 1e-8)

        # Weighted sum of previous output
        focused_output = (previous_output * focus_weights).sum(dim=1)  # [B, D]

        # 4. Combine all revision signals
        combined = torch.cat([rev_embed, quality_embed, focused_output], dim=-1)  # [B, 3D]
        revision_signal = self.combiner(combined)  # [B, D]

        # 5. Blend revision signal with original input using learned gate
        # Expand revision signal to match input sequence length
        revision_signal_expanded = revision_signal.unsqueeze(1).expand(-1, N_in, -1)

        # Compute blend gate
        gate_input = torch.cat([original_input, revision_signal_expanded], dim=-1)
        gate = self.blend_gate(gate_input)  # [B, N_in, D]

        # Blend: gate * revision + (1 - gate) * original
        revision_context = gate * revision_signal_expanded + (1 - gate) * original_input

        return revision_context


# =============================================================================
# SIMPLE GENERATOR (Phase-Quad placeholder)
# =============================================================================


class SimpleGenerator(nn.Module):
    """
    Simple transformer-based generator as placeholder for Phase-Quad.

    In production, this would be replaced with actual PhaseQuadBlock
    from symbolu.hp_quad or similar.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        d_ff: Optional[int] = None,
        num_layers: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        d_ff = d_ff or 4 * d_model

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=num_heads,
            dim_feedforward=d_ff,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

    def forward(
        self,
        x: Tensor,
        content_memory: Optional[Tensor] = None,
        binding_cache: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Tensor]:
        """
        Generate output from input.

        Args:
            x: [B, N, D] - input embeddings
            content_memory: [B, N, D] - accumulated content (optional)
            binding_cache: [B, K, D] - quad cache (optional)

        Returns:
            output: [B, N, D] - generated output
            new_content_memory: [B, N, D] - updated memory
        """
        output = self.encoder(x)

        # Update content memory (simple accumulation)
        if content_memory is not None:
            new_memory = 0.9 * content_memory + 0.1 * output
        else:
            new_memory = output

        return output, new_memory


# =============================================================================
# REFLECTIVE PHASE-QUAD BLOCK
# =============================================================================


class ReflectivePhaseQuadBlock(nn.Module):
    """
    Complete reflective Phase-Quad block with internal revision loop.

    Combines:
    - Generator (Phase-Quad core or placeholder)
    - Critic (neural quality estimator)
    - Decision Gate (output vs revise logic)
    - Revision Encoder (context for revision)

    The forward pass implements an internal loop that:
    1. Generates candidate output
    2. Evaluates quality with critic
    3. Decides to output or revise
    4. If revising, encodes context and loops back

    This enables latent-space revision, which is more efficient than
    token-space revision (o1-style).
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        d_ff: Optional[int] = None,
        max_revisions: int = 3,
        threshold_high: float = 0.85,
        threshold_low: float = 0.50,
        num_quality_dims: int = 3,
        critic_num_layers: int = 2,
        adaptive_threshold: bool = False,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.d_model = d_model
        self.max_revisions = max_revisions

        # Core generator (placeholder - replace with actual Phase-Quad)
        self.generator = SimpleGenerator(
            d_model=d_model,
            num_heads=num_heads,
            d_ff=d_ff,
            num_layers=2,
            dropout=dropout,
        )

        # Critic
        self.critic = ReflectiveCritic(
            d_model=d_model,
            num_heads=num_heads,
            num_layers=critic_num_layers,
            num_quality_dims=num_quality_dims,
            dropout=dropout,
        )

        # Decision gate
        self.decision_gate = DecisionGate(
            threshold_high=threshold_high,
            threshold_low=threshold_low,
            max_revisions=max_revisions,
            adaptive_threshold=adaptive_threshold,
            d_model=d_model if adaptive_threshold else None,
        )

        # Revision encoder
        self.revision_encoder = RevisionEncoder(
            d_model=d_model,
            num_heads=num_heads,
            num_quality_dims=num_quality_dims,
            dropout=dropout,
        )

    def forward(
        self,
        x: Tensor,
        phase_state: Optional[ReflectivePhaseState] = None,
        allow_revision: bool = True,
    ) -> Tuple[Tensor, ReflectivePhaseState, Dict[str, Any]]:
        """
        Forward pass with internal revision loop.

        Args:
            x: [B, N, D] - input embeddings
            phase_state: Optional existing state
            allow_revision: Whether to enable revision loop

        Returns:
            output: [B, N, D] - final output embeddings
            state: Updated ReflectivePhaseState
            stats: Dictionary with revision statistics
        """
        B, N, D = x.shape
        device = x.device

        # Initialize state if needed
        if phase_state is None:
            phase_state = ReflectivePhaseState.create(
                batch_size=B,
                seq_len=N,
                d_model=D,
                max_revisions=self.max_revisions,
                device=device,
            )

        stats = {
            "revision_counts": [],
            "quality_scores": [],
            "quality_dims": [],
            "actions": [],
            "initial_quality": None,
            "final_quality": None,
            "quality_improvement": None,
        }

        current_input = x
        best_output = None
        best_quality = -1.0

        for revision_step in range(self.max_revisions + 1):
            # Generate candidate
            output, new_content_memory = self.generator(
                current_input,
                phase_state.content_memory,
                phase_state.binding_cache,
            )

            # Update state memory
            phase_state.content_memory = new_content_memory

            # Evaluate quality
            with torch.no_grad():
                critique = self.critic(x, output)

            quality_score = critique.quality_score
            quality_mean = quality_score.mean().item()

            # Record stats
            stats["quality_scores"].append(quality_mean)
            stats["quality_dims"].append(critique.quality_dims.mean(0).tolist())

            if revision_step == 0:
                stats["initial_quality"] = quality_mean

            # Track best output
            if quality_mean > best_quality:
                best_quality = quality_mean
                best_output = output.clone()

            # Update state
            phase_state.confidence = quality_score
            if phase_state.quality_history is not None:
                phase_state.quality_history[:, revision_step] = quality_score.squeeze(-1)
            phase_state.previous_attempts.append(output.detach())

            # Decision
            decision = self.decision_gate(
                quality_score,
                phase_state.revision_count,
            )

            stats["actions"].append(decision["action"].float().mean().item())

            # Check if we should output
            if decision["should_output"].all() or not allow_revision:
                stats["revision_counts"].append(revision_step)
                stats["final_quality"] = quality_mean
                stats["quality_improvement"] = quality_mean - (stats["initial_quality"] or 0)
                return best_output, phase_state, stats

            # Prepare for revision
            phase_state.revision_count = (
                phase_state.revision_count + decision["should_revise"].long()
            )

            # Determine revision type
            is_major = decision["is_major_revise"].sum() > decision["is_minor_revise"].sum()
            revision_type = 2 if is_major else 1

            # Encode revision context
            current_input = self.revision_encoder(
                x,
                output,
                critique.quality_dims,
                quality_score,
                critique.focus_mask,
                revision_type,
            )

            # Update focus mask
            phase_state.focus_mask = critique.focus_mask

        # Max revisions reached - return best
        stats["revision_counts"].append(self.max_revisions)
        stats["final_quality"] = best_quality
        stats["quality_improvement"] = best_quality - (stats["initial_quality"] or 0)

        return best_output, phase_state, stats


# =============================================================================
# REFLECTIVE PHASE-QUAD MODEL (Full Model Wrapper)
# =============================================================================


class ReflectivePhaseQuadModel(nn.Module):
    """
    Full model with embedding layers and output projection.

    Wraps ReflectivePhaseQuadBlock with:
    - Token embedding
    - Positional embedding
    - Multiple reflective blocks (stacked)
    - Output projection to vocabulary

    This is a complete language model with reflective capabilities.
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int = 128,
        num_heads: int = 8,
        num_layers: int = 4,
        d_ff: Optional[int] = None,
        max_seq_len: int = 512,
        max_revisions: int = 3,
        threshold_high: float = 0.85,
        threshold_low: float = 0.50,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.max_seq_len = max_seq_len

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Embedding(max_seq_len, d_model)

        # Reflective blocks
        self.blocks = nn.ModuleList([
            ReflectivePhaseQuadBlock(
                d_model=d_model,
                num_heads=num_heads,
                d_ff=d_ff,
                max_revisions=max_revisions,
                threshold_high=threshold_high,
                threshold_low=threshold_low,
                dropout=dropout,
            )
            for _ in range(num_layers)
        ])

        # Output projection
        self.output_norm = nn.LayerNorm(d_model)
        self.output_proj = nn.Linear(d_model, vocab_size, bias=False)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize weights with proper scaling."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: Tensor,
        allow_revision: bool = True,
    ) -> Tuple[Tensor, List[Dict[str, Any]]]:
        """
        Forward pass through model.

        Args:
            input_ids: [B, N] - input token IDs
            allow_revision: Whether to enable revision loops

        Returns:
            logits: [B, N, vocab_size] - output logits
            block_stats: List of stats from each block
        """
        B, N = input_ids.shape
        device = input_ids.device

        # Embed
        positions = torch.arange(N, device=device).unsqueeze(0).expand(B, -1)
        x = self.token_embed(input_ids) + self.pos_embed(positions)

        # Pass through blocks
        block_stats = []
        for block in self.blocks:
            x, _, stats = block(x, allow_revision=allow_revision)
            block_stats.append(stats)

        # Output
        x = self.output_norm(x)
        logits = self.output_proj(x)

        return logits, block_stats


# =============================================================================
# BENCHMARK UTILITIES
# =============================================================================


class ReflectivePhaseQuadBenchmark:
    """
    Benchmarking utilities for Reflective Phase-Quad.

    Provides:
    - Component benchmarks (critic, decision gate, revision encoder)
    - Integration benchmarks (full block with revision loop)
    - Comparison benchmarks (reflective vs single-pass)
    - Quality trajectory analysis
    """

    def __init__(self, config: ReflectivePhaseQuadConfig):
        self.config = config
        self.device = config.device

    def benchmark_critic(
        self,
        batch_size: int = 8,
        seq_len: int = 64,
        num_iterations: int = 100,
    ) -> Dict[str, Any]:
        """Benchmark critic forward pass."""
        import time

        critic = ReflectiveCritic(
            d_model=self.config.d_model,
            num_heads=self.config.num_heads,
            num_layers=self.config.critic_num_layers,
            num_quality_dims=self.config.num_quality_dims,
        ).to(self.device)

        input_embeds = torch.randn(batch_size, seq_len, self.config.d_model, device=self.device)
        output_embeds = torch.randn(batch_size, seq_len, self.config.d_model, device=self.device)

        # Warmup
        for _ in range(10):
            _ = critic(input_embeds, output_embeds)

        # Benchmark
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        start = time.perf_counter()

        for _ in range(num_iterations):
            _ = critic(input_embeds, output_embeds)

        torch.cuda.synchronize() if torch.cuda.is_available() else None
        elapsed = time.perf_counter() - start

        return {
            "total_time_sec": elapsed,
            "per_iteration_ms": (elapsed / num_iterations) * 1000,
            "iterations_per_sec": num_iterations / elapsed,
        }

    def benchmark_decision_gate(
        self,
        batch_size: int = 64,
        num_iterations: int = 1000,
    ) -> Dict[str, Any]:
        """Benchmark decision gate forward pass."""
        import time

        gate = DecisionGate(
            threshold_high=self.config.threshold_high,
            threshold_low=self.config.threshold_low,
            max_revisions=self.config.max_revisions,
        ).to(self.device)

        quality_scores = torch.rand(batch_size, 1, device=self.device)
        revision_counts = torch.randint(0, self.config.max_revisions, (batch_size, 1), device=self.device)

        # Warmup
        for _ in range(100):
            _ = gate(quality_scores, revision_counts)

        # Benchmark
        start = time.perf_counter()

        for _ in range(num_iterations):
            _ = gate(quality_scores, revision_counts)

        elapsed = time.perf_counter() - start

        return {
            "total_time_sec": elapsed,
            "per_iteration_ms": (elapsed / num_iterations) * 1000,
            "iterations_per_sec": num_iterations / elapsed,
        }

    def benchmark_full_block(
        self,
        batch_size: int = 4,
        seq_len: int = 64,
        num_iterations: int = 50,
    ) -> Dict[str, Any]:
        """Benchmark full reflective block with revision loop."""
        import time

        block = ReflectivePhaseQuadBlock(
            d_model=self.config.d_model,
            num_heads=self.config.num_heads,
            d_ff=self.config.d_ff,
            max_revisions=self.config.max_revisions,
            threshold_high=self.config.threshold_high,
            threshold_low=self.config.threshold_low,
        ).to(self.device)

        x = torch.randn(batch_size, seq_len, self.config.d_model, device=self.device)

        # Warmup
        for _ in range(5):
            _ = block(x, allow_revision=True)

        # Benchmark with revision
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        start = time.perf_counter()

        total_revisions = 0
        all_stats = []
        for _ in range(num_iterations):
            _, _, stats = block(x, allow_revision=True)
            total_revisions += sum(stats["revision_counts"])
            all_stats.append(stats)

        torch.cuda.synchronize() if torch.cuda.is_available() else None
        elapsed_with_revision = time.perf_counter() - start

        # Benchmark without revision (single-pass)
        start = time.perf_counter()

        for _ in range(num_iterations):
            _, _, _ = block(x, allow_revision=False)

        torch.cuda.synchronize() if torch.cuda.is_available() else None
        elapsed_single_pass = time.perf_counter() - start

        avg_revisions = total_revisions / num_iterations
        quality_improvements = [s["quality_improvement"] or 0 for s in all_stats]

        return {
            "with_revision": {
                "total_time_sec": elapsed_with_revision,
                "per_iteration_ms": (elapsed_with_revision / num_iterations) * 1000,
                "avg_revisions": avg_revisions,
                "avg_quality_improvement": sum(quality_improvements) / len(quality_improvements),
            },
            "single_pass": {
                "total_time_sec": elapsed_single_pass,
                "per_iteration_ms": (elapsed_single_pass / num_iterations) * 1000,
            },
            "overhead_ratio": elapsed_with_revision / elapsed_single_pass,
        }

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmarks and return combined results."""
        return {
            "config": {
                "d_model": self.config.d_model,
                "num_heads": self.config.num_heads,
                "max_revisions": self.config.max_revisions,
                "threshold_high": self.config.threshold_high,
                "threshold_low": self.config.threshold_low,
            },
            "critic": self.benchmark_critic(),
            "decision_gate": self.benchmark_decision_gate(),
            "full_block": self.benchmark_full_block(),
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_reflective_phase_quad(
    d_model: int = 128,
    num_heads: int = 8,
    max_revisions: int = 3,
    threshold_high: float = 0.85,
    threshold_low: float = 0.50,
    device: str = "cpu",
) -> ReflectivePhaseQuadBlock:
    """
    Factory function to create a Reflective Phase-Quad block.

    Args:
        d_model: Model dimension
        num_heads: Number of attention heads
        max_revisions: Maximum revision attempts
        threshold_high: Quality threshold for acceptance
        threshold_low: Quality threshold for major revision
        device: Target device

    Returns:
        Configured ReflectivePhaseQuadBlock
    """
    block = ReflectivePhaseQuadBlock(
        d_model=d_model,
        num_heads=num_heads,
        max_revisions=max_revisions,
        threshold_high=threshold_high,
        threshold_low=threshold_low,
    )
    return block.to(device)


def create_reflective_model(
    vocab_size: int = 50257,
    d_model: int = 128,
    num_heads: int = 8,
    num_layers: int = 4,
    max_seq_len: int = 512,
    max_revisions: int = 3,
    device: str = "cpu",
) -> ReflectivePhaseQuadModel:
    """
    Factory function to create a complete Reflective Phase-Quad model.

    Args:
        vocab_size: Vocabulary size
        d_model: Model dimension
        num_heads: Number of attention heads
        num_layers: Number of blocks
        max_seq_len: Maximum sequence length
        max_revisions: Maximum revision attempts
        device: Target device

    Returns:
        Configured ReflectivePhaseQuadModel
    """
    model = ReflectivePhaseQuadModel(
        vocab_size=vocab_size,
        d_model=d_model,
        num_heads=num_heads,
        num_layers=num_layers,
        max_seq_len=max_seq_len,
        max_revisions=max_revisions,
    )
    return model.to(device)
