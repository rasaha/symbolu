# Real Enterprise Pilot Checklist

**Status:** Phase-3 readiness documentation against the **frozen** architecture
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
An operational checklist for running the **first real** enterprise validation. It
adds no architecture and asserts no results. Every box is unchecked; this is a
plan, not a record.

---

## Phase A — Agreement & scope

- [ ] Enterprise names **one** cross-vertical workflow to evaluate first
      (recommended: discount → contract activation).
- [ ] Workflow owner, data owner, and enterprise reviewer identified (roles per
      [`ENTERPRISE_PILOT_ONBOARDING_GUIDE.md`](./ENTERPRISE_PILOT_ONBOARDING_GUIDE.md) §4).
- [ ] Scope confirmed **read-only, historical, shadow** — no write/execute path,
      no live traffic.
- [ ] Data-handling / anonymization agreement signed (what may be exported, how
      pseudonymized).
- [ ] It is agreed in writing that **no automated action** is taken on enterprise
      systems during the pilot.

## Phase B — Mapping

- [ ] Workflow mapped using a blank template ([`templates/`](./templates/)); no
      example data introduced.
- [ ] Each participating source system inventoried (record shape → capability
      group) per [`SOURCE_ADAPTER_SPECIFICATION.md`](./SOURCE_ADAPTER_SPECIFICATION.md).
- [ ] Confirmed the workflow is expressible with the **frozen** 10 capability
      groups and 11 invariants. Any gap recorded as an
      **architecture-coverage gap**, not patched with a new invariant.

## Phase C — Adapters (read-only)

- [ ] One adapter per source implementing `ReadOnlyAdapter`; no write calls.
- [ ] Absent fields emit `EvidenceStatus.MISSING` (no invented/default values).
- [ ] `verification` and `authority_role` set honestly (no free upgrades to
      VERIFIED / AUTHORITY_BEARING).
- [ ] Anonymization applied at the adapter boundary; no PII/PHI/secrets in payloads.
- [ ] Adapter isolation confirmed (imports only the neutral model + stdlib; the
      frozen self-containment test passes).
- [ ] Adapter round-trip validated with the data owner on a small sample.

## Phase D — Baseline

- [ ] Real existing controls inventoried for this workflow.
- [ ] Each control mapped to frozen failure codes → `enterprise_baseline_codes`.
- [ ] Baseline reconciled with the modeled floor (`BASELINE_DETECTABLE`); baseline
      only grown, never shrunk without documented enterprise sign-off
      ([`BASELINE_COMPARISON_FRAMEWORK.md`](./BASELINE_COMPARISON_FRAMEWORK.md) §3).
- [ ] `enterprise_baseline_codes` **hash-locked** before any finding is revealed.

## Phase E — Ground truth

- [ ] Historical sample selected (known-good, known-bad, boundary); selection bias
      recorded.
- [ ] Instances labeled per [`GROUND_TRUTH_PROTOCOL.md`](./GROUND_TRUTH_PROTOCOL.md)
      (`clean` / `problematic` / `unknown`, existing-control coverage, confidence).
- [ ] Problem classes mapped to frozen failure codes **before** findings revealed
      (blind adjudication order).
- [ ] Two-party sign-off; labeled set **hash-locked**.

## Phase F — Metric agreement

- [ ] Concrete pass/fail thresholds for the frozen success criteria agreed **with**
      the enterprise and recorded here (thresholds are not pre-set in
      [`ENTERPRISE_METRICS.md`](./ENTERPRISE_METRICS.md)).
- [ ] Denominators, sample size, and reporting date fields agreed.

## Phase G — Shadow run

- [ ] Inputs (ground truth + baseline + export snapshot) hash-recorded before the
      run ([`SHADOW_MODE_OPERATION.md`](./SHADOW_MODE_OPERATION.md) §4).
- [ ] `ShadowEvaluator` run over real historical `WorkflowEvidence`.
- [ ] All findings treated audit-only; **no promotion, no enforcement**.
- [ ] Per-run log captured (findings, net-new, duplicates, missing-data rate,
      disposition/promotion profile, coverage gaps).

## Phase H — Measurement & review

- [ ] Metrics computed on real data only; `TBD` cells filled solely from the run.
- [ ] Redundant (already-caught) findings reported **before** net-new.
- [ ] `unknown` instances and architecture-coverage gaps reported, not hidden.
- [ ] Findings reviewed with enterprise reviewers; agreement/disagreement recorded.
- [ ] No extrapolation beyond the sample; no ROI/detection/readiness claim from one
      pilot.

## Phase I — Decision

- [ ] Results compared to the agreed thresholds (Phase F).
- [ ] Explicit decision recorded: proceed / iterate / stop — with reasons.
- [ ] Only after validated data may an individual invariant (integration closure /
      prohibited-capability exposure first) be *considered* for promotion — a
      separate, later decision, not part of this pilot.

## Abort conditions (stop, do not tune to rescue)

- [ ] A source needs a write path → out of scope.
- [ ] An adapter cannot map without inventing data → coverage gap, not a workaround.
- [ ] Baseline or ground truth not locked before the run → invalid run, discard.
- [ ] Pressure to change the frozen model to improve a number → refuse; record as a
      research finding.

## Cross-references

- Onboarding: [`ENTERPRISE_PILOT_ONBOARDING_GUIDE.md`](./ENTERPRISE_PILOT_ONBOARDING_GUIDE.md)
- Adapters: [`SOURCE_ADAPTER_SPECIFICATION.md`](./SOURCE_ADAPTER_SPECIFICATION.md)
- Ground truth: [`GROUND_TRUTH_PROTOCOL.md`](./GROUND_TRUTH_PROTOCOL.md)
- Baseline: [`BASELINE_COMPARISON_FRAMEWORK.md`](./BASELINE_COMPARISON_FRAMEWORK.md)
- Metrics: [`ENTERPRISE_METRICS.md`](./ENTERPRISE_METRICS.md)
- Shadow operation: [`SHADOW_MODE_OPERATION.md`](./SHADOW_MODE_OPERATION.md)
- Boundary: [`RESEARCH_BOUNDARY.md`](./RESEARCH_BOUNDARY.md)
- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)
