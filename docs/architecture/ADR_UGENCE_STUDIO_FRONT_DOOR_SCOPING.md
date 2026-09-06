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
record (`composition-record.seam-1.json`, unchanged). The next seam waits on its own
ruling under FD-1.

The shape every seam follows: the CR-2 shape (one configuration value, one freeze-test amendment, its own failure tests and
maturity statement, one PR), preserving `REFERENCE_GRADE_SHADOW_ONLY`, the frozen
runtime configuration, existing v1 and v2 behaviour, and every credential and LIVE
prohibition. Issued by its own implementation prompt.
