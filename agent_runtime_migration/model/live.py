"""Live real-model adapter (env-driven, standard-library HTTP).

Implements the ``LanguageModel`` contract (``generate``/``call``) against a live or
local provider selected by environment variables. Supports:

  * provider="openai"    -> POST {base}/v1/chat/completions   (Bearer key)
  * provider="anthropic" -> POST {base}/v1/messages            (x-api-key)
  * provider="ollama"    -> POST {base}/api/chat               (no auth; local)

**No credentials are stored in code, fixtures, traces, or commits.** The API key is
read from the environment at call time and never logged. If no provider/credentials
are configured, ``build_live_model_from_env`` returns ``None`` and the evaluation
runner reports ``BLOCKED_NO_REAL_MODEL`` — it never fabricates a response.

Decoding is deterministic where the provider allows it: ``temperature=0`` and a
``seed`` when supported. The real model may produce planning/reflection text; it may
NOT produce a trusted risk class, principal, authorization, operational-safety
decision, execution eligibility, or execution reference — all output flows through the
existing typed, fail-closed parser before any CER construction.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class LiveModelConfig:
    provider: str
    model_id: str
    base_url: str
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_s: float = 60.0
    seed: Optional[int] = 7

    @property
    def adapter_version(self) -> str:
        return "live-http-1"


class LiveHTTPModel:
    """A minimal, deterministic HTTP adapter. Credentials come from the environment."""

    def __init__(self, config: LiveModelConfig, api_key_env: Optional[str] = None):
        self._c = config
        self._api_key_env = api_key_env
        self.prompt_log: List[int] = []   # lengths only — never prompt/response content w/ secrets

    def _headers(self) -> dict:
        h = {"content-type": "application/json"}
        key = os.environ.get(self._api_key_env or "", "")
        if self._c.provider == "openai" and key:
            h["authorization"] = f"Bearer {key}"
        elif self._c.provider == "anthropic" and key:
            h["x-api-key"] = key
            h["anthropic-version"] = "2023-06-01"
        return h  # key is used transiently; never logged or returned

    def _endpoint_and_body(self, prompt: str):
        c = self._c
        if c.provider == "openai":
            return (f"{c.base_url}/v1/chat/completions",
                    {"model": c.model_id, "temperature": c.temperature, "seed": c.seed,
                     "max_tokens": c.max_tokens,
                     "messages": [{"role": "user", "content": prompt}]})
        if c.provider == "anthropic":
            return (f"{c.base_url}/v1/messages",
                    {"model": c.model_id, "temperature": c.temperature, "max_tokens": c.max_tokens,
                     "messages": [{"role": "user", "content": prompt}]})
        if c.provider == "ollama":
            return (f"{c.base_url}/api/chat",
                    {"model": c.model_id, "stream": False,
                     "options": {"temperature": c.temperature, "seed": c.seed},
                     "messages": [{"role": "user", "content": prompt}]})
        raise ValueError(f"unsupported provider {c.provider!r}")

    @staticmethod
    def _extract_text(provider: str, obj: dict) -> str:
        if provider == "openai":
            return obj["choices"][0]["message"]["content"]
        if provider == "anthropic":
            return "".join(b.get("text", "") for b in obj.get("content", []) if b.get("type") == "text")
        if provider == "ollama":
            return obj.get("message", {}).get("content", "")
        return ""

    def generate(self, prompt: str) -> str:
        self.prompt_log.append(len(prompt))
        url, body = self._endpoint_and_body(prompt)
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=self._c.timeout_s) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
        return self._extract_text(self._c.provider, obj)

    call = generate


# provider -> (default base url, api-key env var)
_PROVIDER_DEFAULTS = {
    "openai": ("https://api.openai.com", "OPENAI_API_KEY"),
    "anthropic": ("https://api.anthropic.com", "ANTHROPIC_API_KEY"),
    "ollama": ("http://127.0.0.1:11434", None),
}


def build_live_model_from_env() -> Optional[LiveHTTPModel]:
    """Return a live model if the environment configures one AND credentials exist;
    otherwise ``None`` (the caller then reports BLOCKED_NO_REAL_MODEL). Never fabricates."""
    provider = os.environ.get("RUNTIME_MODEL_PROVIDER", "").lower()
    if provider not in _PROVIDER_DEFAULTS:
        return None
    default_base, key_env = _PROVIDER_DEFAULTS[provider]
    if key_env is not None and not os.environ.get(key_env):
        return None  # no credentials -> not available
    model_id = os.environ.get("RUNTIME_MODEL_ID")
    if not model_id:
        return None
    base = os.environ.get("RUNTIME_MODEL_BASE_URL", default_base)
    cfg = LiveModelConfig(
        provider=provider, model_id=model_id, base_url=base,
        temperature=float(os.environ.get("RUNTIME_MODEL_TEMPERATURE", "0")),
        max_tokens=int(os.environ.get("RUNTIME_MODEL_MAX_TOKENS", "1024")),
        timeout_s=float(os.environ.get("RUNTIME_MODEL_TIMEOUT_S", "60")))
    return LiveHTTPModel(cfg, api_key_env=key_env)
