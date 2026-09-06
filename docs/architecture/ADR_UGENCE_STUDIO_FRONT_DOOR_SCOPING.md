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
| 5 | Data and tool connections | data permissions, tool scopes, egress restrictions | `data-use-admission` (declared data use), `vendor-dependency`; egress: `ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md` ratified, no package; tool scopes live in the governed-execution restrictions the hook already carries | no screen | `[V]` records, `[G]` egress package and screen |
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
is tests. The next seam (the governed hook in the worker-relay shape, or the console
once FD-8.3 is complete) waits on its own ruling under FD-1.

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
