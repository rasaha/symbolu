"""Claim-type taxonomy (Phase 3) + semantic-failure taxonomy (Phase 4) + disposition vocabulary
(Phase 10 enum; formal freeze in VOCABULARY_V1.md). Stdlib-only, deterministic. ClaimIntegrity
dispositions are DECOMPOSITION states — kept separate from EvidenceAssurance evidence states,
AssertionGate delivery states, and ActionGate decisions.
"""
from __future__ import annotations

from enum import Enum

# ---- Phase 3: claim types (30) ------------------------------------------------------------------
CLAIM_TYPES = (
    "direct_factual", "attributed_factual", "uncertain_factual", "probabilistic", "predictive",
    "causal", "correlational", "comparative", "numerical", "temporal", "jurisdictional",
    "population_specific", "individual_inference", "normative", "recommendation", "prohibition",
    "permission", "procedural_instruction", "conditional", "exception_bearing", "negated",
    "partial_negation", "conjunction", "disjunction", "multi_hop", "citation_dependent", "summary",
    "evidentiary_status", "quoted", "rhetorical_non_assertive",
)

# atomicity commitment per type: "atomic" (split ok), "preserve" (must NOT split off its modifier),
# "split" (must decompose into independent units), "chain" (dependent units), "no_extract".
ATOMICITY_POLICY = {
    "direct_factual": "atomic", "attributed_factual": "preserve", "uncertain_factual": "preserve",
    "probabilistic": "preserve", "predictive": "preserve", "causal": "atomic",
    "correlational": "atomic", "comparative": "preserve", "numerical": "preserve",
    "temporal": "preserve", "jurisdictional": "preserve", "population_specific": "preserve",
    "individual_inference": "preserve", "normative": "atomic", "recommendation": "atomic",
    "prohibition": "atomic", "permission": "atomic", "procedural_instruction": "chain",
    "conditional": "preserve", "exception_bearing": "preserve", "negated": "atomic",
    "partial_negation": "preserve", "conjunction": "split", "disjunction": "preserve",
    "multi_hop": "chain", "citation_dependent": "preserve", "summary": "preserve",
    "evidentiary_status": "preserve", "quoted": "preserve", "rhetorical_non_assertive": "no_extract",
}

# ---- Phase 4: semantic failures (50) ------------------------------------------------------------
# (id, name, severity, correct_disposition, abstain_policy)  abstain_policy: "reject" | "if_material" | "flag" | "no"
SEMANTIC_FAILURES = (
    (1, "qualifier_deletion", "high", "QUALIFIER_LOSS", "if_material"),
    (2, "qualifier_reassignment", "high", "SCOPE_ERROR", "reject"),
    (3, "negation_loss", "crit", "NEGATION_ERROR", "reject"),
    (4, "negation_scope_error", "crit", "NEGATION_ERROR", "reject"),
    (5, "uncertainty_inflation", "high", "SCOPE_ERROR", "if_material"),
    (6, "uncertainty_suppression", "high", "QUALIFIER_LOSS", "if_material"),
    (7, "possibility_to_certainty", "crit", "SCOPE_ERROR", "reject"),
    (8, "correlation_to_causation", "crit", "SCOPE_ERROR", "reject"),
    (9, "causal_direction_reversal", "crit", "SCOPE_ERROR", "reject"),
    (10, "conditional_to_unconditional", "high", "SCOPE_ERROR", "reject"),
    (11, "exception_deletion", "high", "SCOPE_ERROR", "reject"),
    (12, "population_broadening", "high", "SCOPE_ERROR", "reject"),
    (13, "population_narrowing", "med", "SCOPE_ERROR", "if_material"),
    (14, "group_to_individual", "crit", "SCOPE_ERROR", "flag"),
    (15, "temporal_scope_loss", "high", "SCOPE_ERROR", "reject"),
    (16, "stale_present_normalization", "high", "SCOPE_ERROR", "reject"),
    (17, "jurisdiction_loss", "high", "SCOPE_ERROR", "reject"),
    (18, "numeric_alteration", "crit", "NUMERIC_ERROR", "reject"),
    (19, "unit_loss", "crit", "NUMERIC_ERROR", "reject"),
    (20, "range_to_point", "high", "NUMERIC_ERROR", "if_material"),
    (21, "bound_loss", "high", "NUMERIC_ERROR", "reject"),
    (22, "attribution_loss", "high", "ATTRIBUTION_ERROR", "reject"),
    (23, "attributed_to_direct", "high", "ATTRIBUTION_ERROR", "reject"),
    (24, "citation_link_loss", "high", "REFERENCE_ERROR", "reject"),
    (25, "evidence_status_loss", "crit", "SCOPE_ERROR", "reject"),
    (26, "no_evidence_to_false", "crit", "NEGATION_ERROR", "reject"),
    (27, "not_approved_to_ineffective", "crit", "SCOPE_ERROR", "reject"),
    (28, "conjunction_over_split", "med", "OVER_SPLIT", "if_material"),
    (29, "conjunction_under_split", "med", "UNDER_SPLIT", "if_material"),
    (30, "disjunction_collapse", "high", "SCOPE_ERROR", "reject"),
    (31, "pronoun_resolution_error", "high", "REFERENCE_ERROR", "reject"),
    (32, "entity_substitution", "crit", "REFERENCE_ERROR", "reject"),
    (33, "cross_sentence_dependency_loss", "high", "OMITTED_CLAIM", "reject"),
    (34, "antecedent_loss", "med", "REFERENCE_ERROR", "if_material"),
    (35, "modality_change", "crit", "SCOPE_ERROR", "reject"),
    (36, "normative_descriptive_confusion", "high", "SCOPE_ERROR", "if_material"),
    (37, "recommendation_to_fact", "high", "SCOPE_ERROR", "reject"),
    (38, "fact_to_recommendation", "med", "SCOPE_ERROR", "if_material"),
    (39, "limiting_context_omission", "high", "OMITTED_CLAIM", "reject"),
    (40, "invented_implied_claim", "crit", "INVENTED_CLAIM", "reject"),
    (41, "duplicate_as_independent", "low", "OVER_SPLIT", "no"),
    (42, "contradiction_hidden", "high", "UNDER_SPLIT", "reject"),
    (43, "nested_claim_flattening", "high", "OMITTED_CLAIM", "reject"),
    (44, "quote_as_assertion", "high", "ATTRIBUTION_ERROR", "reject"),
    (45, "rhetorical_question_as_claim", "med", "INVENTED_CLAIM", "reject"),
    (46, "hedging_removed", "high", "QUALIFIER_LOSS", "if_material"),
    (47, "confidence_language_misread", "high", "SCOPE_ERROR", "if_material"),
    (48, "causal_mechanism_invented", "crit", "INVENTED_CLAIM", "reject"),
    (49, "compound_partial_extraction", "high", "OMITTED_CLAIM", "reject"),
    (50, "equivalent_paraphrase_rejected", "low", "VALID_WITH_ALTERNATIVES", "no"),
)

# meaning-inversion failures: the extracted claim is KNOWN-wrong -> reject, do not merely abstain
HARD_INVERSIONS = frozenset(
    name for (_id, name, _sev, _disp, ab) in SEMANTIC_FAILURES if ab == "reject")


# ---- Phase 10: ClaimIntegrity disposition vocabulary --------------------------------------------
class Disposition(str, Enum):
    VALID = "VALID"
    VALID_WITH_ALTERNATIVES = "VALID_WITH_ALTERNATIVES"
    PARTIALLY_VALID = "PARTIALLY_VALID"
    OVER_SPLIT = "OVER_SPLIT"
    UNDER_SPLIT = "UNDER_SPLIT"
    QUALIFIER_LOSS = "QUALIFIER_LOSS"
    NEGATION_ERROR = "NEGATION_ERROR"
    SCOPE_ERROR = "SCOPE_ERROR"
    REFERENCE_ERROR = "REFERENCE_ERROR"
    NUMERIC_ERROR = "NUMERIC_ERROR"
    ATTRIBUTION_ERROR = "ATTRIBUTION_ERROR"
    INVENTED_CLAIM = "INVENTED_CLAIM"
    OMITTED_CLAIM = "OMITTED_CLAIM"
    AMBIGUOUS = "AMBIGUOUS"
    INDETERMINATE = "INDETERMINATE"
    REJECT_DECOMPOSITION = "REJECT_DECOMPOSITION"
    ESCALATE = "ESCALATE"


# dispositions that mean "the decomposition preserved meaning and may proceed downstream"
SAFE_DISPOSITIONS = frozenset({Disposition.VALID.value, Disposition.VALID_WITH_ALTERNATIVES.value})

# dispositions that mean "meaning was altered / a claim was invented or omitted" (a semantic-drift hit)
DRIFT_DISPOSITIONS = frozenset({
    Disposition.QUALIFIER_LOSS.value, Disposition.NEGATION_ERROR.value, Disposition.SCOPE_ERROR.value,
    Disposition.REFERENCE_ERROR.value, Disposition.NUMERIC_ERROR.value,
    Disposition.ATTRIBUTION_ERROR.value, Disposition.INVENTED_CLAIM.value,
    Disposition.OMITTED_CLAIM.value, Disposition.REJECT_DECOMPOSITION.value,
})

# severity ordering for adjudication (higher = more restrictive)
SEVERITY_RANK = {"low": 0, "med": 1, "high": 2, "crit": 3}
