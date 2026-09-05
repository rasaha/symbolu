"""DBOS-backed :class:`DurableExecutionAdapter`.

**Where the step boundary is drawn, and why it is the whole design.**

Agent Runtime already runs proposal construction, ``GovernanceHook.evaluate``,
``validate_clearance``, the last-mile authority recheck, the provider invocation and
the resulting transition inside one bounded advancement quantum — its own
``advance_workflow`` docstring says the chain "runs entirely WITHIN a single quantum"
so that nothing can observe or preempt a workflow "between a governance CLEAR and the
provider invocation it cleared".

The durable step is drawn around exactly that quantum: one ``advance`` call is one
``engine.advance_workflow(instance_id)``. Nothing smaller is safe. A step boundary
placed *between* clearance and invocation would let the engine's retry replay the
invocation against a stale clearance, which is the failure the whole boundary exists
to prevent.

**Why each mutating call runs as a DBOS *workflow*, not a bare transaction.**

``run_tx_step`` writes its step record only when it runs inside a DBOS workflow
context — outside one, ``in_wf`` is False and the transaction still commits but no step
record is written. Calling it directly would therefore give the transaction without the
durable step, which is not what owner ruling OD-1 requires. So every mutating operation
here is a decorated ``@DBOS.workflow()`` whose body is a decorated ``@ds.transaction``:
the step record and the runtime's own writes then land in one transaction, which is the
property ``tests/test_od1_single_transaction.py`` proves.

**Why attempts deliberately do NOT share a workflow id.** Each ``advance`` runs as a
fresh DBOS workflow, so DBOS never replays a previously recorded advance result. That is
the conservative choice: every attempt re-enters Agent Runtime and re-crosses the
governance boundary. The step record's role here is atomicity and durable evidence of
the attempt, not replay.

**Why DBOS's replay short-circuit is safe here.** A DBOS transaction step that has
committed replays its recorded result instead of re-running the body, so a replayed
advance does not re-cross the governance boundary. That is correct rather than a
loophole: the step committed, so the effect and the state transition are both durably
recorded, and the action was cleared when it ran. Re-clearing a committed step would
double-execute it. The governance requirement applies to steps that did **not**
commit, and for those DBOS leaves nothing behind at all — verified empirically in
``tests/test_od1_single_transaction.py``, where a SIGKILL mid-transaction leaves
neither the application write nor the step record.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import sqlalchemy as sa

from ..clock import assert_durable_clock
from ..errors import (
    DefinitionVersionMismatch,
    InstanceIdentityError,
    PostureError,
    UnrecoverableInstanceError,
)
from ..postgres.schema import SCHEMA_NAME, schema_statements

__all__ = ["StepOutcome", "DbosRuntimeHost", "DbosExecutionAdapter"]

ENGINE_ID = "dbos"


@dataclass(frozen=True)
class StepOutcome:
    """Concrete :class:`DurableStepOutcome`.

    Deliberately coarse: ``awaiting_external`` collapses WAITING and PAUSED into one
    fact, so the engine cannot schedule differently depending on whether governance
    said HOLD or ESCALATE. It never learns which.
    """

    instance_id: str
    progressed: bool
    terminal: bool
    awaiting_external: bool
    checkpoint_digest: Optional[str] = None
    #: Advisory only, for observability. Never read by scheduling.
    stop_reason: str = ""

    @classmethod
    def from_advance(cls, outcome: Any) -> "StepOutcome":
        return cls(
            instance_id=outcome.instance_id,
            progressed=bool(outcome.progressed),
            terminal=bool(outcome.terminal),
            awaiting_external=bool(outcome.waiting or outcome.paused),
            checkpoint_digest=outcome.checkpoint_digest,
            stop_reason=str(outcome.stop_reason),
        )

    @classmethod
    def parked(cls, instance_id: str, reason: str) -> "StepOutcome":
        return cls(
            instance_id=instance_id,
            progressed=False,
            terminal=False,
            awaiting_external=True,
            stop_reason=reason,
        )


class DbosRuntimeHost:
    """What the adapter needs from the caller to rebuild a runtime for one instance.

    The adapter never constructs an ``AgentRuntimeConfig`` itself: governance hook,
    provider registry, clock and authority recheck are the composition root's to
    choose, and choosing them here would put governance configuration inside the
    engine integration — exactly the boundary ADR §3 forbids.

    ``build_engine(bundle, definition_digest, instance_id)`` returns an Agent Runtime
    engine wired to the supplied durable stores, with its ``id_generator`` pinned to
    ``instance_id``. Pinning it is what makes the ADR's "``instance_id`` is supplied by
    the CALLER, never minted by the engine" true in practice: Agent Runtime mints an id
    from ``config.id_generator`` in ``prepare_workflow``, so the caller's id reaches the
    first durable write only if the generator returns it.

    ``definition_for(workflow_id)`` returns the ``WorkflowDefinition`` an instance was
    started against, so recovery can rebuild it.
    """

    def __init__(
        self,
        *,
        build_engine: Callable[[Any, str, str], Any],
        definition_for: Callable[[str], Any],
        clock: Callable[[], float],
    ) -> None:
        # Refuse a process-local clock before anything consequential can run (ADR §6.4).
        assert_durable_clock(clock)
        self.build_engine = build_engine
        self.definition_for = definition_for
        self.clock = clock


class DbosExecutionAdapter:
    """Drive Agent Runtime transitions durably on DBOS.

    Construction refuses a non-authoritative bundle in production mode and refuses a
    process-local clock, so a misconfigured deployment fails at wiring time rather than
    at the first expiry comparison after a recovery — which is exactly when it would be
    too late to notice.
    """

    def __init__(
        self,
        *,
        datasource: Any,
        host: DbosRuntimeHost,
        bundle: Any,
        worker_id: str = "worker-1",
        production_mode: bool = True,
        definition_digest: str = "",
    ) -> None:
        if production_mode and not bundle.is_production_authoritative:
            raise PostureError(
                "production_mode requires a durable, integrity-checked store bundle; "
                f"{type(bundle).__name__} reports is_production_authoritative=False"
            )
        self._ds = datasource
        self._host = host
        self._bundle = bundle
        self._worker_id = worker_id
        self._durable = _build_durable_callables(datasource, self)
        # The compiled Workflow IR digest THIS deployment is running. Recovery compares
        # it against what an instance was started under and refuses a mismatch (ADR §8
        # row 10): a redeploy with a changed definition must not silently reinterpret
        # instances that are mid-flight under the old one.
        self._definition_digest = definition_digest
        self._engines: Dict[str, Any] = {}

    # -- identity -------------------------------------------------------------
    @property
    def engine_id(self) -> str:
        return ENGINE_ID

    # -- schema ---------------------------------------------------------------
    def create_schema(self, engine: Any) -> None:
        """Create the durable tables. Separate from ``__init__`` so a deployment
        controls when DDL runs."""
        with engine.begin() as conn:
            for stmt in schema_statements():
                conn.execute(sa.text(stmt))

    # -- lifecycle ------------------------------------------------------------
    def start(
        self,
        *,
        workflow_id: str,
        definition_digest: str,
        instance_id: str,
        correlation_id: Optional[str],
        inputs: Mapping[str, Any],
    ) -> str:
        """Register one instance durably. Idempotent on ``instance_id``.

        A duplicate start with the SAME identifying fields returns the existing handle
        and touches nothing. A duplicate start with DIFFERENT ones raises rather than
        overwriting: two callers disagreeing about what an instance is must not be
        resolved silently in favour of whoever wrote last.
        """
        def _register() -> str:
            s = self._ds.sql_session()
            row = s.execute(
                sa.text(
                    f"SELECT workflow_id, definition_digest FROM {SCHEMA_NAME}.runtime_state "
                    "WHERE instance_id = :i"
                ),
                {"i": instance_id},
            ).first()
            if row is not None:
                if row[0] != workflow_id or row[1] != definition_digest:
                    raise InstanceIdentityError(
                        f"instance {instance_id!r} already exists as "
                        f"(workflow_id={row[0]!r}, definition_digest={row[1]!r}); "
                        f"refusing a conflicting start as "
                        f"(workflow_id={workflow_id!r}, definition_digest={definition_digest!r})"
                    )
                return instance_id
            engine = self._engine_for(instance_id, definition_digest)
            definition = self._host.definition_for(workflow_id)
            engine.prepare_workflow(definition, correlation_id)
            s.execute(
                sa.text(
                    f"UPDATE {SCHEMA_NAME}.runtime_state SET definition_digest = :d "
                    "WHERE instance_id = :i"
                ),
                {"d": definition_digest, "i": instance_id},
            )
            return instance_id

        return self._durable.run("start", _register)

    def advance(self, *, instance_id: str, attempt_token: str) -> StepOutcome:
        """One durable step = one bounded advancement of Agent Runtime.

        The entire governance chain runs inside the transaction this opens. A retry
        re-enters it in full.
        """
        def _step() -> StepOutcome:
            s = self._ds.sql_session()
            state = self._bundle.state_store
            if not state.claim(instance_id, self._worker_id, self._host.clock()):
                # Another worker holds the row. Refused, not queued: the loser does not
                # execute, and reports that it did not.
                return StepOutcome.parked(instance_id, "CLAIM_HELD_BY_ANOTHER_WORKER")
            digest = state.definition_digest(instance_id) or ""
            engine = self._engine_for(instance_id, digest)
            events = self._bundle.event_store
            if hasattr(events, "attempt_token"):
                events.attempt_token = attempt_token
            if instance_id not in getattr(engine, "_instances", {}):
                self._rehydrate(engine, instance_id, digest)
            outcome = engine.advance_workflow(instance_id)
            return StepOutcome.from_advance(outcome)

        return self._durable.run("advance", _step)

    def signal(
        self, *, instance_id: str, signal_name: str, payload: Mapping[str, Any]
    ) -> None:
        """Record that something happened outside. Data, never authority.

        A signal never resolves a governance disposition. It is recorded, and the next
        ``advance`` re-crosses the boundary from the beginning; the runtime's own
        ``resume_workflow`` is what re-arms WAITING tasks, and it too re-evaluates.
        """
        def _sig() -> None:
            s = self._ds.sql_session()
            seq = s.execute(
                sa.text(
                    f"SELECT COALESCE(MAX(seq),0)+1 FROM {SCHEMA_NAME}.runtime_events "
                    "WHERE instance_id = :i"
                ),
                {"i": instance_id},
            ).scalar_one()
            s.execute(
                sa.text(
                    f"INSERT INTO {SCHEMA_NAME}.runtime_events "
                    "(instance_id, seq, event_type, body, attempt_token, engine_id) "
                    "VALUES (:i, :s, :t, CAST(:b AS jsonb), NULL, :e)"
                ),
                {
                    "i": instance_id,
                    "s": int(seq),
                    "t": f"EXTERNAL_SIGNAL:{signal_name}",
                    "b": json.dumps({"signal": signal_name, "payload": dict(payload)},
                                    sort_keys=True, default=str),
                    "e": ENGINE_ID,
                },
            )

        self._durable.run("signal", _sig)

    def resume(self, *, instance_id: str) -> None:
        """Explicitly re-arm a parked instance so the next ``advance`` re-evaluates.

        Delegates to the runtime's ``resume_workflow`` — the runtime's own documented
        and only way for HOLD/ESCALATE work to proceed. This adapter adds nothing to it
        and cannot bypass it.
        """
        def _res() -> None:
            digest = self._bundle.state_store.definition_digest(instance_id) or ""
            engine = self._engine_for(instance_id, digest)
            if instance_id not in getattr(engine, "_instances", {}):
                self._rehydrate(engine, instance_id, digest)
            engine.resume_workflow(instance_id)

        self._durable.run("resume", _res)

    def status(self, *, instance_id: str) -> Mapping[str, Any]:
        """Neutral engine-side status. Never a governance status."""
        def _st() -> Mapping[str, Any]:
            s = self._ds.sql_session()
            row = s.execute(
                sa.text(
                    f"SELECT workflow_id, definition_digest, updated_seq "
                    f"FROM {SCHEMA_NAME}.runtime_state WHERE instance_id = :i"
                ),
                {"i": instance_id},
            ).first()
            if row is None:
                return {"known": False}
            events = s.execute(
                sa.text(
                    f"SELECT COUNT(*) FROM {SCHEMA_NAME}.runtime_events WHERE instance_id = :i"
                ),
                {"i": instance_id},
            ).scalar_one()
            return {
                "known": True,
                "engine_id": ENGINE_ID,
                "workflow_id": row[0],
                "definition_digest": row[1],
                "state_writes": int(row[2]),
                "event_count": int(events),
            }

        return self._ds.run_tx_step(None, _st)  # read-only: no step record needed

    def recover(self, *, worker_id: str) -> Sequence[str]:
        """Reclaim instances a crashed worker was driving.

        An instance whose durable state fails integrity checks is NOT recovered — it is
        left out of the returned set and surfaced through :meth:`unrecoverable`. Silently
        re-driving an instance whose state failed verification is precisely the failure
        this boundary exists to prevent.
        """
        def _rec() -> List[str]:
            s = self._ds.sql_session()
            rows = s.execute(
                sa.text(
                    f"SELECT instance_id FROM {SCHEMA_NAME}.worker_claims "
                    "WHERE worker_id = :w ORDER BY instance_id"
                ),
                {"w": worker_id},
            ).all()
            recovered: List[str] = []
            for (iid,) in rows:
                try:
                    self._bundle.state_store.load(iid)
                except Exception:
                    continue  # unrecoverable; reported separately, never re-driven
                recovered.append(iid)
            return recovered

        return self._ds.run_tx_step(None, _rec)  # read-only

    def unrecoverable(self, *, worker_id: str) -> Sequence[str]:
        """Instances claimed by ``worker_id`` whose durable state failed verification."""
        def _unrec() -> List[str]:
            s = self._ds.sql_session()
            rows = s.execute(
                sa.text(
                    f"SELECT instance_id FROM {SCHEMA_NAME}.worker_claims "
                    "WHERE worker_id = :w ORDER BY instance_id"
                ),
                {"w": worker_id},
            ).all()
            bad: List[str] = []
            for (iid,) in rows:
                try:
                    self._bundle.state_store.load(iid)
                except Exception:
                    bad.append(iid)
            return bad

        return self._ds.run_tx_step(None, _unrec)  # read-only

    # -- internals ------------------------------------------------------------
    def _engine_for(self, instance_id: str, definition_digest: str) -> Any:
        """One Agent Runtime per instance, with its id generator pinned to that instance.

        Keyed by instance rather than by definition so two instances can never share a
        generator and mint each other's ids.
        """
        engine = self._engines.get(instance_id)
        if engine is None:
            engine = self._host.build_engine(self._bundle, definition_digest, instance_id)
            self._engines[instance_id] = engine
        return engine

    def forget(self, instance_id: str) -> None:
        """Drop the in-process engine for an instance, forcing the next ``advance`` to
        rehydrate from durable state. Used by the recovery tests to prove that a fresh
        process reads what Postgres kept rather than what memory happened to retain."""
        self._engines.pop(instance_id, None)

    def _rehydrate(self, engine: Any, instance_id: str, definition_digest: str) -> None:
        """Rebuild an in-process instance from durable state.

        Refuses when the stored ``definition_digest`` differs from the definition now on
        offer (ADR §8 row 10): an instance started under one compiled workflow is not
        reinterpreted under another.
        """
        stored = self._bundle.state_store.definition_digest(instance_id)
        deployed = self._definition_digest or definition_digest
        if stored and deployed and stored != deployed:
            raise DefinitionVersionMismatch(instance_id, stored, deployed)
        checkpoint = self._bundle.state_store.load(instance_id)
        if checkpoint is None:
            raise UnrecoverableInstanceError(
                f"instance {instance_id!r} has no durable state to recover from"
            )
        definition = self._host.definition_for(checkpoint.workflow_id)
        engine.recover_runtime(instance_id, definition)


# --------------------------------------------------------------------------- #
# durable callable pair: @DBOS.workflow() wrapping @datasource.transaction
# --------------------------------------------------------------------------- #
class _DurableCallables:
    """One workflow/transaction pair, built once per adapter before ``DBOS.launch()``.

    The indirection through ``_pending`` exists because DBOS serializes a workflow's
    arguments and results, and the closures these operations need (an Agent Runtime
    engine, a store bundle) are neither serializable nor meaningful to another process.
    So the workflow carries only a short operation label, and the closure is handed
    across in-process. What DBOS durably records is the step's *outcome* and the fact
    that the transaction committed — which is exactly what OD-1 is about.
    """

    def __init__(self, workflow: Any) -> None:
        self._workflow = workflow
        self._pending: Dict[str, Callable[[], Any]] = {}
        self._counter = 0

    def run(self, label: str, body: Callable[[], Any]) -> Any:
        self._counter += 1
        key = f"{label}-{self._counter}"
        self._pending[key] = body
        try:
            return self._workflow(key)
        finally:
            self._pending.pop(key, None)

    def _invoke(self, key: str) -> Any:
        body = self._pending.get(key)
        if body is None:
            raise RuntimeError(
                f"no pending durable body for {key!r}; a replayed workflow cannot "
                "re-enter a closure from another process"
            )
        return body()


def _build_durable_callables(datasource: Any, adapter: Any) -> _DurableCallables:
    """Decorate the transaction and the workflow that wraps it.

    Both decorators must be applied BEFORE ``DBOS.launch()``, which is why this runs
    from ``DbosExecutionAdapter.__init__``.
    """
    from dbos import DBOS

    holder: Dict[str, Any] = {}

    @datasource.transaction(isolation_level="READ COMMITTED")
    def _tx(key: str) -> Any:
        return holder["callables"]._invoke(key)

    @DBOS.workflow(name=f"ude_durable_{id(adapter):x}")
    def _wf(key: str) -> Any:
        return _tx(key)

    callables = _DurableCallables(_wf)
    holder["callables"] = callables
    return callables
