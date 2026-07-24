"""Phase 9 - Evidence-obligation policy engine (component under test).

Composes the claim-type classifier, source-role/authority model, risk escalation, and the taxonomy into
a single EvidenceObligation record. Safety-first ordering:

  1. classify claim type and source role
  2. assess risk (ambiguity resolves upward)
  3. taxonomy default obligation (risk-aware)
  4. AUTHORITY GUARD: a low-external-burden obligation that relies on the artifact being authoritative is
     only kept if the source is genuinely authoritative for that claim family; self-referential or
     non-authoritative sources are escalated (no self-verification)
  5. RISK escalation (never lowers)
  6. STRUCTURAL safety floors: no NO_GATE on high risk; no low-burden on an action

Deterministic. Never asserts truth, never judges sufficiency, never authorizes delivery/action.
"""
from __future__ import annotations

from typing import Any, Dict

from evidence_obligation import schema as s
from evidence_obligation import taxonomy, claim_type, risk as risk_mod
from evidence_obligation import source_role as sr, authority as au

# obligation -> (minimum standard, requirement flags)
_STANDARD = {
    s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED: ("external primary authority, current, independent",
        dict(independence=True, freshness=True, authority=True, contradiction=True, citation=True)),
    s.INDEPENDENT_CORROBORATION_REQUIRED: ("independent corroborating source",
        dict(independence=True, freshness=False, authority=False, contradiction=True, citation=True)),
    s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT: ("approved internal authoritative artifact",
        dict(independence=False, freshness=True, authority=True, contradiction=False, citation=False)),
    s.IMPLEMENTATION_EVIDENCE_SUFFICIENT: ("inspectable implementation / test",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=False)),
    s.TELEMETRY_OR_MEASUREMENT_REQUIRED: ("production telemetry / measurement",
        dict(independence=False, freshness=True, authority=False, contradiction=False, citation=False)),
    s.ATTRIBUTION_VERIFICATION_REQUIRED: ("verified attribution to the cited source",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=True)),
    s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED: ("policy + authority + approval evidence",
        dict(independence=False, freshness=True, authority=True, contradiction=False, citation=False)),
    s.LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED: ("deterministic logical/mathematical check",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=False)),
    s.TEMPORAL_VERIFICATION_REQUIRED: ("current-state verification",
        dict(independence=False, freshness=True, authority=False, contradiction=False, citation=False)),
    s.CONTEXTUAL_SUPPORT_SUFFICIENT: ("local contextual support",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=False)),
    s.NO_FACTUAL_EVIDENCE_GATE: ("none (non-factual content)",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=False)),
    s.QUALIFY_BY_DEFAULT: ("qualified delivery; no factual gate satisfied",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=False)),
    s.HUMAN_REVIEW_REQUIRED: ("human adjudication",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=False)),
    s.INDETERMINATE_OBLIGATION: ("unresolved",
        dict(independence=False, freshness=False, authority=False, contradiction=False, citation=False)),
}

# obligations whose satisfaction depends on the ARTIFACT ITSELF being authoritative
_ARTIFACT_DEPENDENT = {s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT}


def assign(item: Dict[str, Any], ablate: frozenset = frozenset()) -> s.EvidenceObligation:
    """Assign an obligation. `ablate` disables named features for the Phase-18 ablation study; the
    default (empty) is the full reference component. Recognized: 'authority_guard', 'risk_escalation',
    'structural_floors', 'source_role', 'risk'."""
    text = item.get("text", "")
    path = item.get("source_path", "")
    kind = item.get("source_kind", "doc")
    intended_use = item.get("intended_use", "review")
    actionability = item.get("claim_actionability", "none")
    claim_id = item.get("artifact_id", "claim")

    fam, ct_codes = claim_type.classify_claim_type(text)
    role, role_codes = ("unknown_source", []) if "source_role" in ablate else \
        sr.classify_source_role(path, kind, text)
    risk_tier, risk_codes = ("low", ["RISK.ABLATED"]) if "risk" in ablate else \
        risk_mod.assess_risk(text, fam, intended_use, actionability)
    codes = ct_codes + role_codes + risk_codes

    obligation = taxonomy.default_obligation(fam, risk_tier)

    # 4. AUTHORITY GUARD - artifact-dependent obligations require genuine authority
    if "authority_guard" not in ablate and obligation in _ARTIFACT_DEPENDENT:
        verdict, acodes = au.authority_for(role, fam)
        codes += acodes
        if verdict in (au.SELF_REFERENTIAL, au.NOT_AUTHORITATIVE):
            obligation = s.INDEPENDENT_CORROBORATION_REQUIRED
            codes.append("POLICY.AUTHORITY_GUARD_ESCALATED")
        elif verdict == au.HISTORICAL_ONLY:
            obligation = s.TEMPORAL_VERIFICATION_REQUIRED
            codes.append("POLICY.HISTORICAL_ONLY_ESCALATED")

    # 5. RISK escalation (never lowers)
    if "risk_escalation" not in ablate:
        obligation, ecodes = risk_mod.escalate_obligation(obligation, risk_tier, fam)
        codes += ecodes

    # 6. STRUCTURAL safety floors
    if "structural_floors" not in ablate:
        if obligation == s.NO_FACTUAL_EVIDENCE_GATE and risk_tier in ("high", "critical"):
            obligation = s.CONTEXTUAL_SUPPORT_SUFFICIENT
            codes.append("POLICY.NO_GATE_FLOOR_HIGH_RISK")
        if actionability in ("action_proposal", "action_directive") and \
                obligation in s.LOW_EXTERNAL_BURDEN:
            obligation = s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED
            codes.append("POLICY.ACTION_FLOOR")

    std, flags = _STANDARD[obligation]
    allow_classes = taxonomy.rule_for(fam).get("allow_classes", [])

    o = s.new_obligation(
        claim_id=claim_id, source_artifact_id=item.get("source_path", ""),
        claim_type=fam, domain=item.get("domain", ""), risk_tier=risk_tier,
        intended_use=intended_use, source_role=role,
        source_authority=au.artifact_authority_level(role),
        artifact_authority=au.artifact_authority_level(role),
        claim_actionability=actionability,
        attribution_state=item.get("attribution_state", "none"),
        implementation_inspectability=(role in (sr.PRIMARY_IMPLEMENTATION, sr.TEST_ARTIFACT)),
        evidence_obligation_type=obligation, minimum_evidence_standard=std,
        required_source_classes=allow_classes,
        independence_requirement=flags["independence"], freshness_requirement=flags["freshness"],
        authority_requirement=flags["authority"], contradiction_search_requirement=flags["contradiction"],
        citation_requirement=flags["citation"],
        human_review_requirement=(obligation == s.HUMAN_REVIEW_REQUIRED),
        no_evidence_gate_rationale=("non-factual content" if obligation == s.NO_FACTUAL_EVIDENCE_GATE else ""),
        obligation_confidence=0.9 if ct_codes != ["CT.DEFAULT"] else 0.5,
        unresolved_ambiguity=(obligation == s.INDETERMINATE_OBLIGATION),
        reason_codes=codes)
    return o
