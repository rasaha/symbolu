# Slot Maturity Summary — Three Distinct Systems

**Date:** 2026-08-03. These three slot systems must be kept **separate**; evidence is not combined
across them without qualification.

## 1. Historical neural slots — `experiments/phase_lc/models.py::BindingSlots`
Soft learned fixed-slot routing with cumulative weighted-average memory (parallel `[B,N,M,D]` scan).
- **Maturity:** `HISTORICAL_RESULT_ONLY` → **`EXACT_REPRODUCTION`**.
  - Full A/B/C reproduced exactly (`repro_abc_run1`, wall 73 min): params exact (A 2000392, B 1999752,
    C 2000492); ppl A 128.4/108.4/118.0, B 62.4/59.3/96.5, C 87.3/83.0/79.7 (vs 128.45/108.43/117.98,
    62.45/59.34/96.50, 87.28/83.02/79.71); C needle 0.467/0/0 (historical 0.4667/0/0).
  - **Causal ablation reproduces exactly** (C seed0): baseline 0.467 → slots_off 0.017, rand-address
    0.050, phase_off 0.475 (unchanged). See the reproduction report + `REPRODUCTION_ACCEPTANCE.json`.
  - Frozen `abc.json` never written (sha256 unchanged).

## 2. Incubated extracted neural class — `hybrid_llm_vnext_lab/src/binding_slots/legacy_phase_lc_slots.py::BindingSlots`
Byte-identical extraction of (1).
- **Maturity:** `NUMERICAL_PARITY` (in fact **EXACT** — 0.0 max error on forward/gradients/ablations/
  diagnostics/state_dict vs the historical class). This is the neural parity that gates reproduction.

## 3. Slots-only trained arm — S (window + incubated slots, **no Phase**)
The decisive Phase-independent learning test.
- **3-seed (seeds 0–2):** `PROVISIONALLY_SUPPORTED` — S−A = +0.161, all 3 formed, causal, structural.
  H4 (Phase-independence) = YES.
- **5-seed holdout (seeds 3–7):** **`PARTIALLY_STABLE` → `NOT_READY_FOR_KDA_VALIDATION`.** Only
  **3/5 formed** (0.000/0.283/0.408/0.075/0.042) — below the pre-registered ≥4/5 bar. Every other gate
  passes (causal collapse on all forming seeds; PPL S 117.8 < A+ 139.8; S beats A+; distance-robust),
  so the effect is real and causal *when it forms* but **formation is unreliable (~60%)**. Failed
  seeds are not distinguishable by slot diagnostics → optimization/init sensitivity. Next step:
  failure analysis, NOT KDA. (See the five-seed validation report.)

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
