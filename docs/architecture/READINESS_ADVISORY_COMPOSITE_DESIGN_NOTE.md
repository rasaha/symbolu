# Readiness Advisory Composite — Design Note

**Status:** design note; **owner ballot 1 recorded AMENDED 2026-09-02** (§10;
ballots 2–5 remain `[R]`). No implementation, no package change.
**Scope:** `packages/capabilities/agent-value-readiness`, its consumed contracts,
the UVI ADR (`ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`) and the ratified
Trusted Evidence and Benchmark Registry ADR
(`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`).
**Evidence labels:** `[V]` verified against the repository · `[I]` inferred ·
`[R]` requires owner ratification · `[G]` gap.

## The load-bearing question

**Can the readiness package emit a genuine Intelligence / Capability / Adoption
composite today?** No. It can *carry* one advisory score it did not compute, and
the contract that carries it holds exactly one score. Everything below follows
from that.

## 1. The boundary, from repository evidence

- The package performs **no metric-to-threshold calculation**; it consumes gate
  statuses recorded upstream and does not compute them. `[V]`
  `README.md:13-14`, restated at `README.md:203-204`, and listed as deferred at
  `README.md:614`.
- A composite is **advisory only** — it may compare systems *within* a tier and
  can **never** change the tier. `[V]` ADR D-5 (`:76`); mandatory gates are
  non-compensatory and non-waivable, and "high composite" is named among the
  things that cannot convert a failure into readiness. `[V]` ADR D-6 (`:79`).
- The evaluator reads `advisory_composite` in exactly three places: to add the
  advisory `GV3RB_ADV_COMPOSITE_CARRIED_NOT_USED_IN_SELECTION`, to echo it onto
  the determination, and to record `advisory_composite_carried` on the trace.
  `[V]` `evaluation/evaluator.py:336,378,413`. It is never read during rule
  selection. `[V]`
- **Nothing in either UVI package computes an attainment or a composite**, and
  **nothing ranks subjects**. `[V]` grep of `src/` for attainment, composite
  computation, ranking and score-sorting: no matches.
- `contracts/composite.py` states the deliberate absence: *"no default weight
  and no `Intelligence × Capability × Adoption` formula — if no versioned method
  is supplied the composite is simply absent rather than fabricated."* `[V]`

## 2. Three conceptually separate outputs

### 2.1 Readiness classification — unchanged
The gate-based evaluator, rules `R0`–`R8`, `EVALUATOR_FORMULA_VERSION`
`GV-3R-b.3`. Nothing in this note touches it.

### 2.2 What blocks, or what is lowest
For a **non-ready** result the evaluator trace already exposes the complete
blocking set — it is a set, not one gate. `[V]` `evaluation/trace.py:67-72`:

```
missing_required_gate_ids · mandatory_failure_gate_ids
mandatory_indeterminate_gate_ids · non_compensable_conditional_gate_ids
uncovered_conditional_gate_ids
```

Report these as they are. Do not collapse them to a single "binding gate";
several gates can bind at once and the trace already says which.

For a **ready** result nothing binds. Report the **lowest observed factor**,
including ties, under that label — not "binding constraint," which would imply
a blocker that does not exist.

### 2.3 Optional advisory quantities
```
B = min(I, C, A)
G = I^α · C^β · A^γ      α + β + γ = 1
```
Both computed **upstream** (§3), both coverage-qualified, neither ever consulted
by the classification. `G` is a *balance* score: it is non-compensatory only at
zero — `(0.4, 1, 1)` scores above `(0.7, 0.7, 0.7)` — which is why `B` exists as
a separate quantity and why `G` alone must not be read as readiness. `[V]`
arithmetic.

## 3. Contract fit: can `AdvisoryComposite` carry both?

**No, not as it stands.** `[V]` The slot is singular on every carrier —
`ReadinessEvaluationCase`, `ReadinessAssessmentRequest`,
`AgentValueReadinessDetermination` each declare
`advisory_composite: Optional[AdvisoryComposite] = None` — and the contract holds
one `score` with one `method_id`/`method_version`. It cannot carry `B` and `G`
as two governed quantities.

Alternatives, none selected here `[R]`:

- **Carry one.** Emit `G` (or `B`) as the sole composite in v1; report the other
  only in the consuming evaluation engine's own record.
- **Encode both in one method.** A method whose single `score` is defined as the
  lexicographic pair — legal under the contract but opaque, and it hides `B`.
- **Contract change.** A tuple- or map-valued advisory slot. This is a change to
  `ugence-agent-value-readiness` contracts and to the ADR's D-5 wording, and is
  **not** proposed here; it would need its own ratification.

The earlier claim that the proposed pair "slots into the existing contract as-is"
was wrong and is withdrawn.

## 4. The comparison boundary is already ratified

An earlier draft of this note proposed a new "Readiness Assessment Producer"
role. **That was wrong and is withdrawn.** The role already exists, ratified,
under a different name: the **consuming evaluation engine**.

`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md` §18 separates four
artifacts and assigns each an owner `[V]`:

| Artifact | Owner |
|---|---|
| Benchmark definition — *what is measured and how comparison is interpreted* | Ugence Benchmark Registry |
| Observed measurement | measurement systems; evidence verified by TAP |
| **Benchmark comparison result** — *deterministic comparison of a verified observation against an exactly resolved definition* | **consuming evaluation engine** |
| Policy decision — *whether that comparison matters* | Policy Authority (requirement), applied by the consuming engine |

The same assignment is restated twice more: §7.2 row 5 puts "calculating
benchmark results / comparisons" with the consuming evaluation engine, and §8's
role-separation matrix row 11 names the "measurement / comparison engine" as the
consuming evaluation engine — explicitly **not** the Registry, TAP or Policy
Authority `[V]`. **B-12 — "The Registry computes nothing"** states that the
Registry does not manufacture observations, calculate benchmark results, perform
comparisons, compute readiness or calculate ROI; its outputs are definitions and
resolutions `[V]`.

**No new role may be created for this.** Introducing a second name for a
ratified boundary would create exactly the parallel vocabulary this platform is
built to avoid.

Note what the same ADR assigns separately: §7.2 row 6 puts "computing readiness"
with `agent-value-readiness`, and §8 row 12 names it the *readiness consumer*,
not an evidence verifier or benchmark registrar (§19) `[V]`. Computing readiness
and performing benchmark comparison are therefore **distinct ratified roles**.
Which component plays the consuming evaluation engine for readiness attainments
is unresolved here `[R]`; this note only forbids inventing a new name for it.

## 5. Normalization — appropriate to the declared scale

**The Registry stores semantics and references, and performs no normalization,
conversion or comparison.** `BenchmarkMeasurementSemantics` records seven
required coordinates — `intended_outcome_ref`, `metric_ref`, `unit`,
`measurement_protocol_ref`, `population_ref`, `aggregation_semantics_ref`,
`observation_window_ref` — and states in its own contract that no conversion,
normalization, dimensional analysis, comparison, aggregation or evaluation
happens there or anywhere in that package `[V]`.

**Measurement scale is absent from every contract.** `MetricClaim` carries
`governed_unit`; `BenchmarkMeasurementSemantics` carries `unit`; neither
declares ratio / interval / ordinal / binary / categorical. `[G]`
`governance-contracts …/evidence.py`, `benchmark-registry …/BenchmarkMeasurementSemantics`.

**Direction already exists — do not duplicate it.** `GovernedThreshold.comparator`
is a five-member `ComparisonOperator` (`GTE`, `GT`, `LTE`, `LT`, `EQ`) `[V]`
`enums.py:83-93`. A separate `HIGHER_IS_BETTER` field would be a second encoding
of the same fact. What `GovernedThreshold` does **not** carry is reference
bounds: it holds `threshold_id`, `governed_unit`, `comparator`, `literal_value`
and an optional `benchmark_ref`. `[V]` `uvi-policy-contracts …/thresholds.py`.

UVI ADR §13, preserved by §18, fixes where a threshold may live: a signed
threshold is a `PolicyThreshold` literal or a `BenchmarkReference`, **never** a
`MetricClaim` `[V]`. Normalization policy therefore attaches to the
policy/threshold side, not to observations.

Consequences the consuming evaluation engine must honour:

- **Ratio normalization only where the scale supports it** — positive,
  ratio-scale, meaningful zero. Not universal; not the default.
- **Strict comparators — attainment and pass/fail are separate results.**
  A value of `0.90` against a `GT 0.90` threshold yields **attainment 1.0** and
  **threshold status failed**. Full normalized attainment does not imply a pass,
  and the pass determination stays with the upstream comparison, never with the
  normalization. Any contract carrying attainment must keep the two fields
  distinct.
- **Zero thresholds.** A lower-is-better dimension with `t = 0` cannot be
  normalized by `t / v`. Such dimensions need governed reference bounds, which
  the current threshold contract does not carry. `[G]`
- **Ordinal dimensions.** `CapabilityDemonstration` is a four-level ordinal;
  any numeric mapping is a policy artifact, not a code default. `[R]`
- **Coverage.** An unmeasured dimension is excluded, never zeroed and never
  credited. Coverage per factor is reported; the composite is absent below a
  governed minimum. No result may claim "all dimensions met" when the coverage
  rule admitted exclusions.

## 6. Recorded recommendations — not implemented, not ratified

Recorded for the ballot. None is implemented; none is a default.

1. **Measurement scale belongs on `BenchmarkMeasurementSemantics`**, because it
   describes the governed metric definition rather than an individual
   observation. It stays descriptive metadata — the Registry still computes
   nothing (B-12).
2. **Normalization policy belongs on the policy/threshold side** and reuses
   `GovernedThreshold.comparator`. Direction is not duplicated. Reference bounds
   and ordinal mappings are method-specific and optional *according to the
   declared measurement scale* — not universally required.
3. **Any attainment addition should be an optional nested advisory object on the
   existing indicator results** — not a parallel result schema and not a bare
   scalar. It must bind: a normalized `Decimal` in `[0, 1]`; normalization
   method id and version; policy / threshold / benchmark references;
   coverage or applicability status; and `is_advisory=True`.
4. **Coverage belongs in a factor / profile summary** and must expose the
   measured and applicable populations, not a single unexplained percentage.
5. **The singular `AdvisoryComposite` remains unchanged** until the owner
   separately decides whether its one score represents `B`, represents `G`, or
   whether a separately ratified profile contract is justified.

### Cross-ADR consequence

Recommendation 1 modifies `BenchmarkMeasurementSemantics`, a contract ratified
under `ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md` (B-1, §15), whose
current form has **no optional field, no default and no partial state** `[V]`.
**Adding measurement scale to it is a cross-ADR contract decision and requires
an ADR amendment before any code.** It cannot be carried as an incidental field
addition, and this note does not propose the amendment text.

## 7. Comparison and ranking — not defined

This note defines **no cross-tier ranking and no automated ranking**. Any future
within-tier comparison is restricted to subjects sharing the same requested
target, policy revision, method id and version, outcome class, applicable
dimension set and evidence window. Bucketing `B` is not proposed: it would add
another unratified constant. The marginal-return lever (`argmax α_F / F`) is
**omitted from v1**: it ignores remediation cost and feasibility and can
misdirect action.

## 8. Validation order

1. **Operational outcomes first**, per outcome class: realized utilization,
   override and rejection rates, quality, incidents. These are what a leading
   indicator is supposed to lead.
2. **ROI association second**, as a separate offline study against
   `governed-value` results — never a runtime path, and confounded by investment
   size, deployment selection and business conditions. `SYNTHETIC` evidence is
   evaluation-only and never validates realized value. `[V]` ADR D-9 (`:320`).

Sample size, effect threshold and acceptance criteria are pre-registration
matters, not defaults in this note.

## 9. Contract-fit table

Corrected against the Benchmark Registry and governance contracts.

| Quantity | Exists today | Carried unchanged | Unrepresented |
|---|---|---|---|
| Readiness tier, rules `R0`–`R8` | yes `[V]` | yes | — |
| Blocking gate **set** (non-ready) | yes, five trace fields `[V]` | yes | — |
| Governed metric definition | `BenchmarkMeasurementSemantics`, 7 required coordinates `[V]` | yes | scale only |
| Claim → definition / policy linkage | `MetricClaim.benchmark_refs`, `.policy_refs`, `.calculation_ref`, `.model_ref` `[V]` | yes | — |
| Threshold + direction | `GovernedThreshold.comparator`, 5 operators `[V]` | yes | reference bounds |
| Factor grouping I / C / A | `ReadinessIndicatorClass` + three catalogs `[V]` | yes | — |
| Dimension result provenance | indicator results carry dimension, `claim`, `status`, `threshold_ref`, `benchmark_ref`, `evidence_refs`, system binding `[V]` | yes | — |
| Policy resolution | `PolicyAuthorityReadinessPolicyResolver` `[V]` | yes | measurement policy |
| One advisory score, versioned, `Decimal`, bounded | `AdvisoryComposite` `[V]` | yes | — |
| **Declared measurement scale** | no | — | `[G]` |
| **Governed normalization policy / reference bounds** | no | — | `[G]` |
| **Normalized advisory attainment** | no | — | `[G]` |
| **Coverage / factor summary** | no | — | `[G]` |
| **More than one advisory quantity** (`B` *and* `G`) | no | — | singular slot `[V]` |
| Ranking consumer | no | — | none exists; none defined `[V]` |

Five gaps remain, not seven new contracts. The earlier inventory understated
what already exists and is corrected here.

## 10. Owner ballots `[R]`

1. **Comparison-engine assignment** — ~~`[R]`~~ **AMENDED 2026-09-02.** *As
   proposed:* which component plays the ratified consuming evaluation engine
   for readiness attainments (§4), with the recommendation to bind to the
   existing role rather than create one. *Owner ruling:* the
   consuming-evaluation-engine responsibility is assigned to a **separately
   commissioned readiness-comparison component upstream of
   `agent-value-readiness`**, not to the current readiness evaluator itself. It
   performs deterministic comparison and emits comparison/attainment records;
   readiness consumes them. **This assigns responsibility but authorizes no
   package, contract or implementation.** The ratified role (§4) is bound, not
   renamed; the component that plays it is new.
2. **Measurement scale** — adopt recommendation 1, requiring an amendment to the
   Benchmark Registry ADR before code (§6).
3. **Normalization policy artifact** — reference bounds, ordinal mappings and
   method versioning on the policy/threshold side (§6, recommendation 2).
4. **Attainment representation** — the nested advisory object on existing
   indicator results, its required fields, and its versioning (§6, recommendation 3).
5. **Advisory carriage** — whether `AdvisoryComposite` carries `B`, carries `G`,
   or a profile contract is ratified; and the coverage summary shape (§6, recommendations 4 and 5).

Constants, formulas, exponents, mappings, coverage minima and statistical
acceptance criteria remain unratified with no defaults, as in §8.

**Recommendation (post-ratification, 2026-09-02):** ballot 1 is resolved
AMENDED as recorded above; commissioning and contract ratification for the new
readiness-comparison component still block implementation. Ballots 2–5 remain
`[R]`. Ratify nothing numeric. Ballot 2 requires an ADR amendment before any
code. Ballots 3 and 4 gate implementation; ballot 5 gates any advisory output
beyond a single score.

**Ratification record (2026-09-02).** Ballot 1 AMENDED as recorded above.
Ballots 2, 3, 4 and 5 remain `[R]`. The ruling departs from the §4
recommendation on *which component* plays the role while preserving the
role itself.

**Authority.** Owner ratification by Rakesh Mohan, 2026-09-02, issued as an explicit owner instruction in Claude Code session `session_01VXERHvJzbb9cjZ1GyFFQLn` after advisory analysis in ChatGPT/Codex and Claude sessions of the same date. The model analysis was advisory only; the owner instruction was the ratifying act. Nothing numeric was ratified, and no code, contract, enum, experiment or test changed with this record.
