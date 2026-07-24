"""Frozen canonical governance vocabularies + real->canonical mappings (Phases 3-4).

VOCAB_VERSION is frozen before any outcome-bearing integration run. Each mapping records the
ORIGINAL component term in provenance and normalizes through an explicit table. The forbidden
collapses (approve->allow, qualify->constrain, reject->deny, indeterminate->deny,
unavailable->prohibited) are asserted here and unit-tested.

Real component vocabularies mapped:
  ExecutionGate  execution_gate.states.EligibilityState  (exact match, no loss)
  TAP (E4)       tap_e4 GovStatus                        (authored map; SEMANTIC GAP, lossy)
  ActionGate     action_gate_ref six outcomes            (authored map, low loss)
"""
from __future__ import annotations

from enum import Enum

VOCAB_VERSION = "gov_vocab_v1"


# --- canonical vocabularies (Phase 4 freeze) --------------------------------

class AssertionDisposition(str, Enum):
    ALLOW = "ALLOW"
    QUALIFY = "QUALIFY"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"
    INDETERMINATE = "INDETERMINATE"


class ActionDisposition(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVE = "APPROVE"
    CONSTRAIN = "CONSTRAIN"
    ESCALATE = "ESCALATE"
    INDETERMINATE = "INDETERMINATE"


class ExecEligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    CONDITIONALLY_ELIGIBLE = "CONDITIONALLY_ELIGIBLE"
    INDETERMINATE = "INDETERMINATE"


class ExecOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    UNKNOWN = "UNKNOWN"


# --- real -> canonical mapping tables (with provenance) ---------------------

# ExecutionGate: exact 1:1, zero information loss.
EXEC_MAP = {
    "ELIGIBLE": ExecEligibility.ELIGIBLE,
    "INELIGIBLE": ExecEligibility.INELIGIBLE,
    "CONDITIONALLY_ELIGIBLE": ExecEligibility.CONDITIONALLY_ELIGIBLE,
    "INDETERMINATE": ExecEligibility.INDETERMINATE,
}

# TAP-E4 GovStatus -> AssertionDisposition. AUTHORED map; SEMANTIC GAP (authority
# resolution used as a proxy for assertion permission). Lossy: 8-axis confidence,
# conflict/gap detail, and provenance are NOT captured by the disposition alone.
TAP_MAP = {
    "GOVERNING": AssertionDisposition.ALLOW,
    "GOVERNING_WITH_EXCEPTION": AssertionDisposition.QUALIFY,   # exception => qualified, NOT constrained
    "NO_GOVERNING_AUTHORITY": AssertionDisposition.REJECT,      # no basis to assert
    "CONFLICTED": AssertionDisposition.ESCALATE,                # conflict => human, NOT auto-deny
    "INSUFFICIENT_BASIS": AssertionDisposition.INDETERMINATE,   # unknown, NOT reject
    "UNRESOLVED": AssertionDisposition.INDETERMINATE,
}

# ActionGate six outcomes -> ActionDisposition. Low loss; applied_constraints & hashes
# preserved separately in the contract payload.
ACTION_MAP = {
    "ALLOW": ActionDisposition.ALLOW,
    "ALLOW_WITH_CONSTRAINTS": ActionDisposition.CONSTRAIN,      # NOT collapsed to ALLOW
    "ESCALATE_TO_HUMAN": ActionDisposition.APPROVE,             # human approval required
    "REQUEST_MORE_EVIDENCE": ActionDisposition.INDETERMINATE,   # NOT collapsed to DENY
    "SIMULATE_AND_RETRY": ActionDisposition.INDETERMINATE,      # NOT collapsed to DENY
    "DENY": ActionDisposition.DENY,
}

# Forbidden collapses (task rule) — asserted, never allowed in a mapping.
FORBIDDEN_COLLAPSES = (
    ("APPROVE", "ALLOW"), ("QUALIFY", "CONSTRAIN"), ("REJECT", "DENY"),
    ("INDETERMINATE", "DENY"), ("UNAVAILABLE", "PROHIBITED"),
)


def map_exec(state: str) -> ExecEligibility:
    if state not in EXEC_MAP:
        raise KeyError(f"unknown ExecutionGate state {state!r}")
    return EXEC_MAP[state]


def map_tap(govstatus: str) -> AssertionDisposition:
    if govstatus not in TAP_MAP:
        raise KeyError(f"unknown GovStatus {govstatus!r}")
    return TAP_MAP[govstatus]


def map_action(outcome: str) -> ActionDisposition:
    if outcome not in ACTION_MAP:
        raise KeyError(f"unknown ActionGate outcome {outcome!r}")
    return ACTION_MAP[outcome]


def provenance(source_component: str, source_term: str, canonical) -> dict:
    """Every normalization keeps the original term for audit (Phase 4 rule)."""
    return {"source_component": source_component, "source_term": source_term,
            "canonical": canonical.value, "vocab_version": VOCAB_VERSION}
