# Owner ratification — a live model-calling provider

**Status:** D-1, D-2, D-3 and D-4 **RATIFIED 2026-09-10**, together with §3's direction, a
CR-5 clarification recorded in the composition-root ADR, and three transport rulings — a
worker-owned reconciliation driver, a dedicated exchange schema under least privilege, and
`OUTCOME_UNKNOWN` as a terminal outcome — recorded in `SPEC_MODEL_EGRESS_UNIT.md` §3.3-§3.5.
D-5 open. Nothing is
implemented. No exchange table is designed and no exchange exists. No gate identifier is
marked satisfied and no ratified pin, gate record or evidence manifest is modified by this
document. The implementation specification opened by these rulings is
`SPEC_MODEL_EGRESS_UNIT.md`.

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

### D-1 — Is inference an action? — **RATIFIED: `INFERENCE_IS_AN_ACTION`**

> **D-1 — INFERENCE_IS_AN_ACTION.** An inference invocation is a governed external action
> because it may create data-egress, vendor, cost and compliance effects. The resulting
> model output carries no decision or execution authority.
> — owner, 2026-09-10

The qualification is the substance of the ruling and must not be lost in implementation:
what is governed is the **request**, because it transmits data outward, incurs cost,
invokes a vendor and creates compliance exposure. The **response** is thereby granted
nothing. It returns as an untrusted proposal or as evidence, and stays untrusted until
independently verified and separately authorized for any consequential use.

Does a model call pass through the governed execution hook and require clearance, or is
reasoning exempt from it?

| Option | Consequence |
|---|---|
| `INFERENCE_IS_AN_ACTION` | Every model call is proposed, cleared and recorded like any other action. Strongest governance claim; highest latency and the largest audit volume. |
| `INFERENCE_IS_EXEMPT` | Reasoning is ungoverned; only its downstream effects are gated. Simpler, and concedes that the loop does not see the step most likely to go wrong. |
| `DEFER` | No live provider is specified. |

*Everything below assumes this is not `DEFER`.*

### D-2 — Where does the provider run, and what happens to CR-5? — **RATIFIED: `SEPARATE_EGRESS_UNIT`**

> **D-2 — SEPARATE_EGRESS_UNIT.** Preserve CR-5 and keep all model-provider network
> access, SDKs and credentials outside Agent Runtime. Commission a separately deployed
> Model Egress Unit with a narrow authorized interface. It may perform approved inference
> calls but may not approve requests, interpret provider output as trusted evidence or
> execute resulting actions.
> — owner, 2026-09-10

CR-5 is **not amended**. The worker's egress claim stands as written, and the vendor call
moves outside it. §4b's cost is accepted with the ruling: a deployment unit, a trust
boundary, and a new CR-family ruling for what may cross it — which is an owner act still
outstanding `[R]`.

| Option | Consequence |
|---|---|
| `AMEND_CR_5_ALLOWLIST_VENDOR` | The worker's allowlist gains named vendor hosts. Smallest change; directly weakens the egress claim, which is currently absolute and easy to state. |
| `SEPARATE_EGRESS_UNIT` | A second deployment unit holds the vendor call; the worker's egress claim survives intact. A new unit, a new boundary, a new CR-family ruling. |
| `NO_LIVE_PROVIDER_IN_THIS_ARCHITECTURE` | The seam stays unimplemented and the claim stays absolute. |

### D-3 — Credential custody — **RATIFIED: `NO_CREDENTIAL_IN_THIS_DEPLOYMENT`**

> **D-3 — NO_CREDENTIAL_IN_THIS_DEPLOYMENT.** The reference deployment must contain no
> model-provider credential and must make no genuine provider call. It may implement and
> test:
>
> - the MEU deployment boundary;
> - authorized-request leasing;
> - minimized-context validation;
> - provider-adapter interfaces using deterministic fakes;
> - response correlation;
> - refusal and retry behavior;
> - provenance placeholders that do not claim genuine provider evidence.
>
> Production model invocation remains blocked until an external secret-manager integration,
> rotation policy, audit trail and custody owner are separately commissioned.
> `PLATFORM_ENVIRONMENT_VARIABLE` is rejected as a production custody mechanism.
>
> A customer-managed credential may not be smuggled into the reference deployment through an
> environment variable, fixture or undocumented operator step. The absence of custody must
> produce an explicit non-production/refusal posture.
> — owner, 2026-09-10

The last paragraph is the enforceable part and the specification treats it as such: absence
of custody is a **posture the unit states and acts on**, not a configuration gap it happens
to have. A deployment with no credential refuses to call and says so; it does not merely
fail to find a key.

| Option | Consequence |
|---|---|
| `PLATFORM_ENVIRONMENT_VARIABLE` | A key in the deployment's environment. Operationally trivial; no rotation, no attestation, and RW-3 already records that no key custody mechanism exists. |
| `EXTERNAL_SECRET_MANAGER` | Custody is a named dependency with rotation and audit. Correct, and prerequisite work before any provider ships. |
| `NO_CREDENTIAL_IN_THIS_DEPLOYMENT` | A live provider is scoped to a customer-operated deployment only. |

### D-4 — What is recorded — **RATIFIED: the exchange is the temporary content plane**

Prompts and responses are the highest-value evidence and the highest-risk payload. This
collides directly with context minimization and data-use admission, both of which are
already composed into the loop.

> **D-4.** The dedicated model-egress exchange is the temporary content plane. It may carry
> structured canonical content consisting only of the authorized, minimized context required
> for inference and the resulting provider output. It may never carry unminimized source
> material, removed context, credentials, authority decisions, grant contents, clearance
> contents, workflow state, or another tenant's data.
>
> `request_digest` must bind the complete immutable inference request — not merely unit
> identifiers — including tenant identity, exchange schema version, ordered minimized unit
> identifiers and exact text, model-selection constraints, inference parameters, and the
> clearance reference and digest. Mutable lease, claim, attempt and processing timestamps are
> excluded. The response record must bind the canonical returned payload and its provenance
> through a response digest.
>
> The append-only audit ledger may retain only identifiers, digests, references, enumerated
> outcomes, metering and provenance. For Model Egress Unit ledger kinds, enforce this through
> a kind-specific schema that refuses content-bearing keys; record this as an unimplemented
> gap until built.
>
> No application-level encrypted-object mechanism is commissioned for the reference
> deployment. This does not waive transport security, database protection or future
> production key custody. No genuine customer content or genuine provider call is authorized
> until exchange tenancy, least-privilege database grants, retention and deletion policy,
> transport protection, and production credential custody are separately verified.
>
> Content remains only until the terminal result has been durably consumed by the worker,
> followed by an owner-approved grace period. Purging replaces content with a non-content
> tombstone containing request identity, digests, outcome, consumption acknowledgement and
> purge time. Engineering may not choose the grace period or maximum retention duration.
>
> Exchange grants and tenancy must be ratified before any content-bearing table is designed
> or implemented.
> — owner, 2026-09-10

**The ballot's framing did not survive the ruling, and that is the point.** Each option below
assumes one store and asks how much of the exchange goes into it. The ruling separates the
planes instead: content lives in the exchange, where it can be purged; the record lives in
the append-only ledger, where it cannot. So it is neither `RECORD_FULL_EXCHANGE` nor
`RECORD_DIGEST_AND_METADATA`, and it is stricter than `RECORD_MINIMIZED_EXCHANGE` — minimized
content is admitted to the exchange only, never to the ledger, and only until the worker has
durably consumed the result.

| Option | Consequence |
|---|---|
| `RECORD_FULL_EXCHANGE` | The audit answers what was actually asked and answered. The ledger becomes a store of potentially sensitive content, under a durability posture RW-6 already limits to single-instance reference grade. |
| `RECORD_DIGEST_AND_METADATA` | Hash, token counts, model id, latency, disposition — no content. Defensible, and cannot reconstruct what happened. |
| `RECORD_MINIMIZED_EXCHANGE` | Content admitted through context minimization only. Consistent with the existing gate; the most work. |

Two consequences are worth stating separately, because they are the ones an implementation
would otherwise soften. **The ledger's content rule has no enforcement today** —
`LedgerEntry.payload` accepts any canonically serializable dict `[G]`, so until the
kind-specific schema exists the rule is stated and unpoliced. And **the grace period and the
maximum retention duration are owner decisions withheld from engineering** `[R]`: until they
are set, no content may be held at all. Recorded in full at `SPEC_MODEL_EGRESS_UNIT.md` §4.4.

### D-5 — Do concentration limits carry into execution?

**Audit first, because the question contains an assumption the repository does not support.**
D-5 asks whether "the vendor mix a plan promised" binds at execution. There is no such
quantity today. Three unrelated things are called a provider:

| | |
|---|---|
| `AgentProfile.provider_id` (`agent-workforce-composer/…/agents.py:119`) `[V]` | Who supplies the **agent**. This is what `provider_concentration_limit_pct` — "max % of **roles** to one provider" — constrains (`composition.py:38, 177-183`) |
| `Candidate.provider` (`model-selection/…/model.py:37`) `[V]` | The **serving model vendor** — `anthropic`, `google`, `alibaba_modelstudio` — bounded by an optional enterprise allowlist, `approved_providers` (`model.py:26`) |
| `ShadowProvider.provider_id = "shadow-recorder"` (`governed-runtime-worker/…/workload.py:48`) `[V]` | A **tool provider** in the runtime's registry |

Only the second is a model vendor, and it is not the one the concentration limit measures.
The composer's constraint is over **role assignments in a team at composition time**: a
three-role team at 67% may give at most two roles to one agent supplier. It says nothing
about how many times anything calls a vendor. So a limit that "carries into execution"
cannot simply be re-evaluated later — **the quantity it would bind does not exist yet** `[G]`.

**Neither capability reaches the runtime `[V]`.** Outside their own packages,
`ugence_agent_workforce_composer` and `ugence_model_selection` appear only in boundary tests
that **forbid importing them** (for example `agent-runtime/tests/test_import_boundaries.py:42`)
and in the compiler's capability registry — where `MODEL_SELECTION` is
`disposition=ADVISORY, optional=True`, described as "policy-bounded model eligibility
(mandatory) + selection (advisory)" (`policy-workflow-compiler/…/capability_registry.py:105-112`),
and the workforce composer **is not a listed capability at all**. The governed loop the worker
runs composes neither.

**Concentration is a property of a sequence, and nothing in the selection path counts `[V]`.**
`ExecutionGate`'s `quota_available` condition reads a `quota_state` **signal the caller
supplies** (`gate.py:113-119`); the gate holds no history. The only stateful counter anywhere
in the runtime is the budget ledger — `PostgresBudgetLedger.reserve()`, idempotent per key,
with the ceiling enforced by a PostgreSQL `CHECK` constraint rather than in-process
bookkeeping (`durable-execution/…/budgets.py:43-72`, `postgres/schema.py:62-78`). Whatever
binds a mix at execution has to look like that, and nothing today does.

**Where the MEU would get the knowledge, and why it cannot.** §3.4 forbids the MEU reading
the worker's application schema, so a count would have to come from the exchange, from a third
store, or not from the MEU at all. The exchange is ruled out by D-4 itself: content is purged
once the terminal result is consumed, and §4.4's tombstone retains request identity, digests,
outcome, consumption acknowledgement and purge time — **it does not retain `model_ref` or
provenance** `[V]`. After a purge the exchange cannot say which vendor was called, so a
counter derived from it silently resets at the retention horizon. A third store is a new trust
boundary, refused by the same reasoning that settled D-4. And a counter the MEU both writes
and enforces against is the MEU marking its own homework.

| Option | Consequence |
|---|---|
| `PLANNING_ONLY` | Concentration limits stay advisory. Honest about today, and it leaves a plan free to promise a mix the runtime does not honour — the gap worth stating plainly rather than discovering. |
| `BIND_AT_AUTHORIZATION` | The limit binds before the request is written to the exchange: the worker refuses, the MEU never sees the request, and §6 gains no refusal. Consistent with `ModelAuthority` already issuing a **binding** ALLOW/DENY/HOLD/ESCALATE under non-compensatory eligibility (`authority.py:146, 172`) `[V]`, and with the registry's split of eligibility (mandatory) from selection (advisory). Needs a durable per-vendor counter shaped like the budget ledger, and a vendor-mix quantity that does not exist yet. |
| `BIND_AT_THE_MEU` | The MEU refuses a call that would breach the mix. Places the check closest to the act — and requires the MEU to hold state it also authors, over a store whose purge horizon resets the denominator. It also gives the MEU a second reason to refuse that is not derived from the authorization it was handed, which is the shape D-1 was careful to deny it. |

**Recommendation: `BIND_AT_AUTHORIZATION`, with the prerequisite stated rather than assumed.**
Binding at execution is right — a plan that promises a mix the runtime ignores is governance
theatre — but "at execution" must mean *before the authorized request is written*, not *at the
MEU*. That keeps the MEU what D-1 and §7 make it: a unit that performs one call and returns
one result, with no authority to refuse on grounds the authorization did not already settle.
So **§6 gains no D-5 refusal**, and the placeholder there resolves by removal rather than by
addition.

Two things must be built before this means anything, and neither is licensed by ruling D-5
`[G]`: a **vendor-mix quantity** over model invocations rather than role assignments, since
none of the three `provider` vocabularies is the one D-5 names; and a **durable per-vendor
counter** with a database-enforced ceiling, shaped like `PostgresBudgetLedger` and owned by
the worker. The audit ledger is not a substitute: it retains metering and provenance under D-4,
but deriving a live quota from an append-only audit trail makes the record load-bearing for
admission, which is not what it is for.


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
D-1; where the first step runs is D-2.

**Superseded 2026-09-10.** §4a and §4b are kept as the pre-ratification record and their
present tense is read as of the day they were written. D-1 and D-2 have since been ratified
(§4), and `SEPARATE_EGRESS_UNIT` is the answer §4b argued toward.

## 5 — What this document does not do

It specifies nothing. No interface, no package layout, no configuration surface, no
sequencing. An implementation specification written before D-1 and D-2 were answered would
have been a specification of one arbitrary reading among several, and the two readings of
D-2 were different products.

It also marks no gate identifier satisfied, admits nothing to the P3E-CTR or GRW-CTR
families, and changes no ratified pin.

**The implementation specification opened by these rulings is
`SPEC_MODEL_EGRESS_UNIT.md`,** written against D-1 through D-4 and stating plainly which
sections D-5 still blocks. The amendments D-2 requires to CR-5 and CR-4 remain outstanding
and are owner acts, not consequences of the spec. Nothing is implemented: no exchange
table is designed, no exchange exists, and no genuine provider call is authorized.
