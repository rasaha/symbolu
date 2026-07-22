#!/usr/bin/env python3
"""Provider-agnostic chat client for the live naming evaluation. Stdlib only (urllib), honours the
environment's HTTPS proxy + CA bundle. Deterministic decoding by default (temperature 0).

Supported model specs ("provider:model"):
  mistral:mistral-large-latest        env MISTRAL_API_KEY
  qwen:qwen-max                       env DASHSCOPE_API_KEY  (DashScope OpenAI-compatible, international)
  qwen:qwen2.5-72b-instruct           "
  openai:gpt-4o-mini                  env OPENAI_API_KEY
  anthropic:claude-opus-4-8           env ANTHROPIC_API_KEY
  compat:<model>                      env LLM_BASE_URL + LLM_API_KEY  (OpenRouter/Together/vLLM/Ollama/…)

`compat` covers any OpenAI-compatible /chat/completions endpoint, e.g.:
  LLM_BASE_URL=https://openrouter.ai/api/v1  LLM_API_KEY=sk-...  compat:qwen/qwen-2.5-72b-instruct
  LLM_BASE_URL=http://localhost:11434/v1     LLM_API_KEY=ollama  compat:qwen2.5:7b
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request

_CA = "/root/.ccr/ca-bundle.crt"


class LLMError(RuntimeError):
    pass


def _ctx():
    ctx = ssl.create_default_context()
    if os.path.exists(_CA):
        ctx.load_verify_locations(_CA)
    return ctx


def _opener():
    handlers = []
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
    handlers.append(urllib.request.HTTPSHandler(context=_ctx()))
    return urllib.request.build_opener(*handlers)


def _post(url, headers, body, timeout=120, retries=4):
    data = json.dumps(body).encode("utf-8")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with _opener().open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            last = LLMError(f"HTTP {e.code}: {detail}")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt); continue
            raise last
        except Exception as e:  # noqa: BLE001
            last = LLMError(str(e))
            if attempt < retries - 1:
                time.sleep(2 ** attempt); continue
            raise last
    raise last or LLMError("request failed")


# ---- provider registry ----------------------------------------------------------------------------
def _openai_compatible(base_url, api_key, model, prompt, temperature, max_tokens, extra_headers=None):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature, "max_tokens": max_tokens}
    out = _post(url, headers, body)
    text = out["choices"][0]["message"]["content"]
    usage = out.get("usage", {})
    return text, {"prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens")}


def _anthropic(model, prompt, temperature, max_tokens):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]}
    out = _post("https://api.anthropic.com/v1/messages", headers, body)
    text = out["content"][0]["text"]
    usage = out.get("usage", {})
    return text, {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens")}


def chat(model_spec, prompt, temperature=0.0, max_tokens=512):
    """Return (text, usage_dict). Raises LLMError on misconfiguration/failure — never fabricates."""
    provider, _, model = model_spec.partition(":")
    if provider == "mistral":
        key = os.environ.get("MISTRAL_API_KEY")
        if not key:
            raise LLMError("MISTRAL_API_KEY not set")
        return _openai_compatible("https://api.mistral.ai/v1", key, model or "mistral-large-latest",
                                  prompt, temperature, max_tokens)
    if provider == "qwen":
        key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
        if not key:
            raise LLMError("DASHSCOPE_API_KEY (or QWEN_API_KEY) not set")
        base = os.environ.get("DASHSCOPE_BASE_URL",
                              "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
        return _openai_compatible(base, key, model or "qwen-max", prompt, temperature, max_tokens)
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMError("OPENAI_API_KEY not set")
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return _openai_compatible(base, key, model or "gpt-4o-mini", prompt, temperature, max_tokens)
    if provider == "anthropic":
        return _anthropic(model or "claude-opus-4-8", prompt, temperature, max_tokens)
    if provider == "compat":
        base = os.environ.get("LLM_BASE_URL")
        key = os.environ.get("LLM_API_KEY", "x")
        if not base:
            raise LLMError("compat: set LLM_BASE_URL (and LLM_API_KEY)")
        return _openai_compatible(base, key, model or os.environ.get("LLM_MODEL", ""),
                                  prompt, temperature, max_tokens)
    raise LLMError(f"unknown provider {provider!r} in model spec {model_spec!r}")


def available_specs():
    """Model specs whose credentials are present in the environment (for auto-selection / diagnostics)."""
    specs = []
    if os.environ.get("MISTRAL_API_KEY"):
        specs.append("mistral:" + os.environ.get("MISTRAL_MODEL", "mistral-large-latest"))
    if os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"):
        specs.append("qwen:" + os.environ.get("QWEN_MODEL", "qwen-max"))
    if os.environ.get("OPENAI_API_KEY"):
        specs.append("openai:" + os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    if os.environ.get("LLM_BASE_URL"):
        specs.append("compat:" + os.environ.get("LLM_MODEL", ""))
    if os.environ.get("ANTHROPIC_API_KEY"):
        specs.append("anthropic:" + os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8"))
    return specs


if __name__ == "__main__":
    import sys
    specs = available_specs()
    print("configured model specs:", specs or "(none — set MISTRAL_API_KEY / DASHSCOPE_API_KEY / "
          "OPENAI_API_KEY / LLM_BASE_URL / ANTHROPIC_API_KEY)")
    if specs and len(sys.argv) > 1 and sys.argv[1] == "--ping":
        text, usage = chat(specs[0], "Reply with exactly one word: PONG", max_tokens=8)
        print(f"ping {specs[0]} -> {text!r}  usage={usage}")
