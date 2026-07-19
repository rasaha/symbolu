# Enterprise Ontology — Cross-Vertical Value Evaluation

**Status:** Self-contained research pilot (`agentic/enterprise_ontology/`).
Read-only; imports no production ActionGate / healthcare / trading / JEPA /
sovereign / latent-state code (enforced by a test). Synthetic scenarios only.

**Question:** does the 12-layer ontology add real cross-vertical value beyond
ordinary per-vertical workflow records — and if so, does the value come from the
twelve labels or from the epistemic/authority metadata?

**Verdict (computed, deterministic): `CROSS_VERTICAL_GOVERNANCE_VALUE`** — with a
sharp qualification: the value is carried by the epistemic/authority/dependency/
reconciliation **metadata** and **~8 of the 12 layers**; four layers
(`cognition`, `integration`, `potential`, `reasoning`) never drive detection.

---

## 1. Method

- 12 sparse semantic layers; a layer may be present/partial/absent/etc. No band
  assumption; **authority is never inferred from the layer** — every record
  carries `epistemic_origin`, `verification`, and `authority_role` independently.
- Ten deterministic cross-vertical invariants. Each is tagged with whether its
  detection **keys on a layer label** or purely on metadata — this drives an
  honest ablation.
- Four fully-modeled multi-vertical scenarios, each with (a) an ontology envelope
  and (b) an ordinary per-vertical **baseline** of workflow records where each
  vertical can raise only its own local flag.
- Comparison = failure classes the ontology surfaces that the baseline cannot.

## 2. Core invariant (implemented + tested)

> No permissive or authority-widening decision may depend solely on advisory,
> non-authoritative, declared-only, or interpretively-inferred records.

`OntologyRecord.is_authority_bearing` returns true only for an explicitly
`authority_bearing` record whose `epistemic_origin` is not interpretive and whose
`verification` is not declared/disputed/unknown. Tests confirm: an advisory or
interpretive record cannot authorize; a record merely *tagged* authority-bearing
but only *declared* is not trusted (`test_declared_authority_bearing_is_not_trusted`).

## 3. Results by scenario

| Scenario | Findings | Ontology-only classes | Baseline caught |
|---|---|---|---|
| Discount (Sales/Finance/IT) | 10 | 8 | `CORE_INVARIANT_BREACH` (Finance-local) |
| Campaign (Marketing/Privacy/Finance/IT) | 10 | 7 | `CORE_INVARIANT_BREACH` (Privacy-local) |
| Procurement (Proc/Finance/Security) | 6 | 4 | `STALE_OR_CONFLICTING_EVIDENCE` (Security-local) |
| Hiring (HR/IT/Payroll) | 7 | 6 | *(nothing)* |

Across the four scenarios the ontology surfaced **10 distinct failure classes the
per-vertical baseline could not express**, driven by all **10 invariants**, with
**20 cross-vertical findings**. The baseline caught only each vertical's own local
flag and, in hiring, nothing at all — because no single vertical sees the whole
event.

Notably, **Procurement is clean on identity/authority/purpose/advisory** and only
trips the Universal/dependency/reconciliation/observation invariants — evidence
the ontology does **not over-flag**: different scenarios exercise different
invariants.

## 4. The findings that matter (evaluation criteria)

1. **Non-obvious cross-vertical dependency/conflict** — ✅ e.g. Marketing launched
   while its Privacy-consent dependency was `DENIED` and IT readiness `PENDING`
   (`CROSS_VERTICAL_DEPENDENCY_FAILURE`); no single vertical's log shows this.
2. **Shared invariant unchanged across scenarios** — ✅ the same 10 invariants run
   over all four events; `FORM_EXECUTION_MISMATCH` fires identically for
   Discount's *quote→contract* and Hiring's *standard→admin access*.
3. **Missing authority/verification gap** — ✅ Sales "approved" a 20% discount
   citing only its own advisory purpose (`MISSING_AUTHORITY_BASIS` +
   `ADVISORY_AUTHORITY_ESCALATION`).
4. **Purpose mismatch between verticals** — ✅ Sales `increase_conversion`
   (declared) vs Finance `preserve_margin` (authoritative) →
   `PURPOSE_POLICY_VIOLATION` + `MISSING_VERIFIED_PURPOSE`.
5. **Local approval vs Universal constraint** — ✅ a within-budget PO still breaches
   firm-wide vendor concentration (`UNIVERSAL_CONSTRAINT_BREACH`); a locally-sized
   campaign still breaches the quarterly marketing budget.
6. **Cross-system reconciliation failure** — ✅ CRM says price 80 / ERP says 100;
   PO 60k / invoice 75k; IAM active / HRIS not onboarded
   (`STATE_RECONCILIATION_FAILURE`, `EXECUTION_OBSERVATION_MISMATCH`).
7. **Generic class grouping different vertical failures** — ✅ the taxonomy maps a
   pricing-quote substitution and an access-level escalation to the same
   `FORM_EXECUTION_MISMATCH`, preserving the original reason codes.
8. **Better audit reconstruction** — ✅ every record carries supplied/observed/
   deterministic/interpretive + declared/inferred/verified + authority role.

## 5. The decisive ablation: labels vs metadata

The ontology's value is **not evenly distributed across the twelve labels.**

- **Metadata-keyed invariants (4/10)** — `authority_provenance`,
  `advisory_non_escalation`, `dependency_satisfaction`, `reconciliation` — key on
  `authority_role`/`verification`/`epistemic_origin` and the dependency/execution
  graph. They would work unchanged if the twelve labels were collapsed to a small
  `record_kind` tag.
- **Layer-keyed invariants (6/10)** — `purpose_consistency` (PURPOSE),
  `form_binding` (FORM/EXECUTION), `core_preservation` (CORE),
  `universal_constraint` (UNIVERSAL), `execution_observation`
  (EXECUTION/OBSERVATION), `identity_authority` (IDENTITY/AGENCY) — use a layer,
  but only as a **coarse selector**; the actual discriminator is still metadata
  (e.g. `verification != VERIFIED`, `authorized_form != executed_form`).
- **Load-bearing layers (8/12):** agency, core, execution, form, identity,
  observation, purpose, universal.
- **Never load-bearing (4/12):** **cognition, integration, potential, reasoning.**
  These carry context/provenance and are useful for audit narration, but **no
  invariant's detection depends on them.**

**Conclusion of the ablation:** the operational value is (a) the
epistemic/authority/verification metadata and (b) a **reduced set of ~6–8 layers**
(Form, Purpose, Core, Universal, Identity/Agency, Execution/Observation). The full
twelve are not required for detection.

## 6. Useful / redundant / missing layers

- **Useful (detection):** Form, Purpose, Core, Universal, Identity, Agency,
  Execution, Observation.
- **Redundant for detection (documentation/observability only):** Cognition,
  Reasoning, Potential, Integration. (Cognition = model advisory is *governed* —
  as advisory it can't authorize — but the ontology enforces that via
  `authority_role`, not via the Cognition *label*.)
- **Missing / thin:** a first-class **cross-event cumulative** substrate (Universal
  is per-event here); an explicit **reconciliation ledger** (modeled as
  after-the-fact execution comparison); and **Potential** (pre-action option-space)
  governance, which no scenario needed.

## 7. Surprising cross-vertical dependencies observed

- A single vertical's "approved" status routinely hides a missing upstream
  authority (Sales-approved discount without Finance sign-off; IT-provisioned
  access without HR identity verification). The baseline shows green in each
  vertical while the event is non-compliant.
- Locally-valid actions breach enterprise constraints (Universal) that no
  participating vertical is positioned to see — the strongest argument for a
  shared cross-vertical layer.

## 8. Where the value came from

**Primarily the provenance/authority metadata, secondarily ~8 of the 12 labels.**
The twelve labels as a *complete set* did **not** materially contribute beyond the
epistemic/authority metadata plus the load-bearing subset. The pilot explicitly
avoids the negative criteria: no invented values were needed, vertical-specific
reason codes are preserved alongside generic classes, and the generic classes
group real structurally-equivalent failures rather than becoming vague.

## 9. Verdict and recommendation

**`CROSS_VERTICAL_GOVERNANCE_VALUE`** — the ontology projection produces reusable,
cross-vertical invariants and findings that ordinary per-vertical workflow records
do not, at acceptable (overlay, read-only) complexity.

**Not** `CANDIDATE_ENTERPRISE_SEMANTIC_ARCHITECTURE`: that claim would require
broader, non-synthetic validation and is deliberately withheld from a four-scenario
pilot.

**Recommendation (deliberately partial):**
- **Adopt** the epistemic/authority/verification metadata + dependency +
  reconciliation model and the generic failure taxonomy — that is where the value
  is.
- **Retain a reduced layer set** (Form, Purpose, Core, Universal, Identity/Agency,
  Execution/Observation) as the shared coordinate system.
- **Demote** Cognition, Reasoning, Potential, Integration to optional
  audit/observability annotations, not required detection layers.
- Treat the twelve-label scheme as a documentation vocabulary, and let any deeper
  embedding be earned by evidence beyond this pilot.

## 10. Limitations and non-claims

- Synthetic scenarios chosen to exercise the invariants; they demonstrate
  *expressiveness and reusability*, not real-world incidence rates.
- "Baseline" is a deliberately naive per-vertical record set; a mature enterprise
  with bespoke cross-system joins could reproduce specific findings — the claim is
  that the ontology makes them *uniform and reusable*, not uniquely possible.
- No production system imports this package; nothing here changes ActionGate,
  healthcare, or trading behavior.
