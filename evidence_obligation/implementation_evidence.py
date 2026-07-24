"""Phase 12 - Implementation evidence.

Decides whether a given kind of implementation evidence SUPPORTS a claim - and, critically, what it does
NOT prove. Implementation evidence may support a behavior/capability claim; it must never automatically
prove production reliability, operational performance, customer availability, security certification, or
real-world effectiveness (those need telemetry / external authority).

Deterministic, fail-closed: an unknown evidence kind is INSUFFICIENT.
"""
from __future__ import annotations

from typing import List, Tuple

SUPPORTS = "SUPPORTS"                    # evidence supports the (behavior/capability) claim
INSUFFICIENT = "INSUFFICIENT"           # evidence does not support the claim
NON_PRODUCTION = "NON_PRODUCTION"       # supports behavior but NOT a production/operational claim

# evidence kind -> what it can support
_STRONG = {"source_code", "unit_test", "integration_test", "configuration", "function_signature"}
_WEAK = {"comment_only", "dead_code", "feature_flag_disabled", "stale_documentation",
         "mocked_behavior", "generated_fixture", "version_mismatch"}

# claim classes that implementation evidence can NEVER prove on its own
_PRODUCTION_CLAIMS = {"measured_performance", "model_quality", "status_report", "current_fact"}
_REQUIRES_EXTERNAL = {"security_certification", "customer_availability", "real_world_effectiveness"}


def assess(evidence_kind: str, claim_family: str) -> Tuple[str, List[str]]:
    """Return (verdict, reason_codes)."""
    # production/operational/effectiveness claims are never proven by implementation alone
    if claim_family in _PRODUCTION_CLAIMS or claim_family in _REQUIRES_EXTERNAL:
        return NON_PRODUCTION, ["IMPL.PRODUCTION_CLAIM_NEEDS_TELEMETRY"]
    if evidence_kind in _WEAK:
        return INSUFFICIENT, [f"IMPL.WEAK:{evidence_kind}"]
    if evidence_kind in _STRONG:
        # integration test can support a composition claim; a bare signature only an interface claim
        if evidence_kind == "function_signature" and claim_family not in ("api_behavior", "code_behavior"):
            return INSUFFICIENT, ["IMPL.SIGNATURE_INSUFFICIENT_FOR_CLAIM"]
        return SUPPORTS, [f"IMPL.SUPPORTS:{evidence_kind}"]
    return INSUFFICIENT, [f"IMPL.UNKNOWN_KIND:{evidence_kind}"]   # fail-closed


# canonical test matrix (Phase 12): evidence_kind, claim_family, expected verdict
TEST_MATRIX = [
    ("source_code", "code_behavior", SUPPORTS),
    ("unit_test", "code_behavior", SUPPORTS),
    ("integration_test", "api_behavior", SUPPORTS),
    ("configuration", "internal_policy", SUPPORTS),
    ("function_signature", "api_behavior", SUPPORTS),
    ("comment_only", "code_behavior", INSUFFICIENT),
    ("dead_code", "code_behavior", INSUFFICIENT),
    ("feature_flag_disabled", "product_capability", INSUFFICIENT),
    ("stale_documentation", "code_behavior", INSUFFICIENT),
    ("mocked_behavior", "code_behavior", INSUFFICIENT),
    ("generated_fixture", "measured_performance", NON_PRODUCTION),
    ("version_mismatch", "code_behavior", INSUFFICIENT),
    ("source_code", "measured_performance", NON_PRODUCTION),      # code != production performance
    ("unit_test", "current_fact", NON_PRODUCTION),                # test != current production status
]


def validate() -> dict:
    rows = []
    correct = 0
    for kind, fam, expected in TEST_MATRIX:
        got, codes = assess(kind, fam)
        ok = got == expected
        correct += ok
        rows.append({"evidence_kind": kind, "claim_family": fam, "expected": expected,
                     "got": got, "ok": ok})
    return {"n": len(TEST_MATRIX), "correct": correct,
            "accuracy": round(correct / len(TEST_MATRIX), 4), "rows": rows}
