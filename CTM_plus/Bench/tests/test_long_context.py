"""CPU regression tests for §20.4 long-context harness + composer.

Pins:

* `track_e_long_context.py` dry-run produces a JSON with the §20.4.v1
  schema (model_id, int4_config, context_lengths, needle_depths,
  perplexity_rows, needle_rows, deltas).
* Needle rows and perplexity rows JOIN on the requested
  context_length_chars (the upstream-chosen window), not the
  post-needle-insertion length — pinned because a bug in this layer
  silently de-correlates the two halves of the eval.
* The composer maps perplexity ratio and needle accuracy delta to
  GREEN/YELLOW/RED bands at the pre-decided thresholds.
* Combined verdict is the worst of the two axes (a model that
  preserves perplexity but fails needle retrieval is still RED).
* Headline verdict picks the largest context length (the partner-
  relevant cell).
* Composer handles partial input — perplexity-only or needle-only
  produces a sane single-axis verdict.

Haystack + needle utilities are also pinned:

* `_insert_needle_at_depth` puts the needle near the requested depth
  percentage (within sentence-boundary slack).
* `_build_haystack` produces text at least as long as the target.
* `_generate_code` produces 6-char alphanumeric codes.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest


pytest.importorskip("torch")
pytest.importorskip("transformers")


def test_long_context_dry_run_writes_v2_schema(tmp_path: Path):
    """End-to-end dry-run writes a JSON with the §20.4.v2 schema.

    Verifies that:
      * schema_version == "§20.4.v2"
      * int4_config reflects the §18.3 ship defaults
      * One perplexity_row per (context_length, cache_type)
      * One needle_row per (context_length, depth, sample, cache_type)
      * The deltas block joins perplexity AND needle on
        the SAME context_length_chars key (not split).
      * Needle rows carry the §20.4 diagnostic-sprint fields.
    """
    from ctm_bench.scripts import track_e_long_context as lc

    out = tmp_path / "long_context.json"
    rc = lc.main([
        "--dry-run",
        "--context-lengths", "100,200",
        "--needle-depths", "0.1,0.5",
        "--needle-samples", "1",
        "--needle-decode-tokens", "4",
        "--output", str(out),
    ])
    assert rc == 0

    data = json.loads(out.read_text())
    assert data["schema_version"] == "§20.4.v2"
    assert data["int4_config"]["k_group_size"] == 32
    assert data["int4_config"]["v_group_size"] == 32
    assert data["int4_config"]["asymmetric"] is True
    assert data["context_lengths"] == [100, 200]
    assert data["needle_depths"] == [0.1, 0.5]

    # Perplexity: 2 ctx × 2 caches = 4 rows.
    p_rows = data["perplexity_rows"]
    assert len(p_rows) == 4
    p_keys = {(r["context_length_chars"], r["cache_type"]) for r in p_rows}
    assert (100, "baseline") in p_keys
    assert (200, "int4-per-channel") in p_keys

    # Needle: 2 ctx × 2 depths × 1 sample × 2 caches = 8 rows.
    n_rows = data["needle_rows"]
    assert len(n_rows) == 8

    # §20.4 diagnostic-sprint fields are present on every needle row.
    for r in n_rows:
        for field_name in (
            "first_stutter_position", "repeated_token_rate",
            "decode_entropy_mean", "decode_entropy_min",
            "decode_entropy_collapsed", "cache_fp16_bytes",
            "cache_compressed_bytes", "cache_compression_ratio",
            "decode_tokens_per_s",
        ):
            assert field_name in r, f"needle row missing {field_name!r}"

    # CRITICAL: deltas keys must match on context length. If perplexity
    # rows use 100 and needle rows use 127 (post-needle), the deltas
    # block fragments into 4 entries instead of 2 — silent bug class.
    per = data["deltas"]["per_context_length"]
    keys = sorted(per.keys())
    # Expect exactly 2 unique context_length_chars keys: 100, 200.
    assert len(keys) == 2, (
        f"Expected 2 ctx-length entries in deltas, got {len(keys)}: {keys}. "
        f"If needle rows recorded post-insertion length while perplexity "
        f"rows recorded pre-insertion length, the keys won't collide and "
        f"this assertion fires."
    )
    for key in keys:
        block = per[key]
        # Each entry should have BOTH perplexity AND needle fields.
        assert "perplexity_ratio" in block, (
            f"Entry {key} missing perplexity_ratio — perplexity rows "
            f"didn't join with needle rows"
        )
        assert "baseline_needle_accuracy" in block, (
            f"Entry {key} missing baseline_needle_accuracy — needle "
            f"rows didn't join with perplexity rows"
        )


def test_long_context_skip_needle_runs_perplexity_only(tmp_path: Path):
    """`--skip-needle` runs perplexity sweep only; the JSON has empty
    needle_rows but a populated perplexity_rows."""
    from ctm_bench.scripts import track_e_long_context as lc

    out = tmp_path / "lc_no_needle.json"
    rc = lc.main([
        "--dry-run", "--skip-needle",
        "--context-lengths", "100",
        "--needle-depths", "0.5",
        "--output", str(out),
    ])
    assert rc == 0
    data = json.loads(out.read_text())
    assert len(data["perplexity_rows"]) == 2  # 1 ctx × 2 caches
    assert len(data["needle_rows"]) == 0


def test_long_context_skip_perplexity_runs_needle_only(tmp_path: Path):
    """`--skip-perplexity` flips the other axis."""
    from ctm_bench.scripts import track_e_long_context as lc

    out = tmp_path / "lc_no_ppl.json"
    rc = lc.main([
        "--dry-run", "--skip-perplexity",
        "--context-lengths", "100",
        "--needle-depths", "0.5",
        "--needle-samples", "1",
        "--needle-decode-tokens", "2",
        "--output", str(out),
    ])
    assert rc == 0
    data = json.loads(out.read_text())
    assert len(data["perplexity_rows"]) == 0
    assert len(data["needle_rows"]) == 2  # 1 ctx × 1 depth × 1 sample × 2 caches


def test_haystack_builder_reaches_target_length():
    """`_build_haystack` must produce text of at least target_chars."""
    from ctm_bench.scripts.track_e_long_context import _build_haystack
    rng = random.Random(0)
    h = _build_haystack(500, rng)
    assert len(h) == 500  # truncated to exactly target
    # Try a few different targets.
    for n in (100, 1000, 5000):
        rng = random.Random(n)
        h = _build_haystack(n, rng)
        assert len(h) == n


def test_needle_insertion_lands_near_target_depth():
    """`_insert_needle_at_depth` inserts within the requested depth
    band. The sentence-boundary search widens the window by up to
    the search-window length (±50 chars), so the actual bound is
    [target - 50, target + 50 + window/2]."""
    from ctm_bench.scripts.track_e_long_context import _insert_needle_at_depth
    haystack = "Sentence one. " * 50 + "Last sentence."  # ~714 chars
    n = len(haystack)
    text, pos = _insert_needle_at_depth(haystack, "NEEDLE", 0.5)
    target = int(n * 0.5)
    # Allow ±100 chars of slack: the sentence-boundary nudge can land
    # anywhere in [target - 50, target + 100] depending on how the
    # window's `rfind(". ")` matches.
    assert target - 100 <= pos <= target + 100, (
        f"insert_at_depth(0.5) on {n}-char haystack returned pos={pos}; "
        f"expected within ±100 of target={target}"
    )
    assert "NEEDLE" in text
    # Sanity: depth 0.0 lands near the start; 1.0 lands near the end.
    _, pos_early = _insert_needle_at_depth(haystack, "NEEDLE", 0.0)
    _, pos_late = _insert_needle_at_depth(haystack, "NEEDLE", 1.0)
    assert pos_early < pos_late


def test_code_generator_format():
    """`_generate_code` produces 6-char alphanumeric strings."""
    from ctm_bench.scripts.track_e_long_context import _generate_code
    rng = random.Random(0)
    code = _generate_code(rng)
    assert len(code) == 6
    for c in code:
        assert c.isalnum() and c.isupper() or c.isdigit()


# --------------------------------------------------------------------- #
# Composer tests                                                        #
# --------------------------------------------------------------------- #


def _make_lc_data(per_ctx_blocks: dict) -> dict:
    """Build a synthetic long-context JSON for composer testing."""
    return {
        "schema_version": "§20.4.v1",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "int4_config": {
            "scheme": "K=per-channel INT4, V=per-token INT4, asymmetric, "
                      "k_group=32, v_group=32",
        },
        "context_lengths": sorted(b["context_length_chars"]
                                   for b in per_ctx_blocks.values()),
        "deltas": {"per_context_length": per_ctx_blocks},
    }


def test_composer_green_when_quality_holds_at_32k(tmp_path: Path):
    """Perplexity ratio 1.02× AND needle delta -3pt at 32k chars →
    headline GREEN."""
    from ctm_bench.scripts import compose_long_context_summary as comp

    data = _make_lc_data({
        "chars=4000": {
            "context_length_chars": 4000,
            "baseline_perplexity": 3.71, "int4_perplexity": 3.80,
            "perplexity_ratio": 1.024,
            "baseline_needle_accuracy": 1.0, "int4_needle_accuracy": 1.0,
            "needle_accuracy_delta_pct": 0.0,
        },
        "chars=32000": {
            "context_length_chars": 32000,
            "baseline_perplexity": 3.50, "int4_perplexity": 3.57,
            "perplexity_ratio": 1.020,
            "baseline_needle_accuracy": 0.95, "int4_needle_accuracy": 0.92,
            "needle_accuracy_delta_pct": -3.0,
        },
    })
    in_path = tmp_path / "lc.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(data))
    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert summary["schema_version"] == "§20.4.v1"
    # Headline = largest context (32000).
    assert summary["headline"]["context_length_chars"] == 32000
    assert summary["headline"]["combined_verdict"] == "GREEN"


def test_composer_red_when_needle_collapses(tmp_path: Path):
    """Perplexity holds (1.04×, GREEN) but needle retrieval collapses
    (-15pt, RED). Combined verdict must take the worst: RED.
    Verifies the "perplexity-holds-but-functional-cap-fails" detection
    that's the whole point of including needle-in-haystack.
    """
    from ctm_bench.scripts import compose_long_context_summary as comp

    data = _make_lc_data({
        "chars=32000": {
            "context_length_chars": 32000,
            "baseline_perplexity": 3.50, "int4_perplexity": 3.64,
            "perplexity_ratio": 1.040,
            "baseline_needle_accuracy": 0.95, "int4_needle_accuracy": 0.80,
            "needle_accuracy_delta_pct": -15.0,
        },
    })
    in_path = tmp_path / "lc.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(data))
    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert summary["headline"]["combined_verdict"] == "RED"
    per = summary["per_context_length"]["chars=32000"]
    assert per["perplexity_verdict"] == "GREEN"  # 1.04 < 1.05
    assert per["needle_verdict"] == "RED"        # -15 < -10


def test_composer_yellow_band(tmp_path: Path):
    """Perplexity 1.10× → YELLOW; needle -8pt → YELLOW. Combined YELLOW.
    Pins the band boundaries at 1.05/1.15 (ppl) and -5/-10 (needle)."""
    from ctm_bench.scripts import compose_long_context_summary as comp

    data = _make_lc_data({
        "chars=16000": {
            "context_length_chars": 16000,
            "baseline_perplexity": 3.50, "int4_perplexity": 3.85,
            "perplexity_ratio": 1.10,
            "baseline_needle_accuracy": 0.95, "int4_needle_accuracy": 0.87,
            "needle_accuracy_delta_pct": -8.0,
        },
    })
    in_path = tmp_path / "lc.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(data))
    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert summary["headline"]["combined_verdict"] == "YELLOW"


def test_composer_decision_tree_boundaries():
    """Pin the exact band-boundary contracts."""
    from ctm_bench.scripts.compose_long_context_summary import (
        _verdict_ppl, _verdict_needle, _combined_verdict,
        PPL_GREEN_RATIO, PPL_YELLOW_RATIO,
        NEEDLE_GREEN_DELTA_PCT, NEEDLE_YELLOW_DELTA_PCT,
    )

    assert PPL_GREEN_RATIO == 1.05
    assert PPL_YELLOW_RATIO == 1.15
    assert NEEDLE_GREEN_DELTA_PCT == -5.0
    assert NEEDLE_YELLOW_DELTA_PCT == -10.0

    # Perplexity bands.
    assert _verdict_ppl(1.00) == "GREEN"
    assert _verdict_ppl(1.05) == "GREEN"
    assert _verdict_ppl(1.06) == "YELLOW"
    assert _verdict_ppl(1.15) == "YELLOW"
    assert _verdict_ppl(1.16) == "RED"
    assert _verdict_ppl(None) == "MEASUREMENT MISSING"

    # Needle bands.
    assert _verdict_needle(0.0) == "GREEN"
    assert _verdict_needle(-5.0) == "GREEN"
    assert _verdict_needle(-5.1) == "YELLOW"
    assert _verdict_needle(-10.0) == "YELLOW"
    assert _verdict_needle(-10.1) == "RED"

    # Combined: worst of two.
    assert _combined_verdict("GREEN", "GREEN") == "GREEN"
    assert _combined_verdict("GREEN", "RED") == "RED"
    assert _combined_verdict("YELLOW", "GREEN") == "YELLOW"
    assert _combined_verdict("RED", "GREEN") == "RED"
    # Missing one axis falls back to the other.
    assert _combined_verdict("MEASUREMENT MISSING", "GREEN") == "GREEN"
    assert _combined_verdict("RED", "MEASUREMENT MISSING") == "RED"


def test_composer_handles_perplexity_only_input(tmp_path: Path):
    """Sweep run with `--skip-needle` → composer should still produce
    a verdict based on perplexity alone."""
    from ctm_bench.scripts import compose_long_context_summary as comp

    data = _make_lc_data({
        "chars=32000": {
            "context_length_chars": 32000,
            "baseline_perplexity": 3.50, "int4_perplexity": 3.57,
            "perplexity_ratio": 1.020,
            # No needle fields.
        },
    })
    in_path = tmp_path / "lc.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(data))
    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    # Perplexity-only: combined = perplexity verdict.
    assert summary["headline"]["combined_verdict"] == "GREEN"
