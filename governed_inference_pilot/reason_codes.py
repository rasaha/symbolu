"""Reason-code taxonomy (Phase 4). Namespaced, stable reason codes preserved end-to-end. Each stage
contributes its own codes; the pilot never rewrites a component's codes, only namespaces and forwards
them. Deterministic.
"""
from __future__ import annotations

from typing import Dict, List

# pilot-level codes (GIP.*) - orchestration / contract / audit
GIP_CODES = {
    "GIP.MISSING_FIELD": "a required contract field was absent or empty",
    "GIP.UNKNOWN_VOCAB": "a downstream disposition value was outside the known vocabulary",
    "GIP.UNKNOWN_CONTRACT": "an unregistered contract was invoked",
    "GIP.VERSION_MISMATCH": "component/contract version mismatch",
    "GIP.SEMANTIC_LOSS": "a governing field was lost during adapter transformation",
    "GIP.FAIL_CLOSED": "a fail-closed contract halted the pipeline",
    "GIP.STAGE_SKIPPED_BY_POLICY": "a stage was skipped by explicit risk-tier policy",
    "GIP.STAGE_EXCEPTION": "a component raised an exception (treated as unsafe)",
    "GIP.EXECUTION_UNAVAILABLE": "no eligible model / execution not permitted",
    "GIP.EVIDENCE_UNAVAILABLE": "evidence could not be bound or was untrusted",
    "GIP.ACTION_ABSENT": "no explicit action proposal found",
    "GIP.ACTION_AMBIGUOUS": "action proposal ambiguous -> INDETERMINATE",
    "GIP.HUMAN_REVIEW_REQUIRED": "routed to human review",
    "GIP.CASCADE_CONSERVATIVE": "multiple conservative stages compounded",
}

# stage code prefixes (a component's own codes are forwarded under these namespaces, never rewritten)
STAGE_PREFIX = {
    "execution_gate": "EXEC.", "model_policy": "MODEL.", "claim_integrity": "CI.",
    "scope_integrity": "SCOPE.", "evidence_assurance": "EA.", "assertion_gate": "AGR.",
    "action_gate": "ACT.",
}


def namespace(stage: str, codes: List[str]) -> List[str]:
    """Forward a component's reason codes under its stage namespace WITHOUT rewriting them: if a code
    is already namespaced (contains a dot), keep it; else prefix with the stage namespace."""
    pre = STAGE_PREFIX.get(stage, "GEN.")
    out = []
    for c in codes:
        out.append(c if "." in c else f"{pre}{c}")
    return out


def describe(code: str) -> str:
    return GIP_CODES.get(code, "(component-defined reason code)")
