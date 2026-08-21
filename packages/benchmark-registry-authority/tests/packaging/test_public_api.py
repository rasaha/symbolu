"""public_api.json equals the actual curated surface, and both counts hold."""

from __future__ import annotations

import dataclasses
import json
import pathlib
from enum import EnumMeta

import ugence_benchmark_registry_authority as pkg
from ugence_benchmark_registry_authority import api

PKG = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = json.loads((PKG / "public_api.json").read_text())


def test_happy_the_manifest_names_the_right_distribution_and_namespace():
    assert MANIFEST["distribution"] == "ugence-benchmark-registry-authority"
    assert MANIFEST["namespace"] == "ugence_benchmark_registry_authority"
    assert MANIFEST["curated_api_module"] == (
        "ugence_benchmark_registry_authority.api"
    )


def test_the_manifest_version_equals_the_package_version():
    assert MANIFEST["package_version"] == api.__version__ == "0.2.1"


def test_the_manifest_symbols_equal_the_curated_surface_minus_version():
    assert set(MANIFEST["symbols"]) == set(api.__all__) - {"__version__"}


def test_both_counts_hold_and_neither_is_corrected_to_match_the_other():
    """``__version__`` is carried as ``package_version``, not as a symbol row.

    The same asymmetry the frozen BR-1 layer has, for the same reason. Both
    numbers are asserted so a future regeneration cannot quietly "fix" one.
    """

    assert len(api.__all__) == 106
    assert len(MANIFEST["symbols"]) == 105
    assert len(MANIFEST["symbols"]) == len(api.__all__) - 1
    assert "__version__" not in MANIFEST["symbols"]


def test_the_top_level_package_re_exports_the_curated_surface_exactly():
    """Everything in ``api.__all__``, plus the ``api`` submodule name itself.

    The same convention the frozen BR-1 layer ships: the top-level namespace
    re-exports the curated surface and additionally names ``api``, so
    ``from ugence_benchmark_registry_authority import api`` is a supported
    import. The manifest snapshots ``api.__all__``, not the top-level name, so
    the submodule is not a symbol row.
    """

    assert set(pkg.__all__) == set(api.__all__) | {"api"}
    for symbol in api.__all__:
        assert getattr(pkg, symbol) is getattr(api, symbol)
    assert pkg.api is api


def test_the_top_level_re_export_is_explicit_not_a_star_import():
    """A star import hides the surface from readers and from static analysis."""

    source = (
        PKG / "src" / "ugence_benchmark_registry_authority" / "__init__.py"
    ).read_text()
    assert "import *" not in source


def test_every_curated_symbol_actually_resolves():
    for symbol in api.__all__:
        assert hasattr(api, symbol), symbol


def test_the_curated_surface_has_no_duplicate_entries():
    assert len(api.__all__) == len(set(api.__all__))


def test_every_manifest_row_records_the_right_kind():
    for symbol, row in MANIFEST["symbols"].items():
        value = getattr(api, symbol)
        kind = row["kind"]
        if isinstance(value, EnumMeta):
            assert kind == "enum", symbol
            assert row["members"] == [m.value for m in value]
        elif isinstance(value, type) and issubclass(value, BaseException):
            assert kind == "error", symbol
        elif isinstance(value, type) and getattr(value, "_is_protocol", False):
            assert kind == "protocol", symbol
        elif isinstance(value, type) and dataclasses.is_dataclass(value):
            assert kind == "contract", symbol
            assert row["fields"] == [f.name for f in dataclasses.fields(value)]
        elif callable(value) and not isinstance(value, type):
            assert kind == "function", symbol


def test_every_pinned_constant_value_in_the_manifest_matches_the_live_value():
    for symbol, row in MANIFEST["symbols"].items():
        if row.get("kind") != "constant" or "value" not in row:
            continue
        value = getattr(api, symbol)
        if isinstance(value, str):
            assert row["value"] == value, symbol


def test_the_manifest_documents_the_count_asymmetry():
    note = MANIFEST["note"]
    assert "package_version" in note
    assert "one shorter" in note


def test_py_typed_ships_in_the_source_tree():
    marker = PKG / "src" / "ugence_benchmark_registry_authority" / "py.typed"
    assert marker.exists()


def test_the_curated_surface_covers_every_shipped_contract_class():
    from ugence_benchmark_registry_authority.contracts.canonical import (
        _contract_type_registry_snapshot,
    )

    for cls, (domain, root_ok) in _contract_type_registry_snapshot().items():
        if root_ok:
            assert cls.__name__ in api.__all__, cls.__name__


def test_no_private_name_leaks_into_the_curated_surface():
    for symbol in api.__all__:
        if symbol == "__version__":
            continue
        assert not symbol.startswith("_"), symbol
