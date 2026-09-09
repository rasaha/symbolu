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

__version__ = "0.2.0"

VERSION = __version__
VERSION_INFO: tuple[int, int, int] = tuple(int(p) for p in __version__.split("."))  # type: ignore[assignment]

#: The first policy version: the eligibility algorithm as it stood through 0.1.0, before
#: the non-compensatory capability floor existed. Retained as a *readable* version —
#: stored records stamped with it stay valid, replayable and verifiable forever — but no
#: longer a writable one. See ``SUPPORTED_POLICY_VERSIONS``.
POLICY_VERSION_V1 = "exec_gate_v1"

#: The current policy version, and what this implementation stamps on every decision it
#: makes. 0.2.0 added the ``quality_within_floor`` condition, so with a floor configured
#: this code can reach a different outcome from 0.1.0 on identical inputs. A policy
#: version identifies *decision semantics*, not record shape, and two implementations
#: that can disagree must not both answer to "exec_gate_v1" — that is precisely what
#: replay and audit use the field to rule out.
#:
#: The bump does not reach backwards. It changes what new decisions are stamped with; it
#: neither rewrites nor invalidates a single stored record.
POLICY_VERSION_V2 = "exec_gate_v2"

#: The version this core stamps on new decisions.
POLICY_VERSION = POLICY_VERSION_V2

#: Every version this core can read back and verify, oldest first. Writing is confined to
#: :data:`POLICY_VERSION`; reading spans all of these. An unrecognized version — including
#: a *newer* one written by a future release — is refused rather than guessed at, because
#: a record whose semantics this code does not know is not one it may attest to.
SUPPORTED_POLICY_VERSIONS: tuple[str, ...] = (POLICY_VERSION_V1, POLICY_VERSION_V2)


def major_of(version: str) -> int:
    return int(version.split(".")[0])
