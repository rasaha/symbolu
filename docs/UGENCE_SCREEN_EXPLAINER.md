# Ugence screens — an explainer, one entry per screen

**Status:** reference, 2026-09-07, after the owner's ruling that AP-3 controls
(`ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §18) and the Bring Your Workflow ruling (§22). Every entry is taken from the screen's
own source: its stated purpose, its stated disclaimer, the operations it calls, and the
ruling that shaped it. Nothing here describes a screen as doing more than its code does.

Four front ends, thirty-three screens. Each entry answers the same five questions:
**what it shows**, **who answers it**, **what the operator can do**, **what it never
does**, and **the ruling that shaped it**.

## The one thing to know first

None of these is an administration screen. Ruling MA-1 refused a per-module admin
screen; ruling AP-1 to AP-5 admitted an authority plane instead, and at this step that
plane reads and does not write. Across all four front ends there are exactly two
kinds of screen: **reads** (display what a package, service or deployment returned)
and **typed intakes** (record what a person asserted, conferring nothing). The acts
that would change what an agent may do (issue, activate, revoke, grant, authorize,
clear, execute) are performed on no screen anywhere, by ruling SD-2. The worker
implements loading and revoking a role grant behind its identity gate, but under AP-3,
which the owner confirmed as controlling (§18), neither is served until the identity
adapter is validated end to end against a real enterprise issuer; the in-process issuer
evidence is implementation and conformance evidence only.

## Module coverage

| Module | Where it reaches a screen |
|---|---|
| Context Minimization, Truth Assurance, ActionGate, Autonomous Control Plane | Console: probes on Modules, stages of the Governed Loop, entries in Audit |
| Agent Runtime | Studio: Simulate (the in-studio path over fixtures), and the worker's shadow run started from Simulate and watched from Review |
| Agent Workforce Composer's adapter over an operator's own document | Studio: Bring Your Workflow (validate, adapt, compare; ephemeral) |
| Model Selection, Hybrid LLM, LLM Steering, Autonomous Runtime | No screen. By ruling MS-1 their registry rows do not reach the studio either |
| The authority directory and approval workflow (not among the nine modules) | Authority Plane: all four screens; Studio: Review Queue and Run Detail |

---

## A · Governance Studio, Eligibility Explorer (13 screens, contract v1)

Every screen here reads the frozen `governance_studio.api.v1` contract, twenty
approved operations over the Agent Workforce Composer, against pinned synthetic
scenarios. Nothing on these screens is editable except the What-If controls, which
act on a temporary copy. The shared banner on every page says it: eligibility is not
selection, assignment, authorization or execution.

### 1 · Scenario catalog (`/scenarios`)
- **Shows:** the pinned synthetic scenarios, each with its title and maturity.
- **Answered by:** `list_scenarios`.
- **Operator can:** open a scenario.
- **Never:** creates, edits or imports a scenario.
- **Ruling:** P3B/P3C screen audit; the frozen v1 contract.

### 2 · Scenario overview (`/scenarios/:id`)
- **Shows:** metadata, versions, verification, digests, maturity and presentation counts.
- **Answered by:** `get_scenario`, `get_scenario_workflow`, `get_scenario_registry`, `get_scenario_eligibility`, `get_version`.
- **Operator can:** read, and navigate to the other screens.
- **Never:** shows a ranking or team-selection metric.
- **Ruling:** screen audit §12.

### 3 · Workflow (`/workflow`)
- **Shows:** the compiled workflow as a graph and an accessible list, synchronised with a node details panel; complete node and edge accounting; every disposition as the API returned it.
- **Answered by:** `get_scenario_workflow`.
- **Operator can:** select nodes, zoom, fit.
- **Never:** edits the workflow or computes a disposition in the browser.
- **Ruling:** screen audit §13 to §15.

### 4 · Role (`/roles/:roleId`)
- **Shows:** one role's requirements, each field badged with its source: compiler, enterprise policy or composer.
- **Answered by:** `get_scenario_workflow`.
- **Operator can:** read.
- **Never:** infers a field.
- **Ruling:** screen audit §16.

### 5 · Agent registry (`/registry`)
- **Shows:** the pinned synthetic agent registry; evidence grouped as DECLARED, MEASURED or OBSERVED, always labelled synthetic; expired evidence stays visible and flagged.
- **Answered by:** `get_scenario_registry`.
- **Operator can:** read.
- **Never:** hides expired evidence or registers an agent.
- **Ruling:** screen audit §17.

### 6 · Eligibility matrix (`/eligibility`)
- **Shows:** agents by rows, API-provided condition names by columns, every state from the API; an explanation drawer per cell.
- **Answered by:** `get_scenario_eligibility`, `explain_eligibility`.
- **Operator can:** filter, reset filters, open an explanation.
- **Never:** shows a score, rank, recommendation or preference.
- **Ruling:** screen audit §18 to §20; the primary P3C screen.

### 7 · Ranking (`/ranking`)
- **Shows:** the canonical API rank order, score decomposition and tie-break as the API gave them.
- **Answered by:** `get_scenario_ranking`, `explain_ranking`.
- **Operator can:** switch to canonical order.
- **Never:** computes a score in the browser.
- **Ruling:** P3D §12 to §13.

### 8 · Composition (`/composition`)
- **Shows:** plan state, assignments, team-level facts, the non-greedy explanation, distinct selection states, and an honest NO_FEASIBLE_TEAM view.
- **Answered by:** `get_scenario_plan`, `explain_plan`.
- **Operator can:** read.
- **Never:** reruns the composition search.
- **Ruling:** P3D §14 to §17.

### 9 · Permission proposals (`/permissions`)
- **Shows:** composition-time permission proposals, categorised, with feasibility.
- **Answered by:** `get_scenario_plan`.
- **Operator can:** read.
- **Never:** describes a proposal as granted, provisioned, active or authorized. A grant is an authority act, and no screen performs one (SD-2).
- **Ruling:** P3D §18 to §19.

### 10 · Fallbacks (`/fallbacks`)
- **Shows:** every role's fallback coverage or gap; the summary counts API-returned states only.
- **Answered by:** `get_scenario_plan`.
- **Operator can:** read.
- **Never:** selects a fallback.
- **Ruling:** P3D §20 to §21.

### 11 · Replay (`/replay`)
- **Shows:** deterministic reconstruction of the plan and whether it matched; a mismatch is a prominent integrity state; a deterministic export.
- **Answered by:** `replay_plan`, `export_scenario`.
- **Operator can:** run the replay, export the scenario.
- **Never:** reruns agent execution or suppresses a mismatch.
- **Ruling:** P3D §22 and §26.

### 12 · Plan comparison (`/compare`)
- **Shows:** the API's diff of two deterministically produced plans from the same scenario.
- **Answered by:** `compare_plans`.
- **Operator can:** choose the two plans.
- **Never:** diffs in the browser.
- **Ruling:** P3D §23.

### 13 · Controlled what-if (`/what-if`)
- **Shows:** the modified plan and diff the API returned for one bounded perturbation.
- **Answered by:** `scenario_what_if`.
- **Operator can:** pick one of nine allowlisted operations with constrained controls and apply it.
- **Never:** mutates the frozen scenario; the API evaluates a temporary copy. No arbitrary JSON, policy, URL or code input.
- **Ruling:** P3D §24 to §25, C2.

---

## B · Governance Studio, Governed Agent Studio (12 screens, contract v2)

Every screen here reads the additive `governance_studio.api.v2` contract, twenty-six
operations, amended seven times by sha256-chained record. The studio backend reaches
each governance package only through the eleven-entry SD-1 allowlist. The banner on
every page says no screen here issues, activates, revokes, grants, authorizes, clears
or executes, and a test enforces it on every operation id, path and summary.

### 14 · Registration (`/studio/registration`)
- **Shows:** the systems registered in this deployment's one tenant, as of an instant.
- **Answered by:** `v2_registry_list`, `v2_registry_register`; the `ai-system-registry` package over a sqlite file under the runtime volume.
- **Operator can:** record what an administrator asserts about one AI system: its binding, an owner reference, a classification label and a validity window.
- **Never:** admits, approves, gates, promotes, attests, edits, revokes or deletes; a changed system is a new registration that supersedes the old. Registering confers nothing.
- **Ruling:** front-door seam 5, FD-9; the amendment v2-A1.

### 15 · Data use (`/studio/data-use`)
- **Shows:** the data-use declarations of this tenant, as of an instant.
- **Answered by:** `v2_data_use_list`, `v2_data_use_declare`; the `data-use-admission` package.
- **Operator can:** record what a declarer asserts about the data one system uses: an opaque reference, its name, its purpose, for how long.
- **Never:** inspects, classifies, redacts, minimizes, admits, authorizes, verifies, scores or enforces; restricts no egress.
- **Ruling:** front-door seam 8, FD-12; v2-A4.

### 16 · Vendor dependencies (`/studio/vendor`)
- **Shows:** the vendor-dependency declarations of this tenant.
- **Answered by:** `v2_vendor_list`, `v2_vendor_declare`; the `vendor-dependency` package.
- **Operator can:** record an opaque vendor reference, a risk posture as declared, a cited policy, a window.
- **Never:** resolves, verifies, scores, grades, ranks, approves, onboards or contacts; the risk posture is recorded, never assessed.
- **Ruling:** front-door seam 9, FD-13; v2-A5.

### 17 · Constitution (`/studio/constitution`)
- **Shows:** the structural validation of an authored constitution and a dry run of every pre-signing check.
- **Answered by:** `v2_constitution_validate`, `v2_constitution_preflight`; the constitution policy and activation packages over the activation root handed at composition.
- **Operator can:** author, validate, preflight.
- **Never:** issues or activates a constitution; those entry points are permanently outside the studio's allowlist. Preflight reports a typed gap where no signing key or trust root exists.
- **Ruling:** SD-2; front-door seam 1, FD-5.

### 18 · Policy (`/studio/policy`)
- **Shows:** a policy pack on the canvas, the Workflow IR it compiles to, and the result of compiling a reviewed pack.
- **Answered by:** `v2_policy_validate`, `v2_policy_synthesize`, `v2_policy_compile`; the policy-workflow compiler.
- **Operator can:** author on the canvas, validate, preview, compile. Compile requires a human approval record the compiler validates.
- **Never:** grants a permission or executes a workflow; the compiler decides what is valid. Today the screen works on a frozen fixture pack; a typed pack intake is a candidate for a later ruling.
- **Ruling:** GAS-R3, the canvas as the ratified authoring surface.

### 19 · Authority (`/studio/authority`)
- **Shows:** which policies are issued, resolvable, revoked or superseded, and the decisions a run rested on; which registry answered, with a warning when it is in-memory.
- **Answered by:** `v2_authority_list_policies`, `v2_authority_read_policy`, `v2_authority_read_decision`; the policy-authority registry handed at composition; the decision store is absent by ruling and reports its gap.
- **Operator can:** read.
- **Never:** issues, revokes or supersedes a policy.
- **Ruling:** front-door seam 2, FD-6.

### 20 · Simulate (`/studio/simulate`)
- **Shows:** two labelled paths: a compiled workflow run in the studio against fixtures, or the governed runtime worker's own shadow run started by relay. Each labelled with its executor, hook and maturity. A permissive hook renders as a red alert saying the result is not a governance result.
- **Answered by:** `v2_simulate_run`; `v2_review_start_shadow_run` relayed to the worker; the agent runtime over the one pinned no-network provider.
- **Operator can:** run a simulation in DRY_RUN, SIMULATION or SHADOW; ask the worker to start its own shadow run.
- **Never:** reaches anything consequential. LIVE is absent, not disabled. No path is chosen for the operator.
- **Ruling:** front-door seam 3, FD-7; seam 6, FD-10.

### 21 · Publish (`/studio/publish`)
- **Shows:** what the console's shadow governed loop returned for a compiled release package.
- **Answered by:** `v2_publish_shadow`; the console over four allowlisted routes, the mode word pinned to `shadow`.
- **Operator can:** send to the shadow loop.
- **Never:** authorizes an action, clears one or runs a live loop. With no console base URL composed, the screen reports the gap.
- **Ruling:** FD-8.1, FD-8.2; CP-3.

### 22 · Observe (`/studio/observe`)
- **Shows:** two distinct sources, never merged: the worker's own audit ledger by correlation id, with the worker's chain verification; and the console's audit chain. Each labelled with record type, executor and maturity. Unreachable, empty, not-found and refused are shown differently.
- **Answered by:** `v2_observe_ledger_chain` relayed to the worker; `v2_observe_audit_ids`, `v2_observe_audit_chain` relayed to the console.
- **Operator can:** read a ledger or a chain by correlation id.
- **Never:** re-derives, re-orders or re-hashes anything; chooses no source for the operator.
- **Ruling:** front-door seam 7, FD-11.4 `TWO_LABELLED_SOURCES`.

### 23 · Review Queue (`/studio/review`)
- **Shows:** parked ESCALATE instances awaiting a human decision, as the governed review service lists them.
- **Answered by:** `v2_review_list_queue`, `v2_review_submit_decision`, relayed to the review service over seven allowlisted routes.
- **Operator can:** relay a GRANT or REJECT decision with a justification and an opaque proof header, forwarded unread.
- **Never:** holds an approver identity, computes eligibility, consumes an approval, signals or resumes anything. The approver is presented and unproven until an identity provider is validated.
- **Ruling:** HR-1 `DISPLAY_AND_TRANSMIT`; ID-1 `PASS_THROUGH_OPAQUE_TOKEN`.

### 24 · Run Detail (`/studio/review/:instanceId`)
- **Shows:** one run, its events, its approval, and the HE-1 linkage as the review service exposes them.
- **Answered by:** `v2_review_read_run`, `v2_review_read_run_events`, `v2_review_read_approval`.
- **Operator can:** read.
- **Never:** resumes, releases, continues or signals; fingerprints and valid-until values are history, never a live permission.
- **Ruling:** GAS-7 HR-D; HE-5.

### 25 · Status (`/studio/status`)
- **Shows:** what the deployment attested about itself before its port bound: the six front-door seam states, the integrity checks, the pinned identities, under a ceiling stating that a configured seam is not a reachable engine.
- **Answered by:** `v2_observe_deployment`; the integrity gate's report, handed to the studio once at composition.
- **Operator can:** read.
- **Never:** probes anything, changes anything, or lists a module registry.
- **Ruling:** MA-2 as amended by MS-1 to MS-5; v2-A7.

---

## C · Console (3 tabs, the packaged console API)

The console app is a separate deployable. It calls exactly four of the five routes the
packaged `ugence-console-api` serves; the six routes ruling CP-3 withheld are not
called, and the two it used to call show a typed gap. Every answer carries the
service's audit ceiling: one process's view, lost on restart.

### 26 · Governed Loop
- **Shows:** the shadow governed loop's stage trail for one scenario: gateway, verify, authorize, clear, record, with each module's decision and the final shadow disposition.
- **Answered by:** `POST /v1/governed-loop/scenario/{scenario_id}`.
- **Operator can:** type a scenario id and run the loop in shadow. The catalogue is a typed gap; an unknown id is the service's own 404.
- **Never:** executes anything; the loop evaluates and records, and the mode is shadow.
- **Ruling:** CP-3; MA-4 `RETIRE_THE_TWO_CALLS`.

### 27 · Modules
- **Shows:** the service's availability probes for the four engines it can reach, under the keys it returns, and its declared audit ceiling. The nine-module registry is a typed gap.
- **Answered by:** `GET /health`.
- **Operator can:** read.
- **Never:** lists module descriptions, maturity or wiring; those live behind a withheld route.
- **Ruling:** CP-3, CP-4; MA-4.

### 28 · Audit
- **Shows:** a decision chain reconstructed by correlation id: what was asserted, whether it was supported, who authorized, whether it was safe.
- **Answered by:** `GET /v1/audit`, `GET /v1/audit/{correlation_id}`.
- **Operator can:** pick or type a correlation id.
- **Never:** re-derives a chain; the console's in-memory store is the record.
- **Ruling:** CP-4 `DECLARE_THE_CEILING`.

---

## D · Authority Plane (4 screens, the governed runtime worker's reads)

The administrators' surface, its own deployable (AP-2). At this step it reads and does
not write. Every answer is shown under an identity banner repeating the worker's own
words: the read was not authenticated; the decision proof the deployment can give;
the adapter's issuer validation, still in-process only; and that a grant is what an
administrator loaded. The worker implements loading and revoking a role grant behind
its identity gate (AW-2 to AW-5) but serves neither until the adapter is validated
against a real enterprise issuer (AP-3 controlling, §18); this app has no write
control and its client cannot name a write.

### 29 · Grants
- **Shows:** the role grants one principal holds in the worker's tenant, active at the worker's clock.
- **Answered by:** `GET /authority/grants?principal_id=`; the sqlite authority directory the worker composed.
- **Operator can:** type a principal id and read; follow a grant to its events.
- **Never:** loads or revokes a grant. Those writes are implemented on the worker and not served before enterprise issuer validation (AP-3).
- **Ruling:** AP-5 `READS_FIRST`.

### 30 · Holders
- **Shows:** every principal of the tenant holding one role in one scope, committees included.
- **Answered by:** `GET /authority/holders?role=&scope=`.
- **Operator can:** type a role and scope and read.
- **Never:** changes a holder.
- **Ruling:** AP-5.

### 31 · Committee
- **Shows:** one committee's counted members against its quorum, at this instant; a lapsed or revoked member is not counted.
- **Answered by:** `GET /authority/committees/{committee_id}?role=&scope=`.
- **Operator can:** read; a missing committee is a typed not-found.
- **Never:** adds a member or changes a quorum.
- **Ruling:** AP-5; directory ruling D-4.

### 32 · Grant events
- **Shows:** a grant's append-only history: loaded, and possibly revoked, with the actor recorded. A grant of another tenant reads as unknown.
- **Answered by:** `GET /authority/grants/{grant_id}/events`.
- **Operator can:** read.
- **Never:** edits a grant in place; the directory records loading and revocation only.
- **Ruling:** AP-5; AP-3 for the writes it does not have.

---

## E · Governance Studio, Bring Your Workflow (1 screen, contract v1)

The one screen on which a document the operator supplies enters the studio. Owner
ruling BW-1 to BW-5 (§22) admitted it as a read-only Workflow IR inspector and
superseded, for this surface only, the earlier "no arbitrary JSON / fixture-upload
input" sentences. The frozen v1 OpenAPI document did not change: three operations it
already carried moved from the front end's forbidden list to its approved list.

### 33 · Bring Your Workflow (`/bring-your-workflow`)
- **Shows:** what a pasted or locally chosen Ugence Workflow IR JSON document declares (version, size, nodes, edges, node kinds, dispositions, human review and authority requirements, tool and capability refs, policy pack, fingerprint, canonical digest); then, on request, the server's validation, adaptation (adapter mode, node dispositions, role requirements, fingerprints, diagnostics) and comparison of a v1 and a v2 adaptation. The disclaimer, verbatim: "Accepts Ugence Workflow IR JSON. It does not execute, publish or persist the submitted workflow."
- **Answered by:** `validate_workflow`, `adapt_workflow`, `compare_adaptations`; nothing else. The guided example is the procurement compiled workflow the catalog serves, bundled with the screen.
- **Operator can:** paste JSON or choose a local `.json` file (read in the browser); load the guided example; validate; adapt; compare against the same workflow in the other contract version; download the report and the adapted envelope to their device.
- **Never:** executes, simulates, publishes or persists the document; fetches a URL; reads an archive; accepts code, YAML, a framework-native object or a credential-shaped value; adds to or changes the scenario catalog; converts from LangGraph, CrewAI, AutoGen, n8n or BPMN (a later, separately scoped phase). Both the browser gate and the server refuse a document over 1 MiB, deeper than 32 levels, or with more than 200 nodes or 400 edges; the server's refusal is the typed 422 `workflow_too_complex`.
- **Ruling:** BW-1 `READ_ONLY_WORKFLOW_IR_INSPECTOR`, BW-2 `PASTE_OR_LOCAL_FILE_BODY_ONLY` with the owner's figures, BW-3 `VALIDATE_ADAPT_COMPARE_ONLY`, BW-4 `EPHEMERAL_NO_SERVER_STORAGE`, BW-5 `REFERENCE_GRADE` (§22).

---

## What is not a screen, and why

- **Granting, revoking:** implemented on the worker behind its identity gate (AW-2 to AW-5) and not served until the identity adapter is validated end to end against a real enterprise issuer (AP-3 controlling, §18). The screens built for them under AW-1 were withdrawn with that ruling's reversal.
- **Issuing, activating:** the authority plane's other two writes, on stores the worker does not compose (AW-2), behind AP-3.
- **Authorizing, clearing, executing:** runtime authority, with ActionGate, the Autonomous Control Plane and the runtime. Refused on every front end by SD-2 and AP-4.
- **Module composition:** providers, hooks and seam files are environment variables read before the port binds. Shown read-only on Status; set nowhere in a browser.
- **The console's module registry:** behind a withheld route; struck from the studio by MS-1.
- **Risk Authority:** its own package records and one administrative emergency stop, with no web surface; the studio is forbidden to import it.
- **A general agent uploader or framework converter:** refused by BW-1. Bring Your Workflow accepts Ugence Workflow IR only. Conversion is an offline command-line tool with no screen (`packages/tooling/workflow-converters`, ruling CV-1 to CV-5, §23): the n8n and BPMN 2.0 converters emit a DRAFT policy pack, a conversion report and a preview Workflow IR labelled `PREVIEW_UNAPPROVED` that this screen can inspect; LangGraph, CrewAI and AutoGen stay deferred until a declarative export exists.
