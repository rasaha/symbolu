"""VR-3 / VR-5 — the neutral vendor-risk label: structure, determinism, the lines
VR-3 draws, and its deliberate separation from the data-classification label.

These tests prove the family accepts any non-blank text as a label (there is no
recognized set), refuses a blank or malformed one at construction, digests
deterministically, never reads a clock, defines no ordering, score or comparison
beyond exact equality, ships no enum, is not interchangeable with
``DataClassificationLabel``, and leaves every frozen provider dataclass untouched.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

import ugence_governance_contracts as g
from ugence_governance_contracts import api
from ugence_governance_contracts.contracts import vendor_risk
from ugence_governance_contracts.contracts.data_classification import DataClassificationLabel
from ugence_governance_contracts.contracts.vendor_risk import (
    VendorRiskContractError,
    VendorRiskLabel,
)


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_a_label_is_one_stripped_text_field():
    label = VendorRiskLabel("  elevated  ")
    assert label.label == "elevated"
    assert [f.name for f in dataclasses.fields(label)] == ["label"]


def test_unknown_non_empty_labels_are_accepted_because_there_is_no_recognized_set():
    """VR-3: no grade, no enum, no taxonomy. Whatever the organization calls it is a label."""

    for text in ("elevated", "tier-1-critical", "approved-with-conditions", "under-review",
                 "whatever-the-org-calls-it", "供应商风险", "sanctioned; do-not-use"):
        assert VendorRiskLabel(text).label == text


def test_a_blank_label_is_refused():
    for blank in ("", "   ", "\t", "\n \t"):
        with pytest.raises(VendorRiskContractError, match="non-empty"):
            VendorRiskLabel(blank)


def test_a_non_string_label_is_refused():
    for bad in (None, 3, 0.7, b"elevated", ["elevated"], object()):
        with pytest.raises(VendorRiskContractError, match="must be a string"):
            VendorRiskLabel(bad)  # type: ignore[arg-type]


def test_a_label_with_control_characters_or_line_breaks_is_refused():
    for bad in ("ele\nvated", "ele\rvated", "ele\x00vated", "ele\x7fvated", "a\x1fb"):
        with pytest.raises(VendorRiskContractError, match="control characters"):
            VendorRiskLabel(bad)
    assert VendorRiskLabel("tier 1").label == "tier 1"


def test_a_label_is_frozen():
    label = VendorRiskLabel("elevated")
    with pytest.raises(dataclasses.FrozenInstanceError):
        label.label = "low"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_equal_labels_share_one_digest_and_different_text_changes_it():
    a = VendorRiskLabel("elevated")
    assert a.canonical_digest() == VendorRiskLabel(" elevated ").canonical_digest()
    assert a.canonical_bytes() == b'{"label":"elevated"}'
    assert len(a.canonical_digest()) == 64
    assert a.canonical_digest() != VendorRiskLabel("Elevated").canonical_digest()
    assert a.canonical_digest() != VendorRiskLabel("low").canonical_digest()


def test_equality_is_exact_text_equality_and_nothing_else():
    assert VendorRiskLabel("elevated") == VendorRiskLabel("elevated")
    assert VendorRiskLabel("elevated") == VendorRiskLabel(" elevated ")
    assert VendorRiskLabel("elevated") != VendorRiskLabel("Elevated")
    assert hash(VendorRiskLabel("x")) == hash(VendorRiskLabel(" x "))


def test_the_family_reads_no_clock():
    tree = ast.parse(pathlib.Path(vendor_risk.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                "uuid4", "random"), name


# --------------------------------------------------------------------------- #
# The lines VR-3 draws: no ordering, no score, no grade, no eligibility
# --------------------------------------------------------------------------- #
def test_labels_cannot_be_ordered():
    """``order=False`` and no rich comparison of its own: sorting labels raises
    rather than inventing a hierarchy of risk."""

    assert VendorRiskLabel.__dataclass_params__.order is False
    for dunder in ("__lt__", "__le__", "__gt__", "__ge__"):
        assert getattr(VendorRiskLabel, dunder) is getattr(object, dunder), dunder
    with pytest.raises(TypeError):
        sorted([VendorRiskLabel("high"), VendorRiskLabel("low")])
    with pytest.raises(TypeError):
        VendorRiskLabel("low") < VendorRiskLabel("high")  # type: ignore[operator]
    with pytest.raises(TypeError):
        max(VendorRiskLabel("low"), VendorRiskLabel("high"))


def test_no_score_grade_severity_or_eligibility_method_exists():
    surface = {n for n in dir(VendorRiskLabel("elevated")) if not n.startswith("_")}
    assert surface == {"label", "canonical_bytes", "canonical_digest"}
    for forbidden in ("score", "grade", "severity", "level", "tier", "rank", "dominates",
                      "is_eligible", "eligible", "is_compatible_with", "compare", "normalize",
                      "lower", "upper", "casefold", "matches", "is_higher_than", "is_approved",
                      "is_sanctioned", "weight", "numeric"):
        assert forbidden not in surface, forbidden


def test_no_enum_taxonomy_or_recognized_set_ships_with_the_family():
    import enum

    assert vendor_risk.__all__ == ["VendorRiskContractError", "VendorRiskLabel"]
    enums = [n for n in dir(vendor_risk)
             if isinstance(getattr(vendor_risk, n), type)
             and issubclass(getattr(vendor_risk, n), enum.Enum)]
    assert enums == []
    tree = ast.parse(pathlib.Path(vendor_risk.__file__).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                assert getattr(target, "id", "") in ("__all__",), getattr(target, "id", "")


def test_the_family_makes_no_risk_judgment_and_grants_no_authority():
    for forbidden in ("assess", "evaluate", "decide", "approve", "authorize", "permit",
                      "resolve", "verify", "fetch", "score", "grade"):
        assert not hasattr(VendorRiskLabel, forbidden), forbidden
        assert not hasattr(vendor_risk, forbidden), forbidden


# --------------------------------------------------------------------------- #
# A separate dimension from data classification (VR-3)
# --------------------------------------------------------------------------- #
def test_the_vendor_risk_label_is_not_the_data_classification_label():
    """Two types, two dimensions: the same text in each is not the same value."""

    assert VendorRiskLabel is not DataClassificationLabel
    assert not issubclass(VendorRiskLabel, DataClassificationLabel)
    assert not issubclass(DataClassificationLabel, VendorRiskLabel)
    assert VendorRiskLabel("elevated") != DataClassificationLabel("elevated")
    assert not isinstance(VendorRiskLabel("elevated"), DataClassificationLabel)
    assert not isinstance(DataClassificationLabel("elevated"), VendorRiskLabel)


# --------------------------------------------------------------------------- #
# Additive compatibility
# --------------------------------------------------------------------------- #
def test_vr5_is_additive_and_the_provider_surface_is_untouched():
    assert g.CONTRACT_VERSION == "1.0.0"
    assert g.__version__ == "0.8.0"
    for name in ("ActionGovernanceRequest", "ActionGovernanceResult",
                 "ExecutionDispatchRequest", "ExecutionDispatchResult",
                 "AssertionGovernanceRequest", "AssertionGovernanceResult"):
        fields = {f.name for f in dataclasses.fields(getattr(api, name))}
        assert not {"vendor", "vendor_ref", "vendor_risk", "risk_label"} & fields, name


def test_the_family_is_exported_where_de5_is():
    for name in ("VendorRiskLabel", "VendorRiskContractError"):
        assert name in api.__all__
        assert getattr(api, name) is getattr(g, name)
        from ugence_governance_contracts import contracts

        assert name in contracts.__all__
