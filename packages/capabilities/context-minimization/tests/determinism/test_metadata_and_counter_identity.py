"""Correction B (v0.1.2) — scalar metadata contract + stable token-counter identity."""

from __future__ import annotations

import datetime
import math

import pytest

from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    InvalidUnitError,
    minimize_context,
)
from ugence_context_minimization.fingerprint import _counter_identity

from support import KeywordOracle, context, unit


# --------------------------------------------------------------------------- #
# Metadata scalar contract
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", ["s", 1, 1.5, 0, True, False, None])
def test_scalar_metadata_values_accepted(value):
    u = ContextUnit(id="x", text="t", metadata={"k": value})
    assert u.metadata["k"] == value


@pytest.mark.parametrize("value", [
    [1, 2], {"a": 1}, {1, 2}, b"bytes", object(), lambda: 1,
    math.nan, math.inf, -math.inf, datetime.date(2026, 1, 1),
])
def test_non_scalar_metadata_values_rejected(value):
    with pytest.raises(InvalidUnitError):
        ContextUnit(id="x", text="t", metadata={"k": value})


def test_non_string_metadata_key_rejected():
    with pytest.raises(InvalidUnitError):
        ContextUnit(id="x", text="t", metadata={1: "v"})


def test_string_metadata_still_works():
    u = ContextUnit(id="x", text="t", metadata={"a": "1", "b": "2"})
    assert dict(u.metadata) == {"a": "1", "b": "2"}


# --------------------------------------------------------------------------- #
# Token-counter identity (run/2)
# --------------------------------------------------------------------------- #
def test_counter_identity_default_is_none_label():
    assert _counter_identity(None) == "default"


def test_counter_identity_uses_module_qualified_name():
    class Local:
        def count(self, text):
            return 1
    ident = _counter_identity(Local())
    assert ident.endswith(".Local") and "." in ident  # module-qualified, not bare name


def test_counter_identity_prefers_explicit_counter_id():
    class WithId:
        counter_id = "my-counter"
        counter_version = "3"

        def count(self, text):
            return 1
    assert _counter_identity(WithId()) == "my-counter@3"


def test_distinct_counter_ids_change_run_fingerprint():
    class C:
        def __init__(self, cid):
            self.counter_id = cid

        def count(self, text):
            return 2
    ctx = context([unit("a", "hello world")])
    ra = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.0,
                          token_counter=C("A"), evaluation_time=1.0)
    rb = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.0,
                          token_counter=C("B"), evaluation_time=1.0)
    assert ra.run_fingerprint != rb.run_fingerprint
