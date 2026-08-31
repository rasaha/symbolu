# Final Conclusions — Enterprise Governance Track

**Status:** Archival record. No marketing language, no speculation. Every claim is
tagged by evidential status and points at where it was established. Cross-references
the frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).

Scope of "validated": unless a line says otherwise, validation means **on
synthetic, schema-shaped fixtures and/or structurally by tests** — not on real
enterprise data. See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

---

## Validated

*Established by passing tests and/or structural argument on synthetic data.*

1. **Human policy can compose with LLM governance under strict authority
   precedence.** Per-decision authority resolves as explicit per-rule mode →
   criticality registry → engine default; the LLM may tighten but can never
   downgrade a human SOURCE_OF_TRUTH decision; unknown criticality fails
   conservatively. *(Phase 0; `human_policy.py`, `governance_service.py`, tests.)*
2. **Domain specializations wrap the generic engine one-directionally.** Healthcare
   and trading packages depend on the generic engine; the generic engine imports
   nothing domain-specific. Verified by isolation/AST scans and tests.
   *(Phases 1–2.)*
3. **Governance decisions can be enforced end-to-end, not merely advised.**
   HMAC-authenticated constraint-bearing authorization artifacts + deterministic
   enforcement adapters with re-checks (TOCTOU) yield zero unauthorized execution
   and zero sensitive-data leakage under adversarial tests. *(Phases 1–2
   enforcement harnesses.)*
4. **Cross-vertical governance value lives in metadata, not layers.** Value is
   carried by provenance / authority / dependency / reconciliation metadata.
   *(Phase 3, verdict `CROSS_VERTICAL_GOVERNANCE_VALUE`.)*
5. **The four initially-unused concepts' semantic content is load-bearing; their
   labels are not.** Under content-ablation the detections disappear; under
   label-ablation they do not. *(Phase 4, verdict
   `SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT`.)*
6. **A single small invariant suite runs unchanged across different workflows.**
   The same 11 invariants govern both synthetic workflows; `authority_provenance`
   and `integration_closure` fire in both. *(Phase 5; `shadow.py`, tests.)*
7. **Missing data is surfaced, never invented.** Adapters emit `EvidenceStatus.MISSING`
   for absent fields; no invariant fabricates a value. *(Phase 5; adapter contract,
   `test_missing_data_is_explicit_not_invented`.)*
8. **Clean workflows produce zero findings.** False-positive guard holds on
   synthetic clean variants. *(Phase 5; `test_clean_workflows_have_no_findings`.)*
9. **Authority is never inferred from a capability group.** `is_authority_bearing`
   requires an authority role AND present status AND real verification. *(Phase 5;
   `model.py`.)*

## Partially supported

*Directionally shown, but only under conditions that limit the claim.*

1. **Scalability via shared-invariant reuse.** Demonstrated across **two** synthetic
   workflows only; not shown at enterprise breadth or on real workflows.
2. **Net-new expressiveness beyond existing controls.** Findings are net-new only
   against a **modeled** strong baseline, not against any enterprise's real controls.
   The synthetic net-new counts describe fixtures, not organizations.
3. **The capability set is sufficient.** The 10 groups expressed the synthetic
   workflows, but sufficiency for arbitrary real workflows is untested; a real
   workflow may reveal a coverage gap (to be recorded, not patched silently).

## Rejected

*Disproven or explicitly not justified by the evidence.*

1. **The twelve-layer ontology as a production runtime schema.** In both ablation
   stages the layer **labels** were never load-bearing. Rejected as a runtime
   schema; retained only as a discovery scaffold. *(Phases 3–4; freeze.)*
2. **Adopting the twelve-label taxonomy for symmetry.** The enum/sequence is not
   justified for production; content-as-typed-evidence replaces it.
3. **Cognition/reasoning-style findings as direct authorizers.** These are
   audit-oriented and should generally not authorize actions directly.

## Unknown

*No evidence either way; requires real operational data.*

1. **Real detection value** on real workflows (precision).
2. **Real recall** against known-bad real cases.
3. **Real false-positive rate** on real clean cases.
4. **Real scalability** across many real, heterogeneous workflows.
5. **Operational effectiveness / ROI.**
6. **Enforcement validation against real systems** (all enforcement work to date is
   against synthetic EMR / simulated broker).
7. **Whether the frozen capability set is complete** for real enterprises.

## One-line summary

The architecture and method are validated *on synthetic data*; the ontology labels
are rejected as a runtime schema; real-world value, accuracy, and effectiveness are
**unknown** and can only be settled by a real enterprise pilot.
