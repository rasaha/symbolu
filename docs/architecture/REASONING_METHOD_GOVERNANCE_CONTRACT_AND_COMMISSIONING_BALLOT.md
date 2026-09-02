# Reasoning Method Governance — Contract Specification and Commissioning Ballot

**Status:** implementable specification for owner ratification, **revision 2**
(correction pass of 2026-09-02 applied; §12 lists the twelve corrections).
Nothing here is implemented and no ballot is recorded. It turns the six owner
rulings of 2026-09-02 into contracts with exact fields, and ends with a ballot
that, once ratified, commissions the first implementation slice as
**research-only** work.
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
package trusting the runtime's own word and without any string field
promoting evidence?** Answer: six contracts (§2–§5), two authority envelopes
specified but not issued (§6), two ports (§7), one append-only record whose
evidence status is a constant (§4), and one comparison engine in its own
package (§9). Everything else is an option set for the owner or an explicit
exclusion.

**Conventions adopted throughout** `[V]`: frozen dataclasses with
`__post_init__` validation, as in `governance-contracts`, `uvi-policy-contracts`
and `agent-value-readiness` (`system_identity.py:259`, `thresholds.py:31`);
digests are lowercase 64-hex SHA-256 computed with `ugence_jcs.canonical_sha256_hex`
(`packages/jcs/src/ugence_jcs/canon.py:129`, no prefix, no envelope, `set_paths`
and `nfc_paths` empty); every contract carries a pinned `schema_version`
literal; decimals travel as strings; nothing numeric is defaulted; a
constructor **refuses** (raises a typed error carrying a code from §11) rather
than coercing.

---

## 1. Capability placement and package ownership

**Ruling applied.** Advisor §8.2 ratifies a neutral, versioned record boundary
with an adapter and no direct import. Composite §10.1 assigns comparison to a
separately commissioned component upstream of `agent-value-readiness`.
Workflow-Fit §11.5 makes reasoning efficiency a property of the selection
policy within the exact `AssessedSystemBinding`, so no `CapabilityDimension`
(`agent-value-readiness …/contracts/enums.py:121`) is added `[V]`.

**Stable ownership, no planned moves.**

| Package | Distribution / import | Owns permanently | Depends on |
|---|---|---|---|
| `packages/capabilities/reasoning-method-governance` | `ugence-reasoning-method-governance` / `ugence_reasoning_method_governance` | shared reasoning-method contracts: §2 catalog and refs, §3 profile, class identity and comparison policy, §4 execution record, §5 fit assessment, §6 envelope shapes, §7 port contracts, §8 research plan shape, §11 error codes | `ugence-governance-contracts`, `ugence-uvi-policy-contracts`, `ugence-jcs` |
| `packages/capabilities/readiness-comparison` | `ugence-readiness-comparison` / `ugence_readiness_comparison` | the comparison **implementation**: the pure engine of §7, its refusal logic, its tests | the above package, `ugence-governance-contracts`, `ugence-uvi-policy-contracts` |

Both packages ship in slice 1 (§9). Nothing is placed in one package for a
later move. `readiness-comparison` is the component the composite ruling
commissions; reasoning-method fit is its first request type, and a later
request type for readiness attainments is additive.

**Prohibited dependencies, enforced by a boundary test as `agentic-proposer`
does** `[V]` (its `tests/test_boundaries.py` and forbidden-wheel list): neither
package may import `agentic`, `agentic_framework`, `reasoning_workflows`,
`adaptive_prompts`, `external_actions` or `WorkflowResult`;
`agent-value-readiness` imports neither package until a later ruling binds
attainments into readiness; `reasoning-method-governance` never imports
`readiness-comparison`.

**Unresolved 1.1 — where the telemetry vocabulary comes from.** The record
needs the `TokenCountBasis`, `UsageAvailability` members and the
`ProviderTokenUsage` field set, which live in the `context-minimization`
capability (`token_accounting.py:135,166,285`) `[V]`.

| Option | Consequence |
|---|---|
| A. Runtime dependency on `ugence-context-minimization` | a contracts package depends on a minimization capability |
| B. Mirror the members as string enums in `reasoning-method-governance`, pinned by a test that imports `context-minimization` under `[test]` only | zero runtime coupling; drift fails CI; two definitions exist |
| C. Move the three types to `governance-contracts` | cleanest long-term; requires a `context-minimization` release and a CM-TA1 change |

**Recommendation: B now, C as a follow-up ruling.** B is the existing
mirror-and-pin pattern (`agentic-proposer/tests/s1_specification_mirror.py`) `[V]`.

---

## 2. `ReasoningMethodCatalog`, `ReasoningMethodCatalogRef`, `ReasoningMethodRef`

The catalog is the governed repertoire. It is **not** the seven-member
`WorkflowType` enum (`reasoning_workflows.py:78-86`) `[V]`; the landscape
evaluation's fifteen-method repertoire is the wider vocabulary.

```python
CATALOG_SCHEMA_VERSION = "reasoning_method.catalog.v1"

class ImplementationEvidenceKind(str, Enum):
    CONCRETE_CLASS_REGISTERED = "CONCRETE_CLASS_REGISTERED"   # a class implementing the method is registered in a runtime registry
    STUB_EXECUTION_COMPLETED = "STUB_EXECUTION_COMPLETED"     # execute() ran to a result with a stub client
    UNIT_TESTS_PRESENT = "UNIT_TESTS_PRESENT"                 # tests exercising the class exist in the runtime tree
    EXECUTION_RECORD_EMITTED = "EXECUTION_RECORD_EMITTED"     # at least one §4 record exists for this method

@dataclass(frozen=True)
class ImplementationEvidence:
    kind: ImplementationEvidenceKind
    ref: str                        # file path, test path or record_digest
    observed_at: datetime           # tz-aware

class ImplementationStatus(str, Enum):        # DERIVED from evidence by the rule below; never declared directly
    EXECUTABLE_TESTED = "EXECUTABLE_TESTED"           # CONCRETE_CLASS_REGISTERED + STUB_EXECUTION_COMPLETED + UNIT_TESTS_PRESENT
    EXECUTABLE_UNTESTED = "EXECUTABLE_UNTESTED"       # CONCRETE_CLASS_REGISTERED + STUB_EXECUTION_COMPLETED
    REGISTERED_NOT_EXECUTED = "REGISTERED_NOT_EXECUTED"  # CONCRETE_CLASS_REGISTERED only
    NO_IMPLEMENTATION_EVIDENCE = "NO_IMPLEMENTATION_EVIDENCE"

@dataclass(frozen=True)
class ReasoningMethodCatalogRef:
    catalog_id: str
    catalog_version: str
    catalog_digest: str             # sha-256 hex; refuses blank or malformed

@dataclass(frozen=True)
class ReasoningMethodRef:
    catalog: ReasoningMethodCatalogRef
    method_id: str
    method_version: str             # all fields non-blank; a ref never denotes a catalog alone

@dataclass(frozen=True)
class ReasoningMethodEntry:
    method_id: str
    method_version: str
    display_name: str
    implementation_evidence: tuple[ImplementationEvidence, ...]
    declared_signals: tuple[str, ...]       # tokens pinned to ComplexitySignal values (adaptive_prompts.py:88)
    requirement_refs: tuple[str, ...]       # tool / evidence requirements, opaque refs
    runtime_binding_ref: str = ""           # opaque, e.g. "agentic.reasoning_workflows.WorkflowType.TREE_OF_THOUGHT"; never imported
    policy_refs: tuple[str, ...] = ()       # MetricClaim.policy_refs shape (evidence.py:386)

    @property
    def implementation_status(self) -> ImplementationStatus: ...   # derived by the rule in ImplementationStatus comments

@dataclass(frozen=True)
class ReasoningMethodCatalog:
    schema_version: Literal["reasoning_method.catalog.v1"]
    catalog_id: str
    catalog_version: str
    entries: tuple[ReasoningMethodEntry, ...]   # unique (method_id, method_version); sorted by that key
    issuer_identity: str
    issued_at: datetime
    catalog_digest: str                         # jcs digest over all fields except catalog_digest

    def ref(self) -> ReasoningMethodCatalogRef: ...
    def method_ref(self, method_id: str, method_version: str) -> ReasoningMethodRef: ...  # refuses unknown entry
```

**Refusals (§11 codes):** `CATALOG_DUPLICATE_ENTRY`, `CATALOG_UNSORTED`,
`REF_BLANK_FIELD`, `DIGEST_MALFORMED`, `SIGNAL_TOKEN_UNKNOWN`,
`SCALAR_LABEL_FIELD_PRESENT` (an entry type with any field named `cost`,
`latency_class`, `resource_level` or similar is rejected at class definition by
a test over the field set, per the advisor note §5 prohibitions),
`STATUS_DECLARED_NOT_DERIVED` (an entry carrying a literal status field).

**Evidence-derived status of the seven `WorkflowType` members (2026-09-02)**
`[V]`. All seven have a concrete class that returns its `workflow_type`
(`reasoning_workflows.py:291,396,523,657,774,898,1011`), all seven are
registered by `WorkflowRegistry._register_defaults` (`:1243` onward), all
seven ran `execute` to a `WorkflowResult` with a stub `LLMClient` in this
session (runtime-reported and harness-observed call counts agreed: 4, 5, 2, 4,
6, 4, 6), and all seven are exercised in
`agentic/agentic_framework/tests/test_reasoning_workflows.py` `[V]`. Under the
derivation rule every member is `EXECUTABLE_TESTED`. **Correction:** revision 1
of this document said three of the seven were implemented; that figure was the
landscape evaluation's count over the fifteen-method repertoire, not the enum.
Evidence, not a prior note, sets the status.

**Unresolved 2.1 — initial catalog membership.**

| Option | Consequence |
|---|---|
| A. The seven `WorkflowType` members, each with the four evidence kinds cited above | every entry is executable; advisor vocabulary equals the runtime enum; the repertoire beyond the enum is not yet nameable |
| B. The seven plus the landscape's remaining eight with `NO_IMPLEMENTATION_EVIDENCE` | complete vocabulary; eight entries no pilot can test, inflating every coverage denominator |
| C. The seven now, with a ratified rule that an entry may be added only with at least `CONCRETE_CLASS_REGISTERED` evidence | executable-only catalog that can grow; the rule itself needs ratifying |

**Recommendation: C.** Coverage (advisor note §6) is measured against catalog
size, so untestable entries would make the measure meaningless, and the
growth rule keeps status evidence-derived.

---

## 3. Task profile, task-class identity and comparison policy

**Ruling applied.** Advisor §8.4 binds ten coordinates. Workflow-Fit §11.3
requires a versioned per-class sufficiency rule. The profile is the
developer's assertion; the class identity is the governed object; the
**comparison policy** is part of the identity and carries every rule the
engine applies, so nothing is decided by fallback.

```python
PROFILE_SCHEMA_VERSION = "reasoning_method.task_profile.v1"
TASK_CLASS_SCHEMA_VERSION = "reasoning_method.task_class.v1"

class TaskReversibility(str, Enum):           # task-class concern; distinct from action-level Reversibility (external_actions.py:155)
    OUTCOME_REVERSIBLE = "OUTCOME_REVERSIBLE"           # the task's outcome can be fully undone after delivery
    OUTCOME_COMPENSATABLE = "OUTCOME_COMPENSATABLE"     # cannot be undone, can be made good by a further governed action
    OUTCOME_IRREVERSIBLE = "OUTCOME_IRREVERSIBLE"
    UNDETERMINED = "UNDETERMINED"                       # allowed on a profile; refused on a class identity

class ConsequenceClass(str, Enum):
    NEGLIGIBLE = "NEGLIGIBLE"
    RECOVERABLE = "RECOVERABLE"
    MATERIAL = "MATERIAL"
    SEVERE = "SEVERE"

class SufficiencyKind(str, Enum):
    THRESHOLD_BASED = "THRESHOLD_BASED"
    IMPROVEMENT_VALUED = "IMPROVEMENT_VALUED"

class ResourceDimension(str, Enum):
    LLM_CALLS = "LLM_CALLS"
    TOTAL_TOKENS = "TOTAL_TOKENS"
    # duration is excluded by rule; depth_used is excluded by rule (workflow-fit note §3)

@dataclass(frozen=True)
class AggregationRef:                          # a governed, versioned aggregation; never an implicit mean
    aggregation_method_id: str
    aggregation_method_version: str
    calculation_ref: str                       # MetricClaim.calculation_ref shape (evidence.py:347 ff.)

@dataclass(frozen=True)
class EvidenceAdmissionRef:                    # points at an authority result; presence is not admission (§7 resolves it)
    authority_identity: str
    authority_result_ref: str
    admitted_digest: str                       # sha-256 hex of the admitted object

@dataclass(frozen=True)
class SufficiencyRule:
    rule_id: str
    rule_version: str
    kind: SufficiencyKind
    threshold: GovernedThreshold               # uvi-policy-contracts thresholds.py:31; literal XOR benchmark_ref
    supporting_evidence_admission: Optional[EvidenceAdmissionRef] = None

@dataclass(frozen=True)
class ComparisonPolicy:
    policy_id: str
    policy_version: str
    sufficiency: SufficiencyRule
    required_dimensions: tuple[ResourceDimension, ...]     # non-empty, unique, sorted; ALL are required on every compared record
    quality_aggregation: Optional[AggregationRef]          # None ⇒ exactly one governed quality result per method is required
    # quality direction is DERIVED from sufficiency.threshold.comparator (§5), never declared

@dataclass(frozen=True)
class TaskProfile:                             # developer-reported; never evidence
    schema_version: Literal["reasoning_method.task_profile.v1"]
    profile_id: str
    domain_ref: str
    intended_outcome_ref: str
    consequence_class: ConsequenceClass
    reversibility: TaskReversibility
    evidence_requirement_refs: tuple[str, ...]
    tool_requirement_refs: tuple[str, ...]
    structural_characteristics: tuple[str, ...]  # tokens pinned to ComplexitySignal values
    population_ref: str
    policy_refs: tuple[str, ...] = ()            # privacy and regulation by reference only
    declared_by: str = ""
    declared_at: Optional[datetime] = None
    assertion_basis: Literal["DEVELOPER_REPORTED"] = "DEVELOPER_REPORTED"

@dataclass(frozen=True)
class TaskClassIdentity:
    schema_version: Literal["reasoning_method.task_class.v1"]
    task_class_id: str
    domain_ref: str
    intended_outcome_ref: str
    consequence_class: ConsequenceClass
    reversibility: TaskReversibility           # UNDETERMINED refused
    evidence_requirement_refs: tuple[str, ...]
    tool_requirement_refs: tuple[str, ...]
    structural_characteristics: tuple[str, ...]
    population_ref: str
    benchmark_set_ref: str
    benchmark_set_digest: str
    comparison_policy: ComparisonPolicy
    task_class_digest: str                     # jcs digest over the ten coordinates + comparison_policy (policy_id, policy_version, sufficiency.rule_id, sufficiency.rule_version)
```

**Compatibility predicate.** `compatible(a, b)` is `a.task_class_digest ==
b.task_class_digest`. Evidence is shared only under equality; otherwise the
engine emits `COMPARISON_EVIDENCE_ABSENT` with `TASK_CLASS_MISMATCH`. Declared
equivalence between distinct classes is a later ruling `[R]`.

**High-consequence rule (ruling §11.3), where it is applied.** The
**constructor** checks only shape: a `MATERIAL` or `SEVERE` class whose
sufficiency is `THRESHOLD_BASED` must carry a `supporting_evidence_admission`
(`ADMISSION_REF_REQUIRED` otherwise). It does **not** treat that reference as
evidence. The **engine** (§7) refuses `THRESHOLD_ONLY_NOT_ADMITTED` unless the
request supplies a resolved admission whose `admitted_digest` and
`authority_result_ref` match the reference and whose issuing authority is one
the request names as resolved. Presence of a string admits nothing.

**Unresolved 3.1 — consequence vocabulary and the high-consequence set.**

| Option | Consequence |
|---|---|
| A. Reuse `GateCategory`-style tokens from `uvi-policy-contracts` (`enums.py:~101`) | existing vocabulary, but it classifies gates, not consequences |
| B. `ConsequenceClass` as above with `{MATERIAL, SEVERE}` as the high-consequence set | explicit and testable; four new tokens to ratify |
| C. Policy-referenced `consequence_policy_ref` resolved by Policy Authority | no new enum; the shape check cannot run at construction |

**Recommendation: B.** "Loss-dominated" in the ruling is a governed-value
notion with no contract here; option B treats `MATERIAL`/`SEVERE` as the
declared proxy and records that a `loss_profile_ref` coordinate is a later
ruling `[R]`.

**Unresolved 3.2 — task-reversibility vocabulary.** Action reversibility
(`agentic/agentic_framework/external_actions.py:155`, a plain class of four
string constants, not an enum) `[V]` describes whether one external action can
be undone. Task-class reversibility describes whether the task's delivered
outcome can be undone. They are different concerns and are not mirrored.

| Option | Consequence |
|---|---|
| A. `TaskReversibility` as above, governed in `reasoning-method-governance` | four tokens to ratify; clean separation |
| B. Define it in `governance-contracts` as a shared vocabulary | wider reuse; requires a `governance-contracts` release |
| C. Two-axis form: `{outcome_reversibility, compensation_path_ref}` | richer; more to ratify before any class can be declared |

**Recommendation: A**, with B revisited when a second consumer appears.

---

## 4. `ReasoningMethodExecutionRecord`

**Ruling applied.** Advisor §8.2. The v1 record is **permanently** at
`OBSERVED / UNATTESTED / UNVERIFIED`. Those axes are constants of the schema,
not fields a producer fills in. Promotion exists only as separate authority
envelopes (§6) that reference `record_digest`.

```python
RECORD_SCHEMA_VERSION = "reasoning_method.execution_record.v1"
RECORD_V1_SOURCE_BASIS = SourceBasis.OBSERVED                    # governance-contracts evidence.py
RECORD_V1_ATTESTATION_STATUS = AttestationStatus.UNATTESTED      # evidence.py:90
RECORD_V1_VERIFICATION_STATUS = VerificationStatus.UNVERIFIED    # evidence.py:112

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
    capture_refs: tuple[str, ...] = ()          # e.g. ApiCallTokenRecord fingerprints (token_accounting.py:433); informational in v1
    # invariants: AVAILABLE ⇒ token_usage present with ≥1 non-None count; not AVAILABLE ⇒ token_usage None;
    #             llm_calls None ⇒ llm_calls_basis == UNKNOWN; negative counts refused

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
    self_reported_quality: Optional[str]        # decimal-as-string; labelled, never evidence, never read by the engine
    issuer_identity: str                        # informational in v1 (unresolved 4.2)
    captured_at: datetime
    parent_record_digest: Optional[str]         # LINEAGE ONLY (see below)
    record_digest: str

    # constants, exposed read-only so consumers can read them but no producer can set them:
    source_basis: ClassVar[SourceBasis] = RECORD_V1_SOURCE_BASIS
    attestation_status: ClassVar[AttestationStatus] = RECORD_V1_ATTESTATION_STATUS
    verification_status: ClassVar[VerificationStatus] = RECORD_V1_VERIFICATION_STATUS
```

**Canonicalization.** `record_digest = canonical_sha256_hex(payload)` where
`payload` is every instance field except `record_digest`, plus the three
constant axes so that a v2 record with different constants can never collide
with a v1 digest; enums by value, datetimes as RFC 3339 UTC, tuples in
declared order. Two records with the same payload are the same record.

**Lifecycle.** Append-only; a record is never mutated or deleted in v1.
`parent_record_digest` records **lineage only**: that this record was produced
in correction or continuation of another. It confers no authority. No
consumer may treat a child, a leaf, or the latest record as authoritative;
fork resolution, ordering and lineage authority are a separate ruling `[R]`
(unresolved 4.1). The constructor refuses `parent_record_digest ==
record_digest` (`LINEAGE_SELF_REFERENCE`), mirroring rule L-1
(`contracts.py:1071-1077`) `[V]`.

**Refusal rules (constructor, §11 codes):** `DIGEST_MALFORMED`;
`ARTIFACT_KIND_UNKNOWN`; `TELEMETRY_INVARIANT` (the invariants above);
`DECIMAL_UNPARSEABLE` for `self_reported_quality`; `REF_BLANK_FIELD` for
`issuer_identity`, `invocation_id`, `task_class_ref`; `DATETIME_NAIVE`;
`LINEAGE_SELF_REFERENCE`; `EVIDENCE_AXIS_SET_BY_PRODUCER` if any constructor
argument attempts to supply `source_basis`, `attestation_status` or
`verification_status`.

**Disclosure.** The record carries references and digests to artifacts, never
artifact content, prompts or reasoning traces. Access to referenced artifacts
is governed by the store that holds them.

**Unresolved 4.1 — lineage authority.**

| Option | Consequence |
|---|---|
| A. Lineage is informational only; an engine request containing two records in one lineage is refused (`LINEAGE_UNRESOLVED`) | no silent choice; the requester must pick one record explicitly |
| B. Latest-by-`captured_at` is authoritative | simple; timestamps are producer-reported and unattested, so authority rests on an unverified field |
| C. A separate `LineageResolution` authority artifact names the authoritative record | correct; needs an authority that does not exist |

**Recommendation: A for slice 1**, and C when a lineage authority is
commissioned.

**Unresolved 4.2 — issuer identity.** (A) free string, informational; (B)
registered adapter id validated against a package list; (C) signed envelope.
**Recommendation: A for slice 1.** Every v1 record is untrusted by constant,
so the identity cannot change any consumer's treatment of it.

---

## 5. `ReasoningMethodFitAssessment`

**Ruling applied.** Workflow-Fit §11.2 (four names), §11.3 (per-class
versioned rule, no global default), §11.5 (property of the selection policy
within the exact binding, per task class).

```python
FIT_SCHEMA_VERSION = "reasoning_method.fit_assessment.v1"

class FitOutcome(str, Enum):                    # exactly the ratified four (study.py:80-84)
    INSUFFICIENT_QUALITY = "INSUFFICIENT_QUALITY"
    SUFFICIENT_RESOURCE_DOMINATED = "SUFFICIENT_RESOURCE_DOMINATED"
    SUFFICIENT_PARETO_EFFICIENT = "SUFFICIENT_PARETO_EFFICIENT"
    COMPARISON_EVIDENCE_ABSENT = "COMPARISON_EVIDENCE_ABSENT"

class QualityDirection(str, Enum):              # DERIVED from the threshold comparator; never declared
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"        # comparator GTE or GT
    LOWER_IS_BETTER = "LOWER_IS_BETTER"          # comparator LTE or LT
    # comparator EQ or NEQ ⇒ engine refusal UNSUPPORTED_COMPARATOR (ComparisonOperator, enums.py:83)

@dataclass(frozen=True)
class QualityResult:                            # one per (task_class, method); never an implicit aggregate
    method: ReasoningMethodRef
    claim_ref: str                              # MetricClaim.claim_id (evidence.py:347); the governed value
    governed_unit: str                          # must equal threshold.governed_unit
    value: str                                  # decimal-as-string
    aggregation: Optional[AggregationRef]       # required iff the claim was CALCULATED from >1 input claims

@dataclass(frozen=True)
class ResourceDelta:
    dimension: ResourceDimension
    relative_to: ReasoningMethodRef             # explicitly named; never "cheapest sufficient"
    delta: str                                  # decimal-as-string; this method minus relative_to

@dataclass(frozen=True)
class DominationRecord:
    dominator: ReasoningMethodRef
    deltas: tuple[ResourceDelta, ...]           # one per required dimension, relative_to == dominator
    quality_delta: Optional[str]                # present iff IMPROVEMENT_VALUED; this method minus dominator, in the derived direction

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
    quality_direction: Optional[QualityDirection]
    quality_margin: Optional[str]               # value vs threshold in the derived direction; None iff evidence absent
    deltas_vs_baseline: tuple[ResourceDelta, ...]   # relative_to == baseline; empty iff evidence absent or INSUFFICIENT_QUALITY
    dominated_by: tuple[DominationRecord, ...]
    dimensions_compared: tuple[ResourceDimension, ...]  # always == comparison_policy.required_dimensions
    comparison_policy_id: str
    comparison_policy_version: str
    quality_result_ref: str                     # the QualityResult.claim_ref used
    input_record_digests: tuple[str, ...]
    evidence_status_source: Literal["RECORD_CONSTANTS_V1"]   # slice 1: OBSERVED/UNATTESTED/UNVERIFIED by construction
    usage_scope: Literal["RESEARCH_ONLY"]       # slice 1 assessments are not approval-bearing
    assessor_identity: str
    assessed_at: datetime
    reason: str
    assessment_digest: str
```

**Outcome rules, exact.** Let `P` be the class's `comparison_policy`, `τ`
its `threshold`, `dir` the direction derived from `τ.comparator`, `Q(m)` the
single `QualityResult.value` for method `m`, and `R(m)` the vector of
`P.required_dimensions` read from `m`'s records.

1. **Refusal before assessment** (request-level, §7): `UNSUPPORTED_COMPARATOR`
   when `τ.comparator ∈ {EQ, NEQ}`; `UNIT_MISMATCH` when any
   `QualityResult.governed_unit ≠ τ.governed_unit`; `SCALE_UNSUPPORTED` when
   a value is not a finite decimal; `AGGREGATION_UNDECLARED` when a method has
   more than one quality claim and `P.quality_aggregation is None`, or a
   `QualityResult` carries an `aggregation` that differs from
   `P.quality_aggregation`.
2. `COMPARISON_EVIDENCE_ABSENT` for a method when any holds: no
   `QualityResult` for it; zero records for it; zero records for the
   baseline; any input record's `task_class_digest` differs; the quality
   claim's `input_evidence_refs` or `evidence_refs` include a record's
   `self_reported_quality`; **any required dimension is unavailable on any
   record of any compared method** (no fallback to fewer dimensions, ever);
   a `THRESHOLD_ONLY_NOT_ADMITTED` refusal applies.
3. `INSUFFICIENT_QUALITY` when `Q(m)` fails `τ` under its comparator.
4. Otherwise, under `THRESHOLD_BASED`: `SUFFICIENT_RESOURCE_DOMINATED` when
   some other sufficient method `m'` has `R(m') ≤ R(m)` on every required
   dimension and `<` on at least one. Under `IMPROVEMENT_VALUED`: the same
   **and** `Q(m')` is not worse than `Q(m)` in `dir`. Ties on every dimension
   are not domination. Each dominator is recorded with its own deltas.
5. Otherwise `SUFFICIENT_PARETO_EFFICIENT`.

Margins and deltas are attributes, never combined. No weights exist. No
arithmetic is performed on quality values beyond the comparator test and the
signed difference; any aggregation happened upstream under a named
`AggregationRef`, and the engine records which.

**Resource value per record.** `LLM_CALLS` reads `telemetry.llm_calls`;
`TOTAL_TOKENS` reads `telemetry.token_usage.total_tokens`. A method with more
than one record for the class requires `P.quality_aggregation`'s companion
**resource aggregation** to be named too; in slice 1 a method with more than
one record is `COMPARISON_EVIDENCE_ABSENT` with `RESOURCE_AGGREGATION_UNDECLARED`
unless the policy names one (unresolved 5.1).

**Unresolved 5.1 — aggregation over repeated executions.**

| Option | Consequence |
|---|---|
| A. Slice 1 admits exactly one record and one quality claim per method per class; repeats are refused | no aggregation anywhere; studies must pre-aggregate under a governed calculation |
| B. `ComparisonPolicy` names one `AggregationRef` used for both quality and each resource dimension | one governed method; may be wrong for counts versus scores |
| C. Separate `quality_aggregation` and `resource_aggregation` refs | precise; two methods to ratify |

**Recommendation: A for slice 1, C as the follow-up.** The merged harness's
mean over cases becomes a research-only calculation that emits one governed
claim per method with `transformation_method = CALCULATED` and a
`calculation_ref` naming it; the engine never averages.

---

## 6. Telemetry binding and promotion controls

Promotion is modelled as **authority-produced envelopes**, never as record
fields. A v1 record is untrusted by construction; only an envelope from an
authority other than the producer can say otherwise, and the engine reads
status from envelopes, not from strings.

```python
ATTESTATION_ENVELOPE_SCHEMA_VERSION = "reasoning_method.attestation_envelope.v1"
VERIFICATION_ENVELOPE_SCHEMA_VERSION = "reasoning_method.verification_envelope.v1"

@dataclass(frozen=True)
class AttestationEnvelope:                      # produced by a capture boundary outside the method's process
    schema_version: Literal["reasoning_method.attestation_envelope.v1"]
    envelope_id: str
    record_digest: str                          # the record attested
    attester_identity: str
    capture_boundary_ref: str                   # what captured it, e.g. a CM-TA1 ApiCallTokenRecord fingerprint set
    attested_fields: tuple[str, ...]            # e.g. ("telemetry.llm_calls", "telemetry.token_usage.total_tokens")
    attested_at: datetime
    envelope_digest: str

@dataclass(frozen=True)
class VerificationEnvelope:                     # produced by the Trusted Evidence Authority
    schema_version: Literal["reasoning_method.verification_envelope.v1"]
    envelope_id: str
    record_digest: str
    attestation_envelope_digest: str            # verification presupposes attestation
    verifier_identity: str
    verification_ref: str
    verified_fields: tuple[str, ...]
    verified_at: datetime
    envelope_digest: str

@dataclass(frozen=True)
class EvidenceStatusView:                       # computed by the engine from record + envelopes; never stored on the record
    record_digest: str
    source_basis: SourceBasis                   # always OBSERVED for v1
    attestation_status: AttestationStatus       # ATTESTED iff a matching AttestationEnvelope is supplied AND its attester is a resolved authority in the request
    verification_status: VerificationStatus     # VERIFIED iff a matching VerificationEnvelope is supplied AND its verifier is a resolved authority in the request
    attested_fields: tuple[str, ...]
    verified_fields: tuple[str, ...]
```

**Rules.** An envelope whose `record_digest` matches no supplied record is
refused (`ENVELOPE_ORPHAN`). An envelope whose issuer is not in the request's
`resolved_authorities` leaves the status unchanged and is reported in
`ignored_envelopes`; a string in an envelope promotes nothing by itself. The
same identity may not appear as both a record's `issuer_identity` and an
envelope's `attester_identity` (`SELF_ATTESTATION`), applying the ratified
no-self-attestation rule (`ADR_UGENCE_POLICY_AUTHORITY.md:184`) `[V]`.

**Slice 1 issues no envelopes.** Every slice 1 assessment carries
`evidence_status_source = "RECORD_CONSTANTS_V1"` and `usage_scope =
"RESEARCH_ONLY"`. The envelope shapes ship so that the engine's status logic
is tested against synthetic envelopes, and so the capture-boundary work can
target a fixed shape.

**Unresolved 6.1 — the capture boundary, deferred beyond slice 1.**
`LLMClient.call(self, prompt: str) -> str` (`reasoning_workflows.py:70`) `[V]`
returns text only; no usage passes through it. Agent Runtime wiring is
excluded from slice 1, so no option here is a slice 1 requirement.

| Option | Consequence |
|---|---|
| A. Pilots through Agent Runtime so CM-TA1 `ApiCallTokenRecord`s exist (`token_accounting.py:433`) `[V]` | attested tokens and call counts; needs an `LLMClient` backed by Agent Runtime, which is new work |
| B. In-process client wrapper recording provider usage | same-process; can never yield an `AttestationEnvelope`; research only |
| C. Provider receipts fetched by `provider_request_id` | independent where the provider exposes usage by request id |

**Recommendation: A when a later slice commissions the capture boundary; B
for slice 1 research runs, which stay untrusted.** Workflow-Fit §11.4 (trust
controls) remains `[R]`; this section specifies shapes, not the ruling.

---

## 7. Comparison-engine ports

**Ruling applied.** Composite §10.1: a separately commissioned component
performs deterministic comparison and emits comparison records; readiness
consumes them. The Registry computes nothing (B-12) `[V]`. The engine lives in
`ugence-readiness-comparison`; the port contracts live in
`ugence-reasoning-method-governance`.

```python
COMPARISON_REQUEST_SCHEMA_VERSION = "readiness_comparison.request.v1"
COMPARISON_RESULT_SCHEMA_VERSION = "readiness_comparison.result.v1"

@dataclass(frozen=True)
class ResolvedAuthority:                        # an authority the requester asserts has been resolved for this request
    authority_identity: str
    resolution_ref: str                         # the policy decision or admission result, by reference

@dataclass(frozen=True)
class ResolvedAdmission:                        # satisfies a SufficiencyRule.supporting_evidence_admission
    authority_identity: str
    authority_result_ref: str
    admitted_digest: str

@dataclass(frozen=True)
class Refusal:
    code: RefusalCode                           # §11
    detail: str
    method: Optional[ReasoningMethodRef] = None # None ⇒ request-level

@dataclass(frozen=True)
class ReadinessComparisonRequest:
    schema_version: Literal["readiness_comparison.request.v1"]
    request_id: str
    task_class: TaskClassIdentity
    catalog: ReasoningMethodCatalogRef
    baseline: ReasoningMethodRef
    candidates: tuple[ReasoningMethodRef, ...]  # unique; baseline may appear
    records: tuple[ReasoningMethodExecutionRecord, ...]
    quality_results: tuple[QualityResult, ...]  # at most one per method (5.1-A)
    quality_claims: tuple[MetricClaim, ...]     # governance-contracts evidence.py:347; one per QualityResult.claim_ref
    attestation_envelopes: tuple[AttestationEnvelope, ...] = ()
    verification_envelopes: tuple[VerificationEnvelope, ...] = ()
    resolved_authorities: tuple[ResolvedAuthority, ...] = ()
    resolved_admissions: tuple[ResolvedAdmission, ...] = ()
    requester_identity: str = ""

@dataclass(frozen=True)
class ReadinessComparisonResult:
    schema_version: Literal["readiness_comparison.result.v1"]
    request_id: str
    request_digest: str
    assessments: tuple[ReasoningMethodFitAssessment, ...]   # one per candidate, always; absence is an outcome
    refusals: tuple[Refusal, ...]                            # request-level ⇒ every assessment is COMPARISON_EVIDENCE_ABSENT
    evidence_status: tuple[EvidenceStatusView, ...]         # one per record
    ignored_envelopes: tuple[str, ...]                       # envelope digests whose issuer was not resolved
    engine_identity: str
    engine_version: str
    produced_at: datetime
    result_digest: str
```

**Engine obligations.** A pure function of the request: no I/O, no clock
other than `produced_at`, no normalization or unit conversion, no fetch of a
`benchmark_ref` (an unresolvable threshold is `THRESHOLD_UNRESOLVABLE`), no
read of `self_reported_quality`, no averaging, no fallback across dimensions,
no inference of authority from names. Determinism: the same request bytes
produce the same `result_digest` modulo `produced_at`, which is excluded from
`result_digest`.

**Unresolved 7.1 — attainment record for readiness.** No `Attainment*` class
exists anywhere `[V]`, and composite ballot 4 remains `[R]`. (A) the result is
the attainment record; (B) a thinner projection; (C) defer to composite
ballot 4. **Recommendation: C.** The reasoning-method path needs only the
result.

---

## 8. Lifecycle: research plan now, approval and revision deferred

**What is specified.** A research plan shape, so that slice 1 studies declare
their comparison set and sampling policy in advance and the advisor's later
coverage measure has a denominator.

```python
class SamplingKind(str, Enum):
    PREREGISTERED = "PREREGISTERED"
    RISK_BASED = "RISK_BASED"
    RANDOMIZED = "RANDOMIZED"

@dataclass(frozen=True)
class ChallengerSamplingPolicy:
    kind: SamplingKind
    policy_ref: str                             # the preregistration, risk rule or seed specification
    declared_coverage_ref: str                  # the coverage declaration, by reference; no number here

@dataclass(frozen=True)
class ResearchComparisonPlan:
    schema_version: Literal["reasoning_method.research_plan.v1"]
    plan_id: str
    task_class: TaskClassIdentity
    binding: BindingRef
    catalog: ReasoningMethodCatalogRef
    baseline: ReasoningMethodRef
    recommended: tuple[ReasoningMethodRef, ...]  # may be empty (unresolved 8.1)
    challengers: ChallengerSamplingPolicy
    usage_scope: Literal["RESEARCH_ONLY"]
    preregistered_by: str
    preregistered_at: datetime
    plan_digest: str
```

**What is deliberately not specified in this revision.**

- **No approval eligibility.** A `SUFFICIENT_PARETO_EFFICIENT` assessment
  under `RESEARCH_ONLY` scope makes nothing eligible for anything. No
  Decision Authority responsibility is assigned here.
- **No pilot state.** `deployment_environment_ref` on `AssessedSystemBinding`
  (`system_identity.py:288`) `[V]` is an opaque string; it is not an
  enforceable lifecycle state and this document does not treat it as one.
- **No revision lineage contract and no reassessment trigger.** Advisor
  decision 5 (binding lifecycle, reassessment, post-pilot approval) remains
  `[R]`. Until it is taken, a changed configuration is simply a different
  `binding_digest`, and an assessment says only which digests it was computed
  from.

**Unresolved 8.1 — a plan with an empty `recommended` set.** (A) permitted,
so abstention studies can run; (B) refused; (C) permitted but excluded from
advisor evaluation. **Recommendation: A.**

**Unresolved 8.2 — lifecycle package** (options for the later ruling, not
for slice 1): (A) lifecycle contracts join `reasoning-method-governance`; (B)
they join `governance-contracts` beside `AssessedSystemBinding`; (C) a
dedicated integration package under `packages/integration/`.
**Recommendation: B**, because the binding whose lifecycle is at issue lives
there.

---

## 9. The minimum first implementation slice — research-only

**Slice 1 delivers, and nothing more:**

1. Package `ugence-reasoning-method-governance` in the `agent-value-readiness`
   layout (`src/…/contracts/`, four test sub-suites, distribution self-check
   script) `[V]`, holding the contracts of §2–§8 and the error codes of §11
   as frozen dataclasses with the stated refusals, digests via `ugence_jcs`,
   pinned schema-version literals, and the v1 evidence axes as class
   constants.
2. Package `ugence-readiness-comparison` holding `compare(request) ->
   result` as a pure function implementing §5 and §7 exactly, its refusal
   logic, and its tests, including the four-outcome fixtures and the mutation
   checks proven in PR #1566 re-expressed against the contracts.
3. Vocabulary-pin tests: `CountBasis`, `UsageAvailabilityToken` and
   `TokenUsageSnapshot` fields against `context-minimization`;
   `structural_characteristics` and `declared_signals` against
   `ComplexitySignal` values; each under a test-only import, with the
   boundary test forbidding the runtime import in both packages.
4. The contract-consistency matrix of §11 as executable tests: every example
   object constructs; every prohibited state is refused with the named code.
5. An adapter **in `experiments/`**, not in either package, mapping the
   study's `RunRecord` to `ReasoningMethodExecutionRecord`, and its
   per-case mean to one `MetricClaim` with `transformation_method =
   CALCULATED` and a `calculation_ref` naming the research aggregation, so
   the existing harness produces governed inputs under `RESEARCH_ONLY`.
6. A CI workflow in the pattern of `workflow-fit-study-ci.yml`.

**Explicitly excluded from slice 1:** the advisor; any Agent Runtime
`LLMClient` or capture boundary; issuing any `AttestationEnvelope` or
`VerificationEnvelope`; any approval, eligibility, pilot-state, revision or
reassessment contract; any `agent-value-readiness` change; catalog content
beyond a test fixture built from the seven-member evidence in §2; any
Constitution binding; any numeric threshold, coverage figure, sampling rate
or acceptance criterion.

**Definition of done:** boundary tests prove no forbidden import in either
package; every §11 row passes; the engine reproduces the four outcomes from
PR #1566's fixtures; the harness adapter round-trips one study into records
and claims whose digests are stable across two runs; every assessment
produced carries `usage_scope = "RESEARCH_ONLY"`.

---

## 10. Owner ballot `[R]`

Ratifying all five commissions slice 1 as specified in §9, as research-only
work. Each item names its recommendation; "ratify as recommended" is a
complete answer.

1. **Placement and ownership** — two packages with stable ownership as in
   §1: shared contracts in `ugence-reasoning-method-governance`, the
   comparison implementation in `ugence-readiness-comparison`, both in slice
   1, no planned moves; telemetry vocabulary mirrored and pinned by test
   (1.1-B); forbidden imports enforced by boundary test in both packages.
   *Options: 1.1-A / 1.1-B / 1.1-C. Recommendation: 1.1-B.*
2. **Catalog and task-class vocabulary** — `ReasoningMethodCatalogRef` and
   `ReasoningMethodRef` as in §2 with no blank-method refs; implementation
   status derived from evidence, with the seven `WorkflowType` members at
   `EXECUTABLE_TESTED` on the cited evidence and a growth rule requiring
   registered-class evidence (2.1-C); `ConsequenceClass` with
   `{MATERIAL, SEVERE}` as the high-consequence set (3.1-B); governed
   `TaskReversibility` distinct from action reversibility (3.2-A);
   compatibility by digest equality.
   *Options: 2.1-A/B/C, 3.1-A/B/C, 3.2-A/B/C. Recommendations: C, B, A.*
3. **Execution record and evidence** — v1 record permanently at
   `OBSERVED/UNATTESTED/UNVERIFIED` as class constants; attestation and
   verification only as authority envelopes referencing `record_digest`, with
   status computed from envelopes whose issuers are resolved in the request;
   append-only lifecycle; `parent_record_digest` as lineage only, with
   two-records-in-one-lineage refused (4.1-A); free-string issuer identity
   (4.2-A); artifacts by reference only.
   *Options: 4.1-A/B/C, 4.2-A/B/C. Recommendations: A, A.*
4. **Comparison policy and rules** — required dimensions declared in the
   class's `ComparisonPolicy`, all required on every record, no fallback;
   quality direction derived from the comparator with `EQ`/`NEQ`, unit
   mismatch and non-decimal scales refused; exactly one governed quality
   result per method in slice 1 with any aggregation named upstream (5.1-A);
   deltas relative to the named baseline and to each named dominator; the
   §11.3 high-consequence rule applied by the engine against a resolved
   admission, never by reference presence; the four-outcome derivation of §5
   exactly.
   *Options: 5.1-A/B/C. Recommendation: A.*
5. **Commissioning, research-only** — slice 1 scope, exclusions and
   definition of done as in §9; no approval eligibility, pilot state,
   Decision Authority responsibility, revision lineage or reassessment
   trigger until Advisor decision 5 is ratified; no capture boundary required
   while Agent Runtime wiring is excluded, slice 1 records remaining untrusted
   research evidence; research plans may carry an empty recommended set
   (8.1-A); attainment representation deferred to composite ballot 4 (7.1-C).
   *Options: 6.1-A/B/C (for a later slice), 8.1-A/B/C, 8.2-A/B/C, 7.1-A/B/C.
   Recommendations: A later, A, B, C.*

No constant, threshold, coverage minimum, sampling rate or acceptance
criterion is ratified by this ballot. Composite ballots 2–5, Advisor
decisions 1, 3 and 5, and Workflow-Fit decisions 1 and 4 remain `[R]` and are
not needed for slice 1.

---

## 11. Contract-consistency matrix

Error codes are one enum, `ContractErrorCode`, raised by constructors, plus
`RefusalCode`, returned by the engine. Both live in
`reasoning-method-governance`. Every row below becomes a test in slice 1.

**Constructible examples.** Each row names the object and the minimal
valid inputs; each must construct and produce a stable digest across two
constructions.

| # | Object | Example inputs |
|---|---|---|
| C1 | `ReasoningMethodCatalogRef` | `("cat.rm", "1", <64-hex>)` |
| C2 | `ReasoningMethodRef` | `(C1, "tree_of_thought", "1")` |
| C3 | `ReasoningMethodEntry` | `tree_of_thought` with four `ImplementationEvidence` items citing `reasoning_workflows.py:396`, the stub execution, the test file, and no record; status derives to `EXECUTABLE_TESTED` |
| C4 | `ReasoningMethodCatalog` | seven entries built as C3, sorted, tz-aware `issued_at` |
| C5 | `TaskReversibility`, `ConsequenceClass` | each member by value |
| C6 | `SufficiencyRule` | `THRESHOLD_BASED`, `GovernedThreshold(GTE, literal "0.9", unit "score.unit")`, no admission |
| C7 | `SufficiencyRule` (high-consequence) | as C6 with an `EvidenceAdmissionRef` present |
| C8 | `ComparisonPolicy` | C6, `required_dimensions = (LLM_CALLS,)`, `quality_aggregation = None` |
| C9 | `TaskProfile` | `RECOVERABLE`, `OUTCOME_REVERSIBLE`, two structural tokens from `ComplexitySignal` |
| C10 | `TaskClassIdentity` | C8, `RECOVERABLE`, `OUTCOME_COMPENSATABLE`, benchmark set ref and digest |
| C11 | `TaskClassIdentity` (high-consequence) | `SEVERE` with C7 |
| C12 | `ExecutionTelemetry` | `llm_calls=4, INJECTED_COUNTER, UNAVAILABLE_NOT_REPORTED, None, UNKNOWN, duration 12` |
| C13 | `ExecutionTelemetry` (tokens) | `AVAILABLE` with `TokenUsageSnapshot(total_tokens=812)`, `PROVIDER_REPORTED` |
| C14 | `BindingRef` | five fields, three 64-hex digests |
| C15 | `ReasoningMethodExecutionRecord` | C2, C14, C12, one `FINAL_OUTPUT` artifact, `self_reported_quality="0.75"`, `parent_record_digest=None` |
| C16 | `ReasoningMethodExecutionRecord` (child) | as C15 with `parent_record_digest = C15.record_digest` |
| C17 | `QualityResult` | C2, claim ref, unit `"score.unit"`, value `"0.92"`, no aggregation |
| C18 | `QualityResult` (aggregated) | as C17 with `AggregationRef("research.mean", "0", calc ref)` |
| C19 | `AttestationEnvelope` | `record_digest = C15.record_digest`, attester `"cm-ta1"`, one attested field |
| C20 | `VerificationEnvelope` | references C19's digest, verifier `"tev"` |
| C21 | `ReadinessComparisonRequest` | C10, C1, baseline `linear_chain`, candidates `(linear_chain, tree_of_thought)`, one record and one `QualityResult` each, matching `MetricClaim`s |
| C22 | `ReadinessComparisonResult` | produced by `compare(C21)`; two assessments, no refusals, two `EvidenceStatusView`s all `UNATTESTED/UNVERIFIED` |
| C23 | `ResearchComparisonPlan` | C10, C14, C1, baseline, empty `recommended`, `PREREGISTERED` policy |

**Refused states.** Each row names the mutation of a constructible example
and the code that must be raised or returned.

| # | Mutation | Code |
|---|---|---|
| R1 | C2 with `method_id=""` | `REF_BLANK_FIELD` |
| R2 | C1 with a 63-character digest | `DIGEST_MALFORMED` |
| R3 | C4 with two entries `("tree_of_thought","1")` | `CATALOG_DUPLICATE_ENTRY` |
| R4 | C4 with entries out of key order | `CATALOG_UNSORTED` |
| R5 | C3 with `declared_signals=("not_a_signal",)` | `SIGNAL_TOKEN_UNKNOWN` |
| R6 | an entry subclass adding a field `cost` | `SCALAR_LABEL_FIELD_PRESENT` (field-set test) |
| R7 | an entry constructed with `implementation_status=` keyword | `STATUS_DECLARED_NOT_DERIVED` |
| R8 | C3 with only `UNIT_TESTS_PRESENT` evidence | constructs; status derives to `NO_IMPLEMENTATION_EVIDENCE` (tests are not execution evidence) |
| R9 | C10 with `reversibility=UNDETERMINED` | `REVERSIBILITY_UNDETERMINED_ON_CLASS` |
| R10 | C10 with `consequence_class=SEVERE`, C6 (no admission) | `ADMISSION_REF_REQUIRED` |
| R11 | C8 with `required_dimensions=()` | `DIMENSIONS_EMPTY` |
| R12 | C8 with `required_dimensions=(TOTAL_TOKENS, LLM_CALLS)` | `DIMENSIONS_UNSORTED` |
| R13 | C12 with `llm_calls=None, llm_calls_basis=INJECTED_COUNTER` | `TELEMETRY_INVARIANT` |
| R14 | C13 with `token_usage=None` | `TELEMETRY_INVARIANT` |
| R15 | C12 with `llm_calls=-1` | `TELEMETRY_INVARIANT` |
| R16 | C15 with `artifacts=(ArtifactRef("REASONING_TRACE", …),)` | `ARTIFACT_KIND_UNKNOWN` |
| R17 | C15 with `self_reported_quality="high"` | `DECIMAL_UNPARSEABLE` |
| R18 | C15 with naive `captured_at` | `DATETIME_NAIVE` |
| R19 | C15 with `parent_record_digest = its own record_digest` | `LINEAGE_SELF_REFERENCE` |
| R20 | C15 constructed with `attestation_status=ATTESTED` keyword | `EVIDENCE_AXIS_SET_BY_PRODUCER` |
| R21 | C17 with `governed_unit="other.unit"` in a C21 request | engine `UNIT_MISMATCH` |
| R22 | C21 with threshold comparator `EQ` | engine `UNSUPPORTED_COMPARATOR` |
| R23 | C21 with a `QualityResult.value="NaN"` | engine `SCALE_UNSUPPORTED` |
| R24 | C21 with two `QualityResult`s for one method, policy `quality_aggregation=None` | engine `AGGREGATION_UNDECLARED` |
| R25 | C21 with two records for one method (slice 1) | engine `RESOURCE_AGGREGATION_UNDECLARED` → that method `COMPARISON_EVIDENCE_ABSENT` |
| R26 | C21 with policy `required_dimensions=(LLM_CALLS, TOTAL_TOKENS)` and one record `UNAVAILABLE_NOT_REPORTED` | engine `DIMENSION_UNAVAILABLE` → `COMPARISON_EVIDENCE_ABSENT` for every candidate; no calls-only fallback |
| R27 | C21 with one record's `task_class_digest` changed | engine `TASK_CLASS_MISMATCH` |
| R28 | C21 without any baseline record | engine `BASELINE_ABSENT` → all `COMPARISON_EVIDENCE_ABSENT` |
| R29 | C21 with a `MetricClaim` whose `input_evidence_refs` names a record's `self_reported_quality` | engine `QUALITY_CLAIM_NOT_INDEPENDENT` |
| R30 | C21 using C11 (SEVERE, threshold-based) with no `resolved_admissions` | engine `THRESHOLD_ONLY_NOT_ADMITTED` |
| R31 | R30 plus a `ResolvedAdmission` whose `admitted_digest` differs from the rule's | engine `THRESHOLD_ONLY_NOT_ADMITTED` |
| R32 | C21 with C15 and C16 both present | engine `LINEAGE_UNRESOLVED` |
| R33 | C21 with C19 but `resolved_authorities=()` | constructs; status stays `UNATTESTED`; C19's digest in `ignored_envelopes` |
| R34 | C21 with C19 and `resolved_authorities=(("cm-ta1", ref),)` | status `ATTESTED` on `attested_fields` only |
| R35 | C21 with C19 whose `attester_identity == record.issuer_identity` | engine `SELF_ATTESTATION` |
| R36 | C21 with C20 but no C19 | engine `VERIFICATION_WITHOUT_ATTESTATION` |
| R37 | C21 with an envelope whose `record_digest` matches no record | engine `ENVELOPE_ORPHAN` |
| R38 | C21 with `schema_version="readiness_comparison.request.v0"` | engine `UNSUPPORTED_SCHEMA_VERSION` |
| R39 | C21 two sufficient methods with equal `LLM_CALLS` | both `SUFFICIENT_PARETO_EFFICIENT`; `dominated_by` empty (ties are not domination) |
| R40 | C21 under `IMPROVEMENT_VALUED`, cheaper method with worse quality in derived direction | no domination; both `SUFFICIENT_PARETO_EFFICIENT` |
| R41 | any object constructed twice from equal inputs | equal digests; any field change ⇒ different digest |

`ContractErrorCode` members: `REF_BLANK_FIELD`, `DIGEST_MALFORMED`,
`CATALOG_DUPLICATE_ENTRY`, `CATALOG_UNSORTED`, `SIGNAL_TOKEN_UNKNOWN`,
`SCALAR_LABEL_FIELD_PRESENT`, `STATUS_DECLARED_NOT_DERIVED`,
`REVERSIBILITY_UNDETERMINED_ON_CLASS`, `ADMISSION_REF_REQUIRED`,
`DIMENSIONS_EMPTY`, `DIMENSIONS_UNSORTED`, `TELEMETRY_INVARIANT`,
`ARTIFACT_KIND_UNKNOWN`, `DECIMAL_UNPARSEABLE`, `DATETIME_NAIVE`,
`LINEAGE_SELF_REFERENCE`, `EVIDENCE_AXIS_SET_BY_PRODUCER`.
`RefusalCode` members: `UNSUPPORTED_SCHEMA_VERSION`, `UNSUPPORTED_COMPARATOR`,
`UNIT_MISMATCH`, `SCALE_UNSUPPORTED`, `AGGREGATION_UNDECLARED`,
`RESOURCE_AGGREGATION_UNDECLARED`, `DIMENSION_UNAVAILABLE`,
`TASK_CLASS_MISMATCH`, `BASELINE_ABSENT`, `METHOD_RECORDS_ABSENT`,
`QUALITY_RESULT_ABSENT`, `QUALITY_CLAIM_NOT_INDEPENDENT`,
`THRESHOLD_UNRESOLVABLE`, `THRESHOLD_ONLY_NOT_ADMITTED`, `LINEAGE_UNRESOLVED`,
`SELF_ATTESTATION`, `VERIFICATION_WITHOUT_ATTESTATION`, `ENVELOPE_ORPHAN`.

---

## 12. Correction record (revision 2, 2026-09-02)

| # | Defect in revision 1 | Correction |
|---|---|---|
| 1 | `ReasoningMethodRef` used with blank method fields to denote a catalog | `ReasoningMethodCatalogRef` introduced (§2); every `ReasoningMethodRef` field non-blank (R1) |
| 2 | Unratified arithmetic mean over quality claims | `QualityResult`, one per method, or an explicit `AggregationRef`; direction derived from the comparator; `EQ`/`NEQ`, unit and scale cases refused (§5, R21–R24) |
| 3 | Record evidence axes were producer-set fields; non-blank strings promoted status | Axes are v1 class constants; `AttestationEnvelope` and `VerificationEnvelope` reference `record_digest`; status computed from envelopes of resolved authorities (§4, §6, R20, R33–R37) |
| 4 | "Newest record in a lineage is authoritative" | `parent_record_digest` is lineage only; two records in one lineage refused until lineage authority is ratified (§4, 4.1, R32) |
| 5 | Deltas "vs cheapest sufficient" | `deltas_vs_baseline` relative to the named baseline; `DominationRecord` deltas relative to each named dominator (§5) |
| 6 | Dimension fallback from calls-plus-tokens to calls-only | `ComparisonPolicy.required_dimensions` on the class; any missing required telemetry ⇒ `COMPARISON_EVIDENCE_ABSENT` (§3, §5, R26) |
| 7 | Reference comparison placed in the contracts package pending a move | Contracts in `reasoning-method-governance`; the engine in `readiness-comparison`; both in slice 1; no planned move (§1, §9) |
| 8 | Approval eligibility, Decision Authority responsibility and `deployment_environment_ref` as pilot state | Removed; slice 1 is `RESEARCH_ONLY`; lifecycle deferred to Advisor decision 5 (§8) |
| 9 | Agent Runtime capture boundary required for approval-bound pilots in slice 1 | No capture boundary in slice 1; records untrusted by constant; 6.1 deferred to a later slice (§6, §9) |
| 10 | "Three of seven implemented" | All seven re-evaluated: concrete class, registered, stub-executed, unit-tested; status evidence-derived (§2) |
| 11 | Task reversibility mirrored from `external_actions.Reversibility` | Governed `TaskReversibility` vocabulary, distinct from action reversibility (§3, 3.2) |
| 12 | High-consequence refusal satisfied by a non-blank reference | Constructor checks shape only; engine requires a `ResolvedAdmission` matching the rule's `EvidenceAdmissionRef` (§3, §7, R10, R30–R31) |
