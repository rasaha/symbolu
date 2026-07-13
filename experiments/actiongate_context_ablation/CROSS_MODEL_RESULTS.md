# CROSS_MODEL_RESULTS — ActionGate Context Minimization replication

> Measured claims only. The Qwen2.5-7B primary run is frozen evidence; other models run the IDENTICAL frozen benchmark (same compressor, prompts, budgets, scoring — verified by fingerprint). No fabricated results: models that did not run are listed as pending.

**Replication verdict: `CONSISTENT_REPLICATION`**  (3/3 real models replicate the hypothesis)

- Real models measured: **3** — Mistral-7B-Instruct-v0.3, Qwen2.5-14B-Instruct, Qwen2.5-7B-Instruct.
- Pending (not yet run): meta-llama/Llama-3.1-8B-Instruct, google/gemma-2-9b-it.

## 1 · Protected vs original — task delta (utility non-regression)

| model | task delta (protected − original) | 95% CI | real |
|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 4.4% | — | True |
| Qwen2.5-14B-Instruct | 2.1% | — | True |
| Qwen2.5-7B-Instruct | 1.6% | — | True |

## 2 · Decision preservation — protected vs protection-unaware

| model | budget | protected | protection-unaware |
|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 20% | 100.0% | 98.7% |
| Mistral-7B-Instruct-v0.3 | 30% | 100.0% | 98.7% |
| Mistral-7B-Instruct-v0.3 | 40% | 100.0% | 97.4% |
| Qwen2.5-14B-Instruct | 20% | 100.0% | 98.7% |
| Qwen2.5-14B-Instruct | 30% | 100.0% | 98.7% |
| Qwen2.5-14B-Instruct | 40% | 100.0% | 97.4% |
| Qwen2.5-7B-Instruct | 20% | 100.0% | 98.7% |
| Qwen2.5-7B-Instruct | 30% | 100.0% | 98.7% |
| Qwen2.5-7B-Instruct | 40% | 100.0% | 97.4% |

## 3 · Cost vs accuracy (protected)

| model | budget | token↓ | cost $ | task acc |
|---|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 20% | 31.9% | 0.0563 | 48.3% |
| Mistral-7B-Instruct-v0.3 | 30% | 45.6% | 0.0533 | 48.3% |
| Mistral-7B-Instruct-v0.3 | 40% | 50.4% | 0.0522 | 48.1% |
| Qwen2.5-14B-Instruct | 20% | 31.9% | 0.0492 | 58.8% |
| Qwen2.5-14B-Instruct | 30% | 45.6% | 0.0466 | 58.1% |
| Qwen2.5-14B-Instruct | 40% | 50.4% | 0.0458 | 58.7% |
| Qwen2.5-7B-Instruct | 20% | 31.9% | 0.0410 | 55.0% |
| Qwen2.5-7B-Instruct | 30% | 45.6% | 0.0393 | 55.5% |
| Qwen2.5-7B-Instruct | 40% | 50.4% | 0.0385 | 55.4% |

## 4 · Architecture sensitivity

- Task-delta spread across real models: 2.8% (small ⇒ architecture-insensitive).
| model | task delta | 95% CI |
|---|---|---|
| Qwen2.5-7B-Instruct | 1.6% | — |
| Qwen2.5-14B-Instruct | 2.1% | — |
| Mistral-7B-Instruct-v0.3 | 4.4% | — |

## 5 · Failure taxonomy (real models, from raw records)

| model | hallucination | extraction_miss | summarization_loss | reasoning_degradation | policy_misunderstanding | tool_argument_error | tool_selection_error | decision_flip | records |
|---|---|---|---|---|---|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | no |
| Qwen2.5-14B-Instruct | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | no |
| Qwen2.5-7B-Instruct | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | no |

## Interpretation

Every real model replicates: protected compression preserves 100% of ActionGate decisions with no utility regression, and beats protection-unaware compression. The effect is architecture-general on this corpus.

_All numbers are measured on the frozen benchmark; absolute task accuracy is known to be depressed by three under-specified tasks (operation-enum items absent from context; exact-match extraction) — the load-bearing quantity is the protected−original delta and the protected-vs-unaware decision-preservation gap._
