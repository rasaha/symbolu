"""H22-C — the durable portfolio orchestration checkpoint and its store.

A :class:`PortfolioCheckpoint` is the *orchestration-layer* durable snapshot (Layer 4). It
holds only what is needed to deterministically reconstruct the H22-B portfolio and
scheduler after a crash/restart, and it references each underlying workflow's runtime
checkpoint **by digest** — it never embeds a copy of that checkpoint, and it never
duplicates Canonical Execution State. The runtime checkpoint remains the sole authority for
each workflow's execution truth.

## What is persisted (and what is not)

Persisted because it is not safely recomputable or it drives *future* scheduling:

* ``portfolio_id`` / ``portfolio_status`` / ``round`` (logical scheduler round);
* per registration: ``instance_id``, ``registration_sequence``, ``priority``, ``weight``,
  ``age``, and the smooth-weighted-round-robin ``fair_credit`` (both ``age`` and
  ``fair_credit`` change the *next* scheduler choice, so restoring them is mandatory for
  scheduler continuity);
* the cross-workflow dependency edges;
* the orchestration failure/cancellation state;
* one **reference** per workflow to its runtime checkpoint (identity + digest);
* the portfolio-level trace sequence anchor.

Deliberately NOT persisted — recomputed on recovery from the durable inputs above and the
recovered workflow states, so no stale derived state can drift:

* dependency depth (recomputed from the edge set);
* eligibility (recomputed from recovered runtime status + dependency verdict);
* scheduler ordering / the eligible list / effective ranks (recomputed each round);
* the full historical trace (audit history lives in the append-only trace, not here);
* any workflow task status or canonical execution state (owned by the runtime checkpoint).

## Integrity

The checkpoint carries a single SHA-256 ``portfolio_digest`` over a deterministic canonical
serialization of every field above (stable key ordering, enums by value, no object
identity, no wall-clock in integrity-critical scheduling semantics). Serialization uses
``allow_nan=False`` so a NaN/±Inf that reached a weight or ``fair_credit`` fails **closed**
rather than being silently accepted. A malformed or tampered checkpoint is rejected on
recovery; and — the *portfolio self-recoverability invariant* — a checkpoint is validated by
the same recovery validator before it is ever persisted (see
:func:`validate_portfolio_checkpoint`), so H22-C never writes a checkpoint its own recovery
would reject.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

# Current portfolio-checkpoint schema version. An unknown future version must fail closed on
# recovery rather than be interpreted under today's semantics.
PORTFOLIO_CHECKPOINT_VERSION = "1"
SUPPORTED_PORTFOLIO_CHECKPOINT_VERSIONS = frozenset({PORTFOLIO_CHECKPOINT_VERSION})


def _portfolio_digest(payload: Dict[str, Any]) -> str:
    """Deterministic SHA-256 over the canonical payload (digest field excluded).

    ``allow_nan=False`` makes a NaN/±Inf anywhere in the payload raise (fail closed) instead
    of emitting the non-deterministic ``NaN``/``Infinity`` JSON tokens."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class WorkflowCheckpointRef:
    """A reference (never a copy) to one workflow's authoritative runtime checkpoint.

    Binds the portfolio registration to the underlying runtime checkpoint by identity
    (``instance_id`` / ``workflow_id`` / ``correlation_id``) and by ``checkpoint_digest`` (the
    runtime checkpoint's base digest). Recovery re-verifies this reference against the runtime
    checkpoint the runtime store actually holds — proving the referenced checkpoint belongs to
    the registration it claims to represent, without ever duplicating its contents."""

    instance_id: str
    workflow_id: str
    correlation_id: Optional[str]
    checkpoint_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "checkpoint_digest": self.checkpoint_digest,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowCheckpointRef":
        return cls(
            instance_id=d["instance_id"],
            workflow_id=d["workflow_id"],
            correlation_id=d.get("correlation_id"),
            checkpoint_digest=d["checkpoint_digest"],
        )


@dataclass(frozen=True)
class PortfolioCheckpoint:
    """A versioned, self-verifying durable snapshot of portfolio orchestration state.

    Construct via :meth:`create` (which computes the digest). ``registrations`` is a list of
    dicts (``instance_id``, ``registration_sequence``, ``priority``, ``weight``, ``age``,
    ``fair_credit``); ``dependencies`` a list of edge dicts; ``workflow_checkpoint_refs`` a
    list of :class:`WorkflowCheckpointRef`; ``failure_state`` / ``cancellation_state`` maps of
    ``instance_id`` → orchestration label. Ordering inside the canonical payload is
    normalized (by ``registration_sequence`` / by ``instance_id``) so the digest is stable
    regardless of input order."""

    checkpoint_version: str
    portfolio_id: str
    portfolio_status: str
    round: int
    registrations: Tuple[Dict[str, Any], ...]
    dependencies: Tuple[Dict[str, Any], ...]
    workflow_checkpoint_refs: Tuple[WorkflowCheckpointRef, ...]
    failure_state: Dict[str, str]
    cancellation_state: Dict[str, str]
    failure_policy: str
    trace_sequence: int
    portfolio_digest: str = ""

    # -- construction -------------------------------------------------------
    @classmethod
    def create(
        cls,
        *,
        portfolio_id: str,
        portfolio_status: str,
        round: int,
        registrations: List[Dict[str, Any]],
        dependencies: List[Dict[str, Any]],
        workflow_checkpoint_refs: List[WorkflowCheckpointRef],
        failure_state: Dict[str, str],
        cancellation_state: Dict[str, str],
        failure_policy: str,
        trace_sequence: int,
    ) -> "PortfolioCheckpoint":
        regs = tuple(sorted(registrations, key=lambda r: r["registration_sequence"]))
        deps = tuple(
            sorted(dependencies, key=lambda d: (d["dependent_id"], d["requires_id"]))
        )
        refs = tuple(sorted(workflow_checkpoint_refs, key=lambda r: r.instance_id))
        obj = cls(
            checkpoint_version=PORTFOLIO_CHECKPOINT_VERSION,
            portfolio_id=portfolio_id,
            portfolio_status=portfolio_status,
            round=int(round),
            registrations=regs,
            dependencies=deps,
            workflow_checkpoint_refs=refs,
            failure_state=dict(failure_state),
            cancellation_state=dict(cancellation_state),
            failure_policy=failure_policy,
            trace_sequence=int(trace_sequence),
        )
        return cls(**{**obj.__dict__, "portfolio_digest": _portfolio_digest(obj.payload())})

    # -- integrity ----------------------------------------------------------
    def payload(self) -> Dict[str, Any]:
        """The canonical, digest-covered payload (every integrity-critical field; the
        digest itself excluded). Deterministic: registrations ordered by sequence, edges and
        refs and maps ordered by id."""
        return {
            "checkpoint_version": self.checkpoint_version,
            "portfolio_id": self.portfolio_id,
            "portfolio_status": self.portfolio_status,
            "round": self.round,
            "registrations": [
                dict(sorted(r.items())) for r in
                sorted(self.registrations, key=lambda r: r["registration_sequence"])
            ],
            "dependencies": [
                dict(sorted(d.items())) for d in
                sorted(self.dependencies, key=lambda d: (d["dependent_id"], d["requires_id"]))
            ],
            "workflow_checkpoint_refs": [
                r.to_dict() for r in
                sorted(self.workflow_checkpoint_refs, key=lambda r: r.instance_id)
            ],
            "failure_state": dict(sorted(self.failure_state.items())),
            "cancellation_state": dict(sorted(self.cancellation_state.items())),
            "failure_policy": self.failure_policy,
            "trace_sequence": self.trace_sequence,
        }

    def compute_digest(self) -> str:
        return _portfolio_digest(self.payload())

    def verify(self) -> bool:
        """True when the stored digest matches the canonical payload. Fails closed (returns
        ``False``) if a NaN/±Inf reached the payload — :func:`_portfolio_digest` raises and
        this reports the mismatch rather than crashing."""
        try:
            return bool(self.portfolio_digest) and self.portfolio_digest == self.compute_digest()
        except ValueError:
            return False

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["portfolio_digest"] = self.portfolio_digest
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioCheckpoint":
        return cls(
            checkpoint_version=d.get("checkpoint_version", ""),
            portfolio_id=d["portfolio_id"],
            portfolio_status=d["portfolio_status"],
            round=int(d["round"]),
            registrations=tuple(dict(r) for r in d.get("registrations", ())),
            dependencies=tuple(dict(x) for x in d.get("dependencies", ())),
            workflow_checkpoint_refs=tuple(
                WorkflowCheckpointRef.from_dict(r)
                for r in d.get("workflow_checkpoint_refs", ())
            ),
            failure_state=dict(d.get("failure_state", {})),
            cancellation_state=dict(d.get("cancellation_state", {})),
            failure_policy=d.get("failure_policy", ""),
            trace_sequence=int(d.get("trace_sequence", 0)),
            portfolio_digest=d.get("portfolio_digest", ""),
        )

    # -- convenience --------------------------------------------------------
    @property
    def instance_ids(self) -> Tuple[str, ...]:
        """Registered workflow ids in registration-sequence order."""
        return tuple(
            r["instance_id"]
            for r in sorted(self.registrations, key=lambda r: r["registration_sequence"])
        )


# --------------------------------------------------------------------------- #
# Store interface + in-memory reference implementation                         #
# --------------------------------------------------------------------------- #
@runtime_checkable
class PortfolioCheckpointStore(Protocol):
    """Neutral durable store for portfolio checkpoints (interface only).

    The core ships only the in-memory reference implementation; a production backend (SQL /
    KV / event store) is supplied externally, exactly as for the single-workflow
    ``CheckpointStore``. ``save`` may implement optimistic concurrency by honoring
    ``expected_generation`` (see :class:`InMemoryPortfolioCheckpointStore`)."""

    def save(self, checkpoint: PortfolioCheckpoint) -> int:
        ...

    def load(self, portfolio_id: str) -> Optional[PortfolioCheckpoint]:
        ...

    def generation(self, portfolio_id: str) -> int:
        ...


class PortfolioCheckpointConflict(Exception):
    """Raised by a compare-and-save store when the expected generation is stale."""


class InMemoryPortfolioCheckpointStore:
    """Deterministic, dependency-free reference store (NOT a durable backend).

    Round-trips every checkpoint through its serialized form so tests exercise the same
    (de)serialization a durable backend would. Tracks a monotonic per-portfolio ``generation``
    and supports optional compare-and-save: pass ``expected_generation`` to
    :meth:`save`; a stale expectation raises :class:`PortfolioCheckpointConflict` (in-process
    optimistic concurrency, not distributed consensus)."""

    def __init__(self) -> None:
        self._latest: Dict[str, dict] = {}
        self._generation: Dict[str, int] = {}

    def save(
        self, checkpoint: PortfolioCheckpoint, expected_generation: Optional[int] = None
    ) -> int:
        pid = checkpoint.portfolio_id
        current = self._generation.get(pid, 0)
        if expected_generation is not None and expected_generation != current:
            raise PortfolioCheckpointConflict(
                f"stale portfolio checkpoint write for {pid!r}: expected generation "
                f"{expected_generation}, store is at {current}"
            )
        self._latest[pid] = checkpoint.to_dict()
        self._generation[pid] = current + 1
        return self._generation[pid]

    def load(self, portfolio_id: str) -> Optional[PortfolioCheckpoint]:
        d = self._latest.get(portfolio_id)
        return PortfolioCheckpoint.from_dict(d) if d is not None else None

    def generation(self, portfolio_id: str) -> int:
        return self._generation.get(portfolio_id, 0)
