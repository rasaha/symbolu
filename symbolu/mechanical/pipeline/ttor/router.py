"""
TTOR v1.4 Router Module

Implements the Two-Tier Ontology Router - the cognitive bridge between
the symbolic aspect engine (v2.6) and the MLCR/Fusion/DHA engines (v2.7/v3.0).

The router orchestrates all formula computations and produces a complete
RoutingPlan with full audit trail for deterministic, enterprise-grade routing.

Pipeline Position:
    User Input → Vritti/Syllable/Kosha → Aspect Mapping → Entropy Engines
    → Experiential Anchors → [TTOR] → Tier/Flow/Modules → MLCR → Renderer
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .constants import (
    ENGINE_FAMILY_DHA,
    ENGINE_FAMILY_FUSION,
    ENGINE_FAMILY_PERSONA,
    ENGINE_FAMILY_RENDERER_ONLY,
    ENTROPY_THRESHOLD,
    REGULATED_DOMAINS,
    TENSION_THRESHOLD,
    TIER_THRESHOLD,
)
from .formulas import (
    anchor_boosts,
    aspect_base_scores,
    compute_conflict_score,
    compute_entropy_boosts,
    domain_modulation,
    entropy_mix,
    final_scores,
)
from .models import FlowMode, RouterContext, RoutingPlan, Tier

logger = logging.getLogger(__name__)


class TTORRouter:
    """
    Two-Tier Ontology Router v1.4

    Deterministic routing engine that computes:
    - Tier selection (LOWER / UPPER / HYBRID)
    - Flow mode (OUTER_ONLY / OUTER_PLUS_INNER / INNER_PRIORITY)
    - Engine family recommendation (persona / fusion / dha / renderer_only)
    - Module activation flags (HRM, LCM, LAM)
    - Safety flags (regulated_mode, allow_metaphor)

    All decisions are fully auditable via the debug dictionary.
    """

    def __init__(self) -> None:
        """Initialize TTOR router."""
        self._log_prefix = "[TTOR v1.4]"

    def route(self, context: RouterContext) -> RoutingPlan:
        """
        Execute routing algorithm on the given context.

        Algorithm Steps:
        1. Compute lower_base, upper_base from aspect probabilities
        2. Compute lower_anchor_boost, upper_anchor_boost from anchor scores
        3. Compute entropy_mix → entropy boosts
        4. Apply domain modulation
        5. Compute final tier scores
        6. Determine Tier (LOWER / UPPER / HYBRID) using threshold
        7. Determine FlowMode based on tier and entropy/tension
        8. Select engine family
        9. Set HRM/LCM/LAM flags
        10. Apply safety overrides (regulated_mode, allow_metaphor)
        11. Construct explanation string
        12. Return complete RoutingPlan with debug dictionary

        Args:
            context: Validated RouterContext with all input signals

        Returns:
            Complete RoutingPlan with routing decisions and audit trail
        """
        debug: Dict[str, Any] = {}

        # =====================================================================
        # STEP 1: Compute aspect base scores
        # =====================================================================
        logger.debug(f"{self._log_prefix} Computing aspect base scores")
        lower_base, upper_base = aspect_base_scores(context.aspect_probs)
        debug["lower_base"] = lower_base
        debug["upper_base"] = upper_base
        logger.debug(f"{self._log_prefix} lower_base={lower_base:.4f}, upper_base={upper_base:.4f}")

        # =====================================================================
        # STEP 2: Compute anchor boosts
        # =====================================================================
        logger.debug(f"{self._log_prefix} Computing anchor boosts")
        lower_anchor_boost, upper_anchor_boost = anchor_boosts(context.anchor_scores)
        debug["lower_anchor_boost"] = lower_anchor_boost
        debug["upper_anchor_boost"] = upper_anchor_boost
        logger.debug(
            f"{self._log_prefix} lower_anchor_boost={lower_anchor_boost:.4f}, "
            f"upper_anchor_boost={upper_anchor_boost:.4f}"
        )

        # =====================================================================
        # STEP 3: Compute entropy mix and entropy boosts
        # =====================================================================
        logger.debug(f"{self._log_prefix} Computing entropy mix")
        normalized_entropy, entropy_ratio = entropy_mix(context.H_D, context.H_G)
        debug["normalized_entropy"] = normalized_entropy
        debug["entropy_ratio"] = entropy_ratio
        debug["H_D"] = context.H_D
        debug["H_G"] = context.H_G
        debug["H_K"] = context.H_K
        logger.debug(
            f"{self._log_prefix} normalized_entropy={normalized_entropy:.4f}, "
            f"entropy_ratio={entropy_ratio:.4f}"
        )

        lower_entropy_boost, upper_entropy_boost = compute_entropy_boosts(
            normalized_entropy, entropy_ratio
        )
        debug["lower_entropy_boost"] = lower_entropy_boost
        debug["upper_entropy_boost"] = upper_entropy_boost
        logger.debug(
            f"{self._log_prefix} lower_entropy_boost={lower_entropy_boost:.4f}, "
            f"upper_entropy_boost={upper_entropy_boost:.4f}"
        )

        # =====================================================================
        # STEP 4: Apply domain modulation
        # =====================================================================
        logger.debug(f"{self._log_prefix} Applying domain modulation for '{context.domain}'")
        lower_domain_mod, upper_domain_mod = domain_modulation(context.domain)
        debug["domain"] = context.domain
        debug["lower_domain_mod"] = lower_domain_mod
        debug["upper_domain_mod"] = upper_domain_mod
        logger.debug(
            f"{self._log_prefix} lower_domain_mod={lower_domain_mod:.4f}, "
            f"upper_domain_mod={upper_domain_mod:.4f}"
        )

        # =====================================================================
        # STEP 5: Compute final tier scores
        # =====================================================================
        logger.debug(f"{self._log_prefix} Computing final tier scores")
        final_lower, final_upper = final_scores(
            lower_base=lower_base,
            upper_base=upper_base,
            lower_anchor_boost=lower_anchor_boost,
            upper_anchor_boost=upper_anchor_boost,
            lower_entropy_boost=lower_entropy_boost,
            upper_entropy_boost=upper_entropy_boost,
            lower_domain_mod=lower_domain_mod,
            upper_domain_mod=upper_domain_mod,
        )
        debug["final_lower"] = final_lower
        debug["final_upper"] = final_upper
        logger.debug(
            f"{self._log_prefix} final_lower={final_lower:.4f}, "
            f"final_upper={final_upper:.4f}"
        )

        # =====================================================================
        # STEP 6: Determine Tier
        # =====================================================================
        tier = self._determine_tier(final_lower, final_upper)
        debug["tier_threshold"] = TIER_THRESHOLD
        debug["tier_difference"] = abs(final_upper - final_lower)
        logger.info(f"{self._log_prefix} Tier determined: {tier.value}")

        # =====================================================================
        # STEP 7: Determine FlowMode
        # =====================================================================
        is_high_entropy = normalized_entropy > ENTROPY_THRESHOLD
        is_high_tension = context.long_arc_tension > TENSION_THRESHOLD
        debug["is_high_entropy"] = is_high_entropy
        debug["is_high_tension"] = is_high_tension
        debug["entropy_threshold"] = ENTROPY_THRESHOLD
        debug["tension_threshold"] = TENSION_THRESHOLD
        debug["long_arc_tension"] = context.long_arc_tension

        flow_mode = self._determine_flow_mode(
            tier=tier,
            is_high_entropy=is_high_entropy,
            is_high_tension=is_high_tension,
        )
        logger.info(f"{self._log_prefix} FlowMode determined: {flow_mode.value}")

        # =====================================================================
        # STEP 8: Select engine family
        # =====================================================================
        conflict_score = compute_conflict_score(lower_anchor_boost, upper_anchor_boost)
        debug["conflict_score"] = conflict_score

        engine_family = self._select_engine_family(
            tier=tier,
            flow_mode=flow_mode,
            is_high_entropy=is_high_entropy,
            conflict_score=conflict_score,
        )
        logger.info(f"{self._log_prefix} Engine family selected: {engine_family}")

        # =====================================================================
        # STEP 9: Set HRM/LCM/LAM flags
        # =====================================================================
        use_hrm, use_lcm, use_lam = self._compute_module_flags(
            tier=tier,
            flow_mode=flow_mode,
            is_high_entropy=is_high_entropy,
            is_high_tension=is_high_tension,
            conflict_score=conflict_score,
        )
        debug["use_hrm"] = use_hrm
        debug["use_lcm"] = use_lcm
        debug["use_lam"] = use_lam
        logger.debug(f"{self._log_prefix} Module flags: HRM={use_hrm}, LCM={use_lcm}, LAM={use_lam}")

        # =====================================================================
        # STEP 10: Apply safety overrides
        # =====================================================================
        regulated_mode, allow_metaphor = self._apply_safety_rules(
            domain=context.domain,
            risk_level=context.risk_level,
            tier=tier,
        )
        debug["risk_level"] = context.risk_level
        debug["regulated_mode"] = regulated_mode
        debug["allow_metaphor"] = allow_metaphor
        logger.debug(
            f"{self._log_prefix} Safety: regulated_mode={regulated_mode}, "
            f"allow_metaphor={allow_metaphor}"
        )

        # =====================================================================
        # STEP 11: Construct explanation
        # =====================================================================
        explanation = self._construct_explanation(
            tier=tier,
            flow_mode=flow_mode,
            engine_family=engine_family,
            final_lower=final_lower,
            final_upper=final_upper,
            normalized_entropy=normalized_entropy,
            is_high_tension=is_high_tension,
            regulated_mode=regulated_mode,
        )

        # =====================================================================
        # STEP 12: Return complete RoutingPlan
        # =====================================================================
        plan = RoutingPlan(
            tier=tier,
            flow_mode=flow_mode,
            preferred_engine_family=engine_family,
            use_hrm=use_hrm,
            use_lcm=use_lcm,
            use_lam=use_lam,
            regulated_mode=regulated_mode,
            allow_metaphor=allow_metaphor,
            explanation=explanation,
            debug=debug,
        )

        logger.info(f"{self._log_prefix} Routing complete: {plan}")
        return plan

    def _determine_tier(self, final_lower: float, final_upper: float) -> Tier:
        """
        Determine routing tier based on final scores.

        Decision Logic:
        - If |upper - lower| < TIER_THRESHOLD: HYBRID
        - If upper > lower: UPPER
        - Otherwise: LOWER

        Args:
            final_lower: Final lower tier score
            final_upper: Final upper tier score

        Returns:
            Selected Tier enum value
        """
        difference = abs(final_upper - final_lower)

        if difference < TIER_THRESHOLD:
            return Tier.HYBRID
        elif final_upper > final_lower:
            return Tier.UPPER
        else:
            return Tier.LOWER

    def _determine_flow_mode(
        self,
        tier: Tier,
        is_high_entropy: bool,
        is_high_tension: bool,
    ) -> FlowMode:
        """
        Determine flow mode based on tier and entropy/tension signals.

        Decision Logic:
        - LOWER + low entropy → OUTER_ONLY
        - UPPER + (high entropy or high tension) → INNER_PRIORITY
        - Otherwise → OUTER_PLUS_INNER

        Args:
            tier: Selected routing tier
            is_high_entropy: Whether normalized entropy exceeds threshold
            is_high_tension: Whether long-arc tension exceeds threshold

        Returns:
            Selected FlowMode enum value
        """
        if tier == Tier.LOWER and not is_high_entropy:
            return FlowMode.OUTER_ONLY
        elif tier == Tier.UPPER and (is_high_entropy or is_high_tension):
            return FlowMode.INNER_PRIORITY
        else:
            return FlowMode.OUTER_PLUS_INNER

    def _select_engine_family(
        self,
        tier: Tier,
        flow_mode: FlowMode,
        is_high_entropy: bool,
        conflict_score: float,
    ) -> str:
        """
        Select preferred engine family for MLCR dispatch.

        Decision Logic:
        - INNER_PRIORITY + high entropy → DHA
        - HYBRID or high conflict → Fusion
        - LOWER + OUTER_ONLY → Persona
        - Default → Persona

        Args:
            tier: Selected routing tier
            flow_mode: Selected flow mode
            is_high_entropy: Whether normalized entropy exceeds threshold
            conflict_score: Anchor conflict score

        Returns:
            Engine family string identifier
        """
        # DHA for deep inner processing with high uncertainty
        if flow_mode == FlowMode.INNER_PRIORITY and is_high_entropy:
            return ENGINE_FAMILY_DHA

        # Fusion for hybrid tier or high conflict (needs integration)
        if tier == Tier.HYBRID or conflict_score > 0.6:
            return ENGINE_FAMILY_FUSION

        # Persona for straightforward lower-tier processing
        if tier == Tier.LOWER and flow_mode == FlowMode.OUTER_ONLY:
            return ENGINE_FAMILY_PERSONA

        # Default to persona for most cases
        return ENGINE_FAMILY_PERSONA

    def _compute_module_flags(
        self,
        tier: Tier,
        flow_mode: FlowMode,
        is_high_entropy: bool,
        is_high_tension: bool,
        conflict_score: float,
    ) -> tuple[bool, bool, bool]:
        """
        Compute HRM/LCM/LAM activation flags.

        HRM (Harmonic Response Module):
        - Active when: HYBRID tier, high entropy, or high conflict

        LCM (Local Context Module):
        - Active when: OUTER_PLUS_INNER or INNER_PRIORITY flow

        LAM (Long-Arc Module):
        - Active when: High tension or INNER_PRIORITY flow

        Args:
            tier: Selected routing tier
            flow_mode: Selected flow mode
            is_high_entropy: Whether normalized entropy exceeds threshold
            is_high_tension: Whether long-arc tension exceeds threshold
            conflict_score: Anchor conflict score

        Returns:
            Tuple of (use_hrm, use_lcm, use_lam) boolean flags
        """
        # HRM: Active for hybrid situations or high uncertainty/conflict
        use_hrm = (
            tier == Tier.HYBRID
            or is_high_entropy
            or conflict_score > 0.5
        )

        # LCM: Active when inner processing is involved
        use_lcm = flow_mode in (FlowMode.OUTER_PLUS_INNER, FlowMode.INNER_PRIORITY)

        # LAM: Active for long-arc concerns or deep inner processing
        use_lam = is_high_tension or flow_mode == FlowMode.INNER_PRIORITY

        return (use_hrm, use_lcm, use_lam)

    def _apply_safety_rules(
        self,
        domain: str,
        risk_level: str,
        tier: Tier,
    ) -> tuple[bool, bool]:
        """
        Apply safety rules for regulated mode and metaphor allowance.

        Regulated Mode:
        - Always True for: regulated domains or high/critical risk

        Allow Metaphor:
        - False for: regulated domains, critical risk, or LOWER tier

        Args:
            domain: Domain classification
            risk_level: Risk level classification
            tier: Selected routing tier

        Returns:
            Tuple of (regulated_mode, allow_metaphor) boolean flags
        """
        is_regulated_domain = domain in REGULATED_DOMAINS
        is_high_risk = risk_level in ("high", "critical")

        # Regulated mode: conservative processing required
        regulated_mode = is_regulated_domain or is_high_risk

        # Metaphor allowance: creative expression permitted
        allow_metaphor = not (
            is_regulated_domain
            or risk_level == "critical"
            or tier == Tier.LOWER
        )

        return (regulated_mode, allow_metaphor)

    def _construct_explanation(
        self,
        tier: Tier,
        flow_mode: FlowMode,
        engine_family: str,
        final_lower: float,
        final_upper: float,
        normalized_entropy: float,
        is_high_tension: bool,
        regulated_mode: bool,
    ) -> str:
        """
        Construct human-readable explanation of routing decision.

        Args:
            tier: Selected routing tier
            flow_mode: Selected flow mode
            engine_family: Selected engine family
            final_lower: Final lower tier score
            final_upper: Final upper tier score
            normalized_entropy: Combined normalized entropy
            is_high_tension: Whether long-arc tension exceeds threshold
            regulated_mode: Whether regulated mode is active

        Returns:
            Explanation string describing the routing decision
        """
        parts: list[str] = []

        # Tier explanation
        score_diff = final_upper - final_lower
        if tier == Tier.HYBRID:
            parts.append(
                f"Hybrid tier selected (score difference {abs(score_diff):.3f} < threshold)"
            )
        elif tier == Tier.UPPER:
            parts.append(
                f"Upper tier selected (upper={final_upper:.3f} > lower={final_lower:.3f})"
            )
        else:
            parts.append(
                f"Lower tier selected (lower={final_lower:.3f} > upper={final_upper:.3f})"
            )

        # Flow mode explanation
        if flow_mode == FlowMode.OUTER_ONLY:
            parts.append("Outer-only flow for concrete processing")
        elif flow_mode == FlowMode.INNER_PRIORITY:
            reasons = []
            if normalized_entropy > ENTROPY_THRESHOLD:
                reasons.append("high entropy")
            if is_high_tension:
                reasons.append("high tension")
            parts.append(f"Inner-priority flow due to: {', '.join(reasons) or 'upper tier'}")
        else:
            parts.append("Outer-plus-inner flow for balanced processing")

        # Engine and safety
        parts.append(f"Engine: {engine_family}")
        if regulated_mode:
            parts.append("Regulated mode active")

        return "; ".join(parts)
