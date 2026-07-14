#!/usr/bin/env python3
"""Deterministic model backend for RunPod. vLLM offline (preferred) or OpenAI-compatible HTTP endpoint.

No silent substitution: if a requested model family/checkpoint cannot be loaded, availability() returns False and
the runner stops with BLOCKED_REQUIRED_MODEL_UNAVAILABLE.
"""
from __future__ import annotations
import json, hashlib, os

# Preferred pinned checkpoints (closest exact class if these exact revs are unavailable — but same FAMILY only).
QWEN_DEFAULT = "Qwen/Qwen3-32B"
MISTRAL_DEFAULT = "mistralai/Mistral-Small-3.1-24B-Instruct-2503"

def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def has_vllm():
    try:
        import vllm  # noqa
        return True
    except Exception:
        return False

class VLLMBackend:
    """Offline vLLM. Deterministic: temperature=0, fixed seed. One model loaded at a time (isolation)."""
    def __init__(self, model_id, seed, dtype="bfloat16", max_model_len=8192, gpu_mem_util=0.90,
                 tensor_parallel_size=1, quantization=None, qwen_enable_thinking=False, max_tokens=2048):
        from vllm import LLM, SamplingParams
        self.model_id = model_id
        self.seed = seed
        self.qwen_enable_thinking = qwen_enable_thinking
        self.family = "qwen" if "qwen" in model_id.lower() else ("mistral" if "mistral" in model_id.lower() else "other")
        self.llm = LLM(model=model_id, dtype=dtype, seed=seed, max_model_len=max_model_len,
                       gpu_memory_utilization=gpu_mem_util, tensor_parallel_size=tensor_parallel_size,
                       quantization=quantization, trust_remote_code=True)
        self.sp = SamplingParams(temperature=0.0, top_p=1.0, top_k=-1, repetition_penalty=1.0,
                                 seed=seed, max_tokens=max_tokens)
        self.tok = self.llm.get_tokenizer()

    def _render(self, system, user):
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        kw = {}
        if self.family == "qwen":
            kw["enable_thinking"] = self.qwen_enable_thinking  # one fixed Qwen mode for the whole run
        return self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **kw)

    def generate(self, system, user):
        prompt = self._render(system, user)
        out = self.llm.generate([prompt], self.sp)[0].outputs[0].text
        return out, {"prompt_sha256": sha_text(prompt), "output_sha256": sha_text(out)}

class OpenAICompatBackend:
    """For a served vLLM OpenAI-compatible endpoint (base_url + model)."""
    def __init__(self, model_id, base_url, seed, api_key="EMPTY", max_tokens=2048, qwen_enable_thinking=False):
        import requests  # noqa
        self.model_id = model_id; self.base_url = base_url.rstrip("/"); self.seed = seed
        self.api_key = api_key; self.max_tokens = max_tokens
        self.family = "qwen" if "qwen" in model_id.lower() else ("mistral" if "mistral" in model_id.lower() else "other")
        self.qwen_enable_thinking = qwen_enable_thinking

    def generate(self, system, user):
        import requests
        body = {"model": self.model_id, "temperature": 0.0, "top_p": 1.0, "seed": self.seed,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.family == "qwen":
            body["chat_template_kwargs"] = {"enable_thinking": self.qwen_enable_thinking}
        r = requests.post(f"{self.base_url}/chat/completions",
                          headers={"Authorization": f"Bearer {self.api_key}"}, json=body, timeout=600)
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"]
        return out, {"prompt_sha256": sha_text(system + "\x00" + user), "output_sha256": sha_text(out)}

def availability(qwen_id, mistral_id, mode):
    """Return (ok, info). mode in {'vllm','openai'}. Does NOT substitute families."""
    info = {"mode": mode, "qwen_id": qwen_id, "mistral_id": mistral_id}
    if "qwen" not in qwen_id.lower():
        return False, {**info, "reason": "qwen_id not Qwen family — substitution prohibited"}
    if "mistral" not in mistral_id.lower():
        return False, {**info, "reason": "mistral_id not Mistral family — substitution prohibited"}
    if mode == "vllm":
        if not has_vllm():
            return False, {**info, "reason": "vllm not importable (no GPU/backend)"}
        return True, {**info, "reason": "vllm present"}
    if mode == "openai":
        try:
            import requests  # noqa
            return True, {**info, "reason": "openai-compat mode selected"}
        except Exception:
            return False, {**info, "reason": "requests not available"}
    return False, {**info, "reason": f"unknown mode {mode}"}
