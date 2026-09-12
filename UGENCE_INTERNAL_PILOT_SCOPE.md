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

**Agent.** An internal cloud-scaling agent operating through Ugence Agent Runtime. *This
is the scenario's intended target state; Agent Runtime is **not** wired today (§3) and its
integration is scheduled under "Later" in the implementation sequence.*

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

*Workflow caveat:* "Action Clearance" above names the **stage**, not the
`ugence-action-clearance` package. That stage is served today by the console's own
`operational_safety.py` (§3). The package is wired only at Slice 2, after a boundary
review.

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
  The console's gate returns `CLEAR / HOLD`; the package's vocabulary is
  `CLEAR · HOLD · BLOCK · ESCALATE`. The three acceptance outcomes are expressible
  **without** the extra two (§8), so this is a fidelity gap, not a blocker — and it is
  gated behind the boundary review in Slice 2.
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

## 8. Acceptance criterion

The first complete pilot must reproduce **all three governed outcomes through the same
API and the same pipeline**. Each call must return an audit record, identify which inputs
were mocked and which real, and perform **no external mutation**.

**Use the vocabulary the components actually emit.** These are the real field values
`[V]`, and they do not line up with the informal permit/deny/escalate labels:

| Model | Field | Values it emits |
|---|---|---|
| `AssertionVerdict` | `coverage` | `SUPPORTED` / `UNSUPPORTED` / `CONSTRAINED` / `INDETERMINATE` |
| `ActionVerdict` | `outcome` | `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS` / `DENIED` / … |
| `ClearanceVerdict` | `disposition` | **`CLEAR` / `HOLD` only** |
| `GovernedLoopResult` | `would_execute`, `final_disposition`, `recorded`, `correlation_id`, `cer_id`, `stages` | — |

The three outcomes, stated in that vocabulary:

1. **Allowed / would execute** — `AssertionVerdict.coverage = SUPPORTED`,
   `ActionVerdict.outcome = AUTHORIZED` (or `AUTHORIZED_WITH_CONSTRAINTS`),
   `ClearanceVerdict.disposition = CLEAR`, `would_execute = true`.
2. **Refused or held because a hard control fails** — `would_execute = false`, reached
   *either* by `ActionVerdict.outcome = DENIED` (authorization refusal: replica ceiling,
   budget ceiling, tenant boundary) *or* by `ClearanceVerdict.disposition = HOLD`
   (operational stop: change freeze). These are **different outcomes from different
   authorities** and must be reported as what each emitted.
3. **Held / review-required because evidence or authority is unsupported or
   insufficient** — `AssertionVerdict.coverage = UNSUPPORTED` or `INDETERMINATE`,
   `would_execute = false`.

**Naming discipline, binding.** The console's clearance gate emits **only `CLEAR` and
`HOLD`** `[V]`. It has no `BLOCK` and no `ESCALATE`. Do not relabel a `HOLD` as `DENY` or
`ESCALATE` in the API, the UI or any demo narration — those words belong to authorities
that did not produce the outcome. `BLOCK` and `ESCALATE` exist in the
`ugence-action-clearance` package's vocabulary, which is **not wired** (§3); until it is,
they must not appear.

## 9. Policy limits — demo fixtures, not Policy Authority

For the internal pilot, replica ceiling, budget ceiling, tenant boundary and change-freeze
window come from **immutable, versioned scenario fixtures owned by the demo adapter**.

Every surface that displays or returns them must label them:

```
DEMO POLICY — NON-AUTHORITATIVE
```

**No artifact may state or imply that Policy Authority evaluated them.** Policy Authority
is not wired (§3), and a fixture is not a policy decision.

Production policy must come from Policy Authority through a **separately defined
integration seam**, specified and reviewed on its own terms. That seam does not exist and
is not designed here `[G]`.

## 10. Front end — `apps/console`

**Selected: `apps/console`**, on measured grounds rather than its name `[V]`:

- Its `src/api.ts` calls exactly the two endpoints this pilot needs —
  `/v1/governed-loop/scenario/${id}` and `/v1/audit/${correlationId}` — and both exist in
  `ugence_console_api/app.py` (`:118` and `:135`). The integration is already matched.
- Its README states it "Talks to the `ugence_console_api` service."
- It carries `dev`, `build`, `preview` and `type-check` scripts, and a `src/decision.ts`
  plus `src/views/` structure suited to showing proposal → gates → outcome → audit.

**Unverified** `[G]`: `node_modules` is absent and there is **no lockfile**
(`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock` all absent). Neither the build nor
`type-check` has been run. "Smallest verified effort" here means smallest *API-integration
distance*, which is measured; build health is not.

**Deferred, with reasons:**

- **`apps/ugence-governance-studio/frontend`** — targets `http://127.0.0.1:8000` and has a
  generated API client, but is a larger app built around eligibility features, aimed at a
  different domain. Deferred as disproportionate, not unsuitable.
- **`frontend/`** (`symbolu-frontend`) — references port 8000 only in its README and Vite
  config; no `/v1/` client code exists in `src`. Deferred: it would need the integration
  written from scratch that `apps/console` already has.

---

## Implementation sequence

**Slice 1 — backend integration only.** `ugence-cloud-scaling-controller` becomes the
real proposal source for **all three fixed scenarios**, running through the existing
SHADOW governed loop. A mocked load signal yields a genuine recommendation instead of a
hard-coded action; a minimal scaling payload carries current replicas, proposed replicas,
tenant, budget and freeze state; each scenario returns its verdict and audit record from
`/v1/governed-loop/scenario/{id}`. Policy limits come from the §9 demo fixtures, labelled
non-authoritative. No front end, no vocabulary change, no external mutation.

This is the acceptance criterion in §8 met at the API, and it is the whole of the first
slice.

**Slice 2 — clearance vocabulary, after a boundary review.** Only once a **separate
boundary review** has run may the console's local safety/clearance module be replaced by
or reconciled with `ugence-action-clearance`. The review is required because the two
vocabularies differ — `CLEAR / HOLD` against `CLEAR · HOLD · BLOCK · ESCALATE` — and
because Action Clearance may narrow or block an authorization but never create one. Which
outcomes become expressible, and what that changes about the three scenarios, is a
decision to take deliberately rather than as a side effect of wiring.

**Slice 3 — front end.** Connect `apps/console` (§10) to the Slice 1 API. Its two
endpoint calls already match, so this is integration and display, not new client work.
Build health must be established first (§10).

**Later.** Agent Runtime integration and its append-only audit event store; Policy
Authority through the §9 seam; Risk Authority; production execution against a real
cluster. None is required for the acceptance criterion, and none should be started before
Slices 1–3 are complete.

---

*Written from the repository state at default-branch head `0e31e295` and owner decisions
of 2026-08-25. Nothing here is ratified; each package's own governance remains the
authority on its contents. No implementation has begun.*
