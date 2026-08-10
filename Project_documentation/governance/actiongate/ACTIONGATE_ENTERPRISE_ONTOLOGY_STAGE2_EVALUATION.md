# Enterprise Ontology — Stage-2 Evaluation (Potential / Cognition / Reasoning / Integration)

**Status:** Self-contained extension (`agentic/enterprise_ontology/stage2/`).
Read-only; imports only stage-1 ontology primitives, no production code
(enforced by the stage-1 isolation test that scans the whole package). Synthetic
scenarios only.

**Purpose.** Stage-1 found four layers "not directly exercised as detection
drivers." This stage tests whether they are **genuinely non-load-bearing** or were
merely **under-exercised** because stage-1 began after a concrete action existed,
treated cognition as auxiliary metadata, embedded reasoning in policy/provenance
fields, and represented integration as a reconciliation flag.

**It does not change the stage-1 verdict.** Stage-1's `CROSS_VERTICAL_GOVERNANCE_VALUE`
and its eight-layer detection suite stand. This is a separate finding.

---

## 1. Method — the mandatory distinction

Every stage-2 invariant keys on **typed evidence content** (`isinstance(record.value,
…)`), never on `record.layer`. That makes the two ablations real measurements
rather than assertions:

- **Label ablation** — retag the concept's records to a *different* layer, keep the
  evidence and all metadata. If findings are unchanged, the **layer label** is not
  load-bearing.
- **Semantic-content ablation** — drop the typed evidence, keep every stage-1
  primitive (executions, `reconciliation_status`, authority metadata). If findings
  drop, the **semantic content** is load-bearing.
- **Metadata reproduction** — can stage-1 primitives alone reproduce the finding?

Each concept has a violating case, a clean case (false-positive guard), both
ablations, a baseline comparison, and provenance/authority edge cases. All
deterministic; no LLM judge.

## 2. Results (measured)

| Concept | Findings | After **label** ablation | Lost after **content** ablation | Metadata structured repro | Metadata coarse existence | FP (clean) | Verdict |
|---|---|---|---|---|---|---|---|
| Potential | 4 | 4 | 4 | 0 | no | 0 | `PLANNING_GOVERNANCE_VALUE` |
| Cognition | 5 | 5 | 5 | 1 | yes | 0 | `AUDIT_VALUE` |
| Reasoning | 5 | 5 | 5 | 0 | no | 0 | `AUDIT_VALUE` |
| Integration | 5 | 5 | 5 | 0 | yes | 0 | `ENFORCEMENT_VALUE` |

**Two facts hold for every concept:**
- **Label ablation changes nothing** (findings after = findings full). The twelve
  *labels* are not load-bearing — detection rides on the typed evidence.
- **Content ablation removes everything** (all findings lost). The *semantic
  content* is load-bearing. Stage-1 under-exercised these concepts; they were not
  worthless.

No concept's structured findings are fully reproducible from stage-1 metadata
(strictly `< findings_full` for all four), and there are zero false positives on
the clean cases.

## 3. Per-concept findings

### Potential — `PLANNING_GOVERNANCE_VALUE` (preventive / planning)
Scenario: an IT deploy agent's reachable action space *before any request*.
Detected `PROHIBITED_CAPABILITY_EXPOSURE` (privileged-maintenance reachable),
`STALE_CAPABILITY_STATE` (revoked DR capability still reachable),
`POTENTIAL_AUTHORITY_MISMATCH` (production reachable without release approval),
`UNAUTHORIZED_PLAN_BRANCH` (partner-env reachable, unpermitted). **Metadata
reproduction: 0** — stage-1 governs only concrete submitted actions and is blind
to capability space before a request exists. **This is the clearest new
capability: governance before an executable request.** Enforcement/planning value.

### Cognition — `AUDIT_VALUE` (audit / observability / explanatory)
Four models disagree; a vertical relies solely on another vertical's *unapproved*
advisory model. Detected `ADVISORY_CONFLICT`, `CONFIDENCE_PROVENANCE_GAP`
(0.85 confidence, no rationale), `UNAPPROVED_MODEL_RELIANCE`,
`COGNITIVE_SOURCE_MISMATCH`, and `ADVISORY_AUTHORITY_ESCALATION`. **Only 1 of 5
(the escalation) is reproducible from stage-1 metadata** — a single advisory flag
cannot express model disagreement, model provenance, or confidence grounding. The
*enforcement* part (advisory-cannot-authorize) already existed in stage-1; the
*incremental* value here is audit/observability. Not a generic advisory flag.

### Reasoning — `AUDIT_VALUE` (audit / explanatory)
Verticals reach the same permissive outcome via `POLICY_VERSION_CONFLICT`
(margin@1.0 vs margin@2.0), `INCOMPATIBLE_RULE_BASIS` (distinct exceptions),
`UNJUSTIFIED_OVERRIDE` (exec override, no derivation), `DERIVATION_CHAIN_FAILURE`
(circular chain), and `REASONING_PROVENANCE_GAP`. **Metadata reproduction: 0** —
and this is explicitly value **beyond `policy_refs`**: flat references cannot
compare `(policy, version)` pairs, evaluate exception compatibility, or check a
derivation graph for cycles/completeness. The value is structural
audit/explanatory reconstructability.

### Integration — `ENFORCEMENT_VALUE` (enforcement / audit)
Every local action "succeeded"; the enterprise state is incoherent. Detected
`CROSS_SYSTEM_STATE_CONFLICT` (ERP date, credit hold), `INCOMPLETE_ENTERPRISE_TRANSITION`
(missing invoice schedule), and `PREMATURE_EVENT_CLOSURE` (event marked complete
with unmet closure conditions). **Stage-1 reconciliation catches the *existence* of
a state disagreement** (coarse=yes, via the mirrored CRM/ERP executions) **but not
the structured classes** — not the intended-vs-observed diff, not closure gating,
not premature closure. This directly answers the key question: **Integration adds
value beyond a binary reconciliation flag** by representing intended final state
and the specific unresolved contradictions, and it can *prevent* premature closure.

## 4. Label ablation vs semantic-content ablation

- **Label ablation (all four):** retagging the concept's records to a wrong layer
  produced identical findings. **The layer labels contribute no operational
  value.** This is consistent with stage-1's conclusion that value lives in
  metadata, not the taxonomy.
- **Semantic-content ablation (all four):** removing the evidence — while keeping
  every stage-1 primitive including `reconciliation_status` and authority metadata
  — eliminated all findings. **The information the concepts represent is
  load-bearing**, and it was simply not present in stage-1's scenarios.

## 5. Did earlier conclusions change?

**Refined, not reversed.**
- Stage-1: "eight layers directly involved; four not exercised as detection
  drivers." Correct *for stage-1's invariant suite and scenarios.*
- Stage-2: the four concepts' **semantic content is load-bearing** once scenarios
  require it (pre-action capability space, advisory conflict, reasoning-path
  incoherence, intended-final-state). But their **layer labels remain
  non-essential.**

So the update is: these are not "redundant" concepts — they are **real governance
concepts that stage-1 under-exercised** — yet the value is carried by **typed
evidence + invariants + provenance/authority metadata**, not by the twelve-label
scheme.

## 6. Classification

- **Enforcement-critical:** Potential (pre-action capability containment /
  preventive) and Integration (closure gating / can block premature completion).
- **Audit / observability only (incremental):** Cognition and Reasoning — they
  surface conflicts, model provenance, and derivation incoherence; the hard
  enforcement (advisory-cannot-authorize) already exists in stage-1.
- **Metadata-equivalent:** none fully. Partial overlap: Cognition (1/5 —
  escalation) and Integration (coarse existence via reconciliation).

## 7. Demote or retain?

- **Retain the concept *content*** as typed evidence + invariants:
  `PotentialEvidence` + capability containment/freshness; `IntegrationEvidence` +
  intended-state/closure; `CognitionEvidence` + conflict/model-provenance (audit);
  `ReasoningEvidence` + version/derivation reconstructability (audit).
- **Demote the *labels*.** Do not keep the twelve-label taxonomy for symmetry. In
  both stages, the labels were not load-bearing under ablation.

## 8. Is the complete twelve-layer ontology more justified after this stage?

**The twelve *labels*: no.** Label ablation removed zero value in either stage.
**The four *concepts*: yes** — their semantic content earns retention as
structured evidence and invariants. The right architecture is a compact set of
**typed governance-evidence structures with provenance/authority metadata**, of
which Potential/Cognition/Reasoning/Integration are now demonstrated members —
not a fixed twelve-slot label scheme.

## 9. Interpretation-rule compliance

- Integration value is **not** claimed from `reconciliation_status`: the content
  ablation removes the structured `IntegrationEvidence` while *retaining*
  `reconciliation_status`, and the structured findings still disappear.
- Reasoning value is **not** claimed from `policy_refs`: the invariants use
  structured `(policy, version)` pairs, derivation-graph cycles, and override/
  exception structure that flat refs cannot express.
- Cognition value is **not** a bare confidence field: it produces conflict,
  reliance, provenance, and cross-vertical source findings; only the escalation is
  reproducible from stage-1.
- Potential value is **not** a tool allowlist: it detects pre-action /
  capability-space issues unavailable to request-time governance.

## 10. Overall stage-2 verdict

**`SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT`.** The four concepts carry real,
non-reproducible governance/audit value at the **content** level (Potential and
Integration enforcement-relevant; Cognition and Reasoning audit-relevant), while
the **layer labels** add nothing under ablation. Retain the evidence structures
and invariants; do not adopt the twelve-label ontology for completeness.

## 11. Limitations and non-claims

- Synthetic scenarios chosen to exercise each concept; they show *expressiveness
  and non-reproducibility*, not real-world incidence.
- "Baseline" and "metadata reproduction" are deliberately faithful to stage-1
  primitives; a bespoke enterprise integration could reproduce specific findings —
  the claim is that these concepts make them *uniform, structured, and
  preventable*, and that the labels are not what delivers that.
- No production code is touched; stage-1 results are unchanged.
