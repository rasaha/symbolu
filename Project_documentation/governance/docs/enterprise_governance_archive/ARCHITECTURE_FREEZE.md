# Architecture Freeze — Enterprise Governance Track

**Status:** Binding freeze declaration for this track. Extends and restates
[`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md);
if the two ever appear to differ, the ACTIONGATE position document governs and this
file is to be corrected to match.

This declaration is distinct from the unrelated
[`../../ONTOLOGY_FREEZE_CONTRACT.md`](../../../../ONTOLOGY_FREEZE_CONTRACT.md), which
belongs to the Symbolu/Varna track and is not part of Enterprise Governance.

---

## 1. What is frozen

The following are **frozen** for the Enterprise Governance track:

1. **Governance capability model** — the 10 neutral capability groups
   (`agentic/enterprise_governance/model.py`, `CapabilityGroup`). No group is added
   for symmetry or on opinion.
2. **Typed evidence model** — `GovernanceEvidence` with explicit `status`
   (including `MISSING`), `verification`, and `authority_role`; missing data is
   surfaced, never invented.
3. **Reusable invariant framework** — the 11 workflow-agnostic invariants
   (`invariants.py`, `INVARIANTS`) and their fixed failure-code vocabulary; they run
   unchanged across workflows.
4. **Provenance model** — evidence carries source and `source_refs`; findings trace
   to the evidence they derive from.
5. **Authority model** — authority is never inferred from a capability group;
   `is_authority_bearing` requires an authority role AND present status AND real
   verification. The human-policy authority precedence (per-rule → criticality
   registry → default; LLM may tighten, never downgrade a SOURCE_OF_TRUTH decision;
   unknown fails conservatively) is frozen.
6. **ActionGate separation** — the evidence/coherence layer produces findings,
   constraints, dependencies, verified authority, and closure state; **ActionGate
   enforces only the resulting authoritative constraint**. Advisory/reasoning
   findings inform; they do not authorize.
7. **Ontology conclusions** — the twelve-layer ontology is a discovery scaffold, not
   a runtime schema; its labels are not load-bearing (stages 1–2). Rejected as a
   production schema.
8. **Promotion ladder** — `AUDIT → WARNING → APPROVAL_REQUIRED → HARD_ENFORCE`
   (`PromotionLevel`) and the dispositions (preventive/blocking/escalating/
   audit-only) are the fixed vocabulary.

## 2. What is NOT frozen (and why)

These remain open because they are **operational, data-driven** decisions, not
architectural ones:

- **Which individual invariants graduate from audit-only toward enforcement.** A
  real-data decision; integration-closure and prohibited-capability-exposure are the
  named first candidates, but no promotion happens without validated data.
- **The exact capability set may extend — only with new real-world evidence.** A
  real workflow that cannot be expressed is recorded as an architecture-coverage
  gap; extension follows evidence, never opinion.

## 3. The bar for changing anything frozen

**Changes require new evidence. Opinion alone is insufficient.**

Concretely, to change a frozen element:

1. Present **real operational evidence** (from a real pilot) that the current model
   is insufficient or wrong — not a synthetic scenario and not a preference.
2. Record the evidence and the proposed change in
   [`DECISION_LOG.md`](DECISION_LOG.md) with its justification.
3. Show the change does not silently reopen a rejected decision (e.g. re-introducing
   the twelve-layer taxonomy) without directly refuting the ablation results that
   rejected it.
4. Update [`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)
   first; this file follows.

## 4. What a freeze does not mean

- It does **not** claim the frozen model is correct for real enterprises — only that
  it is the validated-on-synthetic-data candidate and should not churn without
  evidence.
- It does **not** forbid real-data validation; that is exactly the intended next
  step.
- It does **not** cover other tracks in this repo.

## 5. Cross-references

- Canonical position: [`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)
- Model code: [`../../agentic/enterprise_governance/`](../../agentic/enterprise_governance/)
- Decisions and evidence: [`DECISION_LOG.md`](DECISION_LOG.md)
- Future work within the freeze: [`FUTURE_WORK.md`](FUTURE_WORK.md)
