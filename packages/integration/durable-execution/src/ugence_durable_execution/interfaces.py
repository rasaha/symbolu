"""Neutral durable-execution boundary.

The adapter lets an external engine DRIVE Agent Runtime transitions durably. It
carries no governance concept: no disposition, no envelope, no clearance, no policy,
no credential. Everything it moves across the boundary is either a neutral identifier
or an opaque, already-governed Agent Runtime artefact.

An adapter that needed to understand a governance type in order to schedule correctly
would be the wrong shape, and would be rejected in review on that ground alone.

These Protocols are transcribed from
``docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md`` §4 and are the surface a
second engine (Temporal, ADR §7) must satisfy without modification. ``test_adr_conformance``
asserts the surface still matches the ADR, so a widened Protocol cannot land quietly.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

__all__ = [
    "DurableStepOutcome",
    "DurableExecutionAdapter",
    "DurableStoreBundle",
]


@runtime_checkable
class DurableStepOutcome(Protocol):
    """What one durably-executed Agent Runtime advance reports back to the engine.

    Deliberately coarse. The engine learns only whether it may advance again, whether
    it must wait for something outside itself, and whether the instance is finished.
    It never learns *why* — a HOLD and an ESCALATE are indistinguishable here, because
    the engine must not be able to schedule differently on the basis of a governance
    reason.
    """

    @property
    def instance_id(self) -> str:
        """The Agent Runtime workflow instance this outcome belongs to."""

    @property
    def progressed(self) -> bool:
        """True when runtime state advanced. False is not a failure; it means the
        instance is parked and only an external event can move it."""

    @property
    def terminal(self) -> bool:
        """True when the instance reached a terminal status and must not be driven
        again. An engine that re-drives a terminal instance is a defect."""

    @property
    def awaiting_external(self) -> bool:
        """True when the instance is parked pending something the engine cannot
        supply — a human decision, a re-cleared authority, an expired window. The
        engine may schedule a *re-entry attempt* but never a *resumption*: re-entry
        re-crosses the governance boundary from the beginning."""

    @property
    def checkpoint_digest(self) -> Optional[str]:
        """Digest of the checkpoint written by this advance, if one was written.
        Opaque to the engine; used only for observability and for detecting that two
        engine attempts converged on the same runtime state."""


@runtime_checkable
class DurableExecutionAdapter(Protocol):
    """The contract Agent Runtime depends on to be driven durably.

    Implemented once per engine (DBOS now, Temporal later). Agent Runtime never
    imports a concrete implementation; a composition root injects one.
    """

    @property
    def engine_id(self) -> str:
        """Stable identifier of the engine backing this adapter, recorded in runtime
        events so a receipt says which engine drove the instance. Never used to vary
        governance behaviour."""

    def start(
        self,
        *,
        workflow_id: str,
        definition_digest: str,
        instance_id: str,
        correlation_id: Optional[str],
        inputs: Mapping[str, Any],
    ) -> str:
        """Durably register one workflow instance for execution and return the
        engine's handle for it.

        ``instance_id`` is supplied by the CALLER, never minted by the engine, so the
        durable record and the Agent Runtime checkpoint agree on identity from the
        first write. ``definition_digest`` pins the exact compiled Workflow IR this
        instance was started against; recovery under a different digest must refuse
        (ADR §8 row 10) rather than reinterpret persisted state under new semantics.

        Idempotent on ``instance_id``: a duplicate start returns the existing handle
        and must not create a second instance or reset any state.
        """

    def advance(
        self,
        *,
        instance_id: str,
        attempt_token: str,
    ) -> "DurableStepOutcome":
        """Durably execute ONE Agent Runtime advance and record that it happened.

        This is the durable step, and the whole governance chain lives inside it:
        proposal construction, ``GovernanceHook.evaluate``, ``validate_clearance``,
        the last-mile authority recheck, provider invocation and the resulting state
        transition all occur within this call (ADR §6). The engine may retry this call
        freely; every retry re-enters the full chain.

        ``attempt_token`` identifies the engine's delivery attempt. It is recorded for
        observability and duplicate detection. It is deliberately NOT part of the
        Agent Runtime proposal fingerprint or idempotency key — a retry must produce
        the SAME proposal identity, so that a hook can recognise it as the same
        proposed action rather than a new one (ADR §6.2).
        """

    def signal(
        self,
        *,
        instance_id: str,
        signal_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        """Deliver an external event to a parked instance — a human decision landing,
        an authority re-issued, a hold released.

        The signal is DATA, never authority. It records that something happened
        outside; it never carries a disposition, and delivering it never permits a
        transition. After a signal, the instance is re-driven through ``advance`` and
        the governance boundary is crossed again from the beginning (ADR §8 row 9).
        """

    def status(self, *, instance_id: str) -> Mapping[str, Any]:
        """Neutral engine-side status for observability: known/unknown, parked,
        running, terminal, attempt counts, last error class. Never a governance
        status, and never a substitute for reading Agent Runtime state."""

    def recover(self, *, worker_id: str) -> Sequence[str]:
        """Reclaim instances a crashed worker was driving and return their ids.

        Recovery re-drives from durable state; it never resumes a partially completed
        step and never assumes a step that was in flight succeeded. An instance whose
        durable record cannot be verified is NOT recovered — it is surfaced as
        unrecoverable and left parked, because silently re-driving an instance whose
        state failed integrity checks is precisely the failure this boundary exists to
        prevent (ADR §8 row 7).
        """


@runtime_checkable
class DurableStoreBundle(Protocol):
    """The three Agent Runtime persistence Protocols, supplied together by one engine
    integration so they share a transaction boundary.

    Agent Runtime already defines the Protocols
    (``CheckpointStore``, ``RuntimeEventStore``, ``RuntimeStateStore``); this bundle
    adds nothing to their surface. It exists so a composition root cannot accidentally
    mix a durable checkpoint store with an in-memory event store, which would produce
    a checkpoint whose events are gone after a restart.
    """

    @property
    def checkpoint_store(self) -> Any:
        """A ``CheckpointStore`` implementation. See ADR §5.1."""

    @property
    def event_store(self) -> Any:
        """A ``RuntimeEventStore`` implementation. See ADR §5.2."""

    @property
    def state_store(self) -> Any:
        """A ``RuntimeStateStore`` implementation. See ADR §5.3."""

    @property
    def is_production_authoritative(self) -> bool:
        """True only for a durable, integrity-checked backend.

        Mirrors the posture flag already ratified for Risk Authority persistence
        (``ADR_RISK_AUTHORITY_DURABLE_PERSISTENCE_SCOPING.md`` D-5). A production
        composition root must refuse a bundle that returns False; the in-memory
        reference bundle must never return True.
        """
