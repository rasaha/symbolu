"""
OLM v1.0 Engine Module

Deterministic Ontological Layer Mapper engine that maps symbol dynamics
to the 5+5 ontological layer model for constraint-based processing.

5+5 Ontological Layer Architecture (Patent-Aligned):

Lower 5 — Execution / Manifestation Layers:
    O1 — Action: Immediate execution pressure; raw acts and impulses
    O2 — Tagging: Classification and labeling; assigns type without meaning
    O3 — Forming: Structural shaping and pattern formation
    O4 — Thinking: Rule-based internal transformation; mechanical only
    O5 — Directing: Trajectory steering and vector control

Upper 5 — Governance / Coherence Layers:
    O6 — Reasoning: Logical consistency and admissibility checks
    O7 — Purposing: Constraint alignment toward targets (Phase-7)
    O8 — Meta-Observing: Witness layer; damping, stabilization
    O9 — Unifying: Integration and coherence; contradiction removal
    O10 — Absolving: Termination, dissolution, or release

Key Architectural Principles (Do Not Violate):
- There is no active/passive mode
- There is no controller deciding when layers engage
- All layers exist simultaneously
- Behavior emerges from ontological placement + constraints
- Upper layers never generate, only constrain or terminate
- The system is deterministic, non-semantic, and non-learning

Usage:
    engine = OLMEngine()
    olm_map = engine.build_map(olm_input)
"""

from typing import Dict, List, Tuple, Final, Tuple as TypingTuple, Optional

from .models import (
    OLMInput,
    OntologicalLayerMap,
    LOWER_ONTOLOGICAL_LAYERS,
    UPPER_ONTOLOGICAL_LAYERS,
    ALL_ONTOLOGICAL_LAYERS,
    LEGACY_ASPECT_TO_LAYER,
)

# =============================================================================
# CONSTANTS
# =============================================================================

# Lower-tier anchors: survival, exchange, challenge-focused
LOWER_ANCHORS: Final[TypingTuple[str, ...]] = (
    "Needs",
    "Exchange",
    "Challenge",
)

# Upper-tier anchors: connection, meaning, collective-focused
UPPER_ANCHORS: Final[TypingTuple[str, ...]] = (
    "Belonging",
    "Relation",
    "Change",
    "Meaning",
    "Role",
    "Collective",
)

# Entropy bounds
H_D_MAX: Final[float] = 2.302585093  # ln(10)
H_G_MAX: Final[float] = 1.098612289  # ln(3)
H_K_MAX: Final[float] = 1.609437912  # ln(5)

# Domain classifications
TASK_DOMAINS: Final[TypingTuple[str, ...]] = (
    "task",
    "code",
    "math",
    "lookup",
)

REFLECTIVE_DOMAINS: Final[TypingTuple[str, ...]] = (
    "therapy",
    "philosophy",
    "spiritual",
    "identity",
)


class OLMEngine:
    """
    Deterministic Ontological Layer Mapper.

    Maps symbol dynamics to the 5+5 ontological layer model
    for constraint-based processing by downstream engines.

    This is a STRUCTURAL ONTOLOGY mapper, not a behavioral mode system:
    - All layers exist simultaneously
    - Processing is constrained by ontological layer placement
    - Lower layers (O1-O5) execute symbol dynamics
    - Upper layers (O6-O10) enforce coherence, alignment, and termination
    - No active/passive modes or controller-based task switching

    Attributes:
        layer_threshold: Minimum weight for a layer to be considered dominant.
                        Layers below this are considered suppressed.
        tension_threshold: Minimum combined signal strength to trigger tension detection.
                          Higher values mean stricter tension detection.

    Example:
        engine = OLMEngine(layer_threshold=0.10, tension_threshold=0.25)
        olm_map = engine.build_map(olm_input)
    """

    # Entropy regime thresholds
    ENTROPY_LOW_THRESHOLD: float = 0.33
    ENTROPY_HIGH_THRESHOLD: float = 0.66

    def __init__(
        self,
        *,
        layer_threshold: float = 0.10,
        tension_threshold: float = 0.25,
    ) -> None:
        """
        Initialize the OLM engine with configurable thresholds.

        Args:
            layer_threshold: Minimum weight for dominant layer classification.
            tension_threshold: Minimum strength for tension zone detection.
        """
        self.layer_threshold = layer_threshold
        self.tension_threshold = tension_threshold

    def build_map(self, olm_input: OLMInput) -> OntologicalLayerMap:
        """
        Main entrypoint - builds an ontological layer map from input signals.

        Processing is constrained by ontological layer placement.
        Lower layers execute symbol dynamics; upper layers enforce
        coherence, alignment, and termination.

        Processing Steps:
        1. Normalize layer_weights to sum=1 (defensive)
        2. Split into execution (O1-O5) and governance (O6-O10) profiles
        3. Classify layers → dominant_layers, suppressed_layers
        4. Normalize anchor_scores → anchor_profile
        5. Compute entropy_profile (H_D_norm, H_G_norm, H_K_norm, entropy_mix, regime)
        6. Detect tension_zones between layer groups
        7. Generate resolution_constraints for downstream engines
        8. Compute layer_balance (execution vs governance ratio)

        Args:
            olm_input: OLMInput containing all routing signals.

        Returns:
            OntologicalLayerMap with structured ontological placement data.
        """
        # Convert legacy aspect names if present
        layer_weights = self._convert_legacy_aspects(olm_input.layer_weights)

        # Step 1: Normalize layer weights
        normalized_layers = self._normalize_probs(layer_weights)

        # Step 2: Split into execution and governance profiles
        execution_profile = {
            layer: normalized_layers.get(layer, 0.0)
            for layer in LOWER_ONTOLOGICAL_LAYERS
        }
        governance_profile = {
            layer: normalized_layers.get(layer, 0.0)
            for layer in UPPER_ONTOLOGICAL_LAYERS
        }

        # Normalize each profile separately
        execution_profile = self._normalize_probs(execution_profile)
        governance_profile = self._normalize_probs(governance_profile)

        # Step 3: Classify layers into dominant and suppressed
        dominant_layers, suppressed_layers = self._classify_layers(normalized_layers)

        # Step 4: Normalize anchor scores to create anchor profile
        anchor_profile = self._normalize_probs(olm_input.anchor_scores)

        # Step 5: Compute entropy profile
        entropy_profile = self._compute_entropy_profile(
            olm_input.H_D,
            olm_input.H_G,
            olm_input.H_K,
        )

        # Step 6: Compute layer balance (execution vs governance)
        layer_balance = self._compute_layer_balance(normalized_layers)

        # Step 7: Detect tension zones
        tension_zones = self._detect_tension_zones(
            normalized_layers,
            anchor_profile,
            entropy_profile,
            olm_input.tier,
            layer_balance,
        )

        # Step 8: Generate resolution constraints
        resolution_constraints = self._generate_resolution_constraints(
            dominant_layers,
            suppressed_layers,
            anchor_profile,
            entropy_profile,
            tension_zones,
            olm_input.tier,
            olm_input.domain,
            olm_input.flow_mode,
            layer_balance,
        )

        return OntologicalLayerMap(
            dominant_layers=dominant_layers,
            suppressed_layers=suppressed_layers,
            execution_profile=execution_profile,
            governance_profile=governance_profile,
            anchor_profile=anchor_profile,
            entropy_profile=entropy_profile,
            tension_zones=tension_zones,
            resolution_constraints=resolution_constraints,
            tier=olm_input.tier,
            domain=olm_input.domain,
            layer_balance=round(layer_balance, 4),
        )

    def _convert_legacy_aspects(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        Convert legacy aspect names to ontological layer names.

        This provides backward compatibility with systems still using
        the old aspect nomenclature (Execution, Identity, Form, etc.)

        Args:
            weights: Dictionary with aspect names (legacy or new).

        Returns:
            Dictionary with ontological layer names (O1-O10).
        """
        converted = {}
        for key, value in weights.items():
            if key in LEGACY_ASPECT_TO_LAYER:
                converted[LEGACY_ASPECT_TO_LAYER[key]] = value
            elif key in ALL_ONTOLOGICAL_LAYERS:
                converted[key] = value
            else:
                # Unknown key - skip (defensive)
                pass
        return converted

    def _normalize_probs(self, probs: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize a probability dictionary to sum to 1.0.

        Handles edge cases:
        - Empty dict → empty dict
        - All zeros → uniform distribution
        - Negative values → clamped to 0

        Args:
            probs: Dictionary of name → probability mappings.

        Returns:
            Normalized dictionary where values sum to 1.0.
        """
        if not probs:
            return {}

        # Clamp negative values to 0
        clamped = {k: max(0.0, v) for k, v in probs.items()}

        total = sum(clamped.values())

        if total <= 0:
            # All zeros or empty: return uniform distribution
            n = len(clamped)
            return {k: 1.0 / n for k in clamped}

        return {k: v / total for k, v in clamped.items()}

    def _classify_layers(
        self,
        normalized_layers: Dict[str, float],
    ) -> Tuple[List[str], List[str]]:
        """
        Classify ontological layers into dominant and suppressed based on threshold.

        Dominant layers are sorted by weight (highest first).
        Suppressed layers are those below the threshold.

        All layers exist simultaneously in the ontology;
        this classification describes relative activation, not mode switching.

        Args:
            normalized_layers: Normalized layer weights.

        Returns:
            Tuple of (dominant_layers, suppressed_layers) lists.
        """
        dominant: List[Tuple[str, float]] = []
        suppressed: List[str] = []

        for layer, weight in normalized_layers.items():
            if weight >= self.layer_threshold:
                dominant.append((layer, weight))
            else:
                suppressed.append(layer)

        # Sort dominant by weight descending
        dominant.sort(key=lambda x: x[1], reverse=True)
        dominant_names = [name for name, _ in dominant]

        return dominant_names, suppressed

    def _compute_layer_balance(
        self,
        normalized_layers: Dict[str, float],
    ) -> float:
        """
        Compute the balance between execution and governance layers.

        Returns a ratio where:
        - 0.0 = pure governance (O6-O10 dominant)
        - 0.5 = balanced
        - 1.0 = pure execution (O1-O5 dominant)

        This describes ontological placement, not behavioral mode.

        Args:
            normalized_layers: Normalized layer weights.

        Returns:
            Balance ratio [0, 1].
        """
        execution_sum = sum(
            normalized_layers.get(layer, 0.0)
            for layer in LOWER_ONTOLOGICAL_LAYERS
        )
        governance_sum = sum(
            normalized_layers.get(layer, 0.0)
            for layer in UPPER_ONTOLOGICAL_LAYERS
        )

        total = execution_sum + governance_sum
        if total <= 0:
            return 0.5  # Balanced if no signal

        return execution_sum / total

    def _compute_entropy_profile(
        self,
        H_D: float,
        H_G: float,
        H_K: float,
    ) -> Dict[str, float]:
        """
        Compute entropy profile with normalized values and regime classification.

        Normalizes each entropy measure to [0, 1] range and computes:
        - Combined entropy mix (weighted average)
        - Entropy regime classification ("low", "medium", "high")

        Args:
            H_D: Dimensional entropy [0, ln(10)]
            H_G: Guna entropy [0, ln(3)]
            H_K: Kosha entropy [0, ln(5)]

        Returns:
            Dictionary with normalized values, mix, and regime.
        """
        # Normalize to [0, 1]
        H_D_norm = min(1.0, max(0.0, H_D / H_D_MAX)) if H_D_MAX > 0 else 0.0
        H_G_norm = min(1.0, max(0.0, H_G / H_G_MAX)) if H_G_MAX > 0 else 0.0
        H_K_norm = min(1.0, max(0.0, H_K / H_K_MAX)) if H_K_MAX > 0 else 0.0

        # Weighted entropy mix
        # H_D has higher weight (0.5) as dimensional entropy, H_G (0.3), H_K (0.2)
        entropy_mix = 0.5 * H_D_norm + 0.3 * H_G_norm + 0.2 * H_K_norm

        # Classify regime
        if entropy_mix < self.ENTROPY_LOW_THRESHOLD:
            regime = "low"
        elif entropy_mix < self.ENTROPY_HIGH_THRESHOLD:
            regime = "medium"
        else:
            regime = "high"

        return {
            "H_D_norm": round(H_D_norm, 4),
            "H_G_norm": round(H_G_norm, 4),
            "H_K_norm": round(H_K_norm, 4),
            "entropy_mix": round(entropy_mix, 4),
            "regime": regime,
        }

    def _detect_tension_zones(
        self,
        normalized_layers: Dict[str, float],
        anchor_profile: Dict[str, float],
        entropy_profile: Dict[str, float],
        tier: str,
        layer_balance: float,
    ) -> List[str]:
        """
        Detect tension zones between ontological layer groups.

        Identifies structural tensions in the ontological placement:
        - execution_governance_gap: High O1-O5 with weak O6-O10 constraints
        - governance_without_grounding: High O6-O10 without O1-O3 foundation
        - action_without_direction: High O1 without O5 trajectory control
        - purpose_without_coherence: High O7 without O9 integration
        - boundary_dissolution_risk: High O10 with active lower layers
        - grounding_deficit: Abstract layers active without concrete foundation

        These are STRUCTURAL tensions, not behavioral mode conflicts.

        Args:
            normalized_layers: Normalized layer weights.
            anchor_profile: Normalized anchor profile.
            entropy_profile: Computed entropy profile.
            tier: Routing tier ("lower", "upper", "hybrid").
            layer_balance: Execution vs governance ratio.

        Returns:
            List of tension zone labels.
        """
        tensions: List[str] = []
        entropy_mix = entropy_profile.get("entropy_mix", 0.0)
        regime = entropy_profile.get("regime", "low")

        # Helper to get values with defaults
        def get_layer(name: str) -> float:
            return normalized_layers.get(name, 0.0)

        def get_anchor(name: str) -> float:
            return anchor_profile.get(name, 0.0)

        # Compute aggregate scores for layer groups
        execution_sum = sum(get_layer(l) for l in LOWER_ONTOLOGICAL_LAYERS)
        governance_sum = sum(get_layer(l) for l in UPPER_ONTOLOGICAL_LAYERS)
        lower_anchor_sum = sum(get_anchor(a) for a in LOWER_ANCHORS)
        upper_anchor_sum = sum(get_anchor(a) for a in UPPER_ANCHORS)

        # Pattern 1: execution_governance_gap
        # High execution layers without governance constraints
        if execution_sum > 2 * governance_sum and governance_sum < self.tension_threshold:
            tensions.append("execution_governance_gap")

        # Pattern 2: governance_without_grounding
        # High governance without grounding in O1-O3
        grounding_sum = get_layer("O1_action") + get_layer("O2_tagging") + get_layer("O3_forming")
        if governance_sum > 2 * self.tension_threshold and grounding_sum < self.tension_threshold:
            tensions.append("governance_without_grounding")

        # Pattern 3: action_without_direction
        # High O1 action pressure without O5 trajectory control
        if get_layer("O1_action") > self.tension_threshold and get_layer("O5_directing") < 0.5 * self.tension_threshold:
            tensions.append("action_without_direction")

        # Pattern 4: purpose_without_coherence
        # High O7 purposing without O9 unifying integration
        if get_layer("O7_purposing") > self.tension_threshold and get_layer("O9_unifying") < 0.5 * self.tension_threshold:
            tensions.append("purpose_without_coherence")

        # Pattern 5: boundary_dissolution_risk
        # High O10 absolving with still-active lower layers
        if get_layer("O10_absolving") > self.tension_threshold and execution_sum > 2 * self.tension_threshold:
            tensions.append("boundary_dissolution_risk")

        # Pattern 6: grounding_deficit
        # Similar to pattern 2 but with anchor context
        if (
            governance_sum > 3 * self.tension_threshold
            and get_layer("O1_action") < self.tension_threshold
            and get_layer("O3_forming") < self.tension_threshold
        ):
            tensions.append("grounding_deficit")

        # Pattern 7: needs_without_execution
        # High Needs anchor but low O1 action layer
        needs_score = get_anchor("Needs")
        if needs_score > self.tension_threshold and get_layer("O1_action") < self.tension_threshold:
            tensions.append("needs_without_execution")

        # Pattern 8: meaning_without_purpose
        # High Meaning anchor but low O7 purposing layer
        meaning_score = get_anchor("Meaning")
        if meaning_score > self.tension_threshold and get_layer("O7_purposing") < self.tension_threshold:
            tensions.append("meaning_without_purpose")

        # Pattern 9: high_entropy_destabilization
        # Very high entropy with governance layers suppressed
        if regime == "high" and get_layer("O8_meta_observing") < self.tension_threshold:
            tensions.append("high_entropy_destabilization")

        return tensions

    def _generate_resolution_constraints(
        self,
        dominant_layers: List[str],
        suppressed_layers: List[str],
        anchor_profile: Dict[str, float],
        entropy_profile: Dict[str, float],
        tension_zones: List[str],
        tier: str,
        domain: str,
        flow_mode: str,
        layer_balance: float,
    ) -> List[str]:
        """
        Generate deterministic resolution constraints for downstream engines.

        Constraints are structured labels that guide processing:
        - Layer-based constraints (execution_pressure, governance_check)
        - Entropy-based constraints (high_entropy_damping, low_entropy_stability)
        - Tension-based constraints (derived from tension zones)
        - Domain-based constraints (reflective_domain, task_domain)

        These constraints describe ontological placement, not behavioral modes.

        Args:
            dominant_layers: List of dominant layers.
            suppressed_layers: List of suppressed layers.
            anchor_profile: Normalized anchor profile.
            entropy_profile: Computed entropy profile.
            tension_zones: Detected tension zones.
            tier: Routing tier.
            domain: Domain classification.
            flow_mode: Flow mode specification.
            layer_balance: Execution vs governance ratio.

        Returns:
            List of resolution constraint labels.
        """
        constraints: List[str] = []
        regime = entropy_profile.get("regime", "low")
        entropy_mix = entropy_profile.get("entropy_mix", 0.0)

        # Layer balance constraints
        if layer_balance > 0.7:
            constraints.append("execution_layer_dominant")
            constraints.append("require_governance_check")
        elif layer_balance < 0.3:
            constraints.append("governance_layer_dominant")
            constraints.append("require_grounding_check")
        else:
            constraints.append("balanced_layer_profile")

        # Tier-based constraints
        if tier == "upper":
            constraints.append("upper_tier_processing")
            if "O7_purposing" in dominant_layers or "O10_absolving" in dominant_layers:
                constraints.append("meaning_constraint_active")
        elif tier == "lower":
            constraints.append("lower_tier_processing")
            if "O1_action" in dominant_layers or "O3_forming" in dominant_layers:
                constraints.append("execution_constraint_active")
        else:  # hybrid
            constraints.append("hybrid_tier_processing")

        # Entropy-based constraints
        if regime == "high":
            constraints.append("high_entropy_damping")
            constraints.append("O8_meta_observing_required")
        elif regime == "low":
            constraints.append("low_entropy_stability")
            constraints.append("confident_execution_permitted")
        else:  # medium
            constraints.append("moderate_entropy_adaptive")

        # Flow mode constraints
        if flow_mode == "inner_priority":
            constraints.append("inner_flow_constraint")
        elif flow_mode == "outer_only":
            constraints.append("outer_flow_constraint")
        else:  # outer_plus_inner
            constraints.append("balanced_flow_constraint")

        # Domain-based constraints
        if domain in REFLECTIVE_DOMAINS:
            constraints.append("reflective_domain_active")
            if domain == "therapy":
                constraints.append("therapeutic_boundary_constraint")
            elif domain == "spiritual":
                constraints.append("spiritual_openness_constraint")
            elif domain == "identity":
                constraints.append("identity_exploration_constraint")
        elif domain in TASK_DOMAINS:
            constraints.append("task_domain_active")
            if domain == "code":
                constraints.append("technical_precision_constraint")
            elif domain == "math":
                constraints.append("logical_rigor_constraint")

        # Tension-derived constraints
        for tension in tension_zones:
            if tension == "execution_governance_gap":
                constraints.append("require_governance_layer_activation")
            elif tension == "governance_without_grounding":
                constraints.append("require_grounding_layer_activation")
            elif tension == "action_without_direction":
                constraints.append("require_O5_directing")
            elif tension == "purpose_without_coherence":
                constraints.append("require_O9_unifying")
            elif tension == "boundary_dissolution_risk":
                constraints.append("O10_absolving_check_required")
            elif tension == "grounding_deficit":
                constraints.append("add_concrete_grounding")
            elif tension == "needs_without_execution":
                constraints.append("activate_O1_action")
            elif tension == "meaning_without_purpose":
                constraints.append("activate_O7_purposing")
            elif tension == "high_entropy_destabilization":
                constraints.append("activate_O8_meta_observing")

        # Layer-specific constraints based on dominant layers
        for layer in dominant_layers[:3]:  # Top 3 dominant
            if layer == "O1_action":
                constraints.append("immediate_execution_pressure")
            elif layer == "O2_tagging":
                constraints.append("classification_active")
            elif layer == "O3_forming":
                constraints.append("pattern_formation_active")
            elif layer == "O4_thinking":
                constraints.append("mechanical_transformation_active")
            elif layer == "O5_directing":
                constraints.append("trajectory_control_active")
            elif layer == "O6_reasoning":
                constraints.append("admissibility_check_active")
            elif layer == "O7_purposing":
                constraints.append("constraint_alignment_active")
            elif layer == "O8_meta_observing":
                constraints.append("witness_damping_active")
            elif layer == "O9_unifying":
                constraints.append("coherence_integration_active")
            elif layer == "O10_absolving":
                constraints.append("termination_boundary_active")

        # Anchor-based constraints (significant anchors)
        for anchor, score in anchor_profile.items():
            if score > 0.2:
                if anchor == "Needs":
                    constraints.append("practical_needs_constraint")
                elif anchor == "Meaning":
                    constraints.append("meaning_seeking_constraint")
                elif anchor == "Challenge":
                    constraints.append("growth_challenge_constraint")
                elif anchor == "Belonging":
                    constraints.append("belonging_constraint")
                elif anchor == "Collective":
                    constraints.append("collective_orientation_constraint")

        # Remove duplicates while preserving order
        seen = set()
        unique_constraints = []
        for constraint in constraints:
            if constraint not in seen:
                seen.add(constraint)
                unique_constraints.append(constraint)

        return unique_constraints

    def get_statistics(self) -> Dict[str, float]:
        """
        Get engine configuration statistics.

        Returns:
            Dictionary with threshold configuration.
        """
        return {
            "layer_threshold": self.layer_threshold,
            "tension_threshold": self.tension_threshold,
            "entropy_low_threshold": self.ENTROPY_LOW_THRESHOLD,
            "entropy_high_threshold": self.ENTROPY_HIGH_THRESHOLD,
        }


# Module-level singleton for convenience
_olm_engine: Optional[OLMEngine] = None


def get_olm_engine() -> OLMEngine:
    """
    Get singleton OLM engine instance.

    Returns:
        Shared OLMEngine instance.
    """
    global _olm_engine
    if _olm_engine is None:
        _olm_engine = OLMEngine()
    return _olm_engine
