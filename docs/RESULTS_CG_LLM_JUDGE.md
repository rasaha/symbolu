# Conscious Generation — Weak LLM-Judge Evaluation RESULTS

Harness: `scripts/conscious_generation_training/llm_judge_eval.py` (doc:
`docs/CG_TRAINING_LLM_JUDGE_EVAL.md`). **LLM-judge labels are WEAK screening labels
(`llm_judge_weak_label`), not human labels, and do not validate Conscious Generation training.** The
deterministic rubric and the Phase-3 audit remain authoritative.

## Run configuration (pod, A100-80GB)
- Real SFT split rebuilt from `robustness_eval_v2.json`: n=78, train/val/test = 51/7/20
  (`source = self_distilled_wrapper_passing_framed_answers`).
- QLoRA retrained (Mistral-7B-Instruct-v0.3, 3 epochs). **Underpowered:** 51 train examples, 3 optimizer
  steps, final train_loss ≈ 2.22 — a lightly-tuned adapter. n_test = 20.
- Four-arm generation (A=base, B=base+wrapper, C=LoRA, D=LoRA+wrapper), bf16, answers cached.
- Judges: **Llama 3.1 + Qwen 2.5** via Ollama, forced-JSON output (`format=json`).

## Result 1 — Deterministic four-arm (AUTHORITATIVE): `CG_TRAINING_WRAPPER_STILL_BEST`
| metric | A base | B base+wrap | C LoRA | D LoRA+wrap |
|---|---|---|---|---|
| primary_frame_correct | 0.80 | **0.90** | 0.90 | **0.60** |
| rejected_domain_avoidance | 0.95 | **1.00** | 0.95 | **0.65** |
| factuality_preserved | 1.00 | 1.00 | 1.00 | 0.80 |
| must_include_recall | 0.25 | 0.40 | 0.30 | 0.20 |
| generalization_to_unseen_terms | 0.80 | 0.90 | 0.90 | 0.60 |

- **B (base + wrapper) is best.** ΔPFC C−B = 0.0 (CI [−0.15, 0.15], crosses zero): training does **not**
  beat the wrapper. `c_beats_a = False`.
- **D (LoRA + wrapper) collapses** (PFC 0.60, RDA 0.65): combining the lightly-tuned adapter with the
  wrapper prompt is markedly worse than the wrapper alone — `d_not_worse_than_b = False`. This reproduces
  the D-arm collapse flagged in the earlier T1.

## Result 2 — LLM-judge screen (WEAK): `CG_LLM_JUDGE_AGREEMENT_ACCEPTABLE`
- 80 rows (20×4 arms); **invalid_json_rate = 0.0** (forced-JSON fix; was 0.139 for single Llama before).
- Inter-judge agreement: avg 0.959; Cohen κ on discriminative fields — primary_frame_correct 0.75,
  rejected_domain_leak 0.71, answer_acceptable 0.75, rewrite_needed 0.75 (κ≈0 on near-constant fields).
  Numeric: recall Pearson 0.78, clarity Pearson 0.74.

Per-arm judge-estimated screen:
| arm | frame_correct | rejected_leak | rewrite_needed | acceptable | mean_clarity | mean_recall |
|---|---|---|---|---|---|---|
| A | 0.825 | 0.150 | 0.175 | 0.825 | 4.20 | 0.818 |
| B | 1.000 | 0.000 | 0.000 | 1.000 | 4.60 | 0.940 |
| C | 0.850 | 0.125 | 0.150 | 0.850 | 4.325 | 0.875 |
| D | 1.000 | 0.000 | 0.000 | 1.000 | 4.625 | 0.965 |

## Result 3 — Cross-check (the key lesson): the weak judge MISSES the D-arm collapse
| arm | rubric PFC (authoritative) | judge frame_correct | |
|---|---|---|---|
| A | 0.80 | 0.825 | agree |
| B | 0.90 | 1.00 | ≈ agree |
| C | 0.90 | 0.85 | agree |
| **D** | **0.60** | **1.00** | **judge blind to collapse** |

The deterministic rubric catches D's frame breakage (PFC 0.60, rejected-domain leak ~0.35); the LLM judges
rate D as flawless (frame 1.0, leak 0.0, acceptable 1.0). The judge corroborates the rubric on A/B/C but is
**blind to the single most important failure mode** — a concrete demonstration of the fluency/format bias
documented in `CG_TRAINING_LLM_JUDGE_EVAL.md` §8. The judge would have given D a falsely clean bill of
health. This is exactly why the LLM judge is a *screen*, not a validator.

## Earlier calibration vs Phase-3 audit (corroboration)
On the 72-row Phase-3 audit set (real judges): single Llama 3.1 reached agreement_with_audit **0.797** on
its valid subset (stricter than the audit on 7 items, never more lenient); Llama+Qwen →
`CG_LLM_JUDGE_AGREEMENT_ACCEPTABLE`. So the judges track the deterministic audit on bulk items while still
missing structured failures like the D collapse.

## Honest limits
- **Underpowered training:** 51 train examples / 3 steps / loss 2.22; n_test 20. Treat C/D magnitudes as
  weak; the durable signals are (a) C does not beat B, (b) D < B (collapse).
- **Judge agreement ≠ judge correctness:** Llama and Qwen agreeing means they share priors (incl. fluency
  bias), not that they are right — proven by both missing the D collapse.
- **No circularity:** Mistral was not trained on judge labels; judges only scored, never overrode the
  rubric or audit.

## Conclusion
`CG_TRAINING_WRAPPER_STILL_BEST` stands on the authoritative deterministic rubric, with a notable negative
(D-arm collapse: LoRA + wrapper worse than wrapper alone). The weak LLM-judge harness is implemented,
runs cleanly on real four-arm generations (0.0 invalid JSON, two-family agreement ACCEPTABLE), and is
useful for gross screening — but it **failed to detect the D-arm collapse**, confirming it cannot by
itself validate training. **Strong validation still requires human labels or a human-calibrated subset.**
