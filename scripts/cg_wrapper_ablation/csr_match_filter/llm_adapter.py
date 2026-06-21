"""llm_adapter.py — pluggable LLM backends for the Phase 2 framed-answer eval.

The eval runs ONE model across three prompt arms (base / framed / framed+postcheck). Adapters expose
a single `generate(prompt) -> str`. A deterministic StubLLMAdapter lets the whole harness run offline
(labeled stub / production_valid=false); a RealLLMAdapter placeholder uses an env-configured backend
if available (no API keys required, no hard internet dependency).

This file does NOT touch Phase 1 scoring, generation wrappers, hidden-state probes, or governance.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import registry as REG

# ----------------------------------------------------------------------------------------------- #
# base interface
# ----------------------------------------------------------------------------------------------- #


class LLMAdapter:
    backend = "abstract"
    production_valid = False

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


# ----------------------------------------------------------------------------------------------- #
# StubLLMAdapter — one deterministic "model" driven by prompt content
# ----------------------------------------------------------------------------------------------- #

# the stub's small "world knowledge": polysemous terms it associates with multiple domains. In BASE
# mode (no frame) it surfaces ALL senses (simulating an unfocused base LLM); in FRAMED mode it follows
# the frame and narrows to the primary/secondary domains only.
_ASSOC: Dict[str, List[tuple]] = {
    "doctor":  [("medicine", "medical healing physician care"), ("authority", "institutional authority responsibility")],
    "judge":   [("law", "legal court justice ruling"), ("authority", "authority institutional office")],
    "bank":    [("finance", "money banking finance credit"), ("nature", "river water shore stream")],
    "apple":   [("fruit", "sweet fruit orchard food"), ("technology", "computer technology device software")],
    "fire":    [("heat", "heat flame burning warmth"), ("danger", "hazard danger emergency destruction")],
    "python":  [("programming", "programming software code language"), ("biology", "snake animal reptile species")],
    "virus":   [("biology", "infection disease cells organism"), ("security", "computer malware network attack")],
    "mercury": [("astronomy", "planet solar orbit space"), ("chemistry", "element metal liquid substance"),
                ("mythology", "roman god messenger deity")],
    "soldier": [("danger", "combat danger military conflict"), ("authority", "authority service duty")],
}

_FRAME_RE = {k: re.compile(rf"{k} domains:\s*\n\s*(.+)", re.IGNORECASE)
             for k in ("Primary", "Secondary", "Rejected")}
_REWRITE_RE = re.compile(r"(Primary|Secondary|Rejected):\s*(.*)")


def _domain_keywords(domain: str, term: Optional[str]) -> str:
    """Words the model would use for a domain — its association phrase if known, else registry keywords."""
    if term and term in _ASSOC:
        for d, phrase in _ASSOC[term]:
            if d == domain:
                return phrase
    t = REG.DOMAIN_TEMPLATES.get(domain)
    return " ".join(t.keywords[:4]) if t else domain


class StubLLMAdapter(LLMAdapter):
    """Deterministic, offline. Same 'model' for every arm — only the prompt differs."""

    backend = "stub"
    production_valid = False

    def _query(self, prompt: str) -> str:
        m = re.search(r"User question:\s*\n?\s*(.+)", prompt)
        return (m.group(1).strip() if m else prompt).strip()

    def _term(self, query: str) -> Optional[str]:
        ql = query.lower()
        hits = [k for k in _ASSOC if re.search(rf"\b{k}\b", ql)]
        return hits[0] if hits else None

    def _frame(self, prompt: str) -> Dict[str, List[str]]:
        out = {"primary": [], "secondary": [], "rejected": []}
        if "Rewrite the answer" in prompt:                 # rewrite block: "Primary: a, b"
            for k, v in _REWRITE_RE.findall(prompt):
                out[k.lower()] = [d.strip() for d in v.split(",") if d.strip() and d.strip() != "(none)"]
            return out
        for k, rgx in _FRAME_RE.items():
            m = rgx.search(prompt)
            if m:
                out[k.lower()] = [d.strip() for d in m.group(1).split(",")
                                  if d.strip() and d.strip() != "(none)"]
        return out

    def generate(self, prompt: str) -> str:
        query = self._query(prompt)
        term = self._term(query)
        framed = ("Primary domains:" in prompt) or ("Rewrite the answer" in prompt)

        if not framed:
            # BASE: surface every sense the model knows -> unfocused, may include context-wrong domains
            if term and term in _ASSOC:
                senses = "; ".join(f"{d} ({kw})" for d, kw in _ASSOC[term])
                return (f"The term '{term}' can relate to several areas: {senses}. "
                        f"There are multiple valid interpretations depending on what you mean.")
            subj = term or "the topic"
            return (f"Regarding {subj}, there are several ways to interpret this question. "
                    f"It can be considered from multiple angles without a single fixed answer.")

        # FRAMED / REWRITE: follow the selected frame, use primary keywords, avoid rejected
        fr = self._frame(prompt)
        prim, sec = fr["primary"], fr["secondary"]
        if not prim:
            return (f"Within the available frame, {term or 'this'} does not have a strong primary "
                    f"domain; it is best treated as an open or secondary question.")
        prim_kw = "; ".join(f"{d} ({_domain_keywords(d, term)})" for d in prim)
        ans = (f"Primarily, this concerns {', '.join(prim)} — {prim_kw}. "
               f"{(term or 'It').capitalize()} is mainly a matter of {prim[0]}.")
        if sec:
            sec_kw = ", ".join(f"{d}" for d in sec)
            ans += f" Secondarily, {sec_kw} may be relevant but are not the main frame."
        ans += " Meaning here is established by external semantics, not by how the word sounds."
        return ans


# ----------------------------------------------------------------------------------------------- #
# FixtureLLMAdapter — canned answers by id (for deterministic tests)
# ----------------------------------------------------------------------------------------------- #


class FixtureLLMAdapter(LLMAdapter):
    backend = "fixture"
    production_valid = False

    def __init__(self, answers: Dict[str, str]):
        self.answers = dict(answers)

    def generate(self, prompt: str) -> str:
        # fixtures key on a marker the runner injects: "[[id:<id>]]"
        m = re.search(r"\[\[id:([^\]]+)\]\]", prompt)
        return self.answers.get(m.group(1) if m else "", "")


# ----------------------------------------------------------------------------------------------- #
# RealLLMAdapter — optional, env-configured, no hard dependency
# ----------------------------------------------------------------------------------------------- #


class RealLLMAdapter(LLMAdapter):
    """Wraps a real chat backend if one is configured via env. Never requires keys at import time."""

    backend = "real"
    production_valid = True

    def __init__(self, fn: Callable[[str], str], label: str):
        self._fn = fn
        self.label = label

    def generate(self, prompt: str) -> str:
        return self._fn(prompt)


def _try_real() -> tuple:
    """Return (RealLLMAdapter, info) or (None, reason). Honors CSR_LLM_BACKEND in {anthropic, openai}."""
    backend = os.environ.get("CSR_LLM_BACKEND", "").lower()
    model = os.environ.get("CSR_LLM_MODEL", "")
    if backend == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic()
            mdl = model or "claude-sonnet-4-6"

            def fn(prompt):
                r = client.messages.create(model=mdl, max_tokens=600,
                                           messages=[{"role": "user", "content": prompt}])
                return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            return RealLLMAdapter(fn, f"anthropic:{mdl}"), f"anthropic:{mdl}"
        except Exception as exc:
            return None, f"anthropic unavailable: {exc}"
    if backend == "openai" and os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI()
            mdl = model or "gpt-4o-mini"

            def fn(prompt):
                r = client.chat.completions.create(model=mdl, max_tokens=600,
                                                   messages=[{"role": "user", "content": prompt}])
                return r.choices[0].message.content or ""
            return RealLLMAdapter(fn, f"openai:{mdl}"), f"openai:{mdl}"
        except Exception as exc:
            return None, f"openai unavailable: {exc}"
    return None, ("no real LLM configured (set CSR_LLM_BACKEND=anthropic|openai + API key); "
                  "running in stub mode")


# ----------------------------------------------------------------------------------------------- #
# LocalHFAdapter — a local HuggingFace causal LM (e.g. Mistral); no API key, runs on the pod
# ----------------------------------------------------------------------------------------------- #


class LocalHFAdapter(LLMAdapter):
    backend = "local_hf"
    production_valid = True

    def __init__(self, fn: Callable[[str], str], label: str):
        self._fn = fn
        self.label = label

    def generate(self, prompt: str) -> str:
        return self._fn(prompt)


def _try_local_hf(default_model: str = "mistralai/Mistral-7B-Instruct-v0.3") -> tuple:
    """Load a local/cached HF causal LM. CSR_LLM_MODEL = hub id or local path. (None, reason) on fail."""
    name = os.environ.get("CSR_LLM_MODEL", default_model)
    max_new = int(os.environ.get("CSR_LLM_MAX_TOKENS", "400"))
    # strip THIS package's injected sys.path entries so HF dynamic module loading doesn't hit
    # 'attempted relative import' (same fix as the embedder loader)
    here = str(Path(__file__).resolve().parent)
    parent = str(Path(__file__).resolve().parents[1])
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if p not in ("", here, parent)]
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(name)
        model = AutoModelForCausalLM.from_pretrained(name, torch_dtype="auto", device_map="auto")
        model.eval()

        def fn(prompt, _tok=tok, _mdl=model, _max=max_new):
            if getattr(_tok, "chat_template", None):
                ids = _tok.apply_chat_template([{"role": "user", "content": prompt}],
                                               add_generation_prompt=True, return_tensors="pt")
            else:
                ids = _tok(prompt, return_tensors="pt").input_ids
            ids = ids.to(_mdl.device)
            with torch.no_grad():
                out = _mdl.generate(ids, max_new_tokens=_max, do_sample=False,
                                    pad_token_id=(_tok.eos_token_id or 0))
            return _tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True).strip()
        return LocalHFAdapter(fn, f"local_hf:{name}"), f"local_hf:{name}"
    except Exception as exc:
        return None, f"local HF model unavailable ({name}): {type(exc).__name__}: {exc}"
    finally:
        sys.path[:] = saved


def load_llm_adapter(backend: str = "stub"):
    """Return (adapter, info). backend in {stub, real, local, mistral}. Falls back to stub if absent."""
    if backend in ("local", "hf", "mistral"):
        default = "mistralai/Mistral-7B-Instruct-v0.3"
        adapter, info = _try_local_hf(default)
        if adapter is not None:
            return adapter, info
        return StubLLMAdapter(), f"{backend} requested but unavailable -> stub ({info})"
    if backend == "real":
        adapter, info = _try_real()
        if adapter is not None:
            return adapter, info
        return StubLLMAdapter(), f"real requested but unavailable -> stub ({info})"
    return StubLLMAdapter(), "stub"
