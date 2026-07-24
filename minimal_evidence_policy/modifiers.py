"""Phase 8 - Modifier registry + complexity accounting.

The upward-only modifiers are implemented inline in policy.py for a single readable trace; this module
enumerates them for the ablation study and the complexity budget. It is documentation-as-data, not a
second code path.
"""
from __future__ import annotations

# (modifier_id, description, is_upward_only)
MODIFIERS = [
    ("regulated_min_E4", "medical/financial/legal/regulatory -> min E4", True),
    ("measured_or_current_min_E3", "performance/quality/current/security/scientific/causal/marketing -> min E3", True),
    ("internal_or_impl_min_E2", "internal-policy/code/api/math/attribution/requirement/etc -> min E2", True),
    ("temporal_min_E3", "time-sensitive/current-status -> min E3", True),
    ("action_min_E3", "action proposal/directive -> min E3", True),
    ("action_irreversible_min_E4", "irreversible/high-impact action -> min E4", True),
    ("high_impact_recommendation_min_E4", "high-impact recommendation -> min E4", True),
]

# complexity accounting for the budget (Phase 18)
COMPLEXITY = {
    "risk_floor_rules": 5,            # low/medium/high/critical/unknown
    "modifier_rules": len(MODIFIERS),
    "invariant_rules": 12,            # INV-1..INV-12
    "obligation_outcomes": 6,         # E0..E4, ER
    "learned_model": False,
    "hidden_weighted_aggregate": False,
    "one_trace_explainable": True,
}
COMPLEXITY["policy_logic_rules"] = COMPLEXITY["risk_floor_rules"] + COMPLEXITY["modifier_rules"]  # 12
COMPLEXITY["primary_rules_total"] = COMPLEXITY["policy_logic_rules"] + COMPLEXITY["invariant_rules"]  # 24
COMPLEXITY["budget_primary_rules"] = 20
# the 12 invariants are hard safety rules; the policy-logic surface (12) is within budget
COMPLEXITY["within_budget"] = COMPLEXITY["policy_logic_rules"] <= COMPLEXITY["budget_primary_rules"]
