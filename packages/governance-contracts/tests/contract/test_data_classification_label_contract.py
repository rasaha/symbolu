"""DE-5 — the neutral data-classification label: structure, determinism, and the
lines DE-3 draws.

These tests prove the family accepts any non-blank text as a label (there is no
recognized set), refuses a blank or malformed one at construction, digests
deterministically, never reads a clock, defines no ordering or comparison beyond
exact equality, ships no enum, and leaves every frozen provider dataclass untouched.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

import ugence_governance_contracts as g
from ugence_governance_contracts import api
from ugence_governance_contracts.contracts import data_classification
from ugence_governance_contracts.contracts.data_classification import (
    DataClassificationContractError,
    DataClassificationLabel,
)


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_a_label_is_one_stripped_text_field():
    label = DataClassificationLabel("  confidential  ")
    assert label.label == "confidential"
    assert [f.name for f in dataclasses.fields(label)] == ["label"]


def test_unknown_labels_are_accepted_because_there_is_no_recognized_set():
    """DE-3: no enum, no taxonomy. Whatever the organization calls it is a label."""

    for text in ("confidential", "PII", "annex-iii/5(a)", "whatever-the-org-calls-it",
                 "秘密", "tier 3", "restricted; export-controlled"):
        assert DataClassificationLabel(text).label == text


def test_a_blank_label_is_refused():
    for blank in ("", "   ", "\t", "\n \t"):
        with pytest.raises(DataClassificationContractError, match="non-empty"):
            DataClassificationLabel(blank)


def test_a_non_string_label_is_refused():
    for bad in (None, 3, b"confidential", ["confidential"], object()):
        with pytest.raises(DataClassificationContractError, match="must be a string"):
            DataClassificationLabel(bad)  # type: ignore[arg-type]


def test_a_label_with_control_characters_or_line_breaks_is_refused():
    for bad in ("con\nfidential", "con\rfidential", "con\x00fidential", "con\x7ffidential",
                "a\x1fb"):
        with pytest.raises(DataClassificationContractError, match="control characters"):
            DataClassificationLabel(bad)
    # Interior spaces and tabs are ordinary text, not structure.
    assert DataClassificationLabel("tier 3").label == "tier 3"


def test_a_label_is_frozen():
    label = DataClassificationLabel("confidential")
    with pytest.raises(dataclasses.FrozenInstanceError):
        label.label = "public"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_equal_labels_share_one_digest_and_different_text_changes_it():
    a = DataClassificationLabel("confidential")
    assert a.canonical_digest() == DataClassificationLabel(" confidential ").canonical_digest()
    assert a.canonical_bytes() == b'{"label":"confidential"}'
    assert len(a.canonical_digest()) == 64
    assert a.canonical_digest() != DataClassificationLabel("Confidential").canonical_digest()
    assert a.canonical_digest() != DataClassificationLabel("public").canonical_digest()


def test_equality_is_exact_text_equality_and_nothing_else():
    """No case folding, no normalization: the package cannot know two spellings
    are "really" the same label, and does not pretend to."""

    assert DataClassificationLabel("confidential") == DataClassificationLabel("confidential")
    assert DataClassificationLabel("confidential") != DataClassificationLabel("Confidential")
    # Equality holds over the stripped text, so surrounding whitespace is not a difference.
    assert DataClassificationLabel("confidential") == DataClassificationLabel(" confidential ")
    assert hash(DataClassificationLabel("x")) == hash(DataClassificationLabel(" x "))


def test_the_family_reads_no_clock():
    tree = ast.parse(pathlib.Path(data_classification.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                "uuid4", "random"), name


# --------------------------------------------------------------------------- #
# The lines DE-3 draws: no ordering, no comparison, no vocabulary
# --------------------------------------------------------------------------- #
def test_no_ordering_operation_exists():
    """``order=False`` and no rich comparison of its own: sorting labels raises
    rather than inventing a hierarchy."""

    assert DataClassificationLabel.__dataclass_params__.order is False
    for dunder in ("__lt__", "__le__", "__gt__", "__ge__"):
        assert getattr(DataClassificationLabel, dunder) is getattr(object, dunder), dunder
    with pytest.raises(TypeError):
        sorted([DataClassificationLabel("b"), DataClassificationLabel("a")])
    with pytest.raises(TypeError):
        DataClassificationLabel("a") < DataClassificationLabel("b")  # type: ignore[operator]


def test_no_comparison_severity_or_compatibility_method_exists():
    surface = {n for n in dir(DataClassificationLabel("confidential")) if not n.startswith("_")}
    assert surface == {"label", "canonical_bytes", "canonical_digest"}
    for forbidden in ("dominates", "is_compatible_with", "compatible", "rank", "severity",
                      "level", "tier", "compare", "normalize", "lower", "upper", "casefold",
                      "matches", "classify", "is_higher_than", "includes", "implies"):
        assert forbidden not in surface, forbidden


def test_no_enum_taxonomy_or_recognized_set_ships_with_the_family():
    import enum

    assert data_classification.__all__ == [
        "DataClassificationContractError", "DataClassificationLabel"]
    enums = [n for n in dir(data_classification)
             if isinstance(getattr(data_classification, n), type)
             and issubclass(getattr(data_classification, n), enum.Enum)]
    assert enums == []
    source = pathlib.Path(data_classification.__file__).read_text()
    tree = ast.parse(source)
    # No module-level constant lists a recognized vocabulary.
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = getattr(target, "id", "")
                assert name in ("__all__",), name


def test_the_family_is_not_a_classifier_a_policy_or_an_authority():
    for forbidden in ("classify", "evaluate", "decide", "admit", "authorize", "permit",
                      "redact", "minimize", "enforce"):
        assert not hasattr(DataClassificationLabel, forbidden), forbidden
        assert not hasattr(data_classification, forbidden), forbidden


# --------------------------------------------------------------------------- #
# Additive compatibility
# --------------------------------------------------------------------------- #
def test_de5_is_additive_and_the_provider_surface_is_untouched():
    assert g.CONTRACT_VERSION == "1.0.0"
    assert g.__version__ == "0.6.0"
    for name in ("ActionGovernanceRequest", "ActionGovernanceResult",
                 "ExecutionDispatchRequest", "ExecutionDispatchResult",
                 "AssertionGovernanceRequest", "AssertionGovernanceResult"):
        fields = {f.name for f in dataclasses.fields(getattr(api, name))}
        assert not {"classification", "classification_label", "data_classification"} & fields, name


def test_the_family_is_exported_where_g4_is():
    for name in ("DataClassificationLabel", "DataClassificationContractError"):
        assert name in api.__all__
        assert getattr(api, name) is getattr(g, name)
        from ugence_governance_contracts import contracts

        assert name in contracts.__all__
