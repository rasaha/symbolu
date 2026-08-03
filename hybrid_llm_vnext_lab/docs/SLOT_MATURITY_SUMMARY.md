# Slot Maturity Summary — Three Distinct Systems

**Date:** 2026-08-03. These three slot systems must be kept **separate**; evidence is not combined
across them without qualification.

## 1. Historical neural slots — `experiments/phase_lc/models.py::BindingSlots`
Soft learned fixed-slot routing with cumulative weighted-average memory (parallel `[B,N,M,D]` scan).
- **Maturity:** `HISTORICAL_RESULT_ONLY` → reproduction in progress.
  - A arm reproduced **exactly** (params 2000392; ppl256 128.4/108.4/118.0 vs 128.45/108.43/117.98;
    needle 0.025/0.000/0.017) inside the S run.
  - B/C arms + the C slots-off/rand-address/phase-off ablations: A/B/C reproduction executed via the
    hardened launcher (`repro_abc_run1`); classification recorded in the reproduction report against
    the pre-registered `REPRODUCTION_ACCEPTANCE.json`.

## 2. Incubated extracted neural class — `hybrid_llm_vnext_lab/src/binding_slots/legacy_phase_lc_slots.py::BindingSlots`
Byte-identical extraction of (1).
- **Maturity:** `NUMERICAL_PARITY` (in fact **EXACT** — 0.0 max error on forward/gradients/ablations/
  diagnostics/state_dict vs the historical class). This is the neural parity that gates reproduction.

## 3. Slots-only trained arm — S (window + incubated slots, **no Phase**)
The decisive Phase-independent learning test.
- **Maturity:** `PROVISIONALLY_SUPPORTED` — S−A = +0.161 needle@d96, S>A in all 3 seeds, slots-off /
  randomized-address ablations collapse it, benefit is structural (S = S vs A+). **H4
  (Phase-independence) = YES.** Relational (H5) near chance. `READY_FOR_FIVE_SEED_VALIDATION`.

## 4. Streaming bounded neural slots — `hybrid_llm_vnext_lab/src/binding_slots/bounded_binding_slots.py::BoundedBindingSlots`
Dynamic keys, cosine-threshold match, discrete allocation/eviction, version/source metadata.
- **Maturity:** `MECHANICALLY_VALIDATED` (stdlib reference reproduces its discrete semantics
  deterministically; decode-state bounded `[B,M,D]`, no `[N,N]`) **+ `NEURAL_LEARNING_NOT_VALIDATED`**
  (no trained result exists for this metadata-rich variant; it is a `RELATED_BUT_DIFFERENT_ALGORITHM`
  from the historical scan-based slots — no numerical parity claimed between them).

## 5. Stdlib semantic reference — `hybrid_llm_vnext_lab/src/binding_slots/slot_reference.py::SlotReference`
Dependency-free deterministic model of desired slot-memory semantics. Used for algorithmic probes and
as the discrete-metadata oracle. **Not** used as proof of neural parity or of learned behavior.

## Overall

- **Overall slot maturity (learned, Phase-independent, single-fact):** `PROVISIONALLY_SUPPORTED`.
- **Overall composition readiness:** `READY_FOR_FIVE_SEED_VALIDATION` (not `READY_FOR_PACKAGING`).
- Relational memory, five-seed stability, meaningful-scale training, and production decode remain
  **not established**. KDA/MLA composition and packaging are out of scope for this phase.
