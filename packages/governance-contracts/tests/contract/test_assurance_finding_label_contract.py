"""AE-3 / AE-5 — the neutral assurance-finding label: structure, determinism, the
lines AE-3 draws, and its deliberate separation from ``VerificationStatus`` and the
two other labels.

These tests prove the family accepts any non-blank text as a label (there is no
recognized set), refuses a blank or malformed one at construction, digests
deterministically, never reads a clock, defines no ordering, severity, score or
verification beyond exact equality, ships no enum, is not interchangeable with
``VerificationStatus``, ``DataClassificationLabel`` or ``VendorRiskLabel``, and
leaves every frozen provider dataclass untouched.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import pathlib

import pytest

import ugence_governance_contracts as g
from ugence_governance_contracts import api
from ugence_governance_contracts.contracts import assurance_finding
from ugence_governance_contracts.contracts.assurance_finding import (
    AssuranceFindingContractError,
    AssuranceFindingLabel,
)
from ugence_governance_contracts.contracts.data_classification import DataClassificationLabel
from ugence_governance_contracts.contracts.evidence import VerificationStatus
from ugence_governance_contracts.contracts.vendor_risk import VendorRiskLabel


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_a_label_is_one_stripped_text_field():
    label = AssuranceFindingLabel("  prompt-injection-succeeded  ")
    assert label.label == "prompt-injection-succeeded"
    assert [f.name for f in dataclasses.fields(label)] == ["label"]


def test_unknown_non_empty_labels_are_accepted_because_there_is_no_recognized_set():
    for text in ("prompt-injection-succeeded", "no-finding", "data-exfiltration/partial",
                 "whatever-the-team-calls-it", "越狱成功", "T1 confirmed", "needs-retest; flaky"):
        assert AssuranceFindingLabel(text).label == text


def test_a_blank_label_is_refused():
    for blank in ("", "   ", "\t", "\n \t"):
        with pytest.raises(AssuranceFindingContractError, match="non-empty"):
            AssuranceFindingLabel(blank)


def test_a_non_string_label_is_refused():
    for bad in (None, 3, 0.9, b"finding", ["finding"], object(), VerificationStatus.VERIFIED):
        with pytest.raises(AssuranceFindingContractError, match="must be a string"):
            AssuranceFindingLabel(bad)  # type: ignore[arg-type]


def test_a_label_with_control_characters_or_line_breaks_is_refused():
    for bad in ("fin\nding", "fin\rding", "fin\x00ding", "fin\x7fding", "a\x1fb"):
        with pytest.raises(AssuranceFindingContractError, match="control characters"):
            AssuranceFindingLabel(bad)
    assert AssuranceFindingLabel("T1 confirmed").label == "T1 confirmed"


def test_a_label_is_frozen():
    label = AssuranceFindingLabel("no-finding")
    with pytest.raises(dataclasses.FrozenInstanceError):
        label.label = "finding"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_equal_labels_share_one_digest_and_different_text_changes_it():
    a = AssuranceFindingLabel("no-finding")
    assert a.canonical_digest() == AssuranceFindingLabel(" no-finding ").canonical_digest()
    assert a.canonical_bytes() == b'{"label":"no-finding"}'
    assert len(a.canonical_digest()) == 64
    assert a.canonical_digest() != AssuranceFindingLabel("No-Finding").canonical_digest()
    assert a.canonical_digest() != AssuranceFindingLabel("finding").canonical_digest()


def test_equality_is_exact_text_equality_and_nothing_else():
    assert AssuranceFindingLabel("x") == AssuranceFindingLabel(" x ")
    assert AssuranceFindingLabel("x") != AssuranceFindingLabel("X")
    assert hash(AssuranceFindingLabel("x")) == hash(AssuranceFindingLabel(" x "))


def test_the_family_reads_no_clock():
    tree = ast.parse(pathlib.Path(assurance_finding.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                "uuid4", "random"), name


# --------------------------------------------------------------------------- #
# The lines AE-3 draws: no ordering, severity, score or implied verification
# --------------------------------------------------------------------------- #
def test_labels_cannot_be_ordered():
    assert AssuranceFindingLabel.__dataclass_params__.order is False
    for dunder in ("__lt__", "__le__", "__gt__", "__ge__"):
        assert getattr(AssuranceFindingLabel, dunder) is getattr(object, dunder), dunder
    with pytest.raises(TypeError):
        sorted([AssuranceFindingLabel("critical"), AssuranceFindingLabel("low")])
    with pytest.raises(TypeError):
        AssuranceFindingLabel("low") < AssuranceFindingLabel("critical")  # type: ignore[operator]
    with pytest.raises(TypeError):
        max(AssuranceFindingLabel("low"), AssuranceFindingLabel("critical"))


def test_no_severity_score_or_verification_method_exists():
    surface = {n for n in dir(AssuranceFindingLabel("no-finding")) if not n.startswith("_")}
    assert surface == {"label", "canonical_bytes", "canonical_digest"}
    for forbidden in ("severity", "score", "grade", "level", "tier", "rank", "cvss", "weight",
                      "is_verified", "verified", "verification_status", "is_true", "is_finding",
                      "is_exploitable", "dominates", "compare", "normalize", "lower", "upper",
                      "casefold", "matches"):
        assert forbidden not in surface, forbidden


def test_no_enum_taxonomy_or_recognized_set_ships_with_the_family():
    assert assurance_finding.__all__ == ["AssuranceFindingContractError", "AssuranceFindingLabel"]
    enums = [n for n in dir(assurance_finding)
             if isinstance(getattr(assurance_finding, n), type)
             and issubclass(getattr(assurance_finding, n), enum.Enum)]
    assert enums == []
    tree = ast.parse(pathlib.Path(assurance_finding.__file__).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                assert getattr(target, "id", "") in ("__all__",), getattr(target, "id", "")


def test_the_family_verifies_nothing_and_grants_no_authority():
    for forbidden in ("verify", "assess", "evaluate", "decide", "approve", "authorize", "admit",
                      "score", "grade", "probe", "run", "attack"):
        assert not hasattr(AssuranceFindingLabel, forbidden), forbidden
        assert not hasattr(assurance_finding, forbidden), forbidden


# --------------------------------------------------------------------------- #
# Not VerificationStatus, not the other labels (AE-3)
# --------------------------------------------------------------------------- #
def test_the_label_is_not_verification_status_and_never_implies_it():
    """VerificationStatus says whether a claim was checked; the label says what was
    found. Two statements, two types, no bridge."""

    assert not issubclass(AssuranceFindingLabel, enum.Enum)
    assert not isinstance(AssuranceFindingLabel("VERIFIED"), VerificationStatus)
    assert AssuranceFindingLabel("VERIFIED") != VerificationStatus.VERIFIED
    assert AssuranceFindingLabel("VERIFIED") != "VERIFIED"
    # The enum is untouched: the same three members, nothing added for findings.
    assert [m.value for m in VerificationStatus] == [
        "UNVERIFIED", "VERIFICATION_FAILED", "VERIFIED"]


def test_the_label_is_not_the_other_two_labels():
    for other in (DataClassificationLabel, VendorRiskLabel):
        assert AssuranceFindingLabel is not other
        assert not issubclass(AssuranceFindingLabel, other)
        assert not issubclass(other, AssuranceFindingLabel)
        assert AssuranceFindingLabel("x") != other("x")
        assert not isinstance(AssuranceFindingLabel("x"), other)


# --------------------------------------------------------------------------- #
# Additive compatibility
# --------------------------------------------------------------------------- #
def test_ae5_is_additive_and_the_provider_surface_is_untouched():
    assert g.CONTRACT_VERSION == "1.0.0"
    assert g.__version__ == "0.8.0"
    for name in ("ActionGovernanceRequest", "ActionGovernanceResult",
                 "ExecutionDispatchRequest", "ExecutionDispatchResult",
                 "AssertionGovernanceRequest", "AssertionGovernanceResult",
                 "EvidenceReference", "EvidenceProvenance"):
        fields = {f.name for f in dataclasses.fields(getattr(api, name))}
        assert not {"finding", "finding_label", "assurance", "assurance_finding"} & fields, name


def test_the_family_is_exported_where_vr5_is():
    for name in ("AssuranceFindingLabel", "AssuranceFindingContractError"):
        assert name in api.__all__
        assert getattr(api, name) is getattr(g, name)
        from ugence_governance_contracts import contracts

        assert name in contracts.__all__
