# CG Wrapper Ablation — Generation Track RESULT (filled)

> Closeout of the generation-quality ablation. Numbers transcribed from
> `runs/cg_wrapper_ablation/20260620T235830Z/summary.json`. This is the **generation** verdict;
> the **representation** question (is the Bhava *value* decodable) is the separate Bhava probe.

## Run metadata
| Field | Value |
|-------|-------|
| Run | `20260620T235830Z` |
| Model | `mistralai/Mistral-7B-v0.3` (bf16, frozen) |
| Checkpoint | `checkpoints_cg_active/best_model.pt` (Active-CG, gate −1.0 + N(0,1e-3)) |
| Arms | A_base, B_full, C_phase_off, D_gate0 (E_csr N/A — no CSR in path) |
| Eval sets | format_constraints (24), gsm8k_style (30), json_format (16) = 70 |
| Decoding | greedy, `MAX_NEW_TOKENS=64`, `SEEDS=0` |
| Wallclock | ~9 min (A100 80GB) |

## Sanity checks
| Check | Result |
|-------|--------|
| **K0** gate0 (D) == base | **PASS** — max\|Δlogit\| = 0.000 |
| **K1** inert? | **no** — wrapper is active (KL=0.025, flip=8.05%, corr/hidden=4.6%) |
| **B≈C** | **YES** — KL(B‖C)=1.07e-04, flip=0.089%, ΔBhava=0 |

## Task accuracy (pass rate per arm)
| Set | A_base | B_full | C_phase_off | D_gate0 |
|-----|--------|--------|-------------|---------|
| format_constraints | 0.083 | 0.083 | 0.083 | 0.083 |
| gsm8k_style† | 0.033 | 0.033 | 0.033 | 0.033 |
| json_format | 0.625 | 0.625 | 0.625 | 0.625 |

† gsm floored by `MAX_NEW_TOKENS=64` (step-by-step truncated); json (full range) is the high-power set.

## Paired (Δ = cand − ref; McNemar p)
| Comparison | format | gsm8k | json |
|-----------|--------|-------|------|
| **B − A** | +0.000 (p=1) | +0.000 (p=1) | +0.000 (p=1) |
| **B − C** | +0.000 (p=1) | +0.000 (p=1) | +0.000 (p=1) |
| **C − A** | +0.000 (p=1) | +0.000 (p=1) | +0.000 (p=1) |

## Diagnostics (vs base)
| Arm | KL | flip | gate | corr/hidden | ΔBhava | adptW |
|-----|----|----|------|-------------|--------|-------|
| B_full | 2.46e-2 | 8.05% | 0.270 | 4.55e-2 | 0 | 22.1 |
| C_phase_off | 2.50e-2 | 7.99% | 0.270 | 4.55e-2 | 0 | 22.1 |
| D_gate0 | 0 | 0 | 0 | 0 | 0 | 22.1 |
| B vs C | 1.07e-4 | 0.089% | — | — | 0 | — |

## DECISION: `ACTIVE_NO_EFFECT` → **PARK the generation wrapper**

The Active-CG wrapper genuinely changes logits (8% token flips, K1 not inert) but produces
**zero** change in any objective task metric (B = A exactly on all three sets, p=1), and its
phase/Bhava **dynamics contribute nothing** beyond a static offset (B≈C: KL=1e-4, ΔBhava=0) — and
that offset itself moves no metric. No benefit, no regression.

This matches the end-to-end prediction:
- **Bootstrap analysis** — ORIGINAL can't bootstrap; Active-CG makes it active, not useful.
- **Audit** — generation consumes ΔBhava, which is ~0 (pooled state) → a constant correction.
- **Ablation (here)** — confirmed: B≈C, ΔBhava=0, zero task effect.

**Action:** stop work on the CG wrapper as a generation modifier. The only remaining question that
could justify any further CG work is the **representation** one (Bhava-value decodability), tested
separately by the Bhava probe — and only a `BHAVA_COMPLEMENTARY/STRONG` there would reopen it.

## Caveat / optional follow-up
gsm was token-capped; a confirmatory pass with `MAX_NEW_TOKENS=128` on json+format would add power,
but `B≈C` and `ΔBhava=0` are structural and won't change the verdict.
