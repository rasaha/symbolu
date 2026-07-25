"""Uncertainty contract tests."""

from __future__ import annotations

import pytest

from ai_hiring.rubrics import UncertaintyLevel, UncertaintyRule


def test_uncertainty_levels():
    assert {u.value for u in UncertaintyLevel} == {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}


def test_default_rule():
    rule = UncertaintyRule(capability_id="cap.python")
    assert rule.requires_uncertainty is True
    assert rule.default_level is UncertaintyLevel.UNKNOWN
    assert set(rule.allowed_levels) == set(UncertaintyLevel)


def test_default_must_be_in_allowed():
    with pytest.raises(Exception):
        UncertaintyRule(capability_id="c", default_level=UncertaintyLevel.HIGH,
                        allowed_levels=(UncertaintyLevel.LOW, UncertaintyLevel.UNKNOWN))


def test_allowed_levels_nonempty():
    with pytest.raises(Exception):
        UncertaintyRule(capability_id="c", allowed_levels=())


def test_restricted_levels():
    rule = UncertaintyRule(capability_id="c", default_level=UncertaintyLevel.LOW,
                           allowed_levels=(UncertaintyLevel.LOW, UncertaintyLevel.MEDIUM,
                                           UncertaintyLevel.HIGH))
    assert UncertaintyLevel.UNKNOWN not in rule.allowed_levels


def test_rule_is_frozen():
    from pydantic import ValidationError
    rule = UncertaintyRule(capability_id="c")
    with pytest.raises(ValidationError):
        rule.requires_uncertainty = False
