"""Deterministic replay (Phase 11, invariant 13). Re-runs a scenario under the historical
policy + registry versions recorded in its trace and confirms the terminal outcome and
per-decision states reproduce exactly. Replay is read-only: no telemetry, no registry update.
A replay whose pinned versions differ from the recorded trace fails POLICY.REPLAY_VERSION_MISMATCH.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from control_plane.failure_codes import Failure
from control_plane.orchestrator import Orchestrator, Scenario, TraceResult


@dataclass
class ReplayResult:
    reproduced: bool
    mismatch_reason: Optional[str]
    original_terminal: str
    replay_terminal: str


def replay(sc: Scenario, recorded: TraceResult,
           recorded_policy_version: str, recorded_registry_version: str) -> ReplayResult:
    # version pins must match the recorded trace (invariant 13)
    if (sc.envelope.policy_versions.get("enterprise") != recorded_policy_version
            or sc.envelope.registry_version != recorded_registry_version):
        return ReplayResult(False, Failure.REPLAY_VERSION_MISMATCH.value,
                            recorded.terminal_state, "NOT_RUN")
    # read-only re-run: same enforcement config, deterministic mocks, no live effects
    o = Orchestrator(validate_contracts=True, enforce_invariants=True)
    rep = o.run(sc)
    ok = (rep.terminal_state == recorded.terminal_state
          and rep.terminal_reasons == recorded.terminal_reasons
          and rep.selected == recorded.selected)
    reason = None if ok else "outcome_divergence"
    return ReplayResult(ok, reason, recorded.terminal_state, rep.terminal_state)
