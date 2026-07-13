"""Tests for the cross-model reproducibility analysis (honest, no fabrication)."""

from __future__ import annotations

import pathlib
import sys

_RUNPOD = pathlib.Path(__file__).resolve().parents[1] / "runpod"
if str(_RUNPOD) not in sys.path:
    sys.path.insert(0, str(_RUNPOD))

import runpod_common as RC          # noqa: E402
import cross_model as CM            # noqa: E402


def _cells(orig_acc, protected_delta, protected_dec=1.0, unaware_dec=0.97):
    def cell(method, budget, acc, dec):
        return {"method": method, "budget": budget, "task_accuracy": acc,
                "decision_preservation": dec, "envelope_preservation": 1.0,
                "token_reduction": 0.4, "cost_estimate_usd": 0.04, "n_contexts": 77,
                "tool_call_correctness": 1.0, "hallucination_rate": 0.0,
                "instruction_following_failure": 1.0, "mean_latency_ms": 2000.0,
                "per_task_accuracy": {t: 1.0 for t in CM._TASK_TO_CAUSE}}
    cells = [cell("original", 0.0, orig_acc, 1.0), cell("structural_only", 0.0, orig_acc, 1.0)]
    for b in CM.BUDGETS:
        cells.append(cell("protected", b, orig_acc + protected_delta, protected_dec))
        cells.append(cell("protection_unaware", b, orig_acc + protected_delta, unaware_dec))
    return cells


def _model(short, orig_acc=0.5, protected_delta=0.0, protected_dec=1.0, unaware_dec=0.97,
           is_real=True):
    return CM.ModelResult(model_id="org/" + short, model_revision="rev", is_real=is_real,
                          cells=_cells(orig_acc, protected_delta, protected_dec, unaware_dec),
                          records_path=None, short=short)


# ---- real committed Qwen result ----
def test_qwen_result_loads_and_is_insufficient_alone():
    d = RC.EXPERIMENT_DIR / "results" / "qwen7b_primary_real_llm"
    models = CM.discover([str(d)])
    assert len(models) == 1 and models[0].is_real
    a = CM.analyze(models)
    assert a["replication"]["verdict"] == CM.INSUFFICIENT_MODELS   # 1 real model
    # Qwen: protected slightly beats original, protected decisions 100% > unaware
    f = a["forest"][0]
    assert f["delta_mean"] > 0
    assert a["decision_comparison"][0]["budgets"][0.4]["protected"] == 1.0
    assert a["decision_comparison"][0]["budgets"][0.4]["protection_unaware"] < 1.0


def test_render_investor_md_runs():
    d = RC.EXPERIMENT_DIR / "results" / "qwen7b_primary_real_llm"
    md = CM.render_investor_md(CM.discover([str(d)]))
    assert "CROSS_MODEL_RESULTS" in md and "INSUFFICIENT_MODELS" in md


# ---- verdict logic ----
def test_consistent_when_all_replicate():
    models = [_model("A", protected_delta=0.0), _model("B", protected_delta=0.01)]
    assert CM.verdict(models)["verdict"] == CM.CONSISTENT_REPLICATION


def test_failed_when_none_replicate():
    # big utility regression -> not replicating
    models = [_model("A", protected_delta=-0.2), _model("B", protected_delta=-0.3)]
    assert CM.verdict(models)["verdict"] == CM.FAILED_REPLICATION


def test_model_specific_when_minority_replicate():
    models = [_model("A", protected_delta=0.0), _model("B", protected_delta=-0.5)]
    assert CM.verdict(models)["verdict"] == CM.MODEL_SPECIFIC


def test_partial_when_majority_replicate():
    models = [_model("A", protected_delta=0.0), _model("B", protected_delta=0.0),
              _model("C", protected_delta=-0.5)]
    assert CM.verdict(models)["verdict"] == CM.PARTIAL_REPLICATION


def test_non_real_models_excluded_from_verdict():
    models = [_model("A", protected_delta=0.0, is_real=True),
              _model("MOCK", protected_delta=0.0, is_real=False)]
    v = CM.verdict(models)
    assert v["n_real_models"] == 1 and v["verdict"] == CM.INSUFFICIENT_MODELS


def test_protection_must_beat_unaware_to_replicate():
    # if protection-unaware also preserves decisions (no advantage), does not replicate
    m = _model("A", protected_delta=0.0, protected_dec=1.0, unaware_dec=1.0)
    assert CM._model_replicates(m)["replicates"] is False


# ---- discovery honesty ----
def test_discover_skips_missing_and_empty(tmp_path):
    (tmp_path / "empty").mkdir()
    models = CM.discover([str(tmp_path / "does_not_exist"), str(tmp_path / "empty")])
    assert models == []


def test_failure_taxonomy_counts_decision_flips():
    tax = CM.failure_taxonomy([_model("A", unaware_dec=0.97)])
    # 3 budgets * (1-0.97)*77 ~ 3 * 2 = ~6 flips counted
    assert tax["A"]["counts"]["decision_flip"] >= 1
