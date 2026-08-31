# ActionGate Governance — Frozen Architectural Position

**Status:** Current architectural position, frozen after the two-stage ontology
research (stage-1 cross-vertical value + stage-2 concept validation). This is the
reference conclusion; **do not redesign the twelve layers again unless new
evidence requires it.**

---

## 1. The frozen conclusion

1. **The ontology is a discovery scaffold, not a runtime schema.** It was useful
   for *finding* the governance capabilities that matter. Under ablation, in both
   stages, the twelve *layer labels* were never load-bearing.

2. **The validated value is a set of typed governance capabilities**, carried by
   evidence + provenance + authority metadata and evaluated by reusable
   invariants:
   - identity and authority;
   - purpose and policy basis;
   - authorized action/form;
   - capability and reachable-action space (pre-action);
   - advisory-intelligence provenance;
   - decision derivation and policy versions;
   - protected invariants;
   - enterprise-wide cumulative constraints;
   - execution and observation;
   - intended-state integration and closure.

3. **The twelve-layer enum and sequence are not justified as a production runtime
   schema.** Retain the *concepts as typed evidence + invariants*; do not adopt
   the twelve-label taxonomy for symmetry.

## 2. Evidence trail (research history, retained)

- `ACTIONGATE_ENTERPRISE_ONTOLOGY_EVALUATION.md` — stage 1:
  `CROSS_VERTICAL_GOVERNANCE_VALUE`; value in provenance/authority/dependency/
  reconciliation metadata; 8/12 layers exercised; 4 not.
- `ACTIONGATE_ENTERPRISE_ONTOLOGY_STAGE2_EVALUATION.md` — stage 2: the four
  "unused" concepts' **content** is load-bearing when exercised (Potential/
  Integration enforcement-relevant; Cognition/Reasoning audit); their **labels**
  are not. Verdict `SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT`.

The ontology packages remain in the tree as research history showing *how* these
capabilities were discovered.

## 3. Consequence for the product architecture

The neutral candidate architecture is the **Enterprise Governance Evidence
Model** (`agentic/enterprise_governance/`) — typed capability evidence +
provenance/authority + reusable invariants, evaluated in read-only shadow mode.
It carries no ontology terminology.

## 4. Boundary with ActionGate

Keep the enterprise model OUT of ActionGate. The evidence/coherence layer
produces findings, constraints, dependencies, verified authority, and closure
state; **ActionGate enforces only the resulting authoritative constraint**
(allow / deny / constrain / escalate / require approval). Cognition and reasoning
findings are audit-oriented and should generally not authorize actions directly.

## 5. What is NOT frozen

- Which individual invariants graduate from audit-only to enforcement (that is an
  operational, data-driven decision — see the Phase-3 pilot doc).
- The exact capability set (may extend with real-world evidence).

What *is* frozen: **no more abstract twelve-layer redesign without new evidence.**
