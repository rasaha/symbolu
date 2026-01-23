"""
Text LLM Interference-Aware Proposal Scoring.

This module provides optional proposal-proposal compatibility scoring for
text LLMs using the Phase-Quad architecture. Unlike vision, text interference
is more constrained:

Key differences from vision:
- Lower lambda (0.01-0.03 vs 0.05-0.08)
- Task-conditional (compositional only, not factual/code)
- Entropy-gated (only when proposals are uncertain)
- Late decoding only (min step requirement)

When to use:
- Multi-concept reasoning ("compare X, Y, Z")
- Long-form writing with style blending
- Planning / synthesis / essay generation
- Narrative consistency over long contexts

When NOT to use (auto-disabled):
- Factual Q&A
- Code generation
- Retrieval-heavy tasks
- Short answers

Reference: Designed per architectural guidance for text LLM safety.
"""

import re
from typing import Optional, Dict, Tuple, List, Set
from dataclasses import dataclass
from enum import Enum

import torch
import torch.nn as nn
from torch import Tensor


class InterferenceMode(Enum):
    """Interference application modes."""
    OFF = "off"
    COMPOSE = "compose"  # Multi-concept composition
    REASON = "reason"    # Multi-step reasoning
    WRITE = "write"      # Long-form writing


@dataclass
class TextInterferencePolicy:
    """
    Policy for whether/how to apply interference.

    Low-dimensional control signal (no token-wise injection).
    """
    enable: bool = False
    lam: float = 0.0  # 0.01-0.03 for text
    mode: InterferenceMode = InterferenceMode.OFF
    min_step: int = 8  # Only after N decoding steps
    entropy_gate: float = 1.2  # Entropy threshold


@dataclass
class TextInterferenceConfig:
    """
    Configuration for text LLM interference scoring.

    Attributes:
        enabled: Master switch (default OFF).
        lambda_text: Interference strength (0.01-0.03 for text).
        min_step: Minimum decoding step before interference.
        entropy_gate: Proposal entropy threshold (only apply if H > gate).
        auto_classify: Auto-detect compositional tasks.
        compose_keywords: Keywords that trigger compose mode.
        disable_keywords: Keywords that disable interference.
    """
    enabled: bool = False
    lambda_text: float = 0.02
    min_step: int = 8
    entropy_gate: float = 1.2
    auto_classify: bool = True
    min_multiplier: float = 0.9  # Tighter bounds for text
    max_multiplier: float = 1.1


class TaskClassifier:
    """
    Heuristic task classifier for auto-enabling interference.

    Uses keyword matching to determine if a prompt is compositional
    (should use interference) or factual/code (should not).

    No ML required - deterministic rules using prompt + metadata.
    """

    # Keywords that suggest compositional tasks (enable interference)
    COMPOSE_KEYWORDS: Set[str] = {
        "compare", "contrast", "tradeoffs", "trade-offs", "pros and cons",
        "synthesize", "integrate", "combine", "merge", "blend",
        "analyze across", "dimensions", "factors",
    }

    WRITE_KEYWORDS: Set[str] = {
        "write an essay", "long form", "story", "narrative", "tone",
        "style", "creative writing", "article", "blog post", "report",
    }

    REASON_KEYWORDS: Set[str] = {
        "step by step", "reasoning", "plan", "strategy", "approach",
        "multiple steps", "break down", "analyze", "evaluate options",
    }

    # Keywords that disable interference (factual/code tasks)
    DISABLE_KEYWORDS: Set[str] = {
        "python", "javascript", "typescript", "java", "sql", "code",
        "function", "bug", "error", "stack trace", "implement",
        "what is", "define", "when did", "who is", "where is",
        "cite", "quote", "sources", "reference",
        "one line", "brief", "short answer", "concise",
    }

    def classify(
        self,
        prompt: str,
        config: TextInterferenceConfig,
    ) -> TextInterferencePolicy:
        """
        Classify prompt and return interference policy.

        Args:
            prompt: User prompt text.
            config: Interference configuration.

        Returns:
            TextInterferencePolicy for this prompt.
        """
        if not config.enabled or not config.auto_classify:
            return TextInterferencePolicy(enable=False)

        prompt_lower = prompt.lower()

        # Check disable keywords first (takes priority)
        for keyword in self.DISABLE_KEYWORDS:
            if keyword in prompt_lower:
                return TextInterferencePolicy(
                    enable=False,
                    mode=InterferenceMode.OFF,
                )

        # Check compositional keywords
        mode = InterferenceMode.OFF
        enable = False

        for keyword in self.COMPOSE_KEYWORDS:
            if keyword in prompt_lower:
                mode = InterferenceMode.COMPOSE
                enable = True
                break

        if not enable:
            for keyword in self.WRITE_KEYWORDS:
                if keyword in prompt_lower:
                    mode = InterferenceMode.WRITE
                    enable = True
                    break

        if not enable:
            for keyword in self.REASON_KEYWORDS:
                if keyword in prompt_lower:
                    mode = InterferenceMode.REASON
                    enable = True
                    break

        return TextInterferencePolicy(
            enable=enable,
            lam=config.lambda_text if enable else 0.0,
            mode=mode,
            min_step=config.min_step,
            entropy_gate=config.entropy_gate,
        )


def compute_proposal_entropy(scores: Tensor) -> Tensor:
    """
    Compute entropy of proposal scores.

    Higher entropy = more uncertain = interference may help.
    Lower entropy = confident = interference not needed.

    Args:
        scores: [B, N, K] proposal scores.

    Returns:
        entropy: [B, N] entropy per position.
    """
    # Softmax for probability (only for entropy measurement)
    p = torch.softmax(scores, dim=-1)  # [B, N, K]
    H = -(p * torch.log(p + 1e-9)).sum(dim=-1)  # [B, N]
    return H


def text_interference_rescore(
    proposals: Tensor,
    scores: Tensor,
    lam: float = 0.02,
    min_mult: float = 0.9,
    max_mult: float = 1.1,
    eps: float = 1e-6,
) -> Tuple[Tensor, Dict[str, float]]:
    """
    Apply interference-aware rescoring to text proposals.

    Uses lower lambda and tighter bounds than vision for stability.

    Args:
        proposals: [B, N, K, D] TopK proposals.
        scores: [B, N, K] current scores.
        lam: Interference strength (0.01-0.03 for text).
        min_mult: Minimum multiplier (tighter for text).
        max_mult: Maximum multiplier (tighter for text).
        eps: Numerical stability.

    Returns:
        rescored: [B, N, K] modified scores.
        stats: Diagnostic statistics.
    """
    B, N, K, D = proposals.shape

    # Normalize proposals for cosine similarity
    p_norm = proposals / (proposals.norm(dim=-1, keepdim=True) + eps)

    # Pairwise similarity
    sim = torch.einsum("bnkd,bnqd->bnkq", p_norm, p_norm)  # [B, N, K, K]

    # Zero diagonal
    eye = torch.eye(K, device=sim.device, dtype=sim.dtype)
    sim = sim - eye.unsqueeze(0).unsqueeze(0)

    # Compatibility score
    compat = sim.mean(dim=-1)  # [B, N, K]

    # Compute multiplier with tight clamping
    multiplier = (1.0 + lam * compat).clamp(min_mult, max_mult)

    # Apply
    rescored = scores * multiplier

    # Diagnostics
    with torch.no_grad():
        stats = {
            "text_interference/compat_mean": compat.mean().item(),
            "text_interference/compat_std": compat.std().item(),
            "text_interference/multiplier_mean": multiplier.mean().item(),
        }

    return rescored, stats


class TextInterferenceScorer(nn.Module):
    """
    Text LLM interference scorer with task classification and entropy gating.

    Key safety features:
    1. Task classifier auto-disables for factual/code
    2. Entropy gate only applies when proposals are uncertain
    3. Min step requirement for late decoding only
    4. Lower lambda and tighter bounds than vision

    Example:
        >>> scorer = TextInterferenceScorer(config)
        >>> policy = scorer.classify_task(prompt)
        >>> if policy.enable:
        ...     scores = scorer(proposals, scores, step=step, entropy=H)
    """

    def __init__(self, config: Optional[TextInterferenceConfig] = None):
        super().__init__()
        self.config = config or TextInterferenceConfig()
        self.classifier = TaskClassifier()

        # Diagnostics
        self._last_stats: Dict[str, float] = {}
        self._applications = 0
        self._skips = 0
        self._policy: Optional[TextInterferencePolicy] = None

    def classify_task(self, prompt: str) -> TextInterferencePolicy:
        """
        Classify task and get interference policy.

        Args:
            prompt: User prompt.

        Returns:
            TextInterferencePolicy for this generation.
        """
        self._policy = self.classifier.classify(prompt, self.config)
        return self._policy

    def should_apply(
        self,
        step: int,
        proposal_entropy: Optional[Tensor] = None,
    ) -> bool:
        """
        Check if interference should be applied at this step.

        Args:
            step: Current decoding step.
            proposal_entropy: [B, N] entropy of proposals.

        Returns:
            True if interference should be applied.
        """
        if self._policy is None or not self._policy.enable:
            return False

        # Check min step
        if step < self._policy.min_step:
            return False

        # Check entropy gate
        if proposal_entropy is not None:
            mean_entropy = proposal_entropy.mean().item()
            if mean_entropy < self._policy.entropy_gate:
                return False

        return True

    def forward(
        self,
        proposals: Tensor,
        scores: Tensor,
        step: int = 0,
        proposal_entropy: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Dict[str, float]]:
        """
        Apply interference if conditions are met.

        Args:
            proposals: [B, N, K, D] TopK proposals.
            scores: [B, N, K] current scores.
            step: Current decoding step.
            proposal_entropy: Optional precomputed entropy.

        Returns:
            scores: Possibly rescored [B, N, K].
            stats: Diagnostic statistics.
        """
        # Compute entropy if not provided
        if proposal_entropy is None:
            proposal_entropy = compute_proposal_entropy(scores)

        if not self.should_apply(step, proposal_entropy):
            self._skips += 1
            return scores, {"text_interference/applied": 0.0}

        # Apply interference
        lam = self._policy.lam if self._policy else self.config.lambda_text

        rescored, stats = text_interference_rescore(
            proposals,
            scores,
            lam=lam,
            min_mult=self.config.min_multiplier,
            max_mult=self.config.max_multiplier,
        )

        self._applications += 1
        stats["text_interference/applied"] = 1.0
        stats["text_interference/mode"] = self._policy.mode.value if self._policy else "none"
        stats["text_interference/entropy_mean"] = proposal_entropy.mean().item()
        self._last_stats = stats

        return rescored, stats

    def get_diagnostics(self) -> Dict[str, float]:
        """Get accumulated diagnostics."""
        total = self._applications + self._skips
        return {
            **self._last_stats,
            "text_interference/application_rate": self._applications / max(total, 1),
            "text_interference/total_applications": float(self._applications),
            "text_interference/total_skips": float(self._skips),
        }

    def reset_stats(self):
        """Reset diagnostic counters."""
        self._applications = 0
        self._skips = 0
        self._last_stats = {}
        self._policy = None


class BCVFTextScorer(nn.Module):
    """
    BCVF + Interference hybrid scoring for text LLMs.

    Combines:
    1. BCVF consistency (forward vs backward) to filter valid proposals
    2. Interference compatibility to promote composing proposals

    For text, backward score (sb) uses a proxy since true backward
    verification requires a separate model. Options:
    - Proxy: sb = sigmoid(scores) (simple, always available)
    - True: sb from lightweight verifier model (better, optional)

    Args:
        lambda_f: Forward feasibility weight.
        lambda_b: Backward alignment weight.
        lambda_c: Consistency penalty weight.
        beta: BCVF sharpness.
        interference_enabled: Enable interference on top of BCVF.
        interference_lambda: Interference strength (0.01-0.03).
        use_sb_proxy: Use sigmoid(scores) as sb proxy.
    """

    def __init__(
        self,
        lambda_f: float = 1.0,
        lambda_b: float = 1.0,
        lambda_c: float = 0.25,  # Lower for text
        beta: float = 1.0,       # Lower sharpness for text
        interference_enabled: bool = False,
        interference_lambda: float = 0.02,
        use_sb_proxy: bool = True,
    ):
        super().__init__()
        self.lambda_f = lambda_f
        self.lambda_b = lambda_b
        self.lambda_c = lambda_c
        self.beta = beta
        self.interference_enabled = interference_enabled
        self.interference_lambda = interference_lambda
        self.use_sb_proxy = use_sb_proxy

        # Diagnostics
        self._last_stats: Dict[str, float] = {}

    def forward(
        self,
        proposals: Tensor,
        scores: Tensor,
        memory_state: Optional[Tensor] = None,
        sf: Optional[Tensor] = None,
        sb: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Dict[str, float]]:
        """
        Compute BCVF + interference rescored weights.

        Args:
            proposals: [B, N, K, D] TopK proposals.
            scores: [B, N, K] raw retrieval scores.
            memory_state: [B, N, D] phase memory state (for sb computation).
            sf: [B, N, K] optional precomputed forward scores.
            sb: [B, N, K] optional precomputed backward scores.

        Returns:
            weights: [B, N, K] BCVF-rescored weights (sum to 1).
            stats: Diagnostic statistics.
        """
        B, N, K, D = proposals.shape
        eps = 1e-8

        # Forward score: proxy from retrieval scores
        if sf is None:
            sf = torch.sigmoid(scores)  # [B, N, K]

        # Backward score
        if sb is None:
            if self.use_sb_proxy or memory_state is None:
                # Proxy: just use forward score (simplest)
                sb = sf
            else:
                # Compute from memory state alignment
                p_norm = proposals / (proposals.norm(dim=-1, keepdim=True) + eps)
                m_norm = memory_state / (memory_state.norm(dim=-1, keepdim=True) + eps)
                sb = (p_norm * m_norm.unsqueeze(2)).sum(dim=-1)  # [B, N, K]
                sb = (sb + 1) / 2  # Map [-1, 1] to [0, 1]

        # BCVF Lagrangian
        L = (
            self.lambda_f * (1 - sf) ** 2 +
            self.lambda_b * (1 - sb) ** 2 +
            self.lambda_c * (sf - sb) ** 2
        )

        # BCVF weights
        w_bcvf = torch.exp(-self.beta * L)
        w_bcvf = w_bcvf.clamp(0.0, 2.0)  # Stability

        # Optional interference
        if self.interference_enabled:
            p_norm = proposals / (proposals.norm(dim=-1, keepdim=True) + eps)
            sim = torch.einsum("bnkd,bnqd->bnkq", p_norm, p_norm)
            eye = torch.eye(K, device=sim.device, dtype=sim.dtype)
            sim = sim - eye.unsqueeze(0).unsqueeze(0)
            compat = sim.mean(dim=-1)
            w_int = (1.0 + self.interference_lambda * compat).clamp(0.9, 1.1)
        else:
            w_int = torch.ones_like(w_bcvf)
            compat = torch.zeros_like(sf)

        # Combined weights
        weights = w_bcvf * w_int
        weights = weights / (weights.sum(dim=-1, keepdim=True) + eps)

        # Diagnostics
        with torch.no_grad():
            self._last_stats = {
                "bcvf_text/sf_mean": sf.mean().item(),
                "bcvf_text/sb_mean": sb.mean().item(),
                "bcvf_text/w_bcvf_mean": w_bcvf.mean().item(),
                "bcvf_text/interference_enabled": float(self.interference_enabled),
            }
            if self.interference_enabled:
                self._last_stats["bcvf_text/compat_mean"] = compat.mean().item()
                self._last_stats["bcvf_text/w_int_mean"] = w_int.mean().item()

        return weights, self._last_stats

    def get_diagnostics(self) -> Dict[str, float]:
        """Get last forward pass diagnostics."""
        return self._last_stats


# Convenience factory functions

def create_text_interference_scorer(
    enabled: bool = False,
    lambda_text: float = 0.02,
    **kwargs,
) -> TextInterferenceScorer:
    """Create configured text interference scorer."""
    config = TextInterferenceConfig(
        enabled=enabled,
        lambda_text=lambda_text,
        **kwargs,
    )
    return TextInterferenceScorer(config)


def create_bcvf_text_scorer(
    interference_enabled: bool = False,
    interference_lambda: float = 0.02,
    **kwargs,
) -> BCVFTextScorer:
    """Create BCVF + interference hybrid scorer for text."""
    return BCVFTextScorer(
        interference_enabled=interference_enabled,
        interference_lambda=interference_lambda,
        **kwargs,
    )
