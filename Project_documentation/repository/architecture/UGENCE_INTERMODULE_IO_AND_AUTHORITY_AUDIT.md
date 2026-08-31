# Ugence Inter-Module I/O, Authority & Composition Audit

> **Terminology update — Ugence Decision Governance (2026-08-01).** Canonical vocabulary per
> [`Project_documentation/repository/docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](../docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md).
> **Ugence Decision Governance** is the umbrella; the "Decision Governance" authority discussed
> below is the **Decision Authority** capability (`decision_governance` package, name unchanged).
> **Model Selection** is a distinct capability (tenth), not a Hybrid LLM submodule. The optional
> orchestrator composes workflows but **acquires no authority** from the capabilities it invokes —
> authority stays federated by function. Documentation-only; nothing is renamed here.

**Continues:** `UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md` (branch `claude/ugence-modularity-audit-uujl0h`,
reference commit `e7cb8d35f5d667174d4278c36229d34354869cc9`).

**Central question:** Does each module receive an independent input and produce an
*independently usable* output, or must its output pass through another Ugence module
(ActionGate, Decision Governance, ACP, or a central authority) before it becomes
operationally meaningful?

**Method:** read-only inspection of the actual request/result types, authority semantics,
composition code, and dependency graph. Evidence is cited `file:line`. Interoperability is
**not** inferred from similar field names — only from real type flow. No production code
modified.

**Headline:** The implementation supports a **federated module architecture with
workflow-specific authority chains and an *optional* orchestrator.** Authority is already
distributed and one-directional in code (`platform/PLATFORM_FREEZE_V1.json` F5/F6/F7/F16/F17;
`cer_v0_3/control_plane.py:10-11`). **ActionGate is *not* — and must not become — a universal
central decision engine**; it owns exactly one authority (exact-action authorization) and is
semantically blind to assertions, decisions, model routing, and context. Most modules produce
**evidence or advisory findings** whose correct destination is *the specific authority
responsible for the next governed decision*, not one universal engine.

---

## 1. Executive summary

- **Two authorities exist and are correctly separated in code:** **Decision Governance** owns
  the *binding business decision record* (`decisions/decision.py:25-42`, AI structurally barred);
  **ActionGate** owns *exact-action authorization* and, in its real engine, enforcement
  (`platform` F5; `cyber_security/action_gateway` token mint). **ACP** owns *commit-time
  operational clearance* but ships **advisory/shadow** ("It never authorizes… ACP decides
  *whether now*", `operational_safety.py:8-9`; `cer_v0_3/control_plane.py:10-11`).
- **Everything else is a transformer / evidence-producer / advisory analyzer:** TAP (assertion
  coverage evidence), StoryGraph (`AUTHORITY="ADVISORY"`, effect ceiling OBSERVE/ESCALATE —
  `evidence.py:22-28`), Context Minimization (context transform + withholding evidence),
  Hybrid LLM (model routing), LLM Steering (frame selection + answer audit). None authorizes.
- **Inputs are broadly independent; the shared gap is context, not coupling.** Every module
  accepts a caller-suppliable request/event; upstream Ugence modules are replaceable by
  customer systems. The real deficiency is that **`tenant_id`/`environment_id`/policy-version
  are absent from the neutral contracts and console** and live *only* on the kernel records
  (`cer.py:66`, `decision.py:30`). That is a *shared-contract* gap, not an authority cycle.
- **Outputs split cleanly:** binding (DG, ActionGate) → independently usable; advisory (TAP,
  StoryGraph, ACP-as-shipped, Steering, Hybrid, Context-Min) → usable *as evidence* but only
  *operationally decisive* when routed to the one authority that owns the next decision.
- **No dependency cycles.** Code imports are strictly one-way (`decision_governance` is a
  sink; providers → framework → kernel; no provider imports another). ActionGate↔ACP is a
  legitimate **two-phase** protocol (authorize → clear), not a cycle
  (`cer_v0_3/control_plane.py`; `agent_runtime_migration/control_plane/client.py:70-75`).
- **Recommended target: `FEDERATED MODULE ARCHITECTURE — OPTIONAL ORCHESTRATOR`** (a blend of
  distributed domain authority + workflow-specific chains). A central policy adjudicator is
  *not* required; the existing `cer_v0_3.run_control_plane` (ActionGate+ACP composer) and the
  console governed-loop are *optional* orchestrators customers must be free to bypass.

---

## 2. Module roles (from implementation)

| Module | Primary role(s) — evidence | Secondary |
|---|---|---|
| **TAP** | `VALIDATOR` + `EVIDENCE_PRODUCER` — returns `AssertionCoverage` finding, "no authorize/dispatch/execute surface" | `ADVISORY_ANALYZER` |
| **Decision Governance** | `DECISION_GOVERNANCE` + `RECORDING_AND_RECONSTRUCTION` — immutable `DecisionRecord`, append-only audit ports | `RECOMMENDATION_ENGINE` (CaseRecommendationService) |
| **ActionGate** | `AUTHORIZATION_AUTHORITY` — `ActionGovernanceOutcome`; engine B mints single-use execution token | `EXECUTION_COORDINATOR` (engine B broker) |
| **ACP** | `OPERATIONAL_CLEARANCE` — CLEAR/HOLD vs live signals; "never authorizes" | `ADVISORY_ANALYZER` (shadow as shipped) |
| **StoryGraph** | `ADVISORY_ANALYZER` + `EVIDENCE_PRODUCER` — `AUTHORITY="ADVISORY"`, never ALLOW/DENY | — |
| **Agent Runtime** | `EXECUTION_COORDINATOR` — proposes CER, consumes separated decision; "NEVER makes its own authoritative allow/deny" | (framework variant wrongly embeds `AUTHORIZATION_AUTHORITY` — see §6 conflict) |
| **Hybrid LLM** | `TRANSFORMER` + `RECOMMENDATION_ENGINE` (model routing) | `RESEARCH_CAPABILITY` (scaffold/mock) |
| **Context Minimization** | `TRANSFORMER` (+ `EVIDENCE_PRODUCER` for withheld set) | `RESEARCH_CAPABILITY` (token core) |
| **LLM Steering** | `TRANSFORMER` (frame selection) + `ADVISORY_ANALYZER` (answer audit) | `RESEARCH_CAPABILITY` |

---

## 3. Inspected request & result types (with citations)

| Module | Input type (`file:line`) | Output type (`file:line`) | Tenant? | Authority-context? | Correlation? | Evidence-refs? | Expiry/stale? | Unavailable semantics |
|---|---|---|---|---|---|---|---|---|
| **TAP** | `AssertionGovernanceRequest` `assertion,assertion_type,evidence_refs,source_identity,policy_refs,context,correlation_id` (`contracts/assertion.py:27-36`) | `AssertionGovernanceResult{coverage,evidence_coverage,covered/unsupported,constraints,obligations,explanation_refs,fingerprint}` (`:40-52`) | ❌ | via `source_identity` (weak) | ✅ | ✅ (opaque refs) | ❌ | infra fail → `INDETERMINATE`, never SUPPORTED (F12; `provider.py` fail_safe) |
| **Decision Governance** | domain objects: `DecisionCase`, `ContextEnvelopeRecord` `cer_id,tenant_id,decision_case_id,decision_id,authority_context,policy_context,required_controls,...` (`actions/cer.py:62-85`) | `DecisionRecord{decision_id,tenant_id,authority_type,decided_by,recommendation_refs,assessment_refs,reason_codes,...}` (`decisions/decision.py:25-42`); `ActionAuthorizationResponse` (`actions/authorization.py:23-38`) | ✅ | ✅ `AuthoritySummary` (`cer.py:37-45`) | ✅ | ✅ (refs) | ✅ `expires_at` | typed `GovernanceError`; INDETERMINATE ≠ authorized |
| **ActionGate** | `ActionGovernanceRequest{action_type,requested_parameters,actor,authority_context,target_resource,policy_refs,risk_context,evidence_refs,decision_refs,idempotency_key,correlation_id,authorization_expired}` (`contracts/action.py:27-41`) | `ActionGovernanceResult{outcome,constraints,obligations,expiry,authority_basis,reason_codes,fingerprint}` (`:45-55`) | ❌ (`tenant=""`) | ✅ (opaque string) | ✅ | ✅ | ✅ `expiry` | `INDETERMINATE`/`EXPIRED` never dispatch (F9/F10) |
| **ACP** | `OperationalSignals{error_budget_remaining,cluster_health,change_freeze_active}` (`models.py:78-85`) | `ClearanceVerdict{disposition(CLEAR/HOLD),reason_codes,evaluated}` (`:87-90`) | ❌ | ❌ (content-identity only) | via loop | ❌ | ❌ | missing signal → fail-closed **HOLD** (`operational_safety.py:38-61`) |
| **StoryGraph** | `ObservedEvent` set / JSONL stream (`storygraph.py`) | advisory evidence `{authority:"ADVISORY",effect:OBSERVE/ESCALATE,recommended_consequence,evidence_hash,bound_to}` (`evidence.py:22-50`); `StoryMatch`/`RiskVector` | ❌ (opaque strings) | ❌ | via `bound_to` action_hash | ✅ (`evidence_hash`) | freeze-based | matcher-limit → `unavailable=True` → ESCALATE (fail-loud) |
| **Agent Runtime** | `Goal`/registered `ToolSpec` (`contracts/`); emits CER via `cer_builder` | `GovernanceDecision{actiongate_authorization,acp_operational_safety,composed_eligibility,eligible,execution_reference,required_next_step,trace_ref}` (read-only) (`control_plane/client.py:25-36`); `ExecutionResult` | via CER | via CER | via trace_ref | via CER | via authorization expiry | `build_live_model_from_env()`→None → `BLOCKED_NO_REAL_MODEL` (never fabricates) |
| **Hybrid LLM** | `Corpus`+query (`schema.py`) | `HandoverResult{final_answer,audit,packet}`, decision ∈ `SERVE_IN_HOUSE/ESCALATE/REFUSE` (`pipeline.py:51-61`, `schema.py:143-146`) | ❌ | ❌ | ❌ | span provenance | ❌ | gate fail → `HandoverRefused` (refuse, not authorize) |
| **Context Minimization** | `list[ContextUnit{id,text,redundancy_set,protected}]` (`models.py:30-38`) | `MinimizeResult{kept_ids,removed_ids,total_units,removed_units,protected_ids,lossless}` (`:46-53`) | ❌ | ❌ | dropped on std endpoint | withheld set | ❌ | fail-closed restore / full fallback |
| **LLM Steering** | query + answer text | `CSRMatchDecision(PRIMARY/SECONDARY/WEAK/REJECT_*)` (`match.py:30-39`); `AnswerAuditResult{passed,needs_rewrite,status,findings}` (`answer_audit.py:62-69`) | ❌ | ❌ | ❌ | trace | ❌ | detector-only; recommends rewrite, never rewrites |

**Shared enums / cross-module types actually imported:** providers import only the neutral
`governance_providers.contracts` enums (`ActionGovernanceOutcome`, `AssertionCoverage`) +
`decision_governance.api.*` (down-only). **No provider imports another provider's types**
(F16/F17; verified by grep — §7). StoryGraph, Context-Min, Hybrid, Steering import **no** Ugence
types at all.

---

## 4. Per-module I/O independence matrix

| Module | Input class | Output class | Overall |
|---|---|---|---|
| **TAP** | `INPUT_INDEPENDENT_WITH_SHARED_CONTRACTS` (self-suppliable request; needs framework contract; no tenant) | `OUTPUT_ADVISORY_BUT_USABLE` (coverage finding; to *gate release* needs a policy decision) | Independent input, advisory output |
| **Decision Governance** | `INPUT_INDEPENDENT_WITH_SHARED_CONTRACTS` (constructs domain objects; identity/audit via ports; tenant explicit) | `OUTPUT_INDEPENDENT` (binding `DecisionRecord`; *actions arising* from it need ActionGate) | Independent |
| **ActionGate** | `INPUT_INDEPENDENT_WITH_SHARED_CONTRACTS` (caller supplies actor/authority/resource; engine B rich identity) | `OUTPUT_INDEPENDENT` (binding authorization; ACP *recommended* at commit) | Independent |
| **ACP** | `INPUT_INDEPENDENT` (pure customer telemetry) | `OUTPUT_REQUIRES_AUTHORIZATION` (clearance is meaningful only for an already-authorized action) | Independent input, dependent meaning |
| **StoryGraph** | `INPUT_INDEPENDENT` (customer event stream) | `OUTPUT_ADVISORY_BUT_USABLE` (evidence directly usable by SIEM/case system/gate) | Independent input, advisory output |
| **Agent Runtime** | `INPUT_INDEPENDENT` (goal + registered tools) | `OUTPUT_REQUIRES_AUTHORIZATION` for consequential actions; read-only outputs independent | Independent input, downstream-authority for consequential |
| **Hybrid LLM** | `INPUT_INDEPENDENT` (corpus+query) | `OUTPUT_ADVISORY_BUT_USABLE` (routing/answer; egress selection should be policy-approved) | Research; advisory |
| **Context Minimization** | `INPUT_INDEPENDENT` (context units) | `OUTPUT_INDEPENDENT` (minimized context is a finished artifact; optional validator check) | Independent |
| **LLM Steering** | `INPUT_INDEPENDENT` (query+answer) | `OUTPUT_ADVISORY_BUT_USABLE` (steering/audit; generated result may need TAP before release) | Research; advisory |

No module is `UPSTREAM_MODULE_REQUIRED` on **input**. The dependencies are all **downstream and
semantic** (an advisory output needs an authority to become a decision) — never an input
prerequisite that forces installing another Ugence module.

---

## 5. Module I/O contract table

| Module | Primary input | Required upstream data | Primary output | Output authority | Direct customer use | Required downstream module |
|---|---|---|---|---|---|---|
| **TAP** | assertion + evidence refs | None (refs are customer-owned) | assertion coverage finding + obligations | Advisory / Evidentiary | ✅ (as evidence) | **Customer release policy** *or* Decision Governance |
| **Decision Governance** | decision case + context envelope | None (assessments optional) | binding decision record + authorization response | **Binding decision** | ✅ | **ActionGate** *only to execute actions arising from the decision* |
| **ActionGate** | exact proposed action + authority context | None (decision_refs optional) | exact-action authorization (+ token, engine B) | **Binding authorization / enforcement** | ✅ | **ACP** *conditionally* (live-state-dependent actions) |
| **ACP** | live operational signals | An **authorization** to be *meaningful* | operational clearance CLEAR/HOLD | Operational clearance (advisory as shipped) | ⚠️ (only with an authorization) | **None** (feeds executor/customer) |
| **StoryGraph** | linked event stream | None | advisory sequence-risk evidence | Advisory / Evidentiary | ✅ | **ActionGate / Decision Governance / fraud-case system / customer policy** (consumer's choice) |
| **Agent Runtime** | goal + tool registry | None for read-only; **control plane** for consequential | CER proposal + execution result | Coordinator (not authority) | ✅ (read-only) | **ActionGate (+ACP)** for consequential actions |
| **Hybrid LLM** | corpus + query | None | model-routing decision + answer | Advisory | ✅ | **Customer policy engine** (egress/provider approval) |
| **Context Minimization** | context units | None | minimized context + withheld evidence | Advisory / Evidentiary | ✅ | **Optional validator** (TAP/customer) to confirm essentials kept |
| **LLM Steering** | query + candidate answer | None | frame decision + answer-audit result | Advisory | ✅ | **TAP / customer release policy** (validate generated result) |

---

## 6. Authority-ownership matrix

Applying the principle: **a module may produce strong evidence without owning the authority to
permit, deny, decide, or execute.**

| Authority | Owner (code evidence) | Notes / blur flags |
|---|---|---|
| **Truth / assertion admissibility** | **TAP** (advisory) — but as shipped over a *mock*; the release *decision* is the customer's/DG's | ⚠️ VC docs call TAP a "delivery authority"; code = advisory only |
| **Recommendation generation** | **Decision Governance** (`CaseRecommendationService`); TAP/StoryGraph feed it | — |
| **Binding business decision** | **Decision Governance** (`DecisionRecord`, `AuthorityType` has no AI member) | Clean; F1/F2/F3 |
| **Exact-action authorization** | **ActionGate** (`ActionGovernanceOutcome`; engine B token) | Clean; F5. Do **not** widen to other decisions |
| **Live operational clearance** | **ACP** (CLEAR/HOLD; "never authorizes") | Ships advisory/shadow; F: `compose(ALLOW,HOLD)=HELD_BY_ACP` |
| **Execution** | **External executor / Agent Runtime (coordinator)** — separated from authorization (F8) | ✅ separation enforced |
| **Sequence-risk evidence** | **StoryGraph** (advisory, never ALLOW/DENY) | Clean |
| **Model selection** | **Hybrid LLM / Model-Selection** (advisory routing) | Research; egress needs policy |
| **Context disclosure** | **Context Minimization** (filters; advisory) | No per-actor need-to-know yet |
| **Model steering** | **LLM Steering** (advisory frame/audit) | Research; unwired |
| **Final customer-facing output release** | **UNOWNED in code** — the console loop computes `would_execute` but **executes nothing in any mode**; release is the customer's | ⚠️ gap: no module owns "release," by design left to customer policy |
| **Audit & reconstruction** | **Decision Governance** (`AuditRepository`, `list_by_correlation`); each module keeps its own in-proc log | ⚠️ fragmented (three audit shapes; no shared durable ledger) |

**Authority-blur flags:**
1. **Agentic Framework (mature Agent Runtime)** silently embeds allow/deny + a `POST /authorize`
   service + an internal class named `ActionGate` — it *becomes* a policy authority. The
   boundary-clean `agent_runtime_migration` fixes this (`ensure_not_self_authorized`,
   `client.py:70-75`). **Sell only the migration runtime as governance-neutral.**
2. **Console CER short-circuit:** `ugence_console_api` computes an *ad-hoc* CER and bypasses the
   kernel authorization service — the console is not an authority, but it re-implements CER
   identity locally, blurring where "authorization of record" lives.
3. **TAP "delivery authority" doc-vs-code:** docs imply binding; code is advisory.

---

## 7. Is ActionGate a universal central decision point?

| Architecture | Fit vs implementation | Verdict |
|---|---|---|
| **A — ActionGate as universal central engine** (all outputs flow to ActionGate first) | **Semantic misfit.** ActionGate's contract is *exact-action* authorization (`action_type,requested_parameters,target_resource` — `contracts/action.py:27-41`). It has **no representation of an assertion, a business decision, a model-routing choice, or a context payload**. Forcing TAP/DG/Hybrid/Context outputs through it would require inventing an "action" for each — an unbounded policy monolith. It would also create a single point of failure the modules don't otherwise have (each is independently callable), raise latency, and destroy standalone products (StoryGraph, TAP would need ActionGate to be "meaningful"). Providers deliberately **never invoke one another** (F17). | **REJECT** |
| **B — distributed domain authority** (each module owns its native authority) | **Matches the code.** F5/F6/F7 already encode: assertion-governance ≠ authorize execution; action-governance ≠ determine truth; execution separate from authorization. `cer_v0_3.run_control_plane` composes ActionGate+ACP as *separated* verdicts, not a merged engine. Shared audit works via `correlation_id` + evidence refs, not a central adjudicator. | **ADOPT (core)** |
| **C — central policy adjudicator** (modules emit normalized findings; one adjudicator combines) | **Partly exists, as optional.** `cer_v0_3.run_control_plane` (ActionGate+ACP → composed eligibility) and the console governed-loop are *narrow* adjudicators, both shadow/advisory. A *general* adjudicator over all findings is **not present and not required** — it would recreate the Architecture-A monolith risk. Justified only as an **optional** per-deployment orchestrator. | **OPTIONAL only** |
| **D — workflow-specific composition** (each workflow declares the modules/authorities it needs) | **Matches how customers will actually buy.** A K8s action-control workflow needs Agent Runtime→ActionGate→ACP; a claims-decision workflow needs TAP→Decision Governance; a fraud workflow needs StoryGraph→case system. No universal authority. | **ADOPT (composition model)** |

**Recommendation: B + D — distributed domain authority, composed per workflow, with C available
as an *optional* orchestrator.** ActionGate stays a *bounded* authority for exact-action
authorization; it is never the funnel for assertions, decisions, routing, or context.

---

## 8. When should an output flow to another module?

- **TAP →** It should **not** unilaterally release/reject; it produces an *evidentiary coverage
  finding* (`AssertionCoverage`) that a **customer release policy or Decision Governance** turns
  into a release/hold. (F6: assertion governance does not authorize execution.)
- **Decision Governance →** Produces a **binding decision record** by an accountable authority
  (`DecisionRecord`). *Actions arising from* that decision must still pass **ActionGate** for
  exact-action authorization (decision ≠ authorization of a specific executable action; F8
  separates them). A decision with no executable action needs no ActionGate.
- **StoryGraph →** Remains **advisory evidence** (`AUTHORITY="ADVISORY"`). Correct consumers:
  **ActionGate** (as an escalation input), **Decision Governance** (as assessment), a **fraud/
  case system**, or **customer policy** — the producer must not pick a binding effect.
- **ActionGate →** Requires **ACP** *only when* the authorized action's safety depends on live
  operational state (infra/robotics writes with blast radius). A state-independent action is
  fully served by the authorization alone. So: **conditional**, not mandatory.
- **ACP →** Cannot independently *stop* in a vacuum: a CLEAR/HOLD is meaningful **only relative
  to an existing authorization** (`operational_safety.py:8-9`; `compose(ALLOW,HOLD)=HELD_BY_ACP`).
  It can *withhold* an authorized action; it can never *permit* one. So ACP is a **second-phase
  gate after authorization**, not a standalone stopper.
- **Agent Runtime →** For **consequential** actions it must route the CER through the control
  plane (ActionGate+ACP) and consume the **separated** decision read-only; it may **not** treat
  anything but a control-plane eligibility as permission (`client.py:70-75`). Read-only tools run
  ungoverned by design. It does **not** consume DG binding decisions directly — it consumes the
  composed authorization/clearance.
- **Context Minimization →** Output is usable minimized context, but because minimization can
  drop essential evidence, a **validator (TAP or a customer check)** *should optionally* confirm
  essentials were kept before the reduced context feeds a high-stakes decision. Optional, not
  mandatory.
- **Hybrid LLM →** Routing can be acted on directly for **model choice**, but **provider/data-
  egress** selection should be **policy-approved** (a customer policy engine), since egress is a
  governance-relevant disclosure.
- **LLM Steering →** Steering instructions apply directly to generation; the **generated result**
  should be validated by **TAP or a customer release policy** before external release. Steering
  itself authorizes nothing.

---

## 9. Complementary product pairs

| Pair | One contributes | Other contributes | Integration | Clearer buyer outcome? | Both still independently purchasable? |
|---|---|---|---|---|---|
| **TAP + LLM Steering** | validates the generated answer | shapes generation + self-audit | **Optional** | Yes — "governed generation" | Yes |
| **TAP + Context Minimization** | validates coverage on reduced context | reduces exposure/cost | **Optional** | Moderate | Yes |
| **TAP + Hybrid LLM** | validates the routed answer | routes cheap vs frontier | **Optional** | Moderate | Yes |
| **Decision Governance + TAP** | records accountable decision | supplies assertion evidence for it | **Optional (recommended)** | Yes — "evidenced decision" | Yes |
| **Decision Governance + ActionGate** | binding decision | authorizes the exact action | **Conditional (when decision → action)** | Yes — decision-to-execution accountability | Yes |
| **StoryGraph + ActionGate** | advisory sequence-risk escalation | authorizes/denies the action | **Optional enrichment** | Yes — "sequence-aware action control" | Yes |
| **ActionGate + ACP** | authorization ("may it?") | live clearance ("safe now?") | **Conditional (live-state actions)** | **Strong** — agent action governance | Yes |
| **Agent Runtime + ActionGate** | proposes governed actions | authorizes each exact action | **Mandatory for consequential** | **Strong** — governed runtime | Runtime yes; ActionGate yes |
| **Agent Runtime + ACP** | proposes/executes | commit-time clearance | **Conditional** (needs authorization first) | Yes (with ActionGate) | Yes |
| **Hybrid LLM + Context Minimization** | routes internal/frontier | minimizes egressed context | **Optional** | Yes — private-model efficiency | Yes (both research today) |
| **Full pipeline (all applicable)** | end-to-end governed loop | — | **Optional orchestrator** | Yes — Full AI Control Plane | Yes — each remains sellable |

**Fully standalone (business result complete alone):** StoryGraph, ActionGate (engine B),
Decision Governance, Context Minimization. **Standalone but stronger paired:** TAP (+DG),
ACP (+ActionGate), Agent Runtime (+ActionGate/ACP). **Internal/near-internal:** Agentic
Framework (bundle). **Research pairs, not yet sellable:** Hybrid+Context-Min, Steering+TAP.

---

## 10. Central result envelope

**Recommendation: adopt a *small common envelope* + module-specific extensions. Do not force
one oversized universal schema.**

| Field | Verdict | Rationale |
|---|---|---|
| `correlation_id` | **COMMON (required)** | already the only cross-layer primitive; present on all requests |
| `module_id`, `module_version` | **COMMON (required)** | absent from results today (`ProviderDescriptor` has it, results don't) — needed to interpret any output |
| `authority_type` | **COMMON (required)** | the single most important missing field — makes advisory-vs-binding explicit |
| `advisory_or_binding` | **COMMON (required)** | prevents authority confusion (the Agentic-Framework failure mode) |
| `result_category` | **COMMON (required)** | already exists per family (`outcome`/`coverage`/`disposition`) — normalize the *slot* |
| `result_digest` | **COMMON (required)** | already universal as `fingerprint` |
| `unavailable_controls` / `unknown_controls` | **COMMON (required)** | today only `INDETERMINATE`/`unavailable=True` flags; needed for fail-safe composition |
| `required_next_step` | **COMMON (recommended)** | already computed by the runtime control plane (`required_next_step`) |
| `evidence_refs` | **COMMON (recommended)** | present on TAP/action; generalize |
| `expires_at` / staleness | **COMMON-WHEN-APPLICABLE** | meaningful for authorization/clearance (has it), not for a stateless transform |
| `policy_version` | **COMMON-WHEN-APPLICABLE** | only modules that evaluate policy |
| `tenant_id`, `environment_id` | **COMMON-WHEN-APPLICABLE (must be addable)** | today only on kernel records; must be threadable through the envelope |
| `workflow_id`, `case_id`, `proposal_id`, `cer_id`, `evaluation_id`, `state_snapshot_ref` | **CONTEXTUAL (workflow-scoped)** | present only where the workflow has them; **not** universal — forcing them onto StoryGraph/Context-Min is noise |
| `requirements_satisfied` / `requirements_failed` | **MODULE-SPECIFIC** | map to `constraints`/`obligations` (action) or `covered`/`unsupported` (assertion) — keep as typed extensions |

**Truly common core (belongs on every result):** `correlation_id, module_id, module_version,
authority_type, advisory_or_binding, result_category, result_digest, unavailable_controls,
required_next_step`. **Everything else is contextual or a module-specific extension.**

---

## 11. Sequencing requirements

| Edge | Class | Why |
|---|---|---|
| `Context Minimization → TAP` | **OPTIONAL_ENRICHMENT** | TAP validates with or without prior minimization; minimization only reduces cost/exposure |
| `TAP → Decision Governance` | **CONDITIONAL_SEQUENCE** | required only when a decision *relies on* asserted claims; DG can decide on non-assertion inputs |
| `Decision Governance → ActionGate` | **CONDITIONAL_SEQUENCE** | required only when the decision yields an *exact executable action*; F8 keeps them distinct |
| `StoryGraph → ActionGate` | **OPTIONAL_ENRICHMENT** | advisory escalation input; the gate decides without it; may instead go to DG/case system |
| `ActionGate → ACP` | **CONDITIONAL_SEQUENCE** | required only for actions whose safety depends on live state; state-independent actions skip it |
| `ACP → Agent Runtime execution` | **CONDITIONAL_SEQUENCE** | execution proceeds only if cleared *and* authorized; ACP alone cannot permit |
| `LLM Steering → TAP` | **OPTIONAL_ENRICHMENT / ALTERNATIVE_PATH** | steering shapes generation; TAP validates the result; either can run alone |
| `Hybrid LLM → TAP` | **OPTIONAL_ENRICHMENT** | routing precedes generation; TAP validates output afterward |
| `Agent Runtime → ActionGate` | **MANDATORY_SEQUENCE** (consequential) / OPTIONAL (read-only) | by design no ungoverned consequential path (`ensure_not_self_authorized`) |
| `ActionGate → TAP` (as a truth gate) | **INVALID_COMPOSITION** | violates F7 (action governance must not determine assertion truth) |
| `ACP authorizes without ActionGate` | **INVALID_COMPOSITION** | ACP never mints authorization (`compose` invariants) |

**Only one edge is truly mandatory** — Agent Runtime → ActionGate for consequential actions —
and even that is scoped to *consequential* work. Everything else is conditional or optional.

---

## 12. Integration mechanism per valid edge

| Edge | Recommended mechanism |
|---|---|
| Context Min → TAP | **Shared SDK contract** (in-proc/sync); customer orchestration |
| TAP → Decision Governance | **Evidence reference** (assessment_refs) — DG pulls the finding by ref |
| Decision Governance → ActionGate | **Evidence/decision reference** (`decision_refs` on the action request) + direct sync API |
| StoryGraph → ActionGate / DG / case system | **Event publication / evidence reference** (advisory record consumed asynchronously) |
| ActionGate → ACP | **Direct synchronous API** (two-phase authorize→clear), composed by `cer_v0_3.run_control_plane` |
| ACP → executor | **Direct synchronous API** (gate result) |
| LLM Steering / Hybrid → TAP | **Customer-owned orchestration** (generation pipeline) |
| Agent Runtime → ActionGate(+ACP) | **Policy callback via injected port** (`ControlPlaneClient` — dependency injection, not import) |
| Any → audit | **Durable, shared audit reference** (correlation_id + evidence refs) |

**No central router is recommended merely to share metadata** — correlation IDs and evidence
refs travel *in the contracts*, not through a hub.

---

## 13. Failure & unavailable behavior

Guiding rule (both directions): **absence of a *required* governance control never becomes
permission; absence of an *optional* module never blocks an otherwise-valid standalone
deployment.**

| Module | Not installed / unavailable | Slow | Ambiguous | Stale | Hard failure | Advisory escalation | Disagreement |
|---|---|---|---|---|---|---|---|
| **TAP** (when release-gating) | **Return unavailable → Hold** (INDETERMINATE, never SUPPORTED — F12) | timeout → INDETERMINATE | INDETERMINATE → Require review | expiry → re-evaluate | fail-safe INDETERMINATE | Hold/review | evidence yields to authority |
| **TAP** (optional enrichment) | **Continue with reduced assurance** | continue | note | note | continue | log | — |
| **Decision Governance** | consequential decisions **Hold**; advisory flows continue | Hold | Require review | re-decide | Hold | review | owns the decision |
| **ActionGate** | **Deny/Hold** (no auth → no execution — F9/F10) | Hold | INDETERMINATE → Hold | EXPIRED → Deny | fail-closed | n/a | **authoritative** for its domain |
| **ACP** (live-state action) | **Hold** (fail-closed on missing signal) | Hold | Hold | Hold | Hold | HOLD | can hold, never permit |
| **ACP** (state-independent action) | **Continue** (clearance not required) | continue | — | — | continue | log | — |
| **StoryGraph** (advisory) | **Continue with reduced assurance** (UNAVAILABLE → escalate, fail-loud) | continue | Request evidence / review | escalate | continue | escalate | advisory, never blocks alone |
| **Agent Runtime** | consequential **Blocked** (`BLOCKED_NO_REAL_MODEL`/no eligibility); read-only continues | wait/retry | Request evidence | replan | Hold | escalate | consumes, never overrides |
| **Context Minimization** | **Continue** (fall back to full context) unless a data-exposure policy *requires* it → **Hold** | continue | full fallback | — | full fallback | log | — |
| **Hybrid LLM** | **Continue** (default model) | continue | Refuse | — | Refuse | escalate | advisory |
| **LLM Steering** | **Continue** (no steering) | continue | recommend rewrite | — | continue | recommend review | advisory |

**Invariant preserved:** every *required* control fails **closed** (Hold/Deny/Unavailable —
never silent permit; F9–F13). Every *optional* control fails **open with reduced assurance**, so
a single-module deployment is never held hostage by an uninstalled sibling.

---

## 14. Circular-dependency findings

**No cycles found.** Directed edges by dimension:

- **Code imports:** `decision_governance` (leaf/sink) ← `governance_providers` ← `tap_provider`,
  `actiongate_provider`; `agent_runtime_migration → cer_v0_3 → {action_gate_ref, acp_db}`.
  **No provider imports another provider** (verified: grep of each package shows only
  down-imports; F17). `symbolu`/`agentic`/`control_plane` are **not** imported by the kernel.
- **Runtime calls / evidence / audit flow:** Context-Min → TAP → (DG recommendation) → ActionGate
  → ACP → execution → audit. All forward edges; evidence flows producer→consumer only.
- **Policy authority:** each domain owns its own; no module re-decides another's (F16).

**The two hypothesized cycles do not exist:**
- `TAP → Decision Governance → ActionGate → TAP`: **broken** — ActionGate and TAP are mutually
  unaware (F17); ActionGate never feeds TAP (that edge is `INVALID_COMPOSITION`, F7).
- `ActionGate waits for ACP` / `ACP waits for ActionGate`: **not a cycle** — this is a
  **legitimate two-phase protocol**: ActionGate authorizes *first*, ACP clears *after*, consuming
  the authorization as an opaque token; ACP never calls back into ActionGate
  (`cer_v0_3/control_plane.py`; `composition.py` imports nothing from ActionGate).

**Recommended one-way rules:** providers → framework → kernel (never up); runtime → control-plane
port → {ActionGate, ACP} (never runtime-embedded authority); evidence producers (TAP, StoryGraph,
Context-Min) → consumers (never consumer → producer as a truth source); authorization → clearance
(never clearance → authorization).

---

## 15. Product independence vs governance consistency

| Model | What it buys | What it risks |
|---|---|---|
| **Maximum independence** (per-module API/policy/storage/audit) | fastest standalone sales, no central SPOF | duplicate identity integration, conflicting policies, inconsistent authority semantics, **fragmented audit** (already true — 3 audit shapes), high customer integration burden |
| **Maximum centralization** (all I/O through one engine) | one integration, uniform policy | monolith, single point of failure, **loss of standalone products**, unbounded central policy model, slower module innovation, high deployment friction — and **semantic misfit** (ActionGate can't represent assertions/decisions/routing) |
| **Federated governance** (independent modules sharing *contracts, identity, policy refs, evidence refs, audit correlation*; authority distributed) | standalone sales **and** cross-module consistency; no SPOF; authority stays bounded | requires the shared-contract SDK to actually carry tenant/authority/correlation (today partial) |

**Federated governance is the correct target.** It is also the smallest delta from today: the
provider framework + kernel ports are already federated; the missing pieces are a shared envelope
(tenant/authority/correlation) and a durable shared audit reference — not a new central engine.

---

## 16. Mitigation backlog

| # | Mitigation | Class |
|---|---|---|
| M1 | **Explicit `authority_type` + `advisory_or_binding` in every result** (prevents the Agentic-Framework authority-blur) | **Required for multi-module composition** |
| M2 | **Common governance-contract SDK** (small envelope §10 + registry/resolution — extend `governance_providers`) | Required for multi-module composition |
| M3 | **Module-specific public APIs** kept (do not merge into one schema) | Required for standalone sale |
| M4 | **Shared correlation + evidence references** threaded into results (echo `correlation_id`; add `evidence_refs`) | Required for multi-module composition |
| M5 | **Standard unavailable/stale semantics** (`unavailable_controls`, `expires_at`) uniformly (§13) | Required for multi-module composition |
| M6 | **Fail-safe requirement declarations** — each module declares which controls are required vs optional, so absence-of-required ≠ permission | Required for multi-module composition |
| M7 | **Module capability manifests** (already nascent in `governance_providers` descriptors + console registry) | Recommended for enterprise operations |
| M8 | **Dependency injection instead of direct imports** for cross-authority calls (as `ControlPlaneClient` already does) | Required for standalone sale |
| M9 | **Durable, shared audit references** (replace in-memory console audit with kernel `AuditRepository` + hash-chain) | Recommended for enterprise operations |
| M10 | **Customer-owned orchestration support** (documented direct APIs; orchestrator optional) | Required for standalone sale |
| M11 | **Contract tests between complementary modules** (TAP↔DG, ActionGate↔ACP, Runtime↔control-plane) | Required for multi-module composition |
| M12 | **Prevent hidden authority escalation** — CI check that no module returns a binding effect it doesn't own (extend F16/F17 tests to advisory modules) | Required for multi-module composition |
| M13 | **Prevent one module interpreting another's undocumented internals** (freeze result envelopes; providers already don't cross-import) | Required for multi-module composition |
| M14 | **Optional control plane / optional workflow orchestrator; no mandatory universal router** | Optional future platformization |
| M15 | **Policy composition rules + version compatibility matrix** (which module/policy versions interoperate) | Optional future platformization |
| M16 | **Thread `tenant_id`/`environment_id`** through the shared envelope (today kernel-only) | Required for enterprise operations |

---

## 17. Recommended target patterns

**Pattern 1 — standalone product** (StoryGraph, ActionGate, Context-Min, Decision Governance)
```
Customer system → Ugence module → independently usable result
   (mandatory: the module only)
```

**Pattern 2 — evidence-producing module** (TAP, StoryGraph, LLM Steering, Context-Min)
```
Customer workflow → advisory/evidence module → { customer policy  |  Ugence authority module }
   (mandatory: producer;  conditional: the specific authority for the next decision)
```

**Pattern 3 — complementary authority chain** (governed action)
```
Decision Governance ──(conditional: decision→action)──▶ ActionGate authorization
        │                                                      │
        │                                        (conditional: live-state action)
        ▼                                                      ▼
   binding record                                        ACP live clearance
                                                               │
                                                    (conditional: eligible)
                                                               ▼
                                                    Agent Runtime execution
```
Edges: DG→ActionGate **conditional**; ActionGate→ACP **conditional**; ACP→execution **conditional**.

**Pattern 4 — full governed pipeline**
```
Context Minimization ─(optional)─▶ Hybrid LLM / LLM Steering ─(optional)─▶ TAP
        │ optional                                                          │ conditional
        └──────────────────────────────────────────────────────────────────▼
                                                              Decision Governance
        StoryGraph ─(optional enrichment)──────────────────────────┐        │ conditional
                                                                    ▼        ▼
                                                                 ActionGate (authorize)
                                                                    │ conditional (live-state)
                                                                    ▼
                                                                 ACP (clear)
                                                                    │ conditional
                                                                    ▼
                                                            execution → reconciliation & audit
```
**Mandatory edges:** none universal (only Agent Runtime→ActionGate for *consequential* actions).
**Conditional:** TAP→DG, DG→ActionGate, ActionGate→ACP, ACP→execution. **Optional:** Context-Min,
Hybrid, Steering, StoryGraph enrichment.

---

## 18. Verdicts

### Per-module

| Module | Verdict |
|---|---|
| **StoryGraph** | **INDEPENDENT INPUT — ADVISORY OUTPUT** (evidence directly usable; consumer's choice of authority) |
| **Context Minimization** | **INDEPENDENT INPUT AND OUTPUT** (finished artifact; optional validator) — token core `RESEARCH CAPABILITY` |
| **Decision Governance** | **INDEPENDENT INPUT AND OUTPUT** (binding decision record; ActionGate only to *execute* arising actions) |
| **ActionGate** | **INDEPENDENT INPUT AND OUTPUT** (binding authorization; ACP conditional at commit) |
| **TAP** | **INDEPENDENT INPUT — ADVISORY OUTPUT** (release needs a policy/DG decision) — engine value `RESEARCH` (mock) |
| **ACP** | **INDEPENDENT INPUT — DOWNSTREAM AUTHORITY REQUIRED** (clearance meaningful only after authorization); live engine `RESEARCH CAPABILITY` (shadow) |
| **Agent Runtime** | **INDEPENDENT INPUT — DOWNSTREAM AUTHORITY REQUIRED** for consequential actions (migration); framework = **ORCHESTRATED PIPELINE COMPONENT** that wrongly embeds authority |
| **Hybrid LLM** | **RESEARCH CAPABILITY** (advisory routing; scaffold/mock) |
| **LLM Steering** | **RESEARCH CAPABILITY** (advisory; productizable model-agnostic core) |

### Overall: `FEDERATED MODULE ARCHITECTURE — OPTIONAL ORCHESTRATOR`

Authority is distributed and one-directional in code; composition is workflow-specific; a
central engine is neither present nor warranted. An orchestrator (`cer_v0_3.run_control_plane`,
the console loop) is a convenience for multi-module workflows and must remain **bypassable**.

### The ten required answers

1. **Should all module outputs flow through ActionGate?** **No.** Only exact-executable-action
   proposals. ActionGate cannot represent assertions, decisions, routing, or context; funneling
   them through it creates a semantic-misfit monolith.
2. **Which outputs should flow through Decision Governance?** Those that inform a **binding
   business decision by an accountable authority** — TAP assessments, StoryGraph evidence,
   recommendations (via `assessment_refs`/`recommendation_refs`).
3. **Which outputs are independently usable?** Decision Governance record, ActionGate
   authorization, StoryGraph evidence, Context-Min minimized context, TAP finding (as evidence),
   LLM-Steering audit (as evidence).
4. **Which modules produce evidence rather than decisions?** TAP, StoryGraph, Context
   Minimization, LLM Steering, Hybrid LLM, and ACP-as-shipped (advisory).
5. **Which own binding authority?** Decision Governance (binding decision), ActionGate
   (exact-action authorization/enforcement). ACP owns commit-time clearance (a withhold gate,
   advisory as shipped).
6. **When is ACP mandatory after ActionGate?** Only when the authorized action's safety depends
   on **live operational state** (infra/robotics writes with blast radius). Not for
   state-independent actions.
7. **Is a central orchestrator required?** **No** — optional, for multi-module workflows.
8. **Can customers compose modules through their own workflow engine?** **Yes** — direct
   synchronous APIs + shared contracts + evidence refs; the Ugence orchestrator is one optional
   reference implementation.
9. **Which complementary bundles should be sold?** ActionGate+ACP (agent action governance);
   Decision Governance+TAP (evidenced decisions); StoryGraph+ActionGate (sequence-aware control);
   Agent Runtime+ActionGate+ACP (governed runtime). Research pairs (Hybrid+Context-Min,
   Steering+TAP) later.
10. **How should authority conflicts be resolved?** By **domain precedence**: the authority that
    owns a decision is final *within its domain* (ActionGate DENY is final over ACP; ACP HOLD
    cannot mint authorization; no module overrides another's native authority — F16/F17). Advisory
    dissent **escalates but never overrides**. Required controls fail **closed**. Cross-domain
    conflicts resolve to **human review via Decision Governance**.

---

## 19. Unsupported claims (I/O & authority)

1. **"ActionGate is the central governance decision engine."** Code shows a *bounded* exact-action
   authority with no representation of assertions/decisions/routing/context; providers never
   invoke one another (F17).
2. **"TAP releases/rejects content."** Advisory coverage finding only (F6); over a mock engine.
3. **"ACP independently stops execution."** Meaningful only after an authorization exists; it can
   withhold, never permit; ships shadow (`compose(ALLOW,HOLD)=HELD_BY_ACP`).
4. **"Agent Runtime governs actions."** The migration runtime explicitly delegates and cannot
   self-authorize (`ensure_not_self_authorized`); only the *framework* variant embeds authority,
   and that is a flagged defect, not a product stance.
5. **"Modules share one audit/evidence trail."** Three audit shapes exist; only `correlation_id`
   is common; the console audit is in-memory and not hash-chained.
6. **"There is one canonical result/CER envelope."** Three coexisting schemes (kernel
   `ContextEnvelopeRecord`, `cer_v0_3`, console ad-hoc); no shared result envelope carries
   `authority_type`/tenant across modules today.

---

*Principle applied throughout:* **modules stay independently consumable wherever their business
result is complete; advisory/evidentiary outputs flow only to the specific authority responsible
for the next governed decision — never automatically to one universal central engine.**
