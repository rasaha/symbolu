# Trusted Workflow-Fit Pilot (Phase 4A) — Commissioning Specification and Ballot

**Status:** `[R]` — awaiting the four-item owner ballot in §10. **Nothing here
is implemented.** This document commissions one research-only pilot package
and one gate, and nothing else. It replaces further scoping notes: the four
open decisions it resolves (Workflow-Fit 1 and 4, Advisor 3 and 5) are
answered together in §3–§6, because each is unusable without the others.
**Authority applied:** Workflow-Fit decisions 2, 3, 5 and Advisor decisions 1,
2, 4 as recorded in their notes; the Slice 1 contracts (`4369089d`,
correction 30 at `4324cbdd`); Slice 2 (`8bd6ccf3`); the Phase 3 intake ruling
(`2bffc9cd`) `[V]`.
**Evidence labels:** `[V]` verified against the repository · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Can one research-only pilot produce the four ratified Workflow-Fit outcomes
for one governed task class with every observation bound to exactly what was
tested, with telemetry captured outside the tested workflow, with every
advisor-qualified method and a declared challenger set exercised, and with no
state that reads as approval?** Yes, with two additions to what exists (a
pilot-observation binding and an out-of-process capture boundary) and one
honest limit: quality remains evaluator-reported unless the §5 controls hold,
and nothing in the pilot is VERIFIED unless the Trusted Evidence Authority
issues a receipt for it.

---

## 1. Inventory: what exists, what is reused, what is missing

| Piece | Where `[V]` | Reuse | Gap |
|---|---|---|---|
| Execution record `ReasoningMethodExecutionRecord` v1 with `method`, `binding: BindingRef`, `task_class_digest`, `input_digest`, `model_ref`, `telemetry`, `self_reported_quality`, `issuer_identity`, `parent_record_digest`; evidence axes as class constants `OBSERVED / UNATTESTED / UNVERIFIED` | `reasoning-method-governance/contracts/record.py:169-193` | as is | carries no plan, arm, advisory or case identity |
| `ExecutionTelemetry` (`llm_calls`, `llm_calls_basis: CountBasis`, `token_usage: TokenUsageSnapshot`, `token_count_basis`, `capture_refs`) | `record.py:114-121` | as is; `CountBasis` mirrors Context Minimization's `TokenCountBasis` (`CALLER_SUPPLIED`, `INJECTED_COUNTER`, `PROVIDER_REPORTED`, …) | — |
| `AttestationEnvelope` (attester, `capture_boundary_ref`, `attested_fields`) and `VerificationEnvelope` (verifier, `attestation_envelope_digest`); `EvidenceStatusView` computed by the engine; self-attestation and self-verification refused; unresolved issuers reported in `ignored_envelopes` | `contracts/envelopes.py`; ballot §4 | as is | **no attester exists**; **no adapter from a TEV receipt to a `VerificationEnvelope`** |
| Comparison engine `compare(request, *, produced_at)` with four `FitOutcome`s, `REQUESTER_ASSERTED` authority resolution, `RESEARCH_ONLY` scope | `readiness-comparison/engine.py` (0.2.0) | as is | quality claims have no envelope path: evidence status covers records only |
| `ResearchComparisonPlan` with `baseline`, `recommended` (fenced), `ChallengerSamplingPolicy` (`PREREGISTERED / RISK_BASED / RANDOMIZED`, `declared_coverage_ref`), `plan_digest` | `contracts/plan.py`; ballot §8 | as is | no link from a record to the plan it ran under; no coverage **report**, only a declaration by reference |
| `TaskClassIdentity` binding domain, outcome, consequence, reversibility, requirements, tokens, population, `benchmark_set_ref`, `benchmark_set_digest`, `ComparisonPolicy` (sufficiency rule id and version, dimensions) → `task_class_digest` | `contracts/task_class.py:181-219` | as is: the digest already covers the benchmark set and the sufficiency-rule version | — |
| `AssessedSystemBinding` (`binding_id`, `tenant_id`, `subject_id`, `context_digest`, `system_id`, `system_version`, `configuration_id`, `configuration_digest`, opaque `deployment_environment_ref`) | `governance-contracts/contracts/system_identity.py:260-288` | by `BindingRef` (`binding_digest`, `configuration_digest`, `context_digest`) | no lifecycle state; `deployment_environment_ref` is not a state (ballot §8) |
| `BenchmarkReference` (`benchmark_id`, `version`, `content_digest`, `issuer_ref`) and the Benchmark Registry's canonical identity and lifecycle | `governance-contracts/contracts/evidence.py:318`; `benchmark-registry` | `benchmark_set_digest` on the task class is the pilot's fixed benchmark identity | the harness's case set has no registered benchmark identity `[G]` |
| Workflow-Fit harness: `TaskCase`, `StudyConfig`, `RunRecord` (`calls_runtime_reported` from `WorkflowResult.total_llm_calls`, `calls_harness_observed` from `_CountingClient`), `assess`, governed adapter to records and claims | `experiments/workflow_fit_study/study.py`, `governed_adapter.py` | as the executor and adapter | `_CountingClient` is **the same process and trust domain** as the workflow (its own docstring `study.py:141-145`): it is not a capture boundary |
| `WorkflowResult.total_llm_calls`, `quality_score` (self-reported) | `agentic/agentic_framework/reasoning_workflows.py:145` | carried as `self_reported_quality`; never read by the engine | — |
| Context Minimization `ApiCallTokenRecord` (`logical_request_id`, `attempt_id`, `provider_id`, `AttemptStatus`, `provider_invoked`, token counts, `record_fingerprint`), `ProviderTokenUsage`, `TokenCountBasis`, `UsageAvailability` | `context-minimization/token_accounting.py:135-455` | as the **shape** of a capture-boundary record; `capture_boundary_ref` in ballot §4 already names "a CM-TA1 `ApiCallTokenRecord` fingerprint set" | the CM adapter records its own calls; no component records **another workflow's** calls from outside it `[G]` |
| Trusted Evidence Authority: `EvidenceTrustStage` (six stages), trust anchors, `TrustAnchorCapability`, `issue()` producing a `SignedEvidenceVerificationReceipt` | `trusted-evidence-authority/…/enums.py:27`, `authority/issuance.py:116` | the only verifier port | no anchor capability for reasoning-method telemetry; no receipt→envelope adapter `[G]` |
| Ratified rulings: four outcome names; per-class versioned sufficiency rule, no global default, high-consequence classes need admitted evidence; efficiency is a property of the selection policy within the exact binding; advisor is a separate design-time capability; task-class identity coordinates | Workflow-Fit §11.2/§11.3/§11.5; Advisor §8.1/§8.4 | binding | — |

**Genuinely missing (all research-only, all in the new package of §7):** a
pilot-observation binding (§3), an out-of-process capture boundary that issues
attestations (§4), a quality-evaluator declaration (§5), a pilot arm and
coverage report (§6.1), and a pilot configuration-state ledger (§6.2). No
Slice 1 or Slice 2 contract changes.

---

## 2. Vocabulary carried unchanged

`FitOutcome` (four names), `SourceBasis`, `AttestationStatus`,
`VerificationStatus`, `CountBasis`, `UsageAvailabilityToken`, `SamplingKind`,
`USAGE_SCOPE_RESEARCH_ONLY`, `AUTHORITY_RESOLUTION_BASIS_V1 =
"REQUESTER_ASSERTED"`, `AdvisoryClassification`, `AdvisoryEligibility`,
`RULE_DERIVED`, `COMPARISON_EVIDENCE_ABSENT`. No new label is a synonym of
any of these.

---

## 3. Decision 1 — Usage binding (Workflow-Fit 1)

Every pilot observation is one `PilotObservation` naming exactly what was
tested. Nothing is inferred from names; every coordinate is a digest or a
versioned reference the observation was produced under.

```python
PILOT_OBSERVATION_SCHEMA_VERSION = "workflow_fit_pilot.observation.v1"

class PilotArmKind(str, Enum):
    GOVERNED_BASELINE = "GOVERNED_BASELINE"
    ADVISOR_QUALIFIED = "ADVISOR_QUALIFIED"
    CHALLENGER = "CHALLENGER"

@dataclass(frozen=True)
class PilotArm:
    arm_id: str
    kind: PilotArmKind
    method: ReasoningMethodRef                   # catalog ref + method_id + method_version
    advisory_digest: Optional[str]               # required iff kind == ADVISOR_QUALIFIED; None otherwise
    rule_set: Optional[RuleSetRef]               # the advisory's rule set; same rule
    sampling: Optional[ChallengerSamplingPolicy] # required iff kind == CHALLENGER; None otherwise

@dataclass(frozen=True)
class PilotObservation:
    schema_version: Literal["workflow_fit_pilot.observation.v1"]
    observation_id: str
    plan_digest: str                             # ResearchComparisonPlan.plan_digest (preregistered before any run)
    task_class_digest: str                       # == plan.task_class.task_class_digest; covers benchmark_set_digest and the sufficiency-rule version
    binding: BindingRef                          # == plan.binding; binding_digest and configuration_digest of the AssessedSystemBinding under test
    arm: PilotArm
    model_ref: str                               # == record.model_ref
    case_digest: str                             # digest of the benchmark case executed (from the fixed benchmark set)
    run_id: str                                  # == record.invocation_id
    record_digest: str                           # the ReasoningMethodExecutionRecord this observation is about
    evaluator: QualityEvaluatorDeclaration       # §5
    quality_claim_digest: str                    # the MetricClaim this evaluator produced for this record
    observed_at: datetime
    observation_digest: str
```

**Consistency obligations (constructor and `validate_against_plan(observation,
plan, record)`):** `task_class_digest`, `binding` and `model_ref` equal the
plan's and the record's; `record.method == arm.method`; an
`ADVISOR_QUALIFIED` arm carries an `advisory_digest` whose advisory named
this method in `qualifying` and whose `task_class_digest` equals the plan's
(`ARM_ADVISORY_MISMATCH` otherwise); a `CHALLENGER` arm carries the plan's
sampling policy; a `GOVERNED_BASELINE` arm's method equals `plan.baseline`;
`case_digest` is a member of the benchmark set's case digests
(`CASE_NOT_IN_BENCHMARK_SET`). The binding is therefore: task class (with
benchmark set and sufficiency-rule version) + assessed-system binding +
method and version + model + case + run + advisory and rule-set digests,
exactly as the ruling requires.

**Unresolved 3.1 — where the binding lives.**

| Option | Consequence |
|---|---|
| A. Add `plan_digest`, `arm` and `advisory_digest` fields to `ReasoningMethodExecutionRecord` | one object; but a Slice 1 schema change (`execution_record.v2`) and the record would carry advisor output, crossing the ratified execution-record boundary |
| B. A separate `PilotObservation` referencing the record by digest (above) | no Slice 1 change; the record stays neutral; one more object per run to validate |
| C. Carry the binding only in the plan and join by `invocation_id` | nothing new, but the join is by string and an observation cannot prove which arm it ran under |

**Recommendation: B.**

---

## 4. Decision 2 — Trust controls (Workflow-Fit 4)

**Capture outside the evaluated workflow.** The pilot introduces one
component, the **capture boundary**: a provider-client proxy that runs in a
separate process from the workflow under test, sees every model call the
workflow makes, records per-call `ApiCallTokenRecord`-shaped entries
(request id, attempt, provider, status, provider-reported usage with its
`UsageAvailability`), and after the run computes `llm_calls` and token totals
from **its own** records. It issues an `AttestationEnvelope` for the record
with `attested_fields = ("telemetry.llm_calls",
"telemetry.token_usage.total_tokens")` where provider usage was available,
`capture_boundary_ref` = the fingerprint set of its per-call records, and
`attester_identity` = the boundary's own identity, which must differ from
the record's `issuer_identity` and the request's `requester_identity`
(Slice 1 `SELF_ATTESTATION` otherwise) `[V]`. The harness's `_CountingClient`
is retired from evidence duty: it stays as a runtime-side cross-check only.

**Consistency versus authenticity, stated precisely.**

| Claim | What proves it | Status in the pilot |
|---|---|---|
| The record's `llm_calls` equals the count the boundary observed | the boundary's `AttestationEnvelope`, resolved as an authority in the request | `ATTESTED` on those fields only; everything else `UNATTESTED` |
| The boundary is who it says and its records were not altered | a Trusted Evidence Authority receipt over the attestation, adapted to a `VerificationEnvelope` | **`UNVERIFIED` in 4A** unless 4.1-C is chosen; the engine's resolution stays `REQUESTER_ASSERTED` |
| The workflow's own `total_llm_calls` | nothing beyond the record | `OBSERVED / UNATTESTED / UNVERIFIED`, as v1 constants |
| The quality value | the evaluator declaration of §5 | `REPORTED` unless every §5 control holds; never `ATTESTED` or `VERIFIED` in 4A |
| A resolved authority is genuine | nothing inside the engine (ballot §3) | requester-asserted; reported as such on every result |

**What an existing envelope proves.** An `AttestationEnvelope` proves that a
named capture boundary asserts the attested fields for that record digest;
the engine proves only that the envelope is consistent with the record and
that the attester is one the requester resolved. A `VerificationEnvelope`
proves that a named verifier asserts it verified the attestation. Neither
proves the identity behind the name. `VERIFIED` is reachable only through
the Trusted Evidence Authority's `issue()`; the pilot has no other verifier.

**Who may issue.** Attestation: the capture boundary, never the workflow,
harness, adapter or requester. Verification: the Trusted Evidence Authority
only, under a trust anchor whose `TrustAnchorCapability` covers
reasoning-method telemetry, which does not exist yet `[G]`.

**Unresolved 4.1 — depth of trust in 4A.**

| Option | Consequence |
|---|---|
| A. No capture boundary: everything `UNATTESTED / UNVERIFIED`, stated | cheapest; the pilot measures nothing the workflow could not have reported itself; decision 4 stays open |
| B. Capture boundary with attestation; verification absent and stated | telemetry becomes `ATTESTED` on two fields; quality stays reported; one new component; no TEV work |
| C. B plus a TEV anchor capability and a receipt→`VerificationEnvelope` adapter | `VERIFIED` telemetry; adds a TEV capability member and an adapter, both needing their own ratification |

**Recommendation: B**, with C recorded as the next trust slice. The pilot
report must print the three evidence axes per field; no summary may say
"trusted" for a field that is not `ATTESTED`.

---

## 5. Quality evaluation: when a separate call is not independence

An evaluator that scores quality is **independent** only if all five hold;
otherwise its output is `REPORTED` and the pilot report says so on every
figure derived from it.

```python
class QualityEvidenceStatus(str, Enum):
    INDEPENDENT_UNVERIFIED = "INDEPENDENT_UNVERIFIED"   # all five controls hold; still unverified by any authority
    REPORTED = "REPORTED"                               # any control missing

@dataclass(frozen=True)
class QualityEvaluatorDeclaration:
    evaluator_identity: str          # who scored; must differ from the workflow's model_ref, the record issuer and the requester
    evaluator_version: str
    separation_ref: str              # evidence that the evaluator ran outside the tested workflow: distinct process and call path, no shared prompt state
    scoring_instruction_digest: str  # digest of the scoring instructions, which must name benchmark_set_digest and the task class's sufficiency rule
    benchmark_set_digest: str        # == task class's
    calibration_evidence_ref: str    # a calibration study reference for this evaluator version on this benchmark set; blank ⇒ REPORTED
    evidence_status: QualityEvidenceStatus
```

Constructor: `evidence_status == INDEPENDENT_UNVERIFIED` is refused unless
every field above is non-blank and the identities differ
(`EVALUATOR_NOT_INDEPENDENT`). A human scorer is declared the same way. The
harness's `TaskCase.scorer` callable is wrapped by this declaration; the
`MetricClaim` it produces carries `source_basis = REPORTED` unless the
status is `INDEPENDENT_UNVERIFIED`, in which case `OBSERVED`. Slice 1 has no
envelope for quality claims, so no quality figure can be `ATTESTED` or
`VERIFIED` in 4A `[G]`; extending envelopes to claims is a later ruling.

---

## 6. Decisions 3 and 4 — Pilot composition and lifecycle

### 6.1 Composition (Advisor 3)

The plan is preregistered (`ResearchComparisonPlan`) before any run and
lists: the **governed baseline** (`plan.baseline`); **every method in the
advisory's qualifying set** for the class's profile, by advisory digest
(`plan.recommended`, which stays fenced as intent, not selection); and
**challengers** = every admissible catalog method in neither set, sampled
under `plan.challengers`. When the qualifying set is empty (8.1-A) the pilot
runs baseline and challengers and reports `NO_QUALIFYING_METHOD`.

**Coverage report, mandatory, no threshold.**

```python
@dataclass(frozen=True)
class ChallengerCoverageReport:
    plan_digest: str
    admissible_method_count: str      # decimal strings; the report states counts, never a pass/fail
    qualifying_set_size: str
    baseline_tested: bool
    qualified_tested: str             # of qualifying_set_size
    challengers_declared: str
    challengers_tested: str
    untested_methods: tuple[ReasoningMethodRef, ...]
    sampling: ChallengerSamplingPolicy
```

**Anti-gaming rule.** The pilot report never presents qualifying-set success
without, on the same line, `qualifying_set_size / admissible_method_count`,
set precision (qualified methods found sufficient and undominated, over
qualified methods tested) and `challengers_tested / challengers_declared`
(advisor note §6). A large qualifying set therefore shows as low precision
and a small challenger pool as low coverage.

**Unresolved 6.1 — sampling kind for the first pilot.**

| Option | Consequence |
|---|---|
| A. `PREREGISTERED`, exhaustive: every admissible non-qualified method is a challenger | with a seven-method catalog, full coverage; no sampling to game; cost is bounded by the catalog |
| B. `RANDOMIZED` with a seeded subset | fewer runs; coverage below full; seed and coverage declared |
| C. `RISK_BASED` by consequence class | needs a risk rule that does not exist |

**Recommendation: A** for 4A; B and C stay available through the existing
policy contract when catalogs grow.

### 6.2 Lifecycle (Advisor 5, research scope only)

```python
class PilotConfigurationState(str, Enum):
    PROPOSED = "PROPOSED"                     # binding and plan digests declared; nothing run
    UNDER_TEST = "UNDER_TEST"                 # at least one observation exists; no fit result yet, or COMPARISON_EVIDENCE_ABSENT
    FAILED = "FAILED"                         # fit outcome INSUFFICIENT_QUALITY for this arm
    RESEARCH_QUALIFIED = "RESEARCH_QUALIFIED" # SUFFICIENT_PARETO_EFFICIENT or SUFFICIENT_RESOURCE_DOMINATED, carried verbatim
    REVISED = "REVISED"                       # superseded by a new configuration_digest; lineage to the successor

@dataclass(frozen=True)
class PilotConfigurationStateRecord:
    schema_version: Literal["workflow_fit_pilot.state.v1"]
    plan_digest: str
    binding: BindingRef
    arm: PilotArm
    state: PilotConfigurationState
    fit_outcome: Optional[FitOutcome]          # required for FAILED and RESEARCH_QUALIFIED; None otherwise
    result_digest: Optional[str]               # the ReadinessComparisonResult that set it
    predecessor_state_digest: Optional[str]    # lineage; a REVISED record names its successor's binding digest in successor_binding_digest
    successor_binding_digest: Optional[str]
    usage_scope: Literal["RESEARCH_ONLY"]
    approval_status: Literal["NONE"]           # a constant, so a consumer must change a type to read approval
    recorded_by: str
    recorded_at: datetime
    state_digest: str
```

Closed transitions: `PROPOSED → UNDER_TEST`; `UNDER_TEST → FAILED |
RESEARCH_QUALIFIED`; any state `→ REVISED` when the `configuration_digest`
changes, and the new configuration starts again at `PROPOSED` with a new
`binding_digest` and lineage to the revised record. `FAILED` and
`RESEARCH_QUALIFIED` never transition to each other: a changed result means
a changed configuration or benchmark set, hence `REVISED`. **The
configuration is identified before testing** because `PROPOSED` requires the
binding and plan digests and refuses any observation. **No state is an
approval**: `approval_status` is the constant `"NONE"`, `usage_scope` is
`RESEARCH_ONLY`, and no Decision Authority, Constitution binding or
`deployment_environment_ref` semantics are touched. The Slice 1
`SUFFICIENT_PARETO_EFFICIENT` fence (ballot §8) stands.

**Unresolved 6.2 — placement of the state ledger.**

| Option | Consequence |
|---|---|
| A. In the pilot package (research-only) | matches scope; the production lifecycle ruling (ballot 8.2) stays open and untouched |
| B. In `governance-contracts` beside `AssessedSystemBinding` | pre-empts ballot 8.2 with research-only states |

**Recommendation: A**; ballot 8.2 is not decided by this document.

---

## 7. The smallest research-only pilot, and the implementation boundary

**One task class.** The harness's `hard` class as declared through the
governed adapter (`StudyClassDeclaration`) with a versioned threshold-based
sufficiency rule, `RECOVERABLE` consequence (so no admission is needed) `[I]`;
**fixed benchmark set** = that class's `TaskCase` set, digested into
`benchmark_set_digest`, registered as a `BenchmarkReference` `[G]` (a local
reference is acceptable for 4A; registry registration is a later step);
**governed baseline** `linear_chain@1` as the adapter already uses `[V]`;
**advisor-qualified methods** from one advisory over the class's profile
under `rules.research.v0`; **challengers** every other admissible catalog
method (6.1-A); **one capture boundary**; **one declared evaluator**. Output:
one `ReadinessComparisonResult` producing the four ratified outcomes, one
coverage report, one state record per arm, and a pilot report that prints
evidence axes per field.

**Execution** happens only in the research harness with a caller-supplied
provider client behind the capture boundary. **Not** through Agent Runtime,
Agentic Proposer or Agent Workforce Composer; no runtime integration.

**Package.** `packages/capabilities/workflow-fit-pilot` →
`ugence-workflow-fit-pilot`, depending on `ugence-reasoning-method-governance`,
`ugence-readiness-comparison`, `ugence-reasoning-method-advisor`,
`ugence-governance-contracts`, `ugence-jcs`; the capture boundary in the
same package as a subpackage with no import of `agentic`; the harness stays
in `experiments/`. Boundary test as in Slices 1 and 2.

**In scope:** §3 observation and arm; §4 capture boundary and its
attestation issuance; §5 evaluator declaration; §6.1 coverage report; §6.2
state ledger; a pilot runner that preregisters the plan, runs the arms
through the harness, adapts records, calls `compare()`, and renders the
report; CI gate; wheel self-check.

**Out of scope:** any change to Slice 1 or Slice 2 contracts, enums or
packages; TEV anchor capability and receipt adapter (4.1-C); envelopes for
quality claims; benchmark-registry registration; benchmark-derived advisor
input (`BENCHMARK_DERIVED` stays absent); readiness composite; production
approval, configuration mutation, Constitution binding, runtime execution;
any numeric threshold, sample size, coverage target or acceptance figure.

---

## 8. Executable acceptance tests

| # | Test | Expected |
|---|---|---|
| A1 | `PilotObservation` whose `task_class_digest` differs from the plan's | refused `OBSERVATION_PLAN_MISMATCH` |
| A2 | `ADVISOR_QUALIFIED` arm whose `advisory_digest` names an advisory that did not qualify this method, or with `advisory_digest=None` | `ARM_ADVISORY_MISMATCH` |
| A3 | `CHALLENGER` arm without a sampling policy; `GOVERNED_BASELINE` arm whose method ≠ `plan.baseline` | `ARM_KIND_INCONSISTENT` |
| A4 | observation whose `case_digest` is not in the benchmark set | `CASE_NOT_IN_BENCHMARK_SET` |
| A5 | capture boundary in a separate process observes N calls while the workflow reports M ≠ N | record carries M as `OBSERVED`; the attestation carries N; the engine's `EvidenceStatusView` shows `ATTESTED` on `telemetry.llm_calls`; the report prints both |
| A6 | attestation whose `attester_identity` equals the record issuer or the requester | Slice 1 `SELF_ATTESTATION`, unchanged |
| A7 | attestation from an attester not in `resolved_authorities` | listed in `ignored_envelopes`; status `UNATTESTED` |
| A8 | any pilot result | every `EvidenceStatusView.verification_status == UNVERIFIED`; the report never prints "verified" or "trusted" |
| A9 | `QualityEvaluatorDeclaration(evidence_status=INDEPENDENT_UNVERIFIED)` with blank `calibration_evidence_ref`, or evaluator identity equal to `model_ref` | `EVALUATOR_NOT_INDEPENDENT` |
| A10 | evaluator declared `REPORTED` | its `MetricClaim.source_basis == REPORTED`; every derived figure in the report is labelled `REPORTED` |
| A11 | plan with a three-member qualifying set over a seven-method catalog under 6.1-A | coverage report: `qualifying_set_size=3`, `challengers_declared=3`, `challengers_tested=3`, `untested_methods=()`; set precision printed beside qualifying-set success |
| A12 | the same plan with one challenger omitted | `challengers_tested=2`, `untested_methods` names it; no "success" line without the coverage figures |
| A13 | empty qualifying set | baseline and challengers run; `NO_QUALIFYING_METHOD` reported; no primary anywhere |
| A14 | state ledger: observation recorded against a `PROPOSED` arm without transition | refused; `PROPOSED → UNDER_TEST` required first |
| A15 | `UNDER_TEST` with `COMPARISON_EVIDENCE_ABSENT` | stays `UNDER_TEST`; neither `FAILED` nor `RESEARCH_QUALIFIED` |
| A16 | `FAILED → RESEARCH_QUALIFIED` directly | refused; only `→ REVISED` |
| A17 | changed `configuration_digest` | new `binding_digest`, new `PROPOSED` record with lineage; the old record `REVISED` naming the successor |
| A18 | any state record | `approval_status == "NONE"`, `usage_scope == RESEARCH_ONLY`; field-set test finds no `approved`, `eligible`, `production` field |
| A19 | pilot runner end to end on the harness fixtures with a stub client behind the boundary | exactly the four `FitOutcome` names appear across arms; `result_digest` stable across two runs at one `produced_at`; `authority_resolution_basis == REQUESTER_ASSERTED` |
| A20 | AST boundary scan of the package | no `agentic`, runtime, proposer, composer, readiness, `governed_value`, network or LLM SDK import; no clock read |
| A21 | numeric-default scan | no numeric literal in any contract default; no threshold, sample size or coverage target anywhere in `src/` |

---

## 9. Explicitly excluded from 4A

No production authority or approval; no benchmark-derived advisor change; no
readiness composite; no runtime execution or integration; no TEV capability
or receipt adapter; no quality-claim envelopes; no benchmark-registry
registration; no change to any Slice 1 or Slice 2 contract; no LLM-based
selection; no numeric figure of any kind.

---

## 10. Owner ballot `[R]`

1. **Usage binding.** Ratify §3: a `PilotObservation` (3.1-B) binding plan,
   task-class digest (benchmark set and sufficiency-rule version included),
   assessed-system binding, method and version, model, case, run, record and,
   for advisor-qualified arms, advisory and rule-set digests; no change to
   the execution record.
2. **Trust controls.** Ratify §4 and §5: an out-of-process capture boundary
   is the only attester (4.1-B); the Trusted Evidence Authority is the only
   verifier and issues nothing in 4A, so every field stays `UNVERIFIED`;
   quality is `REPORTED` unless the five evaluator controls hold, and is
   never attested or verified in 4A; the report prints all three axes per
   field.
3. **Pilot composition.** Ratify §6.1: governed baseline, every
   advisor-qualified method by advisory digest, and exhaustive preregistered
   challengers (6.1-A); the coverage report is mandatory and no success
   figure is ever shown without set precision and challenger coverage.
4. **Lifecycle.** Ratify §6.2: the five research-only states with closed
   transitions, configuration identified at `PROPOSED` before any run,
   revision by new digest with lineage, `approval_status = "NONE"` constant,
   the ledger placed in the pilot package (6.2-A); ballot 8.2 and production
   approval remain open.

**Definition of done for 4A** (after ratification): package
`ugence-workflow-fit-pilot` with the §3–§6 contracts, the capture boundary,
the pilot runner over the harness, every §8 row as an executable test, a CI
gate in the Slice 1 pattern, and a wheel self-check. Nothing numeric.
