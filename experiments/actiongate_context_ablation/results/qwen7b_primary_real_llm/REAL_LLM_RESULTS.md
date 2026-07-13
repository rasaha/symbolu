# REAL_LLM_RESULTS — Real-LLM validation of ActionGate Context Minimization

- Client: `durable-run`  | measured with real LLM: **True**
- **Recommendation: `GO`**
  - `zero_decision_flips` = True
  - `envelope_preservation_100` = True
  - `task_accuracy_degradation_lt_2pct` = True
  - `worst_task_accuracy_drop` = -0.01298185941043084
  - `tool_arg_correctness_ge_98pct` = True
  - `measured_with_real_llm` = True

## Method × budget (frozen compressor; durable-run)

| method | budget | token↓ | decision pres. | envelope pres. | task acc | tool-call | halluc | instr-fail | latency ms | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| original | 0% | 0.0% | 100.0% | 100.0% | 53.7% | 98.2% | 0.0% | 100.0% | 2115.45 | 0.0488 |
| protected | 20% | 31.9% | 100.0% | 100.0% | 55.0% | 100.0% | 0.0% | 100.0% | 2018.40 | 0.0410 |
| protected | 30% | 45.6% | 100.0% | 100.0% | 55.5% | 100.0% | 0.0% | 100.0% | 2055.61 | 0.0393 |
| protected | 40% | 50.4% | 100.0% | 100.0% | 55.4% | 100.0% | 0.0% | 100.0% | 2053.93 | 0.0385 |
| protection_unaware | 20% | 31.7% | 98.7% | 100.0% | 54.7% | 100.0% | 0.0% | 100.0% | 1964.18 | 0.0410 |
| protection_unaware | 30% | 46.2% | 98.7% | 100.0% | 55.2% | 100.0% | 0.0% | 100.0% | 2042.63 | 0.0391 |
| protection_unaware | 40% | 51.5% | 97.4% | 100.0% | 54.8% | 100.0% | 0.0% | 100.0% | 2020.71 | 0.0383 |
| structural_only | 0% | 1.4% | 100.0% | 100.0% | 53.6% | 98.2% | 0.0% | 100.0% | 2136.08 | 0.0484 |

## Per-task accuracy (protected vs protection-unaware, highest budget)

| task | protected | protection-unaware |
|---|---|---|
| tool_selection | 100.0% | 100.0% |
| tool_argument_generation | 100.0% | 100.0% |
| factual_qa | 100.0% | 100.0% |
| reasoning | 63.6% | 61.0% |
| instruction_following | 0.0% | 0.0% |
| extraction | 33.0% | 33.0% |
| summarization | 78.8% | 78.8% |
| actiongate_envelope_extraction | 23.4% | 22.5% |

## Provenance

- Model: `Qwen/Qwen2.5-7B-Instruct` revision `a09a35458c702b33eeacc393d103063234e8bc28`
- Code commit: `51284a39740a33eaa03903e1951f7991edafa754`
- Frozen fingerprint: `sha256:ac4e069262ec663de0983c5461c64ad57bb8d62db326e6a6f1701f0628381eac`
- ActionGate policy: `0.1.0-ref:b93b95d182bf796c`
- Records: 3808 (476 per method×budget cell), `n_missing=0`, `n_errors=0`, `is_real=true`.
- Hardware: 1× NVIDIA A100-SXM4-80GB, BF16, greedy decoding, max_new_tokens=64.

_See `README.md` in this folder for the honest interpretation and caveats._
