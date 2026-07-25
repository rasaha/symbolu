"""Scoring-scale definition tests (no scores)."""

from __future__ import annotations

import pytest

from ai_hiring.rubrics import STANDARD_SCALES, ScaleType, ScoringScale, is_standard_scale


def test_standard_scales_present():
    for sid in ("scale.1_5", "scale.0_10", "scale.percentage", "scale.binary",
                "scale.pass_fail"):
        assert is_standard_scale(sid)
        assert STANDARD_SCALES[sid].scale_id == sid


def test_scale_metadata():
    s = STANDARD_SCALES["scale.1_5"]
    assert (s.minimum, s.maximum) == (1, 5)
    assert s.labels == ("1", "2", "3", "4", "5")
    assert s.interpretation


def test_max_below_min_rejected():
    with pytest.raises(Exception):
        ScoringScale(scale_id="x", scale_type=ScaleType.ZERO_TO_TEN, minimum=10, maximum=0)


def test_binary_must_span_0_1():
    with pytest.raises(Exception):
        ScoringScale(scale_id="x", scale_type=ScaleType.BINARY, minimum=0, maximum=5)


def test_pass_fail_span():
    s = ScoringScale(scale_id="pf", scale_type=ScaleType.PASS_FAIL, minimum=0, maximum=1,
                     labels=("FAIL", "PASS"))
    assert s.labels == ("FAIL", "PASS")


def test_custom_scale_requires_labels():
    with pytest.raises(Exception):
        ScoringScale(scale_id="c", scale_type=ScaleType.CUSTOM, minimum=0, maximum=3)


def test_custom_scale_valid():
    s = ScoringScale(scale_id="c", scale_type=ScaleType.CUSTOM, minimum=0, maximum=2,
                     labels=("low", "mid", "high"), precision=0)
    assert s.scale_type is ScaleType.CUSTOM


def test_negative_precision_rejected():
    with pytest.raises(Exception):
        ScoringScale(scale_id="c", scale_type=ScaleType.PERCENTAGE, minimum=0, maximum=100,
                     precision=-1)


def test_unknown_scale_not_standard():
    assert not is_standard_scale("scale.made_up")


def test_scale_is_frozen():
    from pydantic import ValidationError
    s = STANDARD_SCALES["scale.1_5"]
    with pytest.raises(ValidationError):
        s.minimum = 0
