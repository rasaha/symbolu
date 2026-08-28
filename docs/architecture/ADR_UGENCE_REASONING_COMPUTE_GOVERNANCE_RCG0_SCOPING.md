# ADR — Reasoning Compute Governance (RCG-0): Architectural Scoping and Boundary Rulings

## 1. Status, date, baseline, scope, decision owners

- **Status:** **Accepted (ratified) — documentation only.** This ADR records owner
  rulings on the **ownership, authority, enforcement, scope, vocabulary,
  representation, identity placement, exhaustion, reuse and attestation boundary** of
  the capability provisionally named **Reasoning Compute Governance (RCG)**.
  Acceptance is of the *scoping*. **No RCG implementation is authorized by this ADR**,
  and none exists.
- **Date:** 2026-08-28.
- **Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
  default head `237e16ab` (merge of PR #1498, *Add exploratory Reasoning Compute
  Governance roadmap (non-ratified, documentation only)*).
- **Scope:** the ten RCG-0 decisions `RCG-D1` – `RCG-D10` and ten standing principles,
  together with the verified capability-boundary findings and the residual gaps they
  rest on.
- **Non-scope:** this ADR introduces **no runtime code, no package, no contract, no
  field, no enum member, no protocol, no validator, no public API, no test, no CI
  change, no package version and no platform-freeze change**, and it selects **no**
  concrete limit, unit, encoding grammar, range, default, capability class, tier count,
  provider, commercial model, price, cache key, TTL or record shape. It changes
  **architecture documentation only**.
- **Decision owners:** Ugence platform architecture owners for Policy Authority, Model
  Authority, Risk Authority, Decision Authority, Agent Runtime, Runtime Assurance,
  Context Minimization and Agentic Proposer.
- **Related:**
  - [`ROADMAP_UGENCE_REASONING_COMPUTE_GOVERNANCE.md`](ROADMAP_UGENCE_REASONING_COMPUTE_GOVERNANCE.md)
    — the exploratory scoping this ADR rules on; it remains exploratory and ratifies
    nothing of its own.
  - [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) — the single
    platform-wide issuer/verifier of signed, versioned policy families (P-1 … P-11);
    `RCG-D2` and `RCG-D5` depend on it.
  - [`ADR_RISK_AUTHORITY_RA6_AUTHORITY_LIFECYCLE.md`](ADR_RISK_AUTHORITY_RA6_AUTHORITY_LIFECYCLE.md)
    — Risk Authority owns runtime authorization envelopes and their revocation; the
    boundary `RCG-D2` and `RCG-D8` must not cross.
  - [`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`](ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md)
    — OD-1 … OD-10; unchanged by this ADR, and `RCG-D7` is constrained by OD-7 part 5's
    rejected alternative.

> *This ADR changes **no** production code, package, wheel, public API, schema, frozen
> identifier, serialization, digest, contract shape or existing authority boundary. It
> records ratified scoping rulings and defers every implied code or package change to
> later, separately reviewed, separately authorized milestones. C7 and C9 are unmodified
> and remain active; OD-7, OD-8, OD-9 and OD-10 are neither implemented nor reopened. The
> platform-freeze substantive digest is unchanged before and after this ADR
> (`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).*

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` an owner ruling; `[G]` an unresolved gap.

---

## 2. Context

The cost, extent and escalation of probabilistic model computation — and who may
authorize it — had no single architectural home. The exploratory roadmap merged as
PR #1498 scoped the concern and left ten decisions open so that no capability would grow
the concern by accident.

RCG-0 inspected the repository against that scoping. The governing distinction the
owners ratify is:

> A probabilistic model's internal reasoning may remain probabilistic. Ugence governs the
> **surrounding invocation process** — whether probabilistic computation is necessary,
> what authority permits it, its maximum authorized extent, capability routing, context
> and evidence exposure, model/tool/candidate/repair counts, escalation, deterministic
> validation and early stopping, usage measurement, audit evidence and safe result reuse.

RCG does **not** make private model reasoning deterministic and does not inspect,
preserve, replay or prove private chain-of-thought.

### 2.1 — What the repository already holds

The scoping's central finding is that most of the mechanism already exists and only one
object is missing.

| Capability | Status | Holds | Does not establish |
| --- | --- | --- | --- |
| **Model Authority** | `[V]` Implemented | Binding per-**request** `ALLOW`/`DENY`/`HOLD`/`ESCALATE` (`packages/capabilities/model-selection/src/ugence_model_selection/authority.py:1-35`); mandatory cost eligibility (`.../gate.py:165-173`) over `cost_cap_usd` (`.../model.py:29`), provider allowlist (`:25`), residency (`:27`), latency (`:28`); eligibility precedes ranking, non-compensatory (`authority.py:24-27`); a governed `fallback_model_ids` set under `FALLBACK_AUTHORIZED` (`authority.py:71,99,201-207`) | `[V]` It "does not invoke models, route, retry, fail over, load balance, schedule, orchestrate, authorize actions, register providers, or manage credentials" (`.../version.py:11-13`); no multi-request scope |
| **Agent Runtime — budgets** | `[V]` Implemented | Reserve-before-execute ledger over **caller-named** dimensions, `available = limit − consumed − reserved` (`packages/runtime/agent-runtime/src/ugence_agent_runtime/orchestration/budgets.py:1-23`); non-finite/negative fail closed (`:33-45`); a measured overrun raises `BudgetEstimateExceeded` rather than clamping (`:84`, `:242-248`, `:266`); `actual_known=False` marks a conservative charge (`:129-138`) | `[V]` What the limit should be; supplies no usage telemetry of its own (`:19-23`) |
| **Agent Runtime — time, retry, attempts** | `[V]` Implemented | Injected-clock elapsed time (`.../runtime/timeout.py:1-30`); `RetryPolicy.max_attempts`, attempt counting with no clock (`.../runtime/retry.py:1-22`); per-attempt telemetry over **every** actual `provider.execute`, forwarding an opaque provider usage mapping verbatim (`.../observability/attempts.py:1-32`) | `[G]` No tool-call ceiling, no tool-call meter, no candidate or repair-specific counter |
| **Context Minimization — token accounting** | `[V]` Implemented | Three separated measurements; provider usage "never overwrites the pre-call estimate, and it is NOT an invoice" (`packages/capabilities/context-minimization/src/ugence_context_minimization/token_accounting.py:1-32`, `:19-21`); `ProviderTokenUsage` (`:285-304`); `ApiCallTokenRecord` with `usage_availability` and retry lineage (`:433-466`); `LogicalRequestTokenSummary` with separated `provider_reported_total_tokens`, `derived_total_tokens`, `settlement_token_units` (`:581-617`) | `[V]` NO provider tokenizer and NO pricing authority (`:27-31`) |
| **CM × Runtime bridge** | `[V]` Implemented | Normalizes a runtime `ProviderAttempt` into a CM record through an **injected** normalizer, and settles an H22-D reservation from **measured** units only when the summary is complete, else conservatively (`packages/integration/context-minimization-token-accounting-runtime/README.md:1-30`; `.../src/ugence_cm_token_accounting_runtime/bridge.py:1-13`, `:142-164`) | One-way; neither core imports it |
| **Context Minimization proper** | `[V]` Implemented | Extractive, never generative; "creates no authority"; fails closed (`packages/capabilities/context-minimization/README.md:1-16`); structural dedup explicitly narrower than equivalence-preserving minimization (`:20-26`) | `[V]` Admission — it does not decide what was permitted to enter |
| **Policy Authority** | `[V]` Implemented | The single platform-wide issuer/signer/verifier/revoker of policy **versions** for any registered family (`packages/policy-authority/README.md:1-10`) | `[G]` No compute-policy family is registered |
| **Risk Authority / Action Clearance** | `[V]` Implemented | Scoped, time-bound, revocable runtime authority enforced at the point of action (`packages/risk_authority/README.md:1-20`); clearance "may never create authority, broaden authorization, replace ActionGate, dispatch execution" (`packages/capabilities/action-clearance/README.md:1-12`) | Anything about compute magnitude |
| **Runtime / Execution Assurance** | `[V]` Implemented (reference-grade) | "RA-7 observes and assesses. RA-6 owns authority consequences" (`RA7_RUNTIME_ASSURANCE_AS_BUILT.md:1-9`); RA-8 correlates post-effect and emits a neutral reassessment signal (`RA8_EXECUTION_ASSURANCE_AS_BUILT.md:10-19`) | Authority consequences of its own |
| **Agentic Proposer** | `[V]` Implemented | Structure, identity, validation and replay of proposals; C7 (`.../src/ugence_agentic_proposer/contracts.py:456-462`) and C9 (`:495-515`) active | `[V]` No compute, cost, budget, tier or cache concept anywhere in its `src/` |
| **Invocation compute envelope** | `[G]` **Does not exist** | — | The root gap. Every ruling below is downstream of it |
| **Agent Constitution** | `[G]` **Does not exist** | — | `ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:103-107`; `S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2612-2614` |
| **Pricing authority; cache/result reuse; tool-call meter** | `[G]` **None exists** | — | Bound `RCG-D9` and `RCG-D10` |

### 2.2 — Structural constraints the rulings inherit

- `[V]` **No numeric field is possible in the Agentic Proposer contract family.** The
  canonicalization substrate raises `BareNumberError` on bare `float`
  (`packages/jcs/src/ugence_jcs/canon.py:86-90`) and bare `int` (`:91-93`), and
  `UnsupportedTypeError` on any unsupported type including `Decimal` (`:113-114`); C3
  bars every numeric type from every contract and container at any depth, a magnitude
  being carried as a typed decimal **string** whose encoding is ratified at that time
  (`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:435-443`).
- `[V]` **Identity binds referenced identifiers, not referenced contents**
  (`S1_...:2533-2534`), and replay "establishes correspondence to the *referenced
  artifact*; it does not make the advisory digest bind the observation *content*"
  (`:2566-2568`).
- `[V]` **Replay reaches only inputs at the replay boundary.** A criterion needing "a
  scoring service, a per-tenant policy table, a model call, wall-clock time, or any datum
  not carried by `AdvisoryCandidateSet` … is therefore excluded" (`S1_...:3172-3178`).
- `[V]` **Caller-supplied fields are not authoritative.** Of `CandidateAdvisory`'s
  fields only `is_eligible` is package-computed today; every other field "enters through
  caller-supplied builder parameters, so ranking on any of them would let the caller
  steer selection", and timestamps, identifiers, dispositions, review actions and
  reference/assumption/uncertainty counts "**must not** be repurposed as merit proxies"
  (`S1_...:3151-3159`). `[I]` The extension from *merit* to *cost, difficulty and
  escalation* is inference on identical provenance grounds, and `RCG-D2`/principle 7
  ratify it as an RCG constraint rather than as a restatement of S1.
- `[V]` **Authority does not transfer between responsibilities.** The
  `DomainEvaluationProvider` "is authoritative **only** for the domain-evaluation
  responsibility OD-7 ratifies; it does **not** acquire business-preference authority"
  (`S1_...:3168-3170`).
- `[V]` **A terminal `ESCALATE` has no in-contract destination.** Under R-1a a
  no-selection run carries `requested_review_destination_role_ref = None`
  (`contracts.py:602-618`); `CognitiveRoleContract.escalation_role_ref` exists
  (`contracts.py:294`) but `[G]` no ratified rule connects it to a terminal `ESCALATE`
  (`S1_...:3413-3422`) — the reasoning by which OD-9 chose `ABSTAIN`.
- `[V]` **Provider usage is opaque at the runtime boundary by design.** The runtime
  "NEVER interprets provider-specific token fields"; normalizing "is the job of an
  integration adapter, not the runtime" (`attempts.py:9-16`).
- `[V]` **Governance rejections produce no attempt.** A governance `HOLD`/`BLOCK`/
  `ESCALATE`, a clearance/integrity rejection or a provider-not-found "never reaches an
  attempt" (`attempts.py:18-21`), so avoided calls are observable only as an absence.

---

## 3. Ratified decisions RCG-D1 – RCG-D10

`[R]` The following are owner rulings. They are recorded here and nowhere else; the
roadmap's register (§15 of that document) points at this ADR and retains no independent
authority. **These are not `OD-n` numbers**: `[V]` the `OD-n` sequence is the Agentic
Proposer readiness ADR's own record (`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:577`)
and is not extended by this ADR.

### RCG-D1 — Minimal cross-cutting capability

`[R]` Reasoning Compute Governance will be a **distinct, minimal control-plane
capability**. It owns the invocation compute-envelope concept and its policy
integration.

`[R]` It does **not** own or duplicate: runtime execution; budget accounting; model
eligibility; provider routing; token normalization; context minimization; usage
metering; proposal generation; or risk or execution authorization.

`[I]` Consequence: the capability's implementable surface is one object and one policy
integration. Anything larger duplicates a shipped component listed in §2.1.

### RCG-D2 — Layered compute authority

`[R]` **Policy Authority issues and versions the organizational compute-policy family.**

`[R]` The future RCG control-plane capability is the **designated authority that
deterministically derives an invocation-specific compute envelope** within that signed
policy. It may **narrow** organizational limits and may **never expand** them.

`[R]` A model, agent, proposer or caller **may request** additional compute and **may
never authorize** it.

`[R]` **Decision Authority does not issue compute envelopes.** Risk Authority and
ActionGate continue to govern consequential action, not reasoning expenditure.

`[G]` No compute-policy family is registered with Policy Authority, and no component
derives an envelope. Both remain future, separately authorized work.

### RCG-D3 — Existing enforcement components are reused

`[R]` **Agent Runtime enforces countable and temporal dimensions** using its existing
budget, retry and timeout mechanisms.

`[R]` **Model Authority continues to decide per-request model eligibility**, including
provider, capability, residency and cost constraints.

`[R]` **Every initial model request or escalation request must be evaluated by Model
Authority** against the applicable RCG envelope and routing-policy profile. Agent
Runtime may execute only the resulting authorized model or fallback set; **it does not
independently decide that escalation is warranted.**

`[R]` RCG creates **no** additional budget ledger, router, meter or runtime enforcement
engine.

`[R]` Future tool-call and repair limits should be implemented as **governed dimensions
using existing runtime enforcement patterns**, subject to separately reviewed design.

`[I]` This ruling is consistent with, and does not amend, Model Authority's disclaimer
of routing and failover (`version.py:11-13`): Model Authority decides *which model or
fallback set is authorized*; something else executes the call. Nothing here assigns
execution to Model Authority.

### RCG-D4 — Layered, minimum-wins budgets

`[R]` The intended hierarchy is: (1) organizational or role ceiling; (2) mandate
ceiling; (3) invocation envelope; (4) optional stage allocation.

`[R]` All applicable ceilings compose under a **strict, non-compensatory minimum-wins**
rule. A narrower authority may reduce a ceiling and may **never widen** a broader one.

`[R]` The **invocation envelope is the first layer intended for eventual
implementation.**

`[R]` An optional layer that has **not been instantiated contributes no additional
restriction.** A **required invocation envelope that is absent, invalid, expired or
unverifiable fails closed** and does not authorize probabilistic computation.

`[R]` No concrete limit, unit or default is ratified.

`[I]` Minimum-wins matches the platform's existing non-compensatory pattern, in which a
lower-cost candidate "can never override a mandatory policy failure"
(`authority.py:24-27`).

### RCG-D5 — Versioned routing-policy profiles

`[R]` Model-capability governance will use **versioned, organization-controlled
routing-policy profiles issued under Policy Authority.**

`[R]` A profile may eventually express provider-neutral capability requirements,
permitted fallback or escalation classes, and other governed routing constraints.

`[R]` Provider and commercial model identifiers **may be recorded as operational
evidence** but **must not become normative contract vocabulary.**

`[R]` No profile shape, capability class, tier count, provider, commercial model or
price is ratified.

`[I]` `Request.features_required` and the governed `fallback_model_ids` set
(`authority.py:99,201-207`) are the existing shapes a future profile would express
against; this ruling neither changes nor commits to them.

### RCG-D6 — Split representation

`[R]` For **identity-bearing authorization references**, use an **opaque,
policy-resolved token** rather than embedding numeric magnitudes.

`[R]` For a **separate non-identity execution or usage record**, prospective ordered
magnitudes use an explicitly **canonical decimal-string representation with an explicit
unit.**

`[R]` Any conversion between the runtime's numeric representation and a canonical string
must be **explicit, deterministic, lossless within the ratified domain, and
independently tested.**

`[R]` Bare integers, floating-point values and `Decimal` objects **must not** be
casually introduced into the existing Agentic Proposer canonical contract substrate.

`[R]` No field, unit, encoding grammar, range or default is ratified.

`[V]` The conversion obligation is not decorative: the runtime ledger validates and
stores finite non-negative `float` (`budgets.py:33-45`) while the canonical substrate
rejects every bare numeric (`canon.py:86-93`, `:113-114`). Any future value spanning both
crosses a real representation boundary.

### RCG-D7 — Separate authorization and usage records

`[R]` Compute authorization and compute consumption remain **outside the Agentic
Proposer identity projection.**

`[R]` A future compute-authorization record and a separate usage or execution record may
be **linked to the relevant proposal or process by identifiers.**

`[R]` **No compute magnitude or authorization token enters `P_unsigned`** under this
ruling.

`[R]` **Digest inclusion must never be described as proving provenance or proper
authority.** Authority requires an independently verifiable issuance path.

`[R]` The **proposal identity, compute-authorization identity, routing-policy identity,
provider/model identity and usage attestation remain distinct.**

`[V]` Recording such facts on `ProposerProcessRecord` alone is likewise not adopted: OD-7
part 5 rejected that placement because the record sits outside `P_unsigned`
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:635`). This ruling adds nothing to either
artifact.

### RCG-D8 — Fail-closed abstention on exhaustion

`[R]` When an authorized probabilistic-compute envelope is exhausted, **no additional
probabilistic model or governed tool computation may begin.**

`[R]` The **default terminal behavior is `ABSTAIN`.**

`[R]` Deterministic processing may complete **only** when it consumes no additional
governed probabilistic resources and does not manufacture a partial advisory that the
applicable contract does not permit.

`[R]` **Budget exhaustion is never automatically `NEED_EVIDENCE`.** It must not be
reported as missing evidence unless evidence is independently missing.

`[R]` This ruling **does not authorize automatic compute escalation.** A future
additional-authority request requires a separate ratified protocol with a **bounded
attempt count and an authoritative destination.**

`[V]` A terminal `ESCALATE` remains unavailable for the reason OD-9 recorded: no ratified
rule connects any outcome to an effective referral destination (`S1_...:3413-3422`,
`contracts.py:602-618`). `[V]` Exhaustion handling also inherits the ledger's existing
fail-closed treatment of a measured overrun, which raises rather than clamps
(`budgets.py:242-248`).

### RCG-D9 — No cache or result reuse in the ratified scope

`[R]` RCG initially authorizes **no cache or result-reuse mechanism.**

`[R]` Deterministic-equality reuse may be reconsidered **only after** operational
measurement establishes that reuse is valuable **and after** authority, tenant
isolation, canonical identity, freshness, invalidation and revocation rules are
separately ratified.

`[R]` **Caller-declared or model-declared semantic equivalence is not authoritative.**

`[R]` No cache key, TTL, freshness period, identity placement or equivalence rule is
ratified.

`[G]` No cache, cache key, TTL or invalidation mechanism exists anywhere in the
repository; a repository-wide search for result-reuse, cache-key and response-cache
capabilities returns none. `[I]` The dominant hazard is authority drift — a result reused
under a mandate since revoked — which is live rather than theoretical because revocation
is a first-class Risk Authority concept (`packages/risk_authority/README.md:1-20`).

### RCG-D10 — Reuse the existing measurement chain

`[R]` The existing chain remains authoritative for its existing responsibilities: Agent
Runtime **observes attempts**; the Context Minimization–Runtime bridge **normalizes
provider usage**; Context Minimization **records separated usage measures**; the
audit/evidence boundary will eventually **preserve the authorized-versus-consumed
comparison.**

`[R]` RCG adds **no competing usage ledger.**

`[R]` **Provider-reported, derived, settled, consumed, requested, authorized and billed
compute remain separately named quantities. None may silently substitute for another.**

`[R]` **Tool-call counting belongs at Agent Runtime's observable execution boundary.**
Its normalized usage evidence and the authorized-versus-consumed comparison belong in
the **audit/evidence path.** The precise record shape remains unratified.

`[R]` **No pricing authority or billed-compute representation is ratified.**

`[G]` Tool-call counting does not exist; no pricing authority exists; no reconciliation
of provider-reported counts exists; and no component compares authorized against
consumed compute, there being no authorized term to compare.

---

## 4. Standing principles

`[R]` Ratified alongside the ten decisions and binding on any future RCG work.

1. Cost optimization never overrides evidence, policy, risk, identity or execution
   authorization.
2. A model, agent or caller may **request** compute but may not **authorize** it.
3. RCG governs observable invocation processes; it does not make private model reasoning
   deterministic.
4. RCG does not inspect, preserve, replay or prove private chain-of-thought.
5. Vendor and commercial model names are not normative contract values.
6. Authorized, requested, consumed, provider-reported, settled and billed compute remain
   distinct.
7. Caller-supplied confidence, difficulty, uncertainty, priority or desire for more
   computation is not authoritative merely because it is structured or digest-bound.
8. A capability's authority for one responsibility does not transfer automatically to
   another.
9. RCG does not authorize consequential action and does not replace Policy Authority,
   Model Authority, Risk Authority, ActionGate, Agent Runtime, Runtime Assurance,
   Context Minimization or Agentic Proposer.
10. The RCG shadow-measurement pilot remains **unimplemented and unauthorized**.

---

## 5. Non-claims

Reasoning Compute Governance:

- does **not** make model reasoning deterministic;
- does **not** inspect, reconstruct or prove private chain-of-thought — `[V]`
  `ProviderTokenUsage.reasoning_tokens` (`token_accounting.py:299`) is a
  provider-reported **count**, never reasoning content, and must never be described
  otherwise;
- does **not** guarantee that the best candidate was generated, and `[V]` a tighter
  budget makes the disclosed membership ceiling more consequential, not less;
- does **not** prove that omitted evidence or omitted candidates never existed
  (`S1_...:2530-2534`, `:2563-2568`);
- does **not** make caller-supplied data authoritative;
- does **not** permit cost optimization to bypass governance;
- does **not** authorize consequential execution;
- does **not** replace Risk Authority, ActionGate, Policy Authority, an Agent
  Constitution, Context Minimization, Model Authority, Agent Runtime or Runtime
  Assurance, and would depend on them;
- is **not** part of the Agentic Proposer public API — `[V]` no symbol, field or module
  in `packages/capabilities/agentic-proposer/src/` relates to compute, cost, budget,
  capability tier or caching, and the authorized public surface is pinned by
  `packages/capabilities/agentic-proposer/public_api.json`;
- has **no** ratified field, contract shape, vocabulary, budget value, model tier, cache
  rule or record shape. `RCG-D1` – `RCG-D10` rule on **boundary and authority only.**

---

## 6. Residual gaps

`[G]` Recorded so that no reader mistakes a ruling for a capability.

| Gap | Consequence |
| --- | --- |
| No component issues an invocation-level compute envelope | The root gap; `RCG-D2` names the future authority, and nothing implements it |
| The Agent Constitution does not exist | `RCG-D4`'s role-ceiling layer has no carrier until Policy Authority registers the family |
| No compute-policy family is registered with Policy Authority | `RCG-D2` and `RCG-D5` are unimplementable until it is |
| No pricing authority; no billed-compute representation | Currency-denominated ceilings are unbuildable (`token_accounting.py:27-31`) |
| No tool-call counting and no tool-call ceiling | `RCG-D3` and `RCG-D10` assign the responsibility; nothing implements it |
| No candidate-count or repair-specific ceiling | `RCG-D3` defers both to separately reviewed design |
| No cache, cache key, TTL or invalidation anywhere | `RCG-D9` authorizes none |
| No equivalence authority beyond a caller-supplied oracle | Semantic-equivalence reuse remains excluded |
| No provider reconciliation of reported counts | `RCG-D10` keeps the quantities separate; reconciliation is future work |
| No baseline measurement for any cost hypothesis | No saving is claimed or measured by this ADR |
| No escalation destination authority | `RCG-D8` excludes a terminal `ESCALATE` today |
| No representation for *requested* compute | `RCG-D2`'s request/authorize separation has no carrier yet |
| No provider data-retention expression | Region and residency gate *where*, not *how long* |

---

## 7. What this ADR changed

Documentation only. It adds this file and a status/link update to the RCG roadmap, plus
one pointer line in the Agentic Proposer readiness ADR's existing related-roadmap
section so that its "one recorded home" statement does not become stale.

It adds no field, contract, vocabulary, default, package, test, gate or runtime
behaviour; it changes no `public_api.json`, VERSION, package metadata, CI workflow or
platform-freeze artifact; C7 and C9 are unmodified; and OD-7, OD-8, OD-9 and OD-10 are
neither implemented nor reopened.

**No RCG implementation is authorized. The shadow-measurement pilot is not
authorized.** Any implementation requires its own separately reviewed and separately
ratified milestone.
