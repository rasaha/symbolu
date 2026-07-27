# Constrained Enterprise Output Mapping + Duplicate-Noise Hardening — Report

**Decisive question:** can the system translate correct, traceable quadratic evidence findings into
the correct bounded enterprise outcome using transparent constraints, while preserving abstention,
provenance, access control, and the smallest sufficient evidence set?

**Answer:** the **contract/mapper is exact** (oracle over true typed fields = 1.00, mapping error
0.00) and the constrained mapper **eliminates mapping errors** — but it does **not** lift final
accuracy by the ≥0.10 bar, because the true remaining bottleneck is **structured-field prediction**,
not mapping. Frozen slot/quadratic baseline verified (commit `299f5ba`, FREEZE OK, 9/9).

## Results (held-out, streaming)

| mapper | K=4 | K=8 | K=16 | map-err (K=4) |
|---|---:|---:|---:|---:|
| O0 learned latent (baseline) | 0.570 | 0.78 | 0.82 | 0.195 |
| **O1 deterministic contract** | 0.543 | **0.80** | **0.85** | **0.000** |
| O2 constrained + gates | 0.543 | 0.79 | 0.85 | 0.000 |
| O3 learned over typed fields | 0.583 | — | — | 0.184 |
| O4 hybrid (gates + ranking) | 0.533 | — | — | 0.184 |
| **O5 oracle (true fields)** | **1.000** | **1.00** | **1.00** | 0.000 |

Dev ≈ 0.74–0.78; held-out ≈ 0.54–0.85 by K. Structured field accuracy (held-out) = **0.45 at K=4**.
Integrity: evidence-ID preservation **1.0**, unauthorized inclusion **0.0** for every arm.

## What this shows

1. **The outcome contract is exact.** O5 (deterministic `decide` over the TRUE typed fields) = 1.00
   with 0.00 mapping error. The mapper is not the problem.
2. **The constrained mapper removes mapping error** (O1/O2 map-err 0.195 → 0.000, a 100% reduction)
   and is fully transparent/auditable — but its accuracy tracks field-prediction quality.
3. **The bottleneck is field prediction.** The causal control is decisive: O1 on *predicted* fields
   = 0.565 vs O1 on *true* fields = **1.000**. All the loss is evidence→typed-field prediction
   (field_acc 0.45), which the deterministic mapper cannot fix.
4. **K=4 is too small for the outcome contract.** Unlike the role task (2 records, K=4 best), the
   outcome needs budget + policy + approval + conflict (~4–5 records), so field accuracy — and O1/O2
   accuracy — *rise* with K (O1 0.54→0.80→0.85). O1/O2 beat O0 at K≥8.

## §14 acceptance (thresholds fixed in advance)

| criterion | required | actual | pass |
|---|---|---:|---|
| final-accuracy gain over O0 | ≥ 0.10 | +0.03 (K16) / −0.03 (K4) | ❌ |
| mapping-error reduction | ≥ 50% | **100%** (0.195→0.000) | ✅ |
| abstention precision preserved | — | yes | ✅ |
| conflict F1 ≥ 0.90 | — | 0.37 (K4, field-limited) | ❌ |
| evidence-ID preservation 1.0 | — | 1.0 | ✅ |
| unauthorized inclusion 0 | — | 0.0 | ✅ |
| generalizes (dev≈held-out) | — | field-limited at K4 | ❌ |
| K ≤ 8 | — | yes | ✅ |

**VALIDATED: NO** — but the failures are all downstream of field prediction, not the mapper.

## §16 final verdict

- **Frozen slot/Quadratic baseline:** verified.
- **Structured reasoning contract:** validated (O5 = 1.00, mapping error 0.00).
- **Output-mapping rescue:** unsupported *as an accuracy lever* — it eliminates mapping error (100%)
  and is the correct transparent design, but accuracy is capped by field prediction, not mapping.
- **Best mapper:** O1 (deterministic contract; zero mapping error; ≥ O0 at K ≥ 8; fully auditable).
- **Output-mapping failure reduction:** 100% (map-err 0.195 → 0.000).
- **Final accuracy improvement:** −0.03 (K4) to +0.03 (K16) — below the 0.10 bar.
- **Abstention integrity:** validated.
- **Duplicate-noise hardening:** implemented and correct (explicit equivalence classifies pairs;
  collapses only EXACT/SOURCE_REDUNDANT; never active/stale/conflict/version/qualifier/validity
  pairs — tests pass), but not an accuracy lever on top of the frozen admission-time dedup here →
  unsupported as a metric mover.
- **Best slot capacity:** for the OUTCOME contract, K ≥ 8 (K=4 insufficient — richer evidence need
  than the role task); still bounded and ≤ 8 at the acceptance bar.
- **Typed fields vs latent:** equivalent at K=4; typed (O1) > latent (O0) at K ≥ 8.
- **Evidence-ID preservation:** 1.0. **Unauthorized inclusion:** 0.0.
- **Primary remaining bottleneck:** **structured reasoning** — evidence → typed structured fields
  (field_acc 0.45). This is the target of the next phase.
- **Authorized architecture:** evidence ledger → deterministic joins → P5 shared binding slots →
  bounded full slot-to-slot quadratic → typed structured findings → deterministic hard gates →
  constrained enterprise outcome.

Frozen Phase untouched (not used in any arm).
