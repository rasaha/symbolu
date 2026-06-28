# ARCHITECTURE_STATUS

> Single-page snapshot of the Symbol-U v1 architecture after Stage A. **Documentation
> synchronization only** — no theory, no implementation, no architectural change.
> **structure, not validated meaning.**

## Repository Status

- **Symbol-U v1 architecture:** Frozen.
- **Stage A:** Implemented (`symbolu_neural/structural_v1/`).
- **Benchmark:** Frozen (Stage A is the reference benchmark for feature-derived operators).
- **v3 / v4:** Archived reference architecture (historical; not the active line).
- **No active implementation beyond Stage A.**

## Current Structural Status

| gate | result |
|---|---|
| **G1** order-sensitivity | **PASS** |
| **G2** beats random-orthogonal (structure) | **PASS** |
| **G3** beats relabel (binding matters) | **PASS** |
| **G4** factorization | **NOT VALIDATED** (not refuted) |

Overall Stage A verdict: **FAIL** on the G1∧G2∧G3∧G4 gate (G4 not validated). Result detail:
`symbolu_neural/structural_v1/STAGE_A_STRUCTURAL_REPORT.md`. Interpretation:
`STAGE_A_RESULT_AUDIT.md`.

## Interpretation

- Stage A validates **structural expressiveness only**.
- Stage A does **not** validate **meaning**.
- Stage A does **not** validate **Sanskrit / varṇa privilege**.
- Stage A does **not** validate **factorization**.
- Stage A is a **proxy benchmark for the feature-derived initialization**
  (`features → operators → structure`), not a decisive test of the deeper operator-first
  architecture (`latent operators → features as projection`).

## Architectural Position

- The **operator-product kernel** (ordered, non-commuting, feature-grounded operators with a
  latent reading state and linear readouts) **remains the architectural baseline** — supported
  at benchmark level by G1–G3.
- **Factorization remains an unvalidated hypothesis** — demoted from a validated/required
  commitment to a tested-but-unvalidated architectural hypothesis (not abandoned, not refuted).
- **Future architectures** (e.g. operator-first / data-estimated) **may be compared against the
  frozen Stage A benchmark using the same evaluation gates** (G1–G4).

## Repository Rule

- **Future architectural revisions require new experimental evidence.**
- The architecture should **not** evolve through additional theoretical refinement alone.

## Pointers

- Theory freeze: `SYMBOL_U_THEORY_V1_FREEZE.md`
- Design-of-record (pre-implementation): `SYMBOL_U_IMPLEMENTABLE_ARCHITECTURE_V1.md`
- Stage A implementation (frozen): `symbolu_neural/structural_v1/`
- Stage A result + interpretation: `STAGE_A_RESULT_AUDIT.md`
- Pre-registered gate / metric specs: `STRUCTURAL_V1_GATE_THRESHOLDS.md`,
  `STRUCTURAL_V1_FACTORIZATION_METRIC.md`, `STRUCTURAL_V1_OPERATOR_INITIALIZATION.md`
