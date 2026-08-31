"""Model Authority — version.

Model Authority is the cross-cutting policy capability that determines which model, if
any, is authorized to execute a specific request under the current policy, capability,
jurisdiction, security, cost, and runtime conditions, and issues a binding model
authorization decision (ALLOW / DENY / HOLD / ESCALATE).

It composes three stages — **ExecutionGate** (deterministic, fail-closed eligibility:
"can this approved candidate execute this request?"), **ModelPolicy** (the internal
optimization mechanism, ranking eligible candidates), and **ModelAuthority** (the binding
external contract: "which model, if any, is authorized?"). It does not invoke models,
route, retry, fail over, load balance, schedule, orchestrate, authorize actions, register
providers, or manage credentials — those belong to other capabilities/layers.

Evolved from "Model Selection"; the distribution name ``ugence-model-selection`` and the
selection/eligibility symbols are retained as a compatibility surface.

Versioned independently of the platform. This capability was **not** part of the recorded
Platform v1.0 freeze; this package is its first canonical distribution.
"""
from __future__ import annotations

__version__ = "0.1.0"

VERSION = __version__
VERSION_INFO: tuple[int, int, int] = tuple(int(p) for p in __version__.split("."))  # type: ignore[assignment]

#: The eligibility/selection policy-record version stamped on decisions by this core.
#: Mirrors the legacy ``GateConfig.policy_version`` default ("exec_gate_v1"), preserved
#: verbatim so serialized decision records are byte-identical across the migration.
POLICY_VERSION = "exec_gate_v1"


def major_of(version: str) -> int:
    return int(version.split(".")[0])
