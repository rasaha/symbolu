"""
DILchat Adapter - Presentation Layer Translator v1.0

Converts Symbol-U unified output + policy flags into DILchat-ready response format.

The adapter transforms:
    INPUT:
    - unified_output (Dict): USU-API v1.0 output from Symbol-U pipeline
    - policy_flags (Dict): Policy engine flags from domain coherence profiles
    - domain (str): Domain identifier (e.g., "trading", "therapy", "identity")

    OUTPUT:
    - DILchatResponse: Structured response with text, badges, hints, and metadata

Key Components:
    - DILchatBadge: Status chips for UI display
    - DILchatHint: Advisory codes for UI behavior
    - DILchatResponse: Complete response structure
    - build_dilchat_response(): Core transformer function
    - build_dilchat_payload(): JSON serialization wrapper

Design Principles:
    - Zero-LLM: Pure deterministic transformations
    - Presentation-only: No semantic interpretation
    - Non-invasive: Does not modify pipeline behavior
    - Deterministic: Same input produces same output
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ============================================================================
# DILchat Response Schema
# ============================================================================


@dataclass
class DILchatBadge:
    """
    Status badge for UI display.

    Badges are compact visual indicators showing conversation state,
    grounding needs, and behavioral recommendations.

    Attributes:
        label: Display text for badge (e.g., "Stable", "Grounding Needed")
        level: Severity level - "info" (neutral), "warning" (caution), "critical" (urgent)
        description: Human-readable explanation of badge meaning
    """
    label: str
    level: str  # "info" | "warning" | "critical"
    description: str


@dataclass
class DILchatHint:
    """
    UI advisory hint for behavioral guidance.

    Hints provide machine-readable codes that the DILchat UI can use
    to adjust its behavior, tone, or interface elements.

    Attributes:
        code: Machine-readable hint code (e.g., "GROUNDING", "DEEP_REFLECTION")
        message: Human-readable explanation for UI developers
    """
    code: str
    message: str


@dataclass
class DILchatResponse:
    """
    Complete DILchat-facing response structure.

    This is the main output format for DILchat integration, combining
    text output with metadata, badges, hints, and layer summaries.

    Attributes:
        text: Final rendered response text
        badges: List of status badges for UI display
        hints: List of behavioral hints for UI adaptation
        symbolic_summary: Symbolic layer summary (if available)
        practical_summary: Practical layer summary (if available)
        mirror_summary: Mirror-truth layer summary (if available)
        coherence_score: Overall coherence score (0-1)
        stability_status: Stability classification ("stable", "recovering", "fragmented")
        domain: Domain identifier
        raw_unified: Complete unified output (for advanced UI)
        policy_flags: Complete policy flags (for debugging)
    """
    text: str
    badges: List[DILchatBadge] = field(default_factory=list)
    hints: List[DILchatHint] = field(default_factory=list)

    # Layer summaries for advanced UI panes
    symbolic_summary: Optional[str] = None
    practical_summary: Optional[str] = None
    mirror_summary: Optional[str] = None

    # Coherence + domain metadata
    coherence_score: Optional[float] = None
    stability_status: Optional[str] = None
    domain: Optional[str] = None

    # Raw references for advanced UI or logging
    raw_unified: Optional[Dict[str, Any]] = None
    policy_flags: Optional[Dict[str, Any]] = None

    # Phase 2: Temporal formulas (diagnostics only - not used for badges/hints)
    formulas: Optional[Dict[str, Optional[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dictionary.

        Recursively removes None values and converts nested dataclasses
        to plain dictionaries for JSON serialization.

        Returns:
            Clean dictionary with all DILchat response fields
        """
        # Convert to dict using asdict
        result = asdict(self)

        # Remove None values recursively
        result = _remove_none_values(result)

        return result


# ============================================================================
# Core Adapter Function
# ============================================================================


def build_dilchat_response(
    unified_output: Dict[str, Any],
    policy_flags: Dict[str, Any],
    domain: str,
    session_policy_flags: Optional[Dict[str, Any]] = None
) -> DILchatResponse:
    """
    Convert Symbol-U unified output + policy flags into DILchat-ready response.

    This is the main transformer function that extracts data from Symbol-U's
    pipeline output and constructs a presentation-layer response for DILchat.

    Args:
        unified_output: Unified output dictionary from USU-API v1.0
        policy_flags: Policy flags from policy engine
        domain: Domain identifier (e.g., "trading", "therapy", "identity")
        session_policy_flags: Optional session policy flags from session policy layer

    Returns:
        DILchatResponse with complete presentation data

    Examples:
        >>> unified = {
        ...     "text": "Let's explore your feelings...",
        ...     "coherence": {"coherence_score": 0.85, ...},
        ...     "symbolic": {"summary": "Deep reflection"},
        ...     ...
        ... }
        >>> flags = {
        ...     "stability_status": "stable",
        ...     "needs_grounding": False,
        ...     ...
        ... }
        >>> response = build_dilchat_response(unified, flags, "therapy")
        >>> response.badges[0].label
        'Stable'
    """
    # ========================================================================
    # STEP 1: Extract base text
    # ========================================================================
    text = unified_output.get("text", "")

    # ========================================================================
    # STEP 2: Extract coherence & domain metadata
    # ========================================================================
    coherence = unified_output.get("coherence", {})
    metadata = unified_output.get("metadata", {})

    coherence_score = coherence.get("coherence_score")
    persona_drift_score = coherence.get("persona_drift_score")
    temporal_arc_score = coherence.get("temporal_arc_score")

    # Get stability status from policy flags
    stability_status = policy_flags.get("stability_status")

    # Get domain from metadata or use provided domain
    response_domain = metadata.get("domain", domain)

    # ========================================================================
    # STEP 3: Extract layer summaries
    # ========================================================================
    symbolic = unified_output.get("symbolic", {})
    practical = unified_output.get("practical", {})
    mirror = unified_output.get("mirror", {})

    symbolic_summary = symbolic.get("summary") or symbolic.get("reasoning")
    practical_summary = practical.get("summary") or practical.get("text")
    mirror_summary = mirror.get("summary")

    # ========================================================================
    # STEP 4: Merge session policy flags into policy_flags for badge/hint building
    # ========================================================================
    # Create a combined flags dict that includes session policy flags
    combined_flags = {**policy_flags}
    if session_policy_flags:
        combined_flags["session_policy_flags"] = session_policy_flags

    # ========================================================================
    # STEP 5: Build badges (includes session memory + session recap + intent arc badges)
    # ========================================================================
    # Extract session memory for memory-based badges
    session_memory = unified_output.get("session_memory", {})

    # Extract session recap for recap-based badges
    session_recap = unified_output.get("session_recap", {})

    # Extract intent arc for arc-based badges
    intent_arc = unified_output.get("intent_arc", {})

    # Extract identity signature for identity-based badges
    identity_signature = unified_output.get("identity_signature", {})

    # Extract motivation profile for motivation-based badges
    motivation_profile = unified_output.get("motivation_profile", {})

    # Extract trading guardrails for trading-specific badges
    trading_guardrails = unified_output.get("trading_guardrails", {})

    badges = _build_badges(
        stability_status=stability_status,
        policy_flags=combined_flags,
        coherence_score=coherence_score,
        session_memory=session_memory,
        session_recap=session_recap,
        intent_arc=intent_arc,
        identity_signature=identity_signature,
        motivation_profile=motivation_profile,
        trading_guardrails=trading_guardrails,
    )

    # ========================================================================
    # STEP 6: Build hints (includes session memory + session recap + intent arc + identity signature + motivation + trading guardrail + v3 confidence hints)
    # ========================================================================
    hints = _build_hints(combined_flags, session_memory, session_recap, intent_arc, identity_signature, motivation_profile, trading_guardrails, coherence, domain)

    # ========================================================================
    # STEP 7: Extract Phase 2 formulas (diagnostics only)
    # ========================================================================
    formulas_data = unified_output.get("formulas")

    # ========================================================================
    # STEP 8: Assemble DILchatResponse
    # ========================================================================
    return DILchatResponse(
        text=text,
        badges=badges,
        hints=hints,
        symbolic_summary=symbolic_summary,
        practical_summary=practical_summary,
        mirror_summary=mirror_summary,
        coherence_score=coherence_score,
        stability_status=stability_status,
        domain=response_domain,
        raw_unified=unified_output,
        policy_flags=policy_flags,
        formulas=formulas_data,
    )


def build_dilchat_payload(
    unified_output: Dict[str, Any],
    policy_flags: Dict[str, Any],
    domain: str,
    session_policy_flags: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build fully serialized DILchat payload.

    This is the main public API function for DILchat integration.
    It wraps build_dilchat_response() and serializes to JSON-safe dict.

    Args:
        unified_output: Unified output dictionary from USU-API v1.0
        policy_flags: Policy flags from policy engine
        domain: Domain identifier
        session_policy_flags: Optional session policy flags from session policy layer

    Returns:
        JSON-serializable dictionary with complete DILchat response

    Usage:
        # In orchestrator or API endpoint:
        dilchat_payload = build_dilchat_payload(
            ctx.unified_output,
            ctx.policy_flags or {},
            ctx.domain,
            ctx.session_policy_flags.to_dict() if ctx.session_policy_flags else None
        )
        return jsonify(dilchat_payload)  # Flask example
    """
    response = build_dilchat_response(unified_output, policy_flags, domain, session_policy_flags)
    return response.to_dict()


# ============================================================================
# Badge Building Logic
# ============================================================================


def _build_badges(
    stability_status: Optional[str],
    policy_flags: Dict[str, Any],
    coherence_score: Optional[float],
    session_memory: Optional[Dict[str, Any]] = None,
    session_recap: Optional[Dict[str, Any]] = None,
    intent_arc: Optional[Dict[str, Any]] = None,
    identity_signature: Optional[Dict[str, Any]] = None,
    motivation_profile: Optional[Dict[str, Any]] = None,
    trading_guardrails: Optional[Dict[str, Any]] = None,
) -> List[DILchatBadge]:
    """
    Build UI badges based on stability status and policy flags.

    Badge Rules:
        1. Coherence Status Badge (stable/recovering/fragmented)
        2. Grounding Needed Badge (if needs_grounding=True)
        3. Deep Reflection Badge (if allow_deep_reflection=True)
        4. Long-Arc Active Badge (if prefer_arc_mode=True)
        5. Session Fragmented Badge (if session_is_fragmented=True)
        6. Session Grounding Needed Badge (if session_needs_grounding=True)
        7. Session Deep Reflection Allowed Badge (if session_allow_deep_reflection=True)
        8. Memory Breakthrough Badge (if recent breakthrough event)
        9. Memory Fragmentation Badge (if recent fragmentation event)
        10. Session Recap Fragmented Badge (if recap.overall_state == "fragmented")
        11. Session Recap Recovering Badge (if recap.overall_state == "recovering")
        12. Session Recap Breakthrough Badge (if "breakthrough_detected" in recap.key_patterns)
        13. Intent Arc Badges (insight, stabilization, identity exploration, etc.)
        14. Identity Signature Badges (self_stable, self_expanding, self_fragmented, etc.)
        15. Motivation Profile Badges (hope, fear, expansion, stabilization, avoidance, assertion)
        16. Trading Guardrail Badges (high_tension_risk, neg_momentum_risk, volatility_risk, no_action_recommended)

    Args:
        stability_status: Stability classification from policy engine
        policy_flags: Policy flags dictionary (includes session_policy_flags if available)
        coherence_score: Coherence score (0-1)
        session_memory: Session memory dictionary with events
        session_recap: Session recap dictionary with multi-turn summary
        intent_arc: Intent arc dictionary with arc classification
        identity_signature: Identity signature dictionary with signature classification
        motivation_profile: Motivation profile dictionary with motivational driver classification
        trading_guardrails: Trading guardrails dictionary with risk flags

    Returns:
        List of DILchatBadge objects
    """
    badges = []

    # ========================================================================
    # BADGE 1: Coherence Status
    # ========================================================================
    if stability_status:
        if stability_status == "stable":
            badges.append(DILchatBadge(
                label="Stable",
                level="info",
                description="Conversation coherence is stable and healthy."
            ))
        elif stability_status == "recovering":
            badges.append(DILchatBadge(
                label="Recovering",
                level="info",
                description="Coherence is recovering. Temporal arc is improving."
            ))
        elif stability_status == "fragmented":
            badges.append(DILchatBadge(
                label="Fragmented",
                level="warning",
                description="Coherence is fragmented. Consider grounding or recentering."
            ))

    # ========================================================================
    # BADGE 2: Grounding Needed
    # ========================================================================
    if policy_flags.get("needs_grounding"):
        # Determine level based on coherence warning
        level = "critical" if policy_flags.get("coherence_warning") else "warning"

        badges.append(DILchatBadge(
            label="Grounding Needed",
            level=level,
            description="Conversation is unstable. Recommend concrete, calming responses."
        ))

    # ========================================================================
    # BADGE 3: Deep Reflection Open
    # ========================================================================
    if policy_flags.get("allow_deep_reflection"):
        badges.append(DILchatBadge(
            label="Deep Reflection Open",
            level="info",
            description="User appears stable enough for deeper identity/meaning exploration."
        ))

    # ========================================================================
    # BADGE 4: Long-Arc Active
    # ========================================================================
    if policy_flags.get("prefer_arc_mode"):
        badges.append(DILchatBadge(
            label="Long-Arc Active",
            level="info",
            description="Temporal/identity arc reasoning is recommended."
        ))

    # ========================================================================
    # SESSION-LEVEL BADGES (from session policy layer)
    # ========================================================================
    # Extract session policy flags if available
    session_policy = policy_flags.get("session_policy_flags", {})

    # BADGE 5: Session Fragmented
    if session_policy.get("session_is_fragmented"):
        badges.append(DILchatBadge(
            label="Session Fragmented",
            level="warning",
            description="Multi-turn conversation coherence is fragmented. Consider stabilizing."
        ))

    # BADGE 6: Session Grounding Needed
    if session_policy.get("session_needs_grounding"):
        badges.append(DILchatBadge(
            label="Session Grounding Needed",
            level="warning",
            description="Session trajectory requires grounding. Use concrete, stabilizing responses."
        ))

    # BADGE 7: Session Deep Reflection Allowed
    if session_policy.get("session_allow_deep_reflection"):
        badges.append(DILchatBadge(
            label="Session Deep Reflection Allowed",
            level="info",
            description="Session is stable enough for deeper multi-turn exploration."
        ))

    # ========================================================================
    # MEMORY v2.0 BADGES (from session memory events)
    # ========================================================================
    if session_memory:
        recent_events = _get_recent_memory_events(session_memory, n=3)

        # BADGE 8: Memory Breakthrough
        if _has_event_type(recent_events, "breakthrough"):
            badges.append(DILchatBadge(
                label="Breakthrough Moment",
                level="info",
                description="Notable upward clarity shift detected in conversation."
            ))

        # BADGE 9: Memory Fragmentation
        if _has_event_type(recent_events, "fragmentation"):
            badges.append(DILchatBadge(
                label="Moment of Fragmentation",
                level="warning",
                description="Conversation stability momentarily broke. Consider grounding."
            ))

    # ========================================================================
    # SESSION RECAP v1.0 BADGES (from session summarizer)
    # ========================================================================
    if session_recap:
        overall_state = session_recap.get("overall_state")
        key_patterns = session_recap.get("key_patterns", [])

        # BADGE 10: Session Recap Fragmented
        if overall_state == "fragmented":
            badges.append(DILchatBadge(
                label="SESSION_FRAGMENTED",
                level="warning",
                description="Multi-turn session is in fragmented state. Consider grounding."
            ))

        # BADGE 11: Session Recap Recovering
        if overall_state == "recovering":
            badges.append(DILchatBadge(
                label="SESSION_RECOVERING",
                level="info",
                description="Multi-turn session is recovering. Coherence improving."
            ))

        # BADGE 12: Session Recap Breakthrough
        if "breakthrough_detected" in key_patterns:
            badges.append(DILchatBadge(
                label="BREAKTHROUGH",
                level="info",
                description="Session breakthrough detected. Notable clarity shift."
            ))

    # ========================================================================
    # INTENT ARC ENGINE v1.0 BADGES (from intent arc classification)
    # ========================================================================
    if intent_arc:
        arc_type = intent_arc.get("arc_type")

        # Add arc-specific badges
        if arc_type == "insight_arc":
            badges.append(DILchatBadge(
                label="INSIGHT",
                level="info",
                description="Insight arc detected. Breakthrough moments with strong upward trajectory."
            ))
        elif arc_type == "stabilization_arc":
            badges.append(DILchatBadge(
                label="STABILIZING",
                level="info",
                description="Stabilization arc detected. Coherence rising with low volatility."
            ))
        elif arc_type == "identity_arc":
            badges.append(DILchatBadge(
                label="IDENTITY_EXPLORATION",
                level="info",
                description="Identity arc detected. LAM-driven self-exploration in progress."
            ))
        elif arc_type == "resolution_arc":
            badges.append(DILchatBadge(
                label="RECOVERY_PATH",
                level="info",
                description="Resolution arc detected. Recovering from fragmentation through stabilization."
            ))
        elif arc_type == "chaotic_arc":
            badges.append(DILchatBadge(
                label="UNSTABLE_PATTERN",
                level="warning",
                description="Chaotic arc detected. High volatility with unstable coherence patterns."
            ))
        elif arc_type == "dissonance_arc":
            badges.append(DILchatBadge(
                label="DISSONANCE",
                level="warning",
                description="Dissonance arc detected. High persona drift with oscillating trajectory."
            ))
        elif arc_type == "expansion_arc":
            badges.append(DILchatBadge(
                label="EXPANSION",
                level="info",
                description="Expansion arc detected. HRM+LAM synergy with expanding context."
            ))
        elif arc_type == "avoidance_arc":
            badges.append(DILchatBadge(
                label="AVOIDANCE",
                level="warning",
                description="Avoidance arc detected. Flat coherence with minimal progression."
            ))

    # ========================================================================
    # IDENTITY SIGNATURE ENGINE v1.0 BADGES (from identity signature classification)
    # ========================================================================
    if identity_signature:
        signature_type = identity_signature.get("signature_type")

        # Add signature-specific badges
        if signature_type == "self_anchoring":
            badges.append(DILchatBadge(
                label="SELF_STABLE",
                level="info",
                description="Self-anchoring signature. Coherence rising with low persona drift."
            ))
        elif signature_type == "self_expansion":
            badges.append(DILchatBadge(
                label="SELF_EXPANDING",
                level="info",
                description="Self-expansion signature. LAM-driven identity exploration with high temporal arc."
            ))
        elif signature_type == "self_fragmentation":
            badges.append(DILchatBadge(
                label="SELF_FRAGMENTED",
                level="warning",
                description="Self-fragmentation signature. High persona drift with identity instability."
            ))
        elif signature_type == "self_suppression":
            badges.append(DILchatBadge(
                label="SELF_SUPPRESSED",
                level="warning",
                description="Self-suppression signature. Flat coherence with identity avoidance patterns."
            ))
        elif signature_type == "self_integration":
            badges.append(DILchatBadge(
                label="SELF_INTEGRATED",
                level="info",
                description="Self-integration signature. Breakthrough + stabilization with HRM+LAM synergy."
            ))
        elif signature_type == "self_dissonance":
            badges.append(DILchatBadge(
                label="SELF_DISSONANT",
                level="warning",
                description="Self-dissonance signature. Internal identity conflict with high volatility."
            ))
        elif signature_type == "self_discovery":
            badges.append(DILchatBadge(
                label="SELF_DISCOVERY",
                level="info",
                description="Self-discovery signature. Identity breakthrough with improving trajectory."
            ))

    # ========================================================================
    # BADGE 15: Motivation Profile Badges (Motivation Flow Engine v1.0)
    # ========================================================================
    if motivation_profile:
        motivation_type = motivation_profile.get("motivation_type")

        # Add motivation-specific badges (only for 6 non-ambiguous types)
        if motivation_type == "hope_driven":
            badges.append(DILchatBadge(
                label="HOPE_DRIVEN",
                level="info",
                description="Hope-driven motivation. Upward trajectory with breakthrough moments."
            ))
        elif motivation_type == "fear_driven":
            badges.append(DILchatBadge(
                label="FEAR_DRIVEN",
                level="warning",
                description="Fear-driven motivation. Fragmentation and volatility present. Needs support."
            ))
        elif motivation_type == "avoidance_driven":
            badges.append(DILchatBadge(
                label="AVOIDANCE",
                level="warning",
                description="Avoidance-driven motivation. Suppressed expression with defensive patterns."
            ))
        elif motivation_type == "expansion_driven":
            badges.append(DILchatBadge(
                label="EXPANSION",
                level="info",
                description="Expansion-driven motivation. Active exploration with rising temporal arc."
            ))
        elif motivation_type == "stabilization_driven":
            badges.append(DILchatBadge(
                label="STABILIZATION",
                level="info",
                description="Stabilization-driven motivation. Recovery pattern with decreasing volatility."
            ))
        elif motivation_type == "assertion_driven":
            badges.append(DILchatBadge(
                label="ASSERTIVE",
                level="info",
                description="Assertion-driven motivation. Strong self-expression with HRM dominance."
            ))
        # Note: overcorrection and ambiguous_motivation don't get badges (as specified)

    # ========================================================================
    # BADGE 16: Trading Guardrail Badges (Phase 7: Formula-Aware Trading Guardrails v1.0)
    # ========================================================================
    if trading_guardrails:
        # HIGH_TENSION_RISK badge
        if trading_guardrails.get("high_tension_risk"):
            badges.append(DILchatBadge(
                label="HIGH_TENSION_RISK",
                level="critical",
                description="High tension corridor with low resonance detected. Trading risk elevated."
            ))

        # NEG_MOMENTUM_RISK badge
        if trading_guardrails.get("negative_momentum_risk"):
            badges.append(DILchatBadge(
                label="NEG_MOMENTUM_RISK",
                level="critical",
                description="Negative delta SMI with low coherence detected. Downward momentum present."
            ))

        # VOLATILITY_RISK badge
        if trading_guardrails.get("volatility_risk"):
            badges.append(DILchatBadge(
                label="VOLATILITY_RISK",
                level="critical",
                description="High mapper volatility with persona drift detected. Market instability elevated."
            ))

        # NO_ACTION_RECOMMENDED badge (master switch)
        if trading_guardrails.get("recommend_no_action"):
            badges.append(DILchatBadge(
                label="NO_ACTION_RECOMMENDED",
                level="critical",
                description="Trading guardrails recommend no action. Wait for stability before trading."
            ))

    return badges


# ============================================================================
# Hint Building Logic
# ============================================================================


def _build_hints(
    policy_flags: Dict[str, Any],
    session_memory: Optional[Dict[str, Any]] = None,
    session_recap: Optional[Dict[str, Any]] = None,
    intent_arc: Optional[Dict[str, Any]] = None,
    identity_signature: Optional[Dict[str, Any]] = None,
    motivation_profile: Optional[Dict[str, Any]] = None,
    trading_guardrails: Optional[Dict[str, Any]] = None,
    coherence: Optional[Dict[str, Any]] = None,
    domain: Optional[str] = None,
) -> List[DILchatHint]:
    """
    Build UI hints based on policy flags.

    Hint Rules:
        1. GROUNDING - if needs_grounding=True
        2. DEEP_REFLECTION - if allow_deep_reflection=True
        3. PREFER_CONCRETE - if prefer_concrete=True
        4. PREFER_ARC - if prefer_arc_mode=True
        5. COHERENCE_ALERT - if coherence_warning=True
        6. GROUNDING_MODE - if session_recommended_style="grounded"
        7. REFLECTION_MODE - if session_recommended_style="reflective"
        8. EXPLORATION_OK - if session_recommended_style="exploratory"
        9. STATE_CHANGED - if recent mapper flip
        10. SESSION_RECOVERING - if recent stabilization
        11. RECAP_GROUNDING_MODE - if recap.recommended_style="grounded"
        12. RECAP_REFLECTION_MODE - if recap.recommended_style="reflective"
        13. RECAP_EXPLORATION_OK - if recap.recommended_style="exploratory"
        14. Identity Signature Hints (explore_identity, stabilize_identity, etc.)
        15. Motivation Profile Hints (encourage_exploration, stabilize_self, address_avoidance, etc.)
        16. Trading Guardrail Hints (avoid_trade, wait_for_stability, market_volatility_alert)
        17. Phase 12 v3 Confidence Hints (v3_confidence_high, v3_confidence_medium, v3_confidence_low)
        18. Phase 15 Interaction Mode Hints (stable_neutral, self_reflection_allowed, deep_adaptive_active)

    Args:
        policy_flags: Policy flags dictionary (includes session_policy_flags if available)
        session_memory: Session memory dictionary with events
        session_recap: Session recap dictionary with multi-turn summary
        intent_arc: Intent arc dictionary with arc classification
        identity_signature: Identity signature dictionary with signature classification
        motivation_profile: Motivation profile dictionary with motivational driver classification
        trading_guardrails: Trading guardrails dictionary with risk flags
        coherence: Coherence dictionary with v3 quality (Phase 12)
        domain: Domain identifier (Phase 12)

    Returns:
        List of DILchatHint objects
    """
    hints = []

    # ========================================================================
    # HINT 1: GROUNDING
    # ========================================================================
    if policy_flags.get("needs_grounding"):
        hints.append(DILchatHint(
            code="GROUNDING",
            message="Keep responses concrete, short, and stabilizing."
        ))

    # ========================================================================
    # HINT 2: DEEP_REFLECTION
    # ========================================================================
    if policy_flags.get("allow_deep_reflection"):
        hints.append(DILchatHint(
            code="DEEP_REFLECTION",
            message="It's safe to explore deeper emotions or identity themes."
        ))

    # ========================================================================
    # HINT 3: PREFER_CONCRETE
    # ========================================================================
    if policy_flags.get("prefer_concrete"):
        hints.append(DILchatHint(
            code="PREFER_CONCRETE",
            message="Emphasize steps and practical guidance."
        ))

    # ========================================================================
    # HINT 4: PREFER_ARC
    # ========================================================================
    if policy_flags.get("prefer_arc_mode"):
        hints.append(DILchatHint(
            code="PREFER_ARC",
            message="Highlight temporal patterns and long-term arcs."
        ))

    # ========================================================================
    # HINT 5: COHERENCE_ALERT
    # ========================================================================
    if policy_flags.get("coherence_warning"):
        hints.append(DILchatHint(
            code="COHERENCE_ALERT",
            message="Conversation coherence is degraded. Suggest recentering or summarizing."
        ))

    # ========================================================================
    # SESSION-LEVEL HINTS (from session policy layer)
    # ========================================================================
    # Extract session policy flags if available
    session_policy = policy_flags.get("session_policy_flags", {})

    # Get recommended style from session policy
    recommended_style = session_policy.get("session_recommended_style")

    # HINT 6: GROUNDING_MODE
    if recommended_style == "grounded":
        hints.append(DILchatHint(
            code="GROUNDING_MODE",
            message="Session trajectory recommends grounding mode. Use concrete, practical responses."
        ))

    # HINT 7: REFLECTION_MODE
    elif recommended_style == "reflective":
        hints.append(DILchatHint(
            code="REFLECTION_MODE",
            message="Session trajectory recommends reflective mode. Deep exploration is safe."
        ))

    # HINT 8: EXPLORATION_OK
    elif recommended_style == "exploratory":
        hints.append(DILchatHint(
            code="EXPLORATION_OK",
            message="Session trajectory supports exploration. Curious, open-ended responses work well."
        ))

    # ========================================================================
    # MEMORY v2.0 HINTS (from session memory events)
    # ========================================================================
    if session_memory:
        recent_events = _get_recent_memory_events(session_memory, n=3)

        # HINT 9: STATE_CHANGED
        if _has_event_type(recent_events, "mapper_flip"):
            hints.append(DILchatHint(
                code="STATE_CHANGED",
                message="Mapper configuration changed. System adapted to new query patterns."
            ))

        # HINT 10: SESSION_RECOVERING
        if _has_event_type(recent_events, "stabilization"):
            hints.append(DILchatHint(
                code="SESSION_RECOVERING",
                message="Conversation trajectory is stabilizing. Coherence is improving."
            ))

    # ========================================================================
    # SESSION RECAP v1.0 HINTS (from session summarizer)
    # ========================================================================
    if session_recap:
        recommended_style = session_recap.get("recommended_style")

        # HINT 11: RECAP_GROUNDING_MODE
        if recommended_style == "grounded":
            hints.append(DILchatHint(
                code="GROUNDING_MODE",
                message="Session recap recommends grounding mode. Use concrete, practical responses."
            ))

        # HINT 12: RECAP_REFLECTION_MODE
        elif recommended_style == "reflective":
            hints.append(DILchatHint(
                code="REFLECTION_MODE",
                message="Session recap recommends reflective mode. Deep exploration is safe."
            ))

        # HINT 13: RECAP_EXPLORATION_OK
        elif recommended_style == "exploratory":
            hints.append(DILchatHint(
                code="EXPLORATION_OK",
                message="Session recap supports exploration. Curious, open-ended responses work well."
            ))

    # ========================================================================
    # INTENT ARC ENGINE v1.0 HINTS (from intent arc classification)
    # ========================================================================
    if intent_arc:
        arc_type = intent_arc.get("arc_type")

        # Add arc-specific hints
        if arc_type in ["insight_arc", "identity_arc"]:
            hints.append(DILchatHint(
                code="PROMOTE_REFLECTION",
                message="Intent arc suggests reflective mode. Deep exploration and identity themes are safe."
            ))
        elif arc_type in ["chaotic_arc", "dissonance_arc"]:
            hints.append(DILchatHint(
                code="PROMOTE_GROUNDING",
                message="Intent arc suggests grounding mode. Use concrete, stabilizing responses."
            ))
        elif arc_type == "stabilization_arc":
            hints.append(DILchatHint(
                code="ENCOURAGE_STABILITY",
                message="Intent arc shows stabilization. Continue current approach to maintain coherence."
            ))
        elif arc_type == "expansion_arc":
            hints.append(DILchatHint(
                code="EXPLORATION_OK",
                message="Intent arc shows expansion. Complex, multi-layered exploration is appropriate."
            ))

    # ========================================================================
    # IDENTITY SIGNATURE ENGINE v1.0 HINTS (from identity signature classification)
    # ========================================================================
    if identity_signature:
        signature_type = identity_signature.get("signature_type")

        # Add signature-specific hints
        if signature_type == "self_anchoring":
            hints.append(DILchatHint(
                code="MAINTAIN_STABILITY",
                message="Identity signature is self-anchoring. Continue current approach to maintain stability."
            ))
        elif signature_type == "self_expansion":
            hints.append(DILchatHint(
                code="EXPLORE_IDENTITY",
                message="Identity signature is self-expanding. Support identity exploration and LAM-driven themes."
            ))
        elif signature_type == "self_fragmentation":
            hints.append(DILchatHint(
                code="STABILIZE_IDENTITY",
                message="Identity signature is self-fragmenting. Use grounding responses to stabilize identity coherence."
            ))
        elif signature_type == "self_suppression":
            hints.append(DILchatHint(
                code="GROUNDSELF",
                message="Identity signature is self-suppressing. Avoid deep identity exploration, use concrete grounding."
            ))
        elif signature_type == "self_integration":
            hints.append(DILchatHint(
                code="SUPPORT_INTEGRATION",
                message="Identity signature is self-integrating. Support integration process with balanced responses."
            ))
        elif signature_type == "self_dissonance":
            hints.append(DILchatHint(
                code="ADDRESS_DISSONANCE",
                message="Identity signature is self-dissonant. Address internal conflicts with empathetic responses."
            ))
        elif signature_type == "self_discovery":
            hints.append(DILchatHint(
                code="REFLECT_IDENTITY",
                message="Identity signature is self-discovery. Support identity breakthroughs with reflective responses."
            ))

    # ========================================================================
    # MOTIVATION FLOW ENGINE v1.0 HINTS (from motivation profile classification)
    # ========================================================================
    if motivation_profile:
        motivation_type = motivation_profile.get("motivation_type")

        # Add motivation-specific hints (5 deterministic mappings)
        if motivation_type == "hope_driven":
            hints.append(DILchatHint(
                code="ENCOURAGE_EXPLORATION",
                message="Motivation is hope-driven. Encourage continued exploration and positive momentum."
            ))
        elif motivation_type == "fear_driven":
            hints.append(DILchatHint(
                code="CALM_FEAR",
                message="Motivation is fear-driven. Use calming, supportive responses to address fragmentation."
            ))
        elif motivation_type == "avoidance_driven":
            hints.append(DILchatHint(
                code="ADDRESS_AVOIDANCE",
                message="Motivation is avoidance-driven. Gently encourage expression while respecting boundaries."
            ))
        elif motivation_type == "expansion_driven":
            hints.append(DILchatHint(
                code="ENCOURAGE_EXPLORATION",
                message="Motivation is expansion-driven. Support active exploration and LAM-driven identity themes."
            ))
        elif motivation_type == "stabilization_driven":
            hints.append(DILchatHint(
                code="STABILIZE_SELF",
                message="Motivation is stabilization-driven. Maintain stable, supportive responses to aid recovery."
            ))
        elif motivation_type == "assertion_driven":
            hints.append(DILchatHint(
                code="SUPPORT_ASSERTION",
                message="Motivation is assertion-driven. Support strong self-expression and symbolic reasoning."
            ))
        # Note: overcorrection and ambiguous_motivation don't get hints

    # ========================================================================
    # TRADING GUARDRAIL HINTS (Phase 7: Formula-Aware Trading Guardrails v1.0)
    # ========================================================================
    if trading_guardrails:
        # AVOID_TRADE hint (if recommend_no_action is True)
        if trading_guardrails.get("recommend_no_action"):
            hints.append(DILchatHint(
                code="AVOID_TRADE",
                message="Trading guardrails recommend avoiding trades. High risk conditions detected."
            ))

        # WAIT_FOR_STABILITY hint (if high_tension_risk or negative_momentum_risk)
        if trading_guardrails.get("high_tension_risk") or trading_guardrails.get("negative_momentum_risk"):
            hints.append(DILchatHint(
                code="WAIT_FOR_STABILITY",
                message="Wait for coherence and momentum stability before trading."
            ))

        # MARKET_VOLATILITY_ALERT hint (if volatility_risk)
        if trading_guardrails.get("volatility_risk"):
            hints.append(DILchatHint(
                code="MARKET_VOLATILITY_ALERT",
                message="Market volatility elevated. Mapper instability and persona drift detected."
            ))

    # ========================================================================
    # PHASE 12 v3 CONFIDENCE HINTS (v3 quality as interpretation confidence)
    # ========================================================================
    # Only expose v3 confidence hints for therapy/identity domains where v3 is enabled
    if coherence and domain in ["therapy", "identity"]:
        coherence_score_v3 = coherence.get("coherence_score_v3")
        coherence_v3_quality = coherence.get("coherence_v3_quality")

        # Only add v3 confidence hints if both v3 and quality are available
        if coherence_score_v3 is not None and coherence_v3_quality is not None:
            # Classify quality into 3 ranges: high, medium, low
            if coherence_v3_quality >= 0.7:
                hints.append(DILchatHint(
                    code="V3_CONFIDENCE_HIGH",
                    message="v3 interpretation confidence is high. Formula signals are stable and aligned."
                ))
            elif coherence_v3_quality >= 0.4:
                hints.append(DILchatHint(
                    code="V3_CONFIDENCE_MEDIUM",
                    message="v3 interpretation confidence is medium. Some formula signal instability present."
                ))
            else:
                hints.append(DILchatHint(
                    code="V3_CONFIDENCE_LOW",
                    message="v3 interpretation confidence is low. Formula signals are unstable or divergent."
                ))

    # ========================================================================
    # PHASE 15 INTERACTION MODE HINTS (mode-based adaptive hints)
    # ========================================================================
    # Extract interaction mode from policy flags
    interaction_mode = policy_flags.get("interaction_mode")

    if interaction_mode:
        # ANALYTICS_ONLY mode: Standard behavior, no formula influence
        if interaction_mode == "analytics_only":
            hints.append(DILchatHint(
                code="HINT_STABLE_NEUTRAL",
                message="Analytics mode active. Standard deterministic behavior, no formula-based adaptation."
            ))

        # SMART_INSIGHT mode: Soft UI-layer refinement enabled
        elif interaction_mode == "smart_insight":
            hints.append(DILchatHint(
                code="HINT_SELF_REFLECTION_ALLOWED",
                message="Smart insight mode active. UI-layer formula refinement enabled for deeper exploration."
            ))

        # DEEP_ADAPTIVE mode: Full adaptive mode with VMF/ATH hints
        elif interaction_mode == "deep_adaptive":
            hints.append(DILchatHint(
                code="HINT_DEEP_ADAPTIVE_ACTIVE",
                message="Deep adaptive mode active. VMF/ATH emotional arc hints enabled for adaptive responses."
            ))

            # Add VMF emotional momentum hint if available
            vmf_momentum = policy_flags.get("vmf_emotional_momentum")
            if vmf_momentum:
                if vmf_momentum == "rising":
                    hints.append(DILchatHint(
                        code="VMF_MOMENTUM_RISING",
                        message="Emotional momentum is rising. User is in an upward emotional arc."
                    ))
                elif vmf_momentum == "falling":
                    hints.append(DILchatHint(
                        code="VMF_MOMENTUM_FALLING",
                        message="Emotional momentum is falling. Consider supportive, stabilizing responses."
                    ))
                elif vmf_momentum == "stable":
                    hints.append(DILchatHint(
                        code="VMF_MOMENTUM_STABLE",
                        message="Emotional momentum is stable. Current approach is effective."
                    ))

            # Add ATH arc-tension state hint if available
            ath_state = policy_flags.get("ath_arc_tension_state")
            if ath_state:
                if ath_state == "harmonized":
                    hints.append(DILchatHint(
                        code="ATH_HARMONIZED",
                        message="Arc-tension harmonized. User is in balanced state for exploration."
                    ))
                elif ath_state == "building":
                    hints.append(DILchatHint(
                        code="ATH_BUILDING",
                        message="Arc-tension building. Monitor for breakthrough or release moments."
                    ))
                elif ath_state == "releasing":
                    hints.append(DILchatHint(
                        code="ATH_RELEASING",
                        message="Arc-tension releasing. Support the emotional resolution process."
                    ))

    return hints


# ============================================================================
# Helper Functions
# ============================================================================


def _remove_none_values(d: Any) -> Any:
    """
    Recursively remove None values from dictionary.

    Args:
        d: Dictionary, list, or value to process

    Returns:
        Cleaned structure with None values removed
    """
    if isinstance(d, dict):
        return {k: _remove_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [_remove_none_values(item) for item in d if item is not None]
    else:
        return d


def _get_recent_memory_events(session_memory: Dict[str, Any], n: int) -> List[Dict[str, Any]]:
    """
    Get the N most recent memory events from session memory.

    Args:
        session_memory: Session memory dictionary
        n: Number of recent events to retrieve

    Returns:
        List of recent memory event dictionaries
    """
    if not session_memory or 'events' not in session_memory:
        return []

    events = session_memory.get('events', [])
    return events[-n:] if n > 0 else []


def _has_event_type(events: List[Dict[str, Any]], event_type: str) -> bool:
    """
    Check if any event in the list matches the given event type.

    Args:
        events: List of memory event dictionaries
        event_type: Event type to check for

    Returns:
        True if any event matches the type, False otherwise
    """
    return any(e.get('event_type') == event_type for e in events)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    'DILchatBadge',
    'DILchatHint',
    'DILchatResponse',
    'build_dilchat_response',
    'build_dilchat_payload',
]
