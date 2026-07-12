"""Model adapters for the native word-specificity evaluator run.

Two REAL backends (instantiated only on a model-access host) + a deterministic fake for tests/smoke:
  * "vllm_openai"   — talk to a LOCAL vLLM OpenAI-compatible server the operator launched (real socket timeout;
                      dtype / tensor-parallel / max-model-len / trust-remote-code chosen at server launch);
  * "transformers"  — self-contained local HF load at a frozen revision, bf16/fp16, device_map, trust_remote_code;
  * "fake"          — NO model / NO network; used by tests and the offline smoke.

Records the exact resolved model id + revision + runtime config. Never auto-downgrades to a different model; an OOM
is an explicit abort. NO model import at module load. NO answer-key access anywhere in this module.
"""
from __future__ import annotations
import json
import urllib.request
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional


class ModelAbort(RuntimeError):
    """Raised on a fatal, non-recoverable model condition (e.g. OOM). Never downgrade; abort the run."""


@dataclass
class ModelConfig:
    evaluator_id: str
    model_id: str
    family: str
    backend: str = "transformers"          # transformers | vllm_openai | fake
    revision: Optional[str] = None
    dtype: str = "bfloat16"                # bfloat16 | float16
    tensor_parallel_size: int = 1
    max_model_len: Optional[int] = None
    trust_remote_code: bool = False
    base_url: Optional[str] = None          # vllm_openai only (LOCAL server)
    max_new_tokens: int = 24               # tiny — only a {"choice":"W#"} JSON is expected
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 0
    timeout_s: int = 60

    @staticmethod
    def from_manifest_entry(e: Dict) -> "ModelConfig":
        return ModelConfig(
            evaluator_id=e["evaluator_id"], model_id=e["model_id"], family=e["family"],
            backend=e.get("backend", "transformers"), revision=e.get("revision"),
            dtype=e.get("dtype", "bfloat16"), tensor_parallel_size=int(e.get("tensor_parallel_size", 1)),
            max_model_len=e.get("max_model_len"), trust_remote_code=bool(e.get("trust_remote_code", False)),
            base_url=e.get("base_url"), max_new_tokens=int(e.get("max_new_tokens", 24)),
            temperature=0.0, top_p=1.0, seed=int(e.get("seed", 0)), timeout_s=int(e.get("timeout_s", 60)))

    def public_metadata(self) -> Dict:
        d = asdict(self)
        d.pop("base_url", None)             # never record server hosts
        return d


class TransformersEvaluator:
    is_real = True

    def __init__(self, cfg: ModelConfig):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.cfg = cfg
        dt = {"bfloat16": torch.bfloat16, "float16": torch.float16}.get(cfg.dtype, torch.bfloat16)
        self.tok = AutoTokenizer.from_pretrained(cfg.model_id, revision=cfg.revision,
                                                 trust_remote_code=cfg.trust_remote_code)
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                cfg.model_id, revision=cfg.revision, torch_dtype=dt, device_map="auto",
                trust_remote_code=cfg.trust_remote_code)
        except torch.cuda.OutOfMemoryError as e:               # noqa
            raise ModelAbort(f"CUDA OOM loading {cfg.model_id}: {e}. Abort; do NOT downgrade the model.") from e
        self.model.eval()
        # resolve the exact commit that HF actually loaded (provenance)
        self.resolved_revision = (getattr(self.model.config, "_commit_hash", None) or cfg.revision)

    def generate(self, prompt: str, settings=None) -> str:
        import torch
        msgs = [{"role": "user", "content": prompt}]
        enc = self.tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                           return_dict=True).to(self.model.device)
        in_len = enc["input_ids"].shape[1]
        try:
            with torch.no_grad():
                out = self.model.generate(**enc, max_new_tokens=self.cfg.max_new_tokens, do_sample=False,
                                          pad_token_id=self.tok.eos_token_id)
        except torch.cuda.OutOfMemoryError as e:               # noqa
            raise ModelAbort(f"CUDA OOM generating with {self.cfg.model_id}: {e}. Abort; do NOT downgrade.") from e
        return self.tok.decode(out[0][in_len:], skip_special_tokens=True).strip()


class VLLMServerEvaluator:
    is_real = True

    def __init__(self, cfg: ModelConfig):
        if not cfg.base_url:
            raise ValueError("vllm_openai backend requires base_url (a LOCAL vLLM OpenAI server)")
        self.cfg = cfg
        self.resolved_revision = cfg.revision

    def generate(self, prompt: str, settings=None) -> str:
        body = json.dumps({"model": self.cfg.model_id,
                           "messages": [{"role": "user", "content": prompt}],
                           "temperature": 0.0, "top_p": 1.0, "max_tokens": self.cfg.max_new_tokens,
                           "seed": self.cfg.seed}).encode()
        req = urllib.request.Request(self.cfg.base_url.rstrip("/") + "/v1/chat/completions",
                                     data=body, headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.cfg.timeout_s) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()


class FakeEvaluator:
    """Deterministic. NO model / NO network. Default returns a well-formed choice; modes exercise the policy."""
    is_real = False

    def __init__(self, cfg: ModelConfig, mode: str = "valid"):
        self.cfg = cfg
        self.mode = mode
        self.resolved_revision = cfg.revision or "FAKE_REV"
        self._n = 0

    def generate(self, prompt: str, settings=None) -> str:
        self._n += 1
        if self.mode == "invalid":
            return "I think it is W2"
        if self.mode == "empty":
            return ""
        if self.mode == "flaky":                               # invalid on odd calls, valid on even (tests retry)
            return '{"choice": "W1"}' if self._n % 2 == 0 else "not json"
        import hashlib
        lab = "W" + str(1 + int(hashlib.sha256(prompt.encode()).hexdigest(), 16) % 6)
        return json.dumps({"choice": lab})


def build_evaluator(cfg: ModelConfig, fake_mode: Optional[str] = None):
    """Factory. Real backends only instantiated on a model-access host. NEVER substitutes a different model."""
    if cfg.backend == "fake" or fake_mode is not None:
        return FakeEvaluator(cfg, mode=fake_mode or "valid")
    if cfg.backend == "transformers":
        return TransformersEvaluator(cfg)
    if cfg.backend == "vllm_openai":
        return VLLMServerEvaluator(cfg)
    raise ValueError(f"unknown backend {cfg.backend!r} (expected transformers | vllm_openai | fake)")
