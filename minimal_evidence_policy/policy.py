"""Phase 2-3 - The minimal evidence-obligation policy.

Deterministic precedence:
  1. structural invariants (incl. anti-self-verification)  -- can only RAISE
  2. risk floor                                            -- the non-negotiable minimum
  3. upward-only modifiers (claim-type, source-role, temporal, actionability)
  4. E0 eligibility (only for independently non-factual content)
  5. final validation (never below the risk floor)

No later rule weakens an earlier obligation. Small by design: the primary policy rules are counted and
kept within the complexity budget (<=20). Every decision is explainable in one trace.
"""
from __future__ import annotations

from typing import Any, Dict

from minimal_evidence_policy import schema as s, invariants

# --- risk floor (rule 1) ---
_RISK_FLOOR = {"low": s.E1, "medium": s.E2, "high": s.E3, "critical": s.E4, "unknown": s.ER}

# claim families eligible for E0 (non-factual / non-assertive), independently established
_E0_ELIGIBLE = {"subjective_opinion", "user_preference", "hypothetical", "rhetorical",
                "formatting_instruction", "declared_intention", "local_label"}

# families that force a minimum regardless of low risk (upward-only modifiers)
_MIN_E4 = {"medical", "financial", "legal_interpretation", "external_regulation"}      # rule set
_MIN_E3 = {"measured_performance", "model_quality", "current_fact", "security_capability",
           "status_report", "scientific", "causal", "unsupported_marketing"}
_E2_OK = {"code_behavior", "api_behavior", "internal_policy", "mathematical", "attribution",
          "requirement", "prohibition", "process_description", "design_rationale",
          "implementation_plan", "recommendation"}


def assign(item: Dict[str, Any], ablate: frozenset = frozenset()) -> s.Decision:
    claim_id = item.get("artifact_id", "claim")
    risk = item.get("risk_tier", "unknown")
    fam = item.get("claim_family", "")
    actionability = item.get("claim_actionability", "none")
    temporal = item.get("temporal_sensitivity", "static")

    # 2. risk floor (unless ablated). E0-eligible NON-FACTUAL content at low risk is exempt from the
    #    FACTUAL floor (there is no factual claim to gate) -> floor E0; INV-12 still bars high-risk E0.
    e0_eligible = fam in _E0_ELIGIBLE and risk == "low" and not item.get("factual_leak")
    if "risk_floor" in ablate:
        floor = s.E1
    elif e0_eligible:
        floor = s.E0
    else:
        floor = _RISK_FLOOR.get(risk, s.ER)
    obligation = floor
    modifiers = ["MOD.E0_NON_FACTUAL"] if e0_eligible else []
    reason = [f"FLOOR.{risk}->{floor}"]

    # 3. upward-only modifiers (each may only RAISE; ablatable for the study)
    if "claim_type" not in ablate:
        if fam in _MIN_E4:
            obligation = s.higher(obligation, s.E4); modifiers.append("MOD.REGULATED_MIN_E4")
        elif fam in _MIN_E3:
            obligation = s.higher(obligation, s.E3); modifiers.append("MOD.MEASURED_OR_CURRENT_MIN_E3")
        elif fam in _E2_OK:
            obligation = s.higher(obligation, s.E2); modifiers.append("MOD.INTERNAL_OR_IMPL_MIN_E2")
    if "temporal" not in ablate and temporal in ("time_sensitive", "current_status"):
        obligation = s.higher(obligation, s.E3); modifiers.append("MOD.TEMPORAL_MIN_E3")
    if "actionability" not in ablate and actionability in ("action_proposal", "action_directive"):
        obligation = s.higher(obligation, s.E3); modifiers.append("MOD.ACTION_MIN_E3")
        if item.get("irreversible") or item.get("high_impact"):
            obligation = s.higher(obligation, s.E4); modifiers.append("MOD.ACTION_IRREVERSIBLE_MIN_E4")
    if "high_impact_recommendation" not in ablate and fam == "recommendation" and item.get("high_impact"):
        obligation = s.higher(obligation, s.E4); modifiers.append("MOD.HIGH_IMPACT_REC_MIN_E4")

    # 1. structural invariants (applied last so they can only RAISE the result) -- ablatable
    inv_codes = []
    if "invariants" not in ablate:
        obligation, inv_codes = invariants.apply(item, obligation)

    # re-assert the risk floor after E0 (INV-9 monotonic guarantee), unless floor ablated
    if "risk_floor" not in ablate:
        obligation = s.higher(obligation, floor)

    unresolved = []
    for fld in ("risk_tier", "claim_family"):
        if not item.get(fld) or item.get(fld) == "unknown":
            unresolved.append(fld)

    d = s.Decision(
        claim_id=claim_id, risk_floor=floor, modifiers_applied=modifiers,
        invariants_triggered=inv_codes, final_obligation=obligation,
        rationale="; ".join(reason + modifiers + inv_codes),
        unresolved_fields=unresolved,
        review_required=(obligation == s.ER),
        reason_codes=reason + modifiers + inv_codes)

    # fail-closed: a structural violation forces ER
    if s.validate(d):
        d.final_obligation = s.ER; d.review_required = True
        d.reason_codes.append("MP.STRUCTURAL_VIOLATION_TO_ER")
    return d


# primary policy rule count (for the complexity budget)
PRIMARY_RULE_COUNT = 5 + 5 + 12   # risk floor + modifiers + 12 invariants (counted in invariants.py)
