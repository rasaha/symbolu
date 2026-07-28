"""
Governed External Actions & Resource State (H20)
================================================

Adds a **safe, durable execution boundary for external side effects** on top of
the H19 human-governed, H18-durable workflow runtime.  The runtime now cleanly
separates five distinct things that were previously conflated:

    propose  →  authorize  →  execute  →  observe  →  commit

An authorized *goal* does not automatically authorize every external side effect
inside it.  **Every external action crosses its own governed execution boundary**:
its intent is recorded, its actor authority and policy (ActionGate) are checked,
resource preconditions are validated immediately before mutation, execution is
duplicate-suppressed by a stable idempotency key, the result is durably recorded
*before* the goal may complete, and an interrupted action whose result was never
durably obtained becomes ``UNKNOWN`` — never silently replayed.

```
Agent proposes external action
  → intent recorded → authority + ActionGate validated
  → resource preconditions checked → idempotency reserved
  → adapter invoked → result durably recorded → workflow continues
```

H20 owns **execution-state control** — lifecycle, preconditions, idempotency,
optimistic concurrency, durable action records, unknown-outcome reconciliation,
and compensation linkage.  It does **not** author policy: the pluggable
:class:`ActionGate` is treated as authoritative for *whether and under what
constraints* an action may proceed.  H20 does not modify H10–H19, the governance
layer, authorization, TAP, tool execution, or the model providers — it composes
on their public APIs and persists its state through H14 memory so H18 checkpoints
and restores it.

> **Scope statement.** H20 adds governed, durable external-action execution with
> resource preconditions, durable duplicate suppression, and unknown-outcome
> reconciliation, behind deterministic in-memory adapters.  It is **not** a
> distributed transaction coordinator, does **not** provide universal
> exactly-once execution across arbitrary external systems, does **not**
> automatically roll back irreversible operations, and is **not** production
> external-system fault tolerance.  Duplicate suppression is durable *within the
> governed runtime and cooperating adapters*.  Real cloud/database integrations,
> distributed locks, and queues are explicitly out of scope; the reference
> adapters are in-memory and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

# --- H14–H19 public types (composed on, never modified) ---
from agentic.agentic_framework.working_memory import WorkingMemory, MemoryWrite
from agentic.agentic_framework.hierarchical_planning import (
    Goal, GoalStatus, MissionPlan,
)
from agentic.agentic_framework.coordination import CapabilityRegistry, AuthorityModel
from agentic.agentic_framework.event_workflows import (
    WorkflowInstance, WorkflowStatus, WaitCondition, WorkflowEvent,
)
from agentic.agentic_framework.workflow_durability import (
    DurableWorkflowEngine, CheckpointStore, canonical_json, digest_of,
)
from agentic.agentic_framework.human_governance import (
    HumanParticipant, ParticipantRegistry,
)

__all__ = [
    "ActionStatus",
    "GateOutcome",
    "ExecutionResultCode",
    "Reversibility",
    "ReconciliationOutcome",
    "ActionFaultPoint",
    "ExternalResourceRef",
    "ResourceSnapshot",
    "CompensationPlan",
    "ExternalActionIntent",
    "ResourceLease",
    "ActionTransition",
    "ActionGateRequest",
    "ActionGateDecision",
    "ActionGate",
    "AllowAllActionGate",
    "RuleBasedActionGate",
    "AdapterResult",
    "ExternalResourceAdapter",
    "InMemoryResourceAdapter",
    "ScriptedResourceAdapter",
    "ActionApproval",
    "ActionAuthorityValidator",
    "ExternalActionRecord",
    "ActionExecutionResult",
    "ActionFaultInjector",
    "ActionReconciler",
    "ExternalActionExecutor",
    "format_action_trace",
]

# Durable memory key prefixes — persisted in H14 memory, checkpointed by H18.
ACTION_KEY_PREFIX = "__action__:"
IDEM_KEY_PREFIX = "__idem__:"


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class ActionStatus:
    """Append-only external-action lifecycle."""

    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    AUTHORIZED = "AUTHORIZED"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"
    COMPENSATED = "COMPENSATED"


#: Statuses from which no further execution of *this* action may occur.
_TERMINAL_ACTION = {ActionStatus.SUCCEEDED, ActionStatus.FAILED, ActionStatus.DENIED,
                    ActionStatus.RECONCILED, ActionStatus.COMPENSATED}


class GateOutcome:
    """Authoritative ActionGate outcomes (policy, not authored by H20)."""

    ALLOW = "ALLOW"
    ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
    DENY = "DENY"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
    REQUIRE_ADDITIONAL_EVIDENCE = "REQUIRE_ADDITIONAL_EVIDENCE"


class ExecutionResultCode:
    ACTION_EXECUTED = "ACTION_EXECUTED"
    DUPLICATE_ACTION_SUPPRESSED = "DUPLICATE_ACTION_SUPPRESSED"
    AUTHORITY_DENIED = "AUTHORITY_DENIED"
    GATE_DENIED = "GATE_DENIED"
    RESOURCE_VERSION_CONFLICT = "RESOURCE_VERSION_CONFLICT"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    REQUIRES_ADDITIONAL_EVIDENCE = "REQUIRES_ADDITIONAL_EVIDENCE"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    APPROVAL_BINDING_VIOLATION = "APPROVAL_BINDING_VIOLATION"
    OPERATION_UNSUPPORTED = "OPERATION_UNSUPPORTED"
    ACTION_ALREADY_RESOLVED = "ACTION_ALREADY_RESOLVED"


class Reversibility:
    REVERSIBLE = "REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    COMPENSATABLE = "COMPENSATABLE"
    UNKNOWN = "UNKNOWN"


class ReconciliationOutcome:
    CONFIRMED_SUCCEEDED = "CONFIRMED_SUCCEEDED"
    CONFIRMED_FAILED = "CONFIRMED_FAILED"
    STILL_UNKNOWN = "STILL_UNKNOWN"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class ActionFaultPoint:
    """Deterministic fault-injection points along the execution protocol."""

    BEFORE_GOVERNANCE = "before_governance"
    AFTER_AUTHORIZATION = "after_authorization"
    AFTER_RESOURCE_READ = "after_resource_read"
    AFTER_IDEMPOTENCY_RESERVATION = "after_idempotency_reservation"
    BEFORE_ADAPTER = "before_adapter"
    AFTER_ADAPTER_BEFORE_RESULT = "after_adapter_before_result"
    AFTER_RESULT_BEFORE_COMMIT = "after_result_before_commit"
    DURING_RESTORE = "during_restore"
    DURING_RECONCILIATION = "during_reconciliation"


# ---------------------------------------------------------------------------
# External resource identity & state
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExternalResourceRef:
    """An immutable, stable reference to an external resource.

    Identity is the ``(provider, tenant_id, namespace, resource_id)`` tuple —
    never a mutable display name — so it survives checkpoint restoration.
    """

    resource_id: str
    resource_type: str = ""
    provider: str = "mock"
    tenant_id: str = "default"
    namespace: str = "default"
    external_version: Optional[str] = None
    attributes: Tuple[Tuple[str, Any], ...] = ()
    sensitivity: str = "normal"
    ownership_scope: str = ""

    @property
    def key(self) -> str:
        """Stable identity key (independent of mutable attributes/version)."""
        return f"{self.provider}/{self.tenant_id}/{self.namespace}/{self.resource_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id, "resource_type": self.resource_type,
            "provider": self.provider, "tenant_id": self.tenant_id, "namespace": self.namespace,
            "external_version": self.external_version, "attributes": [list(a) for a in self.attributes],
            "sensitivity": self.sensitivity, "ownership_scope": self.ownership_scope,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExternalResourceRef":
        return cls(
            resource_id=d["resource_id"], resource_type=d.get("resource_type", ""),
            provider=d.get("provider", "mock"), tenant_id=d.get("tenant_id", "default"),
            namespace=d.get("namespace", "default"), external_version=d.get("external_version"),
            attributes=tuple(tuple(a) for a in d.get("attributes", [])),
            sensitivity=d.get("sensitivity", "normal"), ownership_scope=d.get("ownership_scope", ""),
        )


@dataclass(frozen=True)
class ResourceSnapshot:
    """An observed, immutable point-in-time view of an external resource."""

    resource: ExternalResourceRef
    observed_version: int
    observed_state: Dict[str, Any] = field(default_factory=dict)
    content_digest: str = ""
    observation_timestamp: float = 0.0
    observation_source: str = ""
    provenance: str = ""
    logical_sequence: int = 0

    @staticmethod
    def digest_for(version: int, state: Dict[str, Any]) -> str:
        return digest_of(canonical_json({"version": version, "state": state}))

    def with_digest(self) -> "ResourceSnapshot":
        return ResourceSnapshot(
            resource=self.resource, observed_version=self.observed_version,
            observed_state=self.observed_state,
            content_digest=self.digest_for(self.observed_version, self.observed_state),
            observation_timestamp=self.observation_timestamp,
            observation_source=self.observation_source, provenance=self.provenance,
            logical_sequence=self.logical_sequence,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource": self.resource.to_dict(), "observed_version": self.observed_version,
            "observed_state": dict(self.observed_state), "content_digest": self.content_digest,
            "observation_timestamp": self.observation_timestamp,
            "observation_source": self.observation_source, "provenance": self.provenance,
            "logical_sequence": self.logical_sequence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ResourceSnapshot":
        return cls(
            resource=ExternalResourceRef.from_dict(d["resource"]),
            observed_version=d["observed_version"], observed_state=dict(d.get("observed_state", {})),
            content_digest=d.get("content_digest", ""),
            observation_timestamp=d.get("observation_timestamp", 0.0),
            observation_source=d.get("observation_source", ""), provenance=d.get("provenance", ""),
            logical_sequence=d.get("logical_sequence", 0),
        )


# ---------------------------------------------------------------------------
# Compensation metadata
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CompensationPlan:
    """Describes *how* an action might be compensated — never a rollback promise."""

    original_action_id: str
    compensating_operation: str = ""
    compensating_parameters: Tuple[Tuple[str, Any], ...] = ()
    required_authority: FrozenSet[str] = frozenset()
    required_approval: bool = False
    applicability_conditions: Tuple[str, ...] = ()
    known_limitations: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_action_id": self.original_action_id,
            "compensating_operation": self.compensating_operation,
            "compensating_parameters": [list(p) for p in self.compensating_parameters],
            "required_authority": sorted(self.required_authority),
            "required_approval": self.required_approval,
            "applicability_conditions": list(self.applicability_conditions),
            "known_limitations": list(self.known_limitations),
        }


# ---------------------------------------------------------------------------
# Action intent (immutable proposal)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExternalActionIntent:
    """An immutable *proposal* to perform an external side effect.

    An intent is what the runtime proposes to do — not proof that it was
    authorized or executed.
    """

    action_id: str
    workflow_id: str
    goal_id: str
    proposing_actor: str
    action_type: str
    target_resource: ExternalResourceRef
    operation: str
    parameters: Tuple[Tuple[str, Any], ...] = ()
    expected_resource_version: Optional[int] = None
    preconditions: Tuple[Tuple[str, Any], ...] = ()    # required observed_state key/value pairs
    authority_requirements: FrozenSet[str] = frozenset()
    policy_context: Tuple[Tuple[str, Any], ...] = ()
    approval_references: Tuple[str, ...] = ()
    idempotency_key: str = ""
    reversibility: str = Reversibility.UNKNOWN
    compensation: Optional[CompensationPlan] = None
    created_sequence: int = 0
    # Durable-observation → H13 assumption effects, applied only on success.
    assumption_effects: Tuple[Tuple[str, str], ...] = ()

    def params_dict(self) -> Dict[str, Any]:
        return dict(self.parameters)

    def parameter_digest(self) -> str:
        """Stable digest of the *material* action (binds a human approval)."""
        return digest_of(canonical_json({
            "operation": self.operation,
            "parameters": dict(self.parameters),
            "resource": self.target_resource.key,
            "expected_resource_version": self.expected_resource_version,
        }))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id, "workflow_id": self.workflow_id, "goal_id": self.goal_id,
            "proposing_actor": self.proposing_actor, "action_type": self.action_type,
            "target_resource": self.target_resource.to_dict(), "operation": self.operation,
            "parameters": [list(p) for p in self.parameters],
            "expected_resource_version": self.expected_resource_version,
            "preconditions": [list(p) for p in self.preconditions],
            "authority_requirements": sorted(self.authority_requirements),
            "policy_context": [list(p) for p in self.policy_context],
            "approval_references": list(self.approval_references),
            "idempotency_key": self.idempotency_key, "reversibility": self.reversibility,
            "compensation": self.compensation.to_dict() if self.compensation else None,
            "created_sequence": self.created_sequence,
            "assumption_effects": [list(a) for a in self.assumption_effects],
            "parameter_digest": self.parameter_digest(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExternalActionIntent":
        comp = d.get("compensation")
        return cls(
            action_id=d["action_id"], workflow_id=d["workflow_id"], goal_id=d["goal_id"],
            proposing_actor=d["proposing_actor"], action_type=d.get("action_type", ""),
            target_resource=ExternalResourceRef.from_dict(d["target_resource"]),
            operation=d["operation"], parameters=tuple(tuple(p) for p in d.get("parameters", [])),
            expected_resource_version=d.get("expected_resource_version"),
            preconditions=tuple(tuple(p) for p in d.get("preconditions", [])),
            authority_requirements=frozenset(d.get("authority_requirements", [])),
            policy_context=tuple(tuple(p) for p in d.get("policy_context", [])),
            approval_references=tuple(d.get("approval_references", [])),
            idempotency_key=d.get("idempotency_key", ""), reversibility=d.get("reversibility", Reversibility.UNKNOWN),
            compensation=CompensationPlan(
                original_action_id=comp["original_action_id"],
                compensating_operation=comp.get("compensating_operation", ""),
                compensating_parameters=tuple(tuple(p) for p in comp.get("compensating_parameters", [])),
                required_authority=frozenset(comp.get("required_authority", [])),
                required_approval=comp.get("required_approval", False),
                applicability_conditions=tuple(comp.get("applicability_conditions", [])),
                known_limitations=tuple(comp.get("known_limitations", [])),
            ) if comp else None,
            created_sequence=d.get("created_sequence", 0),
            assumption_effects=tuple(tuple(a) for a in d.get("assumption_effects", [])),
        )


# ---------------------------------------------------------------------------
# Execution lease (coordination metadata, NOT a distributed lock)
# ---------------------------------------------------------------------------
@dataclass
class ResourceLease:
    lease_id: str
    resource_id: str
    workflow_id: str
    action_id: str
    issued_at: float = 0.0
    expires_at: float = 0.0
    status: str = "ACTIVE"    # ACTIVE | RELEASED | EXPIRED

    def is_active(self, now: float) -> bool:
        return self.status == "ACTIVE" and now < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {"lease_id": self.lease_id, "resource_id": self.resource_id,
                "workflow_id": self.workflow_id, "action_id": self.action_id,
                "issued_at": self.issued_at, "expires_at": self.expires_at, "status": self.status}


# ---------------------------------------------------------------------------
# Append-only lifecycle transition
# ---------------------------------------------------------------------------
@dataclass
class ActionTransition:
    from_status: str
    to_status: str
    reason: str = ""
    timestamp: float = 0.0
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"from_status": self.from_status, "to_status": self.to_status,
                "reason": self.reason, "timestamp": self.timestamp, "sequence": self.sequence}


# ---------------------------------------------------------------------------
# ActionGate boundary (policy — authoritative, not authored by H20)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ActionGateRequest:
    actor: str
    operation: str
    resource: ExternalResourceRef
    parameters: Dict[str, Any]
    sensitivity: str
    workflow_context: Dict[str, Any]
    policy_context: Dict[str, Any]
    approval_evidence: Tuple[str, ...]
    current_state: Dict[str, Any]
    parameter_digest: str


@dataclass(frozen=True)
class ActionGateDecision:
    outcome: str
    reason: str = ""
    constraints: Tuple[Tuple[str, Any], ...] = ()
    evidence_required: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {"outcome": self.outcome, "reason": self.reason,
                "constraints": [list(c) for c in self.constraints],
                "evidence_required": list(self.evidence_required)}


class ActionGate:
    """Strategy interface for the authoritative external-execution policy gate.

    H20 treats the gate's decision as authoritative for *whether and under what
    constraints* an action may proceed.  H20 does not author policy — supply a
    real governance-backed gate in production; the reference gates below are
    deterministic test/example adapters.
    """

    def evaluate(self, request: ActionGateRequest) -> ActionGateDecision:  # pragma: no cover - interface
        raise NotImplementedError


class AllowAllActionGate(ActionGate):
    """A gate that allows everything — for examples and permissive tests only."""

    def evaluate(self, request: ActionGateRequest) -> ActionGateDecision:
        return ActionGateDecision(GateOutcome.ALLOW)


class RuleBasedActionGate(ActionGate):
    """A deterministic reference gate driven by explicit rule sets.

    Evaluation order is fixed so outcomes are reproducible: deny → review →
    evidence → constraints → allow.  Human review is satisfied by supplying the
    named ``review_evidence`` token in the request's ``approval_evidence``.
    """

    def __init__(self, *, deny_operations: FrozenSet[str] = frozenset(),
                 review_operations: FrozenSet[str] = frozenset(),
                 review_sensitivities: FrozenSet[str] = frozenset(),
                 evidence_operations: FrozenSet[str] = frozenset(),
                 constrained_operations: Optional[Dict[str, Dict[str, Any]]] = None,
                 review_evidence: str = "human_approval") -> None:
        self.deny_operations = deny_operations
        self.review_operations = review_operations
        self.review_sensitivities = review_sensitivities
        self.evidence_operations = evidence_operations
        self.constrained_operations = constrained_operations or {}
        self.review_evidence = review_evidence

    def evaluate(self, request: ActionGateRequest) -> ActionGateDecision:
        if request.operation in self.deny_operations:
            return ActionGateDecision(GateOutcome.DENY, reason=f"operation '{request.operation}' denied by policy")
        needs_review = (request.operation in self.review_operations
                        or request.sensitivity in self.review_sensitivities)
        if needs_review and self.review_evidence not in request.approval_evidence:
            return ActionGateDecision(GateOutcome.REQUIRE_HUMAN_REVIEW,
                                      reason="human review required",
                                      evidence_required=(self.review_evidence,))
        if request.operation in self.evidence_operations and not request.approval_evidence:
            return ActionGateDecision(GateOutcome.REQUIRE_ADDITIONAL_EVIDENCE,
                                      reason="additional evidence required")
        if request.operation in self.constrained_operations:
            return ActionGateDecision(GateOutcome.ALLOW_WITH_CONSTRAINTS,
                                      reason="allowed with constraints",
                                      constraints=tuple(self.constrained_operations[request.operation].items()))
        return ActionGateDecision(GateOutcome.ALLOW)


# ---------------------------------------------------------------------------
# External resource adapter contract + reference adapters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AdapterResult:
    """Structured adapter outcome — never a raw provider response or exception."""

    success: bool
    status: str                       # "SUCCEEDED" | "FAILED"
    external_request_ref: str = ""
    external_result_ref: str = ""
    result_payload: Dict[str, Any] = field(default_factory=dict)
    new_version: Optional[int] = None
    post_state: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"success": self.success, "status": self.status,
                "external_request_ref": self.external_request_ref,
                "external_result_ref": self.external_result_ref,
                "result_payload": dict(self.result_payload), "new_version": self.new_version,
                "post_state": dict(self.post_state), "error": self.error}


class ExternalResourceAdapter:
    """Strategy interface for a provider that owns external resource state."""

    def read(self, ref: ExternalResourceRef, *, timestamp: float = 0.0) -> ResourceSnapshot:  # pragma: no cover
        raise NotImplementedError

    def supports(self, operation: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def execute(self, intent: ExternalActionIntent, *, timestamp: float = 0.0) -> AdapterResult:  # pragma: no cover
        raise NotImplementedError

    def query_status(self, idempotency_key: str) -> Optional[AdapterResult]:  # pragma: no cover - interface
        raise NotImplementedError

    def reconcile(self, idempotency_key: str) -> Optional[AdapterResult]:  # pragma: no cover - interface
        raise NotImplementedError

    def describe_compensation(self, operation: str) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryResourceAdapter(ExternalResourceAdapter):
    """Deterministic in-memory resource store with optimistic versioning.

    Applies ``set:<field>`` and ``delete:<field>`` operations plus a generic
    operation that merges ``parameters`` into state and bumps the version.
    Records each executed idempotency key so it can answer status/reconcile.
    """

    def __init__(self, initial: Optional[Dict[str, Tuple[int, Dict[str, Any]]]] = None,
                 *, supported: Optional[FrozenSet[str]] = None) -> None:
        # key -> (version, state)
        self._state: Dict[str, Tuple[int, Dict[str, Any]]] = dict(initial or {})
        self._supported = supported
        self._executed: Dict[str, AdapterResult] = {}   # idempotency_key -> result

    def seed(self, ref: ExternalResourceRef, version: int, state: Dict[str, Any]) -> None:
        self._state[ref.key] = (version, dict(state))

    def read(self, ref: ExternalResourceRef, *, timestamp: float = 0.0) -> ResourceSnapshot:
        version, state = self._state.get(ref.key, (0, {}))
        return ResourceSnapshot(resource=ref, observed_version=version, observed_state=dict(state),
                                observation_timestamp=timestamp, observation_source="in_memory_adapter",
                                provenance="adapter_read").with_digest()

    def supports(self, operation: str) -> bool:
        return self._supported is None or operation in self._supported

    def execute(self, intent: ExternalActionIntent, *, timestamp: float = 0.0) -> AdapterResult:
        if intent.idempotency_key in self._executed:
            # Adapter-side idempotency: return the prior result, no re-mutation.
            return self._executed[intent.idempotency_key]
        version, state = self._state.get(intent.target_resource.key, (0, {}))
        new_state = dict(state)
        op = intent.operation
        params = intent.params_dict()
        if op.startswith("set:"):
            new_state[op.split(":", 1)[1]] = params.get("value")
        elif op.startswith("delete:"):
            new_state.pop(op.split(":", 1)[1], None)
        else:
            new_state.update(params)
        new_version = version + 1
        self._state[intent.target_resource.key] = (new_version, new_state)
        result = AdapterResult(
            success=True, status="SUCCEEDED",
            external_request_ref=f"req:{intent.idempotency_key}",
            external_result_ref=f"res:{intent.target_resource.key}#{new_version}",
            result_payload={"operation": op}, new_version=new_version, post_state=new_state)
        self._executed[intent.idempotency_key] = result
        return result

    def query_status(self, idempotency_key: str) -> Optional[AdapterResult]:
        return self._executed.get(idempotency_key)

    def reconcile(self, idempotency_key: str) -> Optional[AdapterResult]:
        return self._executed.get(idempotency_key)

    def describe_compensation(self, operation: str) -> Dict[str, Any]:
        # set: is compensatable (restore prior value); delete: is not (value lost).
        if operation.startswith("set:"):
            return {"compensatable": True, "strategy": "restore_prior_value"}
        return {"compensatable": False, "strategy": None}


class ScriptedResourceAdapter(ExternalResourceAdapter):
    """A fully-scripted adapter for deterministic tests.

    ``script`` maps an ``action_id`` to an :class:`AdapterResult` (or a callable
    returning one).  ``reconcile_script`` maps an idempotency key to the
    evidence a later reconciliation would find.  Nothing is inferred — every
    outcome is explicit.
    """

    def __init__(self, *, resources: Optional[Dict[str, Tuple[int, Dict[str, Any]]]] = None,
                 script: Optional[Dict[str, Any]] = None,
                 reconcile_script: Optional[Dict[str, AdapterResult]] = None,
                 supported: Optional[FrozenSet[str]] = None) -> None:
        self._resources: Dict[str, Tuple[int, Dict[str, Any]]] = dict(resources or {})
        self._script = script or {}
        self._reconcile = reconcile_script or {}
        self._supported = supported
        self._executed: Dict[str, AdapterResult] = {}

    def set_resource(self, ref: ExternalResourceRef, version: int, state: Dict[str, Any]) -> None:
        self._resources[ref.key] = (version, dict(state))

    def read(self, ref: ExternalResourceRef, *, timestamp: float = 0.0) -> ResourceSnapshot:
        version, state = self._resources.get(ref.key, (0, {}))
        return ResourceSnapshot(resource=ref, observed_version=version, observed_state=dict(state),
                                observation_timestamp=timestamp, observation_source="scripted_adapter",
                                provenance="adapter_read").with_digest()

    def supports(self, operation: str) -> bool:
        return self._supported is None or operation in self._supported

    def execute(self, intent: ExternalActionIntent, *, timestamp: float = 0.0) -> AdapterResult:
        if intent.idempotency_key in self._executed:
            return self._executed[intent.idempotency_key]
        entry = self._script.get(intent.action_id)
        if entry is None:
            result = AdapterResult(success=True, status="SUCCEEDED",
                                   external_request_ref=f"req:{intent.idempotency_key}",
                                   external_result_ref=f"res:{intent.action_id}",
                                   new_version=(self._resources.get(intent.target_resource.key, (0, {}))[0] + 1))
        else:
            result = entry(intent) if callable(entry) else entry
        if result.success:
            self._executed[intent.idempotency_key] = result
        return result

    def query_status(self, idempotency_key: str) -> Optional[AdapterResult]:
        return self._executed.get(idempotency_key) or self._reconcile.get(idempotency_key)

    def reconcile(self, idempotency_key: str) -> Optional[AdapterResult]:
        # Reconciliation surfaces *external evidence* only — an internally
        # cached execute() result is not proof the external system committed.
        return self._reconcile.get(idempotency_key)

    def describe_compensation(self, operation: str) -> Dict[str, Any]:
        return {"compensatable": False, "strategy": None}


# ---------------------------------------------------------------------------
# Authority & human approval
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ActionApproval:
    """A human approval bound to the exact material action (parameter digest)."""

    approval_id: str
    action_id: str
    parameter_digest: str
    approver: str
    timestamp: float = 0.0
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"approval_id": self.approval_id, "action_id": self.action_id,
                "parameter_digest": self.parameter_digest, "approver": self.approver,
                "timestamp": self.timestamp, "rationale": self.rationale}


@dataclass
class _AuthVerdict:
    ok: bool
    reason: str = ""


class ActionAuthorityValidator:
    """Deterministic actor-execution-authority checks (subset discipline).

    Reuses the H16/H19 subset-check pattern: an actor may execute an action only
    if it holds every token in the intent's ``authority_requirements``.  The
    actor→permissions mapping is a rebindable runtime dependency.
    """

    def __init__(self, actor_permissions: Optional[Dict[str, FrozenSet[str]]] = None) -> None:
        self._perms: Dict[str, FrozenSet[str]] = dict(actor_permissions or {})

    def grant(self, actor: str, permissions: FrozenSet[str]) -> "ActionAuthorityValidator":
        self._perms[actor] = frozenset(permissions)
        return self

    def permissions(self, actor: str) -> FrozenSet[str]:
        return self._perms.get(actor, frozenset())

    def can_execute(self, intent: ExternalActionIntent) -> _AuthVerdict:
        granted = self._perms.get(intent.proposing_actor)
        if granted is None:
            return _AuthVerdict(False, f"unknown actor '{intent.proposing_actor}'")
        missing = intent.authority_requirements - granted
        if missing:
            return _AuthVerdict(False, f"missing authority: {sorted(missing)}")
        return _AuthVerdict(True)


# ---------------------------------------------------------------------------
# Durable action record
# ---------------------------------------------------------------------------
@dataclass
class ExternalActionRecord:
    """The durable, append-only record of one external action's whole lifecycle."""

    intent: ExternalActionIntent
    lifecycle_history: List[ActionTransition] = field(default_factory=list)
    gate_decision: Optional[Dict[str, Any]] = None
    approval_references: List[str] = field(default_factory=list)
    pre_snapshot: Optional[Dict[str, Any]] = None
    adapter_invocation_ref: str = ""
    post_snapshot: Optional[Dict[str, Any]] = None
    result_payload: Optional[Dict[str, Any]] = None
    error_info: str = ""
    idempotency_status: str = ""
    reconciliation_status: str = ""
    compensation_references: List[str] = field(default_factory=list)
    logical_sequences: List[int] = field(default_factory=list)
    integrity_digest: str = ""
    _seq: int = 0

    @property
    def status(self) -> str:
        return self.lifecycle_history[-1].to_status if self.lifecycle_history else "NEW"

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_ACTION

    def transition(self, to_status: str, *, reason: str = "", timestamp: float = 0.0) -> None:
        frm = self.status
        self.lifecycle_history.append(ActionTransition(frm, to_status, reason, timestamp, self._seq))
        self._seq += 1

    def compute_digest(self) -> str:
        return digest_of(canonical_json({
            "intent": self.intent.to_dict(),
            "history": [t.to_dict() for t in self.lifecycle_history],
            "gate_decision": self.gate_decision, "result_payload": self.result_payload,
            "idempotency_status": self.idempotency_status,
            "reconciliation_status": self.reconciliation_status,
            "compensation_references": list(self.compensation_references),
        }))

    def seal(self) -> "ExternalActionRecord":
        self.integrity_digest = self.compute_digest()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "lifecycle_history": [t.to_dict() for t in self.lifecycle_history],
            "gate_decision": self.gate_decision, "approval_references": list(self.approval_references),
            "pre_snapshot": self.pre_snapshot, "adapter_invocation_ref": self.adapter_invocation_ref,
            "post_snapshot": self.post_snapshot, "result_payload": self.result_payload,
            "error_info": self.error_info, "idempotency_status": self.idempotency_status,
            "reconciliation_status": self.reconciliation_status,
            "compensation_references": list(self.compensation_references),
            "logical_sequences": list(self.logical_sequences), "integrity_digest": self.integrity_digest,
            "seq": self._seq,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExternalActionRecord":
        rec = cls(
            intent=ExternalActionIntent.from_dict(d["intent"]),
            lifecycle_history=[ActionTransition(t["from_status"], t["to_status"], t.get("reason", ""),
                                                t.get("timestamp", 0.0), t.get("sequence", 0))
                               for t in d.get("lifecycle_history", [])],
            gate_decision=d.get("gate_decision"), approval_references=list(d.get("approval_references", [])),
            pre_snapshot=d.get("pre_snapshot"), adapter_invocation_ref=d.get("adapter_invocation_ref", ""),
            post_snapshot=d.get("post_snapshot"), result_payload=d.get("result_payload"),
            error_info=d.get("error_info", ""), idempotency_status=d.get("idempotency_status", ""),
            reconciliation_status=d.get("reconciliation_status", ""),
            compensation_references=list(d.get("compensation_references", [])),
            logical_sequences=list(d.get("logical_sequences", [])),
            integrity_digest=d.get("integrity_digest", ""),
        )
        rec._seq = d.get("seq", len(rec.lifecycle_history))
        return rec


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------
@dataclass
class ActionExecutionResult:
    code: str
    action_id: str
    record: Optional[ExternalActionRecord] = None
    reason: str = ""
    snapshot: Optional[ResourceSnapshot] = None
    gate_decision: Optional[ActionGateDecision] = None
    event_outcome: Optional[str] = None

    @property
    def executed(self) -> bool:
        return self.code == ExecutionResultCode.ACTION_EXECUTED


# ---------------------------------------------------------------------------
# Fault injection (deterministic, for tests)
# ---------------------------------------------------------------------------
class ActionFaultInjector:
    """Arms a single deterministic fault at a named :class:`ActionFaultPoint`."""

    class InjectedFault(Exception):
        pass

    def __init__(self, point: Optional[str] = None) -> None:
        self.point = point
        self.fired = False

    def check(self, point: str) -> None:
        if self.point == point and not self.fired:
            self.fired = True
            raise ActionFaultInjector.InjectedFault(point)


# ---------------------------------------------------------------------------
# Reconciler
# ---------------------------------------------------------------------------
@dataclass
class ReconciliationResult:
    outcome: str
    action_id: str
    record: Optional[ExternalActionRecord] = None
    detail: str = ""
    event_outcome: Optional[str] = None


class ActionReconciler:
    """Resolves ``UNKNOWN`` actions using durable external evidence.

    Never repeats a non-idempotent action.  A reconciliation may confirm success
    (the workflow continues without re-executing), confirm failure (only the
    affected subtree follows failure behaviour), remain unknown, or require
    manual review.
    """

    def __init__(self, executor: "ExternalActionExecutor") -> None:
        self.executor = executor

    def reconcile(self, wf: WorkflowInstance, action_id: str, *, timestamp: float = 0.0,
                  fault: Optional[ActionFaultInjector] = None) -> ReconciliationResult:
        rec = self.executor._load_record(wf, action_id)
        if rec is None:
            return ReconciliationResult(ReconciliationOutcome.MANUAL_REVIEW_REQUIRED, action_id,
                                        detail="no such action")
        if rec.status != ActionStatus.UNKNOWN:
            return ReconciliationResult(ReconciliationOutcome.MANUAL_REVIEW_REQUIRED, action_id, record=rec,
                                        detail=f"action not UNKNOWN (status={rec.status})")
        if fault:
            fault.check(ActionFaultPoint.DURING_RECONCILIATION)
        adapter = self.executor._adapter_for(rec.intent.target_resource)
        evidence = adapter.reconcile(rec.intent.idempotency_key)
        if evidence is None:
            rec.reconciliation_status = ReconciliationOutcome.STILL_UNKNOWN
            self.executor._persist_record(wf, rec, timestamp=timestamp)
            self.executor.durable.checkpoint(wf, reason="reconcile_still_unknown")
            return ReconciliationResult(ReconciliationOutcome.STILL_UNKNOWN, action_id, record=rec)

        if evidence.success:
            rec.reconciliation_status = ReconciliationOutcome.CONFIRMED_SUCCEEDED
            rec.result_payload = evidence.to_dict()
            rec.adapter_invocation_ref = evidence.external_request_ref
            rec.transition(ActionStatus.RECONCILED, reason="confirmed succeeded", timestamp=timestamp)
            self.executor._mark_idem(wf, rec.intent, "EXECUTED", evidence, timestamp=timestamp)
            self.executor._persist_record(wf, rec, timestamp=timestamp)
            outcome = self.executor._commit_success(wf, rec, evidence, timestamp=timestamp)
            return ReconciliationResult(ReconciliationOutcome.CONFIRMED_SUCCEEDED, action_id, record=rec,
                                        event_outcome=outcome)

        rec.reconciliation_status = ReconciliationOutcome.CONFIRMED_FAILED
        rec.error_info = evidence.error or "confirmed failed"
        rec.transition(ActionStatus.RECONCILED, reason="confirmed failed", timestamp=timestamp)
        self.executor._persist_record(wf, rec, timestamp=timestamp)
        self.executor._commit_failure(wf, rec, timestamp=timestamp)
        return ReconciliationResult(ReconciliationOutcome.CONFIRMED_FAILED, action_id, record=rec)


# ---------------------------------------------------------------------------
# The governed external-action executor
# ---------------------------------------------------------------------------
class ExternalActionExecutor:
    """Governs external side effects on top of the unchanged H18 durable engine.

    Enforces a deterministic execution protocol: authority → ActionGate →
    resource preconditions → idempotency reservation → adapter → durable result
    → workflow resume.  No adapter call occurs before governance, authority,
    approval, precondition, and idempotency checks complete.  Action records and
    idempotency state are stored in H14 ``WorkingMemory`` so H18 checkpoints and
    restores them.
    """

    def __init__(self, registry: CapabilityRegistry, store: CheckpointStore, gate: ActionGate, *,
                 adapters: Optional[Dict[str, ExternalResourceAdapter]] = None,
                 default_adapter: Optional[ExternalResourceAdapter] = None,
                 authority_validator: Optional[ActionAuthorityValidator] = None,
                 participants: Optional[ParticipantRegistry] = None,
                 coordination_authority: Optional[AuthorityModel] = None,
                 fault: Optional[ActionFaultInjector] = None) -> None:
        self.gate = gate
        self.adapters: Dict[str, ExternalResourceAdapter] = dict(adapters or {})
        self.default_adapter = default_adapter
        self.authority = authority_validator or ActionAuthorityValidator()
        self.participants = participants or ParticipantRegistry()
        self.fault = fault
        self.durable = DurableWorkflowEngine(registry, store, authority=coordination_authority)
        self.reconciler = ActionReconciler(self)
        self._records: Dict[str, ExternalActionRecord] = {}
        self._logical = 0

    # ----- workflow creation passthrough -----
    def create_workflow(self, workflow_id: str, plan: MissionPlan, memory: WorkingMemory, *,
                        assumption_context: Optional[Any] = None, run_budget: Optional[Any] = None,
                        wait_conditions: Optional[List[WaitCondition]] = None,
                        created_at: float = 0.0) -> WorkflowInstance:
        return self.durable.create_workflow(
            workflow_id, plan, memory, assumption_context=assumption_context, run_budget=run_budget,
            wait_conditions=wait_conditions, created_at=created_at)

    def _adapter_for(self, ref: ExternalResourceRef) -> ExternalResourceAdapter:
        adapter = self.adapters.get(ref.provider, self.default_adapter)
        if adapter is None:
            raise KeyError(f"no adapter for provider '{ref.provider}'")
        return adapter

    # ----- main pipeline -----
    def execute(self, wf: WorkflowInstance, intent: ExternalActionIntent, *,
                timestamp: float = 0.0) -> ActionExecutionResult:
        rec = self._load_record(wf, intent.action_id)
        if rec is not None and rec.is_terminal():
            # Re-submitting the same, already-resolved action is a duplicate.
            code = (ExecutionResultCode.DUPLICATE_ACTION_SUPPRESSED
                    if rec.status in (ActionStatus.SUCCEEDED, ActionStatus.RECONCILED)
                    else ExecutionResultCode.ACTION_ALREADY_RESOLVED)
            return ActionExecutionResult(code, intent.action_id, record=rec, reason=f"status={rec.status}")
        if rec is not None and rec.status == ActionStatus.UNKNOWN:
            # An interrupted action of unknown outcome is never auto-replayed;
            # it must be resolved by reconciliation first.
            return ActionExecutionResult(ExecutionResultCode.UNKNOWN_OUTCOME, intent.action_id, record=rec,
                                         reason="action is UNKNOWN; requires reconciliation before retry")
        if rec is None:
            rec = ExternalActionRecord(intent=intent)
            rec.transition(ActionStatus.PROPOSED, reason="proposed", timestamp=timestamp)
            self._persist_record(wf, rec, timestamp=timestamp)

        if self.fault:
            self.fault.check(ActionFaultPoint.BEFORE_GOVERNANCE)

        # 1) schema / adapter support
        adapter = self._adapter_for(intent.target_resource)
        if not adapter.supports(intent.operation):
            return self._deny(wf, rec, ExecutionResultCode.OPERATION_UNSUPPORTED,
                              f"operation '{intent.operation}' unsupported", timestamp)

        # 2) actor execution authority (subset check) — BEFORE any state change
        rec.transition(ActionStatus.VALIDATING, reason="validating", timestamp=timestamp)
        verdict = self.authority.can_execute(intent)
        if not verdict.ok:
            return self._deny(wf, rec, ExecutionResultCode.AUTHORITY_DENIED, verdict.reason, timestamp)

        # 3) approval binding: an approval only counts for the exact parameter set
        approval = self._load_approval(wf, intent.action_id)
        approval_evidence: Tuple[str, ...] = ()
        if approval is not None:
            if approval.parameter_digest != intent.parameter_digest():
                return self._deny(wf, rec, ExecutionResultCode.APPROVAL_BINDING_VIOLATION,
                                  "approval does not match current action parameters", timestamp)
            approval_evidence = ("human_approval",) + tuple(intent.approval_references)
            if approval.approval_id not in rec.approval_references:
                rec.approval_references.append(approval.approval_id)
        else:
            approval_evidence = tuple(intent.approval_references)

        # 4) ActionGate (authoritative policy)
        snapshot = adapter.read(intent.target_resource, timestamp=timestamp)
        gate_req = ActionGateRequest(
            actor=intent.proposing_actor, operation=intent.operation, resource=intent.target_resource,
            parameters=intent.params_dict(), sensitivity=intent.target_resource.sensitivity,
            workflow_context={"workflow_id": wf.workflow_id, "goal_id": intent.goal_id},
            policy_context=dict(intent.policy_context), approval_evidence=approval_evidence,
            current_state=dict(snapshot.observed_state), parameter_digest=intent.parameter_digest())
        decision = self.gate.evaluate(gate_req)
        rec.gate_decision = decision.to_dict()
        if decision.outcome == GateOutcome.DENY:
            return self._deny(wf, rec, ExecutionResultCode.GATE_DENIED, decision.reason, timestamp,
                              gate_decision=decision)
        if decision.outcome == GateOutcome.REQUIRE_HUMAN_REVIEW:
            rec.idempotency_status = "AWAITING_HUMAN_REVIEW"
            self._persist_record(wf, rec, timestamp=timestamp)
            self.durable.checkpoint(wf, reason="action_requires_human_review")
            return ActionExecutionResult(ExecutionResultCode.REQUIRES_HUMAN_REVIEW, intent.action_id,
                                         record=rec, reason=decision.reason, gate_decision=decision)
        if decision.outcome == GateOutcome.REQUIRE_ADDITIONAL_EVIDENCE:
            self._persist_record(wf, rec, timestamp=timestamp)
            self.durable.checkpoint(wf, reason="action_requires_evidence")
            return ActionExecutionResult(ExecutionResultCode.REQUIRES_ADDITIONAL_EVIDENCE, intent.action_id,
                                         record=rec, reason=decision.reason, gate_decision=decision)

        if self.fault:
            self.fault.check(ActionFaultPoint.AFTER_AUTHORIZATION)
        rec.transition(ActionStatus.AUTHORIZED, reason=f"gate={decision.outcome}", timestamp=timestamp)

        # 5) resource read + precondition/version checks (immediately pre-mutation)
        rec.pre_snapshot = snapshot.to_dict()
        if self.fault:
            self.fault.check(ActionFaultPoint.AFTER_RESOURCE_READ)
        if intent.expected_resource_version is not None and \
                snapshot.observed_version != intent.expected_resource_version:
            return self._conflict(wf, rec, ExecutionResultCode.RESOURCE_VERSION_CONFLICT,
                                  f"expected version {intent.expected_resource_version}, "
                                  f"observed {snapshot.observed_version}", timestamp)
        for pk, pv in intent.preconditions:
            if snapshot.observed_state.get(pk) != pv:
                return self._conflict(wf, rec, ExecutionResultCode.PRECONDITION_FAILED,
                                      f"precondition '{pk}'={pv!r} not met", timestamp)

        # 6) idempotency reservation (durable) — a duplicate key never re-invokes
        idem = self._load_idem(wf, intent.idempotency_key)
        if idem is not None and idem.get("status") == "EXECUTED" and idem.get("action_id") != intent.action_id:
            rec.idempotency_status = "DUPLICATE_SUPPRESSED"
            rec.transition(ActionStatus.SUCCEEDED, reason="duplicate suppressed (prior execution)",
                           timestamp=timestamp)
            self._persist_record(wf, rec, timestamp=timestamp)
            self.durable.checkpoint(wf, reason="duplicate_suppressed")
            return ActionExecutionResult(ExecutionResultCode.DUPLICATE_ACTION_SUPPRESSED, intent.action_id,
                                         record=rec, reason="idempotency key already executed")

        rec.transition(ActionStatus.READY_TO_EXECUTE, reason="preconditions ok", timestamp=timestamp)
        self._mark_idem(wf, intent, "RESERVED", None, timestamp=timestamp)
        rec.idempotency_status = "RESERVED"
        rec.transition(ActionStatus.EXECUTING, reason="reserved + executing", timestamp=timestamp)
        self._logical += 1
        rec.logical_sequences.append(self._logical)
        self._persist_record(wf, rec, timestamp=timestamp)
        # Durable EXECUTING reservation: if the process dies now, restore→UNKNOWN.
        self.durable.checkpoint(wf, reason="action_reserved_executing")
        if self.fault:
            self.fault.check(ActionFaultPoint.AFTER_IDEMPOTENCY_RESERVATION)

        # 7) adapter invocation (the actual external side effect)
        if self.fault:
            self.fault.check(ActionFaultPoint.BEFORE_ADAPTER)
        result = adapter.execute(intent, timestamp=timestamp)
        rec.adapter_invocation_ref = result.external_request_ref
        try:
            if self.fault:
                # Simulates process/network loss AFTER the external system acted
                # but BEFORE we durably recorded the result → UNKNOWN.
                self.fault.check(ActionFaultPoint.AFTER_ADAPTER_BEFORE_RESULT)
        except ActionFaultInjector.InjectedFault:
            return self._unknown(wf, rec, "interrupted after adapter, before durable result", timestamp)

        # 8) durably record the result BEFORE the goal may complete
        if not result.success:
            rec.error_info = result.error or "adapter reported failure"
            rec.result_payload = result.to_dict()
            self._mark_idem(wf, intent, "FAILED", result, timestamp=timestamp)
            rec.idempotency_status = "FAILED"
            rec.transition(ActionStatus.FAILED, reason=rec.error_info, timestamp=timestamp)
            self._persist_record(wf, rec, timestamp=timestamp)
            self._commit_failure(wf, rec, timestamp=timestamp)
            return ActionExecutionResult(ExecutionResultCode.ACTION_EXECUTED, intent.action_id, record=rec,
                                         reason="action failed", gate_decision=decision)

        rec.result_payload = result.to_dict()
        post = adapter.read(intent.target_resource, timestamp=timestamp)
        rec.post_snapshot = post.to_dict()
        self._mark_idem(wf, intent, "EXECUTED", result, timestamp=timestamp)
        rec.idempotency_status = "EXECUTED"
        rec.transition(ActionStatus.SUCCEEDED, reason="executed", timestamp=timestamp)
        self._persist_record(wf, rec, timestamp=timestamp)
        if self.fault:
            self.fault.check(ActionFaultPoint.AFTER_RESULT_BEFORE_COMMIT)
        outcome = self._commit_success(wf, rec, result, timestamp=timestamp)
        return ActionExecutionResult(ExecutionResultCode.ACTION_EXECUTED, intent.action_id, record=rec,
                                     snapshot=post, gate_decision=decision, event_outcome=outcome)

    # ----- human approval submission (the REQUIRE_HUMAN_REVIEW path) -----
    def submit_action_approval(self, wf: WorkflowInstance, approval: ActionApproval, *,
                               timestamp: float = 0.0) -> ActionExecutionResult:
        """Record a human approval bound to the action, then resume execution.

        The approver's authority is validated with the H19 participant model.
        The approval binds to the action's *current* parameter digest; a
        materially different action cannot reuse it.
        """
        rec = self._load_record(wf, approval.action_id)
        if rec is None:
            return ActionExecutionResult(ExecutionResultCode.ACTION_ALREADY_RESOLVED, approval.action_id,
                                         reason="no such action")
        intent = rec.intent
        participant: Optional[HumanParticipant] = self.participants.get(approval.approver)
        if participant is not None and intent.authority_requirements - participant.permissions:
            return ActionExecutionResult(ExecutionResultCode.AUTHORITY_DENIED, approval.action_id, record=rec,
                                         reason="approver lacks required authority")
        if approval.parameter_digest != intent.parameter_digest():
            return ActionExecutionResult(ExecutionResultCode.APPROVAL_BINDING_VIOLATION, approval.action_id,
                                         record=rec, reason="approval does not match action parameters")
        wf.memory.write(self._approval_key(approval.action_id), approval.to_dict(), category="governance",
                        provenance="action_executor", producing_step="action_executor", timestamp=timestamp)
        return self.execute(wf, intent, timestamp=timestamp)

    # ----- compensation (a NEW governed action linked to the original) -----
    def compensate(self, wf: WorkflowInstance, original_action_id: str,
                   compensation_intent: ExternalActionIntent, *,
                   timestamp: float = 0.0) -> ActionExecutionResult:
        """Run a compensating action as an independent governed action.

        Compensation never rewrites the original history; it links to it.  The
        original transitions to ``COMPENSATED`` only after the compensating
        action succeeds.
        """
        original = self._load_record(wf, original_action_id)
        if original is None:
            return ActionExecutionResult(ExecutionResultCode.ACTION_ALREADY_RESOLVED, original_action_id,
                                         reason="no such original action")
        result = self.execute(wf, compensation_intent, timestamp=timestamp)
        if result.executed and result.record and result.record.status == ActionStatus.SUCCEEDED:
            if compensation_intent.action_id not in original.compensation_references:
                original.compensation_references.append(compensation_intent.action_id)
            original.transition(ActionStatus.COMPENSATED,
                                reason=f"compensated by {compensation_intent.action_id}", timestamp=timestamp)
            self._persist_record(wf, original, timestamp=timestamp)
            self.durable.checkpoint(wf, reason="action_compensated")
        return result

    # ----- localized replanning helper (H15/H12) -----
    def replan_action_goal(self, wf: WorkflowInstance, goal_id: str, replacements: List[Goal]) -> List[str]:
        """Replace only the failed/conflicted action leaf's subtree (H15)."""
        return wf.tree.replace_leaf(goal_id, replacements)

    # ----- commit helpers -----
    def _commit_success(self, wf: WorkflowInstance, rec: ExternalActionRecord, result: AdapterResult, *,
                        timestamp: float) -> Optional[str]:
        """Record result into H14 memory and resume the workflow (H18 deliver)."""
        intent = rec.intent
        ref = intent.target_resource
        wc = wf.wait_by_goal.get(intent.goal_id)
        writes = [
            MemoryWrite(f"resource:{ref.key}", (rec.post_snapshot or {}).get("observed_state", {}),
                        category="resource"),
            MemoryWrite(f"action_result:{intent.goal_id}",
                        {"action_id": intent.action_id, "status": rec.status,
                         "external_result_ref": result.external_result_ref}, category="external_action"),
        ]
        event = WorkflowEvent(
            event_id=f"action-committed:{intent.action_id}",
            type=wc.event_type if wc is not None else "external_action_completed",
            payload=dict(wc.match_dict()) if wc is not None else {},
            timestamp=timestamp, source=f"action:{intent.action_id}", confidence=1.0,
            memory_writes=writes, assumption_signals=dict(intent.assumption_effects))
        if wc is None:
            # No gate to resolve — the result is still durably recorded.
            self.durable.checkpoint(wf, reason="action_committed_no_wait")
            return None
        outcome = self.durable.deliver(wf, event)
        return outcome.outcome

    def _commit_failure(self, wf: WorkflowInstance, rec: ExternalActionRecord, *, timestamp: float) -> None:
        """Fail only the action's goal (localized); resolve its wait if any."""
        intent = rec.intent
        node = wf.tree.lookup(intent.goal_id)
        if node.status not in (GoalStatus.FAILED, GoalStatus.ABORTED):
            node.transition(GoalStatus.FAILED, reason=f"external action {rec.status.lower()}",
                            timestamp=timestamp)
        wc = wf.wait_by_goal.get(intent.goal_id)
        if wc is not None:
            event = WorkflowEvent(
                event_id=f"action-failed:{intent.action_id}", type=wc.event_type,
                payload=dict(wc.match_dict()), timestamp=timestamp, source=f"action:{intent.action_id}",
                memory_writes=[MemoryWrite(f"action_result:{intent.goal_id}",
                                           {"action_id": intent.action_id, "status": rec.status},
                                           category="external_action")])
            self.durable.deliver(wf, event)
        else:
            self.durable.checkpoint(wf, reason="action_failed_no_wait")

    # ----- terminal-result helpers -----
    def _deny(self, wf: WorkflowInstance, rec: ExternalActionRecord, code: str, reason: str,
              timestamp: float, *, gate_decision: Optional[ActionGateDecision] = None) -> ActionExecutionResult:
        rec.transition(ActionStatus.DENIED, reason=reason, timestamp=timestamp)
        self._persist_record(wf, rec, timestamp=timestamp)
        self.durable.checkpoint(wf, reason="action_denied")
        return ActionExecutionResult(code, rec.intent.action_id, record=rec, reason=reason,
                                     gate_decision=gate_decision)

    def _conflict(self, wf: WorkflowInstance, rec: ExternalActionRecord, code: str, reason: str,
                  timestamp: float) -> ActionExecutionResult:
        rec.transition(ActionStatus.CONFLICTED, reason=reason, timestamp=timestamp)
        self._persist_record(wf, rec, timestamp=timestamp)
        self.durable.checkpoint(wf, reason="action_conflicted")
        return ActionExecutionResult(code, rec.intent.action_id, record=rec, reason=reason)

    def _unknown(self, wf: WorkflowInstance, rec: ExternalActionRecord, reason: str,
                 timestamp: float) -> ActionExecutionResult:
        rec.idempotency_status = "UNKNOWN"
        rec.error_info = reason
        rec.transition(ActionStatus.UNKNOWN, reason=reason, timestamp=timestamp)
        self._persist_record(wf, rec, timestamp=timestamp)
        # Block the affected subtree; require reconciliation before it proceeds.
        node = wf.tree.lookup(rec.intent.goal_id)
        if node.status not in (GoalStatus.FAILED, GoalStatus.ABORTED, GoalStatus.COMPLETED):
            node.transition(GoalStatus.BLOCKED, reason="REQUIRES_RECONCILIATION", timestamp=timestamp)
        self.durable.checkpoint(wf, reason="action_unknown")
        return ActionExecutionResult(ExecutionResultCode.UNKNOWN_OUTCOME, rec.intent.action_id, record=rec,
                                     reason=reason)

    # ----- durable persistence (H14 memory → H18 checkpoint) -----
    def _record_key(self, action_id: str) -> str:
        return f"{ACTION_KEY_PREFIX}{action_id}"

    def _idem_key(self, idempotency_key: str) -> str:
        return f"{IDEM_KEY_PREFIX}{idempotency_key}"

    def _approval_key(self, action_id: str) -> str:
        return f"__action_approval__:{action_id}"

    def _persist_record(self, wf: WorkflowInstance, rec: ExternalActionRecord, *, timestamp: float) -> None:
        rec.seal()
        wf.memory.write(self._record_key(rec.intent.action_id), rec.to_dict(), category="external_action",
                        provenance="action_executor", producing_step="action_executor", timestamp=timestamp)
        self._records[rec.intent.action_id] = rec

    def _load_record(self, wf: WorkflowInstance, action_id: str) -> Optional[ExternalActionRecord]:
        if action_id in self._records:
            return self._records[action_id]
        item = wf.memory.peek(self._record_key(action_id))
        if item is None:
            return None
        rec = ExternalActionRecord.from_dict(item.value)
        self._records[action_id] = rec
        return rec

    def _mark_idem(self, wf: WorkflowInstance, intent: ExternalActionIntent, status: str,
                   result: Optional[AdapterResult], *, timestamp: float) -> None:
        wf.memory.write(self._idem_key(intent.idempotency_key), {
            "idempotency_key": intent.idempotency_key, "action_id": intent.action_id, "status": status,
            "external_request_ref": result.external_request_ref if result else "",
            "external_result_ref": result.external_result_ref if result else "",
        }, category="idempotency", provenance="action_executor", producing_step="action_executor",
            timestamp=timestamp)

    def _load_idem(self, wf: WorkflowInstance, idempotency_key: str) -> Optional[Dict[str, Any]]:
        item = wf.memory.peek(self._idem_key(idempotency_key))
        return item.value if item is not None else None

    def _load_approval(self, wf: WorkflowInstance, action_id: str) -> Optional[ActionApproval]:
        item = wf.memory.peek(self._approval_key(action_id))
        if item is None:
            return None
        v = item.value
        return ActionApproval(v["approval_id"], v["action_id"], v["parameter_digest"], v["approver"],
                              v.get("timestamp", 0.0), v.get("rationale", ""))

    def records_for(self, wf: WorkflowInstance) -> List[ExternalActionRecord]:
        out = []
        for key in wf.memory.keys():
            if key.startswith(ACTION_KEY_PREFIX):
                item = wf.memory.peek(key)
                if item:
                    out.append(ExternalActionRecord.from_dict(item.value))
        return out

    # ----- recovery -----
    @classmethod
    def restore(cls, store: CheckpointStore, workflow_id: str, *, registry: CapabilityRegistry,
                gate: ActionGate, adapters: Optional[Dict[str, ExternalResourceAdapter]] = None,
                default_adapter: Optional[ExternalResourceAdapter] = None,
                authority_validator: Optional[ActionAuthorityValidator] = None,
                participants: Optional[ParticipantRegistry] = None,
                coordination_authority: Optional[AuthorityModel] = None,
                fault: Optional[ActionFaultInjector] = None
                ) -> Tuple["ExternalActionExecutor", WorkflowInstance]:
        """Restore a workflow AND its external-action records after process loss.

        Any action durably left in ``EXECUTING`` (reserved, no committed result)
        is transitioned to ``UNKNOWN`` and its goal blocked, awaiting
        reconciliation.  It is never auto-replayed.
        """
        executor = cls(registry, store, gate, adapters=adapters, default_adapter=default_adapter,
                       authority_validator=authority_validator, participants=participants,
                       coordination_authority=coordination_authority, fault=fault)
        engine, wf = DurableWorkflowEngine.restore(
            store, workflow_id, registry=registry, authority=coordination_authority)
        executor.durable = engine
        if fault:
            fault.check(ActionFaultPoint.DURING_RESTORE)
        for rec in executor.records_for(wf):
            executor._records[rec.intent.action_id] = rec
            if rec.status == ActionStatus.EXECUTING:
                rec.idempotency_status = "UNKNOWN"
                rec.error_info = "process loss during EXECUTING; result not durably obtained"
                rec.transition(ActionStatus.UNKNOWN, reason="restored from EXECUTING", timestamp=wf.created_at)
                node = wf.tree.lookup(rec.intent.goal_id)
                if node.status not in (GoalStatus.FAILED, GoalStatus.ABORTED, GoalStatus.COMPLETED):
                    node.transition(GoalStatus.BLOCKED, reason="REQUIRES_RECONCILIATION",
                                    timestamp=wf.created_at)
                executor._persist_record(wf, rec, timestamp=wf.created_at)
        return executor, wf


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_action_trace(rec: ExternalActionRecord) -> str:
    """Render a single continuous, reconstructable external-action history."""
    intent = rec.intent
    lines = [
        f"Action {intent.action_id}  status={rec.status}  goal={intent.goal_id}",
        f"actor={intent.proposing_actor}  op={intent.operation}  resource={intent.target_resource.key}",
        f"idempotency_key={intent.idempotency_key}  digest={intent.parameter_digest()[:12]}…",
        "-" * 60,
    ]
    if rec.gate_decision:
        lines.append(f"  gate: {rec.gate_decision.get('outcome')} — {rec.gate_decision.get('reason', '')}")
    for t in rec.lifecycle_history:
        lines.append(f"  {t.from_status} → {t.to_status}"
                     + (f"  ({t.reason})" if t.reason else ""))
    if rec.reconciliation_status:
        lines.append(f"  reconciliation: {rec.reconciliation_status}")
    for cref in rec.compensation_references:
        lines.append(f"  compensated-by: {cref}")
    return "\n".join(lines)
