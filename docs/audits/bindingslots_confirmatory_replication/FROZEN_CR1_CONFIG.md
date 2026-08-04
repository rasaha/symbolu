# Frozen CR1 configuration (recovered)

Machine-readable: [`FROZEN_CR1_CONFIG.json`](./FROZEN_CR1_CONFIG.json) — a byte copy of the canonical
`experiments/bindingslots_confirmatory/frozen_cr1_config.json`.

CR1 was recovered byte-for-byte from the merged PR #1319 `SELECTED_CANDIDATE.json` +
`EXPERIMENT_MATRIX.json` + `ACCEPTANCE_GATES.json`, and every referenced source file's sha256 was
recomputed live and confirmed identical.

## Intervention

**CR1 = curriculum + temporary write-read alignment** (Family-3 scaffold combination), the merged
selected candidate.

- `slot_lr = nonslot_lr = 0.002`, `slot_warmup = nonslot_warmup = 60`, single AdamW group
  (`grouped = false`), `orthogonal_keys = false`.

### Curriculum (frozen)

- Boundaries **300 / 700 / 1200**.
- Steps 1–300: needle only at d16, low distractors.
- Steps 301–700: 70 % needle at d16/d96, 30 % binding k=2 interference.
- Steps 701–1200: **original ABC_MIX** distribution (final 500 steps original). Handoff at step 700.
- Identical example count to baseline (16 × 1200).

### Temporary write-read alignment (frozen)

- Label-free overlap objective `L_align = -log(mean_overlap + 1e-6)`.
- λ schedule: **0.10** for steps 1–300, linear decay **0.10 → 0** over steps 301–600, **0** for
  steps 601–1200. **Zero during all evaluation.**
- Signal from an auxiliary needle probe (B_align = 8, mixed d16/d96); its cross-entropy is never
  added to the loss. **No inference-time op or parameter.**

## Architecture (frozen, unchanged)

hidden 128 · heads 4 · layers 4 · local window 64 · **slots 32** · slot-key dim 64 · seq len 160 ·
batch 16 · **1200 steps** · AdamW lr 2e-3 · weight decay 0.01 · warmup 60 · grad clip 1.0 · dropout
0 · fp32 · tied-embedding output head. Slot arm **2 000 104** params; A+ control **2 000 392**.
Architecture signature `6e8672bd…`. Slot read/write equations and inference path unchanged.

## Gates (frozen, inherited from Stage B)

Formation: `d96 ≥ 0.075` ∧ `(S−A+) ≥ 0.050` ∧ `d96 ≥ 0.07`. Stage B gates b1..b11 (formation ≥ 4/5,
mean margin ≥ 0.080, median ≥ 0.050, wins ≥ 4/5, beats B0 formation, param match, ppl ≤ 1.20×A+,
causal collapse every forming seed, d16/d220, no N×N, no Phase/KDA/MLA). Causal collapse per forming
seed: slots-off **and** randomized-address each reduce d96 by ≥ 0.050 absolute, cut the slot gain by
≥ 50 %, and land ≤ max(A+ + 0.030, 0.050).

## Frozen source hashes

All pinned in `FROZEN_CR1_CONFIG.json → frozen_code_hashes_sha256` and re-verified by
`verify_confirmatory_prereg.py` (27/0).
