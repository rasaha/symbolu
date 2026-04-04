"""
Tests for Phase4a Varna-Layer Lookup Adapter (O3)
==================================================

Verifies the phase4a adapter that bridges varna-layer interaction
lookups into the framework signal path.
"""

from __future__ import annotations

import json

import pytest

from agentic.agentic_framework.signal_adapters.phase4a_adapter import (
    VarnaLookupResolution,
    resolve_varna_lookup,
    resolve_varna_exists,
)


# =========================================================================
# VarnaLookupResolution contract
# =========================================================================

class TestVarnaLookupResolutionContract:
    """Verify the resolution dataclass contract."""

    def test_frozen(self) -> None:
        res = VarnaLookupResolution(available=False)
        with pytest.raises(AttributeError):
            res.available = True  # type: ignore[misc]

    def test_unavailable_defaults(self) -> None:
        res = VarnaLookupResolution(available=False)
        assert res.varna == ""
        assert res.layer == ""
        assert res.exists is False
        assert res.manifestation_positive == ""
        assert res.manifestation_negative == ""
        assert res.distortion_vector == ""
        assert res.sublimate_vector == ""

    def test_to_dict_structure(self) -> None:
        res = VarnaLookupResolution(
            available=True,
            varna="ka",
            layer="O3_EXECUTION",
            exists=True,
            manifestation_positive="positive text",
            manifestation_negative="negative text",
            distortion_vector="distortion",
            sublimate_vector="sublimation",
        )
        d = res.to_dict()
        assert d["available"] is True
        assert d["varna"] == "ka"
        assert d["layer"] == "O3_EXECUTION"
        assert d["exists"] is True
        assert d["manifestation_positive"] == "positive text"

    def test_to_dict_serializable(self) -> None:
        res = VarnaLookupResolution(available=True, varna="ka", layer="O3_EXECUTION")
        serialized = json.dumps(res.to_dict())
        assert isinstance(serialized, str)


# =========================================================================
# resolve_varna_lookup
# =========================================================================

class TestResolveVarnaLookup:
    """Verify the varna lookup resolve function."""

    def test_valid_pair(self) -> None:
        res = resolve_varna_lookup("ka", "O3_EXECUTION")
        assert res.available is True
        assert res.exists is True
        assert res.varna == "ka"
        assert res.layer == "O3_EXECUTION"
        assert len(res.manifestation_positive) > 0
        assert len(res.manifestation_negative) > 0

    def test_invalid_varna(self) -> None:
        res = resolve_varna_lookup("NONEXISTENT_VARNA", "O3_EXECUTION")
        # Fail-closed: should not raise, returns unavailable or not-exists
        assert isinstance(res, VarnaLookupResolution)
        assert isinstance(res.available, bool)

    def test_invalid_layer(self) -> None:
        res = resolve_varna_lookup("ka", "NONEXISTENT_LAYER")
        assert isinstance(res, VarnaLookupResolution)
        assert isinstance(res.available, bool)

    def test_both_invalid(self) -> None:
        res = resolve_varna_lookup("FAKE", "FAKE")
        assert isinstance(res, VarnaLookupResolution)
        assert isinstance(res.available, bool)

    def test_deterministic(self) -> None:
        res1 = resolve_varna_lookup("ka", "O3_EXECUTION")
        res2 = resolve_varna_lookup("ka", "O3_EXECUTION")
        assert res1.manifestation_positive == res2.manifestation_positive
        assert res1.manifestation_negative == res2.manifestation_negative
        assert res1.distortion_vector == res2.distortion_vector
        assert res1.sublimate_vector == res2.sublimate_vector

    def test_different_pairs_different_results(self) -> None:
        res1 = resolve_varna_lookup("ka", "O3_EXECUTION")
        res2 = resolve_varna_lookup("ka", "O5_COGNITION")
        if res1.exists and res2.exists:
            # At least one field should differ between different layers
            assert (
                res1.manifestation_positive != res2.manifestation_positive
                or res1.distortion_vector != res2.distortion_vector
            )

    def test_source_detail(self) -> None:
        res = resolve_varna_lookup("ka", "O3_EXECUTION")
        assert "phase4a" in res.source_detail

    def test_all_fields_are_strings(self) -> None:
        res = resolve_varna_lookup("ka", "O3_EXECUTION")
        assert isinstance(res.varna, str)
        assert isinstance(res.layer, str)
        assert isinstance(res.manifestation_positive, str)
        assert isinstance(res.manifestation_negative, str)
        assert isinstance(res.distortion_vector, str)
        assert isinstance(res.sublimate_vector, str)


# =========================================================================
# resolve_varna_exists
# =========================================================================

class TestResolveVarnaExists:
    """Verify the existence check function."""

    def test_valid_pair_exists(self) -> None:
        assert resolve_varna_exists("ka", "O3_EXECUTION") is True

    def test_invalid_varna_not_exists(self) -> None:
        assert resolve_varna_exists("NONEXISTENT", "O3_EXECUTION") is False

    def test_invalid_layer_not_exists(self) -> None:
        assert resolve_varna_exists("ka", "NONEXISTENT") is False

    def test_returns_bool(self) -> None:
        result = resolve_varna_exists("ka", "O3_EXECUTION")
        assert isinstance(result, bool)


# =========================================================================
# Fail-closed behavior
# =========================================================================

class TestFailClosed:
    """Verify fail-closed behavior (errors -> unavailable, never raise)."""

    def test_lookup_with_none_varna(self) -> None:
        res = resolve_varna_lookup(None, "O3_EXECUTION")  # type: ignore[arg-type]
        assert isinstance(res, VarnaLookupResolution)
        assert isinstance(res.available, bool)

    def test_lookup_with_none_layer(self) -> None:
        res = resolve_varna_lookup("ka", None)  # type: ignore[arg-type]
        assert isinstance(res, VarnaLookupResolution)
        assert isinstance(res.available, bool)

    def test_lookup_never_raises(self) -> None:
        for bad_v, bad_l in [(None, None), (42, "layer"), ("varna", []), ({}, True)]:
            res = resolve_varna_lookup(bad_v, bad_l)  # type: ignore[arg-type]
            assert isinstance(res, VarnaLookupResolution)

    def test_exists_never_raises(self) -> None:
        for bad_v, bad_l in [(None, None), (42, "layer"), ("varna", [])]:
            result = resolve_varna_exists(bad_v, bad_l)  # type: ignore[arg-type]
            assert isinstance(result, bool)


# =========================================================================
# Framework integration
# =========================================================================

class TestFrameworkIntegration:
    """Verify the adapter is properly wired into the signal_adapters package."""

    def test_importable_from_package(self) -> None:
        from agentic.agentic_framework.signal_adapters import (
            resolve_varna_lookup as pkg_lookup,
            resolve_varna_exists as pkg_exists,
            VarnaLookupResolution as PkgRes,
        )
        assert pkg_lookup is resolve_varna_lookup
        assert pkg_exists is resolve_varna_exists
        assert PkgRes is VarnaLookupResolution

    def test_in_package_all(self) -> None:
        from agentic.agentic_framework import signal_adapters
        assert "resolve_varna_lookup" in signal_adapters.__all__
        assert "resolve_varna_exists" in signal_adapters.__all__
        assert "VarnaLookupResolution" in signal_adapters.__all__


# =========================================================================
# Canonical source verification
# =========================================================================

class TestCanonicalSourceUsage:
    """Verify the adapter consumes the canonical phase4a module."""

    def test_lookup_matches_direct(self) -> None:
        from agentic.ontology.phase4a.lookup import lookup_interaction

        adapter_res = resolve_varna_lookup("ka", "O3_EXECUTION")
        direct = lookup_interaction("ka", "O3_EXECUTION")

        assert adapter_res.manifestation_positive == direct.manifestation_positive
        assert adapter_res.manifestation_negative == direct.manifestation_negative
        assert adapter_res.distortion_vector == direct.distortion_vector
        assert adapter_res.sublimate_vector == direct.sublimate_vector

    def test_exists_matches_direct(self) -> None:
        from agentic.ontology.phase4a.lookup import has_interaction

        assert resolve_varna_exists("ka", "O3_EXECUTION") == has_interaction("ka", "O3_EXECUTION")
        assert resolve_varna_exists("FAKE", "FAKE") == has_interaction("FAKE", "FAKE")
