# Trusted Workflow-Fit Pilot (Phase 4A) — Commissioning Specification and Ballot

**Status:** `[R]` — revision 2, awaiting the four-item owner ballot in §10.
**Nothing here is implemented.** This document commissions one research-only
pilot package and one gate, and nothing else. It replaces further scoping
notes: the four open decisions it resolves (Workflow-Fit 1 and 4, Advisor 3
and 5) are answered together in §3–§6, because each is unusable without the
others. Revision 2 applies the eleven owner corrections recorded in §11.
**Authority applied:** Workflow-Fit decisions 2, 3, 5 and Advisor decisions 1,
2, 4 as recorded in their notes; the Slice 1 contracts (`4369089d`,
correction 30 at `4324cbdd`); Slice 2 (`8bd6ccf3`); the Phase 3 intake ruling
(`2bffc9cd`) `[V]`.
**Evidence labels:** `[V]` verified against the repository · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Can one research-only pilot produce ratified Workflow-Fit outcomes for one
governed task class, with every observation bound before execution to
exactly what was tested, with telemetry captured outside the tested workflow
and digested into the record before attestation, with every advisor-qualified
method and a declared challenger set exercised, and with no state that reads
as approval or as a quality verdict?** Yes, with one preregistered manifest
that fixes plan, advice, methods and roles, benchmark case set, capture
boundary, evaluator and aggregation references before any run; one
out-of-process capture boundary; and two honest limits: evaluator
independence is declared and unverified in 4A, and nothing is VERIFIED unless
the Trusted Evidence Authority issues a receipt for it.

---

## 1. Inventory: what exists, what is reused, what is missing

| Piece | Where `[V]` | Reuse | Gap |
|---|---|---|---|
| Execution record `ReasoningMethodExecutionRecord` v1 with `method`, `binding: BindingRef`, `task_class_digest`, `input_digest`, `model_ref`, `telemetry`, `self_reported_quality`, `issuer_identity`, `parent_record_digest`; evidence axes as class constants `OBSERVED / UNATTESTED / UNVERIFIED`; **one record per method per task class** (ballot 5.1-A) | `reasoning-method-governance/contracts/record.py:169-193`; governed adapter `experiments/workflow_fit_study/governed_adapter.py` | as is, at its existing aggregation boundary | carries no manifest, role, advisory or case-set identity |
| `ExecutionTelemetry` (`llm_calls`, `llm_calls_basis: CountBasis`, `token_usage: TokenUsageSnapshot`, `token_count_basis`, `capture_refs`) | `record.py:114-121` | as is; populated from the capture boundary (§4) | — |
| `AttestationEnvelope` (attester, `capture_boundary_ref`, `attested_fields`) and `VerificationEnvelope`; `EvidenceStatusView` computed by the engine; self-attestation and self-verification refused; unresolved issuers reported in `ignored_envelopes` | `contracts/envelopes.py`; ballot §4 | as is | **no attester exists**; **no adapter from a TEV receipt to a `VerificationEnvelope`** |
| Comparison engine `compare(request, *, produced_at)`, four `FitOutcome`s, `REQUESTER_ASSERTED` authority resolution, `RESEARCH_ONLY` scope; four-outcome fixtures from PR #1566 | `readiness-comparison/engine.py` (0.2.0); `tests/engine/test_four_outcomes_pr1566.py` | as is; the fixtures become the synthetic engine-coverage fixture (§8, A22) | quality claims have no envelope path |
| `ResearchComparisonPlan` with `baseline`, `recommended` (fenced), `ChallengerSamplingPolicy` (`PREREGISTERED / RISK_BASED / RANDOMIZED`, `declared_coverage_ref`), `plan_digest` | `contracts/plan.py`; ballot §8 | as is, embedded by value in the manifest (§3) | no link from a record to the plan; no coverage **report** |
| `AggregationRef` (`aggregation_id`, `aggregation_version`, `calculation_ref`); `ComparisonPolicy.quality_aggregation`; `MetricClaim.transformation_method = CALCULATED` with `calculation_ref` | `contracts/task_class.py`; governed adapter (`RESEARCH_MEAN`) | as the declared quality and resource aggregation references | resource aggregation is declared by the adapter only in prose (its sum over the case set) `[G]` |
| `TaskClassIdentity` binding domain, outcome, consequence, reversibility, requirements, tokens, population, `benchmark_set_ref`, `benchmark_set_digest`, `ComparisonPolicy` (sufficiency rule id and version, dimensions) → `task_class_digest` | `contracts/task_class.py:181-219` | as is | `benchmark_set_digest` names a set but carries no case list |
| `AssessedSystemBinding` (`configuration_id`, `configuration_digest`, `context_digest`, opaque `deployment_environment_ref`) | `governance-contracts/contracts/system_identity.py:260-288` | by `BindingRef` | no lifecycle state |
| `BenchmarkReference` (`benchmark_id`, `version`, `content_digest`, `issuer_ref`); Benchmark Registry canonical identity and lifecycle | `governance-contracts/contracts/evidence.py:318`; `benchmark-registry` | as the head of the benchmark manifest (§3.2) | **a `BenchmarkReference` cannot prove membership: it has no case list** `[G]` |
| Workflow-Fit harness: `TaskCase`, `StudyConfig`, `RunRecord` (`calls_runtime_reported` from `WorkflowResult.total_llm_calls`, `calls_harness_observed` from `_CountingClient`), `assess`; governed adapter summing `llm_calls` over the same case set per method | `experiments/workflow_fit_study/study.py`, `governed_adapter.py` | as the executor and adapter | `_CountingClient` is **the same process and trust domain** as the workflow (`study.py:141-145`): not a capture boundary |
| `WorkflowResult.total_llm_calls`, `quality_score` | `agentic/agentic_framework/reasoning_workflows.py:145` | retained only as labelled diagnostics (§4) | — |
| Context Minimization `ApiCallTokenRecord` (`logical_request_id`, `attempt_id`, `provider_id`, `AttemptStatus`, `provider_invoked`, token counts, `record_fingerprint`), `TokenCountBasis`, `UsageAvailability` | `context-minimization/token_accounting.py:135-455` | as the **shape** of a capture-boundary record; ballot §4 already names "a CM-TA1 `ApiCallTokenRecord` fingerprint set" as a `capture_boundary_ref` | no component records **another workflow's** calls from outside it `[G]` |
| Trusted Evidence Authority: `EvidenceTrustStage` (six stages), trust anchors, `TrustAnchorCapability`, `issue()` → `SignedEvidenceVerificationReceipt` | `trusted-evidence-authority/…/enums.py:27`, `authority/issuance.py:116` | the only verifier port | no anchor capability for reasoning-method telemetry; no receipt→envelope adapter `[G]` |
| Ratified rulings: four outcome names; per-class versioned sufficiency rule with no global default; efficiency as a property of the selection policy within the exact binding; advisor as a separate design-time capability; task-class identity coordinates; Phase 3 intake | Workflow-Fit §11.2/§11.3/§11.5; Advisor §8.1/§8.4; demo README | binding | — |

**Genuinely missing (all research-only, all in the new package of §7):** a
preregistered pilot manifest (§3.1), a benchmark manifest with the case list
(§3.2), a per-method pilot observation at Slice 1's aggregation boundary
(§3.3), an out-of-process capture boundary that populates telemetry and then
attests it (§4), an evaluator declaration (§5), a coverage report (§6.1) and
a neutral state ledger with lineage (§6.2). No Slice 1 or Slice 2 contract
changes.

---

## 2. Vocabulary carried unchanged

`FitOutcome` (four names), `SourceBasis`, `AttestationStatus`,
`VerificationStatus`, `CountBasis`, `UsageAvailabilityToken`, `SamplingKind`,
`AggregationRef`, `USAGE_SCOPE_RESEARCH_ONLY`, `AUTHORITY_RESOLUTION_BASIS_V1 =
"REQUESTER_ASSERTED"`, `AdvisoryClassification`, `AdvisoryEligibility`,
`RULE_DERIVED`, `COMPARISON_EVIDENCE_ABSENT`. No new label is a synonym of
any of these, and no lifecycle state names an outcome (§6.2).

**Numbers.** This document supplies **no owner-supplied numeric default,
threshold, sample size, coverage target or acceptance figure**. Observed
counts (calls, tokens, cases, methods) and caller-declared research
configuration (a task class's declared threshold, a case count) remain
numeric and are carried as validated integers or decimal strings where the
existing contracts already do so.

---

## 3. Decision 1 — Usage binding (Workflow-Fit 1)

### 3.1 Preregistered pilot manifest

Everything a pilot will do is fixed and digested **before execution** in one
`PilotStudyManifest`. No advisory, role or method can be attached
afterwards: an observation is admissible only if it names a manifest digest
that already existed, and the manifest carries no field that execution could
fill in.

```python
PILOT_MANIFEST_SCHEMA_VERSION = "workflow_fit_pilot.manifest.v1"

class PilotRole(str, Enum):                     # NON-EXCLUSIVE: one method may carry several
    GOVERNED_BASELINE = "GOVERNED_BASELINE"     # method == plan.baseline
    ADVISOR_QUALIFIED = "ADVISOR_QUALIFIED"     # method ∈ advisory.qualifying
    CHALLENGER = "CHALLENGER"                   # admissible catalog method ∉ advisory.qualifying

@dataclass(frozen=True)
class PilotMethodAssignment:
    method: ReasoningMethodRef                  # catalog ref + method_id + method_version; unique per manifest
    roles: tuple[PilotRole, ...]                # non-empty, sorted by member order, no repeats

@dataclass(frozen=True)
class CaptureBoundaryDeclaration:
    boundary_identity: str                      # the attester; must differ from record issuer and requester
    boundary_version: str
    process_separation_ref: str                 # how the boundary runs outside the workflow's process (declared, unverified in 4A)
    record_shape_ref: str                       # e.g. the ApiCallTokenRecord shape it emits
    attested_field_names: tuple[str, ...]       # exactly the ExecutionTelemetry fields it will populate and attest

@dataclass(frozen=True)
class PilotStudyManifest:
    schema_version: Literal["workflow_fit_pilot.manifest.v1"]
    manifest_id: str
    plan: ResearchComparisonPlan                # by value; plan_digest is therefore inside manifest_digest
    advisory_digest: Optional[str]              # required iff any assignment carries ADVISOR_QUALIFIED; None otherwise
    rule_set: Optional[RuleSetRef]              # the advisory's rule set, same rule
    methods: tuple[PilotMethodAssignment, ...]  # DEDUPLICATED by (method_id, method_version); ordered by sort key; every plan.recommended member present
    benchmark: BenchmarkManifest                # §3.2, by value; carries the complete ordered case-digest set
    capture_boundary: CaptureBoundaryDeclaration
    evaluator: QualityEvaluatorDeclaration      # §5
    resource_aggregation: AggregationRef        # how per-case resource counts become the record's telemetry (the adapter's sum over the case set)
    quality_aggregation: AggregationRef         # == plan.task_class.comparison_policy.quality_aggregation when that policy declares one
    usage_scope: Literal["RESEARCH_ONLY"]
    preregistered_by: str
    preregistered_at: datetime
    manifest_digest: str
```

**Constructor obligations.** Exactly one assignment carries
`GOVERNED_BASELINE` and its method equals `plan.baseline`
(`ROLE_INCONSISTENT`); `ADVISOR_QUALIFIED` appears only when
`advisory_digest` and `rule_set` are present, and never when they are absent
(`ADVISORY_REQUIRED`); no method appears twice (`METHOD_DUPLICATE`); every
`plan.recommended` member is assigned; `benchmark.benchmark_manifest_digest ==
plan.task_class.benchmark_set_digest` (`BENCHMARK_MANIFEST_MISMATCH`);
`quality_aggregation` equals the task class's declared aggregation when one
is declared (`AGGREGATION_MISMATCH`); `usage_scope` is the constant.
**Role deduplication.** Roles are non-exclusive: a baseline that the advisory
did not qualify carries `GOVERNED_BASELINE` and `CHALLENGER`; a qualified
baseline carries `GOVERNED_BASELINE` and `ADVISOR_QUALIFIED`. Each method is
run once and its one record serves every role it carries; coverage (§6.1)
counts methods per role, never runs. Whether the assigned roles match the
referenced advisory is checked by the validation operation (§3.4), which
receives the advisory.

### 3.2 Benchmark manifest

```python
BENCHMARK_MANIFEST_SCHEMA_VERSION = "workflow_fit_pilot.benchmark_manifest.v1"

@dataclass(frozen=True)
class BenchmarkManifest:
    schema_version: Literal["workflow_fit_pilot.benchmark_manifest.v1"]
    benchmark: BenchmarkReference               # existing head: benchmark_id, version, content_digest, issuer_ref
    case_digests: tuple[str, ...]               # COMPLETE, ascending by code point, unique, non-empty; one sha-256 per case
    case_count: int                             # == len(case_digests); validated non-negative integer
    issuer_identity: str
    issued_at: datetime
    benchmark_manifest_digest: str
```

A `BenchmarkReference` alone proves nothing about membership because it has
no case list; the manifest does. `case_digests` is the only source of
membership, and the task class's `benchmark_set_digest` must equal
`benchmark_manifest_digest` so the task-class identity names exactly this
case set. Registry registration of the reference is a later step `[G]`.

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
    case_set_digest: str                        # == manifest.benchmark.benchmark_manifest_digest: the complete ordered case set
    case_count: int                             # == manifest.benchmark.case_count; validated non-negative integer
    resource_aggregation: AggregationRef        # == manifest.resource_aggregation
    quality_aggregation: AggregationRef         # == manifest.quality_aggregation
    record_digest: str                          # the aggregated ReasoningMethodExecutionRecord for this method
    attestation_envelope_digest: Optional[str]  # the capture boundary's envelope over record_digest, when issued
    quality_claim_digest: str                   # the MetricClaim the declared evaluator produced for this record
    diagnostics: WorkflowReportedDiagnostics
    observed_at: datetime
    observation_digest: str
```

### 3.4 Validation operation

`validate_observation(observation, *, manifest, plan, record, benchmark,
quality_claim, advisory=None)` receives **every object needed to verify the
observation's claims** and refuses any missing or mismatched one. It never
infers membership, roles or advice from digests alone.

| Check | Refusal |
|---|---|
| `observation.manifest_digest == manifest.manifest_digest`; `manifest.plan == plan` | `MANIFEST_MISMATCH` |
| `record.record_digest == observation.record_digest`; `record.method == observation.method`; `record.task_class_digest`, `record.binding`, `record.model_ref` equal the observation's and the plan's | `RECORD_MISMATCH` |
| `benchmark.benchmark_manifest_digest == observation.case_set_digest == plan.task_class.benchmark_set_digest`; `benchmark.case_count == observation.case_count` | `BENCHMARK_MANIFEST_MISMATCH` |
| `quality_claim` digest equals `observation.quality_claim_digest`; its `calculation_ref` names `manifest.quality_aggregation.calculation_ref`; its evaluator fields match `manifest.evaluator` | `QUALITY_CLAIM_MISMATCH` |
| observation roles equal the manifest assignment's roles for this method | `ROLE_INCONSISTENT` |
| any role is `ADVISOR_QUALIFIED` ⇒ `advisory` supplied, `advisory.advisory_digest == manifest.advisory_digest`, `advisory.rule_set == manifest.rule_set`, `advisory.task_class_digest == plan.task_class.task_class_digest`, and this method ∈ `advisory.qualifying`; conversely a method ∈ `advisory.qualifying` must carry the role | `ADVISORY_REQUIRED` / `ADVISORY_MISMATCH` |
| any role is `CHALLENGER` ⇒ method ∉ `advisory.qualifying` (when an advisory exists) and method ∈ the catalog's admissible set | `ROLE_INCONSISTENT` |
| `observation.attestation_envelope_digest` set ⇒ the envelope is supplied, its `record_digest == record.record_digest`, its `attester_identity == manifest.capture_boundary.boundary_identity` and its `attested_fields == manifest.capture_boundary.attested_field_names` | `ATTESTATION_MISMATCH` |
| the manifest's `preregistered_at` precedes `record.captured_at` and `observation.observed_at` | `MANIFEST_NOT_PRIOR` |

**Unresolved 3.1 — where the binding lives.**

| Option | Consequence |
|---|---|
| A. Add manifest, roles and advisory fields to `ReasoningMethodExecutionRecord` | one object, but a Slice 1 schema change and the record would carry advisor output across the ratified execution-record boundary |
| B. Manifest plus a separate `PilotObservation` referencing the record by digest (above) | no Slice 1 change; the record stays neutral; validation needs every object, which §3.4 requires anyway |

**Recommendation: B.**

---

## 4. Decision 2 — Trust controls (Workflow-Fit 4)

**Capture outside the evaluated workflow, then attest.** The pilot introduces
one component, the **capture boundary** declared in the manifest: a
provider-client proxy running in a separate process from the workflow under
test that sees every model call the workflow makes and records per-call
`ApiCallTokenRecord`-shaped entries (request id, attempt, provider, status,
provider-reported usage with its `UsageAvailability`).

**Order of operations, binding.** (1) The workflow runs behind the boundary
over the case set. (2) The adapter builds `ExecutionTelemetry` **from the
boundary's records**: `llm_calls` = the boundary's aggregated call count
under `manifest.resource_aggregation`, `llm_calls_basis = CALLER_SUPPLIED`
with `capture_refs` naming the boundary's record fingerprints;
`token_usage` from provider-reported usage with `token_count_basis =
PROVIDER_REPORTED` where available, else `UNKNOWN` `[I]`. (3) The execution
record is constructed and **digested with those values**. (4) The boundary
issues an `AttestationEnvelope` over that `record_digest` with
`attested_fields == manifest.capture_boundary.attested_field_names`,
`capture_boundary_ref` = its fingerprint set, and `attester_identity` =
`boundary_identity`, which must differ from the record's `issuer_identity`
and the request's `requester_identity` (Slice 1 `SELF_ATTESTATION`
otherwise) `[V]`. **An envelope never carries a competing value**: it attests
the values already in the record. Runtime-reported and in-process counts are
kept only in `WorkflowReportedDiagnostics`, labelled
`RUNTIME_REPORTED_DIAGNOSTIC`, and enter neither telemetry nor any envelope.

**Consistency versus authenticity, stated precisely.**

| Claim | What proves it | Status in the pilot |
|---|---|---|
| The record's `llm_calls` and token totals are the boundary's observations | the boundary's `AttestationEnvelope`, resolved as an authority in the request | `ATTESTED` on the declared fields only; everything else `UNATTESTED` |
| The boundary is who it says, ran outside the workflow's process, and its records were not altered | a Trusted Evidence Authority receipt over the attestation, adapted to a `VerificationEnvelope` | **`UNVERIFIED` in 4A**; `process_separation_ref` is declared, not verified; the engine's resolution stays `REQUESTER_ASSERTED` |
| The workflow's own `total_llm_calls` | nothing | diagnostic only; never evidence |
| The quality value | the evaluator declaration (§5) | evaluator-produced; independence declared and unverified; never `ATTESTED` or `VERIFIED` in 4A |
| A resolved authority is genuine | nothing inside the engine (ballot §3) | requester-asserted; reported as such on every result |

**What an existing envelope proves.** An `AttestationEnvelope` proves that a
named capture boundary asserts the attested fields for that record digest;
the engine proves only that the envelope is consistent with the record and
that the attester is one the requester resolved. A `VerificationEnvelope`
proves that a named verifier asserts it verified the attestation. Neither
proves the identity behind the name. `VERIFIED` is reachable only through
the Trusted Evidence Authority's `issue()`; the pilot has no other verifier.

**Who may issue.** Attestation: the declared capture boundary, never the
workflow, harness, adapter, evaluator or requester. Verification: the
Trusted Evidence Authority only, under a trust anchor whose
`TrustAnchorCapability` covers reasoning-method telemetry, which does not
exist yet `[G]`.

**Unresolved 4.1 — depth of trust in 4A.**

| Option | Consequence |
|---|---|
| A. No capture boundary: everything `UNATTESTED / UNVERIFIED`, stated | cheapest; the pilot measures nothing the workflow could not have reported itself; decision 4 stays open |
| B. Capture boundary populates telemetry and attests it; verification absent and stated | telemetry `ATTESTED` on the declared fields; quality declared-unverified; one new component; no TEV work |
| C. B plus a TEV anchor capability and a receipt→`VerificationEnvelope` adapter | `VERIFIED` telemetry; adds a TEV capability member and an adapter, each needing its own ratification |

**Recommendation: B**, with C recorded as the next trust slice. The pilot
report prints the three evidence axes per field and the diagnostics under
their label; no summary may say "trusted" or "verified" for any field.

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
    model_ref: Optional[str]                    # required iff kind == LLM: the model the evaluator called; compared only to the tested workflow's model_ref
    separation_declaration_ref: str             # declares a distinct process and call path with no shared prompt state; unverified
    scoring_instruction_digest: str             # digest of the scoring instructions, which name benchmark_manifest_digest and the sufficiency rule
    benchmark_manifest_digest: str              # == the manifest's benchmark
    calibration_evidence_ref: str               # calibration study reference for this evaluator version on this benchmark; may be blank, and blankness is reported
    independence_status: Literal["DECLARED_UNVERIFIED"]   # the only value in 4A
    declaration_digest: str
```

**Obligations.** `kind == LLM` requires `model_ref`; other kinds refuse it
(`EVALUATOR_KIND_INCONSISTENT`). `evaluator_identity` must differ from the
record's `issuer_identity`, the request's `requester_identity` and the
capture boundary's identity, and an LLM evaluator's `model_ref` is compared
to the tested workflow's `model_ref` only to report sameness, never to an
identity string (`EVALUATOR_SELF_LOOP` when identities coincide;
`EVALUATOR_SHARES_MODEL` reported, not refused). A `MetricClaim` produced
under this declaration carries `transformation_method = CALCULATED` and the
manifest's `quality_aggregation.calculation_ref`.

**Unresolved 5.1 — the claim's `source_basis`.**

| Option | Consequence |
|---|---|
| A. `REPORTED` for every evaluator-produced claim in 4A | honest by construction; the engine does not read `source_basis` for the outcome, so results are unaffected; every quality figure is labelled reported |
| B. `OBSERVED`, with the report stating separately that evaluator independence and identity are requester-asserted and unverified | matches the adapter's current practice; risks reading as measured rather than judged |

**Recommendation: A.** Under either option the report states, beside every
quality figure, `independence_status = DECLARED_UNVERIFIED` and whether
`calibration_evidence_ref` is blank. Slice 1 has no envelope for quality
claims, so no quality figure can be `ATTESTED` or `VERIFIED` in 4A `[G]`.

---

## 6. Decisions 3 and 4 — Pilot composition and lifecycle

### 6.1 Composition (Advisor 3)

The manifest fixes the composition before any run: the **governed baseline**
(`plan.baseline`); **every method in the advisory's qualifying set** for the
class's profile, by advisory digest (`plan.recommended` stays fenced as
intent, not selection); and **challengers** = every admissible catalog
method not in the qualifying set (exhaustive, `PREREGISTERED`). Roles are
non-exclusive and methods are deduplicated (§3.1). When the qualifying set
is empty (8.1-A) the manifest carries no `ADVISOR_QUALIFIED` role, and the
pilot runs the baseline and challengers and reports `NO_QUALIFYING_METHOD`.

**Coverage report, mandatory, no target.** Counts are validated
non-negative integers over deduplicated methods.

```python
@dataclass(frozen=True)
class ChallengerCoverageReport:
    manifest_digest: str
    admissible_method_count: int
    methods_assigned: int                       # deduplicated
    methods_with_record: int                    # deduplicated; one record each
    baseline_has_record: bool
    qualified_declared: int                     # methods carrying ADVISOR_QUALIFIED
    qualified_with_record: int
    challengers_declared: int                   # methods carrying CHALLENGER (a non-qualified baseline counts once here and once as baseline)
    challengers_with_record: int
    methods_without_record: tuple[ReasoningMethodRef, ...]
    sampling: ChallengerSamplingPolicy
```

**Anti-gaming rule.** The pilot report never presents qualifying-set success
without, on the same line, `qualified_declared / admissible_method_count`,
set precision (qualified methods with a sufficient and undominated outcome,
over qualified methods with a record) and `challengers_with_record /
challengers_declared` (advisor note §6). A large qualifying set shows as low
precision and a thin challenger pool as low coverage. Set precision counts
`SUFFICIENT_PARETO_EFFICIENT` only; `SUFFICIENT_RESOURCE_DOMINATED` is
sufficient but dominated and is reported under its own name.

**Unresolved 6.1 — sampling kind for the first pilot.**

| Option | Consequence |
|---|---|
| A. `PREREGISTERED`, exhaustive: every admissible non-qualified method is a challenger | with the seven-method research catalog, full coverage; no sampling to game |
| B. `RANDOMIZED` with a seeded subset | fewer runs; coverage below full; seed and coverage declared |
| C. `RISK_BASED` by consequence class | needs a risk rule that does not exist |

**Recommendation: A** for 4A; B and C stay available through the existing
policy contract when catalogs grow.

### 6.2 Lifecycle (Advisor 5, research scope only)

Lifecycle states are **neutral**: none names an outcome, and the exact
`FitOutcome` is carried separately and verbatim.

```python
class PilotConfigurationState(str, Enum):
    PROPOSED = "PROPOSED"                       # manifest digested; nothing run
    UNDER_TEST = "UNDER_TEST"                   # at least one observation validated; no engine result yet
    EVALUATED = "EVALUATED"                     # an engine result assessed this method: fit_outcome is one of the three assessed outcomes
    INCONCLUSIVE = "INCONCLUSIVE"               # the engine returned COMPARISON_EVIDENCE_ABSENT or a refusal for this method
    REVISED = "REVISED"                         # superseded: a successor manifest exists (see revision scope)

class RevisionScope(str, Enum):                 # what changed; several may apply
    CONFIGURATION = "CONFIGURATION"             # binding / configuration_digest
    TASK_CLASS = "TASK_CLASS"                   # task_class_digest
    BENCHMARK_MANIFEST = "BENCHMARK_MANIFEST"
    COMPARISON_PLAN = "COMPARISON_PLAN"
    SUFFICIENCY_RULE = "SUFFICIENCY_RULE"

@dataclass(frozen=True)
class PilotConfigurationStateRecord:
    schema_version: Literal["workflow_fit_pilot.state.v1"]
    manifest_digest: str
    method: ReasoningMethodRef
    roles: tuple[PilotRole, ...]
    state: PilotConfigurationState
    fit_outcome: Optional[FitOutcome]           # required for EVALUATED (never COMPARISON_EVIDENCE_ABSENT there) and for INCONCLUSIVE when the engine returned that outcome; None otherwise
    refusal_codes: tuple[str, ...]              # engine refusal codes for INCONCLUSIVE; empty otherwise
    result_digest: Optional[str]                # the ReadinessComparisonResult that set EVALUATED or INCONCLUSIVE
    predecessor_state_digest: Optional[str]     # lineage within one manifest, and from a successor's PROPOSED back to the REVISED record
    predecessor_manifest_digest: Optional[str]  # set on a successor manifest's PROPOSED record
    successor_manifest_digest: Optional[str]    # set on a REVISED record
    successor_state_digest: Optional[str]       # set on a REVISED record once the successor's PROPOSED record exists
    revision_scope: tuple[RevisionScope, ...]   # non-empty on REVISED and on a successor's PROPOSED; empty otherwise
    usage_scope: Literal["RESEARCH_ONLY"]
    approval_status: Literal["NONE"]            # a constant, so a consumer must change a type to read approval
    recorded_by: str
    recorded_at: datetime
    state_digest: str
```

**Closed transitions.** `PROPOSED → UNDER_TEST → EVALUATED | INCONCLUSIVE`;
any state `→ REVISED`. `EVALUATED` and `INCONCLUSIVE` never transition to
each other or to `UNDER_TEST`: a different result requires a different
manifest, hence `REVISED`. **Revision scope** covers any change to the
configuration (`binding_digest` / `configuration_digest`), the task class,
the benchmark manifest, the comparison plan or the sufficiency rule; any of
these yields a new `manifest_digest`, a `REVISED` record on the predecessor
naming `successor_manifest_digest` and `revision_scope`, and a `PROPOSED`
record on the successor naming `predecessor_manifest_digest` and
`predecessor_state_digest`. Lineage is therefore bound to manifest and state
digests on both sides, never to a binding digest alone.

**The configuration is identified before testing** because `PROPOSED`
requires the manifest digest and refuses any observation. **No state is an
approval and no state is a verdict**: `approval_status` is the constant
`"NONE"`, `usage_scope` is `RESEARCH_ONLY`, `SUFFICIENT_RESOURCE_DOMINATED`
is never described as qualified, and no Decision Authority, Constitution
binding or `deployment_environment_ref` semantics are touched. The Slice 1
`SUFFICIENT_PARETO_EFFICIENT` fence (ballot §8) stands.

**Unresolved 6.2 — placement of the state ledger.**

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
digested, ordered and counted, its `benchmark_manifest_digest` set as the
task class's `benchmark_set_digest`; **governed baseline** `linear_chain@1`
as the adapter already uses `[V]`; **advisor-qualified methods** from one
advisory over the class's profile under `rules.research.v0`, by digest;
**challengers** every other admissible catalog method (6.1-A); **one capture
boundary**; **one declared evaluator**; **aggregation references** the
adapter's sum over the case set for resources and the declared research mean
for quality. Output: one `ReadinessComparisonResult` with **whichever
outcomes its evidence warrants**, one coverage report, one state record per
method, and a pilot report that prints evidence axes per field and
diagnostics under their label. A real pilot never manufactures missing
evidence to obtain `COMPARISON_EVIDENCE_ABSENT`; the four-outcome
demonstration lives in a synthetic engine-coverage fixture (A22).

**Execution** happens only in the research harness with a caller-supplied
provider client behind the capture boundary. **Not** through Agent Runtime,
Agentic Proposer or Agent Workforce Composer; no runtime integration.

**Package.** `packages/capabilities/workflow-fit-pilot` →
`ugence-workflow-fit-pilot`, depending on `ugence-reasoning-method-governance`,
`ugence-readiness-comparison`, `ugence-reasoning-method-advisor`,
`ugence-governance-contracts`, `ugence-jcs`; the capture boundary in the same
package as a subpackage with no import of `agentic`; the harness stays in
`experiments/`. Boundary test as in Slices 1 and 2.

**In scope:** §3.1 manifest, §3.2 benchmark manifest, §3.3 observation and
diagnostics, §3.4 validation operation; §4 capture boundary, telemetry
population and attestation issuance; §5 evaluator declaration; §6.1 coverage
report; §6.2 state ledger with lineage; a pilot runner that preregisters the
manifest, runs the methods through the harness behind the boundary, adapts
records, calls `compare()`, and renders the report; CI gate; wheel
self-check.

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
| A2 | manifest with an `ADVISOR_QUALIFIED` role and `advisory_digest=None`; or with `advisory_digest` set and no such role | `ADVISORY_REQUIRED` |
| A3 | manifest listing one method twice | `METHOD_DUPLICATE` |
| A4 | manifest whose `benchmark.benchmark_manifest_digest ≠ plan.task_class.benchmark_set_digest` | `BENCHMARK_MANIFEST_MISMATCH` |
| A5 | benchmark manifest with unsorted, repeated or empty `case_digests`, or `case_count ≠ len` | refused at construction |
| A6 | observation naming a `manifest_digest` that no manifest supplied to validation carries; or an observation whose `observed_at` precedes `manifest.preregistered_at` | `MANIFEST_MISMATCH` / `MANIFEST_NOT_PRIOR` |
| A7 | observation with `case_set_digest ≠ benchmark_manifest_digest` or `case_count` mismatch | `BENCHMARK_MANIFEST_MISMATCH` |
| A8 | observation whose roles differ from the manifest assignment; or an `ADVISOR_QUALIFIED` observation whose supplied advisory did not qualify the method; or validation called without the advisory for such a role; or a method in `advisory.qualifying` assigned without the role | `ROLE_INCONSISTENT` / `ADVISORY_MISMATCH` / `ADVISORY_REQUIRED` |
| A9 | validation called with any required object omitted, or with a record whose digest, method, binding, task class or model differs | refused (`RECORD_MISMATCH` etc.); never a pass by omission |
| A10 | quality claim whose `calculation_ref` is not the manifest's `quality_aggregation.calculation_ref` | `QUALITY_CLAIM_MISMATCH` |
| A11 | boundary in a separate process observes N calls while the workflow reports M ≠ N | record telemetry carries N with `capture_refs` naming the boundary records; diagnostics carry M under `RUNTIME_REPORTED_DIAGNOSTIC`; the attestation is over the record digest computed with N; `EvidenceStatusView` shows `ATTESTED` on the declared fields |
| A12 | an envelope whose `attested_fields` differ from the manifest's declaration, or over a record digest other than the observation's | `ATTESTATION_MISMATCH` |
| A13 | attestation whose `attester_identity` equals the record issuer or the requester | Slice 1 `SELF_ATTESTATION`, unchanged |
| A14 | attester not in `resolved_authorities` | listed in `ignored_envelopes`; status `UNATTESTED` |
| A15 | any pilot result | every `EvidenceStatusView.verification_status == UNVERIFIED`; the report never prints "verified" or "trusted"; every quality figure carries `DECLARED_UNVERIFIED` and the calibration-blank flag |
| A16 | `EvaluatorKind.LLM` without `model_ref`, or `HUMAN` with one | `EVALUATOR_KIND_INCONSISTENT` |
| A17 | evaluator identity equal to the record issuer, the requester or the boundary | `EVALUATOR_SELF_LOOP`; an LLM evaluator whose `model_ref` equals the workflow's is reported `EVALUATOR_SHARES_MODEL`, not refused |
| A18 | coverage report on a manifest with three qualified methods over a seven-method catalog under 6.1-A, baseline not qualified | `admissible_method_count=7`, `methods_assigned=7`, `qualified_declared=3`, `challengers_declared=4` (the baseline counted once as challenger and once as baseline), all `_with_record` equal after the run, `methods_without_record=()`; set precision printed beside qualifying-set success |
| A19 | the same manifest with one challenger's record missing | `challengers_with_record=3`, `methods_without_record` names it; no success line without the coverage figures; negative or non-integer counts refused at construction |
| A20 | empty qualifying set | no `ADVISOR_QUALIFIED` role; baseline and challengers run; `NO_QUALIFYING_METHOD` reported; no primary anywhere |
| A21 | state ledger: observation recorded against a `PROPOSED` method without transition; `EVALUATED → INCONCLUSIVE`; `EVALUATED` with `fit_outcome=None` or `COMPARISON_EVIDENCE_ABSENT`; `INCONCLUSIVE` with neither that outcome nor a refusal code; `SUFFICIENT_RESOURCE_DOMINATED` rendered with the word "qualified" | each refused |
| A22 | **synthetic engine-coverage fixture** (the PR #1566 four-outcome fixtures, not a pilot run) | exactly the four `FitOutcome` names appear; `result_digest` stable across two runs at one `produced_at` |
| A23 | real pilot runner end to end on the harness fixtures with a stub client behind the boundary | only the outcomes its evidence warrants appear; no `COMPARISON_EVIDENCE_ABSENT` unless evidence is genuinely absent; `authority_resolution_basis == REQUESTER_ASSERTED`; one record and one observation per method |
| A24 | revision: change any of configuration, task class, benchmark manifest, plan or sufficiency rule | new `manifest_digest`; predecessor `REVISED` with `successor_manifest_digest`, `successor_state_digest` and a non-empty `revision_scope`; successor `PROPOSED` with `predecessor_manifest_digest` and `predecessor_state_digest`; a change outside those five scopes with the same manifest digest is refused |
| A25 | any state record | `approval_status == "NONE"`, `usage_scope == RESEARCH_ONLY`; field-set test finds no `approved`, `eligible`, `qualified`, `production` field; no state name equals a `FitOutcome` name |
| A26 | AST boundary scan of the package | no `agentic`, runtime, proposer, composer, readiness, `governed_value`, network or LLM SDK import; no clock read |
| A27 | numeric scan of `src/` | no owner-supplied numeric default, threshold, sample size, coverage target or acceptance figure; integer fields are counts validated non-negative |

---

## 9. Explicitly excluded from 4A

No production authority or approval; no benchmark-derived advisor change; no
readiness composite; no runtime execution or integration; no TEV capability
or receipt adapter; no quality-claim envelopes; no benchmark-registry
registration; no change to any Slice 1 or Slice 2 contract; no LLM-based
selection; no owner-supplied numeric default, threshold, sample size,
coverage target or acceptance figure.

---

## 10. Owner ballot `[R]`

1. **Usage binding.** Ratify §3: a preregistered `PilotStudyManifest` (3.1-B)
   digested before execution that binds the comparison plan, the exact
   advisory and rule-set digests where advice is used, the deduplicated
   methods with their non-exclusive roles, the benchmark manifest with its
   complete ordered case-digest set, the capture-boundary and evaluator
   declarations and the resource and quality aggregation references; one
   `PilotObservation` per method at Slice 1's aggregation boundary
   referencing that manifest; and a validation operation that receives
   every object it needs and refuses omission. No execution-record change.
2. **Trust controls.** Ratify §4 and §5: the declared out-of-process capture
   boundary populates `ExecutionTelemetry` before the record is digested and
   then attests those values on that record digest (4.1-B); runtime-reported
   counts are retained only as labelled diagnostics; the Trusted Evidence
   Authority is the only verifier and issues nothing in 4A, so every field
   stays `UNVERIFIED`; evaluator independence is `DECLARED_UNVERIFIED`,
   evaluator-produced claims carry `source_basis = REPORTED` (5.1-A), and the
   report prints the three axes per field.
3. **Pilot composition.** Ratify §6.1: governed baseline, every
   advisor-qualified method by advisory digest, and exhaustive preregistered
   challengers (6.1-A) as non-exclusive roles over deduplicated methods; a
   mandatory coverage report with validated integer counts; no success
   figure without set precision and challenger coverage; the four-outcome
   demonstration only as a synthetic engine fixture.
4. **Lifecycle.** Ratify §6.2: the five neutral states with closed
   transitions and the `FitOutcome` carried separately; the configuration
   identified at `PROPOSED` before any run; revision for any change to
   configuration, task class, benchmark manifest, comparison plan or
   sufficiency rule, with lineage bound to predecessor and successor
   manifest and state digests; `approval_status = "NONE"` constant; the
   ledger placed in the pilot package (6.2-A); ballot 8.2 and production
   approval remain open.

**Definition of done for 4A** (after ratification): package
`ugence-workflow-fit-pilot` with the §3–§6 contracts, the capture boundary,
the pilot runner over the harness, every §8 row as an executable test, a CI
gate in the Slice 1 pattern, and a wheel self-check. No owner-supplied
numeric figure.

---

## 11. Correction record (revision 2, owner instruction, 2026-09-02)

| # | Before | After |
|---|---|---|
| 1 | No preregistered manifest; an arm could name an advisory after the fact | `PilotStudyManifest` digested before execution binding plan, advisory and rule-set digests, deduplicated methods and roles, benchmark manifest, boundary and evaluator declarations, aggregation references; observations reference its digest; `MANIFEST_NOT_PRIOR` (§3.1, §3.4) |
| 2 | Observation described one case and one invocation with a singular `case_digest` | Slice 1's one-record-per-method boundary retained; `case_set_digest` and `case_count` over the complete ordered set; resource and quality aggregation references bound (§3.3) |
| 3 | Membership inferred from `benchmark_set_digest` | `BenchmarkManifest` carrying the exact ordered case digests; validation receives it (§3.2, §3.4) |
| 4 | Envelope carried the boundary's count as a competing value against the record's | boundary values populate `ExecutionTelemetry` before digesting; the envelope attests those values; runtime counts only as `RUNTIME_REPORTED_DIAGNOSTIC` (§4) |
| 5 | `validate_against_plan(observation, plan, record)` | `validate_observation` receiving manifest, plan, record, benchmark manifest, quality claim and advisory when applicable; refuses omission or mismatch (§3.4) |
| 6 | Five non-blank fields promoted an evaluator to `INDEPENDENT_UNVERIFIED`; identity compared to `model_ref` | `independence_status` fixed at `DECLARED_UNVERIFIED`; `EvaluatorKind` and `model_ref` for LLM evaluators; identity and model compared only within their own types; claims `REPORTED` (5.1-A) (§5) |
| 7 | `FAILED` and `RESEARCH_QUALIFIED` states named outcomes | `PROPOSED / UNDER_TEST / EVALUATED / INCONCLUSIVE / REVISED`; `fit_outcome` carried separately; `SUFFICIENT_RESOURCE_DOMINATED` never called qualified (§6.2, A21, A25) |
| 8 | Revision covered only `configuration_digest` with `successor_binding_digest` | `RevisionScope` over configuration, task class, benchmark manifest, plan and sufficiency rule; lineage by predecessor and successor manifest and state digests (§6.2, A24) |
| 9 | Exclusive arm kinds; decimal-string counts | Non-exclusive `PilotRole`s with stated deduplication; validated non-negative integer counts; exhaustive challengers kept (§3.1, §6.1) |
| 10 | "All four outcomes appear" expected of the real pilot | Moved to a synthetic engine-coverage fixture (A22); the real pilot emits only warranted outcomes (A23, §7) |
| 11 | "No numeric figure of any kind" | "No owner-supplied numeric default, threshold, sample size, coverage target or acceptance figure"; observed counts and caller-declared configuration remain numeric (§2, §7, §9, A27) |

The four ballot items of §10 were revised accordingly and remain `[R]`.
Nothing is ratified by this revision.
