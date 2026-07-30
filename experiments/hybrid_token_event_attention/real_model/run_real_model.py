"""
run_real_model.py — RM1 single entrypoint (RM1 §3, §4, §16).

    python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
        --model-id "$UGENCE_REAL_MODEL_ID" --mode smoke --limit 20

Flow: probe environment → RESOURCE_MANIFEST.json → gate/load the ACTUAL model (or RESOURCE_BLOCKED) →
one-instance forward-pass proof → run RM0–RM7 → metrics/controls/acceptance → artifacts + report.

If torch/transformers/weights/hardware are unavailable the harness does NOT fabricate a result: it
writes RESOURCE_BLOCKED with exact remediation and stops before any scientific claim. A MockBackend
exists ONLY for `--self-test-mock` (a clearly-labelled wiring smoke) and the unit tests — it is never
written as a real-model result.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional

from .hf_backend import probe_environment, load_backend, ResourceBlocked, Backend

HERE = os.path.dirname(__file__)
DEFAULT_OUT = os.path.join(HERE, "results")
CHECKPOINT = os.path.join(HERE, "results", "event_checkpoint.json")

SCOPE_STATEMENT = (
    "RM1 tests an actual frozen token-language model inside the external governed dual-domain "
    "architecture. It does not validate FSCS, model-weight adaptation, production deployment, or "
    "universal superiority of event attention.")


@dataclass
class RealModelConfig:
    model_id: str = ""
    revision: Optional[str] = None
    dataset_jsonl: Optional[str] = None
    mode: str = "smoke"
    limit: int = 20
    seed: int = 0
    device: str = "auto"
    dtype: str = "auto"
    load_in_4bit: bool = False
    max_input_tokens: int = 2048
    max_new_tokens: int = 256
    clarification_limit: int = 1
    output_dir: str = DEFAULT_OUT
    offline: bool = False
    resume: bool = False
    trust_remote_code: bool = False
    attn_implementation: str = "eager"
    # internal / non-CLI:
    K: int = 8
    max_extraction_attempts: int = 2
    run_generative: bool = True
    min_confidence: float = 0.5
    mock_responder: Optional[Callable] = None

    def redacted(self) -> Dict:
        d = {k: v for k, v in asdict(self).items() if k != "mock_responder"}
        return d


def _parse_args(argv) -> RealModelConfig:
    p = argparse.ArgumentParser(prog="run_real_model")
    p.add_argument("--model-id", default=os.environ.get("UGENCE_REAL_MODEL_ID", ""))
    p.add_argument("--revision", default=os.environ.get("UGENCE_MODEL_REVISION"))
    p.add_argument("--dataset-jsonl", default=None)
    p.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default="auto")
    p.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="auto")
    p.add_argument("--load-in-4bit", action="store_true")
    p.add_argument("--max-input-tokens", type=int, default=2048)
    p.add_argument("--max-new-tokens", type=int, default=256)
    p.add_argument("--clarification-limit", type=int, default=1)
    p.add_argument("--output-dir", default=DEFAULT_OUT)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--trust-remote-code", action="store_true")
    p.add_argument("--self-test-mock", action="store_true",
                   help="run a clearly-labelled MOCK wiring smoke (NOT a real-model result)")
    a = p.parse_args(argv)
    cfg = RealModelConfig(
        model_id=a.model_id, revision=a.revision, dataset_jsonl=a.dataset_jsonl, mode=a.mode,
        limit=a.limit, seed=a.seed, device=a.device, dtype=a.dtype, load_in_4bit=a.load_in_4bit,
        max_input_tokens=a.max_input_tokens, max_new_tokens=a.max_new_tokens,
        clarification_limit=a.clarification_limit, output_dir=a.output_dir, offline=a.offline,
        resume=a.resume, trust_remote_code=a.trust_remote_code)
    cfg._self_test_mock = a.self_test_mock  # type: ignore
    return cfg


def _write_json(path: str, obj: Dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def _resource_manifest(env: Dict, cfg: RealModelConfig) -> Dict:
    return {"config": cfg.redacted(), "environment": env, "scope_statement": SCOPE_STATEMENT}


# ------------------------------------------------------------------ blocked report
def _blocked_report(payload: Dict, env: Dict) -> str:
    L = []
    a = L.append
    a("# RM1 Real-Model Validation Report\n")
    a("> " + SCOPE_STATEMENT + "\n")
    a("## Status: RESOURCE_BLOCKED\n")
    a("The RM1 harness is complete and unit-tested, but an ACTUAL open-weight model could not be "
      "loaded in this environment. No real-model scientific claim is made. Per RM1 §2/§16 the "
      "harness stops here rather than substitute the stand-in.\n")
    a("### Block detail\n```json\n" + json.dumps(payload, indent=2) + "\n```\n")
    a("### Detected environment\n```json\n" + json.dumps(env, indent=2) + "\n```\n")
    a("### Remediation\n")
    for step in payload.get("remediation", []):
        a(f"- {step}")
    a("\n### Recommended command\n```\n" + payload.get("recommended_command", "") + "\n```\n")
    a("\n---\n")
    a("Actual model:\n    " + (payload.get("requested_model") or "<unset>") + "\n")
    a("Actual-model execution:\n    RESOURCE_BLOCKED\n")
    a("Corpus:\n    CONTROLLED (not executed — blocked before inference)\n")
    for line in ("Token-only result", "Retrieval result", "Governed-event deterministic result",
                 "Router-gated event-attention result", "Event attention incremental relational gain",
                 "Oracle-to-predicted construction gap", "Required-event survival",
                 "Evidence-ID preservation", "Unauthorized-event inclusion",
                 "Explanation supported precision", "Unsupported-claim recall"):
        a(f"{line}:\n    RESOURCE_BLOCKED (not measured)\n")
    a("Best architecture:\n    RESOURCE_BLOCKED\n")
    a("Primary bottleneck:\n    resources\n")
    a("Evidence classification:\n    RESOURCE BLOCKED\n")
    a("Authorized next step:\n    hardware rerun (load an actual open-weight model on a suitable "
      "machine with deps installed; see remediation)\n")
    a("\n> " + SCOPE_STATEMENT + "\n")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None, cfg: Optional[RealModelConfig] = None) -> Dict:
    if cfg is None:
        cfg = _parse_args(argv or [])
    env = probe_environment()
    os.makedirs(cfg.output_dir, exist_ok=True)
    _write_json(os.path.join(cfg.output_dir, "RESOURCE_MANIFEST.json"),
                _resource_manifest(env, cfg))

    # self-test mock wiring smoke (explicitly NOT a real result)
    if getattr(cfg, "_self_test_mock", False):
        return _run_mock_smoke(cfg, env)

    # gate + load the ACTUAL model
    try:
        backend = load_backend(cfg, env)
    except ResourceBlocked as rb:
        payload = rb.payload()
        _write_json(os.path.join(cfg.output_dir, "REAL_MODEL_RESULTS.json"),
                    {"status": "RESOURCE_BLOCKED", "block": payload, "environment": env,
                     "scope_statement": SCOPE_STATEMENT})
        with open(os.path.join(cfg.output_dir, "REAL_MODEL_VALIDATION_REPORT.md"), "w") as f:
            f.write(_blocked_report(payload, env))
        # empty audit artifacts
        open(os.path.join(cfg.output_dir, "REAL_MODEL_TRACES.jsonl"), "a").close()
        open(os.path.join(HERE, "quarantine", "QUARANTINE.jsonl"), "a").close()
        print("RESOURCE_BLOCKED:", payload["reason"])
        return {"status": "RESOURCE_BLOCKED", "block": payload}

    # real model loaded — run the study (this branch executes only on a suitable machine)
    return _run_study(backend, cfg, env, real=True)


def _run_mock_smoke(cfg: RealModelConfig, env: Dict) -> Dict:
    from .hf_backend import MockBackend
    from .mock_corpus import make_mock_responder
    from . import evaluation as E
    models = E.get_event_models(seed=cfg.seed, epochs=8, checkpoint_path=CHECKPOINT)
    held = models["held"][: cfg.limit]
    results = []
    traces_path = os.path.join(cfg.output_dir, "MOCK_HARNESS_TRACES.jsonl")
    with open(traces_path, "w") as tf:
        for inst in held:
            backend = MockBackend(responder=make_mock_responder(inst))
            ir = E.run_instance(backend, inst, models, cfg)
            results.append(ir)
            tf.write(json.dumps({"instance_id": ir.instance_id, "family": ir.task_family,
                                 "route": ir.route, "answers": ir.answers,
                                 "admitted_ids": ir.admitted_ids,
                                 "required_survival": ir.required_survival}, default=str) + "\n")
    metrics = E.aggregate(results, generative=True)
    xm = E.extraction_metrics(results, held)
    controls = E.causal_controls_rm(models, held, cfg)
    acc = E.acceptance(metrics, xm)
    out = {"status": "MOCK_HARNESS_SMOKE",
           "WARNING": "MockBackend wiring proof — NOT a real-model result and NOT a scientific claim.",
           "backend": MockBackend().info(), "event_checkpoint_hash": models["hash"],
           "metrics": metrics, "extraction_metrics": xm, "causal_controls": controls,
           "acceptance": acc, "scope_statement": SCOPE_STATEMENT}
    _write_json(os.path.join(cfg.output_dir, "MOCK_HARNESS_SMOKE.json"), out)
    print("MOCK_HARNESS_SMOKE complete — invariants_hold =", controls["invariants_hold"])
    return out


def _run_study(backend: Backend, cfg: RealModelConfig, env: Dict, real: bool) -> Dict:
    from . import evaluation as E
    proof = backend.forward_probe("Purchases above $50,000 require finance-director approval.")
    models = E.get_event_models(seed=cfg.seed, epochs=20, checkpoint_path=CHECKPOINT)
    held = models["held"]
    held = held[: cfg.limit] if cfg.mode == "smoke" else held
    results, traces = [], []
    for inst in held:
        ir = E.run_instance(backend, inst, models, cfg)
        results.append(ir)
        traces.append({"instance_id": ir.instance_id, "family": ir.task_family, "route": ir.route,
                       "answers": ir.answers, "admitted_ids": ir.admitted_ids,
                       "faithfulness": ir.faithfulness, "trace": ir.trace})
    metrics = E.aggregate(results, generative=True)
    xm = E.extraction_metrics(results, held)
    controls = E.causal_controls_rm(models, held, cfg)
    acc = E.acceptance(metrics, xm)
    out = {"status": "REAL_MODEL_RUN" if real else "MOCK_RUN", "execution_proof": proof,
           "model": backend.info(), "event_checkpoint_hash": models["hash"], "mode": cfg.mode,
           "metrics": metrics, "extraction_metrics": xm, "causal_controls": controls,
           "acceptance": acc, "environment": env, "scope_statement": SCOPE_STATEMENT}
    _write_json(os.path.join(cfg.output_dir, "REAL_MODEL_RESULTS.json"), out)
    with open(os.path.join(cfg.output_dir, "REAL_MODEL_TRACES.jsonl"), "w") as f:
        for t in traces:
            f.write(json.dumps(t, default=str) + "\n")
    print(f"{out['status']} complete — model={backend.info().get('model_id')} "
          f"params={backend.info().get('param_count')}")
    return out


if __name__ == "__main__":
    result = main(sys.argv[1:])
    if result.get("status") == "RESOURCE_BLOCKED":
        sys.exit(3)   # distinct RESOURCE_BLOCKED sentinel
