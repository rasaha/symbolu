"""§4.6 ConventionalBlendDecoder tests — equal-weight blend over M."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.decoders.blend import decode_conventional_blend
from symbolu_bcvf_llm.sources.mock import MockSource


def _one_hot_logits(l0_top: int, V: int = 4, L: int = 3):
    logits = np.full((L, V), -10.0, dtype=np.float32)
    logits[0, l0_top] = 10.0
    for l in range(1, L):
        logits[l, 0] = 10.0
    return logits


def test_blend_agrees_when_all_sources_agree():
    # All three sources point at token 2.
    def fn(prefix):
        return _one_hot_logits(2)

    sources = [MockSource(fn, L=3, V=4) for _ in range(3)]
    result = decode_conventional_blend(sources, max_tokens=3)
    assert result.emitted_tokens == [2, 2, 2]


def test_blend_majority_wins_at_m3():
    # Sources 0 and 1 point at token 1; source 2 points at token 3.
    # Equal-weight blend of three softmaxed one-hot distributions:
    # bin 1 gets 2·0.999 = 1.998 mass; bin 3 gets 1·0.999 = 0.999.
    # argmax(avg) = 1.
    def make_fn(top):
        def fn(prefix):
            return _one_hot_logits(top)
        return fn

    sources = [
        MockSource(make_fn(1), L=3, V=4),
        MockSource(make_fn(1), L=3, V=4),
        MockSource(make_fn(3), L=3, V=4),
    ]
    result = decode_conventional_blend(sources, max_tokens=3)
    assert result.emitted_tokens == [1, 1, 1]


def test_blend_all_sources_receive_committed_tokens():
    def fn(prefix):
        return _one_hot_logits(0, V=4)

    sources = [MockSource(fn, L=3, V=4) for _ in range(3)]
    result = decode_conventional_blend(sources, max_tokens=4)
    assert len(result.emitted_tokens) == 4
    for s in sources:
        assert s.committed_prefix == (0, 0, 0, 0)


def test_blend_rejects_vocab_mismatch():
    def fn_a(prefix):
        return np.zeros((3, 4), dtype=np.float32)

    def fn_b(prefix):
        return np.zeros((3, 6), dtype=np.float32)

    src0 = MockSource(fn_a, L=3, V=4)
    src1 = MockSource(fn_b, L=3, V=6)
    with pytest.raises(ValueError):
        decode_conventional_blend([src0, src1], max_tokens=3)
