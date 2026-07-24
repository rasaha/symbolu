"""Phase 7 - Independent ground-truth rubrics.

Two annotation procedures assign each item a GOLD evidence obligation from surface features ALONE. These
rubrics are DELIBERATELY independent of the component under test: this module does NOT import
classifier.py, policy.py, obligations.py, taxonomy.py, source_role.py, or authority.py. Its keyword
logic is authored separately so scoring the reference component against it is not circular.

  Annotator A - claim-type + source-role rubric.
  Annotator B - decision-impact + evidence-burden rubric.

Gold = adjudication of A and B. High-risk disagreement is NOT resolved optimistically (it resolves to
the higher burden / human review). Deterministic, stdlib-only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# obligation constants duplicated here as bare strings (NOT imported from schema) to keep the rubric
# independent of the component's own module surface.
EXTERNAL = "EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED"
CORROB = "INDEPENDENT_CORROBORATION_REQUIRED"
INTERNAL_AUTH = "INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT"
IMPL = "IMPLEMENTATION_EVIDENCE_SUFFICIENT"
TELEMETRY = "TELEMETRY_OR_MEASUREMENT_REQUIRED"
ATTRIBUTION = "ATTRIBUTION_VERIFICATION_REQUIRED"
POLICY_AUTH = "POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED"
LOGICAL = "LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED"
TEMPORAL = "TEMPORAL_VERIFICATION_REQUIRED"
CONTEXTUAL = "CONTEXTUAL_SUPPORT_SUFFICIENT"
NO_GATE = "NO_FACTUAL_EVIDENCE_GATE"
QUALIFY = "QUALIFY_BY_DEFAULT"
HUMAN_REVIEW = "HUMAN_REVIEW_REQUIRED"
INDETERMINATE = "INDETERMINATE_OBLIGATION"

# --- rubric A signals (claim type) ---
_A = [
    ("medical", re.compile(r"\b(patient|clinical|diagnos|drug|dosage|therapy|symptom|treatment|cure)\w*", re.I), EXTERNAL),
    ("financial", re.compile(r"\b(invest|revenue|portfolio|trading|roi|profit|valuation|financial\s+risk)\w*", re.I), EXTERNAL),
    ("legal", re.compile(r"\b(liable|lawful|statute|regulation|jurisdiction|legally\s+required|gdpr|hipaa)\w*", re.I), EXTERNAL),
    ("performance", re.compile(r"\b(latency|throughput|p95|p99|benchmark|requests\s+per\s+second|uptime|reliability)\w*", re.I), TELEMETRY),
    ("attribution", re.compile(r"\b(according\s+to|as\s+stated\s+by|per\s+the|cited|quoted)\b", re.I), ATTRIBUTION),
    ("mathematical", re.compile(r"\b(equals|computed|sum of|derivation|theorem|proof that|big-?o)\b", re.I), LOGICAL),
    ("code_behavior", re.compile(r"\b(function|method|returns?|parameter|argument|class|module|api|endpoint)\b", re.I), IMPL),
    ("policy", re.compile(r"\b(policy|must\s+not|shall|prohibited|required\s+to|permitted|forbidden)\b", re.I), INTERNAL_AUTH),
    ("temporal", re.compile(r"\b(current(ly)?|latest|as\s+of\s+now|presently|active\s+incident)\b", re.I), TEMPORAL),
    ("opinion", re.compile(r"\b(i\s+think|in\s+my\s+opinion|we\s+believe|arguably|preferable|nicer)\b", re.I), NO_GATE),
    ("recommendation", re.compile(r"\b(should|recommend|suggest|advise|it\s+is\s+best|consider)\b", re.I), CONTEXTUAL),
]

# --- rubric B signals (decision impact / evidence burden) ---
_B_HIGH_IMPACT = re.compile(
    r"\b(security|vulnerab|exploit|credential|delete|irreversible|production|payment|access\s+control|"
    r"authenticat|authoriz|patient|financial|legal|medical)\w*", re.I)
_B_MEASURABLE = re.compile(r"\b(measure|metric|percent|rate|speed|slower|faster|cost|\d+\s*(ms|s|%|rps))\b", re.I)
_B_ABSOLUTE = re.compile(r"\b(always|never|guarantee|100\s*%|proven|completely|impossible|zero\s+risk)\b", re.I)
_B_NONASSERTIVE = re.compile(r"\b(for\s+example|e\.g\.|note\s+that|this\s+section|see\s+also|todo|placeholder)\b", re.I)


def annotator_A(text: str, source_role_hint: str) -> Tuple[str, str]:
    """Claim-type + source-role rubric. Returns (claim_family_guess, obligation)."""
    t = text or ""
    for fam, rx, obl in _A:
        if rx.search(t):
            # source-role adjustment: a code-behavior claim in non-code is weaker -> contextual
            if fam == "code_behavior" and source_role_hint not in ("primary_implementation", "test_artifact"):
                return "process_description", CONTEXTUAL
            return fam, obl
    return "process_description", CONTEXTUAL


def annotator_B(text: str) -> Tuple[str, str]:
    """Decision-impact + evidence-burden rubric. Returns (burden_level, obligation)."""
    t = text or ""
    high = bool(_B_HIGH_IMPACT.search(t))
    measurable = bool(_B_MEASURABLE.search(t))
    absolute = bool(_B_ABSOLUTE.search(t))
    nonassertive = bool(_B_NONASSERTIVE.search(t))
    if high and absolute:
        return "high", EXTERNAL
    if high:
        return "high", CORROB
    if measurable:
        return "medium", TELEMETRY
    if nonassertive:
        return "low", CONTEXTUAL
    if absolute:
        return "medium", CORROB
    return "low", CONTEXTUAL


# burden ordering for adjudication (higher index = stronger obligation)
_BURDEN_ORDER = [NO_GATE, CONTEXTUAL, QUALIFY, IMPL, INTERNAL_AUTH, ATTRIBUTION, TEMPORAL, LOGICAL,
                 TELEMETRY, CORROB, POLICY_AUTH, EXTERNAL, HUMAN_REVIEW, INDETERMINATE]
_RANK = {o: i for i, o in enumerate(_BURDEN_ORDER)}
_HIGH_RISK_OBLS = {CORROB, POLICY_AUTH, EXTERNAL}


def adjudicate(text: str, source_role_hint: str) -> Dict[str, Any]:
    """Combine A and B into a gold obligation with acceptable alternates and unsafe (unacceptable)
    obligations. High-risk disagreement resolves conservatively (higher burden), never optimistically."""
    fam, obl_a = annotator_A(text, source_role_hint)
    burden, obl_b = annotator_B(text)

    agree = obl_a == obl_b
    # gold = the HIGHER-burden of the two annotations (conservative adjudication)
    gold = obl_a if _RANK[obl_a] >= _RANK[obl_b] else obl_b
    # if either annotator flags a high-risk obligation, gold must be at least that burden
    if obl_a in _HIGH_RISK_OBLS or obl_b in _HIGH_RISK_OBLS:
        strongest = max([obl_a, obl_b], key=lambda o: _RANK[o])
        gold = strongest
    # unresolved high-risk disagreement -> human review
    unresolved = (not agree) and (obl_a in _HIGH_RISK_OBLS or obl_b in _HIGH_RISK_OBLS) and \
        abs(_RANK[obl_a] - _RANK[obl_b]) >= 4
    if unresolved:
        gold = HUMAN_REVIEW

    # acceptable alternates: within one burden rank of gold, not weaker than the weaker annotation
    acceptable = sorted({obl_a, obl_b, gold}, key=lambda o: _RANK[o])
    # unacceptable: any obligation strictly weaker than the WEAKER annotation when gold is high-risk
    unacceptable: List[str] = []
    if gold in _HIGH_RISK_OBLS or gold == HUMAN_REVIEW:
        floor = min(_RANK[obl_a], _RANK[obl_b])
        unacceptable = [o for o in _BURDEN_ORDER if _RANK[o] < floor and o in
                        (NO_GATE, CONTEXTUAL, IMPL, INTERNAL_AUTH)]
    # NO_GATE is never acceptable for a high-impact claim
    if gold in _HIGH_RISK_OBLS and NO_GATE not in unacceptable:
        unacceptable.append(NO_GATE)

    return {
        "claim_family_gold": fam,
        "burden_level_gold": burden,
        "annotator_A_obligation": obl_a,
        "annotator_B_obligation": obl_b,
        "annotators_agree": agree,
        "gold_obligation": gold,
        "acceptable_obligations": acceptable,
        "unacceptable_obligations": sorted(set(unacceptable)),
        "unresolved": unresolved,
        "human_review_required": gold == HUMAN_REVIEW,
    }
