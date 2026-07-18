"""
test_realcg_smoke.py — Plumbing validation for the real_cg internal-signal path.

Two layers:
  1. Pure-logic tests (no agentic framework needed): the fail-closed mapping and the
     vritti-risk / JEPA-disagreement math, exercised with crafted resolution objects.
  2. End-to-end stub tests (skip cleanly if the agentic package is unavailable): run the
     LIVE extraction path via StubCGLLMAdapter — no torch / no GPU / no checkpoint.

This validates that the real_cg extraction path is wired and executes. It is NOT evidence
that model-internal signals improve governance: the stub state is a fixed fixture, so the
internal signals are constant across scenarios and carry no discriminative claim.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from experiments.signal_gov.configs import CONFIGS, CONFIG_ORDER
from experiments.signal_gov.dataset import load_handbuilt, load_smoke
from experiments.signal_gov.features import (
    FEATURE_FIELDS,
    MISSING_SIGNAL_RISK,
    MockFeatureExtractor,
    RealCGSignalError,
    _jepa_disagreement_from_assessment,
    _vritti_risk_from_distribution,
    map_resolutions_to_signals,
)
from experiments.signal_gov.run_experiment import run


# ---------------------------------------------------------------------------
# Skip gate: real_cg stub needs the in-repo agentic package (numpy only; NO torch).
# ---------------------------------------------------------------------------

def _agentic_available() -> bool:
    try:
        import agentic.agentic_framework.sovereign_bridge  # noqa: F401
        import agentic.agentic_framework.jepa_governance  # noqa: F401
        import agentic.agentic_framework.llm_adapters  # noqa: F401
        return True
    except Exception:
        return False


agentic_required = pytest.mark.skipif(
    not _agentic_available(),
    reason="real_cg stub path needs the in-repo agentic framework (numpy only; torch NOT required)",
)


# Helpers to craft duck-typed resolution objects for the pure-logic tests.
def _vr(coherence=0.5, dist=None, degraded=False, source="real"):
    return SimpleNamespace(
        coherence=coherence,
        distribution=dist or {"pramana": 1.0, "viparyaya": 0.0, "vikalpa": 0.0,
                              "smrti": 0.0, "nidra": 0.0},
        degraded=degraded,
        source=SimpleNamespace(value=source),
    )


def _asmt(regime="normal", conf_adj=0.0):
    return SimpleNamespace(regime=SimpleNamespace(value=regime),
                           confidence_adjustment=conf_adj)


# ===========================================================================
# 1. Pure-logic tests (no agentic dependency)
# ===========================================================================

def test_missing_entropy_fails_closed_not_zero():
    er = SimpleNamespace(available=False, combined_entropy=None)
    sig = map_resolutions_to_signals(er, _vr(), _asmt())
    assert sig.entropy == MISSING_SIGNAL_RISK
    assert sig.entropy != 0.0  # must NOT silently pass a missing risk signal as zero
    assert sig.degraded is True
    assert "entropy_unavailable" in sig.detail


def test_missing_entropy_strict_raises():
    er = SimpleNamespace(available=False, combined_entropy=None)
    with pytest.raises(RealCGSignalError):
        map_resolutions_to_signals(er, _vr(), _asmt(), strict=True)


def test_present_entropy_used_directly():
    er = SimpleNamespace(available=True, combined_entropy=0.42)
    sig = map_resolutions_to_signals(er, _vr(), _asmt())
    assert sig.entropy == pytest.approx(0.42)
    assert sig.degraded is False
    assert sig.detail == "ok"


def test_vritti_risk_is_nongrounded_mass():
    risk = _vritti_risk_from_distribution(
        {"pramana": 0.4, "viparyaya": 0.2, "vikalpa": 0.1, "smrti": 0.0, "nidra": 0.3})
    assert risk == pytest.approx(0.6)  # viparyaya + vikalpa + nidra


def test_jepa_disagreement_mapping():
    assert _jepa_disagreement_from_assessment(_asmt("normal", 0.0)) == 0.0
    assert _jepa_disagreement_from_assessment(_asmt("process_drift", 0.0)) == 0.5
    assert _jepa_disagreement_from_assessment(_asmt("dual_anomaly", 0.0)) == 1.0
    assert _jepa_disagreement_from_assessment(_asmt("unknown", 0.0)) == 1.0  # fail-closed
    # confidence-adjustment magnitude also raises disagreement
    assert _jepa_disagreement_from_assessment(_asmt("normal", -0.5)) == pytest.approx(1.0)


def test_unknown_regime_degrades():
    er = SimpleNamespace(available=True, combined_entropy=0.2)
    sig = map_resolutions_to_signals(er, _vr(), _asmt("unknown"))
    assert sig.degraded is True
    assert "jepa_regime_unknown" in sig.detail


def test_degraded_vritti_flagged():
    er = SimpleNamespace(available=True, combined_entropy=0.2)
    sig = map_resolutions_to_signals(er, _vr(degraded=True, source="approximated"), _asmt())
    assert sig.degraded is True
    assert "vritti_degraded" in sig.detail


# ===========================================================================
# 2. End-to-end stub tests (live extraction path; no torch/GPU/checkpoint)
# ===========================================================================

@agentic_required
def test_realcg_runs_with_stub_no_torch():
    from experiments.signal_gov.features import RealCGFeatureExtractor

    fx = RealCGFeatureExtractor(use_stub=True)
    assert fx.is_stub is True
    feats = fx.extract_all(load_handbuilt())
    assert len(feats) == 15
    for fv in feats:
        assert fv.provenance.startswith("real_cg:")
        assert "stub" in fv.provenance  # deterministic_stub provenance tag
        # internal signals populated (NOT silently all-zero)
        assert all(0.0 <= v <= 1.0 for v in
                   (fv.entropy, fv.coherence, fv.vritti_risk, fv.jepa_disagreement))
        assert (fv.entropy + fv.vritti_risk + fv.jepa_disagreement) > 0.0


@agentic_required
def test_realcg_stub_snapshot_values():
    # Wiring-contract snapshot of the deterministic stub fixture through the LIVE
    # engines. If the engines legitimately change, update this snapshot intentionally.
    from experiments.signal_gov.features import RealCGFeatureExtractor

    fv = RealCGFeatureExtractor(use_stub=True).extract(load_smoke()[0])
    assert fv.vritti_risk == pytest.approx(1.0, abs=1e-6)   # stub fixture -> nidra-dominant
    assert fv.coherence == pytest.approx(0.5, abs=1e-6)
    assert fv.entropy == pytest.approx(0.119, abs=0.02)     # low entropy from fixture
    assert fv.jepa_disagreement == pytest.approx(0.5, abs=1e-6)  # process_drift regime


@agentic_required
def test_realcg_schema_matches_mock():
    from experiments.signal_gov.features import RealCGFeatureExtractor

    s = load_smoke()[0]
    real = RealCGFeatureExtractor(use_stub=True).extract(s).to_dict()
    mock = MockFeatureExtractor().extract(s).to_dict()
    assert set(real.keys()) == set(mock.keys()) == set(FEATURE_FIELDS)


@agentic_required
def test_realcg_c4_consumes_signal_and_flips_vs_c3():
    from experiments.signal_gov.features import RealCGFeatureExtractor

    sc = load_handbuilt()
    feats = RealCGFeatureExtractor(use_stub=True).extract_all(sc)
    c3 = next(c for c in CONFIGS if c.name.startswith("C3"))
    c4 = next(c for c in CONFIGS if c.name.startswith("C4"))
    diffs = [abs(c4.score(s, f) - c3.score(s, f)) for s, f in zip(sc, feats)]
    # C4 must actually consume the extracted internal signal -> at least one score flips.
    assert max(diffs) > 1e-6


@agentic_required
def test_realcg_determinism():
    from experiments.signal_gov.features import RealCGFeatureExtractor

    s = load_smoke()
    a = [fv.to_dict() for fv in RealCGFeatureExtractor(use_stub=True).extract_all(s)]
    b = [fv.to_dict() for fv in RealCGFeatureExtractor(use_stub=True).extract_all(s)]
    assert a == b


@agentic_required
def test_realcg_writes_feature_cache(tmp_path):
    res = run("real_cg", "handbuilt", tmp_path, real_cg_stub=True, n_boot=50,
              make_plots=False)
    cache = tmp_path / "features.jsonl"
    assert cache.exists() and cache.stat().st_size > 0
    assert res.results["meta"]["feature_cache"] == str(cache)
    rows = [json.loads(ln) for ln in cache.read_text().splitlines() if ln.strip()]
    assert len(rows) == res.results["dataset"]["n_total"]
    for r in rows:                                   # cache schema == FEATURE_FIELDS
        assert set(r.keys()) == set(FEATURE_FIELDS)
        assert r["provenance"].startswith("real_cg:")


@agentic_required
def test_realcg_cache_replay_bit_identical(tmp_path):
    gpu = run("real_cg", "handbuilt", tmp_path / "extract", real_cg_stub=True,
              n_boot=50, make_plots=False)
    cache = tmp_path / "extract" / "features.jsonl"
    replay = run("cached", "handbuilt", tmp_path / "replay",
                 features_path=str(cache), n_boot=50, make_plots=False)
    for name in CONFIG_ORDER:                        # metrics identical offline
        g, r = gpu.results["configs"][name], replay.results["configs"][name]
        assert r["auroc"] == pytest.approx(g["auroc"], abs=1e-12)
        assert r["auprc"] == pytest.approx(g["auprc"], abs=1e-12)
        assert r["catch_at_budget"] == g["catch_at_budget"]


@agentic_required
def test_realcg_cache_provenance_preserved(tmp_path):
    gpu = run("real_cg", "smoke", tmp_path / "extract", real_cg_stub=True,
              n_boot=50, make_plots=False)
    cache = tmp_path / "extract" / "features.jsonl"
    replay = run("cached", "smoke", tmp_path / "replay",
                 features_path=str(cache), n_boot=50, make_plots=False)
    # provenance is carried through the cache into the replay's metadata.
    assert replay.results["meta"]["feature_provenance"] == \
        gpu.results["meta"]["feature_provenance"]
    assert "real_cg" in replay.results["meta"]["feature_provenance"]


@agentic_required
def test_realcg_no_cache_write_disables(tmp_path):
    res = run("real_cg", "smoke", tmp_path, real_cg_stub=True, n_boot=50,
              make_plots=False, write_cache=False)
    assert not (tmp_path / "features.jsonl").exists()
    assert res.results["meta"]["feature_cache"] is None


@agentic_required
def test_realcg_run_report_marks_plumbing(tmp_path):
    res = run("real_cg", "smoke", tmp_path, real_cg_stub=True, n_boot=50)
    for name in ("results.json", "metrics.csv", "experiment_report.md",
                 "roc_overlay.png", "catch_at_budget.png", "signal_importance.csv"):
        assert (tmp_path / name).exists() and (tmp_path / name).stat().st_size > 0
    report = (tmp_path / "experiment_report.md").read_text()
    assert "Plumbing validation, not evidence" in report
    assert res.results["meta"]["feature_provenance"].startswith("real_cg")
    # By construction (constant stub state) the internal signal cannot improve AUROC.
    cfg = res.results["configs"]
    assert cfg["C4_plus_internal_signals"]["auroc"] == pytest.approx(
        cfg["C3_approval_risk_confidence"]["auroc"], abs=1e-9)
