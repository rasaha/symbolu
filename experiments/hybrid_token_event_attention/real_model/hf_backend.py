"""
hf_backend.py — environment/resource gate + real Hugging Face causal-LM backend (RM1 §2, §3).

Two backends implement one interface (`Backend`):

    HFBackend    loads an ACTUAL open-weight causal LM through `transformers`. torch/transformers
                 are imported lazily so the rest of the harness (and the whole unit-test suite)
                 works without them. Deterministic decoding (do_sample=False). Records full model
                 provenance in `.info()`.
    MockBackend  a scripted, torch-free stand-in used ONLY for unit tests and the clearly-labelled
                 harness smoke. Its `.info()["backend"] == "MOCK"`; it is NEVER allowed to stand in
                 for a real-model scientific result.

The resource gate probes the environment BEFORE any weights are loaded and refuses to run rather
than silently degrade: it never silently quantizes and never silently switches model families. If
the requested model cannot be loaded it raises `ResourceBlocked` carrying exact remediation.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- probing
def _pkg_version(name: str) -> Optional[str]:
    try:
        m = importlib.import_module(name)
        return getattr(m, "__version__", "unknown")
    except Exception:
        return None


def _pkg_present(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def probe_environment() -> Dict:
    """Detect hardware + library availability WITHOUT importing torch unless it exists."""
    info: Dict = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "disk_free_gb": round(shutil.disk_usage(".").free / 1e9, 2),
        "packages": {name: _pkg_version(name) for name in
                     ("torch", "transformers", "accelerate", "safetensors",
                      "bitsandbytes", "numpy", "tokenizers")},
        "cuda_available": False,
        "mps_available": False,
        "gpu_count": 0,
        "vram_gb": None,
        "ram_gb": None,
        "supported_dtypes": ["float32"],   # CPU always supports fp32
    }
    # RAM (best-effort, stdlib only)
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        info["ram_gb"] = round(pages * page_size / 1e9, 2)
    except Exception:
        pass
    # torch-dependent probing, only if torch is actually installed
    if info["packages"]["torch"]:
        try:
            import torch  # noqa
            info["cuda_available"] = bool(torch.cuda.is_available())
            if info["cuda_available"]:
                info["gpu_count"] = torch.cuda.device_count()
                try:
                    props = torch.cuda.get_device_properties(0)
                    info["vram_gb"] = round(props.total_memory / 1e9, 2)
                    info["gpu_name"] = props.name
                    info["supported_dtypes"].append("float16")
                    if torch.cuda.is_bf16_supported():
                        info["supported_dtypes"].append("bfloat16")
                except Exception:
                    pass
            mps = getattr(getattr(torch, "backends", None), "mps", None)
            if mps is not None and mps.is_available():
                info["mps_available"] = True
                info["supported_dtypes"].append("float16")
        except Exception as e:  # torch present but broken
            info["torch_import_error"] = repr(e)
    return info


# --------------------------------------------------------------------------- resource block
@dataclass
class ResourceBlocked(Exception):
    reason: str
    requested_model: str
    detected: Dict = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)
    param_count_estimate: Optional[str] = None
    est_memory_gb: Optional[float] = None
    remediation: List[str] = field(default_factory=list)
    recommended_command: str = ""

    def payload(self) -> Dict:
        d = asdict(self)
        d["status"] = "RESOURCE_BLOCKED"
        return d

    def __str__(self) -> str:
        return f"RESOURCE_BLOCKED: {self.reason} (model={self.requested_model})"


# --------------------------------------------------------------------------- generation result
@dataclass
class GenerationResult:
    text: str
    prompt_token_ids: List[int]
    output_token_ids: List[int]
    n_input_tokens: int
    n_output_tokens: int
    logits_shape: Optional[List[int]] = None


# --------------------------------------------------------------------------- backends
class Backend:
    is_real: bool = False

    def info(self) -> Dict:  # model provenance metadata
        raise NotImplementedError

    def generate(self, prompt: str, max_new_tokens: int = 256,
                 max_input_tokens: int = 2048) -> GenerationResult:
        raise NotImplementedError

    def forward_probe(self, text: str) -> Dict:
        """One-instance proof an actual model executed: logits shape + token ids."""
        raise NotImplementedError


class MockBackend(Backend):
    """Deterministic scripted backend for tests / harness smoke. NEVER a real-model result."""
    is_real = False

    def __init__(self, responder=None, model_id: str = "mock://deterministic"):
        # responder: callable(prompt:str) -> str ; default echoes an empty JSON object
        self.responder = responder or (lambda p: "{}")
        self.model_id = model_id
        self._vocab = 32000

    def info(self) -> Dict:
        return {
            "backend": "MOCK", "is_real": False, "model_id": self.model_id,
            "revision": "n/a", "architecture": "MockDeterministic", "param_count": 0,
            "tokenizer_class": "MockTokenizer", "vocab_size": self._vocab,
            "context_limit": 4096, "dtype": "n/a", "quantization": "none",
            "attn_implementation": "n/a", "device": "cpu", "trust_remote_code": False,
        }

    def _toks(self, s: str) -> List[int]:
        return [(hash(w) % self._vocab) for w in s.split()]

    def generate(self, prompt: str, max_new_tokens: int = 256,
                 max_input_tokens: int = 2048) -> GenerationResult:
        out = self.responder(prompt)
        pt = self._toks(prompt)[:max_input_tokens]
        ot = self._toks(out)[:max_new_tokens]
        return GenerationResult(text=out, prompt_token_ids=pt, output_token_ids=ot,
                                n_input_tokens=len(pt), n_output_tokens=len(ot),
                                logits_shape=[1, len(pt), self._vocab])

    def forward_probe(self, text: str) -> Dict:
        pt = self._toks(text)
        return {"backend": "MOCK", "logits_shape": [1, len(pt), self._vocab],
                "generated_token_ids": pt[:5], "device": "cpu", "dtype": "n/a",
                "note": "MOCK backend — NOT a real-model execution proof"}


# dtype resolution ---------------------------------------------------------------------
def resolve_dtype(requested: str, env: Dict) -> str:
    if requested != "auto":
        want = {"bf16": "bfloat16", "fp16": "float16", "fp32": "float32"}[requested]
        if want not in env["supported_dtypes"]:
            raise ValueError(f"requested dtype {want} not supported by hardware "
                             f"(supported: {env['supported_dtypes']})")
        return want
    if env["cuda_available"]:
        return "bfloat16" if "bfloat16" in env["supported_dtypes"] else "float16"
    if env["mps_available"]:
        return "float16"
    return "float32"


def resolve_device(requested: str, env: Dict) -> str:
    if requested != "auto":
        return requested
    if env["cuda_available"]:
        return "cuda"
    if env["mps_available"]:
        return "mps"
    return "cpu"


class HFBackend(Backend):
    """Real Hugging Face causal LM. Lazily imports torch/transformers."""
    is_real = True

    def __init__(self, config, env: Dict):
        self.config = config
        self.env = env
        self._meta: Dict = {}
        self._model = None
        self._tok = None
        self._torch = None
        self._load()

    def _load(self) -> None:
        cfg = self.config
        missing = [p for p in ("torch", "transformers") if not _pkg_present(p)]
        if missing:
            raise ResourceBlocked(
                reason=f"required package(s) not installed: {', '.join(missing)}",
                requested_model=cfg.model_id, detected=self.env, missing=missing,
                remediation=[
                    "pip install -r experiments/hybrid_token_event_attention/real_model/"
                    "requirements-real-model.txt",
                ],
                recommended_command=_recommended_command(cfg))
        if cfg.load_in_4bit:
            if not (self.env["cuda_available"] and _pkg_present("bitsandbytes")):
                raise ResourceBlocked(
                    reason="--load-in-4bit requires CUDA and an importable bitsandbytes",
                    requested_model=cfg.model_id, detected=self.env,
                    missing=[m for m in ("bitsandbytes",) if not _pkg_present(m)] or ["cuda"],
                    remediation=["run on a CUDA machine with bitsandbytes, or drop --load-in-4bit"],
                    recommended_command=_recommended_command(cfg))
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self._torch = torch
        dtype = resolve_dtype(cfg.dtype, self.env)
        device = resolve_device(cfg.device, self.env)
        torch_dtype = getattr(torch, dtype)
        load_kwargs = dict(revision=cfg.revision, trust_remote_code=cfg.trust_remote_code)
        if cfg.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            self._tok = AutoTokenizer.from_pretrained(cfg.model_id, **load_kwargs)
            model_kwargs = dict(load_kwargs)
            model_kwargs["torch_dtype"] = torch_dtype
            model_kwargs["attn_implementation"] = cfg.attn_implementation
            if cfg.load_in_4bit:
                from transformers import BitsAndBytesConfig
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
            self._model = AutoModelForCausalLM.from_pretrained(cfg.model_id, **model_kwargs)
            if not cfg.load_in_4bit:
                self._model = self._model.to(device)
            self._model.eval()
        except ResourceBlocked:
            raise
        except Exception as e:
            raise ResourceBlocked(
                reason=f"model load failed: {type(e).__name__}: {e}",
                requested_model=cfg.model_id, detected=self.env,
                remediation=[
                    "verify the model id / local path and revision",
                    "ensure Hugging Face Hub is reachable (this sandbox returns HTTP 403 for "
                    "huggingface.co) or pass a local --model-id directory with --offline",
                    "accept the model license on the Hub if required",
                ],
                recommended_command=_recommended_command(cfg))
        cfgobj = getattr(self._model, "config", None)
        n_params = sum(p.numel() for p in self._model.parameters())
        self._meta = {
            "backend": "HF", "is_real": True, "model_id": cfg.model_id,
            "revision": cfg.revision or "main",
            "architecture": type(self._model).__name__,
            "param_count": int(n_params),
            "tokenizer_class": type(self._tok).__name__,
            "vocab_size": int(getattr(self._tok, "vocab_size", 0) or 0),
            "context_limit": int(getattr(cfgobj, "max_position_embeddings", 0) or 0),
            "dtype": dtype, "quantization": "4bit" if cfg.load_in_4bit else "none",
            "attn_implementation": cfg.attn_implementation, "device": device,
            "trust_remote_code": cfg.trust_remote_code,
            "library_versions": {k: self.env["packages"][k] for k in
                                 ("torch", "transformers", "accelerate", "safetensors")},
        }

    def info(self) -> Dict:
        return dict(self._meta)

    def generate(self, prompt: str, max_new_tokens: int = 256,
                 max_input_tokens: int = 2048) -> GenerationResult:
        torch = self._torch
        enc = self._tok(prompt, return_tensors="pt", truncation=True,
                        max_length=max_input_tokens)
        enc = {k: v.to(self._model.device) for k, v in enc.items()}
        with torch.no_grad():
            out = self._model.generate(**enc, max_new_tokens=max_new_tokens,
                                       do_sample=False, num_beams=1,
                                       pad_token_id=getattr(self._tok, "eos_token_id", None))
        in_len = enc["input_ids"].shape[1]
        gen_ids = out[0][in_len:].tolist()
        text = self._tok.decode(gen_ids, skip_special_tokens=True)
        return GenerationResult(text=text, prompt_token_ids=enc["input_ids"][0].tolist(),
                                output_token_ids=gen_ids, n_input_tokens=in_len,
                                n_output_tokens=len(gen_ids))

    def forward_probe(self, text: str) -> Dict:
        torch = self._torch
        enc = self._tok(text, return_tensors="pt", truncation=True, max_length=64)
        enc = {k: v.to(self._model.device) for k, v in enc.items()}
        with torch.no_grad():
            out = self._model(**enc)
            next_id = int(out.logits[0, -1].argmax().item())
        return {"backend": "HF", "model_class": type(self._model).__name__,
                "revision": self._meta["revision"], "param_count": self._meta["param_count"],
                "logits_shape": list(out.logits.shape), "generated_token_ids": [next_id],
                "device": str(self._model.device), "dtype": self._meta["dtype"]}


def _recommended_command(cfg) -> str:
    return ("On a CUDA machine (>=16GB VRAM for a 7B bf16 model) with deps installed:\n"
            "  pip install -r experiments/hybrid_token_event_attention/real_model/"
            "requirements-real-model.txt\n"
            f"  export UGENCE_REAL_MODEL_ID={cfg.model_id or '<hf-repo-or-local-dir>'}\n"
            "  python -m experiments.hybrid_token_event_attention.real_model.run_real_model \\\n"
            "      --model-id \"$UGENCE_REAL_MODEL_ID\" --mode smoke --limit 20")


def load_backend(config, env: Optional[Dict] = None) -> Backend:
    """Gate → real backend, or raise ResourceBlocked. `config.mock_responder` forces MockBackend."""
    env = env or probe_environment()
    if getattr(config, "mock_responder", None) is not None:
        return MockBackend(responder=config.mock_responder, model_id=config.model_id or "mock://")
    if not config.model_id:
        raise ResourceBlocked(
            reason="no model specified: pass --model-id or set UGENCE_REAL_MODEL_ID",
            requested_model="", detected=env, missing=["model-id"],
            remediation=["export UGENCE_REAL_MODEL_ID=<hf-repo-or-local-dir>"],
            recommended_command=_recommended_command(config))
    return HFBackend(config, env)
