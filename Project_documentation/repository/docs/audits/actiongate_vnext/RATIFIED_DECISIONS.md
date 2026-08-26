# ActionGate vNext — Ratified Decisions

**Date:** 2026-08-26
**Scope:** Clock authority for replayed scenarios. No ActionGate policy semantics
are changed here, and CABP is out of scope.

---

## D1 — The scenario clock is authoritative for a replayed scenario

**Decision `[R]`:** A replayed scenario has exactly one time domain: the frozen
scenario clock the run's DGM services are built from. Every collaborator that
stamps or compares a time within that run — the CER binding service, the
execution adapter, and the ActionGate control-plane adapter alike — must read
that clock. The wall clock is not a permitted source of time inside a replay.

**Consequence:** `ActionGovernanceControlPlaneAdapter`'s default
(`_default_clock` → kernel `utc_now`) is correct for live operation and wrong
for every replay harness. Harnesses must inject the clock explicitly; the
default is never the right answer inside one.

**Rationale:** the value being compared is the run's own CER expiry, which the
run itself minted on the frozen clock. Comparing it against the wall clock
compares two unrelated instants, and makes a replay's verdict a function of the
calendar date the suite happens to run on. Determinism is the point of the
harness.

---

## Regression found while settling these items

**`[V]` Symptom.** 84 tests failed across `enterprise_validation_pilot`,
`comparative_governance_benchmark` and `provider_heterogeneity_validation`.

**`[V]` Cause.** Those harnesses build their CER on a frozen scenario clock
(`make_clock` → 2026-01-01T00:00:00Z, so `expires_at` is 2026-01-01T01:00:00Z)
while constructing `ActionGovernanceControlPlaneAdapter` with its default wall
clock — e.g. `provider_heterogeneity_validation/runners/workflow.py:149`. The
adapter stamps `authorized_at = now_wall` and `expires_at = now_wall +
validity`; `ExecutionService.create_execution_intent` then compares that stamp
against the scenario clock and raises `AuthorizationExpiredError`
(`packages/capabilities/decision-authority/src/ugence_decision_authority/services/execution_service.py:129`).

**`[V]` Latency of the fault.** The failure is date-dependent, not
deterministic: it appears whenever the wall clock sits on the wrong side of the
scenario clock. Reproduced by pinning the wall clock to 2025-06-01 — 62 failures
in the pilot, a collection-time error in the benchmark, 3 in heterogeneity
validation.

**`[V]` Resolution — control-plane adapter.** Under D1, the scenario clock is
injected at all three adapter construction sites:
`enterprise_validation_pilot/composition/root.py`,
`comparative_governance_benchmark/strategies/_actiongate_support.py` (the seed
now flows in from `strategies/action_only.py`), and
`provider_heterogeneity_validation/runners/workflow.py`. ActionGate policy
semantics are untouched.

**`[V]` Resolution — residual collaborators.** The adapter was not the only
collaborator left on a default wall clock. Ten further sites now take the
scenario clock, closing D1 across the three trees:

| Collaborator | Sites |
| --- | --- |
| `AuditService` | `enterprise_validation_pilot/composition/root.py`, `comparative_governance_benchmark/runners/dgm.py` |
| `ActionRequestValidationService` | same two files |
| `ExecutionValidationService` | same two files |
| `build_execution_adapter` | `comparative_governance_benchmark/strategies/{action_only,assertion_only,no_governance}.py`, `provider_heterogeneity_validation/runners/workflow.py` |

Only the audit service and the control-plane adapter reached a replay's
*outcome*; the rest stamped times that no assertion reads today. They are
injected anyway, because D1 is a property of the run, not of whichever fields
the current result schema happens to expose.

**`[V]` Guard.** Each tree carries `tests/test_clock_domain.py`. The scan is no
longer single-class: for every call site under the tree it resolves the callee
to the real object through that module's own imports and rejects the site when
the object's signature has a `clock` parameter and the call passes none. That
covers the kernel services, the audit service, both validation services and the
execution adapter, and it will cover a collaborator that grows a clock later.
Factory-mediated construction is covered from both ends — a factory that itself
takes a `clock` is a collaborator, so its own call sites must pass one, while
the constructor it mediates is exempt because the clock reaches it through a
forwarded mapping the AST cannot read. A companion test asserts the scan still
resolves the collaborators it is meant to guard, so a resolver that silently
matched nothing cannot pass.

**`[V]` Skew seam.** The replay guard moves three seams together, since a wall
clock reaches a replay three ways: the kernel clock function
`ugence_decision_authority.common.utc_now`; the parameter defaults that *bound*
that function at import time (a collaborator built without `clock=` holds the
original object in `__init__.__kwdefaults__`, where a module-attribute patch
cannot reach it — 14 kernel classes); and the framework adapter's lazily built
kernel cache, `action_to_control_plane._KERNEL["utc_now"]`. A third test asserts
the seam actually moves all three, so the replay guard cannot pass vacuously.
Removing any injection fails the scan; removing the adapter's injection also
fails the replay with the original `AuthorizationExpiredError`.

**`[V]` State.** 283 tests pass across the three trees (271 pre-existing, 12
guards), with the wall clock at its true value and pinned to 2025-06-01 — the
skew that originally reproduced the regression.

---

## The 16 `Field(default_factory=utc_now)` model defaults need no injection seam

**`[V]` Finding.** The kernel carries 16 pydantic fields defaulting to
`utc_now`. Instrumenting all 16 and replaying every scenario across the three
trees (990 results) shows **one** default ever fires:
`ports/linked_record.py:45`, `LinkedRecordSnapshot.created_at` — 2,580 times,
and from the harnesses' own `_NeutralLinked` stub, not from kernel code. The
other 15 never fire: each governed service supplies the timestamp explicitly
from its injected clock, so the field default is unreachable on the governed
path.

**`[V]` Consequence.** Re-pinning all 16 defaults to 2025-06-01 and replaying
leaves all 990 results identical. `LinkedRecordSnapshot.created_at` is read
nowhere in the kernel — no service, port or policy compares it — so the one
default that does fire cannot move a verdict.

**`[R]` Recommendation.** No seam. Adding `clock=` plumbing to 16 value objects
would widen the kernel's construction surface to inject a value that is either
never produced or never read, and the D1 guard already fails any *service* that
starts reading a wall clock. If a future field default becomes load-bearing, the
fix is to have the owning service pass the instant explicitly — which is how the
other 15 are already correct — not to make the models clock-aware.
