"""Legacy ``tap_provider`` namespace compatibility (identity-preserving).

Consumers that still import from ``tap_provider`` must observe the SAME objects as
the canonical ``ugence_tap_provider`` package — same classes, same modules, same
serialization — so no consumer needs a code change.
"""
from __future__ import annotations

import importlib

import pytest

DEEP_MODULES = [
    "api", "core", "client", "configuration", "conformance", "errors",
    "health", "mapping", "mapping.controls", "mapping.request", "mapping.result",
    "observability", "provider", "version",
]


@pytest.mark.parametrize("sub", DEEP_MODULES)
def test_legacy_submodule_is_the_same_object_as_canonical(sub):
    legacy = importlib.import_module("tap_provider." + sub)
    canon = importlib.import_module("ugence_tap_provider." + sub)
    assert legacy is canon


def test_top_level_version_identity():
    import tap_provider
    import ugence_tap_provider
    assert tap_provider.__version__ is ugence_tap_provider.__version__ == "0.1.0"


def test_public_api_symbols_are_identical_objects():
    import tap_provider.api as legacy_api
    import ugence_tap_provider.api as canon_api
    assert list(legacy_api.__all__) == list(canon_api.__all__)
    for name in canon_api.__all__:
        assert getattr(legacy_api, name) is getattr(canon_api, name), name


def test_deep_from_import_still_works():
    from tap_provider.api import TAPProvider, build_tap_provider
    from tap_provider.mapping.result import map_result, MAPPING_VERSION
    from tap_provider.core import TapEngine, TapOutcome
    assert MAPPING_VERSION == "tap-map-1"
    assert build_tap_provider().descriptor().provider_id == "tap"
    assert TapOutcome.SUPPORTED.value == "SUPPORTED"
    assert map_result is not None and TAPProvider is not None and TapEngine is not None


def test_facade_version_info_is_the_canonical_helper():
    import tap_provider
    import ugence_tap_provider
    assert tap_provider.version_info is ugence_tap_provider.version_info
    assert tap_provider.version_info().distribution == "ugence-tap-provider"
