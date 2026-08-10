# Live Contract Inventory — Code Governance Implementation-Readiness Audit

> **Documentation only.** This inventory records the *actual, live* public contracts in the
> repository at the audited commit. Every field list below was read directly from source at
> the cited `path:line`. No contract, schema, provider, API snapshot, or frozen artifact is
> changed by this document. Authoritative technical source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md`
> (v0.2). Terminology follows
> `docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`.

Audited commit: `3ec11e4ecbc209eabc69d3c0d8a75ecaa10f6def` (default branch tip).

---

## 0. Canonical vs. legacy layout

Real code lives under `packages/`. Top-level directories (`governance_providers/`,
`decision_governance/`, …) are logic-free compatibility shims re-exporting the canonical
packages (object identity preserved). New code imports the canonical public surfaces.

| Capability | Canonical package | Public import |
|---|---|---|
| Neutral provider contracts | `packages/governance-contracts/` | `ugence_governance_contracts` (`.api`) |
| Governance Provider Framework | `packages/governance-provider-framework/` | `ugence_governance_provider_framework.api` |
| Decision Authority | `packages/capabilities/decision-authority/` | `ugence_decision_authority` (`.api`) |
| StoryGraph | `packages/capabilities/storygraph/` | `ugence_storygraph` |
| Model Selection | `packages/capabilities/model-selection/` | `ugence_model_selection` |
| TAP provider (adapter) | `tap_provider/` | `tap_provider` |
| ActionGate provider (adapter) | `actiongate_provider/` | `actiongate_provider` |

---

## 1. Neutral governance contracts (`ugence_governance_contracts`)

Package docstring: a **leaf** package importing only the Python standard library; defines
provider-neutral governance contracts. `__version__ = "0.1.0"`, `CONTRACT_VERSION = "1.0.0"`.
"These are neutral *contracts*, not authority." (`src/ugence_governance_contracts/__init__.py:1`)

### 1.1 `ProviderKind` — the three peer capability families
`src/ugence_governance_contracts/metadata.py:19`

```
ASSERTION_GOVERNANCE = "ASSERTION_GOVERNANCE"   # future: TAP; feeds assessment/recommendation
ACTION_GOVERNANCE    = "ACTION_GOVERNANCE"      # future: ActionGate; adapts onto ActionControlPlanePort
EXTERNAL_EXECUTION   = "EXTERNAL_EXECUTION"     # dispatch/observe an external system
```

"Peers — never conflated." Adding a fourth family is a **MAJOR** change against
`platform/PLATFORM_FREEZE_V1.json` ("new provider families" is listed under MAJOR at
`PLATFORM_FREEZE_V1.json:21`). **Code Governance requires no new `ProviderKind`.**

### 1.2 `ProviderDescriptor` (`metadata.py:60`)
`provider_id: str` · `kind: ProviderKind` · `implementation_version: str` ·
`compatibility: ProviderCompatibility` · `capabilities: ProviderCapabilities` ·
`factory: Callable[[], object]` (zero-arg) · `vendor: str = ""` · `default: bool = False` ·
`metadata: dict[str, str]`. Property `contract_version`.

- `ProviderCapabilities` (`metadata.py:35`): `kind`, `features: frozenset[str]`, `deterministic: bool`.
- `ProviderCompatibility` (`metadata.py:48`): `contract_version`, `compatible_kernel_majors: frozenset[str]={"1"}`, `config_schema_version="1"`.
- `ProviderHealth` (`metadata.py:56`): `state: ProviderLifecycleState`, `healthy: bool`, `detail`.

### 1.3 Lifecycle (`lifecycle.py:16`)
`ProviderLifecycleState`: `REGISTERED → INITIALIZING → AVAILABLE ↔ DEGRADED → UNAVAILABLE →
STOPPING → STOPPED`. Deterministic transition table (`_ALLOWED`, `lifecycle.py:29`); no
background threads. This is **provider availability**, distinct from any business-record lifecycle.

### 1.4 Error taxonomy (`errors.py`)
`FailureClass` = `RETRYABLE · TERMINAL · INDETERMINATE · CONFIGURATION · COMPATIBILITY`.
`ProviderError` (base, `TERMINAL`) plus registration/resolution/compatibility/configuration/
unavailable(`RETRYABLE`)/timeout(`RETRYABLE`)/protocol/result-validation subclasses. Vendor
exceptions must be normalized at the adapter boundary and never leak into services.

### 1.5 `ASSERTION_GOVERNANCE` contract (`contracts/assertion.py`) — implemented by TAP
- `AssertionGovernanceRequest` (`:26`): `assertion: str` · `assertion_type: str=""` ·
  **`evidence_refs: tuple[str, ...]=()`** · `source_identity: str=""` · `policy_refs: tuple[str,...]=()` ·
  `context: Mapping[str,str]` · `correlation_id: str=""`.
- `AssertionGovernanceResult` (`:41`): `coverage: AssertionCoverage` · `evidence_coverage: float` ·
  `covered_evidence_refs: tuple[str,...]` · `unsupported_elements` · `omitted_qualifiers` ·
  `constraints` · `obligations` · `explanation_refs` · `provider_trace_id: str` · `fingerprint: str`.
- `AssertionCoverage` (`:19`): `SUPPORTED · UNSUPPORTED · INDETERMINATE · CONSTRAINED`.
- Protocol: `AssertionGovernanceProvider.evaluate(request) -> result` (`:62`).
- **Note:** evidence is passed as **string reference tuples**, not payloads. There is *no*
  `evidence` payload field. Large artifacts stay outside the governance request.

### 1.6 `ACTION_GOVERNANCE` contract (`contracts/action.py`) — implemented by ActionGate
- `ActionGovernanceRequest` (`:29`): `action_type: str` · **`requested_parameters: Mapping[str,str]`** ·
  `actor: str=""` · `authority_context: str=""` · `target_resource: str=""` ·
  `policy_refs: tuple[str,...]` · `risk_context: Mapping[str,str]` · `evidence_refs: tuple[str,...]` ·
  `decision_refs: tuple[str,...]` · `idempotency_key: str=""` · `correlation_id: str=""` ·
  `authorization_expired: bool=False`.
- `ActionGovernanceResult` (`:47`): `outcome: ActionGovernanceOutcome` · `constraints: tuple[str,...]` ·
  `obligations: tuple[str,...]` · `expiry: Optional[datetime]` · `authority_basis: str` ·
  `reason_codes: tuple[str,...]` · `provider_trace_id: str` · `fingerprint: str`.
- `ActionGovernanceOutcome` (`:22`): `AUTHORIZED · AUTHORIZED_WITH_CONSTRAINTS · DENIED · INDETERMINATE · EXPIRED`.
- Protocol: `ActionGovernanceProvider.authorize(request) -> result` (`:60`).
- **Confirmed:** `ActionGovernanceResult` emits **no standalone `ExactChangeAuthorization`**.
  It carries `outcome/constraints/obligations/expiry/authority_basis/reason_codes/fingerprint`.
  `requested_parameters` is a `Mapping[str,str]` — it *can* carry key→value pairs (e.g. exact SHAs).
  `decision_refs`, `evidence_refs`, `idempotency_key`, `correlation_id` provide governance-ref binding.

### 1.7 `EXTERNAL_EXECUTION` contract (`contracts/execution.py`) — implemented by GitHub Execution Provider (new)
- `ExecutionDispatchRequest` (`:31`): `action_type: str` · **`parameters: Mapping[str,str]`** ·
  `idempotency_key: str=""` · `correlation_id: str=""`. **No governance-reference fields.**
- `ExecutionDispatchResult` (`:39`): `accepted: bool` · `external_request_id` · `acknowledgement` ·
  `pending` · `timed_out` · `transport_error` · `retryable`. "A *transport* result — never a business outcome."
- `ExecutionObservation` (`:54`): `business_outcome: ExecutionBusinessOutcome` ·
  `observed_parameters: Mapping[str,str]` · `final: bool` · `reason` · `provider_trace_id` · `fingerprint`.
- `ExecutionBusinessOutcome` (`:22`): `SUCCEEDED · FAILED · REJECTED · PENDING · DUPLICATE · UNKNOWN`.
- Protocol: `ExternalExecutionProvider.dispatch / observe / cancel` (`:66`).
- **Confirmed (design §4.7):** the neutral dispatch request does **not inherently** carry a
  DecisionRecord ref, CER hash, ActionGate result, or ACP clearance. Governance binding must be
  provided *above* the neutral contract (product envelope / `parameters` map / DA `ExecutionIntent`).

---

## 2. Governance Provider Framework (`ugence_governance_provider_framework`)

Owns registration, resolution, adaptation, conformance, observability. **Owns no authority and
no policy.** Adapters normalize vendor errors and adapt neutral providers onto the frozen kernel
ports. Source tree: `registry/`, `resolution.py`, `adapters/` (`assertion_integration.py`,
`action_to_control_plane.py`, `execution_to_external_system.py`, `_kernel.py`), `conformance/`,
`reference/`, `configuration.py`, `fingerprint.py`, `observability.py`, `version.py`.
Detailed surface in `PROVIDER_ROLE_MATRIX.md`.

---

## 3. Decision Authority (`ugence_decision_authority`, frozen kernel)

Every record subclasses `DomainModel` with `model_config = ConfigDict(frozen=True, extra="forbid")`
(`base.py:19`) — **immutable and closed to unknown fields. No open metadata/extension dict exists
on any core decision contract.**

### 3.1 `DecisionRecord` — the binding decision (`decisions/decision.py:25`)
`decision_id` · `decision_case_id` · `tenant_id` · `decision_type` · `outcome: DecisionOutcome` ·
`authority_type: AuthorityType` · `decided_by: str` · `decided_at: datetime` ·
`recommendation_refs: tuple[VersionedRef,...]` · `assessment_refs: tuple[VersionedRef,...]` ·
`policy_refs: tuple[VersionedRef,...]` · `reason_codes: tuple[ReasonCode,...]` ·
`override_record_id: Optional[str]` · `effective_status: EffectiveStatus=EFFECTIVE` ·
`supersedes_decision_id: Optional[str]`.
- **No `content_hash` / `compute_hash()`** — immutability is structural (`frozen=True`) only.
- Validator requires a non-empty `reason_codes`; `AuthorityType` has no AI member (AI cannot decide).
- Authorized actor identity is carried as the bare principal `decided_by` + `authority_type`
  (no embedded `ActorIdentity` object).

### 3.2 `ContextEnvelopeRecord` (CER, `schema_version="cer.v1"`, `actions/cer.py:62`)
`cer_id` · `tenant_id` · `decision_case_id` · `decision_id` · `action_request_id` · `action_type` ·
`target_system` · `subject_context: SubjectContext` · `authority_context: AuthoritySummary` ·
`policy_context: PolicyContext` · `decision_context: DecisionContext` ·
`runtime_constraints: tuple[str,...]` · `data_classifications: tuple[str,...]` ·
**`permitted_parameters: tuple[str,...]`** · **`prohibited_parameters: tuple[str,...]`** ·
**`required_controls: tuple[str,...]`** · `issued_at` · `expires_at: Optional[datetime]` ·
`schema_version="cer.v1"` · **`content_hash: str`** · `correlation_id: str`.
- `content_hash` = SHA-256 (`compute_hash()`, `cer.py:101`) over governance context (tenant, case,
  decision, action_request, action_type, target_system, subjects, authority type+scope, policy_refs
  `id:version`, outcome, override, sorted permitted/prohibited params, required_controls,
  data_classifications, schema_version). Excludes timestamps/correlation.
- `is_expired(at)` (`cer.py:124`). Docstring: "a governance context record, **not** an execution command."
- **Critical structural fact:** `permitted_parameters` / `prohibited_parameters` / `required_controls`
  are `tuple[str,...]` — parameter/control **names**, not key→value data. The CER has **no generic
  metadata/payload dict**; exact merge-artifact *values* (SHAs, merge-tree digest) have no typed home
  in the CER itself. (See `DECISION_AND_CER_MAPPING.md` and `EXACT_MERGE_IDENTITY.md`.)

### 3.3 `ActionRequest` (`actions/action_request.py:24`)
`action_request_id` · `tenant_id` · `decision_case_id` · `decision_case_version: int` · `decision_id` ·
`action_type` · `target_system` · `subject_refs` · **`requested_parameters: dict[str,str]`** ·
`policy_refs: tuple[VersionedRef,...]` · `authority_ref` · `action_mapping_ref: VersionedRef` ·
`cer_id: Optional[str]` · `status: ActionRequestStatus=DRAFT` · `version:int` · `request_version_id` ·
`created_by` · `created_at` · `correlation_id` · `idempotency_key` · `supersedes_action_request_id`.
Methods `parameters_hash()`, `content_key()`, `evolve()`. **`requested_parameters` is a key→value
map that CAN carry the exact merge-artifact values.** Status enum has **no** `EXECUTED/SUCCEEDED`.

### 3.4 `ActionAuthorizationResponse` (DA-internal action authorization, `actions/authorization.py:23`)
`authorization_id` · `action_request_id` · `cer_id` · `outcome: AuthorizationOutcome` · `reason_codes` ·
`constraints` · `obligations` · `authorized_at` · `expires_at` · `control_plane_ref` ·
`policy_versions: tuple[str,...]` · `correlation_id` · `attempt:int`. Produced through
`ActionControlPlanePort.authorize(action_request, cer)` (`actions/control_plane.py:25`), with an
`OfflineDeterministicControlPlane` reference impl (never executes).

### 3.5 `OverrideRecord` (`decisions/override.py:25`)
`override_id` · `decision_case_id` · `tenant_id` · `final_outcome` · `authorized_by` ·
`reason_codes` (required) · `original_recommendation_id?` · `original_proposed_outcome?` ·
`policy_default_outcome?` · `permitting_policy_ref?: VersionedRef` · `notes` · `created_at`.

### 3.6 Identity / authority / supersession
- `ActorIdentity` (`identity/provider.py:16`): `actor_id`, `actor_type: ActorType`, `authenticated: bool`.
  `ActorType` (`identity/actor.py:8`): `AI · HUMAN · SYSTEM`; unknown → `SYSTEM, unauthenticated`.
- `AuthorityType` (`decisions/status.py:76`): `HUMAN_REVIEWER · HUMAN_APPROVER · DELEGATED_POLICY ·
  COMMITTEE · EXTERNAL_AUTHORITY`. No AI member.
- `AuthorityContext` (`decisions/authority.py:23`): includes **`segregation_of_duties: bool=False`**
  and `required_approvals: int=0`, `granting_policy_ref`, `limits`, `effective_from/until`.
- SoD / author≠approver enforced in `services/case_validation_service.py` `validate_authority`
  (`:105`, SoD check `:138`) — **only when `authority.segregation_of_duties` is explicitly True**.
- Supersession: `supersedes_*` id fields + status enums (`EffectiveStatus`, `CaseStatus.SUPERSEDED`,
  etc.); append-only `evolve()` snapshots. **No automatic patch-hash-based invalidation of a live
  decision** (see `RISK_REGISTER.md`). `ReasonCode.STALE_EVIDENCE` exists but nothing computes it.
- **Extensibility:** `policy_refs` are free `VersionedRef` (`decisions/subject.py:30`; `kind` "never
  interpreted") — a product may reference any repository policy id + version **without a contract
  change**. `ReasonCode` is a **closed enum** (`vocabulary.py:20`); adding a code is a contract change.

---

## 4. TAP / ActionGate / StoryGraph / ACP / Execution — summary

Full field-level surfaces and maturity for these are in the companion documents:
- `EVIDENCE_AND_TAP_MAPPING.md` — TAP adapter + evidence subsystem.
- `ACTIONGATE_AND_ACP_MAPPING.md` — ActionGate provider + ACP clearance.
- `EXTERNAL_EXECUTION_MAPPING.md` — execution family + DA execution machinery.
- `MATURITY_MATRIX.md` — maturity classification per component.

Machine-readable form of this inventory: `contract_inventory.json`.
