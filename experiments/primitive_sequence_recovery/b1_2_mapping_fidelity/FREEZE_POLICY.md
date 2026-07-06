# Freeze Policy — DEVELOPMENT_FREEZE vs EVIDENCE_FREEZE

Governing policy for the varṇa mapping-fidelity line (B1.2 / B1.3 / any revised Layer-3 work) going forward.
Adopted by operator directive. **Structure, not validated meaning.**

## Two freeze types

- **DEVELOPMENT_FREEZE** — a working snapshot for design iteration. Artifacts under a development freeze
  **may be revised, unfrozen, and refrozen**. Development probes **may be run** to test feasibility, leakage,
  coverage, style comparability, target eligibility, and control construction.
- **EVIDENCE_FREEZE** — a locked configuration whose run **counts as evidence**. Declared **explicitly**, never
  implicitly. Only a run under an active EVIDENCE_FREEZE may be cited as evidence.

## Rules under DEVELOPMENT_FREEZE (the current default)

Allowed: revise / unfreeze / refreeze design artifacts; run development probes (feasibility, leakage,
coverage, style-comparability, eligibility, control construction).

**Prohibited — always, dev or evidence:**

- Do **not** treat development probes as **positive evidence**.
- Do **not** claim `LIMITED_GENERATION_UTILITY`.
- Do **not** claim `MAPPING_FIDELITY_SIGNAL`.
- Do **not** unblock Track B.
- Do **not** claim ontology validation, Sanskrit privilege, or semantic truth.
- Do **not** silently overwrite failed designs — a failed design is preserved and its failure recorded.

**Every refreeze must record:** (1) *what changed*, (2) *why it changed*, (3) *which prior result remains
valid*. Use the refreeze log below.

## Rules at and after EVIDENCE_FREEZE

- A run counts as evidence **only** after an **explicit** EVIDENCE_FREEZE declaration.
- After EVIDENCE_FREEZE, **any design change creates a new experiment version** (e.g. B1.3 → B1.3.1) and
  **cannot be used to rescue the prior frozen run**. The prior frozen run's verdict stands on its own.
- A negative EVIDENCE_FREEZE run is a real negative; a positive one is subject to all the standing non-claims
  above until independently reviewed.

## Standing state at adoption

| item | freeze class | status | valid as |
|---|---|---|---|
| **B1.1** (8-arm generation, judged, scored) | **EVIDENCE** (frozen `b1_1_freeze_manifest.json`) | `RANDOM_OR_SCRAMBLED_MATCHES` | **evidence** (a real negative; unchanged) |
| Track G | EVIDENCE | `RANDOM_POLARITY_EXPLAINS` (1fe5562) | evidence (preserved) |
| Track F | EVIDENCE | `CORRECTNESS_DEGRADED` | evidence (preserved) |
| B1.2 prose R3 powered audit | DEVELOPMENT probe | `STOP_NOW_R3_STYLE_TELL_ROBUST_FAIL` (ba 0.70, CI [0.5929,0.7929]) | **design finding**, not positive evidence |
| B1.2 G builder / lexname inventory / hypernym probe | DEVELOPMENT probe | too-coarse / `V_PROJECTION_TRIVIAL_STOP_NOW` | design findings, not positive evidence |
| B1.2 mapping-fidelity result | — | **none** — no EVIDENCE_FREEZE was ever declared for B1.2 | n/a |

**No EVIDENCE_FREEZE is currently active** for B1.2/B1.3. All B1.2 work to date is DEVELOPMENT; its failed
designs are preserved (not overwritten) and its probe findings are design findings, **not** evidence for or
against Symbol-U. The only standing *evidence* remains B1.1 (negative), Track G, and Track F.

## Refreeze log

Append one row per (re)freeze. Newest first.

| date (op-supplied) | artifact set | freeze class | what changed | why | prior result that remains valid |
|---|---|---|---|---|---|
| — | policy adoption | — | adopted DEVELOPMENT vs EVIDENCE freeze discipline | operator directive | B1.1 `RANDOM_OR_SCRAMBLED_MATCHES` (evidence); Track G/F negatives |

*(No timestamps are auto-generated; the operator supplies dates when recording a refreeze.)*

## Anchors (unchanged)

```
B1.1 verdict:               RANDOM_OR_SCRAMBLED_MATCHES (EVIDENCE; unchanged)
LIMITED_GENERATION_UTILITY: NOT earned
MAPPING_FIDELITY_SIGNAL:    NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
current EVIDENCE_FREEZE:    NONE active for B1.2/B1.3
```

**Structure, not validated meaning.** Development iteration is permitted and does not produce evidence;
only an explicit EVIDENCE_FREEZE does, and it cannot be retro-rescued by later design changes.
