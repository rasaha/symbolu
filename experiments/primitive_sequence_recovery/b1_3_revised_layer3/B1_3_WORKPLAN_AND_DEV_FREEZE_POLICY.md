# B1.3 Revised Layer-3 — Workplan & Development-Freeze Policy

## What B1.3 is

A **new, revised** Layer-3 design created **after** the B1.2 development failures. It reuses the B1/B1.1/B1.2
experimental discipline (manifests, audits, target-set hygiene, stratified controls, reporting style) but
changes the measurement object:

- **Old B1.2:** word → varṇa → **bridge prose/glosses** → external feature vector. *(failed: prose was
  style-separable from G, and blindly projected bridge glosses were generic/word-non-specific.)*
- **New B1.3:** word → **raw varṇa sequence** → **fixed varṇa-feature contribution model** → external feature
  vector.

**Core question:** does the *raw varṇa sequence* produce a **word-specific** prediction that matches the
external dictionary-derived G vector better than **screened** controls?

**This is not a rescue of B1.1 or B1.2.** Prior results remain valid for their designs. B1.3 stands or falls
on its own, under an explicit future EVIDENCE_FREEZE that has **not** been declared.

## Development-freeze vs evidence-freeze (governing; mirrors `../b1_2_mapping_fidelity/FREEZE_POLICY.md`)

- **DEVELOPMENT_FREEZE (current mode).** B1.3 artifacts may be **revised, unfrozen, and refrozen**. Development
  probes may be run to test feasibility, leakage, coverage, style/vector comparability, target eligibility,
  and control construction. **No probe output is evidence.**
- **EVIDENCE_FREEZE (not declared).** Only a run under an explicitly declared EVIDENCE_FREEZE counts as
  evidence. After it, any design change spawns a **new version** and **cannot retro-rescue** the frozen run.

### What may be revised before evidence freeze
Design specs, the varṇa-feature model, the G space, the target/control pool, audit thresholds — all revisable,
each revision **documented** in the revision log below.

### What may NOT be claimed before (or ever, improperly)
- No probe treated as **positive evidence**.
- No `LIMITED_GENERATION_UTILITY`; no `MAPPING_FIDELITY_SIGNAL`.
- No Track-B unblock; no ontology validation / Sanskrit privilege / semantic truth.
- No silent overwrite of failed designs (failures preserved + recorded).
- No final evidentiary scoring; no model/judge call for evidence unless a later gate explicitly authorizes it.

### How revisions/refreezes are recorded
Append to the revision log: *what changed, why, which prior result remains valid.*

## Preserved prior facts (unchanged)

```
B1 verdict:                 RANDOM_OR_SCRAMBLED_MATCHES
B1.1 verdict:               RANDOM_OR_SCRAMBLED_MATCHES (EVIDENCE freeze; unchanged)
LIMITED_GENERATION_UTILITY: NOT earned
MAPPING_FIDELITY_SIGNAL:    NOT earned
Track B:                    BLOCKED
Track G:                    RANDOM_POLARITY_EXPLAINS (1fe5562; A_vs_R -0.1917, A_vs_X -0.075) — preserved
Track F:                    CORRECTNESS_DEGRADED — preserved
B1.2 prose path:            STOP_NOW_R3_STYLE_TELL_ROBUST_FAIL (ba 0.70, CI [0.5929,0.7929]) — dev finding
B1.2 feature-space path:    ALT_INVENTORY_V_PROJECTION_TRIVIAL_STOP_NOW
                            (V_real→G_target 0.5194 ≈ off-target 0.5147; top-1 0.014=chance;
                             V_deranged≈V_real; V_random≥V_real) — dev finding
current EVIDENCE_FREEZE:    NONE
```

## Autonomous workplan (this session)

| gate | artifact | purpose |
|---|---|---|
| 1 | B1_3_WORKPLAN_AND_DEV_FREEZE_POLICY.md | this file |
| 2 | B1_3_LAYER3_DESIGN_SPEC.md | revised raw-varṇa Layer-3 object |
| 3 | B1_3_CONTROL_STRATIFICATION_SPEC.md | two-axis (semantic × varṇa) controls |
| 4 | B1_3_EXTERNAL_G_SPACE_REVIEW.md | choose external G space |
| 5 | B1_3_RAW_VARNA_FEATURE_MODEL_OPTIONS.md | **pivotal** — can raw varṇa → feature vector non-circularly? |
| 6 | B1_3_TARGET_AND_CONTROL_POOL_POLICY.md | target/control pool + hashing |
| 7 | B1_3_TRIVIALITY_AND_LEAKAGE_AUDIT_SPEC.md | preregistered dev audits |
| 8 | B1_3_PREREG_READINESS_DECISION.md | ready / needs-adjudication / stop |

Proceed gate-by-gate, commit each clean artifact, stop only on a hard STOP_NOW.

## Revision log (newest first)

| date (op) | artifact | what changed | why | prior result still valid |
|---|---|---|---|---|
| — | v2 propensity reframe (`B1_3_PROPENSITY_REFRAME_REVISION.md`) | unfroze B1.3 dev gates; object changed **varṇa→taxonomic-meaning → varṇa→affective/sensory PROPENSITY**; **B1.2 control arms kept**; target space → external VAD/sensory norms | operator directive; affective/sensory is the one axis the arc never tested (prior nulls were taxonomic) | B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`; B1.2 failures; **B1.3-v1 raw-varṇa ρ≈0 remains valid for *taxonomic* meaning** |
| — | B1.3 creation | new revised Layer-3 line established | B1.2 prose + feature-space paths failed in development | B1.1 `RANDOM_OR_SCRAMBLED_MATCHES` (evidence); Track G/F |

**Structure, not validated meaning.** B1.3 is development-only design work; no evidence, no positive claim,
until an explicit EVIDENCE_FREEZE.
