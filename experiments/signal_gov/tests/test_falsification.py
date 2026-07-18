"""
test_falsification.py — the fabrication probe set + the conditional decision rule.

Torch-free: the scenario set is oracle-labeled, and the analysis is pure numpy, so every
verdict branch is exercised here without a model. The live run (run.py) is GPU-only.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.signal_gov.falsification.analysis import (
    AUROC_SIGNAL, FOOL_RATE_MIN, VERDICT_DEPRIORITIZE_CONF, VERDICT_DEPRIORITIZE_PROJ,
    VERDICT_INCONCLUSIVE, VERDICT_KILL, VERDICT_SCALE, analyze, render_report,
)
from experiments.signal_gov.falsification.scenarios import load_fabrication
from experiments.signal_gov.oracle import verify_consistency


# ----- scenario set -----------------------------------------------------------

def test_fabrication_set_balanced_and_oracle_consistent():
    sc = load_fabrication()
    assert len(sc) == 20
    assert sum(s.unsafe_label for s in sc) == 10           # 10 matched pairs
    assert verify_consistency(sc) == []                    # labels == oracle, by construction
    assert all(s.category == "ambiguous_hallucinated" for s in sc)


def test_available_tools_in_prompt_and_hallucinated_tool_excluded():
    for s in load_fabrication():
        assert "Available tools:" in s.user_prompt        # info is in the MODEL's input
        avail = s.policy_context["available_tools"]
        if s.unsafe_label == 1:
            assert s.proposed_tool not in avail            # fabricated tool
        else:
            assert s.proposed_tool in avail                # grounded tool


# ----- decision rule: synthetic inputs for each branch ------------------------

_LABELS = np.array([1] * 10 + [0] * 10)          # 10 unsafe, 10 safe


def _signals(internal, raw, *, c3=None, c4=None, cg_ent=None):
    n = len(internal)
    return {
        "C3": np.full(n, 0.5) if c3 is None else np.asarray(c3, float),
        "C4": np.full(n, 0.5) if c4 is None else np.asarray(c4, float),
        "internal_risk": np.asarray(internal, float),
        "cg_state_entropy": np.full(n, 0.5) if cg_ent is None else np.asarray(cg_ent, float),
        "raw_entropy": np.asarray(raw, float),
    }


def test_verdict_kill_when_nothing_separates_the_fooled_subset():
    conf = np.full(20, 0.9)                       # all confident -> fool_rate = 1.0
    flat = np.tile([0.45, 0.55], 10)              # uncorrelated with label -> AUROC ~0.5
    r = analyze(labels=_LABELS, verbalized_conf=conf,
                signals=_signals(flat, flat), n_boot=50)
    assert r.fool_rate == pytest.approx(1.0)
    assert r.verdict == VERDICT_KILL
    assert r.headline == "KILL/DEPRIORITIZE"


def test_verdict_scale_when_internal_signals_separate():
    conf = np.full(20, 0.9)
    sep = np.array([0.85] * 10 + [0.15] * 10)     # internal_risk high on unsafe
    r = analyze(labels=_LABELS, verbalized_conf=conf,
                signals=_signals(sep, np.tile([0.5, 0.5], 10)), n_boot=50)
    assert r.aurocs_subset["internal_risk"] >= AUROC_SIGNAL
    assert r.verdict == VERDICT_SCALE
    assert r.headline == "SCALE"


def test_verdict_deprioritize_projection_when_only_raw_entropy_wins():
    conf = np.full(20, 0.9)
    flat = np.tile([0.45, 0.55], 10)              # internal_risk ~ chance
    raw = np.array([0.85] * 10 + [0.15] * 10)     # raw entropy separates
    r = analyze(labels=_LABELS, verbalized_conf=conf,
                signals=_signals(flat, raw), n_boot=50)
    assert r.verdict == VERDICT_DEPRIORITIZE_PROJ


def test_verdict_deprioritize_when_confidence_not_fooled():
    # Model is NOT fooled: low confidence on the unsafe items -> they leave the subset.
    conf = np.array([0.2] * 10 + [0.9] * 10)
    sep = np.array([0.85] * 10 + [0.15] * 10)
    r = analyze(labels=_LABELS, verbalized_conf=conf,
                signals=_signals(sep, sep), n_boot=50)
    assert r.fool_rate < FOOL_RATE_MIN
    assert r.verdict == VERDICT_DEPRIORITIZE_CONF


def test_verdict_inconclusive_when_subset_too_small_per_class():
    # High fool_rate (all unsafe confident) but only 1 confident safe item.
    conf = np.array([0.9] * 10 + [0.9] + [0.2] * 9)
    sep = np.array([0.85] * 10 + [0.15] * 10)
    r = analyze(labels=_LABELS, verbalized_conf=conf,
                signals=_signals(sep, sep), n_boot=50)
    assert r.confident_safe < 2
    assert r.verdict == VERDICT_INCONCLUSIVE


def test_render_report_contains_verdict_and_gates():
    conf = np.full(20, 0.9)
    flat = np.tile([0.45, 0.55], 10)
    r = analyze(labels=_LABELS, verbalized_conf=conf, signals=_signals(flat, flat), n_boot=50)
    md = render_report(r, provenance="real_cg:test")
    assert "Gate 1" in md and "Gate 2" in md
    assert r.headline in md and "fool_rate" in md
