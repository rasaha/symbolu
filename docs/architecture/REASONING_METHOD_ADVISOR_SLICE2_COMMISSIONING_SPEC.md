# Reasoning Method Advisor — Slice 2 Commissioning Specification

**Status:** **RATIFIED AS AMENDED — all three §10 ballot items ratified by the
owner, 2026-09-02, after the four amendments recorded in §11.** Slice 2 is
commissioned as research-only work and is **not implemented**; implementation
awaits a separate owner instruction.
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
primary only when exactly one method qualifies.

---

## 1. Placement and boundaries

| Package | Distribution / import | Depends on |
|---|---|---|
| `packages/capabilities/reasoning-method-advisor` | `ugence-reasoning-method-advisor` / `ugence_reasoning_method_advisor` | `ugence-reasoning-method-governance`, `ugence-governance-contracts`, `ugence-uvi-policy-contracts`, `ugence-jcs` |

**Consumes, unchanged:** `TaskProfile`, `TaskClassIdentity`,
`ReasoningMethodCatalog`, `ReasoningMethodCatalogRef`, `ReasoningMethodRef`,
`ImplementationStatus` and `COMPLEXITY_SIGNAL_TOKENS` from
`ugence_reasoning_method_governance.api` `[V]`. Slice 2 adds no field to any
slice 1 contract and consumes no comparison result (§6).

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
    task_class: Optional[TaskClassIdentity]     # the governed class when one is declared; None ⇒ UNCLASSIFIED (binding restriction below)
    catalog: ReasoningMethodCatalog             # the full catalog, so rules read entries; its digest is recorded
    rule_set: RuleSet                           # §4; evaluated exactly as supplied
    requester_identity: str = ""
    # There is NO comparison-results field. Slice 2 never consults comparison evidence (§6).
```

**Unclassified requests (owner ruling, binding).** A request without a
governed `TaskClassIdentity` receives **exploratory `RULE_DERIVED` advice
only**. The advisory marks it `classification = UNCLASSIFIED_EXPLORATORY` and
`eligibility = INELIGIBLE_UNCLASSIFIED`: it is ineligible for benchmark
comparison, for governed configuration binding, and for any production
authority, and its `evidence_status` remains the explicit
`COMPARISON_EVIDENCE_ABSENT`. A request with a governed class is marked
`GOVERNED_TASK_CLASS` and `JOINABLE_BY_TASK_CLASS_DIGEST`; that marks
joinability to a future comparison, not any eligibility for approval.

**Refusals (constructor):** blank identifiers (`REF_BLANK_FIELD`); a
`task_class` whose `structural_characteristics` are not a superset of the
profile's (`PROFILE_CLASS_MISMATCH`).
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

class AdvisoryClassification(str, Enum):
    GOVERNED_TASK_CLASS = "GOVERNED_TASK_CLASS"
    UNCLASSIFIED_EXPLORATORY = "UNCLASSIFIED_EXPLORATORY"

class AdvisoryEligibility(str, Enum):
    JOINABLE_BY_TASK_CLASS_DIGEST = "JOINABLE_BY_TASK_CLASS_DIGEST"     # joinable to a future comparison; not an approval
    INELIGIBLE_UNCLASSIFIED = "INELIGIBLE_UNCLASSIFIED"                 # no benchmark comparison, no configuration binding, no production authority

@dataclass(frozen=True)
class RuleOutcome:                              # one fired rule, as a reason
    rule_id: str
    rule_version: str
    rule_kind: RuleKind                         # §4
    matched_tokens: tuple[str, ...]             # the profile coordinates the predicate matched, sorted
    rationale_ref: str
    rationale_statement: str                    # the rule's declared inclusion/exclusion rationale, verbatim

@dataclass(frozen=True)
class QualifyingTradeOff:                       # present for every qualifying method when more than one qualifies
    method: ReasoningMethodRef
    distinguishing_reasons: tuple[RuleOutcome, ...]      # inclusion reasons this method has that no other qualifying method has
    distinguishing_requirement_refs: tuple[str, ...]     # catalog requirement_refs this method has that no other qualifying method has
    # no ordering, weight, score or preference: a trade-off is a difference, not a ranking

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
    classification: AdvisoryClassification     # GOVERNED_TASK_CLASS iff task_class_digest is not None
    eligibility: AdvisoryEligibility            # INELIGIBLE_UNCLASSIFIED iff classification is UNCLASSIFIED_EXPLORATORY
    qualifying: tuple[QualifyingMethod, ...]    # zero, one or many; ordered by (method_id, method_version)
    excluded: tuple[ExcludedMethod, ...]        # every catalog entry not qualifying; same order
    trade_offs: tuple[QualifyingTradeOff, ...]  # one per qualifying method iff more than one qualifies; otherwise empty
    primary: Optional[ReasoningMethodRef]       # set iff exactly one method qualifies (§4)
    primary_basis: Optional[Literal["SOLE_QUALIFYING_METHOD"]]
    no_primary_reason: Optional[NoPrimaryReason]  # set iff primary is None
    evidence_status: Literal["COMPARISON_EVIDENCE_ABSENT"]   # slice 2 constant, explicit on every advisory
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
not a ranking: its order is the catalog sort key. `trade_offs` are
differences, not preferences. `primary` is never derived from position,
rule count, rule priority, implementation order, or any weight; it exists
only when the qualifying set has exactly one member.

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
    rule_id: str                                # stable identifier; never reused for a different predicate or method set
    rule_version: str                           # bumped on any change to predicate, method_ids or rationale
    kind: RuleKind
    predicate: Predicate                        # the declared profile (or catalog-side) predicate
    method_ids: tuple[str, ...]                 # non-empty; each must exist in the catalog at evaluation (RULE_METHOD_UNKNOWN otherwise)
    rationale_ref: str                          # where the rule comes from (a document, line range or ruling); never prose alone
    rationale_statement: str                    # the inclusion or exclusion rationale, one sentence, carried into every RuleOutcome

@dataclass(frozen=True)
class RuleSet:
    schema_version: Literal["reasoning_method.rule_set.v1"]
    rule_set_id: str
    rule_set_version: str
    admissibility: Predicate                    # catalog-side gate every method must pass before any rule applies (unresolved 4.1)
    rules: tuple[Rule, ...]                     # CANONICAL ORDER REQUIRED: ascending rule_id by Unicode code point; unique rule_id (see canonical-input rule)
    provenance_ref: str
    issuer_identity: str
    issued_at: datetime
    rule_set_digest: str
```

**Canonical-input rule.** `RuleSet.rules` must be supplied in canonical
order: ascending `rule_id`, compared by Unicode code point, with `rule_id`
unique. A tuple not in that order is refused with `RULE_SET_UNSORTED`; a
repeated `rule_id` is refused with `RULE_DUPLICATE_ID`. A rule set therefore
has exactly one admitted representation, `rule_set_digest` is derived from
that single canonical representation, and every advisory carries it in
`rule_set`. Canonical order is a **serialization** property only: it never
confers priority, preference or tie-breaking, and §4 step 4 reads no
position. Order independence is therefore a property of the **evaluator**,
tested as such (§7, P11), not a property of tolerating unsorted input.

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
4. **Primary** is set iff `|Q| == 1`, with `primary_basis =
   SOLE_QUALIFYING_METHOD`. If `|Q| == 0`, `no_primary_reason =
   NO_QUALIFYING_METHOD`. If `|Q| > 1`, the advisory returns the **complete
   qualifying set**, every method's inclusion reasons, and one
   `QualifyingTradeOff` per qualifying method whose distinguishing reasons
   and requirement refs are the set differences against the other qualifying
   methods, with `no_primary_reason = MULTIPLE_QUALIFYING_METHODS` and **no
   primary**. Rule count, rule priority and implementation order never
   manufacture a winner: this is the ratified advisor-specific
   no-forced-winner rule, with OD-8 cited as precedent only.
5. `classification` and `eligibility` are set from the presence of
   `task_class` (§2). Every label is `RULE_DERIVED`; the advisory's
   `evidence_status` is `COMPARISON_EVIDENCE_ABSENT`.

Evaluation is a pure function of `(profile, task_class, catalog, rule_set)`.
The same inputs yield the same `advisory_digest` across processes. The
evaluator's internal traversal order over rules, catalog entries and
qualifying methods must not affect any output: implementations are tested by
evaluating one admitted canonical `RuleSet` through differently ordered
internal traversals (§7, P11).

**Constructor obligations on the advisory (every one a §7 row):**

- `trade_offs` is empty when zero or one method qualifies.
- When more than one method qualifies, `trade_offs` holds **exactly one**
  record per qualifying method, in the same order as `qualifying`, and no
  record for any excluded method.
- A `QualifyingTradeOff` with empty `distinguishing_reasons` **and** empty
  `distinguishing_requirement_refs` is permitted: it states that the method is
  not distinguishable from the others by rule or requirement, and is never
  presented, ordered or labelled as a preference.
- Every `RuleOutcome.rule_version` equals the `rule_version` of the rule in
  the admitted `RuleSet` whose `rule_id` it names; a mismatch is refused with
  `RULE_OUTCOME_VERSION_MISMATCH`.

**Initial rule set `rules.research.v0`.** Provenance: a transcription of
`WorkflowSelector.SIGNAL_MAP` (`reasoning_workflows.py:1177-1188`) `[V]` into
ten `SUPPORT` rules, one per `ComplexitySignal` token, each naming the one
method the selector maps it to. Each rule carries a stable `rule_id`
(`research.signal.<token>`), `rule_version` `"0"`, its declared predicate
(`STRUCTURAL_TOKEN_PRESENT` on that token), a `rationale_ref` citing that
line range, and a `rationale_statement` reading "transcribed from the
experimental WorkflowSelector mapping; provenance only". **Transcription
supplies research provenance for where the rule came from. It is not
evidence that the selector's routing is correct**; no study has tested that
mapping, and the advisory's `COMPARISON_EVIDENCE_ABSENT` status says so.
`SIGNAL_PRIORITY` (`:1191-1202`) `[V]` is **not** transcribed: it is a
first-match tie-break, and slice 2 breaks no ties. No `EXCLUDE` rule ships in
v0; the admissibility predicate is the only gate. v0's digest is carried on
every advisory so a later rule set cannot be confused with it.

**Unresolved 4.1 — admissibility gate.**

| Option | Consequence |
|---|---|
| A. `IMPLEMENTATION_STATUS_IN (EXECUTABLE_TESTED,)` | only tested-executable methods can qualify; under the slice 1 fixture all seven qualify for admissibility |
| B. `IMPLEMENTATION_STATUS_IN (EXECUTABLE_TESTED, EXECUTABLE_UNTESTED)` | untested executables can be advised; a pilot could then run an untested method |
| C. No admissibility gate; every catalog entry is a candidate | absent methods can be "recommended"; coverage measures lose meaning |

**Recommendation: A.**

**2.1 — `task_class` optional, with a binding restriction (resolved by owner
ruling, §11).** Profile-only requests are permitted and yield exploratory
`RULE_DERIVED` advice marked `UNCLASSIFIED_EXPLORATORY` /
`INELIGIBLE_UNCLASSIFIED` (§2). The former options A (optional) and B
(required) are superseded by this ruling.

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
- `COMPARISON_EVIDENCE_ABSENT` as the advisory's `evidence_status`, always
  and explicitly, in slice 2, for classified and unclassified requests alike.
  The advisor does not know outcomes; it says so structurally.
- `BENCHMARK_DERIVED` is **not a member** of `AdvisoryLabel` in slice 2. Its
  later addition is an additive enum change under a new label-set version.
- No numeric outcome prediction, no probability, no scalar cost or latency
  label, no ranking. A rule-derived claim never says "92–95%"
  (advisor note §5 prohibitions) `[V]`.

---

## 6. Comparison-result ingestion is out of scope

Slice 2 contracts carry **no comparison-results field** and the advisor
**consults no comparison evidence**. Ingestion of `ReadinessComparisonResult`
values is introduced only in the later benchmark-derived slice, through a
**separately ratified contract change**: a new request schema version that
adds the field, a `BENCHMARK_DERIVED` label member, and an ingestion rule
set version whose predicates may read `ReasoningMethodFitAssessment.outcome`
for a matching `task_class_digest`. Whether an advisory may then carry
`BENCHMARK_DERIVED` on an assessment whose `usage_scope` is `RESEARCH_ONLY`
is that slice's ruling `[R]`. A slice 2 field-set test asserts the request
type has no such field, so the later change is visible as a schema change,
not a silent widening.

---

## 7. Tests against representative profiles

Profiles are TEST INPUTS. Each row is an executable test; digests are
asserted stable across two constructions and two processes.

| # | Profile (structural tokens; consequence; reversibility) | Catalog | Expected |
|---|---|---|---|
| P1 | `comparison_request`; RECOVERABLE; OUTCOME_REVERSIBLE; governed class declared | seven-member slice 1 fixture | `Q = {map_reduce}`, primary `map_reduce`, basis `SOLE_QUALIFYING_METHOD`, `GOVERNED_TASK_CLASS` / `JOINABLE_BY_TASK_CLASS_DIGEST`, `trade_offs = ()` |
| P2 | `comparison_request`, `ambiguity_detected` | same | `Q = {map_reduce, tree_of_thought}`, no primary, `MULTIPLE_QUALIFYING_METHODS`; two `QualifyingTradeOff`s, each carrying the one inclusion reason the other lacks |
| P3 | no tokens | same | `Q = ∅`, no primary, `NO_QUALIFYING_METHOD`; every entry excluded with `NO_SUPPORTING_RULE` |
| P4 | `conditional_logic`, `causal_reasoning` under a rule set where one `EXCLUDE` rule removes `debate` for `SEVERE` consequence; profile SEVERE | same | `Q = {linear_chain}`; `debate` excluded with the `EXCLUDE` outcome; primary `linear_chain` |
| P5 | `comparison_request` with a rule set adding a second `SUPPORT` rule naming `debate` on the same token | same | `Q = {map_reduce, debate}`, no primary; both trade-offs have empty `distinguishing_reasons` (same reason) and differ only by requirement refs, if any; adding a third rule for `debate` still yields no primary (rule count never manufactures a winner) |
| P6 | `comparison_request`, catalog where `map_reduce` carries only `UNIT_TESTS_PRESENT` evidence | modified fixture | `map_reduce` excluded `INADMISSIBLE_IMPLEMENTATION_STATUS`; `Q = ∅` |
| P7 | P1 with `task_class = None` | same | identical `qualifying`; `task_class_digest` `None`; `UNCLASSIFIED_EXPLORATORY` / `INELIGIBLE_UNCLASSIFIED`; `evidence_status` explicitly `COMPARISON_EVIDENCE_ABSENT` |
| P8 | field-set test over `ReasoningMethodAdvisoryRequest` and `ReasoningMethodAdvisory` | — | no field named `comparison_results`, `comparison_result_digests` or any `*comparison*` name exists |
| P11 | evaluator-level order independence: P1's admitted canonical `RuleSet` evaluated through three differently ordered internal traversals (rules reversed, catalog entries reversed, qualifying methods shuffled by a seeded permutation), via a test-only traversal hook | same | identical `qualifying`, `excluded`, `trade_offs`, `primary` and `advisory_digest` across all traversals |
| P12 | P1's rules supplied in reversed order | same | `RuleSet` refused with `RULE_SET_UNSORTED`; the rule set has one admitted representation |
| P13 | P2 (two qualifiers) | same | `trade_offs` has exactly two records, one per qualifying method, in `qualifying` order, and none for any excluded method |
| P14 | P5 (two qualifiers supported by the same rule) | same | both trade-offs have empty `distinguishing_reasons`; the advisory carries no preference field, ordering or label between them |
| P9 | P1 with `reversibility = UNDETERMINED` | same | constructs (a profile may be undetermined); same `Q` |
| P10 | P1 twice, then with `rule_set_version` bumped | same | first two digests equal; third differs |
| R-a | any advisory type declared with a field named `score`, `rank`, `probability`, `cost` or `latency_class` | — | refused at class definition |
| R-b | a `Rule` naming a method absent from the catalog | — | `RULE_METHOD_UNKNOWN` at evaluation |
| R-c | a `Predicate` of kind `STRUCTURAL_TOKEN_PRESENT` with a non-signal token | — | `SIGNAL_TOKEN_UNKNOWN` |
| R-d | a request whose `task_class.structural_characteristics` omits a profile token | — | `PROFILE_CLASS_MISMATCH` |
| R-e | a hand-built advisory with `primary` set and `|qualifying| ≠ 1` | — | `PRIMARY_WITHOUT_SOLE_QUALIFIER` |
| R-i | a hand-built advisory with `trade_offs` non-empty and `|qualifying| ≤ 1`, or with `|qualifying| > 1` and a trade-off count other than `|qualifying|`, or a trade-off naming an excluded method | — | `TRADE_OFF_CARDINALITY` |
| R-j | a hand-built advisory whose `RuleOutcome.rule_version` differs from the admitted rule's version for that `rule_id` | — | `RULE_OUTCOME_VERSION_MISMATCH` |
| R-k | a `RuleSet` with two rules sharing a `rule_id` | — | `RULE_DUPLICATE_ID` |
| R-g | a hand-built advisory with `task_class_digest` `None` and `classification = GOVERNED_TASK_CLASS`, or `UNCLASSIFIED_EXPLORATORY` with `eligibility ≠ INELIGIBLE_UNCLASSIFIED` | — | `CLASSIFICATION_INCONSISTENT` |
| R-h | a `Rule` with blank `rule_version` or blank `rationale_statement` | — | `REF_BLANK_FIELD` |
| R-f | `AdvisoryLabel("BENCHMARK_DERIVED")` | — | `ValueError`: not a member |
| B | AST scan of `src/` | — | no forbidden import (§1) |

Slice 2 adds these codes to a package-local `AdvisorErrorCode`:
`PROFILE_CLASS_MISMATCH`, `RULE_METHOD_UNKNOWN`,
`PRIMARY_WITHOUT_SOLE_QUALIFIER`, `CLASSIFICATION_INCONSISTENT`,
`TRADE_OFF_CARDINALITY`, `RULE_OUTCOME_VERSION_MISMATCH`,
`RULE_SET_UNSORTED`, `RULE_DUPLICATE_ID`; it reuses `REF_BLANK_FIELD`, `DIGEST_MALFORMED`,
`SIGNAL_TOKEN_UNKNOWN`, `SCALAR_LABEL_FIELD_PRESENT` and `DATETIME_NAIVE`
from slice 1 `[V]`.

---

## 8. Explicitly excluded from slice 2

No LLM-based selection of any kind. No `BENCHMARK_DERIVED` claim. No
comparison-result ingestion. No numeric outcome prediction. No scalar cost, latency or resource label. No production
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

## 10. Owner ballot — ~~`[R]`~~ **RATIFIED AS AMENDED 2026-09-02**

1. **Contracts and placement — RATIFIED AS AMENDED.** *Owner ruling,
   verbatim:* "approve the separate design-time Reasoning Method Advisor
   capability and its dependency only on the Slice 1 governance contracts.
   The optional-task-class restriction above is binding." Applied: §1
   placement and dependencies; the §2–§3 contracts with `BENCHMARK_DERIVED`
   absent from `AdvisoryLabel`; `task_class` optional with the
   unclassified restriction of §2 as a binding rule; no comparison-results
   field (§6).
2. **Rules and primary selection — RATIFIED AS AMENDED.** *Owner ruling,
   verbatim:* "approve deterministic, versioned, order-independent rule
   evaluation. A primary is permitted only when exactly one method
   qualifies; multiple qualifying methods produce no primary." Applied: the
   §4 evaluation exactly, with `SOLE_QUALIFYING_METHOD` as the only primary
   basis and trade-offs returned for multiple qualifiers; admissibility gate
   4.1-A; initial rule set as a transcription of `SIGNAL_MAP` without
   `SIGNAL_PRIORITY`, carrying stable identifiers, versions, declared
   predicates and rationale, labelled research provenance and not evidence
   of correctness (4.2-A).
3. **Commissioning — RATIFIED AS AMENDED.** *Owner ruling, verbatim:*
   "commission only the research-only, rule-derived Slice 2 described in the
   amended specification. Exclude benchmark-derived advice,
   comparison-result ingestion, LLM-based selection, configuration approval
   and runtime integration." Applied: §8 exclusions and §9 definition of
   done; nothing numeric ratified.

**Remaining open decisions, exact.** Advisor decisions 3 (pilot composition
and sampling policy) and 5 (binding lifecycle, reassessment and post-pilot
approval); Workflow-Fit decisions 1 (usage binding) and 4 (trust controls);
Composite ballots 2 (measurement scale), 3 (normalization policy artifact),
4 (attainment representation) and 5 (advisory carriage); and, within this
specification, the later benchmark-derived slice's contract change (§6).
None is needed for slice 2.

**Authority.** Owner ratification by Rakesh Mohan, 2026-09-02, issued as an
explicit owner instruction in Claude Code session
`session_01VXERHvJzbb9cjZ1GyFFQLn`, which also directed the four amendments
of §11. The model analysis was advisory only; the owner instruction was the
ratifying act. Nothing numeric was ratified, and no source, contract, enum,
experiment or test changed with this record.

---

## 11. Amendment record (owner instruction, 2026-09-02)

| # | Before | After |
|---|---|---|
| 1 | Primary only under unique rule support (`UNIQUE_RULE_SUPPORT`; a third `NoPrimaryReason`) | Primary iff exactly one method qualifies (`SOLE_QUALIFYING_METHOD`); multiple qualifiers return the complete set, reasons and `QualifyingTradeOff`s with no primary; rule count, priority and implementation order never manufacture a winner (§3, §4, P1, P2, P5, R-e) |
| 2 | `task_class` optional with no consequence beyond a `None` digest | Unclassified requests receive exploratory `RULE_DERIVED` advice only, marked `UNCLASSIFIED_EXPLORATORY` / `INELIGIBLE_UNCLASSIFIED`; `COMPARISON_EVIDENCE_ABSENT` explicit on every advisory (§2, §3, §5, P7, R-g) |
| 3 | Request carried a `comparison_results` slot, recorded but unused | Slot removed from both contracts; ingestion only in the later benchmark-derived slice through a separately ratified contract change; field-set test asserts absence (§1, §2, §3, §6, §8, P8) |
| 4 | Transcription of `WorkflowSelector` described as provenance without stating what it is not | Stated as research provenance, not evidence the routing is correct; every rule carries a stable `rule_id`, `rule_version`, declared predicate and `rationale_statement`, propagated into each `RuleOutcome` (§4, R-h) |

**Correction (owner instruction, 2026-09-02, after ratification).** The
ratified text retained `RULE_SET_UNSORTED` while P11 supplied the same rules
reversed and expected an identical digest, which cannot both hold. Resolved
by the canonical-input approach: `RuleSet.rules` must be supplied in one
stated canonical order (ascending `rule_id` by code point), unsorted or
duplicate rules are refused, canonical order affects serialization and never
priority, the advisory digest derives from the single canonical
representation, and P11 is replaced by an evaluator-level traversal-order
test. Constructor obligations on `trade_offs` cardinality, permitted empty
differences, and `RuleOutcome.rule_version` fidelity were added (§4, §7 rows
P11–P14, R-i, R-j, R-k). The three ballot rulings are unchanged by this
correction.
