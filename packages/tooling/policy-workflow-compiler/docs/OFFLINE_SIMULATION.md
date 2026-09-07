# Deterministic Offline Simulation (PWC-P3C)

A simulation exercises a compiled release under one scenario's facts and records
what it observes. **It simulates; it never executes.**

## Two rulings

| Ruling | Decision |
| --- | --- |
| **P3C-1** | A run is **evidence, not a gate**. It never blocks compilation, and no compiler entry point accepts a `SimulationRun` — a test asserts that. Gating compilation on a simulation would put the simulator on the execution path. |
| **P3C-2** | A contradicted oracle is an `OracleComparison` **field on the run**, not a validation diagnostic: a disagreement is a property of one run against one scenario, not of the release. |

## What a run consumes and produces

Consumes a `CompiledReleasePackage` and one `TestScenario` or `ReplayCase`. Nothing
else — no clock, environment, filesystem, socket, registry or credential.

Produces a `SimulationRun`: the release digest it bound, an ordered `trace` of
`NodeObservation`s, the terminal state, reason codes, described audit events,
unreached nodes, the oracle comparison, and a `run_digest` that is a pure function
of all of it. **Replay is digest equality.**

## Observing without deciding

| Node kind | Observes | Never |
| --- | --- | --- |
| `AUTHORITY_CHECK` | "requires authority *A*" | that an actor holds it |
| `APPROVAL_GATE` | "requires approval by role *R*" | granting approval |
| `SEGREGATION_OF_DUTIES_GATE` | that the steps must differ | enforcing it |
| `ACTION_CLEARANCE_REQUIREMENT` | that clearance is required | clearing anything |
| `AUDIT_EMISSION` | the events that *would* be emitted | emitting one |

### Conditional continuation

A requirement the simulator may not resolve does not stop the traversal — it makes
everything downstream **conditional** on that requirement, and the run says so in
`conditional_on_requirements`. The terminal state is the outcome *if* those are met.
Continuing silently would be indistinguishable from deciding; stopping would make
simulation useless past the first authority node, which every governed workflow has.

### Nothing is fabricated

Two rules earn their place here, both discovered by running the traversal rather
than by reasoning about it:

- **An unmodelled constraint is not a failure.** Only the numeric bound kinds
  (`NUMERIC_RANGE`, `HARD_LIMIT`) are evaluated. Treating "I cannot evaluate this"
  as "this failed" would deny every workflow using a membership or once-only
  constraint — a fabricated answer dressed as a conservative one.
- **No arbitrary branch is ever taken.** If no outgoing edge matches the observed
  outcome, the traversal stops and the run reports `INCOMPLETE`. An earlier version
  fell back to the first outgoing edge, which silently manufactured a path the graph
  does not state.

Every predicate is evaluated through the single shared evaluator
(`evaluation/predicates.py`); there is no second interpretation of the policy
language.

## How it stays a simulator

A runtime is distinguished by three things this package must never acquire: an
**effect**, an **authority**, and a **seam**. Four AST-enforced rules remove all
three — no I/O surface, no provider import, no authorization-shaped field on any
output type, and no `Protocol` or `ABC` through which a real provider could be
supplied.

`runtime_deployment_implemented`, `runtime_execution_implemented` and
`action_authorization_implemented` remain `false`, and
`simulation_grants_authorization` is a permanent `false`.

## A finding about the shipped scenarios

The scenarios assurance generation emits satisfy the coverage invariant — they cite
the object ids they exercise — but they carry few or no **facts**. Simulating them
therefore blocks at the first evidence node, which is the honest answer for those
inputs rather than a defect in the traversal.

Making generated scenarios simulation-ready would change the assurance manifest and
therefore every release digest, so it is not done here. It is a real gap for the
pilot evidence list, and it needs its own ratification.
