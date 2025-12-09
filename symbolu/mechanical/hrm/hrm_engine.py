"""
HRM v1.0 Engine Module

Deterministic High-Resolution Mapper engine that transforms coarse TTOR + Aspect/Anchor
inputs into a high-resolution cognitive map for Fusion/DHA engines.

Key Features:
- Pure deterministic processing (no LLM, no randomness)
- Conflict zone detection between aspects and anchors
- Entropy regime classification
- Resolution hint generation

Usage:
    engine = HRMEngine()
    hrm_map = engine.build_map(hrm_input)
"""

from typing import Dict, List, Tuple, Final, Tuple as TypingTuple

from .models import HRMInput, HighResolutionMap

# =============================================================================
# CONSTANTS (mirrored from TTOR to avoid circular imports)
# =============================================================================
# These constants are defined here to avoid importing from
# symbolu.mechanical.pipeline.ttor.constants which triggers heavy pipeline imports.
# Values must stay in sync with TTOR constants module.

# Lower-tier aspects: operational, concrete, identity-focused
LOWER_ASPECTS: Final[TypingTuple[str, ...]] = (
    "Execution",
    "Identity",
    "Form",
    "Cognition",
)

# Upper-tier aspects: abstract, meaning-focused, transcendent
UPPER_ASPECTS: Final[TypingTuple[str, ...]] = (
    "Agency",
    "Reasoning",
    "Purpose",
    "Observation",
    "Core",
    "Universal",
)

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


class HRMEngine:
    """
    Deterministic High-Resolution Mapper.

    Takes coarse TTOR + Aspect/Anchor inputs and produces a HighResolutionMap
    for Fusion/DHA engines to use for deeper but still deterministic reasoning.

    Attributes:
        aspect_threshold: Minimum probability for an aspect to be considered dominant.
                         Aspects below this are considered suppressed.
        conflict_threshold: Minimum combined signal strength to trigger conflict detection.
                           Higher values mean stricter conflict detection.

    Example:
        engine = HRMEngine(aspect_threshold=0.15, conflict_threshold=0.25)
        hrm_map = engine.build_map(hrm_input)
    """

    # Entropy regime thresholds
    ENTROPY_LOW_THRESHOLD: float = 0.33
    ENTROPY_HIGH_THRESHOLD: float = 0.66

    def __init__(
        self,
        *,
        aspect_threshold: float = 0.15,
        conflict_threshold: float = 0.25,
    ) -> None:
        """
        Initialize the HRM engine with configurable thresholds.

        Args:
            aspect_threshold: Minimum probability for dominant aspect classification.
            conflict_threshold: Minimum strength for conflict zone detection.
        """
        self.aspect_threshold = aspect_threshold
        self.conflict_threshold = conflict_threshold

    def build_map(self, hrm_input: HRMInput) -> HighResolutionMap:
        """
        Main entrypoint - builds a high-resolution cognitive map from input signals.

        Processing Steps:
        1. Normalize aspect_probs to sum=1 (defensive)
        2. Rank aspects → dominant_aspects, suppressed_aspects
        3. Normalize anchor_scores → anchor_profile
        4. Compute entropy_profile (H_D_norm, H_G_norm, H_K_norm, entropy_mix, regime)
        5. Detect conflict_zones between aspects and anchors
        6. Generate resolution_hints for Fusion/DHA

        Args:
            hrm_input: HRMInput containing all routing signals.

        Returns:
            HighResolutionMap with structured cognitive mapping data.
        """
        # Step 1: Normalize aspect probabilities
        normalized_aspects = self._normalize_probs(hrm_input.aspect_probs)

        # Step 2: Classify aspects into dominant and suppressed
        dominant_aspects, suppressed_aspects = self._classify_aspects(normalized_aspects)

        # Step 3: Normalize anchor scores to create anchor profile
        anchor_profile = self._normalize_probs(hrm_input.anchor_scores)

        # Step 4: Compute entropy profile
        entropy_profile = self._compute_entropy_profile(
            hrm_input.H_D,
            hrm_input.H_G,
            hrm_input.H_K,
        )

        # Step 5: Detect conflict zones
        conflict_zones = self._detect_conflict_zones(
            normalized_aspects,
            anchor_profile,
            entropy_profile,
            hrm_input.tier,
        )

        # Step 6: Generate resolution hints
        resolution_hints = self._generate_resolution_hints(
            dominant_aspects,
            suppressed_aspects,
            anchor_profile,
            entropy_profile,
            conflict_zones,
            hrm_input.tier,
            hrm_input.domain,
            hrm_input.flow_mode,
        )

        return HighResolutionMap(
            dominant_aspects=dominant_aspects,
            suppressed_aspects=suppressed_aspects,
            anchor_profile=anchor_profile,
            entropy_profile=entropy_profile,
            conflict_zones=conflict_zones,
            resolution_hints=resolution_hints,
            tier=hrm_input.tier,
            domain=hrm_input.domain,
        )

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

    def _classify_aspects(
        self,
        normalized_aspects: Dict[str, float],
    ) -> Tuple[List[str], List[str]]:
        """
        Classify aspects into dominant and suppressed based on threshold.

        Dominant aspects are sorted by probability (highest first).
        Suppressed aspects are those below the threshold.

        Args:
            normalized_aspects: Normalized aspect probabilities.

        Returns:
            Tuple of (dominant_aspects, suppressed_aspects) lists.
        """
        dominant: List[Tuple[str, float]] = []
        suppressed: List[str] = []

        for aspect, prob in normalized_aspects.items():
            if prob >= self.aspect_threshold:
                dominant.append((aspect, prob))
            else:
                suppressed.append(aspect)

        # Sort dominant by probability descending
        dominant.sort(key=lambda x: x[1], reverse=True)
        dominant_names = [name for name, _ in dominant]

        return dominant_names, suppressed

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

        # Weighted entropy mix (same formula as TTOR)
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

    def _detect_conflict_zones(
        self,
        normalized_aspects: Dict[str, float],
        anchor_profile: Dict[str, float],
        entropy_profile: Dict[str, float],
        tier: str,
    ) -> List[str]:
        """
        Detect conflict zones between aspects and anchors.

        Identifies tension patterns that may require special handling:
        - practical_support_gap: High Needs + low Execution
        - identity_integration_gap: High Meaning/Collective + low Identity
        - growth_edge_tension: High Challenge + high Purpose + high entropy
        - survival_transcendence_tension: Strong lower anchors + strong upper aspects
        - grounding_deficit: High upper aspects + low Form/Execution

        Args:
            normalized_aspects: Normalized aspect probabilities.
            anchor_profile: Normalized anchor profile.
            entropy_profile: Computed entropy profile.
            tier: Routing tier ("lower", "upper", "hybrid").

        Returns:
            List of conflict zone labels.
        """
        conflicts: List[str] = []
        entropy_mix = entropy_profile.get("entropy_mix", 0.0)
        regime = entropy_profile.get("regime", "low")

        # Helper to get values with defaults
        def get_aspect(name: str) -> float:
            return normalized_aspects.get(name, 0.0)

        def get_anchor(name: str) -> float:
            return anchor_profile.get(name, 0.0)

        # Compute aggregate scores for tier groups
        lower_aspect_sum = sum(get_aspect(a) for a in LOWER_ASPECTS)
        upper_aspect_sum = sum(get_aspect(a) for a in UPPER_ASPECTS)
        lower_anchor_sum = sum(get_anchor(a) for a in LOWER_ANCHORS)
        upper_anchor_sum = sum(get_anchor(a) for a in UPPER_ANCHORS)

        # Pattern 1: practical_support_gap
        # High Needs but low Execution → user needs practical help but system is abstract
        needs_score = get_anchor("Needs")
        execution_score = get_aspect("Execution")
        if needs_score > self.conflict_threshold and execution_score < self.conflict_threshold:
            conflicts.append("practical_support_gap")

        # Pattern 2: identity_integration_gap
        # High Meaning/Collective but low Identity → meaning-seeking without identity grounding
        meaning_collective = get_anchor("Meaning") + get_anchor("Collective")
        identity_score = get_aspect("Identity")
        if meaning_collective > 2 * self.conflict_threshold and identity_score < self.conflict_threshold:
            conflicts.append("identity_integration_gap")

        # Pattern 3: growth_edge_tension
        # High Challenge + high Purpose + high entropy → transformative but unstable
        challenge_score = get_anchor("Challenge")
        purpose_score = get_aspect("Purpose")
        if (
            challenge_score > self.conflict_threshold
            and purpose_score > self.conflict_threshold
            and regime == "high"
        ):
            conflicts.append("growth_edge_tension")

        # Pattern 4: survival_transcendence_tension
        # Strong lower anchors (Needs, Exchange, Challenge) + strong upper aspects (Purpose, Universal)
        if (
            lower_anchor_sum > 2 * self.conflict_threshold
            and upper_aspect_sum > 2 * self.conflict_threshold
        ):
            conflicts.append("survival_transcendence_tension")

        # Pattern 5: grounding_deficit
        # High upper aspects but low Form/Execution → abstract without practical grounding
        form_score = get_aspect("Form")
        if (
            upper_aspect_sum > 3 * self.conflict_threshold
            and form_score < self.conflict_threshold
            and execution_score < self.conflict_threshold
        ):
            conflicts.append("grounding_deficit")

        # Pattern 6: relational_isolation
        # Low Belonging/Relation with high individual aspects (Agency, Identity)
        belonging_relation = get_anchor("Belonging") + get_anchor("Relation")
        agency_score = get_aspect("Agency")
        if (
            belonging_relation < self.conflict_threshold
            and agency_score > self.conflict_threshold
            and identity_score > self.conflict_threshold
        ):
            conflicts.append("relational_isolation")

        # Pattern 7: change_resistance
        # High Role/Exchange (stability-seeking) with high Change anchor
        role_exchange = get_anchor("Role") + get_anchor("Exchange")
        change_score = get_anchor("Change")
        if role_exchange > 2 * self.conflict_threshold and change_score > 2 * self.conflict_threshold:
            conflicts.append("change_resistance_tension")

        return conflicts

    def _generate_resolution_hints(
        self,
        dominant_aspects: List[str],
        suppressed_aspects: List[str],
        anchor_profile: Dict[str, float],
        entropy_profile: Dict[str, float],
        conflict_zones: List[str],
        tier: str,
        domain: str,
        flow_mode: str,
    ) -> List[str]:
        """
        Generate deterministic resolution hints for Fusion/DHA engines.

        Hints are structured labels that guide downstream processing:
        - Tier-based hints (upper_tier_deep_processing, lower_tier_concrete_focus)
        - Entropy-based hints (high_entropy_upper_tilt, low_entropy_stability)
        - Conflict-based hints (derived from conflict zones)
        - Domain-based hints (reflective_domain_emphasis, task_domain_efficiency)

        Args:
            dominant_aspects: List of dominant aspects.
            suppressed_aspects: List of suppressed aspects.
            anchor_profile: Normalized anchor profile.
            entropy_profile: Computed entropy profile.
            conflict_zones: Detected conflict zones.
            tier: Routing tier.
            domain: Domain classification.
            flow_mode: Flow mode specification.

        Returns:
            List of resolution hint labels.
        """
        hints: List[str] = []
        regime = entropy_profile.get("regime", "low")
        entropy_mix = entropy_profile.get("entropy_mix", 0.0)

        # Tier-based hints
        if tier == "upper":
            hints.append("upper_tier_deep_processing")
            if "Purpose" in dominant_aspects or "Universal" in dominant_aspects:
                hints.append("meaning_oriented_response")
        elif tier == "lower":
            hints.append("lower_tier_concrete_focus")
            if "Execution" in dominant_aspects or "Form" in dominant_aspects:
                hints.append("action_oriented_response")
        else:  # hybrid
            hints.append("hybrid_tier_balanced_approach")

        # Entropy-based hints
        if regime == "high":
            hints.append("high_entropy_upper_tilt")
            hints.append("uncertainty_acknowledgment")
        elif regime == "low":
            hints.append("low_entropy_stability")
            hints.append("confident_response_appropriate")
        else:  # medium
            hints.append("moderate_entropy_adaptive")

        # Flow mode hints
        if flow_mode == "inner_priority":
            hints.append("inner_flow_introspective")
        elif flow_mode == "outer_only":
            hints.append("outer_flow_practical")
        else:  # outer_plus_inner
            hints.append("balanced_flow_mode")

        # Domain-based hints
        if domain in REFLECTIVE_DOMAINS:
            hints.append("reflective_domain_emphasis")
            if domain == "therapy":
                hints.append("therapeutic_sensitivity")
            elif domain == "spiritual":
                hints.append("spiritual_openness")
            elif domain == "identity":
                hints.append("identity_exploration_support")
        elif domain in TASK_DOMAINS:
            hints.append("task_domain_efficiency")
            if domain == "code":
                hints.append("technical_precision")
            elif domain == "math":
                hints.append("logical_rigor")

        # Conflict-derived hints
        for conflict in conflict_zones:
            if conflict == "practical_support_gap":
                hints.append("anchor_tension_needs_vs_abstract")
                hints.append("ground_in_practical")
            elif conflict == "identity_integration_gap":
                hints.append("identity_vs_meaning_gap")
                hints.append("support_identity_grounding")
            elif conflict == "growth_edge_tension":
                hints.append("transformative_edge_detected")
                hints.append("careful_pacing_advised")
            elif conflict == "survival_transcendence_tension":
                hints.append("anchor_tension_survival_vs_transcendence")
                hints.append("honor_both_levels")
            elif conflict == "grounding_deficit":
                hints.append("abstract_without_ground")
                hints.append("add_concrete_elements")
            elif conflict == "relational_isolation":
                hints.append("relational_need_detected")
                hints.append("connection_emphasis")
            elif conflict == "change_resistance_tension":
                hints.append("stability_change_tension")
                hints.append("gradual_transition_support")

        # Anchor-based hints (dominant anchors)
        for anchor, score in anchor_profile.items():
            if score > 0.2:  # Significant anchor presence
                if anchor == "Needs":
                    hints.append("attend_to_practical_needs")
                elif anchor == "Meaning":
                    hints.append("meaning_seeking_detected")
                elif anchor == "Challenge":
                    hints.append("growth_challenge_present")
                elif anchor == "Belonging":
                    hints.append("belonging_need_present")
                elif anchor == "Collective":
                    hints.append("collective_orientation")

        # Remove duplicates while preserving order
        seen = set()
        unique_hints = []
        for hint in hints:
            if hint not in seen:
                seen.add(hint)
                unique_hints.append(hint)

        return unique_hints

    def get_statistics(self) -> Dict[str, float]:
        """
        Get engine configuration statistics.

        Returns:
            Dictionary with threshold configuration.
        """
        return {
            "aspect_threshold": self.aspect_threshold,
            "conflict_threshold": self.conflict_threshold,
            "entropy_low_threshold": self.ENTROPY_LOW_THRESHOLD,
            "entropy_high_threshold": self.ENTROPY_HIGH_THRESHOLD,
        }


# Module-level singleton for convenience
_hrm_engine: HRMEngine = None


def get_hrm_engine() -> HRMEngine:
    """
    Get singleton HRM engine instance.

    Returns:
        Shared HRMEngine instance.
    """
    global _hrm_engine
    if _hrm_engine is None:
        _hrm_engine = HRMEngine()
    return _hrm_engine
