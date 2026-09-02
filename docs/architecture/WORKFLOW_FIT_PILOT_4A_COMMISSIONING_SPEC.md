# Trusted Workflow-Fit Pilot (Phase 4A) — Commissioning Specification and Ballot

**Status:** **RATIFIED — all four §10 ballot items ratified as recommended
by the owner, 2026-09-02, including the four additional revision scopes
(revision 4).** **Nothing here is implemented**; implementation awaits a
separate owner instruction. This document commissions one research-only
pilot package and one gate, and nothing else. It replaces further scoping
notes: the four open decisions it resolves (Workflow-Fit 1 and 4, Advisor 3
and 5) are answered together in §3–§6, because each is unusable without the
others. Revision 2 applied eleven owner corrections; revision 3 applies the
adversarial design review's four blockers, nine major defects and three
minor corrections; revision 4 applies the two follow-up reviews of revision
3 (§11).
**Authority applied:** Workflow-Fit decisions 2, 3, 5 and Advisor decisions 1,
2, 4 as recorded in their notes; the Slice 1 contracts (`4369089d`,
correction 30 at `4324cbdd`); Slice 2 (`8bd6ccf3`); the Phase 3 intake ruling
(`2bffc9cd`) `[V]`.
**Evidence labels:** `[V]` verified against the repository · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Can one research-only pilot produce ratified Workflow-Fit outcomes for one
governed task class, with every observation bound before execution to
exactly what was tested, with telemetry captured outside the tested workflow,
recomputed by the capture boundary and digested into the record before
attestation, with every advisor-qualified method and a declared challenger
set exercised, and with every judgment labelled research-only and
non-authoritative?** Yes, with one preregistered manifest validated against
the full advisory and catalog before any run; one out-of-process capture
boundary with a specified port, record and issuance operation; and three
honest limits stated on every output: preregistration is declared and
locally enforced, not proven; evaluator independence is declared and
unverified; nothing is VERIFIED unless the Trusted Evidence Authority issues
a receipt for it.

---

## 1. Inventory: what exists, what is reused, what is missing

| Piece | Where `[V]` | Reuse | Gap |
|---|---|---|---|
| Execution record `ReasoningMethodExecutionRecord` v1 with `method`, `binding: BindingRef`, `task_class_digest`, `input_digest`, `model_ref`, `telemetry`, `self_reported_quality`, `issuer_identity`, `parent_record_digest`; evidence axes as class constants `OBSERVED / UNATTESTED / UNVERIFIED`; **one record per method per task class** (ballot 5.1-A) | `reasoning-method-governance/contracts/record.py:169-193`; governed adapter `experiments/workflow_fit_study/governed_adapter.py` | as is, at its existing aggregation boundary | carries no manifest, role, advisory or case-set identity |
| `ExecutionTelemetry` (`llm_calls`, `llm_calls_basis: CountBasis`, `token_usage: TokenUsageSnapshot`, `token_usage_availability`, `token_count_basis`, `capture_refs`); `CountBasis` includes `INJECTED_COUNTER` and `PROVIDER_REPORTED` | `record.py:64-121` | as is; populated from the capture boundary (§4) | — |
| `AttestationEnvelope` (attester, `capture_boundary_ref`, `attested_fields`) and `VerificationEnvelope`; `EvidenceStatusView` computed by the engine; self-attestation and self-verification refused; unresolved issuers reported in `ignored_envelopes` | `contracts/envelopes.py`; ballot §4 | as is | **no attester exists**; **no adapter from a TEV receipt to a `VerificationEnvelope`** |
| Comparison engine `compare(request, *, produced_at)`, four `FitOutcome`s, `REQUESTER_ASSERTED` authority resolution, `RESEARCH_ONLY` scope; four-outcome fixtures from PR #1566 | `readiness-comparison/engine.py` (0.2.0); `tests/engine/test_four_outcomes_pr1566.py` | as is; the fixtures become the synthetic engine-coverage fixture (§8, A25) | quality claims have no envelope path |
| `MetricClaim` (`claim_id`, `metric_id`, `value`, `governed_unit`, `source_basis`, `transformation_method`, `evidence_refs`, …) and `QualityResult` (`method`, `claim_ref`, `value`, `aggregation`) | `governance-contracts/contracts/evidence.py:347-369`; `reasoning-method-governance/contracts/assessment.py:47-52` | as is | **no evaluator identity or version field**: a claim cannot bind its evaluator `[G]` |
| `ResearchComparisonPlan` with `baseline`, `recommended` (fenced), `ChallengerSamplingPolicy`, `plan_digest` | `contracts/plan.py`; ballot §8 | as is, embedded by value in the manifest (§3) | no link from a record to the plan; no coverage **report** |
| `AggregationRef`; `ComparisonPolicy.quality_aggregation`; `MetricClaim.transformation_method = CALCULATED` with `calculation_ref` | `contracts/task_class.py`; governed adapter (`RESEARCH_MEAN`) | as the declared quality and resource aggregation references | resource aggregation declared by the adapter only in prose `[G]` |
| `TaskClassIdentity` (…, `benchmark_set_ref`, `benchmark_set_digest`, `ComparisonPolicy`) → `task_class_digest` | `contracts/task_class.py:181-219` | as is | `benchmark_set_digest` names a set but carries no case list |
| `AssessedSystemBinding` (`configuration_id`, `configuration_digest`, `context_digest`, opaque `deployment_environment_ref`) | `governance-contracts/contracts/system_identity.py:260-288` | by `BindingRef` | no lifecycle state |
| `BenchmarkReference` (`benchmark_id`, `version`, `content_digest`, `issuer_ref`); Benchmark Registry canonical identity and lifecycle | `governance-contracts/contracts/evidence.py:318`; `benchmark-registry` | as the head of the benchmark manifest (§3.2) | **a `BenchmarkReference` cannot prove membership: it has no case list** `[G]` |
| Workflow-Fit harness: `TaskCase`, `StudyConfig`, `RunRecord`, `assess`; governed adapter summing `llm_calls` over the same case set per method | `experiments/workflow_fit_study/study.py`, `governed_adapter.py` | as the executor and adapter | `_CountingClient` is **the same process and trust domain** as the workflow (`study.py:141-145`): not a capture boundary |
| `WorkflowResult.total_llm_calls`, `quality_score` | `agentic/agentic_framework/reasoning_workflows.py:145` | retained only as labelled diagnostics (§4) | — |
| Context Minimization `ApiCallTokenRecord` (`logical_request_id`, `attempt_id`, `provider_id`, `AttemptStatus`, `provider_invoked`, token counts, `record_fingerprint`), `TokenCountBasis`, `UsageAvailability` | `context-minimization/token_accounting.py:135-455` | as the **shape** of the capture record (§4.2) | no component records **another workflow's** calls from outside it `[G]` |
| Trusted Evidence Authority: `EvidenceTrustStage` (six stages), trust anchors, `TrustAnchorCapability`, `issue()` → `SignedEvidenceVerificationReceipt` | `trusted-evidence-authority/…/enums.py:27`, `authority/issuance.py:116` | the only verifier port | no anchor capability for reasoning-method telemetry; no receipt→envelope adapter `[G]` |
| Ratified rulings: four outcome names; per-class versioned sufficiency rule; efficiency as a property of the selection policy within the exact binding; advisor as a separate design-time capability; task-class identity coordinates; Phase 3 intake | Workflow-Fit §11.2/§11.3/§11.5; Advisor §8.1/§8.4; demo README | binding | — |

**Genuinely missing (all research-only, all in the new package of §7):** a
preregistered pilot manifest with its pre-execution validation (§3.1), a
benchmark manifest with the case list bound to its head (§3.2), a per-method
pilot observation at Slice 1's aggregation boundary (§3.3), a quality
evaluation record binding the evaluator to the claim (§3.4), an
out-of-process capture boundary with a specified port, capture record,
completeness rule and issuance operation (§4), an evaluator declaration
(§5), a coverage report (§6.1) and a neutral state ledger with one-way,
derived-scope lineage and a pure transition operation (§6.2). No Slice 1 or
Slice 2 contract changes.

---

## 2. Vocabulary carried unchanged

`FitOutcome` (four names), `SourceBasis`, `AttestationStatus`,
`VerificationStatus`, `CountBasis`, `UsageAvailabilityToken`, `SamplingKind`,
`AggregationRef`, `USAGE_SCOPE_RESEARCH_ONLY`, `AUTHORITY_RESOLUTION_BASIS_V1 =
"REQUESTER_ASSERTED"`, `AdvisoryClassification`, `AdvisoryEligibility`,
`RULE_DERIVED`, `COMPARISON_EVIDENCE_ABSENT`. No new label is a synonym of
any of these, and no lifecycle state names an outcome (§6.2). The pilot
package does not depend on Context Minimization, so it defines a pilot-local
`CaptureAttemptStatus` (`SUCCEEDED / FAILED / TIMEOUT / EXCEPTION`) and pins
its members to Context Minimization's `AttemptStatus` under a test-only
import, in the Slice 1 vocabulary-pin pattern.

**Numbers.** This document supplies **no owner-supplied numeric default,
threshold, sample size, coverage target or acceptance figure**. Observed
counts (calls, tokens, cases, methods) and caller-declared research
configuration remain numeric and are carried as validated integers or
decimal strings where the existing contracts already do so.

**Judgments.** A pilot result necessarily contains `FitOutcome` judgments
such as `INSUFFICIENT_QUALITY`. The enforceable requirement is not that no
judgment appears, but that **every judgment is labelled `RESEARCH_ONLY`,
reported or unverified on its evidence axes, and non-authoritative**, and
that no lifecycle state, role name or summary line restates a judgment as
approval, qualification or verdict.

---

## 3. Decision 1 — Usage binding (Workflow-Fit 1)

### 3.1 Preregistered pilot manifest

Everything a pilot will do is fixed and digested in one `PilotStudyManifest`
**and validated against the full advisory and catalog before any run**. No
advisory, role or method can be attached afterwards: an observation is
admissible only if it names a manifest digest the runner already held, and
the manifest carries no field that execution could fill in.

```python
PILOT_MANIFEST_SCHEMA_VERSION = "workflow_fit_pilot.manifest.v1"

class PilotRole(str, Enum):                     # NON-EXCLUSIVE: one method may carry several
    GOVERNED_BASELINE = "GOVERNED_BASELINE"     # method == plan.baseline
    ADVISOR_QUALIFIED = "ADVISOR_QUALIFIED"     # method ∈ advisory.qualifying
    CHALLENGER = "CHALLENGER"                   # admissible catalog method ∉ advisory.qualifying

@dataclass(frozen=True)
class PilotMethodAssignment:
    method: ReasoningMethodRef                  # unique per manifest
    roles: tuple[PilotRole, ...]                # non-empty, sorted by member order, no repeats

# Telemetry fields the boundary MAY attest. llm_calls is always populated and attested;
# token fields only when the provider reported usage for every call (§4.3).
ATTESTABLE_TELEMETRY_FIELDS = (
    "telemetry.llm_calls",
    "telemetry.token_usage.input_tokens",
    "telemetry.token_usage.output_tokens",
    "telemetry.token_usage.total_tokens",
)

@dataclass(frozen=True)
class CaptureBoundaryDeclaration:
    boundary_identity: str                      # the attester; must differ from record issuer and requester
    boundary_version: str
    process_separation_ref: str                 # how the boundary runs outside the workflow's process (declared, unverified in 4A)
    port_ref: str                               # the local IPC endpoint the workflow's client is bound to (§4.1)
    allowed_attested_fields: tuple[str, ...]    # ⊆ ATTESTABLE_TELEMETRY_FIELDS; must include telemetry.llm_calls

class PreregistrationStatus(str, Enum):
    DECLARED_UNVERIFIED = "DECLARED_UNVERIFIED" # the only value in 4A: timestamps are caller-supplied and can be backdated

@dataclass(frozen=True)
class PilotStudyManifest:
    schema_version: Literal["workflow_fit_pilot.manifest.v1"]
    manifest_id: str
    plan: ResearchComparisonPlan                # by value; plan_digest is therefore inside manifest_digest
    advisory_digest: Optional[str]              # required iff any assignment carries ADVISOR_QUALIFIED; None otherwise
    rule_set: Optional[RuleSetRef]              # the advisory's rule set, same rule
    methods: tuple[PilotMethodAssignment, ...]  # DEDUPLICATED by (method_id, method_version); ordered by sort key
    benchmark: BenchmarkManifest                # §3.2, by value
    capture_boundary: CaptureBoundaryDeclaration
    evaluator: QualityEvaluatorDeclaration      # §5
    resource_aggregation: AggregationRef        # how per-case resource counts become the record's telemetry (the sum over the case set)
    quality_aggregation: AggregationRef         # == plan.task_class.comparison_policy.quality_aggregation when that policy declares one
    preregistration_status: PreregistrationStatus
    usage_scope: Literal["RESEARCH_ONLY"]
    preregistered_by: str
    preregistered_at: datetime
    manifest_digest: str
```

**Constructor obligations (shape only).** Exactly one assignment carries
`GOVERNED_BASELINE` and its method equals `plan.baseline`
(`ROLE_INCONSISTENT`); any `ADVISOR_QUALIFIED` role **requires**
`advisory_digest` and `rule_set` (`ADVISORY_REQUIRED`), while a manifest may
carry `advisory_digest` with **no** such role, which is exactly the
empty-qualifying-set case and is checked by `validate_manifest`; `rule_set`
is present iff `advisory_digest` is; no method appears twice (`METHOD_DUPLICATE`); every
`plan.recommended` member is assigned; `benchmark.benchmark_manifest_digest ==
plan.task_class.benchmark_set_digest` (`BENCHMARK_MANIFEST_MISMATCH`);
`quality_aggregation` equals the task class's declared aggregation when one
is declared (`AGGREGATION_MISMATCH`); `capture_boundary.allowed_attested_fields
⊆ ATTESTABLE_TELEMETRY_FIELDS` and includes `telemetry.llm_calls`
(`ATTESTED_FIELDS_INVALID`); `preregistration_status` and `usage_scope` are
the constants.

**Pre-execution validation, `validate_manifest(manifest, *, catalog,
rule_set, advisory=None) -> ValidatedManifest`**, runs before the runner
accepts the manifest and again by any consumer. It receives the **full
catalog**, the **full `RuleSet`** whose admissibility predicate defines the
admissible set (always, whether or not advice is used), and the **full
advisory** whenever `advisory_digest` is set. It refuses:

| Check | Refusal |
|---|---|
| `catalog.ref() ≠ plan.catalog`; or `rule_set.ref() ≠ manifest.rule_set` when set | `CATALOG_MISMATCH` / `RULE_SET_MISMATCH` |
| `advisory` omitted while `advisory_digest` is set, or supplied with a different digest, rule set, catalog ref or `task_class_digest` than the manifest's and plan's | `ADVISORY_REQUIRED` / `ADVISORY_MISMATCH` |
| the set of methods carrying `ADVISOR_QUALIFIED` ≠ the advisory's **complete** `qualifying` set (both may be empty); or `plan.recommended` ≠ that set | `ADVISORY_MISMATCH` |
| under exhaustive composition (6.1-A), the set of assigned methods ≠ the catalog's admissible set under `rule_set.admissibility`; or a `CHALLENGER` role on a qualified method; or an admissible non-qualified method without `CHALLENGER` | `COMPOSITION_INCOMPLETE` |
| any assigned method absent from the catalog | `METHOD_NOT_IN_CATALOG` |

On success it returns a `ValidatedManifest` — a frozen record of
`manifest_digest`, `catalog_digest`, `rule_set_digest`, `advisory_digest`
(or `None`), the validated admissible method set, the validating package
version and a digest of its own — which `validate_observation` requires as
an input, so no observation can be validated against a manifest that was
never validated.

**Role deduplication.** Roles are non-exclusive: a baseline that the advisory
did not qualify carries `GOVERNED_BASELINE` and `CHALLENGER`; a qualified
baseline carries `GOVERNED_BASELINE` and `ADVISOR_QUALIFIED`. Each method is
run once and its one record serves every role it carries; coverage (§6.1)
counts methods per role, never runs.

**Preregistration is declared, not proven.** Comparing caller-supplied
timestamps cannot establish that the manifest existed before execution. In
4A the manifest's `preregistration_status` is the constant
`DECLARED_UNVERIFIED`, and chronology is **locally process-enforced**: the
pilot runner refuses to start any run without a validated manifest digest in
hand and stamps that digest on every capture record it emits (§4.2). The
report prints the status beside the manifest digest.

### 3.2 Benchmark manifest

```python
BENCHMARK_MANIFEST_SCHEMA_VERSION = "workflow_fit_pilot.benchmark_manifest.v1"

@dataclass(frozen=True)
class BenchmarkManifest:
    schema_version: Literal["workflow_fit_pilot.benchmark_manifest.v1"]
    benchmark: BenchmarkReference               # existing head: benchmark_id, version, content_digest, issuer_ref
    case_digests: tuple[str, ...]               # COMPLETE, ascending by code point, unique, NON-EMPTY; one sha-256 per case
    case_count: int                             # == len(case_digests); validated POSITIVE integer
    issuer_identity: str
    issued_at: datetime
    benchmark_manifest_digest: str
```

**Head bound to membership.** `benchmark.content_digest` is defined as the
JCS digest of the ordered `case_digests` tuple (the benchmark's canonical
content is exactly its case set); the constructor recomputes it and refuses a
mismatch (`BENCHMARK_HEAD_MISMATCH`). `benchmark_manifest_digest` covers the
head and the list, so the task class's `benchmark_set_digest` names both.
A `BenchmarkReference` alone still proves nothing about membership;
validation always receives the manifest. Registry registration of the
reference is a later step `[G]`.

### 3.3 Pilot observation, at Slice 1's aggregation boundary

Slice 1 admits **one execution record per method per task class** (ballot
5.1-A), whose telemetry is the declared resource aggregation over the same
case set for every method `[V]`. A `PilotObservation` therefore describes one
method's aggregated record, never one case or one workflow invocation.

```python
PILOT_OBSERVATION_SCHEMA_VERSION = "workflow_fit_pilot.observation.v1"

@dataclass(frozen=True)
class WorkflowReportedDiagnostics:              # runtime-reported values, retained for diagnosis only; never evidence
    total_llm_calls_reported: Optional[int]     # sum of WorkflowResult.total_llm_calls over the case set
    harness_observed_calls: Optional[int]       # the in-process _CountingClient sum
    label: Literal["RUNTIME_REPORTED_DIAGNOSTIC"]

@dataclass(frozen=True)
class PilotObservation:
    schema_version: Literal["workflow_fit_pilot.observation.v1"]
    observation_id: str
    manifest_digest: str                        # the preregistered PilotStudyManifest
    method: ReasoningMethodRef                  # == record.method; one assignment in the manifest
    roles: tuple[PilotRole, ...]                # == the manifest assignment's roles
    task_class_digest: str                      # == manifest.plan.task_class.task_class_digest
    binding: BindingRef                         # == manifest.plan.binding
    model_ref: str                              # == record.model_ref
    case_set_digest: str                        # == manifest.benchmark.benchmark_manifest_digest
    case_count: int                             # == manifest.benchmark.case_count
    resource_aggregation: AggregationRef        # == manifest.resource_aggregation
    quality_aggregation: AggregationRef         # == manifest.quality_aggregation
    record_digest: str                          # the aggregated ReasoningMethodExecutionRecord for this method
    attestation_envelope_digest: Optional[str]  # the capture boundary's envelope over record_digest, when issued
    quality_evaluation_digest: str              # the QualityEvaluationRecord (§3.4) for this record
    diagnostics: WorkflowReportedDiagnostics
    observed_at: datetime
    observation_digest: str
```

### 3.4 Quality evaluation record and the validation operation

`MetricClaim` carries no evaluator identity `[V]`, so the pilot binds the
evaluator to the claim with a pilot-local record that the observation
references.

```python
QUALITY_EVALUATION_SCHEMA_VERSION = "workflow_fit_pilot.quality_evaluation.v1"

@dataclass(frozen=True)
class QualityEvaluationRecord:
    schema_version: Literal["workflow_fit_pilot.quality_evaluation.v1"]
    evaluation_id: str
    manifest_digest: str
    method: ReasoningMethodRef
    record_digest: str                          # the execution record scored
    case_set_digest: str                        # == manifest.benchmark.benchmark_manifest_digest
    evaluator_declaration_digest: str           # == manifest.evaluator.declaration_digest
    scoring_instruction_digest: str             # == manifest.evaluator.scoring_instruction_digest
    quality_aggregation: AggregationRef         # == manifest.quality_aggregation
    claim_digest: str                           # JCS digest of the MetricClaim's fields (MetricClaim has no self-digest; the pilot canonicalizes it with its package-local canonicalizer)
    quality_result_digest: str                  # JCS digest of the QualityResult carrying that claim_ref and aggregation
    independence_status: Literal["DECLARED_UNVERIFIED"]
    evaluated_by: str                           # == manifest.evaluator.evaluator_identity
    evaluated_at: datetime
    evaluation_digest: str
```

**`validate_observation(observation, *, validated, manifest, plan, record,
benchmark, evaluation, quality_claim, quality_result, advisory=None,
attestation=None)`** receives every object needed to verify the
observation's claims and refuses any missing or mismatched one. `validated`
is the `ValidatedManifest` returned by `validate_manifest` (§3.1); the
prerequisite is therefore an input, not a presupposition. It never infers
membership, roles or advice from digests alone.

| Check | Refusal |
|---|---|
| `validated.manifest_digest == manifest.manifest_digest == observation.manifest_digest`; `validated.advisory_digest == manifest.advisory_digest`; `manifest.plan == plan` | `MANIFEST_MISMATCH` / `MANIFEST_NOT_VALIDATED` |
| `record.record_digest == observation.record_digest`; `record.method == observation.method`; `record.task_class_digest`, `record.binding`, `record.model_ref` equal the observation's and the plan's | `RECORD_MISMATCH` |
| `benchmark.benchmark_manifest_digest == observation.case_set_digest == plan.task_class.benchmark_set_digest`; `benchmark.case_count == observation.case_count` | `BENCHMARK_MANIFEST_MISMATCH` |
| `evaluation.evaluation_digest == observation.quality_evaluation_digest`; its `manifest_digest`, `record_digest`, `case_set_digest`, `evaluator_declaration_digest`, `scoring_instruction_digest`, `quality_aggregation` and `evaluated_by` equal the manifest's and the observation's; the JCS digest of `quality_claim` `== evaluation.claim_digest`; the claim's `evidence_refs` name `evaluation.evaluation_id`; its `transformation_method == CALCULATED` | `QUALITY_EVALUATION_MISMATCH` |
| the JCS digest of `quality_result` `== evaluation.quality_result_digest`; `quality_result.method == observation.method`; `quality_result.claim_ref == quality_claim.claim_id`; `quality_result.value == quality_claim.value`; `quality_result.aggregation == manifest.quality_aggregation` | `QUALITY_RESULT_MISMATCH` |
| observation roles equal the manifest assignment's roles for this method | `ROLE_INCONSISTENT` |
| any role is `ADVISOR_QUALIFIED` ⇒ `advisory` supplied with `manifest.advisory_digest` and this method ∈ `advisory.qualifying` | `ADVISORY_REQUIRED` / `ADVISORY_MISMATCH` |
| `observation.attestation_envelope_digest` set ⇒ `attestation` supplied, its digest equal, its `record_digest == record.record_digest`, its `attester_identity == manifest.capture_boundary.boundary_identity`, its `attested_fields` a non-empty subset of `manifest.capture_boundary.allowed_attested_fields` containing `telemetry.llm_calls`, and its `capture_boundary_ref` equal to the JCS digest of `record.telemetry.capture_refs[1:]` (the ordered capture fingerprints, §4.2) | `ATTESTATION_MISMATCH` |
| the manifest digest stamped on the record's `capture_refs` (§4.2) equals `observation.manifest_digest`; `record.captured_at` and `observation.observed_at` are not earlier than `manifest.preregistered_at` (a local chronology check, not proof) | `MANIFEST_NOT_PRIOR` |

**3.1 (resolved by ratification, recommendation adopted) — where the binding lives.**

| Option | Consequence |
|---|---|
| A. Add manifest, roles and advisory fields to `ReasoningMethodExecutionRecord` | one object, but a Slice 1 schema change and the record would carry advisor output across the ratified execution-record boundary |
| B. Manifest plus separate observation and evaluation records referencing the execution record by digest (above) | no Slice 1 change; the record stays neutral; validation needs every object, which §3.1 and §3.4 require anyway |

**Recommendation: B.**

---

## 4. Decision 2 — Trust controls (Workflow-Fit 4)

### 4.1 The capture boundary: port, process and provider factory

The pilot introduces one component, the **capture boundary**, declared in
the manifest and running in **a separate operating-system process** from the
workflow under test. Its contract is a port and a frame protocol, not a
network client:

```python
class ProviderGatewayPort(Protocol):            # implemented by the boundary process; the ONLY client the workflow is given
    def call(self, request: GatewayRequest) -> GatewayResponse: ...

@dataclass(frozen=True)
class GatewayRequest:                           # one frame per model call, written by the workflow-side stub
    manifest_digest: str                        # stamped by the runner; the boundary refuses a request without the digest it was started with
    method_id: str
    method_version: str
    run_id: str                                 # the execution's invocation_id
    case_digest: str                            # member of the benchmark manifest
    sequence: int                               # per (run_id, case_digest), starting at 1, contiguous
    prompt: str                                 # the prompt TEXT: the provider needs it; only its digest ever enters a record

@dataclass(frozen=True)
class GatewayResponse:
    sequence: int                               # echoes the request
    status: CaptureAttemptStatus                # SUCCEEDED / FAILED / TIMEOUT / EXCEPTION
    text: Optional[str]                         # the model output when SUCCEEDED; None otherwise
    error_class: Optional[str]                  # the provider error's class name when not SUCCEEDED; never the message text
    usage: Optional[TokenUsageSnapshot]         # provider-reported usage as the provider port returned it
    usage_availability: UsageAvailabilityToken
    provider_request_id: Optional[str]
    capture_fingerprint: str                    # the CaptureRecord the boundary wrote for this call (§4.2)

class RunControlFrame(str, Enum):               # written by the RUNNER, never by the workflow
    RUN_BEGIN = "RUN_BEGIN"                     # (manifest_digest, method, run_id)
    CASE_BEGIN = "CASE_BEGIN"                   # (run_id, case_digest)
    CASE_END = "CASE_END"                       # (run_id, case_digest, harness_observed_calls_for_case)
    RUN_END = "RUN_END"                         # (run_id, harness_observed_calls)
```

**Provider side.** Inside the boundary process the provider is reached only
through a pilot-defined port:

```python
class ProviderPort(Protocol):                   # implemented by the CALLER, outside the pilot package
    def complete(self, prompt: str) -> ProviderResult: ...

@dataclass(frozen=True)
class ProviderResult:
    text: str
    usage: Optional[TokenUsageSnapshot]
    usage_availability: UsageAvailabilityToken
    provider_request_id: Optional[str]
    provider_id: str
```

**Process start and provider construction.** The runner starts the boundary
with `subprocess` as a separate interpreter process, passing three
arguments: the transport endpoint, the manifest digest, and a
`provider_factory` dotted path (`package.module:function`). The boundary
entry module performs **exactly one dynamic import** of that module and calls
the function, which must return a `ProviderPort`; the object never crosses
the process boundary, so nothing need be serializable. The provider SDK is
imported by the caller's factory module, never by the pilot package; the
boundary test (A30) permits that single `importlib.import_module` call in
the boundary entry module and nowhere else. A factory that fails to import or
returns an object without `complete` aborts the boundary before any run
(`PROVIDER_FACTORY_INVALID`).

**Transport.** A local inter-process channel (a Unix domain socket, or a
pipe pair where sockets are unavailable) carrying JSON-encoded frames, one
per call or control event, referenced by
`CaptureBoundaryDeclaration.port_ref`. The harness's workflow client is a
thin stub that writes one `GatewayRequest` per model call and reads one
`GatewayResponse`; it holds no provider credential and no SDK.

**Completeness rule (exact, both directions).** The workflow under test is
constructed with the gateway stub as its only client; that this is its only
call path is a harness property the package cannot prove and is declared in
`process_separation_ref`. A method's run is complete iff, for that `run_id`:
every case digest of the benchmark manifest appears exactly once between
`CASE_BEGIN` and `CASE_END`; sequence numbers within each case are
contiguous from 1; and the boundary's captured call count equals the
harness-observed count at `RUN_END` and per case at `CASE_END` (`captured ==
harness_observed`, refusing **either** direction of disagreement). An
incomplete run yields **no execution record and no envelope**; the method's
state becomes `INCONCLUSIVE` with refusal `CAPTURE_INCOMPLETE`.

**Failure behaviour.** A provider failure is a capture record with
`CaptureAttemptStatus` other than `SUCCEEDED`; it counts as a call and is
returned to the workflow as a `GatewayResponse` with `text = None`. A
boundary failure to write a record aborts the run for that method
(`CAPTURE_INCOMPLETE`). The boundary never retries on the workflow's behalf.

### 4.2 The capture record

```python
@dataclass(frozen=True)
class CaptureRecord:                            # ApiCallTokenRecord-shaped; one per model call
    manifest_digest: str
    method: ReasoningMethodRef
    run_id: str
    case_digest: str
    sequence: int
    provider_id: str
    attempt_id: str
    status: CaptureAttemptStatus                # pilot-local; pinned to Context Minimization's AttemptStatus by test
    provider_invoked: bool
    usage_availability: UsageAvailabilityToken
    usage: Optional[TokenUsageSnapshot]         # provider-reported; None when unavailable
    prompt_digest: str
    response_digest: str
    captured_at: datetime                       # the boundary's own instant
    capture_fingerprint: str                    # JCS digest of the fields above
```

**Correlation and canonical order.** A capture record belongs to a
method's run iff its `manifest_digest`, `method`, `run_id` and `case_digest`
match and its `sequence` is contiguous within `(run_id, case_digest)`. The
**canonical order** of a run's records is the tuple `(case_digest,
sequence)`, ascending, with `case_digest` ordered as in the benchmark
manifest (ascending by code point); every reference to "sequence order"
means this total order, so `capture_refs` and `capture_boundary_ref` are
deterministic. The boundary retains its records for the manifest; nothing
else may write them.

### 4.3 Order of operations and attestation issuance

1. The runner validates the manifest (§3.1) and starts the boundary process
   with the transport endpoint, the manifest digest and the
   `provider_factory` dotted path; the boundary constructs the `ProviderPort`
   internally from that factory, as §4.1 specifies. No provider object
   crosses the process boundary.
2. The workflow runs behind the boundary over the complete case set.
3. **The boundary recomputes telemetry** from its own capture records, in
   canonical order (§4.2): `llm_calls` = the count of capture records for
   the run under `manifest.resource_aggregation` (the sum over the case
   set); `llm_calls_basis = INJECTED_COUNTER`; `token_usage` =
   provider-reported usage summed **per field**, where a field is summed only
   if it is present in every capture record and is otherwise `None`;
   `token_usage_availability = AVAILABLE` only if every capture record has
   `usage_availability = AVAILABLE`, otherwise the first unavailable reason
   and `token_usage = None`; `token_count_basis = PROVIDER_REPORTED` when
   `token_usage` is present, else `UNKNOWN`; `capture_refs` = the manifest
   digest followed by every `capture_fingerprint` in canonical order. The
   boundary returns this telemetry to the runner as a JSON payload.
4. The adapter constructs the execution record **with exactly that
   telemetry** and digests it, then passes the record's **canonical JCS
   payload** (the exact payload whose digest is `record_digest`, with the
   digest field included) back to the boundary. No deserialization into the
   Slice 1 dataclass happens in the boundary.
5. **`issue_attestation(record_payload, capture_records, *, declaration,
   record_issuer_identity, requester_identity, envelope_id) ->
   AttestationEnvelope`** runs in the boundary process. It recomputes step 3
   from the supplied capture records; recomputes the record digest from the
   payload with the digest field excluded and verifies it equals the
   payload's `record_digest`; verifies the payload's `telemetry` equals the
   recomputation field by field, and refuses otherwise
   (`TELEMETRY_NOT_RECOMPUTED`); verifies `declaration.boundary_identity`
   differs from `record_issuer_identity` and `requester_identity`, refusing
   otherwise before Slice 1 would (`SELF_ATTESTATION`) `[V]`. It then issues
   the envelope over `record_digest` with `attested_fields` = the
   **supported subset** of `declaration.allowed_attested_fields`: always
   `telemetry.llm_calls`; each token field only when that field of
   `token_usage` is present; `capture_boundary_ref` = the JCS digest of the
   ordered capture fingerprints; `attester_identity =
   declaration.boundary_identity`; `envelope_id` as supplied by the runner
   and required to equal `f"att:{record_digest[:16]}:{boundary_identity}"`
   (deterministic, so two issuances collide rather than multiply);
   `attested_at` **generated by the boundary**: the single timezone-aware
   issuance instant the boundary obtains itself at the moment it issues,
   never supplied by the runner or any caller (with `CaptureRecord.captured_at`,
   the only clock reads the package permits, §7).

**An envelope never carries a competing value**: it attests values the
boundary itself recomputed and found in the record. The boundary never
attests a record whose telemetry it did not recompute. Runtime-reported and
in-process counts survive only in `WorkflowReportedDiagnostics`, labelled
`RUNTIME_REPORTED_DIAGNOSTIC`, and enter neither telemetry nor any envelope.

### 4.4 Consistency versus authenticity, stated precisely

| Claim | What proves it | Status in the pilot |
|---|---|---|
| The record's `llm_calls` (and token totals, when attested) equal what the boundary captured and recomputed | the boundary's `AttestationEnvelope`, resolved as an authority in the request | `ATTESTED` on the envelope's fields only; everything else `UNATTESTED` |
| The boundary is who it says, ran in a separate process, and its capture records were not altered | a Trusted Evidence Authority receipt over the attestation, adapted to a `VerificationEnvelope` | **`UNVERIFIED` in 4A**; `process_separation_ref` is declared, not verified; the engine's resolution stays `REQUESTER_ASSERTED` |
| The manifest existed before execution | nothing beyond local process enforcement | `DECLARED_UNVERIFIED` |
| The workflow's own `total_llm_calls` | nothing | diagnostic only; never evidence |
| The quality value | the evaluation record and evaluator declaration (§3.4, §5) | evaluator-produced; independence `DECLARED_UNVERIFIED`; never `ATTESTED` or `VERIFIED` in 4A |
| A resolved authority is genuine | nothing inside the engine (ballot §3) | requester-asserted; reported as such on every result |

**What an existing envelope proves.** An `AttestationEnvelope` proves that a
named capture boundary asserts the attested fields for that record digest;
the engine proves only that the envelope is consistent with the record and
that the attester is one the requester resolved. A `VerificationEnvelope`
proves that a named verifier asserts it verified the attestation. Neither
proves the identity behind the name. `VERIFIED` is reachable only through
the Trusted Evidence Authority's `issue()`; the pilot has no other verifier.

**Who may issue.** Attestation: the declared capture boundary through
`issue_attestation`, never the workflow, harness, adapter, evaluator or
requester. Verification: the Trusted Evidence Authority only, under a trust
anchor whose `TrustAnchorCapability` covers reasoning-method telemetry, which
does not exist yet `[G]`.

**4.1 (resolved by ratification, recommendation adopted) — depth of trust in 4A.**

| Option | Consequence |
|---|---|
| A. No capture boundary: everything `UNATTESTED / UNVERIFIED`, stated | cheapest; the pilot measures nothing the workflow could not have reported itself; decision 4 stays open |
| B. Capture boundary recomputes and populates telemetry, then attests it; verification absent and stated | telemetry `ATTESTED` on the supported fields; quality declared-unverified; one new component; no TEV work |
| C. B plus a TEV anchor capability and a receipt→`VerificationEnvelope` adapter | `VERIFIED` telemetry; adds a TEV capability member and an adapter, each needing its own ratification |

**Recommendation: B**, with C recorded as the next trust slice. The pilot
report prints the three evidence axes per field, the preregistration status,
and the diagnostics under their label; no summary may say "trusted" or
"verified" for any field.

---

## 5. Quality evaluation: declared, not proven

Field completeness and unequal strings do not prove independence. In 4A an
evaluator's separation from the tested workflow is **declared and
unverified**, and no quality figure is promoted on the strength of a
declaration.

```python
class EvaluatorKind(str, Enum):
    HUMAN = "HUMAN"
    LLM = "LLM"
    PROGRAMMATIC = "PROGRAMMATIC"

@dataclass(frozen=True)
class QualityEvaluatorDeclaration:
    evaluator_identity: str                     # who scored (an evaluator identity, not a model reference)
    evaluator_version: str
    kind: EvaluatorKind
    model_ref: Optional[str]                    # required iff kind == LLM; compared only to the tested workflow's model_ref
    separation_declaration_ref: str             # declares a distinct process and call path with no shared prompt state; unverified
    scoring_instruction_digest: str             # digest of the scoring instructions, which name benchmark_manifest_digest and the sufficiency rule
    benchmark_manifest_digest: str              # == the manifest's benchmark
    calibration_evidence_ref: str               # may be blank; blankness is reported
    independence_status: Literal["DECLARED_UNVERIFIED"]   # the only value in 4A
    declaration_digest: str
```

**Obligations.** `kind == LLM` requires `model_ref`; other kinds refuse it
(`EVALUATOR_KIND_INCONSISTENT`). `evaluator_identity` must differ from the
record's `issuer_identity`, the request's `requester_identity` and the
capture boundary's identity (`EVALUATOR_SELF_LOOP`); an LLM evaluator's
`model_ref` is compared to the tested workflow's `model_ref` only to report
sameness (`EVALUATOR_SHARES_MODEL`, reported, not refused), never to an
identity string. Every claim the evaluator produces is bound through a
`QualityEvaluationRecord` (§3.4) whose `evidence_refs` link is checked by
validation.

**5.1 (resolved by ratification, recommendation adopted) — the claim's `source_basis`.**

| Option | Consequence |
|---|---|
| A. `REPORTED` for every evaluator-produced claim in 4A | honest by construction; the engine does not read `source_basis` for the outcome; every quality figure is labelled reported |
| B. `OBSERVED`, with the report stating separately that evaluator independence and identity are requester-asserted and unverified | matches the adapter's current practice; risks reading as measured rather than judged |

**Recommendation: A.** Under either option the report states, beside every
quality figure, `independence_status = DECLARED_UNVERIFIED` and whether
`calibration_evidence_ref` is blank. Slice 1 has no envelope for quality
claims, so no quality figure can be `ATTESTED` or `VERIFIED` in 4A `[G]`.

---

## 6. Decisions 3 and 4 — Pilot composition and lifecycle

### 6.1 Composition (Advisor 3)

The manifest fixes the composition before any run and `validate_manifest`
proves it complete against the catalog and advisory: the **governed
baseline** (`plan.baseline`); **every method in the advisory's complete
qualifying set**, by advisory digest (`plan.recommended` equals that set and
stays fenced as intent, not selection); and **challengers** = every
admissible catalog method not in the qualifying set (exhaustive,
`PREREGISTERED`). Roles are non-exclusive and methods deduplicated (§3.1).
When the qualifying set is empty (8.1-A) the manifest carries no
`ADVISOR_QUALIFIED` role, and the pilot runs the baseline and challengers and
reports `NO_QUALIFYING_METHOD`.

**Coverage report, mandatory, no target.** Counts are validated
non-negative integers over deduplicated methods.

```python
@dataclass(frozen=True)
class ChallengerCoverageReport:
    manifest_digest: str
    admissible_method_count: int
    methods_assigned: int                       # deduplicated; == admissible_method_count under 6.1-A
    methods_with_record: int
    baseline_has_record: bool
    qualified_declared: int                     # methods carrying ADVISOR_QUALIFIED
    qualified_with_record: int
    challengers_declared: int                   # methods carrying CHALLENGER (a non-qualified baseline counts here and as baseline)
    challengers_with_record: int
    methods_without_record: tuple[ReasoningMethodRef, ...]
    sampling: ChallengerSamplingPolicy
    summary_permitted: bool                     # derived: methods_with_record == methods_assigned and methods_assigned == admissible_method_count
```

**Anti-gaming rule.** Set precision = qualified methods whose outcome is
`SUFFICIENT_PARETO_EFFICIENT`, **divided by `qualified_declared`** (never by
methods with a record, so an omitted result can only lower it). The report
prints **no success summary at all** unless `summary_permitted` is true,
which requires every assigned method to have a record and the assignment to
cover the whole admissible catalog. When a summary is printed it always
carries, on the same line, `qualified_declared / admissible_method_count`,
set precision and `challengers_with_record / challengers_declared` (advisor
note §6). `SUFFICIENT_RESOURCE_DOMINATED` is sufficient but dominated and is
reported under its own name, never as a success.

**6.1 (resolved by ratification, recommendation adopted) — sampling kind for the first pilot.**

| Option | Consequence |
|---|---|
| A. `PREREGISTERED`, exhaustive: every admissible non-qualified method is a challenger | with the seven-method research catalog, full coverage; no sampling to game |
| B. `RANDOMIZED` with a seeded subset | fewer runs; coverage below full; `summary_permitted` would need a ratified rule for partial coverage |
| C. `RISK_BASED` by consequence class | needs a risk rule that does not exist |

**Recommendation: A** for 4A; B and C stay available through the existing
policy contract when catalogs grow.

### 6.2 Lifecycle (Advisor 5, research scope only)

Lifecycle states are **neutral**: none names an outcome, and the exact
`FitOutcome` is carried separately and verbatim. Lineage is **one-way** so
that every record is constructible: a predecessor names only the successor's
manifest digest; a successor names the predecessor's state digest.
`revision_scope` is **derived**, never asserted.

```python
class PilotConfigurationState(str, Enum):
    PROPOSED = "PROPOSED"                       # manifest validated; nothing run
    UNDER_TEST = "UNDER_TEST"                   # at least one observation validated; no engine result yet
    EVALUATED = "EVALUATED"                     # an engine result assessed this method with one of the three assessed outcomes
    INCONCLUSIVE = "INCONCLUSIVE"               # COMPARISON_EVIDENCE_ABSENT, an engine refusal, or CAPTURE_INCOMPLETE / WORKFLOW_FAILED for this method
    REVISED = "REVISED"                         # superseded: a successor manifest exists

class RevisionScope(str, Enum):                 # derived by comparing predecessor and successor manifests; several may apply
    CONFIGURATION = "CONFIGURATION"             # plan.binding.configuration_digest or binding_digest differs
    TASK_CLASS = "TASK_CLASS"                   # plan.task_class.task_class_digest differs
    BENCHMARK_MANIFEST = "BENCHMARK_MANIFEST"   # benchmark.benchmark_manifest_digest differs
    COMPARISON_PLAN = "COMPARISON_PLAN"         # plan_digest differs after masking task_class, binding and benchmark (baseline, recommended, challengers, catalog, preregistration)
    SUFFICIENCY_RULE = "SUFFICIENCY_RULE"       # the task class's sufficiency rule id or version differs
    # The four scopes below extend the owner-listed five so that every manifest coordinate is
    # revisable; ratified with ballot item 4 on 2026-09-02.
    ADVICE = "ADVICE"                           # advisory_digest or rule_set differs
    EVALUATOR = "EVALUATOR"                     # evaluator.declaration_digest differs
    CAPTURE_BOUNDARY = "CAPTURE_BOUNDARY"       # capture_boundary declaration differs
    AGGREGATION = "AGGREGATION"                 # resource_aggregation or quality_aggregation differs

def derive_revision_scope(predecessor: PilotStudyManifest, successor: PilotStudyManifest) -> tuple[RevisionScope, ...]:
    """Pure. Returns the non-empty, member-ordered set of scopes in which the two manifests differ,
    or refuses REVISION_WITHOUT_CHANGE when no covered coordinate differs. Every manifest field is
    covered by some scope (a difference only in `methods` is a difference in ADVICE, COMPARISON_PLAN
    or the catalog's admissible set, hence never uncovered), so two manifests with different digests
    always yield a scope."""

@dataclass(frozen=True)
class PilotConfigurationStateRecord:
    schema_version: Literal["workflow_fit_pilot.state.v1"]
    manifest_digest: str
    method: ReasoningMethodRef
    roles: tuple[PilotRole, ...]
    state: PilotConfigurationState
    fit_outcome: Optional[FitOutcome]           # required for EVALUATED (never COMPARISON_EVIDENCE_ABSENT there); COMPARISON_EVIDENCE_ABSENT or None for INCONCLUSIVE; None otherwise
    refusal_codes: tuple[str, ...]              # engine or capture refusal codes for INCONCLUSIVE; empty otherwise
    result_digest: Optional[str]                # the ReadinessComparisonResult that set EVALUATED or INCONCLUSIVE
    predecessor_state_digest: Optional[str]     # the record this one follows: within one manifest, or the REVISED record of the predecessor manifest
    predecessor_manifest_digest: Optional[str]  # set on a successor manifest's PROPOSED record
    successor_manifest_digest: Optional[str]    # set on a REVISED record; the ONLY forward reference
    revision_scope: tuple[RevisionScope, ...]   # == derive_revision_scope(...) on REVISED and on a successor's PROPOSED; empty otherwise
    usage_scope: Literal["RESEARCH_ONLY"]
    approval_status: Literal["NONE"]            # a constant, so a consumer must change a type to read approval
    recorded_by: str
    recorded_at: datetime
    state_digest: str

class LifecycleEvent(str, Enum):
    OBSERVATION_VALIDATED = "OBSERVATION_VALIDATED"
    RESULT_ASSESSED = "RESULT_ASSESSED"
    RESULT_INCONCLUSIVE = "RESULT_INCONCLUSIVE"
    SUPERSEDED = "SUPERSEDED"

def transition(predecessor: PilotConfigurationStateRecord, event: LifecycleEvent, *,
               manifest: PilotStudyManifest, successor_manifest: Optional[PilotStudyManifest] = None,
               result: Optional[ReadinessComparisonResult] = None, recorded_by: str, recorded_at: datetime) -> PilotConfigurationStateRecord:
    """Pure. The only way to produce a non-PROPOSED record. Refuses any event not permitted from
    predecessor.state (STATE_TRANSITION_INVALID); reads fit_outcome and refusal codes from `result`
    for this method; on SUPERSEDED requires `successor_manifest`, derives revision_scope, and returns
    the REVISED record. The successor's PROPOSED record is produced by propose(successor_manifest,
    predecessor=revised_record), which copies revision_scope and names the REVISED record's digest."""
```

**Closed transitions.** `PROPOSED → UNDER_TEST → EVALUATED | INCONCLUSIVE`;
`PROPOSED → INCONCLUSIVE` only on a capture or workflow refusal
(`CAPTURE_INCOMPLETE`, `WORKFLOW_FAILED`), since an incomplete run validates
no observation and so never reaches `UNDER_TEST`; any state `→ REVISED`.
`EVALUATED` and `INCONCLUSIVE` never transition to each other or to
`UNDER_TEST`: a different result requires a different manifest, hence
`REVISED`. A constructor can check a record's own shape only; **transition
history is enforced by `transition` and `propose`**, which receive the
predecessor record and the relevant manifests, and by
`validate_lineage(records, manifests, results)`, which replays a chain,
refuses a record that no permitted transition produces, and refuses an
`EVALUATED` or `INCONCLUSIVE` record whose named engine result is not
supplied or does not give that method the recorded outcome and refusals.
`WORKFLOW_FAILED` is the pilot refusal recorded when the tested workflow
itself raises after a captured provider failure: the run ends incomplete.

**Revision scope** covers any change to the configuration, the task class,
the benchmark manifest, the comparison plan or the sufficiency rule (the
owner-listed five) and, as ratified with ballot item 4, to the advice, the
evaluator, the capture boundary or the aggregation references; any of these
yields a new `manifest_digest`, a `REVISED` record on the predecessor naming
`successor_manifest_digest` with the derived `revision_scope`, and a
`PROPOSED` record on the successor naming `predecessor_manifest_digest` and
`predecessor_state_digest` (the `REVISED` record's digest). `revision_scope`
is a **manifest-level** property: every successor `PROPOSED` record carries
the same derived tuple. A caller cannot omit or invent a scope:
`validate_lineage` recomputes `derive_revision_scope` and refuses a mismatch
(`REVISION_SCOPE_MISMATCH`).

**Method-set drift between manifests.** Superseding is per manifest, so
`transition(SUPERSEDED)` is applied to **every** method record of the
predecessor. A method absent from the successor still receives a `REVISED`
record whose `successor_manifest_digest` names a manifest in which it has no
assignment; `validate_lineage` accepts that as the method's terminal record.
A method new to the successor receives a `PROPOSED` record from
`propose(successor_manifest, predecessor=None, predecessor_manifest=...)`
with `predecessor_manifest_digest` set, `predecessor_state_digest = None`
and the manifest-level `revision_scope`; `validate_lineage` requires that
every predecessor method has a `REVISED` record and every successor method
has a `PROPOSED` record (`LINEAGE_INCOMPLETE` otherwise).

**The configuration is identified before testing** because `PROPOSED`
requires a validated manifest and refuses any observation. **No state is an
approval, and no state restates a judgment**: `approval_status` is the
constant `"NONE"`, `usage_scope` is `RESEARCH_ONLY`,
`SUFFICIENT_RESOURCE_DOMINATED` is never rendered as qualified or as a
success, and no Decision Authority, Constitution binding or
`deployment_environment_ref` semantics are touched. The Slice 1
`SUFFICIENT_PARETO_EFFICIENT` fence (ballot §8) stands.

**6.2 (resolved by ratification, recommendation adopted) — placement of the state ledger.**

| Option | Consequence |
|---|---|
| A. In the pilot package (research-only) | matches scope; the production lifecycle ruling (ballot 8.2) stays open |
| B. In `governance-contracts` beside `AssessedSystemBinding` | pre-empts ballot 8.2 with research-only states |

**Recommendation: A**; ballot 8.2 is not decided by this document.

---

## 7. The smallest research-only pilot, and the implementation boundary

**One task class.** The harness's `hard` class as declared through the
governed adapter (`StudyClassDeclaration`) with a versioned threshold-based
sufficiency rule and `RECOVERABLE` consequence (so no admission is needed)
`[I]`; **benchmark manifest** = that class's `TaskCase` set, each case
digested, ordered and counted, its head `content_digest` recomputed from the
list, its `benchmark_manifest_digest` set as the task class's
`benchmark_set_digest`; **governed baseline** `linear_chain@1` as the adapter
already uses `[V]`; **advisor-qualified methods** from one advisory over the
class's profile under `rules.research.v0`, by digest; **challengers** every
other admissible catalog method (6.1-A); **one capture boundary** process
with the caller's provider client injected into it; **one declared
evaluator** with its evaluation records; **aggregation references** the sum
over the case set for resources and the declared research mean for quality.
Output: one `ReadinessComparisonResult` with **whichever outcomes its
evidence warrants**, one coverage report, one state chain per method, and a
pilot report that prints evidence axes per field, preregistration and
independence statuses, and diagnostics under their label. A real pilot never
manufactures missing evidence to obtain `COMPARISON_EVIDENCE_ABSENT`; the
four-outcome demonstration lives in a synthetic engine-coverage fixture
(A25).

**Execution** happens only in the research harness with the gateway stub as
the workflow's only client and the provider client inside the boundary
process. **Not** through Agent Runtime, Agentic Proposer or Agent Workforce
Composer; no runtime integration.

**Package.** `packages/capabilities/workflow-fit-pilot` →
`ugence-workflow-fit-pilot`, depending on `ugence-reasoning-method-governance`,
`ugence-readiness-comparison`, `ugence-reasoning-method-advisor`,
`ugence-governance-contracts`, `ugence-jcs` (not on Context Minimization:
`CaptureAttemptStatus` is pilot-local and pinned by a test-only import);
the boundary process entry point, ports, frames, capture record and
`issue_attestation` in a subpackage that imports only the standard library's
`subprocess`, `socket`, `json`, `importlib` and `datetime` facilities plus
the contracts above, and never `agentic`, a network client or an LLM SDK;
the harness stays in `experiments/`. Boundary test as in Slices 1 and 2,
with three allowances limited to the boundary subpackage: the socket and
subprocess imports, exactly one `importlib.import_module` call in the entry
module for the provider factory, and one clock read for
`CaptureRecord.captured_at` and `attested_at`.

**In scope:** §3.1 manifest and `validate_manifest`; §3.2 benchmark
manifest; §3.3 observation and diagnostics; §3.4 evaluation record and
`validate_observation`; §4 gateway port, capture record, completeness and
failure rules, telemetry recomputation and `issue_attestation`; §5 evaluator
declaration; §6.1 coverage report; §6.2 state ledger with `transition`,
`propose`, `derive_revision_scope` and `validate_lineage`; a pilot runner
that validates the manifest, starts the boundary, runs the methods through
the harness, adapts records, calls `compare()`, and renders the report; CI
gate; wheel self-check.

**Out of scope:** any change to Slice 1 or Slice 2 contracts, enums or
packages; TEV anchor capability and receipt adapter (4.1-C); envelopes for
quality claims; benchmark-registry registration; benchmark-derived advisor
input (`BENCHMARK_DERIVED` stays absent); readiness composite; production
approval, configuration mutation, Constitution binding, runtime integration;
any owner-supplied numeric default, threshold, sample size, coverage target
or acceptance figure.

---

## 8. Executable acceptance tests

| # | Test | Expected |
|---|---|---|
| A1 | manifest whose baseline assignment's method ≠ `plan.baseline`, or with no `GOVERNED_BASELINE`, or two | `ROLE_INCONSISTENT` |
| A2 | manifest with an `ADVISOR_QUALIFIED` role and `advisory_digest=None`; or `rule_set` present without `advisory_digest`; or `validate_manifest` called without the advisory when the digest is set | `ADVISORY_REQUIRED`; a manifest with `advisory_digest` set and no qualified role constructs and validates when the advisory's qualifying set is empty |
| A3 | manifest listing one method twice; or `allowed_attested_fields` outside `ATTESTABLE_TELEMETRY_FIELDS` or lacking `telemetry.llm_calls` | `METHOD_DUPLICATE` / `ATTESTED_FIELDS_INVALID` |
| A4 | manifest whose `benchmark.benchmark_manifest_digest ≠ plan.task_class.benchmark_set_digest` | `BENCHMARK_MANIFEST_MISMATCH` |
| A5 | benchmark manifest with unsorted, repeated or empty `case_digests`, `case_count ≠ len` or `case_count ≤ 0`, or a head `content_digest` that is not the digest of the list | refused at construction (`BENCHMARK_HEAD_MISMATCH` for the head) |
| A6 | `validate_manifest` with an advisory whose complete qualifying set differs from the `ADVISOR_QUALIFIED` methods or from `plan.recommended`; or whose catalog ref differs from the plan's; or with a catalog or rule set whose ref differs from the manifest's; or with a catalog whose admissible set under `rule_set.admissibility` is not exactly the assigned set; or a `CHALLENGER` role on a qualified method; or called without the rule set | `ADVISORY_MISMATCH` / `CATALOG_MISMATCH` / `RULE_SET_MISMATCH` / `COMPOSITION_INCOMPLETE`; success returns a `ValidatedManifest` whose digest changes with any input |
| A7 | observation naming a manifest digest other than the supplied manifest's; or whose record's `capture_refs` stamp a different manifest digest; or whose instants precede `preregistered_at` | `MANIFEST_MISMATCH` / `MANIFEST_NOT_PRIOR`; the report prints `preregistration_status = DECLARED_UNVERIFIED` |
| A8 | observation with `case_set_digest ≠ benchmark_manifest_digest` or `case_count` mismatch | `BENCHMARK_MANIFEST_MISMATCH` |
| A9 | observation roles differing from the manifest assignment; or an `ADVISOR_QUALIFIED` observation whose supplied advisory did not qualify the method | `ROLE_INCONSISTENT` / `ADVISORY_MISMATCH` |
| A10 | `validate_observation` called with any required object omitted, with a `ValidatedManifest` for a different manifest or advisory, or with a record whose digest, method, binding, task class or model differs | refused (`MANIFEST_NOT_VALIDATED`, `RECORD_MISMATCH` etc.); never a pass by omission |
| A11 | evaluation record whose `evaluator_declaration_digest`, `scoring_instruction_digest`, `quality_aggregation` or `evaluated_by` differs from the manifest's; or a claim whose `evidence_refs` do not name the evaluation id; or whose JCS digest ≠ `evaluation.claim_digest`; or a `QualityResult` whose digest, `claim_ref`, `value`, `method` or `aggregation` does not match | `QUALITY_EVALUATION_MISMATCH` / `QUALITY_RESULT_MISMATCH` |
| A12 | boundary process observes N capture records for a method while the workflow reports M ≠ N | record telemetry carries N with `llm_calls_basis = INJECTED_COUNTER` and `capture_refs` = manifest digest + fingerprints; diagnostics carry M under `RUNTIME_REPORTED_DIAGNOSTIC`; the envelope is over the record digest computed with N; `EvidenceStatusView` shows `ATTESTED` on the envelope's fields |
| A13 | `issue_attestation` given a record payload whose telemetry differs from the recomputation over the supplied capture records, or whose `record_digest` is not the digest of the payload; or with `boundary_identity` equal to `record_issuer_identity` or `requester_identity`; or with an `envelope_id` other than the deterministic form | `TELEMETRY_NOT_RECOMPUTED` / `SELF_ATTESTATION` / `ATTESTATION_MISMATCH`; no envelope |
| A13a | `issue_attestation` has no `attested_at` parameter; two issuances of the same record by the boundary carry boundary-generated, timezone-aware `attested_at` values that are not earlier than every capture record's `captured_at`; the runner process reads no clock | as stated; a caller-supplied instant cannot be passed |
| A14 | a run with a gap in capture sequence numbers; a benchmark case with no `CASE_BEGIN`/`CASE_END` pair or appearing twice; `captured calls ≠ harness_observed_calls` in **either** direction at `CASE_END` or `RUN_END` | no record, no envelope; state `INCONCLUSIVE` with `CAPTURE_INCOMPLETE` (`WORKFLOW_FAILED` when the workflow itself raised); when the governed baseline's run is incomplete the engine is still called and every complete method becomes `INCONCLUSIVE` with the engine's `BASELINE_ABSENT` refusal |
| A15 | one capture record with `usage_availability ≠ AVAILABLE`; and separately a run where `total_tokens` is present in every record but `input_tokens` is absent in one | first: `token_usage = None`, availability carries the reason, the envelope attests `telemetry.llm_calls` only; second: `total_tokens` summed and attested, `input_tokens = None` and not attested |
| A16 | an envelope whose `attested_fields` are not a subset of the declaration's allowed fields, omit `telemetry.llm_calls`, cover a record digest other than the observation's, or whose `capture_boundary_ref` is not the digest of the record's ordered capture fingerprints | `ATTESTATION_MISMATCH` |
| A16a | gateway round trip: a `GatewayRequest` carrying prompt text yields a `GatewayResponse` whose `text` is the provider port's output, whose `capture_fingerprint` names a capture record holding only `prompt_digest` and `response_digest`; a provider exception yields `status = EXCEPTION`, `text = None`, `error_class` set, and still one capture record; a factory path that does not resolve to a `ProviderPort` aborts with `PROVIDER_FACTORY_INVALID` before any frame | as stated; the prompt and response text never appear in any record or envelope |
| A16b | two runs whose capture records are identical but delivered in different arrival order | identical `capture_refs`, `capture_boundary_ref`, telemetry and record digest (canonical `(case_digest, sequence)` order) |
| A17 | attestation whose `attester_identity` equals the record issuer or the requester | Slice 1 `SELF_ATTESTATION`, unchanged |
| A18 | attester not in `resolved_authorities` | listed in `ignored_envelopes`; status `UNATTESTED` |
| A19 | any pilot result | every `EvidenceStatusView.verification_status == UNVERIFIED`; the report never prints "verified" or "trusted"; every quality figure carries `DECLARED_UNVERIFIED` and the calibration-blank flag; every judgment line carries `RESEARCH_ONLY` |
| A20 | `EvaluatorKind.LLM` without `model_ref`, or `HUMAN` with one; evaluator identity equal to the record issuer, the requester or the boundary; LLM evaluator sharing the workflow's `model_ref` | `EVALUATOR_KIND_INCONSISTENT`; `EVALUATOR_SELF_LOOP`; `EVALUATOR_SHARES_MODEL` reported, not refused |
| A21 | coverage report on a manifest with three qualified methods over a seven-method catalog under 6.1-A, baseline not qualified | `admissible_method_count=7`, `methods_assigned=7`, `qualified_declared=3`, `challengers_declared=4`; after a complete run every `_with_record` equals its `_declared`, `summary_permitted=True`, and set precision uses denominator 3 |
| A22 | the same manifest with one qualified method's record missing, then with one challenger's record missing | `summary_permitted=False` in both; no success summary printed; `methods_without_record` names the method; set precision, when computed, still divides by `qualified_declared`; negative or non-integer counts refused at construction |
| A23 | empty qualifying set | no `ADVISOR_QUALIFIED` role; baseline and challengers run; `NO_QUALIFYING_METHOD` reported; no primary anywhere |
| A24 | `transition` from `PROPOSED` on `RESULT_ASSESSED`; `EVALUATED` on `RESULT_INCONCLUSIVE`; `RESULT_ASSESSED` whose result gives this method `COMPARISON_EVIDENCE_ABSENT`; an `INCONCLUSIVE` record with neither that outcome nor a refusal code; an outcome line rendering `SUFFICIENT_RESOURCE_DOMINATED` as "qualified" or "success" (the `ADVISOR_QUALIFIED` role label is not an outcome line and is permitted) | each refused (`STATE_TRANSITION_INVALID` for the transitions) |
| A25 | **synthetic engine-coverage fixture** (the PR #1566 four-outcome fixtures, not a pilot run) | exactly the four `FitOutcome` names appear; `result_digest` stable across two runs at one `produced_at` |
| A26 | real pilot runner end to end on the harness fixtures with a stub provider client injected into the boundary process | only the outcomes its evidence warrants appear; no `COMPARISON_EVIDENCE_ABSENT` unless evidence is genuinely absent; `authority_resolution_basis == REQUESTER_ASSERTED`; one record, one observation and one evaluation per method |
| A27 | `SUPERSEDED` with a successor manifest differing in configuration, task class, benchmark manifest, plan, sufficiency rule, advice, evaluator, capture boundary or aggregation (each in turn, then several at once) | predecessor `REVISED` records for every method with `successor_manifest_digest` and the derived manifest-level `revision_scope`; successor `PROPOSED` records for every successor method with `predecessor_manifest_digest`, `predecessor_state_digest` = the matching `REVISED` record's digest (or `None` for a method new to the successor) and the same scope; all records constructible in order; `validate_lineage` accepts the chain, including a method dropped by the successor |
| A28 | `SUPERSEDED` with a successor manifest identical to the predecessor; a `REVISED` record whose `revision_scope` differs from the derivation; a chain missing a `REVISED` record for a predecessor method or a `PROPOSED` record for a successor method; a chain containing a record no permitted transition produces; a hand-built `EVALUATED` or `INCONCLUSIVE` record naming a result digest that is not supplied or that gives the method a different outcome | `REVISION_WITHOUT_CHANGE`; `REVISION_SCOPE_MISMATCH`; `LINEAGE_INCOMPLETE`; `validate_lineage` refuses (`STATE_TRANSITION_INVALID` / `LINEAGE_INCOMPLETE`) |
| A29 | any state record | `approval_status == "NONE"`, `usage_scope == RESEARCH_ONLY`; field-set test finds no `approved`, `eligible`, `qualified`, `production` field; no state name equals a `FitOutcome` name |
| A30 | AST boundary scan of the package | no `agentic`, runtime, proposer, composer, readiness, `governed_value`, Context Minimization, network client or LLM SDK import anywhere; `socket`, `subprocess` and `importlib` only inside the boundary subpackage, with exactly one `import_module` call in its entry module; no clock read outside the boundary's `captured_at` and `attested_at`; `CaptureAttemptStatus` members pinned to Context Minimization's `AttemptStatus` under a test-only import |
| A31 | numeric scan of `src/` | no owner-supplied numeric default, threshold, sample size, coverage target or acceptance figure; integer fields are counts validated non-negative (positive where required) |

---

## 9. Explicitly excluded from 4A

No production authority or approval; no benchmark-derived advisor change; no
readiness composite; no runtime execution or integration; no TEV capability
or receipt adapter; no quality-claim envelopes; no benchmark-registry
registration; no change to any Slice 1 or Slice 2 contract; no LLM-based
selection; no owner-supplied numeric default, threshold, sample size,
coverage target or acceptance figure.

---

## 10. Owner ballot — ~~`[R]`~~ **RATIFIED 2026-09-02**

1. **Usage binding.** Ratify §3: a `PilotStudyManifest` (3.1-B) digested and
   validated against the full catalog and advisory before execution, binding
   the comparison plan, the exact advisory and rule-set digests where advice
   is used, the deduplicated methods with their non-exclusive roles, the
   benchmark manifest with its complete ordered case-digest set bound to its
   head, the capture-boundary and evaluator declarations and the aggregation
   references, with preregistration `DECLARED_UNVERIFIED` and locally
   enforced; `validate_manifest` receiving the full catalog, rule set and
   advisory and returning a `ValidatedManifest`; one `PilotObservation` and
   one `QualityEvaluationRecord` per method at Slice 1's aggregation
   boundary; and `validate_observation` receiving every object, the
   validated-manifest artifact, quality result and attestation included. No
   execution-record change.
2. **Trust controls.** Ratify §4 and §5: a separate-process capture boundary
   reached through the gateway frames as the workflow's only client, with the
   provider constructed inside the boundary from a caller-supplied factory
   through one dynamic import; an exact two-directional completeness rule
   over cases and calls under which an incomplete capture yields no record; telemetry recomputed by the
   boundary from its capture records (`INJECTED_COUNTER`,
   `PROVIDER_REPORTED`) and digested into the record before
   `issue_attestation`, which recomputes and refuses mismatch, attesting the
   supported subset of the declared fields (4.1-B); runtime counts retained
   only as labelled diagnostics; the Trusted Evidence Authority as the only
   verifier, issuing nothing in 4A; evaluator independence
   `DECLARED_UNVERIFIED`; claims `REPORTED` (5.1-A); every judgment labelled
   research-only and non-authoritative.
3. **Pilot composition.** Ratify §6.1: governed baseline, the advisory's
   complete qualifying set, and exhaustive preregistered challengers (6.1-A)
   as non-exclusive roles over deduplicated methods, proven complete by
   `validate_manifest`; a mandatory coverage report with validated integer
   counts; set precision over `qualified_declared`; no success summary unless
   every assigned method has a record and the catalog is fully covered; the
   four-outcome demonstration only as a synthetic engine fixture.
4. **Lifecycle.** Ratify §6.2: the five neutral states with closed
   transitions enforced by the pure `transition`, `propose` and
   `validate_lineage` operations, the `FitOutcome` carried separately; the
   configuration identified at `PROPOSED` before any run; revision for any
   change to configuration, task class, benchmark manifest, comparison plan
   or sufficiency rule, **and, as an amendment to the owner-listed five,
   for any change to the advice, the evaluator, the capture boundary or the
   aggregation references** (without which such manifests could not be
   superseded), with `revision_scope` derived from the two manifests as a
   manifest-level property, one-way lineage (predecessor names the
   successor manifest; successor names the predecessor state), and stated
   rules for methods dropped by or new to a successor; `approval_status =
   "NONE"` constant; the ledger placed in the pilot package (6.2-A); ballot
   8.2 and production approval remain open.

**Ratification record (2026-09-02).** *Owner ruling, verbatim:* "Ratify
all four as recommended, including the four additional revision scopes."
Applied: item 1 with 3.1-B; item 2 with 4.1-B and 5.1-A; item 3 with 6.1-A;
item 4 with 6.2-A and the nine-member `RevisionScope` (the owner-listed five
plus `ADVICE`, `EVALUATOR`, `CAPTURE_BOUNDARY`, `AGGREGATION`). Ratified:
Workflow-Fit decisions 1 (usage binding) and 4 (trust controls) and Advisor
decisions 3 (pilot composition) and 5 (lifecycle), **within the research-only
scope of 4A**; ballot 8.2 (production lifecycle placement), the Trusted
Evidence Authority capability (4.1-C), quality-claim envelopes, benchmark
registration and production approval remain open. Nothing numeric was
ratified.

**Authority.** Owner ratification by Rakesh Mohan, 2026-09-02, issued as an
explicit owner instruction in Claude Code session
`session_01VXERHvJzbb9cjZ1GyFFQLn` after revisions 2–4 applied the owner's
corrections and two adversarial design reviews. The model analysis was
advisory only; the owner instruction was the ratifying act. No source,
contract, enum, experiment or test changed with this record.

**Definition of done for 4A** (ratified): package
`ugence-workflow-fit-pilot` with the §3–§6 contracts and operations, the
boundary process, the pilot runner over the harness, every §8 row as an
executable test, a CI gate in the Slice 1 pattern, and a wheel self-check. No
owner-supplied numeric figure.

---

## 11. Correction record

### Revision 2 (owner instruction, 2026-09-02)

| # | Before | After |
|---|---|---|
| 1 | No preregistered manifest; an arm could name an advisory after the fact | `PilotStudyManifest` digested before execution; observations reference its digest (§3.1) |
| 2 | Observation described one case and one invocation with a singular case digest | Slice 1's one-record-per-method boundary retained; complete ordered case set; aggregation references bound (§3.3) |
| 3 | Membership inferred from `benchmark_set_digest` | `BenchmarkManifest` carrying the exact ordered case digests; validation receives it (§3.2) |
| 4 | Envelope carried the boundary's count as a competing value | boundary values populate telemetry before digesting; the envelope attests those values; runtime counts only as diagnostics (§4) |
| 5 | A three-argument plan validation | a validation operation receiving every object (§3.4) |
| 6 | Non-blank fields promoted an evaluator; identity compared to `model_ref` | `DECLARED_UNVERIFIED`; `EvaluatorKind` and `model_ref`; identity and model compared within their own types; claims `REPORTED` (§5) |
| 7 | Outcome-named states | `PROPOSED / UNDER_TEST / EVALUATED / INCONCLUSIVE / REVISED`; `fit_outcome` separate (§6.2) |
| 8 | Revision covered only the configuration digest | `RevisionScope` over five coordinates; manifest and state lineage (§6.2) |
| 9 | Exclusive arm kinds; decimal-string counts | Non-exclusive `PilotRole`s with deduplication; integer counts; exhaustive challengers (§3.1, §6.1) |
| 10 | "All four outcomes appear" expected of the real pilot | Synthetic engine-coverage fixture; the real pilot emits only warranted outcomes (§7) |
| 11 | "No numeric figure of any kind" | "No owner-supplied numeric default, threshold, sample size, coverage target or acceptance figure" (§2) |

### Revision 3 (adversarial design review, applied on owner instruction, 2026-09-02)

| # | Defect | Resolution |
|---|---|---|
| B1 | Circular lineage digests: predecessor named the successor's state digest and vice versa | One-way linkage: predecessor names `successor_manifest_digest` only; successor names `predecessor_state_digest` and `predecessor_manifest_digest` (§6.2, A27) |
| B2 | Validation lacked the catalog and the envelope, and could not prove the assignment equalled the advisory's complete qualifying set | `validate_manifest(manifest, catalog, advisory)` before execution proves completeness against the full advisory and catalog; `validate_observation` gains `attestation` (§3.1, §3.4, A6, A16) |
| B3 | `MetricClaim` has no evaluator fields, so "evaluator fields match" was unimplementable `[V]` | `QualityEvaluationRecord` binding declaration digest, claim digest, method, manifest, case set, scoring instructions and aggregation; observation references it; claim `evidence_refs` link checked (§3.4, A11) |
| B4 | Capture boundary declared but not specified | Gateway port and frame, transport, provider client injected into the boundary process, capture record with correlation, completeness and failure rules, recomputation and `issue_attestation` (§4.1–§4.3, A12–A16) |
| M5 | Timestamps presented as preregistration proof | `PreregistrationStatus.DECLARED_UNVERIFIED`; chronology locally process-enforced and stamped on capture records; stated on the report (§3.1, §4.4, A7) |
| M6 | `CALLER_SUPPLIED` for an injected counter | `INJECTED_COUNTER` for calls; `PROVIDER_REPORTED` for tokens (§4.3, A12) |
| M7 | Boundary could attest adapter-supplied telemetry blindly | `issue_attestation` recomputes from capture records and verifies the record digest; `TELEMETRY_NOT_RECOMPUTED` (§4.3, A13) |
| M8 | Exact attested-field tuple could not handle unavailable usage | `ATTESTABLE_TELEMETRY_FIELDS`, `allowed_attested_fields`, envelope fields = supported subset; calls always, tokens conditional (§3.1, §4.3, A15, A16) |
| M9 | Manifest/advisory and manifest/catalog correspondence checked only when observations arrived | `validate_manifest` refuses `ADVISORY_MISMATCH` and `COMPOSITION_INCOMPLETE` before any run (§3.1, A6) |
| M10 | Benchmark head unrelated to membership | `content_digest` defined as the digest of the ordered case list, recomputed; `BENCHMARK_HEAD_MISMATCH` (§3.2, A5) |
| M11 | Set precision improvable by omitting a bad result | Denominator `qualified_declared`; `summary_permitted` requires complete records and full catalog coverage (§6.1, A21, A22) |
| M12 | `revision_scope` caller-asserted | `derive_revision_scope` pure; `validate_lineage` recomputes; `REVISION_WITHOUT_CHANGE`, `REVISION_SCOPE_MISMATCH` (§6.2, A27, A28) |
| M13 | "No quality verdict" impossible as written | Requirement restated: every judgment labelled research-only, reported or unverified, non-authoritative; no state, role or summary restates it as approval (§2, A19) |
| m1 | `case_count` non-negative while the list is non-empty | positive (§3.2, A5) |
| m2 | "qualified" prohibition could reject the `ADVISOR_QUALIFIED` role label | prohibition scoped to outcome lines; the role label is permitted (§6.2, A24) |
| m3 | Transitions enforced by constructors alone | pure `transition`, `propose`, `validate_lineage` receiving predecessor record and manifests (§6.2, A24, A27, A28) |

The four ballot items of §10 were revised accordingly and remained `[R]`
at this revision; nothing was ratified by it.

### Revision 4 (two follow-up reviews of revision 3, applied on owner instruction, 2026-09-02)

| # | Defect | Resolution |
|---|---|---|
| B1 | Empty qualifying set unconstructible with its advisory recorded (A2 versus §6.1) | role ⇒ digest, not iff; `validate_manifest` compares possibly empty sets (§3.1, A2) |
| B2 | Gateway could not execute a call: only a prompt digest crossed, `GatewayResponse` undefined | `GatewayRequest.prompt` text; `GatewayResponse` with status, text, error class, usage, availability, provider request id and capture fingerprint; text never enters a record (§4.1, A16a) |
| B3 | `issue_attestation` lacked the identities and envelope fields it must use | receives the record's canonical payload, capture records, declaration, record issuer and requester identities and a deterministic `envelope_id`; generates `attested_at` itself; refuses self-attestation itself (§4.3, A13, A13a) |
| B4 | `quality_result_digest` unvalidated | `validate_observation` receives the `QualityResult`; `QUALITY_RESULT_MISMATCH`; claim and result digests defined as JCS digests (§3.4, A11) |
| M5 | `validate_manifest` could not compute admissibility; no rule set or catalog-ref checks | receives the `RuleSet`; `CATALOG_MISMATCH`, `RULE_SET_MISMATCH`; advisory catalog ref checked (§3.1, A6) |
| M6 | Manifest validation only presupposed by observation validation | `ValidatedManifest` artifact returned and required; `MANIFEST_NOT_VALIDATED` (§3.1, §3.4, A10) |
| M7 | `RevisionScope` could not express advice, evaluator, boundary or aggregation changes | four scopes added and ratified with ballot item 4; every manifest coordinate now covered (§6.2, A27) |
| M8 | Method-set drift across manifests unspecified | superseding applied to every predecessor method; dropped methods terminal; new methods `PROPOSED` with `predecessor_state_digest = None`; manifest-level scope; `LINEAGE_INCOMPLETE` (§6.2, A27, A28) |
| M9 | Record transfer into the boundary unspecified | canonical JCS payload passed; digest recomputed from it; no deserialization (§4.3) |
| M10 | Provider injection across processes undefined | `ProviderPort`, `ProviderResult`, `subprocess` start with a factory dotted path, exactly one dynamic import in the entry module; `PROVIDER_FACTORY_INVALID` (§4.1, §7, A16a, A30) |
| M11 | Completeness blind to skipped cases and one-directional | runner-written `RUN_BEGIN / CASE_BEGIN / CASE_END / RUN_END` frames; every case exactly once; `captured == harness_observed` in both directions (§4.1, A14) |
| M12 | `AttemptStatus` had no source under the import boundary | pilot-local `CaptureAttemptStatus` pinned to Context Minimization by test-only import (§2, §4.2, A30) |
| M13 | Capture-record order ambiguous across cases | canonical order `(case_digest, sequence)`; deterministic `capture_refs` and record digest (§4.2, A16b) |
| m1 | `capture_boundary_ref` not rechecked against the record | recomputed from `capture_refs[1:]` in `validate_observation` (§3.4, A16) |
| m2 | Per-field token summation undefined | a field is summed only if present in every record, else `None`; attested per field (§4.3, A15) |
| m3 | "Only client" presented as a package property | declared in `process_separation_ref`, not proven (§4.1) |

The four ballot items of §10 were revised accordingly and were ratified as
recommended on 2026-09-02 (§10).

### Consistency amendment after ratification (owner instruction, 2026-09-02)

§4.3 step 1 now states that the runner supplies the `provider_factory`
dotted path and the boundary constructs the `ProviderPort` internally, as
§4.1 specifies; step 5 no longer takes `attested_at` from the caller, the
boundary generating the single timezone-aware issuance instant itself
(A13a). Documentation only; the §10 rulings are unchanged.

**Post-implementation audit correction (adversarial review of PR #1575 at
`fc895f2a`, 2026-09-02).** (1) `validate_lineage` now receives the engine
results and refuses an `EVALUATED` or `INCONCLUSIVE` record whose named
result is absent or disagrees, so no state is reachable around a fabricated
result digest (§6.2, A28). (2) The closed-transition list gains
`PROPOSED → INCONCLUSIVE` on a capture or workflow refusal, which the
implementation needs because an incomplete run validates no observation;
`WORKFLOW_FAILED` is named (§6.2, A14). (3) When the baseline's run is
incomplete the engine is still called so complete methods do not remain
`UNDER_TEST` (A14). No ballot ruling changes.
