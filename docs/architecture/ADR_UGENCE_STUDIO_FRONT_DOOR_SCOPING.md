# ADR — Governed Agent Studio as the front door: scoping audit

**Status:** scoping audit, 2026-09-05. Documentation only; no code, branch or PR.
Owner decisions FD-1 to FD-5 were all ruled on 2026-09-05 (§6). **The rulings authorize
documentation only; no seam is activated by them.** Labels: `[V]` verified, `[I]` inferred,
`[R]` requires ratification, `[G]` gap.

## 1 — The question

Does the "studio as front door" outline (build a governed agent, or govern an existing
one, converging on one governance pipeline through ten screens) ask for anything the
repository does not already own? **Mostly no.** Eight of the ten screens map to
packages that exist and produce the artifact the outline names. What is missing is
composition: the deployed studio hands its context one seam, so six of the seven live
screens report typed gaps. Two screens would create no enforceable artifact today and
must not be built as screens. The import path is already ruled.

## 2 — What the studio composes today

- `build_studio_context` accepts seven seams `[V]` (`app_v2.py:58-69`): `activation_root`,
  `policy_registry`, `decision_store`, `policy_identities`, `governance_hook`,
  `provider_registry`, `console_base_url`, `review_service_base_url`. Every one is
  optional; a service handed nothing reports itself unavailable and names the gap.
- The P3E container hands it exactly one: `review_service_base_url` `[V]`
  (`deployment/governance-studio/src/governance_studio_deployment/app.py:62`, CR-2).
- Seven screens exist in the frontend `[V]` (`frontend/src/features/studio/*Screen.tsx`):
  Constitution, Policy, Authority, Simulate, Publish, Observe, Review queue and run
  detail, over 17 v2 operations `[V]` (`api/v2/*.py`). The v1 screen audit fixed the
  rule every row below applies: thin orchestration, no re-implemented governance
  logic, no route grants, authorizes or executes `[V]`
  (`GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md`).

## 3 — Screen to package map

| # | Outline screen | Artifact the outline names | Repository owner of that artifact | Studio today | Label |
|---|---|---|---|---|---|
| 1 | Use-case designer | registered use case, purpose, prohibited uses | `ai-system-registry` (`SystemRegistration`: binding, `owner_ref`, classification, validity; records what an administrator asserted) plus `data-use-admission`; ruled contracts-only in v1 (gap-sequencing D-5) | no screen | `[V]` package, `[G]` screen |
| 2 | Agent role builder | Agent Constitution and owner | `agent-constitution-policy` (family), `-activation` (preflight, issuance receipts), `-conformance`; owner is an opaque external fact (OD-C4=A) | Constitution screen; `activation_root` not handed in P3E | `[V]` |
| 3 | Workflow canvas | typed proposal and workflow contracts | `policy-workflow-compiler` (`compile_policy_pack` to Workflow IR), `agent-workforce-composer` (role adaptation, eligibility); the React Flow canvas is the ratified authoring surface (GAS-R3) | Policy screen (validate, synthesize, compile) | `[V]` |
| 4 | Model and reasoning selector | model-selection and reasoning-governance records | `model-selection` (policy-bounded selection, owns no routing), `reasoning-method-governance` and `-advisor` (research-only slice 1), `agentic-proposer-strategy-permission-*` (signable strategy permission) | no screen | `[V]` packages (research-only labels), `[G]` screen |
| 5 | Data and tool connections | data permissions, tool scopes, egress restrictions | `data-use-admission` (declared data use), `vendor-dependency`; egress: `ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md` is **discharged** — it authorized `data-use-admission`, which shipped as seam 8; what it deferred is *result* egress (DE-1), a seam no document has declared; tool scopes live in the governed-execution restrictions the hook already carries | screens shipped (seams 8, 9) | `[V]` records and screens, `[G]` result egress, undeclared |
| 6 | Policy builder | machine-enforceable policy bindings | `policy-authority` registry, `policy-workflow-compiler`, `decision-authority`; `agentic-proposer` S1 contracts (proposes, decides nothing) | Policy and Authority screens; `policy_registry`, `decision_store` not handed in P3E | `[V]` |
| 7 | Simulation laboratory | evidence, failures, readiness | `agent-runtime` over fixture providers, `agent-runtime-governance` hook; readiness: `agent-value-readiness`; `agent-assurance-evidence` records what an exercise found | Simulate screen; `governance_hook`, `provider_registry` not handed in P3E, so it BLOCKs by design | `[V]` |
| 8 | Authority designer | authority graph and approval workflow | `authority-directory` (grants, delegation, committees), `approval-workflow`, `governed-review`, `governed-review-service`, `approver-identity-jwt` | Review queue and run detail, wired end to end (steps 2 and 3) | `[V]` |
| 9 | Deployment | signed configuration, governed runtime deployment | `agent-constitution-activation` receipts; `execution-reservation` (clearance receipts); the governed runtime worker (CR-1); publish today proxies the console's shadow loop only | Publish screen; `console_base_url` not handed in P3E | `[V]` shadow, `[G]` any non-shadow deployment (roadmap §11.2 non-goals) |
| 10 | Live operations console | audit trail, assurance, incident controls | `control-plane-root` ledger, `incident-response` (records and proposes; never revokes or executes), `risk-authority-*-assurance`, `cloud-scaling-credential-broker` (Phase 5X, a handle not execution, cloud-scaling only per D-1) | Observe screen over the console; Run detail over the worker | `[V]` records, `[G]` live execution and interventions |

## 4 — Screens that must not be built as screens

- **Use-case designer with prose intake.** No package turns a plain-language goal into
  a use case; the proposer works from typed inputs `[V]`. A screen that accepts prose
  and emits a registration would be the studio authoring governance content, which the
  v1 audit forbids. A typed registration form over `ai-system-registry` is admissible.
- **Live operations with interventions.** Suspend, contain, recover as buttons would
  claim execution control that no package exercises: `incident-response` proposes,
  the credential broker issues handles, LIVE is structurally blocked (§11.2). An
  observe-only console over the audit ledger and incident records is admissible.

## 5 — Govern an existing agent, under GAS-5

GAS-5 removed the Langflow importer from the sequence and scope; entry needed a
demonstrated customer need and a new ruling `[V]` (roadmap §11.3). The owner gave
that ruling on 2026-09-05 (`ENTER_LANGFLOW_IMPORT_FIRST`); the scoping is in
`ADR_UGENCE_LANGFLOW_IMPORT_SCOPING.md`. Copilot Studio,
Vertex AI, ServiceNow, LangGraph and CrewAI appear only in positioning documents `[V]`
(`docs/COMPETITIVE_LANDSCAPE.md`, `INVESTOR_PITCH.md`); no adapter exists `[G]`. The
integration-hub amendment already defines the two shapes such an adapter must take
`[V]`: a **runtime connector** bridges a runtime to the canonical execution and
lifecycle contracts, and `agent-runtime-governance` is its governance half while the
execution half (execution-reservation ports) is unbuilt. The minimum contract for any
"govern an existing agent" path is therefore: one-way, validate never execute, compile
the accepted subset to Workflow IR through `compile_policy_pack`, refuse anything
unmapped, and record consequential transitions against execution-reservation. Nothing
here is implemented.

## 6 — Owner decisions (ruled 2026-09-05)

| # | Ruling |
|---|---|
| **FD-1** | **`ONE_SEAM_PER_STEP`.** One front-door seam is introduced and validated at a time. Each seam requires its own bounded implementation, failure tests, maturity statement and independently reviewable commit before the next seam begins. |
| **FD-2** | **`ENTER_LANGFLOW_FIRST`** (ruled earlier the same day). GAS-5 superseded by `ENTER_LANGFLOW_IMPORT_FIRST`; Langflow is the first and only import format; other platforms stay customer-gated; scoped in `ADR_UGENCE_LANGFLOW_IMPORT_SCOPING.md`, where LI-1 to LI-5 are ruled and implementation is blocked on a fixture. |
| **FD-3** | **`COMPOSITION_RECORD_IN_REGISTRY`.** The studio front-door composition is represented through an immutable, versioned registry record using existing registry ownership (`ai-system-registry`). No new package is created merely to hold composition metadata. |
| **FD-4** | **`TYPED_INTAKE_ONLY`.** The first front door accepts only versioned, schema-validated typed input. It performs no prose-to-contract conversion, LLM interpretation, inferred defaults or silent repair. Prose assistance remains a later, separately ruled capability. |
| **FD-5** | **`SCREEN_1_ONLY`.** Only screen 1 enters the next implementation step, as the activation root. Screens 4, 5 and 10 remain unchanged and are introduced only through later, separately validated seams. |

| **FD-6** | **Seam 2 = `POLICY_REGISTRY_AND_DECISION_STORE`** (ruled 2026-09-06). The Authority screen may receive read-only access to the policy registry and the decision store through the deployment composition root. The seam permits typed retrieval and display only: it confers no policy authorship, decision issuance, approval, mutation, credential access, provider execution or LIVE capability. The policy and decision displayed must be tenant-bound and linked through their existing canonical references (the registry's `PolicyCoordinate` and record ids, the decision's own id and audit reference); missing, malformed, cross-tenant, stale or unbound records produce a typed refusal or a typed gap, and the screen never infers, repairs or synthesizes authority. `GOVERNANCE_HOOK_AND_PROVIDER_REGISTRY` and `CONSOLE_BASE_URL` remain unruled future seams and are not implemented. FD-3, FD-4, the `REFERENCE_GRADE_SHADOW_ONLY` ceiling, the frozen v1 and v2 contracts and every credential and LIVE prohibition are preserved. |

**Shape of seam 2, and one gap `[G]`.** The Authority screen reads a `PolicyRegistry`
(`issued_records_for_identity`, `get_issued`, `revocations_for`, `supersessions_for`)
for the identities it is configured with, and a Decision Authority record store
(`get(decision_id)`) `[V]` (`services/studio_v2.py`, `AuthorityService`). The registry
half is the seam-1 store: the same `SqlitePolicyRegistry` file the activation root
opens, handed once more as `policy_registry`, plus a typed, versioned list of policy
identities to enumerate (FD-4: no discovery, no default). The decision-store half has
no durable implementation in the repository: Decision Authority ships in-memory
repositories only (`InMemoryDecisionCaseRepository` and siblings) and
`execution-reservation` is the durable backend of its execution ledger, not of
decision cases `[V]`. Seam 2 therefore hands `policy_registry` and
`policy_identities` and leaves `decision_store` absent, so the decision read keeps
its typed gap `decision_authority_store`; a durable Decision Authority record store
is a separate package decision, not part of this seam. The ruling authorizes
documentation only; the seam activates by its own implementation prompt.

**What the rulings authorize.** Documentation only. No seam is activated, no code is
changed, and the P3E container still hands the studio context the review-service URL
alone until the next implementation prompt is issued and its PR merges.

**Reading of FD-5 `[I]`.** The ruling names the activation root as the seam. The
activation root serves the studio's first screen in its own order, Constitution
(§3 row 2: `build_studio_context(activation_root=...)`, consumed by
`ConstitutionService.preflight`). The outline's screen 1, the use-case registration
form over `ai-system-registry` (§3 row 1), is not entered by this ruling; if the owner
intended it, a one-line correction re-rules FD-5. The next seam is therefore: the P3E
profile hands the studio an activation root composed from the constitution
authority's own deny-by-default signer and verifiers (no key material in the studio;
`build_activation_root` accepts none) over a durable policy registry, so preflight
reports its real result and issuance refuses.

## 7 — Next step

**Seam 1 shipped** (`governance-studio-deployment` 0.3.0): `UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH`
composes `build_activation_root` over `SqlitePolicyRegistry` under the runtime volume
with `DenyAll` verifiers and a refusing signer; preflight reports the activation
package's real result, issuance and activation refuse, no key material exists; the
composition is `composition-record.json`, an `ai-system-registry` record (FD-3).
Composing surfaced two studio-backend defects fixed alongside (a `from_dict` that did
not exist; a bare-string approval reference where an `ApprovalEvidenceRef` is
required) and made `decode_dataclass` public in policy-authority 0.3.1. The frozen v2
request still carries the approval reference as one string, read as a typed
three-part encoding; a structured field is a v2 contract amendment for a later,
separately ruled step. **Seam 2 shipped** (`governance-studio-deployment` 0.4.0): `UGENCE_STUDIO_TENANT_ID` and
`UGENCE_STUDIO_POLICY_IDENTITIES` (typed, `<policy_family>|<policy_id>|<scope>`) hand
the Authority screen `ReadOnlyTenantBoundRegistry`, a four-read view of the seam-1
registry instance bound to one tenant, plus the identities; `decision_store` stays
absent. The studio's `AuthorityService` was corrected alongside: it addressed the
registry by record id and by an untyped identity where the port takes an exact
coordinate and four keyword parts, so it now resolves a record id through the
configured identities' records, parses the typed identity, displays every record by
its canonical references without the signature bytes or the policy body, and maps a
registry refusal to a typed refusal. The composition record now supersedes the seam-1
record (`composition-record.seam-1.json`, unchanged). **Seam 3 shipped**
(`governance-studio-deployment` 0.5.0, FD-7): `UGENCE_STUDIO_SIMULATION_PROVIDER=1`
hands the Simulate screen a `ProviderRegistry` holding the one pinned in-package
provider (`fixture` 0.1.0, `DEMONSTRATION_ONLY`; records in memory, returns success,
no socket, no file); `governance_hook` stays the runtime's fail-closed default, so
every consequential task BLOCKs with `GOVERNANCE_NOT_CONFIGURED` and the trace shows
it; the root refuses any hook handed to the Simulate service before bind and the
startup integrity gate fails if the package's source could construct a permissive
one; the profile's `agent_execution` prohibition carries its FD-7.1 definition; the
composition record supersedes the seam-2 record (`composition-record.seam-2.json`,
unchanged). Matrix rows 1 to 6 of §8.2 are tests, rows 4 and 6 no longer gaps.
**Seam 4 absent by ruling** (FD-8.1; FD-8.2 shipped in the studio backend, §9.5).
**Seam 5 shipped** (`governance-studio-deployment` 0.6.0, FD-9):
`UGENCE_STUDIO_SYSTEM_REGISTRY_PATH` hands the Registration screen a tenant-bound
`SqliteSystemRegistry` (`ai-system-registry` 0.2.0, the one ruled local store) under
the runtime volume, with `registered_by` this deployment's name and version and every
owner reference recorded as `PRESENTED_UNPROVEN`; the frozen v2 contract is amended
once (v2-A1, `openapi_v2.amendments.json`) by `v2_registry_register` and
`v2_registry_list`, the generated client regenerated, the P3E freeze carrying the
new digest; `register` is the only write; the composition record supersedes the
seam-3 record (`composition-record.seam-3.json`, unchanged); §10.4's failure matrix
is tests. **Seam 6 shipped** (`governance-studio-deployment` 0.7.0, FD-10, with
`governed-review-service` 0.5.0 and `governed-runtime-worker` 0.2.0): the worker's
sixth route `POST /review/runs` (`review_start_shadow_run`) asks a `ShadowRunStarter`
the worker composes to start the worker's own `wf-shadow` under the worker's own
definition digest, minting the instance id from the caller's typed correlation id and
running the first bounded quantum so the run parks on ESCALATE in the existing queue;
the adapter's `DefinitionVersionMismatch` and `InstanceIdentityError` are the typed
`REFUSED_DEFINITION` and `REFUSED_CONFLICT`, a retried start is `REPLAYED`, any mode
word but `shadow` is `REFUSED_MODE`, and any other body key is refused with 422 so no
workflow, task, provider, mode or digest crosses (FD-10.3). The studio's review client
is six routes (four reads, two relays), `StartRunService` relays the typed request and
returns the worker's answer unchanged, the v2 contract is amended once more (v2-A2,
`v2_review_start_shadow_run`) with its generated client and the frontend manifest, the
Simulate screen shows the seam-3 in-process run and the worker relay as two labelled
paths (FD-10.5), the P3E egress record and its freeze test name six routes over the one
existing destination, CR-2 and HR-1 are amended in their ADRs, and §11.3's matrix is
tests in the worker, the studio backend and the profile. No configuration value, image
package, credential or second egress destination was added; the composition record
supersedes the seam-5 record (`composition-record.seam-5.json`, unchanged). **Seam 7
shipped** (`governance-studio-deployment` 0.8.0, FD-11, with `control-plane-root` 0.2.0,
`governed-review-service` 0.6.0 and `governed-runtime-worker` 0.3.0): the ledger's one
raw read, `read_entries`, returns a tenant's own rows for one correlation id in chain
order, refusing a blank key, an in-memory store and a foreign schema version, and its
ADR D-5 and README say a raw read is not reconstruction; the worker's seventh route
`GET /review/audit/{correlation_id}` (`review_read_audit`) returns the worker's own
tenant's rows with `chain_verified` as a typed field, a chain that does not verify is
`REFUSED_INTEGRITY` with the entries withheld, another schema version `REFUSED_SCHEMA`,
no reader `REFUSED_UNCONFIGURED`, unknown 404, malformed 422, no list-all route and no
write; the studio's review client is seven routes (five reads, two relays),
`LedgerObserveService` returns the worker's answer unchanged under a backend-stated
source label, the v2 contract is amended a third time (v2-A3, `v2_observe_ledger_chain`)
with its generated client and the frontend manifest, the Observe screen shows the
worker ledger and the console's typed gap as two labelled sources (FD-11.4) and
re-derives nothing, the P3E egress record and freeze test name seven routes over the
one destination, CR-2 is amended again in its ADR, and §12.4 is tests in
control-plane-root, the review service, the worker, the studio backend and the profile.
No configuration value, image package, credential or second egress destination was
added; the composition record supersedes the seam-6 record
(`composition-record.seam-6.json`, unchanged). **Seam 8 shipped**
(`governance-studio-deployment` 0.9.0, FD-12, with `data-use-admission` 0.2.0): the
package's one ruled durable home, `SqliteDataUseDeclarations`, is a tenant-bound,
append-only sqlite file in the seam-5 posture whose only write is `declare` — a
duplicate derived id refused, a supersession admitted only by `supersession_refusals`,
a file bound to one tenant never re-bound, the record digest re-verified on the way
out, and no clock read; the studio backend's `DeclarationService` takes typed intake
only, the tenant the store's and the id derived, and its answers state that the
declarer is presented and unproven, that a declaration confers nothing, and that no
egress restriction is expressible because no egress-authority package exists; the v2
contract is amended a fourth time (v2-A4, `v2_data_use_declare` and
`v2_data_use_list`) with its generated client and the frontend manifest; the Data use
screen carries typed fields, a single Declare control, hints saying the classification,
purpose and residency labels are interpreted nowhere, and no admit, authorize, verify,
score, enforce, revoke, edit or delete control; the P3E profile adds one configuration
value, `UGENCE_STUDIO_DATA_USE_DECLARATIONS_PATH`, requiring `UGENCE_STUDIO_TENANT_ID`,
one package in the image and one startup-integrity check; and §13.4 is tests in the
package, the studio backend, the frontend and the profile. The composition record
supersedes the seam-7 record (`composition-record.seam-7.json`, unchanged). Seam 8
closed the **last outline row** a studio-alone seam can reach, which is what FD-12.1
ruled; it did not close the row. `vendor-dependency` is the same shape again inside
row 5 and, in FD-12.1's own words, "its own later seam under FD-1" — audited as seam 9
in §14. (An earlier revision of this paragraph said the front door was at its ceiling
with no further studio-alone seam remaining. That overstated FD-12.1 and is corrected
here.) **Seam 9 shipped** (`governance-studio-deployment` 0.10.0, FD-13, with
`vendor-dependency` 0.2.0): the same durable-home posture again —
`SqliteVendorDeclarations`, tenant-bound, append-only, `declare` its only write, the
record digest re-verified on read and no clock — with the studio backend's
`VendorDeclarationService` taking typed intake only and the v2 contract amended a
fifth time (v2-A5, `v2_vendor_declare` and `v2_vendor_list`). What FD-13.4 required is
what the seam is careful about: the risk posture is recorded verbatim and matched by
exact text, ordered, compared, ranked and scored nowhere, and no vendor approval,
onboarding status, tier or certification is expressible at the seam or displayed
beside it, because no package in this repository computes one; `policy_ref` is
recorded and never resolved; `vendor_ref` is opaque and no field could carry an
address, endpoint, credential, contract term or price. The P3E profile adds one
configuration value, `UGENCE_STUDIO_VENDOR_DECLARATIONS_PATH`, requiring
`UGENCE_STUDIO_TENANT_ID`, one package in the image and one startup-integrity check;
§14.4 is tests in the package, the studio backend, the frontend and the profile; and
the composition record supersedes the seam-8 one (`composition-record.seam-8.json`,
unchanged). **With seam 9 the front door under FD-1 is at its ceiling**, as FD-13.1
ruled: no studio-alone seam remains. Row 5's third element, egress restrictions, has a
ratified ADR and no package and stays a gap; the console remains a packaging body of
work, a durable Decision Authority store a package decision, and the mirror
coordinates, Langflow fixture and enterprise issuer owner inputs.

The shape every seam follows: the CR-2 shape (one configuration value, one freeze-test amendment, its own failure tests and
maturity statement, one PR), preserving `REFERENCE_GRADE_SHADOW_ONLY`, the frozen
runtime configuration, existing v1 and v2 behaviour, and every credential and LIVE
prohibition. Issued by its own implementation prompt.

## 8 — Seam 3 audit: `GOVERNANCE_HOOK_AND_PROVIDER_REGISTRY` (2026-09-06)

**The question.** Can the P3E profile hand the Simulate screen a provider registry
and a governance hook without breaching its own `agent_execution` prohibition?
**Only by owner ruling.** The Simulate screen runs the Agent Runtime in the studio
process; over an in-image fixture provider that performs no I/O, and under the
runtime's own fail-closed default hook, nothing acts on the world, but P3E's
ratified profile lists `agent_execution` as prohibited and `LIMITATIONS.md` reads
"does not … execute agents". Whether a fixture-only run is "agent execution" is a
product-intent question, not a repository fact. Everything below is documentation;
no seam is activated.

### 8.1 What exists today `[V]`

- **The seams.** `build_studio_context(governance_hook=, provider_registry=)` reach
  `SimulateService` only (`app_v2.py:64-89`, `services/studio_v2.py:398-520`). With no
  registry the run answers the typed gap `simulation_providers`. With a registry and
  no hook the runtime's default `UnconfiguredGovernanceHook` BLOCKs every
  consequential task with `GOVERNANCE_NOT_CONFIGURED` (`governance/hooks.py:31-43`,
  engine: task FAILED, category `GOVERNANCE_BLOCK`); the response carries
  `governance_hook_configured` and `governance_hook_permissive`, and the screen
  renders a permissive hook as a red alert (screen audit rows 4 and 265). LIVE is
  refused before any runtime is built; the accepted mode is placed in every task's
  arguments and a task declaring another mode is refused (`studio_v2.py:431-447`).
  Quanta are capped at 64. The frontend submits one fixed sample workflow
  (`SimulateScreen.tsx:17-20`, `provider_id: "fixture"`); the user types nothing, so
  FD-4 is satisfied by construction for this step.
- **The registry.** `ProviderRegistry` is explicit and injected: `register` refuses a
  provider without a string `provider_id` and refuses a duplicate; a task naming an
  unregistered provider fails with `PROVIDER_NOT_FOUND` and no attempt is made
  (`providers/registry.py`, `runtime/execution.py:145-156`). A `Provider` is
  `provider_id`, `version`, `execute(ToolInvocation) -> ToolResult`.
- **The hooks.** Three implementations exist: `UnconfiguredGovernanceHook` (BLOCK,
  the default), `AllowAllGovernanceHook` (CLEARs everything; documented as unsafe and
  never a default), and `GovernedExecutionHook` (`agent-runtime-governance`), which
  composes through `RiskAuthorityCompositionEngine.compose` over a deployment-supplied
  `GovernanceInputSource` and fails closed with typed reasons: source raised →
  `GOVERNANCE_INPUT_SOURCE_UNAVAILABLE`; source returned `None` →
  `GOVERNANCE_PROPOSAL_NOT_AUTHORITY_BOUND`; malformed inputs, composition failure,
  GRANT without an envelope id, record capacity (`hook.py:44-63, 174-270`). Its
  maturity is `Core implemented`; Risk Authority `production_mode` raises
  `ProductionContainmentError`, and HOLD, DEFER, ESCALATE and MANUAL_REVIEW have no
  sink in the studio (`agent_runtime_governance.maturity()`, screen audit "Gaps").
- **The worker already composes this seam.** `governed-runtime-worker` wires
  `GovernedExecutionHook` over `ApprovalBoundInputSource` and a `ProviderRegistry`
  holding one `ShadowProvider` (`FIXTURE_ONLY`, records in memory, returns success)
  whose upstream source parks every proposal on ESCALATE (`composition.py:227-238`,
  `workload.py`). CR-1 ruled that execution lives in the worker, not P3E.
- **The image.** P3E carries `agent-runtime` (the studio backend imports it) but
  not `agent-runtime-governance`, `risk-authority-runtime`, `risk-authority`,
  `decision-authority` or `actiongate-provider` (`approved-runtime-config.json`
  `first_party_packages_in_image`; the hook's dependency chain). A governed hook in
  P3E is five Dockerfile additions; a fixture registry under the default hook is none.
- **The profile.** `prohibited` includes `agent_execution`, `external_tool_calls`,
  `external_model_calls`, `credential_provisioning`; `approved-runtime-config.json`
  lists `governance_hook` and `provider_registry` as `absent_by_ruling`. Startup
  integrity classifies any failure text containing "fixture" as
  `SYNTHETIC_DATA_BOUNDARY_FAILED` (`startup_integrity.py:205`), so a configuration
  variable or error message for this seam must not carry that word.

### 8.2 Failure matrix (what the code does today; rows marked `[G]` need a test)

| # | Case | Result |
|---|---|---|
| 1 | no registry handed | typed gap `simulation_providers`, `result: null` `[V]` |
| 2 | registry, no hook | every consequential task BLOCKs `GOVERNANCE_NOT_CONFIGURED`; trace shows the block; both flags `false` `[V]` |
| 3 | task names an unregistered provider | `PROVIDER_NOT_FOUND`, zero attempts, no provider invoked `[V]` |
| 4 | task with no `provider_id` | not exercised by any test `[G]` |
| 5 | malformed workflow (mode conflict, unknown mode, LIVE) | refused before a runtime exists `[V]` |
| 6 | permissive hook injected | run CLEARs by construction; `governance_hook_permissive: true`; red banner `[V]`; nothing refuses it in production mode `[G]` |
| 7 | governed hook, source raises / returns `None` / GRANT without envelope | BLOCK with the typed reason above `[V]` (unit level, in the governance package) |
| 8 | governed hook, ESCALATE | task WAITING, workflow PAUSED; no sink reachable from the studio `[V]`, `[G]` by design |
| 9 | cross-tenant | the hook and registry seams carry no tenant: a `TransitionProposal` has a correlation id, not a tenant; only an input source can bind one `[V]`; under the default hook nothing tenant-bound is read `[V]` |
| 10 | credential, key material, egress | none in either seam: the registry is in-process, the fixture provider opens no socket, the hook holds no key ring (the source would) `[V]` |

### 8.3 Prohibitions preserved by any admissible shape `[V]`

No credential, key material or DSN enters the studio; `external_tool_calls` and
`external_model_calls` stay prohibited, so the only admissible provider performs no I/O;
LIVE stays absent from the mode list and refused by the service; `ENFORCEMENT_ENABLED`
stays `False`; `REFERENCE_GRADE_SHADOW_ONLY` stands; the v1 and v2 contract bytes are
untouched (the response fields already exist); no FROM line or ratified digest changes;
the mirror blocker is unchanged.

### 8.4 Proposed ruling FD-7 (five decisions, recommended option first; ruled in §8.5)

| # | Decision | Options |
|---|---|---|
| **FD-7.1** | Is a fixture-only run in P3E `agent_execution`? | **`FIXTURE_RUN_ADMISSIBLE`**: a run whose every provider is an in-image, no-I/O fixture and whose modes exclude LIVE is a demonstration, not agent execution; the profile's `prohibited` entry is re-worded to "agent execution against any non-fixture provider". `FIXTURE_RUN_PROHIBITED`: seam 3 stays absent in P3E; the Simulate screen keeps its typed gap until a worker relay is separately ruled. |
| **FD-7.2** | Host | **`P3E_IN_PROCESS`** (the studio's own runtime, as the service is written). `WORKER_RELAY` (a sixth relayed route on the worker's review service; amends CR-2's five-route allowlist and the worker; not in this step). |
| **FD-7.3** | Hook for this step | **`RUNTIME_DEFAULT_BLOCK`**: only `provider_registry` is handed; `governance_hook` stays the runtime's fail-closed default and the trace shows every BLOCK honestly; no new package. `GOVERNED_HOOK_OVER_FIXTURE_SOURCE`: `GovernedExecutionHook` over a source shaped like the worker's, five packages added to the image, ESCALATE with no sink. |
| **FD-7.4** | Provider set | **`ONE_PINNED_FIXTURE_PROVIDER`**: one provider in the deployment package, id and version recorded in `approved-runtime-config.json`, records in memory and returns success, no I/O, enabled by one boolean configuration value; no provider list is read from the environment (FD-4: no discovery). `CONFIGURED_PROVIDER_IDS`: a typed list, each resolving to an in-image implementation. |
| **FD-7.5** | Permissive hook | **`PROHIBITED_IN_PROFILE`**: the P3E root never constructs `AllowAllGovernanceHook`, startup integrity fails if `governance_hook_permissive` could be true, and the composition record states it. `LABELLED_ONLY` (today's behaviour). |

Under the recommended options seam 3 is: one configuration value, one fixture provider
in `governance-studio-deployment`, `provider_registry` handed and `governance_hook`
absent by ruling, a superseding composition record, the profile's `agent_execution`
entry re-worded, and matrix rows 1 to 6 as tests. The governed hook then becomes a
later seam of its own (FD-1), entered only when a sink for ESCALATE exists in the studio
or the worker relay is ruled.

### 8.5 Ruling FD-7 (owner, 2026-09-06)

| # | Ruling |
|---|---|
| **FD-7.1** | **`FIXTURE_RUN_ADMISSIBLE`.** A run whose every provider is an in-image, no-I/O fixture and whose modes exclude LIVE is a demonstration, not agent execution. The profile's `prohibited` entry `agent_execution` is re-worded, when seam 3 ships, to "agent execution against any non-fixture provider"; `external_tool_calls` and `external_model_calls` stand unchanged. |
| **FD-7.2** | **`P3E_IN_PROCESS`.** The Simulate screen runs the studio's own Agent Runtime, as `SimulateService` is written. No worker relay; CR-2's five-route allowlist is untouched. |
| **FD-7.3** | **`RUNTIME_DEFAULT_BLOCK`.** Seam 3 hands `provider_registry` only. `governance_hook` stays the runtime's fail-closed default and is recorded as absent by ruling; every consequential task BLOCKs with `GOVERNANCE_NOT_CONFIGURED` and the trace shows it. No package is added to the image. The governed hook is a later seam of its own (FD-1), entered only when ESCALATE has a sink in the studio or a worker relay is ruled. |
| **FD-7.4** | **`ONE_PINNED_FIXTURE_PROVIDER`.** One provider in `governance-studio-deployment`, its id and version recorded in `approved-runtime-config.json`; it records in memory, returns success, opens no socket and reads no file. It is enabled by one boolean configuration value whose name and error text avoid the word "fixture" (§8.1, startup-integrity classification). No provider list is read from the environment (FD-4: no discovery, no default). |
| **FD-7.5** | **`PROHIBITED_IN_PROFILE`.** The P3E composition root never constructs `AllowAllGovernanceHook` or any permissive hook; startup integrity fails if `governance_hook_permissive` could be true; the composition record states the prohibition. |

**What the ruling authorizes.** Documentation only. No seam is activated, no code is
changed, and the P3E container still hands the studio context the review-service
URL, the activation root and the seam-2 authority reads until seam 3's own
implementation prompt is issued and its PR merges. That step, when entered, ships:
one configuration value, one fixture provider, `provider_registry` handed and
`governance_hook` absent by ruling, the re-worded `agent_execution` entry, a
superseding composition record (FD-3, the seam-2 record kept byte-for-byte), and
matrix rows 1 to 6 as tests, with rows 4 and 6 closing their `[G]`. FD-3, FD-4, the
`REFERENCE_GRADE_SHADOW_ONLY` ceiling, `ENFORCEMENT_ENABLED = False`, the frozen v1
and v2 contracts, every FROM line and ratified digest, and every credential, egress
and LIVE prohibition are preserved. `CONSOLE_BASE_URL` and the governed hook remain
unruled future seams; neither is implemented.

## 9 — Seam 4 audit: `CONSOLE_BASE_URL` (2026-09-06)

**The question.** Can the P3E profile hand the Publish and Observe screens the
console without a second deployment unit or a new egress? **No.** The console is a
root-level prototype service with no authentication, no TLS, no packaging and a
per-instance in-memory audit store, and the Publish screen's request body does not
match the console's request model, so today the compiled-package path can only ever
render a typed gap. Seam 4 is not enterable as it stands; what would have to be true
first is a set of owner decisions (§9.4). Everything below is documentation; no seam
is activated.

### 9.1 What exists today `[V]`

- **The seam.** `build_studio_context(console_base_url=)` builds one `ConsoleClient`
  shared by `PublishService` and `ObserveService` (`app_v2.py:79-95`). The client is
  standard-library `urllib`, sends no credential and no header beyond content type,
  and refuses any route outside a closed set of four before opening a connection:
  `POST /v1/governed-loop/shadow`, `POST /v1/governed-loop/scenario/{id}`,
  `GET /v1/audit`, `GET /v1/audit/{id}` (`clients/console.py:35-45, 95-101`);
  `/v1/actions/authorize`, `/v1/actions/clear` and a hypothetical `/live` are refused
  (`test_v2_operation_ids.py:140-152`, SD-2). Unset, both screens answer the typed
  gap `console_api`; unreachable and empty are distinguished (`studio_v2.py:522-570`).
- **The console.** `ugence_console_api/` at the repository root, version 0.1.0: a
  FastAPI prototype served by `uvicorn` on plain HTTP, `0.0.0.0:8090`, with no
  authentication and CORS `*` (`app.py:42-56`, `__main__.py`). Its `AuditStore` is an
  in-memory dict, documented as "deliberately a prototype seam" (`audit.py:8-11`).
  Its capabilities import root legacy modules (`governance_providers`, `tap_provider`,
  `actiongate_provider`, `ugence_context_minimization`) under fail-safe imports. It is
  not a distribution under `packages/`, has no Dockerfile, no compose file and no
  deployment unit, and is in neither the P3E nor the worker image. It makes no
  outbound call of its own.
- **The shadow loop.** `orchestrator.run` evaluates four stages (context minimization,
  truth assurance, ActionGate, operational clearance), records the chain and returns
  `would_execute`; it invokes no provider and changes nothing in any system in any mode
  (`orchestrator.py:55-140`). `mode` is client-supplied (`SHADOW`, `RECOMMENDATION`,
  `ENFORCEMENT`) and the shadow route does not pin it (`app.py:111-116`,
  `models.py:21-24`).
- **The Publish payload does not fit.** `PublishService.shadow` posts the
  `CompiledReleasePackage` dict verbatim as the body of `/v1/governed-loop/shadow`
  (`studio_v2.py:533-538`); the console's `GovernedLoopRequest` requires `assertion`,
  `action` and `operational_signals` (`models.py:125-131`), none of which a compiled
  package carries (`compiler/release.py:64-82`). The console answers 422, which the
  client surfaces as `ConsoleUnavailable`, so the screen shows the gap `console_api`.
  Only the `scenario_id` path, a frozen console scenario, can succeed. No test in the
  studio exercises a real console `[V]` (the only console tests use an unreachable
  host). A compiled package is not a governed-loop request; mapping one onto the
  other would be the studio authoring governance content (v1 audit rule, FD-4).
- **The profile.** P3E permits exactly one outbound destination, the review relay,
  and the freeze test asserts exactly one (`test_container_artifacts.py:94-104`); the
  review URL must be https and carry no credential. The console has no TLS.
- **The alternative record.** The worker holds the control-plane-root `AuditLedger`,
  durable and hash-chained, but it exposes `append`, `entry_count` and `verify_chain`
  only, no read by reference (`ledger.py:147-238`), and the review service's five
  routes carry linkages on run detail, not a ledger read (`http.py:33-39`). An
  observe-only screen over that ledger (§3 row 10, §4) needs a read port first.

### 9.2 Failure matrix (what the code does today)

| # | Case | Result |
|---|---|---|
| 1 | URL unset | typed gap `console_api` on both screens `[V]` |
| 2 | console unreachable | typed gap naming the failure, never an empty list `[V]` |
| 3 | route outside the four | refused before a socket opens `[V]` |
| 4 | compiled package to the shadow loop | console 422 → typed gap; the path cannot succeed `[V]`, a defect `[G]` |
| 5 | unknown `scenario_id` / unknown correlation id | console 404 → typed gap `[V]`; not distinguished from unreachable `[G]` |
| 6 | `mode` other than shadow inside the payload | not pinned by the studio; the console answers in that mode `[G]` |
| 7 | cross-tenant | the console has no tenant dimension; audit ids are global to one instance `[V]`, `[G]` |
| 8 | credential | none sent, none held, none required by the console: anyone on the segment may post `[V]` |
| 9 | LIVE | no such console route; the allowlist refuses any `live` path `[V]` |
| 10 | restart | the audit store is lost with the console process `[V]` |

### 9.3 Prohibitions any admissible shape must preserve `[V]`

No credential enters the studio; a second egress exists only by ruling, https only,
to a private listener; SD-2 stands (the four routes, nothing that authorizes, clears
or executes); shadow only, with the mode pinned by the studio and never by the
payload; LIVE absent; `ENFORCEMENT_ENABLED` False; the frozen v1 and v2 bytes,
every FROM line and ratified digest untouched; `REFERENCE_GRADE_SHADOW_ONLY`.

### 9.4 Proposed ruling FD-8 (five decisions, recommended option first; ruled in §9.5)

| # | Decision | Options |
|---|---|---|
| **FD-8.1** | Is seam 4 entered now? | **`ABSENT_UNTIL_PREREQUISITES`**: `console_base_url` stays absent by ruling; the Publish and Observe screens keep their typed gap; the prerequisites are FD-8.2 to FD-8.4 and each is its own step. `ENTER_WITH_CONSOLE_AS_THIRD_UNIT`: package and deploy the prototype behind TLS and a gate now. |
| **FD-8.2** | The Publish request | **`PIN_SHADOW_AND_REFUSE_UNMAPPED`**: the studio pins `mode=shadow` in every governed-loop body it sends, and the compiled-package path answers a typed refusal (`publish_payload_unmapped`) rather than relaying a body the console cannot accept; only `scenario_id` reaches the console. `TYPED_ADAPTER`: a ruled, versioned mapping from `CompiledReleasePackage` to `GovernedLoopRequest` (none exists; it would author governance content). |
| **FD-8.3** | The console as a deployable | **`PACKAGE_FIRST`**: before any deployment unit, `ugence_console_api` becomes a distribution under `packages/` with a private TLS listener, an access gate, a pinned scenario set and a stated maturity; the root prototype is never deployed as-is. `DEPLOY_PROTOTYPE`. |
| **FD-8.4** | Egress | **`SECOND_DESTINATION_BY_RULING`**: when seam 4 is entered, the profile's permitted egress moves from one destination to two, https only, the four routes named, the freeze test amended; until then none. |
| **FD-8.5** | Observe's record | **`LABELLED_SINGLE_INSTANCE`**: whenever a console is handed, the Observe screen states it shows one console instance's in-memory audit, lost on restart. `OBSERVE_OVER_WORKER_LEDGER`: a later seam of its own, needing a ledger read port in control-plane-root and a sixth relayed route (amends CR-2). |

Under the recommended options no seam is activated by this ruling; the next
implementation step is FD-8.2 alone (a studio-backend correction with tests, no
deployment change), and seam 4 waits on FD-8.3.

### 9.5 Ruling FD-8 (owner, 2026-09-06)

| # | Ruling |
|---|---|
| **FD-8.1** | **`ABSENT_UNTIL_PREREQUISITES`.** The console does not enter the P3E deployment profile until its prerequisites are separately completed and ratified. Its current root-level prototype, unauthenticated HTTP listener, in-memory audit store and absence from both container images are not an acceptable deployable boundary. |
| **FD-8.2** | **`PIN_SHADOW_AND_REFUSE_UNMAPPED`.** `PublishService` must construct every governed-loop request with mode fixed to shadow. Caller-supplied or compiled-package mode values cannot select enforcement or any other mode. A `compiled_package` lacking a valid `scenario_id` is not translatable to the console's frozen-scenario request shape and must return the typed refusal `publish_payload_unmapped` before any outbound request. It must not invent an assertion, action, signal, scenario or default. For an accepted frozen-scenario request, relay only the validated `scenario_id` using the console's existing request contract. Do not forward arbitrary compiled-package fields. |
| **FD-8.3** | **`PACKAGE_FIRST`.** Before the console may enter deployment, it must become a bounded, installable and tested package or deployment unit with explicit public API, configuration, persistence boundary, authentication boundary, maturity label and import restrictions. Packaging is a separately scoped future body of work; it does not begin here. |
| **FD-8.4** | **`SECOND_DESTINATION_BY_RULING`.** If seam 4 is later admitted, the console is a second explicitly ruled outbound destination. It must use HTTPS, receive an independently frozen allowlist/configuration entry and satisfy the P3E egress and secret constraints. The existing one-destination freeze must not be silently widened in this step. |
| **FD-8.5** | **`LABELLED_SINGLE_INSTANCE`.** Until durable multi-instance storage exists, Observe output may describe only the records held by the identified console instance. Every response and screen must disclose that limitation and must not imply durable, complete, distributed or restart-safe audit coverage. |

**What the ruling authorizes.** FD-8.2 alone enters implementation, in the studio
backend only: no deployment variable, no second egress, no image package, no console
deployment, no console change, the console destination allowlist exactly preserved,
the v2 contract and generated client and the v1 API and its frontend byte-identical.
Seam 4 stays absent by ruling (FD-8.1) until FD-8.3 is completed and ratified as its
own body of work; FD-8.4 and FD-8.5 bind any later admission. `REFERENCE_GRADE_SHADOW_ONLY`
and every credential and LIVE-execution prohibition are preserved.

**FD-8.2 shipped** (studio backend, same PR as this record): `PublishService` validates
`scenario_id` as a typed token before anything else and answers the typed refusal
`publish_payload_unmapped` for a missing, empty, malformed or wrong-type value with
zero outbound calls; it relays only the validated id through the console client's
scenario route, whose body is the constant `{"mode": "shadow"}`; the client's shadow
route, no longer called by the service, also overrides any `mode` it is handed. No
field of `compiled_package` is read. The console allowlist, the frozen runtime
configuration, the v1 and v2 contract bytes and the generated client are unchanged.
The Publish screen, which sends no `scenario_id`, now renders the typed refusal
rather than a console gap; offering a scenario selector is a frontend change for a
later step. Maturity: **Core implemented** for the pin and the refusal; the console
itself remains a prototype (FD-8.1, FD-8.3).

## 10 — Next-step audit under FD-1 (2026-09-06)

**The question.** With seams 1 to 3 shipped and seam 4 absent by ruling, which of
the three remaining front-door candidates can be entered next as one bounded seam?
**Screen 1, a typed registration form over `ai-system-registry`.** The governed hook
has no admissible home in P3E, and a durable Decision Authority store would hold
nothing because no deployment produces decision records. Everything below is
documentation; no seam is activated.

### 10.1 The governed hook seam `[V]`

- `GovernedExecutionHook` composes over a deployment-supplied `GovernanceInputSource`;
  an ESCALATE leaves the task WAITING and the workflow PAUSED, and the runtime proceeds
  only through `resume_workflow`, which HR-4 keeps bare and unexposed: the DBOS adapter
  is the only caller (`engine.py:8-10, 195-203`; human-review ADR §5 HR-4).
- The only ESCALATE sink in the repository is the worker: `ApprovalBoundInputSource`
  over the approval ledger and directory, the review service's queue and the bounded
  resume (HR-A to HR-E, `governed-runtime-worker/composition.py:227-238`). The
  service's five routes carry no ingest for a run that lives elsewhere (`http.py:33-39`).
- The studio's simulation runtime is in-process and in-memory: no checkpoint, state or
  event store is handed (`SimulateService.run`, `studio_v2.py`), so a parked run cannot outlive the
  request, let alone reach a queue.
- Therefore the hook in P3E is either a hook whose ESCALATE has no sink, which FD-7.3
  already refused, or the worker's stack composed into P3E, which reopens CR-1. `[I]`
  Its admissible shape is `WORKER_RELAY` (the FD-7.2 alternative): a Simulate run
  executed by the worker and relayed like the review screens, which amends CR-2's
  five-route allowlist and the worker itself. Not a front-door seam of the studio
  alone; not next.

### 10.2 The durable Decision Authority store `[V]`

- `decision-authority` 1.0.0 is frozen (gap-sequencing D-2) and ships in-memory
  repositories only; `DecisionCaseRepository` is a seventeen-method append-only port
  with no durable implementation and no ruling on its persistence posture (Risk
  Authority has one; Decision Authority does not).
- No deployment produces a decision record. The worker's hook consumes Decision
  Authority as a `GovernanceVetoResult` mapped from outcome values
  (`risk-authority-runtime/decision_authority_adapter.py:74-149`); nothing calls
  `create_case` or `record_decision`. A durable store handed to P3E would be empty,
  and the studio must not write it (SD-2).
- The studio's read does not fit the port: `AuthorityService.decision` calls
  `decision_store.get(decision_id)` (`studio_v2.py:389-395`) where the port offers
  `get_decision` and returns a `DecisionRecord`; the same class of mismatch seam 2
  corrected for the policy registry `[G]`.
- Therefore a durable Decision Authority store is a package decision (persistence
  posture, a producer, and the studio read corrected) before it can be a seam. Not next.

### 10.3 Screen 1, a typed registration form over `ai-system-registry` `[V]`

- The package ships `SystemRegistration`, `AssessedSystemBinding`, deterministic
  `registration_id_for`, `supersession_refusals` and one read-only `SystemRegistryPort`
  Protocol with no implementation and no store (registry ADR D-4); it records and
  never gates (D-5); the classification label is uninterpreted (D-2); a changed system
  is a new registration carrying `supersedes` (D-3). Three front-door composition
  records already exercise exactly this record type and chain (FD-3, §7).
- FD-4 is satisfied by the record itself: every field is typed and validated by the
  package's own refusal reasons; nothing is inferred; a blank label or owner is
  refused. §4 of this ADR already names a typed registration form over
  `ai-system-registry` as admissible, and forbids prose intake.
- What the seam needs that does not exist: (a) a durable home, since "a composition
  root holds whatever it registers" and the registry ADR places the operational
  registry and its systems-of-record connectors post-v1 under D-5 `[R]` whether a
  local sqlite store under the runtime volume, in the seam-1 posture, is inside or
  outside that line; (b) a registrant: `owner_ref` is a non-secret directory handle,
  never an authenticated identity, and no IdP exists (AI-C waits on an issuer), so the
  registrant is presented and unproven `[R]`; (c) two v2 operations, which change the
  frozen `openapi_v2.json` bytes and the generated client for the first time since
  the freeze `[R]`; (d) one screen, under the same frontend version, as HR-D added the
  review screens `[I]`.
- The seam's only write would be `register`. SD-2's verbs (issue, activate, revoke,
  grant, authorize, clear, execute) do not cover it, D-5 makes a registration an input
  to somebody else's decision, and the record confers nothing; but it is the front
  door's first mutation from the studio, and FD-6 recorded seam 2 as conferring no
  mutation, so the boundary needs its own ruling `[R]`.

### 10.4 Recommendation and proposed ruling FD-9 (five decisions, recommended first; ruled in §10.5)

Screen 1 is the only candidate whose prerequisites are rulings rather than packages
or deployment units.

| # | Decision | Options |
|---|---|---|
| **FD-9.1** | Next seam | **`SCREEN_1_TYPED_REGISTRATION`**: seam 5 is a typed registration form over `ai-system-registry`, composed through the P3E root, tenant-bound to `UGENCE_STUDIO_TENANT_ID`. `GOVERNED_HOOK_VIA_WORKER_RELAY` (amends CR-2 and the worker). `DECISION_STORE_PACKAGE_FIRST` (a package decision, not a seam). |
| **FD-9.2** | Durable home | **`LOCAL_SQLITE_UNDER_RUNTIME_VOLUME`**: `ai-system-registry` 0.2.0 adds one sqlite implementation of `SystemRegistryPort` plus a single append, `register`, in the seam-1 posture (a file under the runtime volume; no server, driver or DSN; the `persistent_database` prohibition stands); D-5's post-v1 line is read as the systems-of-record connectors, which stay unbuilt. `COMPOSITION_ROOT_MEMORY`: held in process, lost on restart, labelled. |
| **FD-9.3** | Registrant | **`OWNER_REF_PRESENTED_UNPROVEN`**: `owner_ref` is a typed opaque handle the form supplies, recorded as presented and unproven; `registered_by` is the deployment name and version; no identity is claimed until an issuer exists (AI-C). `REQUIRE_IDENTITY` (blocks on the issuer). |
| **FD-9.4** | Contract | **`V2_AMENDMENT_TWO_OPERATIONS`**: `v2_registry_register` and `v2_registry_list`, validated by the package's own refusal reasons and `supersession_refusals`, with `openapi_v2.json` and the generated client re-frozen by their own amendment record in the same step. `NO_CONTRACT_CHANGE` (not possible: no operation exists). |
| **FD-9.5** | Mutation boundary | **`REGISTER_IS_THE_ONLY_WRITE`**: the seam writes registrations and nothing else; no edit, no revocation, no gate, no admission, no attestation; a changed system is a new registration superseding the old (D-3); the record confers no approval, maturity, authority or permission; SD-2 and every credential and LIVE prohibition unchanged. |

Under the recommended options seam 5 ships in its own implementation step: the
package release, the two operations with a re-frozen contract, the screen, the
deployment composition (one registry file under the runtime volume, tenant-bound),
a superseding composition record, and a failure matrix (missing tenant, blank owner
or label, inadmissible supersession, cross-tenant read, restart, contract-byte
amendment recorded).

### 10.5 Ruling FD-9 (owner, 2026-09-06)

| # | Ruling |
|---|---|
| **FD-9.1** | **`SCREEN_1_TYPED_REGISTRATION`.** Seam 5 is a typed registration form over `ai-system-registry`, composed through the P3E root and tenant-bound to `UGENCE_STUDIO_TENANT_ID`. The governed hook stays a later seam in the worker-relay shape, and a durable Decision Authority store stays a package decision. |
| **FD-9.2** | **`LOCAL_SQLITE_UNDER_RUNTIME_VOLUME`.** `ai-system-registry` 0.2.0 adds one sqlite implementation of `SystemRegistryPort` plus a single append, `register`, in the seam-1 posture: a file under the writable runtime volume, no server, no driver, no DSN, the `persistent_database` prohibition standing. D-5's post-v1 line is read as the systems-of-record connectors, which stay unbuilt. |
| **FD-9.3** | **`OWNER_REF_PRESENTED_UNPROVEN`.** `owner_ref` is a typed opaque handle the form supplies, recorded as presented and unproven; `registered_by` is the deployment name and version; no identity is claimed until an issuer exists (AI-C). |
| **FD-9.4** | **`V2_AMENDMENT_TWO_OPERATIONS`.** `v2_registry_register` and `v2_registry_list`, validated by the package's own refusal reasons and `supersession_refusals`; `openapi_v2.json` and the generated client are re-frozen by their own amendment record in the same step, the first amendment since the v2 freeze. |
| **FD-9.5** | **`REGISTER_IS_THE_ONLY_WRITE`.** The seam writes registrations and nothing else: no edit, no revocation, no gate, no admission, no attestation; a changed system is a new registration superseding the old (D-3); the record confers no approval, maturity, authority or permission; SD-2 and every credential and LIVE prohibition unchanged. |

**What the ruling authorizes.** Documentation only. No seam is activated, no code is
changed, no package is released and no contract byte moves. Seam 5 activates by its
own implementation prompt, which will ship in one step: `ai-system-registry` 0.2.0,
the two operations with the re-frozen contract and generated client, the screen, the
deployment composition (one registry file under the runtime volume, tenant-bound,
one configuration value), a superseding composition record (FD-3), and the failure
matrix named in §10.4. FD-1, FD-3, FD-4, the `REFERENCE_GRADE_SHADOW_ONLY` ceiling,
`ENFORCEMENT_ENABLED = False`, the frozen v1 contract, every FROM line and ratified
digest, and every credential, egress and LIVE prohibition are preserved.

## 11 — Audit: the governed hook in the worker-relay shape (2026-09-06)

**The question.** With seams 1, 2, 3 and 5 shipped and seam 4 absent by ruling, can
the governed hook reach the Simulate screen as a run executed by the worker and
relayed like the review screens? **Yes, in exactly one shape:** the studio asks the
worker to start the worker's own shadow workflow and reads it back through the routes
that already exist; nothing the studio holds crosses the wire. Whether asking another
unit to start its fixture run is the studio "executing" under SD-2 is the owner's
call. Everything below is documentation; no seam is activated.

### 11.1 What exists today `[V]`

- **No route starts a run.** The review service exposes five routes (four reads, one
  relayed decision; `http.py:33-39`); its only adapter calls are `status`, `signal`
  and `resume` (`service.py:309, 530, 554`). The worker's own end-to-end test starts
  its run in process, `worker.adapter.start(workflow_id=ShadowWorkload.WORKFLOW_ID, …)`
  (`test_end_to_end.py:115`). The studio's review client is a closed set of the same
  five routes with one proof route (`clients/review.py`), the P3E egress record names
  the five (`approved-runtime-config.json`, `external_network_egress.permitted[0].routes`),
  and the frontend manifest freezes them (`review_service_routes_reachable_from_the_studio`).
- **The worker runs one definition.** `ShadowWorkload` defines `wf-shadow` only, one
  consequential task on the `FIXTURE_ONLY` `ShadowProvider`, and its upstream source
  parks every proposal on ESCALATE (`workload.py`). The DBOS adapter binds every
  instance to the worker's `definition_digest` at composition and refuses a start under
  any other (`DefinitionVersionMismatch`, `dbos_engine.py:222-236`), refuses a
  conflicting duplicate start and returns the existing handle for an identical one
  (`InstanceIdentityError`, idempotent on `instance_id`). A studio-supplied workflow
  therefore cannot run on the worker at all; that is a property, not a choice.
- **The sink exists.** ESCALATE from the governed hook lands in the approval ledger
  and the review queue; the existing decision relay resumes the bounded quantum
  (HR-A to HR-E). A relayed run needs no new sink.
- **The worker's postures hold.** Private TLS listener, identity port mandatory in
  production (CR-3), one deployment-mode switch (CR-4), JWKS as its only egress (CR-5),
  `SINGLE_TENANT` with its own configured tenant.
- **What the rulings say.** CR-2 names one configuration value and the five routes;
  HR-1 says the studio "holds no approver identity, computes no eligibility, consumes
  nothing, signals nothing and resumes nothing"; SD-2 says the studio never executes;
  FD-7.1 admitted a fixture-only, non-LIVE run in P3E as a demonstration, not agent
  execution; FD-7.3 kept the hook out of P3E because ESCALATE had no sink there.

### 11.2 The one admissible shape `[I]`

A sixth worker route, `POST /review/runs`, that starts the worker's own `wf-shadow`
with a worker-minted instance id and an optional typed correlation id, idempotent by
the adapter's own rule; the studio relays it through its client, then reads the run,
its events and its approvals through the four routes it already has, and a human's
decision travels through the one relay it already has. No workflow, task, provider,
mode or digest is sent: the digest binding makes any other shape unrunnable, and FD-4
forbids untyped intake. The Simulate screen would show two labelled paths: the seam-3
in-process fixture run (hook absent, every consequential task BLOCKs) and the worker
relay (the governed hook over the approval-bound source, ESCALATE parked in the
review queue, resumed only by a recorded decision).

What it amends: the worker (one route, one `adapter.start` call, tests); the review
service (`ROUTES` gains one entry whose operation id passes the prohibition scan); the
studio's review client (six routes, the proof route unchanged); CR-2 and the P3E
egress record and its freeze test (six routes); the frontend manifest; the v2 contract
(a second amendment, one operation) and its generated client; HR-1's wording (the
studio may start the worker's own shadow run; it still signals and resumes nothing).
It adds no configuration value, no package to the P3E image, no credential and no
second egress destination.

### 11.3 Failure matrix (what the code does today, or would by construction)

| # | Case | Result |
|---|---|---|
| 1 | review URL unset | typed gap `review_service`, as the review screens `[V]` |
| 2 | worker unreachable, or the route absent on an older worker | typed gap naming the failure, never an empty run `[V]` (HTTP 404 surfaces as unavailable) |
| 3 | a studio-supplied workflow, provider, mode or digest | not expressible: the route takes none; a foreign digest is refused by the adapter `[V]` |
| 4 | duplicate start | idempotent on the instance id; a conflicting one refused `[V]` |
| 5 | ESCALATE | parked in the existing queue; visible on Review, resumed only by a recorded decision `[V]` |
| 6 | decision without a proof | `PRESENTED_UNPROVEN`, as today; production requires the identity port (CR-3) `[V]` |
| 7 | cross-tenant | the worker is `SINGLE_TENANT` with its own tenant; the studio names none `[V]` |
| 8 | LIVE | the worker's providers are `FIXTURE_ONLY`; the route names no mode `[V]` |
| 9 | credential | none crosses on the start; the proof header stays on the decision route only (ID-1) `[V]` |
| 10 | the studio's in-process Simulate | unchanged; a second, labelled path, never merged `[G]` until built |

### 11.4 Prohibitions any admissible shape must preserve `[V]`

No credential in the studio; no second egress destination (the worker's listener is
the one already permitted); the worker's only egress stays the JWKS host (CR-5); no
studio-supplied definition, provider or mode; SD-2's seven verbs absent from every
operation id and path; LIVE absent; `ENFORCEMENT_ENABLED` False; the frozen v1 bytes,
every FROM line and ratified digest untouched; `REFERENCE_GRADE_SHADOW_ONLY`; the
worker image's own gate set unchanged.

### 11.5 Proposed ruling FD-10 (five decisions, recommended first; ruled in §11.6)

| # | Decision | Options |
|---|---|---|
| **FD-10.1** | Is starting the worker's own shadow run the studio executing (SD-2)? | **`START_IS_A_RELAY`**: asking a separate unit to start the fixture workflow it already owns, over `FIXTURE_ONLY` providers, with nothing supplied by the studio, is display and transmit in FD-7.1's sense, not execution; SD-2's verbs stay absent from the route. `START_IS_EXECUTION`: the relay stays absent. |
| **FD-10.2** | The route | **`SIXTH_ROUTE_START_SHADOW_RUN`**: `POST /review/runs` on the worker, body an optional typed correlation id, the worker mints the instance id, idempotent by the adapter's rule. `SEPARATE_SIMULATE_SERVICE` (a new unit; not next). |
| **FD-10.3** | What crosses | **`NO_DEFINITION_CROSSES`**: no workflow, task, provider, mode or digest is sent; the worker's definition digest binds. `TYPED_DEFINITION_UPLOAD` (refused by the digest binding). |
| **FD-10.4** | The amendment set | **`ONE_STEP_AMENDMENT`**: CR-2 (six routes), HR-1 (start of the worker's own shadow run added; signal and resume still absent), the P3E egress record and freeze test, the frontend manifest, the v2 contract (amendment v2-A2, one operation) and generated client, in one step with tests. |
| **FD-10.5** | The Simulate screen | **`TWO_LABELLED_PATHS`**: the in-process fixture run and the worker relay are distinct, each labelled with its executor, hook and maturity; never merged into one "run". |

### 11.6 Ruling FD-10 (owner, 2026-09-06)

| # | Ruling |
|---|---|
| **FD-10.1** | **`START_IS_A_RELAY`.** Asking the separate governed runtime worker to start the fixture workflow it already owns, over `FIXTURE_ONLY` providers, with nothing supplied by the studio, is display and transmit in FD-7.1's sense, not execution. SD-2's seven verbs stay absent from every operation id and path; the studio still executes nothing. |
| **FD-10.2** | **`SIXTH_ROUTE_START_SHADOW_RUN`.** Seam 6 is `POST /review/runs` on the worker: the body is an optional typed correlation id, the worker mints the instance id, the start is idempotent by the DBOS adapter's own rule, and the run is read back through the four existing reads and resumed only through the existing decision relay. |
| **FD-10.3** | **`NO_DEFINITION_CROSSES`.** No workflow, task, provider, mode or digest is sent by the studio; the worker's `definition_digest` binds every instance to the definition it already runs, and the adapter's refusal of any other digest stands as the property that makes the seam safe. |
| **FD-10.4** | **`ONE_STEP_AMENDMENT`.** CR-2 (six routes), HR-1's wording (the studio may start the worker's own shadow run; it still signals and resumes nothing), the P3E egress record and its freeze test, the frontend manifest, and the v2 contract (amendment v2-A2, one operation) with its generated client are amended together, in one step, with tests. No configuration value, image package, credential or second egress destination is added. |
| **FD-10.5** | **`TWO_LABELLED_PATHS`.** The Simulate screen shows the seam-3 in-process fixture run and the worker relay as distinct paths, each labelled with its executor, its hook and its maturity; they are never merged into one "run". |

**What the ruling authorizes.** Documentation only. No seam is activated, no route
exists, no contract byte moves and no code changes. Seam 6 activates by its own
implementation prompt (issued and shipped 2026-09-06; see §7), which ships in one step: the worker route and its
`adapter.start` call with tests, the review service's sixth `ROUTES` entry, the
studio's review client and relay service, the v2 amendment v2-A2 with the regenerated
client, the frontend manifest and the Simulate screen's second labelled path, the P3E
egress record and freeze test, CR-2 and HR-1 amended in their ADRs, and the failure
matrix of §11.3 as tests. FD-1, FD-3, FD-4, SD-2, CR-3, CR-4, CR-5, the
`REFERENCE_GRADE_SHADOW_ONLY` ceiling, `ENFORCEMENT_ENABLED = False`, the frozen v1
contract, every FROM line and ratified digest, the worker image's gate set, and every
credential, egress and LIVE prohibition are preserved.

## 12 — Next-step audit under FD-1 (2026-09-06, after seam 6)

**The question.** With seams 1, 2, 3, 5 and 6 shipped and seam 4 absent by ruling,
which of the three remaining candidates can be entered next as one bounded seam: the
console once FD-8.3 is satisfiable, a durable Decision Authority record store as a
package decision, or Observe over the worker's ledger (FD-8.5's later seam)?
**Observe over the worker's ledger.** The console is a package-and-deployment body of
work that FD-8.3 says does not begin here, and a durable Decision Authority store
would still hold nothing. Everything below is documentation; no seam is activated.

### 12.1 The console once FD-8.3 is satisfiable `[V]`

- **Unchanged since §9.1.** `ugence_console_api/` is still the root-level prototype:
  two commits in its history (`785f49e56`, `6509dc5fa`), no distribution under
  `packages/` or `products/` (a name search finds none), plain HTTP on `0.0.0.0:8090`
  with CORS `*` (`app.py:42-56`), and an in-memory `AuditStore` documented as "a
  prototype seam" (`audit.py:8-11`). Its audit record is the console's own shape
  (`AuditChain`: `correlation_id`, `cer_id`, `mode`, `final_disposition`, stage
  entries; `models.py:169-182`), read by `list_ids` and `get` (`audit.py:26-34`).
- **FD-8.3 is not satisfiable by a front-door step.** The ruling names what must be
  true first (a bounded, installable, tested package or deployment unit with explicit
  public API, configuration, persistence boundary, authentication boundary, maturity
  label and import restrictions) and says "packaging is a separately scoped future body
  of work; it does not begin here" (§9.5). None of those exists. The console's
  capabilities import root legacy modules under fail-safe imports (§9.1), so the
  import-restriction boundary alone is a scoping question of its own.
- **What entering it would amend.** A new package or third deployment unit with its
  own scoping ADR, gate set and evidence manifest (as the worker has); FD-8.4's second
  egress destination, moving the P3E freeze from one destination to two, https only,
  with the four console routes named; the console client unchanged; the Observe screen
  labelled per FD-8.5. **What it must preserve.** No credential in the studio; SD-2's
  four console routes and nothing that authorizes, clears or executes; the mode pinned
  to shadow by the studio (FD-8.2); LIVE absent; `REFERENCE_GRADE_SHADOW_ONLY`;
  `ENFORCEMENT_ENABLED` False; the frozen v1 bytes, every FROM line and ratified
  digest.
- `[I]` At least three ruled steps stand between here and seam 4: the console's own
  scoping and packaging ADR, its deployment unit and evidence, then FD-8.4's egress
  amendment. Not a front-door seam; not next.

### 12.2 A durable Decision Authority record store `[V]`

- **Frozen and in-memory.** `decision-authority` 1.0.0 "stays frozen" (gap-sequencing
  ratification D-2). `DecisionCaseRepository` is an eighteen-method append-only Protocol
  (`repositories/decision_case_repository.py:29-52`; §10.2 counted seventeen, corrected
  here) with `InMemoryDecisionCaseRepository` as its only implementation, alongside the
  in-memory action-request and execution repositories; no sqlite or other durable
  implementation exists in the package.
- **No producer.** Outside the package, `create_case` and `record_decision` are called
  only by test harnesses and the external-consumer packaging example
  (`packages/providers/actiongate/tests/lifecycle_harness.py:74-76`,
  `packages/governance-provider-framework/tests/kernel_lifecycle.py:47-49`,
  `packaging/external_consumer/consumer.py:85-89`). No deployment unit produces a
  decision record; the worker consumes Decision Authority as a `GovernanceVetoResult`
  (§10.2). A durable store handed to P3E would be empty, and the studio must not write
  it (SD-2).
- **The studio read still mismatches the port.** `AuthorityService.decision` calls
  `decision_store.get(decision_id)` (`studio_v2.py:406-412`) where the port offers
  `get_decision` and returns a `DecisionRecord` `[G]`, the same class of mismatch seam 2
  corrected for the policy registry.
- **What entering it would amend.** A persistence posture ruling for a frozen 1.0.0
  package (or a sqlite implementation in a sibling integration package, as
  `ai-system-registry` 0.2.0 did for its own port); a producer, which none of the
  deployed units is; the studio read corrected; one P3E configuration value and one
  file under the runtime volume; a composition record. **What it must preserve.** SD-2
  (the studio never creates a case or records a decision); the `persistent_database`
  prohibition (a file under the volume, no server, no driver, no DSN); tenant binding;
  every credential and LIVE prohibition.
- `[I]` A package decision first, a front-door seam only once a deployed unit produces
  records. Not next.

### 12.3 Observe over the worker's ledger `[V]`

- **The record exists and is durable.** The worker composes the control-plane-root
  `AuditLedger` at `<data_dir>/audit-ledger.sqlite3` (`composition.py:214`): per-tenant,
  hash-chained, append-only by database triggers, schema-versioned (`ledger.py:96-140`).
  Since HE-1 the review service appends one `governed_review.linkage.v2` entry per
  completed round trip, carrying the checkpoint's `correlation_id`, `recorded_by` the
  worker, and the `ReviewLinkage` payload (instance, task, consumer ref, proposal
  fingerprint, approval id and state, decider, timestamps; `linkage.py:167-215`,
  `governed-review/linkage.py:118-132`). Seam 6's relayed runs land in it on a GRANT.
- **The ledger has no read for observation.** Its public reads are `entry_count` and
  `verify_chain`, "for verification only" (`ledger.py:200-236`); the README states "no
  console, no connector, no reconstruction API" (`README.md:115`), and the
  control-plane-root ADR scopes the first slice to "the audit-ledger service and
  nothing else" (D-5) and forbids the root to own any decision, queue or second
  vocabulary (D-4). `StoredEntry` (`ledger.py:57-75`) is what a row is: the entry, its
  sequence, `prev_digest` and `record_digest`, and `entry_ref = <tenant>/<seq>`.
- **A read-only precedent exists.** `LedgerLinkageIndex` in the review service opens
  the ledger file `mode=ro`, refuses any schema version but the one the installed
  package declares, and reads one row by digest, "writes nothing and interprets
  nothing else" (`linkage.py:114-165`). Run detail already returns the linkages of
  one instance with their `AuditReference` (HE-5, `service.py:296-314`), and the
  studio's Run Detail screen renders them as history.
- **What Observe would add.** What §3 row 10 and §4 named: the durable, chain-verified
  record read by correlation id rather than by instance, which is what the Observe
  screen's subtitle promises ("reconstruct a decision chain by correlation id") and
  what the console path cannot deliver while it is absent (FD-8.1). The record type
  differs from the console's stage chain: it is receipts, digests and references, not
  stage narratives; the screen must say so (FD-8.5's labelling, extended).
- **What entering it would amend.** (a) A ledger read: either a read port in
  `control-plane-root` (`read_entries(tenant_id, correlation_id)` returning stored
  entries in `tenant_seq` order plus the chain verification, which touches D-5 and the
  README's "no reconstruction API" and needs the owner to rule that a raw, uninterpreted
  read is not reconstruction `[R]`), or a second read-only index in the review service
  on the `LedgerLinkageIndex` precedent, which changes no package API but puts schema
  knowledge in a second place `[I]`. (b) The review service: a seventh route, a read,
  whose operation id passes the prohibition scan; CR-2 amended to seven routes. (c) The
  studio's review client (seven routes, the proof route unchanged), an Observe relay
  service that returns the worker's answer unchanged, the v2 contract (amendment v2-A3,
  one operation) and its generated client, the frontend manifest, and the Observe screen
  showing the worker ledger as a labelled source beside the console's typed gap. (d) The
  P3E egress record and freeze test (seven routes over the one destination), a
  superseding composition record. No configuration value, image package, credential or
  second egress destination is added. **What it must preserve.** Read-only: no append,
  edit or verification-trigger route from the studio (the append is the review
  service's own act on a GRANT); the studio re-derives, re-orders and re-hashes nothing
  and shows the worker's verification result as the worker's; the worker reads its own
  tenant only (`SINGLE_TENANT`; the studio names none); the proof header stays on the
  decision route (ID-1); SD-2's verbs absent from every operation id and path; no
  credential; LIVE absent; `ENFORCEMENT_ENABLED` False; the frozen v1 bytes, every
  FROM line and ratified digest; `REFERENCE_GRADE_SHADOW_ONLY`; FD-8.1 (the console
  stays absent) and FD-8.5 (the source is labelled).

### 12.4 Failure matrix for seam 7 (what the code does today, or would by construction)

| # | Case | Result |
|---|---|---|
| 1 | review URL unset | typed gap `review_service`, as the review screens and the worker path `[V]` |
| 2 | older worker without the route, or unreachable | typed gap naming the failure, never an empty chain `[V]` (404 surfaces as unavailable) |
| 3 | unknown correlation id | typed not-found from the worker, distinguished from unreachable `[G]` until built |
| 4 | chain fails verification | the ledger raises `LedgerIntegrityError` (`ledger.py:224-232`); the route must answer a typed integrity refusal, never a 500 and never the entries alone `[G]` |
| 5 | ledger schema version differs | refused by the read, as the index refuses today `[V]` |
| 6 | ledger file absent or in memory | refused before a connection: the index refuses `:memory:` today `[V]` |
| 7 | cross-tenant | the worker reads its own configured tenant; the ledger is keyed per tenant; the studio names none `[V]` |
| 8 | a write from the studio | not expressible: the route is a read; the ledger refuses UPDATE and DELETE by trigger `[V]` |
| 9 | credential or proof on the read | none crosses; the proof route stays the decision relay (ID-1) `[V]` |
| 10 | the console path | unchanged: the typed gap `console_api` beside the labelled worker source (FD-8.1, FD-8.5) `[G]` until built |

### 12.5 Recommendation and proposed ruling FD-11 (five decisions, recommended first; ruled in §12.6)

Observe over the worker's ledger is the only candidate whose prerequisites are rulings
rather than packages, deployment units or producers, and it follows the seam-6 shape
exactly: one relayed route, one contract amendment, no new destination.

| # | Decision | Options |
|---|---|---|
| **FD-11.1** | Next seam | **`OBSERVE_OVER_WORKER_LEDGER`**: seam 7 is a read of the worker's control-plane audit ledger by correlation id, relayed through the review service like seam 6. `CONSOLE_PACKAGING_BODY_OF_WORK` (FD-8.3; not a front-door seam). `DECISION_STORE_PACKAGE_DECISION` (empty until a producer exists). |
| **FD-11.2** | Where the read lives | **`READ_PORT_IN_CONTROL_PLANE_ROOT`**: `control-plane-root` 0.2.0 adds one read-only, tenant-scoped `read_entries(tenant_id, correlation_id)` returning stored entries in chain order with their digests, plus the existing `verify_chain`; the ADR's D-5 and the README's "no reconstruction API" are amended to say a raw, uninterpreted read of a tenant's own rows is not reconstruction; the ledger stays the one owner of its schema. `REVIEW_SERVICE_READ_INDEX`: a second read-only index on the `LedgerLinkageIndex` precedent; no package change, schema knowledge in two places. |
| **FD-11.3** | The route | **`SEVENTH_ROUTE_LEDGER_READ`**: `GET /review/audit/{correlation_id}` on the worker returns its own tenant's entries for that correlation id in `tenant_seq` order (kind, `recorded_at`, `recorded_by`, payload, `entry_ref`, `record_digest`, `prev_digest`) and the chain verification result as a typed field; an integrity failure is a typed refusal; unknown is a typed not-found; no list-all route. `LINKAGES_ON_RUN_DETAIL_ONLY` (exists already; no seam). |
| **FD-11.4** | The Observe screen | **`TWO_LABELLED_SOURCES`**: the worker ledger (durable, per-tenant, hash-chained, `REFERENCE_GRADE`, receipts not stage narratives) and the console (the typed gap `console_api` while FD-8.1 holds), each labelled with its record type, executor and maturity, never merged; the screen re-derives nothing and shows the worker's verification result as the worker's. `REPLACE_CONSOLE_PATH`. |
| **FD-11.5** | The amendment set and mutation boundary | **`READ_ONLY_ONE_STEP_AMENDMENT`**: CR-2 (seven routes), the P3E egress record and freeze test, the frontend manifest, the v2 contract (amendment v2-A3, one operation) with its generated client, and `control-plane-root` 0.2.0, in one step with tests; no append, edit or verification-trigger route from the studio; no configuration value, image package, credential or second egress destination. |

Under the recommended options seam 7 ships in its own implementation step: the
read port with tests, the seventh route and its `ROUTES` entry, the studio's client
and relay service, the v2 amendment and generated client, the frontend manifest and
the Observe screen's labelled worker source, the P3E egress record and freeze test,
CR-2 amended, a superseding composition record, and §12.4 as tests. Owner decisions
remaining before implementation: the five above, of which FD-11.2 carries the one
`[R]` (whether a raw read amends D-5 or falls outside it).

### 12.6 Ruling FD-11 (owner, 2026-09-06)

| # | Ruling |
|---|---|
| **FD-11.1** | **`OBSERVE_OVER_WORKER_LEDGER`.** Seam 7 is a read of the worker's control-plane audit ledger by correlation id, relayed through the review service as seam 6 relays the start. The console stays a packaging body of work under FD-8.3, and a durable Decision Authority store stays a package decision; neither is a front-door seam. |
| **FD-11.2** | **`READ_PORT_IN_CONTROL_PLANE_ROOT`.** `control-plane-root` 0.2.0 adds one read-only, tenant-scoped read of a tenant's own rows by correlation id, returning stored entries in chain order with their digests, beside the existing `verify_chain`; its ADR's D-5 and its README's "no reconstruction API" are amended to say that a raw, uninterpreted read of a tenant's own rows is not reconstruction, and the ledger stays the one owner of its schema. The owner records `REVIEW_SERVICE_READ_INDEX` (a second read-only index on the `LedgerLinkageIndex` precedent, no package change) as the admissible alternative; seam 7's implementation prompt names which of the two it ships, and the control-plane-root amendment is the recommended one. |
| **FD-11.3** | **`SEVENTH_ROUTE_LEDGER_READ`.** `GET /review/audit/{correlation_id}` on the worker returns its own tenant's entries for that correlation id in `tenant_seq` order (kind, `recorded_at`, `recorded_by`, payload, `entry_ref`, `record_digest`, `prev_digest`) and the chain verification result as a typed field. An integrity failure is a typed refusal, never a 500 and never the entries alone; an unknown correlation id is a typed not-found; there is no list-all route. |
| **FD-11.4** | **`TWO_LABELLED_SOURCES`.** The Observe screen shows the worker ledger (durable, per-tenant, hash-chained, `REFERENCE_GRADE`, receipts rather than stage narratives) and the console (the typed gap `console_api` while FD-8.1 holds) as distinct sources, each labelled with its record type, executor and maturity, never merged. The screen re-derives, re-orders and re-hashes nothing and shows the worker's verification result as the worker's. |
| **FD-11.5** | **`READ_ONLY_ONE_STEP_AMENDMENT`.** CR-2 (seven routes), the P3E egress record and its freeze test, the frontend manifest, the v2 contract (amendment v2-A3, one operation) with its generated client, and `control-plane-root` 0.2.0 are amended together, in one step, with tests. No append, edit or verification-trigger route exists from the studio; no configuration value, image package, credential or second egress destination is added. |

**What the ruling authorizes.** Documentation only. No seam is activated, no route
exists, no package is released, no contract byte moves and no code changes. Seam 7
activates by its own implementation prompt (issued and shipped 2026-09-06; see §7),
which ships in one step: the read
port in `control-plane-root` 0.2.0 with tests and its ADR and README amended, the
review service's seventh `ROUTES` entry and route with tests, the studio's review
client and Observe relay service, the v2 amendment v2-A3 with the regenerated client,
the frontend manifest and the Observe screen's labelled worker source beside the
console's gap, the P3E egress record and freeze test, CR-2 amended in its ADR, a
superseding composition record, and the failure matrix of §12.4 as tests. FD-1, FD-3,
FD-4, FD-8.1, FD-8.5, SD-2, CR-3, CR-4, CR-5, ID-1, the `REFERENCE_GRADE_SHADOW_ONLY`
ceiling, `ENFORCEMENT_ENABLED = False`, the frozen v1 contract, every FROM line and
ratified digest, the worker image's gate set, and every credential, egress and LIVE
prohibition are preserved.

## 13 — Remaining front-door audit under FD-1 (2026-09-06, after seam 7)

**The question.** With seams 1, 2, 3, 5, 6 and 7 shipped and seam 4 absent by ruling,
is any front-door seam of the studio alone still enterable, or is what remains the
console packaging body of work (FD-8.3), a durable Decision Authority store as a
package decision, or the three owner-blocked inputs? **One studio-alone seam remains:
outline screen 5, a typed declaration form over `data-use-admission` in the seam-5
shape.** Everything else is a package decision, a separately scoped body of work, an
owner input, or a non-goal. Everything below is documentation; no seam is activated.

### 13.1 The outline rows still without a screen `[V]`

- **Row 5, data and tool connections.** `data-use-admission` 0.1.0 and
  `vendor-dependency` 0.1.0 are both `CONTRACTS_ONLY` (`version.py:16` in each): each
  ships one typed record (`DataUseDeclaration`: binding, `data_ref`, an uninterpreted
  classification label, `purpose_label`, validity, `residency_label`, `supersedes`,
  `declared_by`; `VendorDependencyDeclaration` likewise with `vendor_ref` and a risk
  posture label), a deterministic `declaration_id_for`, `supersession_refusals`, and
  one read-only port (`DataUseDeclarationPort`, `VendorDependencyPort`;
  `selectors.py:131` and `:135`) with no implementation and no store. Each README
  says the package "records what a declarer asserted" and never inspects, verifies,
  scores, persists or decides. That is exactly `ai-system-registry`'s state before
  FD-9, and seam 5 is the proven shape for it. The row's third element, egress
  restrictions, was described here as having a ratified ADR and no package. That was
  wrong from seam 8 onward and is corrected in that ADR's §7: it is discharged, and
  what stays `[G]` is *result* egress (DE-1), a seam no document has declared.
- **Row 4, model and reasoning selector.** `model-selection` and
  `reasoning-method-governance` are 0.1.0 research-only slices (§3); roadmap §11.2 rules
  "no research-only package in the product". Not enterable as a screen `[V]`.
- **Row 7's evidence half.** `agent-assurance-evidence` is
  `REFERENCE_GRADE_CONTRACT_ONLY` with a read-only `AssuranceFindingPort` and no
  producer; a finding typed by an administrator would be the same shape as a
  declaration, but the Simulate paths already produce the studio's evidence and no
  ruling names a finding as front-door intake. Later, if at all `[I]`.
- **Row 9 beyond shadow and row 10 interventions** are non-goals (§4, roadmap §11.2).
- **The Publish scenario selector** left open by FD-8.2 (§9.5) is a frontend change
  with no reachable console while FD-8.1 holds; not next `[V]`.
- **The Authority decision read** still calls `decision_store.get` where the port
  offers `get_decision` (`studio_v2.py:408-414`) `[G]`; a correction that belongs to
  the step that first hands a decision store, not a seam.

### 13.2 What is not a front-door seam `[V]`

- **The console (FD-8.3).** Unchanged since §12.1: a root prototype, no package, no
  deployment unit, an in-memory audit store. Packaging "does not begin here" (§9.5);
  it needs its own scoping ADR, deployment unit and evidence, then FD-8.4. A body of
  work, not a seam.
- **A durable Decision Authority store.** Unchanged since §12.2: frozen 1.0.0,
  in-memory repositories, no producing deployment; a store handed to P3E would be
  empty. A package decision first.
- **The owner-blocked inputs.** The mirror record is
  `RATIFIED_PENDING_MIRROR_COORDINATES` with `registry_host`, `repository_prefix` and
  `secret_name` all null and provisioning `PENDING_OUTSIDE_REPOSITORY`
  (`docs/audits/ugence_governance_studio_p3e/BASE_IMAGE_MIRROR_DECISION.json`); every
  container gate set halts on it, and no repository change may fill those fields. The
  Langflow importer is ruled entered and blocked on a genuine secret-free export fixture
  (LI-5, roadmap §11.3). Real approver identity waits on an enterprise issuer (AI-E).
  None of the three is repository work; each unblocks work that is.

### 13.3 The one remaining seam: typed data-use declarations `[V]`

What it would amend, in the seam-5 shape: `data-use-admission` 0.2.0 adds one sqlite
implementation of `DataUseDeclarationPort` plus a single append, `declare`, under the
runtime volume (no server, driver or DSN); the studio backend adds a `DeclarationService`
over it with two v2 operations (declare, list-for-tenant), validated by the package's
own refusal reasons and `supersession_refusals`, the tenant the deployment's and never
the caller's; the frontend adds one screen with typed fields and a single Declare
control; P3E adds one configuration value naming the file, requires
`UGENCE_STUDIO_TENANT_ID`, records the seam, and supersedes the composition record; the
v2 contract is amended once more (v2-A4, two operations). **What it must preserve.**
FD-4 (typed intake, no inference, no repair); the package's own prohibitions (the
record carries no data, only a `data_ref`; the classification, purpose and residency
labels are uninterpreted; nothing is inspected, verified, scored, admitted or
enforced); the `persistent_database` prohibition; tenant binding; SD-2 (declare is
not an authority act and confers nothing); no egress restriction is invented for the
absent egress package; every credential and LIVE prohibition; the frozen v1 bytes,
FROM lines and ratified digests; `REFERENCE_GRADE_SHADOW_ONLY` and
`ENFORCEMENT_ENABLED = False`. `vendor-dependency` is the same shape again and, under
FD-1, its own later seam.

### 13.4 Failure matrix for seam 8 (by construction, on the seam-5 precedent)

| # | Case | Result |
|---|---|---|
| 1 | file path unset | typed gap `data_use_declarations` on both routes `[G]` until built |
| 2 | tenant unset with the path set | refused before bind, as seam 5 `[V]` shape |
| 3 | blank `data_ref` or `purpose_label`, malformed validity | the package's typed refusal, nothing written `[V]` shape |
| 4 | a caller-supplied `tenant_id` | contract refusal (unknown field); the tenant is the deployment's `[V]` shape |
| 5 | inadmissible supersession | `supersession_refusals` as the package states it `[V]` |
| 6 | cross-tenant read, a file bound to another tenant | typed refusal, never an empty answer; refused before bind `[V]` shape |
| 7 | any payload, dataset or record content | not expressible: `data_ref` is an opaque handle and no field carries data `[V]` |
| 8 | a write other than declare | no route: no edit, revocation, admission or enforcement `[V]` shape |
| 9 | restart | records survive on the volume `[V]` shape |
| 10 | egress restrictions | absent; the screen says the egress package does not exist and invents nothing `[G]` |

### 13.5 Recommendation and proposed ruling FD-12 (five decisions, recommended first; ruled in §13.6)

Seam 8 is the only remaining item whose prerequisites are rulings rather than a
package decision, a packaging body of work or an owner input, and it is the last
outline row a studio-alone seam can reach. After it, the front door under FD-1 is at
its ceiling until the owner inputs arrive or the console is packaged.

| # | Decision | Options |
|---|---|---|
| **FD-12.1** | Next seam | **`SCREEN_5_TYPED_DATA_USE_DECLARATIONS`**: seam 8 is a typed declaration form over `data-use-admission`, composed through the P3E root and tenant-bound. `FRONT_DOOR_CEILING_REACHED`: no further studio-alone seam; the remaining work is the owner inputs and the console packaging body of work. `CONSOLE_PACKAGING_BODY_OF_WORK` (FD-8.3; its own ADR first). |
| **FD-12.2** | Durable home | **`LOCAL_SQLITE_UNDER_RUNTIME_VOLUME`**: `data-use-admission` 0.2.0 adds one sqlite implementation of `DataUseDeclarationPort` plus a single append, `declare`, in the seam-5 posture; one configuration value names the file. `COMPOSITION_ROOT_MEMORY`. |
| **FD-12.3** | Declarer | **`DECLARED_BY_PRESENTED_UNPROVEN`**: `declared_by` is a typed opaque handle the form supplies, recorded as presented and unproven, with the deployment's name and version as the recording composition; no identity is claimed until an issuer exists (AI-E). `REQUIRE_IDENTITY`. |
| **FD-12.4** | Contract | **`V2_AMENDMENT_TWO_OPERATIONS`**: `v2_data_use_declare` and `v2_data_use_list`, validated by the package's own refusal reasons and `supersession_refusals`, with `openapi_v2.json` and the generated client re-frozen by amendment v2-A4 in the same step. |
| **FD-12.5** | Mutation boundary | **`DECLARE_IS_THE_ONLY_WRITE`**: the seam writes declarations and nothing else; no edit, revocation, admission, verification, scoring or enforcement; a changed declaration is a new one superseding the old; the record carries no data and confers nothing; egress restrictions are not invented; `vendor-dependency` is a later seam of its own under FD-1. |

Under the recommended options seam 8 ships in its own implementation step: the
package release, the two operations with a re-frozen contract, the screen, the
deployment composition (one declarations file under the runtime volume, tenant-bound),
a superseding composition record, and §13.4 as tests. Owner decisions remaining before
implementation: the five above; none carries an `[R]` beyond the choice itself, since
seam 5 already settled the durable-home and registrant questions for this shape.

### 13.6 Ruling FD-12 (owner, 2026-09-06)

| # | Ruling |
|---|---|
| **FD-12.1** | **`SCREEN_5_TYPED_DATA_USE_DECLARATIONS`.** Seam 8 is a typed declaration form over `data-use-admission`, composed through the P3E root and tenant-bound to `UGENCE_STUDIO_TENANT_ID`. It is the last outline row a studio-alone seam can reach: the console stays a packaging body of work under FD-8.3, a durable Decision Authority store a package decision, and the mirror coordinates, Langflow fixture and enterprise issuer owner inputs. `vendor-dependency` is the same shape again and its own later seam under FD-1. |
| **FD-12.2** | **`LOCAL_SQLITE_UNDER_RUNTIME_VOLUME`.** `data-use-admission` 0.2.0 adds one sqlite implementation of `DataUseDeclarationPort` plus a single append, `declare`, in the seam-5 posture: a file under the writable runtime volume named by one configuration value, no server, no driver, no DSN, the `persistent_database` prohibition standing. The file is bound to the deployment's tenant at first open and never re-bound. |
| **FD-12.3** | **`DECLARED_BY_PRESENTED_UNPROVEN`.** `declared_by` is a typed opaque handle the form supplies, recorded as presented and unproven; the recording composition is this deployment's name and version; no identity is claimed until an enterprise issuer exists (AI-E). |
| **FD-12.4** | **`V2_AMENDMENT_TWO_OPERATIONS`.** `v2_data_use_declare` and `v2_data_use_list`, validated by the package's own refusal reasons and `supersession_refusals`; `openapi_v2.json` and the generated client are re-frozen by amendment v2-A4 in the same step, the fourth amendment since the v2 freeze. |
| **FD-12.5** | **`DECLARE_IS_THE_ONLY_WRITE`.** The seam writes declarations and nothing else: no edit, revocation, admission, verification, scoring or enforcement has a route. A changed declaration is a new one superseding the old; the record carries no data, only an opaque `data_ref`, and its classification, purpose and residency labels stay uninterpreted; the record confers no approval, admission, authority or permission. Egress restrictions are not invented for the absent egress package. SD-2 and every credential and LIVE prohibition are unchanged. |

**What the ruling authorizes.** Documentation only. No seam is activated, no route
exists, no package is released, no contract byte moves and no code changes. Seam 8
activates by its own implementation prompt, which will ship in one step: the
`data-use-admission` 0.2.0 release with its sqlite store and tests, the studio
backend's declaration service and the two v2 operations with amendment v2-A4 and the
regenerated client, the frontend manifest and the declaration screen, the P3E
composition (one configuration value, one file under the runtime volume, tenant-bound)
with a superseding composition record, and the failure matrix of §13.4 as tests. FD-1,
FD-3, FD-4, FD-8.1, FD-8.3, SD-2, the `persistent_database` prohibition, the
`REFERENCE_GRADE_SHADOW_ONLY` ceiling, `ENFORCEMENT_ENABLED = False`, the frozen v1
contract, every FROM line and ratified digest, and every credential, egress and LIVE
prohibition are preserved.

## 14 — Remaining front-door audit under FD-1 (2026-09-06, after seam 8)

**The question.** With seams 1, 2, 3, 5, 6, 7 and 8 shipped and seam 4 absent by
ruling, is the front door at its ceiling? **No. One studio-alone seam remains:
`vendor-dependency`, the second element of outline row 5, in the same shape seam 8
just proved.** FD-12.1 said so in terms — "`vendor-dependency` is the same shape again
and its own later seam under FD-1" — and §7's earlier claim that no further seam
remained overstated it. That sentence is corrected in §7; this section is the audit
behind the correction. Everything else remains a package decision, a separately
scoped body of work, an owner input, or a non-goal.

### 14.1 The correction `[V]`

Seam 8 closed the last outline **row** a studio-alone seam can reach, not the row
itself. Row 5, "data and tool connections", has three elements: data-use declarations
(seam 8, shipped), vendor and tool dependencies (`vendor-dependency`, open), and
egress restrictions (no package, §3) `[G]`. Reading "last row" as "last seam" is the
error; the ruling's own final sentence contradicts it.

### 14.2 Seam 9: `vendor-dependency`, and why it is enterable `[V]`

`vendor-dependency` 0.1.0 stands exactly where `data-use-admission` 0.1.0 stood before
FD-12: `MATURITY = "CONTRACTS_ONLY"` (`version.py:16`), one typed record, a
deterministic `declaration_id_for`, `supersession_refusals`, and one read-only
`VendorDependencyPort` whose docstring states "**No implementation ships in 0.1.0**"
(`selectors.py:135-144`). Its five reads mirror the data-use port's, `vendor_ref` and
`risk_posture_label` standing where `data_ref` and `classification_label` stand. Seam
8 is therefore not merely a precedent but a template: the same durable-home posture,
the same one-write boundary, the same presented-unproven declarer, the same two-
operation amendment, the same P3E configuration value.

### 14.3 What remains, by kind `[V]`

| Item | Kind | State |
|---|---|---|
| `vendor-dependency` declarations (row 5) | **seam a ruling can open** | enterable now; needs FD-13 |
| Result egress (row 5) | seam not yet declared | its ADR is discharged; DE-1's deferred seam has no document `[G]` |
| Console in the profile (seam 4) | packaging body of work | FD-8.1 holds until FD-8.3 completes |
| Durable Decision Authority store | package decision | no producer; store empty by construction |
| Mirror coordinates | owner input | `registry_host`, `repository_prefix`, `secret_name` all `null`; `PENDING_OUTSIDE_REPOSITORY` |
| Langflow export fixture | owner input | a genuine secret-free export is required as evidence before implementation |
| Enterprise issuer (AI-E) | owner input | no issuer exists; every declarer stays `PRESENTED_UNPROVEN` |
| Rows 4, 7-evidence, 9-beyond-shadow, 10 | non-goal or not-yet | research-only packages, no producer, or ruled out |
| `decision_store.get` vs `get_decision` | defect, not a seam | `studio_v2.py:430` calls `.get`; the repository offers `get_decision` `[G]` |

The last row is unchanged since §13.1 recorded it and still belongs to the step that
first hands a decision store, not to a seam.

### 14.4 Failure matrix for seam 9 (by construction, on the seam-8 precedent)

Identical in shape to §13.4, with `vendor_ref` for `data_ref` and `risk_posture_label`
for `classification_label`: an unset path is the typed gap `vendor_declarations`; a
tenant unset with the path set is refused before bind; blank `vendor_ref` or malformed
validity is the package's typed refusal; a caller-supplied `tenant_id` is a contract
refusal; an inadmissible supersession is `supersession_refusals` as the package states
it; a cross-tenant read is a typed refusal, never an empty answer; a vendor's contract
terms, pricing or contact data are not expressible, because no field carries them; no
write but `declare` has a route; records survive restart; and no vendor approval,
onboarding status or risk verdict is invented, because no package computes one `[G]`.

### 14.5 Recommendation and proposed ruling FD-13 (four decisions, recommended first; ruled in §14.6)

Seam 9 is the only remaining item whose prerequisite is a ruling rather than an owner
input, a packaging body of work or a package decision. Because seam 8 settled the
durable-home, declarer and mutation-boundary questions for this exact shape, the
decisions left are fewer than FD-12's.

| # | Decision | Options |
|---|---|---|
| **FD-13.1** | Next seam | **`SCREEN_5_TYPED_VENDOR_DECLARATIONS`**: seam 9 is a typed vendor-dependency form in the seam-8 shape, completing row 5 but for egress. `FRONT_DOOR_CEILING_REACHED`: decline the seam and treat row 5 as done. |
| **FD-13.2** | Durable home | **`LOCAL_SQLITE_UNDER_RUNTIME_VOLUME`**: `vendor-dependency` 0.2.0 adds one sqlite `VendorDependencyPort` implementation plus a single `declare`, tenant-bound, named by one configuration value — the seam-8 posture unchanged. `COMPOSITION_ROOT_MEMORY`. |
| **FD-13.3** | Contract | **`V2_AMENDMENT_TWO_OPERATIONS`**: `v2_vendor_declare` and `v2_vendor_list`, re-frozen as amendment v2-A5 with the regenerated client in the same step. |
| **FD-13.4** | Risk posture | **`RISK_POSTURE_UNINTERPRETED`**: `risk_posture_label` is recorded exactly as typed and ordered, compared, scored and evaluated nowhere; the screen says so, and no vendor approval or onboarding status is invented. `RATIFY_A_VOCABULARY`: an owner-fixed posture taxonomy (none exists). |

Under the recommended options seam 9 ships in one step on the seam-8 template: the
`vendor-dependency` 0.2.0 release with its store and tests, the studio backend's
service and two operations with amendment v2-A5 and the regenerated client, the
screen, the P3E composition with a superseding composition record, and §14.4 as tests.
Owner decisions remaining before implementation: the four above. If FD-13.1 is
declined, the front door is at its ceiling and the correction in §7 should say so.

**What this section authorizes.** Documentation only. No seam is activated, no route
exists, no package is released, no contract byte moves and no code changes.

### 14.6 Ruling FD-13 (owner, 2026-09-06)

| # | Ruling |
|---|---|
| **FD-13.1** | **`SCREEN_5_TYPED_VENDOR_DECLARATIONS`.** Seam 9 is a typed vendor-dependency form over `vendor-dependency`, composed through the P3E root and tenant-bound to `UGENCE_STUDIO_TENANT_ID`, in the shape seam 8 proved. It completes outline row 5 but for egress restrictions, which have a ratified ADR and no package and stay a gap until one exists. With seam 9 shipped the front door under FD-1 reaches its ceiling: the console stays a packaging body of work under FD-8.3, a durable Decision Authority store a package decision, and the mirror coordinates, Langflow fixture and enterprise issuer owner inputs. |
| **FD-13.2** | **`LOCAL_SQLITE_UNDER_RUNTIME_VOLUME`.** `vendor-dependency` 0.2.0 adds one sqlite implementation of `VendorDependencyPort` plus a single append, `declare`, in the seam-5 and seam-8 posture: a file under the writable runtime volume named by one configuration value, no server, no driver, no DSN, the `persistent_database` prohibition standing. The file is bound to the deployment's tenant at first open and never re-bound; a read or write naming another tenant is a typed refusal, never an empty answer. `declared_by` is a typed opaque handle recorded as presented and unproven, the recording composition this deployment's name and version, exactly as FD-12.3 ruled for seam 8; no identity is claimed until an enterprise issuer exists (AI-E). |
| **FD-13.3** | **`V2_AMENDMENT_TWO_OPERATIONS`.** `v2_vendor_declare` and `v2_vendor_list`, validated by the package's own refusal reasons and `supersession_refusals`; `openapi_v2.json` and the generated client are re-frozen by amendment v2-A5 in the same step, the fifth since the v2 freeze. |
| **FD-13.4** | **`RISK_POSTURE_UNINTERPRETED`.** `risk_posture_label` is what the declarer called the vendor's posture and nothing more: recorded stripped and verbatim, and ordered, compared, scored, ranked and evaluated nowhere. No vendor approval, onboarding status, tier, certification or risk verdict is invented or displayed, because no package in this repository computes one. `declare` is the only write — no edit, revocation, admission, verification, scoring, approval or enforcement has a route — a changed declaration is a new one superseding the old, and the record confers no approval, admission, authority or permission. The record carries an opaque `vendor_ref` and never a vendor's contract terms, pricing or contact data, because no field could hold them. SD-2 and every credential and LIVE prohibition are unchanged. |

**What the ruling authorizes.** Documentation only. No seam is activated, no route
exists, no package is released, no contract byte moves and no code changes. Seam 9
activates by its own implementation prompt, which will ship in one step: the
`vendor-dependency` 0.2.0 release with its sqlite store and tests, the studio
backend's declaration service and the two v2 operations with amendment v2-A5 and the
regenerated client, the frontend manifest and the vendor screen, the P3E composition
(one configuration value, one file under the runtime volume, tenant-bound) with a
superseding composition record, and the failure matrix of §14.4 as tests. FD-1, FD-3,
FD-4, FD-8.1, FD-8.3, FD-12, SD-2, the `persistent_database` prohibition, the
`REFERENCE_GRADE_SHADOW_ONLY` ceiling, `ENFORCEMENT_ENABLED = False`, the frozen v1
contract, every FROM line and ratified digest, and every credential, egress and LIVE
prohibition are preserved.

## 15 — Closing audit: the front door at its ceiling (2026-09-06, after seam 9)

**The question.** With seams 1, 2, 3, 5, 6, 7, 8 and 9 shipped and seam 4 absent by
ruling, is the ceiling FD-13.1 named reached, and what would have to change for any
further seam to open? **It is reached, and no ruling is needed to close it.** Every
remaining item is blocked on something no ruling can supply: a package that does not
exist, a body of work not yet begun, a producer that does not exist, or an input only
the owner holds. This section records that state and proposes nothing.

### 15.1 What the composed profile is, verified `[V]`

`deployment/governance-studio/approved-runtime-config.json` at
`governance-studio-deployment` 0.10.0 hands `build_studio_context` eight seams —
`review_service_base_url`, `activation_root`, `policy_registry`, `policy_identities`,
`provider_registry`, `system_registry`, `data_use_declarations`,
`vendor_declarations` — behind eight configuration values, with fifteen first-party
packages in the image. Three dependencies stay absent by ruling: `decision_store`,
`governance_hook` (FD-7.3's fail-closed default stands) and `console_base_url`
(FD-8.1). `data_classification` is `SYNTHETIC_DEMONSTRATION_ONLY` and the composition
record's `classification_label` is `REFERENCE_GRADE_SHADOW_ONLY`.

The v2 contract has been amended five times since its freeze, and the chain verifies
end to end: v2-A1 (registry), v2-A2 (start relay), v2-A3 (ledger read), v2-A4
(data-use), v2-A5 (vendor), each `previous_sha256` matching its predecessor's
`sha256`, and the committed `openapi_v2.json` bytes matching the latest. The frozen v1
contract is `dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656`,
unchanged since GAS-4. The composition-record chain runs unbroken from seam 1 to seam
9, each prior record kept byte-for-byte and still reconstructing.

The three seam packages that gained a durable home — `ai-system-registry`,
`data-use-admission`, `vendor-dependency` — are all 0.2.0,
`CONTRACTS_PLUS_LOCAL_STORE`, `ENFORCEMENT_ENABLED = False`. `control-plane-root` is
0.2.0 and `REFERENCE_GRADE`.

### 15.2 What remains, and the one input that unblocks each `[V]`

| Item | Kind | The one input | Who supplies it |
|---|---|---|---|
| Result egress (row 5's third element) | seam not yet declared | a document declaring where model output crosses a boundary worth governing; the named ADR is discharged, not unimplemented (its §7) `[G]` | a body of work, then an owner ratification |
| Console in the profile (seam 4) | packaging body of work | FD-8.3 completion: the root prototype `ugence_console_api/` (not `apps/console/`, which is its separate frontend) becomes a bounded, installable, tested distribution with an authentication boundary and a stated maturity; scoped in `ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md`, which proposes CP-1 to CP-5 | a body of work, after an owner ruling |
| Durable Decision Authority store | package decision | a producer of decisions; the store would be empty by construction until one exists | a body of work |
| Mirror coordinates | owner input | `registry_host`, `repository_prefix`, `secret_name` — all three `null`, `provisioning.status: PENDING_OUTSIDE_REPOSITORY` | the owner |
| Langflow export fixture | owner input | one genuine secret-free export; only `ADR_UGENCE_LANGFLOW_IMPORT_SCOPING.md` exists, no fixture | the owner |
| Enterprise issuer (AI-E) | owner input | an issuer; until then every declarer across the seams stays `PRESENTED_UNPROVEN` | the owner |

Three of the six are owner decisions in the strict sense — the owner holds the input
and no work in this repository substitutes for it. The other three are bodies of work
whose absence is structural, not a matter of choosing.

### 15.3 The standing defect `[G]`

`studio_v2.py:447` calls `self._decisions.get(decision_id)` where the Decision
Authority repository offers `get_decision`
(`repositories/decision_case_repository.py:43`). Unchanged since §13.1 recorded it. It
is a defect, not a seam, and it belongs to whichever step first hands a real decision
store — which is why no seam has fixed it: no seam hands one.

### 15.4 What would have to change for a further seam to open `[I]`

A front-door seam under FD-1 needs a package with a public surface the studio can type
against and a composition root that can hand it over. Every outline row that had one
now has a screen. A tenth seam therefore requires a *new package* first. Result egress was audited as
the candidate on 2026-09-06 and is not one yet: its seam has never been declared, no
producer of model output is reachable (`LIVE` is absent), and `ENFORCEMENT_ENABLED` is
`False` everywhere, so a package written now would answer no question. The prerequisite
is a document declaring the seam, then a scoping ADR of its own — a body of work and an
owner ratification, not a ruling this document can make. Until such a package exists, or the
console is packaged under FD-8.3, or an owner input arrives, there is nothing for a
ruling to decide.

**No ruling is proposed.** The ceiling FD-13.1 named is reached, and this section
closes the front-door sequence rather than opening another.
