# DBOS durable execution — integration scoping

**Status: RATIFIED — DBOS is the initial durable-execution engine by owner ruling
OD-3 (§9, 2026-09-05).** The ruling rests on every row of the §8 matrix passing in CI
(§8A). Ratified means that and only that: not pilot-validated, not
production-certified, not approved for any live system. This record fixes what the
implementation must do (roadmap item GAS-2; see
`Project_documentation/repository/ugence_platform/UGENCE_PRODUCTIZATION_ROADMAP.md`
§11). Beyond the ratified claim, no document, README or release note may describe the engine
integration as implemented, durable, exactly-once, distributed-safe or
production-ready.

**Evidence labels.** `[V]` verified against this repository at the cited symbol or
`file:line`; `[I]` architectural inference; `[R]` an owner decision still required;
`[G]` an unresolved gap. Every statement about future behaviour is written in a
conditional or future tense: where this document says *would*, *must* or *will*,
nothing exists yet.

---

## 1 — The question

Agent Runtime coordinates a governed workflow correctly in one process and says so
plainly: it is **not distributed-safe, not exactly-once, not live-verified, not
pilot-validated and not production-ready** `[V]`
(`packages/runtime/agent-runtime/README.md:36`), and its only persistence
implementations are in-memory references behind three Protocols `[V]`
(`.../persistence/interfaces.py`, `.../persistence/in_memory.py`). A durable engine
is what turns that coordination into something that survives a crash.

> **The load-bearing question: what must a durable engine be allowed to own, so that
> a crash or a retry can never replay a consequential provider call without the
> governance hook clearing it again?**

The answer this record fixes: **the engine owns scheduling and recovery, and nothing
else.** It never holds governance state, never decides whether a step may run, and
never re-drives a step past the hook. Every retry re-enters the same Agent Runtime
transition and therefore re-crosses the same governance boundary.

---

## 2 — Ratified decisions (owner, this programme)

These are settled and are not reopened by this record.

| # | Decision |
|---|---|
| **R-1** | **DBOS is the initial standalone durable-execution engine**, ratified for use only after it passes the complete matrix in §8. Until then its status is *candidate*. |
| **R-2** | **Temporal is the future regulated-enterprise adapter.** The execution adapter must make that swap possible without touching Workflow IR, governance state or receipts (§7). |
| **R-3** | **Workflow IR and governance state are always owned by Ugence.** The engine owns scheduling and recovery only. Agent Runtime owns proposal binding, the governance hook, budgets, checkpoints and receipts. The engine is never the source of truth for governance state. |
| **R-4** | **The governance hook runs inside the durable step.** The engine executes Agent Runtime transitions; Agent Runtime calls the hook before any provider invocation, so a retry can never replay a consequential call without re-clearing it (§6). |
| **R-5** | Both the engine and Agent Runtime persist to the same Postgres, subject to the boundary in §3 and the open decision OD-2 in §9. |

---

## 3 — Ownership boundary

The column that matters is the third: what each side is **forbidden** to do. A
boundary stated only as a list of responsibilities drifts; stated as prohibitions it
can be tested.

| Concern | Owner | The other side must never |
|---|---|---|
| Step scheduling, dispatch, retry timing, worker recovery after crash | **DBOS engine** | Agent Runtime must never schedule its own retries or hold a worker loop; it advances when driven. |
| Which step ran, how many times, and what the durable log says about it | **DBOS engine** | Agent Runtime must never read engine internals to decide a governance outcome. |
| `TransitionProposal` construction, deep-freezing and fingerprinting | **Agent Runtime** `[V]` (`models/proposal.py`) | The engine must never construct, mutate, re-fingerprint or reorder a proposal. |
| Calling `GovernanceHook.evaluate` and obeying the disposition | **Agent Runtime** `[V]` (`runtime/engine.py:590`) | The engine must never call the hook, cache its result, or skip it on a retry. |
| `validate_clearance` — fingerprint, binding reference, correlation, expiry, last-mile authority recheck | **Agent Runtime** `[V]` (`governance/decisions.py`) | The engine must never treat its own successful step completion as evidence of clearance. |
| The governance decision itself (`GovernedExecutionDecision`, `RiskAuthorizationEnvelope`, `DecisionRecord`) | **Governance packages** `[V]` (`packages/integration/risk-authority-runtime/`, `packages/risk_authority/`, `packages/capabilities/decision-authority/`) | Neither the engine nor Agent Runtime may mint, widen, extend or re-date any of them. |
| Checkpoints, runtime events, runtime state | **Agent Runtime Protocols**, DBOS-backed implementations `[V]` (`persistence/interfaces.py`) | The engine must never write these tables through its own API; it writes them only by executing an Agent Runtime transition. |
| Budgets and receipts | **Agent Runtime / governance packages** `[V]` (`orchestration/budgets.py`) | The engine must never settle, reserve or release a budget on its own recovery path. |
| Workflow IR — authoring, compilation, versioning | **Ugence compiler** `[V]` (`packages/tooling/policy-workflow-compiler/`, `compile_policy_pack`) | The engine must never interpret, rewrite or version Workflow IR; it receives an opaque workflow id and a definition digest. |
| The wall clock used for clearance expiry | **The adapter, injected into `AgentRuntimeConfig.clock`** (§6.4) | Neither side may compare a `valid_until` against a process-local monotonic reading. |

**The one-sentence test.** If the durable log were deleted and the workflow re-driven
from its last checkpoint, every consequential call would be re-proposed, re-cleared
and re-validated, and nothing about permission would be recovered from the engine.

---

## 4 — The execution adapter interface

Agent Runtime depends on these Protocols; the DBOS package implements them; a future
Temporal package implements the same ones (R-2). **Docstrings only — no
implementation is specified or authorized here.** These would live in a new
integration package (`packages/integration/durable-execution/`), never inside
`packages/runtime/agent-runtime`, whose import boundary is CI-enforced `[V]`
(`packages/runtime/agent-runtime/tests/test_import_boundaries.py`).

```python
"""Neutral durable-execution boundary.

The adapter lets an external engine DRIVE Agent Runtime transitions durably. It
carries no governance concept: no disposition, no envelope, no clearance, no policy,
no credential. Everything it moves across the boundary is either a neutral identifier
or an opaque, already-governed Agent Runtime artefact.

An adapter that needed to understand a governance type in order to schedule correctly
would be the wrong shape, and would be rejected in review on that ground alone.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable


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
        (§8, row 9) rather than reinterpret persisted state under new semantics.

        Idempotent on ``instance_id``: a duplicate start returns the existing handle
        and must not create a second instance or reset any state.
        """

    def advance(
        self,
        *,
        instance_id: str,
        attempt_token: str,
    ) -> DurableStepOutcome:
        """Durably execute ONE Agent Runtime advance and record that it happened.

        This is the durable step, and the whole governance chain lives inside it:
        proposal construction, ``GovernanceHook.evaluate``, ``validate_clearance``,
        the last-mile authority recheck, provider invocation and the resulting state
        transition all occur within this call (§6). The engine may retry this call
        freely; every retry re-enters the full chain.

        ``attempt_token`` identifies the engine's delivery attempt. It is recorded for
        observability and duplicate detection. It is deliberately NOT part of the
        Agent Runtime proposal fingerprint or idempotency key — a retry must produce
        the SAME proposal identity, so that a hook can recognise it as the same
        proposed action rather than a new one (§6.2).
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
        the governance boundary is crossed again from the beginning (§8, row 8).
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
        prevent (§8, row 7).
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
        """A ``CheckpointStore`` implementation. See §5.1."""

    @property
    def event_store(self) -> Any:
        """A ``RuntimeEventStore`` implementation. See §5.2."""

    @property
    def state_store(self) -> Any:
        """A ``RuntimeStateStore`` implementation. See §5.3."""

    @property
    def is_production_authoritative(self) -> bool:
        """True only for a durable, integrity-checked backend.

        Mirrors the posture flag already ratified for Risk Authority persistence
        (``ADR_RISK_AUTHORITY_DURABLE_PERSISTENCE_SCOPING.md`` D-5). A production
        composition root must refuse a bundle that returns False; the in-memory
        reference bundle must never return True.
        """
```

---

## 5 — Mapping the three stores onto DBOS and Postgres

Agent Runtime's Protocols are small and already exactly right for a relational
backend `[V]` (`persistence/interfaces.py`): `CheckpointStore.put`/`latest`,
`RuntimeEventStore.append`/`events`, `RuntimeStateStore.save`/`load`. Nothing in
their surface changes. What follows is what a Postgres implementation must satisfy.

### 5.1 `CheckpointStore` — append-only checkpoint history

One row per checkpoint, keyed `(instance_id, seq)`, `seq` monotonically increasing
per instance under a unique constraint. `put` inserts; it never updates. `latest`
reads the highest `seq`.

Both digests are stored as written and **verified on read**: a checkpoint carries a
base `digest` over the coordination payload and a separate `extension_digest` over
the canonical-execution-state extension `[V]`
(`persistence/checkpoints.py`, `Checkpoint.verify`, `Checkpoint.verify_extension`,
`Checkpoint.validate_execution_states`). A row failing either check is **not
repaired and not skipped** — the instance is surfaced as unrecoverable. The
`checkpoint_version` column is read before parsing, so an unknown future version
refuses rather than being interpreted under today's semantics `[V]`
(`SUPPORTED_CHECKPOINT_VERSIONS`).

### 5.2 `RuntimeEventStore` — append-only event log

One row per event, keyed `(instance_id, seq)` with the same unique constraint, plus
the engine's `attempt_token` and `engine_id` as observability columns that no read
path branches on. `events` returns rows in `seq` order. A duplicate engine delivery
that produces a semantically identical event still appends — the log records what the
runtime did, including that it re-did it — and the duplicate is detectable by
`attempt_token`, never suppressed silently.

### 5.3 `RuntimeStateStore` — the single resume point

One row per `instance_id`, updated in place under `SELECT ... FOR UPDATE`. This is the
row an engine worker takes a lock on to claim an instance, and it is what makes
"one instance is driven by one worker at a time" a database property rather than a
convention `[V]` — the property Agent Runtime today explicitly does not provide
(`README.md:36`, "not distributed-safe").

### 5.4 Transaction boundary

One `advance` writes: the state row, one checkpoint row, N event rows, and the engine's
own step record. **These commit together or not at all.** If DBOS keeps its step
record in the same Postgres database, the honest way to get atomicity is a single
transaction spanning both; if it does not, the two can diverge under a crash between
commits. Which of these DBOS actually offers is the single most important thing to
establish before implementation, and it is open decision **OD-1** (§9). The matrix
row that would settle it is §8 row 3.

### 5.5 What is NOT stored here

No governance state. No `GovernedExecutionDecision`, no `RiskAuthorizationEnvelope`,
no `IssuedPolicyRecord`, no `DecisionRecord`. Checkpoints carry only coordination
state and neutral references, and they hold no credentials, no provider outputs and
no authority by explicit design `[V]` (`persistence/checkpoints.py` module docstring).
Governance packages keep their own ratified stores; see OD-2 (§9) for the tension
this creates with R-5.

---

## 6 — The hook inside the durable step

### 6.1 Why inside

Agent Runtime already runs the whole chain — governance evaluation, exact-action
clearance, provider invocation and the state transition — inside a single bounded
advancement quantum, specifically so that nothing can interleave between a CLEAR and
the invocation it cleared `[V]` (`runtime/engine.py`, `advance_workflow` docstring:
"The governance→exact-action→provider chain runs entirely WITHIN a single quantum").
The durable step is drawn around exactly that quantum. Nothing smaller is safe; a
step boundary placed *between* clearance and invocation would let the engine's own
retry replay the invocation while re-using a stale clearance, which is the failure
this entire record exists to prevent.

Bounded advancement also never self-resolves a restrictive disposition `[V]` (same
docstring: it "never self-resolves a governance HOLD or ESCALATE"). So a parked
instance stays parked no matter how many times the engine drives it — the engine
cannot grind a HOLD into a CLEAR by retrying.

### 6.2 Idempotency keys survive retries unchanged

Agent Runtime derives the key as `f"{instance.instance_id}:{ti.task_id}"` `[V]`
(`runtime/engine.py:498`). It contains **no attempt number and no timestamp**, which
is the property that makes it usable across engine retries: attempt 1 and attempt 7 of
the same task produce the *same* idempotency key. A hook or downstream provider can
therefore recognise the repeat as the same intended action rather than a second one.

The adapter must not touch this. `attempt_token` is deliberately excluded from the key
and from the fingerprint (§4). An adapter that mixed the engine's attempt identity into
either would make every retry look like a brand-new action, defeating duplicate
suppression at the provider and inflating any budget the action consumes.

### 6.3 Fingerprints and correlation survive retries unchanged

`TransitionProposal.build` fingerprints over workflow, instance, task, provider,
operation, deeply-frozen canonical arguments, idempotency key and correlation id `[V]`
(`models/proposal.py`, `compute_fingerprint`). Every one of those is either persisted
in the checkpoint or recomputed deterministically from it, so **the proposal
reconstructed after a crash fingerprints identically to the one lost**. That identity
is what lets a CLEAR issued before the crash be recognised — or correctly refused —
after it.

Two existing checks then do the work, and neither is relaxed for durability:

- `validate_clearance` requires the CLEAR to carry `proposal_fingerprint` equal to the
  exact proposal, at least one non-empty binding reference, and a
  `correlation_reference` equal to the proposal's correlation id when one is present;
  anything missing or mismatched fails closed `[V]` (`governance/decisions.py`).
- The invocation is **re-fingerprinted immediately before the provider call** and
  compared, so the permission consumed provably applies to the exact call made `[V]`
  (`runtime/engine.py:615-624`, `models/proposal.py` module docstring).

### 6.4 The clock is the sharp edge `[G]`

`AgentRuntimeConfig.clock` defaults to `time.monotonic()` `[V]`
(`config.py:33-35`), and that reading is what `validate_clearance` compares against a
clearance's `valid_until` `[V]` (`runtime/engine.py:547-548`). **`time.monotonic()` is
process-local**: after a crash and recovery in a new process its origin is arbitrary,
so a `valid_until` minted before the crash and compared after it is being compared
against an unrelated number. The comparison would not merely be imprecise — it would
be meaningless, and could read as *not yet expired* for an arbitrarily long outage.

This is a real gap, not a hypothetical one, and it is the reason the matrix has two
clock rows rather than one. Two things follow, both mandatory for the adapter:

1. A durable deployment **must** inject a wall-clock (epoch-seconds) `clock`. The
   monotonic default is safe only for a single-process run and must be refused by the
   production composition root.
2. Any evaluator that mints `valid_until` must mint it on the **same time base**. The
   engine's clock, the runtime's clock and the evaluator's clock being three different
   things is exactly the skew condition row 11 tests.

Neither point changes Agent Runtime: `clock` is already an injection point on a frozen
config dataclass `[V]` (`config.py:64`). The adapter supplies the right callable; the
runtime is untouched.

### 6.5 Revocation and epoch advance mid-workflow

The mechanism already exists and is unused by default: `AgentRuntimeConfig`
`authority_recheck` is an optional last-mile callable, run only **after** every binding
check has passed and immediately before the irreversible effect, that re-verifies the
authority the CLEAR rested on is still valid — not expired, not revoked, not
stale-epoch `[V]` (`config.py:70`, `governance/decisions.py`, RA-6 §8 "last-mile
TOCTOU"). It cannot mint anything; it can only confirm or fail closed. A hook that
raises or returns a malformed shape is normalized to a fail-closed rejection carrying
`GOVERNANCE_AUTHORITY_RECHECK_ERROR` `[V]` (same module).

**A durable deployment must configure it.** In a single-process run a long gap between
clearance and effect is unusual; under a durable engine, retries and recovery make that
gap routine, and an unconfigured recheck means a revocation landing mid-workflow is
never noticed. This is a configuration requirement of the adapter, not a change to the
runtime.

---

## 7 — What Temporal must implement to replace DBOS

The swap is a package substitution at the composition root and nothing else. Temporal
qualifies when, and only when, all of the following hold.

1. **The same Protocols, unchanged.** `DurableExecutionAdapter`, `DurableStepOutcome`
   and `DurableStoreBundle` as written in §4, with no added method, no added
   parameter, and no widened return type. A Protocol that had to grow for Temporal was
   the wrong Protocol for DBOS.
2. **The step boundary is the same quantum.** One `advance` = one bounded advancement
   of Agent Runtime, with the governance chain wholly inside it (§6.1). Temporal's
   activity/workflow split must not be allowed to place a boundary between clearance
   and invocation — in Temporal's model the entire quantum is one **activity**, never a
   workflow-level sequence of finer activities.
3. **Determinism stays outside the engine.** Temporal replays workflow code; Agent
   Runtime's advance must therefore be an activity, not replayed workflow logic. Any
   design in which Temporal replay re-executes the governance hook as part of history
   replay is disqualified outright.
4. **Zero diff in the protected surface.** Adding the Temporal adapter must change no
   file under `packages/runtime/agent-runtime/`, no Workflow IR type, no governance
   package, and no receipt shape. This is verified by diff at the exit gate, not
   asserted.
5. **The same matrix passes.** Every row of §8, against Temporal, with its own
   evidence. A row that passed for DBOS is not inherited.
6. **The store bundle is separable.** Temporal keeps its own history store; the three
   Agent Runtime stores must remain the Postgres implementations of §5, unchanged.
   Temporal history is never permitted to become the source of truth for checkpoints,
   events or runtime state (R-3).
7. **Clock discipline is preserved.** §6.4 applies identically: a wall-clock is
   injected, and the evaluator's time base matches.

**What Temporal buys, stated honestly** `[I]`: mature multi-region operation, a
supported managed offering, and an ecosystem of regulated-industry deployments. It
does not buy any governance property this record specifies — every fail-closed
behaviour in §8 is provided by Agent Runtime and the governance packages, and would be
identical under either engine. The engine choice is an operations decision, and
presenting it as a compliance one would be a false claim.

---

## 8 — Durability and failure matrix (the ratification gate)

**DBOS is a candidate until every row here has passing evidence in CI against a real
local Postgres.** A row is not satisfied by a unit test with a mocked engine: the
crash rows require a process actually killed, and the Postgres rows require the
database actually stopped. A row whose evidence is "by inspection" is not satisfied.

Throughout, *consequential* means a transition that reaches a provider.

| # | Failure | Expected behaviour (fail-closed) | Evidence that proves it |
|---:|---|---|---|
| 1 | **Crash before the provider call** — worker killed after the proposal is built, before or during `evaluate`. | No provider was invoked and none may be. On recovery the instance re-drives from the last checkpoint, rebuilds a proposal with an **identical fingerprint** (§6.3), and calls the hook again. A CLEAR obtained before the crash is not reused from any engine record. | Kill a worker at an injected fault point; assert zero provider invocations recorded across both processes; assert the pre-crash and post-crash proposal fingerprints are equal; assert `evaluate` call count is exactly 2 (once per process). |
| 2 | **Crash during the provider call** — worker killed after invocation is issued, before any result is recorded. | The runtime must not assume success and must not assume failure. The instance re-drives, re-proposes, **re-clears**, and re-invokes under the *same* idempotency key `[V]` (`engine.py:498`), leaving deduplication to the provider. No checkpoint claims a completed transition. | Kill mid-invocation against a provider that records every call with its idempotency key; assert two calls carrying one identical key; assert the hook ran again before the second; assert no checkpoint records completion for the lost attempt. |
| 3 | **Crash after the provider call, before the commit** — the effect happened; the durable record did not. | The *most dangerous* row. Recovery must re-drive and therefore re-invoke; correctness depends on the provider treating the repeated idempotency key as a duplicate. The runtime must never infer from an engine step record that a governance clearance was consumed. Whether the engine step record and the Agent Runtime tables commit atomically is **OD-1** (§9); if they cannot, this row's expected behaviour is the conservative one just stated, and that must be documented as a residual, not hidden. | Kill between effect and commit; assert the provider saw the same idempotency key twice and reports the second as duplicate; assert the checkpoint chain has no gap and every checkpoint verifies; assert the second attempt crossed the hook. Additionally: assert whether the engine's step record and the runtime state row are ever observed in disagreement, and record the answer. |
| 4 | **Duplicate delivery / retry of a consequential step** — the engine delivers `advance` twice concurrently or in sequence for one instance. | Exactly one worker holds the instance (`SELECT ... FOR UPDATE` on the state row, §5.3); the loser does not execute. A sequential retry re-crosses the hook. Two deliveries never produce two clearances treated as independent permission. | Two workers, one instance, contended `advance`; assert exactly one executes and the other returns without progressing; assert hook invocation count equals executed-advance count, never less; assert the event log contains both attempt tokens (the duplicate is recorded, not suppressed). |
| 5 | **Clearance validity expires during a retry** — the CLEAR carried `valid_until`, and the retry lands after it. | Fail closed: `validate_clearance` rejects with `GOVERNANCE_CLEAR_EXPIRED`, expiry being **inclusive** — at `now == valid_until` the clearance is already expired `[V]` (`governance/interfaces.py` `GovernanceEvaluation` docstring). No provider call. The instance parks; it does not fail the workflow silently and does not proceed. | With an injected wall-clock, issue a clearance with a short `valid_until`, delay past it, retry; assert the rejection reason code is exactly `GOVERNANCE_CLEAR_EXPIRED`; assert zero provider invocations; assert the boundary case `now == valid_until` also rejects. |
| 6 | **Envelope revocation / epoch advance mid-workflow** — authority is revoked, or the epoch advances, between clearance and effect. | The configured `authority_recheck` (§6.5) fails closed at the last mile with `GOVERNANCE_CLEAR_AUTHORITY_STALE`; the provider is not invoked. A recheck that raises or returns a malformed shape yields `GOVERNANCE_AUTHORITY_RECHECK_ERROR` — never a permit `[V]` (`governance/decisions.py`). | Revoke between CLEAR and effect; assert `CLEAR_REJECTED_AUTHORITY_STALE` and zero invocations. Separately assert a raising recheck and a malformed-return recheck both reject. **Also assert the negative case: with `authority_recheck` unset, revocation goes unnoticed** — proving the configuration requirement is load-bearing and not decorative. |
| 7 | **Postgres unavailable** — the database is stopped mid-run and later restarted. | No advance proceeds while state cannot be durably written: an advance that cannot commit its checkpoint must not have invoked a provider. Instances become unrecoverable-and-parked, not silently in-memory. On restart, recovery resumes only instances whose checkpoints pass `verify()`, `verify_extension()` and `validate_execution_states()` `[V]`; a failing instance is surfaced, never repaired. | Stop Postgres mid-workflow; assert no provider invocation occurs during the outage; assert no in-memory fallback is used (the production bundle refuses `is_production_authoritative=False`); restart and assert recovery; corrupt one checkpoint row and assert that instance is reported unrecoverable rather than resumed. |
| 8 | **Concurrent instances contending for one budget** | The budget is settled exactly once per consumed action across concurrent instances, under a database constraint rather than in-process bookkeeping `[V]` — today's resource coordination is portfolio-local (`docs/AGENT_RUNTIME_LIMITATIONS.md:22`). Over-consumption fails closed: an instance that cannot reserve does not invoke. | N concurrent instances against a budget of K < N; assert exactly K invocations and N−K fail-closed refusals; assert no double settlement after a mid-run crash of a holder; assert the total consumed never exceeds K under repeated randomized interleavings. |
| 9 | **Pause and resume across a human decision spanning hours** | The instance parks on HOLD or ESCALATE and stays parked however often it is driven `[V]` (bounded advancement never self-resolves a restrictive disposition). A `signal` records the human decision as **data**; it grants nothing. On re-entry the boundary is crossed again from the beginning, and the clearance obtained hours earlier is not reused. | Park on ESCALATE; drive repeatedly over a simulated multi-hour span (wall-clock injected) and assert zero invocations and zero disposition changes; deliver a signal; assert the hook is called again and a *fresh* evaluation — not the stored one — decides. Assert the pre-pause and post-resume fingerprints are equal, so the human decided about the same action that then ran. |
| 10 | **Recovery after a workflow-definition version change** | Refuse, do not reinterpret. An instance started under `definition_digest` A must not be recovered under digest B; it is surfaced for an explicit operator decision. Independently, an unknown `checkpoint_version` refuses rather than being read under current semantics `[V]` (`SUPPORTED_CHECKPOINT_VERSIONS`). | Start under A, replace the definition with B, recover; assert a typed refusal naming both digests and zero invocations. Separately write a checkpoint with a synthetic future `checkpoint_version` and assert recovery refuses. Assert a legacy (version `"0"`) checkpoint still recovers, carrying no execution-state lineage rather than fabricating it. |
| 11 | **Clock skew between engine and evaluator** | Skew must never widen permission. With the evaluator ahead of the runtime, a clearance must not be honoured past its true expiry; with the runtime ahead, an early rejection is acceptable — the asymmetry is deliberate and is the fail-closed direction. A monotonic clock must be **refused** by the production composition root (§6.4). | Run the matrix's expiry cases with injected skew in both directions at several magnitudes; assert no combination yields an invocation after true expiry; assert skew in the safe direction produces refusal, never a permit. Assert a composition root configured with the default monotonic clock refuses to start in production mode — this is the test that closes the `[G]` in §6.4. |

**Rows 3, 6 (negative case), 7 (corruption case), 10 and 11 are the ones most likely
to be quietly skipped.** They are named here so that skipping one is visible.

---

## 8A — Verification record (GAS-2, 2026-09-05)

Implemented at `packages/integration/durable-execution` (`ugence-durable-execution`
0.1.0). The suite runs against a real PostgreSQL 16 server: the crash rows kill real
processes, and row 7 stops the real database.

**Result: 43 passed — all eleven rows green, none skipped.** `packages/runtime/agent-runtime`
is byte-unchanged and its own suite still passes (364 passed, 2 skipped).

### OD-1 is satisfied, and proven rather than inferred

| Case | Observed | What it establishes |
|---|---|---|
| SIGKILL with the transaction open | application write **absent**, step record **absent** | one transaction — two separate commits would leave exactly one |
| Success | both present | they commit together |
| Exception before commit | write rolled back; only an *error* outcome recorded afterwards | no success record survives a failed step |
| Replay of a committed step | body does not re-run | the recorded result replays, correctly, for work that already happened |

**The detail that would have made this gate vacuous.** `run_tx_step` writes its step
record **only inside a DBOS workflow context**; called directly, `in_wf` is False and the
transaction still commits but no step record is written. An adapter built the obvious way
would have had the transaction without the durable step and would have *appeared* to pass
OD-1 while testing nothing. Every mutating operation is therefore a `@DBOS.workflow()`
wrapping a `@datasource.transaction`; read-only operations stay on a plain transaction,
since a step record would record an attempt that changed nothing. §5.4 is read subject to
this.

### Three findings that change how the matrix reads

1. **Recovery never auto-runs.** Agent Runtime restores a recovered instance as PAUSED
   requiring explicit continuation, so a post-crash retry is deliberately two steps — an
   explicit resume, then an advance that re-crosses the boundary from the beginning.
   Rows 1–3 assert this rather than working around it. `[V]`
2. **Row 7 blocks rather than raising.** With Postgres down, DBOS's retriable-error loop
   backs off indefinitely, so an in-process advance never returns. Blocking is the
   correct behaviour — an advance that cannot commit its checkpoint must not proceed —
   but it has to be observed from outside, so the row attempts the advance in a child
   process under a hard timeout and asserts what did *not* happen while it blocked. `[V]`
3. **Attempts deliberately do not share a workflow id**, so DBOS never replays a
   recorded advance. Every attempt re-enters the runtime and re-crosses the hook; the
   step record's role here is atomicity and durable evidence, not replay. `[I]`

### The §6.4 clock gap is closed

`assert_durable_clock` refuses the runtime's monotonic default at construction, and row 11
asserts both the refusal and that skew never widens permission in either direction at
several magnitudes. The residual is stated, not papered over: detection recognises the
known default, and a deployment that hides a monotonic reading behind an unrecognisable
wrapper defeats the guard.

### Status: DBOS is RATIFIED (OD-3)

Every row is green in CI against a real PostgreSQL 16 on the runner. CI evidence: durable-execution-ci job 101254854185 (first green run on PR #1605) and job 101257085510 on `fe6f1591` (after the four review fixes): OD-1 5 passed; matrix rows 01–11 all PASSED, 29 passed, "No matrix row was skipped"; production-hook re-run 12 passed; boundaries and ADR conformance 12 passed; Agent Runtime unchanged, 364 passed.
Four defects found in review between those runs were fixed before the ruling: the
row-10 comparison could pass vacuously through a default digest; a budget refusal
aborted the enclosing transaction; `signal()` raced a concurrent advance for the
sequence key; the attempt token was never reset. `DBOS_ENGINE_STATUS` is `RATIFIED`,
asserted by the package suite together with the OD-3 record in §9.

---

## 8B — GAS-3: the production hook, and the matrix re-run (2026-09-05)

Implemented at `packages/integration/agent-runtime-governance`
(`ugence-agent-runtime-governance` 0.1.0). **68 passed.** Agent Runtime, RA-4.5
composition and the RA-6 status runtime are all byte-unchanged and their own suites
still pass.

### The projection

`GovernedExecutionDecision` → `GovernanceEvaluation`, bound to the exact proposal
fingerprint and correlation id, with Risk Authority's own `envelope_id` as the binding
reference. Total and non-broadening `[V]`:

| `FinalDisposition` | → | Runtime directive |
|---|---|---|
| `GRANT` | `CLEAR` | CONTINUE |
| `DENY` | `BLOCK` | STOP |
| `HOLD_NON_EXECUTABLE` | `HOLD`, or `ESCALATE` where an approval is required | WAIT / PAUSE |
| `ERROR_NON_EXECUTABLE` | `BLOCK` | STOP |
| anything else | `BLOCK` | STOP |

A GRANT carrying no `envelope_id` is **refused**, not given a minted identifier: there
would be nothing to bind the clearance to, and inventing one would make an unbindable
permission look bindable.

### Three widening paths, closed and tested `[V]`

1. **A str-enum look-alike.** `FinalDisposition` subclasses `str`, so `"GRANT"` compares
   equal to `FinalDisposition.GRANT` *and hashes identically* — a dict lookup or an `==`
   check accepts it. `isinstance` is checked first.
2. **A self-reported `executable`.** CLEAR requires GRANT *and* `executable is True`, so
   an object claiming `executable=True` beside a DENY is refused.
3. **An uninspectable decision.** `getattr(obj, name, default)` only swallows
   `AttributeError`. A decision whose `__getattr__` raised anything else propagated into
   the runtime's hot path — where a raising hook is indistinguishable from one that was
   never asked. **The adversarial suite caught this while being written**; every read is
   now guarded and the hook never raises.

### The recheck is wired, not rebuilt `[V]`

Risk Authority's status runtime already ships `make_pre_effect_recheck`, already in the
`(evaluation, proposal, now) -> (ok, reasons)` shape the `authority_recheck` seam
expects. Rebuilding it would duplicate authority-critical logic outside the package that
owns it. What was missing is the *resolver* — mapping a neutral proposal back to the
envelope its CLEAR rested on — so the hook records `fingerprint -> (envelope, tier)` on
clearing and `build_authority_recheck` supplies it.

Tested against genuine Ed25519-signed envelopes through the RA-6 scenario builder: a real
revocation and a real epoch advance are both caught at the commit point. This closes the
loop opened by §8 row 6's negative case.

### Matrix re-run with the production hook `[V]`

`packages/integration/durable-execution/tests/test_matrix_production_hook.py`, **12
passed**. The rows below ran with the real hook in place of `AllowAllGovernanceHook`.

| Row | With the production hook |
|---:|---|
| 1 · crash before the provider call | PASSING — hook re-consulted after recovery, identical fingerprint |
| 2 · crash during the provider call | PASSING — same idempotency key on retry |
| 3 · crash after the effect, before the commit | PASSING — advance transaction rolled back whole |
| 4 · duplicate delivery | PASSING — exactly one executes |
| 5 · clearance expiry | PASSING — **stronger**: expiry originates on the envelope and travels composition → epoch-seconds projection → `validate_clearance` |
| 6 · revocation, and the negative case | PASSING — both |
| 7 · checkpoint corruption | PASSING |
| 8 · budget contention | governance-independent — covered once in `test_matrix.py` |
| 9 · pause and resume | PASSING — **stronger**: ESCALATE is *derived* from a composed HOLD carrying a required approval, not injected |
| 10 · definition version change | governance-independent |
| 11 · clock skew and monotonic refusal | governance-independent |

The three exemptions are asserted by a test that inspects those rows' source for hook
dependence, so the gap in the count is proven rather than asserted. A baseline test also
confirms the production hook actually reaches CLEAR — otherwise the durability
assertions would pass vacuously by never clearing.

### Maturity: Core implemented `[V]`

Not pilot-validated, not production-certified. What stays blocked is unchanged by GAS-3:
Risk Authority `production_mode` still raises `ProductionContainmentError` `[G]`; **HOLD,
DEFER, ESCALATE and MANUAL_REVIEW still have no sink** `[G]` — the hook now emits them
faithfully and the runtime parks on them correctly, and there is still nowhere for a
human to see the parked instance; no credential broker exists `[G]`.

---

## 9 — Owner decisions (ruled 2026-09-05)

OD-1 and OD-2 were ruled by the repository owner before GAS-2 began. OD-3 was ruled on GAS-2's CI evidence after the review fixes. None is outstanding.

| # | Ruling |
|---|---|
| **OD-1** | **`REQUIRE_SINGLE_TRANSACTION`.** Atomic commit is a **DBOS ratification gate**, not a documented residual. The DBOS step record, the `RuntimeStateStore` update, the `CheckpointStore` append and the `RuntimeEventStore` appends must commit in **one supported Postgres transaction**. If DBOS cannot provide this, **DBOS remains a candidate and GAS-2 stops and reports the evidence** — a permanent split-commit residual is neither accepted nor engineered around. This *strengthens* what §5.4 and §8 row 3 previously contemplated: those passages are read subject to this ruling. |
| **OD-3** | **`RATIFY`** (2026-09-05). DBOS is promoted from *candidate* to *ratified as the initial engine* on the evidence in §8A: durable-execution-ci job 101257085510 on `fe6f1591`, every matrix row PASSED, no row skipped, production-hook re-run green, Agent Runtime unchanged. `DBOS_ENGINE_STATUS` is `RATIFIED`. Ratified establishes nothing beyond the matrix: not pilot-validated, not production-certified, no live execution, no credentials. |
| **OD-2** | **`COEXIST_WITH_BOUNDARY`.** Risk Authority and execution-reservation persistence stay on their separately ratified SQLite Posture B `[V]` (`ADR_RISK_AUTHORITY_DURABLE_PERSISTENCE_SCOPING.md` D-1). DBOS and the three Agent Runtime stores share Postgres. The two backends coexist behind an **explicitly documented consistency boundary**, stated in the adapter README. GAS-2 migrates and redesigns no governance store. §8 row 8's budget ledger therefore lives in the shared Postgres. |

### What OD-1 changes in this record

§5.4 previously left the atomicity question open and offered a conservative fallback
for §8 row 3. Under OD-1 there is no fallback: **row 3 is a gate**. The adapter must
demonstrate one transaction covering the engine's step record and all three store
writes, or GAS-2 halts. The row 3 evidence column is read accordingly — the clause
"if they cannot, this row's expected behaviour is the conservative one" is superseded
and is retained only to show what was rejected.

---

## 10 — Gaps that survive this record `[G]`

The Credential Broker (cloud-scaling Phase 5X) does not exist, so no live execution is
reachable regardless of engine `[V]` (capability pipeline Appendix B §B.6 ¶2). Risk
Authority `production_mode` raises `ProductionContainmentError` `[V]`
(`packages/risk_authority/src/risk_authority/domain/errors.py:19`). HOLD, DEFER,
ESCALATE and MANUAL_REVIEW have no sink, so §8 row 9's parked instance has nowhere to
be seen by a human until one is built. Registries are in-memory. Multi-region
consistency, HSM/KMS custody and key rotation are untouched here. The clock defect in
§6.4 is open until row 11 passes.

## 11 — Next step

GAS-2 and GAS-3 are implemented; their evidence is recorded in §8A and §8B, and OD-3
is ruled `RATIFY` (§9). GAS-4 (Studio v1) is the next build item; it is gated by SD-1
and SD-2, both already ruled.
