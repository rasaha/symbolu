# REAL_LLM_RESULTS — Real-LLM validation of ActionGate Context Minimization

> ## ⚠️ NO REAL LLM AVAILABLE — RESULTS DEFERRED, NOT FABRICATED

> No runnable open-weight LLM in this environment: transformers/torch not installed, HuggingFace is policy-blocked (403 CONNECT), and no ANTHROPIC_API_KEY/OPENAI_API_KEY is set. Harness is ready; results deferred.

> The harness below is complete and model-agnostic; it runs unchanged the instant a local open-weight model (transformers) or an API key is provided. The numbers in this run come from a **deterministic reader** (not a language model) and measure only information preservation — an upper bound on real LLM accuracy. They are **non-scientific** and exist solely to validate plumbing.

- Client: `mock_reader(deterministic, NON-SCIENTIFIC)`  | measured with real LLM: **False**
- **Recommendation: `BLOCKED_NO_MODEL`**
  — `BLOCKED_NO_MODEL`: GO/LIMITED_GO/STOP cannot be honestly emitted without real-LLM evidence. Emitting one would violate the no-fabrication rule.

  - `zero_decision_flips` = True
  - `envelope_preservation_100` = True
  - `task_accuracy_degradation_lt_2pct` = True
  - `worst_task_accuracy_drop` = 0.0
  - `tool_arg_correctness_ge_98pct` = False
  - `measured_with_real_llm` = False

## Method × budget (frozen compressor; DETERMINISTIC READER, non-scientific)

| method | budget | token↓ | decision pres. | envelope pres. | task acc | tool-call | halluc | instr-fail | latency ms | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| original | 0% | 0.0% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0352 |
| structural_only | 0% | 1.4% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0349 |
| protected | 10% | 31.2% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0307 |
| protected | 20% | 31.9% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0306 |
| protected | 30% | 45.6% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0283 |
| protected | 40% | 50.4% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0276 |
| protected | 50% | 62.2% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0257 |
| protected | 60% | 67.1% | 100.0% | 100.0% | 95.7% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0250 |
| protection_unaware | 10% | 31.0% | 98.7% | 100.0% | 95.2% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0307 |
| protection_unaware | 20% | 31.7% | 98.7% | 100.0% | 95.2% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0306 |
| protection_unaware | 30% | 46.2% | 98.7% | 100.0% | 95.2% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0283 |
| protection_unaware | 40% | 51.5% | 97.4% | 100.0% | 95.2% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0275 |
| protection_unaware | 50% | 65.4% | 88.3% | 94.8% | 93.8% | 81.7% | 0.0% | 0.0% | 0.01 | 0.0254 |
| protection_unaware | 60% | 73.8% | 71.4% | 88.3% | 90.8% | 80.7% | 0.0% | 0.0% | 0.01 | 0.0241 |

## Per-task accuracy (protected vs protection-unaware, highest budget)

| task | protected | protection-unaware |
|---|---|---|
| tool_selection | 100.0% | 100.0% |
| tool_argument_generation | 37.5% | 34.4% |
| factual_qa | 100.0% | 91.7% |
| reasoning | 100.0% | 87.0% |
| instruction_following | 100.0% | 100.0% |
| extraction | 100.0% | 95.7% |
| summarization | 100.0% | 89.6% |
| actiongate_envelope_extraction | 100.0% | 100.0% |

## What a real-LLM run will decide

Primary success criteria (evaluated automatically once a real model runs): decision flips = 0, task-accuracy degradation < 2%, tool-arg correctness ≥ 98%, envelope preservation = 100%. On the deterministic reader the structural criteria (decision/envelope preservation) already hold for the protected method at every budget, and the protection-unaware control degrades them at high compression — so the harness demonstrably distinguishes the methods. The **task-quality** criterion is the open question a real LLM must answer.

## To run for real

```python
from actiongate_context_ablation import real_llm_bench as R
from actiongate_context_ablation.llm_client import TransformersLLMClient
res = R.run(TransformersLLMClient('Qwen/Qwen2.5-0.5B-Instruct'))  # or an API client
print(R.render_report_md(res))
```

