"""Frozen verdict precedence (protocol before base capability). Torch-free.

Precedence (first match wins), per Amendment-002 §6 / preregistration §10:
  0 PROTOCOL_VIOLATED
  1 RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY
  2 SHORTCUT_OR_LEAKAGE_DETECTED
  3 RESOURCE_BLOCKED
  4 ABSTENTION_FAILED
  5 EVIDENCE_GROUNDING_FAILED
  6 TEMPORAL_REASONING_FAILED
  7 POLICY_REASONING_FAILED
  8 RELATIONAL_REASONING_VALIDATED
  9 RELATIONAL_REASONING_PARTIAL
 10 RELATIONAL_REASONING_NOT_FOUND
"""
from __future__ import annotations

from .config import FORBIDDEN_VERDICTS, PRESERVED_VERDICTS

ALLOWED = (
    "RELATIONAL_REASONING_VALIDATED", "RELATIONAL_REASONING_PARTIAL", "RELATIONAL_REASONING_NOT_FOUND",
    "TEMPORAL_REASONING_FAILED", "POLICY_REASONING_FAILED", "EVIDENCE_GROUNDING_FAILED",
    "ABSTENTION_FAILED", "RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY",
    "SHORTCUT_OR_LEAKAGE_DETECTED", "PROTOCOL_VIOLATED", "RESOURCE_BLOCKED",
)


def decide(*, protocol_valid: bool, base_capability_established: bool, shortcut_detected: bool,
           resource_ok: bool, gates: dict, discovery_ok: bool, composite_ok: bool) -> dict:
    """Return the primary verdict + preserved co-emitted invariants. Never emits a forbidden verdict.

    `gates` is the result of gates.evaluate_gates(...)['gates']. Missing gate results (value None) are
    treated as not-yet-decided and do not by themselves force a failure at steps 4-7.
    """
    def failed(name: str) -> bool:
        g = gates.get(name)
        return bool(g is not None and g.get("pass") is False)

    if not protocol_valid:
        primary = "PROTOCOL_VIOLATED"
        co = ()
    elif not base_capability_established:
        primary = "RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY"
        co = ("BASE_COPY_SELECTION_CAPABILITY_NOT_ESTABLISHED",)
    elif shortcut_detected:
        primary = "SHORTCUT_OR_LEAKAGE_DETECTED"; co = ()
    elif not resource_ok:
        primary = "RESOURCE_BLOCKED"; co = ()
    elif failed("abstention_R10_R11") or failed("false_abstention_on_answerable_max"):
        primary = "ABSTENTION_FAILED"; co = ()
    elif failed("evidence_precision") or failed("evidence_recall"):
        primary = "EVIDENCE_GROUNDING_FAILED"; co = ()
    elif failed("latest_event") or failed("R7_path_discovery_temporal"):
        primary = "TEMPORAL_REASONING_FAILED"; co = ()
    elif failed("policy_condition") or failed("R9_composite_final_answer"):
        primary = "POLICY_REASONING_FAILED"; co = ()
    else:
        all_pass = all(v.get("pass") for v in gates.values() if v.get("pass") is not None)
        if all_pass and discovery_ok and composite_ok:
            primary = "RELATIONAL_REASONING_VALIDATED"; co = ()
        elif not (discovery_ok and composite_ok):
            primary = "RELATIONAL_REASONING_PARTIAL"; co = ()  # path-execution only
        else:
            primary = "RELATIONAL_REASONING_NOT_FOUND"; co = ()
    assert primary in ALLOWED
    assert primary not in FORBIDDEN_VERDICTS
    return {"primary_verdict": primary, "co_emitted": list(co),
            "preserved": list(PRESERVED_VERDICTS)}
