# Roadmap: Ugence Reasoning Compute Governance (provisional name)

**Status: EXPLORATORY ROADMAP — NOT RATIFIED — NO IMPLEMENTATION AUTHORIZED.**

Nothing in this document is an owner ruling, a contract, a vocabulary, a default, a
schedule or a development commitment. No field name, enum member, budget value, model
tier, cache rule, terminal outcome or ownership assignment below is ratified. The
capability name *Reasoning Compute Governance* (RCG) is itself provisional.

This document exists so that a cross-cutting concern currently discussed in passing —
what it costs to invoke a probabilistic model, and who is allowed to authorize that
cost — has one place to be scoped before any capability grows it by accident.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` an owner decision still required; `[G]` an
unresolved gap. Every statement about future behaviour is written in a conditional or
future tense. Where this document says *would*, *could* or *may*, nothing exists.

---

## 1 — The governing distinction

> The model's internal reasoning may remain probabilistic. Ugence would make the
> **surrounding invocation process** bounded, authorized, observable, replayable where
> the inputs are actually carried, and economically accountable.

RCG is a hypothesis about the *envelope* around a model call, not about the model. It
would govern whether a call happens, how large it may be, how many times it may repeat,
which capability class it may reach, and what evidence of consumption survives
afterwards. It would say nothing about how the model arrives at its output.

### 1.1 — Required non-claims

Stated once, and load-bearing for everything below. Reasoning Compute Governance:

* does **not** make LLM reasoning deterministic;
* does **not** inspect, reconstruct or prove a model's private chain of thought, and no
  design below may be read as doing so;
* does **not** guarantee that the best candidate was generated;
* does **not** prove that omitted evidence or omitted candidates never existed;
* does **not** make a caller-supplied value authoritative;
* does **not** permit cost optimization to bypass governance;
* does **not** authorize execution of anything;
* does **not** replace Risk Authority, ActionGate, Policy Authority, an Agent
  Constitution, Context Minimization or Runtime Assurance, and would depend on them;
* is **not** part of the implemented Agentic Proposer public API. `[V]` No symbol,
  field or module in `packages/capabilities/agentic-proposer/` relates to compute
  budgeting, and its authorized public surface is pinned by
  `packages/capabilities/agentic-proposer/public_api.json`;
* ratifies nothing — see the status line at the head of this document.

### 1.2 — Precondition check performed for this roadmap

`[V]` No Reasoning Compute Governance implementation exists in this repository under
this or another name: a repository-wide search for *compute budget*, *token budget*,
*reasoning compute* and *compute governance* returns no capability package
implementing an invocation-level compute envelope. What does exist — and what RCG must
not duplicate — is inventoried in §4.

---

## 2 — The questions in scope

RCG-shaped questions, recorded as questions. None is answered here.

* Whether a probabilistic model call is necessary at all.
* Which capability tier may be invoked.
* What context and evidence may be supplied.
* How many model calls, tool calls and repair attempts are permitted.
* How many candidates may be generated.
* When a more capable and more expensive model may be used.
* When deterministic processing is sufficient.
* When execution must stop, abstain or escalate.
* How actual consumption is measured.
* When a previously validated result may be reused safely.

`[R]` Each of these becomes a ruling only through the phases in §9 and the register in
§11. Turning any of them into an answer inside this document would be exactly the
failure it is written to prevent.

---

## 3 — Product and economic motivation

RCG would **not** lower a provider's price per token. `[I]` It is a hypothesis about
lowering *total expected cost* by reducing:

unnecessary model invocations; unnecessary use of frontier models; oversized context;
open-ended agent loops; redundant candidate generation; repeated tool retrieval;
repeated semantic criticism; schema-repair loops; repeated work on identical,
still-fresh inputs; and model calls for decisions deterministic code can make.

The proposed mechanism, in order:

1. deterministic preflight;
2. cheapest-adequate model routing;
3. context minimization;
4. bounded generation;
5. deterministic validation and filtering;
6. tightly bounded repair;
7. capability escalation only under authorized, observable conditions;
8. measured consumption and later audit.

**These eight are design hypotheses for future ratification, not implemented
behaviour, and no cost reduction is claimed or measured.** `[G]` No baseline exists in
this repository against which any of them could be evaluated; establishing one is
RCG-6 work, not a precondition assumed here.

---

## 4 — What already exists, and what RCG must not duplicate

This inventory is the most important section for scoping. Three of the eight proposed
mechanisms are already owned, in part, by shipped capabilities.

### 4.1 — Model Authority (`packages/capabilities/model-selection/`)

`[V]` Model Authority already decides **which model, if any, is authorized to execute a
specific request** under policy, capability, jurisdiction, security, cost and runtime
conditions, and issues a binding `ALLOW`/`DENY`/`HOLD`/`ESCALATE` decision
(`packages/capabilities/model-selection/src/ugence_model_selection/authority.py:1-35`).
Its request contract already carries a per-request cost ceiling
(`.../model.py:29`), a provider allowlist (`.../model.py:25`), a residency
constraint (`.../model.py:27`) and a latency limit (`.../model.py:28`), and the
cost cap is enforced as a **mandatory eligibility gate**, not a ranking preference
(`.../gate.py:168-172`). Eligibility precedes ranking; a cheaper candidate never
overrides a mandatory policy failure (`.../authority.py:24-27`).

`[V]` Model Authority explicitly disclaims a large part of what §3 proposes: it "does
not invoke models, route, retry, fail over, load balance, schedule, orchestrate,
authorize actions, register providers, or manage credentials"
(`.../version.py:11-13`).

`[I]` **Consequence for RCG.** Mechanism 2 (*cheapest-adequate routing*) is
substantially an existing capability at the level of *which model is authorized for one
request*. What is absent is the layer above it: a **multi-call invocation envelope**
that bounds how many authorized requests an agentic run may make, and under what
observable condition a *later* request in the same run may name a more capable class.
`[G]` RCG must not re-implement model authorization; if it exists at all, it plausibly
consumes Model Authority rather than replacing it. That boundary is unresolved.

### 4.2 — Agent Runtime budgets (`packages/runtime/agent-runtime/`)

`[V]` A generic reserve-before-execute budget coordinator already exists over
caller-named numeric dimensions — the docstring names `token_units`, `model_cost`,
`external_api_calls`, `compute_units` as *caller* names, not hardcoded semantics — and
enforces `available = limit − consumed − reserved` so concurrent quanta cannot
oversubscribe a shared ceiling
(`packages/runtime/agent-runtime/src/ugence_agent_runtime/orchestration/budgets.py:1-23`).
Non-finite and negative amounts fail closed (`.../budgets.py:33-45`).

`[V]` Critically, it **measures nothing itself**: it "never fabricates provider usage",
and with no runtime usage telemetry in that release settlement charges the full
reservation as consumed under a documented conservative rule, recording
`actual_known=False` so an audit reader cannot mistake a conservative charge for a
measured one (`.../budgets.py:19-23`, `.../budgets.py:129-133`). `settle` does accept an
injected measured actual (`.../budgets.py:236-243`), so the seam for real metering
exists; `[G]` nothing in that package supplies one.

`[V]` Deterministic elapsed-time budgets exist via an injected clock
(`.../runtime/timeout.py:1-30`).

`[I]` **Consequence for RCG.** A generic enforcement substrate for numeric ceilings
already exists at the orchestration layer. `[G]` What does not exist is (i) any
authority that says *what the limits should be for a given organizational role or
invocation*, and (ii) any binding of the runtime's `PortfolioBudget` dimensions to
provider-measured consumption. RCG-3 would most plausibly configure this component
rather than build a second one; that is a hypothesis, not a ruling.

### 4.3 — Context Minimization token accounting (`packages/capabilities/context-minimization/`)

`[V]` Three distinct measurements are already contracted and kept deliberately
separate: context measurement, a **pre-call estimate** of the complete serialized
request counted by an *injected* counter, and **provider-reported usage** after an
attempt — which "never overwrites the pre-call estimate, and is NOT an invoice"
(`packages/capabilities/context-minimization/src/ugence_context_minimization/token_accounting.py:1-31`).

`[V]` `ProviderTokenUsage` already carries input, cached-input, cache-write, output,
`reasoning_tokens` and total counts plus the provider request id and the adapter
identity that parsed them (`.../token_accounting.py:284-304`). `ApiCallTokenRecord`
already binds one provider attempt to an attempt number, a retry-of reference, the
minimization run fingerprint, a `usage_availability` state and an
`usage_unavailable_reason` (`.../token_accounting.py:432-466`), and
`LogicalRequestTokenSummary` already aggregates attempt, success, failure, retry and
usage-unknown counts across one logical request (`.../token_accounting.py:580-613`).
The module implements **no pricing authority and no provider tokenizer**
(`.../token_accounting.py:27-31`).

`[I]` **Consequence for RCG.** Much of what §8 lists as "prospective observability"
already has a contracted, deterministic, replay-friendly shape here. `[G]` RCG must not
define a second, competing usage record. Whether the metering record belongs to Context
Minimization at all — it arrived there because minimization needed to *prove* what it
saved, not because measurement is minimization's job — is itself unresolved and is a
plausible early RCG-0 finding.

### 4.4 — Context Minimization proper

`[V]` Extractive, never generative; creates no authority; fails closed when
caller-defined equivalence cannot be established
(`packages/capabilities/context-minimization/README.md:1-30`). `[I]` Mechanism 3
(*context minimization*) is therefore an existing capability, and RCG's only plausible
contribution is a **ceiling** on the envelope handed to it — not a second minimizer.

### 4.5 — The authority layers RCG would depend on and never replace

`[V]` Policy Authority is the single platform-wide issuer/verifier of signed, versioned
policy (`packages/policy-authority/README.md:1-16`). `[V]` Risk Authority turns an
approved governance decision into scoped, time-bound, revocable runtime authority
enforced at the point of action (`packages/risk_authority/README.md:1-20`). `[V]` Action
Clearance may preserve, narrow, hold, escalate or block an existing authorization and
"may never create authority, broaden authorization, replace ActionGate, dispatch
execution" (`packages/capabilities/action-clearance/README.md:1-12`). `[V]` Decision
Authority governs when a recommendation may become a binding business decision
(`packages/capabilities/decision-authority/README.md:1-20`).

`[G]` **The Agent Constitution does not exist.** This is already recorded as a residual
limitation of the Agentic Proposer
(`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2604-2607`)
and as an open architectural dependency in the readiness ADR
(`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:105`). Any hypothesis
that assigns role-level compute ceilings to an Agent Constitution assigns them to
something that has no implementation to receive them.

---

## 5 — Relationship to the Agentic Proposer

`[V]` The Agentic Proposer governs the structure, identity, validation and replay of
observable proposals. It does not make a model's private reasoning deterministic, and
its specification carries no compute, cost, budget or model-tier concept.

`[I]` A future RCG boundary might constrain the probabilistic computation used to
*produce* those proposals — whether candidate generation uses a model at all, a maximum
generation effort, a number of attempts, a permitted capability class, the
evidence/context envelope, whether a semantic critic is invoked, and the conditions
under which a higher-cost tier may be *requested*.

**Nothing of the sort is added to `CognitiveRoleContract`, `ProposerAdvisory`,
`ProposerProcessRecord`, `AdvisoryCandidateSet`, `P_unsigned` or any other contract by
this document.** `[R]` Contract placement and identity treatment are owner decisions
(register items D6 and D7 in §11).

`[V]` Two structural facts bound anything RCG could later add there:

* **No numeric field is possible in that contract family.** The canonicalisation
  substrate raises `BareNumberError` on any `int` and any `float`
  (`packages/jcs/src/ugence_jcs/canon.py:86-93`) and `UnsupportedTypeError` on
  `Decimal`, at any nesting depth; the specification's C3 therefore bars every numeric
  type from every contract and container
  (`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:435-443`,
  and the reproduction at `:106-119`). Any future budget magnitude in that family must
  be a canonical typed **string**, with its encoding ratified at that time.
* **Domain completion and selection are structurally unconstructible in S1** (C7 at
  `:603-616`, C9 at `:659-700`), so RCG cannot assume a downstream evaluation or
  selection step exists to be budgeted.

`[I]` This roadmap deliberately does **not** make the frozen S1 specification the design
home for a cross-cutting capability. S1 receives one non-normative pointer to this
document and nothing else.

---

## 6 — Constraints inherited from the OD-8 / OD-9 review

Each finding was re-verified against the current repository for this roadmap. Where the
repository states something narrower than the finding as given, the narrower statement
is recorded.

1. **Most current candidate inputs are caller-supplied; structure and digest-binding do
   not confer authority.** `[V]` Of `CandidateAdvisory`'s fields only `is_eligible` is
   package-computed, and every other field — `candidate_id` included — "enters through
   caller-supplied builder parameters, so ranking on any of them would let the caller
   steer selection" (`.../S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:3143-3151`).
   **RCG constraint:** no caller-supplied field may become a cost, difficulty, merit or
   escalation signal.

2. **Inclusion in `P_unsigned` establishes integrity after construction, not
   provenance.** `[V]` "No amount of ordinary field validation authenticates a
   caller-supplied Boolean — a validator sees the value, not its provenance", and the
   operative guarantee is independent **recomputation** by the consumer, not
   construction discipline (`:1820-1848`). **RCG constraint:** an authorized-compute
   value inside a digest proves only that it was not altered afterwards. Proving *who
   issued it* requires a separate, ratified authority and provenance path.

3. **A model's self-report cannot authorize its own budget.** `[I]` The repository does
   not state this in these words, so it is recorded as inference from two verified
   facts: the caller-provenance rule in (1), and `[V]` the explicit refusal to rank on
   `uncertainties` because doing so "would additionally punish honest disclosure"
   (`:3149-3151`). **RCG constraint:** a model's expressed confidence, difficulty or
   desire for more computation is at most an input to a deterministic control that
   evaluates it against an authoritative policy. It never authorizes anything.

4. **Deterministic replay reaches only the inputs the replayable boundary carries.**
   `[V]` A criterion needing "a scoring service, a per-tenant policy table, a model
   call, wall-clock time, or any datum not carried by `AdvisoryCandidateSet` — would be
   unreplayable by the very function OD-7 ratifies to replay it, and is therefore
   excluded" (`:3160-3170`); and identity "binds referenced identifiers, not referenced
   contents" (`:2525-2560`). **RCG constraint:** hidden external state — a routing
   table, a live price list, a provider's internal fallback — is not replayable by
   inclusion in a record that merely names it.

5. **Numeric budget representation requires deliberate canonicalisation decisions.**
   `[V]` As in §5: `BareNumberError` on `int`/`float`, `UnsupportedTypeError` on
   `Decimal` (`canon.py:86-93`), and the ratified consequence that "any numeric rank
   must be a canonical decimal *string*" (`:3155-3159`). **RCG constraint:** casual use
   of floating-point budget values in any identity-bearing artifact is excluded by the
   substrate, not by preference.

6. **Candidate-set membership and upstream omission remain disclosed ceilings.** `[V]`
   Part K records that identity does not bind the bodies behind referenced identifiers,
   and that replay "establishes correspondence to the *referenced artifact*; it does not
   make the advisory digest bind the observation *content*" (`:2525-2585`). **RCG
   constraint:** compute governance must not be presented as proving that all possible
   candidates or all relevant evidence were supplied. Reducing candidate count for cost
   makes this ceiling *more* consequential, not less.

7. **Authority for one responsibility does not transfer to another.** `[V]` The
   `DomainEvaluationProvider` "is authoritative **only** for the domain-evaluation
   responsibility OD-7 ratifies; it does **not** acquire business-preference authority"
   (`:3160-3162`). **RCG constraint:** domain-evaluation authority confers no budget,
   routing, model-tier or business-preference authority, and neither does any other
   single-responsibility provider.

8. **Caller-supplied fields must not be repurposed as trusted signals.** `[V]` The
   ratified statement is explicit: "Timestamps, identifiers, dispositions, review
   actions, reference counts, assumption counts and uncertainty counts **must not** be
   repurposed as merit proxies" (`:3143-3148`). `[I]` The extension from *merit* to
   *cost, difficulty and escalation* is inference, on identical provenance grounds, and
   is recorded as such rather than as a ratified rule.

`[R]` Findings 1–2 and 4–7 are recorded as architectural constraints on any future RCG
design. Findings 3 and 8 are recorded as inference-grade constraints pending their own
ratification.

---

## 7 — Preliminary responsibility hypothesis, and where it conflicts with the repository

The hypothesis under evaluation, **not an owner ruling**:

| Responsibility | Preliminary owner | Repository assessment |
| --- | --- | --- |
| Authorize maximum reasoning scope for an organizational role | Agent Constitution or Policy Authority | `[G]` The Agent Constitution does not exist (§4.5). Policy Authority issues and verifies *policy versions* for registered families (`packages/policy-authority/README.md:8-12`); it is a plausible issuer, but a compute-policy family would have to be registered and ratified. |
| Authorize an invocation-specific compute envelope | Policy/Decision Authority or another control-plane authority | `[G]` No component issues a per-invocation envelope today. Decision Authority governs *binding business decisions* (`packages/capabilities/decision-authority/README.md:1-20`), which is a different object. **Conflict:** the hypothesis names two candidates for one unowned responsibility. |
| Enforce model, token, tool, retry and elapsed-time limits | Agent Runtime | `[I]` Best-supported row. Generic numeric ceilings and elapsed-time budgets already exist (§4.2). `[G]` Retry and tool-call ceilings specifically are not shown to exist in that component. |
| Operate within the authorized envelope while producing candidates | Agentic Proposer | `[I]` Plausible as *subject* of the envelope. `[V]` The Proposer carries no compute concept and its contract family admits no numeric field (§5), so it cannot be the envelope's home without a ratified string representation. |
| Decide deterministic eligibility, domain evaluation and selection | Existing/future governed deterministic components | `[V]` Partly real (Equation 1 eligibility), partly unconstructible in S1 (C7, C9 — §5). |
| Measure actual provider and tool consumption | Runtime metering | **Conflict.** `[V]` The contracted provider-usage record lives in **Context Minimization** (§4.3), while the Agent Runtime budget coordinator has *no* usage telemetry (§4.2). The hypothesis names a component that does not hold the measurement. |
| Preserve usage evidence and authorized-versus-consumed comparison | Audit/evidence record | `[G]` No component compares an authorized envelope to consumed usage, because no authorized envelope exists to compare against. |
| Permit consequential action after proposal production | Risk Authority and ActionGate | `[V]` Well supported and unchanged by anything here (§4.5). |

`[R]` **Two conflicts are left unresolved rather than reconciled.** First, metering sits
in a capability whose stated job is minimization, not measurement. Second, the
invocation-envelope issuer is named twice and implemented nowhere. Resolving either by
assertion in this document would be the ratification this task excludes.

`[I]` **The whole capability is explicitly not assigned to the Agentic Proposer** merely
because model reasoning occurs upstream of a proposal. On the repository evidence the
responsibility is split across at least four components, and the Proposer holds the one
role — *subject of the envelope* — that carries no authority at all.

---

## 8 — Prospective control dimensions

**Illustrative only. These are not field names, and no unit, default or type is
selected.** For each: what it limits · who might authorize it · what might enforce it ·
how usage might be measured · what might happen at the limit.

| Dimension | Limits | Possible authorizer | Possible enforcer | Possible measurement | At the limit |
| --- | --- | --- | --- | --- | --- |
| Max input tokens | Request size per call | `[R]` unresolved | `[I]` pre-call, at the invocation seam | `[V]` a pre-call estimate shape exists (§4.3) | `[R]` unresolved |
| Max output tokens | Generation length per call | `[R]` unresolved | `[I]` provider parameter | `[V]` provider-reported output tokens (§4.3) | `[R]` unresolved |
| Max total model calls | Loop breadth per invocation | `[R]` unresolved | `[I]` Agent Runtime | `[V]` attempt counts exist (§4.3) | `[R]` unresolved |
| Max tool calls | Retrieval amplification | `[R]` unresolved | `[I]` Agent Runtime | `[G]` no tool-call meter identified | `[R]` unresolved |
| Max candidates | Generation redundancy | `[R]` unresolved | `[I]` the producing component | `[I]` candidate-set cardinality is observable | `[R]` unresolved |
| Max repair attempts | Schema-repair loops | `[R]` unresolved | `[I]` Agent Runtime | `[V]` retry counts exist (§4.3) | `[R]` unresolved |
| Max semantic-review passes | Critic loops | `[R]` unresolved | `[G]` no critic component exists | `[G]` none | `[R]` unresolved |
| Max elapsed time | Wall-clock exposure | `[R]` unresolved | `[V]` injected-clock budgets exist (§4.2) | `[V]` same | `[R]` unresolved |
| Permitted capability classes | Which tier may be reached | `[R]` unresolved | `[V]` Model Authority gates eligibility per request (§4.1) | `[I]` decision provenance is recorded | `[V]` `DENY`/`HOLD`/`ESCALATE` already exist as decisions |
| Permitted fallback/escalation classes | Where a run may go next | `[R]` unresolved | `[G]` Model Authority explicitly does not route or fail over (§4.1) | `[G]` none | `[R]` unresolved |
| Second-model critic permitted/required | Correlated-error exposure | `[R]` unresolved | `[G]` none | `[G]` none | `[R]` unresolved |
| Context/evidence size ceiling | Envelope handed downstream | `[R]` unresolved | `[I]` upstream of Context Minimization | `[V]` context measurement exists (§4.3) | `[R]` unresolved |
| Cache reuse permission and freshness | Whether a prior result may stand | `[R]` unresolved | `[G]` none | `[G]` none | `[R]` unresolved |
| Overall invocation cost ceiling | Total spend per invocation | `[R]` unresolved | `[V]` a per-*request* cost cap exists (§4.1); no per-*invocation* one does | `[G]` no pricing authority exists (§4.3) | `[R]` unresolved |
| Per-stage / per-provider allocation | Distribution within a ceiling | `[R]` unresolved | `[I]` Agent Runtime named dimensions (§4.2) | `[V]` per-provider attribution exists (§4.3) | `[R]` unresolved |

`[R]` **No concrete default, unit, bound or vocabulary is selected**, and no vendor model
name, current price or commercial product tier appears as a normative value anywhere in
this document. `[I]` If a tier vocabulary is ever ratified it should be a **versioned
capability class or an organization-controlled routing profile**, precisely so that a
provider's product renaming is not a contract change. That is a recommendation, not a
ruling.

---

## 9 — Cost-control mechanisms, with their risks

Each mechanism is a hypothesis. The risk paragraph is the part that matters.

**9.1 Deterministic preflight.** Check authority, input completeness, policy
applicability and deterministic rules *before* invoking a model. `[I]` The checks most
likely to avoid a call are: absent or expired authority (Risk Authority's domain),
structurally invalid requests (contract validation), and cases a deterministic rule
already decides. *Risk:* a preflight that merely predicts the model's answer is a second
decision procedure with no authority; preflight must **refuse or admit**, never
pre-decide.

**9.2 Capability-tier routing.** Use the cheapest sufficient class; escalate only on an
observable condition. Illustrative triggers — structural validation failure, unresolved
evidence conflict, a semantic-verification requirement, risk classification, a
policy-mandated review, or a lower tier's failure to produce a conformant result within
its own retry budget. **None of these is ratified.** `[V]` The model may *request*
escalation; it cannot authorize it (§6, finding 3), and a deterministic control must
evaluate the request against an authoritative policy. *Risk:* `[V]` Model Authority
already owns per-request authorization and explicitly does not route or fail over
(§4.1), so an RCG router risks becoming a second, unauthorized authorization path.

**9.3 Context minimization.** Supply only evidence relevant to the declared
organizational function and permitted task. `[V]` This is an existing capability with a
fail-closed equivalence contract (§4.4). *Risk:* duplication. RCG's contribution, if
any, is a ceiling on what enters — an *admission* concern the minimizer explicitly
places upstream of itself.

**9.4 Bounded candidate generation.** Prefer one bounded structured generation yielding
a limited candidate set over one open-ended call per candidate. *Risk:* the tradeoff is
cost against diversity, and a low candidate count **suppresses alternatives**. `[V]` It
must never be presented as evidence that the best candidate was considered; the
membership ceiling of §6 finding 6 applies directly and gets worse as the budget
tightens.

**9.5 Deterministic validation before semantic review.** Run schema, reference,
identity, eligibility and domain checks before any model-based critic. `[I]` Cheapest
first, and it also keeps the expensive stage from being the thing that discovers a
malformed input. *Risk:* none identified beyond ordering.

**9.6 Bounded repair.** Permit a small, explicitly authorized number of repairs for
malformed structured output. `[R]` **The terminal behaviour after exhaustion is not
chosen here** — see §10 and register item D8.

**9.7 Conditional critic or second-model review.** Invoke semantic criticism only when
risk, policy or deterministic validation requires it. *Risk:* an always-on
model-as-judge loop multiplies cost by a constant factor for every invocation, and
**correlated model errors** mean a critic drawn from the same family may agree with a
wrong output for the same reason it was produced. A critic is not independent evidence
merely because it is a second call.

**9.8 Deduplication.** Remove identical or demonstrably equivalent candidate
representations before further evaluation. `[V]` The distinction is already made in this
repository: *structural* deduplication removes exact duplicates and declared redundancy
sets and is explicitly **narrower** than equivalence-preserving minimization
(`packages/capabilities/context-minimization/README.md:20-30`). *Risk:* byte or field
equality is safe; **semantic equivalence is not**, and asserting it without a ratified
equivalence authority silently discards candidates that differed in a way nobody
declared.

**9.9 Cache and result reuse.** Reuse is explorable only where a canonical identity
binds *all* relevant inputs: organizational role and mandate; policy/profile versions;
normalized evidence; request identity; relevant model and routing configuration;
tool/provider versions; and a freshness constraint. **Caching is unsafe if evidence,
authority, policy, model configuration or freshness has changed.** `[R]` No cache key,
TTL, or placement in `P_unsigned` or any other identity projection is ratified here.
*Risk:* a cache keyed on inputs but not on *authority* will serve a result computed
under a mandate that has since been revoked.

**9.10 Early fail-closed termination.** Stop probabilistic work when authority is
absent, required evidence is absent, the request is structurally invalid, a
deterministic refusal already applies, or the authorized envelope is exhausted. `[R]`
The terminal outcomes remain subject to separate ratification (§10).

---

## 10 — Authorization, consumption, request and billing are four different things

* **Authorized compute** — the maximum probabilistic resources the organization permits
  for the invocation.
* **Consumed compute** — what the runtime and providers actually used.
* **Requested compute** — what an agent or model asks to use.
* **Billed compute** — what the provider reports or charges.

These are **not interchangeable**, and no design may let one stand in for another. `[V]`
The repository already draws two of these lines: provider-reported usage "never
overwrites the pre-call estimate, and it is NOT an invoice"
(`.../token_accounting.py:16-21`), and the Agent Runtime marks a conservatively charged
reservation as *not* an actual measurement (`.../budgets.py:129-133`).

An agent or model **may request** additional compute and **must not authorize** it.
Actual usage must come from runtime or provider measurement, never from model
self-report. `[R]` A future audit record should be able to compare authorized against
consumed compute; **its contract shape and identity placement are not decided here.**

### 10.1 — Budget-exhaustion behaviour: options, not a choice

Possible outcomes, recorded without selection: terminate and `ABSTAIN`; request
additional authority; `ESCALATE`; return `NEED_EVIDENCE` **only** when the actual cause
is missing evidence; continue with deterministic processing only; or return a bounded
partial advisory if a future contract explicitly permits one.

**Budget exhaustion is not evidence insufficiency and must not be reported as
`NEED_EVIDENCE`.** A model's desire to continue is not proof that more compute is
necessary.

`[V]` Two repository facts constrain the eventual choice. `ESCALATE` currently has no
in-contract destination on a no-selection run: R-1a leaves
`requested_review_destination_role_ref = None`
(`packages/capabilities/agentic-proposer/src/ugence_agentic_proposer/contracts.py:602-618`),
and while `CognitiveRoleContract.escalation_role_ref` exists (`contracts.py:294`), `[G]`
no ratified rule connects it to a terminal `ESCALATE`
(`.../S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:3405-3415`). `[I]` An RCG exhaustion
outcome of `ESCALATE` would therefore need the same severity-and-destination authority
that OD-9 found missing.

---

## 11 — Identity, provenance and replay: the open questions

Recorded as questions. `[R]` unless a ratified artifact already answers them.

1. What authoritative object issues an invocation budget? `[R]`
2. Is the budget role-level, mandate-level, invocation-level, or layered? `[R]`
3. Which identity/version proves the governing compute policy? `[R]` — `[V]` Policy
   Authority already issues, signs and verifies versioned policy for registered
   families (`packages/policy-authority/README.md:8-12`), so the *mechanism* may exist
   even though the family does not.
4. Which parts, if any, belong inside a proposal's identity projection? `[R]` — `[V]`
   constrained by C3's no-numeric rule (§5).
5. Is compute authorization bound to the proposal, the process record, or a separate
   execution record? `[R]`
6. How is actual usage attested? `[R]` — `[G]` no attestation path exists today.
7. May provider-reported token counts be trusted directly, or must the runtime
   reconcile them? `[R]` — `[V]` the existing record already keeps a
   `usage_availability` state and the identity of the adapter that parsed the provider's
   numbers (`.../token_accounting.py:284-304`), which is the shape reconciliation would
   need but is not itself reconciliation.
8. How are model and routing-policy versions identified without embedding unstable
   vendor names? `[R]`
9. What can deterministic replay prove? `[R]` — `[V]` bounded by §6 finding 4.
10. What remains an explicitly disclosed ceiling? `[R]` — `[V]` at minimum the
    membership and omission ceilings of §6 finding 6.

---

## 12 — Privacy, security and retention

Roadmap considerations, none designed: tenant isolation; sensitive-evidence
minimization; provider data-retention requirements; prompt and result caching; cache
invalidation and deletion; model-provider routing restrictions; geographical and
organizational processing constraints.

Adversarial considerations specific to a *budget*: prevention of budget escalation
through adversarial prompts (a prompt that talks a control into raising its own
ceiling); **denial-of-wallet** and infinite-loop attacks; tool-use amplification;
repeated repair amplification.

`[V]` Two existing footholds: Model Authority already gates on approved providers,
region and residency (`.../model.py:25-27`), and the token record already carries tenant,
workflow, agent and task attribution (`.../token_accounting.py:366-373`).

**Auditability without private chain-of-thought.** Ugence should record observable
inputs, outputs, tool activity, routing decisions, validation results and measured
usage. It should **not** record, reconstruct or claim to verify a model's private chain
of thought — and no observability requirement in §13 may be read as requiring it.

---

## 13 — Observability and economic evaluation

Prospective operational measures. **None is ratified as a contract field**, and several
already have a shape in §4.3 that a future design should reuse rather than re-invent:

authorized versus consumed tokens; model calls per proposal; tool calls per proposal;
candidates generated and retained; repair attempts; cache hit/reuse rate; capability-tier
escalation rate; deterministic-preflight avoidance rate; validation-failure rate;
semantic-review invocation rate; elapsed time; provider-reported cost; proposal
completion, abstention and escalation rates; cost per conformant proposal; cost per
ultimately authorized action.

**Cost is an operational measurement, not decision authority.** A cheaper proposal must
not bypass safety, evidence, policy or action authorization, and no metric above may be
wired into an authorization path.

---

## 14 — Provisional phases

**Non-ratified. These are a structured path for future owner decisions, not approved
development commitments, and carry no schedule.**

**RCG-0 — architectural scoping.** Determine ownership boundaries; inventory existing
budget, metering, context-minimization, runtime and audit capabilities (§4 is a first
pass); identify duplication risks — at least Model Authority (§4.1), Agent Runtime
budgets (§4.2) and Context Minimization token accounting (§4.3); prepare an
owner-decision brief. *Exit:* the register in §15 is answerable.

**RCG-1 — authority and policy model.** Who may set ceilings; role versus mandate versus
invocation budgets; capability classes and escalation authority; exhaustion behaviour.

**RCG-2 — contract and identity design.** Any budget envelope; representation and
cardinality; canonicalisation (bounded by §5); identity and provenance binding;
authorized-versus-consumed record shapes.

**RCG-3 — deterministic enforcement.** Runtime limits; routing control; retry and
tool-call limits; fail-closed behaviour; adversarial and mutation tests.

**RCG-4 — metering and audit.** Trustworthy usage capture; authorized-versus-consumed
comparison; provider reconciliation; immutable audit evidence.

**RCG-5 — caching and adaptive optimization.** Canonical reuse identity; freshness and
invalidation; tier escalation; conditional critics; cost/quality evaluation.

**RCG-6 — pilot and ratification evidence.** Shadow deployment; cost and quality
baselines; safety and authority regression testing; go/no-go criteria for enforcement.

`[I]` RCG-0 is the only phase this document supports starting. Every later phase depends
on rulings that do not exist.

---

## 15 — Owner-decision register

Ten decisions, consolidated. **These are not OD numbers.** `[V]` The `OD-n` sequence is
the Agentic Proposer readiness ADR's own record
(`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:577`), and no authority
has been given to extend it for a different capability. The `RCG-D` prefix below is a
local label for this document only and confers nothing.

| # | Decision | Status |
| --- | --- | --- |
| RCG-D1 | **Owning capability.** Does RCG exist as a capability at all, and if so where — a new package, an extension of Agent Runtime, or a policy family under an existing authority? | `[R]` |
| RCG-D2 | **Compute-authorizing authority.** What object issues an invocation compute envelope, and under whose signature? §7 names two candidates and implements neither. | `[R]` / `[G]` |
| RCG-D3 | **Enforcement component.** Which component enforces which dimension, and specifically whether Agent Runtime's existing coordinator (§4.2) is configured rather than duplicated. | `[R]` |
| RCG-D4 | **Budget scope.** Role, mandate, invocation, or layered — and how layers compose when they disagree. | `[R]` |
| RCG-D5 | **Capability-tier vocabulary.** Whether versioned capability classes or organization-controlled routing profiles exist at all, and their relationship to Model Authority's existing per-request decision. No vendor name may be a normative value. | `[R]` |
| RCG-D6 | **Budget representation and canonicalisation.** Typed string encoding, cardinality and comparison rules, given that the substrate admits no numeric type (§5). | `[R]` |
| RCG-D7 | **Identity and provenance placement.** Whether any compute value enters an identity projection, and what proves who issued it (§6 finding 2). | `[R]` |
| RCG-D8 | **Exhaustion and escalation behaviour.** Which terminal outcome follows an exhausted envelope, given that `ESCALATE` has no ratified destination today (§10.1). | `[R]` / `[G]` |
| RCG-D9 | **Cache/reuse authority and freshness.** Whether reuse is permitted, keyed on what, invalidated by what, and authorized by whom. | `[R]` / `[G]` |
| RCG-D10 | **Usage attestation and audit record.** Who owns the metering record, whether provider counts are reconciled, and where the authorized-versus-consumed comparison lives — noting that today's record sits in Context Minimization (§4.3) and the runtime's budget has no telemetry (§4.2). | `[R]` / `[G]` |

`[G]` Two structural gaps sit underneath the register and are not decisions anyone can
take in isolation: the **Agent Constitution does not exist** (§4.5), and **no component
holds an invocation-level compute envelope** for any authority to bind to.

---

## 16 — What this document changed

Documentation only. It adds this file and two non-normative pointers to it. It adds no
field, no vocabulary, no default, no test, no gate and no runtime behaviour, and it
neither authorizes nor blocks any implementation.
