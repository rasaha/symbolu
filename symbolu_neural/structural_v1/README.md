# structural_v1 — Stage A structural testbed

> **structure, not validated meaning.** Stage A tests whether a feature-grounded
> operator product produces inventory-specific, factorizable, order-dependent
> **structure** that beats three nulls (bag, random-orthogonal, relabel). A PASS
> establishes a **structural signal only** — it does **not** validate meaning,
> Sanskrit/varna privilege, or LLM usefulness. Operators are **provisional**
> (feature-derived, not estimated from data).

Specs frozen before implementation:
`../../STRUCTURAL_V1_OPERATOR_INITIALIZATION.md`,
`../../STRUCTURAL_V1_GATE_THRESHOLDS.md`,
`../../STRUCTURAL_V1_FACTORIZATION_METRIC.md`.

## Boundaries (enforced by `tests/test_import_ban.py`)
- No import of `llm`, `judge`, `policy`, `policy_v4`, `symbolu_state`.
- No network / API / HTTP client.
- No LLM, policy translation, human-study, cross-modal, or Sanskrit-comparison code.
- numpy-only; deterministic; fixed seeds.

## Contents
| file | role |
|---|---|
| `features.py` | static phonological feature chart (k=4), `decompose` (surfaces all warnings) |
| `operators.py` | generators + `expm`; feature-init, random-orthogonal, relabel, weak-coupling |
| `engine.py` | matrix-product reading (order-sensitive) + bag baseline (order-blind) |
| `metrics.py` | order-effect matrix `B`, structure_score, effective_rank, commuting/coupling coeffs |
| `gate.py` | G1–G4 with frozen thresholds and nulls |
| `report.py` | deterministic markdown report (labeled structure-only) |
| `run.py` | entrypoint: `python -m symbolu_neural.structural_v1.run` |
| `tests/` | minimal correctness tests + import-ban test |

## Run
```
python -m symbolu_neural.structural_v1.run            # writes STAGE_A_STRUCTURAL_REPORT.md
python -m symbolu_neural.structural_v1.tests.test_structural_v1
python -m symbolu_neural.structural_v1.tests.test_import_ban
```

## Gates
- **G1** order-sensitivity exists and ≫ bag (bag = 0 by construction).
- **G2** structure_score beats random-orthogonal null (structure, not magnitude).
- **G3** structure_score beats relabel null (specific feature→unit binding matters).
- **G4** factorization: low effective dim **and** reliable disjoint<shared gap **and**
  beats random-factorization null. (Partly circular by construction; informative parts
  are the relabel / random-factorization nulls.)

**Stage A PASS = G1 ∧ G2 ∧ G3 ∧ G4.** A structural FAIL/INCONCLUSIVE says nothing for or
against meaning, varna privilege, or LLM usefulness — none of which Stage A tests.
