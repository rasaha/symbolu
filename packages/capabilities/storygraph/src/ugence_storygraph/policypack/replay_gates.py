"""Pre-registered replay acceptance gates + data-quality minimums (§6, §13).

Frozen and digest-sealed BEFORE any enterprise replay findings are viewed. Because no
sanitized enterprise dataset is present in this phase, no findings have been examined,
so this pre-registration is clean. ``evaluate_gates`` is used when a real dataset is
supplied; it is exercised here only against the synthetic fixture to prove the harness.
"""

from __future__ import annotations

from ..canonical import digest

REPLAY_GATES_VERSION = "ctd.replay_gates/1.0.0"

# §6 — minimum data quality required for a bounded, safe replay. If mandatory fields
# or entity relationships are too sparse, replay STOPS (mandatory StoryGraph relations
# cannot be evaluated safely).
DATA_QUALITY_MINIMUMS = {
    "min_normalization_success_rate": 0.98,
    "max_rejection_rate": 0.02,
    "max_entity_resolution_failure_rate": 0.05,
    "max_ordering_ambiguity_rate": 0.10,
    "max_duplicate_rate": 0.05,
    "max_cross_tenant_contamination": 0,        # hard zero
    "max_redaction_failures": 0,                # hard zero
    "min_trusted_context_availability": 0.50,
}

# §13 — acceptance gates R1..R9.
ACCEPTANCE_GATES = {
    "R1_policy_fit": "The customer workflow is represented without silently changing "
                     "business meaning (policy-gap report resolved).",
    "R2_data_quality": "Mandatory fields and entity relationships are sufficiently "
                       "available for bounded replay (DATA_QUALITY_MINIMUMS met).",
    "R3_tenant_isolation": "No event or evidence crosses tenant boundaries.",
    "R4_deterministic_replay": "Repeated replay produces identical findings and digests.",
    "R5_exact_completion_integrity": "Every exact-completion finding has all required "
                                     "nodes and mandatory edges positively satisfied.",
    "R6_context_safety": "Missing/unavailable legitimate evidence does not strengthen "
                         "the harmful graph.",
    "R7_explanation_quality": "Each review item identifies the exact events, "
                              "relationships, context coverage, and unresolved issues.",
    "R8_operational_burden": "Review volume and duplicate findings remain below the "
                             "pre-registered pilot threshold.",
    "R9_evidence_chain": "The official replay uses the two-commit evidence workflow.",
}

# §13 R8 pilot thresholds (pre-registered)
PILOT_THRESHOLDS = {
    "max_review_items_per_1000_events": 60.0,
    "max_duplicate_finding_rate": 0.10,
    "max_benign_escalate_rate": 0.10,
}

PREREGISTRATION = {
    "version": REPLAY_GATES_VERSION,
    "data_quality_minimums": DATA_QUALITY_MINIMUMS,
    "acceptance_gates": ACCEPTANCE_GATES,
    "pilot_thresholds": PILOT_THRESHOLDS,
    "preregistered_before_findings": True,
    "note": "Sealed before any enterprise replay findings were viewed. No sanitized "
            "enterprise dataset was present in this phase.",
}


def preregistration_digest() -> str:
    return digest(PREREGISTRATION, domain="CTD-REPLAY-PREREG")


def data_quality_gate(dq: dict) -> dict:
    """Evaluate R2 against a data-quality report (deterministic)."""
    total = max(1, dq.get("records_received", 0))
    norm_rate = dq.get("records_normalized", 0) / total
    reject_rate = dq.get("records_rejected", 0) / total
    checks = [
        ("min_normalization_success_rate", norm_rate,
         norm_rate >= DATA_QUALITY_MINIMUMS["min_normalization_success_rate"]),
        ("max_rejection_rate", reject_rate,
         reject_rate <= DATA_QUALITY_MINIMUMS["max_rejection_rate"]),
        ("max_cross_tenant_contamination", dq.get("cross_tenant_contamination", 0),
         dq.get("cross_tenant_contamination", 0) == 0),
        ("max_redaction_failures", dq.get("redaction_failures", 0),
         dq.get("redaction_failures", 0) == 0),
        ("unknown_event_types", dq.get("unknown_event_types", 0),
         dq.get("unknown_event_types", 0) == 0),
        ("ordering_conflicts", dq.get("ordering_conflicts", 0),
         dq.get("ordering_conflicts", 0) == 0),
    ]
    return {"gate": "R2_data_quality",
            "pass": all(ok for _, _, ok in checks),
            "checks": [{"metric": m, "value": v, "pass": ok} for m, v, ok in checks]}
