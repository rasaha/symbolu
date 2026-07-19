# Resume Guide — Enterprise Governance Track

**Status:** Practical guide for resuming this track months or years later. The track
is **frozen** and research-complete pending real enterprise validation; resuming
means starting the **real pilot**, not more synthetic work. Cross-references the
frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).

---

## 0. Read these first (in order)

1. [`../../FINAL_PROJECT_STATUS.md`](../../FINAL_PROJECT_STATUS.md) — where the track
   stands.
2. [`../enterprise_pilot/RESEARCH_BOUNDARY.md`](../enterprise_pilot/RESEARCH_BOUNDARY.md)
   — what may and may not be claimed. **Non-negotiable.**
3. [`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)
   and [`ARCHITECTURE_FREEZE.md`](./ARCHITECTURE_FREEZE.md) — what is frozen and the
   bar to change it.
4. [`FINAL_CONCLUSIONS.md`](./FINAL_CONCLUSIONS.md) and
   [`KNOWN_LIMITATIONS.md`](./KNOWN_LIMITATIONS.md) — what is / isn't established.
5. [`../enterprise_pilot/REAL_ENTERPRISE_PILOT_CHECKLIST.md`](../enterprise_pilot/REAL_ENTERPRISE_PILOT_CHECKLIST.md)
   — the operational runbook.

## 1. Prerequisites

- **A real enterprise partner** willing to share read-only historical data and name
  domain owners.
- **A named cross-vertical workflow** to evaluate first.
- **Access to run the frozen code** (`agentic/enterprise_governance/`); confirm its
  test suite still passes before anything else.
- **Agreement in writing** that the pilot is read-only, shadow-mode, no automated
  action, historical-first.

## 2. Required enterprise artifacts

From the partner, for the chosen workflow (details in
[`../enterprise_pilot/ENTERPRISE_PILOT_ONBOARDING_GUIDE.md`](../enterprise_pilot/ENTERPRISE_PILOT_ONBOARDING_GUIDE.md) §3):

1. **Read-only historical records** from each participating system (export, replica,
   or scoped read — never a write path).
2. **A description of existing controls** for that workflow (to build the real
   baseline, per [`../enterprise_pilot/BASELINE_COMPARISON_FRAMEWORK.md`](../enterprise_pilot/BASELINE_COMPARISON_FRAMEWORK.md)).
3. **Ground-truth labels** on a historical sample (known-good / known-bad /
   known-outcome), per [`../enterprise_pilot/GROUND_TRUTH_PROTOCOL.md`](../enterprise_pilot/GROUND_TRUTH_PROTOCOL.md).
4. **Anonymization rules** so the adapter can pseudonymize at the boundary while
   preserving cross-system joins.

## 3. Recommended first workflow

**Discount → contract activation.** It spans Sales/Finance/Legal/CRM/ERP/Billing/
Provisioning, exercises the most capability groups, and has a blank mapping template
ready ([`../enterprise_pilot/templates/MAPPING_TEMPLATE_DISCOUNT_APPROVAL.md`](../enterprise_pilot/templates/MAPPING_TEMPLATE_DISCOUNT_APPROVAL.md)).
IAM role/access is a good second workflow (template also provided).

## 4. Recommended pilot sequence

Follow [`../enterprise_pilot/REAL_ENTERPRISE_PILOT_CHECKLIST.md`](../enterprise_pilot/REAL_ENTERPRISE_PILOT_CHECKLIST.md)
Phases A–I:

1. **A Agreement & scope** → 2. **B Mapping** (blank template) →
3. **C Read-only adapters** (MISSING-not-invented) → 4. **D Baseline** (real
controls → `enterprise_baseline_codes`, hash-locked) → 5. **E Ground truth**
(labeled, blind adjudication, hash-locked) → 6. **F Metric agreement** (thresholds
set *with* the enterprise) → 7. **G Shadow run** (audit-only, no enforcement) →
8. **H Measurement & review** → 9. **I Decision**.

## 5. Success criteria

Set concrete thresholds *with* the enterprise (not pre-baked). Proceeding toward
productization requires real-data evidence of: findings not trivially available
already; low, explainable false positives; shared invariants reused across multiple
real workflows; clear authority provenance; actionable cross-vertical dependencies;
measurable reconciliation/audit improvement; and at least one preventive finding
before an invalid execution
([`../../ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md) §8).

## 6. Stop conditions

Stop and report; do not tune to rescue a number:

- A source requires a **write/execute path** → out of scope.
- An adapter **cannot map without inventing data** → record an architecture-coverage
  gap.
- **Baseline or ground truth was not locked** before the run → invalid run, discard.
- Pressure to **change the frozen model to improve a number** → refuse; record as a
  research finding requiring its own review.
- Results **fail the agreed thresholds** → record the negative result honestly.

## 7. Estimated effort (rough, planning-only — not a commitment)

These are coarse planning estimates to size a first pilot, **not** measured figures:

| Step | Rough effort |
|---|---|
| Agreement, scope, data-handling | days–weeks (mostly partner/legal, not engineering) |
| Mapping one workflow | 1–3 days with the workflow owner |
| Read-only adapters (per source) | ~0.5–2 days each; no model changes |
| Real baseline construction | 1–3 days with control owners |
| Ground-truth labeling | depends on sample size and record availability; often the long pole |
| Shadow run + metrics | hours (code is ready) |
| Review + decision | days with enterprise reviewers |

The engineering is small; the **partner-dependent** steps (data access, control
inventory, labeling) dominate the timeline.

## 8. What NOT to do on resume

- Do not add capability groups, invariants, or ontology concepts.
- Do not run more synthetic scenarios.
- Do not wire ActionGate to an enterprise write path before validated data.
- Do not make any efficacy/ROI/readiness claim from a single pilot.
- Do not reopen a frozen decision without new real-data evidence
  ([`ARCHITECTURE_FREEZE.md`](./ARCHITECTURE_FREEZE.md) §3).

## 9. Cross-references

- Readiness package: [`../enterprise_pilot/`](../enterprise_pilot/)
- Future work: [`FUTURE_WORK.md`](./FUTURE_WORK.md)
- Repository index: [`REPOSITORY_INDEX.md`](./REPOSITORY_INDEX.md)
