"""Canonical Execution State — the runtime-owned, versioned, integrity-protected
identity of a single execution trajectory.

The Agent Runtime is the canonical owner of *execution trajectory identity*: for a
given workflow/task it records exactly which trajectory it is coordinating, what
caused it, what immutable action identity (the ``TransitionProposal`` fingerprint) is
involved, and what external authority/artifact references are associated with it. It
does this while remaining explicitly **non-authoritative** about policy and business
decisions.

``CanonicalExecutionState`` is deliberately NOT any of the following:

* agent reasoning context (prompts, message history, RAG, scratchpad, model state);
* shared semantic memory or LLM scratch reasoning;
* policy, permission, authorization, clearance, or admitted evidence — it carries
  immutable *references* to such external authority objects, never their substance;
* the H22 portfolio scheduler / resource ledger / fairness state;
* a second, independently canonicalized copy of the proposed action payload — action
  identity remains owned by ``TransitionProposal`` and is referenced here by
  fingerprint, never re-derived.

Three separate contexts are preserved by design (see
``docs/AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md``):

    A. Agent Reasoning Context   — owned OUTSIDE the runtime (agent frameworks);
    B. Canonical Execution State — owned by the Agent Runtime (this object);
    C. Enterprise Authority State — owned EXTERNALLY (governance / decision authority).

The object is a frozen, stdlib-only dataclass with deterministic canonical
serialization and a SHA-256 content digest. Semantically equivalent construction
produces an identical digest; changing any identity-bearing field changes the digest.
Constructing one creates no authority: it cannot turn HOLD/BLOCK/ESCALATE into CLEAR,
and it cannot mint a reference governance did not produce.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence, Tuple

from ..runtime.errors import ExecutionStateError

# Version of the canonical execution-state schema. Bump on any change to the set or
# meaning of identity-bearing fields so digests are never silently reinterpreted.
STATE_VERSION = "1"
# The versions this build can construct/verify. An unsupported version fails closed
# rather than being silently reinterpreted under the current schema's field meanings.
SUPPORTED_STATE_VERSIONS = frozenset({STATE_VERSION})


def _ref(value: Any, name: str) -> Optional[str]:
    """Validate an optional single reference: a string or None. Any other type is an
    identity-bearing value the runtime will not canonicalize by ``repr()`` — fail closed."""
    if value is None or isinstance(value, str):
        return value
    raise ExecutionStateError(
        f"{name} must be a string reference or None, got {type(value).__name__}"
    )


def _freeze_refs(values: Any, name: str) -> Tuple[str, ...]:
    """Copy a sequence of string references into an immutable tuple, so later mutation
    of the caller's list cannot alter canonical identity. Rejects non-string members."""
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise ExecutionStateError(f"{name} must be a sequence of strings, not a string")
    if not isinstance(values, Sequence):
        raise ExecutionStateError(
            f"{name} must be a sequence of strings, got {type(values).__name__}"
        )
    out = []
    for v in values:
        if not isinstance(v, str):
            raise ExecutionStateError(
                f"{name} entries must be strings, got {type(v).__name__}"
            )
        out.append(v)
    return tuple(out)


def _opt_float(value: Any, name: str) -> Optional[float]:
    if value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutionStateError(
            f"{name} must be a number or None, got {type(value).__name__}"
        )
    if not math.isfinite(value):
        # NaN / Infinity are not deterministically canonicalizable (and JSON has no
        # standard representation) — fail closed rather than admit a non-finite horizon.
        raise ExecutionStateError(f"{name} must be finite, got {value!r}")
    return value


@dataclass(frozen=True)
class ExecutionLineage:
    """Neutral, typed lineage references supplied at workflow/task boundaries.

    This is the *seam* through which optional causation, parent, agent/plan, and
    artifact references reach canonical execution state without smuggling them through
    untyped metadata. Every field is optional and defaults to unavailable — the runtime
    never fabricates provenance. Agent/plan references are *lineage constraints only*:
    carrying an ``assigned_agent_ref`` never causes the runtime to select, re-rank, or
    invent an agent; carrying an ``authority_scope_ref`` never lets the runtime
    reinterpret or broaden authority. Artifact/evidence references are opaque handles to
    externally owned objects; the runtime stores the reference, never the object.
    """

    # Causation / parent lineage.
    causation_id: Optional[str] = None
    parent_workflow_ref: Optional[str] = None
    parent_task_ref: Optional[str] = None
    # Agent / plan lineage (AWC/H16 constraints only; never runtime authorship).
    assigned_agent_ref: Optional[str] = None
    agent_team_plan_ref: Optional[str] = None
    assignment_digest: Optional[str] = None
    authority_scope_ref: Optional[str] = None
    # Data / artifact lineage (references only).
    input_artifact_refs: Tuple[str, ...] = ()
    output_artifact_refs: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "causation_id", _ref(self.causation_id, "causation_id"))
        object.__setattr__(self, "parent_workflow_ref", _ref(self.parent_workflow_ref, "parent_workflow_ref"))
        object.__setattr__(self, "parent_task_ref", _ref(self.parent_task_ref, "parent_task_ref"))
        object.__setattr__(self, "assigned_agent_ref", _ref(self.assigned_agent_ref, "assigned_agent_ref"))
        object.__setattr__(self, "agent_team_plan_ref", _ref(self.agent_team_plan_ref, "agent_team_plan_ref"))
        object.__setattr__(self, "assignment_digest", _ref(self.assignment_digest, "assignment_digest"))
        object.__setattr__(self, "authority_scope_ref", _ref(self.authority_scope_ref, "authority_scope_ref"))
        object.__setattr__(self, "input_artifact_refs", _freeze_refs(self.input_artifact_refs, "input_artifact_refs"))
        object.__setattr__(self, "output_artifact_refs", _freeze_refs(self.output_artifact_refs, "output_artifact_refs"))
        object.__setattr__(self, "evidence_refs", _freeze_refs(self.evidence_refs, "evidence_refs"))

    def overlay(self, other: Optional["ExecutionLineage"]) -> "ExecutionLineage":
        """Return a lineage where ``other``'s *set* fields take precedence over this one.

        Used to combine workflow-common lineage (this) with task-specific lineage
        (``other``): a scalar field on ``other`` wins when it is not ``None``; a sequence
        field wins when it is non-empty. This lets sibling tasks carry different agents,
        artifacts, and causation while still inheriting workflow-common references (e.g. a
        shared team plan or parent workflow). ``None`` leaves this lineage unchanged."""
        if other is None:
            return self

        def s(a, b):  # scalar override
            return b if b is not None else a

        def q(a, b):  # sequence override
            return b if b else a

        return ExecutionLineage(
            causation_id=s(self.causation_id, other.causation_id),
            parent_workflow_ref=s(self.parent_workflow_ref, other.parent_workflow_ref),
            parent_task_ref=s(self.parent_task_ref, other.parent_task_ref),
            assigned_agent_ref=s(self.assigned_agent_ref, other.assigned_agent_ref),
            agent_team_plan_ref=s(self.agent_team_plan_ref, other.agent_team_plan_ref),
            assignment_digest=s(self.assignment_digest, other.assignment_digest),
            authority_scope_ref=s(self.authority_scope_ref, other.authority_scope_ref),
            input_artifact_refs=q(self.input_artifact_refs, other.input_artifact_refs),
            output_artifact_refs=q(self.output_artifact_refs, other.output_artifact_refs),
            evidence_refs=q(self.evidence_refs, other.evidence_refs),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "causation_id": self.causation_id,
            "parent_workflow_ref": self.parent_workflow_ref,
            "parent_task_ref": self.parent_task_ref,
            "assigned_agent_ref": self.assigned_agent_ref,
            "agent_team_plan_ref": self.agent_team_plan_ref,
            "assignment_digest": self.assignment_digest,
            "authority_scope_ref": self.authority_scope_ref,
            "input_artifact_refs": list(self.input_artifact_refs),
            "output_artifact_refs": list(self.output_artifact_refs),
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionLineage":
        return cls(
            causation_id=d.get("causation_id"),
            parent_workflow_ref=d.get("parent_workflow_ref"),
            parent_task_ref=d.get("parent_task_ref"),
            assigned_agent_ref=d.get("assigned_agent_ref"),
            agent_team_plan_ref=d.get("agent_team_plan_ref"),
            assignment_digest=d.get("assignment_digest"),
            authority_scope_ref=d.get("authority_scope_ref"),
            input_artifact_refs=tuple(d.get("input_artifact_refs", ())),
            output_artifact_refs=tuple(d.get("output_artifact_refs", ())),
            evidence_refs=tuple(d.get("evidence_refs", ())),
        )


@dataclass(frozen=True)
class CanonicalExecutionState:
    """One deterministic snapshot of a runtime execution trajectory.

    All identity-bearing fields are flat scalars (str/int/float/None) or ordered tuples
    of strings — never nested arbitrary structures — so canonical serialization is a
    single ``json.dumps(..., sort_keys=True)`` with no dependence on the proposal's
    argument canonicalizer. Action identity is referenced through ``proposal_fingerprint``
    (and ``operation``/``idempotency_key``/``proposal_version`` as descriptive echoes),
    never by re-canonicalizing the proposal arguments here.

    Build snapshots through :func:`ugence_agent_runtime.runtime.execution_state.build_execution_state`
    rather than authoring field values directly — the runtime is the primary author of
    execution truth. The dataclass remains constructible (package convention), but a
    hand-authored instance still cannot create authority: dispositions and references are
    inert strings that the governance boundary — not this object — validates.
    """

    # --- IDENTITY ----------------------------------------------------------
    runtime_id: str = ""
    runtime_version: str = ""
    workflow_id: str = ""
    instance_id: str = ""
    task_id: Optional[str] = None
    state_version: str = STATE_VERSION
    # --- CORRELATION / CAUSATION ------------------------------------------
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    parent_workflow_ref: Optional[str] = None
    parent_task_ref: Optional[str] = None
    # --- AGENT / PLAN LINEAGE (references only) ----------------------------
    assigned_agent_ref: Optional[str] = None
    agent_team_plan_ref: Optional[str] = None
    assignment_digest: Optional[str] = None
    authority_scope_ref: Optional[str] = None
    # --- RUNTIME STATE -----------------------------------------------------
    workflow_status: Optional[str] = None
    task_status: Optional[str] = None
    attempt: int = 0
    # --- ACTION IDENTITY (reference to the TransitionProposal; not a second payload) --
    provider_id: Optional[str] = None
    operation: Optional[str] = None
    idempotency_key: Optional[str] = None
    proposal_version: Optional[str] = None
    proposal_fingerprint: Optional[str] = None
    # --- AUTHORITY LINEAGE (references only; never minted by the runtime) --
    governance_disposition: Optional[str] = None
    evaluation_reference: Optional[str] = None
    authorization_reference: Optional[str] = None
    clearance_reference: Optional[str] = None
    valid_until: Optional[float] = None
    # --- DATA / ARTIFACT LINEAGE (references only) -------------------------
    input_artifact_refs: Tuple[str, ...] = ()
    output_artifact_refs: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()
    # --- EXECUTION LINEAGE -------------------------------------------------
    # execution_reference / result_digest are neutral seams for a future Runtime
    # Assurance / receipt consumer; there is no canonical upstream source in the
    # reference engine yet, so they default to unavailable and are never fabricated.
    execution_reference: Optional[str] = None
    result_digest: Optional[str] = None
    # --- INTEGRITY ---------------------------------------------------------
    state_digest: str = ""

    def __post_init__(self) -> None:
        # Validate/normalize identity-bearing fields, failing closed on unsupported
        # types and freezing supplied sequences so external mutation cannot alter identity.
        for name in (
            "runtime_id", "runtime_version", "workflow_id", "instance_id", "task_id",
            "state_version", "correlation_id", "causation_id", "parent_workflow_ref",
            "parent_task_ref", "assigned_agent_ref", "agent_team_plan_ref",
            "assignment_digest", "authority_scope_ref", "workflow_status", "task_status",
            "provider_id", "operation", "idempotency_key", "proposal_version",
            "proposal_fingerprint", "governance_disposition", "evaluation_reference",
            "authorization_reference", "clearance_reference", "execution_reference",
            "result_digest", "state_digest",
        ):
            object.__setattr__(self, name, _ref(getattr(self, name), name))
        # A version this build does not understand must fail closed rather than be
        # digested under the current schema's field meanings.
        if self.state_version not in SUPPORTED_STATE_VERSIONS:
            raise ExecutionStateError(
                f"unsupported state_version {self.state_version!r} "
                f"(supported: {sorted(SUPPORTED_STATE_VERSIONS)})"
            )
        if not isinstance(self.attempt, int) or isinstance(self.attempt, bool):
            raise ExecutionStateError(
                f"attempt must be an int, got {type(self.attempt).__name__}"
            )
        object.__setattr__(self, "valid_until", _opt_float(self.valid_until, "valid_until"))
        object.__setattr__(self, "input_artifact_refs", _freeze_refs(self.input_artifact_refs, "input_artifact_refs"))
        object.__setattr__(self, "output_artifact_refs", _freeze_refs(self.output_artifact_refs, "output_artifact_refs"))
        object.__setattr__(self, "evidence_refs", _freeze_refs(self.evidence_refs, "evidence_refs"))

    # -- canonical representation ------------------------------------------
    def canonical_payload(self) -> Dict[str, Any]:
        """Deterministic, digest-excluded payload. Ordered tuples render as JSON arrays;
        the mapping is serialized with ``sort_keys=True`` so insertion order is
        irrelevant. The ``state_digest`` field is intentionally excluded so the digest
        never covers itself."""
        return {
            "state_version": self.state_version,
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "workflow_id": self.workflow_id,
            "instance_id": self.instance_id,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "parent_workflow_ref": self.parent_workflow_ref,
            "parent_task_ref": self.parent_task_ref,
            "assigned_agent_ref": self.assigned_agent_ref,
            "agent_team_plan_ref": self.agent_team_plan_ref,
            "assignment_digest": self.assignment_digest,
            "authority_scope_ref": self.authority_scope_ref,
            "workflow_status": self.workflow_status,
            "task_status": self.task_status,
            "attempt": self.attempt,
            "provider_id": self.provider_id,
            "operation": self.operation,
            "idempotency_key": self.idempotency_key,
            "proposal_version": self.proposal_version,
            "proposal_fingerprint": self.proposal_fingerprint,
            "governance_disposition": self.governance_disposition,
            "evaluation_reference": self.evaluation_reference,
            "authorization_reference": self.authorization_reference,
            "clearance_reference": self.clearance_reference,
            "valid_until": self.valid_until,
            "input_artifact_refs": list(self.input_artifact_refs),
            "output_artifact_refs": list(self.output_artifact_refs),
            "evidence_refs": list(self.evidence_refs),
            "execution_reference": self.execution_reference,
            "result_digest": self.result_digest,
        }

    def compute_digest(self) -> str:
        # allow_nan=False rejects any non-finite float defensively; construction already
        # guarantees finite values, so this can only trip on a corrupted in-memory object.
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def sealed(self) -> "CanonicalExecutionState":
        """Return a copy whose ``state_digest`` is the computed digest of this state.

        The runtime builder always returns a sealed state, so a persisted or event-
        anchored digest provably corresponds to the snapshot's identity-bearing fields."""
        return dataclasses.replace(self, state_digest=self.compute_digest())

    def is_intact(self) -> bool:
        """True when the stored digest still matches the identity-bearing fields."""
        return bool(self.state_digest) and self.state_digest == self.compute_digest()

    def to_dict(self) -> Dict[str, Any]:
        d = self.canonical_payload()
        d["state_digest"] = self.state_digest
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalExecutionState":
        return cls(
            state_version=d.get("state_version", STATE_VERSION),
            runtime_id=d.get("runtime_id", ""),
            runtime_version=d.get("runtime_version", ""),
            workflow_id=d.get("workflow_id", ""),
            instance_id=d.get("instance_id", ""),
            task_id=d.get("task_id"),
            correlation_id=d.get("correlation_id"),
            causation_id=d.get("causation_id"),
            parent_workflow_ref=d.get("parent_workflow_ref"),
            parent_task_ref=d.get("parent_task_ref"),
            assigned_agent_ref=d.get("assigned_agent_ref"),
            agent_team_plan_ref=d.get("agent_team_plan_ref"),
            assignment_digest=d.get("assignment_digest"),
            authority_scope_ref=d.get("authority_scope_ref"),
            workflow_status=d.get("workflow_status"),
            task_status=d.get("task_status"),
            attempt=int(d.get("attempt", 0)),
            provider_id=d.get("provider_id"),
            operation=d.get("operation"),
            idempotency_key=d.get("idempotency_key"),
            proposal_version=d.get("proposal_version"),
            proposal_fingerprint=d.get("proposal_fingerprint"),
            governance_disposition=d.get("governance_disposition"),
            evaluation_reference=d.get("evaluation_reference"),
            authorization_reference=d.get("authorization_reference"),
            clearance_reference=d.get("clearance_reference"),
            valid_until=d.get("valid_until"),
            input_artifact_refs=tuple(d.get("input_artifact_refs", ())),
            output_artifact_refs=tuple(d.get("output_artifact_refs", ())),
            evidence_refs=tuple(d.get("evidence_refs", ())),
            execution_reference=d.get("execution_reference"),
            result_digest=d.get("result_digest"),
            state_digest=d.get("state_digest", ""),
        )
