# Readiness Advisory Composite — Design Note

**Status:** design note for owner review. No implementation, no package change.
**Scope:** `packages/capabilities/agent-value-readiness`, its consumed contracts,
and the UVI ADR (`ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`).
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
  only in the producer's own record.
- **Encode both in one method.** A method whose single `score` is defined as the
  lexicographic pair — legal under the contract but opaque, and it hides `B`.
- **Contract change.** A tuple- or map-valued advisory slot. This is a change to
  `ugence-agent-value-readiness` contracts and to the ADR's D-5 wording, and is
  **not** proposed here; it would need its own ratification.

The earlier claim that the proposed pair "slots into the existing contract as-is"
was wrong and is withdrawn.

## 4. The Readiness Assessment Producer boundary

A conceptual role, deliberately **not assigned to any existing package** `[R]`:

| Supplies | Who |
|---|---|
| thresholds, comparators, normalization methods, method versions | governed policy (`GovernedThreshold`, `IntendedOutcomePolicy`) |
| measurements | admitted evidence (`MetricClaim` and its evidence axes) |
| dimension attainments, factor scores, coverage, any `B`/`G` | **the producer** |
| validation and carriage of the admitted result | the readiness package, unchanged |

The producer is the component that would breach the readiness boundary if it
lived inside it. It must also obey ADR "reference producers never self-attest"
(`:322`): a producer's composite arrives with the same evidence axes as its
inputs and elevates nothing.

## 5. Normalization — appropriate to the declared scale

`MetricClaim` carries `governed_unit` but **no declared measurement scale**
(ratio / interval / ordinal). `[G]` `governance-contracts …/evidence.py:357-376`.
`GovernedThreshold` carries one `comparator` and one `literal_value`, with **no
reference bounds**. `[V]` `uvi-policy-contracts …/thresholds.py`.

Consequences the producer must honour:

- **Ratio normalization only where the scale supports it** — positive,
  ratio-scale, meaningful zero. Not universal; not the default.
- **Strict comparators.** `GT`/`LT` must not yield full attainment at equality;
  the pass determination stays with the upstream gate evaluator, and attainment
  cannot exceed what that determination permits. `[V]` `ComparisonOperator`
  has five members, `enums.py:83-93`.
- **Zero thresholds.** A lower-is-better dimension with `t = 0` cannot be
  normalized by `t / v`. Such dimensions need governed reference bounds, which
  the current threshold contract does not carry. `[G]`
- **Ordinal dimensions.** `CapabilityDemonstration` is a four-level ordinal;
  any numeric mapping is a policy artifact, not a code default. `[R]`
- **Coverage.** An unmeasured dimension is excluded, never zeroed and never
  credited. Coverage per factor is reported; the composite is absent below a
  governed minimum. No result may claim "all dimensions met" when the coverage
  rule admitted exclusions.

## 6. Comparison and ranking — not defined

This note defines **no cross-tier ranking and no automated ranking**. Any future
within-tier comparison is restricted to subjects sharing the same requested
target, policy revision, method id and version, outcome class, applicable
dimension set and evidence window. Bucketing `B` is not proposed: it would add
another unratified constant. The marginal-return lever (`argmax α_F / F`) is
**omitted from v1**: it ignores remediation cost and feasibility and can
misdirect action.

## 7. Validation order

1. **Operational outcomes first**, per outcome class: realized utilization,
   override and rejection rates, quality, incidents. These are what a leading
   indicator is supposed to lead.
2. **ROI association second**, as a separate offline study against
   `governed-value` results — never a runtime path, and confounded by investment
   size, deployment selection and business conditions. `SYNTHETIC` evidence is
   evaluation-only and never validates realized value. `[V]` ADR D-9 (`:320`).

Sample size, effect threshold and acceptance criteria are pre-registration
matters, not defaults in this note.

## 8. Owner decisions `[R]`

1. **Contract path for `B` and `G`** — carry one, encode one, or ratify a
   contract change (§3).
2. **Producer host** — which component becomes the Readiness Assessment
   Producer (§4).
3. **Normalization artifacts** — reference bounds, measurement-scale
   declaration, ordinal mapping, strict-comparator handling (§5).
4. **Aggregation and exponents** — factor aggregation rule, coverage minimum,
   and the `α, β, γ` triples per outcome class, all as versioned policy (§2.3).
5. **Validation pre-registration** — primary operational targets, sample size,
   effect threshold, acceptance criteria (§7).

## 9. Contract-fit table

| Quantity | Exists today | Carried unchanged | Unrepresented |
|---|---|---|---|
| Readiness tier, rules `R0`–`R8` | yes `[V]` | yes | — |
| Blocking gate **set** (non-ready) | yes, five trace fields `[V]` | yes | — |
| Lowest observed factor (ready) | no | — | needs producer output `[G]` |
| One advisory score, versioned, `Decimal`, bounded | `AdvisoryComposite` `[V]` | yes | — |
| Second advisory score (`B` *and* `G`) | no | — | singular slot `[V]` |
| Dimension attainment | no | — | no field on any indicator result `[G]` |
| Declared measurement scale | no | — | absent from `MetricClaim` `[G]` |
| Reference bounds per threshold | no | — | absent from `GovernedThreshold` `[G]` |
| Coverage per factor | no | — | `[G]` |
| Producer authority / method registry | no | — | `[G]` |
| Ranking consumer | no | — | none exists; none defined `[V]` |

**Recommendation:** ratify §2 and §4 as architecture. Ratify nothing numeric.
Do not implement until decisions 1–3 are made; decisions 4–5 gate any method
version beyond a stub.
