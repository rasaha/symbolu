# Decision Log — Enterprise Governance Track

**Status:** Archival record of the major decisions and the evidence behind them.
Cross-references the frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).

Each entry: **Decision · Reason · Evidence · Current status.** "Evidence" is what
actually justified the call — synthetic unless stated.

---

### D1 — Human sets authority; the LLM may only tighten

- **Decision:** Human policy governs; the LLM's governance output is advisory and can
  tighten but never downgrade a human SOURCE_OF_TRUTH decision. Per-decision
  authority resolves as per-rule mode → criticality registry → engine default;
  unknown criticality fails conservatively.
- **Reason:** In high-stakes governance, a model must not be able to weaken a human
  decision; authority must be explicit and conservative under uncertainty.
- **Evidence:** Implemented and tested (`human_policy.py`, `governance_service.py`);
  existing behavior/tests preserved when no per-rule/action config exists.
- **Current status:** **Frozen** (authority model).

### D2 — Domains wrap the generic engine one-directionally

- **Decision:** Healthcare and trading specializations depend on the generic engine;
  the generic engine never imports domain code.
- **Reason:** Keeps the core reusable and prevents domain rules leaking into the
  substrate.
- **Evidence:** Isolation/AST scans + tests; across all later phases the only
  generic-engine change was adding `non_critical_facts` to the registry.
- **Current status:** **Frozen** (separation principle).

### D3 — Prove enforcement, not just decision

- **Decision:** Each domain must show the decision is enforced end-to-end via a
  constraint-bearing authorization artifact + enforcement adapter, validated
  adversarially.
- **Reason:** A governance decision that isn't enforced is theater; the claim needed
  teeth.
- **Evidence:** Adversarial tests show zero unauthorized execution and zero
  sensitive-data leakage (synthetic EMR / simulated broker).
- **Current status:** Kept as evidence; **real-system enforcement remains
  UNKNOWN** ([`KNOWN_LIMITATIONS.md`](./KNOWN_LIMITATIONS.md)).

### D4 — Artifacts are HMAC-authenticated, not called digital signatures

- **Decision:** Authorization artifacts use HMAC authentication and are described as
  HMAC-authenticated, not as asymmetric digital signatures.
- **Reason:** Accuracy. HMAC provides integrity/authentication with a shared secret;
  calling it a digital signature would misstate the security property.
- **Evidence:** Implementation uses HMAC; documentation was corrected to match.
- **Current status:** Standing naming rule.

### D5 — Ontology has cross-vertical value, but the layers are suspect

- **Decision:** Accept cross-vertical governance value; flag the twelve layers for
  scrutiny because 4 of 12 were never keyed on.
- **Reason:** Value appeared in provenance/authority/dependency/reconciliation
  metadata, not in the layer taxonomy.
- **Evidence:** Phase 3 verdict `CROSS_VERTICAL_GOVERNANCE_VALUE`; 8/12 layers
  exercised.
- **Current status:** Superseded by D6 (labels rejected as runtime schema).

### D6 — Ontology is a discovery scaffold, not a runtime schema

- **Decision:** Retain the concepts as typed evidence + invariants; **reject** the
  twelve-label taxonomy as a production runtime schema.
- **Reason:** Under ablation the layer **labels** were never load-bearing; the
  **content** was.
- **Evidence:** Phase 4 verdict `SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT`
  (content-ablation removes detections; label-ablation does not).
- **Current status:** **Frozen** (ontology conclusion).

### D7 — Extract a neutral capability model

- **Decision:** Build the Enterprise Governance Evidence Model (10 capability groups,
  11 invariants) with no ontology terminology as the production candidate.
- **Reason:** Carry the validated content without the rejected labels.
- **Evidence:** `agentic/enterprise_governance/`; the 11 invariants run unchanged
  across workflows; tests pass.
- **Current status:** **Frozen** (capability + invariant model).

### D8 — ActionGate remains the enforcement boundary

- **Decision:** Keep the enterprise model OUT of ActionGate; it produces
  findings/constraints and ActionGate enforces only the resulting authoritative
  constraint. Advisory/reasoning findings do not authorize.
- **Reason:** Separation of concerns; prevents advisory signals from silently
  authorizing actions.
- **Evidence:** Boundary described in the freeze and pilot docs; enforced by keeping
  the packages import-isolated.
- **Current status:** **Frozen** (ActionGate separation).

### D9 — Use a strong (not naive) existing-controls baseline

- **Decision:** Model existing enterprise controls generously; count a finding
  net-new only if even a strong baseline would miss it. The baseline may only grow,
  never shrink without documented sign-off.
- **Reason:** A weak baseline inflates apparent value; honesty requires the opposite
  bias.
- **Evidence:** `baseline.py` `BASELINE_DETECTABLE`; `test_strong_baseline_catches_realistic_controls`.
- **Current status:** Standing measurement rule
  ([`../enterprise_pilot/BASELINE_COMPARISON_FRAMEWORK.md`](../enterprise_pilot/BASELINE_COMPARISON_FRAMEWORK.md)).

### D10 — Shadow mode precedes enforcement

- **Decision:** Evaluate read-only in shadow mode (observe → evaluate → emit →
  compare → human review); no automated denial; promotion from audit to enforcement
  is later and data-driven.
- **Reason:** You cannot justify enforcing on findings whose real accuracy is
  unmeasured.
- **Evidence:** `shadow.py`; promotion ladder in `model.py`.
- **Current status:** Frozen operating mode; *which* invariants promote is **not
  frozen**.

### D11 — Stop synthetic validation; prepare for real data

- **Decision:** After the shadow pilot and readiness package, stop synthetic work
  and freeze/archive.
- **Reason:** Additional synthetic work adds no new evidence; the open questions are
  all real-data questions.
- **Evidence:** All remaining unknowns require operational data
  ([`FINAL_CONCLUSIONS.md`](./FINAL_CONCLUSIONS.md) "Unknown").
- **Current status:** **In force** — track frozen.

### D12 — No fabricated data, no efficacy claims

- **Decision:** Ship blank templates, keep all metrics `TBD`, and make no
  operational-effectiveness/ROI/readiness claim.
- **Reason:** Any such claim on synthetic data would be false.
- **Evidence:** [`../enterprise_pilot/RESEARCH_BOUNDARY.md`](../enterprise_pilot/RESEARCH_BOUNDARY.md);
  metrics doc values all `TBD`.
- **Current status:** Standing honesty rule.

---

## Cross-references

- Freeze scope: [`ARCHITECTURE_FREEZE.md`](./ARCHITECTURE_FREEZE.md)
- Conclusions: [`FINAL_CONCLUSIONS.md`](./FINAL_CONCLUSIONS.md)
- Timeline: [`RESEARCH_TIMELINE.md`](./RESEARCH_TIMELINE.md)
