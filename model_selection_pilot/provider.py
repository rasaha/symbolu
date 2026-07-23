"""Execution adapters for the shadow pilot.

Three kinds of adapter:

  * REAL adapters (Anthropic / OpenAI / Bedrock) -- genuinely ready to run via
    stdlib urllib (proxy-aware). They are INERT without credentials: available()
    returns (False, reason) and generate() refuses to run. No key is ever read
    from anywhere but the environment; no secret is printed.

  * STUB adapter -- a DETERMINISTIC OFFLINE MOCK used ONLY to self-test the
    pipeline (scoring, routing, ablations, guards) when no real model can run.
    Its outputs are SYNTHETIC and MUST NOT be interpreted as real-model evidence.
    It is the only adapter that (as a mock) consults task ground truth, in order
    to fabricate a skill-degraded but gradeable response. The routing policy never
    sees any of this -- the routing-time information boundary is unaffected.

The pilot is BLOCKED for real execution in this environment (see PILOT_STATUS.md);
resolve_adapters() therefore returns only the stub, in clearly-labeled self-test
mode. Supplying a provider key flips the corresponding real adapter to available.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from model_selection_pilot.common import approx_tokens, clamp, det_signed, det_unit


@dataclass
class GenResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    retries: int = 0
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class ModelAdapter:
    """Abstract execution adapter. Subclasses implement available() and generate()."""

    id: str = "abstract"
    provider: str = "abstract"
    is_real: bool = False

    def available(self) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError

    def generate(self, prompt: str, schema: Optional[Dict[str, Any]], max_tokens: int) -> GenResult:
        raise NotImplementedError

    def self_assess(self, task_view: Dict[str, Any]) -> Dict[str, Any]:
        """Bounded cold-start self-assessment (task-shape fields ONLY).

        Real adapters override this with an actual preflight call. The default is
        a neutral 'medium difficulty' assessment. Never returns forbidden fields.
        """
        size = task_view.get("input_tokens_k", 0.0)
        return {"anticipated_reasoning_difficulty": "medium",
                "suggested_decomposition": "decompose" if size > 6 else "single_pass",
                "likely_tool_requirement": task_view["task_class"] in ("long_document_qa", "grounded_comparison"),
                "anticipated_execution_weakness": "none",
                "recommended_prompting_strategy": "structured_json"}


# ---------------------------------------------------------------------------
# REAL adapters (ready-to-run, inert without keys)
# ---------------------------------------------------------------------------
def _proxy_opener() -> urllib.request.OpenerDirector:
    # honor HTTPS_PROXY so real calls work inside the sandbox network policy
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
    return urllib.request.build_opener(*handlers)


def _post_json(url: str, headers: Dict[str, str], body: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    with _proxy_opener().open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class AnthropicAdapter(ModelAdapter):
    is_real = True
    provider = "anthropic"

    def __init__(self, model_id: str, api_version: str = "2023-06-01"):
        self.id = model_id
        self.api_version = api_version

    def available(self) -> Tuple[bool, Optional[str]]:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False, "ANTHROPIC_API_KEY not set"
        return True, None

    def generate(self, prompt, schema, max_tokens) -> GenResult:
        ok, reason = self.available()
        if not ok:
            return GenResult("", 0, 0, 0.0, error=f"unavailable: {reason}")
        headers = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": self.api_version}
        body = {"model": self.id, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        t0 = time.time()
        try:
            resp = _post_json("https://api.anthropic.com/v1/messages", headers, body)
        except Exception as e:  # pragma: no cover - network path
            return GenResult("", approx_tokens(prompt), 0, (time.time() - t0) * 1000, error=str(e)[:200])
        text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        usage = resp.get("usage", {})
        return GenResult(text, usage.get("input_tokens", approx_tokens(prompt)),
                         usage.get("output_tokens", approx_tokens(text)),
                         (time.time() - t0) * 1000, raw={"stop_reason": resp.get("stop_reason")})


class OpenAIAdapter(ModelAdapter):
    is_real = True
    provider = "openai"

    def __init__(self, model_id: str):
        self.id = model_id

    def available(self) -> Tuple[bool, Optional[str]]:
        if not os.environ.get("OPENAI_API_KEY"):
            return False, "OPENAI_API_KEY not set"
        return True, None

    def generate(self, prompt, schema, max_tokens) -> GenResult:
        ok, reason = self.available()
        if not ok:
            return GenResult("", 0, 0, 0.0, error=f"unavailable: {reason}")
        headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
        body = {"model": self.id, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        if schema is not None:
            body["response_format"] = {"type": "json_object"}
        t0 = time.time()
        try:
            resp = _post_json("https://api.openai.com/v1/chat/completions", headers, body)
        except Exception as e:  # pragma: no cover - network path
            return GenResult("", approx_tokens(prompt), 0, (time.time() - t0) * 1000, error=str(e)[:200])
        text = resp["choices"][0]["message"]["content"]
        usage = resp.get("usage", {})
        return GenResult(text, usage.get("prompt_tokens", approx_tokens(prompt)),
                         usage.get("completion_tokens", approx_tokens(text)),
                         (time.time() - t0) * 1000)


class BedrockAdapter(ModelAdapter):
    """AWS Bedrock (requires boto3 + valid AWS creds + granted model access)."""
    is_real = True
    provider = "bedrock"

    def __init__(self, model_id: str, region: str = "us-east-1"):
        self.id = model_id
        self.region = region

    def available(self) -> Tuple[bool, Optional[str]]:
        if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
            return False, "AWS credentials not set"
        try:
            import boto3  # noqa: F401
        except Exception:
            return False, "boto3 not installed"
        return True, None  # note: does not prove model access is granted

    def generate(self, prompt, schema, max_tokens) -> GenResult:  # pragma: no cover - network path
        ok, reason = self.available()
        if not ok:
            return GenResult("", 0, 0, 0.0, error=f"unavailable: {reason}")
        import boto3
        client = boto3.client("bedrock-runtime", region_name=self.region)
        t0 = time.time()
        try:
            resp = client.converse(modelId=self.id,
                                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                                    inferenceConfig={"maxTokens": max_tokens})
        except Exception as e:
            return GenResult("", approx_tokens(prompt), 0, (time.time() - t0) * 1000, error=str(e)[:200])
        text = "".join(c.get("text", "") for c in resp["output"]["message"]["content"])
        usage = resp.get("usage", {})
        return GenResult(text, usage.get("inputTokens", approx_tokens(prompt)),
                         usage.get("outputTokens", approx_tokens(text)),
                         (time.time() - t0) * 1000)


REAL_ADAPTER_TYPES = {"anthropic": AnthropicAdapter, "openai": OpenAIAdapter, "bedrock": BedrockAdapter}


# ---------------------------------------------------------------------------
# STUB adapter (offline self-test ONLY -- outputs are synthetic, not evidence)
# ---------------------------------------------------------------------------
# Latent skill per (model_id, task_class) in [0,1]. Heterogeneous by design so
# the pipeline self-test has routing signal. NOT a claim about any real model.
STUB_SKILLS: Dict[str, Dict[str, float]] = {
    "stub_fast_small": {"structured_extraction": 0.62, "classification": 0.80, "summarization": 0.55,
                        "long_document_qa": 0.40, "grounded_comparison": 0.45,
                        "clause_identification": 0.50, "schema_constrained_generation": 0.60},
    "stub_medium": {"structured_extraction": 0.74, "classification": 0.82, "summarization": 0.72,
                    "long_document_qa": 0.66, "grounded_comparison": 0.68,
                    "clause_identification": 0.70, "schema_constrained_generation": 0.78},
    "stub_strong_reason": {"structured_extraction": 0.80, "classification": 0.84, "summarization": 0.82,
                           "long_document_qa": 0.86, "grounded_comparison": 0.85,
                           "clause_identification": 0.83, "schema_constrained_generation": 0.82},
    "stub_long_context": {"structured_extraction": 0.78, "classification": 0.78, "summarization": 0.84,
                          "long_document_qa": 0.88, "grounded_comparison": 0.80,
                          "clause_identification": 0.82, "schema_constrained_generation": 0.74},
    "stub_open_weight": {"structured_extraction": 0.66, "classification": 0.79, "summarization": 0.64,
                         "long_document_qa": 0.55, "grounded_comparison": 0.58,
                         "clause_identification": 0.62, "schema_constrained_generation": 0.68},
}


class StubAdapter(ModelAdapter):
    """DETERMINISTIC OFFLINE MOCK. Produces a skill-degraded, gradeable response
    from task ground truth. For pipeline self-test only; not real-model evidence."""
    is_real = False
    provider = "stub"

    def __init__(self, model_id: str, base_latency_ms: float):
        self.id = model_id
        self.base_latency_ms = base_latency_ms

    def available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    def _skill(self, task_class: str) -> float:
        return STUB_SKILLS.get(self.id, {}).get(task_class, 0.6)

    def self_assess(self, task_view: Dict[str, Any]) -> Dict[str, Any]:
        """Skill-correlated but OVERCONFIDENT self-assessment (mock preflight).

        A genuinely capable model tends to report lower difficulty; overconfidence
        biases the report downward; noise blurs it. Task-shape fields only."""
        tc = task_view["task_class"]
        skill = self._skill(tc)
        raw = (1.0 - skill) - 0.08 + det_signed(self.id, task_view["task_id"], "adv") * 0.12
        difficulty = "low" if raw < 0.28 else "high" if raw > 0.50 else "medium"
        size = task_view.get("input_tokens_k", 0.0)
        return {"anticipated_reasoning_difficulty": difficulty,
                "suggested_decomposition": "decompose" if size > 6 else "single_pass",
                "likely_tool_requirement": tc in ("long_document_qa", "grounded_comparison"),
                "anticipated_execution_weakness": "long-context recall" if size > 6 else "none",
                "recommended_prompting_strategy": "structured_json"}

    def generate_for_task(self, task: Dict[str, Any]) -> GenResult:
        tc = task["task_class"]
        skill = self._skill(tc)
        gt = task["_oracle"]
        n = det_unit(self.id, task["task_id"])  # deterministic per (model, task)
        eff = clamp(skill + det_signed(self.id, task["task_id"], "eff") * 0.08)
        out: Any
        if tc == "structured_extraction" or tc == "schema_constrained_generation":
            fields = gt["fields"]
            out = {}
            for i, (k, v) in enumerate(sorted(fields.items())):
                keep = det_unit(self.id, task["task_id"], k) < eff
                if keep:
                    out[k] = v
                elif det_unit(self.id, task["task_id"], k, "corrupt") < 0.5:
                    out[k] = str(v) + "?"  # corrupted value present but wrong
            # schema-validity: low-skill models sometimes emit invalid JSON
            if tc == "schema_constrained_generation" and det_unit(self.id, task["task_id"], "schema") > eff:
                text = json.dumps(out)[:-1]  # truncated => invalid JSON
                return self._wrap(task, text)
            text = json.dumps(out)
        elif tc == "classification":
            labels = task["label_set"]
            correct = gt["label"]
            if n < eff:
                pick = correct
            else:
                others = [l for l in labels if l != correct] or [correct]
                pick = others[int(det_unit(self.id, task["task_id"], "wrong") * len(others)) % len(others)]
            text = json.dumps({"label": pick})
        elif tc == "summarization":
            facts = gt["key_facts"]
            k = max(1, int(round(len(facts) * eff)))
            covered = facts[:k]
            unsupported = det_unit(self.id, task["task_id"], "hallu") > eff
            claims = list(covered) + (["UNSUPPORTED: " + gt.get("distractor", "unrelated claim")] if unsupported else [])
            text = json.dumps({"summary_points": claims})
        elif tc == "long_document_qa":
            ans_ok = n < eff
            ev_ok = det_unit(self.id, task["task_id"], "ev") < eff
            text = json.dumps({"answer": gt["answer"] if ans_ok else gt["wrong_answer"],
                               "evidence_id": gt["evidence_id"] if ev_ok else "para_0"})
        elif tc == "grounded_comparison":
            text = json.dumps({"verdict": gt["verdict"] if n < eff else gt["wrong_verdict"]})
        elif tc == "clause_identification":
            present = gt["clause_ids"]
            all_ids = task["candidate_clause_ids"]
            picked = [c for c in present if det_unit(self.id, task["task_id"], c) < eff]
            # false positives at low skill
            for c in all_ids:
                if c not in present and det_unit(self.id, task["task_id"], c, "fp") > eff + 0.2:
                    picked.append(c)
            text = json.dumps({"clause_ids": sorted(set(picked))})
        else:
            text = json.dumps({})
        return self._wrap(task, text)

    def _wrap(self, task: Dict[str, Any], text: str) -> GenResult:
        prompt_tokens = approx_tokens(task["input_text"]) + 60
        completion_tokens = approx_tokens(text)
        size = task.get("input_tokens_k", approx_tokens(task["input_text"]) / 1000.0)
        jitter = 1.0 + det_signed(self.id, task["task_id"], "lat") * 0.15
        latency = self.base_latency_ms * (1.0 + size / 8.0) * jitter
        return GenResult(text, prompt_tokens, completion_tokens, round(latency, 1), raw={"stub": True})

    def generate(self, prompt, schema, max_tokens) -> GenResult:  # not used; task-aware path preferred
        return GenResult(json.dumps({}), approx_tokens(prompt), 2, self.base_latency_ms)


# ---------------------------------------------------------------------------
# Availability resolver
# ---------------------------------------------------------------------------
def resolve_adapters(registry: Dict[str, Any]) -> Tuple[Dict[str, ModelAdapter], Dict[str, Any]]:
    """Return {model_id: adapter} plus a status report.

    Real adapters are used where their provider key exists; otherwise the pilot
    falls back to STUB adapters for every model and marks mode=SELF_TEST.
    """
    real: Dict[str, ModelAdapter] = {}
    status: Dict[str, Any] = {"real_available": {}, "mode": None, "notes": []}
    for mid, m in registry["models"].items():
        prov = m["provider_facts"]["provider"]["value"]
        atype = REAL_ADAPTER_TYPES.get(prov)
        if atype is None:
            status["real_available"][mid] = f"no adapter for provider '{prov}'"
            continue
        adapter = atype(m["provider_facts"]["model_version"]["value"])
        ok, reason = adapter.available()
        status["real_available"][mid] = "available" if ok else reason
        if ok:
            real[mid] = adapter

    if len(real) == len(registry["models"]) and real:
        status["mode"] = "REAL"
        return real, status

    # not all real adapters available -> self-test with stubs (never mix, so the
    # counterfactual is internally consistent and clearly labeled non-evidence)
    stubs: Dict[str, ModelAdapter] = {
        mid: StubAdapter("stub_" + m["stub_profile"], m["provider_facts"]["base_latency_ms"]["value"])
        for mid, m in registry["models"].items()}
    status["mode"] = "SELF_TEST"
    status["notes"].append("No complete set of real adapters available; running deterministic "
                           "STUB self-test. Outputs are synthetic and are NOT real-model evidence.")
    return stubs, status
