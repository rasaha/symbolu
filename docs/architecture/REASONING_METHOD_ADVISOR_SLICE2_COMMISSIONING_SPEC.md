# Reasoning Method Advisor — Slice 2 Commissioning Specification

**Status:** bounded commissioning specification for owner ratification.
**Nothing here is implemented.** Slice 2 is a **research-only, deterministic,
rule-derived** Reasoning Method Advisor. It commissions one package and one
CI gate and nothing else.
**Authority applied:** Advisor decision 1, RATIFIED 2026-09-02 (separate
design-time capability; *reasoning method* vocabulary; advisor-specific
no-forced-winner rule with OD-8 as precedent only; extends neither Agentic
Proposer nor Agent Workforce Composer); Advisor decisions 2 and 4 and
Workflow-Fit decisions 2, 3 and 5 as recorded in their notes; the slice 1
contracts merged at `4369089d` (PR #1569) `[V]`.
**Evidence labels:** `[V]` verified against the repository · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Given a developer's task profile, the governed catalog, and a versioned
rule set, which methods qualify, which are excluded, and why, without any
prediction the system cannot support?** Slice 2 answers with a set-valued,
labelled, digested advisory whose every claim is `RULE_DERIVED` and whose
evidence status is always `COMPARISON_EVIDENCE_ABSENT`, and that names a
primary only when exactly one method is uniquely supported.

---

## 1. Placement and boundaries

| Package | Distribution / import | Depends on |
|---|---|---|
| `packages/capabilities/reasoning-method-advisor` | `ugence-reasoning-method-advisor` / `ugence_reasoning_method_advisor` | `ugence-reasoning-method-governance`, `ugence-governance-contracts`, `ugence-uvi-policy-contracts`, `ugence-jcs` |

**Consumes, unchanged:** `TaskProfile`, `TaskClassIdentity`,
`ReasoningMethodCatalog`, `ReasoningMethodCatalogRef`, `ReasoningMethodRef`,
`ImplementationStatus`, `COMPLEXITY_SIGNAL_TOKENS` and
`ReadinessComparisonResult` from `ugence_reasoning_method_governance.api`
`[V]`. Slice 2 adds no field to any slice 1 contract.

**Forbidden imports, enforced by the same boundary-test pattern as slice 1**
`[V]`: `agentic`, `agentic_framework`, `reasoning_workflows`,
`adaptive_prompts`, `external_actions`, `ugence_readiness_comparison`,
`ugence_agentic_proposer`, `ugence_agent_workforce_composer`,
`ugence_agent_runtime`, `ugence_agent_value_readiness`, `governed_value`,
`ugence_context_minimization`, `ugence_policy_authority`, and any LLM or
network SDK. The advisor reads a profile and a catalog; it calls nothing.

---

## 2. Advisory request

```python
ADVISORY_REQUEST_SCHEMA_VERSION = "reasoning_method.advisory_request.v1"

@dataclass(frozen=True)
class RuleSetRef:
    rule_set_id: str
    rule_set_version: str
    rule_set_digest: str                        # sha-256 hex; the RuleSet's own digest (§4)

@dataclass(frozen=True)
class ReasoningMethodAdvisoryRequest:
    schema_version: Literal["reasoning_method.advisory_request.v1"]
    request_id: str
    profile: TaskProfile                        # developer-reported; DEVELOPER_REPORTED by construction
    task_class: Optional[TaskClassIdentity]     # the governed class when one is declared (unresolved 2.1)
    catalog: ReasoningMethodCatalog             # the full catalog, so rules read entries; its digest is recorded
    rule_set: RuleSet                           # §4; evaluated exactly as supplied
    comparison_results: tuple[ReadinessComparisonResult, ...] = ()   # ACCEPTED, RECORDED, NOT USED in slice 2 (§6)
    requester_identity: str = ""
```

**Refusals (constructor):** blank identifiers (`REF_BLANK_FIELD`); a
`task_class` whose `structural_characteristics` are not a superset of the
profile's (`PROFILE_CLASS_MISMATCH`); a `comparison_results` entry whose
`schema_version` is not the slice 1 result literal (`UNSUPPORTED_SCHEMA_VERSION`).
The request never carries a query string, a prompt, or runtime text:
`ComplexityDetector.analyze(self, text: str)` (`adaptive_prompts.py:359`)
`[V]` reads runtime text and is not consumed; the profile's
`structural_characteristics` tokens are the design-time signal.

---

## 3. Advisory result

```python
ADVISORY_SCHEMA_VERSION = "reasoning_method.advisory.v1"

class AdvisoryLabel(str, Enum):                 # BENCHMARK_DERIVED is deliberately absent in slice 2
    RULE_DERIVED = "RULE_DERIVED"
    COMPARISON_EVIDENCE_ABSENT = "COMPARISON_EVIDENCE_ABSENT"

class NoPrimaryReason(str, Enum):
    NO_QUALIFYING_METHOD = "NO_QUALIFYING_METHOD"
    MULTIPLE_QUALIFYING_METHODS = "MULTIPLE_QUALIFYING_METHODS"
    QUALIFYING_METHOD_NOT_UNIQUELY_SUPPORTED = "QUALIFYING_METHOD_NOT_UNIQUELY_SUPPORTED"

@dataclass(frozen=True)
class RuleOutcome:                              # one fired rule, as a reason
    rule_id: str
    rule_kind: RuleKind                         # §4
    matched_tokens: tuple[str, ...]             # the profile coordinates the predicate matched, sorted
    rationale_ref: str

@dataclass(frozen=True)
class QualifyingMethod:
    method: ReasoningMethodRef
    label: AdvisoryLabel                        # always RULE_DERIVED in slice 2
    inclusion_reasons: tuple[RuleOutcome, ...]  # ≥1; ordered by rule_id

@dataclass(frozen=True)
class ExcludedMethod:
    method: ReasoningMethodRef
    label: AdvisoryLabel                        # always RULE_DERIVED in slice 2
    exclusion_reasons: tuple[RuleOutcome, ...]  # ≥1; a method no SUPPORT rule reached carries the synthetic NO_SUPPORTING_RULE outcome

@dataclass(frozen=True)
class ReasoningMethodAdvisory:
    schema_version: Literal["reasoning_method.advisory.v1"]
    advisory_id: str
    request_digest: str
    profile_digest: str
    task_class_digest: Optional[str]
    catalog: ReasoningMethodCatalogRef
    rule_set: RuleSetRef
    qualifying: tuple[QualifyingMethod, ...]    # zero, one or many; ordered by (method_id, method_version)
    excluded: tuple[ExcludedMethod, ...]        # every catalog entry not qualifying; same order
    primary: Optional[ReasoningMethodRef]       # only when exactly one qualifies AND it is uniquely supported (§4)
    primary_basis: Optional[Literal["UNIQUE_RULE_SUPPORT"]]
    no_primary_reason: Optional[NoPrimaryReason]  # set iff primary is None
    evidence_status: Literal["COMPARISON_EVIDENCE_ABSENT"]   # slice 2 constant: no admitted comparison evidence exists
    comparison_result_digests: tuple[str, ...]  # digests of any supplied results; recorded, not consulted
    usage_scope: Literal["RESEARCH_ONLY"]
    advisor_identity: str
    advisor_version: str
    advised_at: datetime
    advisory_digest: str
```

**Prohibitions carried structurally.** No field can hold a number: there is no
score, rank, probability, confidence, cost, latency or resource label, and a
test over the field set of every advisory type rejects any such name (the
slice 1 `SCALAR_LABEL_FIELD_PRESENT` pattern) `[V]`. `qualifying` is a set,
not a ranking: its order is the catalog sort key. `primary` is never derived
from position, count of reasons, or any weight.

---

## 4. Deterministic, versioned profile-to-method rules

```python
RULE_SET_SCHEMA_VERSION = "reasoning_method.rule_set.v1"

class RuleKind(str, Enum):
    SUPPORT = "SUPPORT"                         # if the predicate matches, the named methods gain an inclusion reason
    EXCLUDE = "EXCLUDE"                         # if the predicate matches, the named methods gain an exclusion reason and cannot qualify

class PredicateKind(str, Enum):
    STRUCTURAL_TOKEN_PRESENT = "STRUCTURAL_TOKEN_PRESENT"       # value ∈ profile.structural_characteristics
    CONSEQUENCE_CLASS_IN = "CONSEQUENCE_CLASS_IN"               # profile.consequence_class ∈ values
    REVERSIBILITY_IN = "REVERSIBILITY_IN"                       # profile.reversibility ∈ values
    REQUIREMENT_REF_PRESENT = "REQUIREMENT_REF_PRESENT"         # value ∈ evidence_requirement_refs ∪ tool_requirement_refs
    IMPLEMENTATION_STATUS_IN = "IMPLEMENTATION_STATUS_IN"       # entry.implementation_status ∈ values (catalog-side predicate)

@dataclass(frozen=True)
class Predicate:
    kind: PredicateKind
    values: tuple[str, ...]                     # non-empty; STRUCTURAL_TOKEN_PRESENT values must be COMPLEXITY_SIGNAL_TOKENS

@dataclass(frozen=True)
class Rule:
    rule_id: str
    kind: RuleKind
    predicate: Predicate
    method_ids: tuple[str, ...]                 # non-empty; each must exist in the catalog at evaluation (RULE_METHOD_UNKNOWN otherwise)
    rationale_ref: str                          # where the rule comes from; never prose alone

@dataclass(frozen=True)
class RuleSet:
    schema_version: Literal["reasoning_method.rule_set.v1"]
    rule_set_id: str
    rule_set_version: str
    admissibility: Predicate                    # catalog-side gate every method must pass before any rule applies (unresolved 4.1)
    rules: tuple[Rule, ...]                     # unique rule_id; ordered by rule_id
    provenance_ref: str
    issuer_identity: str
    issued_at: datetime
    rule_set_digest: str
```

**Evaluation, exact and order-free.**

1. **Admissible set** `A` = catalog entries whose `implementation_status`
   satisfies `admissibility`. An inadmissible entry is excluded with the
   synthetic outcome `INADMISSIBLE_IMPLEMENTATION_STATUS`.
2. For every rule `r` whose predicate matches the profile (or the entry, for
   catalog-side predicates), every method in `r.method_ids ∩ A` receives a
   `RuleOutcome`: an inclusion reason if `r.kind == SUPPORT`, an exclusion
   reason if `EXCLUDE`.
3. **Qualifying set** `Q` = methods in `A` with at least one inclusion reason
   and no exclusion reason. Methods in `A` with an exclusion reason are
   excluded with those reasons. Methods in `A` with no reason at all are
   excluded with the synthetic outcome `NO_SUPPORTING_RULE`.
4. **Primary** is set iff `|Q| == 1` **and** the union of `method_ids` over
   all fired `SUPPORT` rules, intersected with `A`, equals `Q`. That is,
   exactly one method qualifies and no fired support rule named any other
   admissible method. Otherwise `primary` is `None` with the applicable
   `NoPrimaryReason`. Rule priority, rule count and rule order never break a
   tie: this is the ratified advisor-specific no-forced-winner rule, with
   OD-8 cited as precedent only.
5. Every label is `RULE_DERIVED`; the advisory's `evidence_status` is
   `COMPARISON_EVIDENCE_ABSENT`.

Evaluation is a pure function of `(profile, task_class, catalog, rule_set)`.
The same inputs yield the same `advisory_digest` across processes.

**Initial rule set `rules.research.v0` `[R]`.** Provenance: a transcription of
`WorkflowSelector.SIGNAL_MAP` (`reasoning_workflows.py:1177-1188`) `[V]` into
ten `SUPPORT` rules, one per `ComplexitySignal` token, each naming the one
method the selector maps it to, with `rationale_ref` citing that line range.
`SIGNAL_PRIORITY` (`:1191-1202`) `[V]` is **not** transcribed: it is a
first-match tie-break, and slice 2 breaks no ties. No `EXCLUDE` rule ships in
v0; the admissibility predicate is the only gate. v0 is research provenance,
not a ratified mapping, and its digest is carried on every advisory so a
later rule set cannot be confused with it.

**Unresolved 4.1 — admissibility gate.**

| Option | Consequence |
|---|---|
| A. `IMPLEMENTATION_STATUS_IN (EXECUTABLE_TESTED,)` | only tested-executable methods can qualify; under the slice 1 fixture all seven qualify for admissibility |
| B. `IMPLEMENTATION_STATUS_IN (EXECUTABLE_TESTED, EXECUTABLE_UNTESTED)` | untested executables can be advised; a pilot could then run an untested method |
| C. No admissibility gate; every catalog entry is a candidate | absent methods can be "recommended"; coverage measures lose meaning |

**Recommendation: A.**

**Unresolved 2.1 — is `task_class` required?**

| Option | Consequence |
|---|---|
| A. Optional; profile-only requests permitted, `task_class_digest` `None` | usable at design time before a governed class exists; the advisory cannot be joined to any fit assessment |
| B. Required | every advisory is joinable to comparison results by `task_class_digest`; no advice before a class is declared |

**Recommendation: A for slice 2**, because the advisor is design-time and
the class often does not yet exist; B becomes natural when ingestion (§6)
arrives.

**Unresolved 4.2 — rule set v0 provenance.**

| Option | Consequence |
|---|---|
| A. Transcribe `SIGNAL_MAP` as ten `SUPPORT` rules, no `EXCLUDE` rules | immediately runnable; encodes the experimental selector's opinions as research provenance |
| B. Ship an empty rule set; the owner authors rules before any advisory can qualify a method | nothing inherited from the runtime; no advisory has content until rules are ratified |
| C. Transcribe `SIGNAL_MAP` and add consequence-based `EXCLUDE` rules | more discriminating; the exclusions would be invented, not derived |

**Recommendation: A**, labelled as research provenance with the selector
line range as `rationale_ref`.

---

## 5. Labels and prohibitions

- `RULE_DERIVED` on every inclusion and exclusion.
- `COMPARISON_EVIDENCE_ABSENT` as the advisory's `evidence_status`, always,
  in slice 2. The advisor does not know outcomes; it says so structurally.
- `BENCHMARK_DERIVED` is **not a member** of `AdvisoryLabel` in slice 2. Its
  later addition is an additive enum change under a new label-set version.
- No numeric outcome prediction, no probability, no scalar cost or latency
  label, no ranking. A rule-derived claim never says "92–95%"
  (advisor note §5 prohibitions) `[V]`.

---

## 6. Later ingestion without changing the request

The request already carries `comparison_results`. Slice 2 validates their
schema version, records their `result_digest`s in
`comparison_result_digests`, and **consults nothing in them**. A later slice
adds, without touching the request contract: a `BENCHMARK_DERIVED` label
member; an ingestion rule set version whose predicates may read
`ReasoningMethodFitAssessment.outcome` for the matching `task_class_digest`;
and additive result fields. Whether an advisory may then carry
`BENCHMARK_DERIVED` on an assessment whose `usage_scope` is `RESEARCH_ONLY`
is that slice's ruling, not this one's `[R]`.

---

## 7. Tests against representative profiles

Profiles are TEST INPUTS. Each row is an executable test; digests are
asserted stable across two constructions and two processes.

| # | Profile (structural tokens; consequence; reversibility) | Catalog | Expected |
|---|---|---|---|
| P1 | `comparison_request`; RECOVERABLE; OUTCOME_REVERSIBLE | seven-member slice 1 fixture | `Q = {map_reduce}`, primary `map_reduce`, basis `UNIQUE_RULE_SUPPORT` |
| P2 | `comparison_request`, `ambiguity_detected` | same | `Q = {map_reduce, tree_of_thought}`, no primary, `MULTIPLE_QUALIFYING_METHODS` |
| P3 | no tokens | same | `Q = ∅`, no primary, `NO_QUALIFYING_METHOD`; every entry excluded with `NO_SUPPORTING_RULE` |
| P4 | `conditional_logic`, `causal_reasoning` under a rule set where one `EXCLUDE` rule removes `debate` for `SEVERE` consequence; profile SEVERE | same | `Q = {linear_chain}`; `debate` excluded with the `EXCLUDE` outcome; primary `linear_chain` |
| P5 | `comparison_request` with a rule set adding a second `SUPPORT` rule naming `debate` on the same token | same | `Q = {map_reduce, debate}`, no primary |
| P6 | `comparison_request`, catalog where `map_reduce` carries only `UNIT_TESTS_PRESENT` evidence | modified fixture | `map_reduce` excluded `INADMISSIBLE_IMPLEMENTATION_STATUS`; `Q = ∅` |
| P7 | P1 with `task_class = None` | same | identical `qualifying`; `task_class_digest` `None` |
| P8 | P1 with a supplied `ReadinessComparisonResult` | same | identical `qualifying` and labels; `comparison_result_digests` non-empty; `evidence_status` still `COMPARISON_EVIDENCE_ABSENT` |
| P9 | P1 with `reversibility = UNDETERMINED` | same | constructs (a profile may be undetermined); same `Q` |
| P10 | P1 twice, then with `rule_set_version` bumped | same | first two digests equal; third differs |
| R-a | any advisory type declared with a field named `score`, `rank`, `probability`, `cost` or `latency_class` | — | refused at class definition |
| R-b | a `Rule` naming a method absent from the catalog | — | `RULE_METHOD_UNKNOWN` at evaluation |
| R-c | a `Predicate` of kind `STRUCTURAL_TOKEN_PRESENT` with a non-signal token | — | `SIGNAL_TOKEN_UNKNOWN` |
| R-d | a request whose `task_class.structural_characteristics` omits a profile token | — | `PROFILE_CLASS_MISMATCH` |
| R-e | a hand-built advisory with `primary` set and `|qualifying| ≠ 1` | — | `PRIMARY_WITHOUT_UNIQUE_SUPPORT` |
| R-f | `AdvisoryLabel("BENCHMARK_DERIVED")` | — | `ValueError`: not a member |
| B | AST scan of `src/` | — | no forbidden import (§1) |

Slice 2 adds these codes to a package-local `AdvisorErrorCode`:
`PROFILE_CLASS_MISMATCH`, `RULE_METHOD_UNKNOWN`,
`PRIMARY_WITHOUT_UNIQUE_SUPPORT`, `RULE_SET_UNSORTED`,
`RULE_DUPLICATE_ID`; it reuses `REF_BLANK_FIELD`, `DIGEST_MALFORMED`,
`SIGNAL_TOKEN_UNKNOWN`, `SCALAR_LABEL_FIELD_PRESENT` and `DATETIME_NAIVE`
from slice 1 `[V]`.

---

## 8. Explicitly excluded from slice 2

No LLM-based selection of any kind. No `BENCHMARK_DERIVED` claim. No numeric
outcome prediction. No scalar cost, latency or resource label. No production
approval, no configuration mutation, no binding change. No Agent Constitution
binding. No attestation, verification or envelope issuance. No change to
Agentic Proposer, Agent Workforce Composer, Agent Runtime, readiness
classification, ROI or governed value, or the readiness advisory composite.
No change to any slice 1 contract, enum or package. No coverage, sampling or
acceptance figure.

---

## 9. Definition of done

Package `ugence-reasoning-method-advisor` with `advise(request) -> advisory`
as a pure function; the §2–§4 contracts; rule set `rules.research.v0`
shipped as a test fixture only (not as catalog or policy content); every §7
row as an executable test; the boundary test; a CI workflow in the slice 1
pattern; a wheel-based distribution self-check proving no forbidden package
is importable. Every advisory carries `usage_scope = "RESEARCH_ONLY"` and
`evidence_status = "COMPARISON_EVIDENCE_ABSENT"`.

---

## 10. Owner ballot `[R]`

Ratifying all three commissions slice 2 as specified in §9, research-only.
"Ratify as recommended" is a complete answer.

1. **Contracts and placement** — `ugence-reasoning-method-advisor` as in §1;
   the request and advisory of §2–§3 with `BENCHMARK_DERIVED` absent from
   `AdvisoryLabel`; `task_class` optional (2.1-A); `comparison_results`
   accepted and recorded but not consulted (§6).
   *Options: 2.1-A / 2.1-B. Recommendation: A.*
2. **Rules and the primary rule** — the §4 evaluation exactly: set-valued
   qualification, primary only under unique rule support, no tie-break by
   priority, count or order; admissibility gate 4.1-A; initial rule set as a
   transcription of `SIGNAL_MAP` without `SIGNAL_PRIORITY`, labelled research
   provenance (4.2-A).
   *Options: 4.1-A/B/C, 4.2-A/B/C. Recommendations: A, A.*
3. **Commissioning, research-only** — slice 2 scope, the §8 exclusions and
   the §9 definition of done; nothing numeric ratified; Advisor decisions 3
   and 5, Workflow-Fit decisions 1 and 4, and Composite ballots 2–5 remain
   `[R]` and are not needed for slice 2.
