"""Model Selection — version.

Model Selection is the cross-cutting policy capability that evaluates already-approved
model/provider candidates against mandatory eligibility constraints and policy-weighted
optimization criteria, then returns a deterministic policy-bounded selection or a
no-eligible-model outcome.

It owns exactly two stages — **ExecutionGate** (deterministic, fail-closed eligibility:
"can this approved candidate execute this request?") and **ModelPolicy** (advisory,
policy-bounded selection: "which eligible candidate should?"). It does not invoke models,
route, retry, fail over, load balance, schedule, orchestrate, authorize actions, register
providers, or manage credentials — those belong to other capabilities/layers.

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
