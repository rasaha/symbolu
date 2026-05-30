#!/usr/bin/env python3
# Phase 6L — CPU regression for the capacity instrumentation analysis layer.
#
# Independently verifies the four core claims of the Phase 6L analysis (with
# different data from the --selftest).  No torch/vllm; runs anywhere.
#
# Run:  python CTM_plus/Bench/tests/test_phase6l_capacity_demo.py
#       (also pytest-collectable)

import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import phase6l_capacity_demo as m


def _row(cell, B, completed=None, oom=False, preempts=0, slot_x=False,
         peak_live=None, peak_util_pct=None, total_blocks=1000,
         max_concurrency=None, hbm_gb=None, agg_tps=None,
         sidecar_bytes=None, model_weights_gb=None, kv_cache_budget_gb=None):
    pu = (peak_util_pct / 100.0) if peak_util_pct is not None else None
    sat = bool((pu or 0) >= 0.90 or preempts > 0 or oom)
    return {
        "cell": cell, "batch": B,
        "completed": completed if completed is not None else B,
        "oom": oom, "preempts": preempts, "slot_exhausted": slot_x,
        "peak_live": peak_live, "peak_util": pu,
        "saturation_observed": sat, "total_blocks": total_blocks,
        "max_concurrency": max_concurrency, "hbm_gb": hbm_gb, "agg_tps": agg_tps,
        "error": None,
        "sidecar_bytes_by_tensor": sidecar_bytes or {},
        "model_weights_gb": model_weights_gb,
        "kv_cache_budget_gb": kv_cache_budget_gb,
    }


_GB = 1e9
# Real Phase 6G per-tensor sidecar inventory (~3.42 GB total).
_SIDECARS = {"k_protect_ext": 0.82 * _GB, "k_scale_ext": 0.65 * _GB,
             "k_xmin_ext": 0.65 * _GB, "v_scale_ext": 0.65 * _GB,
             "v_xmin_ext": 0.65 * _GB}


def _real_rows():
    """The actual Phase 6L pod result (Qwen-7B, A100, mml=8192, B=128)."""
    return [
        _row("bf16", 128, peak_live=58, peak_util_pct=100.0, preempts=8,
             total_blocks=28310, hbm_gb=42.44, agg_tps=597.3, model_weights_gb=14.25),
        _row("protected", 128, peak_live=117, peak_util_pct=100.0, preempts=6,
             total_blocks=28310, hbm_gb=46.83, agg_tps=130.4,
             sidecar_bytes=_SIDECARS, model_weights_gb=14.25),
    ]


def test_ceiling_not_reached_low_util():
    # A run where the largest B completed cleanly at 55% utilization.
    rows = [_row("bf16", 96, peak_live=96, peak_util_pct=55.0)]
    assert m._ceiling_not_reached(rows)
    assert m._demonstrated_live(rows) is None


def test_ceiling_reached_high_util():
    rows = [_row("bf16", 96, peak_live=54, peak_util_pct=94.0, preempts=2)]
    assert not m._ceiling_not_reached(rows)
    assert m._demonstrated_live(rows) == 54


def test_submitted_b_exceeds_demonstrated_live():
    # B=160 submitted, but only 58 ran resident simultaneously.
    rows = [_row("bf16", 160, completed=160, peak_live=58,
                 peak_util_pct=96.0, preempts=5)]
    dem = m._demonstrated_live(rows)
    assert dem == 58
    assert dem < 160


def test_demonstrated_density_ratio_uses_live_not_submitted_b():
    rows = [
        _row("bf16",      160, peak_live=55, peak_util_pct=95.0, preempts=3,
             total_blocks=1000),
        _row("protected", 160, peak_live=99, peak_util_pct=93.0, preempts=1,
             total_blocks=900),
    ]
    a = m._phase6l_analyze(rows)
    # bf16 seq_per_kblock = 55/1.0 = 55; prot = 99/0.9 = 110; ratio = 2.0x
    assert a["by_cell"]["bf16"]["demonstrated_live"] == 55
    assert a["by_cell"]["protected"]["demonstrated_live"] == 99
    assert a["demonstrated_density_ratio"] is not None
    assert abs(a["demonstrated_density_ratio"] - 2.0) < 0.01
    # Submitted B was equal (160/160=1.0x) — ratio must differ significantly.
    assert abs(a["demonstrated_density_ratio"] - 1.0) > 0.5


def test_claim_demonstrated_in_window():
    rows = [
        _row("bf16",      128, peak_live=55, peak_util_pct=95.0, preempts=2,
             total_blocks=1000),
        _row("protected", 192, peak_live=95, peak_util_pct=92.0, preempts=1,
             total_blocks=900),
    ]
    a = m._phase6l_analyze(rows)
    # ratio ≈ (95/0.9)/(55/1.0) ≈ 105.6/55 ≈ 1.92×  → in [1.5, 2.5] → DEMONSTRATED
    assert a["claim_demonstrated"]
    assert a["claim_status"] == "DEMONSTRATED"


def test_claim_not_demonstrated_outside_window():
    # protected has similar live seqs but far fewer blocks -> ratio < 1.5.
    rows = [
        _row("bf16",      64, peak_live=55, peak_util_pct=95.0, preempts=1,
             total_blocks=1000),
        _row("protected", 64, peak_live=52, peak_util_pct=97.0, preempts=2,
             total_blocks=800),
    ]
    # ratio = (52/0.8)/(55/1.0) = 65/55 ≈ 1.18× → outside [1.5, 2.5]
    a = m._phase6l_analyze(rows)
    assert not a["claim_demonstrated"]
    assert a["claim_status"] == "MEASURED_OUTSIDE_WINDOW"


def test_ceiling_not_reached_blocks_demonstration():
    # Both cells submitted large B but never pressured the pool.
    rows = [
        _row("bf16",      200, peak_live=200, peak_util_pct=60.0),
        _row("protected", 200, peak_live=200, peak_util_pct=58.0),
    ]
    a = m._phase6l_analyze(rows)
    assert "CEILING_NOT_REACHED" in a["claim_status"]
    assert a["demonstrated_density_ratio"] is None
    assert not a["claim_demonstrated"]


def test_invalid_slot_exhaustion():
    rows = [_row("protected", 64, slot_x=True, peak_live=40, peak_util_pct=70.0)]
    a = m._phase6l_analyze(rows)
    assert a["claim_status"] == "INVALID_SLOT_EXHAUSTION"
    assert not a["claim_demonstrated"]


def test_sidecar_tax_measured_from_tensor_bytes():
    a = m._phase6l_analyze(_real_rows())
    st = a["sidecar_tax"]
    assert abs(st["absolute_hbm_delta_gb"] - 4.39) < 0.01
    assert abs(st["measured_sidecar_tax_gb"] - 3.42) < 0.01
    assert st["sidecar_tax_estimated"] is False
    assert st["sidecar_breakdown_available"] is True
    # tax is 77.9% of the delta; the rest (~0.97 GB) is non-sidecar overhead.
    assert abs(st["sidecar_tax_pct_of_delta"] - 77.9) < 0.5
    assert abs(st["non_sidecar_residual_delta_gb"] - 0.97) < 0.01
    # per-tensor breakdown surfaced in hbm_accounting.
    pc = a["hbm_accounting"]["protected"]["sidecar_gb_by_tensor"]
    assert abs(pc["k_protect_ext"] - 0.82) < 0.01
    assert abs(pc["k_scale_ext"] - 0.65) < 0.01


def test_net_density_is_headline_and_net_of_tax():
    a = m._phase6l_analyze(_real_rows())
    dn = a["density"]
    assert dn["bf16_demonstrated_live"] == 58
    assert dn["protected_demonstrated_live"] == 117
    assert abs(dn["raw_live_ratio"] - 2.017) < 0.01
    assert abs(dn["bf16_seq_per_gb"] - 1.367) < 0.01
    assert abs(dn["protected_seq_per_gb"] - 2.498) < 0.01
    assert abs(dn["net_density_ratio"] - 1.83) < 0.02            # headline
    # The headline is the NET ratio, distinct from the raw live ratio.
    assert abs(dn["net_density_ratio"] - dn["raw_live_ratio"]) > 0.1
    assert a["claim_status"] == "DEMONSTRATED"
    assert a["headline_metric"] == "net_density_ratio"
    assert abs(a["headline_density_ratio"] - dn["net_density_ratio"]) < 1e-9


def test_counterfactual_is_labeled_and_not_headline():
    # Guardrail: the no-sidecar ratio must NOT be used as the headline/claim.
    a = m._phase6l_analyze(_real_rows())
    dn = a["density"]
    assert dn["net_density_ratio_without_sidecars"] is not None
    # Removing the tax inflates the ratio -> strictly larger than the real one.
    assert dn["net_density_ratio_without_sidecars"] > dn["net_density_ratio"]
    # Headline stays the REAL net ratio, never the counterfactual.
    assert a["headline_density_ratio"] == dn["net_density_ratio"]
    assert a["headline_density_ratio"] != dn["net_density_ratio_without_sidecars"]


def test_graceful_degradation_without_tensor_discovery():
    # No sidecar_bytes -> breakdown unavailable, but the VC-critical numbers
    # (absolute delta, net density, raw ratio, claim) still compute.
    rows = [
        _row("bf16", 128, peak_live=58, peak_util_pct=100.0, preempts=8,
             total_blocks=28310, hbm_gb=42.44),
        _row("protected", 128, peak_live=117, peak_util_pct=100.0, preempts=6,
             total_blocks=28310, hbm_gb=46.83),
    ]
    a = m._phase6l_analyze(rows)
    st = a["sidecar_tax"]
    assert st["measured_sidecar_tax_gb"] is None
    assert st["sidecar_tax_estimated"] is True
    assert st["sidecar_breakdown_available"] is False
    assert abs(st["absolute_hbm_delta_gb"] - 4.39) < 0.01      # still computed
    assert abs(a["density"]["net_density_ratio"] - 1.83) < 0.02  # still computed
    assert a["claim_status"] == "DEMONSTRATED"                  # headline survives


def test_falsified_claim_when_net_ratio_below_window():
    # Both saturate, but the sidecar tax erases the packing win -> net < 1.5x.
    rows = [
        _row("bf16", 128, peak_live=55, peak_util_pct=95.0, preempts=2,
             total_blocks=28314, hbm_gb=43.8),
        _row("protected", 128, peak_live=62, peak_util_pct=96.0, preempts=3,
             total_blocks=26900, hbm_gb=48.5, sidecar_bytes=_SIDECARS),
    ]
    a = m._phase6l_analyze(rows)
    # net = (62/48.5)/(55/43.8) = 1.278/1.256 = 1.018 -> outside [1.5,2.5]
    assert a["density"]["net_density_ratio"] < 1.5
    assert a["claim_status"] == "MEASURED_OUTSIDE_WINDOW"
    assert not a["claim_demonstrated"]


def test_sidecar_audit_json_fallback_gives_exact_tax():
    # A run whose per-cell JSON has no embedded sidecar bytes (older run) can
    # still get an EXACT per-tensor tax from a Phase 6G sidecar-audit JSON.
    import json as _json
    import tempfile
    rows = [
        _row("bf16", 128, peak_live=58, peak_util_pct=100.0, preempts=8,
             total_blocks=28310, hbm_gb=42.44),
        _row("protected", 128, peak_live=117, peak_util_pct=100.0, preempts=6,
             total_blocks=28310, hbm_gb=46.83),       # no sidecar_bytes
    ]
    with tempfile.TemporaryDirectory() as d:
        audit = Path(d) / "audit_mml8192.json"
        audit.write_text(_json.dumps({"sidecar_ranked": [
            {"tensor": "k_protect_ext", "total_bytes": int(0.82 * _GB)},
            {"tensor": "k_scale_ext",   "total_bytes": int(0.65 * _GB)},
            {"tensor": "k_xmin_ext",    "total_bytes": int(0.65 * _GB)},
            {"tensor": "v_scale_ext",   "total_bytes": int(0.65 * _GB)},
            {"tensor": "v_xmin_ext",    "total_bytes": int(0.65 * _GB)},
            {"tensor": "protect_mask",  "total_bytes": 800_000},   # non-canonical
        ]}))
        # Without the audit: tax UNAVAILABLE/estimated.
        a0 = m._phase6l_analyze(rows)
        assert a0["sidecar_tax"]["sidecar_tax_estimated"] is True
        # With the audit: exact per-tensor tax, breakdown available.
        a1 = m._phase6l_analyze(rows, audit_path=str(audit))
    st = a1["sidecar_tax"]
    assert st["sidecar_tax_estimated"] is False
    assert st["sidecar_breakdown_available"] is True
    assert abs(st["measured_sidecar_tax_gb"] - 3.42) < 0.01   # protect_mask dropped
    assert "Phase 6G sidecar audit" in st["sidecar_tax_source"]
    pc = a1["hbm_accounting"]["protected"]["sidecar_gb_by_tensor"]
    assert "protect_mask" not in pc and abs(pc["k_protect_ext"] - 0.82) < 0.01
    # Headline net density is identical either way (it comes from hbm_gb).
    assert abs(a1["density"]["net_density_ratio"]
               - a0["density"]["net_density_ratio"]) < 1e-9


def test_worker_owns_sidecar_walk_and_does_not_import_phase6l():
    # Extra: the saturation worker is self-contained — it discovers sidecars
    # itself and must NOT import the analysis layer back (avoids the
    # phase6k14 -> phase6l runtime coupling).
    worker_src = (_SCR / "phase6k14_saturation.py").read_text()
    assert "import phase6l_capacity_demo" not in worker_src
    assert "def _discover_sidecar_bytes" in worker_src
    # And the GPU-side discovery no longer lives in the analysis module.
    assert not hasattr(m, "discover_sidecar_bytes")


def test_selftest_passes():
    assert m._selftest() == 0


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'} "
          f"({len(tests) - failed}/{len(tests)})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
