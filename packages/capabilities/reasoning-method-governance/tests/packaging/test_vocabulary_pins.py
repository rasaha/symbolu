"""Vocabulary-pin tests (spec §9 item 3; 1.1-B).

The contracts package MIRRORS three vocabularies and never imports their
sources at runtime. These tests import the sources under test only:
``ugence_context_minimization.token_accounting`` for the telemetry vocabulary,
and ``agentic/agentic_framework/adaptive_prompts.py`` loaded by file path (its
package ``__init__`` pulls numpy; the module itself is stdlib-only) for the
signal tokens.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import pathlib
import sys

import pytest

from ugence_reasoning_method_governance.api import COMPLEXITY_SIGNAL_TOKENS, CountBasis, TokenUsageSnapshot, UsageAvailabilityToken

REPO = pathlib.Path(__file__).resolve().parents[5]


def _token_accounting():
    src = REPO / "packages" / "capabilities" / "context-minimization" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return pytest.importorskip("ugence_context_minimization.token_accounting")


def test_count_basis_mirrors_token_count_basis():
    ta = _token_accounting()
    assert [(m.name, m.value) for m in CountBasis] == [(m.name, m.value) for m in ta.TokenCountBasis]


def test_usage_availability_token_mirrors_usage_availability():
    ta = _token_accounting()
    assert [(m.name, m.value) for m in UsageAvailabilityToken] == [(m.name, m.value) for m in ta.UsageAvailability]


def test_token_usage_snapshot_field_names_in_order():
    ta = _token_accounting()
    theirs = [f.name for f in dataclasses.fields(ta.ProviderTokenUsage)]
    ours = [f.name for f in dataclasses.fields(TokenUsageSnapshot)]
    assert ours == theirs


def _adaptive_prompts():
    path = REPO / "agentic" / "agentic_framework" / "adaptive_prompts.py"
    assert path.is_file()
    spec = importlib.util.spec_from_file_location("_pin_adaptive_prompts", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass decoration resolves the module by name
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_signal_tokens_mirror_complexity_signal_values():
    ap = _adaptive_prompts()
    assert COMPLEXITY_SIGNAL_TOKENS == frozenset(m.value for m in ap.ComplexitySignal)
