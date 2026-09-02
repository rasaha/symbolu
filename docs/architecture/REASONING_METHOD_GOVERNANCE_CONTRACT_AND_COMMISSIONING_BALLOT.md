# Reasoning Method Governance — Contract Specification and Commissioning Ballot

**Status:** implementable specification for owner ratification. Nothing here is
implemented. It turns the six owner rulings of 2026-09-02 into contracts with
exact fields, and ends with a ballot that, once ratified, commissions the first
implementation slice.
**Supersedes as the implementation reference:** the contract-shaped parts of
`REASONING_METHOD_ADVISOR_SCOPING_NOTE.md`, `WORKFLOW_FIT_READINESS_SCOPING_NOTE.md`
and `READINESS_ADVISORY_COMPOSITE_DESIGN_NOTE.md`. Their rulings remain the
authority; this document is their specification.
**Evidence labels:** `[V]` verified against the repository · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**What is the smallest set of contracts that lets a reasoning-method execution
cross from the experimental runtime to the governed side, be compared under a
governed task class, and yield one of the four ratified outcomes, without any
package trusting the runtime's own word?** Answer: five contracts and two ports
(§2–§5, §7), one append-only record lifecycle (§4), and one reference comparison
implementation (§9). Everything else in this document is either an option set
for the owner or an explicit exclusion.

**Conventions adopted throughout** `[V]`: frozen dataclasses with
`__post_init__` validation, as in `governance-contracts`, `uvi-policy-contracts`
and `agent-value-readiness` (`system_identity.py:259`, `thresholds.py:31`);
digests are lowercase 64-hex SHA-256 computed with `ugence_jcs.canonical_sha256_hex`
(`packages/jcs/src/ugence_jcs/canon.py:129`, no prefix, no envelope); every
contract carries a pinned `schema_version` literal; nothing numeric is
defaulted.

---

## 1. Capability placement and package ownership

**Ruling applied.** Advisor §8.2 ratifies a neutral, versioned record boundary
with an adapter and no direct import. Composite §10.1 assigns comparison to a
separately commissioned component upstream of `agent-value-readiness`.
Workflow-Fit §11.5 makes reasoning efficiency a property of the selection
policy within the exact `AssessedSystemBinding`, so no `CapabilityDimension`
(`agent-value-readiness …/contracts/enums.py:121`) is added `[V]`.

**Two packages, one commissioned now, one commissioned by port only.**

| Package | Distribution / import | Owns | Depends on |
|---|---|---|---|
| `packages/capabilities/reasoning-method-governance` | `ugence-reasoning-method-governance` / `ugence_reasoning_method_governance` | §2 catalog and ref, §3 profile and class identity, §4 execution record, §5 fit assessment, §7 port contracts, §8 pilot plan and lineage, reference comparison (§9) | `ugence-governance-contracts`, `ugence-uvi-policy-contracts`, `ugence-jcs` |
| `packages/capabilities/readiness-comparison` | `ugence-readiness-comparison` / `ugence_readiness_comparison` | the generic consuming evaluation engine of the Benchmark Registry ADR (§7); reasoning-method fit is its first client | the above, plus `ugence-benchmark-registry` |

**Prohibited dependencies, enforced by a boundary test as `agentic-proposer`
does** `[V]` (its `tests/test_boundaries.py` and forbidden-wheel list): neither
package may import `agentic`, `agentic_framework`, `reasoning_workflows` or
`WorkflowResult`; `agent-value-readiness` may not import either package until a
later ruling binds attainments into readiness.

**Unresolved 1.1 — where the telemetry vocabulary comes from.** The record
needs `TokenCountBasis`, `UsageAvailability` and the `ProviderTokenUsage` field
set, which live in the `context-minimization` capability
(`token_accounting.py:135,166,285`) `[V]`.

| Option | Consequence |
|---|---|
| A. Runtime dependency on `ugence-context-minimization` | one capability depends on another; pulls minimization code into a contracts package |
| B. Mirror the members as string tokens, pinned by a test that imports `context-minimization` under `[test]` only | zero runtime coupling; drift caught in CI; two definitions exist |
| C. Move the three types to `governance-contracts` | cleanest long-term; requires a `context-minimization` release and a CM-TA1 change |

**Recommendation: B now, C as a follow-up ruling.** B is the existing
mirror-and-pin pattern (`tests/s1_specification_mirror.py` in
`agentic-proposer`) `[V]`.

**Unresolved 1.2 — one package or two.** A single package is simpler; two
packages keep the comparison engine's authority generic, which the composite
ruling requires ("upstream of `agent-value-readiness`", not specific to
reasoning methods). **Recommendation: two, with only the second's port
contracts in slice 1** (§9).

---

## 2. `ReasoningMethodCatalog` and `ReasoningMethodRef`

The catalog is the governed repertoire. It is **not** the seven-member
`WorkflowType` enum (`reasoning_workflows.py:78-86`) `[V]`; the landscape
evaluation found fifteen methods of which three are implemented `[V]`.

```python
CATALOG_SCHEMA_VERSION = "reasoning_method.catalog.v1"

class ImplementationStatus(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    INFRASTRUCTURE_ONLY = "INFRASTRUCTURE_ONLY"
    ABSENT = "ABSENT"

@dataclass(frozen=True)
class ReasoningMethodRef:
    catalog_id: str
    catalog_version: str
    method_id: str
    method_version: str
    # invariant: all four non-blank; identity = (catalog_id, catalog_version, method_id, method_version)

@dataclass(frozen=True)
class ReasoningMethodEntry:
    method_id: str
    method_version: str
    display_name: str
    implementation_status: ImplementationStatus
    declared_signals: tuple[str, ...]          # tokens pinned to ComplexitySignal values (adaptive_prompts.py:88)
    requirement_refs: tuple[str, ...]          # tool / evidence requirements, opaque refs
    runtime_binding_ref: str = ""              # opaque, e.g. "agentic.reasoning_workflows.WorkflowType.TREE_OF_THOUGHT"; never imported
    policy_refs: tuple[str, ...] = ()          # MetricClaim.policy_refs shape (evidence.py:386)
    # prohibited: any scalar resource label, any numeric outcome claim (advisor note §5 prohibitions)

@dataclass(frozen=True)
class ReasoningMethodCatalog:
    schema_version: Literal["reasoning_method.catalog.v1"]
    catalog_id: str
    catalog_version: str
    entries: tuple[ReasoningMethodEntry, ...]  # unique (method_id, method_version); sorted by that key
    issuer_identity: str
    issued_at: datetime                        # tz-aware
    catalog_digest: str                        # jcs digest over all fields except catalog_digest
```

**Refusals:** duplicate `(method_id, method_version)`; unsorted entries; blank
identity; `declared_signals` token outside the pinned vocabulary; any entry
field named `cost`, `latency_class` or similar scalar label (checked by field
set, not by value).

**Unresolved 2.1 — initial catalog membership.**

| Option | Consequence |
|---|---|
| A. The three `IMPLEMENTED` methods only (`LINEAR_CHAIN`, `TREE_OF_THOUGHT`, `ITERATIVE_REFINEMENT`) | every entry is executable; advisor can only ever recommend three |
| B. All seven enum members with honest `implementation_status` | matches the runtime; four entries are `PARTIAL`/`INFRASTRUCTURE_ONLY` and cannot be piloted |
| C. The full fifteen-method repertoire | complete vocabulary; eight `ABSENT` entries that no pilot can test, inflating coverage denominators |

**Recommendation: B.** Coverage (§6 of the advisor note) is measured against
catalog size; `ABSENT` entries would make every coverage figure meaningless.

---

## 3. Task profile and task-class identity

**Ruling applied.** Advisor §8.4 binds ten coordinates. The profile is the
developer's assertion; the class identity is the governed object.

```python
PROFILE_SCHEMA_VERSION = "reasoning_method.task_profile.v1"
TASK_CLASS_SCHEMA_VERSION = "reasoning_method.task_class.v1"

class SufficiencyKind(str, Enum):
    THRESHOLD_BASED = "THRESHOLD_BASED"
    IMPROVEMENT_VALUED = "IMPROVEMENT_VALUED"

@dataclass(frozen=True)
class SufficiencyRule:
    rule_id: str
    rule_version: str
    kind: SufficiencyKind
    threshold: GovernedThreshold                # uvi-policy-contracts thresholds.py:31; literal XOR benchmark_ref
    supporting_evidence_refs: tuple[str, ...] = ()

@dataclass(frozen=True)
class TaskProfile:                              # developer-reported; never evidence
    schema_version: Literal["reasoning_method.task_profile.v1"]
    profile_id: str
    domain_ref: str
    intended_outcome_ref: str
    consequence_class: str                      # token; vocabulary is unresolved 3.1
    reversibility: str                          # token pinned to external_actions.Reversibility values (external_actions.py:155)
    evidence_requirement_refs: tuple[str, ...]
    tool_requirement_refs: tuple[str, ...]
    structural_characteristics: tuple[str, ...] # tokens pinned to ComplexitySignal values
    population_ref: str
    policy_refs: tuple[str, ...] = ()           # privacy and regulation by reference only
    declared_by: str = ""
    declared_at: Optional[datetime] = None
    assertion_basis: Literal["DEVELOPER_REPORTED"] = "DEVELOPER_REPORTED"

@dataclass(frozen=True)
class TaskClassIdentity:
    schema_version: Literal["reasoning_method.task_class.v1"]
    task_class_id: str
    domain_ref: str
    intended_outcome_ref: str
    consequence_class: str
    reversibility: str
    evidence_requirement_refs: tuple[str, ...]
    tool_requirement_refs: tuple[str, ...]
    structural_characteristics: tuple[str, ...]
    population_ref: str
    benchmark_set_ref: str
    benchmark_set_digest: str
    sufficiency: SufficiencyRule
    task_class_digest: str                      # jcs digest over the ten coordinates + sufficiency (rule_id, rule_version)
```

**Compatibility predicate.** `compatible(a, b)` is `a.task_class_digest ==
b.task_class_digest`. Evidence is shared only under equality; otherwise the
consumer emits `COMPARISON_EVIDENCE_ABSENT`. Declared equivalence between
distinct classes is a later ruling `[R]`.

**Refusal (ruling §11.3).** Construction fails when `consequence_class` is in
the high-consequence set and `sufficiency.kind == THRESHOLD_BASED` with empty
`supporting_evidence_refs`. The high-consequence set is defined by option 3.1.

**Unresolved 3.1 — consequence vocabulary and the high-consequence set.**

| Option | Consequence |
|---|---|
| A. Reuse `GateCategory`-style tokens from `uvi-policy-contracts` (`enums.py:~101`) | existing vocabulary, but it classifies gates, not consequences |
| B. New closed enum `ConsequenceClass = {NEGLIGIBLE, RECOVERABLE, MATERIAL, SEVERE}` with `{MATERIAL, SEVERE}` as high-consequence | explicit and testable; four new tokens to ratify |
| C. Policy-referenced: `consequence_policy_ref` resolved by Policy Authority | no new enum; comparison engine cannot apply the refusal without a policy fetch |

**Recommendation: B.** The refusal must be decidable at construction time from
the identity alone.

**Unresolved 3.2 — reversibility source.** `Reversibility` is a plain class of
string constants in `agentic/`, not an enum, and nothing under `packages/`
defines one `[V]`. Options: mirror the four tokens and pin by test (as 1.1-B),
or define a governed enum in `governance-contracts`. **Recommendation: mirror
and pin now**; the boundary test forbids the import.

---

## 4. `ReasoningMethodExecutionRecord`

**Ruling applied.** Advisor §8.2: neutral, versioned, adapter-emitted, no
direct import; identity, canonicalization, lifecycle, promotion and disclosure
are decided here for the first time.

```python
RECORD_SCHEMA_VERSION = "reasoning_method.execution_record.v1"

class ArtifactKind(str, Enum):
    CANDIDATE = "CANDIDATE"
    REVISION = "REVISION"
    DECISION = "DECISION"
    FINAL_OUTPUT = "FINAL_OUTPUT"
    # deliberately absent: REASONING_TRACE, PROMPT, TRANSCRIPT

@dataclass(frozen=True)
class ArtifactRef:
    kind: ArtifactKind
    ref: str
    digest: str                                 # sha-256 hex of the artifact content

class CountBasis(str, Enum):                    # mirrors TokenCountBasis (token_accounting.py:135), pinned by test
    CALLER_SUPPLIED = "CALLER_SUPPLIED"
    INJECTED_COUNTER = "INJECTED_COUNTER"
    DEFAULT_APPROXIMATE = "DEFAULT_APPROXIMATE"
    MIXED = "MIXED"
    PROVIDER_REPORTED = "PROVIDER_REPORTED"
    UNKNOWN = "UNKNOWN"

class UsageAvailabilityToken(str, Enum):        # mirrors UsageAvailability (token_accounting.py:166), pinned by test
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE_NOT_REPORTED = "UNAVAILABLE_NOT_REPORTED"
    UNAVAILABLE_PROVIDER_ERROR = "UNAVAILABLE_PROVIDER_ERROR"
    UNAVAILABLE_UNKNOWN = "UNAVAILABLE_UNKNOWN"

@dataclass(frozen=True)
class TokenUsageSnapshot:                       # mirrors ProviderTokenUsage fields (token_accounting.py:285); all Optional
    input_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_write_input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    provider_request_id: Optional[str] = None

@dataclass(frozen=True)
class ExecutionTelemetry:
    llm_calls: Optional[int]
    llm_calls_basis: CountBasis
    token_usage_availability: UsageAvailabilityToken
    token_usage: Optional[TokenUsageSnapshot]
    token_count_basis: CountBasis
    duration_ms: Optional[int]                  # diagnostic only; never a comparison dimension
    attestation_refs: tuple[str, ...] = ()      # e.g. ApiCallTokenRecord fingerprints (token_accounting.py:433)
    # invariants: AVAILABLE ⇒ token_usage is not None and has at least one non-None count;
    #             not AVAILABLE ⇒ token_usage is None; llm_calls None ⇒ llm_calls_basis == UNKNOWN

@dataclass(frozen=True)
class BindingRef:                               # the exact AssessedSystemBinding under test (system_identity.py:260)
    binding_id: str
    configuration_id: str
    configuration_digest: str
    context_digest: str
    binding_digest: str                         # AssessedSystemBinding.canonical_digest() (system_identity.py:399)

@dataclass(frozen=True)
class ReasoningMethodExecutionRecord:
    schema_version: Literal["reasoning_method.execution_record.v1"]
    record_id: str
    tenant_id: str
    subject_id: str
    invocation_id: str
    method: ReasoningMethodRef
    binding: BindingRef
    task_class_ref: str
    task_class_digest: str
    input_digest: str
    model_ref: str                              # Model Authority reference; never a model choice
    policy_refs: tuple[str, ...]
    artifacts: tuple[ArtifactRef, ...]
    telemetry: ExecutionTelemetry
    self_reported_quality: Optional[str]        # decimal-as-string; labelled, never evidence
    source_basis: SourceBasis                   # governance-contracts evidence.py
    attestation_status: AttestationStatus       # evidence.py:90
    attestation_ref: str
    attester_identity: str
    verification_status: VerificationStatus     # evidence.py:112
    verification_ref: str
    verifier_identity: str
    issuer_identity: str
    captured_at: datetime                       # tz-aware
    parent_record_digest: Optional[str]         # lineage, as ProposerAdvisory.parent_advisory_digest (contracts.py:980)
    record_digest: str
```

**Canonicalization.** `record_digest = canonical_sha256_hex(payload)` where
`payload` is every field except `record_digest`, enums by value, datetimes as
RFC 3339 UTC, tuples in declared order (`set_paths` and `nfc_paths` empty, as
`ProposerAdvisory` does) `[V]`. Two records with the same payload are the same
record.

**Evidence status on emission.** An emitter running in the same process as the
method **must** set `source_basis = OBSERVED`, `attestation_status =
UNATTESTED`, `verification_status = UNVERIFIED`, with the three ref fields
blank. The constructor refuses `ATTESTED` without a non-blank `attestation_ref`
and `attester_identity`, and refuses `VERIFIED` without `verification_ref` and
`verifier_identity`. Promotion is §6.

**Lifecycle.** Append-only. A record is never mutated. A correction is a new
record whose `parent_record_digest` names the superseded one; the newest record
in a lineage is authoritative for a consumer that reads the whole lineage. The
constructor refuses `parent_record_digest == record_digest`, mirroring rule L-1
(`contracts.py:1071-1077`) `[V]`.

**Refusal rules (constructor).** Any malformed digest; `ArtifactKind` outside
the enum; telemetry invariants above; `self_reported_quality` not parseable as
a decimal; blank `issuer_identity`; naive datetime; `method.catalog_version`
blank.

**Disclosure.** The record carries **references and digests** to artifacts,
never artifact content, prompts or reasoning traces. Access to the referenced
artifacts is governed by whatever store holds them; the record itself is
disclosable to any consumer that may see the binding.

**Unresolved 4.1 — revocation.**

| Option | Consequence |
|---|---|
| A. No revocation in v1; supersession only | simple; a bad record stays readable but is superseded |
| B. Revocation envelope after `benchmark-registry-authority` (`envelopes.py:488`, `trust.py:456`) | full authority machinery; needs an issuer key model that does not exist for this package |
| C. Tombstone record with `ArtifactKind`-free payload and `revoked_reason` | lightweight; a tombstone is still a record and can itself be superseded |

**Recommendation: A**, with B taken up when the Trusted Evidence Authority
rules on capture keys.

**Unresolved 4.2 — issuer authority.** Who may emit v1 records: (A) any adapter,
with `issuer_identity` a free string; (B) a registered adapter id validated
against a list in the package; (C) a signed envelope. **Recommendation: A for
slice 1**, because every v1 record is `UNATTESTED` by rule and the identity is
informational until §6 promotion exists.

---

## 5. `ReasoningMethodFitAssessment`

**Ruling applied.** Workflow-Fit §11.2 (four names), §11.3 (per-class rule,
no global default), §11.5 (property of the selection policy within the exact
binding, per task class).

```python
FIT_SCHEMA_VERSION = "reasoning_method.fit_assessment.v1"

class FitOutcome(str, Enum):                    # exactly the ratified four (study.py:80-84)
    INSUFFICIENT_QUALITY = "INSUFFICIENT_QUALITY"
    SUFFICIENT_RESOURCE_DOMINATED = "SUFFICIENT_RESOURCE_DOMINATED"
    SUFFICIENT_PARETO_EFFICIENT = "SUFFICIENT_PARETO_EFFICIENT"
    COMPARISON_EVIDENCE_ABSENT = "COMPARISON_EVIDENCE_ABSENT"

class ResourceDimension(str, Enum):
    LLM_CALLS = "LLM_CALLS"
    TOTAL_TOKENS = "TOTAL_TOKENS"
    # duration is excluded by rule; depth_used is excluded by rule (workflow-fit note §3)

@dataclass(frozen=True)
class ResourceDelta:
    dimension: ResourceDimension
    delta: str                                  # decimal-as-string; method minus cheapest sufficient

@dataclass(frozen=True)
class ReasoningMethodFitAssessment:
    schema_version: Literal["reasoning_method.fit_assessment.v1"]
    assessment_id: str
    task_class_ref: str
    task_class_digest: str
    binding_digest: str
    method: ReasoningMethodRef
    baseline: ReasoningMethodRef
    outcome: FitOutcome
    quality_margin: Optional[str]               # decimal-as-string; None iff evidence absent
    resource_deltas: tuple[ResourceDelta, ...]  # empty iff evidence absent or outcome INSUFFICIENT_QUALITY
    dominated_by: tuple[ReasoningMethodRef, ...]
    dimensions_compared: tuple[ResourceDimension, ...]
    sufficiency_rule_id: str
    sufficiency_rule_version: str
    quality_claim_refs: tuple[str, ...]         # MetricClaim ids; each must be usage_scope EVALUATION_ONLY or GENERAL and never self-reported
    input_record_digests: tuple[str, ...]
    source_basis: SourceBasis                   # the weakest across inputs
    attestation_status: AttestationStatus       # the weakest across inputs
    verification_status: VerificationStatus     # the weakest across inputs
    assessor_identity: str
    assessed_at: datetime
    reason: str
    assessment_digest: str
```

**Outcome rules, exact.** Let `Q` be the mean of the independent quality
claims for `(task_class, method)`, `τ` the rule's `GovernedThreshold`
evaluated with its `comparator`, and `R(m)` the resource vector over
`dimensions_compared`.

1. `COMPARISON_EVIDENCE_ABSENT` when any holds: no `SufficiencyRule`; zero
   records for the method; zero records for the baseline; any input record's
   `task_class_digest` differs; any quality claim traces to
   `self_reported_quality`; a dimension in `dimensions_compared` is
   unavailable on any compared record.
2. `INSUFFICIENT_QUALITY` when `Q` fails `τ` under the comparator.
3. Otherwise, under `THRESHOLD_BASED`: `SUFFICIENT_RESOURCE_DOMINATED` when
   some other sufficient method `m'` has `R(m') ≤ R(m)` on every dimension and
   `<` on at least one. Under `IMPROVEMENT_VALUED`: the same, **and**
   `Q(m') ≥ Q(m)`. Ties on every dimension are not domination.
4. Otherwise `SUFFICIENT_PARETO_EFFICIENT`.

Margins and deltas are attributes, never combined. No weights exist.

**Unresolved 5.1 — which dimensions slice 1 compares.**

| Option | Consequence |
|---|---|
| A. `LLM_CALLS` only | total order; matches today's runtime, which records no tokens (`WorkflowResult` `:144-145`) `[V]`; over-reasoning on tokens invisible |
| B. `LLM_CALLS` plus `TOTAL_TOKENS` whenever every compared record has `AVAILABLE` usage, else `LLM_CALLS` only | honest Pareto when tokens exist; comparisons within a class can differ in dimensionality |
| C. Both always, evidence absent when tokens missing | strictest; every current runtime record yields absence |

**Recommendation: B**, with `dimensions_compared` recorded on every assessment
so the reader knows which rule produced it.

---

## 6. Telemetry binding and promotion controls

Three states on the existing axes `[V]` (`evidence.py:90,112`). No new label.

| State | Axes | Condition |
|---|---|---|
| Runtime-reported | `OBSERVED` / `UNATTESTED` / `UNVERIFIED` | emitted by the same process; every v1 adapter record |
| Attested | `OBSERVED` / `ATTESTED` / `UNVERIFIED` | `attestation_refs` name capture records produced **outside** the method's process, binding invocation, provider and attempt; `attester_identity` is the capture boundary |
| Verified | `OBSERVED` / `ATTESTED` / `VERIFIED` | the Trusted Evidence Authority has checked the attested counts against provider records and issued `verification_ref` |

**Binding rule.** Token telemetry attests only through `ApiCallTokenRecord`
(`token_accounting.py:433`) or its successor: it already binds
`logical_request_id`, `attempt_id`, `provider_id`, `usage_availability` and
`provider_usage` `[V]`, and CM-TA1 already produces it from Agent Runtime
attempts `[V]`. Call counts attest through the same records by counting
attempts with `provider_invoked = True`. A harness-side counter at the client
boundary, as in the study (`study.py:140`), is still same-process and stays
`UNATTESTED` `[V]`.

**Promotion is never performed by the emitter or the assessor.** Only a
capture boundary sets `ATTESTED`; only the Trusted Evidence Authority sets
`VERIFIED`. This is the ratified no-self-attestation rule applied to this
record (`ADR_UGENCE_POLICY_AUTHORITY.md:184`) `[V]`.

**Unresolved 6.1 — the capture boundary for the experimental runtime.**
`LLMClient.call(self, prompt: str) -> str` (`reasoning_workflows.py:70`) `[V]`
returns text only; no usage passes through it.

| Option | Consequence |
|---|---|
| A. Run pilots only through Agent Runtime so CM-TA1 records exist | attested tokens from day one; the `agentic/` workflows need an `LLMClient` backed by Agent Runtime, which is new work outside this package |
| B. A client wrapper that records provider usage into `ApiCallTokenRecord` shape from inside the process | same-process; cannot rise above `UNATTESTED`; useful only as a stepping stone |
| C. Provider receipts fetched by `provider_request_id` after the fact | independent, but only where the provider exposes usage by request id |

**Recommendation: A for any pilot whose assessment is meant to reach approval;
B is acceptable for research runs and must stay labelled.** Workflow-Fit §11.4
(trust controls) is resolved by this section only if the owner ratifies it;
otherwise it remains `[R]`.

---

## 7. Comparison-engine ports

**Ruling applied.** Composite §10.1: a separately commissioned component
performs deterministic comparison and emits comparison/attainment records;
readiness consumes them. The Registry computes nothing (B-12) `[V]`.

```python
COMPARISON_REQUEST_SCHEMA_VERSION = "readiness_comparison.request.v1"
COMPARISON_RESULT_SCHEMA_VERSION = "readiness_comparison.result.v1"

class RefusalCode(str, Enum):
    NO_SUFFICIENCY_RULE = "NO_SUFFICIENCY_RULE"
    TASK_CLASS_MISMATCH = "TASK_CLASS_MISMATCH"
    BASELINE_ABSENT = "BASELINE_ABSENT"
    METHOD_RECORDS_ABSENT = "METHOD_RECORDS_ABSENT"
    QUALITY_CLAIM_NOT_INDEPENDENT = "QUALITY_CLAIM_NOT_INDEPENDENT"
    DIMENSION_UNAVAILABLE = "DIMENSION_UNAVAILABLE"
    THRESHOLD_UNRESOLVABLE = "THRESHOLD_UNRESOLVABLE"
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"

@dataclass(frozen=True)
class Refusal:
    code: RefusalCode
    detail: str

@dataclass(frozen=True)
class ReadinessComparisonRequest:
    schema_version: Literal["readiness_comparison.request.v1"]
    request_id: str
    task_class: TaskClassIdentity
    catalog: ReasoningMethodRef                 # catalog_id/version only; method fields blank
    baseline: ReasoningMethodRef
    candidates: tuple[ReasoningMethodRef, ...]
    records: tuple[ReasoningMethodExecutionRecord, ...]
    quality_claims: tuple[MetricClaim, ...]     # governance-contracts evidence.py:347; independent evaluator
    dimensions_requested: tuple[ResourceDimension, ...]
    requester_identity: str

@dataclass(frozen=True)
class ReadinessComparisonResult:
    schema_version: Literal["readiness_comparison.result.v1"]
    request_id: str
    request_digest: str
    assessments: tuple[ReasoningMethodFitAssessment, ...]   # one per candidate, always present; absence is an outcome
    refusals: tuple[Refusal, ...]                            # request-level; when non-empty every assessment is COMPARISON_EVIDENCE_ABSENT
    engine_identity: str
    engine_version: str
    produced_at: datetime
    result_digest: str
```

**Engine obligations.** Pure function of the request; no I/O; no normalization
or unit conversion (a `GovernedThreshold` whose `governed_unit` differs from
the claims' `governed_unit` is `THRESHOLD_UNRESOLVABLE`); `benchmark_ref`
thresholds resolve only through an already-admitted Registry entry supplied in
the request, never fetched. The engine never reads `self_reported_quality`.

**Unresolved 7.1 — attainment record for readiness.** The composite ruling
says readiness consumes comparison/attainment records, but no `Attainment*`
class exists anywhere `[V]`. Options: (A) `ReadinessComparisonResult` is the
attainment record and readiness consumes it directly; (B) a thinner
`AttainmentRecord {task_class_digest, method, outcome, digests}` projected
from the result; (C) defer until composite ballot 4 is taken.
**Recommendation: C**, since composite ballot 4 (attainment representation)
remains `[R]` and this specification must not pre-empt it. The reasoning-method
path needs only the result.

---

## 8. Pilot sampling, approval, revision and reassessment

```python
class SamplingKind(str, Enum):
    PREREGISTERED = "PREREGISTERED"
    RISK_BASED = "RISK_BASED"
    RANDOMIZED = "RANDOMIZED"

@dataclass(frozen=True)
class ChallengerSamplingPolicy:
    kind: SamplingKind
    policy_ref: str                             # the preregistration, risk rule or seed specification
    declared_coverage_ref: str                  # what fraction of the catalog this policy will test, declared in advance
    # no numeric coverage minimum here; it is declared in the referenced policy

@dataclass(frozen=True)
class PilotPlan:
    schema_version: Literal["reasoning_method.pilot_plan.v1"]
    plan_id: str
    task_class: TaskClassIdentity
    binding: BindingRef
    baseline: ReasoningMethodRef
    recommended: tuple[ReasoningMethodRef, ...]  # from the advisor's qualifying set; may be empty
    challengers: ChallengerSamplingPolicy
    catalog: ReasoningMethodRef
    preregistered_by: str
    preregistered_at: datetime
    plan_digest: str

@dataclass(frozen=True)
class BindingLineage:                           # AssessedSystemBinding has no parent field (system_identity.py:276-290)
    binding_digest: str
    parent_binding_digest: Optional[str]
    superseding_reason: str                     # e.g. "assessment <digest> INSUFFICIENT_QUALITY"
```

**Approval.** Not a contract of this package. A `SUFFICIENT_PARETO_EFFICIENT`
assessment makes a binding **eligible**; the approval artifact is produced by
Decision Authority and references `assessment_digest`, `binding_digest` and
`plan_digest`. This package defines no approval type, so that it can never
approve.

**Pilot status.** `deployment_environment_ref` naming a pilot environment
(`system_identity.py:288`) `[V]` marks a binding as under assessment. No new
state is added; `authorizes_deployment` remains `False` on every readiness
trace `[V]`.

**Reassessment triggers, exact.** An assessment is stale, and no approval may
cite it, when any of the digests it binds no longer matches the live object:
`binding_digest` (any change to model, prompt, tools, policy or method
version changes `configuration_digest`), `task_class_digest` (including a new
`sufficiency` rule version), `catalog_version`, or any `input_record_digest`
superseded by a newer lineage record. Staleness is decidable by digest
equality alone; no narrower rule exists in v1.

**Unresolved 8.1 — whether a `PilotPlan` may run with an empty `recommended`
set.** (A) Yes: baseline plus challengers alone measure coverage and false
exclusion; (B) No: a plan with nothing to test against is refused; (C) Yes,
but the result cannot feed advisor evaluation. **Recommendation: A.** The
advisor's appropriate-abstention measure needs plans that ran despite an
empty qualifying set.

---

## 9. The minimum first implementation slice

**Slice 1 delivers, and nothing more:**

1. Package `ugence-reasoning-method-governance` skeleton in the
   `agent-value-readiness` layout (`src/…/contracts/`, four test sub-suites,
   distribution self-check script) `[V]`.
2. Contracts of §2, §3, §4, §5 and §7 as frozen dataclasses with the refusal
   rules stated, digests via `ugence_jcs`, and pinned schema-version literals.
3. Vocabulary-pin tests: `CountBasis`, `UsageAvailabilityToken` and
   `TokenUsageSnapshot` fields against `context-minimization`;
   `structural_characteristics` and `declared_signals` against
   `ComplexitySignal` values; `reversibility` against
   `external_actions.Reversibility` — each under a test-only import with the
   boundary test forbidding the runtime import.
4. A reference comparison implementation `compare(request) -> result` in the
   same package, ported from `experiments/workflow_fit_study/study.py`'s
   `assess` with its ten tests re-expressed against the contracts, including
   the mutation checks already proven in PR #1566.
5. An adapter **in `experiments/`, not in the package**, that maps the study's
   `RunRecord` to `ReasoningMethodExecutionRecord` with the mandatory
   `OBSERVED/UNATTESTED/UNVERIFIED` axes, so the existing harness produces
   governed records.
6. A CI workflow in the pattern of `workflow-fit-study-ci.yml`.

**Explicitly excluded from slice 1:** the advisor (rule-derived or otherwise);
`ugence-readiness-comparison` as a package (its port contracts ship in the
first package and move later); any Agent Runtime `LLMClient`; attestation or
verification; any `agent-value-readiness` change; any catalog content beyond a
test fixture; any Constitution binding; any numeric threshold, coverage
figure or sampling rate.

**Definition of done:** boundary test proves no `agentic` import; every
refusal rule has a failing-input test; the reference comparison reproduces the
four outcomes from PR #1566's fixtures; the harness adapter round-trips one
study into records whose digests are stable across two runs.

---

## 10. Owner ballot `[R]`

Ratifying all five commissions slice 1 as specified in §9. Each item names its
recommendation; "ratify as recommended" is a complete answer.

1. **Placement and dependencies** — two packages as in §1; slice 1 ships only
   `ugence-reasoning-method-governance`; telemetry vocabulary mirrored and
   pinned by test (1.1-B); reversibility mirrored and pinned (3.2); prohibited
   imports enforced by boundary test.
2. **Catalog membership and task-class vocabulary** — initial catalog is the
   seven `WorkflowType` members with honest `implementation_status` (2.1-B);
   `ConsequenceClass = {NEGLIGIBLE, RECOVERABLE, MATERIAL, SEVERE}` with
   `{MATERIAL, SEVERE}` as the high-consequence set for the §11.3 refusal
   (3.1-B); compatibility is digest equality.
3. **Execution-record lifecycle** — append-only with supersession by
   `parent_record_digest`; no revocation in v1 (4.1-A); free-string issuer
   identity in v1 (4.2-A); every same-process record fixed at
   `OBSERVED/UNATTESTED/UNVERIFIED`; artifacts by reference only, with
   `ArtifactKind` excluding traces, prompts and transcripts.
4. **Comparison rules** — the four-outcome derivation of §5 exactly, including
   the joint quality-and-resource domination test under `IMPROVEMENT_VALUED`
   and strict ties; dimensions per 5.1-B with `dimensions_compared` recorded;
   attainment representation deferred to composite ballot 4 (7.1-C).
5. **Commissioning** — slice 1 scope, exclusions and definition of done as in
   §9; approval remains a Decision Authority artifact outside this package;
   pilot status by `deployment_environment_ref`; revision lineage by
   `BindingLineage`; reassessment on any bound-digest change; pilots may run
   with an empty recommended set (8.1-A); §6 promotion rule adopted, with the
   capture boundary per 6.1-A for approval-bound pilots and 6.1-B for
   research runs only.

No constant, threshold, coverage minimum, sampling rate or acceptance
criterion is ratified by this ballot. Composite ballots 2–5, Advisor decisions
1, 3 and 5, and Workflow-Fit decision 1 remain `[R]` and are not needed for
slice 1.
