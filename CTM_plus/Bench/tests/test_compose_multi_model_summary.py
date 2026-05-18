"""CPU regression tests for §20.3 multi-model replication composer.

Pins:

* Reads N per-model `track_e_quality_eval` JSONs and produces a
  merged §20.3.v1 JSON with per-model deltas + a cross-model verdict.
* Cross-model verdict = WORST single-model verdict (one model's
  failure means INT4 doesn't generalize, even if others pass).
* Per-model combined verdict = worst of MMLU and perplexity bands.
* Band thresholds: MMLU GREEN ≥ -1.5pt, YELLOW ≥ -3.0pt; ppl
  GREEN ≤ 1.05, YELLOW ≤ 1.15.
* `--inputs label=path` parsing accepts both labeled and bare paths.
* Composer handles missing fields gracefully — a JSON missing MMLU
  but having perplexity produces a "MEASUREMENT MISSING" MMLU band
  and falls back to the perplexity verdict.

The brief: "Same harness, same eval. Removes the 'one-model demo'
caveat" — these tests pin that the composer renders the partner-
shareable artefact correctly across N models with N being arbitrary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_eval_json(
    path: Path, *, model_id: str,
    baseline_mmlu: float = 0.70, int4_mmlu: float = 0.69,
    baseline_ppl: float = 3.71, int4_ppl: float = 3.80,
) -> None:
    """Synthetic `track_e_quality_eval`-shaped JSON for one model."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "model_id": model_id,
        "dtype": "float16",
        "eval_kinds": ["perplexity", "mmlu"],
        "turboquant_config": {"quant": "int4-per-channel"},
        "perplexity": [
            {"cache_type": "baseline", "text_chars": 1411, "text_tokens": 282,
             "perplexity": baseline_ppl, "nll_per_token": 1.31},
            {"cache_type": "int4-per-channel", "text_chars": 1411,
             "text_tokens": 282, "perplexity": int4_ppl, "nll_per_token": 1.34},
        ],
        "mmlu": [
            {"cache_type": "baseline", "num_questions": 1000,
             "correct": int(baseline_mmlu * 1000), "accuracy": baseline_mmlu,
             "per_subject": {}},
            {"cache_type": "int4-per-channel", "num_questions": 1000,
             "correct": int(int4_mmlu * 1000), "accuracy": int4_mmlu,
             "per_subject": {}},
        ],
        "deltas": {
            "perplexity_ratio": int4_ppl / baseline_ppl,
            "mmlu_accuracy_delta_pt": (int4_mmlu - baseline_mmlu) * 100.0,
        },
    }))


def test_compose_three_models_all_green(tmp_path: Path, capsys):
    """Happy path: 3 models, each within KIVI literature range.
    Cross-model verdict = GREEN."""
    from ctm_bench.scripts import compose_multi_model_summary as comp

    qwen = tmp_path / "qwen" / "results.json"
    llama = tmp_path / "llama" / "results.json"
    mistral = tmp_path / "mistral" / "results.json"
    _write_eval_json(qwen, model_id="Qwen/Qwen2.5-7B-Instruct",
                     baseline_mmlu=0.702, int4_mmlu=0.693)  # -0.9pt
    _write_eval_json(llama, model_id="meta-llama/Meta-Llama-3-8B-Instruct",
                     baseline_mmlu=0.660, int4_mmlu=0.654)  # -0.6pt
    _write_eval_json(mistral, model_id="mistralai/Mistral-7B-Instruct-v0.3",
                     baseline_mmlu=0.620, int4_mmlu=0.610)  # -1.0pt

    out_path = tmp_path / "summary.json"
    rc = comp.main([
        "--inputs",
        f"Qwen-7B={qwen}",
        f"Llama-3-8B={llama}",
        f"Mistral-7B={mistral}",
        "--json-output", str(out_path),
    ])
    assert rc == 0

    out = capsys.readouterr().out
    assert "Qwen-7B" in out
    assert "Llama-3-8B" in out
    assert "Mistral-7B" in out
    assert "**GREEN.**" in out

    summary = json.loads(out_path.read_text())
    assert summary["schema_version"] == "§20.3.v1"
    assert summary["n_models"] == 3
    assert summary["cross_model_verdict"] == "GREEN"
    assert summary["models"]["Qwen-7B"]["combined_verdict"] == "GREEN"
    assert summary["models"]["Llama-3-8B"]["combined_verdict"] == "GREEN"
    assert summary["models"]["Mistral-7B"]["combined_verdict"] == "GREEN"


def test_cross_model_verdict_is_worst_of_models(tmp_path: Path):
    """Cross-model verdict = WORST single model. Two models GREEN +
    one RED → cross = RED. This is the partner-relevant signal: a
    single failing model means INT4 doesn't generalize, even if
    others pass."""
    from ctm_bench.scripts import compose_multi_model_summary as comp

    qwen = tmp_path / "qwen" / "results.json"
    llama = tmp_path / "llama" / "results.json"
    mistral = tmp_path / "mistral" / "results.json"
    _write_eval_json(qwen, model_id="qwen", baseline_mmlu=0.70, int4_mmlu=0.69)  # GREEN (-1.0pt)
    _write_eval_json(llama, model_id="llama", baseline_mmlu=0.65, int4_mmlu=0.64)  # GREEN (-1.0pt)
    _write_eval_json(mistral, model_id="mistral",
                     baseline_mmlu=0.62, int4_mmlu=0.55)  # RED (-7.0pt)

    out_path = tmp_path / "summary.json"
    rc = comp.main([
        "--inputs",
        f"Qwen-7B={qwen}", f"Llama-3-8B={llama}", f"Mistral-7B={mistral}",
        "--json-output", str(out_path),
    ])
    assert rc == 0

    summary = json.loads(out_path.read_text())
    assert summary["cross_model_verdict"] == "RED"
    assert summary["models"]["Qwen-7B"]["combined_verdict"] == "GREEN"
    assert summary["models"]["Mistral-7B"]["combined_verdict"] == "RED"


def test_cross_model_verdict_yellow_when_one_model_mediocre(tmp_path: Path):
    """Two GREEN + one YELLOW → cross = YELLOW. Pin the worst-of-
    semantic doesn't dilute by averaging."""
    from ctm_bench.scripts import compose_multi_model_summary as comp

    qwen = tmp_path / "qwen.json"
    llama = tmp_path / "llama.json"
    _write_eval_json(qwen, model_id="qwen",
                     baseline_mmlu=0.70, int4_mmlu=0.695)  # GREEN
    _write_eval_json(llama, model_id="llama",
                     baseline_mmlu=0.65, int4_mmlu=0.625)  # YELLOW (-2.5pt)

    out_path = tmp_path / "summary.json"
    rc = comp.main([
        "--inputs", f"Qwen-7B={qwen}", f"Llama-3-8B={llama}",
        "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert summary["cross_model_verdict"] == "YELLOW"


def test_decision_tree_band_boundaries(tmp_path: Path):
    """Pin the exact GREEN/YELLOW/RED MMLU band thresholds at
    -1.5 / -3.0 pt and ppl ratio thresholds at 1.05 / 1.15."""
    from ctm_bench.scripts.compose_multi_model_summary import (
        _verdict_mmlu, _verdict_ppl,
        MMLU_GREEN_THRESHOLD_PT, MMLU_YELLOW_THRESHOLD_PT,
        PPL_GREEN_RATIO, PPL_YELLOW_RATIO,
    )
    assert MMLU_GREEN_THRESHOLD_PT == -1.5
    assert MMLU_YELLOW_THRESHOLD_PT == -3.0
    assert PPL_GREEN_RATIO == 1.05
    assert PPL_YELLOW_RATIO == 1.15

    # MMLU bands.
    assert _verdict_mmlu(0.0) == "GREEN"
    assert _verdict_mmlu(-1.5) == "GREEN"
    assert _verdict_mmlu(-1.6) == "YELLOW"
    assert _verdict_mmlu(-3.0) == "YELLOW"
    assert _verdict_mmlu(-3.1) == "RED"
    assert _verdict_mmlu(None) == "MEASUREMENT MISSING"

    # Perplexity bands.
    assert _verdict_ppl(1.00) == "GREEN"
    assert _verdict_ppl(1.05) == "GREEN"
    assert _verdict_ppl(1.06) == "YELLOW"
    assert _verdict_ppl(1.15) == "YELLOW"
    assert _verdict_ppl(1.16) == "RED"


def test_per_model_combined_verdict_takes_worst_axis():
    """Combined verdict = worst(MMLU, perplexity). A model with
    GREEN MMLU but RED perplexity still reads RED — the partner-
    relevant signal isn't averaged away."""
    from ctm_bench.scripts.compose_multi_model_summary import (
        _combined_per_model_verdict,
    )
    assert _combined_per_model_verdict("GREEN", "GREEN") == "GREEN"
    assert _combined_per_model_verdict("GREEN", "RED") == "RED"
    assert _combined_per_model_verdict("YELLOW", "GREEN") == "YELLOW"
    # Missing one axis falls back to the other.
    assert _combined_per_model_verdict("MEASUREMENT MISSING", "GREEN") == "GREEN"
    assert _combined_per_model_verdict("RED", "MEASUREMENT MISSING") == "RED"
    # Both missing → MISSING.
    assert _combined_per_model_verdict(
        "MEASUREMENT MISSING", "MEASUREMENT MISSING",
    ) == "MEASUREMENT MISSING"


def test_compose_handles_missing_file(tmp_path: Path):
    """A non-existent path → row with note='file not found', combined
    verdict reflects MEASUREMENT MISSING. Pipeline doesn't crash."""
    from ctm_bench.scripts import compose_multi_model_summary as comp

    out_path = tmp_path / "summary.json"
    rc = comp.main([
        "--inputs", f"Missing={tmp_path / 'no_such_file.json'}",
        "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert summary["cross_model_verdict"] == "MEASUREMENT MISSING"
    assert summary["models"]["Missing"]["note"] == "file not found"


def test_compose_handles_missing_mmlu_falls_back_to_perplexity(tmp_path: Path):
    """An eval that ran only `--eval perplexity` produces a JSON
    with empty `mmlu`. Composer reads perplexity, marks MMLU missing,
    combined verdict falls back to perplexity-only."""
    from ctm_bench.scripts import compose_multi_model_summary as comp

    p = tmp_path / "ppl_only.json"
    p.write_text(json.dumps({
        "model_id": "test",
        "perplexity": [
            {"cache_type": "baseline", "perplexity": 3.71, "nll_per_token": 1.31},
            {"cache_type": "int4-per-channel", "perplexity": 3.78, "nll_per_token": 1.33},
        ],
        "mmlu": [],
    }))
    out_path = tmp_path / "summary.json"
    rc = comp.main([
        "--inputs", f"Test={p}",
        "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    row = summary["models"]["Test"]
    assert row["mmlu_verdict"] == "MEASUREMENT MISSING"
    assert row["mmlu_delta_pt"] is None
    # ppl ratio 3.78/3.71 = 1.019 → GREEN
    assert row["perplexity_verdict"] == "GREEN"
    # Combined = perplexity (the only available axis).
    assert row["combined_verdict"] == "GREEN"


def test_parse_input_arg_accepts_label_equals_path():
    """`label=path` parsed into (label, Path)."""
    from ctm_bench.scripts.compose_multi_model_summary import _parse_input_arg
    label, p = _parse_input_arg("Qwen-7B=/tmp/qwen/results.json")
    assert label == "Qwen-7B"
    assert str(p) == "/tmp/qwen/results.json"
    # Strips whitespace.
    label, p = _parse_input_arg("  Foo = /tmp/bar.json  ")
    assert label == "Foo"
    assert str(p) == "/tmp/bar.json"


def test_parse_input_arg_falls_back_to_parent_dir_name():
    """Bare path (no `=`) → label = parent directory name."""
    from ctm_bench.scripts.compose_multi_model_summary import _parse_input_arg
    label, p = _parse_input_arg("/tmp/llama-3-8b/results.json")
    assert label == "llama-3-8b"
    assert p.name == "results.json"


def test_summary_includes_per_model_source_paths(tmp_path: Path):
    """The merged JSON records each model's source path so the
    partner-shareable artefact is auditable back to the raw runs."""
    from ctm_bench.scripts import compose_multi_model_summary as comp

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_eval_json(a, model_id="a")
    _write_eval_json(b, model_id="b")
    out_path = tmp_path / "summary.json"
    rc = comp.main([
        "--inputs", f"A={a}", f"B={b}",
        "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert summary["models"]["A"]["source_path"] == str(a)
    assert summary["models"]["B"]["source_path"] == str(b)
