# Enterprise Governance — Phase-3 Shadow Pilot (neutral capability model)

**Status:** Read-only shadow-mode pilot (`agentic/enterprise_governance/`).
Self-contained; imports no production or ontology-research code.

> **Honesty boundary — read first.** This pilot runs over **realistic source
> *schemas* with *synthetic* fixtures** and a strong existing-controls baseline.
> It is **not** real operational validation. It makes **no claim** of real-world
> efficacy, detection rates, or readiness. Real Phase-3 requires real (or
> anonymized-from-real) artifacts, real existing controls, and domain owners. The
> pilot demonstrates *architecture, reuse, and net-new expressiveness against a
> strong baseline* — nothing more.

---

## 1. Neutral Enterprise Governance Evidence Model

No ontology terminology. Ten capability groups, each carried as typed
`GovernanceEvidence` with explicit **status** (present/partial/**missing**/n-a),
**verification** (declared/inferred/verified/disputed/unknown), and
**authority_role** (authority_bearing/supporting/advisory/non_authoritative).
Authority is never inferred from the capability group. Missing data is explicit —
never invented.

Capabilities: identity & authority · purpose & policy basis · authorized form ·
capability & reachable-action space · advisory-intelligence provenance · decision
derivation & policy versions · protected invariants · enterprise cumulative
constraints · execution & observation · intended-state integration & closure.

## 2. Adapters, not another abstract model

Read-only, source-schema-shaped adapters (`adapters.py`) map one system's record
shape to neutral evidence: `CRMAdapter`, `PolicyRegistryAdapter`, `FinanceAdapter`
(ERP), `IAMAdapter`. Each emits `MISSING` for fields the source does not carry
(e.g. a finance decision with no approver → an explicit missing-authority
evidence record). A workflow does not have to populate every capability.

## 3. Reusable invariants

Eleven workflow-agnostic invariants (`invariants.py`) run **unchanged** over any
workflow: authority provenance, advisory non-escalation, capability containment,
purpose verification, policy-version consistency, form binding, reconciliation,
dependency satisfaction, cumulative constraint, protected invariant, integration
closure. Each finding carries a **disposition** (preventive/blocking/escalating/
audit-only) and a **default promotion level**.

## 4. Strong existing-controls baseline

The baseline (`baseline.py`) is deliberately **generous**: it models an approval
matrix, an ERP reconciliation job, a business-rule engine, and an IAM access
review, and assumes they are present and effective — so it already catches
`MISSING_AUTHORITY_BASIS`, `STATE_RECONCILIATION_FAILURE`,
`PROTECTED_INVARIANT_BREACH`, and `PROHIBITED_CAPABILITY_EXPOSURE`. A finding is
**net-new** only if even this strong baseline would miss it.

## 5. Shadow-mode evaluation

`observe → evaluate → emit findings → compare to baseline → (human review)`. No
automated denial. Promotion ladder per invariant: audit-only → warning →
approval-required → hard-enforce. First enforcement candidates are **integration
closure** and **prohibited-capability exposure**; **cognition/reasoning-style**
findings stay audit-oriented longer.

## 6. Measured results (synthetic, schema-shaped)

Two workflows, one shared invariant suite:

| Workflow | Findings | Net-new vs strong baseline | Baseline already catches |
|---|---|---|---|
| discount → contract | 12 | **9** | authority, reconciliation, protected-invariant |
| IAM role / offboarding | 7 | **5** | authority, prohibited-capability |

- **Net-new codes** (discount): premature closure, policy-version conflict,
  form-execution mismatch, cross-system dependency failure, cross-system state
  conflict, incomplete transition, advisory-authority escalation, unverified
  purpose. (IAM): stale capability, capability-authority mismatch, premature
  closure, incomplete transition, cross-system state conflict.
- **Shared-invariant reuse:** the same 11 invariants govern **both** workflows
  unchanged; `authority_provenance` and `integration_closure` fired in both.
- **False-positive rate: 0.0** (clean variants of both workflows produce zero
  findings).
- **Missing-data explicit:** the finance-approval gap surfaces as a `MISSING`
  evidence record, not a fabricated value.

These show the architecture is reusable and adds expressiveness beyond a strong
baseline — on synthetic data. They do **not** establish real detection value.

## 7. Boundary with ActionGate

```
 Enterprise evidence & coherence layer (this pilot)
        ↓  findings, constraints, dependencies, verified authority, closure state
 ActionGate
        ↓  allow / deny / constrain / escalate / require approval
```

ActionGate enforces only the resulting authoritative constraint. Advisory/
reasoning findings inform; they do not authorize.

## 8. Phase-3 success criteria (for REAL validation — not met here)

Proceed toward productization only if **real-data** validation shows: findings
not trivially available already; low, explainable false positives; shared
invariants reused across multiple real workflows; clear authority provenance;
actionable cross-vertical dependencies; measurable reconciliation/audit
improvement; and at least one preventive finding before an invalid execution.
**This pilot does not and cannot assert these on synthetic data.**

## 9. Recommended immediate sequence (real Phase-3)

1. Use this neutral capability spec as the contract.
2. Select one real cross-vertical workflow (discount→contract is a good first
   pick — it spans Sales/Finance/Legal/CRM/ERP/Billing/Provisioning).
3. Define its real source artifacts and write real read-only adapters.
4. Run read-only historical / shadow evaluation on real records.
5. Compare against the actual existing controls and known outcomes.
6. Promote individual invariants (integration closure, capability exposure first)
   from audit-only toward enforcement only after validated data.

## 10. Limitations and non-claims

- Synthetic, schema-shaped fixtures; no real production records; no real controls.
- The baseline is a *model* of existing controls, intentionally generous.
- No efficacy, detection-rate, ROI, or readiness claim.
- No production code is touched; the ontology-research verdicts are unchanged.
