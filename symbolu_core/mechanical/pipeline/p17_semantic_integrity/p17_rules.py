"""
P17 - Semantic Integrity Monitor Rule Functions

Deterministic rule functions for detecting integrity issues between
upstream semantic/lexical decisions. No NLP libraries; regex/string only.

Each rule function:
- Takes relevant upstream artifacts as input
- Returns a list of IntegrityIssue objects
- Is fully deterministic (no LLM, no randomness)
- Uses strict allow-lists for detection

Design Principles:
- Conservative: False positives acceptable if severity reflects uncertainty
- Deterministic: Same inputs always produce same outputs
- Observable: Evidence paths trace back to source artifacts
"""

from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, List, Optional, Set

from symbolu_core.mechanical.pipeline.p17_semantic_integrity.p17_schema import (
    IntegrityIssue,
    IntegrityIssueType,
    Severity,
    create_issue,
)


# ============================================================================
# ALLOW-LISTS AND WORD LISTS
# ============================================================================

# Certainty markers - words that imply certainty/definiteness
# Used to detect UNCERTAINTY_COLLAPSE when P8 has UNCERTAINTY slot populated
CERTAINTY_MARKERS: FrozenSet[str] = frozenset({
    # Definite certainty words
    "definitely",
    "certainly",
    "absolutely",
    "clearly",
    "obviously",
    "undoubtedly",
    "surely",
    "without doubt",
    "unquestionably",
    "positively",
    "decidedly",
    "unmistakably",
    "for certain",
    "for sure",
    "no doubt",
    "without question",
    # Strong assertion patterns
    "is",  # When used as "she is depressed" vs "she seems"
    "are",
    "always",
    "never",
    "must be",
    "has to be",
    "will be",
    # Authority assertions
    "proven",
    "confirmed",
    "established",
    "known",
    "fact",
    "true",
    "correct",
})

# Uncertainty preservers - words that maintain epistemic uncertainty
# P9 should use these when P8 has UNCERTAINTY slot
UNCERTAINTY_PRESERVERS: FrozenSet[str] = frozenset({
    "might",
    "may",
    "could",
    "perhaps",
    "possibly",
    "maybe",
    "seems",
    "appears",
    "feels like",
    "looks like",
    "sounds like",
    "unsure",
    "uncertain",
    "unclear",
    "i think",
    "i feel",
    "i wonder",
    "i'm not sure",
    "it seems",
    "it appears",
    "potentially",
    "likely",
    "unlikely",
    "probably",
    "possibly",
})

# Causal connectors - words that imply causal relationships
# Used to detect CAUSE_LEAK when regime/discourse blocks CAUSE
CAUSAL_CONNECTORS: FrozenSet[str] = frozenset({
    "because",
    "since",
    "therefore",
    "thus",
    "hence",
    "so",
    "as a result",
    "consequently",
    "due to",
    "owing to",
    "caused by",
    "leads to",
    "results in",
    "stems from",
    "arises from",
    "it's because",
    "that's why",
    "the reason is",
    "this means",
    "this shows",
    "this proves",
    "explains why",
    "accounts for",
})

# Authority markers - patterns implying diagnosis/judgment about others
# Used to detect AUTHORITY_DRIFT in RELATIONAL contexts
AUTHORITY_MARKERS: FrozenSet[str] = frozenset({
    # Diagnostic assertions about others
    "you are",
    "she is",
    "he is",
    "they are",
    "you're",
    "she's",
    "he's",
    "they're",
    # Labeling patterns
    "you have",
    "she has",
    "he has",
    "they have",
    "you need",
    "she needs",
    "he needs",
    "they need",
    # Authority statements
    "you should",
    "she should",
    "he should",
    "they should",
    "you must",
    "she must",
    "he must",
    "they must",
})

# Diagnostic labels - mental health / personality labels
# Especially sensitive in RELATIONAL contexts
DIAGNOSTIC_LABELS: FrozenSet[str] = frozenset({
    "depressed",
    "anxious",
    "bipolar",
    "narcissist",
    "narcissistic",
    "borderline",
    "psychotic",
    "delusional",
    "paranoid",
    "obsessive",
    "compulsive",
    "traumatized",
    "triggered",
    "gaslighting",
    "toxic",
    "abusive",
    "manipulative",
    "codependent",
    "controlling",
    "avoidant",
    "attachment",
    "dysfunctional",
})

# Tone escalation markers - words that escalate authority/certainty
# Even when from valid pools, these signal potential drift
TONE_ESCALATION_MARKERS: FrozenSet[str] = frozenset({
    # Intensifiers
    "very",
    "extremely",
    "incredibly",
    "absolutely",
    "completely",
    "totally",
    "utterly",
    "highly",
    "deeply",
    "profoundly",
    # Superlatives
    "best",
    "worst",
    "most",
    "least",
    "only",
    "always",
    "never",
    "everyone",
    "no one",
    "everything",
    "nothing",
    # Emphatic markers
    "really",
    "truly",
    "actually",
    "literally",
    "seriously",
    "honestly",
})

# Regimes that restrict causal inference
CAUSAL_RESTRICTIVE_REGIMES: FrozenSet[str] = frozenset({
    "DE_ESCALATE",
    "STABILIZE",
    "HOLD",
})

# Discourse acts that should not contain causal reasoning
CAUSAL_RESTRICTIVE_DISCOURSE_ACTS: FrozenSet[str] = frozenset({
    "REFLECTION",
    "ACKNOWLEDGMENT",
    "DEFERRAL",
})


# ============================================================================
# RULE FUNCTIONS
# ============================================================================


def detect_uncertainty_collapse(
    p8: Optional[Any],
    p9: Optional[Any],
) -> List[IntegrityIssue]:
    """
    Detect uncertainty collapse: UNCERTAINTY slot present but certainty markers in P9.

    When P8 semantic frame has an UNCERTAINTY slot populated, the lexical
    selections in P9 should preserve that uncertainty. If P9 contains
    certainty markers, this is a collapse of the intended uncertainty.

    Args:
        p8: SemanticFrame from P8 (may be None)
        p9: LexicalFrame from P9 (may be None)

    Returns:
        List of IntegrityIssue objects for detected violations
    """
    issues: List[IntegrityIssue] = []

    # Check if we have required inputs
    if p8 is None or p9 is None:
        return issues

    # Check if P8 has UNCERTAINTY slot populated
    has_uncertainty_slot = False
    uncertainty_value: Optional[str] = None

    # Access slots dict from P8
    slots = getattr(p8, "slots", None)
    if slots is not None:
        for slot_key, slot_value in slots.items():
            slot_name = getattr(slot_key, "value", str(slot_key))
            if slot_name == "UNCERTAINTY" and slot_value is not None:
                has_uncertainty_slot = True
                uncertainty_value = str(slot_value)
                break

    if not has_uncertainty_slot:
        return issues

    # Check P9 selections for certainty markers
    selections = getattr(p9, "selections", None)
    if selections is None:
        return issues

    # Collect all lexical text from P9
    lexical_text = ""
    for slot_key, lexeme in selections.items():
        if lexeme is not None:
            lexical_text += " " + str(lexeme).lower()

    # Check for certainty markers
    found_certainty_markers: List[str] = []
    for marker in CERTAINTY_MARKERS:
        # Use word boundary matching for single words
        if len(marker.split()) == 1:
            pattern = r'\b' + re.escape(marker) + r'\b'
            if re.search(pattern, lexical_text, re.IGNORECASE):
                found_certainty_markers.append(marker)
        else:
            # Multi-word phrases
            if marker.lower() in lexical_text:
                found_certainty_markers.append(marker)

    # Check if any uncertainty preservers are present
    has_uncertainty_preserver = False
    for preserver in UNCERTAINTY_PRESERVERS:
        if len(preserver.split()) == 1:
            pattern = r'\b' + re.escape(preserver) + r'\b'
            if re.search(pattern, lexical_text, re.IGNORECASE):
                has_uncertainty_preserver = True
                break
        else:
            if preserver.lower() in lexical_text:
                has_uncertainty_preserver = True
                break

    # Issue if certainty markers found and no uncertainty preservers
    if found_certainty_markers and not has_uncertainty_preserver:
        issues.append(create_issue(
            issue_type=IntegrityIssueType.UNCERTAINTY_COLLAPSE,
            severity=Severity.HIGH,
            message=(
                f"UNCERTAINTY slot populated in P8 ('{uncertainty_value}') but P9 "
                f"contains certainty markers: {found_certainty_markers}. "
                f"Lexical selections should preserve uncertainty."
            ),
            evidence_paths=[
                "p8.slots.UNCERTAINTY",
                "p9.selections",
            ],
        ))

    return issues


def detect_cause_leak(
    p6: Optional[Any],
    p7: Optional[Any],
    p8: Optional[Any],
    p9: Optional[Any],
) -> List[IntegrityIssue]:
    """
    Detect causal inference leakage when regime/discourse blocks CAUSE.

    When the regime is DE_ESCALATE/STABILIZE/HOLD or discourse act is
    REFLECTION/ACKNOWLEDGMENT/DEFERRAL, causal reasoning should be avoided.
    This rule detects causal connectors in P9 lexical selections.

    Args:
        p6: RegimeEnvelope from P6 (may be None)
        p7: DiscourseEnvelope from P7 (may be None)
        p8: SemanticFrame from P8 (may be None)
        p9: LexicalFrame from P9 (may be None)

    Returns:
        List of IntegrityIssue objects for detected violations
    """
    issues: List[IntegrityIssue] = []

    if p9 is None:
        return issues

    # Check if causal reasoning is restricted by regime
    regime_restricts_cause = False
    regime_value: Optional[str] = None
    if p6 is not None:
        regime = getattr(p6, "regime", None)
        if regime is not None:
            regime_value = getattr(regime, "value", str(regime))
            if regime_value in CAUSAL_RESTRICTIVE_REGIMES:
                regime_restricts_cause = True

    # Check if causal reasoning is restricted by discourse act
    discourse_restricts_cause = False
    discourse_value: Optional[str] = None
    if p7 is not None:
        act = getattr(p7, "act", None)
        if act is not None:
            discourse_value = getattr(act, "value", str(act))
            if discourse_value in CAUSAL_RESTRICTIVE_DISCOURSE_ACTS:
                discourse_restricts_cause = True

    # Check if P8 has CAUSE slot blocked (None value)
    p8_blocks_cause = False
    if p8 is not None:
        slots = getattr(p8, "slots", None)
        if slots is not None:
            for slot_key, slot_value in slots.items():
                slot_name = getattr(slot_key, "value", str(slot_key))
                if slot_name == "CAUSE":
                    # CAUSE slot exists but is None = blocked
                    if slot_value is None:
                        p8_blocks_cause = True
                    break

    # If no restrictions, no issue possible
    if not (regime_restricts_cause or discourse_restricts_cause or p8_blocks_cause):
        return issues

    # Collect all lexical text from P9
    selections = getattr(p9, "selections", None)
    if selections is None:
        return issues

    lexical_text = ""
    for slot_key, lexeme in selections.items():
        if lexeme is not None:
            lexical_text += " " + str(lexeme).lower()

    # Check for causal connectors
    found_causal_connectors: List[str] = []
    for connector in CAUSAL_CONNECTORS:
        if len(connector.split()) == 1:
            pattern = r'\b' + re.escape(connector) + r'\b'
            if re.search(pattern, lexical_text, re.IGNORECASE):
                found_causal_connectors.append(connector)
        else:
            if connector.lower() in lexical_text:
                found_causal_connectors.append(connector)

    if found_causal_connectors:
        # Build evidence paths
        evidence_paths = ["p9.selections"]
        restriction_source = []

        if regime_restricts_cause:
            evidence_paths.append("p6.regime")
            restriction_source.append(f"regime={regime_value}")

        if discourse_restricts_cause:
            evidence_paths.append("p7.act")
            restriction_source.append(f"discourse={discourse_value}")

        if p8_blocks_cause:
            evidence_paths.append("p8.slots.CAUSE")
            restriction_source.append("CAUSE slot blocked")

        issues.append(create_issue(
            issue_type=IntegrityIssueType.CAUSE_LEAK,
            severity=Severity.HIGH,
            message=(
                f"Causal inference leaked: found connectors {found_causal_connectors} "
                f"but causal reasoning restricted by: {', '.join(restriction_source)}. "
                f"P9 should avoid implying causation."
            ),
            evidence_paths=evidence_paths,
        ))

    return issues


def detect_authority_drift(
    po1: Optional[Any],
    p7: Optional[Any],
    p9: Optional[Any],
) -> List[IntegrityIssue]:
    """
    Detect authority drift: RELATIONAL content treated as REFLEXIVE assertions.

    When PO1 indicates RELATIONAL mode (talking about others), P9 should
    not contain authoritative diagnostic assertions ("she is definitely depressed").
    This protects against projecting certainty onto others.

    Args:
        po1: PhaseMinusOneEnvelope from PO1 (may be None)
        p7: DiscourseEnvelope from P7 (may be None)
        p9: LexicalFrame from P9 (may be None)

    Returns:
        List of IntegrityIssue objects for detected violations
    """
    issues: List[IntegrityIssue] = []

    if p9 is None:
        return issues

    # Check if mode is RELATIONAL
    is_relational = False

    if po1 is not None:
        # Check selected_primary for mode
        selected_primary = getattr(po1, "selected_primary", None)
        if selected_primary is not None:
            mode = getattr(selected_primary, "mode", None)
            if mode is not None:
                mode_value = getattr(mode, "value", str(mode))
                if mode_value == "RELATIONAL":
                    is_relational = True

        # Also check clauses for RELATIONAL mode
        if not is_relational:
            clauses = getattr(po1, "clauses", None)
            if clauses:
                for clause in clauses:
                    selected = getattr(clause, "selected", None)
                    if selected is not None:
                        mode = getattr(selected, "mode", None)
                        if mode is not None:
                            mode_value = getattr(mode, "value", str(mode))
                            if mode_value == "RELATIONAL":
                                is_relational = True
                                break

    if not is_relational:
        return issues

    # Collect all lexical text from P9
    selections = getattr(p9, "selections", None)
    if selections is None:
        return issues

    lexical_text = ""
    for slot_key, lexeme in selections.items():
        if lexeme is not None:
            lexical_text += " " + str(lexeme).lower()

    # Check for authority markers combined with diagnostic labels
    found_authority_issues: List[str] = []

    for authority_marker in AUTHORITY_MARKERS:
        if authority_marker.lower() in lexical_text:
            # Check if followed by certainty marker or diagnostic label
            for certainty in CERTAINTY_MARKERS:
                if len(certainty.split()) == 1:
                    # Check if authority marker + certainty appear together
                    pattern = authority_marker.lower() + r'\s+\w*\s*' + certainty.lower()
                    if re.search(pattern, lexical_text, re.IGNORECASE):
                        found_authority_issues.append(
                            f"'{authority_marker} ... {certainty}'"
                        )

            for label in DIAGNOSTIC_LABELS:
                if label.lower() in lexical_text:
                    # Check proximity to authority marker
                    pattern = authority_marker.lower() + r'[^.]*' + label.lower()
                    if re.search(pattern, lexical_text, re.IGNORECASE):
                        found_authority_issues.append(
                            f"'{authority_marker} ... {label}'"
                        )

    # Also check for direct diagnostic statements
    for marker in AUTHORITY_MARKERS:
        for label in DIAGNOSTIC_LABELS:
            # Pattern: "she is depressed", "you are narcissistic"
            pattern = marker.lower() + r'\s+' + label.lower()
            if re.search(pattern, lexical_text, re.IGNORECASE):
                if f"'{marker} {label}'" not in found_authority_issues:
                    found_authority_issues.append(f"'{marker} {label}'")

    if found_authority_issues:
        issues.append(create_issue(
            issue_type=IntegrityIssueType.AUTHORITY_DRIFT,
            severity=Severity.HIGH,
            message=(
                f"Authority drift in RELATIONAL context: found diagnostic assertions "
                f"{found_authority_issues[:3]}{'...' if len(found_authority_issues) > 3 else ''}. "
                f"RELATIONAL mode should avoid definitive claims about others."
            ),
            evidence_paths=[
                "po1.selected_primary.mode",
                "p9.selections",
            ],
        ))

    return issues


def detect_tone_escalation(
    p9: Optional[Any],
) -> List[IntegrityIssue]:
    """
    Detect tone escalation signals in lexical selections.

    Even when lexemes come from valid pools, certain intensifiers and
    emphatic markers can escalate tone in ways that may contradict
    upstream de-escalation intent.

    Args:
        p9: LexicalFrame from P9 (may be None)

    Returns:
        List of IntegrityIssue objects for detected violations
    """
    issues: List[IntegrityIssue] = []

    if p9 is None:
        return issues

    # Collect all lexical text from P9
    selections = getattr(p9, "selections", None)
    if selections is None:
        return issues

    lexical_text = ""
    for slot_key, lexeme in selections.items():
        if lexeme is not None:
            lexical_text += " " + str(lexeme).lower()

    # Count escalation markers
    found_escalation_markers: List[str] = []
    for marker in TONE_ESCALATION_MARKERS:
        pattern = r'\b' + re.escape(marker) + r'\b'
        matches = re.findall(pattern, lexical_text, re.IGNORECASE)
        if matches:
            found_escalation_markers.extend([marker] * len(matches))

    # Threshold for reporting: 3+ escalation markers is concerning
    if len(found_escalation_markers) >= 3:
        # Deduplicate for message
        unique_markers = list(set(found_escalation_markers))

        issues.append(create_issue(
            issue_type=IntegrityIssueType.TONE_ESCALATION,
            severity=Severity.WARN,
            message=(
                f"Tone escalation signals detected: {len(found_escalation_markers)} "
                f"intensifiers/emphatics found: {unique_markers[:5]}"
                f"{'...' if len(unique_markers) > 5 else ''}. "
                f"Consider whether this aligns with upstream posture."
            ),
            evidence_paths=["p9.selections"],
        ))
    elif len(found_escalation_markers) >= 1:
        # Lower count is INFO level
        unique_markers = list(set(found_escalation_markers))

        issues.append(create_issue(
            issue_type=IntegrityIssueType.TONE_ESCALATION,
            severity=Severity.INFO,
            message=(
                f"Minor tone escalation: {len(found_escalation_markers)} "
                f"intensifiers found: {unique_markers}."
            ),
            evidence_paths=["p9.selections"],
        ))

    return issues


def detect_slot_contradictions(
    p8: Optional[Any],
    p9: Optional[Any],
) -> List[IntegrityIssue]:
    """
    Detect contradictions between P8 semantic slots and P9 lexical selections.

    When P8 populates a slot with a specific semantic value, P9's lexical
    selection for that slot should be semantically consistent.

    Args:
        p8: SemanticFrame from P8 (may be None)
        p9: LexicalFrame from P9 (may be None)

    Returns:
        List of IntegrityIssue objects for detected violations
    """
    issues: List[IntegrityIssue] = []

    if p8 is None or p9 is None:
        return issues

    p8_slots = getattr(p8, "slots", None)
    p9_selections = getattr(p9, "selections", None)

    if p8_slots is None or p9_selections is None:
        return issues

    # Build lookup of P8 slot values
    p8_slot_values: Dict[str, Optional[str]] = {}
    for slot_key, slot_value in p8_slots.items():
        slot_name = getattr(slot_key, "value", str(slot_key))
        p8_slot_values[slot_name] = slot_value

    # Build lookup of P9 selections
    p9_slot_values: Dict[str, str] = {}
    for slot_key, lexeme in p9_selections.items():
        slot_name = getattr(slot_key, "value", str(slot_key))
        if lexeme is not None:
            p9_slot_values[slot_name] = str(lexeme)

    # Check STATE slot for semantic contradiction
    if "STATE" in p8_slot_values and "STATE" in p9_slot_values:
        p8_state = p8_slot_values["STATE"]
        p9_state = p9_slot_values["STATE"]

        if p8_state is not None and p9_state is not None:
            # Check for opposite sentiment words
            positive_markers = {"happy", "good", "well", "better", "positive", "calm", "peaceful"}
            negative_markers = {"sad", "bad", "worse", "negative", "anxious", "upset", "angry"}

            p8_positive = any(m in p8_state.lower() for m in positive_markers)
            p8_negative = any(m in p8_state.lower() for m in negative_markers)
            p9_positive = any(m in p9_state.lower() for m in positive_markers)
            p9_negative = any(m in p9_state.lower() for m in negative_markers)

            # Contradiction if opposite polarities
            if (p8_positive and p9_negative) or (p8_negative and p9_positive):
                issues.append(create_issue(
                    issue_type=IntegrityIssueType.CONTRADICTION,
                    severity=Severity.HIGH,
                    message=(
                        f"STATE slot contradiction: P8 semantic value '{p8_state}' "
                        f"conflicts with P9 lexical selection '{p9_state}'. "
                        f"Semantic polarity mismatch detected."
                    ),
                    evidence_paths=[
                        "p8.slots.STATE",
                        "p9.selections.STATE",
                    ],
                ))

    return issues


def detect_missing_inputs(
    po1: Optional[Any],
    p6: Optional[Any],
    p7: Optional[Any],
    p8: Optional[Any],
    p9: Optional[Any],
) -> List[IntegrityIssue]:
    """
    Detect missing required inputs for integrity analysis.

    When critical upstream artifacts are missing, P17 cannot perform
    full analysis. This reports INSUFFICIENT_EVIDENCE issues.

    Args:
        po1: PhaseMinusOneEnvelope from PO1 (may be None)
        p6: RegimeEnvelope from P6 (may be None)
        p7: DiscourseEnvelope from P7 (may be None)
        p8: SemanticFrame from P8 (may be None)
        p9: LexicalFrame from P9 (may be None)

    Returns:
        List of IntegrityIssue objects for missing inputs
    """
    issues: List[IntegrityIssue] = []

    # P8 and P9 are critical for integrity analysis
    if p8 is None and p9 is None:
        issues.append(create_issue(
            issue_type=IntegrityIssueType.INSUFFICIENT_EVIDENCE,
            severity=Severity.WARN,
            message=(
                "Both P8 semantic frame and P9 lexical frame are missing. "
                "Cannot perform semantic-lexical integrity checks."
            ),
            evidence_paths=["p8", "p9"],
        ))
    elif p8 is None:
        issues.append(create_issue(
            issue_type=IntegrityIssueType.INSUFFICIENT_EVIDENCE,
            severity=Severity.INFO,
            message=(
                "P8 semantic frame is missing. "
                "Limited integrity analysis possible."
            ),
            evidence_paths=["p8"],
        ))
    elif p9 is None:
        issues.append(create_issue(
            issue_type=IntegrityIssueType.INSUFFICIENT_EVIDENCE,
            severity=Severity.INFO,
            message=(
                "P9 lexical frame is missing. "
                "Limited integrity analysis possible."
            ),
            evidence_paths=["p9"],
        ))

    # PO1 missing limits authority drift detection
    if po1 is None:
        issues.append(create_issue(
            issue_type=IntegrityIssueType.INSUFFICIENT_EVIDENCE,
            severity=Severity.INFO,
            message=(
                "PO1 grounding envelope is missing. "
                "Cannot detect RELATIONAL authority drift."
            ),
            evidence_paths=["po1"],
        ))

    # P6 missing limits cause leak detection
    if p6 is None:
        issues.append(create_issue(
            issue_type=IntegrityIssueType.INSUFFICIENT_EVIDENCE,
            severity=Severity.INFO,
            message=(
                "P6 regime envelope is missing. "
                "Cannot detect regime-based cause leak restrictions."
            ),
            evidence_paths=["p6"],
        ))

    return issues


# Public exports
__all__ = [
    # Word lists (for testing/extension)
    "CERTAINTY_MARKERS",
    "UNCERTAINTY_PRESERVERS",
    "CAUSAL_CONNECTORS",
    "AUTHORITY_MARKERS",
    "DIAGNOSTIC_LABELS",
    "TONE_ESCALATION_MARKERS",
    "CAUSAL_RESTRICTIVE_REGIMES",
    "CAUSAL_RESTRICTIVE_DISCOURSE_ACTS",
    # Rule functions
    "detect_uncertainty_collapse",
    "detect_cause_leak",
    "detect_authority_drift",
    "detect_tone_escalation",
    "detect_slot_contradictions",
    "detect_missing_inputs",
]
