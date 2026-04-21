"""§4.6 VanillaDecoder tests — source-0 argmax."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.decoders.vanilla import decode_vanilla
from symbolu_bcvf_llm.sources.mock import MockSource


def _argmax_schedule(schedule):
    """Return a logits fn that puts 10.0 on `schedule[i]` at the i-th call."""
    counter = {"i": 0}

    def fn(prefix):
        pref_len = len(prefix)
        logits = np.full((3, 5), -10.0, dtype=np.float32)
        # Use the prefix-length to pick the row, so the result depends
        # on committed state (deterministic).
        for l in range(3):
            logits[l, schedule[(pref_len + l) % len(schedule)]] = 10.0
        counter["i"] += 1
        return logits

    return fn


def test_vanilla_emits_source0_argmax():
    # Source 0 prefers token 2 at position 0 regardless of prefix.
    def fn(prefix):
        logits = np.full((3, 4), -10.0, dtype=np.float32)
        logits[0, 2] = 10.0
        logits[1, 0] = 10.0
        logits[2, 1] = 10.0
        return logits

    src0 = MockSource(fn, L=3, V=4)
    result = decode_vanilla([src0], max_tokens=5)
    assert result.emitted_tokens == [2, 2, 2, 2, 2]
    assert result.num_steps == 5
    assert not result.stopped_on_eos


def test_vanilla_stops_on_eos():
    EOS = 3

    def fn(prefix):
        logits = np.full((3, 4), -10.0, dtype=np.float32)
        if len(prefix) < 2:
            logits[0, 0] = 10.0
        else:
            logits[0, EOS] = 10.0
        logits[1, 1] = 10.0
        logits[2, 2] = 10.0
        return logits

    src0 = MockSource(fn, L=3, V=4, eos_token_id=EOS)
    result = decode_vanilla([src0], max_tokens=10, eos_token_id=EOS)
    assert result.stopped_on_eos
    assert result.emitted_tokens[-1] == EOS


def test_vanilla_ignores_other_sources_for_decision():
    # Source 0 wants token 0, source 1 wants token 3.
    # Vanilla must emit 0.
    def fn0(prefix):
        logits = np.full((3, 4), -10.0, dtype=np.float32)
        logits[0, 0] = 10.0
        return logits

    def fn1(prefix):
        logits = np.full((3, 4), -10.0, dtype=np.float32)
        logits[0, 3] = 10.0
        return logits

    src0 = MockSource(fn0, L=3, V=4)
    src1 = MockSource(fn1, L=3, V=4)
    result = decode_vanilla([src0, src1], max_tokens=3)
    assert result.emitted_tokens == [0, 0, 0]
    # But source 1 still receives the same commits, so its prefix matches.
    assert src1.committed_prefix == (0, 0, 0)


def test_vanilla_rejects_empty_sources():
    with pytest.raises(ValueError):
        decode_vanilla([], max_tokens=3)
