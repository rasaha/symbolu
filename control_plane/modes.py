"""Execution modes (Phase 11). Capability flags per mode; default is MOCK.

ENFORCEMENT is the ONLY mode in which real external provider calls and real action
execution are permitted, and it requires explicit configuration. In this environment
ENFORCEMENT is never enabled (task constraint: no live calls, no real actions).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeCaps:
    name: str
    authoritative: str          # who is the authoritative decision maker in this mode
    external_calls: bool        # may ProviderAdapter make a real provider call?
    customer_data: bool         # may real customer data cross the provider boundary?
    actions_execute: bool       # may ActionAdapter actually execute?
    audit_required: bool
    fallback: str
    override: str
    spend_controls: str
    notes: str


MODE_TABLE = {
    "REPLAY": ModeCaps(
        "REPLAY", authoritative="historical record", external_calls=False, customer_data=False,
        actions_execute=False, audit_required=True, fallback="as-recorded",
        override="none (read-only)", spend_controls="zero spend",
        notes="Re-runs a recorded trace under its pinned historical versions (invariant 13). "
              "Emits no telemetry, no registry update."),
    "MOCK": ModeCaps(
        "MOCK", authoritative="deterministic mock components", external_calls=False, customer_data=False,
        actions_execute=False, audit_required=True, fallback="mock re-evaluation",
        override="simulated only", spend_controls="zero spend",
        notes="Default. Provider/TAP/ActionGate/ActionAdapter are deterministic mocks. "
              "Used for scenario suite and integration evaluation."),
    "SHADOW": ModeCaps(
        "SHADOW", authoritative="existing production path (control plane is advisory)",
        external_calls=False, customer_data=False, actions_execute=False, audit_required=True,
        fallback="defer to production", override="none",
        spend_controls="zero incremental spend",
        notes="Control plane computes a recommendation alongside the real path but never acts. "
              "Recommendation vs authoritative route recorded for comparison."),
    "ADVISORY": ModeCaps(
        "ADVISORY", authoritative="human/consumer of the recommendation",
        external_calls=False, customer_data=False, actions_execute=False, audit_required=True,
        fallback="human decision", override="human",
        spend_controls="zero action spend",
        notes="Emits decisions/recommendations for a human to act on; the plane itself "
              "executes nothing."),
    "ENFORCEMENT": ModeCaps(
        "ENFORCEMENT", authoritative="control plane", external_calls=True, customer_data=True,
        actions_execute=True, audit_required=True, fallback="re-enter eligibility+policy (invariant 19)",
        override="explicit, attributable, audited (invariant 8)",
        spend_controls="hard cost/latency budgets enforced",
        notes="ONLY mode where real calls and real actions occur. Requires explicit config. "
              "Audit-write success gates execution (invariant 15). DISABLED in this environment."),
}

DEFAULT_MODE = "MOCK"
NON_ENFORCING = {"REPLAY", "MOCK", "SHADOW", "ADVISORY"}


def caps(mode: str) -> ModeCaps:
    if mode not in MODE_TABLE:
        raise ValueError(f"POLICY.CONTRACT_VERSION_UNSUPPORTED: unknown mode {mode}")
    return MODE_TABLE[mode]


def may_execute_actions(mode: str) -> bool:
    return caps(mode).actions_execute


def may_call_provider(mode: str) -> bool:
    return caps(mode).external_calls
