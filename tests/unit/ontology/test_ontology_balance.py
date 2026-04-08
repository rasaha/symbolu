"""
Tests for Ontology Balance Signal (O3)
=======================================

Verifies the mirror-pair balance resolution added to the ontology
adapter as a governance-ready structural equilibrium signal.
"""

from __future__ import annotations

import json

import pytest

from agentic.agentic_framework.signal_adapters.ontology_adapter import (
    OntologyBalanceResolution,
    resolve_ontology_balance,
)


# =========================================================================
# OntologyBalanceResolution contract
# =========================================================================

class TestBalanceResolutionContract:
    """Verify the balance resolution dataclass contract."""

    def test_frozen(self) -> None:
        res = OntologyBalanceResolution(available=False)
        with pytest.raises(AttributeError):
            res.available = True  # type: ignore[misc]

    def test_unavailable_defaults(self) -> None:
        res = OntologyBalanceResolution(available=False)
        assert res.balance_score == 0.0
        assert res.total_imbalance == 0.0
        assert res.dominant_state == ""
        assert res.pair_details == ()
        assert res.propagation_needed == ()

    def test_to_dict_structure(self) -> None:
        res = OntologyBalanceResolution(
            available=True,
            balance_score=0.75,
            total_imbalance=0.5,
            dominant_state="balanced",
            pair_details=(("ACTION_ABSOLUTE", 0.3, 0.4, 0.1, "balanced"),),
            propagation_needed=("ACTION_ABSOLUTE",),
        )
        d = res.to_dict()
        assert d["available"] is True
        assert d["balance_score"] == 0.75
        assert d["total_imbalance"] == 0.5
        assert d["dominant_state"] == "balanced"
        assert len(d["pair_details"]) == 1
        assert d["pair_details"][0]["pair"] == "ACTION_ABSOLUTE"
        assert d["pair_details"][0]["imbalance"] == 0.1
        assert d["propagation_needed"] == ["ACTION_ABSOLUTE"]

    def test_to_dict_serializable(self) -> None:
        res = OntologyBalanceResolution(
            available=True,
            balance_score=0.8,
            pair_details=(("P1", 0.1, 0.2, 0.1, "balanced"),),
        )
        serialized = json.dumps(res.to_dict())
        assert isinstance(serialized, str)
        deserialized = json.loads(serialized)
        assert deserialized["available"] is True


# =========================================================================
# resolve_ontology_balance
# =========================================================================

class TestResolveOntologyBalance:
    """Verify the balance resolve function."""

    def test_basic_balance(self) -> None:
        res = resolve_ontology_balance("The king ruled wisely over the land")
        assert res.available is True
        assert 0.0 <= res.balance_score <= 1.0
        assert res.total_imbalance >= 0.0

    def test_five_mirror_pairs(self) -> None:
        res = resolve_ontology_balance("A simple test sentence")
        assert res.available is True
        assert len(res.pair_details) == 5

    def test_pair_detail_structure(self) -> None:
        res = resolve_ontology_balance("The warrior fought bravely")
        assert res.available is True
        for pair_name, lo, hi, imb, state in res.pair_details:
            assert isinstance(pair_name, str)
            assert isinstance(lo, float)
            assert isinstance(hi, float)
            assert isinstance(imb, float)
            assert isinstance(state, str)

    def test_dominant_state_present(self) -> None:
        res = resolve_ontology_balance("Testing dominant state")
        assert res.available is True
        assert isinstance(res.dominant_state, str)
        assert len(res.dominant_state) > 0

    def test_propagation_needed_is_tuple_of_strings(self) -> None:
        res = resolve_ontology_balance("The soul contemplated the absolute")
        assert res.available is True
        assert isinstance(res.propagation_needed, tuple)
        for name in res.propagation_needed:
            assert isinstance(name, str)

    def test_empty_content(self) -> None:
        res = resolve_ontology_balance("")
        assert res.available is True
        # Empty text -> zero vector -> specific balance characteristics
        assert 0.0 <= res.balance_score <= 1.0

    def test_whitespace_only(self) -> None:
        res = resolve_ontology_balance("   ")
        assert res.available is True
        assert 0.0 <= res.balance_score <= 1.0

    def test_deterministic(self) -> None:
        text = "The empire rose and fell"
        res1 = resolve_ontology_balance(text)
        res2 = resolve_ontology_balance(text)
        assert res1.balance_score == res2.balance_score
        assert res1.total_imbalance == res2.total_imbalance
        assert res1.pair_details == res2.pair_details
        assert res1.propagation_needed == res2.propagation_needed

    def test_different_content_can_differ(self) -> None:
        res1 = resolve_ontology_balance("The warrior fought with great action and force")
        res2 = resolve_ontology_balance("The soul witnessed absolute stillness in silence")
        # Different texts may produce different balance profiles
        # (not guaranteed, but very likely with these contrasting texts)
        assert res1.available is True
        assert res2.available is True

    def test_source_detail(self) -> None:
        res = resolve_ontology_balance("test")
        assert "mirror_balance" in res.source_detail


# =========================================================================
# Fail-closed behavior
# =========================================================================

class TestFailClosed:
    """Verify fail-closed behavior."""

    def test_with_none_graceful(self) -> None:
        res = resolve_ontology_balance(None)  # type: ignore[arg-type]
        assert isinstance(res, OntologyBalanceResolution)
        assert isinstance(res.available, bool)

    def test_never_raises(self) -> None:
        for bad_input in [None, 42, [], {}, True, b"bytes"]:
            res = resolve_ontology_balance(bad_input)  # type: ignore[arg-type]
            assert isinstance(res, OntologyBalanceResolution)


# =========================================================================
# Framework integration
# =========================================================================

class TestFrameworkIntegration:
    """Verify the balance signal is wired into signal_adapters."""

    def test_importable_from_package(self) -> None:
        from agentic.agentic_framework.signal_adapters import (
            resolve_ontology_balance as pkg_balance,
            OntologyBalanceResolution as PkgRes,
        )
        assert pkg_balance is resolve_ontology_balance
        assert PkgRes is OntologyBalanceResolution

    def test_in_package_all(self) -> None:
        from agentic.agentic_framework import signal_adapters
        assert "resolve_ontology_balance" in signal_adapters.__all__
        assert "OntologyBalanceResolution" in signal_adapters.__all__


# =========================================================================
# Canonical source verification
# =========================================================================

class TestCanonicalSourceUsage:
    """Verify the adapter consumes canonical mirror_pairs module."""

    def test_balance_matches_direct(self) -> None:
        from agentic.ontology.backbone.encoder import encode_10d
        from agentic.ontology.backbone.mirror_pairs import compute_balance

        text = "Deterministic balance test"
        adapter_res = resolve_ontology_balance(text)
        direct_report = compute_balance(encode_10d(text))

        assert adapter_res.balance_score == direct_report.balance_score
        assert adapter_res.total_imbalance == direct_report.total_imbalance
        assert adapter_res.dominant_state == direct_report.dominant_state
