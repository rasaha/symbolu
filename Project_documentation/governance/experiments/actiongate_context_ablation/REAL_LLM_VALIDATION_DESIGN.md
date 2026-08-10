# REAL_LLM_VALIDATION_DESIGN

Model-agnostic harness that drives the FROZEN compressor through real downstream
tasks. Nothing here modifies the compressor, detector, extractor, or ActionGate.

## Components

- `llm_client.py` — `LLMClient` interface + `LLMResponse`. Backends:
  - `TransformersLLMClient(model_name)` — local open-weight model via `transformers`
    (Qwen/Llama/Gemma/Mistral). Lazy import; ready to run.
  - `AgenticAPIClient(adapter)` — wraps the repo's agentic AnthropicAdapter/
    OpenAIAdapter (needs an API key).
  - `MockReaderClient` — DETERMINISTIC rule-based reader for plumbing validation
    only (answers iff the answer-bearing span survived). NOT a model; non-scientific.
  - `probe_available_client()` — honest availability check; falls back to the reader
    with a documented reason. Never fabricates a model.
- `llm_tasks.py` — builds tasks per context with ground truth from the frozen gate:
  tool_selection, tool_argument_generation, factual_qa, reasoning,
  instruction_following, extraction, summarization, actiongate_envelope_extraction.
  Each task carries a model-agnostic scorer (exact-match / fact-recall).
- `real_llm_bench.py` — runs {original, structural_only, protected,
  protection_unaware} × budgets × tasks; aggregates all metrics; computes the
  success criteria and the recommendation (`BLOCKED_NO_MODEL` if no real model ran).
- `real_llm_plots.py` — accuracy/decision/cost/latency vs compression; watermarked
  NON-SCIENTIFIC when no real model ran.

## Prompt construction

The LLM prompt is the **action-request header** (tool/verb/target/base args — always
present, it is the action being governed) plus the surviving prose spans (ticket,
justification, evidence, approval, logs) in original order. The compressor removes
only prose spans; the structured request is never compressed away. This is why
structured tasks (tool selection, envelope) are robust across methods, while
prose-dependent tasks (reasoning, factual QA, extraction) are where protection-aware
vs protection-unaware compression diverges.

## Why the methods differ (validated on the deterministic reader)

Even with the non-scientific reader, the harness already shows the expected split at
high compression: the **protected** method holds decision preservation and envelope
preservation at 100% and task accuracy flat, while **protection-unaware** compression
drops decision/envelope preservation and reasoning accuracy — because it removes
decision-relevant prose the protected method keeps. A real LLM is required to confirm
that the *quality* of answers (not just information availability) is preserved.

## Determinism

Task generation and grading are deterministic. Real-model latency and (for real
runs) sampling are the only non-deterministic elements; latency is reported but never
used in an equality/hash check. The deterministic-reader dry run is fully reproducible.

## LLMLingua-2

Not runnable here (requires a HuggingFace model; HF is policy-blocked). The
protection-unaware method is the installed stand-in for protection-blind selection.
Slot the real LLMLingua-2 in as a fifth method when HF access is available.
