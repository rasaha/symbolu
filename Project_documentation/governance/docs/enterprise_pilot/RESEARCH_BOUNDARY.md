# Research Boundary

**Status:** Phase-3 readiness documentation against the **frozen** architecture
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
This is the honesty contract for the whole enterprise-pilot package. Read it before
any other document here and before quoting any number to anyone.

---

## 1. The one thing to remember

**Nothing in this repository has been validated on real enterprise data.**
Everything shipped — the neutral Enterprise Governance Evidence Model, its
invariants, the shadow pilot, and every number in the pilot doc — runs on
**synthetic, schema-shaped fixtures** against a **modeled** existing-controls
baseline. That demonstrates *architecture, reuse, and net-new expressiveness on
synthetic data*. It establishes **no** real-world detection value, accuracy, ROI,
or readiness.

## 2. What is proven vs. what is not

| Claim | Status | Evidence |
|---|---|---|
| The 10 capability groups + 11 invariants run unchanged over multiple workflows | **Shown on synthetic data** | `shadow.py`, `tests/test_enterprise_governance.py` |
| Missing data is surfaced, never invented | **Shown structurally** | adapter contract emits `MISSING`; test `test_missing_data_is_explicit_not_invented` |
| Clean workflows produce zero findings (false-positive guard) | **Shown on synthetic data** | `test_clean_workflows_have_no_findings` |
| Findings are net-new vs a *strong* modeled baseline | **Shown on synthetic data** | `baseline.py`, `test_strong_baseline_catches_realistic_controls` |
| The layer/ontology *labels* were never load-bearing | **Concluded (research)** | stage-1 & stage-2 evaluations, frozen position |
| Real detection value on real workflows | **NOT established** | requires a real pilot; every metric is `TBD` |
| Real false-positive rate on real data | **NOT established** | `TBD` |
| Operational effectiveness / ROI / readiness | **NOT claimed** | out of scope by design |

## 3. Hard prohibitions for this phase

These are non-negotiable and apply to all ten deliverables:

1. **Do not fabricate enterprise data.** No synthetic record is ever presented as
   real. Templates ship **blank**.
2. **Do not fabricate or estimate results.** Metric cells stay `TBD` until a real
   run fills them with dated, denominator-bearing values.
3. **Do not claim operational effectiveness.** No "detects X% of…", no ROI, no
   "production-ready".
4. **Do not redesign the frozen architecture.** No new capability groups, no new
   ontology concepts, no reshaping of the evidence/authority model, invariants,
   promotion ladder, or ActionGate boundary.
5. **Do not add invariants** except where *documentation* genuinely requires it,
   with the reason recorded. A workflow that will not fit is a **coverage gap to
   report**, not a prompt to extend the model.
6. **Do not modify production code** (ActionGate / healthcare / trading / JEPA /
   sovereign / latent-state / enforcement).
7. **Do not alter previous research conclusions** (stage-1, stage-2, the freeze).
8. **Do not connect a write/execute path** to any enterprise system; the pilot is
   read-only shadow.
9. **Do not open a pull request** unless explicitly asked.

## 4. What IS in bounds for this phase

- Documentation describing *how* a real pilot would be onboarded, ingested,
  compared, and measured.
- Blank mapping templates.
- Cross-referencing the frozen architecture and the existing shadow pilot.
- Recording coverage gaps and open questions honestly.

## 5. Continuity with prior conclusions

- **Stage-1** (`ACTIONGATE_ENTERPRISE_ONTOLOGY_EVALUATION.md`):
  `CROSS_VERTICAL_GOVERNANCE_VALUE`; value in provenance/authority/dependency/
  reconciliation metadata; 8/12 layers exercised, 4 not. **Unchanged.**
- **Stage-2** (`ACTIONGATE_ENTERPRISE_ONTOLOGY_STAGE2_EVALUATION.md`):
  `SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT`. **Unchanged.**
- **Freeze** (`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`): ontology is a
  discovery scaffold; the validated value is typed capabilities + invariants; no
  more twelve-layer redesign without new evidence. **Unchanged.**

This package sits **downstream** of all three and changes none of them.

## 6. How to talk about this externally

- Correct: "We have an architecture and a read-only shadow method; on synthetic
  data it reuses one invariant suite across workflows and surfaces net-new findings
  against a strong modeled baseline. We have not yet run it on real enterprise
  data."
- Incorrect: anything implying measured real-world detection, accuracy, or
  readiness.

## 7. Cross-references

- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md).
- Synthetic pilot & non-claims: [`ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md) §10.
- Metrics (all `TBD`): [`ENTERPRISE_METRICS.md`](./ENTERPRISE_METRICS.md).
- Readiness self-assessment: [`ENTERPRISE_READINESS_REPORT.md`](./ENTERPRISE_READINESS_REPORT.md).
