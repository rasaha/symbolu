"""
hf_backend.py — real Hugging Face causal-LM backend + resource gate + offline mock backend.

Three concrete backends, one factory:

  * ``HFCausalBackend`` — a genuine ``transformers`` ``AutoModelForCausalLM`` + ``AutoTokenizer``.
    This is the ONLY backend whose output may be used for a scientific verdict. It records the
    proof-of-execution fields RM1 requires (model class, revision, parameter count, logits shape,
    generated token ids, device, dtype) on the first real forward pass.

  * ``MockBackend`` — a deterministic, offline stub that parses the *governed source text* with a
    fixed grammar. It is CLEARLY NOT a real model. It exists only so the surrounding harness is
    fully exercisable (unit tests, plumbing smoke) without weights, network, torch or transformers.
    Its results are always tagged ``execution="MOCK"`` and are never a real-model result.

  * factory ``load_backend(cfg)`` — probes the environment (``probe_environment``) and either
    returns a live ``HFCausalBackend`` or raises ``ResourceBlocked`` with exact remediation. It
    never silently downgrades to the mock backend and never silently quantizes or switches families.

Design constraints honoured here:
  * default ``trust_remote_code=False``
  * dtype: bfloat16 when genuinely supported, float16 only on compatible CUDA, float32 on CPU
  * 4-bit only when CUDA is available AND ``bitsandbytes`` imports AND the caller opted in
  * authentication tokens are read from the environment but NEVER printed or stored in artifacts
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Errors                                                                       #
# --------------------------------------------------------------------------- #
class ResourceBlocked(Exception):
    """Raised when a genuine open-weight model cannot be loaded. Carries a structured manifest so
    the caller can emit ``RESOURCE_BLOCKED`` with exact remediation and stop before any claim."""

    def __init__(self, manifest: Dict):
        self.manifest = manifest
        super().__init__(manifest.get("reason", "RESOURCE_BLOCKED"))


# --------------------------------------------------------------------------- #
# Model-load configuration                                                     #
# --------------------------------------------------------------------------- #
@dataclass
class ModelConfig:
    model_id: str
    revision: Optional[str] = None
    device: str = "auto"          # auto|cuda|mps|cpu
    dtype: str = "auto"           # auto|bf16|fp16|fp32
    load_in_4bit: bool = False
    trust_remote_code: bool = False
    max_input_tokens: int = 2048
    max_new_tokens: int = 512
    offline: bool = False
    seed: int = 0


# --------------------------------------------------------------------------- #
# Environment probe                                                            #
# --------------------------------------------------------------------------- #
def _pkg_version(name: str) -> Optional[str]:
    if importlib.util.find_spec(name) is None:
        return None
    try:
        mod = importlib.import_module(name)
        return getattr(mod, "__version__", "unknown")
    except Exception:
        return None


def _total_ram_bytes() -> Optional[int]:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def probe_environment() -> Dict:
    """Detect interpreter, packages, hardware and supported floating-point types.

    Pure-stdlib and side-effect-free: importing torch is attempted only to read device availability,
    and never triggers a weight download. Safe to call on a machine with nothing installed.
    """
    versions = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": _pkg_version("torch"),
        "transformers": _pkg_version("transformers"),
        "accelerate": _pkg_version("accelerate"),
        "safetensors": _pkg_version("safetensors"),
        "bitsandbytes": _pkg_version("bitsandbytes"),
        "numpy": _pkg_version("numpy"),
    }

    hw = {
        "cpu_count": os.cpu_count(),
        "total_ram_bytes": _total_ram_bytes(),
        "cuda_available": False,
        "cuda_device_count": 0,
        "mps_available": False,
        "vram_bytes_per_device": [],
        "supported_fp": ["float32"],   # CPU always supports float32
    }

    if versions["torch"]:
        try:
            import torch  # noqa: PLC0415
            if torch.cuda.is_available():
                hw["cuda_available"] = True
                hw["cuda_device_count"] = torch.cuda.device_count()
                for i in range(torch.cuda.device_count()):
                    try:
                        props = torch.cuda.get_device_properties(i)
                        hw["vram_bytes_per_device"].append(int(props.total_memory))
                    except Exception:
                        hw["vram_bytes_per_device"].append(None)
                # bf16 support on the current CUDA device
                try:
                    if torch.cuda.is_bf16_supported():
                        hw["supported_fp"].append("bfloat16")
                except Exception:
                    pass
                hw["supported_fp"].append("float16")
            mps = getattr(getattr(torch, "backends", None), "mps", None)
            if mps is not None and mps.is_available():
                hw["mps_available"] = True
                # MPS supports fp16; bf16 support is device-dependent and not assumed
                if "float16" not in hw["supported_fp"]:
                    hw["supported_fp"].append("float16")
        except Exception:
            pass

    return {"versions": versions, "hardware": hw}


def _select_device(cfg: ModelConfig, env: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Return (device, error). device in {'cuda','mps','cpu'}; error non-None => cannot honour."""
    hw = env["hardware"]
    if cfg.device == "cuda":
        return ("cuda", None) if hw["cuda_available"] else (None, "cuda_requested_but_unavailable")
    if cfg.device == "mps":
        return ("mps", None) if hw["mps_available"] else (None, "mps_requested_but_unavailable")
    if cfg.device == "cpu":
        return "cpu", None
    # auto
    if hw["cuda_available"]:
        return "cuda", None
    if hw["mps_available"]:
        return "mps", None
    return "cpu", None


def _select_dtype(cfg: ModelConfig, device: str, env: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Return (dtype_name, error). Never silently picks an unsupported type."""
    supported = env["hardware"]["supported_fp"]
    if cfg.dtype == "bf16":
        if "bfloat16" in supported:
            return "bfloat16", None
        return None, "bf16_requested_but_unsupported"
    if cfg.dtype == "fp16":
        if device == "cpu":
            return None, "fp16_requested_on_cpu"  # fp16 matmul on CPU is not a supported real path
        if "float16" in supported:
            return "float16", None
        return None, "fp16_requested_but_unsupported"
    if cfg.dtype == "fp32":
        return "float32", None
    # auto: bf16 when supported, else fp16 on CUDA, else fp32 on CPU
    if device == "cuda":
        if "bfloat16" in supported:
            return "bfloat16", None
        return "float16", None
    if device == "mps":
        return "float16", None
    return "float32", None


def _four_bit_ok(cfg: ModelConfig, device: str, env: Dict) -> Tuple[bool, Optional[str]]:
    if not cfg.load_in_4bit:
        return False, None
    if device != "cuda":
        return False, "4bit_requires_cuda"
    if not env["versions"]["bitsandbytes"]:
        return False, "4bit_requires_bitsandbytes"
    return True, None


def build_resource_manifest(cfg: ModelConfig, env: Dict, reason: str,
                            remediation: Dict) -> Dict:
    """The structured record emitted on RESOURCE_BLOCKED (also written to RESOURCE_MANIFEST.json)."""
    return {
        "status": "RESOURCE_BLOCKED",
        "reason": reason,
        "requested_model": cfg.model_id,
        "requested_revision": cfg.revision,
        "requested_device": cfg.device,
        "requested_dtype": cfg.dtype,
        "requested_load_in_4bit": cfg.load_in_4bit,
        "environment": env,
        "remediation": remediation,
    }


def _missing_core_packages(env: Dict) -> List[str]:
    need = ["torch", "transformers"]
    return [p for p in need if not env["versions"][p]]


# --------------------------------------------------------------------------- #
# Backend interface + proof-of-execution                                       #
# --------------------------------------------------------------------------- #
@dataclass
class ExecutionProof:
    """Recorded on the first real forward pass — the evidence that an actual model executed."""
    model_class: str = ""
    model_revision: Optional[str] = None
    parameter_count: Optional[int] = None
    logits_shape: Optional[List[int]] = None
    generated_token_ids: Optional[List[int]] = None
    device: str = ""
    dtype: str = ""
    verified: bool = False


@dataclass
class GenResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    generated_token_ids: List[int] = field(default_factory=list)
    latency_ms: float = 0.0


class Backend:
    """Abstract text-in / text-out causal-LM backend with deterministic (greedy) decoding."""
    name = "abstract"
    execution = "ABSTRACT"     # "REAL" | "MOCK"

    def describe(self) -> Dict:  # model-identity manifest (no secrets)
        raise NotImplementedError

    def generate(self, system: str, user: str, max_new_tokens: Optional[int] = None) -> GenResult:
        raise NotImplementedError

    @property
    def proof(self) -> ExecutionProof:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Real Hugging Face backend                                                    #
# --------------------------------------------------------------------------- #
class HFCausalBackend(Backend):
    """Genuine transformers AutoModelForCausalLM. Greedy, deterministic decoding (do_sample=False).

    Constructed only via ``load_backend`` after the resource gate has passed, so by the time this
    object exists torch + transformers are importable and the device/dtype are honourable.
    """
    name = "hf-causal"
    execution = "REAL"

    def __init__(self, cfg: ModelConfig, device: str, dtype: str, four_bit: bool):
        self.cfg = cfg
        self.device = device
        self.dtype_name = dtype
        self.four_bit = four_bit
        self._proof = ExecutionProof(device=device, dtype=dtype)
        self._load()

    def _load(self) -> None:  # pragma: no cover - requires torch + weights, gated out in sandbox
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
        torch_dtype = dtype_map[self.dtype_name]

        # transformers renamed the `torch_dtype` from_pretrained kwarg to `dtype` in 4.56 and REMOVED
        # `torch_dtype` in 5.x — pick the key the installed version accepts (supports the 4.40 floor
        # through 5.x). See requirements-real-model.txt.
        try:
            _parts = transformers.__version__.split(".")
            _ver = (int(_parts[0]), int(_parts[1]) if len(_parts) > 1 else 0)
        except Exception:
            _ver = (4, 40)
        dtype_key = "dtype" if _ver >= (4, 56) else "torch_dtype"

        kwargs: Dict = {
            "revision": self.cfg.revision,
            "trust_remote_code": self.cfg.trust_remote_code,
        }
        if self.four_bit:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch_dtype)
        else:
            kwargs[dtype_key] = torch_dtype

        if self.device == "cuda":
            kwargs["device_map"] = "auto"

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.cfg.model_id, revision=self.cfg.revision,
            trust_remote_code=self.cfg.trust_remote_code)
        self.model = AutoModelForCausalLM.from_pretrained(self.cfg.model_id, **kwargs)
        if self.device != "cuda":            # device_map handles cuda placement
            self.model = self.model.to(self.device)
        self.model.eval()

        torch.manual_seed(self.cfg.seed)
        if self.device == "cuda":
            torch.cuda.manual_seed_all(self.cfg.seed)

        self._proof.model_class = type(self.model).__name__
        self._proof.model_revision = self.cfg.revision
        try:
            self._proof.parameter_count = int(sum(p.numel() for p in self.model.parameters()))
        except Exception:
            self._proof.parameter_count = None

    def describe(self) -> Dict:  # pragma: no cover - requires a loaded model
        tok = self.tokenizer
        cfg = self.model.config
        return {
            "model_id": self.cfg.model_id,
            "revision": self.cfg.revision,
            "architecture_class": type(self.model).__name__,
            "parameter_count": self._proof.parameter_count,
            "tokenizer_class": type(tok).__name__,
            "tokenizer_vocab_size": int(getattr(tok, "vocab_size", 0) or 0),
            "context_limit": int(getattr(cfg, "max_position_embeddings", 0) or 0),
            "dtype": self.dtype_name,
            "quantization": "4bit" if self.four_bit else "none",
            "attention_implementation": getattr(cfg, "_attn_implementation", "default"),
            "device_map": "auto" if self.device == "cuda" else self.device,
            "trust_remote_code": self.cfg.trust_remote_code,
            "execution": self.execution,
        }

    def generate(self, system: str, user: str,
                 max_new_tokens: Optional[int] = None) -> GenResult:  # pragma: no cover
        import time
        import torch

        prompt = self._format_chat(system, user)
        enc = self.tokenizer(prompt, return_tensors="pt", truncation=True,
                             max_length=self.cfg.max_input_tokens)
        input_ids = enc["input_ids"].to(self.model.device)
        n_prompt = int(input_ids.shape[1])
        t0 = time.time()
        with torch.no_grad():
            out = self.model.generate(
                input_ids,
                attention_mask=enc.get("attention_mask", None).to(self.model.device)
                if enc.get("attention_mask", None) is not None else None,
                do_sample=False,                      # deterministic decoding
                num_beams=1,
                max_new_tokens=max_new_tokens or self.cfg.max_new_tokens,
                pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            )
        latency_ms = (time.time() - t0) * 1000.0
        gen_ids = out[0][n_prompt:].tolist()
        text = self.tokenizer.decode(gen_ids, skip_special_tokens=True)

        if not self._proof.verified:
            # capture proof-of-execution from a single real forward pass
            with torch.no_grad():
                logits = self.model(input_ids).logits
            self._proof.logits_shape = list(logits.shape)
            self._proof.generated_token_ids = gen_ids[:32]
            self._proof.verified = True

        return GenResult(text=text, prompt_tokens=n_prompt, completion_tokens=len(gen_ids),
                         generated_token_ids=gen_ids, latency_ms=latency_ms)

    def _format_chat(self, system: str, user: str) -> str:  # pragma: no cover
        tok = self.tokenizer
        if getattr(tok, "chat_template", None):
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            try:
                return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            except Exception:
                pass
        return f"{system}\n\n{user}\n"

    @property
    def proof(self) -> ExecutionProof:
        return self._proof


# --------------------------------------------------------------------------- #
# Offline mock backend (tests / plumbing only — never a verdict)               #
# --------------------------------------------------------------------------- #
class MockBackend(Backend):
    """Deterministic offline backend. NOT a real model.

    It does not "understand" anything: given the extraction prompt (which embeds the governed source
    text in a fixed machine grammar) it returns a JSON extraction produced by a deterministic parser.
    This lets the whole RM1 pipeline run end-to-end so the plumbing and the deterministic gate are
    testable without weights. Every result carries ``execution="MOCK"`` and is excluded from claims.
    """
    name = "mock-offline"
    execution = "MOCK"

    def __init__(self, responder=None):
        # responder: callable(system, user) -> str. Default returns "{}" (empty proposal set).
        self._responder = responder or (lambda system, user: "{}")
        self._proof = ExecutionProof(model_class="MockBackend", device="cpu", dtype="float32",
                                     parameter_count=0, verified=True,
                                     logits_shape=[1, 1, 1], generated_token_ids=[0])

    def describe(self) -> Dict:
        return {
            "model_id": "MOCK-OFFLINE-STUB",
            "revision": None,
            "architecture_class": "MockBackend",
            "parameter_count": 0,
            "tokenizer_class": "whitespace-mock",
            "tokenizer_vocab_size": 0,
            "context_limit": 0,
            "dtype": "float32",
            "quantization": "none",
            "attention_implementation": "none",
            "device_map": "cpu",
            "trust_remote_code": False,
            "execution": self.execution,
        }

    def generate(self, system: str, user: str, max_new_tokens: Optional[int] = None) -> GenResult:
        text = self._responder(system, user)
        return GenResult(text=text, prompt_tokens=max(1, len(user) // 4),
                         completion_tokens=max(1, len(text) // 4),
                         generated_token_ids=[0], latency_ms=0.0)

    @property
    def proof(self) -> ExecutionProof:
        return self._proof


# --------------------------------------------------------------------------- #
# Factory + resource gate                                                      #
# --------------------------------------------------------------------------- #
def load_backend(cfg: ModelConfig, env: Optional[Dict] = None) -> HFCausalBackend:
    """Load a REAL Hugging Face backend or raise ``ResourceBlocked`` with a full manifest.

    Never returns the mock backend and never silently quantizes or switches model families.
    """
    env = env or probe_environment()

    missing = _missing_core_packages(env)
    if missing:
        raise ResourceBlocked(build_resource_manifest(
            cfg, env, reason=f"missing_packages:{','.join(missing)}",
            remediation=_remediation(cfg, env, missing_packages=missing)))

    device, derr = _select_device(cfg, env)
    if derr:
        raise ResourceBlocked(build_resource_manifest(
            cfg, env, reason=derr, remediation=_remediation(cfg, env)))

    dtype, dterr = _select_dtype(cfg, device, env)
    if dterr:
        raise ResourceBlocked(build_resource_manifest(
            cfg, env, reason=dterr, remediation=_remediation(cfg, env)))

    four_bit, qerr = _four_bit_ok(cfg, device, env)
    if qerr:
        raise ResourceBlocked(build_resource_manifest(
            cfg, env, reason=qerr, remediation=_remediation(cfg, env)))

    try:  # pragma: no cover - not reachable without torch + weights in the sandbox
        return HFCausalBackend(cfg, device=device, dtype=dtype, four_bit=four_bit)
    except Exception as exc:  # weights missing / gated / OOM / download / offline with no cache
        _first = (str(exc).strip().splitlines() or [""])[0][:200]
        _reason = f"model_load_failed:{type(exc).__name__}"
        if _first:
            _reason += f": {_first}"
        raise ResourceBlocked(build_resource_manifest(
            cfg, env, reason=_reason,
            remediation=_remediation(cfg, env, load_error=str(exc)[:600])))


def _estimate_memory_note(cfg: ModelConfig) -> str:
    return ("Estimated memory ~= parameter_count * bytes_per_param (2 for bf16/fp16, 4 for fp32) "
            "plus KV cache and activations; e.g. a 7B model needs ~14 GB in fp16, ~28 GB in fp32, "
            "and ~5-6 GB under 4-bit CUDA quantization.")


def _remediation(cfg: ModelConfig, env: Dict, missing_packages: Optional[List[str]] = None,
                 load_error: Optional[str] = None) -> Dict:
    steps: List[str] = []
    if missing_packages:
        steps.append(
            "pip install -r experiments/hybrid_token_event_attention/real_model/"
            "requirements-real-model.txt")
    steps.append(
        "Run on a machine with a CUDA GPU (>= 16 GB VRAM for a 7B model in bf16/fp16, or use "
        "--load-in-4bit on CUDA for ~6 GB), or a CPU host with >= 32 GB RAM for fp32 (slow).")
    rev = f' --revision "{cfg.revision}"' if cfg.revision else ""
    steps.append(
        "Recommended command on a suitable machine:\n"
        f'  export UGENCE_REAL_MODEL_ID="{cfg.model_id}"\n'
        "  python -m experiments.hybrid_token_event_attention.real_model.run_real_model \\\n"
        f'      --model-id "$UGENCE_REAL_MODEL_ID"{rev} --mode smoke --limit 20 --device auto '
        "--dtype auto")
    if load_error:
        # download / load failures: prefer local weights, authenticate, and avoid the Xet path
        steps.append(
            "If this was a DOWNLOAD failure (interrupted / 'Reconstructing (incomplete total...)' / "
            "RuntimeError mid-fetch): point --model-id at a LOCAL model directory to skip the "
            "download, e.g. --model-id /path/to/mistral-7b-instruct-v0.3 (optionally add --offline).")
        steps.append(
            "Otherwise: set HF_TOKEN for authenticated, higher-rate downloads; if the Xet transfer "
            "keeps failing, disable it with HF_HUB_DISABLE_XET=1 (or `pip uninstall -y hf_xet`), or "
            "pre-fetch once with `huggingface-cli download <model-id>` then pass its local path.")
    out = {
        "missing_package_or_access_requirement": missing_packages or [],
        "detected_hardware": env["hardware"],
        "estimated_memory_requirement": _estimate_memory_note(cfg),
        "recommended_steps": steps,
    }
    if load_error:
        out["load_error"] = load_error
    return out
