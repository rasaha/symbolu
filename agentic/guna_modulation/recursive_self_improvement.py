"""
Recursive Self-Improvement for SymbolU v2.7 Enterprise
=======================================================

Integrates with the existing Guna modulation framework to enable
self-improvement capabilities using available signals.

Key Integration Points:
1. Observables (s, r, t, H, M, C_contr, F_fail) → Signal source
2. Utility computation → Evaluation metric
3. State Evolution Engine → Learning mechanism
4. Causal Layer → Reasoning about failures

This module enables the system to:
- Track its own utility outcomes
- Identify patterns of low utility
- Generate hypotheses for improvement
- Modify its beliefs/coefficients based on evidence

Version: 2.7.4
Date: 2025-12-23
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Callable
from collections import deque
from enum import Enum
from datetime import datetime
import math

from agentic.guna_modulation.observables import Observables, MotionType
from agentic.guna_modulation.utility import (
    compute_utility,
    UtilityAudit,
)
from agentic.guna_modulation.state_types import StateRegister
from agentic.guna_modulation.v27_config import (
    UtilityCoefficients,
    DEFAULT_UTILITY_COEFFICIENTS,
    V27Config,
)


# =============================================================================
# Belief System
# =============================================================================

class BeliefType(Enum):
    """Types of beliefs in the enterprise knowledge base."""
    PRIOR = "prior"           # Initial assumptions from design
    LEARNED = "learned"       # Learned from observation
    HYPOTHESIS = "hypothesis" # Proposed but unverified
    VERIFIED = "verified"     # Tested and confirmed
    DEPRECATED = "deprecated" # Previously held, now rejected


@dataclass
class Belief:
    """
    A belief about system behavior or optimal configuration.

    Uses Bayesian confidence updating based on utility outcomes.
    """
    id: str
    content: str
    belief_type: BeliefType
    confidence: float  # P(belief is true) in [0, 1]

    # Evidence tracking
    evidence_count: int = 0
    supporting_evidence: int = 0
    contradicting_evidence: int = 0

    # Temporal tracking
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_with_utility(self, utility: float, threshold: float = 0.5) -> "Belief":
        """Update belief based on utility outcome."""
        self.evidence_count += 1

        # Utility above threshold supports the belief
        if utility > threshold:
            self.supporting_evidence += 1
        else:
            self.contradicting_evidence += 1

        # Bayesian update (Beta posterior)
        alpha = self.supporting_evidence + 1
        beta = self.contradicting_evidence + 1
        self.confidence = alpha / (alpha + beta)

        self.last_updated = datetime.now().isoformat()

        # Check for state transitions
        if self.confidence < 0.2 and self.evidence_count >= 10:
            self.belief_type = BeliefType.DEPRECATED
        elif self.confidence > 0.8 and self.evidence_count >= 20:
            if self.belief_type == BeliefType.HYPOTHESIS:
                self.belief_type = BeliefType.VERIFIED

        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.belief_type.value,
            "confidence": self.confidence,
            "evidence": self.evidence_count,
            "supporting": self.supporting_evidence,
            "contradicting": self.contradicting_evidence,
        }


# =============================================================================
# Observation Tracking
# =============================================================================

@dataclass
class UtilityObservation:
    """A recorded utility observation for self-evaluation."""
    id: str
    timestamp: str
    observables: Observables
    state: StateRegister
    utility: float
    utility_audit: UtilityAudit

    # Context for analysis
    guna_dominant: str  # "sattva", "rajas", or "tamas"
    motion_level: str   # "low", "medium", "high"
    entropy_level: str  # "low", "medium", "high"
    contradiction_level: str  # "low", "medium", "high"


class SelfEvaluator:
    """
    Tracks utility outcomes and identifies patterns of failure.

    Uses the existing Observables and Utility infrastructure
    to measure and categorize system performance.
    """

    def __init__(self, history_size: int = 500):
        self.observations: deque = deque(maxlen=history_size)

        # Performance by context
        self.utility_by_guna_dominant: Dict[str, List[float]] = {
            "sattva": [], "rajas": [], "tamas": []
        }
        self.utility_by_motion: Dict[str, List[float]] = {
            "low": [], "medium": [], "high": []
        }
        self.utility_by_entropy: Dict[str, List[float]] = {
            "low": [], "medium": [], "high": []
        }

        # Trend tracking
        self.recent_utilities: deque = deque(maxlen=50)
        self.low_utility_streak: int = 0
        self.max_low_utility_streak: int = 0

    def record_observation(
        self,
        observables: Observables,
        state: StateRegister,
        utility: float,
        utility_audit: UtilityAudit,
    ) -> UtilityObservation:
        """Record a utility observation for analysis."""
        # Categorize the observation
        guna_dominant = self._get_guna_dominant(observables)
        motion_level = self._categorize_level(observables.M)
        entropy_level = self._categorize_level(observables.H)
        contradiction_level = self._categorize_level(observables.C_contr)

        obs = UtilityObservation(
            id=f"obs_{len(self.observations)}_{datetime.now().timestamp()}",
            timestamp=datetime.now().isoformat(),
            observables=observables,
            state=state,
            utility=utility,
            utility_audit=utility_audit,
            guna_dominant=guna_dominant,
            motion_level=motion_level,
            entropy_level=entropy_level,
            contradiction_level=contradiction_level,
        )

        self.observations.append(obs)
        self.recent_utilities.append(utility)

        # Track by context
        self.utility_by_guna_dominant[guna_dominant].append(utility)
        self.utility_by_motion[motion_level].append(utility)
        self.utility_by_entropy[entropy_level].append(utility)

        # Limit context lists
        for d in [self.utility_by_guna_dominant, self.utility_by_motion, self.utility_by_entropy]:
            for k in d:
                if len(d[k]) > 200:
                    d[k] = d[k][-100:]

        # Track streaks
        if utility < 0.3:
            self.low_utility_streak += 1
            self.max_low_utility_streak = max(
                self.max_low_utility_streak,
                self.low_utility_streak
            )
        else:
            self.low_utility_streak = 0

        return obs

    def _get_guna_dominant(self, obs: Observables) -> str:
        """Get dominant Guna from observables."""
        if obs.s >= obs.r and obs.s >= obs.t:
            return "sattva"
        elif obs.r >= obs.s and obs.r >= obs.t:
            return "rajas"
        else:
            return "tamas"

    def _categorize_level(self, value: float) -> str:
        """Categorize a [0,1] value into low/medium/high."""
        if value < 0.33:
            return "low"
        elif value < 0.67:
            return "medium"
        return "high"

    def get_average_utility(self) -> float:
        """Get overall average utility."""
        if not self.recent_utilities:
            return 0.5
        return sum(self.recent_utilities) / len(self.recent_utilities)

    def get_utility_by_context(self) -> Dict[str, Dict[str, float]]:
        """Get average utility by context."""
        def avg(lst):
            return sum(lst) / len(lst) if lst else 0.5

        return {
            "by_guna": {k: avg(v) for k, v in self.utility_by_guna_dominant.items()},
            "by_motion": {k: avg(v) for k, v in self.utility_by_motion.items()},
            "by_entropy": {k: avg(v) for k, v in self.utility_by_entropy.items()},
        }

    def identify_failure_patterns(self) -> List[Dict[str, Any]]:
        """Identify patterns where utility is consistently low."""
        patterns = []
        avg_utility = self.get_average_utility()

        # Check Guna-specific failures
        for guna, utilities in self.utility_by_guna_dominant.items():
            if len(utilities) >= 10:
                guna_avg = sum(utilities) / len(utilities)
                if guna_avg < avg_utility - 0.1:
                    patterns.append({
                        "type": "guna_failure",
                        "guna": guna,
                        "average_utility": guna_avg,
                        "overall_average": avg_utility,
                        "description": f"Low utility when {guna} dominant",
                    })

        # Check motion-specific failures
        for level, utilities in self.utility_by_motion.items():
            if len(utilities) >= 10:
                level_avg = sum(utilities) / len(utilities)
                if level_avg < avg_utility - 0.1:
                    patterns.append({
                        "type": "motion_failure",
                        "motion_level": level,
                        "average_utility": level_avg,
                        "overall_average": avg_utility,
                        "description": f"Low utility during {level} motion",
                    })

        # Check entropy-specific failures
        for level, utilities in self.utility_by_entropy.items():
            if len(utilities) >= 10:
                level_avg = sum(utilities) / len(utilities)
                if level_avg < avg_utility - 0.1:
                    patterns.append({
                        "type": "entropy_failure",
                        "entropy_level": level,
                        "average_utility": level_avg,
                        "overall_average": avg_utility,
                        "description": f"Low utility during {level} entropy",
                    })

        return patterns

    def get_summary(self) -> Dict[str, Any]:
        """Get evaluation summary."""
        return {
            "total_observations": len(self.observations),
            "average_utility": self.get_average_utility(),
            "utility_by_context": self.get_utility_by_context(),
            "low_utility_streak": self.low_utility_streak,
            "max_low_utility_streak": self.max_low_utility_streak,
            "failure_patterns": self.identify_failure_patterns(),
        }


# =============================================================================
# Knowledge Base
# =============================================================================

class EnterpriseKnowledgeBase:
    """
    Self-modifiable knowledge base for enterprise self-improvement.

    Stores beliefs about:
    - Optimal coefficient settings
    - Context-specific strategies
    - Failure conditions to avoid
    """

    def __init__(self):
        self.beliefs: Dict[str, Belief] = {}
        self.coefficient_adjustments: Dict[str, float] = {}
        self._initialize_prior_beliefs()

    def _initialize_prior_beliefs(self):
        """Initialize with prior beliefs from system design."""
        priors = [
            ("sattva_positive", "High Sattva leads to high utility", 0.7),
            ("rajas_moderate", "Moderate Rajas is optimal", 0.6),
            ("tamas_caution", "High Tamas requires careful handling", 0.7),
            ("low_entropy_stable", "Low entropy indicates stable state", 0.8),
            ("high_motion_opportunity", "High motion signals transformation opportunity", 0.6),
            ("contradiction_penalize", "High contradiction should penalize utility", 0.8),
            ("failure_penalize", "High failure should penalize utility", 0.9),
            ("coefficients_balanced", "Default coefficients are well-balanced", 0.6),
        ]

        for belief_id, content, confidence in priors:
            self.beliefs[belief_id] = Belief(
                id=belief_id,
                content=content,
                belief_type=BeliefType.PRIOR,
                confidence=confidence,
            )

    def add_belief(self, belief: Belief) -> None:
        """Add a new belief."""
        self.beliefs[belief.id] = belief

    def update_belief_with_utility(
        self,
        belief_id: str,
        utility: float,
        threshold: float = 0.5,
    ) -> Optional[Belief]:
        """Update a belief based on utility observation."""
        if belief_id not in self.beliefs:
            return None
        return self.beliefs[belief_id].update_with_utility(utility, threshold)

    def get_active_beliefs(self) -> List[Belief]:
        """Get non-deprecated beliefs."""
        return [
            b for b in self.beliefs.values()
            if b.belief_type != BeliefType.DEPRECATED
        ]

    def get_coefficient_adjustment(self, coef_name: str) -> float:
        """Get learned adjustment for a coefficient."""
        return self.coefficient_adjustments.get(coef_name, 1.0)

    def set_coefficient_adjustment(self, coef_name: str, adjustment: float) -> None:
        """Set a coefficient adjustment (multiplier)."""
        # Bound adjustments to prevent extreme values
        self.coefficient_adjustments[coef_name] = max(0.5, min(2.0, adjustment))

    def export_state(self) -> Dict[str, Any]:
        """Export knowledge base state."""
        return {
            "beliefs": {k: v.to_dict() for k, v in self.beliefs.items()},
            "coefficient_adjustments": self.coefficient_adjustments,
            "active_count": len(self.get_active_beliefs()),
        }


# =============================================================================
# Meta-Reasoner
# =============================================================================

class MetaReasoner:
    """
    Reasons about system performance and generates improvement hypotheses.

    Uses failure patterns from SelfEvaluator to propose
    coefficient adjustments and strategy changes.
    """

    def __init__(self, kb: EnterpriseKnowledgeBase, evaluator: SelfEvaluator):
        self.kb = kb
        self.evaluator = evaluator
        self.hypotheses: List[Belief] = []

    def analyze_and_generate_hypotheses(self) -> List[Belief]:
        """Generate improvement hypotheses based on failure analysis."""
        hypotheses = []
        patterns = self.evaluator.identify_failure_patterns()
        summary = self.evaluator.get_summary()

        for pattern in patterns:
            hypothesis = self._hypothesis_from_pattern(pattern)
            if hypothesis:
                hypotheses.append(hypothesis)

        # Check for overall low utility
        if summary["average_utility"] < 0.4:
            hypotheses.append(Belief(
                id=f"hyp_low_overall_{datetime.now().timestamp()}",
                content="Overall utility is low; coefficients may need rebalancing",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.6,
                metadata={
                    "average_utility": summary["average_utility"],
                    "action": "rebalance_coefficients",
                }
            ))

        # Check for streak
        if summary["max_low_utility_streak"] >= 5:
            hypotheses.append(Belief(
                id=f"hyp_streak_{datetime.now().timestamp()}",
                content="Experienced utility streak failure; may need conservative mode",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.5,
                metadata={
                    "streak": summary["max_low_utility_streak"],
                    "action": "enable_conservative_mode",
                }
            ))

        self.hypotheses = hypotheses
        return hypotheses

    def _hypothesis_from_pattern(self, pattern: Dict[str, Any]) -> Optional[Belief]:
        """Generate a hypothesis from a failure pattern."""
        pattern_type = pattern.get("type")

        if pattern_type == "guna_failure":
            guna = pattern.get("guna")
            return Belief(
                id=f"hyp_guna_{guna}_{datetime.now().timestamp()}",
                content=f"Utility low when {guna} dominant; adjust {guna} coefficient",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.5,
                metadata={
                    "pattern": pattern,
                    "action": f"adjust_{guna}_coefficient",
                }
            )

        elif pattern_type == "motion_failure":
            level = pattern.get("motion_level")
            return Belief(
                id=f"hyp_motion_{level}_{datetime.now().timestamp()}",
                content=f"Utility low during {level} motion; adjust motion handling",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.5,
                metadata={
                    "pattern": pattern,
                    "action": f"adjust_motion_{level}",
                }
            )

        elif pattern_type == "entropy_failure":
            level = pattern.get("entropy_level")
            return Belief(
                id=f"hyp_entropy_{level}_{datetime.now().timestamp()}",
                content=f"Utility low during {level} entropy; adjust entropy penalty",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.5,
                metadata={
                    "pattern": pattern,
                    "action": "adjust_lambda_H",
                }
            )

        return None

    def prioritize_hypotheses(self) -> List[Tuple[Belief, float]]:
        """Prioritize hypotheses by expected improvement value."""
        prioritized = []

        for hyp in self.hypotheses:
            # Priority based on confidence and pattern severity
            pattern = hyp.metadata.get("pattern", {})
            severity = abs(
                pattern.get("average_utility", 0.5) -
                pattern.get("overall_average", 0.5)
            )
            priority = hyp.confidence * (1 + severity)
            prioritized.append((hyp, priority))

        prioritized.sort(key=lambda x: x[1], reverse=True)
        return prioritized


# =============================================================================
# Self-Improving Engine
# =============================================================================

@dataclass
class ImprovementAction:
    """A self-improvement action."""
    id: str
    timestamp: str
    description: str
    action_type: str
    before_value: Any
    after_value: Any
    triggered_by: str
    reverted: bool = False


class EnterpriseSelfImprover:
    """
    Orchestrates recursive self-improvement using existing signals.

    Integrates with:
    - Observables (signal source)
    - Utility computation (evaluation)
    - Knowledge Base (beliefs)
    - State Evolution (learning)
    """

    def __init__(
        self,
        config: Optional[V27Config] = None,
        auto_improve: bool = False,
        improvement_threshold: float = 0.6,
    ):
        self.config = config
        self.kb = EnterpriseKnowledgeBase()
        self.evaluator = SelfEvaluator()
        self.reasoner = MetaReasoner(self.kb, self.evaluator)

        self.auto_improve = auto_improve
        self.improvement_threshold = improvement_threshold

        # Learned adjustments
        self.coefficient_overrides: Optional[UtilityCoefficients] = None
        self.conservative_mode: bool = False

        # Tracking
        self.executed_improvements: List[ImprovementAction] = []
        self.observation_count: int = 0
        self.improvement_cycle_count: int = 0

        # Callbacks
        self.on_improvement: Optional[Callable[[ImprovementAction], None]] = None

    def observe(
        self,
        observables: Observables,
        state: StateRegister,
        coefficients: Optional[UtilityCoefficients] = None,
    ) -> Tuple[float, UtilityAudit]:
        """
        Observe an evaluation and track for self-improvement.

        This wraps the normal utility computation and adds tracking.
        """
        # Use overridden coefficients if available
        effective_coefficients = self.coefficient_overrides or coefficients or DEFAULT_UTILITY_COEFFICIENTS

        # Apply conservative mode if enabled
        if self.conservative_mode:
            effective_coefficients = self._apply_conservative_mode(effective_coefficients)

        # Compute utility
        utility, audit = compute_utility(observables, state, effective_coefficients)

        # Record observation
        self.evaluator.record_observation(observables, state, utility, audit)
        self.observation_count += 1

        # Update beliefs based on utility
        self._update_beliefs_from_observation(observables, utility)

        # Check if improvement cycle should run
        if self.auto_improve and self._should_run_improvement():
            self.run_improvement_cycle()

        return utility, audit

    def _update_beliefs_from_observation(
        self,
        observables: Observables,
        utility: float,
    ) -> None:
        """Update relevant beliefs based on the observation."""
        # Update Guna-specific beliefs
        if observables.s > 0.5:
            self.kb.update_belief_with_utility("sattva_positive", utility)
        if observables.r > 0.5:
            self.kb.update_belief_with_utility("rajas_moderate", utility)
        if observables.t > 0.5:
            self.kb.update_belief_with_utility("tamas_caution", utility)

        # Update entropy belief
        if observables.H < 0.3:
            self.kb.update_belief_with_utility("low_entropy_stable", utility)

        # Update motion belief
        if observables.M > 0.5:
            self.kb.update_belief_with_utility("high_motion_opportunity", utility)

    def _should_run_improvement(self) -> bool:
        """Check if improvement cycle should run."""
        # Run every 100 observations
        if self.observation_count > 0 and self.observation_count % 100 == 0:
            return True

        # Run if utility streak is bad
        if self.evaluator.low_utility_streak >= 5:
            return True

        return False

    def run_improvement_cycle(self) -> List[ImprovementAction]:
        """Execute one improvement cycle."""
        self.improvement_cycle_count += 1

        # Generate hypotheses
        hypotheses = self.reasoner.analyze_and_generate_hypotheses()
        if not hypotheses:
            return []

        # Prioritize
        prioritized = self.reasoner.prioritize_hypotheses()

        executed = []

        for hypothesis, priority in prioritized:
            if priority >= self.improvement_threshold:
                action = self._execute_improvement(hypothesis)
                if action:
                    executed.append(action)
                    if self.on_improvement:
                        self.on_improvement(action)

        return executed

    def _execute_improvement(self, hypothesis: Belief) -> Optional[ImprovementAction]:
        """Execute an improvement based on a hypothesis."""
        action_type = hypothesis.metadata.get("action", "")

        if action_type.startswith("adjust_") and "coefficient" in action_type:
            return self._adjust_guna_coefficient(hypothesis)
        elif action_type == "adjust_lambda_H":
            return self._adjust_entropy_penalty(hypothesis)
        elif action_type == "enable_conservative_mode":
            return self._enable_conservative_mode(hypothesis)
        elif action_type == "rebalance_coefficients":
            return self._rebalance_coefficients(hypothesis)

        return None

    def _adjust_guna_coefficient(self, hypothesis: Belief) -> ImprovementAction:
        """Adjust a Guna coefficient based on failure pattern."""
        pattern = hypothesis.metadata.get("pattern", {})
        guna = pattern.get("guna", "sattva")

        # Get current coefficient
        current = self.coefficient_overrides or DEFAULT_UTILITY_COEFFICIENTS
        coef_name = f"c_{guna[0].upper()}"  # c_S, c_R, or c_T

        current_value = getattr(current, coef_name, 1.0)

        # Adjust (reduce if utility was low)
        new_value = current_value * 0.9

        # Create new coefficients
        new_coefficients = UtilityCoefficients(
            c_S=new_value if guna == "sattva" else current.c_S,
            c_R=new_value if guna == "rajas" else current.c_R,
            c_T=new_value if guna == "tamas" else current.c_T,
            lambda_H=current.lambda_H,
            lambda_C=current.lambda_C,
            lambda_F=current.lambda_F,
        )

        self.coefficient_overrides = new_coefficients
        self.kb.add_belief(hypothesis)

        action = ImprovementAction(
            id=f"imp_{len(self.executed_improvements)}",
            timestamp=datetime.now().isoformat(),
            description=f"Adjusted {coef_name} from {current_value:.2f} to {new_value:.2f}",
            action_type="coefficient_adjustment",
            before_value=current_value,
            after_value=new_value,
            triggered_by=hypothesis.id,
        )
        self.executed_improvements.append(action)
        return action

    def _adjust_entropy_penalty(self, hypothesis: Belief) -> ImprovementAction:
        """Adjust entropy penalty based on failure pattern."""
        current = self.coefficient_overrides or DEFAULT_UTILITY_COEFFICIENTS

        # Increase penalty if high entropy causes problems (clamped to [-1, 1])
        new_lambda_H = max(-1.0, min(1.0, current.lambda_H * 1.1))

        new_coefficients = UtilityCoefficients(
            c_S=current.c_S,
            c_R=current.c_R,
            c_T=current.c_T,
            lambda_H=new_lambda_H,
            lambda_C=current.lambda_C,
            lambda_F=current.lambda_F,
        )

        self.coefficient_overrides = new_coefficients
        self.kb.add_belief(hypothesis)

        action = ImprovementAction(
            id=f"imp_{len(self.executed_improvements)}",
            timestamp=datetime.now().isoformat(),
            description=f"Adjusted λ_H from {current.lambda_H:.2f} to {new_lambda_H:.2f}",
            action_type="coefficient_adjustment",
            before_value=current.lambda_H,
            after_value=new_lambda_H,
            triggered_by=hypothesis.id,
        )
        self.executed_improvements.append(action)
        return action

    def _enable_conservative_mode(self, hypothesis: Belief) -> ImprovementAction:
        """Enable conservative mode after utility streak failure."""
        before = self.conservative_mode
        self.conservative_mode = True
        self.kb.add_belief(hypothesis)

        action = ImprovementAction(
            id=f"imp_{len(self.executed_improvements)}",
            timestamp=datetime.now().isoformat(),
            description="Enabled conservative mode due to utility streak failure",
            action_type="mode_change",
            before_value=before,
            after_value=True,
            triggered_by=hypothesis.id,
        )
        self.executed_improvements.append(action)
        return action

    def _rebalance_coefficients(self, hypothesis: Belief) -> ImprovementAction:
        """Rebalance all coefficients toward defaults."""
        current = self.coefficient_overrides or DEFAULT_UTILITY_COEFFICIENTS
        default = DEFAULT_UTILITY_COEFFICIENTS

        # Move 20% toward defaults
        blend = 0.2
        new_coefficients = UtilityCoefficients(
            c_S=current.c_S * (1 - blend) + default.c_S * blend,
            c_R=current.c_R * (1 - blend) + default.c_R * blend,
            c_T=current.c_T * (1 - blend) + default.c_T * blend,
            lambda_H=current.lambda_H * (1 - blend) + default.lambda_H * blend,
            lambda_C=current.lambda_C * (1 - blend) + default.lambda_C * blend,
            lambda_F=current.lambda_F * (1 - blend) + default.lambda_F * blend,
        )

        self.coefficient_overrides = new_coefficients
        self.kb.add_belief(hypothesis)

        action = ImprovementAction(
            id=f"imp_{len(self.executed_improvements)}",
            timestamp=datetime.now().isoformat(),
            description="Rebalanced coefficients 20% toward defaults",
            action_type="coefficient_rebalance",
            before_value=str(current),
            after_value=str(new_coefficients),
            triggered_by=hypothesis.id,
        )
        self.executed_improvements.append(action)
        return action

    def _apply_conservative_mode(
        self,
        coefficients: UtilityCoefficients,
    ) -> UtilityCoefficients:
        """Apply conservative adjustments to coefficients."""
        # Clamp values to valid range [-1, 1]
        def clamp(val: float) -> float:
            return max(-1.0, min(1.0, val))

        return UtilityCoefficients(
            c_S=clamp(coefficients.c_S),
            c_R=clamp(coefficients.c_R * 0.8),  # Reduce Rajas influence
            c_T=clamp(coefficients.c_T * 0.8),  # Reduce Tamas influence
            lambda_H=clamp(coefficients.lambda_H * 1.2),  # Slight increase, clamped
            lambda_C=clamp(coefficients.lambda_C * 1.2),  # Slight increase, clamped
            lambda_F=clamp(coefficients.lambda_F * 1.2),  # Slight increase, clamped
        )

    def get_effective_coefficients(self) -> UtilityCoefficients:
        """Get the currently effective utility coefficients."""
        base = self.coefficient_overrides or DEFAULT_UTILITY_COEFFICIENTS
        if self.conservative_mode:
            return self._apply_conservative_mode(base)
        return base

    def get_reasoning_trace(self) -> List[Dict[str, Any]]:
        """Get reasoning trace showing self-improvement logic."""
        trace = []

        # Evaluation summary
        summary = self.evaluator.get_summary()
        trace.append({
            "step": "evaluation",
            "average_utility": summary["average_utility"],
            "observations": summary["total_observations"],
        })

        # Failure patterns
        for pattern in summary["failure_patterns"]:
            trace.append({
                "step": "pattern_detected",
                "type": pattern["type"],
                "description": pattern["description"],
            })

        # Hypotheses
        for hyp in self.reasoner.hypotheses:
            trace.append({
                "step": "hypothesis",
                "content": hyp.content,
                "confidence": hyp.confidence,
            })

        # Improvements
        for imp in self.executed_improvements[-5:]:
            trace.append({
                "step": "improvement",
                "description": imp.description,
                "action_type": imp.action_type,
            })

        return trace

    def get_state_summary(self) -> Dict[str, Any]:
        """Get comprehensive state summary."""
        return {
            "observation_count": self.observation_count,
            "improvement_cycles": self.improvement_cycle_count,
            "improvements_executed": len(self.executed_improvements),
            "conservative_mode": self.conservative_mode,
            "active_beliefs": len(self.kb.get_active_beliefs()),
            "evaluation": self.evaluator.get_summary(),
            "effective_coefficients": str(self.get_effective_coefficients()),
        }

    def export_learned_state(self) -> Dict[str, Any]:
        """Export learned state for persistence."""
        return {
            "knowledge_base": self.kb.export_state(),
            "coefficient_overrides": str(self.coefficient_overrides) if self.coefficient_overrides else None,
            "conservative_mode": self.conservative_mode,
            "improvements": [
                {
                    "id": imp.id,
                    "description": imp.description,
                    "action_type": imp.action_type,
                }
                for imp in self.executed_improvements
            ],
        }


# =============================================================================
# Factory
# =============================================================================

def create_enterprise_self_improver(
    config: Optional[V27Config] = None,
    auto_improve: bool = True,
    improvement_threshold: float = 0.6,
) -> EnterpriseSelfImprover:
    """
    Create an enterprise self-improvement system.

    Args:
        config: V27 configuration (optional)
        auto_improve: Enable automatic self-improvement
        improvement_threshold: Minimum priority to execute improvements

    Returns:
        Configured EnterpriseSelfImprover
    """
    return EnterpriseSelfImprover(
        config=config,
        auto_improve=auto_improve,
        improvement_threshold=improvement_threshold,
    )
