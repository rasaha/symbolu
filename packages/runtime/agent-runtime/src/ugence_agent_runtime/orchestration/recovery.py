"""H22-C — portfolio checkpoint construction, validation, and side-effect-free recovery.

Three responsibilities live here:

* :func:`build_portfolio_checkpoint` — snapshot the current H22-B portfolio into a durable
  :class:`~.persistence.PortfolioCheckpoint`, referencing each workflow's runtime checkpoint
  **by digest** (never by copy).
* :func:`validate_portfolio_checkpoint` — the single recovery validator. It is run both on
  recovery *and* immediately before any persist (the portfolio self-recoverability
  invariant), so H22-C never writes a checkpoint its own recovery would reject.
* :func:`recover_portfolio` — reconstruct the portfolio, its scheduler fairness/aging state,
  its dependencies, and its failure/cancellation state from a durable checkpoint, binding each
  referenced runtime checkpoint and recovering each workflow through the **existing** Agent
  Runtime recovery contract.

Recovery is strictly reconstruction, never continuation:

    recover_portfolio(...)  performs  provider calls = 0, governance calls = 0,
                                      workflow advancement = 0, automatic resume = 0

A recovered portfolio ``requires_continuation`` — the operator/application must explicitly
choose to step the scheduler before any new execution occurs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..models.workflow import (
    TERMINAL_WORKFLOW_STATUSES,
    WorkflowDefinition,
    WorkflowStatus,
)
from ..runtime.errors import CheckpointError, RecoveryError
from .dependencies import DependencyGraph, DependencyType, WorkflowDependency
from .persistence import (
    SUPPORTED_PORTFOLIO_CHECKPOINT_VERSIONS,
    PortfolioCheckpoint,
    WorkflowCheckpointRef,
)
from .portfolio import (
    TERMINAL_PORTFOLIO_STATUSES,
    PortfolioStatus,
    PortfolioWorkflowEntry,
    WorkflowPortfolio,
    WorkflowPriority,
)
from .tracing import PortfolioEventStore, PortfolioEventType, PortfolioTrace

_PRIORITY_VALUES = frozenset(p.value for p in WorkflowPriority)
_DEP_TYPE_VALUES = frozenset(t.value for t in DependencyType)
_STATUS_VALUES = frozenset(s.value for s in PortfolioStatus)

# The only orchestration failure label the H22-C controller records for an observed failure.
_FAILURE_LABELS = frozenset({"WORKFLOW_FAILED"})


def _failure_policy_values() -> frozenset:
    # Lazy import to avoid a module-load cycle (control imports this module).
    from .control import PortfolioFailurePolicy

    return frozenset(p.value for p in PortfolioFailurePolicy)


def _cancellation_labels() -> frozenset:
    """Permitted cancellation-state labels: the explicit cancellation scopes plus the two
    failure policies that cancel cooperatively (FAIL_DEPENDENTS / FAIL_PORTFOLIO)."""
    from .control import CancellationScope, PortfolioFailurePolicy

    return frozenset(
        {
            *(s.value for s in CancellationScope),
            PortfolioFailurePolicy.FAIL_DEPENDENTS.value,
            PortfolioFailurePolicy.FAIL_PORTFOLIO.value,
        }
    )


# --------------------------------------------------------------------------- #
# Checkpoint construction                                                      #
# --------------------------------------------------------------------------- #
def _runtime_checkpoint_store(runtime: object):
    cfg = getattr(runtime, "config", None)
    store = getattr(cfg, "state_store", None) or getattr(cfg, "checkpoint_store", None)
    return store


def _load_runtime_checkpoint(store: object, instance_id: str):
    if store is None:
        return None
    if hasattr(store, "load"):
        return store.load(instance_id)
    if hasattr(store, "latest"):
        return store.latest(instance_id)
    return None


def build_portfolio_checkpoint(
    portfolio: WorkflowPortfolio,
    runtime: object,
    *,
    failure_policy: str,
    trace_sequence: int,
) -> PortfolioCheckpoint:
    """Snapshot ``portfolio`` into an unpersisted :class:`PortfolioCheckpoint`.

    For every registration it records a :class:`WorkflowCheckpointRef` to that workflow's
    latest runtime checkpoint (identity + base digest) — a reference, never a copy. The
    runtime MUST be persisting workflow checkpoints (a ``state_store`` or ``checkpoint_store``
    is configured and holds a checkpoint for each registered instance); otherwise there is no
    durable workflow state to reference and a :class:`CheckpointError` is raised."""
    store = _runtime_checkpoint_store(runtime)
    if store is None:
        raise CheckpointError(
            "cannot build a portfolio checkpoint: the runtime has no state_store/"
            "checkpoint_store, so there is no durable workflow checkpoint to reference"
        )
    registrations: List[Dict[str, Any]] = []
    refs: List[WorkflowCheckpointRef] = []
    for entry in portfolio.entries():
        registrations.append(
            {
                "instance_id": entry.instance_id,
                "registration_sequence": entry.registration_sequence,
                "priority": entry.priority.value,
                "weight": entry.weight,
                "age": entry.age,
                "fair_credit": entry.fair_credit,
            }
        )
        wf_cp = _load_runtime_checkpoint(store, entry.instance_id)
        if wf_cp is None:
            raise CheckpointError(
                f"no runtime checkpoint found for workflow {entry.instance_id!r}: the "
                "workflow must be checkpointed before the portfolio references it"
            )
        # Bind BOTH runtime integrity domains: the base coordination digest AND the separate
        # canonical-execution-state extension digest (+ schema version). The base digest
        # deliberately excludes the extension, so base alone would not uniquely bind a v1
        # checkpoint. A legacy (v0) checkpoint carries an empty extension_digest.
        refs.append(
            WorkflowCheckpointRef(
                instance_id=wf_cp.instance_id,
                workflow_id=wf_cp.workflow_id,
                correlation_id=wf_cp.correlation_id,
                checkpoint_digest=wf_cp.digest,
                checkpoint_version=wf_cp.checkpoint_version,
                extension_digest=wf_cp.extension_digest,
            )
        )
    dependencies = [
        {
            "dependent_id": e.dependent_id,
            "requires_id": e.requires_id,
            "dependency_type": e.dep_type.value,
        }
        for e in portfolio.dependencies
    ]
    return PortfolioCheckpoint.create(
        portfolio_id=portfolio.portfolio_id,
        portfolio_status=portfolio.status.value,
        round=portfolio.round,
        registrations=registrations,
        dependencies=dependencies,
        workflow_checkpoint_refs=refs,
        failure_state=portfolio.failure_state(),
        cancellation_state=portfolio.cancellation_state(),
        failure_policy=failure_policy,
        trace_sequence=trace_sequence,
    )


# --------------------------------------------------------------------------- #
# Validation (recovery validator == self-recoverability validator)            #
# --------------------------------------------------------------------------- #
def _finite(x: object) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def validate_portfolio_checkpoint(cp: PortfolioCheckpoint) -> Tuple[bool, Optional[str]]:
    """Validate a portfolio checkpoint fail-closed. Returns ``(ok, reason)``.

    Enforces (in order): supported version; digest integrity; identity; registration
    uniqueness + sequence consistency; valid priority enum; positive finite weight; valid
    integer non-negative age; finite ``fair_credit``; valid dependency references + acyclic
    graph; lifecycle status; a workflow checkpoint reference for every registration (and no
    orphan refs); failure/cancellation targets that are registered; a known failure policy;
    a non-negative integer trace sequence. Malformed values are rejected, never normalized."""
    # Version gate FIRST — never interpret an unknown schema under today's rules.
    if cp.checkpoint_version not in SUPPORTED_PORTFOLIO_CHECKPOINT_VERSIONS:
        return False, (
            f"unsupported checkpoint_version {cp.checkpoint_version!r} "
            f"(supported: {sorted(SUPPORTED_PORTFOLIO_CHECKPOINT_VERSIONS)})"
        )
    # Digest integrity (also fails closed on NaN/Inf that reached the payload).
    if not cp.verify():
        return False, "portfolio_digest mismatch (checkpoint corrupt or tampered)"
    if not cp.portfolio_id or not isinstance(cp.portfolio_id, str):
        return False, "portfolio_id missing"
    if cp.portfolio_status not in _STATUS_VALUES:
        return False, f"invalid portfolio_status {cp.portfolio_status!r}"
    if not isinstance(cp.round, int) or cp.round < 0:
        return False, "round must be a non-negative integer"
    if not isinstance(cp.trace_sequence, int) or cp.trace_sequence < 0:
        return False, "trace_sequence must be a non-negative integer"
    if cp.failure_policy not in _failure_policy_values():
        return False, f"invalid failure_policy {cp.failure_policy!r}"

    # Registrations.
    ids: List[str] = []
    seqs: List[int] = []
    for r in cp.registrations:
        iid = r.get("instance_id")
        if not iid or not isinstance(iid, str):
            return False, "registration missing instance_id"
        ids.append(iid)
        seq = r.get("registration_sequence")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            return False, f"registration {iid!r} has invalid registration_sequence {seq!r}"
        seqs.append(seq)
        if r.get("priority") not in _PRIORITY_VALUES:
            return False, f"registration {iid!r} has invalid priority {r.get('priority')!r}"
        w = r.get("weight")
        if not _finite(w) or w <= 0:
            return False, f"registration {iid!r} weight must be positive and finite"
        age = r.get("age")
        if not isinstance(age, int) or isinstance(age, bool) or age < 0:
            return False, f"registration {iid!r} age must be a non-negative integer"
        if not _finite(r.get("fair_credit")):
            return False, f"registration {iid!r} fair_credit must be finite"
    id_set = set(ids)
    if len(id_set) != len(ids):
        return False, "duplicate registration instance_id"
    # Registration sequences must be the canonical CONTIGUOUS range 0 .. len-1 — the exact
    # invariant H22-B assigns (registration_sequence = len(order) at registration time). A
    # gap/offset is a tampered or corrupt snapshot.
    if sorted(seqs) != list(range(len(seqs))):
        return False, (
            "registration_sequence must be the contiguous range 0.."
            f"{len(seqs) - 1} (got {sorted(seqs)})"
        )

    # Dependencies (validate references + type, then acyclicity via the graph).
    edges: List[WorkflowDependency] = []
    for d in cp.dependencies:
        dep, req, dt = d.get("dependent_id"), d.get("requires_id"), d.get("dependency_type")
        if dep not in id_set:
            return False, f"dependency references unknown dependent {dep!r}"
        if req not in id_set:
            return False, f"dependency references unknown predecessor {req!r}"
        if dep == req:
            return False, f"workflow {dep!r} cannot depend on itself"
        if dt not in _DEP_TYPE_VALUES:
            return False, f"dependency has invalid dependency_type {dt!r}"
        edges.append(WorkflowDependency(dependent_id=dep, requires_id=req, dep_type=DependencyType(dt)))
    # Order nodes by registration_sequence so the graph traversal is deterministic.
    order = [iid for _, iid in sorted(zip(seqs, ids))]
    try:
        DependencyGraph(order, edges)  # rejects cycles fail-closed
    except ValueError as exc:
        return False, f"invalid dependency graph: {exc}"

    # Workflow checkpoint references: exactly one per registration, no orphans, digest present.
    ref_ids = [r.instance_id for r in cp.workflow_checkpoint_refs]
    if len(set(ref_ids)) != len(ref_ids):
        return False, "duplicate workflow_checkpoint_ref instance_id"
    if set(ref_ids) != id_set:
        missing = id_set - set(ref_ids)
        extra = set(ref_ids) - id_set
        return False, (
            f"workflow_checkpoint_refs do not cover registrations exactly "
            f"(missing={sorted(missing)}, orphan={sorted(extra)})"
        )
    for r in cp.workflow_checkpoint_refs:
        if not r.workflow_id or not isinstance(r.workflow_id, str):
            return False, f"workflow_checkpoint_ref {r.instance_id!r} missing workflow_id"
        if not r.checkpoint_digest or not isinstance(r.checkpoint_digest, str):
            return False, f"workflow_checkpoint_ref {r.instance_id!r} missing checkpoint_digest"

    # Failure / cancellation targets must be registered workflows, with labels drawn from the
    # actual permitted vocabulary (a corrupt or fabricated label is rejected).
    for iid, label in cp.failure_state.items():
        if iid not in id_set:
            return False, f"failure_state references unknown workflow {iid!r}"
        if label not in _FAILURE_LABELS:
            return False, f"failure_state[{iid!r}] has invalid label {label!r}"
    cancellation_labels = _cancellation_labels()
    for iid, label in cp.cancellation_state.items():
        if iid not in id_set:
            return False, f"cancellation_state references unknown workflow {iid!r}"
        if label not in cancellation_labels:
            return False, f"cancellation_state[{iid!r}] has invalid scope label {label!r}"
    return True, None


# --------------------------------------------------------------------------- #
# Recovery result + recovery                                                   #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PortfolioRecoveryResult:
    """The immutable outcome of a side-effect-free portfolio recovery.

    ``portfolio`` is the reconstructed (frozen-topology) :class:`WorkflowPortfolio`; ``trace``
    is a :class:`PortfolioTrace` re-seated past the checkpoint anchor and any durable events,
    carrying exactly one ``PORTFOLIO_RECOVERED`` event; ``recovered_workflow_ids`` are the
    workflows reconstructed through the runtime recovery contract; ``requires_continuation`` is
    always ``True`` (a recovered portfolio must be explicitly continued before any execution);
    ``failure_policy`` is the persisted :class:`~.control.PortfolioFailurePolicy` — exposed as a
    typed, first-class field so a reconstructed controller uses the recovered policy by default
    (never silently the constructor default); ``recovery_metadata`` holds per-workflow recovery
    notes (e.g. ``config_mismatch``) — never fabricated. No provider, governance, or advancement
    call is made to produce this."""

    portfolio: WorkflowPortfolio
    trace: PortfolioTrace
    recovered_workflow_ids: Tuple[str, ...]
    requires_continuation: bool
    checkpoint_version: str
    failure_policy: Any  # PortfolioFailurePolicy (typed; annotated Any to avoid an import cycle)
    recovery_metadata: Dict[str, Any] = field(default_factory=dict)


def recover_portfolio(
    *,
    store: object,
    portfolio_id: str,
    runtime: object,
    definitions: Mapping[str, WorkflowDefinition],
    trace: Optional[PortfolioTrace] = None,
    event_store: Optional[PortfolioEventStore] = None,
) -> PortfolioRecoveryResult:
    """Reconstruct a portfolio from its durable checkpoint. **No execution occurs.**

    Loads and validates the portfolio checkpoint; for each referenced workflow it (1) binds the
    reference to the runtime checkpoint the runtime store actually holds across BOTH integrity
    domains — identity, base ``checkpoint_digest``, ``checkpoint_version``, and the separate
    canonical-execution-state ``extension_digest`` — (2) verifies that runtime checkpoint's own
    integrity (``verify`` / ``verify_extension`` / ``validate_execution_states``), and (3)
    reconstructs the workflow through ``runtime.recover_runtime`` (which makes no
    provider/governance call and never auto-runs). It then rebuilds the portfolio with its
    round, per-workflow ``age``/``fair_credit``, dependencies, and failure/cancellation state,
    performs a **semantic** cross-bind against the recovered runtime statuses, and re-seats the
    trace position (continuing past both the checkpoint anchor and any durable events). Emits
    exactly one ``PORTFOLIO_RECOVERED`` event. The result ``requires_continuation``.

    ``definitions`` maps each registered ``instance_id`` to its original
    :class:`WorkflowDefinition`. Pass ``event_store`` to recover the durable audit history and
    keep the trace sequence globally monotonic across restart; ``runtime_id`` /
    ``runtime_version`` are origin provenance and are NOT required to match (upgrades recover)."""
    cp = store.load(portfolio_id) if hasattr(store, "load") else None
    if cp is None:
        raise RecoveryError(f"no portfolio checkpoint found for {portfolio_id!r}")

    ok, reason = validate_portfolio_checkpoint(cp)
    if not ok:
        raise RecoveryError(f"portfolio checkpoint for {portfolio_id!r} failed validation: {reason}")

    rt_store = _runtime_checkpoint_store(runtime)
    if rt_store is None:
        raise RecoveryError(
            "runtime has no state_store/checkpoint_store: cannot bind or recover the "
            "referenced workflow checkpoints"
        )

    refs_by_id = {r.instance_id: r for r in cp.workflow_checkpoint_refs}
    recovered_ids: List[str] = []
    wf_meta: Dict[str, Any] = {}
    recovered_status: Dict[str, WorkflowStatus] = {}

    for iid in cp.instance_ids:
        ref = refs_by_id[iid]
        definition = definitions.get(iid)
        if definition is None:
            raise RecoveryError(f"no WorkflowDefinition supplied for workflow {iid!r}")
        # Cross-binding: prove the referenced runtime checkpoint belongs to this registration,
        # across BOTH integrity domains. NOTE: runtime_id / runtime_version are origin
        # provenance and are deliberately NOT required to match — an upgrade must recover.
        wf_cp = _load_runtime_checkpoint(rt_store, iid)
        if wf_cp is None:
            raise RecoveryError(f"no runtime checkpoint found for referenced workflow {iid!r}")
        if wf_cp.instance_id != ref.instance_id:
            raise RecoveryError(f"workflow checkpoint instance_id mismatch for {iid!r}")
        if wf_cp.workflow_id != ref.workflow_id:
            raise RecoveryError(
                f"workflow checkpoint workflow_id {wf_cp.workflow_id!r} != referenced "
                f"{ref.workflow_id!r} for {iid!r}"
            )
        if wf_cp.correlation_id != ref.correlation_id:
            raise RecoveryError(f"workflow checkpoint correlation_id mismatch for {iid!r}")
        if wf_cp.digest != ref.checkpoint_digest:
            raise RecoveryError(
                f"workflow checkpoint base digest for {iid!r} does not match the portfolio "
                "reference (the reference does not bind the runtime checkpoint on record)"
            )
        if wf_cp.checkpoint_version != ref.checkpoint_version:
            raise RecoveryError(
                f"workflow checkpoint_version {wf_cp.checkpoint_version!r} != referenced "
                f"{ref.checkpoint_version!r} for {iid!r}"
            )
        # The base digest EXCLUDES the canonical-execution-state extension, so bind the
        # extension digest too — a resealed extension (base unchanged) is caught here.
        if wf_cp.extension_digest != ref.extension_digest:
            raise RecoveryError(
                f"workflow checkpoint extension digest for {iid!r} does not match the "
                "portfolio reference (canonical-execution-state extension altered/resealed)"
            )
        # Verify the runtime checkpoint's OWN integrity across both domains before accepting.
        if not wf_cp.verify():
            raise RecoveryError(f"referenced runtime checkpoint for {iid!r} failed base integrity")
        if wf_cp.checkpoint_version != "0":
            states_ok, states_reason = wf_cp.validate_execution_states()
            if not (wf_cp.verify_extension() and states_ok):
                raise RecoveryError(
                    f"referenced runtime checkpoint for {iid!r} failed canonical-execution-"
                    f"state integrity: {states_reason or 'extension_digest mismatch'}"
                )
        elif wf_cp.has_extension_data():
            raise RecoveryError(
                f"legacy (v0) runtime checkpoint for {iid!r} unexpectedly carries extension data"
            )
        if definition.workflow_id != ref.workflow_id:
            raise RecoveryError(
                f"supplied definition workflow_id {definition.workflow_id!r} != referenced "
                f"{ref.workflow_id!r} for {iid!r}"
            )
        # Reconstruct the workflow through the EXISTING runtime recovery contract (no exec).
        rec = runtime.recover_runtime(iid, definition)
        recovered_ids.append(iid)
        recovered_status[iid] = runtime.instance(iid).status
        wf_meta[iid] = {
            "resumed_from_status": rec.resumed_from_status,
            "requires_continuation": rec.requires_continuation,
            "config_mismatch": rec.config_mismatch,
        }

    # Semantic cross-binding: the orchestration state H22-C claims must match underlying
    # runtime truth AFTER recovery. A resealed checkpoint whose outer digest was recomputed
    # but whose claimed state contradicts the recovered workflows must still fail closed.
    _semantic_cross_bind(cp, recovered_status)

    # Rebuild the portfolio orchestration aggregate from the validated snapshot.
    entries: List[PortfolioWorkflowEntry] = []
    for r in sorted(cp.registrations, key=lambda r: r["registration_sequence"]):
        entries.append(
            PortfolioWorkflowEntry(
                instance_id=r["instance_id"],
                registration_sequence=r["registration_sequence"],
                priority=WorkflowPriority(r["priority"]),
                weight=float(r["weight"]),
                age=int(r["age"]),
                fair_credit=float(r["fair_credit"]),
            )
        )
    dependencies = [
        WorkflowDependency(
            dependent_id=d["dependent_id"],
            requires_id=d["requires_id"],
            dep_type=DependencyType(d["dependency_type"]),
        )
        for d in cp.dependencies
    ]
    portfolio = WorkflowPortfolio._restore(
        portfolio_id=cp.portfolio_id,
        status=PortfolioStatus(cp.portfolio_status),
        round=cp.round,
        entries=entries,
        dependencies=dependencies,
        failed=dict(cp.failure_state),
        cancelled=dict(cp.cancellation_state),
    )

    # Re-seat the trace position (crash-safe past the checkpoint anchor AND any durable event)
    # and record exactly one recovery event. A durable event store preserves pre-crash history.
    if trace is not None:
        restored_trace = trace
    else:
        restored_trace = PortfolioTrace.restore(
            cp.portfolio_id, cp.trace_sequence, event_store=event_store
        )
    restored_trace.emit(
        PortfolioEventType.PORTFOLIO_RECOVERED,
        portfolio_id=cp.portfolio_id,
        round=cp.round,
        checkpoint_version=cp.checkpoint_version,
        portfolio_digest=cp.portfolio_digest,
        recovered_workflow_ids=list(recovered_ids),
    )

    from .control import PortfolioFailurePolicy  # lazy (module-load cycle)

    return PortfolioRecoveryResult(
        portfolio=portfolio,
        trace=restored_trace,
        recovered_workflow_ids=tuple(recovered_ids),
        requires_continuation=True,
        checkpoint_version=cp.checkpoint_version,
        failure_policy=PortfolioFailurePolicy(cp.failure_policy),
        recovery_metadata={
            "portfolio_digest": cp.portfolio_digest,
            "failure_policy": cp.failure_policy,
            "workflows": wf_meta,
        },
    )


def _semantic_cross_bind(
    cp: PortfolioCheckpoint, recovered_status: Mapping[str, WorkflowStatus]
) -> None:
    """Prove the portfolio's claimed orchestration state matches recovered runtime truth.

    Fails closed (``RecoveryError``) if the claim contradicts the workflows actually
    reconstructed from their runtime checkpoints — even when the outer portfolio digest was
    validly resealed. Intermediate ``CREATED``/``ACTIVE`` portfolios are not over-constrained."""
    # failure_state[iid] ⇒ that workflow really is FAILED; cancellation_state[iid] ⇒ CANCELLED.
    for iid in cp.failure_state:
        if recovered_status.get(iid) is not WorkflowStatus.FAILED:
            raise RecoveryError(
                f"failure_state claims {iid!r} failed, but its recovered runtime status is "
                f"{recovered_status.get(iid)!r}"
            )
    for iid in cp.cancellation_state:
        if recovered_status.get(iid) is not WorkflowStatus.CANCELLED:
            raise RecoveryError(
                f"cancellation_state claims {iid!r} cancelled, but its recovered runtime status "
                f"is {recovered_status.get(iid)!r}"
            )
    # Terminal portfolio lifecycle invariants created by the H22-C controller: COMPLETED,
    # FAILED, and CANCELLED all imply every registered workflow is terminal (FAIL_PORTFOLIO and
    # PORTFOLIO_ALL cancel every non-terminal workflow; COMPLETED means all workflows finished).
    status = PortfolioStatus(cp.portfolio_status)
    if status in TERMINAL_PORTFOLIO_STATUSES:
        non_terminal = [
            iid for iid, st in recovered_status.items()
            if st not in TERMINAL_WORKFLOW_STATUSES
        ]
        if non_terminal:
            raise RecoveryError(
                f"portfolio_status {status.value} but recovered workflows are non-terminal: "
                f"{sorted(non_terminal)}"
            )
        # FAILED additionally implies at least one observed workflow failure was recorded.
        if status is PortfolioStatus.FAILED and not cp.failure_state:
            raise RecoveryError(
                "portfolio_status FAILED but no workflow failure was recorded"
            )
