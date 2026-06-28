"""Self-contained LLM client for v3: anthropic / mistral (real) + mock (plumbing).

The mock is a deterministic stand-in so the harness runs with no API. It CANNOT
rewrite under a policy or judge quality, so mock runs yield NO scientific verdict
(the pilot enforces this). Real backends require ANTHROPIC_API_KEY / MISTRAL_API_KEY.

Real HTTP calls go through `_post_json`, which adds:
  * a client-side THROTTLE (min interval between requests) so we don't trip the
    provider's rate limit in the first place — the harness fires ~576 calls/seed;
  * exponential-backoff RETRY on 429 / 5xx, honoring the `Retry-After` header.
Tune via env: LLM_MIN_INTERVAL (sec, default 1.1), LLM_MAX_RETRIES (default 6).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional

_RETRY_CODES = {429, 500, 502, 503, 504}
_last_call = [0.0]   # module-level: wall-clock of the previous request (mutable cell)


def _throttle(min_interval: float) -> None:
    if min_interval <= 0:
        return
    wait = min_interval - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def _post_json(url: str, headers: dict, payload: dict,
               timeout: int = 90, min_interval: float = 1.1,
               max_retries: int = 6) -> dict:
    """POST JSON with throttle + exponential-backoff retry on rate-limit / transient
    server errors. Raises the last error if retries are exhausted."""
    min_interval = float(os.environ.get("LLM_MIN_INTERVAL", min_interval))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", max_retries))
    body = json.dumps(payload).encode()
    for attempt in range(max_retries + 1):
        _throttle(min_interval)
        try:
            req = urllib.request.Request(url, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in _RETRY_CODES and attempt < max_retries:
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = (float(ra) if ra and str(ra).strip().replace(".", "", 1).isdigit()
                        else min(2.0 ** attempt, 60.0))
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError:
            if attempt < max_retries:
                time.sleep(min(2.0 ** attempt, 60.0))
                continue
            raise
    raise RuntimeError("unreachable")   # loop either returns or raises


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
    min_interval = 1.1   # seconds between requests (overridable per backend / env)

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
        out = _post_json(
            f"{base}/v1/messages",
            {"content-type": "application/json", "anthropic-version": "2023-06-01",
             "x-api-key": self.key},
            {"model": self.model, "max_tokens": self.max_tokens, "system": system,
             "messages": [{"role": "user", "content": user}]},
            min_interval=self.min_interval)
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
        out = _post_json(
            f"{self.base}/v1/chat/completions",
            {"content-type": "application/json", "Authorization": f"Bearer {self.key}"},
            {"model": self.model, "max_tokens": self.max_tokens,
             "temperature": 0.7, "messages": msgs},
            min_interval=self.min_interval)
        return out["choices"][0]["message"]["content"]


def get_llm(backend: str = "mock", model: Optional[str] = None):
    if backend == "mock":
        return MockLLM()
    if backend == "anthropic":
        return AnthropicLLM(model or "claude-haiku-4-5-20251001")
    if backend == "mistral":
        return MistralLLM(model or "mistral-small-latest")
    raise ValueError(f"unknown backend {backend!r}")
