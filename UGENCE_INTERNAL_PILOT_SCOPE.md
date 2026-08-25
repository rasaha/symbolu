# Ugence internal pilot — governed cloud scaling

**Status: scoping record, not a commitment.** Written 2026-08-25. No external client
exists; Ugence is its own first user. This document says what the pilot is, what already
ships, what integration remains, and what is deliberately faked. It ratifies nothing and
binds no package's governance.

Evidence labels: `[V]` verified against the repository, `[I]` inferred, `[G]` gap.

---

## 1. The scenario

**Decision.** Whether an AI cloud-operations agent may scale a production-like
application from its current replica count to a proposed replica count in response to
rising load.

**Agent.** An internal cloud-scaling agent operating through Ugence Agent Runtime.

**Subject.** A simulated tenant application in a sandbox Kubernetes environment. **No
real customer and no production infrastructure.**

**Consequence if wrong.**

| Failure | Harm |
|---|---|
| Scale too little | Degraded service or outage |
| Scale too much | Cost-limit violation |
| Scale during a change freeze | Organizational policy violation |
| Wrong tenant or agent acts | Authorization failure |
| Execute without clearance | Uncontrolled infrastructure change |

**Three outcomes the pilot must demonstrate.**

1. **Permit** — evidence sufficient, tenant and agent authorized, replica and budget
   limits satisfied, no freeze in effect.
2. **Deny** — a hard rule is violated: maximum replicas, budget ceiling, tenant boundary
   or change freeze.
3. **Escalate / abstain** — required evidence or authority is missing or conflicting, so
   **no execution occurs**.

**Visible workflow.**

```
load signal → agent scaling proposal → evidence/context display
   → policy and risk evaluation → permit / deny / escalate
   → Action Clearance when permitted → dry-run execution
   → outcome and audit record
```

The deliverable is a **standalone app plus service API**. ServiceNow is a later
integration adapter, not the pilot host.

## 2. Already implemented `[V]`

The scenario sits on the mature part of this repository, not on new ground.

| Component | Version | Size | Role in the pilot |
|---|---|---|---|
| `ugence-cloud-scaling-controller` | `0.4.0` | ~20,280 LOC | **The proposal source.** Consumes normalized workload observations, produces explainable scaling recommendations. Declares itself `ADVISORY · Execution capability: NONE` — no code in the wheel can apply its own advice |
| `ugence-agent-runtime` | `0.7.0` | ~9,920 LOC | Execution-coordination kernel: canonical execution state, bounded workflow advancement, durable checkpoint/recovery, append-only audit event store |
| `ugence-risk-authority` | — | ~7,550 LOC | Risk evaluation |
| `ugence-policy-authority` | — | ~3,510 LOC | Policy decisions |
| `ugence-governance-contracts` | — | ~1,770 LOC | Shared contract layer |
| `ugence-action-clearance` | `0.1.0` | ~1,610 LOC | Pre-execution clearance: `CLEAR · HOLD · BLOCK · ESCALATE`, precedence `BLOCK > ESCALATE > HOLD > CLEAR`. Stateless; may narrow or block an authorization, never create one |
| `actiongate` provider | `0.1.0` | — | "May **this exact** action execute?" |
| `ugence_console_api` | — | ~1,120 LOC | **An app and API shell that already implements this scenario's shape** — see below |

**`ugence_console_api` is closer to the pilot than expected** `[V]`. Its
`scenarios.py` docstring reads: *"an enterprise Kubernetes / infrastructure agent
proposing a high-consequence write. Three variants exercise the non-compensatory gates —
a clean allow, an operational HOLD, and an unsupported assertion."* That is this pilot's
Permit / Deny / Escalate triad, already written.

Its `orchestrator.py` implements the governed loop:

```
Gateway   -> Context Minimization     what may enter
Verify    -> Truth Assurance          is the assertion supported
Authorize -> ActionGate               may THIS exact action execute (CER-bound)
Clear     -> Autonomous Control Plane is it operationally safe right now
Record    -> Audit                    reconstructable decision chain
```

Gates are **non-compensatory** — a clean authorization cannot buy back an operational
HOLD. FastAPI endpoints already exist for `/v1/gateway/minimize`,
`/v1/assertions/evaluate`, `/v1/actions/authorize`, `/v1/actions/clear`,
`/v1/governed-loop/shadow`, `/v1/governed-loop/scenario/{id}` and `/v1/audit` `[V]`.

## 3. Integration work still required `[V]`

The console API is a **prototype shell with partial wiring**, and this is the bulk of the
pilot's real work.

**What it genuinely wires** — via deferred imports inside functions:
`actiongate_provider.configuration.build_actiongate_provider`,
`governance_providers.api`, `tap_provider.configuration.build_tap_provider`, and
`ugence_context_minimization.api`.

**What it does not wire at all.** Five local modules in
`ugence_console_api/capabilities/` (~373 LOC total) stand in for real capability:
`action_control.py`, `context_gateway.py`, `operational_safety.py`, `truth_evidence.py`,
`registry.py`. Notably `operational_safety.py` is the console's **own** digital
control-plane sibling — it is *not* the `ugence-action-clearance` package.

So none of the following is connected today:

- **`ugence-cloud-scaling-controller`** → the proposal step. Today the console's scenarios
  carry a hard-coded proposed action; the controller that would generate it is unused.
- **`ugence-agent-runtime`** → execution coordination and the audit event store. The
  console keeps its own simpler audit list.
- **`ugence-action-clearance`** → the Clear stage, replacing `operational_safety.py`.
  Note the console's gate returns `CLEAR / HOLD`; the package's vocabulary is
  `CLEAR · HOLD · BLOCK · ESCALATE`, which is what the three-outcome demo needs.
- **`ugence-policy-authority` / `ugence-risk-authority`** → the policy and risk evaluation
  step. Replica ceilings, budget ceilings, tenant boundaries and freeze windows have no
  home yet `[G]`.
- **`ugence_context_minimization`** is imported but resolves to no directory in this tree
  `[G]` — availability unconfirmed.

**Also required:** a scaling-specific decision contract (current replicas, proposed
replicas, tenant, budget, freeze state) — no such contract exists today `[G]`.

## 4. Mocked inputs

Everything entering the loop is **fabricated and labelled as such**. None of it comes
from a real system:

- load signals (CPU, memory, latency, error rate, queue depth) — hand-authored fixtures
- Kubernetes cluster state and current replica counts — simulated
- tenant and agent identity — fixtures, not authenticated principals
- budget position and cost ceilings — static values
- change-freeze calendar — a static window

A mocked input must be visibly mocked in the UI. The pilot demonstrates **how governance
behaves given inputs**, not that the inputs are true.

## 5. Dry-run execution

**Nothing is applied to any cluster.** The pilot executes in the console's existing
SHADOW mode, whose semantics are already implemented `[V]`: *"the loop evaluates and
records but changes nothing; `would_execute` still reports what ENFORCEMENT would have
done."*

This is a good fit rather than a compromise. The three outcomes are decision outcomes;
demonstrating them needs a faithful decision path and an honest record, not a real
`kubectl scale`. The scaling controller's own `Execution capability: NONE` posture points
the same way.

## 6. Future production capabilities — explicitly out of scope

Not in the pilot, and not to be implied by it:

- real Kubernetes apply, rollback and compensation
- durable, tamper-evident audit storage (Agent Runtime has an append-only event store;
  the console does not use it)
- authenticated tenants and multi-tenancy isolation
- a stability-committed public API
- **the ServiceNow integration** — a later adapter. `UGENCE_SERVICENOW_*` documents
  describe a **proposed** integration and state that no connector ships today `[V]`
- live cost and freeze-calendar feeds

## 7. What must not be claimed

**Benchmark Registry and BR-2C are outside this pilot's critical path and must not be
presented as verified authority.** BR-2 ships contracts only at `0.2.3` with no
cryptographic capability; BR-2C was deliberately deferred on 2026-08-25 with D-38 and
D-32(4) standing `[V]`.

No artifact, screen or document produced by this pilot may describe evidence as
cryptographically verified, trusted by BR-2C, production-authorized, or independently
audited. The audit record is a **reconstructable decision chain**, not a signed one.

## 8. Resolved and still open

**Resolved by this scenario:** what the pilot demonstrates; which app (the console API
plus a front end over it); the primary user (an operator watching a governed scaling
decision); that the API is internal-only for now; which packages compose §2.

**Still open** `[G]`:

- **Acceptance criterion.** With no external client, "done" must be chosen. Proposed:
  all three outcomes reproducible end to end from a single API call each, with an audit
  record for every one.
- **Where policy limits live.** Replica ceiling, budget ceiling, tenant boundary and
  freeze window need a home — Policy Authority, static pilot config, or both.
- **Front end.** `apps/console`, `apps/ugence-governance-studio` and `frontend/` all
  exist; none is identified as the target.

---

## Smallest slice that produces a working end-to-end demo

**One scenario, one outcome, one honest record — not all three outcomes.**

Wire `ugence-cloud-scaling-controller` into `ugence_console_api` as the proposal source,
so a mocked load signal produces a real recommendation rather than a hard-coded action;
add a minimal scaling decision payload (current replicas, proposed replicas, tenant,
budget, freeze flag); run it through the existing governed loop in SHADOW mode; return
the verdict and audit record from one endpoint.

Target the **Permit** path first, through `/v1/governed-loop/scenario/{id}`.

That slice is small because it adds one real integration to a loop that already runs, and
it is end-to-end because it spans load signal → proposal → evaluation → clearance →
dry-run → audit. **Deny** and **Escalate** then follow by varying the mocked inputs
against the same path, which is why they are not in the first slice.

Deliberately excluded from the slice: Agent Runtime integration, replacing
`operational_safety.py` with `ugence-action-clearance`, Policy/Risk Authority wiring, and
any front end. Each is worth doing; none is needed to prove the path runs.

---

*Written from the repository state at default-branch head `0e31e295` and owner decisions
of 2026-08-25. Nothing here is ratified; each package's own governance remains the
authority on its contents. No implementation has begun.*
