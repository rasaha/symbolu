"""
Recursive Self-Improvement Module

Experimental AGI-like capability for the Bayesian trading system.

Core Concept:
The system observes its own performance, reasons about its failures,
and modifies its own knowledge base to improve future decisions.

Architecture:
1. SelfEvaluator - Tracks predictions vs outcomes, identifies errors
2. KnowledgeBase - Stores beliefs, rules, hypotheses (self-modifiable)
3. MetaReasoner - Analyzes patterns, generates improvement hypotheses
4. SelfImprover - Orchestrates the self-improvement loop

This is inspired by:
- Schmidhuber's Gödel Machine (self-modifying code with proofs)
- Bayesian Program Learning (learning to learn)
- Meta-learning (learning about learning dynamics)

Key Safety: All modifications are logged and reversible.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Callable
from collections import deque
from enum import Enum
import math
import json
from datetime import datetime


class BeliefType(Enum):
    """Types of beliefs in the knowledge base."""
    PRIOR = "prior"           # Initial assumptions
    LEARNED = "learned"       # Learned from data
    HYPOTHESIS = "hypothesis" # Proposed but unverified
    VERIFIED = "verified"     # Tested and confirmed
    DEPRECATED = "deprecated" # Previously held, now rejected


class ImprovementType(Enum):
    """Types of self-improvement actions."""
    WEIGHT_ADJUSTMENT = "weight_adjustment"
    THRESHOLD_CHANGE = "threshold_change"
    RULE_ADDITION = "rule_addition"
    RULE_REMOVAL = "rule_removal"
    BELIEF_UPDATE = "belief_update"
    STRATEGY_SWITCH = "strategy_switch"


@dataclass
class Belief:
    """
    A single belief in the knowledge base.

    Beliefs are probability-weighted assertions about the world
    that can be updated based on evidence.
    """
    id: str
    content: str  # Human-readable description
    belief_type: BeliefType
    confidence: float  # P(belief is true) in [0, 1]
    evidence_count: int = 0  # Number of observations
    supporting_evidence: int = 0  # Confirmations
    contradicting_evidence: int = 0  # Contradictions
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    parent_belief_id: Optional[str] = None  # For belief evolution tracking
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_with_evidence(self, supports: bool, weight: float = 1.0) -> "Belief":
        """Bayesian update of belief confidence based on evidence."""
        self.evidence_count += 1
        if supports:
            self.supporting_evidence += 1
        else:
            self.contradicting_evidence += 1

        # Bayesian update using Beta distribution
        # Prior: Beta(α, β) where α = supporting + 1, β = contradicting + 1
        alpha = self.supporting_evidence + 1
        beta = self.contradicting_evidence + 1

        # Posterior mean
        self.confidence = alpha / (alpha + beta)
        self.last_updated = datetime.now().isoformat()

        return self

    def should_deprecate(self, threshold: float = 0.2) -> bool:
        """Check if belief should be deprecated due to low confidence."""
        return (
            self.evidence_count >= 10 and  # Enough evidence
            self.confidence < threshold
        )

    def should_verify(self, threshold: float = 0.8, min_evidence: int = 20) -> bool:
        """Check if hypothesis should be promoted to verified."""
        return (
            self.belief_type == BeliefType.HYPOTHESIS and
            self.evidence_count >= min_evidence and
            self.confidence >= threshold
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.belief_type.value,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "supporting": self.supporting_evidence,
            "contradicting": self.contradicting_evidence,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "parent_id": self.parent_belief_id,
            "metadata": self.metadata,
        }


@dataclass
class Prediction:
    """A prediction made by the system for evaluation."""
    id: str
    timestamp: str
    signal: float  # Predicted signal strength [-1, 1]
    direction: str  # "buy", "sell", "neutral"
    confidence: float  # Model's confidence
    context: Dict[str, Any]  # Market context at prediction time
    outcome: Optional[float] = None  # Actual outcome (filled later)
    was_correct: Optional[bool] = None
    error_magnitude: Optional[float] = None


@dataclass
class ImprovementAction:
    """A self-improvement action taken by the system."""
    id: str
    timestamp: str
    action_type: ImprovementType
    description: str
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    reasoning: str  # Why this improvement was made
    triggered_by: List[str]  # IDs of beliefs/observations that triggered this
    success_metric: Optional[float] = None  # Measured after implementation
    reverted: bool = False


class KnowledgeBase:
    """
    Self-modifiable knowledge base.

    Stores beliefs about:
    - Market behavior patterns
    - Model performance characteristics
    - Optimal parameter ranges
    - Failure modes and their conditions

    Key feature: The system can add, modify, and remove its own beliefs.
    """

    def __init__(self):
        self.beliefs: Dict[str, Belief] = {}
        self.belief_history: List[Tuple[str, Belief]] = []  # For rollback
        self._initialize_prior_beliefs()

    def _initialize_prior_beliefs(self):
        """Initialize with foundational beliefs."""
        priors = [
            ("trending_momentum", "Momentum strategies work better in trending markets", 0.7),
            ("ranging_reversion", "Mean reversion works better in ranging markets", 0.7),
            ("high_vol_caution", "High volatility requires smaller position sizes", 0.8),
            ("wave3_strongest", "Elliott Wave 3 is typically the strongest move", 0.75),
            ("adx_trend_indicator", "ADX > 25 indicates a strong trend", 0.8),
            ("bayesian_uncertainty", "High uncertainty should reduce position size", 0.85),
            ("regime_persistence", "Market regimes tend to persist", 0.6),
            ("indicator_confluence", "Multiple indicator agreement increases reliability", 0.75),
        ]

        for belief_id, content, confidence in priors:
            self.beliefs[belief_id] = Belief(
                id=belief_id,
                content=content,
                belief_type=BeliefType.PRIOR,
                confidence=confidence,
                metadata={"source": "initialization"}
            )

    def add_belief(self, belief: Belief) -> None:
        """Add a new belief to the knowledge base."""
        self.belief_history.append(("add", belief))
        self.beliefs[belief.id] = belief

    def update_belief(self, belief_id: str, supports: bool, weight: float = 1.0) -> Optional[Belief]:
        """Update a belief with new evidence."""
        if belief_id not in self.beliefs:
            return None

        belief = self.beliefs[belief_id]
        old_belief = Belief(**belief.__dict__)  # Copy for history
        self.belief_history.append(("update", old_belief))

        belief.update_with_evidence(supports, weight)

        # Check for state transitions
        if belief.should_deprecate():
            belief.belief_type = BeliefType.DEPRECATED
        elif belief.should_verify():
            belief.belief_type = BeliefType.VERIFIED

        return belief

    def deprecate_belief(self, belief_id: str, reason: str) -> Optional[Belief]:
        """Mark a belief as deprecated."""
        if belief_id not in self.beliefs:
            return None

        belief = self.beliefs[belief_id]
        old_belief = Belief(**belief.__dict__)
        self.belief_history.append(("deprecate", old_belief))

        belief.belief_type = BeliefType.DEPRECATED
        belief.metadata["deprecation_reason"] = reason
        belief.last_updated = datetime.now().isoformat()

        return belief

    def get_active_beliefs(self) -> List[Belief]:
        """Get all non-deprecated beliefs."""
        return [
            b for b in self.beliefs.values()
            if b.belief_type != BeliefType.DEPRECATED
        ]

    def get_beliefs_by_type(self, belief_type: BeliefType) -> List[Belief]:
        """Get beliefs of a specific type."""
        return [b for b in self.beliefs.values() if b.belief_type == belief_type]

    def get_high_confidence_beliefs(self, threshold: float = 0.7) -> List[Belief]:
        """Get beliefs with confidence above threshold."""
        return [
            b for b in self.get_active_beliefs()
            if b.confidence >= threshold
        ]

    def rollback_last_change(self) -> bool:
        """Rollback the last change to the knowledge base."""
        if not self.belief_history:
            return False

        action, old_belief = self.belief_history.pop()

        if action == "add":
            del self.beliefs[old_belief.id]
        elif action in ("update", "deprecate"):
            self.beliefs[old_belief.id] = old_belief

        return True

    def export_state(self) -> Dict[str, Any]:
        """Export current knowledge base state."""
        return {
            "beliefs": {k: v.to_dict() for k, v in self.beliefs.items()},
            "history_length": len(self.belief_history),
            "active_count": len(self.get_active_beliefs()),
            "deprecated_count": len(self.get_beliefs_by_type(BeliefType.DEPRECATED)),
        }


class SelfEvaluator:
    """
    Evaluates the system's own predictions and identifies patterns of failure.

    Tracks:
    - Prediction accuracy over time
    - Accuracy by market regime
    - Accuracy by confidence level
    - Systematic biases (e.g., over-bullish)
    """

    def __init__(self, history_size: int = 1000):
        self.predictions: deque = deque(maxlen=history_size)
        self.completed_predictions: deque = deque(maxlen=history_size)

        # Performance metrics by context
        self.accuracy_by_regime: Dict[str, List[bool]] = {}
        self.accuracy_by_confidence: Dict[str, List[bool]] = {}  # "low", "medium", "high"
        self.accuracy_by_direction: Dict[str, List[bool]] = {}

        # Bias tracking
        self.bullish_predictions = 0
        self.bearish_predictions = 0
        self.bullish_correct = 0
        self.bearish_correct = 0

        # Error patterns
        self.consecutive_errors = 0
        self.max_consecutive_errors = 0
        self.error_contexts: List[Dict[str, Any]] = []

    def record_prediction(
        self,
        signal: float,
        direction: str,
        confidence: float,
        context: Dict[str, Any],
    ) -> str:
        """Record a new prediction."""
        pred_id = f"pred_{len(self.predictions)}_{datetime.now().timestamp()}"

        prediction = Prediction(
            id=pred_id,
            timestamp=datetime.now().isoformat(),
            signal=signal,
            direction=direction,
            confidence=confidence,
            context=context,
        )

        self.predictions.append(prediction)

        # Track direction bias
        if direction == "buy":
            self.bullish_predictions += 1
        elif direction == "sell":
            self.bearish_predictions += 1

        return pred_id

    def record_outcome(
        self,
        prediction_id: str,
        actual_outcome: float,
        price_change_percent: float,
    ) -> Optional[Prediction]:
        """Record the outcome of a prediction."""
        # Find prediction
        prediction = None
        for pred in self.predictions:
            if pred.id == prediction_id:
                prediction = pred
                break

        if not prediction:
            return None

        # Calculate if correct
        prediction.outcome = actual_outcome

        if prediction.direction == "buy":
            prediction.was_correct = price_change_percent > 0
        elif prediction.direction == "sell":
            prediction.was_correct = price_change_percent < 0
        else:
            prediction.was_correct = abs(price_change_percent) < 0.5  # Neutral correct if small move

        prediction.error_magnitude = abs(prediction.signal - actual_outcome)

        # Update tracking
        self._update_accuracy_tracking(prediction)
        self.completed_predictions.append(prediction)

        return prediction

    def _update_accuracy_tracking(self, prediction: Prediction) -> None:
        """Update accuracy tracking structures."""
        regime = prediction.context.get("regime", "unknown")
        confidence_bucket = self._confidence_bucket(prediction.confidence)

        # By regime
        if regime not in self.accuracy_by_regime:
            self.accuracy_by_regime[regime] = []
        self.accuracy_by_regime[regime].append(prediction.was_correct)

        # By confidence
        if confidence_bucket not in self.accuracy_by_confidence:
            self.accuracy_by_confidence[confidence_bucket] = []
        self.accuracy_by_confidence[confidence_bucket].append(prediction.was_correct)

        # By direction
        if prediction.direction not in self.accuracy_by_direction:
            self.accuracy_by_direction[prediction.direction] = []
        self.accuracy_by_direction[prediction.direction].append(prediction.was_correct)

        # Bias tracking
        if prediction.direction == "buy" and prediction.was_correct:
            self.bullish_correct += 1
        elif prediction.direction == "sell" and prediction.was_correct:
            self.bearish_correct += 1

        # Error tracking
        if not prediction.was_correct:
            self.consecutive_errors += 1
            self.max_consecutive_errors = max(self.max_consecutive_errors, self.consecutive_errors)
            self.error_contexts.append(prediction.context)
            if len(self.error_contexts) > 100:
                self.error_contexts.pop(0)
        else:
            self.consecutive_errors = 0

    def _confidence_bucket(self, confidence: float) -> str:
        if confidence < 0.4:
            return "low"
        elif confidence < 0.7:
            return "medium"
        return "high"

    def get_overall_accuracy(self) -> float:
        """Get overall prediction accuracy."""
        if not self.completed_predictions:
            return 0.5  # Prior

        correct = sum(1 for p in self.completed_predictions if p.was_correct)
        return correct / len(self.completed_predictions)

    def get_accuracy_by_regime(self) -> Dict[str, float]:
        """Get accuracy breakdown by regime."""
        result = {}
        for regime, outcomes in self.accuracy_by_regime.items():
            if outcomes:
                result[regime] = sum(outcomes) / len(outcomes)
        return result

    def get_directional_bias(self) -> Dict[str, float]:
        """Detect directional bias in predictions."""
        total = self.bullish_predictions + self.bearish_predictions
        if total == 0:
            return {"bullish_ratio": 0.5, "bullish_accuracy": 0.5, "bearish_accuracy": 0.5}

        return {
            "bullish_ratio": self.bullish_predictions / total,
            "bullish_accuracy": self.bullish_correct / max(1, self.bullish_predictions),
            "bearish_accuracy": self.bearish_correct / max(1, self.bearish_predictions),
        }

    def identify_failure_patterns(self) -> List[Dict[str, Any]]:
        """Analyze error contexts to identify failure patterns."""
        if len(self.error_contexts) < 5:
            return []

        patterns = []

        # Check for regime-specific failures
        regime_counts = {}
        for ctx in self.error_contexts:
            regime = ctx.get("regime", "unknown")
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        total_errors = len(self.error_contexts)
        for regime, count in regime_counts.items():
            if count / total_errors > 0.4:  # 40%+ errors in one regime
                patterns.append({
                    "type": "regime_failure",
                    "regime": regime,
                    "error_proportion": count / total_errors,
                    "description": f"High error rate in {regime} regime",
                })

        # Check for high volatility failures
        high_vol_errors = sum(
            1 for ctx in self.error_contexts
            if ctx.get("volatility_ratio", 1.0) > 1.5
        )
        if high_vol_errors / total_errors > 0.5:
            patterns.append({
                "type": "volatility_failure",
                "error_proportion": high_vol_errors / total_errors,
                "description": "Errors concentrated in high volatility periods",
            })

        # Check for confidence miscalibration
        by_conf = self.accuracy_by_confidence
        if "high" in by_conf and by_conf["high"]:
            high_conf_acc = sum(by_conf["high"]) / len(by_conf["high"])
            if high_conf_acc < 0.6:  # High confidence predictions should be > 60% accurate
                patterns.append({
                    "type": "overconfidence",
                    "high_confidence_accuracy": high_conf_acc,
                    "description": "High confidence predictions underperforming",
                })

        return patterns

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """Get comprehensive evaluation summary."""
        return {
            "total_predictions": len(self.completed_predictions),
            "overall_accuracy": self.get_overall_accuracy(),
            "accuracy_by_regime": self.get_accuracy_by_regime(),
            "accuracy_by_confidence": {
                k: sum(v) / len(v) if v else 0.5
                for k, v in self.accuracy_by_confidence.items()
            },
            "directional_bias": self.get_directional_bias(),
            "consecutive_errors": self.consecutive_errors,
            "max_consecutive_errors": self.max_consecutive_errors,
            "failure_patterns": self.identify_failure_patterns(),
        }


class MetaReasoner:
    """
    Reasons about the system's own performance and generates improvement hypotheses.

    This is the "thinking about thinking" component that:
    1. Analyzes evaluation metrics
    2. Identifies root causes of failures
    3. Generates hypotheses for improvement
    4. Prioritizes improvement actions
    """

    def __init__(self, knowledge_base: KnowledgeBase, evaluator: SelfEvaluator):
        self.kb = knowledge_base
        self.evaluator = evaluator
        self.hypotheses: List[Belief] = []
        self.improvement_history: List[ImprovementAction] = []

    def analyze_and_generate_hypotheses(self) -> List[Belief]:
        """
        Analyze current performance and generate improvement hypotheses.

        This is the core meta-reasoning step where the system
        reasons about its own failures and proposes solutions.
        """
        hypotheses = []
        summary = self.evaluator.get_evaluation_summary()
        patterns = summary["failure_patterns"]

        # Generate hypotheses based on failure patterns
        for pattern in patterns:
            hypothesis = self._generate_hypothesis_for_pattern(pattern)
            if hypothesis:
                hypotheses.append(hypothesis)

        # Check for belief-prediction mismatches
        mismatch_hypotheses = self._check_belief_alignment()
        hypotheses.extend(mismatch_hypotheses)

        # Check for overconfidence
        if summary["overall_accuracy"] < 0.5:
            hypotheses.append(Belief(
                id=f"hyp_reduce_confidence_{datetime.now().timestamp()}",
                content="Model is overconfident; should increase uncertainty estimates",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.6,
                metadata={
                    "current_accuracy": summary["overall_accuracy"],
                    "action": ImprovementType.THRESHOLD_CHANGE.value,
                    "target": "confidence_scaling",
                }
            ))

        self.hypotheses = hypotheses
        return hypotheses

    def _generate_hypothesis_for_pattern(self, pattern: Dict[str, Any]) -> Optional[Belief]:
        """Generate a hypothesis to address a specific failure pattern."""
        pattern_type = pattern.get("type")

        if pattern_type == "regime_failure":
            regime = pattern.get("regime")
            return Belief(
                id=f"hyp_regime_{regime}_{datetime.now().timestamp()}",
                content=f"Model underperforms in {regime} regime; should adjust strategy",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.5 + pattern.get("error_proportion", 0) * 0.3,
                metadata={
                    "pattern": pattern,
                    "action": ImprovementType.STRATEGY_SWITCH.value,
                    "target_regime": regime,
                }
            )

        elif pattern_type == "volatility_failure":
            return Belief(
                id=f"hyp_volatility_{datetime.now().timestamp()}",
                content="Model fails in high volatility; should reduce position sizes or pause",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.5 + pattern.get("error_proportion", 0) * 0.3,
                metadata={
                    "pattern": pattern,
                    "action": ImprovementType.WEIGHT_ADJUSTMENT.value,
                    "target": "volatility_scaling",
                }
            )

        elif pattern_type == "overconfidence":
            return Belief(
                id=f"hyp_overconfidence_{datetime.now().timestamp()}",
                content="High confidence predictions are unreliable; recalibrate confidence",
                belief_type=BeliefType.HYPOTHESIS,
                confidence=0.7,
                metadata={
                    "pattern": pattern,
                    "action": ImprovementType.THRESHOLD_CHANGE.value,
                    "target": "confidence_threshold",
                }
            )

        return None

    def _check_belief_alignment(self) -> List[Belief]:
        """Check if held beliefs align with observed performance."""
        hypotheses = []
        accuracy_by_regime = self.evaluator.get_accuracy_by_regime()

        # Check trending belief
        trending_belief = self.kb.beliefs.get("trending_momentum")
        if trending_belief and "trending" in accuracy_by_regime:
            if accuracy_by_regime["trending"] < 0.5 and trending_belief.confidence > 0.6:
                hypotheses.append(Belief(
                    id=f"hyp_trending_wrong_{datetime.now().timestamp()}",
                    content="Belief about momentum in trends may be wrong for this market",
                    belief_type=BeliefType.HYPOTHESIS,
                    confidence=0.6,
                    metadata={
                        "challenges_belief": "trending_momentum",
                        "action": ImprovementType.BELIEF_UPDATE.value,
                    }
                ))

        # Check ranging belief
        ranging_belief = self.kb.beliefs.get("ranging_reversion")
        if ranging_belief and "ranging" in accuracy_by_regime:
            if accuracy_by_regime["ranging"] < 0.5 and ranging_belief.confidence > 0.6:
                hypotheses.append(Belief(
                    id=f"hyp_ranging_wrong_{datetime.now().timestamp()}",
                    content="Belief about mean reversion in ranges may be wrong for this market",
                    belief_type=BeliefType.HYPOTHESIS,
                    confidence=0.6,
                    metadata={
                        "challenges_belief": "ranging_reversion",
                        "action": ImprovementType.BELIEF_UPDATE.value,
                    }
                ))

        return hypotheses

    def prioritize_improvements(self) -> List[Tuple[Belief, float]]:
        """
        Prioritize hypotheses by expected improvement value.

        Priority = confidence × potential_impact × feasibility
        """
        if not self.hypotheses:
            return []

        prioritized = []

        for hyp in self.hypotheses:
            # Impact based on action type
            impact_weights = {
                ImprovementType.WEIGHT_ADJUSTMENT.value: 0.8,
                ImprovementType.THRESHOLD_CHANGE.value: 0.6,
                ImprovementType.BELIEF_UPDATE.value: 0.7,
                ImprovementType.STRATEGY_SWITCH.value: 0.9,
                ImprovementType.RULE_ADDITION.value: 0.5,
                ImprovementType.RULE_REMOVAL.value: 0.5,
            }

            action = hyp.metadata.get("action", "")
            impact = impact_weights.get(action, 0.5)

            # Feasibility (lower for complex changes)
            feasibility = 0.9 if action in [
                ImprovementType.WEIGHT_ADJUSTMENT.value,
                ImprovementType.THRESHOLD_CHANGE.value,
            ] else 0.7

            priority = hyp.confidence * impact * feasibility
            prioritized.append((hyp, priority))

        # Sort by priority descending
        prioritized.sort(key=lambda x: x[1], reverse=True)
        return prioritized


class RecursiveSelfImprover:
    """
    Orchestrates the recursive self-improvement loop.

    The Loop:
    1. Observe performance (SelfEvaluator)
    2. Reason about failures (MetaReasoner)
    3. Generate improvement hypotheses
    4. Test hypotheses against held beliefs
    5. Execute approved improvements (modify KnowledgeBase)
    6. Log all changes for rollback

    This creates a system that can improve itself over time
    by learning from its own mistakes.
    """

    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        evaluator: Optional[SelfEvaluator] = None,
        auto_improve: bool = False,
        improvement_threshold: float = 0.7,
    ):
        self.kb = knowledge_base or KnowledgeBase()
        self.evaluator = evaluator or SelfEvaluator()
        self.reasoner = MetaReasoner(self.kb, self.evaluator)

        self.auto_improve = auto_improve
        self.improvement_threshold = improvement_threshold

        # Improvement tracking
        self.pending_improvements: List[Tuple[Belief, float]] = []
        self.executed_improvements: List[ImprovementAction] = []
        self.rejected_improvements: List[Tuple[Belief, str]] = []

        # Callbacks for integration
        self.on_improvement_proposed: Optional[Callable[[Belief], None]] = None
        self.on_improvement_executed: Optional[Callable[[ImprovementAction], None]] = None
        self.on_belief_changed: Optional[Callable[[Belief], None]] = None

    def observe_prediction(
        self,
        signal: float,
        direction: str,
        confidence: float,
        context: Dict[str, Any],
    ) -> str:
        """Record a prediction for later evaluation."""
        return self.evaluator.record_prediction(signal, direction, confidence, context)

    def observe_outcome(
        self,
        prediction_id: str,
        actual_outcome: float,
        price_change_percent: float,
    ) -> None:
        """Record the outcome and trigger improvement cycle if needed."""
        prediction = self.evaluator.record_outcome(
            prediction_id, actual_outcome, price_change_percent
        )

        if prediction and not prediction.was_correct:
            # Update relevant beliefs based on error context
            self._update_beliefs_from_error(prediction)

        # Check if improvement cycle should run
        if self._should_run_improvement_cycle():
            self.run_improvement_cycle()

    def _update_beliefs_from_error(self, prediction: Prediction) -> None:
        """Update beliefs based on prediction error context."""
        regime = prediction.context.get("regime", "unknown")

        # Update regime-specific beliefs
        if regime == "trending":
            self.kb.update_belief("trending_momentum", supports=False, weight=0.5)
        elif regime == "ranging":
            self.kb.update_belief("ranging_reversion", supports=False, weight=0.5)

        # Update volatility belief
        vol_ratio = prediction.context.get("volatility_ratio", 1.0)
        if vol_ratio > 1.5:
            self.kb.update_belief("high_vol_caution", supports=True, weight=0.5)

    def _should_run_improvement_cycle(self) -> bool:
        """Determine if improvement cycle should run."""
        # Run every 100 completed predictions
        completed = len(self.evaluator.completed_predictions)
        if completed > 0 and completed % 100 == 0:
            return True

        # Run if consecutive errors exceed threshold
        if self.evaluator.consecutive_errors >= 5:
            return True

        return False

    def run_improvement_cycle(self) -> List[ImprovementAction]:
        """
        Execute one improvement cycle.

        This is where the system reflects on its performance
        and potentially modifies itself.
        """
        # 1. Generate hypotheses based on performance analysis
        hypotheses = self.reasoner.analyze_and_generate_hypotheses()

        if not hypotheses:
            return []

        # 2. Prioritize hypotheses
        prioritized = self.reasoner.prioritize_improvements()
        self.pending_improvements = prioritized

        executed = []

        # 3. Execute improvements (if auto-improve or above threshold)
        for hypothesis, priority in prioritized:
            if self.on_improvement_proposed:
                self.on_improvement_proposed(hypothesis)

            if self.auto_improve and priority >= self.improvement_threshold:
                action = self._execute_improvement(hypothesis)
                if action:
                    executed.append(action)
                    if self.on_improvement_executed:
                        self.on_improvement_executed(action)
            elif priority < self.improvement_threshold:
                self.rejected_improvements.append((
                    hypothesis,
                    f"Priority {priority:.2f} below threshold {self.improvement_threshold}"
                ))

        return executed

    def _execute_improvement(self, hypothesis: Belief) -> Optional[ImprovementAction]:
        """Execute a specific improvement based on hypothesis."""
        action_type_str = hypothesis.metadata.get("action", "")

        try:
            action_type = ImprovementType(action_type_str)
        except ValueError:
            return None

        before_state = self.kb.export_state()

        # Execute based on action type
        if action_type == ImprovementType.BELIEF_UPDATE:
            target_belief_id = hypothesis.metadata.get("challenges_belief")
            if target_belief_id:
                self.kb.update_belief(target_belief_id, supports=False, weight=1.0)

        elif action_type == ImprovementType.WEIGHT_ADJUSTMENT:
            # Add a new belief about weight adjustment
            new_belief = Belief(
                id=f"learned_weight_adj_{datetime.now().timestamp()}",
                content=hypothesis.content,
                belief_type=BeliefType.LEARNED,
                confidence=hypothesis.confidence,
                metadata={"source": hypothesis.id}
            )
            self.kb.add_belief(new_belief)

        elif action_type == ImprovementType.THRESHOLD_CHANGE:
            # Add a belief about threshold adjustment needed
            new_belief = Belief(
                id=f"learned_threshold_{datetime.now().timestamp()}",
                content=hypothesis.content,
                belief_type=BeliefType.LEARNED,
                confidence=hypothesis.confidence,
                metadata={"source": hypothesis.id}
            )
            self.kb.add_belief(new_belief)

        elif action_type == ImprovementType.STRATEGY_SWITCH:
            target_regime = hypothesis.metadata.get("target_regime")
            new_belief = Belief(
                id=f"learned_strategy_{target_regime}_{datetime.now().timestamp()}",
                content=f"Alternative strategy needed for {target_regime} regime",
                belief_type=BeliefType.LEARNED,
                confidence=hypothesis.confidence,
                metadata={"source": hypothesis.id, "regime": target_regime}
            )
            self.kb.add_belief(new_belief)

        after_state = self.kb.export_state()

        improvement = ImprovementAction(
            id=f"imp_{len(self.executed_improvements)}_{datetime.now().timestamp()}",
            timestamp=datetime.now().isoformat(),
            action_type=action_type,
            description=hypothesis.content,
            before_state=before_state,
            after_state=after_state,
            reasoning=f"Triggered by hypothesis: {hypothesis.id}",
            triggered_by=[hypothesis.id],
        )

        self.executed_improvements.append(improvement)

        # Also add the hypothesis to KB as it's now acted upon
        hypothesis.belief_type = BeliefType.LEARNED
        self.kb.add_belief(hypothesis)

        if self.on_belief_changed:
            self.on_belief_changed(hypothesis)

        return improvement

    def rollback_improvement(self, improvement_id: str) -> bool:
        """Rollback a specific improvement."""
        for i, imp in enumerate(self.executed_improvements):
            if imp.id == improvement_id:
                # Restore before state (simplified - in practice would be more complex)
                imp.reverted = True
                self.kb.rollback_last_change()
                return True
        return False

    def get_improvement_recommendations(self) -> List[Dict[str, Any]]:
        """Get current improvement recommendations without executing."""
        hypotheses = self.reasoner.analyze_and_generate_hypotheses()
        prioritized = self.reasoner.prioritize_improvements()

        return [
            {
                "hypothesis": hyp.content,
                "confidence": hyp.confidence,
                "priority": priority,
                "action_type": hyp.metadata.get("action"),
                "would_execute": priority >= self.improvement_threshold,
            }
            for hyp, priority in prioritized
        ]

    def get_state_summary(self) -> Dict[str, Any]:
        """Get comprehensive state summary."""
        return {
            "knowledge_base": self.kb.export_state(),
            "evaluation": self.evaluator.get_evaluation_summary(),
            "pending_improvements": len(self.pending_improvements),
            "executed_improvements": len(self.executed_improvements),
            "rejected_improvements": len(self.rejected_improvements),
            "auto_improve": self.auto_improve,
            "improvement_threshold": self.improvement_threshold,
        }

    def get_reasoning_trace(self) -> List[Dict[str, Any]]:
        """Get the reasoning trace showing how improvements were derived."""
        trace = []

        # Add evaluation observations
        summary = self.evaluator.get_evaluation_summary()
        trace.append({
            "step": "evaluation",
            "observation": f"Overall accuracy: {summary['overall_accuracy']:.2%}",
            "details": summary,
        })

        # Add failure pattern analysis
        for pattern in summary["failure_patterns"]:
            trace.append({
                "step": "pattern_detection",
                "observation": pattern["description"],
                "details": pattern,
            })

        # Add hypothesis generation
        for hyp, priority in self.pending_improvements:
            trace.append({
                "step": "hypothesis",
                "observation": hyp.content,
                "confidence": hyp.confidence,
                "priority": priority,
                "action": hyp.metadata.get("action"),
            })

        # Add executed improvements
        for imp in self.executed_improvements[-5:]:  # Last 5
            trace.append({
                "step": "improvement",
                "action": imp.action_type.value,
                "description": imp.description,
                "reasoning": imp.reasoning,
            })

        return trace


# Factory function
def create_self_improving_system(
    auto_improve: bool = False,
    improvement_threshold: float = 0.7,
) -> RecursiveSelfImprover:
    """
    Create a recursive self-improvement system.

    Args:
        auto_improve: If True, automatically execute improvements above threshold
        improvement_threshold: Minimum priority to auto-execute (0.0-1.0)

    Returns:
        Configured RecursiveSelfImprover
    """
    return RecursiveSelfImprover(
        auto_improve=auto_improve,
        improvement_threshold=improvement_threshold,
    )
