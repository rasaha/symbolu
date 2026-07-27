# Phase v3 — 2×2 transition ablation (γ_t vs ω_t)

State focus Top-1 (3-seed mean), write gate / curriculum / budget / readout matched.

| cell | d64 | d128 | d256 | d512 | d1024 | d2048 | d4096 |
|---|---|---|---|---|---|---|---|
| B (γ=1, ω=0) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.983 |
| B+γ (γ_t, ω=0) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.998 | 0.330 |
| B+ω (γ=1, ω_t) | 1.000 | 1.000 | 0.986 | 0.899 | 0.596 | 0.423 | 0.286 |
| AB (γ_t, ω_t) | 0.995 | 0.952 | 0.819 | 0.609 | 0.438 | 0.383 | 0.380 |
| V2-S (reference) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.938 |

## Transition dynamics at d2048 (3-seed mean)
| cell | eff γ | acc. rotation (turns) | phase align cos | cue retention | state norm |
|---|---:|---:|---:|---:|---:|
| B (γ=1, ω=0) | 1.0000 | 0.0 | +1.00 | 1.000 | 17.9 |
| B+γ (γ_t, ω=0) | 0.9997 | 0.0 | +1.00 | 0.547 | 15.5 |
| B+ω (γ=1, ω_t) | 1.0000 | 380.1 | +0.03 | 1.000 | 28.0 |
| AB (γ_t, ω_t) | 0.9974 | 288.2 | +0.03 | 0.126 | 9.8 |

## Interpretation
**Decision:** Keep V2-S; dynamic retention is unnecessary. Remove token-dependent rotation from persistent memory.

- dynamic_retention_helps (B+γ>B): **False**
- rotation_harmful (B+ω<B): **True**
- rotation_cancels_retention (AB<B+γ): **True**
- retention_adds_no_value (B+γ≤B): **True**
- all_v3_below_V2S: **False**
