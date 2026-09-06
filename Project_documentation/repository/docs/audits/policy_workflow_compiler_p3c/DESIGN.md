# PWC-P3C — Deterministic Offline Simulation: Design

**Status:** design. Step one — the shared predicate evaluator — is **delivered**;
the simulator itself is not. Two rulings remain open, recorded at the end.
**Scope:** `packages/tooling/policy-workflow-compiler`. The last build phase in the
ratified order (`../policy_workflow_compiler_ratification/RATIFICATION.md`).

Findings carry `[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## What already exists

`[V]` The inputs a simulation needs are already typed and already generated.
`TestScenario` carries `initial_facts`, `actor_identities`, `evidence`,
`requested_action` and an `ExpectedOutcome` oracle (`terminal_state`,
`reason_codes`, `audit_events`, `authorization_outcome`); `ReplayCase` carries
`captured_facts` plus the same oracle. Assurance generation emits both into
`AssuranceManifest` across 14 categories behind a fail-closed coverage invariant,
and the Procurement reference ships three scenarios.

`[V]` Nothing consumes them as a *run*. `CompiledPackageVerifier` recomputes
digests and checks authority boundaries, coverage completeness, capability-manifest
agreement and audit baseline fields — structural checks over the artifact. It never
walks the graph with facts.

So P3C's delta is narrow: an evaluator that walks the compiled graph under a
scenario's facts and records what it observes.

## Step one — the finding that shaped the phase `[G]`

A deterministic predicate evaluator **already existed**, privately, inside
`reference/procurement_equivalence.py`. It handled **eight of twelve** comparators.
`IN`, `NOT_IN`, `NON_EMPTY` and `IS_EMPTY` fell through to `False`: a policy using
any of them evaluated as *unsatisfied* rather than raising — a silent wrong answer
inside a harness whose entire job is to prove that two interpretations agree.

This is the `canonical_pack_view` lesson repeating. Two interpreters of one policy
language would let the harness that proves equivalence and the simulator that
demonstrates behaviour disagree, invisibly.

**Delivered:** `evaluation/predicates.py` is now the single interpreter, total over
all twelve comparators, and `_eval_predicate` is a thin alias that delegates to it.
Its rules are stated rather than implied:

- A predicate that cannot be evaluated is **not satisfied** — a missing fact, or an
  operand of the wrong shape, yields `False` rather than an exception.
- **Absence is emptiness.** `IS_EMPTY` treats a missing fact as empty and
  `NON_EMPTY` treats it as not non-empty. Emptiness has an answer for an absent
  fact in a way ordering and membership do not, and this direction is the safe one:
  a policy that blocks on empty evidence blocks when the evidence never arrived.
- **Ordering requires comparable operands** — two real numbers, or two strings.
  `bool` is excluded despite being an `int` in Python, because comparing a flag to
  a threshold is an authoring mistake and answering it would hide one.
- **An unknown comparator raises.** That is the defect being removed, and it must
  not return through a future enum member nobody wires up.

`[V]` Both equivalence harnesses still report `EQUIVALENT` at their existing check
counts, and every digest is unchanged.

## What a run consumes and produces

**Consumes:** a compiled release (its `workflow_ir.v2`) and one scenario. Nothing
else — no clock, no environment, no filesystem, no network, no registry, no
credentials.

**Produces** a `SimulationRun`:

```text
release_digest          the release simulated, bound in
scenario_id             the scenario simulated
trace                   ordered NodeObservation per visited node
terminal_state          the terminal outcome reached
reason_codes            declarative labels the traversal accumulated
described_audit_events  events the audit schema says WOULD be emitted
unreached_nodes         nodes the facts never reached
run_digest              content digest over all of the above
```

`[V]` Traversal order is already deterministic: v1 emits content-addressed node ids
and deterministically ordered edges.

## Simulating without deciding

The distinction the phase rests on. For each node kind the simulator reports **what
the graph requires**, never **that the requirement was met**:

| Node kind | Observes | Never |
| --- | --- | --- |
| `AUTHORITY_CHECK` | "requires authority *A*; the scenario names actor *X*" | that *X* holds *A* |
| `APPROVAL_GATE` | "requires approval by role *R*" | granting approval |
| `SEGREGATION_OF_DUTIES_GATE` | "these steps must differ; the scenario's identities do or don't" | enforcing it live |
| `ACTION_CLEARANCE_REQUIREMENT` | "clearance is required here" | clearing anything |
| `AUDIT_EMISSION` | "these event types would be emitted" | emitting one |

A scenario's `actor_identities` are **stated facts**, not credentials, and its
`authorization_outcome` is an **oracle to compare against**, not an authorization
the simulator issues. Comparing an observation to an oracle yields a test result,
and a test result is not a grant.

## Where the boundary is enforced in code

`[V]` The technique is established — the X1 boundary test and the composition
root's AST suite both use it.

1. **No I/O surface.** A run takes data and returns data. An AST test refuses `os`,
   `socket`, `urllib`, `requests`, `secrets`, `random`, `time`, `open` and any clock
   read inside the simulation package.
2. **No provider import**, by the same scan that keeps Policy Authority out of the
   compiler.
3. **No authorization-shaped return.** `SimulationRun` and `NodeObservation` are
   frozen data with no field that could carry a grant, an approval record or a
   clearance; a test asserts the field set.
4. **No adapters or ports.** A port is the seam through which a simulator becomes a
   runtime. There is none, and an AST test asserts no `Protocol` or `ABC` is defined
   in the package.

## How it avoids becoming a runtime

The ratification names this failure mode, so it deserves an answer rather than a
promise. A runtime is distinguished by three things a simulator must never acquire:
an **effect** (something changes outside the process), an **authority** (it decides
rather than describes), and a **seam** (a port where a real provider plugs in). The
four rules above remove all three, and each is enforced by a test rather than a
convention.

## Maturity

New: `offline_simulation_implemented`, `deterministic_replay_of_simulation_verified`.
New permanent non-goal: `simulation_grants_authorization=false`.
Unchanged and false: `runtime_deployment_implemented`,
`runtime_execution_implemented`, `action_authorization_implemented`.

## Digest impact

None. P3C reads a compiled release and writes nothing into it — no pack field, no
IR field, no manifest field. `policy_pack.v1`/`v2`, `workflow_ir.v1`/`v2` and every
approval are untouched, and a test pins them.

## Open rulings `[R]`

**P3C-1 — simulation is evidence, not a gate.** A run should produce a report and
must not block compilation. Making compilation depend on a simulation result would
put the simulator on the execution path and begin exactly the coupling this phase
exists to avoid. Recommendation: the pilot evidence list consumes simulation
reports; the compiler does not.

**P3C-2 — where a simulator's own failure is reported.** Whether a scenario whose
observation contradicts its oracle is a `SimulationRun` field, a validation
diagnostic, or a separate report object. Recommendation: a field on the run, since
a contradicted oracle is a property of that run rather than of the release.
