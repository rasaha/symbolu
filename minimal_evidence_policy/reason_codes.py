"""Phase 8 - Reason-code catalog for the minimal policy.

Deterministic, human-readable reason codes emitted by the policy, modifiers, and invariants. Kept as a
flat catalog so every decision trace is explainable and stable.
"""
from __future__ import annotations

CATALOG = {
    # floor
    "FLOOR": "risk floor applied (risk_tier -> level)",
    # modifiers
    "MOD.E0_NON_FACTUAL": "non-factual content exempt from the factual floor",
    "MOD.REGULATED_MIN_E4": "medical/financial/legal/regulatory -> min E4",
    "MOD.MEASURED_OR_CURRENT_MIN_E3": "performance/quality/current/security/etc -> min E3",
    "MOD.INTERNAL_OR_IMPL_MIN_E2": "internal-policy/code/api/etc -> min E2",
    "MOD.TEMPORAL_MIN_E3": "time-sensitive/current-status -> min E3",
    "MOD.ACTION_MIN_E3": "action proposal/directive -> min E3",
    "MOD.ACTION_IRREVERSIBLE_MIN_E4": "irreversible/high-impact action -> min E4",
    "MOD.HIGH_IMPACT_REC_MIN_E4": "high-impact recommendation -> min E4",
    # invariants
    "INV-1.NO_MODEL_SELF_VERIFICATION": "model-generated factual assertion cannot self-verify -> >=E3",
    "INV-2.NO_CIRCULAR_CORROBORATION": "claim-derived/circular evidence not independent -> >=E3",
    "INV-3.INTERNAL_NOT_AUTHORITATIVE": "internal-authority claim without explicit basis -> >=E3",
    "INV-4.DOC_VS_IMPL_CONFLICT": "documentation contradicts implementation -> ER",
    "INV-5.FIXTURE_NOT_TELEMETRY": "fixture/mock/synthetic not production telemetry -> >=E3",
    "INV-6.IMPL_NOT_OPERATIONAL": "implementation does not prove operational performance -> >=E3",
    "INV-7.STALE_AUTHORITY": "stale authority cannot satisfy a current claim -> >=E3",
    "INV-8.ATTRIBUTION_NOT_TRUTH": "attribution verification is not truth verification -> >=E3",
    "INV-10.UNKNOWN_TO_REVIEW": "unknown critical metadata -> ER",
    "INV-11.ACTION_NEEDS_AUTHORITY": "action authority separate from factual support -> >=E3",
    "INV-11.APPROVAL_ABSENT": "action lacks approval evidence",
    "INV-12.NO_HIGH_RISK_E0": "no high-risk/critical E0 -> >=E1",
    # structural
    "MP.STRUCTURAL_VIOLATION_TO_ER": "structural validation failed -> ER (fail-closed)",
}


def describe(code: str) -> str:
    key = code.split(":")[0]
    return CATALOG.get(key, CATALOG.get(key.split(".")[0], "unknown code"))
