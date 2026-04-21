"""§4.6 run_decode generic-outer-loop tests."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.decoders.loop import run_decode
from symbolu_bcvf_llm.sources.mock import MockSource


def _flat_fn(V):
    return lambda prefix: np.zeros((3, V), dtype=np.float32)


def test_run_decode_stops_at_max_tokens():
    src = MockSource(_flat_fn(4), L=3, V=4)

    def strategy(lookaheads, step):
        return 0

    result = run_decode([src], strategy, max_tokens=7)
    assert result.num_steps == 7
    assert not result.stopped_on_eos


def test_run_decode_stops_at_eos():
    src = MockSource(_flat_fn(4), L=3, V=4, eos_token_id=2)

    def strategy(lookaheads, step):
        return 0 if step < 3 else 2

    result = run_decode([src], strategy, max_tokens=10, eos_token_id=2)
    assert result.stopped_on_eos
    assert result.num_steps == 4
    assert result.emitted_tokens == [0, 0, 0, 2]


def test_run_decode_rejects_out_of_range_token():
    src = MockSource(_flat_fn(4), L=3, V=4)

    def strategy(lookaheads, step):
        return 99

    with pytest.raises(ValueError):
        run_decode([src], strategy, max_tokens=3)


def test_run_decode_commits_after_emit():
    src = MockSource(_flat_fn(4), L=3, V=4)

    def strategy(lookaheads, step):
        return step % 3

    result = run_decode([src], strategy, max_tokens=5)
    assert src.committed_prefix == (0, 1, 2, 0, 1)
    assert result.emitted_tokens == [0, 1, 2, 0, 1]
