# CROSS_MODEL_RESULTS — ActionGate Context Minimization replication

> Measured claims only. The Qwen2.5-7B primary run is frozen evidence; other models run the IDENTICAL frozen benchmark (same compressor, prompts, budgets, scoring — verified by fingerprint). No fabricated results: models that did not run are listed as pending.

**Replication verdict: `INSUFFICIENT_MODELS`**  (1/1 real models replicate the hypothesis)

> Only one real model has run so far (Qwen2.5-7B). Cross-model replication requires ≥2 real models; run the pending models on RunPod to complete it.

- Real models measured: **1** — Qwen2.5-7B-Instruct.
- Pending (not yet run): Qwen/Qwen2.5-14B-Instruct, meta-llama/Llama-3.1-8B-Instruct, google/gemma-2-9b-it, mistralai/Mistral-7B-Instruct-v0.3.

## 1 · Protected vs original — task delta (utility non-regression)

| model | task delta (protected − original) | 95% CI | real |
|---|---|---|---|
| Qwen2.5-7B-Instruct | 1.6% | — | True |

## 2 · Decision preservation — protected vs protection-unaware

| model | budget | protected | protection-unaware |
|---|---|---|---|
| Qwen2.5-7B-Instruct | 20% | 100.0% | 98.7% |
| Qwen2.5-7B-Instruct | 30% | 100.0% | 98.7% |
| Qwen2.5-7B-Instruct | 40% | 100.0% | 97.4% |

## 3 · Cost vs accuracy (protected)

| model | budget | token↓ | cost $ | task acc |
|---|---|---|---|---|
| Qwen2.5-7B-Instruct | 20% | 31.9% | 0.0410 | 55.0% |
| Qwen2.5-7B-Instruct | 30% | 45.6% | 0.0393 | 55.5% |
| Qwen2.5-7B-Instruct | 40% | 50.4% | 0.0385 | 55.4% |

## 4 · Architecture sensitivity

- Task-delta spread across real models: — (small ⇒ architecture-insensitive).
| model | task delta | 95% CI |
|---|---|---|
| Qwen2.5-7B-Instruct | 1.6% | — |

## 5 · Failure taxonomy (real models, from raw records)

| model | hallucination | extraction_miss | summarization_loss | reasoning_degradation | policy_misunderstanding | tool_argument_error | tool_selection_error | decision_flip | records |
|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-7B-Instruct | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | no |

## Interpretation

One real model (Qwen2.5-7B) shows protected compression preserving decisions and utility while protection-unaware degrades decisions. This is consistent with the hypothesis but is a single architecture — cross-model replication is **pending** the other models. No cross-model claim is made yet.

_All numbers are measured on the frozen benchmark; absolute task accuracy is known to be depressed by three under-specified tasks (operation-enum items absent from context; exact-match extraction) — the load-bearing quantity is the protected−original delta and the protected-vs-unaware decision-preservation gap._
