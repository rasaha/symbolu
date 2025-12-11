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

    # Phase 16: Formula Fusion Stabilizer (diagnostics only - not used for badges/hints)
    stabilizer: Optional[Dict[str, Optional[float]]] = None

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
        coherence=coherence,
        domain=response_domain,
        unified_output=unified_output,
    )

    # ========================================================================
    # STEP 6: Build hints (includes session memory + session recap + intent arc + identity signature + motivation + trading guardrail + v3 confidence hints + APEL)
    # ========================================================================
    # Extract persona_echo_profile from unified_output (Phase 31)
    persona_echo_profile = unified_output.get("persona_echo_profile")

    hints = _build_hints(combined_flags, session_memory, session_recap, intent_arc, identity_signature, motivation_profile, trading_guardrails, coherence, domain, persona_echo_profile)

    # ========================================================================
    # STEP 7: Extract Phase 2 formulas (diagnostics only)
    # ========================================================================
    formulas_data = unified_output.get("formulas")

    # ========================================================================
    # STEP 7b: Extract Phase 16 Formula Fusion Stabilizer (diagnostics only)
    # ========================================================================
    # Stabilizer data can come from coherence block or top-level formulas
    stabilizer_data = coherence.get("stabilizer") or unified_output.get("stabilizer")

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
        stabilizer=stabilizer_data,
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
    coherence: Optional[Dict[str, Any]] = None,
    domain: Optional[str] = None,
    unified_output: Optional[Dict[str, Any]] = None,
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
        17. Symbolic Harmonization Badges (Phase 28) - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only

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
        coherence: Coherence dictionary with symbolic harmonization data
        domain: Domain identifier (e.g., "therapy", "identity", "trading")

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
    # Phase 28: Symbolic Harmonization Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract symbolic harmonization from coherence if available
    symbolic_harmonization = coherence.get("symbolic_harmonization", {}) if coherence else {}
    symbolic_harmonization_index = symbolic_harmonization.get("index") or symbolic_harmonization.get("symbolic_harmonization_index")

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    therapy_or_identity_domain = domain in ["therapy", "identity"]
    smart_or_deep_mode = policy_flags.get("interaction_mode") in ["smart_insight", "deep_adaptive"]

    if therapy_or_identity_domain and smart_or_deep_mode and symbolic_harmonization_index is not None:
        # SYMBOLIC_HARMONY_HIGH: >= 0.75
        if symbolic_harmonization_index >= 0.75:
            badges.append(DILchatBadge(
                label="SYMBOLIC_HARMONY_HIGH",
                level="info",
                description="Symbolic harmonization is high. Meaning layers, practical grounding, and mirror tensions are well-aligned."
            ))
        # SYMBOLIC_HARMONY_MEDIUM: 0.50 - 0.75
        elif symbolic_harmonization_index >= 0.50:
            badges.append(DILchatBadge(
                label="SYMBOLIC_HARMONY_MEDIUM",
                level="info",
                description="Symbolic harmonization is moderate. Core meaning structures are coherent."
            ))
        # SYMBOLIC_HARMONY_LOW: < 0.50
        else:
            badges.append(DILchatBadge(
                label="SYMBOLIC_HARMONY_LOW",
                level="warning",
                description="Symbolic harmonization is low. Meaning layers show misalignment."
            ))

    # ========================================================================
    # Phase 29: Persona Resonance Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract persona resonance from coherence observation
    persona_resonance_bias = coherence.get("persona_resonance_bias") if coherence else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and persona_resonance_bias is not None:
        # PERSONA_HARMONY_POSITIVE: positive bias (+0.02 to +0.05)
        if persona_resonance_bias >= 0.02:
            badges.append(DILchatBadge(
                label="PERSONA_HARMONY_POSITIVE",
                level="info",
                description="Persona tone is slightly softer and more expressive due to high symbolic harmonization."
            ))
        # PERSONA_HARMONY_NEUTRAL: neutral bias (-0.01 to +0.01)
        elif -0.01 <= persona_resonance_bias <= 0.01:
            badges.append(DILchatBadge(
                label="PERSONA_HARMONY_NEUTRAL",
                level="info",
                description="Persona tone is neutral with no harmonization-based adjustment."
            ))
        # PERSONA_HARMONY_NEGATIVE: negative bias (-0.05 to -0.02)
        elif persona_resonance_bias <= -0.02:
            badges.append(DILchatBadge(
                label="PERSONA_HARMONY_NEGATIVE",
                level="info",
                description="Persona tone is slightly simpler and grounded due to low symbolic harmonization."
            ))

    # ========================================================================
    # Phase 30: Cross-Layer Resonance Persona Mapping Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract persona_resonance_map from unified_output
    persona_resonance_map = unified_output.get("persona_resonance_map") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and persona_resonance_map is not None:
        # Extract modulation parameters from the map
        modulation_params = persona_resonance_map.get("modulation_parameters", {})
        raw_signals = persona_resonance_map.get("raw_signals", {})

        metaphor_weight = modulation_params.get("metaphor_weight")
        warmth_weight = modulation_params.get("warmth_weight")
        structure_weight = modulation_params.get("structure_weight")
        grounding_bias = modulation_params.get("grounding_bias")

        cognitive_drift_v3 = raw_signals.get("cognitive_drift_v3")
        ucf_csi = raw_signals.get("ucf_csi")

        # PERSONA_RESONANCE_HIGH: high metaphor + warmth (≥ 0.65 average)
        if metaphor_weight is not None and warmth_weight is not None:
            avg_resonance = (metaphor_weight + warmth_weight) / 2.0
            if avg_resonance >= 0.65:
                badges.append(DILchatBadge(
                    label="PERSONA_RESONANCE_HIGH",
                    level="info",
                    description="Cross-layer resonance signals high metaphor and warmth. Tone is expressive and symbolic."
                ))

        # PERSONA_RESONANCE_LOW: high structure + grounding (≥ 0.65 average)
        if structure_weight is not None and grounding_bias is not None:
            avg_grounding = (structure_weight + grounding_bias) / 2.0
            if avg_grounding >= 0.65:
                badges.append(DILchatBadge(
                    label="PERSONA_RESONANCE_LOW",
                    level="info",
                    description="Cross-layer resonance signals high structure and grounding. Tone is practical and concrete."
                ))

        # PERSONA_RESONANCE_BALANCED: mid-range on all weights
        if (metaphor_weight is not None and warmth_weight is not None and
            structure_weight is not None and grounding_bias is not None):
            all_weights = [metaphor_weight, warmth_weight, structure_weight, grounding_bias]
            avg_all = sum(all_weights) / len(all_weights)
            if 0.45 <= avg_all <= 0.55:
                badges.append(DILchatBadge(
                    label="PERSONA_RESONANCE_BALANCED",
                    level="info",
                    description="Cross-layer resonance signals balanced tone modulation across all parameters."
                ))

        # PERSONA_RESONANCE_DRIFT_CAUTION: high cognitive drift (≥ 0.60)
        if cognitive_drift_v3 is not None and cognitive_drift_v3 >= 0.60:
            badges.append(DILchatBadge(
                label="PERSONA_RESONANCE_DRIFT_CAUTION",
                level="warning",
                description="High cognitive drift detected. Grounding bias increased to stabilize tone."
            ))

        # PERSONA_RESONANCE_STABILITY_STRONG: high UCF stability (≥ 0.70)
        if ucf_csi is not None and ucf_csi >= 0.70:
            badges.append(DILchatBadge(
                label="PERSONA_RESONANCE_STABILITY_STRONG",
                level="info",
                description="Unified consciousness stability is high. Tone modulation is stable and consistent."
            ))

    # ========================================================================
    # Phase 32: Insight Window Gating Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract insight_window from policy_flags if available
    insight_window = policy_flags.get("insight_window", {})

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and insight_window:
        insight_window_open = insight_window.get("insight_window_open", False)
        insight_mode = insight_window.get("insight_mode", "none")
        insight_tags = insight_window.get("insight_tags", [])

        # INSIGHT_WINDOW_OPEN: Window is open for deeper reflection
        if insight_window_open and insight_mode != "none":
            badges.append(DILchatBadge(
                label="INSIGHT_WINDOW_OPEN",
                level="info",
                description=f"Insight window open ({insight_mode} mode). UCF signals indicate readiness for deeper reflection."
            ))

        # INSIGHT_WINDOW_DEEP: Deep insight mode active
        if insight_mode == "deep":
            badges.append(DILchatBadge(
                label="INSIGHT_WINDOW_DEEP",
                level="info",
                description="Deep insight mode active. Meta-insight and symbolic interpretation enabled."
            ))

        # INSIGHT_WINDOW_CAUTION_ENTROPY: High entropy or transitional state
        if "entropy_high" in insight_tags or "entropy_transitional" in insight_tags:
            badges.append(DILchatBadge(
                label="INSIGHT_WINDOW_CAUTION_ENTROPY",
                level="warning",
                description="Entropy caution: temporal field shows volatility or transition."
            ))

        # INSIGHT_WINDOW_CAUTION_DRIFT: Drift risk detected
        if "drift_caution" in insight_tags:
            badges.append(DILchatBadge(
                label="INSIGHT_WINDOW_CAUTION_DRIFT",
                level="warning",
                description="Drift caution: cognitive drift elevated, monitor stability."
            ))

        # INSIGHT_WINDOW_CLOSED: Window is closed (only if domain/mode gates passed but window closed)
        if not insight_window_open and insight_mode == "none":
            # Only add if we're in the right domain/mode but window closed due to metrics
            badges.append(DILchatBadge(
                label="INSIGHT_WINDOW_CLOSED",
                level="info",
                description="Insight window closed. UCF signals indicate reflection not recommended at this time."
            ))

    # ========================================================================
    # Phase 33: Persona Schema Adaptive Routing Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract schema_adaptive_map from unified_output
    schema_adaptive_map = unified_output.get("schema_adaptive_map") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and schema_adaptive_map is not None:
        # Extract schema alignment metrics
        schema_alignment_scores = schema_adaptive_map.get("schema_alignment_scores", {})
        schema_confidence = schema_adaptive_map.get("schema_confidence")
        schema_stability = schema_adaptive_map.get("schema_stability")
        schema_drift = schema_adaptive_map.get("schema_drift")
        schema_tags = schema_adaptive_map.get("schema_tags", [])

        # SCHEMA_ALIGNMENT_HIGH: Dominant persona alignment >= 0.70
        if schema_alignment_scores:
            max_alignment = max(schema_alignment_scores.values()) if schema_alignment_scores else 0.0
            if max_alignment >= 0.70:
                # Find the persona with max alignment
                max_persona = max(schema_alignment_scores, key=schema_alignment_scores.get)
                badges.append(DILchatBadge(
                    label="SCHEMA_ALIGNMENT_HIGH",
                    level="info",
                    description=f"High persona schema alignment detected ({max_persona.title()}: {max_alignment:.2f}). User patterns strongly match {max_persona} schema."
                ))

        # SCHEMA_ALIGNMENT_LOW: All persona alignments < 0.40
        if schema_alignment_scores:
            all_low = all(score < 0.40 for score in schema_alignment_scores.values())
            if all_low:
                badges.append(DILchatBadge(
                    label="SCHEMA_ALIGNMENT_LOW",
                    level="warning",
                    description="Low schema alignment across all personas. User patterns do not strongly match any schema."
                ))

        # SCHEMA_STABILITY_STRONG: Schema stability >= 0.80
        if schema_stability is not None and schema_stability >= 0.80:
            badges.append(DILchatBadge(
                label="SCHEMA_STABILITY_STRONG",
                level="info",
                description="Schema fit is highly stable. User patterns show consistent persona alignment over time."
            ))

        # SCHEMA_DRIFT_CAUTION: Schema drift >= 0.50
        if schema_drift is not None and schema_drift >= 0.50:
            badges.append(DILchatBadge(
                label="SCHEMA_DRIFT_CAUTION",
                level="warning",
                description="Schema drift detected. User's persona alignment patterns are shifting significantly."
            ))

    # ========================================================================
    # Phase 34: Identity Harmonics Layer Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract identity_harmonics from unified_output
    identity_harmonics = unified_output.get("identity_harmonics") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and identity_harmonics is not None:
        # Extract identity harmonics metrics
        cih = identity_harmonics.get("cih")
        aih = identity_harmonics.get("aih")
        rih = identity_harmonics.get("rih")
        ihi = identity_harmonics.get("ihi")
        identity_stability_score = identity_harmonics.get("identity_stability_score")
        identity_flexibility_score = identity_harmonics.get("identity_flexibility_score")
        identity_harmonics_tags = identity_harmonics.get("identity_harmonics_tags", [])

        # IDENTITY_HARMONICS_HIGH: Overall IHI >= 0.75
        if ihi is not None and ihi >= 0.75:
            badges.append(DILchatBadge(
                label="IDENTITY_HARMONICS_HIGH",
                level="info",
                description=f"High identity harmonics alignment (IHI: {ihi:.2f}). Strong identity coherence across semantic, adaptive, and relational dimensions."
            ))

        # IDENTITY_HARMONICS_MEDIUM: Overall IHI between 0.50 and 0.75
        elif ihi is not None and 0.50 <= ihi < 0.75:
            badges.append(DILchatBadge(
                label="IDENTITY_HARMONICS_MEDIUM",
                level="info",
                description=f"Medium identity harmonics alignment (IHI: {ihi:.2f}). Moderate identity coherence."
            ))

        # IDENTITY_HARMONICS_LOW: Overall IHI < 0.50
        elif ihi is not None and ihi < 0.50:
            badges.append(DILchatBadge(
                label="IDENTITY_HARMONICS_LOW",
                level="warning",
                description=f"Low identity harmonics alignment (IHI: {ihi:.2f}). Identity coherence may be fragmented."
            ))

        # IDENTITY_FLEXIBILITY_HIGH: AIH >= 0.70
        if aih is not None and aih >= 0.70:
            badges.append(DILchatBadge(
                label="IDENTITY_FLEXIBILITY_HIGH",
                level="info",
                description=f"High adaptive identity harmonic (AIH: {aih:.2f}). Strong capacity for coherent identity shifts."
            ))

        # IDENTITY_STABILITY_STRONG: CIH >= 0.75
        if cih is not None and cih >= 0.75:
            badges.append(DILchatBadge(
                label="IDENTITY_STABILITY_STRONG",
                level="info",
                description=f"Strong core identity stability (CIH: {cih:.2f}). Consistent identity signals across turns."
            ))

    # ========================================================================
    # Phase 35: Predictive Persona Drift Model Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract predictive_persona_drift from unified_output
    predictive_drift = unified_output.get("predictive_persona_drift") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and predictive_drift is not None:
        # Extract predictive drift metrics
        drift_magnitude = predictive_drift.get("magnitude")
        drift_direction = predictive_drift.get("direction", {})
        drift_stability = predictive_drift.get("stability")
        drift_band = predictive_drift.get("band")
        drift_tags = predictive_drift.get("tags", [])

        # PREDICTIVE_DRIFT_HIGH: Drift magnitude >= 0.65 OR drift band = HIGH
        if (drift_magnitude is not None and drift_magnitude >= 0.65) or drift_band == "HIGH":
            badges.append(DILchatBadge(
                label="PREDICTIVE_DRIFT_HIGH",
                level="warning",
                description=f"High predicted persona drift (magnitude: {drift_magnitude:.2f if drift_magnitude else 'N/A'}). Tone may shift in coming turns."
            ))

        # PREDICTIVE_DRIFT_MEDIUM: Drift band = MEDIUM
        elif drift_band == "MEDIUM":
            badges.append(DILchatBadge(
                label="PREDICTIVE_DRIFT_MEDIUM",
                level="info",
                description=f"Medium predicted persona drift (magnitude: {drift_magnitude:.2f if drift_magnitude else 'N/A'}). Moderate drift tendency detected."
            ))

        # PREDICTIVE_DRIFT_LOW: Drift band = LOW
        elif drift_band == "LOW":
            badges.append(DILchatBadge(
                label="PREDICTIVE_DRIFT_LOW",
                level="info",
                description=f"Low predicted persona drift (magnitude: {drift_magnitude:.2f if drift_magnitude else 'N/A'}). Stable trajectory expected."
            ))

        # DRIFT_DIRECTION_STRUCTURE: toward_structure >= 0.60
        if drift_direction.get("toward_structure", 0.0) >= 0.60:
            badges.append(DILchatBadge(
                label="DRIFT_DIRECTION_STRUCTURE",
                level="info",
                description="Drift direction: toward structure. Future tone may become more logical and precise."
            ))

        # DRIFT_DIRECTION_WARMTH: toward_warmth >= 0.60
        if drift_direction.get("toward_warmth", 0.0) >= 0.60:
            badges.append(DILchatBadge(
                label="DRIFT_DIRECTION_WARMTH",
                level="info",
                description="Drift direction: toward warmth. Future tone may become more empathic and connected."
            ))

        # DRIFT_DIRECTION_GROUNDING: toward_grounding >= 0.60
        if drift_direction.get("toward_grounding", 0.0) >= 0.60:
            badges.append(DILchatBadge(
                label="DRIFT_DIRECTION_GROUNDING",
                level="info",
                description="Drift direction: toward grounding. Future tone may become more stable and rooted."
            ))

        # DRIFT_STABILITY_STRONG: Drift stability >= 0.70
        if drift_stability is not None and drift_stability >= 0.70:
            badges.append(DILchatBadge(
                label="DRIFT_STABILITY_STRONG",
                level="info",
                description=f"Strong drift trajectory stability (DSS: {drift_stability:.2f}). Prediction confidence is high."
            ))

        # DRIFT_STABILITY_WEAK: Drift stability < 0.40
        elif drift_stability is not None and drift_stability < 0.40:
            badges.append(DILchatBadge(
                label="DRIFT_STABILITY_WEAK",
                level="warning",
                description=f"Weak drift trajectory stability (DSS: {drift_stability:.2f}). Prediction confidence is low."
            ))

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

    # ========================================================================
    # Phase 37: Adaptive Continuity Engine Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract adaptive continuity from unified_output if available
    adaptive_continuity = None
    if unified_output and "adaptive_continuity" in unified_output:
        adaptive_continuity = unified_output.get("adaptive_continuity")

    # Extract continuity metrics
    continuity_css = None
    continuity_band = None
    continuity_tags = []

    if adaptive_continuity is not None and isinstance(adaptive_continuity, dict):
        continuity_css = adaptive_continuity.get("css")
        continuity_band = adaptive_continuity.get("band")
        continuity_tags = adaptive_continuity.get("tags", [])

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode:
        # Band-based badges (if band is available)
        if continuity_band == "HIGH":
            badges.append(DILchatBadge(
                label="CONTINUITY_HIGH",
                level="info",
                description="Session continuity is high. Narrative and identity patterns are stable and coherent."
            ))
        elif continuity_band == "MEDIUM":
            badges.append(DILchatBadge(
                label="CONTINUITY_MEDIUM",
                level="info",
                description="Session continuity is moderate. Core narrative and identity patterns are present."
            ))
        elif continuity_band == "LOW":
            badges.append(DILchatBadge(
                label="CONTINUITY_LOW",
                level="warning",
                description="Session continuity is low. Narrative or identity patterns show fragmentation."
            ))

        # Tag-based badges (diagnostic detail)
        if "CONTINUITY_FRAGMENTED" in continuity_tags:
            badges.append(DILchatBadge(
                label="CONTINUITY_FRAGMENTED",
                level="warning",
                description="Narrative continuity is fragmented. Themes and intents are unstable."
            ))

        if "CONTINUITY_STABLE" in continuity_tags:
            badges.append(DILchatBadge(
                label="CONTINUITY_STABLE",
                level="info",
                description="Continuity is stable. Session-wide resilience and alignment are strong."
            ))

        if "CONTINUITY_IDENTITY_REINFORCED" in continuity_tags:
            badges.append(DILchatBadge(
                label="CONTINUITY_IDENTITY_REINFORCED",
                level="info",
                description="Identity continuity is reinforced. Identity patterns are persistent and echoing."
            ))

    # ========================================================================
    # Phase 40: Cross-Horizon Resonance Alignment Engine Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract cross-horizon resonance from unified_output if available
    cross_horizon_resonance = None
    if unified_output and "cross_horizon_resonance" in unified_output:
        cross_horizon_resonance = unified_output.get("cross_horizon_resonance")

    # Extract CHRA metrics
    chra_alignment_band = None
    chra_tags = []

    if cross_horizon_resonance is not None and isinstance(cross_horizon_resonance, dict):
        chra_alignment_band = cross_horizon_resonance.get("alignment_band")
        chra_tags = cross_horizon_resonance.get("diagnostic_tags", [])

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode:
        # Band-based badges (if band is available)
        if chra_alignment_band == "HIGH_ALIGNMENT":
            badges.append(DILchatBadge(
                label="CH_RES_ALIGNMENT_HIGH",
                level="info",
                description="Multi-horizon forecast trends align well with resonance, identity, and symbolic signals."
            ))
        elif chra_alignment_band == "MIXED_ALIGNMENT":
            badges.append(DILchatBadge(
                label="CH_RES_ALIGNMENT_MIXED",
                level="info",
                description="Mixed alignment between forecast trends and resonance/identity signals."
            ))
        elif chra_alignment_band == "LOW_ALIGNMENT":
            badges.append(DILchatBadge(
                label="CH_RES_ALIGNMENT_LOW",
                level="warning",
                description="Forecast trends show low alignment with resonance, identity, and symbolic patterns."
            ))

        # Tag-based badges (diagnostic detail)
        if "DRIFT_TENSION_HIGH" in chra_tags:
            badges.append(DILchatBadge(
                label="CH_RES_DRIFT_TENSION_HIGH",
                level="warning",
                description="High tension detected between predicted trends and drift risk."
            ))

        if "IDENTITY_SUPPORTS_TREND" in chra_tags:
            badges.append(DILchatBadge(
                label="CH_RES_IDENTITY_SUPPORTING_TREND",
                level="info",
                description="Identity harmonics and memory support the forecasted direction."
            ))

        if "LONG_TERM_ALIGNMENT_WEAK" in chra_tags:
            badges.append(DILchatBadge(
                label="CH_RES_LONG_TERM_UNCERTAIN",
                level="warning",
                description="Long-term forecast (H3) shows weak alignment with stability signals."
            ))

    # ========================================================================
    # Phase 41: Coherence-Regime Scenario Mapper Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract coherence_regime from unified_output
    coherence_regime = unified_output.get("coherence_regime") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and coherence_regime is not None:
        dominant_regime = coherence_regime.get("dominant_regime")
        regime_band = coherence_regime.get("band")

        # COHERENCE_REGIME_STABLE: stable regime with high scores
        if dominant_regime == "stable_therapeutic_processing" or regime_band == "stable":
            badges.append(DILchatBadge(
                label="COHERENCE_REGIME_STABLE",
                level="info",
                description="Session exhibits stable therapeutic processing pattern. Coherence and continuity are strong."
            ))

        # COHERENCE_REGIME_VOLATILE: volatile identity drift or ambivalent state
        if dominant_regime in ["volatile_identity_drift", "ambivalent_conflicted_state"] or regime_band == "volatile":
            badges.append(DILchatBadge(
                label="COHERENCE_REGIME_VOLATILE",
                level="warning",
                description="Session exhibits volatility in identity or coherence. High drift or conflict detected."
            ))

        # COHERENCE_REGIME_MIXED: mixed regime signals
        if regime_band == "mixed":
            badges.append(DILchatBadge(
                label="COHERENCE_REGIME_MIXED",
                level="info",
                description="Session exhibits mixed regime signals. Multiple coherence patterns detected."
            ))

        # COHERENCE_REGIME_RECOVERY: recovery/stabilization pattern
        if dominant_regime == "recovery_stabilization_phase":
            badges.append(DILchatBadge(
                label="COHERENCE_REGIME_RECOVERY",
                level="info",
                description="Session exhibits recovery stabilization pattern. Coherence is improving."
            ))

        # COHERENCE_REGIME_IDENTITY_DRIFT: identity drift dominant
        if dominant_regime == "volatile_identity_drift":
            badges.append(DILchatBadge(
                label="COHERENCE_REGIME_IDENTITY_DRIFT",
                level="warning",
                description="Session exhibits volatile identity drift. Identity continuity is weak."
            ))

        # COHERENCE_REGIME_SURFACE_LEVEL: surface level interaction
        if dominant_regime == "surface_level_interaction":
            badges.append(DILchatBadge(
                label="COHERENCE_REGIME_SURFACE_LEVEL",
                level="info",
                description="Session exhibits surface-level interaction. Low depth and symbolic harmonization."
            ))

    # ========================================================================
    # Phase 42: Scenario Fusion Engine Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract scenario_fusion from unified_output
    scenario_fusion = unified_output.get("scenario_fusion") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and scenario_fusion is not None:
        uncertainty_band = scenario_fusion.get("uncertainty_band")
        alignment = scenario_fusion.get("alignment")
        divergence = scenario_fusion.get("divergence")
        tags = scenario_fusion.get("tags", [])

        # SCENARIO_FUTURE_STABLE: low uncertainty, high alignment, low divergence
        if uncertainty_band == "low":
            badges.append(DILchatBadge(
                label="SCENARIO_FUTURE_STABLE",
                level="info",
                description="Future scenario outlook is stable with high regime alignment and low uncertainty."
            ))

        # SCENARIO_FUTURE_CAUTIOUS: medium uncertainty
        if uncertainty_band == "medium":
            badges.append(DILchatBadge(
                label="SCENARIO_FUTURE_CAUTIOUS",
                level="info",
                description="Future scenario outlook is cautious with moderate uncertainty and mixed regime signals."
            ))

        # SCENARIO_FUTURE_UNCERTAIN: high uncertainty
        if uncertainty_band == "high":
            badges.append(DILchatBadge(
                label="SCENARIO_FUTURE_UNCERTAIN",
                level="warning",
                description="Future scenario outlook is uncertain with high divergence and low regime consensus."
            ))

        # SCENARIO_PATH_CONVERGING: high alignment and consensus
        if (alignment is not None and alignment >= 0.65) or "SCENARIO_PATH_CONVERGING" in tags:
            badges.append(DILchatBadge(
                label="SCENARIO_PATH_CONVERGING",
                level="info",
                description="Scenario paths are converging with strong alignment across coherence regimes."
            ))

        # SCENARIO_PATH_DIVERGING: high divergence, low consensus
        if (divergence is not None and divergence >= 0.65) or "SCENARIO_PATH_DIVERGING" in tags:
            badges.append(DILchatBadge(
                label="SCENARIO_PATH_DIVERGING",
                level="warning",
                description="Scenario paths are diverging with weak consensus across coherence regimes."
            ))

    # ========================================================================
    # Phase 44: Coherence-Scenario Alignment Engine Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract coherence_scenario_alignment from unified_output
    csae = unified_output.get("coherence_scenario_alignment") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and csae is not None:
        alignment_band = csae.get("alignment_band")
        alignment_score = csae.get("alignment_score")
        conflict_index = csae.get("conflict_index")
        csae_tags = csae.get("diagnostic_tags", [])

        # CSAE_ALIGNMENT_HIGH: high alignment band
        if alignment_band == "high":
            badges.append(DILchatBadge(
                label="CSAE_ALIGNMENT_HIGH",
                level="info",
                description="High alignment between temporal forecasts, scenario paths, and identity continuity signals."
            ))

        # CSAE_ALIGNMENT_MEDIUM: medium alignment band
        if alignment_band == "medium":
            badges.append(DILchatBadge(
                label="CSAE_ALIGNMENT_MEDIUM",
                level="info",
                description="Moderate alignment across forecast horizons and scenario fusion signals."
            ))

        # CSAE_ALIGNMENT_LOW: low alignment band
        if alignment_band == "low":
            badges.append(DILchatBadge(
                label="CSAE_ALIGNMENT_LOW",
                level="warning",
                description="Low alignment between coherence forecasts and scenario paths. Weak signal consensus."
            ))

        # CSAE_ALIGNMENT_CONFLICT: conflict band
        if alignment_band == "conflict":
            badges.append(DILchatBadge(
                label="CSAE_ALIGNMENT_CONFLICT",
                level="warning",
                description="Conflicting signals detected between temporal forecasts, scenario paths, and identity continuity."
            ))

        # CSAE_STRONG_CONSENSUS: strong alignment from tags
        if "strong_alignment_multi_horizon" in csae_tags or "alignment_coherence_rising" in csae_tags:
            badges.append(DILchatBadge(
                label="CSAE_STRONG_CONSENSUS",
                level="info",
                description="Strong multi-horizon consensus with rising coherence alignment across all forecast windows."
            ))

        # CSAE_SCENARIO_CONTRADICTION: contradiction detected
        if "scenario_contradiction_detected" in csae_tags or "drift_conflict" in csae_tags:
            badges.append(DILchatBadge(
                label="CSAE_SCENARIO_CONTRADICTION",
                level="warning",
                description="Contradiction detected between scenario paths and coherence forecasts. High conflict index."
            ))

    # ========================================================================
    # Phase 45: Multi-Trajectory Stability Field (MTSF) Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract MTSF from unified_output
    mtsf = unified_output.get("multi_trajectory_stability_field") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and mtsf is not None:
        band = mtsf.get("band")
        tsi = mtsf.get("tsi", 0.0)
        tvi = mtsf.get("tvi", 0.0)
        chf = mtsf.get("chf", 0.0)
        mtsf_tags = mtsf.get("tags", [])

        # MTSF_STABILITY_HIGH: HIGH band
        if band == "HIGH":
            badges.append(DILchatBadge(
                label="MTSF_STABILITY_HIGH",
                level="info",
                description="High trajectory stability with strong cross-phase convergence across all forecasting layers."
            ))

        # MTSF_STABILITY_MEDIUM: MEDIUM band
        if band == "MEDIUM":
            badges.append(DILchatBadge(
                label="MTSF_STABILITY_MEDIUM",
                level="info",
                description="Moderate trajectory stability with acceptable convergence across forecast horizons."
            ))

        # MTSF_STABILITY_LOW: LOW band
        if band == "LOW":
            badges.append(DILchatBadge(
                label="MTSF_STABILITY_LOW",
                level="warning",
                description="Low trajectory stability detected. Weak convergence across forecasting layers."
            ))

        # MTSF_STABILITY_CHAOTIC: CHAOTIC band
        if band == "CHAOTIC":
            badges.append(DILchatBadge(
                label="MTSF_STABILITY_CHAOTIC",
                level="warning",
                description="Chaotic trajectory field detected. Very low stability with high volatility or cross-horizon conflict."
            ))

        # MTSF_CROSS_HORIZON_CONFLICT: high CHF
        if "CROSS_HORIZON_CONFLICT" in mtsf_tags:
            badges.append(DILchatBadge(
                label="MTSF_CROSS_HORIZON_CONFLICT",
                level="warning",
                description="Strong disagreement detected between short-term, mid-term, and long-term forecast horizons."
            ))

        # MTSF_CONVERGENCE: trajectory converging
        if "TRAJECTORY_CONVERGING" in mtsf_tags or "TRAJECTORY_STRONGLY_CONVERGING" in mtsf_tags:
            badges.append(DILchatBadge(
                label="MTSF_CONVERGENCE",
                level="info",
                description="Forecast trajectories are converging across all phases, indicating stable future outlook."
            ))

        # MTSF_DIVERGENCE: trajectory diverging
        if "TRAJECTORY_DIVERGING" in mtsf_tags or "TRAJECTORY_STRONGLY_DIVERGING" in mtsf_tags:
            badges.append(DILchatBadge(
                label="MTSF_DIVERGENCE",
                level="warning",
                description="Forecast trajectories are diverging across forecasting layers, indicating trajectory instability."
            ))

    # Phase 46: Trajectory Field Convergence Engine (TFCE) - Diagnostic-only badges
    # Extract TFCE data from unified output
    tfce = unified_output.get("trajectory_field_convergence") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and tfce is not None:
        band = tfce.get("convergence_band")
        convergence_index = tfce.get("convergence_index", 0.0)
        divergence_index = tfce.get("divergence_index", 0.0)
        stability_index = tfce.get("stability_index", 0.0)
        tfce_tags = tfce.get("diagnostic_tags", [])

        # TRAJECTORY_CONVERGENCE_HIGH: high convergence band
        if band == "high":
            badges.append(DILchatBadge(
                label="TRAJECTORY_CONVERGENCE_HIGH",
                level="info",
                description="High trajectory convergence detected. All predictive trajectories are aligning toward a coherent future."
            ))

        # TRAJECTORY_CONVERGENCE_MEDIUM: medium convergence band
        if band == "medium":
            badges.append(DILchatBadge(
                label="TRAJECTORY_CONVERGENCE_MEDIUM",
                level="info",
                description="Moderate trajectory convergence detected. Most trajectories are moving toward alignment."
            ))

        # TRAJECTORY_CONVERGENCE_LOW: low convergence band
        if band == "low":
            badges.append(DILchatBadge(
                label="TRAJECTORY_CONVERGENCE_LOW",
                level="warning",
                description="Low trajectory convergence detected. Predictive trajectories are showing limited alignment."
            ))

        # TRAJECTORY_FRAGMENTED: fragmented convergence band
        if band == "fragmented":
            badges.append(DILchatBadge(
                label="TRAJECTORY_FRAGMENTED",
                level="warning",
                description="Fragmented trajectory field detected. Predictive paths are diverging across multiple dimensions."
            ))

        # TRAJECTORY_CONSENSUS: strong consensus across trajectories
        if "TRAJECTORY_CONSENSUS" in tfce_tags:
            badges.append(DILchatBadge(
                label="TRAJECTORY_CONSENSUS",
                level="info",
                description="Strong trajectory consensus detected. High convergence with stable alignment across all predictive layers."
            ))

    # ========================================================================
    # Phase 48: Macro-Stability Regulator (MSR) Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract Phase 48 MSR data from unified_output
    macro_stability_regulator = unified_output.get("macro_stability_regulator") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and macro_stability_regulator:
        macro_stability_index = macro_stability_regulator.get("macro_stability_index", 0.0)
        macro_predictive_confidence = macro_stability_regulator.get("macro_predictive_confidence", 0.0)
        stability_band = macro_stability_regulator.get("stability_band")

        # MACRO_STABILITY_HIGH badge
        if stability_band == "high" and macro_stability_index >= 0.70:
            badges.append(DILchatBadge(
                label="Macro-Stability: High",
                level="info",
                description="Overall system stability is high across all forecasting subsystems."
            ))

        # MACRO_STABILITY_MEDIUM badge
        elif stability_band == "medium":
            badges.append(DILchatBadge(
                label="Macro-Stability: Medium",
                level="info",
                description="Overall system stability is moderate. Some subsystems show divergence."
            ))

        # MACRO_STABILITY_LOW badge
        elif stability_band == "low":
            badges.append(DILchatBadge(
                label="Macro-Stability: Low",
                level="warning",
                description="Overall system stability is low. Multiple subsystems showing instability."
            ))

        # MACRO_STABILITY_FRAGMENTED badge
        elif stability_band == "fragmented":
            badges.append(DILchatBadge(
                label="Macro-Stability: Fragmented",
                level="warning",
                description="Overall system is fragmented. Significant divergence across forecasting subsystems."
            ))

        # MACRO_PREDICTIVE_UNCERTAINTY badge
        if macro_predictive_confidence <= 0.40:
            badges.append(DILchatBadge(
                label="Predictive Uncertainty",
                level="warning",
                description="Forecasting subsystems show low confidence and alignment."
            ))

    # ========================================================================
    # Phase 49: Unified Cross-Phase Temporal Stability Engine (UCTSE) Badges (diagnostic only - therapy/identity + SMART_INSIGHT/DEEP_ADAPTIVE only)
    # ========================================================================
    # Extract Phase 49 UCTSE data from unified_output
    temporal_stability = unified_output.get("temporal_stability") if unified_output else None

    # Only add badges for therapy/identity domains AND SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and temporal_stability:
        temporal_stability_index = temporal_stability.get("temporal_stability_index", 0.0)
        stability_band = temporal_stability.get("stability_band")

        # TEMPORAL_STABILITY_HIGH badge
        if stability_band == "HIGH" and temporal_stability_index >= 0.75:
            badges.append(DILchatBadge(
                label="Temporal Stability: High",
                level="info",
                description="Strong temporal stability across all forecasting phases. Low drift risk and high future consistency."
            ))

        # TEMPORAL_STABILITY_MEDIUM badge
        elif stability_band == "MEDIUM":
            badges.append(DILchatBadge(
                label="Temporal Stability: Medium",
                level="info",
                description="Moderate temporal stability. Balanced stability with manageable drift risk."
            ))

        # TEMPORAL_STABILITY_LOW badge
        elif stability_band == "LOW":
            badges.append(DILchatBadge(
                label="Temporal Stability: Low",
                level="warning",
                description="Limited temporal stability. Elevated drift risk detected across forecasting layers."
            ))

        # TEMPORAL_STABILITY_FRAGMENTED badge
        elif stability_band == "FRAGMENTED":
            badges.append(DILchatBadge(
                label="Temporal Stability: Fragmented",
                level="warning",
                description="Fragmented temporal stability. High drift risk and low predictive consistency."
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
    persona_echo_profile: Optional[Dict[str, Any]] = None,
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

    # ========================================================================
    # Phase 17: Semantic Integrity & Cognitive Drift v3 Hints (diagnostic only)
    # ========================================================================
    if coherence:
        semantic_data = coherence.get("semantic", {})
        integrity_score = semantic_data.get("integrity_score")
        drift_v3 = semantic_data.get("cognitive_drift_v3")

        # Only add semantic hints if we have both metrics
        if integrity_score is not None and drift_v3 is not None:
            # SEMANTIC_INTEGRITY_STRONG: High integrity, low drift
            if integrity_score >= 0.75 and drift_v3 <= 0.3:
                hints.append(DILchatHint(
                    code="SEMANTIC_INTEGRITY_STRONG",
                    message="Semantic integrity strong. Conversation is coherent and stable across layers."
                ))

            # SEMANTIC_INTEGRITY_FRAGILE: Low integrity, high drift
            elif integrity_score <= 0.45 and drift_v3 >= 0.5:
                hints.append(DILchatHint(
                    code="SEMANTIC_INTEGRITY_FRAGILE",
                    message="Semantic integrity fragile. Consider grounding or summarization to stabilize."
                ))

            # SEMANTIC_INTEGRITY_MIXED: Mid-range integrity and/or drift
            elif (0.45 < integrity_score < 0.75) or (0.3 < drift_v3 < 0.5):
                hints.append(DILchatHint(
                    code="SEMANTIC_INTEGRITY_MIXED",
                    message="Semantic integrity mixed. Monitor for stabilization or drift trends."
                ))

    # ========================================================================
    # Phase 18: Temporal Entropy Differential Hints (diagnostic only)
    # ========================================================================
    if coherence:
        temporal_entropy_data = coherence.get("temporal_entropy", {})
        entropy_volatility = temporal_entropy_data.get("volatility")

        # Only add temporal field hints if we have volatility metric
        if entropy_volatility is not None:
            # TEMPORAL_FIELD_STABLE: Low volatility (< 0.25)
            if entropy_volatility < 0.25:
                hints.append(DILchatHint(
                    code="TEMPORAL_FIELD_STABLE",
                    message="Temporal field stable. Emotional/cognitive state is consistent and predictable."
                ))

            # TEMPORAL_FIELD_TRANSITIONAL: Mid-range volatility (0.25 - 0.60)
            elif 0.25 <= entropy_volatility < 0.60:
                hints.append(DILchatHint(
                    code="TEMPORAL_FIELD_TRANSITIONAL",
                    message="Temporal field transitional. Emotional/cognitive state is shifting or adapting."
                ))

            # TEMPORAL_FIELD_VOLATILE: High volatility (>= 0.60)
            else:
                hints.append(DILchatHint(
                    code="TEMPORAL_FIELD_VOLATILE",
                    message="Temporal field volatile. Emotional/cognitive state is highly variable or unstable."
                ))

    # ========================================================================
    # Phase 19: Semantic-Temporal Drift Fusion Hints (diagnostic only)
    # ========================================================================
    # Gating: therapy/identity domain OR smart_insight/deep_adaptive mode
    drift_fusion_enabled = (
        domain in ["therapy", "identity"]
        or interaction_mode in ["smart_insight", "deep_adaptive"]
    )

    if drift_fusion_enabled and coherence and "drift_fusion" in coherence:
        drift_index = coherence["drift_fusion"].get("index")
        drift_risk_band = coherence["drift_fusion"].get("risk_band", "")

        if drift_index is not None:
            # DRIFT_LOW_RISK: drift index < 0.30 OR risk_band == "low"
            if drift_index < 0.30 or drift_risk_band == "low":
                hints.append(DILchatHint(
                    code="DRIFT_LOW_RISK",
                    message="Semantic-temporal drift is low and stable."
                ))
            # DRIFT_MODERATE_RISK: drift index 0.30-0.65 OR risk_band == "moderate"
            elif 0.30 <= drift_index < 0.65 or drift_risk_band == "moderate":
                hints.append(DILchatHint(
                    code="DRIFT_MODERATE_RISK",
                    message="Moderate semantic-temporal drift present."
                ))
            # DRIFT_HIGH_RISK: drift index >= 0.65 OR risk_band == "high"
            elif drift_index >= 0.65 or drift_risk_band == "high":
                hints.append(DILchatHint(
                    code="DRIFT_HIGH_RISK",
                    message="High semantic-temporal drift detected. Consider grounding strategies or semantic stabilization."
                ))

    # ========================================================================
    # Phase 31: Adaptive Persona Echo Layer (APEL) Hints (diagnostic only)
    # ========================================================================
    # Gating: (therapy/identity domain) AND (smart_insight/deep_adaptive mode)
    interaction_mode_lower = interaction_mode.lower() if interaction_mode else ""
    apel_enabled = (
        domain in ["therapy", "identity"]
        and interaction_mode_lower in ["smart_insight", "deep_adaptive"]
    )

    if apel_enabled and persona_echo_profile:
        echo_enabled = persona_echo_profile.get("echo_enabled", False)
        echo_mode = persona_echo_profile.get("echo_mode", "none")
        echo_focus_tags = persona_echo_profile.get("echo_focus_tags", [])
        echo_risk_tags = persona_echo_profile.get("echo_risk_tags", [])

        # Primary mode hints
        if echo_enabled:
            if echo_mode == "light":
                hints.append(DILchatHint(
                    code="APEL_LIGHT_ACTIVE",
                    message="Light persona echo active. Minimal tone echo for stability reinforcement."
                ))
            elif echo_mode == "reflective":
                hints.append(DILchatHint(
                    code="APEL_REFLECTIVE_ACTIVE",
                    message="Reflective persona echo active. Moderate tone echo for identity coherence."
                ))
            elif echo_mode == "pattern":
                hints.append(DILchatHint(
                    code="APEL_PATTERN_ACTIVE",
                    message="Pattern persona echo active. Full tone echo for multi-turn pattern reinforcement."
                ))
        else:
            # Echo disabled
            hints.append(DILchatHint(
                code="APEL_ECHO_DISABLED",
                message="Persona echo layer is disabled for this interaction."
            ))

        # Supplementary hints
        if echo_enabled:
            # APEL_DRIFT_SENSITIVE: when drift_caution in risk_tags
            if "drift_caution" in echo_risk_tags:
                hints.append(DILchatHint(
                    code="APEL_DRIFT_SENSITIVE",
                    message="Echo layer is drift-sensitive. Tone modulation adapts to semantic drift risk."
                ))

            # APEL_STABILITY_ANCHORED: when stability in focus_tags
            if "stability" in echo_focus_tags:
                hints.append(DILchatHint(
                    code="APEL_STABILITY_ANCHORED",
                    message="Echo layer is stability-anchored. Tone reinforces stable coherence patterns."
                ))

    # ========================================================================
    # Phase 21: Mirror-Time Loop Hints (diagnostic only)
    # ========================================================================
    # Only show when interaction_mode in {smart_insight, deep_adaptive}
    if interaction_mode in ["smart_insight", "deep_adaptive"] and coherence:
        mirror_time_loop_data = coherence.get("mirror_time_loop", {})
        reversal_probability = mirror_time_loop_data.get("reversal_probability")
        stability_band = mirror_time_loop_data.get("details", {}).get("stability_band")

        # If we have mirror-time loop data, add stability-based hints
        if stability_band is not None:
            # MIRROR_TIME_STABLE: stable band
            if stability_band == "stable":
                hints.append(DILchatHint(
                    code="MIRROR_TIME_STABLE",
                    message="Mirror-time loop stable. Forward and reflection are aligned, temporal flow is coherent."
                ))

            # MIRROR_TIME_TRANSITIONAL: transitional band
            elif stability_band == "transitional":
                hints.append(DILchatHint(
                    code="MIRROR_TIME_TRANSITIONAL",
                    message="Mirror-time loop transitional. Forward-reflection alignment is shifting, monitor for stabilization or reversal."
                ))

            # MIRROR_TIME_REVERSAL_RISK: unstable band OR high reversal probability
            elif stability_band == "unstable":
                hints.append(DILchatHint(
                    code="MIRROR_TIME_REVERSAL_RISK",
                    message="Mirror-time loop unstable. High reversal risk detected, reflection may overtake forward progression."
                ))

        # Add reversal risk hint if probability is high (even if band is not unstable)
        elif reversal_probability is not None and reversal_probability > 0.65:
            hints.append(DILchatHint(
                code="MIRROR_TIME_REVERSAL_RISK",
                message="Mirror-time loop reversal risk elevated. Monitor for temporal inversion or retrospective drift."
            ))

    # ========================================================================
    # Phase 22: Mirror-Time Cycle Hints (diagnostic only)
    # ========================================================================
    # Only show when interaction_mode in {smart_insight, deep_adaptive}
    # AND domain in {therapy, identity}
    if (interaction_mode in ["smart_insight", "deep_adaptive"] and
        domain in ["therapy", "identity"] and
        coherence):

        mirror_time_cycles_data = coherence.get("mirror_time_cycles", {})
        dominant_cycle_type = mirror_time_cycles_data.get("dominant_type")

        # If we have cycle data, add cycle-type based hints
        if dominant_cycle_type is not None:
            # MIRROR_CYCLE_CONVERGING: alignment increasing, tension decreasing
            if dominant_cycle_type == "converging":
                hints.append(DILchatHint(
                    code="MIRROR_CYCLE_CONVERGING",
                    message="Mirror-time cycles converging. Self and reflection are moving toward alignment, integration is improving."
                ))

            # MIRROR_CYCLE_DIVERGING: alignment decreasing, tension increasing
            elif dominant_cycle_type == "diverging":
                hints.append(DILchatHint(
                    code="MIRROR_CYCLE_DIVERGING",
                    message="Mirror-time cycles diverging. Self and reflection are separating, internal conflict may be increasing."
                ))

            # MIRROR_CYCLE_OSCILLATING: multiple sign changes, unstable pattern
            elif dominant_cycle_type == "oscillating":
                hints.append(DILchatHint(
                    code="MIRROR_CYCLE_OSCILLATING",
                    message="Mirror-time cycles oscillating. Self-reflection patterns are fluctuating, indicating exploration or uncertainty."
                ))

            # MIRROR_CYCLE_STALLED: low change in alignment and tension
            elif dominant_cycle_type == "stalled":
                hints.append(DILchatHint(
                    code="MIRROR_CYCLE_STALLED",
                    message="Mirror-time cycles stalled. Self-reflection patterns are static, may indicate plateau or resistance to change."
                ))

    # ========================================================================
    # Phase 23: Cause-Effect Inversion Analytics Hints (diagnostic only)
    # ========================================================================
    # Only add for therapy/identity domains and SMART_INSIGHT/DEEP_ADAPTIVE modes
    therapy_or_identity_domain = domain in ["therapy", "identity"]
    smart_or_deep_mode = interaction_mode in ["smart_insight", "deep_adaptive"]

    if therapy_or_identity_domain and smart_or_deep_mode and coherence:
        cause_effect_data = coherence.get("cause_effect_inversion", {})
        inversion_band = cause_effect_data.get("inversion_band")
        cause_chain_stability_avg = cause_effect_data.get("avg_cause_chain_stability")

        # Add inversion band hints if available
        if inversion_band is not None:
            # CAUSE_PATH_FORWARD_DOMINANT: forward_dominant band
            if inversion_band == "forward_dominant":
                hints.append(DILchatHint(
                    code="CAUSE_PATH_FORWARD_DOMINANT",
                    message="Cause-effect path is forward-dominant. Standard linear temporal interpretation fits best."
                ))

            # CAUSE_PATH_INVERSION_PLAUSIBLE: inversion_plausible band
            elif inversion_band == "inversion_plausible":
                hints.append(DILchatHint(
                    code="CAUSE_PATH_INVERSION_PLAUSIBLE",
                    message="Cause-effect inversion is plausible. Mirror-time explanation may provide additional insight alongside forward-time reading."
                ))

            # CAUSE_PATH_INVERSION_DOMINANT: inversion_dominant band
            elif inversion_band == "inversion_dominant":
                hints.append(DILchatHint(
                    code="CAUSE_PATH_INVERSION_DOMINANT",
                    message="Cause-effect inversion is dominant. Mirror-time explanation fits better than forward-time cause→effect reading."
                ))

        # Add cause-chain stability hints if available
        if cause_chain_stability_avg is not None:
            # CAUSE_CHAIN_STABLE: high stability (>= 0.65)
            if cause_chain_stability_avg >= 0.65:
                hints.append(DILchatHint(
                    code="CAUSE_CHAIN_STABLE",
                    message="Cause-chain is stable. Temporal coherence is high, patterns are consistent and reliable."
                ))

            # CAUSE_CHAIN_UNSTABLE: low stability (<= 0.35)
            elif cause_chain_stability_avg <= 0.35:
                hints.append(DILchatHint(
                    code="CAUSE_CHAIN_UNSTABLE",
                    message="Cause-chain is unstable. Temporal coherence is low, patterns may be unclear or contradictory."
                ))

    # ========================================================================
    # Phase 24: Resonance Weighting Function Hints (diagnostic only)
    # ========================================================================
    # Only add for therapy/identity domains and SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and coherence:
        resonance_data = coherence.get("resonance_weighting", {})
        resonance_entropy = resonance_data.get("entropy")
        dominant_metrics = resonance_data.get("dominant_metrics", [])

        # Add resonance focus hints based on entropy
        if resonance_entropy is not None:
            # RESONANCE_FOCUSED: low entropy (< 0.35) - one or few metrics dominate
            if resonance_entropy < 0.35:
                hints.append(DILchatHint(
                    code="RESONANCE_FOCUSED",
                    message="Resonance weighting is focused. Signal clarity is high, one or few metrics strongly dominate trustworthiness."
                ))
            # RESONANCE_BALANCED: medium entropy (0.35 <= entropy < 0.70) - balanced trust across metrics
            elif resonance_entropy < 0.70:
                hints.append(DILchatHint(
                    code="RESONANCE_BALANCED",
                    message="Resonance weighting is balanced. Trust is distributed evenly across multiple metrics."
                ))
            # RESONANCE_DIFFUSE: high entropy (>= 0.70) - trust is spread widely
            else:
                hints.append(DILchatHint(
                    code="RESONANCE_DIFFUSE",
                    message="Resonance weighting is diffuse. Trust is spread broadly across many metrics, signal clarity is lower."
                ))

        # Add dominant metric hints if available
        if dominant_metrics:
            # RESONANCE_COEFF_COHERENCE_DOMINANT: coherence_fused is top metric
            if any("coherence" in metric for metric in dominant_metrics[:1]):
                hints.append(DILchatHint(
                    code="RESONANCE_COEFF_COHERENCE_DOMINANT",
                    message="Resonance weighting favors coherence metrics. Conversation stability signals are most trustworthy."
                ))

            # RESONANCE_COEFF_SEMANTIC_DOMINANT: semantic_integrity is top metric
            if any("semantic" in metric for metric in dominant_metrics[:1]):
                hints.append(DILchatHint(
                    code="RESONANCE_COEFF_SEMANTIC_DOMINANT",
                    message="Resonance weighting favors semantic integrity. Self-consistency signals are most trustworthy."
                ))

            # RESONANCE_COEFF_RESONANCE_DOMINANT: resonance_index is top metric
            if "resonance_index" in dominant_metrics[:1]:
                hints.append(DILchatHint(
                    code="RESONANCE_COEFF_RESONANCE_DOMINANT",
                    message="Resonance weighting favors resonance index. Formula-based stabilizing signals are most trustworthy."
                ))

            # RESONANCE_COEFF_DRIFT_INVERSE_WEIGHTED: drift_inverse or cognitive_stability is weighted
            if any("drift_inverse" in metric or "cognitive_stability" in metric for metric in dominant_metrics):
                hints.append(DILchatHint(
                    code="RESONANCE_COEFF_DRIFT_INVERSE_WEIGHTED",
                    message="Resonance weighting considers drift control. Low-drift signals are contributing to overall trust."
                ))

    # ========================================================================
    # Phase 27: Symbolic Harmonization Formula Hints (diagnostic only)
    # ========================================================================
    # Only add for therapy/identity domains and SMART_INSIGHT/DEEP_ADAPTIVE modes
    if therapy_or_identity_domain and smart_or_deep_mode and coherence:
        symbolic_harmonization_data = coherence.get("symbolic_harmonization", {})
        symbolic_harmonization_index = symbolic_harmonization_data.get("index")

        # Add harmonization hints based on SHI level
        if symbolic_harmonization_index is not None:
            # SYMBOLIC_HARMONY_HIGH: >= 0.75
            if symbolic_harmonization_index >= 0.75:
                hints.append(DILchatHint(
                    code="SYMBOLIC_HARMONY_HIGH",
                    message="Symbolic harmonization is high. Meaning layers, practical grounding, and mirror tensions are well-aligned. Deep symbolic exploration is supported."
                ))
            # SYMBOLIC_HARMONY_MEDIUM: 0.50 - 0.75
            elif symbolic_harmonization_index >= 0.50:
                hints.append(DILchatHint(
                    code="SYMBOLIC_HARMONY_MEDIUM",
                    message="Symbolic harmonization is moderate. Core meaning structures are coherent but some tension between symbolic and practical layers exists."
                ))
            # SYMBOLIC_HARMONY_LOW: < 0.50
            else:
                hints.append(DILchatHint(
                    code="SYMBOLIC_HARMONY_LOW",
                    message="Symbolic harmonization is low. Meaning layers show misalignment. Use concrete grounding to stabilize symbolic coherence."
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
