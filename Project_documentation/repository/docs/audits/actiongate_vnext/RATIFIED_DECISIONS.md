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

## D1 applicability — the rule binds a composition root, not a tree

**Decision `[R]`:** D1 applies at composition-root granularity. A composition
root that injects a clock into any Decision Authority or
governance-provider-framework collaborator must inject one into *every*
clock-capable collaborator it wires. A root that injects nowhere is not replaying
under an injected clock, and D1 says nothing about it.

A **composition root** is the top-level definition that does the wiring: a class,
a module-level function, or the module body for wiring done at import time.
Definitions nested inside one of those belong to it — so `PilotComposition`, which
builds its execution adapter in `__init__`, its control plane in `control_plane`
and its DGM bundle in `build_dgm`, is one root, not three.

**Rationale — why roots and not whole trees.** The rejected alternative was to
require every clock-capable construction anywhere under a tree to pass a clock.
That rule is unsound outside a replay harness, and measurably so. Applied to the
surfaces that must stay silent it fires 78 times on code that is correct as it
stands `[V]`:

| Surface | Sites the whole-tree rule would reject |
| --- | --- |
| `packages/providers/actiongate/tests` | 12 |
| `packages/providers/tap/tests` | 3 |
| `packages/governance-provider-framework/tests` | 16 |
| `packaging/external_consumer` | 12 |
| `packages/products/ai-hiring/tests` | 35 |

None of those is a defect. A conformance harness, a packaging smoke test and an
external-consumer sample all construct the kernel the way a consumer would —
on its defaults — and that is precisely what they exist to demonstrate. The
whole-tree rule cannot distinguish "this code forgot the scenario clock" from
"this code is not replaying a scenario at all", because the distinction is not a
property of a file's location.

It *is* a property of a composition root. Injecting a clock is the act that
declares a root to be replaying in a chosen time domain; once a root has made
that declaration, a sibling collaborator left on the wall clock is a genuine
second time domain inside one run, which is the fault D1 exists to prevent. A
root that never injects has made no such declaration and is judged by its own
tests, not by this one.

`packages/products/ai-hiring/tests/test_execution_binding.py` is the case that
settles the wording `[V]`. Its two expiry tests deliberately run on **two**
clocks — `_authorized_with_clocks` anchors the binder, the control plane and the
authorization service at `t0`, and each test then builds an `ExecutionService`
at `t_late` to prove that an authorization, or a CER, that was valid at submit
time blocks execution once it expires. Every collaborator in every one of those
roots is injected, so the rule is satisfied: D1 requires one *injected* clock
domain per root, not one *instant* per test. The same file's
`test_constrained_authorization_is_reflected_in_intent` injects nowhere and is
silent. The whole-tree rule would have rejected both halves of that file.

**Consequence `[V]` — the residual the granularity accepts.** A root holding a
single clock-capable collaborator cannot be internally inconsistent, so removing
its one injection makes the root silent rather than offending. Six roots across
the three trees hold exactly one such site; mutating each in turn (drop `clock=`,
run that tree's four guards) separates them:

| Sole-site root | Mutation caught by |
| --- | --- |
| `comparative_governance_benchmark/strategies/_actiongate_support.py:resolve_actiongate` | the replay body — the adapter reaches the verdict |
| `enterprise_validation_pilot/composition/engines.py:build_execution_adapter` | nothing (see below) |
| `comparative_governance_benchmark/runners/execution.py:build_execution_adapter` | nothing (see below) |
| `comparative_governance_benchmark/strategies/no_governance.py:NoGovernanceStrategy` | nothing |
| `comparative_governance_benchmark/strategies/assertion_only.py:AssertionOnlyStrategy` | nothing |
| `comparative_governance_benchmark/strategies/action_only.py:ActionOnlyStrategy` | nothing |

The three strategy classes are the residual this granularity introduces: each
wires exactly one clock-capable collaborator, `build_execution_adapter`, so
dropping its `clock=` leaves the root silent, and the adapter's stamps reach no
field the replay body compares. The whole-tree rule would have caught them — at
the cost of the 78 false rejections above.

The two `build_execution_adapter` bodies are a different and pre-existing blind
spot: their injection is the forwarding step `extra["clock"] = clock`, which the
factory-mediation exemption deliberately does not read. That exemption is
unchanged by this decision and would be equally blind under the whole-tree rule.

Everything else is caught. Dropping `clock=` at the control-plane adapter, the
audit service, either validation service or any kernel service fails the scan;
dropping the pilot's or the heterogeneity runner's adapter injection fails the
replay body as well.

This residual is the price of the property that keeps the guard silent on the
five surfaces above: a rule that fires on a root with one collaborator is the
whole-tree rule again. It is bounded and named, not open-ended — any of the
three that grows a second clock-capable sibling in its root falls back under the
scan immediately.

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

**`[V]` Guard.** One implementation, three trees:
`enterprise_validation_pilot/tests/clock_domain_guard.py` — hosted in the pilot
because the benchmark and the heterogeneity runner already depend on it and the
reverse dependency does not exist. It carries the parts that do not vary: the
call-site scan that implements the applicability rule above, and the skew seam.
Each tree's `tests/test_clock_domain.py` keeps what does vary — its own replay
body — and re-exports the shared guards as its own tests, so the count is
unchanged at four per tree.

The scan is not single-class: for every call site under the tree it resolves the
callee to the real object through that module's own imports, groups the sites by
composition root, and rejects a site whose object's signature has a `clock`
parameter and whose call passes none — but only inside a root that hands an
injected clock to an authority collaborator elsewhere. That covers the kernel
services, the audit service, both validation services and the execution adapter,
and it will cover a collaborator that grows a clock later. A tree-owned factory
counts as an authority collaborator when its own body constructs one — which is
how `build_execution_adapter` triggers the rule for the roots that wire it.
Factory-mediated construction is covered from both ends: a factory that itself
takes a `clock` is a collaborator, so its own call sites must pass one, while the
constructor it mediates is exempt because the clock reaches it through a
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
Removing an injection fails the scan wherever the rule applies (see the residual
named above); removing the pilot's adapter injection also fails the replay body.

**`[V]` Silence off the harnesses.** Running the shared scan over the surfaces
the rule must not disturb returns no offender on any of them:
`packages/providers/actiongate/tests`, `packages/providers/tap/tests`,
`packages/governance-provider-framework/tests`, `packaging/external_consumer`,
and the whole of `packages/products/ai-hiring/tests` — including
`test_execution_binding.py`, whose two-clock expiry tests are deliberate and
fully injected.

**`[V]` State.** 283 tests pass across the three trees (271 pre-existing, 12
guards — four per tree, unchanged by the consolidation), with the wall clock at
its true value and pinned to 2025-06-01, the skew that originally reproduced the
regression.

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
