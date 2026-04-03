"""
JEPA Governance — Composite latent state + runtime process + residual governor.

Architecture:
    OntologySignal (12-layer OLM weights)
        +
    VrittiSignal (5-vritti distribution)
        ↓
    JEPACompositeSignal (structured fusion via R[v,a] coupling matrix)
        ↓
    RuntimeProcessState (what the agent is actually doing)
        ↓
    ResidualGovernor (compares JEPA composite vs runtime behavior)
        ↓
    GovernanceAssessment (regime + allow/deny/confirm/halt + reason codes)

JEPA here is NOT a trajectory predictor. It is a composite latent state
formed by integrating the vertical ontological classification with the
horizontal 5-vritti cognitive classification. The R[v,a] coupling matrix
from chitta_vritti/coupling.py provides the mathematical bridge.

Regime classification:
    NORMAL         — JEPA and runtime aligned, residual low
    PROCESS_DRIFT  — runtime deviates from JEPA-justified behavior
    SEMANTIC_SHIFT — ontology/vritti state changed, requires re-evaluation
    DUAL_ANOMALY   — both JEPA and runtime incoherent, block/halt
    UNKNOWN        — insufficient signals, fail closed
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from agentic.chitta_vritti.coupling import get_aspect_weights as _get_aspect_weights


# =========================================================================
# Constants
# =========================================================================

VRITTI_NAMES = ("pramana", "viparyaya", "vikalpa", "smrti", "nidra")

ONTOLOGY_LAYERS = (
    "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
    "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
    "O9_WITNESSES", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING",
)

# Vritti modes that indicate the system should NOT be executing actions
# (it should be observing, verifying, or halting instead)
OBSERVATION_VRITTIS = frozenset({"viparyaya", "nidra"})

# Vritti modes compatible with active execution
EXECUTION_VRITTIS = frozenset({"pramana", "smrti"})

# Ontology layers primarily associated with observation/governance (upper 6)
GOVERNANCE_ONTOLOGY = frozenset({
    "O7_REASONING", "O8_PURPOSE", "O9_WITNESSES",
    "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING",
})

# Ontology layers primarily associated with execution (lower 6)
EXECUTION_ONTOLOGY = frozenset({
    "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION",
    "O4_STRUCTURE", "O5_COGNITION", "O6_AGENCY",
})


# =========================================================================
# Startup validation: ensure coupling matrix is importable and functional
# =========================================================================

def _validate_coupling_import() -> None:
    """Validate that the R[v,a] coupling matrix is available at startup.

    Fail-fast: if the coupling module is missing or broken, the governance
    system cannot compute JEPA composites and should not start silently.
    Checks both the count AND exact key names match ONTOLOGY_LAYERS.
    """
    test_dist = {"pramana": 1.0, "viparyaya": 0.0, "vikalpa": 0.0,
                 "smrti": 0.0, "nidra": 0.0}
    result = _get_aspect_weights(test_dist)
    if not isinstance(result, dict):
        raise ImportError(
            "chitta_vritti.coupling.get_aspect_weights returned invalid result: "
            f"expected dict, got {type(result).__name__}"
        )
    expected_keys = set(ONTOLOGY_LAYERS)
    actual_keys = set(result.keys())
    if actual_keys != expected_keys:
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        raise ImportError(
            "chitta_vritti.coupling.get_aspect_weights returned wrong keys: "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )

_validate_coupling_import()


# =========================================================================
# Enums
# =========================================================================


class GovernanceRegime(enum.Enum):
    """Regime classification from residual comparison."""
    NORMAL = "normal"
    PROCESS_DRIFT = "process_drift"
    SEMANTIC_SHIFT = "semantic_shift"
    DUAL_ANOMALY = "dual_anomaly"
    UNKNOWN = "unknown"


class RuntimeActionCategory(enum.Enum):
    """Behavioral category of the proposed action."""
    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"
    PRIVILEGED = "privileged"
    UNKNOWN = "unknown"


# =========================================================================
# A1. Ontology Signal
# =========================================================================


@dataclass(frozen=True)
class OntologySignal:
    """Vertical ontological classification of the current state.

    Derived from OLMGovernanceSignals (12-layer weights).

    Attributes:
        layer_weights: Weight for each of the 12 ontological layers [0, 1].
        primary_layer: Layer with highest activation.
        governance_strength: Sum of upper-6 governance layer weights.
        execution_strength: Sum of lower-6 execution layer weights.
        confidence: Overall classification confidence [0, 1].
        evidence: Human-readable evidence for the classification.
    """
    layer_weights: Dict[str, float]
    primary_layer: str
    governance_strength: float
    execution_strength: float
    confidence: float
    evidence: str

    def layer_balance(self) -> float:
        """Execution vs governance ratio [0, 1]. 0.5 = balanced."""
        total = self.governance_strength + self.execution_strength
        if total == 0:
            return 0.5
        return self.execution_strength / total

    def is_governance_dominant(self) -> bool:
        return self.governance_strength > self.execution_strength

    def is_execution_dominant(self) -> bool:
        return self.execution_strength > self.governance_strength


# =========================================================================
# A2. Vritti Signal
# =========================================================================


@dataclass(frozen=True)
class VrittiSignal:
    """Horizontal 5-vritti cognitive classification.

    Derived from ChittaVrittiResult.

    Attributes:
        distribution: Probability distribution over 5 vrittis (sums to 1.0).
        primary_vritti: Mode with highest activation.
        coherence: Cross-representation agreement [0, 1].
        score: Overall readiness score [0, 1].
        confidence: Classification confidence [0, 1].
        evidence: Human-readable evidence.
    """
    distribution: Dict[str, float]
    primary_vritti: str
    coherence: float
    score: float
    confidence: float
    evidence: str

    def is_observation_mode(self) -> bool:
        """True if dominant vritti suggests observation, not execution."""
        return self.primary_vritti in OBSERVATION_VRITTIS

    def is_execution_mode(self) -> bool:
        """True if dominant vritti is compatible with active execution."""
        return self.primary_vritti in EXECUTION_VRITTIS

    def misperception_risk(self) -> float:
        """Viparyaya activation — risk of acting on misperception."""
        return self.distribution.get("viparyaya", 0.0)

    def dormancy_risk(self) -> float:
        """Nidra activation — risk of acting from low-awareness state."""
        return self.distribution.get("nidra", 0.0)


# =========================================================================
# A3. JEPA Composite Signal
# =========================================================================


@dataclass(frozen=True)
class JEPACompositeSignal:
    """Structured fusion of ontological and vritti classifiers.

    JEPA = Joint Embedding Predictive Architecture (used here as composite
    latent state, not as trajectory predictor).

    The composite is built by:
    1. Taking the 5-vritti distribution (horizontal cognitive mode)
    2. Multiplying through the R[v,a] coupling matrix to get expected
       ontological activation from the cognitive mode
    3. Comparing expected activation against actual OLM layer weights
    4. Computing alignment, stability, and integrated confidence

    This reveals whether the cognitive mode and ontological position are
    coherent — e.g., if the vritti says "valid cognition" (pramana), the
    ontology should show strong O7_REASONING activation.

    Attributes:
        ontology: The ontological signal component.
        vritti: The vritti signal component.
        expected_ontology: Layer weights predicted by vritti via R[v,a].
        actual_ontology: Actual layer weights from OLM.
        ontology_vritti_alignment: Cosine similarity between expected
            and actual ontology activations [0, 1].
        integrated_confidence: Combined confidence from both classifiers
            weighted by alignment [0, 1].
        stability: How stable/reliable this composite is [0, 1].
        summary: Canonical human-readable summary.
        coupling_evidence: Which vritti-ontology couplings drove the signal.
    """
    ontology: OntologySignal
    vritti: VrittiSignal
    expected_ontology: Dict[str, float]
    actual_ontology: Dict[str, float]
    ontology_vritti_alignment: float
    integrated_confidence: float
    stability: float
    summary: str
    coupling_evidence: Tuple[str, ...]


# =========================================================================
# B. Runtime Process State
# =========================================================================


@dataclass(frozen=True)
class RuntimeProcessState:
    """What the agent is actually doing in behavior space.

    This is separate from JEPA (which is the semantic-cognitive latent state).
    RuntimeProcessState captures the behavioral/execution context.

    Attributes:
        action_type: High-level action (e.g. "authorize", "call_tool").
        tool_name: Specific tool or capability being invoked.
        action_category: READ_ONLY / MUTATING / DESTRUCTIVE / PRIVILEGED.
        risk_level: Tool risk classification string.
        confidence_score: Caller-provided confidence [0, 1].
        agency_level: FULL / CONFIRM / INFORM.
        requires_confirmation: Whether human confirmation needed.
        execution_mode: FULL / CAUTIOUS / CONFIRM_REQUIRED / BLOCKED.
        escalation_level: NONE / NOTIFY / CONFIRM / HALT.
        session_id: Session correlation.
        actor_id: Agent or human identity.
        declared_capabilities: Capabilities the action requires.
        is_side_effecting: Whether the action has external side effects.
    """
    action_type: str
    tool_name: str
    action_category: RuntimeActionCategory
    risk_level: str
    confidence_score: float
    agency_level: str
    requires_confirmation: bool
    execution_mode: str
    escalation_level: str
    session_id: str
    actor_id: str
    declared_capabilities: Tuple[str, ...]
    is_side_effecting: bool


# =========================================================================
# C. Residual Signal
# =========================================================================


@dataclass(frozen=True)
class ResidualSignal:
    """Comparison between JEPA composite state and runtime process state.

    The residual is the key governance control signal. It answers:
    "Does what the agent is doing fit what the latent state says it should be?"

    Attributes:
        residual_magnitude: Overall mismatch severity [0, 1].
            0.0 = perfect alignment, 1.0 = complete incoherence.
        semantic_consistency: Is the action semantically coherent with
            the ontological position? [0, 1] (1 = consistent).
        action_state_coherence: Is the action appropriate for the
            current vritti mode? [0, 1] (1 = coherent).
        regime: Classified governance regime.
        risk_factors: Specific risk factor descriptions.
        reason_codes: Machine-readable reason codes.
        explanation: Human-readable explanation of the residual.
    """
    residual_magnitude: float
    semantic_consistency: float
    action_state_coherence: float
    regime: GovernanceRegime
    risk_factors: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    explanation: str


# =========================================================================
# D. Governance Assessment (output)
# =========================================================================


@dataclass(frozen=True)
class JEPAGovernanceAssessment:
    """Full governance output from the JEPA residual governor.

    This is the final assessment that feeds into SafetyContract and
    GovernanceService decision-making.

    Attributes:
        regime: Classified governance regime.
        recommended_action: ALLOW / DENY / CONFIRM / HALT / DEGRADE.
        execution_mode_override: Suggested override for execution mode.
        escalation_override: Suggested override for escalation level.
        confidence_adjustment: Adjustment to apply to confidence [-0.5, 0].
        reason_codes: Machine-readable governance reason codes.
        rationale: Human-readable decision rationale.
        jepa_composite: The full JEPA composite signal (for audit).
        runtime_state: The runtime state (for audit).
        residual: The residual comparison (for audit).
    """
    regime: GovernanceRegime
    recommended_action: str
    execution_mode_override: Optional[str]
    escalation_override: Optional[str]
    confidence_adjustment: float
    reason_codes: Tuple[str, ...]
    rationale: str
    jepa_composite: JEPACompositeSignal
    runtime_state: RuntimeProcessState
    residual: ResidualSignal

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-friendly dict for GovernanceAuditStore."""
        return {
            "regime": self.regime.value,
            "recommended_action": self.recommended_action,
            "execution_mode_override": self.execution_mode_override,
            "escalation_override": self.escalation_override,
            "confidence_adjustment": self.confidence_adjustment,
            "reason_codes": list(self.reason_codes),
            "rationale": self.rationale,
            "ontology_primary": self.jepa_composite.ontology.primary_layer,
            "ontology_confidence": self.jepa_composite.ontology.confidence,
            "vritti_primary": self.jepa_composite.vritti.primary_vritti,
            "vritti_confidence": self.jepa_composite.vritti.confidence,
            "ontology_vritti_alignment": self.jepa_composite.ontology_vritti_alignment,
            "integrated_confidence": self.jepa_composite.integrated_confidence,
            "residual_magnitude": self.residual.residual_magnitude,
            "semantic_consistency": self.residual.semantic_consistency,
            "action_state_coherence": self.residual.action_state_coherence,
            "action_category": self.runtime_state.action_category.value,
            "tool_name": self.runtime_state.tool_name,
            "risk_level": self.runtime_state.risk_level,
        }


# =========================================================================
# Builders and Classifiers
# =========================================================================


def build_ontology_signal(
    *,
    layer_weights: Optional[Dict[str, float]] = None,
    olm_signals: Any = None,
) -> OntologySignal:
    """Build an OntologySignal from OLM layer weights or OLMGovernanceSignals.

    Args:
        layer_weights: Dict mapping layer names to weights [0, 1].
        olm_signals: OLMGovernanceSignals from olm_bridge.py.

    Returns:
        OntologySignal with classification, confidence, and evidence.

    Raises:
        ValueError: If neither argument is provided.
    """
    if olm_signals is not None:
        weights = {}
        for layer in ONTOLOGY_LAYERS:
            attr = _olm_layer_to_attr(layer)
            weights[layer] = getattr(olm_signals, attr, 0.0)
        gov_str = olm_signals.governance_strength
        exec_str = olm_signals.execution_strength
    elif layer_weights is not None:
        # Validate keys: warn about unknown keys (may indicate ontology extension)
        unknown_keys = set(layer_weights.keys()) - set(ONTOLOGY_LAYERS)
        if unknown_keys:
            import logging
            logging.getLogger(__name__).warning(
                "Unknown layer_weights keys (ignored): %s", unknown_keys
            )
        weights = {l: layer_weights.get(l, 0.0) for l in ONTOLOGY_LAYERS}
        gov_str = sum(weights[l] for l in ONTOLOGY_LAYERS if l in GOVERNANCE_ONTOLOGY)
        exec_str = sum(weights[l] for l in ONTOLOGY_LAYERS if l in EXECUTION_ONTOLOGY)
    else:
        raise ValueError("Either layer_weights or olm_signals must be provided")

    primary = max(weights, key=weights.get)
    total = sum(weights.values())

    # Confidence as true confidence: combine dominance (how much the
    # primary stands out) with coverage (how much total signal exists).
    # Raw proportion (primary/total) overstates confidence when all
    # layers are uniformly high.
    if total > 0:
        dominance = weights[primary] / total  # [0, 1]
        n = len(weights)
        # Entropy-based: uniform dist has dominance=1/n, perfect has 1.0
        # Rescale so uniform→0, single-layer→1
        uniformity = 1.0 / n if n > 0 else 0.0
        if dominance > uniformity:
            discrimination = (dominance - uniformity) / (1.0 - uniformity)
        else:
            discrimination = 0.0
        # Coverage: primary weight itself as a raw signal strength
        coverage = min(1.0, weights[primary])
        confidence = 0.6 * discrimination + 0.4 * coverage
    else:
        confidence = 0.0

    return OntologySignal(
        layer_weights=weights,
        primary_layer=primary,
        governance_strength=gov_str,
        execution_strength=exec_str,
        confidence=min(1.0, confidence),
        evidence=f"Primary={primary} ({weights[primary]:.2f}), "
                 f"gov={gov_str:.2f}, exec={exec_str:.2f}",
    )


def build_vritti_signal(
    *,
    vritti_result: Any = None,
    vritti_distribution: Optional[Dict[str, float]] = None,
    coherence: float = 0.5,
    score: float = 0.5,
) -> VrittiSignal:
    """Build a VrittiSignal from ChittaVrittiResult or raw distribution.

    Args:
        vritti_result: ChittaVrittiResult from chitta_vritti engine.
        vritti_distribution: Raw dict mapping vritti names to probabilities.
        coherence: Cross-representation coherence [0, 1].
        score: Readiness score [0, 1].

    Returns:
        VrittiSignal with classification, confidence, and evidence.
    """
    if vritti_result is not None:
        dist = dict(vritti_result.vritti)
        coh = vritti_result.coherence
        sc = vritti_result.score
        primary = vritti_result.dominant_vritti
    elif vritti_distribution is not None:
        # Validate keys: warn about unknown vritti names
        unknown_keys = set(vritti_distribution.keys()) - set(VRITTI_NAMES)
        if unknown_keys:
            import logging
            logging.getLogger(__name__).warning(
                "Unknown vritti_distribution keys (ignored): %s", unknown_keys
            )
        dist = {v: vritti_distribution.get(v, 0.0) for v in VRITTI_NAMES}
        total = sum(dist.values())
        if total <= 0:
            # All-zero vritti → fail-closed: treat as nidra (dormancy)
            dist = {"pramana": 0.0, "viparyaya": 0.0, "vikalpa": 0.0,
                    "smrti": 0.0, "nidra": 1.0}
            coh = 0.0
            sc = 0.0
            primary = "nidra"
        else:
            # Normalize if not already
            if abs(total - 1.0) > 0.01:
                dist = {k: v / total for k, v in dist.items()}
            coh = coherence
            sc = score
            primary = max(dist, key=dist.get)
    else:
        # Fail-closed: no vritti data → high nidra (dormancy)
        dist = {"pramana": 0.0, "viparyaya": 0.0, "vikalpa": 0.0,
                "smrti": 0.0, "nidra": 1.0}
        coh = 0.0
        sc = 0.0
        primary = "nidra"

    confidence = dist.get(primary, 0.0) * coh if coh > 0 else 0.0

    return VrittiSignal(
        distribution=dist,
        primary_vritti=primary,
        coherence=coh,
        score=sc,
        confidence=min(1.0, confidence),
        evidence=f"Primary={primary} ({dist.get(primary, 0):.2f}), "
                 f"coherence={coh:.2f}, score={sc:.2f}",
    )


def build_jepa_composite(
    ontology: OntologySignal,
    vritti: VrittiSignal,
) -> JEPACompositeSignal:
    """Build the JEPA composite signal from ontology + vritti.

    Integration logic:
    1. Compute expected ontological activation from vritti via R[v,a]:
       expected[a] = sum_v(vritti[v] * R[v,a])
    2. Compare expected vs actual layer weights (cosine similarity).
    3. Integrated confidence = geometric mean of both confidences,
       scaled by alignment.
    4. Stability = alignment * vritti coherence.

    This reveals whether the cognitive mode and ontological position are
    coherent. High alignment means the system's cognitive state and
    semantic position agree.
    """
    # Step 1: Expected ontological activation from vritti
    expected = _get_aspect_weights(vritti.distribution)

    # Step 2: Actual ontological activation
    actual = dict(ontology.layer_weights)

    # Step 3: Cosine similarity between expected and actual
    exp_vec = np.array([expected.get(l, 0.0) for l in ONTOLOGY_LAYERS])
    act_vec = np.array([actual.get(l, 0.0) for l in ONTOLOGY_LAYERS])

    exp_norm = np.linalg.norm(exp_vec)
    act_norm = np.linalg.norm(act_vec)

    if exp_norm > 0 and act_norm > 0:
        raw_cosine = float(np.dot(exp_vec, act_vec) / (exp_norm * act_norm))
        # Preserve anti-correlation signal: negative cosine means the
        # actual ontology is anti-correlated with what the vritti expects.
        # Clamp to [-1, 1] for numerical safety, then map to [0, 1]
        # where 0 = perfect anti-correlation, 0.5 = orthogonal, 1 = aligned.
        raw_cosine = max(-1.0, min(1.0, raw_cosine))
        alignment = (raw_cosine + 1.0) / 2.0
    else:
        alignment = 0.0

    # Step 4: Integrated confidence
    if ontology.confidence > 0 and vritti.confidence > 0:
        geo_mean = math.sqrt(ontology.confidence * vritti.confidence)
        integrated = geo_mean * alignment
    else:
        integrated = 0.0

    # Step 5: Stability
    stability = alignment * vritti.coherence

    # Step 6: Coupling evidence
    evidence = []
    primary_coupling_layer = _get_primary_coupling(vritti.primary_vritti)
    actual_primary = ontology.primary_layer
    if primary_coupling_layer == actual_primary:
        evidence.append(
            f"{vritti.primary_vritti}→{primary_coupling_layer} ALIGNED"
        )
    else:
        evidence.append(
            f"{vritti.primary_vritti}→{primary_coupling_layer} expected, "
            f"actual={actual_primary} MISALIGNED"
        )

    # Summary
    summary = (
        f"JEPA[{vritti.primary_vritti}|{ontology.primary_layer}] "
        f"align={alignment:.2f} conf={integrated:.2f} "
        f"stab={stability:.2f}"
    )

    return JEPACompositeSignal(
        ontology=ontology,
        vritti=vritti,
        expected_ontology=expected,
        actual_ontology=actual,
        ontology_vritti_alignment=alignment,
        integrated_confidence=integrated,
        stability=stability,
        summary=summary,
        coupling_evidence=tuple(evidence),
    )


def build_runtime_process_state(
    *,
    action_type: str = "",
    tool_name: str = "",
    risk_level: str = "",
    confidence_score: float = 0.5,
    agency_level: str = "FULL",
    requires_confirmation: bool = False,
    execution_mode: str = "",
    escalation_level: str = "NONE",
    session_id: str = "",
    actor_id: str = "",
    capabilities: Sequence[str] = (),
) -> RuntimeProcessState:
    """Build a RuntimeProcessState from governance request context.

    Automatically classifies the action category from risk_level.
    """
    risk_lower = risk_level.lower()
    if risk_lower in ("destructive",):
        cat = RuntimeActionCategory.DESTRUCTIVE
    elif risk_lower in ("privileged",):
        cat = RuntimeActionCategory.PRIVILEGED
    elif risk_lower in ("write", "execute"):
        cat = RuntimeActionCategory.MUTATING
    elif risk_lower in ("read_only",):
        cat = RuntimeActionCategory.READ_ONLY
    else:
        cat = RuntimeActionCategory.UNKNOWN

    is_side_effecting = cat in (
        RuntimeActionCategory.MUTATING,
        RuntimeActionCategory.DESTRUCTIVE,
        RuntimeActionCategory.PRIVILEGED,
    )

    return RuntimeProcessState(
        action_type=action_type,
        tool_name=tool_name,
        action_category=cat,
        risk_level=risk_level,
        confidence_score=confidence_score,
        agency_level=agency_level,
        requires_confirmation=requires_confirmation,
        execution_mode=execution_mode,
        escalation_level=escalation_level,
        session_id=session_id,
        actor_id=actor_id,
        declared_capabilities=tuple(capabilities),
        is_side_effecting=is_side_effecting,
    )


# =========================================================================
# Residual Governor
# =========================================================================

# Thresholds for residual comparison.
# Alignment is now on [0, 1] where 0.5 = orthogonal, 1.0 = aligned,
# 0.0 = anti-correlated (mapped from cosine via (cos+1)/2).
# Old thresholds (raw cosine 0.40, 0.20) map to:
_ALIGNMENT_LOW = 0.70
_ALIGNMENT_CRITICAL = 0.60
_VRITTI_OBSERVATION_THRESHOLD = 0.35
_MISPERCEPTION_HIGH = 0.40
_DORMANCY_HIGH = 0.50


def compute_residual(
    jepa: JEPACompositeSignal,
    runtime: RuntimeProcessState,
) -> ResidualSignal:
    """Compare JEPA composite state against runtime process state.

    Residual rules:
    1. Semantic consistency: Does the action fit the ontological position?
       - Destructive actions from governance-dominant ontology = inconsistent
       - Read-only actions always semantically consistent
    2. Action-state coherence: Is the action appropriate for the vritti mode?
       - Observation vrittis (viparyaya, nidra) + side effects = incoherent
       - Execution vrittis (pramana, smrti) + action = coherent
    3. Residual magnitude: Overall mismatch combining alignment,
       semantic consistency, and action-state coherence.

    Returns:
        ResidualSignal with magnitude, consistency, coherence, regime,
        risk factors, reason codes, and explanation.
    """
    risk_factors: List[str] = []
    reason_codes: List[str] = []

    # --- Semantic consistency ---
    # Bounded weighted aggregation: each factor contributes a weighted
    # penalty in [0, weight_i], and the total is clamped to [0, 1].
    # This replaces additive -= deductions which could stack beyond 1.0.
    sem_penalties: List[float] = []

    if runtime.is_side_effecting and jepa.ontology.is_governance_dominant():
        sem_penalties.append(0.30)
        risk_factors.append(
            f"Side-effecting action '{runtime.tool_name}' from "
            f"governance-dominant ontology (gov={jepa.ontology.governance_strength:.2f})"
        )
        reason_codes.append("GOVERNANCE_ONTOLOGY_EXECUTING")

    if runtime.action_category == RuntimeActionCategory.DESTRUCTIVE:
        exec_weight = jepa.ontology.layer_weights.get("O3_EXECUTION", 0.0)
        if exec_weight < 0.3:
            sem_penalties.append(0.40)
            risk_factors.append(
                f"Destructive action with weak O3_EXECUTION ({exec_weight:.2f})"
            )
            reason_codes.append("DESTRUCTIVE_WITHOUT_EXECUTION_ONTOLOGY")

    if runtime.action_category == RuntimeActionCategory.PRIVILEGED:
        agency_weight = jepa.ontology.layer_weights.get("O6_AGENCY", 0.0)
        if agency_weight < 0.3:
            sem_penalties.append(0.30)
            risk_factors.append(
                f"Privileged action with weak O6_AGENCY ({agency_weight:.2f})"
            )
            reason_codes.append("PRIVILEGED_WITHOUT_AGENCY_ONTOLOGY")

    # Bounded aggregation: 1 - product(1 - p_i) ensures [0, 1] range
    # even when multiple penalties apply simultaneously.
    if sem_penalties:
        combined = 1.0
        for p in sem_penalties:
            combined *= (1.0 - p)
        semantic_consistency = max(0.0, combined)
    else:
        semantic_consistency = 1.0

    # --- Action-state coherence ---
    # Same bounded aggregation approach.
    act_penalties: List[float] = []

    vritti = jepa.vritti
    if vritti.is_observation_mode() and runtime.is_side_effecting:
        act_penalties.append(0.50)
        risk_factors.append(
            f"Side-effecting action during {vritti.primary_vritti} "
            f"(observation/dormancy mode)"
        )
        reason_codes.append("SIDE_EFFECT_IN_OBSERVATION_MODE")

    if vritti.misperception_risk() > _MISPERCEPTION_HIGH:
        if runtime.is_side_effecting:
            act_penalties.append(0.30)
            risk_factors.append(
                f"High viparyaya ({vritti.misperception_risk():.2f}) "
                f"during side-effecting action"
            )
            reason_codes.append("HIGH_MISPERCEPTION_EXECUTING")

    if vritti.dormancy_risk() > _DORMANCY_HIGH:
        if runtime.action_category != RuntimeActionCategory.READ_ONLY:
            act_penalties.append(0.30)
            risk_factors.append(
                f"High nidra ({vritti.dormancy_risk():.2f}) "
                f"during non-read-only action"
            )
            reason_codes.append("HIGH_DORMANCY_EXECUTING")

    # Vikalpa (imagination) + any mutating side effect = concerning
    # (not only destructive/privileged — mutating writes also risky)
    vikalpa_level = vritti.distribution.get("vikalpa", 0.0)
    if vikalpa_level > 0.40 and runtime.is_side_effecting:
        act_penalties.append(0.30)
        risk_factors.append(
            f"High vikalpa ({vikalpa_level:.2f}) during "
            f"{runtime.action_category.value} action"
        )
        reason_codes.append("IMAGINATIVE_DESTRUCTIVE")

    if act_penalties:
        combined = 1.0
        for p in act_penalties:
            combined *= (1.0 - p)
        action_state_coherence = max(0.0, combined)
    else:
        action_state_coherence = 1.0

    # --- Residual magnitude ---
    # Blend of alignment inversion, semantic inconsistency, and action incoherence
    alignment_residual = 1.0 - jepa.ontology_vritti_alignment
    semantic_residual = 1.0 - semantic_consistency
    action_residual = 1.0 - action_state_coherence

    residual_magnitude = (
        0.35 * alignment_residual
        + 0.30 * semantic_residual
        + 0.35 * action_residual
    )
    residual_magnitude = min(1.0, residual_magnitude)

    # --- Regime classification ---
    regime = _classify_regime(
        alignment=jepa.ontology_vritti_alignment,
        semantic_consistency=semantic_consistency,
        action_state_coherence=action_state_coherence,
        residual_magnitude=residual_magnitude,
        integrated_confidence=jepa.integrated_confidence,
    )

    if regime == GovernanceRegime.UNKNOWN:
        reason_codes.append("UNKNOWN_REGIME")

    explanation = _build_explanation(
        regime=regime,
        residual_magnitude=residual_magnitude,
        semantic_consistency=semantic_consistency,
        action_state_coherence=action_state_coherence,
        risk_factors=risk_factors,
        jepa=jepa,
        runtime=runtime,
    )

    return ResidualSignal(
        residual_magnitude=residual_magnitude,
        semantic_consistency=semantic_consistency,
        action_state_coherence=action_state_coherence,
        regime=regime,
        risk_factors=tuple(risk_factors),
        reason_codes=tuple(reason_codes),
        explanation=explanation,
    )


def _classify_regime(
    *,
    alignment: float,
    semantic_consistency: float,
    action_state_coherence: float,
    residual_magnitude: float,
    integrated_confidence: float,
) -> GovernanceRegime:
    """Classify the governance regime from residual signals."""

    # UNKNOWN: insufficient confidence to classify
    if integrated_confidence < 0.05:
        return GovernanceRegime.UNKNOWN

    # DUAL_ANOMALY: both JEPA and runtime are incoherent
    if alignment < _ALIGNMENT_CRITICAL and action_state_coherence < 0.5:
        return GovernanceRegime.DUAL_ANOMALY

    if semantic_consistency < 0.4 and action_state_coherence < 0.4:
        return GovernanceRegime.DUAL_ANOMALY

    # SEMANTIC_SHIFT: ontology/vritti alignment broken
    if alignment < _ALIGNMENT_LOW:
        return GovernanceRegime.SEMANTIC_SHIFT

    # PROCESS_DRIFT: runtime deviates from JEPA-justified behavior
    if action_state_coherence < 0.5 or semantic_consistency < 0.5:
        return GovernanceRegime.PROCESS_DRIFT

    if residual_magnitude > 0.4:
        return GovernanceRegime.PROCESS_DRIFT

    # NORMAL: everything aligned
    return GovernanceRegime.NORMAL


# =========================================================================
# Governance Assessment (top-level)
# =========================================================================

# Regime → governance behavior mapping
_REGIME_ACTIONS = {
    GovernanceRegime.NORMAL: "ALLOW",
    GovernanceRegime.PROCESS_DRIFT: "DEGRADE",
    GovernanceRegime.SEMANTIC_SHIFT: "CONFIRM",
    GovernanceRegime.DUAL_ANOMALY: "HALT",
    GovernanceRegime.UNKNOWN: "HALT",
}

_REGIME_EXECUTION_MODE = {
    GovernanceRegime.NORMAL: None,  # No override
    GovernanceRegime.PROCESS_DRIFT: "CAUTIOUS",
    GovernanceRegime.SEMANTIC_SHIFT: "CONFIRM_REQUIRED",
    GovernanceRegime.DUAL_ANOMALY: "BLOCKED",
    GovernanceRegime.UNKNOWN: "BLOCKED",
}

_REGIME_ESCALATION = {
    GovernanceRegime.NORMAL: None,  # No override
    GovernanceRegime.PROCESS_DRIFT: "NOTIFY",
    GovernanceRegime.SEMANTIC_SHIFT: "CONFIRM",
    GovernanceRegime.DUAL_ANOMALY: "HALT",
    GovernanceRegime.UNKNOWN: "HALT",
}

_REGIME_CONFIDENCE_ADJ = {
    GovernanceRegime.NORMAL: 0.0,
    GovernanceRegime.PROCESS_DRIFT: -0.15,
    GovernanceRegime.SEMANTIC_SHIFT: -0.20,
    GovernanceRegime.DUAL_ANOMALY: -0.40,
    GovernanceRegime.UNKNOWN: -0.50,
}


def assess_governance(
    jepa: JEPACompositeSignal,
    runtime: RuntimeProcessState,
) -> JEPAGovernanceAssessment:
    """Run the full JEPA residual governance assessment.

    This is the top-level entry point. It:
    1. Computes the residual between JEPA composite and runtime state.
    2. Classifies the governance regime.
    3. Maps regime to governance behavior (allow/deny/confirm/halt/degrade).
    4. Produces a full audit-ready assessment.

    Args:
        jepa: JEPA composite signal from build_jepa_composite().
        runtime: Runtime process state from build_runtime_process_state().

    Returns:
        JEPAGovernanceAssessment with regime, action, and full audit payload.
    """
    residual = compute_residual(jepa, runtime)
    regime = residual.regime

    action = _REGIME_ACTIONS[regime]
    exec_override = _REGIME_EXECUTION_MODE[regime]
    esc_override = _REGIME_ESCALATION[regime]
    conf_adj = _REGIME_CONFIDENCE_ADJ[regime]

    # Collect all reason codes
    codes = list(residual.reason_codes)
    codes.append(f"REGIME_{regime.value.upper()}")

    rationale = (
        f"JEPA residual governor: regime={regime.value}, "
        f"action={action}, residual={residual.residual_magnitude:.2f}, "
        f"semantic={residual.semantic_consistency:.2f}, "
        f"coherence={residual.action_state_coherence:.2f}. "
        f"{residual.explanation}"
    )

    return JEPAGovernanceAssessment(
        regime=regime,
        recommended_action=action,
        execution_mode_override=exec_override,
        escalation_override=esc_override,
        confidence_adjustment=conf_adj,
        reason_codes=tuple(codes),
        rationale=rationale,
        jepa_composite=jepa,
        runtime_state=runtime,
        residual=residual,
    )


# =========================================================================
# Convenience: end-to-end assessment
# =========================================================================


def jepa_governance_check(
    *,
    layer_weights: Optional[Dict[str, float]] = None,
    olm_signals: Any = None,
    vritti_result: Any = None,
    vritti_distribution: Optional[Dict[str, float]] = None,
    coherence: float = 0.5,
    score: float = 0.5,
    action_type: str = "",
    tool_name: str = "",
    risk_level: str = "",
    confidence_score: float = 0.5,
    agency_level: str = "FULL",
    requires_confirmation: bool = False,
    execution_mode: str = "",
    escalation_level: str = "NONE",
    session_id: str = "",
    actor_id: str = "",
    capabilities: Sequence[str] = (),
) -> JEPAGovernanceAssessment:
    """One-call convenience for the full JEPA governance pipeline.

    Builds all three layers (ontology, vritti, runtime), constructs the
    JEPA composite, and runs residual assessment.
    """
    ontology = build_ontology_signal(
        layer_weights=layer_weights, olm_signals=olm_signals,
    )
    vritti_sig = build_vritti_signal(
        vritti_result=vritti_result,
        vritti_distribution=vritti_distribution,
        coherence=coherence,
        score=score,
    )
    jepa = build_jepa_composite(ontology, vritti_sig)
    runtime = build_runtime_process_state(
        action_type=action_type,
        tool_name=tool_name,
        risk_level=risk_level,
        confidence_score=confidence_score,
        agency_level=agency_level,
        requires_confirmation=requires_confirmation,
        execution_mode=execution_mode,
        escalation_level=escalation_level,
        session_id=session_id,
        actor_id=actor_id,
        capabilities=capabilities,
    )
    return assess_governance(jepa, runtime)


# =========================================================================
# Canonical safe JEPA wrapper (reusable by both enforcement points)
# =========================================================================


def safe_jepa_governance_check(**kwargs) -> JEPAGovernanceAssessment:
    """Safe wrapper around jepa_governance_check that never raises.

    This is the single canonical entry point for JEPA assessment that
    both GovernanceService and MCPGateway should use. It catches any
    internal error and returns an explicit UNKNOWN-regime assessment
    instead of raising or returning None.

    Returns:
        JEPAGovernanceAssessment — always. On failure, returns an
        explicit UNKNOWN regime with HALT/BLOCKED posture.
    """
    try:
        return jepa_governance_check(**kwargs)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            "JEPA governance check failed (safe wrapper): %s", e
        )
        return _make_unavailable_assessment(str(e), kwargs)


def _make_unavailable_assessment(
    error_msg: str,
    context: Dict[str, Any],
) -> JEPAGovernanceAssessment:
    """Build synthetic UNKNOWN-regime assessment when JEPA cannot compute.

    Used by safe_jepa_governance_check and can be used by MCPGateway
    for fail-closed error handling.
    """
    zero_weights = {l: 0.0 for l in ONTOLOGY_LAYERS}
    zero_dist = {"pramana": 0.0, "viparyaya": 0.0, "vikalpa": 0.0,
                 "smrti": 0.0, "nidra": 1.0}
    ontology = OntologySignal(
        layer_weights=zero_weights, primary_layer="O1_POTENTIAL",
        governance_strength=0.0, execution_strength=0.0,
        confidence=0.0, evidence=f"JEPA unavailable: {error_msg}",
    )
    vritti_sig = VrittiSignal(
        distribution=zero_dist, primary_vritti="nidra",
        coherence=0.0, score=0.0, confidence=0.0,
        evidence=f"JEPA unavailable: {error_msg}",
    )
    composite = JEPACompositeSignal(
        ontology=ontology, vritti=vritti_sig,
        expected_ontology=zero_weights, actual_ontology=zero_weights,
        ontology_vritti_alignment=0.0, integrated_confidence=0.0,
        stability=0.0, summary="JEPA UNAVAILABLE",
        coupling_evidence=("JEPA_ERROR",),
    )
    runtime = build_runtime_process_state(
        action_type=context.get("action_type", ""),
        tool_name=context.get("tool_name", ""),
        risk_level=context.get("risk_level", ""),
        confidence_score=context.get("confidence_score", 0.0),
        agency_level=context.get("agency_level", "FULL"),
        execution_mode=context.get("execution_mode", "BLOCKED"),
        escalation_level=context.get("escalation_level", "HALT"),
        session_id=context.get("session_id", ""),
        actor_id=context.get("actor_id", ""),
        capabilities=context.get("capabilities", ()),
    )
    residual = ResidualSignal(
        residual_magnitude=1.0, semantic_consistency=0.0,
        action_state_coherence=0.0, regime=GovernanceRegime.UNKNOWN,
        risk_factors=(f"JEPA computation error: {error_msg}",),
        reason_codes=("JEPA_UNAVAILABLE", "UNKNOWN_REGIME"),
        explanation=f"JEPA check failed: {error_msg}. Fail-closed.",
    )
    return JEPAGovernanceAssessment(
        regime=GovernanceRegime.UNKNOWN,
        recommended_action="HALT",
        execution_mode_override="BLOCKED",
        escalation_override="HALT",
        confidence_adjustment=-0.50,
        reason_codes=("JEPA_UNAVAILABLE", "UNKNOWN_REGIME"),
        rationale=f"JEPA unavailable: {error_msg}. Fail-closed to HALT.",
        jepa_composite=composite,
        runtime_state=runtime,
        residual=residual,
    )


def apply_jepa_override(
    baseline_decision: str,
    baseline_eligible: bool,
    assessment: JEPAGovernanceAssessment,
) -> Dict[str, Any]:
    """Shared JEPA override logic for both GovernanceService and MCPGateway.

    Applies the JEPA assessment to a baseline governance decision.
    JEPA can only make decisions STRICTER, never more permissive.

    Uses the full assessment fields:
    - recommended_action
    - confidence_adjustment
    - execution_mode_override
    - escalation_override

    Args:
        baseline_decision: Baseline governance decision ("ALLOW", "DENY", "DEFER")
        baseline_eligible: Whether the request was eligible before JEPA
        assessment: Full JEPA governance assessment

    Returns:
        Dict with keys:
        - decision: new decision string
        - eligible: new eligible flag
        - overrode: whether JEPA changed the decision
        - regime: assessment regime value
        - reason_codes: assessment reason codes
        - confidence_adjustment: assessment confidence adjustment
        - execution_mode_override: assessment execution mode override
        - escalation_override: assessment escalation override
        - recommended_action: assessment recommended action
    """
    regime = assessment.regime
    recommended = assessment.recommended_action
    new_decision = baseline_decision
    new_eligible = baseline_eligible

    if regime == GovernanceRegime.NORMAL:
        pass  # No change
    elif recommended in ("HALT", "DENY"):
        new_decision = "DENY"
        new_eligible = False
    elif recommended in ("DEGRADE", "CONFIRM"):
        if baseline_decision == "ALLOW":
            new_decision = "DEFER"
            new_eligible = False
    else:
        # Fallback: use execution_mode_override / escalation_override
        if assessment.execution_mode_override == "BLOCKED":
            new_decision = "DENY"
            new_eligible = False
        elif assessment.escalation_override == "HALT":
            new_decision = "DENY"
            new_eligible = False

    # Invariant: decision != ALLOW => eligible must be False.
    # This covers the case where baseline was already DENY/DEFER
    # but baseline_eligible was True (shouldn't happen, but enforce).
    if new_decision != "ALLOW":
        new_eligible = False

    return {
        "decision": new_decision,
        "eligible": new_eligible,
        "overrode": new_decision != baseline_decision,
        "regime": assessment.regime.value,
        "reason_codes": list(assessment.reason_codes),
        "confidence_adjustment": assessment.confidence_adjustment,
        "execution_mode_override": assessment.execution_mode_override,
        "escalation_override": assessment.escalation_override,
        "recommended_action": assessment.recommended_action,
    }


# =========================================================================
# Helpers
# =========================================================================


_OLM_LAYER_ATTR_MAP = {
    "O1_POTENTIAL": "potential_weight",
    "O2_IDENTITY": "identity_weight",
    "O3_EXECUTION": "execution_weight",
    "O4_STRUCTURE": "structure_weight",
    "O5_COGNITION": "cognition_weight",
    "O6_AGENCY": "agency_weight",
    "O7_REASONING": "reasoning_weight",
    "O8_PURPOSE": "purpose_weight",
    "O9_WITNESSES": "witness_weight",
    "O10_UNIFYING": "unifying_weight",
    "O11_INTEGRATION": "integration_weight",
    "O12_ABSOLVING": "absolving_weight",
}


def _olm_layer_to_attr(layer: str) -> str:
    """Map OLM layer name to OLMGovernanceSignals attribute name.

    Robust to ontology extension: unknown layers produce a
    deterministic snake_case attribute name rather than KeyError.
    """
    attr = _OLM_LAYER_ATTR_MAP.get(layer)
    if attr is not None:
        return attr
    # Fallback: derive attr name from layer name (e.g. "O13_NEW" → "new_weight")
    parts = layer.split("_", 1)
    suffix = parts[1].lower() if len(parts) > 1 else parts[0].lower()
    return f"{suffix}_weight"


def _get_primary_coupling(vritti_name: str) -> str:
    """Get the ontology layer with strongest coupling for a vritti."""
    return {
        "pramana": "O7_REASONING",
        "viparyaya": "O6_AGENCY",
        "vikalpa": "O5_COGNITION",
        "smrti": "O3_EXECUTION",
        "nidra": "O1_POTENTIAL",
    }.get(vritti_name, "O1_POTENTIAL")


def _build_explanation(
    *,
    regime: GovernanceRegime,
    residual_magnitude: float,
    semantic_consistency: float,
    action_state_coherence: float,
    risk_factors: List[str],
    jepa: JEPACompositeSignal,
    runtime: RuntimeProcessState,
) -> str:
    """Build human-readable explanation of the residual."""
    parts = [f"Regime: {regime.value}."]

    if regime == GovernanceRegime.NORMAL:
        parts.append(
            f"JEPA state [{jepa.vritti.primary_vritti}|{jepa.ontology.primary_layer}] "
            f"is consistent with {runtime.action_category.value} action "
            f"on '{runtime.tool_name}'."
        )
    elif regime == GovernanceRegime.PROCESS_DRIFT:
        parts.append(
            f"Runtime behavior ({runtime.action_category.value} on '{runtime.tool_name}') "
            f"drifts from JEPA state [{jepa.vritti.primary_vritti}|{jepa.ontology.primary_layer}]."
        )
    elif regime == GovernanceRegime.SEMANTIC_SHIFT:
        parts.append(
            f"Ontology-vritti alignment is low ({jepa.ontology_vritti_alignment:.2f}), "
            f"suggesting a semantic or cognitive mode shift."
        )
    elif regime == GovernanceRegime.DUAL_ANOMALY:
        parts.append(
            "Both JEPA state and runtime behavior indicate serious incoherence."
        )
    elif regime == GovernanceRegime.UNKNOWN:
        parts.append("Insufficient signal data to classify regime. Fail closed.")

    if risk_factors:
        parts.append(f"Risk factors: {'; '.join(risk_factors[:3])}.")

    return " ".join(parts)


# =========================================================================
# Shared signal approximation (used by GovernanceService and MCP Gateway)
# =========================================================================


def approximate_layer_weights(
    *,
    quality: float = 0.5,
    coherence: float = 0.5,
    internal_consistency: float = 0.5,
    goal_alignment: float = 0.5,
    trajectory_confidence: float = 0.5,
    overall_confidence: float = 0.5,
) -> Dict[str, float]:
    """Approximate OLM layer weights from available governance signals.

    Canonical shared implementation used by both GovernanceService and
    SafeMCPGateway so that equivalent inputs produce identical JEPA
    composites across enforcement points.
    """
    return {
        "O1_POTENTIAL": 0.3,
        "O2_IDENTITY": internal_consistency * 0.8,
        "O3_EXECUTION": overall_confidence * 0.7,
        "O4_STRUCTURE": coherence * 0.6,
        "O5_COGNITION": quality * 0.8,
        "O6_AGENCY": goal_alignment * 0.7,
        "O7_REASONING": quality * 0.9,
        "O8_PURPOSE": goal_alignment * 0.8,
        "O9_WITNESSES": trajectory_confidence * 0.6,
        "O10_UNIFYING": coherence * 0.7,
        "O11_INTEGRATION": overall_confidence * 0.5,
        "O12_ABSOLVING": trajectory_confidence * 0.4,
    }


def approximate_vritti(
    *,
    quality: float = 0.5,
    coherence: float = 0.5,
    overall_confidence: float = 0.5,
) -> Dict[str, float]:
    """Approximate vritti distribution from available governance signals.

    Canonical shared implementation. The distribution is always
    normalizable because at least one component (pramana or nidra)
    is positive for any non-negative inputs.  If all inputs are 0.0,
    nidra = 0.3 dominates, producing a valid dormancy distribution.
    """
    pramana = min(1.0, quality * 0.6 + coherence * 0.4)
    viparyaya = max(0.0, 0.5 - quality * 0.8)
    vikalpa = max(0.0, 0.4 - coherence * 0.5) * min(1.0, quality + 0.3)
    nidra = max(0.0, 0.3 - overall_confidence * 0.5)

    total = pramana + viparyaya + vikalpa + nidra
    if total <= 0:
        # All signals exactly zero (mathematically unlikely but possible
        # with quality=coherence=overall_confidence=0.0 → pramana=0,
        # viparyaya=0.5, vikalpa=0.12, nidra=0.3 → total>0).
        # Defensive: treat as full dormancy.
        return {"pramana": 0.0, "viparyaya": 0.0, "vikalpa": 0.0,
                "smrti": 0.0, "nidra": 1.0}
    return {
        "pramana": pramana / total,
        "viparyaya": viparyaya / total,
        "vikalpa": vikalpa / total,
        "smrti": 0.0,
        "nidra": nidra / total,
    }


# =========================================================================
# Exports
# =========================================================================

__all__ = [
    # Enums
    "GovernanceRegime",
    "RuntimeActionCategory",
    # Signal structures
    "OntologySignal",
    "VrittiSignal",
    "JEPACompositeSignal",
    "RuntimeProcessState",
    "ResidualSignal",
    "JEPAGovernanceAssessment",
    # Builders
    "build_ontology_signal",
    "build_vritti_signal",
    "build_jepa_composite",
    "build_runtime_process_state",
    # Governor
    "compute_residual",
    "assess_governance",
    "jepa_governance_check",
    # Safe wrappers (canonical entry points for enforcement)
    "safe_jepa_governance_check",
    "apply_jepa_override",
    # Shared signal approximation
    "approximate_layer_weights",
    "approximate_vritti",
]
