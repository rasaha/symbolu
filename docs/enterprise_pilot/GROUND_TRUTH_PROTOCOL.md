# Ground-Truth Protocol

**Status:** Phase-3 readiness documentation against the **frozen** architecture
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
This defines how a real enterprise supplies labels so that pilot findings can be
judged. It contains **no** labels, **no** enterprise data, and makes **no** claim
about how the system will score.

---

## 1. Why ground truth is required

A shadow finding is only meaningful against a known answer. Without enterprise-
supplied ground truth we cannot distinguish a true detection from a coincidence,
nor a false positive from an unlabeled true positive. **We do not generate ground
truth ourselves** — doing so would be fabricating enterprise data, which is
explicitly out of bounds ([`RESEARCH_BOUNDARY.md`](./RESEARCH_BOUNDARY.md)). Ground
truth is authored by the enterprise workflow owner.

## 2. Unit of labeling: the historical workflow instance

Label at the level the model evaluates: one **workflow instance**
(a `WorkflowEvidence` assembled by the adapters from one real historical case).
For each instance the enterprise provides:

| Field | Values | Who assigns |
|---|---|---|
| `instance_id` | opaque, stable | data owner |
| `known_outcome` | `clean` / `problematic` / `unknown` | workflow owner |
| `problem_class` (if problematic) | enterprise's own words, then mapped to a failure code | workflow owner |
| `caught_by_existing_controls` | `yes` / `no` / `partial` / `unknown` | workflow owner |
| `materialized_impact` | free text or `none` / `unknown` | workflow owner |
| `label_confidence` | `high` / `medium` / `low` | workflow owner |
| `label_source` | audit record / incident ticket / memory / reconstruction | workflow owner |

`unknown` is a **first-class** label. An instance the enterprise cannot confidently
label stays `unknown` and is excluded from precision/recall (§5), never coerced to
`clean`.

## 3. Mapping problem classes to failure codes (adjudication, not scoring)

The frozen invariants emit a fixed vocabulary of failure codes (`invariants.py`):
`MISSING_AUTHORITY_BASIS`, `ADVISORY_AUTHORITY_ESCALATION`,
`PROHIBITED_CAPABILITY_EXPOSURE`, `STALE_CAPABILITY_STATE`,
`CAPABILITY_AUTHORITY_MISMATCH`, `UNAUTHORIZED_REACHABLE_CAPABILITY`,
`UNVERIFIED_PURPOSE`, `POLICY_VERSION_CONFLICT`, `FORM_EXECUTION_MISMATCH`,
`STATE_RECONCILIATION_FAILURE`, `CROSS_SYSTEM_DEPENDENCY_FAILURE`,
`CUMULATIVE_CONSTRAINT_BREACH`, `PROTECTED_INVARIANT_BREACH`,
`INCOMPLETE_ENTERPRISE_TRANSITION`, `CROSS_SYSTEM_STATE_CONFLICT`,
`PREMATURE_EVENT_CLOSURE`, `UNRESOLVED_INTEGRATION_DEPENDENCY`.

The enterprise describes each problem **in their own language first**. A joint
adjudication session then maps it to zero, one, or several of the codes above.
Rules:

- The mapping is agreed **before** shadow findings are revealed, to avoid fitting
  the labels to the output.
- A problem that maps to **none** of the codes is recorded as an
  **architecture-coverage gap** (the model cannot express it) — a genuine result,
  not something to paper over by inventing an invariant.
- A problem class the enterprise cannot decide is left `unknown`.

## 4. Sampling

- **Include known-bad cases.** The enterprise supplies historical instances they
  *know* were problematic (from incidents, audits, post-mortems) so recall is
  measurable, not just specificity.
- **Include clean cases** to measure false positives — this mirrors the frozen
  clean-workflow false-positive guard (`test_clean_workflows_have_no_findings`).
- **Include boundary cases** the enterprise found ambiguous.
- **Record selection bias.** How instances were chosen is logged; a convenience
  sample is stated as such. No silent filtering.

## 5. How ground truth is used in measurement

Feeds the definitions in [`ENTERPRISE_METRICS.md`](./ENTERPRISE_METRICS.md):

- **True positive** — a finding on an instance labeled `problematic` whose mapped
  failure code matches the adjudicated problem class.
- **False positive** — a finding on an instance labeled `clean`.
- **False negative** — a `problematic` instance with a mapped code that produced
  **no** matching finding.
- **Net-new true positive** — a true positive whose failure code is **not** in the
  baseline-detectable set for that workflow, **and** whose instance was labeled
  `caught_by_existing_controls != yes`
  (see [`BASELINE_COMPARISON_FRAMEWORK.md`](./BASELINE_COMPARISON_FRAMEWORK.md)).
- `unknown`-labeled instances are **excluded** from precision/recall and reported
  separately as coverage-of-unknowns.

## 6. Integrity controls

- **Blind adjudication order:** label → map codes → *then* reveal findings.
- **Two-party sign-off:** workflow owner + data owner both sign the label set.
- **Immutable snapshot:** the labeled set is frozen (hash-recorded) before any
  metric is computed; later relabeling is a new, dated version, not an edit.
- **No back-fitting:** we never adjust invariants, adapters, or the baseline to
  improve a score after seeing ground truth. Any such change would be a research
  finding requiring its own review, not a tuning step.

## 7. What this protocol forbids

- Generating, simulating, or estimating labels on the enterprise's behalf.
- Treating `unknown` as `clean`.
- Revealing findings before the code mapping is agreed.
- Changing the frozen model to fit the labels.

## 8. Cross-references

- Metrics that consume these labels: [`ENTERPRISE_METRICS.md`](./ENTERPRISE_METRICS.md).
- Baseline comparison for net-new: [`BASELINE_COMPARISON_FRAMEWORK.md`](./BASELINE_COMPARISON_FRAMEWORK.md).
- Failure-code vocabulary: `agentic/enterprise_governance/invariants.py`.
- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md).
