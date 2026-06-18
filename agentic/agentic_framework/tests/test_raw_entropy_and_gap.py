"""
Tests for the raw-entropy signal adapter, the confidence-risk gap, and signal config.

These are the pivot primitives: raw next-token entropy as the first-class uncertainty
signal, and "confident-but-uncertain -> escalate". Provider-agnostic + fail-closed.
"""

import math

import pytest

from agentic.agentic_framework.signal_adapters.raw_entropy_adapter import (
    RawEntropyResolution, predictive_entropy_from_logits,
    predictive_entropy_from_logprobs, resolve_raw_entropy_signal,
)
from agentic.agentic_framework.signal_adapters.confidence_risk_gap import (
    assess_confidence_risk_gap,
)
from agentic.agentic_framework.signal_config import (
    DEFAULT_SIGNAL_CONFIG, SignalConfig, SignalMode,
)


# ----- signal config defaults encode the pivot --------------------------------

def test_default_config_promotes_raw_entropy_and_demotes_cg():
    c = DEFAULT_SIGNAL_CONFIG
    assert c.enable_raw_entropy_signal and c.raw_entropy_mode == SignalMode.STABLE
    assert not c.enable_cg_state_signals
    assert c.cg_state_signals_mode == SignalMode.EXPERIMENTAL
    assert c.enable_confidence_risk_gap


def test_risk_minimum_gate():
    c = SignalConfig(min_risk_level_for_gap="write")
    assert not c.risk_meets_gap_minimum("read_only")
    assert c.risk_meets_gap_minimum("write")
    assert c.risk_meets_gap_minimum("destructive")


# ----- raw entropy: provider-agnostic computation -----------------------------

def test_entropy_from_logits_uniform_is_max_peaked_is_min():
    assert predictive_entropy_from_logits([0, 0, 0, 0]) == pytest.approx(1.0, abs=1e-9)
    assert predictive_entropy_from_logits([20, 0, 0, 0]) == pytest.approx(0.0, abs=1e-3)


def test_entropy_from_logprobs_topk_in_range():
    near_uniform = [math.log(0.25)] * 4
    peaked = [math.log(0.97), math.log(0.01), math.log(0.01), math.log(0.01)]
    assert predictive_entropy_from_logprobs(near_uniform) == pytest.approx(1.0, abs=1e-6)
    assert predictive_entropy_from_logprobs(peaked) < 0.3


def test_resolve_prefers_scalar_then_logits_then_logprobs():
    assert resolve_raw_entropy_signal(raw_entropy=0.8).source == "scalar"
    assert resolve_raw_entropy_signal(logits=[0, 0, 0, 0]).source == "logits"
    assert resolve_raw_entropy_signal(logprobs=[math.log(0.5), math.log(0.5)]).source == "logprobs"


def test_resolve_degrades_gracefully_when_no_source():
    r = resolve_raw_entropy_signal()
    assert isinstance(r, RawEntropyResolution)
    assert not r.available and r.confidence_penalty == 0.0 and r.raw_entropy is None


def test_resolve_disabled_is_unavailable():
    r = resolve_raw_entropy_signal(raw_entropy=0.9, enabled=False)
    assert not r.available and r.confidence_penalty == 0.0


def test_confidence_penalty_bounds():
    assert resolve_raw_entropy_signal(raw_entropy=0.1).confidence_penalty == 0.0
    assert resolve_raw_entropy_signal(raw_entropy=0.95).confidence_penalty == pytest.approx(0.15)
    mid = resolve_raw_entropy_signal(raw_entropy=0.5).confidence_penalty
    assert 0.0 < mid < 0.15


# ----- confidence-risk gap: the falsification finding -------------------------

def _re(value):
    return resolve_raw_entropy_signal(raw_entropy=value)


def test_gap_escalates_on_confident_but_uncertain_risky_action():
    # The fooled-unsafe signature: says safe, internally uncertain, non-trivial tool.
    r = assess_confidence_risk_gap(
        verbalized_safety_confidence=0.9, raw_entropy_resolution=_re(0.85),
        tool_risk_level="destructive")
    assert r.escalate and r.level == "confirm" and r.available
    assert r.gap == pytest.approx(0.75, abs=1e-6)   # 0.9 + 0.85 - 1
    assert "internally uncertain" in r.reason


def test_gap_no_escalate_when_confident_and_certain():
    r = assess_confidence_risk_gap(
        verbalized_safety_confidence=0.9, raw_entropy_resolution=_re(0.1),
        tool_risk_level="destructive")
    assert not r.escalate and r.available and r.gap == 0.0


def test_gap_no_escalate_when_model_is_appropriately_unsure():
    # Low verbalized confidence -> the model already flags doubt; gap should not fire.
    r = assess_confidence_risk_gap(
        verbalized_safety_confidence=0.2, raw_entropy_resolution=_re(0.85),
        tool_risk_level="destructive")
    assert not r.escalate and r.available


def test_gap_skips_low_risk_tools():
    r = assess_confidence_risk_gap(
        verbalized_safety_confidence=0.9, raw_entropy_resolution=_re(0.9),
        tool_risk_level="read_only")
    assert not r.escalate and "risk=read_only" in r.reason


def test_gap_degrades_when_raw_entropy_unavailable():
    r = assess_confidence_risk_gap(
        verbalized_safety_confidence=0.9,
        raw_entropy_resolution=resolve_raw_entropy_signal(),  # unavailable
        tool_risk_level="destructive")
    assert not r.escalate and not r.available
    assert "degrading to verbalized confidence" in r.reason


def test_gap_not_assessed_without_verbalized_confidence():
    r = assess_confidence_risk_gap(
        verbalized_safety_confidence=None, raw_entropy_resolution=_re(0.9),
        tool_risk_level="destructive")
    assert not r.escalate and not r.available


def test_gap_disabled_via_config():
    cfg = SignalConfig(enable_confidence_risk_gap=False)
    r = assess_confidence_risk_gap(
        verbalized_safety_confidence=0.9, raw_entropy_resolution=_re(0.9),
        tool_risk_level="destructive", config=cfg)
    assert not r.escalate and "disabled" in r.reason
