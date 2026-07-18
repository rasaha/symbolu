"""
test_confidence_baseline.py — the real C3 (verbalized) / C3b (top-1) confidence baselines.

Covers the parts that need no GPU/torch:
  - _parse_confidence robustness (the verbalized-score parser),
  - the FeatureVector schema gains text_confidence_top1 (defaulted),
  - mock-mode run wires the C3b variant config + the C4-vs-C3b DeLong block +
    the inv_text_confidence_top1 importance column,
  - the StubCGLLMAdapter path falls back to the neutral placeholder for BOTH
    confidences (it cannot self-report), flagged in provenance.

It does NOT exercise live elicitation (that needs a real checkpoint + torch) and makes
no claim about whether internal signals beat either confidence baseline.
"""

from __future__ import annotations

import pytest

from experiments.signal_gov.configs import VARIANT_CONFIG_ORDER
from experiments.signal_gov.dataset import load_smoke
from experiments.signal_gov.features import (
    FEATURE_FIELDS,
    FeatureVector,
    _confidence_prompt,
    _parse_confidence,
)
from experiments.signal_gov.run_experiment import run


# ----- verbalized-score parser -------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("0.85", 0.85),
    ("Safety score: 0.2 because it deletes data", 0.2),
    (".7", 0.7),
    ("1", 1.0),
    ("0", 0.0),
    ("80%", 0.8),     # percentage -> /100
    ("80", 0.8),      # bare >1 -> treated as percentage
    ("the model says 0.33 out of 1.00", 0.33),  # first match wins
])
def test_parse_confidence_valid(text, expected):
    assert _parse_confidence(text) == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("text", ["", "no number at all", "150", "9999"])
def test_parse_confidence_unparseable_returns_none(text):
    assert _parse_confidence(text) is None


def test_confidence_prompt_mentions_action_and_asks_for_number():
    s = load_smoke()[0]
    p = _confidence_prompt(s)
    assert s.proposed_tool in p
    assert "0.00" in p and "1.00" in p  # the elicited scale


# ----- schema + defaults -------------------------------------------------------

def test_feature_vector_has_top1_field_defaulted():
    assert "text_confidence_top1" in FEATURE_FIELDS
    fv = FeatureVector(
        scenario_id="x", risk_norm=0.5, text_confidence=0.5, entropy=0.5,
        coherence=0.5, vritti_risk=0.5, jepa_disagreement=0.5, provenance="t")
    assert fv.text_confidence_top1 == 0.5                 # default
    assert "text_confidence_top1" in fv.to_dict()


# ----- variant config is wired through run() -----------------------------------

def test_mock_run_wires_c3b_variant_and_delong(tmp_path):
    res = run("mock", "smoke", tmp_path, n_boot=50, make_plots=False)
    r = res.results
    # C1..C4 stay the ONLY nested configs (ordering check unaffected).
    assert set(r["configs"].keys()) == {
        "C1_approval_only", "C2_approval_risk",
        "C3_approval_risk_confidence", "C4_plus_internal_signals"}
    # C3b lives in a separate variant block.
    assert VARIANT_CONFIG_ORDER == ["C3b_confidence_top1"]
    assert "C3b_confidence_top1" in r["variant_configs"]
    assert "auroc" in r["variant_configs"]["C3b_confidence_top1"]
    # C4-vs-C3b DeLong block + the new importance column exist.
    db = r["delong_c4_vs_c3b"]
    assert db is not None and "delta_auroc" in db and "p_value" in db
    assert "inv_text_confidence_top1" in r["signal_importance"]


def test_mock_report_has_baseline_sensitivity_section(tmp_path):
    run("mock", "smoke", tmp_path, n_boot=50, make_plots=False)
    report = (tmp_path / "experiment_report.md").read_text()
    assert "Baseline sensitivity" in report
    assert "C3b" in report and "C4 vs C3b" in report


# ----- stub path: neutral placeholder for BOTH confidences ---------------------

def _agentic_available() -> bool:
    try:
        import agentic.agentic_framework.llm_adapters  # noqa: F401
        return True
    except Exception:
        return False


agentic_required = pytest.mark.skipif(
    not _agentic_available(),
    reason="stub real_cg path needs the in-repo agentic framework (numpy only; no torch)",
)


@agentic_required
def test_stub_uses_placeholder_for_both_confidences():
    from experiments.signal_gov.features import RealCGFeatureExtractor

    fv = RealCGFeatureExtractor(use_stub=True).extract(load_smoke()[0])
    # The stub cannot self-report; both confidence baselines stay neutral + flagged.
    assert fv.text_confidence == pytest.approx(0.5, abs=1e-9)
    assert fv.text_confidence_top1 == pytest.approx(0.5, abs=1e-9)
    assert "conf[stub_placeholder]" in fv.provenance
