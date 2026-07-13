"""Pluggable LLM client layer for the real-LLM validation harness.

The harness is model-agnostic: every model call goes through ``LLMClient.generate``.
Three real backends are provided and are ready to run the instant a model/key is
available — NO harness code changes are needed:

  * TransformersLLMClient — local open-weight model via `transformers` (Qwen/Llama/…).
  * AgenticAPIClient      — wraps the repo's agentic AnthropicAdapter/OpenAIAdapter.
  * MockReaderClient      — a DETERMINISTIC rule-based reader used ONLY to validate
                            the harness plumbing end-to-end. It is NOT a language
                            model; runs using it are explicitly non-scientific.

``probe_available_client()`` reports, honestly, whether a real model is runnable in
the current environment. It never fabricates one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .units import count_tokens


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    is_real: bool          # False for the deterministic reader
    peak_mem_mb: float = 0.0
    throughput_tps: float = 0.0


class TransformersLLMClient:
    """Local open-weight model via HuggingFace transformers (Qwen/Llama/Gemma/Mistral).

    Deployment-correct: applies the tokenizer chat template with add_generation_prompt,
    selects BF16 where supported else FP16 on CUDA, refuses a silent CPU fallback when
    CUDA is requested, runs under inference_mode with greedy decoding (temperature 0),
    decodes only the generated tokens, and reports prompt/generated token counts,
    latency, peak CUDA memory, and throughput. It does not change the logical prompt
    content (system + question) or any scoring."""

    is_real = True

    def __init__(self, model_name: str, max_new_tokens: int = 64, *, dtype: str = "auto",
                 device: str = "cuda", seed: int = 0):
        import torch  # noqa: F401  (raises clearly if absent)
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        torch.manual_seed(seed)
        self.device = device
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable; refusing silent CPU fallback. "
                               "Set DEVICE=cpu explicitly only for non-benchmark debugging.")
        if dtype == "auto":
            if device == "cuda":
                dt = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            else:
                dt = torch.float32
        else:
            dt = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[dtype]
        self.dtype = dt
        self.max_new_tokens = max_new_tokens
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=dt,
                                                          device_map=None)
        if device == "cuda":
            self.model.to("cuda")               # explicit; no accelerate CPU offload
        self.model.eval()
        self.name = f"hf:{model_name}:{str(dt).split('.')[-1]}:{device}"

    def _render(self, system: str, prompt: str) -> str:
        messages = ([{"role": "system", "content": system}] if system else [])
        messages.append({"role": "user", "content": prompt})
        if getattr(self.tok, "chat_template", None):
            return self.tok.apply_chat_template(messages, tokenize=False,
                                                add_generation_prompt=True)
        return (system + "\n\n" + prompt) if system else prompt

    def generate(self, system: str, prompt: str, *, task=None, max_tokens: int = 64) -> LLMResponse:
        torch = self.torch
        text = self._render(system, prompt)
        ids = self.tok(text, return_tensors="pt").to(self.model.device)
        in_len = int(ids["input_ids"].shape[1])
        if self.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        with torch.inference_mode():
            out = self.model.generate(**ids, max_new_tokens=min(max_tokens, self.max_new_tokens),
                                      do_sample=False, num_beams=1,
                                      pad_token_id=(self.tok.pad_token_id or self.tok.eos_token_id))
        dt = (time.perf_counter() - t0) * 1000.0
        gen_ids = out[0][in_len:]
        n_gen = int(gen_ids.shape[0])
        gen = self.tok.decode(gen_ids, skip_special_tokens=True)
        peak = (torch.cuda.max_memory_allocated() / 1e6) if self.device == "cuda" else 0.0
        tps = (n_gen / (dt / 1000.0)) if dt > 0 else 0.0
        return LLMResponse(gen.strip(), in_len, n_gen, dt, True,
                           peak_mem_mb=peak, throughput_tps=tps)


class AgenticAPIClient:
    """Wraps an agentic-framework adapter (AnthropicAdapter / OpenAIAdapter). Requires
    an API key in the environment. Not an open-weight model, but a real LLM for
    completeness."""

    is_real = True

    def __init__(self, adapter):
        self.adapter = adapter
        self.name = f"api:{type(adapter).__name__}"

    def generate(self, system: str, prompt: str, *, task=None, max_tokens: int = 64) -> LLMResponse:
        t0 = time.perf_counter()
        try:
            text = self.adapter.call(prompt, system=system)  # type: ignore[call-arg]
        except TypeError:
            text = self.adapter(prompt)
        dt = (time.perf_counter() - t0) * 1000.0
        usage = getattr(self.adapter, "get_last_usage", lambda: None)() or {}
        pt = int(usage.get("input_tokens", count_tokens(system + prompt)))
        ct = int(usage.get("output_tokens", count_tokens(str(text))))
        return LLMResponse(str(text).strip(), pt, ct, dt, True)


class MockReaderClient:
    """DETERMINISTIC rule-based reader — validates harness plumbing, NOT a model.

    It answers a task only from information present in the provided (possibly
    compressed) prompt: each task carries an ``answer_key`` (the exact answer) and an
    ``answer_span`` (the text that must be present for the answer to be recoverable).
    The reader returns the answer iff that span survives in the prompt, else a refusal.
    So its 'accuracy' equals information preservation — an UPPER BOUND on a real LLM,
    and explicitly non-scientific."""

    is_real = False
    name = "mock_reader(deterministic, NON-SCIENTIFIC)"

    def generate(self, system: str, prompt: str, *, task=None, max_tokens: int = 64) -> LLMResponse:
        t0 = time.perf_counter()
        if task is None:
            ans = ""
        else:
            span = (task.get("answer_span") or "").strip()
            present = bool(span) and span.lower() in prompt.lower()
            ans = task.get("answer_key", "") if present else "INSUFFICIENT_CONTEXT"
        dt = (time.perf_counter() - t0) * 1000.0
        return LLMResponse(ans, count_tokens(system + prompt), count_tokens(ans), dt, False)


@dataclass
class Availability:
    real_available: bool
    reason: str
    tried: dict


def probe_available_client():
    """Return (client, Availability). Tries real backends, falls back to the
    deterministic reader with an honest 'not available' reason. Never fabricates."""
    import os
    tried = {}
    # 1) local transformers model
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        tried["transformers"] = "installed"
        # even if installed, weights must be reachable; caller can construct explicitly
    except Exception as e:
        tried["transformers"] = f"missing: {e.__class__.__name__}"
    # 2) API keys
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        tried[k] = "set" if os.environ.get(k) else "unset"
    real = (tried.get("transformers") == "installed") or any(
        tried.get(k) == "set" for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"))
    if not real:
        reason = ("No runnable open-weight LLM in this environment: transformers/torch "
                  "not installed, HuggingFace is policy-blocked (403 CONNECT), and no "
                  "ANTHROPIC_API_KEY/OPENAI_API_KEY is set. Harness is ready; results deferred.")
        return MockReaderClient(), Availability(False, reason, tried)
    return MockReaderClient(), Availability(
        True, "A real backend appears available; construct it explicitly to run.", tried)
