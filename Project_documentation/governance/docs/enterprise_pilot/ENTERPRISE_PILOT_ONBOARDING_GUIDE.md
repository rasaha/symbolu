# Enterprise Pilot Onboarding Guide

**Status:** Phase-3 readiness documentation. The architecture is **frozen**
(see [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
This guide prepares the project for the **first real enterprise validation**. It
does **not** redesign anything and it contains **no** enterprise data, results, or
efficacy claims.

> **Read the honesty boundary first**
> ([`RESEARCH_BOUNDARY.md`](RESEARCH_BOUNDARY.md)). Everything shipped to date is
> validated on **synthetic, schema-shaped fixtures** against a **strong modeled
> baseline**. No real detection value has been established. This guide describes
> *how a company would participate*, not what results they would get.

---

## 1. What this pilot answers

One question only:

> *If a company agreed tomorrow to evaluate this system, what would they need to
> provide, how would we ingest it, how would we compare against their existing
> controls, and how would we measure success?*

Nothing in this phase asserts operational effectiveness. The pilot is **read-only
and shadow-mode**: it observes, evaluates, and emits findings for human review. It
issues **no** automated denials and touches **no** source system.

## 2. The frozen architecture you are onboarding onto

The runtime is the **Enterprise Governance Evidence Model**
(`agentic/enterprise_governance/`). Its shape is fixed:

| Element | Where | Count | Frozen? |
|---|---|---|---|
| Capability groups | `model.py` (`CapabilityGroup`) | 10 | Yes — do not add for symmetry |
| Reusable invariants | `invariants.py` (`INVARIANTS`) | 11 | Yes — see note below |
| Read-only source adapters | `adapters.py` | 4 reference | Extend per source, same contract |
| Strong-controls baseline | `baseline.py` | 4 detectable codes | Modeled, generous, honest |
| Shadow evaluator + metrics | `shadow.py` | — | Yes |

> **Invariant-count note.** The shadow-pilot doc counts **11** invariant
> functions in `INVARIANTS`. Onboarding a real source **must not** add invariants
> to make a workflow "fit." New invariants are permitted only when *documentation
> or a real, evidenced gap* requires one, per the freeze
> ([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md) §5).
> If a workflow cannot be expressed with the existing capability groups and
> invariants, that is a **finding about the architecture**, to be recorded — not a
> silent extension.

The ten capability groups (neutral, no ontology labels):
identity & authority · purpose & policy basis · authorized form · capability &
reachable-action space · advisory-intelligence provenance · decision derivation &
policy versions · protected invariants · enterprise cumulative constraints ·
execution & observation · intended-state integration & closure.

## 3. What the enterprise provides (and what they do NOT)

**They provide** (read-only, historical, may be anonymized — see
[`SOURCE_ADAPTER_SPECIFICATION.md`](SOURCE_ADAPTER_SPECIFICATION.md) and
[`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md)):

1. **One real cross-vertical workflow** to evaluate first. Recommended:
   *discount → contract activation* (spans Sales/Finance/Legal/CRM/ERP/Billing/
   Provisioning), per the pilot doc's recommended sequence.
2. **Read-only historical records** for that workflow from each participating
   system (export, replica, or scoped read API — never a write path).
3. **A description of their existing controls** for that workflow (approval
   matrices, reconciliation jobs, rule engines, access reviews) so the comparison
   baseline reflects reality, not a strawman
   ([`BASELINE_COMPARISON_FRAMEWORK.md`](BASELINE_COMPARISON_FRAMEWORK.md)).
4. **Ground-truth labels** for a sample of historical cases (known-good, known-bad,
   known-outcome) so findings can be judged
   ([`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md)).

**They do NOT provide, and we do NOT request:**

- Any write/execute credential or path into a production system.
- PII/PHI/secret material beyond what the mapping strictly requires; where a field
  is not needed, it is dropped at the adapter boundary, not carried.
- Live production traffic in the first pilot — historical/shadow only.

## 4. Roles

| Role | Responsibility |
|---|---|
| **Enterprise workflow owner** | Names the workflow, confirms the existing controls, signs off on ground truth. |
| **Enterprise data owner** | Provides read-only historical exports; approves anonymization. |
| **Pilot integrator (us)** | Writes the read-only adapter(s) to the frozen contract; runs shadow evaluation. |
| **Enterprise reviewer** | Adjudicates findings against ground truth; no automated action is ever taken on their behalf. |

## 5. The onboarding sequence

Mirrors the pilot doc's "recommended immediate sequence (real Phase-3)":

1. **Agree the workflow.** Fill a mapping template
   ([`templates/`](./templates/)) with the enterprise owner. Blank templates
   only — no example data is shipped.
2. **Inventory the sources.** For each system in the workflow, record its record
   shape and which capability group(s) it can populate
   ([`SOURCE_ADAPTER_SPECIFICATION.md`](SOURCE_ADAPTER_SPECIFICATION.md)).
3. **Write read-only adapters.** One adapter per source, to the
   `ReadOnlyAdapter` contract. Every field the source does not carry is emitted as
   `EvidenceStatus.MISSING` — never invented.
4. **Capture existing controls → baseline.** Translate the real controls into the
   `StrongControlsBaseline` detectable set so "net-new" means *net-new versus what
   they already run* ([`BASELINE_COMPARISON_FRAMEWORK.md`](BASELINE_COMPARISON_FRAMEWORK.md)).
5. **Collect ground truth.** Label a historical sample
   ([`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md)).
6. **Run shadow evaluation** on the real historical records
   ([`SHADOW_MODE_OPERATION.md`](SHADOW_MODE_OPERATION.md)). No enforcement.
7. **Measure** against the agreed metrics
   ([`ENTERPRISE_METRICS.md`](ENTERPRISE_METRICS.md)) and ground truth.
8. **Review with the enterprise.** Findings are advisory input to their reviewers.

## 6. Where ActionGate sits

Unchanged from the freeze: the evidence/coherence layer produces findings,
constraints, dependencies, verified authority, and closure state; **ActionGate
enforces only the resulting authoritative constraint** (allow / deny / constrain /
escalate / require approval). Advisory and reasoning-style findings inform; they do
not authorize. In this pilot ActionGate is **not** wired to any enterprise write
path — the pilot stops at "findings for human review."

## 7. Exit criteria for onboarding (not for success)

Onboarding is *complete* when: the workflow is mapped, adapters emit evidence with
explicit MISSING for gaps, the baseline reflects the enterprise's real controls,
and a labeled ground-truth sample exists. **Success** is a separate judgment made
later against [`ENTERPRISE_METRICS.md`](ENTERPRISE_METRICS.md) — and this guide
makes no prediction about it.

## 8. Cross-references

- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)
- Shadow pilot (synthetic): [`ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../actiongate/ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md)
- Neutral model code: `agentic/enterprise_governance/`
- This package: adapter spec, ground truth, baseline comparison, metrics, shadow
  operation, checklist, templates, research boundary, readiness report.
