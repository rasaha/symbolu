"""
P24 - Acoustic-Ontology Projection Observer Resolver

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    OBSERVER PHASE — WITNESS ONLY                               ║
║                                                                                ║
║  This phase may observe and summarize internal signals.                        ║
║  It may NOT influence regime, discourse, semantics, lexicon, or policy.        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This phase is observer-only and non-authoritative.

Projects outer human interpretation (10-layer ontology) from pipeline artifacts
and compares against inner acoustic witness (P22) + alignment/tension (P23).

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify context or any upstream state
    - Observer-only: Observes without influencing
    - No raw text access: Must NOT read text, tokens, or input_text
    - No feedback: Must NOT feed data back into P1-P23
    - No gating: Must NOT gate, block, or allow anything
    - No behavior change: Must NOT cause any downstream behavior change

Allowed Inputs (READ-ONLY):
    - ctx.phase_minus_one -> is_blocked(), overall_policy
    - ctx.p6_regime -> regime
    - ctx.p7_discourse_envelope -> act
    - ctx.semantic_frame -> slots
    - ctx.lexical_frame -> selections
    - ctx.grammar_evidence (optional dict)
    - ctx.p22_acoustic_witness -> pressure_band, dominant_motion
    - ctx.p23_alignment_report -> alignment_state, tension_score

Forbidden Inputs (HARD ERROR if accessed):
    - raw text (input_text, text, user_input, etc.)
    - token lists
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from symbolu.mechanical.pipeline.p24_projection.p24_projection_schema import (
    P24_VERSION,
    ALLOWED_PROJECTION_TAGS,
    OntologyLayer,
    ProjectionRiskBand,
    ProjectionMismatchType,
    P24ProjectionReport,
    P24InvariantViolation,
    create_blocked_report,
)


# ============================================================================
# FORBIDDEN ATTRIBUTE SETS - Invariant Protection
# ============================================================================


FORBIDDEN_TEXT_ATTRS = frozenset({
    "user_raw_text",
    "raw_text",
    "text",
    "input_text",
    "user_input",
})

FORBIDDEN_TOKEN_ATTRS = frozenset({
    "tokens",
    "token_list",
    "words",
    "word_list",
})

ALL_FORBIDDEN_ATTRS = FORBIDDEN_TEXT_ATTRS | FORBIDDEN_TOKEN_ATTRS


# ============================================================================
# DISCOURSE ACT -> BASE LAYERS MAPPING (DETERMINISTIC)
# ============================================================================


DISCOURSE_ACT_LAYERS: Dict[str, Tuple[OntologyLayer, ...]] = {
    "INSTRUCTION": (OntologyLayer.EXECUTION, OntologyLayer.AGENCY, OntologyLayer.PURPOSE),
    "QUESTION": (OntologyLayer.OBSERVATION, OntologyLayer.REASONING),
    "EXPLANATION": (OntologyLayer.REASONING, OntologyLayer.PURPOSE, OntologyLayer.CORE),
    "REFLECTION": (OntologyLayer.COGNITION, OntologyLayer.IDENTITY),
    "ACKNOWLEDGMENT": (OntologyLayer.OBSERVATION, OntologyLayer.COGNITION),
    "DEFERRAL": (OntologyLayer.OBSERVATION,),
}


# ============================================================================
# CERTAINTY MARKERS FOR LEXICAL LEAK DETECTION
# ============================================================================


CERTAINTY_MARKERS = frozenset({
    "definitely",
    "certainly",
    "guarantee",
    "prove",
    "must",
    "always",
    "never",
})


# ============================================================================
# CONSERVATIVE REGIMES (where imperative_under_careful applies)
# ============================================================================


CONSERVATIVE_REGIMES = frozenset({
    "CAREFUL",
    "DE_ESCALATE",
    "HOLD",
    "STABILIZE",
})


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class P24ProjectionResolver:
    """
    P24 Acoustic-Ontology Projection Observer.

    This phase is observer-only and non-authoritative.

    Projects outer human interpretation from pipeline artifacts and compares
    against inner acoustic witness + alignment state.

    Usage:
        resolver = P24ProjectionResolver()
        report = resolver.resolve(ctx)

    The resolver:
        - Only reads allowed inputs
        - Raises P24InvariantViolation for forbidden access
        - Returns a frozen P24ProjectionReport
        - Never modifies context or influences routing
    """

    def __init__(self) -> None:
        """
        Initialize the resolver.

        This phase is observer-only and non-authoritative.
        """
        self._version = P24_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def resolve(self, ctx: Any) -> P24ProjectionReport:
        """
        Resolve acoustic-ontology projection from pipeline context.

        This phase is observer-only and non-authoritative.

        This is the main entry point. It:
            1. Checks if PO1 is blocked -> returns blocked report
            2. Extracts base layers from discourse act
            3. Applies slot-based refinement
            4. Computes projection risk score and band
            5. Computes mismatch type from P23 alignment (observes without deciding)
            6. Computes confidence from evidence completeness
            7. Returns frozen projection report

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            P24ProjectionReport with projection observations

        Raises:
            P24InvariantViolation: If invariants are violated
        """
        # Check for blocked context (PO1)
        if self._is_po1_blocked(ctx):
            return create_blocked_report()

        # Initialize tags set
        tags: set = set()

        # Step 1: Extract discourse act and get base layers
        discourse_act = self._extract_discourse_act(ctx)
        base_layers = self._get_base_layers(discourse_act, tags)

        # Step 2: Apply slot-based refinement (may add layers and tags)
        refined_layers = self._apply_slot_refinement(ctx, base_layers, tags)

        # Step 3: Compute projection risk score
        risk_score, risk_tags = self._compute_risk_score(ctx, discourse_act)
        tags.update(risk_tags)

        # Step 4: Determine risk band from score
        risk_band = self._score_to_risk_band(risk_score)

        # Step 5: Determine mismatch type from P23 alignment
        mismatch_type, mismatch_tags = self._determine_mismatch(ctx, risk_band)
        tags.update(mismatch_tags)

        # Step 6: Check for additional condition tags
        additional_tags = self._check_additional_conditions(ctx, discourse_act)
        tags.update(additional_tags)

        # Step 7: Compute confidence from evidence completeness
        confidence = self._compute_confidence(ctx, tags)

        # Step 8: Add inner_outer_tension tag if mismatch
        if mismatch_type != ProjectionMismatchType.NONE:
            tags.add("inner_outer_tension")

        # Validate all tags are allowed
        invalid_tags = tags - ALLOWED_PROJECTION_TAGS
        if invalid_tags:
            raise P24InvariantViolation(
                f"Computed invalid tags: {invalid_tags}",
                violation_type="INVALID_TAG",
            )

        # Build debug info
        debug = {
            "risk_score": risk_score,
            "discourse_act": discourse_act,
            "base_layer_count": len(base_layers),
            "refined_layer_count": len(refined_layers),
        }

        return P24ProjectionReport(
            projected_layers=tuple(refined_layers),
            projection_risk_band=risk_band,
            mismatch_type=mismatch_type,
            projection_tags=frozenset(tags),
            confidence=confidence,
            debug=debug,
        )

    # ========================================================================
    # EXTRACTION METHODS (READ-ONLY)
    # ========================================================================

    def _is_po1_blocked(self, ctx: Any) -> bool:
        """
        Check if PO1 (phase_minus_one) is blocked.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            True if PO1 is blocked, False otherwise
        """
        po1 = getattr(ctx, "phase_minus_one", None)
        if po1 is not None:
            is_blocked_method = getattr(po1, "is_blocked", None)
            if callable(is_blocked_method):
                return is_blocked_method()
            blocked = getattr(po1, "blocked", None)
            if blocked is not None:
                return bool(blocked)
        return False

    def _extract_discourse_act(self, ctx: Any) -> str:
        """
        Extract discourse act from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            Discourse act string (uppercase)
        """
        # Try p7_discourse_envelope
        p7 = getattr(ctx, "p7_discourse_envelope", None)
        if p7 is not None:
            act = getattr(p7, "act", None)
            if act is not None:
                return getattr(act, "value", str(act)).upper()

        # Try p7_discourse
        p7 = getattr(ctx, "p7_discourse", None)
        if p7 is not None:
            act = getattr(p7, "act", None)
            if act is not None:
                return getattr(act, "value", str(act)).upper()
            act = getattr(p7, "discourse_act", None)
            if act is not None:
                return getattr(act, "value", str(act)).upper()

        # Default: unknown
        return ""

    def _extract_regime(self, ctx: Any) -> str:
        """
        Extract regime from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            Regime string (uppercase)
        """
        p6 = getattr(ctx, "p6_regime", None)
        if p6 is not None:
            regime = getattr(p6, "regime", None)
            if regime is not None:
                return getattr(regime, "value", str(regime)).upper()
        return "HOLD"  # Default to most conservative

    def _extract_semantic_frame(self, ctx: Any) -> Optional[Any]:
        """
        Extract semantic frame from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            SemanticFrame or None
        """
        # Try semantic_frame (standard location)
        frame = getattr(ctx, "semantic_frame", None)
        if frame is not None:
            return frame

        # Try p8_semantic_frame
        frame = getattr(ctx, "p8_semantic_frame", None)
        if frame is not None:
            return frame

        return None

    def _extract_lexical_frame(self, ctx: Any) -> Optional[Any]:
        """
        Extract lexical frame from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            LexicalFrame or None
        """
        frame = getattr(ctx, "lexical_frame", None)
        if frame is not None:
            return frame

        frame = getattr(ctx, "p9_lexical_frame", None)
        if frame is not None:
            return frame

        return None

    def _extract_grammar_evidence(self, ctx: Any) -> Dict[str, Any]:
        """
        Extract grammar evidence from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            Grammar evidence dict (empty if not present)
        """
        evidence = getattr(ctx, "grammar_evidence", None)
        if isinstance(evidence, dict):
            return evidence
        return {}

    def _extract_p22_witness(self, ctx: Any) -> Optional[Any]:
        """
        Extract P22 acoustic witness from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            P22AcousticVrittiWitness or None
        """
        witness = getattr(ctx, "p22_acoustic_witness", None)
        if witness is not None:
            return witness

        witness = getattr(ctx, "p22", None)
        if witness is not None:
            return witness

        return None

    def _extract_p23_report(self, ctx: Any) -> Optional[Any]:
        """
        Extract P23 alignment report from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            P23AlignmentReport or None
        """
        report = getattr(ctx, "p23_alignment_report", None)
        if report is not None:
            return report

        report = getattr(ctx, "p23", None)
        if report is not None:
            return report

        return None

    # ========================================================================
    # LAYER RESOLUTION METHODS
    # ========================================================================

    def _get_base_layers(
        self,
        discourse_act: str,
        tags: set,
    ) -> List[OntologyLayer]:
        """
        Get base projected layers from discourse act.

        This phase is observer-only and non-authoritative.

        Args:
            discourse_act: Discourse act string (uppercase)
            tags: Tags set to add low_evidence if missing

        Returns:
            List of base ontology layers
        """
        if discourse_act in DISCOURSE_ACT_LAYERS:
            return list(DISCOURSE_ACT_LAYERS[discourse_act])
        else:
            # Unknown discourse act -> empty tuple + low_evidence tag
            tags.add("low_evidence")
            return []

    def _apply_slot_refinement(
        self,
        ctx: Any,
        base_layers: List[OntologyLayer],
        tags: set,
    ) -> List[OntologyLayer]:
        """
        Apply slot-based refinement to layers.

        This phase is observer-only and non-authoritative.

        Rules:
            - If CAUSE populated under conservative regime -> add outer_overreach_risk tag
            - If REQUEST_FOCUS populated -> add PURPOSE if < 3 layers
            - If CONSTRAINT/LIMITATION populated -> add EXECUTION if < 3 layers

        Args:
            ctx: Pipeline context
            base_layers: Base layers from discourse act
            tags: Tags set to update

        Returns:
            Refined list of layers (max 3)
        """
        layers = list(base_layers)  # Make a copy
        semantic_frame = self._extract_semantic_frame(ctx)
        regime = self._extract_regime(ctx)

        if semantic_frame is None:
            return layers[:3]  # Ensure max 3

        # Get slots dict
        slots = getattr(semantic_frame, "slots", None)
        if not isinstance(slots, dict):
            return layers[:3]

        # Check for CAUSE under conservative regime
        cause_populated = self._is_slot_populated(slots, "CAUSE")
        if cause_populated and regime in CONSERVATIVE_REGIMES:
            tags.add("outer_overreach_risk")

        # Check REQUEST_FOCUS -> add PURPOSE preference
        request_focus_populated = self._is_slot_populated(slots, "REQUEST_FOCUS")
        if request_focus_populated and len(layers) < 3:
            if OntologyLayer.PURPOSE not in layers:
                layers.append(OntologyLayer.PURPOSE)

        # Check CONSTRAINT/LIMITATION -> add EXECUTION preference
        constraint_populated = self._is_slot_populated(slots, "CONSTRAINT")
        limitation_populated = self._is_slot_populated(slots, "LIMITATION")
        if (constraint_populated or limitation_populated) and len(layers) < 3:
            if OntologyLayer.EXECUTION not in layers:
                layers.append(OntologyLayer.EXECUTION)

        # Ensure max 3 layers
        return layers[:3]

    def _is_slot_populated(self, slots: Dict, slot_name: str) -> bool:
        """
        Check if a semantic slot is populated.

        This phase is observer-only and non-authoritative.

        Args:
            slots: Slots dictionary
            slot_name: Slot name to check

        Returns:
            True if slot exists and has a non-None value
        """
        for key, value in slots.items():
            key_name = getattr(key, "value", str(key)).upper()
            if key_name == slot_name and value is not None:
                return True
        return False

    # ========================================================================
    # RISK SCORE COMPUTATION
    # ========================================================================

    def _compute_risk_score(
        self,
        ctx: Any,
        discourse_act: str,
    ) -> Tuple[float, set]:
        """
        Compute projection risk score.

        This phase is observer-only and non-authoritative.

        Scoring rules:
            - Start at 0.2
            - +0.3 if discourse act in {EXPLANATION, INSTRUCTION}
            - +0.2 if grammar_evidence.get("imperative_form") is True
            - +0.2 if certainty markers in lexical frame
            - -0.2 if UNCERTAINTY slot populated
            - Clamp to [0.0, 1.0]

        Args:
            ctx: Pipeline context
            discourse_act: Discourse act string

        Returns:
            Tuple of (risk_score, tags set)
        """
        tags: set = set()
        score = 0.2  # Base score

        # +0.3 if discourse act in {EXPLANATION, INSTRUCTION}
        if discourse_act in {"EXPLANATION", "INSTRUCTION"}:
            score += 0.3

        # Check grammar evidence
        grammar_evidence = self._extract_grammar_evidence(ctx)
        if not grammar_evidence:
            tags.add("missing_grammar_evidence")
        else:
            # +0.2 if imperative_form is True
            if grammar_evidence.get("imperative_form") is True:
                score += 0.2

        # Check lexical frame for certainty markers
        lexical_frame = self._extract_lexical_frame(ctx)
        if lexical_frame is None:
            tags.add("missing_lexical_frame")
        else:
            if self._has_certainty_markers(lexical_frame):
                tags.add("lexical_certainty_leak")
                score += 0.2

        # Check semantic frame for UNCERTAINTY slot
        semantic_frame = self._extract_semantic_frame(ctx)
        if semantic_frame is None:
            tags.add("missing_semantic_frame")
        else:
            slots = getattr(semantic_frame, "slots", None)
            if isinstance(slots, dict):
                if self._is_slot_populated(slots, "UNCERTAINTY"):
                    score -= 0.2

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(1.0, score))

        return score, tags

    def _has_certainty_markers(self, lexical_frame: Any) -> bool:
        """
        Check if lexical frame contains certainty markers.

        This phase is observer-only and non-authoritative.

        Args:
            lexical_frame: LexicalFrame object

        Returns:
            True if any certainty marker is found
        """
        selections = getattr(lexical_frame, "selections", None)
        if not isinstance(selections, dict):
            return False

        for value in selections.values():
            if isinstance(value, str):
                value_lower = value.lower()
                for marker in CERTAINTY_MARKERS:
                    if marker in value_lower:
                        return True
        return False

    def _score_to_risk_band(self, score: float) -> ProjectionRiskBand:
        """
        Convert risk score to risk band.

        This phase is observer-only and non-authoritative.

        Args:
            score: Risk score in [0.0, 1.0]

        Returns:
            ProjectionRiskBand
        """
        if score <= 0.33:
            return ProjectionRiskBand.LOW
        elif score <= 0.66:
            return ProjectionRiskBand.MODERATE
        else:
            return ProjectionRiskBand.HIGH

    # ========================================================================
    # MISMATCH DETERMINATION
    # ========================================================================

    def _determine_mismatch(
        self,
        ctx: Any,
        risk_band: ProjectionRiskBand,
    ) -> Tuple[ProjectionMismatchType, set]:
        """
        Determine mismatch type from P23 alignment and risk band.

        This phase is observer-only and non-authoritative.

        Rules:
            - If P23 alignment_state == ALIGNED and risk_band == LOW -> NONE
            - If P23 alignment_state in {TENSION} or risk_band == MODERATE -> SOFT_MISMATCH
            - If P23 alignment_state == CONTRADICTION or risk_band == HIGH -> STRONG_MISMATCH
            - If P23 missing -> treat as TENSION (conservative), add low_evidence tag

        Args:
            ctx: Pipeline context
            risk_band: Computed risk band

        Returns:
            Tuple of (mismatch_type, tags set)
        """
        tags: set = set()
        p23_report = self._extract_p23_report(ctx)

        # Get alignment state
        if p23_report is None:
            alignment_state = "TENSION"  # Conservative default
            tags.add("low_evidence")
        else:
            alignment_state_obj = getattr(p23_report, "alignment_state", None)
            if alignment_state_obj is not None:
                alignment_state = getattr(alignment_state_obj, "value", str(alignment_state_obj)).upper()
            else:
                alignment_state = "TENSION"
                tags.add("low_evidence")

        # Determine mismatch type
        if alignment_state == "CONTRADICTION" or risk_band == ProjectionRiskBand.HIGH:
            return ProjectionMismatchType.STRONG_MISMATCH, tags
        elif alignment_state == "TENSION" or risk_band == ProjectionRiskBand.MODERATE:
            return ProjectionMismatchType.SOFT_MISMATCH, tags
        elif alignment_state == "ALIGNED" and risk_band == ProjectionRiskBand.LOW:
            return ProjectionMismatchType.NONE, tags
        else:
            # Default: conservative
            return ProjectionMismatchType.SOFT_MISMATCH, tags

    # ========================================================================
    # ADDITIONAL CONDITIONS
    # ========================================================================

    def _check_additional_conditions(
        self,
        ctx: Any,
        discourse_act: str,
    ) -> set:
        """
        Check for additional condition tags.

        This phase is observer-only and non-authoritative.

        Rules:
            - imperative_under_careful: imperative_form True AND regime in conservative set
            - high_pressure_low_authority: P22 pressure HIGH AND discourse in {DEFERRAL, ACKNOWLEDGMENT}

        Args:
            ctx: Pipeline context
            discourse_act: Discourse act string

        Returns:
            Set of additional tags
        """
        tags: set = set()

        # Check imperative_under_careful
        grammar_evidence = self._extract_grammar_evidence(ctx)
        regime = self._extract_regime(ctx)

        if grammar_evidence.get("imperative_form") is True:
            if regime in CONSERVATIVE_REGIMES:
                tags.add("imperative_under_careful")

        # Check high_pressure_low_authority
        p22_witness = self._extract_p22_witness(ctx)
        if p22_witness is not None:
            pressure = getattr(p22_witness, "pressure_band", "low")
            if pressure == "high" and discourse_act in {"DEFERRAL", "ACKNOWLEDGMENT"}:
                tags.add("high_pressure_low_authority")

        return tags

    # ========================================================================
    # CONFIDENCE COMPUTATION
    # ========================================================================

    def _compute_confidence(self, ctx: Any, tags: set) -> float:
        """
        Compute confidence from evidence completeness.

        This phase is observer-only and non-authoritative.

        Rules:
            - If PO1 blocked -> 0.0
            - Else start at 1.0 and subtract:
                - -0.3 if lexical frame missing
                - -0.3 if semantic frame missing
                - -0.2 if grammar_evidence missing
                - -0.2 if P23 missing
                - -0.1 if P22 missing
            - Clamp to [0.0, 1.0]

        Args:
            ctx: Pipeline context
            tags: Current tags set

        Returns:
            Confidence score in [0.0, 1.0]
        """
        if self._is_po1_blocked(ctx):
            return 0.0

        confidence = 1.0

        if "missing_lexical_frame" in tags:
            confidence -= 0.3

        if "missing_semantic_frame" in tags:
            confidence -= 0.3

        if "missing_grammar_evidence" in tags:
            confidence -= 0.2

        # Check P23 missing
        p23_report = self._extract_p23_report(ctx)
        if p23_report is None:
            confidence -= 0.2

        # Check P22 missing
        p22_witness = self._extract_p22_witness(ctx)
        if p22_witness is None:
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))


# ============================================================================
# STANDALONE RESOLVE FUNCTION
# ============================================================================


def resolve_projection(ctx: Any) -> P24ProjectionReport:
    """
    Standalone function to resolve projection.

    This phase is observer-only and non-authoritative.

    Convenience function for direct use without creating resolver instance.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P24ProjectionReport with projection observations
    """
    resolver = P24ProjectionResolver()
    return resolver.resolve(ctx)


def access_forbidden_attribute(ctx: Any, attr_name: str) -> None:
    """
    Helper to enforce forbidden attribute access.

    This phase is observer-only and non-authoritative.

    This function is provided for testing that forbidden access raises errors.

    Args:
        ctx: Context object
        attr_name: Attribute name to check

    Raises:
        P24InvariantViolation: Always, if attr_name is forbidden
    """
    if attr_name in ALL_FORBIDDEN_ATTRS:
        raise P24InvariantViolation(
            f"Attempted to access forbidden attribute: {attr_name}",
            violation_type="FORBIDDEN_ACCESS",
        )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    "P24ProjectionResolver",
    "resolve_projection",
    "access_forbidden_attribute",
    # Forbidden attribute sets
    "FORBIDDEN_TEXT_ATTRS",
    "FORBIDDEN_TOKEN_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
    # Discourse -> layers mapping
    "DISCOURSE_ACT_LAYERS",
    # Certainty markers
    "CERTAINTY_MARKERS",
    # Conservative regimes
    "CONSERVATIVE_REGIMES",
]
