# Owner ratification — a live model-calling provider

**Status:** ballot, not a decision. Nothing here is implemented, scheduled or authorized.
No gate identifier is marked satisfied and no ratified pin, gate record or evidence
manifest is modified by this document.

**The question:** may the agent runtime gain a provider that calls a model vendor's API,
and under what constraints?

## 1 — The finding that shapes everything else

**A live model call from the worker contradicts a ratified ruling as it stands today.**

CR-5 `ALLOWLISTED_JWKS_HOST`: *"The worker's only egress is the configured JWKS host over
HTTPS, as platform configuration recorded as `EXTERNAL_DEPLOYMENT_EVIDENCE`; no discovery
document, no docker.io, nothing else."* `[V]`

A call to `api.openai.com`, `api.anthropic.com` or `api.mistral.ai` is egress to a host
that is not the JWKS host. The composition-root ADR's own conformance table, row 5, makes
it a named refusal case: *"The worker attempts any egress other than the JWKS host →
refused by platform allowlist"* `[V]`.

This is not an obstacle to route around. It means the decision is not "add a package" but
**"amend CR-5, or place the provider outside the worker"** — and those are different
products. Every other decision below is downstream of it.

## 2 — What exists today

| Component | State | Evidence |
|---|---|---|
| Neutral execution boundary | Built | `providers/interfaces.py` — `Provider` protocol: `provider_id`, `version`, `execute(ToolInvocation) -> ToolResult` `[V]` |
| Vendor neutrality | Deliberate, documented | Same file: *"The runtime embeds no vendor-specific behavior (no OpenAI, Anthropic, GitHub, cloud, or database specifics) — those belong in concrete provider implementations that live in separate packages."* `[V]` |
| Registry | Built, explicit injection | `providers/registry.py` — no import-time population, no global provider state `[V]` |
| Concrete providers in the product | One | `ShadowProvider`, `provider_id="shadow-recorder"`, `maturity="FIXTURE_ONLY"`: records in memory, returns success, no external effect `[V]` |
| Model-calling provider | None | No package under `packages/` implements `Provider` against any vendor; no SDK, no key handling in any product distribution `[V]` |
| Model SDKs elsewhere in the monorepo | Present, not reachable | `symbolu_training/`, `ndol/experiments/`, `truth_assurance_pipeline/tap_e1_1_realmodel/model_client.py` are research trees; no product distribution imports them `[I]` |
| Credential custody | Absent | No mechanism anywhere; RW-3's parallel finding already records that no certificate authority or key custody exists `[G]` |
| Cost, rate and quota governance | Absent | Nothing meters, budgets or refuses on spend `[G]` |
| Prompt and response handling policy | Absent | No record states what may be sent, retained or logged `[G]` |

**The seam is built; the capability is not.** In code a vendor provider is one package
implementing one protocol. That smallness is the trap: the governance surface it opens is
the largest in the product, because *does not execute* is the claim every screen makes.

## 3 — Rulings this touches

| Ruling | Bearing | Label |
|---|---|---|
| **CR-5** | Direct contradiction. Model egress is not the JWKS host. | `[R]` |
| **CR-4** | `production` sets every switch together and *"enables no LIVE execution."* A live provider is LIVE execution by name. | `[R]` |
| **CR-3** | Private segment, TLS, identity mandatory in production. An outbound vendor call is a new trust direction the ruling does not contemplate. | `[R]` |
| **CR-1** | The worker hosts the runtime host and providers. A vendor provider would live here — or the ruling needs a second unit. | `[R]` |
| **AP-4** | *"The plane may name grant, revoke, activate and issue. It may never…"* — the authority surface stays read-only regardless. Unaffected, and must remain so. | `[V]` |
| **RW-2** | A production image comes from the external gate pipeline by digest. A provider carrying a vendor SDK enlarges that unbuilt image. | `[G]` |

## 4 — The ballot

Five decisions. Each changes the specification materially; the first changes whether the
others are asked at all.

### D-1 — Is inference an action?

Does a model call pass through the governed execution hook and require clearance, or is
reasoning exempt from it?

| Option | Consequence |
|---|---|
| `INFERENCE_IS_AN_ACTION` | Every model call is proposed, cleared and recorded like any other action. Strongest governance claim; highest latency and the largest audit volume. |
| `INFERENCE_IS_EXEMPT` | Reasoning is ungoverned; only its downstream effects are gated. Simpler, and concedes that the loop does not see the step most likely to go wrong. |
| `DEFER` | No live provider is specified. |

*Everything below assumes this is not `DEFER`.*

### D-2 — Where does the provider run, and what happens to CR-5?

**Owner's stated preference: `SEPARATE_EGRESS_UNIT`** — keep the worker private and
preserve CR-5 rather than allow it to call vendors. Recorded as a preference; the decision
is open, and §4b states what each option costs.

| Option | Consequence |
|---|---|
| `AMEND_CR_5_ALLOWLIST_VENDOR` | The worker's allowlist gains named vendor hosts. Smallest change; directly weakens the egress claim, which is currently absolute and easy to state. |
| `SEPARATE_EGRESS_UNIT` | A second deployment unit holds the vendor call; the worker's egress claim survives intact. A new unit, a new boundary, a new CR-family ruling. |
| `NO_LIVE_PROVIDER_IN_THIS_ARCHITECTURE` | The seam stays unimplemented and the claim stays absolute. |

### D-3 — Credential custody

| Option | Consequence |
|---|---|
| `PLATFORM_ENVIRONMENT_VARIABLE` | A key in the deployment's environment. Operationally trivial; no rotation, no attestation, and RW-3 already records that no key custody mechanism exists. |
| `EXTERNAL_SECRET_MANAGER` | Custody is a named dependency with rotation and audit. Correct, and prerequisite work before any provider ships. |
| `NO_CREDENTIAL_IN_THIS_DEPLOYMENT` | A live provider is scoped to a customer-operated deployment only. |

### D-4 — What is recorded

Prompts and responses are the highest-value evidence and the highest-risk payload. This
collides directly with context minimization and data-use admission, both of which are
already composed into the loop.

| Option | Consequence |
|---|---|
| `RECORD_FULL_EXCHANGE` | The audit answers what was actually asked and answered. The ledger becomes a store of potentially sensitive content, under a durability posture RW-6 already limits to single-instance reference grade. |
| `RECORD_DIGEST_AND_METADATA` | Hash, token counts, model id, latency, disposition — no content. Defensible, and cannot reconstruct what happened. |
| `RECORD_MINIMIZED_EXCHANGE` | Content admitted through context minimization only. Consistent with the existing gate; the most work. |

### D-5 — Do concentration limits carry into execution?

The registry already reasons about provider concentration in **planning** — the
procurement scenario is non-greedy team selection under provider concentration limits
`[V]`. A live provider makes those limits enforceable at execution for the first time.

| Option | Consequence |
|---|---|
| `LIMITS_BIND_AT_EXECUTION` | The vendor mix a plan promised is the mix that runs. Closes the gap between planned and actual governance. |
| `PLANNING_ONLY` | Concentration limits stay advisory. A plan may promise a mix the runtime does not honour, which is a gap worth stating plainly rather than discovering. |

## 4a — The execution sequence, and where it still needs a decision

An earlier seven-step sequence was put forward and corrected. What follows is the
**owner's preferred spine**, recorded with the boundaries the owner set. It is a stated
preference, not a ratification: D-2 in particular remains open, and §4b says why.

### The preferred spine

```
separate Agent Runtime invokes the model
  → constrained tool-schema output
  → typed proposal OR typed refusal
  → Context Minimization
  → TAP evidence verification
  → ActionGate authorization
  → authorization disposition recorded
  → Autonomous Control Plane operational clearance
  → clearance / HOLD / denial / escalation recorded
  → named human approval workflow, when escalated
  → executor independently verifies the clearance receipt
  → action executes
  → Runtime Assurance verifies and records the outcome
```

The distinction the spine preserves, and the reason ActionGate cannot be the last gate:

> **Authorization** answers whether the action is allowed in principle.
> **Clearance** answers whether it is safe and appropriate to execute *now*.

Both shipped console refusals turn on exactly that separation: ActionGate returns
`AUTHORIZED` with `reasons: ['policy_allow']` and the action is stopped anyway, once by
operational clearance under a change freeze and once by the evidence gate `[V]`. The
deployed order is already Context Minimization → TAP → ActionGate → Autonomous Control
Plane `[V]`.

### The boundaries the owner set

1. **Vendor-model egress is not ratified.** `AMEND_CR_5_ALLOWLIST_VENDOR` stays an explicit
   D-2 decision and is not implied by this spine — see §4b.
2. **Record at more than one point.** The proposal and its evidence are persisted *before*
   evaluation; the authorization and operational-clearance dispositions are persisted
   *before* execution. Recording is a precondition of acting, not a consequence of it.
3. **Authorization and clearance are separate and non-substitutable.** Neither may stand in
   for the other, and neither may be skipped because the other passed.
4. **An escalation is routed to a named, scoped human approver**, carrying an approval
   reference and an expiry. Escalation is a destination, not a status.
5. **The executor independently verifies the clearance receipt** — its `cer-…` identifier,
   the action it binds to, its scope, its expiry and its integrity — rather than trusting
   its caller.
6. **The execution outcome is recorded afterward through Runtime Assurance.**

### What each boundary rests on today

| Boundary | Repository state |
|---|---|
| Ordered authorize-then-clear | Implemented and demonstrated `[V]` |
| Clearance receipts exist to be verified | `cer-…` identifiers ride every disposition, and `clearance_receipts.json` is part of each scenario `[V]` |
| An approval workflow to escalate into | `ugence-approval-workflow` and the approver identity adapter are composed into the worker `[V]`; the approver stays `PRESENTED_UNPROVEN` until AP-3 is validated `[G]` |
| Constrained tool-schema output | Nothing. No model call exists, so no output contract does either `[G]` |
| Executor-side receipt verification | Nothing. No executor exists, and no code verifies a receipt's binding, scope, expiry or integrity `[G]` |
| Runtime Assurance | `packages/integration/risk-authority-runtime-assurance` exists (RA-7) but is **not installed in the worker image** — the Dockerfile copies `risk-authority-runtime` and `risk-authority-status-runtime` and not this one `[V]` |

**One correction to boundary 6 as written.** RA-7 does not "verify" an execution in the
sense of validating it. Its own contract says `RA-7 OBSERVES AND ASSESSES. RA-6 OWNS
AUTHORITY CONSEQUENCES.`: it risk-types the trajectory, emits a neutral
`AuthorityReassessmentSignal` on material deviation, and RA-6 enforces the consequence
*at the next commit* `[V]`. So Runtime Assurance cannot un-execute an action. It records
the outcome and changes what is permitted next. Stated that way it is a strong final step;
stated as verification it would promise a rollback the design does not have.

**Two `[G]`s worth naming before they are assumed.** A typed refusal from the conversion
step — "this output maps to no proposable action" — must be first-class, because a
converter that always yields a proposal is the same defect as a planner that always yields
a team, which the studio already refuses to be `[V]`. And the approver a human approval
routes to is presented and unproven until AP-3's validation; an escalation today would name
an approver the deployment cannot authenticate.

## 4b — D-2 is a cost, not a consequence

The spine places the model call in a **separate Agent Runtime** with controlled vendor
egress, which submits typed proposals inward. The governance worker stays private and keeps
its existing restricted egress. That is `SEPARATE_EGRESS_UNIT` in D-2, and it preserves
CR-5 intact rather than amending it.

**This is the owner's stated preference and it is recorded as such, not as ratified.**
D-2 stays open, and it stays open in both directions:

- Choosing the separate runtime **costs a deployment unit, a new trust boundary and a new
  CR-family ruling** for what may cross it. Nothing in this repository implements that
  boundary today `[G]`.
- Choosing `AMEND_CR_5_ALLOWLIST_VENDOR` costs the egress claim — currently absolute, and
  worth stating in one sentence: *the worker calls one host, and that host is your identity
  provider*.

**Ratify `AMEND_CR_5_ALLOWLIST_VENDOR` only if there is a concrete need for the worker
itself — not the separate Agent Runtime — to call a model vendor.** No such need is
recorded in this repository today `[G]`. Until one is, the amendment buys nothing and
spends a claim.

Nothing in §4a or §4b ratifies anything. Whether the loop is arranged this way is part of
D-1; where the first step runs is D-2; and both remain unanswered.

## 5 — What this document does not do

It specifies nothing. No interface, no package layout, no configuration surface, no
sequencing. An implementation specification written before D-1 and D-2 are answered would
be a specification of one arbitrary reading among several, and the two readings of D-2 are
different products.

It also marks no gate identifier satisfied, admits nothing to the P3E-CTR or GRW-CTR
families, and changes no ratified pin.

**On ratification of D-1 through D-5, the next artifact is an implementation
specification** written against the answers, followed by the amendments D-2 requires to
CR-5 and CR-4 — which are owner acts, not consequences of the spec.
