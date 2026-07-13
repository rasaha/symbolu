"""Tests for the RunPod execution machinery (everything validatable without a GPU)."""

from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

_RUNPOD = pathlib.Path(__file__).resolve().parents[1] / "runpod"
if str(_RUNPOD) not in sys.path:
    sys.path.insert(0, str(_RUNPOD))

import runpod_common as RC          # noqa: E402
import run_benchmark as RB          # noqa: E402
import verify_results as V          # noqa: E402
import run_manifest as M            # noqa: E402
import collect as CO                # noqa: E402
import probe_environment as PE      # noqa: E402
from actiongate_context_ablation import real_llm_bench as R  # noqa: E402


def _has_cuda_model() -> bool:
    """True only on a real pod with CUDA + a local Qwen model present."""
    if not os.environ.get("MODEL_DIR"):
        return False
    try:
        import torch
    except Exception:
        return False
    return bool(torch.cuda.is_available()) and PE.model_complete(os.environ["MODEL_DIR"])[0]


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "t")
    monkeypatch.setenv("RUN_KIND", "SMOKE_ONLY")
    monkeypatch.setenv("ALLOW_MOCK", "1")
    monkeypatch.setenv("ALLOW_DIRTY", "1")
    monkeypatch.setenv("CONTEXTS_LIMIT", "5")
    monkeypatch.setenv("BUDGETS", "0.3")
    monkeypatch.setenv("METHODS", "original,protected")
    return RC.load_config()


# ---- config / fingerprint / keys ----
def test_defaults_reproduce_primary(monkeypatch):
    for k in ("BUDGETS", "METHODS", "MODEL_ID", "RUN_KIND", "RESULTS_ROOT", "RUN_ID"):
        monkeypatch.delenv(k, raising=False)
    c = RC.load_config()
    assert c["budgets"] == [0.2, 0.3, 0.4]
    assert c["methods"] == ["original", "structural_only", "protected", "protection_unaware"]
    assert c["model_id"] == RC.PRIMARY_MODEL
    assert c["run_kind"] == RC.RUN_KIND_PRIMARY


def test_frozen_fingerprint_stable_and_structured():
    a, b = RC.frozen_fingerprint(), RC.frozen_fingerprint()
    assert a["fingerprint"] == b["fingerprint"] and a["fingerprint"].startswith("sha256:")
    assert "compressor.py" in a["files"] and "real_llm_bench.py" in a["files"]


def test_example_key_format():
    k = RC.example_key("run", "revABC", "protected", 0.3, "ctx1", "reasoning")
    assert k == "run|revABC|protected|0.3000|ctx1|reasoning"


# ---- atomic store ----
def test_atomic_append_and_read(tmp_path):
    p = tmp_path / "r.jsonl"
    RC.atomic_append_jsonl(p, {"a": 1})
    RC.atomic_append_jsonl(p, {"a": 2})
    assert [r["a"] for r in RC.read_records(p)] == [1, 2]


def test_read_records_drops_torn_line(tmp_path):
    p = tmp_path / "r.jsonl"
    RC.atomic_append_jsonl(p, {"a": 1})
    with open(p, "a") as f:
        f.write('{"a": 2, "partial"')   # crash-torn line
    assert [r["a"] for r in RC.read_records(p)] == [1]


# ---- redaction ----
def test_secret_redaction(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_supersecret")
    assert "hf_supersecret" not in RC.redact("error using hf_supersecret here")
    assert "***REDACTED***" in RC.redact("token hf_supersecret")


# ---- durable run + resume ----
def test_run_persists_and_resumes(cfg):
    out1 = RB.run(cfg)
    assert out1["new_records"] > 0
    out2 = RB.run(cfg)
    assert out2["new_records"] == 0                # resume skips completed keys
    assert out2["total_records"] == out1["total_records"]


def test_aggregation_matches_frozen_harness(tmp_path, monkeypatch):
    # durable records aggregated == frozen R.run() cells, on identical methods/budgets
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "eq")
    monkeypatch.setenv("RUN_KIND", "SMOKE_ONLY")
    monkeypatch.setenv("ALLOW_MOCK", "1")
    monkeypatch.setenv("ALLOW_DIRTY", "1")
    monkeypatch.setenv("CONTEXTS_LIMIT", "6")
    monkeypatch.setenv("BUDGETS", "0.1,0.2,0.3,0.4,0.5,0.6")
    monkeypatch.setenv("METHODS", "original,structural_only,protected,protection_unaware")
    c = RC.load_config()
    RB.run(c)
    durable = RB.build_result(RC.read_records(RC.records_path(c)))
    ref = R.run(contexts_limit=6)
    d = {(x.method, round(x.budget, 4)): x for x in durable.cells}
    for rc in ref.cells:
        a = d[(rc.method, round(rc.budget, 4))]
        for f in ("token_reduction", "decision_preservation", "envelope_preservation",
                  "task_accuracy", "tool_call_correctness", "hallucination_rate"):
            assert round(getattr(a, f), 6) == round(getattr(rc, f), 6), (rc.method, rc.budget, f)


# ---- guards ----
def test_duplicate_key_differing_prompt_rejected(cfg):
    RB.run(cfg)
    rp = RC.records_path(cfg)
    rec = RC.read_records(rp)[0]
    bad = dict(rec, prompt_hash="sha256:DIFFERENT")
    RC.atomic_append_jsonl(rp, bad)          # inject a conflicting duplicate
    with pytest.raises(RuntimeError, match="duplicate result key"):
        RB.run(cfg)


def test_resume_rejects_changed_fingerprint(cfg):
    RB.run(cfg)
    cp = RC.config_path(cfg)
    d = json.loads(cp.read_text())
    d["frozen_fingerprint"] = "sha256:TAMPERED"
    cp.write_text(json.dumps(d))
    with pytest.raises(RuntimeError, match="resume guard"):
        RB.run(cfg)


def test_dirty_tree_guard(cfg, monkeypatch):
    monkeypatch.setenv("ALLOW_DIRTY", "0")
    c = RC.load_config()
    monkeypatch.setattr(RC, "git_state", lambda: {"branch": "b", "commit": "c", "dirty": True})
    with pytest.raises(RuntimeError, match="dirty"):
        RB.run(c)


def test_primary_rejects_mock_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path))
    monkeypatch.setenv("ALLOW_MOCK", "0")
    monkeypatch.setenv("RUN_KIND", "PRIMARY")
    c = RC.load_config()
    # no torch/GPU here -> real client construction must FAIL LOUDLY (never silently mock)
    with pytest.raises(Exception):
        RB.build_client(c)


# ---- verify / manifest / collect ----
def test_verify_ok_and_manifest(cfg):
    RB.run(cfg)
    vr = V.verify(cfg)
    assert vr["ok"] and vr["n_missing"] == 0
    man = M.build_manifest(cfg)
    assert man["n_records"] == vr["n_records"] and man["checksums"]


def test_verify_detects_missing(cfg):
    RB.run(cfg)
    rp = RC.records_path(cfg)
    recs = RC.read_records(rp)[:-1]              # drop one -> incomplete
    rp.write_text("\n".join(json.dumps(r, sort_keys=True) for r in recs) + "\n")
    vr = V.verify(cfg)
    assert not vr["ok"] and vr["n_missing"] >= 1


def test_verify_detects_smoke_primary_mix(cfg):
    RB.run(cfg)
    rp = RC.records_path(cfg)
    rec = dict(RC.read_records(rp)[0], run_kind="PRIMARY", key="x|y|z|0|q|r")
    RC.atomic_append_jsonl(rp, rec)
    vr = V.verify(cfg)
    assert not vr["ok"] and any("mixed" in p for p in vr["problems"])


def test_collect_builds_reports(tmp_path, monkeypatch):
    # collect is only run on the full primary method set; report renderer needs all 4
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "coll")
    monkeypatch.setenv("RUN_KIND", "SMOKE_ONLY")
    monkeypatch.setenv("ALLOW_MOCK", "1")
    monkeypatch.setenv("ALLOW_DIRTY", "1")
    monkeypatch.setenv("CONTEXTS_LIMIT", "5")
    monkeypatch.setenv("BUDGETS", "0.3")
    monkeypatch.setenv("METHODS", "original,structural_only,protected,protection_unaware")
    cfg = RC.load_config()
    RB.run(cfg)
    rep = CO.build_reports(cfg, make_plots=False)
    rd = RC.run_dir(cfg)
    assert (rd / "results.json").exists() and (rd / "results.csv").exists()
    assert (rd / "REAL_LLM_RESULTS.md").exists()
    assert rep["recommendation"] == "BLOCKED_NO_MODEL"    # mock -> never GO/LIMITED_GO/STOP


# ---- probe failure paths ----
def test_probe_reports_no_gpu(cfg):
    fatal = PE.check(cfg, require_gpu=True, require_model=False)
    assert any("CUDA" in f for f in fatal)               # no GPU in this env


def test_probe_incomplete_model(cfg):
    fatal = PE.check(cfg, require_gpu=False, require_model=True)
    assert any("incomplete" in f for f in fatal)


def test_model_complete_false_when_missing(tmp_path):
    ok, msg = PE.model_complete(str(tmp_path / "nope"))
    assert not ok


# ---- gated CUDA/Qwen test (skips honestly) ----
@pytest.mark.skipif(not _has_cuda_model(),
                    reason="no CUDA GPU + local Qwen model available")
def test_real_qwen_generates():   # pragma: no cover - only runs on a real pod
    from actiongate_context_ablation.llm_client import TransformersLLMClient
    client = TransformersLLMClient(os.environ["MODEL_DIR"], device="cuda")
    resp = client.generate("You are helpful.", "Reply with the word OK.")
    assert resp.is_real and resp.completion_tokens > 0
