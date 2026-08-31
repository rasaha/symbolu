# Constrained Enterprise Output Mapping + Duplicate-Noise Hardening

**Decisive question:** can the system translate correct, traceable quadratic evidence findings into
the correct bounded enterprise outcome using transparent constraints, while preserving abstention,
provenance, access control, and the smallest sufficient evidence set?

Targets the two residual bottlenecks the validated slots+quadratic result left: **output-mapping
failure (~65%)** and **duplicate-waste (~34%)**. Builds strictly **on top of** the frozen stack —
the evidence ledger, P5 slot policy, slot-capacity results, access-control rules, and the frozen
Phase package are imported unchanged (baseline recorded at commit `299f5ba`, FREEZE OK, 9/9).

## Pipeline

```
evidence ledger → deterministic joins → P5 shared binding slots (K=4)
  → bounded full slot-to-slot quadratic → TYPED structured finding
  → deterministic HARD GATES → constrained enterprise outcome
```

The quadratic stage emits a **typed** `StructuredFinding` (budget/policy/approval status, material
conflict, evidence complete) — every field traceable to slot evidence IDs — instead of only a latent
vector. A transparent mapper turns the finding into one of five bounded outcomes.

## Outcomes (non-executing)

`APPROVE` · `REJECT` · `REVIEW_REQUIRED` · `ABSTAIN_INCOMPLETE_EVIDENCE` ·
`ABSTAIN_MATERIAL_CONFLICT`, each with an exact semantic contract (`outcome_contract.decide`). Hard
gates (§7 — unauthorized→blocked, missing→abstain-incomplete, conflict→abstain-conflict,
approval-missing→review) fire before any learned mapping and cannot be overridden.

## Mapper arms

`O0` current learned latent→outcome head (baseline) · `O1` deterministic contract over predicted
typed fields · `O2` constrained rule + confidence/abstention thresholds · `O3` small learned mapper
over typed fields only · `O4` hybrid (hard gates + learned ranking of the non-gated outcomes) · `O5`
oracle contract over the TRUE typed fields (mapping ceiling). O5 separates reasoning-field errors
from mapping errors.

## Duplicate-noise hardening

`duplicate_equivalence.py` replaces unsafe semantic dedup with explicit evidence-equivalence:
classifies each pair (EXACT / SOURCE_REDUNDANT / SEMANTICALLY_SIMILAR_BUT_DISTINCT / CONFLICT_PAIR /
VERSION_PAIR / NON_DUPLICATE) and auto-collapses **only** EXACT and SOURCE_REDUNDANT (provenance
preserved); active/stale, conflict, qualifier, and validity-window pairs are never collapsed. Every
collapse is audited.

## Discipline

No Phase. No learned slot admission. Slot capacity **not** inflated (K=4 primary; K=8/16
confirmatory only). Acceptance thresholds (§14) fixed in advance and never lowered.

## Files

`outcome_contract.py` · `workflows.py` · `structured_reasoning.py` · `policy_mapper.py` ·
`constrained_mapper.py` · `learned_mapper.py` · `duplicate_equivalence.py` · `train.py` ·
`evaluate.py` · `run_mapping.py` · `tests/` · `results/` · `ENTERPRISE_OUTPUT_MAPPING_REPORT.md` ·
`ENTERPRISE_OUTPUT_MAPPING_RESULTS.json`.
