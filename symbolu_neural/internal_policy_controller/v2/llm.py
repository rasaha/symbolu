"""Self-contained LLM client for v2: anthropic / mistral (real) + mock (plumbing).

The mock is a deterministic stand-in so the harness runs with no API. It CANNOT
rewrite under a policy or judge quality, so mock runs yield NO scientific verdict
(the pilot enforces this). Real backends require ANTHROPIC_API_KEY / MISTRAL_API_KEY
(absent in this sandbox).
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional


class MockLLM:
    backend = "mock"
    is_real = False

    def chat(self, system: str, user: str, seed: int = 0) -> str:
        # deterministic, content-free: enough to exercise the pipeline only
        if "Rate" in system or "judge" in system.lower():
            return json.dumps({k: 3 for k in
                               ["clarity", "directness", "usefulness", "caution",
                                "speculation_reduction", "escalation_reduction",
                                "completeness", "meaning_preservation", "fluency"]} |
                              {"prefer_final": False})
        return f"[mock answer to: {user[:60]}]"


class _HTTPLLM:
    is_real = True

    def __init__(self, model, max_tokens=512):
        self.model, self.max_tokens = model, max_tokens

    def chat(self, system: str, user: str, seed: int = 0) -> str:
        raise NotImplementedError


class AnthropicLLM(_HTTPLLM):
    backend = "anthropic"

    def __init__(self, model="claude-haiku-4-5-20251001", max_tokens=512):
        super().__init__(model, max_tokens)
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — real run unavailable here.")

    def chat(self, system, user, seed=0):
        base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        body = json.dumps({"model": self.model, "max_tokens": self.max_tokens,
                           "system": system,
                           "messages": [{"role": "user", "content": user}]}).encode()
        req = urllib.request.Request(f"{base}/v1/messages", data=body, method="POST",
                                     headers={"content-type": "application/json",
                                              "anthropic-version": "2023-06-01",
                                              "x-api-key": self.key})
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read())
        return "".join(b.get("text", "") for b in out.get("content", []))


class MistralLLM(_HTTPLLM):
    backend = "mistral"

    def __init__(self, model="mistral-small-latest", max_tokens=512):
        super().__init__(model, max_tokens)
        self.key = os.environ.get("MISTRAL_API_KEY")
        self.base = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai")
        if not self.key:
            raise RuntimeError("MISTRAL_API_KEY not set — real run unavailable here.")

    def chat(self, system, user, seed=0):
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": user}]
        body = json.dumps({"model": self.model, "max_tokens": self.max_tokens,
                           "temperature": 0.7, "messages": msgs}).encode()
        req = urllib.request.Request(f"{self.base}/v1/chat/completions", data=body,
                                     method="POST",
                                     headers={"content-type": "application/json",
                                              "Authorization": f"Bearer {self.key}"})
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read())
        return out["choices"][0]["message"]["content"]


def get_llm(backend: str = "mock", model: Optional[str] = None):
    if backend == "mock":
        return MockLLM()
    if backend == "anthropic":
        return AnthropicLLM(model or "claude-haiku-4-5-20251001")
    if backend == "mistral":
        return MistralLLM(model or "mistral-small-latest")
    raise ValueError(f"unknown backend {backend!r}")
