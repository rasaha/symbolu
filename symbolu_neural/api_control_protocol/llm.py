"""LLM clients for the pilot.

Two backends:

- ``anthropic`` : a REAL call to the Messages API. Requires ANTHROPIC_API_KEY.
                  This is the ONLY backend that can answer the actual question
                  (does a real LLM follow a Symbol-U JSON packet better than NL?).
                  Not available in this sandbox (no API key), but wired and ready.

- ``mock``      : a deterministic offline instruction-follower SIMULATOR. It keys
                  ONLY on plain-English tone words found in the control message and
                  emits a templated sentence in that tone; it does NOT interpret
                  Sanskrit ontology terms.

  *** IMPORTANT: the mock ENCODES THE NULL HYPOTHESIS BY ASSUMPTION ***
  (i.e. "a model follows English tone words, not the ontology"). It therefore
  PROVES NOTHING about the hypothesis — it only exercises the pipeline and the
  metric code. Whether a real LLM understands `guna: sattva` is exactly the
  empirical question the mock cannot settle. Treat mock numbers as plumbing only.
"""
from __future__ import annotations

import os
from typing import Optional

from .ontology import AXES, TONE_LEXICON

_TEMPLATES = {
    "calm": "Let us take this gently and clearly, one grounded step at a time.",
    "active": "Right, let's move fast and hit the key points with real momentum now.",
    "heavy": "This sits with a slow, solemn weight that we must consider gravely.",
    "neutral": "Here is a straightforward response to the question as asked.",
}


class MockLLM:
    backend = "mock"
    is_real = False

    def generate(self, control: str, prompt: str, seed: int = 0) -> str:
        text = control.lower()
        hits = {a: sum(1 for w in TONE_LEXICON[a] if w in text) for a in AXES}
        best = max(hits, key=hits.get)
        tone = best if hits[best] > 0 else "neutral"
        return _TEMPLATES[tone]


class AnthropicLLM:
    backend = "anthropic"
    is_real = True

    def __init__(self, model: str = "claude-haiku-4-5-20251001", max_tokens: int = 256):
        self.model = model
        self.max_tokens = max_tokens
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — the real-LLM arm cannot run here. "
                "Set it on a machine with API access (see report §commands).")

    def generate(self, control: str, prompt: str, seed: int = 0) -> str:
        import json
        import urllib.request

        base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        user = (control + "\n\n" + prompt) if control else prompt
        body = json.dumps({
            "model": self.model, "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            f"{base}/v1/messages", data=body, method="POST",
            headers={"content-type": "application/json",
                     "anthropic-version": "2023-06-01", "x-api-key": self.key})
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read())
        return "".join(b.get("text", "") for b in out.get("content", []))


class MistralLLM:
    """Real call to Mistral's chat-completions API. Requires MISTRAL_API_KEY.

    Mistral models are generation-only over the API (no hidden states), so this
    powers the external-control-protocol and rerank/refine paths — not the
    internal-neural adapter (which needs open weights run locally).
    Base URL overridable via MISTRAL_BASE_URL (also works for any OpenAI-compatible
    endpoint: vLLM / Ollama / Together / LM Studio — just set base + key + model).
    """

    backend = "mistral"
    is_real = True

    def __init__(self, model: str = "mistral-small-latest", max_tokens: int = 256):
        self.model = model
        self.max_tokens = max_tokens
        self.key = os.environ.get("MISTRAL_API_KEY")
        self.base = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai")
        if not self.key:
            raise RuntimeError(
                "MISTRAL_API_KEY not set — the real-LLM arm cannot run here. "
                "Set it on a machine with Mistral API access (see report §commands).")

    def generate(self, control: str, prompt: str, seed: int = 0) -> str:
        import json
        import urllib.request

        user = (control + "\n\n" + prompt) if control else prompt
        body = json.dumps({
            "model": self.model, "max_tokens": self.max_tokens, "temperature": 0.7,
            "messages": [{"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            f"{self.base}/v1/chat/completions", data=body, method="POST",
            headers={"content-type": "application/json",
                     "Authorization": f"Bearer {self.key}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read())
        return out["choices"][0]["message"]["content"]


def get_llm(backend: str = "mock", model: Optional[str] = None):
    if backend == "mock":
        return MockLLM()
    if backend == "anthropic":
        return AnthropicLLM(model or "claude-haiku-4-5-20251001")
    if backend == "mistral":
        return MistralLLM(model or "mistral-small-latest")
    raise ValueError(f"unknown llm backend {backend!r}")
