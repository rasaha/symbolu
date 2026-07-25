"""The pilot consumes provider conformance — it does not redefine it (Task 117)."""
from __future__ import annotations

from actiongate_provider.configuration import build_actiongate_provider
from actiongate_provider.conformance import run_actiongate_conformance
from governance_providers.conformance import (
    run_action_provider_conformance, run_assertion_provider_conformance)
from tap_provider.configuration import build_tap_provider
from tap_provider.conformance import run_tap_conformance


def test_pilot_consumes_shared_assertion_conformance():
    assert run_assertion_provider_conformance(lambda: build_tap_provider()).passed


def test_pilot_consumes_tap_specific_conformance():
    assert run_tap_conformance().passed


def test_pilot_consumes_shared_action_conformance():
    assert run_action_provider_conformance(lambda: build_actiongate_provider()).passed


def test_pilot_consumes_actiongate_specific_conformance():
    assert run_actiongate_conformance().passed
