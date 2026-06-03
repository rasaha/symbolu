"""Pure-Python regression tests for AttentionAggregator.flush_to_evictor.

No torch dependency — runs on any CPU host (unlike the torch-gated
composition test). Locks the concurrency fix for the Day-5b bridge
warning: "attention flush to evictor failed: dictionary changed size
during iteration".
"""

from __future__ import annotations

from kv_policy.vllm_evictor import AttentionAggregator


def test_flush_to_evictor_survives_concurrent_record():
    """The flusher (a separate asyncio task) iterates the aggregator
    buffer while the capture hook records new samples from vLLM's
    model-exec thread. Simulate that race by having the evictor's
    ``forward_block_attention`` record a NEW block back into the
    aggregator mid-flush. With the old in-place iteration this raised
    RuntimeError; the atomic buffer-swap must make it safe AND not lose
    the late sample (it flushes on the next call)."""
    aggregator = AttentionAggregator()

    class _MutatingEvictor:
        def __init__(self):
            self.received = []
            self._fired = False

        def forward_block_attention(self, block_id, attention_sum, seq_len=None):
            self.received.append((block_id, attention_sum))
            if not self._fired:  # mimic the capture path firing mid-flush
                self._fired = True
                aggregator.record_block_attention(block_id=999, weight=0.5)

    aggregator.record_block_attention(block_id=101, weight=0.6)
    aggregator.record_block_attention(block_id=102, weight=0.4)

    evictor = _MutatingEvictor()
    flushed = aggregator.flush_to_evictor(evictor)  # must NOT raise
    assert flushed == 2, flushed
    assert {b for b, _ in evictor.received} == {101, 102}

    # The late-arriving block 999 landed in the fresh buffer; flushes next.
    assert aggregator.buffered_blocks == 1
    flushed2 = aggregator.flush_to_evictor(evictor)
    assert flushed2 == 1
    assert any(b == 999 for b, _ in evictor.received)


def test_flush_empty_buffer_is_noop():
    aggregator = AttentionAggregator()

    class _E:
        def __init__(self):
            self.n = 0

        def forward_block_attention(self, block_id, attention_sum, seq_len=None):
            self.n += 1

    e = _E()
    assert aggregator.flush_to_evictor(e) == 0
    assert e.n == 0


def test_flush_accumulates_then_clears():
    """Two records to the same block accumulate; flush clears the buffer."""
    aggregator = AttentionAggregator()
    received = {}

    class _E:
        def forward_block_attention(self, block_id, attention_sum, seq_len=None):
            received[block_id] = attention_sum

    aggregator.record_block_attention(block_id=7, weight=0.3)
    aggregator.record_block_attention(block_id=7, weight=0.4)
    assert aggregator.flush_to_evictor(_E()) == 1
    assert abs(received[7] - 0.7) < 1e-9
    assert aggregator.buffered_blocks == 0          # buffer cleared
    assert aggregator.flush_to_evictor(_E()) == 0   # nothing left


if __name__ == "__main__":  # allow running without pytest (no-torch CPU box)
    test_flush_to_evictor_survives_concurrent_record()
    test_flush_empty_buffer_is_noop()
    test_flush_accumulates_then_clears()
    print("attention aggregator flush: 3/3 PASS")
