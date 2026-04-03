"""
Adaptive Policy Engine

Policy-level memory that modifies future budgets, decay rates, attention patterns,
and tool access based on session performance trajectory.

THIS IS NOT COMMODITY "LEARNING FROM MISTAKES":
    ❌ Logs → Embeddings → RAG retrieval (everyone does this)
    ✅ Past performance → Policy parameters → Behavior change (structural leverage)

CORE MECHANISMS:
    1. SCC-Inspired Parameter Tuning
       - Gradient descent on thresholds based on coherence trajectory
       - θ_{t+1} = θ_t + ρ * ∇_θ C_global(t)

    2. Session Trajectory Classification
       - 8 motivation types: hope, fear, avoidance, expansion, stabilization, etc.
       - Each type triggers different policy adjustments

    3. Budget & Decay Modulation
       - Revision budget adjusted based on session stability
       - Quality threshold decay for recovering sessions
       - Attention budget for complex vs simple queries

    4. Tool Access Gating
       - Tool permissions based on coherence history
       - Stricter gates for unstable sessions
       - Progressive trust building

ARCHITECTURE:
    ┌─────────────────────────────────────────────────────────────┐
    │                  AdaptivePolicyEngine                        │
    │  ┌─────────────────┐  ┌─────────────────┐                   │
    │  │ Performance     │  │ Policy          │                   │
    │  │ History         │→ │ Parameters      │                   │
    │  │ (per-session)   │  │ (tunable)       │                   │
    │  └─────────────────┘  └─────────────────┘                   │
    │           │                    │                             │
    │           ▼                    ▼                             │
    │  ┌─────────────────┐  ┌─────────────────┐                   │
    │  │ Trajectory      │  │ Budget/Decay    │                   │
    │  │ Classifier      │→ │ Modulator       │                   │
    │  └─────────────────┘  └─────────────────┘                   │
    │           │                    │                             │
    │           ▼                    ▼                             │
    │  ┌─────────────────────────────────────────────────────┐    │
    │  │              PolicyDecision                          │    │
    │  │  - revision_budget    - quality_threshold            │    │
    │  │  - tool_permissions   - response_style               │    │
    │  │  - attention_budget   - decay_rate                   │    │
    │  └─────────────────────────────────────────────────────┘    │
    └─────────────────────────────────────────────────────────────┘

INSPIRED BY:
    - CTM+ SCC (Self-tuning Coherence Control)
    - Phase-Quad Session Policy Flags
    - Motivation Flow Engine
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Enums and Constants
# =============================================================================


class SessionTrajectory(Enum):
    """
    Session trajectory classification.

    Based on motivation_engine.py patterns, simplified for agentic use.
    """
    HOPE_DRIVEN = "hope_driven"              # Upward arc, improving
    FEAR_DRIVEN = "fear_driven"              # Fragmented, volatile
    EXPANSION_DRIVEN = "expansion_driven"    # Exploring, growing
    STABILIZATION_DRIVEN = "stabilization"   # Recovering from decline
    OVERCORRECTION = "overcorrection"        # Sharp oscillations
    AVOIDANCE_DRIVEN = "avoidance_driven"    # Flat, suppressed
    STABLE = "stable"                        # Healthy, consistent
    UNKNOWN = "unknown"                      # Not enough data


class ToolPermission(Enum):
    """Tool permission levels."""
    FULL = "full"              # All tools available
    STANDARD = "standard"      # Most tools, no destructive
    RESTRICTED = "restricted"  # Read-only, no execution
    BLOCKED = "blocked"        # No tool access


# Default policy parameters
DEFAULT_POLICY_PARAMS = {
    # Quality thresholds
    "quality_threshold_high": 0.85,
    "quality_threshold_low": 0.50,

    # Revision control
    "max_revisions": 3,
    "revision_budget_base": 3,

    # Coherence thresholds
    "coherence_stable_threshold": 0.70,
    "coherence_recovering_threshold": 0.45,
    "coherence_critical_threshold": 0.30,

    # Tool access thresholds
    "tool_full_access_coherence": 0.75,
    "tool_standard_access_coherence": 0.55,
    "tool_restricted_access_coherence": 0.35,

    # Decay rates
    "quality_decay_rate": 0.95,      # Per-turn quality expectation decay
    "coherence_decay_rate": 0.98,    # Per-turn coherence decay

    # Learning rate for SCC updates
    "scc_learning_rate": 0.05,

    # Attention/budget multipliers
    "attention_budget_base": 1.0,
    "complexity_budget_multiplier": 1.5,
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class PerformanceSnapshot:
    """
    Single-turn performance record.

    Captures quality, coherence, and behavior metrics for one interaction.
    """
    turn_index: int
    timestamp: float

    # Quality metrics
    quality_score: float
    revision_count: int

    # Coherence metrics (from CoherenceMetrics)
    coherence_score: float
    goal_alignment: float
    internal_consistency: float
    volatility: float

    # Outcome
    was_successful: bool  # User accepted / no safety block
    was_revised: bool     # Required revision
    was_blocked: bool     # Safety blocked

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "timestamp": self.timestamp,
            "quality_score": self.quality_score,
            "revision_count": self.revision_count,
            "coherence_score": self.coherence_score,
            "goal_alignment": self.goal_alignment,
            "internal_consistency": self.internal_consistency,
            "volatility": self.volatility,
            "was_successful": self.was_successful,
            "was_revised": self.was_revised,
            "was_blocked": self.was_blocked,
        }


@dataclass
class SessionPerformanceHistory:
    """
    Multi-turn performance history for a session.

    Maintains rolling window of performance snapshots and computed aggregates.
    """
    session_id: str
    snapshots: List[PerformanceSnapshot] = field(default_factory=list)

    # Computed aggregates (updated on each append)
    avg_quality: float = 0.0
    avg_coherence: float = 0.0
    quality_trend: float = 0.0      # Positive = improving
    coherence_trend: float = 0.0    # Positive = improving
    volatility_avg: float = 0.0
    success_rate: float = 1.0
    revision_rate: float = 0.0
    block_rate: float = 0.0

    # Trajectory markers
    had_breakthrough: bool = False   # Quality jumped > 0.2
    had_fragmentation: bool = False  # Coherence dropped < 0.3
    had_recovery: bool = False       # Coherence recovered after drop
    oscillation_count: int = 0       # Sign changes in quality trend

    def append(self, snapshot: PerformanceSnapshot) -> None:
        """Append snapshot and update aggregates."""
        self.snapshots.append(snapshot)
        self._update_aggregates()

    def _update_aggregates(self) -> None:
        """Recompute all aggregate metrics."""
        if not self.snapshots:
            return

        n = len(self.snapshots)

        # Simple averages
        self.avg_quality = sum(s.quality_score for s in self.snapshots) / n
        self.avg_coherence = sum(s.coherence_score for s in self.snapshots) / n
        self.volatility_avg = sum(s.volatility for s in self.snapshots) / n

        # Rates
        self.success_rate = sum(1 for s in self.snapshots if s.was_successful) / n
        self.revision_rate = sum(1 for s in self.snapshots if s.was_revised) / n
        self.block_rate = sum(1 for s in self.snapshots if s.was_blocked) / n

        # Trends (linear regression slope approximation)
        if n >= 2:
            quality_delta = self.snapshots[-1].quality_score - self.snapshots[0].quality_score
            coherence_delta = self.snapshots[-1].coherence_score - self.snapshots[0].coherence_score
            self.quality_trend = quality_delta / n
            self.coherence_trend = coherence_delta / n

        # Trajectory markers
        self._detect_trajectory_markers()

    def _detect_trajectory_markers(self) -> None:
        """Detect breakthrough, fragmentation, recovery, oscillation."""
        if len(self.snapshots) < 2:
            return

        # Breakthrough: quality jump > 0.2
        for i in range(1, len(self.snapshots)):
            if self.snapshots[i].quality_score - self.snapshots[i-1].quality_score > 0.2:
                self.had_breakthrough = True
                break

        # Fragmentation: coherence < 0.3
        for s in self.snapshots:
            if s.coherence_score < 0.3:
                self.had_fragmentation = True
                break

        # Recovery: coherence dip then rise
        if len(self.snapshots) >= 3:
            coherences = [s.coherence_score for s in self.snapshots]
            for i in range(1, len(coherences) - 1):
                if coherences[i] < coherences[i-1] and coherences[i] < coherences[i+1]:
                    if coherences[-1] > coherences[i] + 0.15:
                        self.had_recovery = True
                        break

        # Oscillation count: sign changes in quality deltas
        if len(self.snapshots) >= 3:
            deltas = [
                self.snapshots[i].quality_score - self.snapshots[i-1].quality_score
                for i in range(1, len(self.snapshots))
            ]
            self.oscillation_count = sum(
                1 for i in range(len(deltas) - 1)
                if deltas[i] * deltas[i+1] < 0
            )

    @property
    def turn_count(self) -> int:
        return len(self.snapshots)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "avg_quality": self.avg_quality,
            "avg_coherence": self.avg_coherence,
            "quality_trend": self.quality_trend,
            "coherence_trend": self.coherence_trend,
            "volatility_avg": self.volatility_avg,
            "success_rate": self.success_rate,
            "revision_rate": self.revision_rate,
            "block_rate": self.block_rate,
            "had_breakthrough": self.had_breakthrough,
            "had_fragmentation": self.had_fragmentation,
            "had_recovery": self.had_recovery,
            "oscillation_count": self.oscillation_count,
        }


@dataclass
class PolicyParameters:
    """
    Tunable policy parameters.

    These are the θ in the SCC update: θ_{t+1} = θ_t + ρ * ∇_θ C_global(t)
    """
    # Quality thresholds
    quality_threshold_high: float = 0.85
    quality_threshold_low: float = 0.50

    # Revision control
    revision_budget: int = 3

    # Coherence thresholds for tool access
    tool_full_access_coherence: float = 0.75
    tool_standard_access_coherence: float = 0.55
    tool_restricted_access_coherence: float = 0.35

    # Decay rates
    quality_decay_rate: float = 0.95

    # Attention budget multiplier
    attention_budget: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "quality_threshold_high": self.quality_threshold_high,
            "quality_threshold_low": self.quality_threshold_low,
            "revision_budget": self.revision_budget,
            "tool_full_access_coherence": self.tool_full_access_coherence,
            "tool_standard_access_coherence": self.tool_standard_access_coherence,
            "tool_restricted_access_coherence": self.tool_restricted_access_coherence,
            "quality_decay_rate": self.quality_decay_rate,
            "attention_budget": self.attention_budget,
        }

    def clone(self) -> "PolicyParameters":
        """Create a copy of parameters."""
        return PolicyParameters(
            quality_threshold_high=self.quality_threshold_high,
            quality_threshold_low=self.quality_threshold_low,
            revision_budget=self.revision_budget,
            tool_full_access_coherence=self.tool_full_access_coherence,
            tool_standard_access_coherence=self.tool_standard_access_coherence,
            tool_restricted_access_coherence=self.tool_restricted_access_coherence,
            quality_decay_rate=self.quality_decay_rate,
            attention_budget=self.attention_budget,
        )


@dataclass
class PolicyDecision:
    """
    Policy decision for current turn.

    This is what the Adaptive Policy Engine outputs to guide behavior.
    """
    # Quality control
    quality_threshold: float           # Minimum quality to accept
    revision_budget: int               # Max revisions allowed

    # Tool access
    tool_permission: ToolPermission    # What tools are available
    allowed_tools: List[str]           # Specific allowed tool names
    blocked_tools: List[str]           # Specific blocked tool names

    # Response guidance
    response_style: str                # "grounded", "reflective", "exploratory", "neutral"
    attention_budget: float            # Multiplier for compute budget

    # Trajectory info
    trajectory: SessionTrajectory      # Current session trajectory
    trajectory_confidence: float       # Confidence in trajectory classification

    # Reasoning (for observability)
    reasoning: List[str]               # Why these decisions were made

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_threshold": self.quality_threshold,
            "revision_budget": self.revision_budget,
            "tool_permission": self.tool_permission.value,
            "allowed_tools": self.allowed_tools,
            "blocked_tools": self.blocked_tools,
            "response_style": self.response_style,
            "attention_budget": self.attention_budget,
            "trajectory": self.trajectory.value,
            "trajectory_confidence": self.trajectory_confidence,
            "reasoning": self.reasoning,
        }


# =============================================================================
# Trajectory Classifier
# =============================================================================


class TrajectoryClassifier:
    """
    Classify session trajectory from performance history.

    Simplified version of motivation_engine.py for agentic use.
    """

    def classify(
        self,
        history: SessionPerformanceHistory,
    ) -> Tuple[SessionTrajectory, float, List[str]]:
        """
        Classify session trajectory.

        Returns:
            Tuple of (trajectory, confidence, drivers)
        """
        if history.turn_count < 2:
            return SessionTrajectory.UNKNOWN, 0.3, ["insufficient_turns"]

        # Check each trajectory type
        candidates = []

        # HOPE_DRIVEN: Upward trends, breakthrough
        if self._check_hope_driven(history):
            conf = 0.75 + min(history.quality_trend * 2, 0.20)
            candidates.append((SessionTrajectory.HOPE_DRIVEN, conf, ["upward_quality", "breakthrough"]))

        # FEAR_DRIVEN: Fragmentation, high volatility
        if self._check_fear_driven(history):
            conf = 0.70 + min(history.volatility_avg * 0.3, 0.20)
            candidates.append((SessionTrajectory.FEAR_DRIVEN, conf, ["fragmentation", "high_volatility"]))

        # EXPANSION_DRIVEN: Good quality, exploring
        if self._check_expansion_driven(history):
            conf = 0.70 + min(history.avg_quality * 0.2, 0.20)
            candidates.append((SessionTrajectory.EXPANSION_DRIVEN, conf, ["high_quality", "exploration"]))

        # STABILIZATION_DRIVEN: Recovery pattern
        if self._check_stabilization_driven(history):
            conf = 0.75 + min(history.coherence_trend * 2, 0.15)
            candidates.append((SessionTrajectory.STABILIZATION_DRIVEN, conf, ["recovery_pattern", "improving"]))

        # OVERCORRECTION: Oscillations
        if self._check_overcorrection(history):
            conf = 0.65 + min(history.oscillation_count * 0.05, 0.20)
            candidates.append((SessionTrajectory.OVERCORRECTION, conf, ["oscillations", "instability"]))

        # AVOIDANCE_DRIVEN: Flat, low engagement
        if self._check_avoidance_driven(history):
            conf = 0.60
            candidates.append((SessionTrajectory.AVOIDANCE_DRIVEN, conf, ["flat_metrics", "low_engagement"]))

        # STABLE: Good coherence, consistent
        if self._check_stable(history):
            conf = 0.80 + min(history.avg_coherence * 0.15, 0.15)
            candidates.append((SessionTrajectory.STABLE, conf, ["high_coherence", "consistent"]))

        # Select best candidate
        if not candidates:
            return SessionTrajectory.UNKNOWN, 0.4, ["no_pattern_matched"]

        # Sort by confidence
        candidates.sort(key=lambda x: -x[1])
        return candidates[0]

    def _check_hope_driven(self, h: SessionPerformanceHistory) -> bool:
        return (
            h.quality_trend > 0.05 and
            h.had_breakthrough and
            h.volatility_avg < 0.5
        )

    def _check_fear_driven(self, h: SessionPerformanceHistory) -> bool:
        return (
            h.had_fragmentation and
            h.volatility_avg > 0.5 and
            h.block_rate > 0.1
        )

    def _check_expansion_driven(self, h: SessionPerformanceHistory) -> bool:
        return (
            h.avg_quality > 0.7 and
            h.avg_coherence > 0.6 and
            h.revision_rate < 0.5
        )

    def _check_stabilization_driven(self, h: SessionPerformanceHistory) -> bool:
        return (
            h.had_recovery and
            h.coherence_trend > 0.03 and
            h.volatility_avg < 0.45
        )

    def _check_overcorrection(self, h: SessionPerformanceHistory) -> bool:
        return (
            h.oscillation_count >= 2 and
            h.volatility_avg > 0.4
        )

    def _check_avoidance_driven(self, h: SessionPerformanceHistory) -> bool:
        return (
            abs(h.quality_trend) < 0.02 and
            abs(h.coherence_trend) < 0.02 and
            h.avg_quality < 0.6
        )

    def _check_stable(self, h: SessionPerformanceHistory) -> bool:
        return (
            h.avg_coherence >= 0.70 and
            h.volatility_avg < 0.35 and
            h.success_rate > 0.8
        )


# =============================================================================
# SCC Parameter Tuner
# =============================================================================


class SCCParameterTuner:
    """
    Self-tuning Coherence Control parameter optimizer.

    Implements gradient descent on policy parameters based on coherence trajectory.

    Update rule: θ_{t+1} = θ_t + ρ * ∇_θ C_global(t)

    Where:
        - θ = policy parameters (thresholds, budgets, etc.)
        - ρ = learning rate
        - C_global = global coherence metric
        - ∇_θ = gradient estimate based on recent performance
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        min_samples: int = 3,
    ):
        self.learning_rate = learning_rate
        self.min_samples = min_samples

    def update(
        self,
        params: PolicyParameters,
        history: SessionPerformanceHistory,
        trajectory: SessionTrajectory,
    ) -> PolicyParameters:
        """
        Update policy parameters based on performance history.

        Args:
            params: Current policy parameters
            history: Session performance history
            trajectory: Classified trajectory

        Returns:
            Updated PolicyParameters
        """
        if history.turn_count < self.min_samples:
            return params

        new_params = params.clone()

        # Compute gradients based on trajectory and metrics
        gradients = self._compute_gradients(history, trajectory)

        # Apply updates with learning rate
        new_params.quality_threshold_high = self._clamp(
            params.quality_threshold_high + self.learning_rate * gradients["quality_threshold_high"],
            0.70, 0.95
        )

        new_params.quality_threshold_low = self._clamp(
            params.quality_threshold_low + self.learning_rate * gradients["quality_threshold_low"],
            0.30, 0.60
        )

        new_params.revision_budget = max(1, min(5,
            params.revision_budget + int(round(gradients["revision_budget"]))
        ))

        new_params.quality_decay_rate = self._clamp(
            params.quality_decay_rate + self.learning_rate * gradients["quality_decay_rate"],
            0.85, 0.99
        )

        new_params.attention_budget = self._clamp(
            params.attention_budget + self.learning_rate * gradients["attention_budget"],
            0.5, 2.0
        )

        return new_params

    def _compute_gradients(
        self,
        history: SessionPerformanceHistory,
        trajectory: SessionTrajectory,
    ) -> Dict[str, float]:
        """
        Compute gradient estimates for each parameter.

        Gradient direction based on:
        - If quality improving → lower thresholds (less restrictive)
        - If quality declining → raise thresholds (more restrictive)
        - If high revision rate → increase budget
        - If high block rate → relax tool access
        """
        gradients = {
            "quality_threshold_high": 0.0,
            "quality_threshold_low": 0.0,
            "revision_budget": 0.0,
            "quality_decay_rate": 0.0,
            "attention_budget": 0.0,
        }

        # Quality trend drives threshold adjustment
        if history.quality_trend > 0.05:
            # Improving: can relax thresholds slightly
            gradients["quality_threshold_high"] = -0.02
            gradients["quality_threshold_low"] = -0.02
        elif history.quality_trend < -0.05:
            # Declining: tighten thresholds
            gradients["quality_threshold_high"] = 0.03
            gradients["quality_threshold_low"] = 0.02

        # Revision rate drives budget
        if history.revision_rate > 0.6:
            # High revision rate: need more budget
            gradients["revision_budget"] = 1.0
        elif history.revision_rate < 0.2 and history.avg_quality > 0.8:
            # Low revision, high quality: can reduce budget
            gradients["revision_budget"] = -0.5

        # Trajectory-specific adjustments
        if trajectory == SessionTrajectory.FEAR_DRIVEN:
            # Fear: be more permissive to help recovery
            gradients["quality_threshold_high"] = -0.03
            gradients["quality_decay_rate"] = 0.02  # Slower decay
            gradients["attention_budget"] = 0.2

        elif trajectory == SessionTrajectory.HOPE_DRIVEN:
            # Hope: maintain momentum
            gradients["attention_budget"] = 0.1

        elif trajectory == SessionTrajectory.STABILIZATION_DRIVEN:
            # Stabilizing: gradual normalization
            gradients["quality_decay_rate"] = -0.01  # Faster return to normal

        elif trajectory == SessionTrajectory.OVERCORRECTION:
            # Overcorrecting: add damping
            gradients["revision_budget"] = -0.5  # Reduce oscillation opportunity
            gradients["attention_budget"] = -0.1

        return gradients

    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))


# =============================================================================
# Tool Access Controller
# =============================================================================


class ToolAccessController:
    """
    Control tool access based on coherence and history.

    Implements progressive trust building:
    - New sessions start with STANDARD access
    - Good performance → FULL access
    - Poor coherence → RESTRICTED or BLOCKED
    """

    # Default tool classifications
    DESTRUCTIVE_TOOLS = [
        "file_delete", "file_overwrite", "system_execute",
        "network_request", "database_modify", "send_email",
    ]

    READ_ONLY_TOOLS = [
        "file_read", "search", "calculate", "format",
        "database_query", "api_get",
    ]

    def determine_access(
        self,
        history: SessionPerformanceHistory,
        params: PolicyParameters,
        trajectory: SessionTrajectory,
    ) -> Tuple[ToolPermission, List[str], List[str]]:
        """
        Determine tool access level.

        Returns:
            Tuple of (permission_level, allowed_tools, blocked_tools)
        """
        # Get current coherence (last snapshot or default)
        current_coherence = 0.5
        if history.snapshots:
            current_coherence = history.snapshots[-1].coherence_score

        # Determine base permission level
        if current_coherence >= params.tool_full_access_coherence:
            permission = ToolPermission.FULL
        elif current_coherence >= params.tool_standard_access_coherence:
            permission = ToolPermission.STANDARD
        elif current_coherence >= params.tool_restricted_access_coherence:
            permission = ToolPermission.RESTRICTED
        else:
            permission = ToolPermission.BLOCKED

        # Trajectory-based adjustments
        if trajectory == SessionTrajectory.FEAR_DRIVEN:
            # Downgrade by one level for safety
            permission = self._downgrade_permission(permission)

        if trajectory == SessionTrajectory.OVERCORRECTION:
            # Restrict to prevent oscillation amplification
            if permission == ToolPermission.FULL:
                permission = ToolPermission.STANDARD

        # History-based adjustments
        if history.block_rate > 0.2:
            # High block rate = something's wrong, be cautious
            permission = self._downgrade_permission(permission)

        if history.had_breakthrough and history.success_rate > 0.9:
            # Excellent performance = trust upgrade
            permission = self._upgrade_permission(permission)

        # Determine specific tool lists
        allowed, blocked = self._get_tool_lists(permission)

        return permission, allowed, blocked

    def _downgrade_permission(self, perm: ToolPermission) -> ToolPermission:
        if perm == ToolPermission.FULL:
            return ToolPermission.STANDARD
        if perm == ToolPermission.STANDARD:
            return ToolPermission.RESTRICTED
        if perm == ToolPermission.RESTRICTED:
            return ToolPermission.BLOCKED
        return ToolPermission.BLOCKED

    def _upgrade_permission(self, perm: ToolPermission) -> ToolPermission:
        if perm == ToolPermission.BLOCKED:
            return ToolPermission.RESTRICTED
        if perm == ToolPermission.RESTRICTED:
            return ToolPermission.STANDARD
        if perm == ToolPermission.STANDARD:
            return ToolPermission.FULL
        return ToolPermission.FULL

    def _get_tool_lists(
        self,
        permission: ToolPermission,
    ) -> Tuple[List[str], List[str]]:
        if permission == ToolPermission.FULL:
            return ["*"], []
        if permission == ToolPermission.STANDARD:
            return ["*"], self.DESTRUCTIVE_TOOLS
        if permission == ToolPermission.RESTRICTED:
            return self.READ_ONLY_TOOLS, self.DESTRUCTIVE_TOOLS
        # BLOCKED
        return [], ["*"]


# =============================================================================
# Response Style Selector
# =============================================================================


class ResponseStyleSelector:
    """
    Select response style based on trajectory and history.

    Styles:
    - "grounded": Concrete, stabilizing, practical
    - "reflective": Deep, exploratory, philosophical
    - "exploratory": Curious, open-ended
    - "neutral": Balanced, adaptive
    """

    def select(
        self,
        history: SessionPerformanceHistory,
        trajectory: SessionTrajectory,
    ) -> str:
        """Select appropriate response style."""
        # Trajectory-based selection (from session_policy.py logic)
        if trajectory == SessionTrajectory.FEAR_DRIVEN:
            return "grounded"  # Stabilize with concrete responses

        if trajectory == SessionTrajectory.HOPE_DRIVEN:
            return "reflective"  # Encourage exploration

        if trajectory == SessionTrajectory.EXPANSION_DRIVEN:
            return "exploratory"  # Support growth

        if trajectory == SessionTrajectory.STABILIZATION_DRIVEN:
            return "grounded"  # Support recovery

        if trajectory == SessionTrajectory.OVERCORRECTION:
            return "grounded"  # Dampen oscillations

        if trajectory == SessionTrajectory.AVOIDANCE_DRIVEN:
            return "exploratory"  # Encourage engagement

        if trajectory == SessionTrajectory.STABLE:
            # Stable session: check if can go deeper
            if history.avg_coherence > 0.75 and history.volatility_avg < 0.3:
                return "reflective"
            return "neutral"

        return "neutral"


# =============================================================================
# Adaptive Policy Engine (Main Class)
# =============================================================================


class AdaptivePolicyEngine:
    """
    Main Adaptive Policy Engine.

    Integrates all components to produce policy decisions based on
    session performance history.

    USAGE:
        engine = AdaptivePolicyEngine()

        # Record performance after each turn
        engine.record_turn(
            session_id="session-123",
            quality_score=0.85,
            coherence_score=0.78,
            ...
        )

        # Get policy decision for next turn
        decision = engine.get_policy_decision("session-123")

        # Use decision in agent
        generator = ReflectiveGenerator(
            threshold_high=decision.quality_threshold,
            max_revisions=decision.revision_budget,
        )
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        history_window: int = 50,
    ):
        """
        Initialize Adaptive Policy Engine.

        Args:
            learning_rate: SCC learning rate for parameter updates
            history_window: Max turns to keep in history per session
        """
        self.learning_rate = learning_rate
        self.history_window = history_window

        # Per-session state
        self._histories: Dict[str, SessionPerformanceHistory] = {}
        self._parameters: Dict[str, PolicyParameters] = {}

        # Components
        self._classifier = TrajectoryClassifier()
        self._tuner = SCCParameterTuner(learning_rate=learning_rate)
        self._tool_controller = ToolAccessController()
        self._style_selector = ResponseStyleSelector()

    def record_turn(
        self,
        session_id: str,
        quality_score: float,
        revision_count: int,
        coherence_score: float,
        goal_alignment: float = 0.7,
        internal_consistency: float = 0.7,
        volatility: float = 0.3,
        was_successful: bool = True,
        was_revised: bool = False,
        was_blocked: bool = False,
    ) -> None:
        """
        Record performance for a turn.

        Call this after each interaction to update the policy engine.

        Args:
            session_id: Session identifier
            quality_score: Response quality [0.0, 1.0]
            revision_count: Number of revisions used
            coherence_score: Coherence score [0.0, 1.0]
            goal_alignment: Goal alignment [0.0, 1.0]
            internal_consistency: Internal consistency [0.0, 1.0]
            volatility: Volatility index [0.0, 1.0]
            was_successful: Whether turn was successful
            was_revised: Whether revision was needed
            was_blocked: Whether safety blocked the action
        """
        # Initialize session if needed
        if session_id not in self._histories:
            self._histories[session_id] = SessionPerformanceHistory(session_id=session_id)
            self._parameters[session_id] = PolicyParameters()

        history = self._histories[session_id]

        # Create snapshot
        snapshot = PerformanceSnapshot(
            turn_index=history.turn_count,
            timestamp=time.time(),
            quality_score=quality_score,
            revision_count=revision_count,
            coherence_score=coherence_score,
            goal_alignment=goal_alignment,
            internal_consistency=internal_consistency,
            volatility=volatility,
            was_successful=was_successful,
            was_revised=was_revised,
            was_blocked=was_blocked,
        )

        # Append to history
        history.append(snapshot)

        # Trim history if too long
        if len(history.snapshots) > self.history_window:
            history.snapshots = history.snapshots[-self.history_window:]
            history._update_aggregates()

        # Update parameters using SCC
        trajectory, _, _ = self._classifier.classify(history)
        self._parameters[session_id] = self._tuner.update(
            self._parameters[session_id],
            history,
            trajectory,
        )

    def get_policy_decision(
        self,
        session_id: str,
    ) -> PolicyDecision:
        """
        Get policy decision for next turn.

        Args:
            session_id: Session identifier

        Returns:
            PolicyDecision with thresholds, budgets, tool access, style
        """
        # Get or create session state
        if session_id not in self._histories:
            self._histories[session_id] = SessionPerformanceHistory(session_id=session_id)
            self._parameters[session_id] = PolicyParameters()

        history = self._histories[session_id]
        params = self._parameters[session_id]

        # Classify trajectory
        trajectory, confidence, drivers = self._classifier.classify(history)

        # Get tool access
        tool_perm, allowed, blocked = self._tool_controller.determine_access(
            history, params, trajectory
        )

        # Get response style
        style = self._style_selector.select(history, trajectory)

        # Build reasoning
        reasoning = [
            f"Trajectory: {trajectory.value} (confidence: {confidence:.2f})",
            f"Drivers: {', '.join(drivers)}",
            f"History: {history.turn_count} turns, avg_quality={history.avg_quality:.2f}",
            f"Tool access: {tool_perm.value}",
            f"Style: {style}",
        ]

        if history.quality_trend > 0:
            reasoning.append(f"Quality improving (+{history.quality_trend:.3f}/turn)")
        elif history.quality_trend < 0:
            reasoning.append(f"Quality declining ({history.quality_trend:.3f}/turn)")

        return PolicyDecision(
            quality_threshold=params.quality_threshold_high,
            revision_budget=params.revision_budget,
            tool_permission=tool_perm,
            allowed_tools=allowed,
            blocked_tools=blocked,
            response_style=style,
            attention_budget=params.attention_budget,
            trajectory=trajectory,
            trajectory_confidence=confidence,
            reasoning=reasoning,
        )

    def get_session_history(self, session_id: str) -> Optional[SessionPerformanceHistory]:
        """Get performance history for a session."""
        return self._histories.get(session_id)

    def get_session_parameters(self, session_id: str) -> Optional[PolicyParameters]:
        """Get current policy parameters for a session."""
        return self._parameters.get(session_id)

    def reset_session(self, session_id: str) -> None:
        """Reset session state."""
        if session_id in self._histories:
            del self._histories[session_id]
        if session_id in self._parameters:
            del self._parameters[session_id]

    def get_all_sessions(self) -> List[str]:
        """Get all tracked session IDs."""
        return list(self._histories.keys())


# =============================================================================
# Factory Functions
# =============================================================================


def create_adaptive_policy_engine(
    learning_rate: float = 0.05,
    history_window: int = 50,
) -> AdaptivePolicyEngine:
    """
    Create an Adaptive Policy Engine.

    Args:
        learning_rate: SCC learning rate (default 0.05)
        history_window: Max turns to track per session (default 50)

    Returns:
        AdaptivePolicyEngine instance
    """
    return AdaptivePolicyEngine(
        learning_rate=learning_rate,
        history_window=history_window,
    )


# =============================================================================
# Public API
# =============================================================================


__all__ = [
    # Enums
    "SessionTrajectory",
    "ToolPermission",
    # Data classes
    "PerformanceSnapshot",
    "SessionPerformanceHistory",
    "PolicyParameters",
    "PolicyDecision",
    # Main engine
    "AdaptivePolicyEngine",
    "create_adaptive_policy_engine",
    # Components (for advanced use)
    "TrajectoryClassifier",
    "SCCParameterTuner",
    "ToolAccessController",
    "ResponseStyleSelector",
]
