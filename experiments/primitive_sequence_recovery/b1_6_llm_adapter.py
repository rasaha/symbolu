"""B1.6 local LLM generation adapter (modeled on the B1.1 run pattern).

Provides a narrow `generate(prompt, settings) -> str` interface with:
  - a REAL transformers adapter (lazy CUDA/HF load at a frozen revision),
  - an OPTIONAL local OpenAI-compatible endpoint adapter (e.g. a local vLLM server),
  - a deterministic FakeAdapter for tests (NO model, NO network),
  - output-format validation + a frozen retry policy (never silently edits output).

Reuses B1.1's committed shape (run_b1_1_generation.TransformersAdapter / MockAdapter /
_gen_with_retry / model_access_readiness). Makes NO external API call at import or in
tests. Real generation runs only on a model-access host (RunPod). No judging here.
B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass, field, asdict, replace
from typing import Dict, List, Optional, Tuple


@dataclass
class GenerationSettings:
    model_id: str = "MOCK_ONLY"
    revision: Optional[str] = None
    backend: str = "transformers"          # "transformers" | "openai_compat_local" | "fake"
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 600          # room for Title + 120-180w Interpretation + 2 bullets + Caution
    seed: int = 0
    timeout_s: int = 120
    max_attempts: int = 3
    base_url: Optional[str] = None          # for openai_compat_local (LOCAL server only)

    def metadata(self) -> Dict:
        d = asdict(self)
        d.pop("base_url", None)             # do not record endpoint hosts in the manifest
        return d


# --------------------------------------------------------------------------------------
# Backend readiness (mirrors B1.1 model_access_readiness; NO network touched)
# --------------------------------------------------------------------------------------
def model_backend_readiness() -> Dict:
    checks: Dict = {}
    try:
        import torch  # noqa
        checks["torch_importable"] = True
        checks["cuda_available"] = bool(torch.cuda.is_available())
    except Exception as e:                                  # noqa: BLE001
        checks["torch_importable"] = False
        checks["cuda_available"] = False
        checks["torch_error"] = str(e)
    try:
        import transformers
        checks["transformers_version"] = transformers.__version__
    except Exception as e:                                  # noqa: BLE001
        checks["transformers_version"] = None
        checks["transformers_error"] = str(e)
    checks["note"] = ("Real generation requires a model-access host (CUDA + transformers, or a local "
                      "OpenAI-compatible server). No network is touched here.")
    return checks


# --------------------------------------------------------------------------------------
# Output-format validation (Title / Interpretation / Practical reflection / Caution)
# --------------------------------------------------------------------------------------
REQUIRED_SECTIONS = ("Title:", "Interpretation:", "Practical reflection:", "Caution:")


def _interpretation_wordcount(text: str) -> int:
    try:
        seg = text.split("Interpretation:", 1)[1]
        seg = seg.split("Practical reflection:", 1)[0]
    except IndexError:
        return 0
    return len([w for w in seg.split() if w.strip()])


def validate_output_format(text: str, interp_min: int = 60, interp_max: int = 260) -> Tuple[bool, List[str]]:
    """Rough structural + length check. Never edits; only accepts/rejects."""
    reasons: List[str] = []
    if not text or not text.strip():
        return False, ["empty output"]
    idx = -1
    for sec in REQUIRED_SECTIONS:
        j = text.find(sec)
        if j < 0:
            reasons.append(f"missing section: {sec}")
        elif j < idx:
            reasons.append(f"section out of order: {sec}")
        else:
            idx = j
    wc = _interpretation_wordcount(text)
    if wc and not (interp_min <= wc <= interp_max):
        reasons.append(f"interpretation word count {wc} outside rough bounds [{interp_min},{interp_max}]")
    return (not reasons), reasons


# --------------------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------------------
class TransformersAdapter:
    """REAL adapter — lazy-loads a frozen model at a frozen revision. Instantiated only on a
    model-access host; never in tests or this environment (readiness gate refuses first)."""
    is_real = True
    backend = "transformers"

    def __init__(self, settings: GenerationSettings):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.s = settings
        self.tok = AutoTokenizer.from_pretrained(settings.model_id, revision=settings.revision)
        self.model = AutoModelForCausalLM.from_pretrained(
            settings.model_id, revision=settings.revision, torch_dtype=torch.float16, device_map="auto")
        self.model.eval()

    def generate(self, prompt: str, settings: Optional[GenerationSettings] = None) -> str:
        import torch
        from transformers import set_seed
        s = settings or self.s
        set_seed(s.seed)
        msgs = [{"role": "user", "content": prompt}]        # user-turn only; no system prompt
        enc = self.tok.apply_chat_template(
            msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(self.model.device)
        in_len = enc["input_ids"].shape[1]
        with torch.no_grad():
            out = self.model.generate(**enc, do_sample=True, temperature=s.temperature, top_p=s.top_p,
                                      max_new_tokens=s.max_tokens, pad_token_id=self.tok.eos_token_id)
        return self.tok.decode(out[0][in_len:], skip_special_tokens=True).strip()


class OpenAICompatLocalAdapter:
    """OPTIONAL adapter for a LOCAL OpenAI-compatible server (e.g. vLLM). Talks only to settings.base_url
    (must be a local/host address). Not used in tests; makes no external API call."""
    is_real = True
    backend = "openai_compat_local"

    def __init__(self, settings: GenerationSettings):
        if not settings.base_url:
            raise ValueError("openai_compat_local backend requires settings.base_url (a LOCAL server)")
        self.s = settings

    def generate(self, prompt: str, settings: Optional[GenerationSettings] = None) -> str:
        s = settings or self.s
        body = json.dumps({
            "model": s.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": s.temperature, "top_p": s.top_p, "max_tokens": s.max_tokens,
        }).encode()
        req = urllib.request.Request(s.base_url.rstrip("/") + "/v1/chat/completions",
                                     data=body, headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=s.timeout_s) as resp:   # local host only
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()


class FakeAdapter:
    """Deterministic test adapter. NO model, NO network. Produces well-formed output by default so the
    happy path validates; `malformed=True` produces output that fails validation."""
    is_real = False
    backend = "fake"

    def __init__(self, settings: Optional[GenerationSettings] = None, malformed: bool = False):
        self.s = settings or GenerationSettings(model_id="FAKE", backend="fake")
        self.malformed = malformed

    def generate(self, prompt: str, settings: Optional[GenerationSettings] = None) -> str:
        h = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        if self.malformed:
            return f"[FAKE_MALFORMED_{h}] no required sections here"
        filler = " ".join(["the reading unfolds steadily and plainly"] * 18)  # ~108 words
        return (f"Title: reading {h}\n"
                f"Interpretation: {filler} and settles into a calm close.\n"
                f"Practical reflection:\n- consider it slowly\n- hold it lightly\n"
                f"Caution: This is a limited, non-authoritative reading and may not fit every context.")


# --------------------------------------------------------------------------------------
# Retry (mirrors B1.1 _gen_with_retry) + validation
# --------------------------------------------------------------------------------------
def generate_with_retry(adapter, prompt: str, settings: GenerationSettings,
                        validate: bool = True, sleep=time.sleep) -> Tuple[Optional[str], str, List[str]]:
    """Frozen retry policy: up to max_attempts; validate format (never edit); on repeated failure return
    a failure status. Returns (text|None, status, reasons). status in {ok, format_invalid, error}."""
    last_reasons: List[str] = []
    had_exception = False
    for attempt in range(settings.max_attempts):
        # Vary the seed per attempt so a retry is a genuinely different generation, not an identical
        # (set_seed-pinned) repeat of the same format-failing output.
        attempt_settings = settings if attempt == 0 else replace(settings, seed=settings.seed + attempt)
        try:
            text = adapter.generate(prompt, attempt_settings)
            had_exception = False
        except Exception as e:                              # noqa: BLE001
            had_exception = True
            last_reasons = [f"{type(e).__name__}: {e}"]
            if attempt < settings.max_attempts - 1:
                sleep(min(2 ** attempt, 8))
            continue
        if not validate:
            return text, "ok", []
        ok, reasons = validate_output_format(text)
        if ok:
            return text, "ok", []
        last_reasons = reasons          # do NOT edit output to fix it; retry a fresh generation
    return None, ("error" if had_exception else "format_invalid"), last_reasons


def build_adapter(settings: GenerationSettings):
    """Factory. Real backends only instantiated on a model-access host."""
    if settings.backend == "fake":
        return FakeAdapter(settings)
    if settings.backend == "transformers":
        return TransformersAdapter(settings)
    if settings.backend == "openai_compat_local":
        return OpenAICompatLocalAdapter(settings)
    raise ValueError(f"unknown backend {settings.backend!r}")
