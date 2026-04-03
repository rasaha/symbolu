"""
Confidence Gating Module

Confidence that CONTROLS behavior, not just ANNOTATES output.

THIS IS NOT COSMETIC CONFIDENCE:
    ❌ Scalar number displayed to user
    ❌ Post-hoc annotation
    ❌ Advisory only

THIS IS BEHAVIORAL CONFIDENCE:
    ✅ Gates tool execution
    ✅ Throttles compute budget
    ✅ Escalates to human verification
    ✅ Weights memory retention
    ✅ Controls, not annotates

ARCHITECTURE:
    ┌─────────────────────────────────────────────────────────────┐
    │                  ConfidenceGate                              │
    │                                                              │
    │  Inputs (existing signals):                                  │
    │  ├─ QualityCritique.overall_score                           │
    │  ├─ CoherenceMetrics.internal_consistency                   │
    │  ├─ PolicyDecision.trajectory_confidence                    │
    │  └─ Custom confidence estimators                            │
    │                                                              │
    │  Outputs (behavioral controls):                              │
    │  ├─ EscalationDecision (human_required, reason)             │
    │  ├─ BudgetAllocation (revision_budget, attention_budget)    │
    │  ├─ MemoryWeight (retention_weight, importance_score)       │
    │  └─ ExecutionPermission (allowed, requires_confirmation)    │
    └─────────────────────────────────────────────────────────────┘

CONFIDENCE AGGREGATION:
    We combine multiple existing signals into a unified confidence score:

    C_unified = w1*quality + w2*coherence + w3*consistency + w4*trajectory_conf

    Where weights are configurable based on context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


# =============================================================================
# Enums
# =============================================================================


class EscalationLevel(Enum):
    """Escalation levels for human intervention."""
    NONE = "none"                    # No escalation needed
    NOTIFY = "notify"                # Inform human, but proceed
    CONFIRM = "confirm"              # Require human confirmation
    HALT = "halt"                    # Stop and wait for human


class ExecutionMode(Enum):
    """Execution permission modes."""
    FULL = "full"                    # Execute without restriction
    CAUTIOUS = "cautious"            # Execute with extra validation
    CONFIRM_REQUIRED = "confirm"     # Require explicit confirmation
    BLOCKED = "blocked"              # Do not execute


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ConfidenceSignals:
    """
    Aggregated confidence signals from various sources.

    Collects existing scores from the framework into a unified view.
    """
    # Quality signals (from QualityCritique)
    quality_score: float = 0.5
    coherence_score: float = 0.5
    correctness_score: float = 0.5
    completeness_score: float = 0.5
    relevance_score: float = 0.5

    # Coherence signals (from CoherenceMetrics)
    internal_consistency: float = 0.5
    goal_alignment: float = 0.5
    prediction_reversal_risk: float = 0.5
    volatility_index: float = 0.5

    # Trajectory signals (from AdaptivePolicyEngine)
    trajectory_confidence: float = 0.5
    session_stability: float = 0.5

    # Action-specific signals
    action_complexity: float = 0.5      # How complex is the requested action
    action_reversibility: float = 1.0   # Can it be undone? (1.0 = fully reversible)

    # Phase 3: Session enrichment signals
    identity_stability: float = 0.5     # 0=fragile/unstable, 1=stable/anchored
    motivation_stability: float = 0.5   # 0=fear/avoidance/overcorrection, 1=hope/stable
    temporal_stability: float = 0.5     # 0=tense/volatile, 1=stable/recovering
    session_enrichment_adjustment: float = 0.0  # Bounded penalty from adapter (<=0)

    # Strategy 2: Output modulation → confidence adjustment
    # Bounded adjustment derived from E = G × P × T (guna modulation intensity).
    # Low E → cautionary penalty (up to -0.10); high E → modest uplift (up to +0.03).
    # Missing/unavailable E → 0.0 (neutral, no effect).
    output_modulation_adjustment: float = 0.0  # Bounded [-0.10, +0.03]

    def to_dict(self) -> Dict[str, float]:
        return {
            "quality_score": self.quality_score,
            "coherence_score": self.coherence_score,
            "correctness_score": self.correctness_score,
            "completeness_score": self.completeness_score,
            "relevance_score": self.relevance_score,
            "internal_consistency": self.internal_consistency,
            "goal_alignment": self.goal_alignment,
            "prediction_reversal_risk": self.prediction_reversal_risk,
            "volatility_index": self.volatility_index,
            "trajectory_confidence": self.trajectory_confidence,
            "session_stability": self.session_stability,
            "action_complexity": self.action_complexity,
            "action_reversibility": self.action_reversibility,
            "identity_stability": self.identity_stability,
            "motivation_stability": self.motivation_stability,
            "temporal_stability": self.temporal_stability,
            "session_enrichment_adjustment": self.session_enrichment_adjustment,
            "output_modulation_adjustment": self.output_modulation_adjustment,
        }


@dataclass
class UnifiedConfidence:
    """
    Unified confidence score with breakdown.

    Combines multiple signals into a single actionable confidence.
    """
    # Overall confidence [0.0, 1.0]
    overall: float

    # Component breakdown
    quality_component: float
    coherence_component: float
    stability_component: float
    action_component: float

    # Metadata
    signals_used: List[str] = field(default_factory=list)
    weights_applied: Dict[str, float] = field(default_factory=dict)

    @property
    def is_high(self) -> bool:
        return self.overall >= 0.75

    @property
    def is_medium(self) -> bool:
        return 0.45 <= self.overall < 0.75

    @property
    def is_low(self) -> bool:
        return self.overall < 0.45

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "quality_component": self.quality_component,
            "coherence_component": self.coherence_component,
            "stability_component": self.stability_component,
            "action_component": self.action_component,
            "is_high": self.is_high,
            "is_medium": self.is_medium,
            "is_low": self.is_low,
            "signals_used": self.signals_used,
        }


@dataclass
class EscalationDecision:
    """
    Decision about whether to escalate to human.

    Low confidence → escalate for verification.
    """
    level: EscalationLevel
    confidence: float
    reasons: List[str] = field(default_factory=list)
    suggested_questions: List[str] = field(default_factory=list)
    timeout_seconds: Optional[float] = None  # How long to wait for human

    @property
    def requires_human(self) -> bool:
        return self.level in [EscalationLevel.CONFIRM, EscalationLevel.HALT]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "requires_human": self.requires_human,
            "suggested_questions": self.suggested_questions,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class BudgetAllocation:
    """
    Compute budget allocation based on confidence.

    Low confidence → more budget for verification/revision.
    High confidence → less budget needed.
    """
    # Revision control
    revision_budget: int              # Max revisions allowed
    revision_threshold: float         # Quality threshold to accept

    # Compute allocation
    attention_multiplier: float       # Multiplier for compute budget
    max_tokens: int                   # Token limit for response

    # Verification
    require_self_check: bool          # Must self-verify before output
    require_source_citation: bool     # Must cite sources if factual

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision_budget": self.revision_budget,
            "revision_threshold": self.revision_threshold,
            "attention_multiplier": self.attention_multiplier,
            "max_tokens": self.max_tokens,
            "require_self_check": self.require_self_check,
            "require_source_citation": self.require_source_citation,
        }


@dataclass
class MemoryWeight:
    """
    Memory retention weight based on confidence.

    High confidence → store with high weight, retrieve preferentially.
    Low confidence → store with low weight or don't store.
    """
    retention_weight: float           # [0.0, 1.0] - How important to remember
    retrieval_priority: float         # [0.0, 1.0] - Priority in retrieval
    should_store: bool                # Whether to store at all
    expiry_turns: Optional[int]       # Auto-expire after N turns (None = permanent)
    tags: List[str] = field(default_factory=list)  # Metadata tags

    def to_dict(self) -> Dict[str, Any]:
        return {
            "retention_weight": self.retention_weight,
            "retrieval_priority": self.retrieval_priority,
            "should_store": self.should_store,
            "expiry_turns": self.expiry_turns,
            "tags": self.tags,
        }


@dataclass
class ExecutionPermission:
    """
    Permission to execute an action based on confidence.

    Confidence gates whether actions can proceed.
    """
    mode: ExecutionMode
    confidence: float
    allowed_actions: List[str] = field(default_factory=list)
    blocked_actions: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    fallback_action: Optional[str] = None

    @property
    def can_execute(self) -> bool:
        return self.mode in [ExecutionMode.FULL, ExecutionMode.CAUTIOUS]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "confidence": self.confidence,
            "can_execute": self.can_execute,
            "allowed_actions": self.allowed_actions,
            "blocked_actions": self.blocked_actions,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_prompt": self.confirmation_prompt,
            "fallback_action": self.fallback_action,
        }


@dataclass
class ConfidenceGateDecision:
    """
    Complete confidence gate decision.

    Bundles all behavioral controls into a single decision.
    """
    confidence: UnifiedConfidence
    escalation: EscalationDecision
    budget: BudgetAllocation
    memory: MemoryWeight
    execution: ExecutionPermission

    # Reasoning for observability
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": self.confidence.to_dict(),
            "escalation": self.escalation.to_dict(),
            "budget": self.budget.to_dict(),
            "memory": self.memory.to_dict(),
            "execution": self.execution.to_dict(),
            "reasoning": self.reasoning,
        }


# =============================================================================
# Confidence Aggregator
# =============================================================================


@dataclass
class AggregationWeights:
    """Weights for combining confidence signals."""
    quality: float = 0.30
    coherence: float = 0.25
    stability: float = 0.25
    action: float = 0.20

    def normalize(self) -> "AggregationWeights":
        """Normalize weights to sum to 1.0."""
        total = self.quality + self.coherence + self.stability + self.action
        if total == 0:
            return AggregationWeights(0.25, 0.25, 0.25, 0.25)
        return AggregationWeights(
            quality=self.quality / total,
            coherence=self.coherence / total,
            stability=self.stability / total,
            action=self.action / total,
        )


class ConfidenceAggregator:
    """
    Aggregates multiple confidence signals into unified confidence.

    Uses weighted combination with configurable weights.
    """

    def __init__(self, weights: Optional[AggregationWeights] = None):
        self.weights = (weights or AggregationWeights()).normalize()

    def aggregate(self, signals: ConfidenceSignals) -> UnifiedConfidence:
        """
        Aggregate signals into unified confidence.

        Components:
        - Quality: quality_score, correctness, completeness, relevance
        - Coherence: coherence_score, internal_consistency, goal_alignment
        - Stability: trajectory_confidence, session_stability, 1-volatility
        - Action: action_reversibility, 1-action_complexity
        """
        # Quality component
        quality_component = (
            signals.quality_score * 0.4 +
            signals.correctness_score * 0.3 +
            signals.completeness_score * 0.15 +
            signals.relevance_score * 0.15
        )

        # Coherence component
        coherence_component = (
            signals.coherence_score * 0.4 +
            signals.internal_consistency * 0.35 +
            signals.goal_alignment * 0.25
        )

        # Stability component (invert risk metrics)
        stability_component = (
            signals.trajectory_confidence * 0.4 +
            signals.session_stability * 0.3 +
            (1.0 - signals.volatility_index) * 0.15 +
            (1.0 - signals.prediction_reversal_risk) * 0.15
        )

        # Action component (high reversibility, low complexity = high confidence)
        action_component = (
            signals.action_reversibility * 0.6 +
            (1.0 - signals.action_complexity) * 0.4
        )

        # Weighted combination
        overall = (
            self.weights.quality * quality_component +
            self.weights.coherence * coherence_component +
            self.weights.stability * stability_component +
            self.weights.action * action_component
        )

        # Phase 3: Apply bounded session enrichment penalty (additive, <=0).
        # This is stricter-only: penalty can only reduce confidence, never raise it.
        overall += signals.session_enrichment_adjustment

        # Strategy 2: Apply bounded output modulation adjustment.
        # Derived from E = G × P × T. Asymmetric: larger downside than upside.
        # Bounds: [-0.10, +0.03]. Missing E → 0.0 (neutral).
        overall += signals.output_modulation_adjustment

        # Clamp to [0, 1]
        overall = max(0.0, min(1.0, overall))

        signals_used = [
            "quality_score", "coherence_score", "internal_consistency",
            "trajectory_confidence", "volatility_index", "action_reversibility",
        ]
        if signals.session_enrichment_adjustment != 0.0:
            signals_used.append("session_enrichment_adjustment")
        if signals.output_modulation_adjustment != 0.0:
            signals_used.append("output_modulation_adjustment")

        return UnifiedConfidence(
            overall=overall,
            quality_component=quality_component,
            coherence_component=coherence_component,
            stability_component=stability_component,
            action_component=action_component,
            signals_used=signals_used,
            weights_applied={
                "quality": self.weights.quality,
                "coherence": self.weights.coherence,
                "stability": self.weights.stability,
                "action": self.weights.action,
            },
        )


# =============================================================================
# Behavioral Controllers
# =============================================================================


class EscalationController:
    """
    Determines when to escalate to human based on confidence.

    Thresholds:
    - NONE: confidence >= 0.75
    - NOTIFY: 0.55 <= confidence < 0.75
    - CONFIRM: 0.35 <= confidence < 0.55
    - HALT: confidence < 0.35
    """

    def __init__(
        self,
        halt_threshold: float = 0.35,
        confirm_threshold: float = 0.55,
        notify_threshold: float = 0.75,
        default_timeout: float = 300.0,  # 5 minutes
    ):
        self.halt_threshold = halt_threshold
        self.confirm_threshold = confirm_threshold
        self.notify_threshold = notify_threshold
        self.default_timeout = default_timeout

    def decide(
        self,
        confidence: UnifiedConfidence,
        action_description: Optional[str] = None,
    ) -> EscalationDecision:
        """Determine escalation level from confidence."""
        c = confidence.overall
        reasons = []
        questions = []

        if c < self.halt_threshold:
            level = EscalationLevel.HALT
            reasons.append(f"Confidence critically low ({c:.2f})")
            if confidence.quality_component < 0.4:
                reasons.append("Quality assessment uncertain")
            if confidence.coherence_component < 0.4:
                reasons.append("Response may be incoherent")
            if confidence.stability_component < 0.4:
                reasons.append("Session state unstable")
            questions.append("Should I proceed with this action?")
            questions.append("Can you provide more context?")

        elif c < self.confirm_threshold:
            level = EscalationLevel.CONFIRM
            reasons.append(f"Confidence below threshold ({c:.2f})")
            if confidence.action_component < 0.5:
                reasons.append("Action may have significant impact")
            questions.append("Please confirm this is correct.")

        elif c < self.notify_threshold:
            level = EscalationLevel.NOTIFY
            reasons.append(f"Moderate confidence ({c:.2f})")

        else:
            level = EscalationLevel.NONE

        return EscalationDecision(
            level=level,
            confidence=c,
            reasons=reasons,
            suggested_questions=questions,
            timeout_seconds=self.default_timeout if level in [
                EscalationLevel.CONFIRM, EscalationLevel.HALT
            ] else None,
        )


class BudgetController:
    """
    Allocates compute budget based on confidence.

    Low confidence → more budget for verification.
    High confidence → minimal budget needed.
    """

    def __init__(
        self,
        base_revision_budget: int = 3,
        base_max_tokens: int = 2048,
        min_revision_budget: int = 1,
        max_revision_budget: int = 5,
    ):
        self.base_revision_budget = base_revision_budget
        self.base_max_tokens = base_max_tokens
        self.min_revision_budget = min_revision_budget
        self.max_revision_budget = max_revision_budget

    def allocate(self, confidence: UnifiedConfidence) -> BudgetAllocation:
        """Allocate budget based on confidence."""
        c = confidence.overall

        # Low confidence → more revisions allowed
        if c < 0.4:
            revision_budget = self.max_revision_budget
            revision_threshold = 0.75  # Higher bar to accept
            attention_multiplier = 1.5
            require_self_check = True
            require_source_citation = True
        elif c < 0.6:
            revision_budget = self.base_revision_budget + 1
            revision_threshold = 0.80
            attention_multiplier = 1.2
            require_self_check = True
            require_source_citation = False
        elif c < 0.8:
            revision_budget = self.base_revision_budget
            revision_threshold = 0.85
            attention_multiplier = 1.0
            require_self_check = False
            require_source_citation = False
        else:
            # High confidence → can use less budget
            revision_budget = max(self.min_revision_budget, self.base_revision_budget - 1)
            revision_threshold = 0.85
            attention_multiplier = 0.9
            require_self_check = False
            require_source_citation = False

        # Scale max tokens with attention multiplier
        max_tokens = int(self.base_max_tokens * attention_multiplier)

        return BudgetAllocation(
            revision_budget=revision_budget,
            revision_threshold=revision_threshold,
            attention_multiplier=attention_multiplier,
            max_tokens=max_tokens,
            require_self_check=require_self_check,
            require_source_citation=require_source_citation,
        )


class MemoryController:
    """
    Controls memory retention based on confidence.

    High confidence → store with high weight, long retention.
    Low confidence → store with low weight or skip storage.
    """

    def __init__(
        self,
        store_threshold: float = 0.3,
        high_priority_threshold: float = 0.8,
        default_expiry_turns: int = 50,
    ):
        self.store_threshold = store_threshold
        self.high_priority_threshold = high_priority_threshold
        self.default_expiry_turns = default_expiry_turns

    def decide(self, confidence: UnifiedConfidence) -> MemoryWeight:
        """Decide memory retention from confidence."""
        c = confidence.overall
        tags = []

        # Don't store very low confidence responses
        if c < self.store_threshold:
            return MemoryWeight(
                retention_weight=0.0,
                retrieval_priority=0.0,
                should_store=False,
                expiry_turns=None,
                tags=["low_confidence", "not_stored"],
            )

        # High confidence → high retention, no expiry
        if c >= self.high_priority_threshold:
            tags.append("high_confidence")
            return MemoryWeight(
                retention_weight=1.0,
                retrieval_priority=1.0,
                should_store=True,
                expiry_turns=None,  # Permanent
                tags=tags,
            )

        # Medium confidence → proportional retention
        # Map [store_threshold, high_priority_threshold] to [0.3, 1.0]
        range_size = self.high_priority_threshold - self.store_threshold
        normalized = (c - self.store_threshold) / range_size
        retention_weight = 0.3 + normalized * 0.7
        retrieval_priority = 0.2 + normalized * 0.6

        # Shorter expiry for lower confidence
        if c < 0.5:
            expiry_turns = self.default_expiry_turns // 2
            tags.append("medium_low_confidence")
        else:
            expiry_turns = self.default_expiry_turns
            tags.append("medium_confidence")

        return MemoryWeight(
            retention_weight=retention_weight,
            retrieval_priority=retrieval_priority,
            should_store=True,
            expiry_turns=expiry_turns,
            tags=tags,
        )


class ExecutionController:
    """
    Controls action execution based on confidence.

    Confidence gates whether actions can proceed.
    """

    # Actions that require higher confidence
    HIGH_RISK_ACTIONS = [
        "file_delete", "file_overwrite", "database_modify",
        "send_email", "api_post", "system_execute", "deploy",
    ]

    # Actions that are always allowed
    SAFE_ACTIONS = [
        "file_read", "search", "calculate", "format", "explain",
    ]

    def __init__(
        self,
        full_threshold: float = 0.75,
        cautious_threshold: float = 0.55,
        confirm_threshold: float = 0.35,
    ):
        self.full_threshold = full_threshold
        self.cautious_threshold = cautious_threshold
        self.confirm_threshold = confirm_threshold

    def decide(
        self,
        confidence: UnifiedConfidence,
        requested_action: Optional[str] = None,
    ) -> ExecutionPermission:
        """Decide execution permission from confidence."""
        c = confidence.overall

        # Check if action is high-risk
        is_high_risk = requested_action and any(
            risk in requested_action.lower()
            for risk in self.HIGH_RISK_ACTIONS
        )

        # Check if action is safe
        is_safe = requested_action and any(
            safe in requested_action.lower()
            for safe in self.SAFE_ACTIONS
        )

        # Determine mode
        if c >= self.full_threshold:
            if is_high_risk and c < 0.85:
                mode = ExecutionMode.CAUTIOUS
            else:
                mode = ExecutionMode.FULL
        elif c >= self.cautious_threshold:
            mode = ExecutionMode.CAUTIOUS
        elif c >= self.confirm_threshold:
            mode = ExecutionMode.CONFIRM_REQUIRED
        else:
            mode = ExecutionMode.BLOCKED

        # Safe actions get upgraded
        if is_safe and mode == ExecutionMode.BLOCKED:
            mode = ExecutionMode.CONFIRM_REQUIRED
        if is_safe and mode == ExecutionMode.CONFIRM_REQUIRED:
            mode = ExecutionMode.CAUTIOUS

        # High-risk actions get downgraded
        if is_high_risk and mode == ExecutionMode.FULL and c < 0.9:
            mode = ExecutionMode.CAUTIOUS
        if is_high_risk and mode == ExecutionMode.CAUTIOUS and c < 0.7:
            mode = ExecutionMode.CONFIRM_REQUIRED

        # Build permission
        requires_confirmation = mode == ExecutionMode.CONFIRM_REQUIRED
        confirmation_prompt = None
        if requires_confirmation:
            confirmation_prompt = f"Confidence is {c:.2f}. Confirm action: {requested_action}?"

        fallback_action = None
        if mode == ExecutionMode.BLOCKED:
            fallback_action = "explain_instead"  # Explain rather than execute

        return ExecutionPermission(
            mode=mode,
            confidence=c,
            allowed_actions=self.SAFE_ACTIONS if mode != ExecutionMode.BLOCKED else [],
            blocked_actions=self.HIGH_RISK_ACTIONS if c < self.full_threshold else [],
            requires_confirmation=requires_confirmation,
            confirmation_prompt=confirmation_prompt,
            fallback_action=fallback_action,
        )


# =============================================================================
# Main Confidence Gate
# =============================================================================


class ConfidenceGate:
    """
    Main Confidence Gate that controls behavior based on confidence.

    Aggregates confidence signals and makes behavioral decisions:
    - Escalation to human
    - Budget allocation
    - Memory retention
    - Execution permission

    USAGE:
        gate = ConfidenceGate()

        # Build signals from existing framework data
        signals = ConfidenceSignals(
            quality_score=critique.overall_score,
            coherence_score=coherence.internal_consistency,
            trajectory_confidence=policy_decision.trajectory_confidence,
            ...
        )

        # Get gating decision
        decision = gate.evaluate(signals, action="file_delete")

        # Use decision
        if decision.escalation.requires_human:
            await get_human_confirmation()

        if decision.execution.can_execute:
            execute_action()

        if decision.memory.should_store:
            store_with_weight(decision.memory.retention_weight)
    """

    def __init__(
        self,
        aggregation_weights: Optional[AggregationWeights] = None,
        escalation_thresholds: Optional[Dict[str, float]] = None,
        budget_config: Optional[Dict[str, int]] = None,
        memory_config: Optional[Dict[str, float]] = None,
        execution_thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize Confidence Gate.

        Args:
            aggregation_weights: Weights for combining signals
            escalation_thresholds: Thresholds for escalation levels
            budget_config: Budget allocation configuration
            memory_config: Memory retention configuration
            execution_thresholds: Execution permission thresholds
        """
        self.aggregator = ConfidenceAggregator(aggregation_weights)

        self.escalation_controller = EscalationController(
            **(escalation_thresholds or {})
        )

        self.budget_controller = BudgetController(
            **(budget_config or {})
        )

        self.memory_controller = MemoryController(
            **(memory_config or {})
        )

        self.execution_controller = ExecutionController(
            **(execution_thresholds or {})
        )

    def evaluate(
        self,
        signals: ConfidenceSignals,
        action: Optional[str] = None,
    ) -> ConfidenceGateDecision:
        """
        Evaluate confidence signals and produce behavioral decisions.

        Args:
            signals: Confidence signals from various sources
            action: Optional action being considered

        Returns:
            ConfidenceGateDecision with all behavioral controls
        """
        # Aggregate confidence
        confidence = self.aggregator.aggregate(signals)

        # Get behavioral decisions
        escalation = self.escalation_controller.decide(confidence, action)
        budget = self.budget_controller.allocate(confidence)
        memory = self.memory_controller.decide(confidence)
        execution = self.execution_controller.decide(confidence, action)

        # Build reasoning
        reasoning = self._build_reasoning(confidence, escalation, budget, memory, execution)

        return ConfidenceGateDecision(
            confidence=confidence,
            escalation=escalation,
            budget=budget,
            memory=memory,
            execution=execution,
            reasoning=reasoning,
        )

    def _build_reasoning(
        self,
        confidence: UnifiedConfidence,
        escalation: EscalationDecision,
        budget: BudgetAllocation,
        memory: MemoryWeight,
        execution: ExecutionPermission,
    ) -> List[str]:
        """Build reasoning explanation for decision."""
        reasoning = []

        # Confidence level
        if confidence.is_high:
            reasoning.append(f"High confidence ({confidence.overall:.2f})")
        elif confidence.is_medium:
            reasoning.append(f"Medium confidence ({confidence.overall:.2f})")
        else:
            reasoning.append(f"Low confidence ({confidence.overall:.2f})")

        # Component breakdown
        if confidence.quality_component < 0.5:
            reasoning.append("Quality component weak - response may need revision")
        if confidence.coherence_component < 0.5:
            reasoning.append("Coherence component weak - response may be inconsistent")
        if confidence.stability_component < 0.5:
            reasoning.append("Stability component weak - session state uncertain")
        if confidence.action_component < 0.5:
            reasoning.append("Action component weak - action may be risky")

        # Escalation
        if escalation.level != EscalationLevel.NONE:
            reasoning.append(f"Escalation: {escalation.level.value}")

        # Budget
        if budget.require_self_check:
            reasoning.append("Self-check required before output")
        if budget.revision_budget > 3:
            reasoning.append(f"Extra revisions allowed ({budget.revision_budget})")

        # Memory
        if not memory.should_store:
            reasoning.append("Response will not be stored in memory")
        elif memory.expiry_turns:
            reasoning.append(f"Memory expires after {memory.expiry_turns} turns")

        # Execution
        if execution.mode == ExecutionMode.BLOCKED:
            reasoning.append("Action execution blocked due to low confidence")
        elif execution.requires_confirmation:
            reasoning.append("Human confirmation required before execution")

        return reasoning

    def quick_check(
        self,
        quality_score: float,
        coherence_score: float,
        action: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Quick confidence check with minimal signals.

        Args:
            quality_score: Response quality [0, 1]
            coherence_score: Coherence score [0, 1]
            action: Optional action being considered

        Returns:
            Tuple of (can_proceed, reason)
        """
        signals = ConfidenceSignals(
            quality_score=quality_score,
            coherence_score=coherence_score,
            correctness_score=quality_score,
            internal_consistency=coherence_score,
        )

        decision = self.evaluate(signals, action)

        can_proceed = (
            decision.execution.can_execute and
            not decision.escalation.requires_human
        )

        reason = decision.reasoning[0] if decision.reasoning else "No specific reason"

        return can_proceed, reason


# =============================================================================
# Factory Functions
# =============================================================================


def create_confidence_gate(
    quality_weight: float = 0.30,
    coherence_weight: float = 0.25,
    stability_weight: float = 0.25,
    action_weight: float = 0.20,
) -> ConfidenceGate:
    """
    Create a Confidence Gate with custom weights.

    Args:
        quality_weight: Weight for quality signals
        coherence_weight: Weight for coherence signals
        stability_weight: Weight for stability signals
        action_weight: Weight for action signals

    Returns:
        Configured ConfidenceGate
    """
    weights = AggregationWeights(
        quality=quality_weight,
        coherence=coherence_weight,
        stability=stability_weight,
        action=action_weight,
    )
    return ConfidenceGate(aggregation_weights=weights)


def create_strict_confidence_gate() -> ConfidenceGate:
    """
    Create a strict Confidence Gate with higher thresholds.

    Use for high-stakes applications.
    """
    return ConfidenceGate(
        escalation_thresholds={
            "halt_threshold": 0.45,
            "confirm_threshold": 0.65,
            "notify_threshold": 0.85,
        },
        execution_thresholds={
            "full_threshold": 0.85,
            "cautious_threshold": 0.65,
            "confirm_threshold": 0.45,
        },
    )


def create_permissive_confidence_gate() -> ConfidenceGate:
    """
    Create a permissive Confidence Gate with lower thresholds.

    Use for low-stakes applications or rapid prototyping.
    """
    return ConfidenceGate(
        escalation_thresholds={
            "halt_threshold": 0.20,
            "confirm_threshold": 0.40,
            "notify_threshold": 0.60,
        },
        execution_thresholds={
            "full_threshold": 0.60,
            "cautious_threshold": 0.40,
            "confirm_threshold": 0.20,
        },
    )


# =============================================================================
# Integration Helpers
# =============================================================================


def signals_from_critique(critique: Any) -> ConfidenceSignals:
    """
    Build ConfidenceSignals from a QualityCritique.

    Args:
        critique: QualityCritique from reflective_loop

    Returns:
        ConfidenceSignals populated from critique
    """
    return ConfidenceSignals(
        quality_score=getattr(critique, "overall_score", 0.5),
        coherence_score=getattr(critique, "coherence", 0.5),
        correctness_score=getattr(critique, "correctness", 0.5),
        completeness_score=getattr(critique, "completeness", 0.5),
        relevance_score=getattr(critique, "relevance", 0.5),
    )


def signals_from_coherence_metrics(metrics: Any) -> ConfidenceSignals:
    """
    Build ConfidenceSignals from CoherenceMetrics.

    Args:
        metrics: CoherenceMetrics from coherence_tracker

    Returns:
        ConfidenceSignals populated from metrics
    """
    return ConfidenceSignals(
        internal_consistency=getattr(metrics, "internal_consistency", 0.5),
        goal_alignment=getattr(metrics, "goal_alignment", 0.5),
        prediction_reversal_risk=getattr(metrics, "prediction_reversal_risk", 0.5),
        volatility_index=getattr(metrics, "volatility_index", 0.5),
        coherence_score=getattr(metrics, "overall_coherence", 0.5),
    )


def signals_from_policy_decision(decision: Any) -> ConfidenceSignals:
    """
    Build ConfidenceSignals from PolicyDecision.

    Args:
        decision: PolicyDecision from adaptive_policy

    Returns:
        ConfidenceSignals populated from decision
    """
    return ConfidenceSignals(
        trajectory_confidence=getattr(decision, "trajectory_confidence", 0.5),
        session_stability=1.0 if getattr(decision, "response_style", "") == "stable" else 0.6,
    )


def merge_signals(*signal_list: ConfidenceSignals) -> ConfidenceSignals:
    """
    Merge multiple ConfidenceSignals, taking the first non-default value.

    Args:
        signal_list: Multiple ConfidenceSignals to merge

    Returns:
        Merged ConfidenceSignals
    """
    result = ConfidenceSignals()

    for signals in signal_list:
        for field_name in [
            "quality_score", "coherence_score", "correctness_score",
            "completeness_score", "relevance_score", "internal_consistency",
            "goal_alignment", "prediction_reversal_risk", "volatility_index",
            "trajectory_confidence", "session_stability", "action_complexity",
            "action_reversibility",
        ]:
            current = getattr(result, field_name)
            new_val = getattr(signals, field_name)
            # Take new value if current is default (0.5) and new is not
            if current == 0.5 and new_val != 0.5:
                setattr(result, field_name, new_val)
            # Special case for action_reversibility (default 1.0)
            elif field_name == "action_reversibility" and current == 1.0 and new_val != 1.0:
                setattr(result, field_name, new_val)

    return result


# =============================================================================
# Public API
# =============================================================================


__all__ = [
    # Enums
    "EscalationLevel",
    "ExecutionMode",
    # Data classes
    "ConfidenceSignals",
    "UnifiedConfidence",
    "EscalationDecision",
    "BudgetAllocation",
    "MemoryWeight",
    "ExecutionPermission",
    "ConfidenceGateDecision",
    "AggregationWeights",
    # Main gate
    "ConfidenceGate",
    # Factory functions
    "create_confidence_gate",
    "create_strict_confidence_gate",
    "create_permissive_confidence_gate",
    # Integration helpers
    "signals_from_critique",
    "signals_from_coherence_metrics",
    "signals_from_policy_decision",
    "merge_signals",
]
