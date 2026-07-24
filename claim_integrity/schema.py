"""Canonical claim unit + the four/five preservation properties (Phase 2). Stdlib-only, deterministic.
Each field is a semantic dimension a decomposition step can silently corrupt; the study measures
preservation per dimension, never as one collapsed score.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "ci_claim_v1"


@dataclass
class ClaimUnit:
    claim_id: str
    source_output_id: str
    source_span: tuple                        # (start, end) char offsets into original text
    normalized_text: str
    claim_type: str                           # one of taxonomy.CLAIM_TYPES
    subject: str = ""
    predicate: str = ""
    object: str = ""
    polarity: str = "affirmative"             # affirmative | negated | partial_negation
    quantifier: Optional[str] = None          # none | universal | existential | proportional
    modality: str = "none"                    # none | possibility | necessity | obligation | permission | prohibition
    uncertainty: str = "none"                 # none | hedged | probabilistic | attributed_uncertainty
    confidence_expression: str = ""           # surface phrase carrying uncertainty
    temporal_scope: str = ""                  # as-of / window / tense marker
    spatial_scope: str = ""
    jurisdiction: str = ""
    population: str = ""                       # cohort | individual | entity | ""
    conditions: List[str] = field(default_factory=list)     # "only if" / "unless"
    exceptions: List[str] = field(default_factory=list)     # carve-outs
    causal_direction: str = "none"            # none | causal | correlational | reverse
    comparative_reference: str = ""
    numerical_values: List[str] = field(default_factory=list)
    units: List[str] = field(default_factory=list)
    ranges: List[str] = field(default_factory=list)
    attribution: str = "direct"               # direct | attributed
    attributed_source: str = ""
    evidence_status_language: str = ""        # "no evidence" | "not approved" | ...
    citation_references: List[str] = field(default_factory=list)
    reference_links: Dict[str, str] = field(default_factory=dict)   # pronoun -> antecedent
    depends_on: List[str] = field(default_factory=list)
    conjunction_structure: str = ""
    disjunction_structure: str = ""
    rhetorical_status: str = "assertive"      # assertive | non_assertive
    normative_status: str = "descriptive"     # descriptive | normative
    decomposition_confidence: float = 1.0
    unresolved_ambiguity: str = ""
    reason_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source_span"] = list(self.source_span)
        return d


# The five preservation properties measured separately (Phase 2). Never collapsed into one score.
PRESERVATION_PROPERTIES = (
    "atomicity",              # exactly one independently evaluable proposition
    "completeness",           # all materially relevant assertions extracted
    "semantic_preservation",  # meaning retained (polarity/modality/uncertainty/causal/evidentiary/numeric)
    "scope_preservation",     # qualifiers/quantifiers/conditions/exceptions/temporal/juris/population attached correctly
    "reference_preservation", # entities/pronouns/citations/cross-sentence dependencies correct
)

# The semantic dimensions preservation is scored on (Phase 11). One per fragile field.
SEMANTIC_DIMENSIONS = (
    "propositional", "polarity", "quantifier", "modality", "uncertainty",
    "temporal", "population", "jurisdiction", "numeric", "attribution",
    "citation", "causal_direction", "normative_status",
)
