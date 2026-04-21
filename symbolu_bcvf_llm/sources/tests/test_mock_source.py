"""§4.3 MockSource behaviour tests — torch-free."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.sources.base import Source
from symbolu_bcvf_llm.sources.mock import MockSource


def _constant_logits_fn(L: int, V: int):
    table = np.tile(np.arange(V, dtype=np.float32), (L, 1))

    def fn(prefix):
        return table

    return fn


def test_mock_source_implements_protocol():
    src = MockSource(_constant_logits_fn(3, 4), L=3, V=4)
    assert isinstance(src, Source)


def test_mock_source_lookahead_shape_and_dtype():
    src = MockSource(_constant_logits_fn(5, 32), L=5, V=32)
    probs, mask = src.lookahead()
    assert probs.shape == (5, 32)
    assert probs.dtype == np.float32
    assert mask.shape == (5,)
    assert mask.dtype == np.bool_


def test_mock_source_lookahead_sums_to_one():
    src = MockSource(_constant_logits_fn(5, 7), L=5, V=7)
    probs, _ = src.lookahead()
    row_sums = probs.sum(axis=-1)
    np.testing.assert_allclose(row_sums, 1.0, rtol=0, atol=1e-5)


def test_mock_source_commit_changes_context():
    log = []

    def fn(prefix):
        log.append(prefix)
        return np.zeros((3, 4), dtype=np.float32)

    src = MockSource(fn, L=3, V=4)
    src.lookahead()
    src.commit(2)
    src.lookahead()
    assert log == [(), (2,)]


def test_mock_source_rejects_out_of_range_commit():
    src = MockSource(_constant_logits_fn(3, 4), L=3, V=4)
    with pytest.raises(ValueError):
        src.commit(4)
    with pytest.raises(ValueError):
        src.commit(-1)


def test_mock_source_rejects_wrong_shape_from_fn():
    def fn(prefix):
        return np.zeros((4, 4))  # wrong L

    src = MockSource(fn, L=3, V=4)
    with pytest.raises(ValueError):
        src.lookahead()


def test_mock_source_eos_mask_truncates_after_first_eos():
    V = 5
    EOS = 3

    # Logits such that argmax at l=0 is 0, at l=1 is 1, at l=2 is EOS,
    # at l=3 is 4, at l=4 is 0. Mask should be [T, T, T, F, F].
    logits = np.full((5, V), -10.0, dtype=np.float32)
    logits[0, 0] = 10.0
    logits[1, 1] = 10.0
    logits[2, EOS] = 10.0
    logits[3, 4] = 10.0
    logits[4, 0] = 10.0

    src = MockSource(lambda p: logits, L=5, V=V, eos_token_id=EOS)
    _, mask = src.lookahead()
    assert mask.tolist() == [True, True, True, False, False]


def test_mock_source_no_eos_mask_all_true():
    src = MockSource(_constant_logits_fn(5, 10), L=5, V=10, eos_token_id=None)
    _, mask = src.lookahead()
    assert mask.all()


def test_mock_source_requires_L_ge_3():
    with pytest.raises(ValueError):
        MockSource(_constant_logits_fn(2, 4), L=2, V=4)


def test_mock_source_reset_rewinds_prefix():
    src = MockSource(_constant_logits_fn(3, 4), L=3, V=4)
    src.commit(1)
    src.commit(2)
    assert src.committed_prefix == (1, 2)
    src.reset()
    assert src.committed_prefix == ()
    src.reset([3])
    assert src.committed_prefix == (3,)
