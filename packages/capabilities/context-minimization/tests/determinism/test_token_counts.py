"""Correction B (v0.1.2) — token-count value contract.

A token count (caller-supplied ``ContextUnit.token_count`` or an injected
``TokenCounter.count`` result) must be a non-negative ``int``: never ``bool``,
non-integral ``float``, NaN, ``inf``, or ``str``. Malformed counts raise
``InvalidUnitError`` deterministically, before any fingerprint uses the value.
"""

from __future__ import annotations

import math

import pytest

from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    InvalidUnitError,
    minimize_context,
)

from support import KeywordOracle, context, unit


# --------------------------------------------------------------------------- #
# caller-supplied ContextUnit.token_count
# --------------------------------------------------------------------------- #
def test_zero_token_count_accepted():
    u = ContextUnit(id="x", text="", token_count=0)
    assert u.counted_tokens() == 0


def test_positive_int_token_count_accepted():
    assert ContextUnit(id="x", text="t", token_count=5).counted_tokens() == 5


def test_large_int_token_count_accepted():
    assert ContextUnit(id="x", text="t", token_count=10**9).counted_tokens() == 10**9


@pytest.mark.parametrize("bad", [-1, True, False, 1.5, 2.0, math.nan, math.inf, "3", object()])
def test_malformed_token_count_rejected(bad):
    with pytest.raises(InvalidUnitError):
        ContextUnit(id="x", text="t", token_count=bad)


# --------------------------------------------------------------------------- #
# injected TokenCounter.count() outputs
# --------------------------------------------------------------------------- #
class _Counter:
    def __init__(self, value):
        self.value = value

    def count(self, text):
        return self.value


def test_injected_counter_valid_int_accepted():
    ctx = context([unit("a", "hello world")])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.0,
                         token_counter=_Counter(4), evaluation_time=1.0)
    assert r.original_tokens == 4


@pytest.mark.parametrize("bad", [-1, True, 1.5, math.nan, math.inf, "3", object()])
def test_injected_counter_malformed_output_rejected(bad):
    ctx = Context(id="c", correlation_id="k", units=(
        ContextUnit(id="a", text="hello world"),))
    with pytest.raises(InvalidUnitError):
        minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.0,
                         token_counter=_Counter(bad), evaluation_time=1.0)


def test_zero_from_injected_counter_accepted():
    ctx = context([unit("a", "hello")])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.0,
                         token_counter=_Counter(0), evaluation_time=1.0)
    assert r.original_tokens == 0
