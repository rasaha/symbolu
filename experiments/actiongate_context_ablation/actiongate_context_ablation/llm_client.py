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


class TransformersLLMClient:
    """Local open-weight model via HuggingFace transformers. Lazy — importing/loading
    only happens on construction, so the harness has no hard dependency."""

    is_real = True

    def __init__(self, model_name: str, max_new_tokens: int = 64):
        import torch  # noqa: F401  (raises clearly if absent)
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.name = f"hf:{model_name}"
        self.max_new_tokens = max_new_tokens
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.eval()

    def generate(self, system: str, prompt: str, *, task=None, max_tokens: int = 64) -> LLMResponse:
        import torch
        text = (system + "\n\n" + prompt) if system else prompt
        ids = self.tok(text, return_tensors="pt")
        t0 = time.perf_counter()
        with torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=min(max_tokens, self.max_new_tokens),
                                      do_sample=False)
        dt = (time.perf_counter() - t0) * 1000.0
        gen = self.tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        return LLMResponse(gen.strip(), int(ids["input_ids"].shape[1]),
                           int(out.shape[1] - ids["input_ids"].shape[1]), dt, True)


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
