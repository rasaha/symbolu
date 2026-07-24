"""Adversarial decomposition study (Phase 17). 25 cases engineered to induce semantic drift during
decomposition. Each carries a gold claim (with the load-bearing dimension) and the meaning it must
retain. We run every method and report which SILENTLY alter meaning (produce a fluent claim whose
disposition is a drift state). Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, List

# (id, text, risk_class, gold_claim_dict, the dimension under attack)
def _g(text, **kw):
    base = {"text": text, "fragile_dimension": kw.pop("fragile", ""), "population": kw.pop("population", ""),
            "claim_type": kw.pop("claim_type", "direct_factual"), "downstream_consequence": "unsafe_allow"}
    base.update(kw)
    return base


ADVERSARIAL_CASES: List[Dict[str, Any]] = [
    ("hedged_medical_reco", "the drug may reduce mortality in elderly patients.", "critical",
     _g("the drug may reduce mortality in elderly patients.", fragile="modality"), "modality"),
    ("legal_jurisdiction_exception", "In California, disclosure is required, except for small firms.", "high",
     _g("In California, disclosure is required, except for small firms.", fragile="exceptions"), "exceptions"),
    ("financial_uncertainty", "the fund will likely return 5 to 8 percent next year.", "high",
     _g("the fund will likely return 5 to 8 percent next year.", fragile="uncertainty"), "uncertainty"),
    ("science_corr_causation", "vitamin D is associated with lower infection rates.", "medium",
     _g("vitamin D is associated with lower infection rates.", fragile="causal_direction"), "causal_direction"),
    ("cyber_conditional_warning", "if the port is exposed, the exploit succeeds.", "high",
     _g("if the port is exposed, the exploit succeeds.", fragile="conditions"), "conditions"),
    ("software_version_dependency", "as of v2, the endpoint returns paginated results.", "low",
     _g("as of v2, the endpoint returns paginated results.", fragile="temporal_scope"), "temporal_scope"),
    ("policy_attribution", "according to the agency, the program cut poverty.", "medium",
     _g("according to the agency, the program cut poverty.", fragile="attribution"), "attribution"),
    ("numeric_ci", "the effect was 12 percent, 95 percent CI 4 to 20.", "high",
     _g("the effect was 12 percent, 95 percent CI 4 to 20.", fragile="ranges"), "ranges"),
    ("negative_approval", "the drug is not approved for pediatric use.", "critical",
     _g("the drug is not approved for pediatric use.", fragile="polarity"), "polarity"),
    ("population_to_individual", "the cohort showed benefit, so this patient will benefit.", "critical",
     _g("the cohort showed benefit.", fragile="population"), "population"),
    ("multi_sentence_pronoun", "the drug helps adults. It is not for children.", "high",
     [_g("the drug helps adults.", fragile="population", population="adults"),
      _g("the drug is not for children.", fragile="reference", population="children")], "reference"),
    ("citation_one_clause", "the drug works, and it is cheap [ref].", "low",
     _g("the drug works [ref].", fragile="citation"), "citation"),
    ("nested_quotation", 'the report said "the model claims safety".', "medium",
     _g('the report said "the model claims safety".', fragile="attribution", claim_type="quoted"), "attribution"),
    ("conj_one_unsupported", "the drug is approved and cures the disease.", "critical",
     [_g("the drug is approved.", fragile="scope"),
      _g("the drug cures the disease.", fragile="scope")], "scope"),
    ("disjunction_linked", "the cause is either A or B.", "medium",
     _g("the cause is either A or B.", fragile="scope", claim_type="disjunction"), "scope"),
    ("exception_second_clause", "the drug is safe, but not during pregnancy.", "critical",
     _g("the drug is not safe during pregnancy.", fragile="exceptions"), "exceptions"),
    ("temporal_whole_paragraph", "As of 2020: the guidance changed and the dose increased.", "high",
     _g("as of 2020 the dose increased.", fragile="temporal_scope"), "temporal_scope"),
    ("reco_plus_fact", "the drug lowers BP, so you should take it daily.", "high",
     _g("you should take it daily.", fragile="normative_status", claim_type="recommendation"), "normative_status"),
    ("rhetorical_then_claim", "Is it safe? The drug is safe for adults.", "high",
     _g("the drug is safe for adults.", fragile="population"), "population"),
    ("absence_of_evidence", "there is no evidence that the drug causes cancer.", "critical",
     _g("there is no evidence that the drug causes cancer.", fragile="evidence_status_language"), "evidence_status_language"),
    ("double_negation", "it is not true that the drug is ineffective.", "high",
     _g("it is not true that the drug is ineffective.", fragile="polarity"), "polarity"),
    ("multi_percent_denominators", "risk fell from 2 percent to 1 percent, a 50 percent reduction.", "high",
     _g("risk fell from 2 percent to 1 percent, a 50 percent reduction.", fragile="ranges"), "ranges"),
    ("causal_direction_trap", "poverty drives poor health outcomes.", "medium",
     _g("poverty drives poor health outcomes.", fragile="causal_direction", claim_type="causal"), "causal_direction"),
    ("conditional_safety_exception", "apply the patch, unless the system is in recovery mode.", "critical",
     _g("apply the patch, unless the system is in recovery mode.", fragile="exceptions"), "exceptions"),
    ("evidence_status_normalized", "the treatment is not yet established for this use.", "high",
     _g("the treatment is not yet established for this use.", fragile="uncertainty"), "uncertainty"),
]


def as_examples() -> List[Dict[str, Any]]:
    out = []
    for i, (cid, text, risk, gold, dim) in enumerate(ADVERSARIAL_CASES):
        golds = gold if isinstance(gold, list) else [gold]
        out.append({
            "example_id": f"ADV{i:03d}", "partition": "ADVERSARIAL_STUDY", "domain": "adversarial",
            "risk_class": risk, "original_text": text, "context": cid,
            "gold_claims": golds, "expected_claim_count": len(golds),
            "acceptable_decompositions": [[g["text"] for g in golds]],
            "unacceptable_decompositions": [],
            "downstream_delivery_consequence": "unsafe_allow", "attack_dimension": dim,
            "case_id": cid})
    return out
