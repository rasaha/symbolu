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
unchanged). Matrix rows 1 to 6 of §8.2 are tests, rows 4 and 6 no longer gaps. The
next seam (`CONSOLE_BASE_URL`, or the governed hook once ESCALATE has a sink) waits
on its own ruling under FD-1.

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
