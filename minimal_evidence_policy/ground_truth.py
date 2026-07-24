"""Phase 6 - Independent ground truth (minimal vocabulary).

Derives item metadata from surface signals and assigns a GOLD obligation level (E0..ER) via two
independent rubrics, adjudicated conservatively. This module does NOT import policy.py, invariants.py, or
modifiers.py - so scoring the minimal policy against it is not circular. Metadata is a shared surface
derivation; the two obligation rubrics are authored separately.

Deterministic, stdlib-only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Tuple

E0, E1, E2, E3, E4, ER = ("E0_NO_FACTUAL_EVIDENCE_GATE", "E1_CONTEXTUAL_SUPPORT",
                          "E2_AUTHORITATIVE_INTERNAL_OR_IMPLEMENTATION_EVIDENCE",
                          "E3_INDEPENDENT_OR_MEASURED_EVIDENCE",
                          "E4_EXTERNAL_AUTHORITATIVE_EVIDENCE_AND_REVIEW",
                          "ER_HUMAN_REVIEW_OR_INDETERMINATE")
_RANK = {E0: 0, E1: 1, E2: 2, E3: 3, E4: 4, ER: 5}

# ---- surface metadata derivation (shared) ----
_FAM = [
    ("medical", re.compile(r"\b(patient|clinical|diagnos|dosage|therap|treatment|cure)\w*", re.I)),
    ("financial", re.compile(r"\b(invest|portfolio|revenue|trading|profit|financial\s+risk)\w*", re.I)),
    ("legal_interpretation", re.compile(r"\b(liable|lawful|statute|jurisdiction|legally|gdpr|hipaa)\w*", re.I)),
    ("security_capability", re.compile(r"\b(secure|vulnerab|exploit|attack|credential|auth)\w*", re.I)),
    ("measured_performance", re.compile(r"\b(latency|throughput|p95|p99|benchmark|uptime|reliab)\w*", re.I)),
    ("action_proposal", re.compile(r"\b(deploy|delete|grant\s+access|revoke|shut\s+down|restart)\w*", re.I)),
    ("current_fact", re.compile(r"\b(currently|as\s+of\s+now|active\s+incident|now\s+running)\b", re.I)),
    ("internal_policy", re.compile(r"\b(policy|must\s+not|shall|prohibited|required\s+to)\b", re.I)),
    ("attribution", re.compile(r"\b(according\s+to|as\s+stated\s+by|per\s+the|cited)\b", re.I)),
    ("code_behavior", re.compile(r"\b(function|method|returns?|parameter|class|module)\b", re.I)),
    ("recommendation", re.compile(r"\b(should|recommend|suggest|advise)\b", re.I)),
    ("subjective_opinion", re.compile(r"\b(i\s+think|in\s+my\s+opinion|we\s+believe|arguably)\b", re.I)),
]
_HIGH_IMPACT = re.compile(r"\b(security|vulnerab|credential|delete|production|payment|access\s+control|"
                          r"patient|financial|medical|legal|irreversible)\w*", re.I)
_ABSOLUTE = re.compile(r"\b(always|never|guarantee|100\s*%|fully\s+secure|zero\s+risk|proven)\b", re.I)
_NONFACTUAL_FAMS = {"subjective_opinion"}
_FACTUAL_FAMS = {"medical", "financial", "legal_interpretation", "security_capability",
                 "measured_performance", "current_fact", "internal_policy", "attribution", "code_behavior"}


def derive_metadata(text: str, source_path: str, source_kind: str) -> Dict[str, Any]:
    t = text or ""
    fam = "process_description"
    for name, rx in _FAM:
        if rx.search(t):
            fam = name; break
    high_impact = bool(_HIGH_IMPACT.search(t))
    absolute = bool(_ABSOLUTE.search(t))
    # risk from impact + family
    if fam in ("medical", "financial", "legal_interpretation") or high_impact:
        risk = "high"
    elif fam in ("security_capability", "measured_performance", "current_fact", "action_proposal") or absolute:
        risk = "medium"
    else:
        risk = "low"
    if re.search(r"\.(py|js|ts|go)$", source_path):
        role = "test_artifact" if re.search(r"(^|/)(tests?|test_)", source_path) else "primary_implementation"
    else:
        role = "generated_documentation"
    return {
        "claim_family": fam, "risk_tier": risk, "source_role": role,
        "factual": fam in _FACTUAL_FAMS,
        "claim_actionability": "action_directive" if fam == "action_proposal" else "none",
        "temporal_sensitivity": "current_status" if fam in ("current_fact",) else "static",
        "high_impact": high_impact, "factual_leak": bool(_HIGH_IMPACT.search(t)) and fam in _NONFACTUAL_FAMS,
    }


def annotator_A(md: Dict[str, Any]) -> str:
    """Risk + claim-type rubric."""
    fam, risk = md["claim_family"], md["risk_tier"]
    if fam in ("medical", "financial", "legal_interpretation"):
        return E4
    if fam in ("measured_performance", "security_capability", "current_fact"):
        return E3
    if fam in ("code_behavior", "internal_policy", "attribution"):
        return E2
    if fam in _NONFACTUAL_FAMS and risk == "low" and not md["factual_leak"]:
        return E0
    return {"low": E1, "medium": E2, "high": E3, "critical": E4}.get(risk, ER)


def annotator_B(md: Dict[str, Any]) -> str:
    """Decision-impact + source rubric."""
    if md["claim_actionability"] != "none":
        return E3
    if md["high_impact"]:
        return E3
    if md["source_role"] == "generated_documentation" and md["factual"]:
        return E3               # generated doc making a factual claim needs independent evidence
    if md["factual"]:
        return E2
    if md["claim_family"] in _NONFACTUAL_FAMS and md["risk_tier"] == "low":
        return E0
    return E1


def adjudicate(text: str, source_path: str, source_kind: str) -> Dict[str, Any]:
    md = derive_metadata(text, source_path, source_kind)
    a, b = annotator_A(md), annotator_B(md)
    gold = a if _RANK[a] >= _RANK[b] else b          # conservative: higher burden
    acceptable = sorted({a, b, gold}, key=lambda x: _RANK[x])
    # unsafe = any level strictly below the lower annotation (never safe to go below)
    floor = min(_RANK[a], _RANK[b])
    unsafe = [lvl for lvl, r in _RANK.items() if r < floor]
    return {**md, "annotator_A": a, "annotator_B": b, "annotators_agree": a == b,
            "gold_obligation": gold, "acceptable_obligations": acceptable,
            "unsafe_obligations": sorted(unsafe, key=lambda x: _RANK[x]),
            "human_review_required": gold == ER}
