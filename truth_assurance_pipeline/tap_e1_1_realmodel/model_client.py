"""
Model-client abstraction for TAP-E1.1 (Real Model Validation).

The ONLY variable under study in TAP-E1.1 is the interpretation engine. Everything
else (schema, deterministic extraction, provenance, ambiguity, conflict, clarification,
metrics, gates) is imported UNCHANGED from the frozen TAP-E1 package.

A ``ModelClient`` turns a raw request into a *model interpretation core* (a small
dict, see ``MODEL_CORE_KEYS``). Three implementations:

  * ``AnthropicModelClient`` — real Anthropic API. Used automatically when an API key
    is present. This is the intended production path for the experiment.
  * ``CachedModelClient`` — replays previously recorded model outputs from a JSONL
    cache keyed by ``case_id``. This is how a real-model run is scored reproducibly:
    the (non-deterministic) model call happens ONCE, its output is frozen to disk, and
    all scoring is deterministic over the frozen file.
  * ``MockModelClient`` — a deterministic offline stub (delegates to the frozen TAP-E1
    deterministic interpreter). CLEARLY NOT a real model; used only by tests so the
    harness is exercisable without network access. Never used for a verdict.

HONESTY: in this environment no Anthropic API key is available, so the real-model
outputs scored here were produced by the *in-session agent model* (claude-opus-4-8)
acting as the interpreter and cached to ``cache/agent_model_outputs.jsonl``. That is a
real LLM performing the interpretation, but it is NOT an independent API run, and the
same model both authored the corpus and interpreted it — see the leakage audit and the
experiment report for why this bounds the claim.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest

MODEL_CORE_KEYS = (
    "raw_intent", "primary_objective", "task_type", "requested_output",
    "target_object", "entities", "explicit_constraints", "temporal_constraints",
    "stated_assumptions", "references", "interpretation_status",
)


@dataclass(frozen=True)
class ModelResult:
    case_id: str
    core: Mapping[str, object]
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    source: str          # "api" | "cache" | "mock"

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _estimate_tokens(text: str) -> int:
    # rough, provider-agnostic estimate (~4 chars/token); used for the cost report
    return max(1, len(text) // 4)


class ModelClient:
    name = "abstract"

    def interpret(self, request: RawUserRequest) -> ModelResult:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Real API client (used when a key is present)                                #
# --------------------------------------------------------------------------- #

class AnthropicModelClient(ModelClient):
    """Real Anthropic API interpreter. Requires ``ANTHROPIC_API_KEY``. Not exercised
    in this environment (no key); kept ready and behind ``is_available``."""
    name = "anthropic-api"

    def __init__(self, model: str = "claude-opus-4-8", record_path: Optional[str] = None):
        self.model = model
        self.record_path = record_path

    @staticmethod
    def is_available() -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def interpret(self, request: RawUserRequest) -> ModelResult:  # pragma: no cover
        import anthropic  # imported lazily so the package works without the SDK

        from truth_assurance_pipeline.tap_e1_1_realmodel.prompts import build_prompt
        prompt = build_prompt(request)
        client = anthropic.Anthropic()
        t0 = time.time()
        resp = client.messages.create(
            model=self.model, max_tokens=1200,
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}])
        latency = (time.time() - t0) * 1000.0
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        core = _parse_json_object(text)
        usage = getattr(resp, "usage", None)
        pt = getattr(usage, "input_tokens", _estimate_tokens(prompt["user"]))
        ct = getattr(usage, "output_tokens", _estimate_tokens(text))
        res = ModelResult(request.request_id, core, self.model, latency, pt, ct, "api")
        if self.record_path:
            _append_cache(self.record_path, res, prompt)
        return res


# --------------------------------------------------------------------------- #
# Cached client (replay recorded real-model outputs)                          #
# --------------------------------------------------------------------------- #

class CachedModelClient(ModelClient):
    """Replays recorded model outputs. Deterministic and offline."""
    name = "cache"

    def __init__(self, cache_path: str):
        self.cache_path = cache_path
        self._by_id: Dict[str, dict] = {}
        if os.path.exists(cache_path):
            with open(cache_path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    self._by_id[rec["case_id"]] = rec

    def has(self, case_id: str) -> bool:
        return case_id in self._by_id

    def covered_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._by_id))

    def interpret(self, request: RawUserRequest) -> ModelResult:
        rec = self._by_id.get(request.request_id)
        if rec is None:
            raise KeyError(f"no cached model output for case {request.request_id!r}")
        return ModelResult(
            request.request_id, rec["output"], rec.get("model", "unknown"),
            float(rec.get("latency_ms", 0.0)),
            int(rec.get("prompt_tokens", 0)), int(rec.get("completion_tokens", 0)),
            "cache")


# --------------------------------------------------------------------------- #
# Mock client (tests only)                                                     #
# --------------------------------------------------------------------------- #

class MockModelClient(ModelClient):
    """Deterministic stub that fabricates a model core from the frozen TAP-E1
    deterministic interpreter. NOT a real model; for tests/regression only."""
    name = "mock"

    def interpret(self, request: RawUserRequest) -> ModelResult:
        from truth_assurance_pipeline.tap_e1_intent.interpreter import (
            IntentUnderstandingLayer, config,
        )
        rec = IntentUnderstandingLayer(config("V2")).interpret(request)
        core = {
            "raw_intent": rec.primary_objective,
            "primary_objective": rec.primary_objective,
            "task_type": rec.task_type.value,
            "requested_output": rec.requested_output,
            "target_object": rec.target_object,
            "entities": [e.text for e in rec.entities],
            "explicit_constraints": [{"text": c.text, "polarity": c.polarity.value}
                                     for c in rec.explicit_constraints],
            "temporal_constraints": [t.text for t in rec.temporal_constraints],
            "stated_assumptions": list(rec.stated_assumptions),
            "references": list(rec.references),
            "interpretation_status": rec.interpretation_status.value,
        }
        return ModelResult(request.request_id, core, "mock-deterministic", 0.0,
                           0, 0, "mock")


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #

def _parse_json_object(text: str) -> dict:  # pragma: no cover - api path
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("model did not return a JSON object")
    return json.loads(text[start:end + 1])


def _append_cache(path: str, res: ModelResult, prompt: Mapping[str, str]) -> None:  # pragma: no cover
    rec = {
        "case_id": res.case_id, "model": res.model,
        "prompt_hash": _estimate_tokens(prompt["user"]),
        "latency_ms": res.latency_ms, "prompt_tokens": res.prompt_tokens,
        "completion_tokens": res.completion_tokens, "output": dict(res.core),
    }
    with open(path, "a") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def default_client(cache_path: str) -> ModelClient:
    """Pick the best available client: real API if a key exists, else the cache."""
    if AnthropicModelClient.is_available():  # pragma: no cover - no key here
        return AnthropicModelClient(record_path=cache_path)
    return CachedModelClient(cache_path)
