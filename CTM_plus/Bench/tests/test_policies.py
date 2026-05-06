"""Tests for the policy adapters."""

from __future__ import annotations

import pytest

from ctm_bench.policies import (
    AccessContext,
    BenchConfig,
    FIFOPolicy,
    LRUPolicy,
    POLICIES,
    get_policy,
)


def _ctx(seq_id: int = 0, position: int = 0, attn: float = 0.1) -> AccessContext:
    return AccessContext(
        seq_id=seq_id,
        position=position,
        seq_len=position + 1,
        attention_weight=attn,
        is_prefill=False,
    )


def test_bench_config_validates_max_blocks_positive():
    with pytest.raises(ValueError, match="max_blocks"):
        BenchConfig(max_blocks=0)


def test_bench_config_validates_block_size_positive():
    with pytest.raises(ValueError, match="block_size"):
        BenchConfig(max_blocks=8, block_size=0)


def test_bench_config_validates_sink_tokens_non_negative():
    with pytest.raises(ValueError, match="sink_tokens"):
        BenchConfig(max_blocks=8, sink_tokens=-1)


def test_bench_config_attention_ema_alpha_defaults_none():
    cfg = BenchConfig(max_blocks=8)
    assert cfg.attention_ema_alpha is None


def test_bench_config_validates_ema_alpha_range():
    with pytest.raises(ValueError, match="attention_ema_alpha"):
        BenchConfig(max_blocks=8, attention_ema_alpha=0.0)
    with pytest.raises(ValueError, match="attention_ema_alpha"):
        BenchConfig(max_blocks=8, attention_ema_alpha=1.5)
    with pytest.raises(ValueError, match="attention_ema_alpha"):
        BenchConfig(max_blocks=8, attention_ema_alpha=-0.1)


def test_bench_config_accepts_valid_ema_alpha():
    # Boundary values: just-positive and 1.0 inclusive.
    cfg_low = BenchConfig(max_blocks=8, attention_ema_alpha=0.001)
    assert cfg_low.attention_ema_alpha == 0.001
    cfg_high = BenchConfig(max_blocks=8, attention_ema_alpha=1.0)
    assert cfg_high.attention_ema_alpha == 1.0


def test_lru_evicts_oldest_first():
    cfg = BenchConfig(max_blocks=4)
    policy = LRUPolicy(cfg)
    for bid in range(4):
        policy.on_access(bid, _ctx(position=bid))
    victims = policy.select_victims(1)
    assert victims == [0]


def test_lru_re_access_promotes_recency():
    cfg = BenchConfig(max_blocks=4)
    policy = LRUPolicy(cfg)
    for bid in range(4):
        policy.on_access(bid, _ctx(position=bid))
    # Re-access block 0 → it becomes most recently used.
    policy.on_access(0, _ctx(position=99))
    victims = policy.select_victims(1)
    assert victims == [1]


def test_lru_on_evict_drops_block():
    cfg = BenchConfig(max_blocks=4)
    policy = LRUPolicy(cfg)
    for bid in range(4):
        policy.on_access(bid, _ctx(position=bid))
    policy.on_evict(0)
    victims = policy.select_victims(1)
    assert victims == [1]


def test_lru_select_victims_handles_zero():
    cfg = BenchConfig(max_blocks=4)
    policy = LRUPolicy(cfg)
    for bid in range(4):
        policy.on_access(bid, _ctx(position=bid))
    assert policy.select_victims(0) == []


def test_fifo_does_not_update_recency_on_re_access():
    cfg = BenchConfig(max_blocks=4)
    policy = FIFOPolicy(cfg)
    for bid in range(4):
        policy.on_access(bid, _ctx(position=bid))
    policy.on_access(0, _ctx(position=99))
    # FIFO ignores the re-access; block 0 still evicts first.
    assert policy.select_victims(1) == [0]


def test_policy_registry_keys():
    assert set(POLICIES.keys()) == {"lru", "fifo", "ctm_plus"}


def test_get_policy_unknown_raises():
    with pytest.raises(KeyError, match="unknown policy"):
        get_policy("does_not_exist", BenchConfig(max_blocks=8))


def test_get_policy_lru_constructs():
    policy = get_policy("lru", BenchConfig(max_blocks=8))
    assert isinstance(policy, LRUPolicy)


def test_ctm_plus_adapter_threads_ema_alpha_through():
    """When BenchConfig.attention_ema_alpha is set, the adapter
    should construct KVCachePolicy with that alpha. We verify by
    inspecting the wrapped policy's ema_alpha attribute."""
    try:
        from ctm_bench.policies import CTMPlusPolicyAdapter
        adapter = CTMPlusPolicyAdapter(
            BenchConfig(max_blocks=8, attention_ema_alpha=0.05)
        )
    except ImportError:
        pytest.skip("kv_policy not installed; covered by import-error contract test")
    # The wrapped KVCachePolicy stores it as `ema_alpha`.
    assert adapter._policy.ema_alpha == 0.05  # noqa: SLF001


def test_ctm_plus_adapter_propagates_seed_to_internal_rng():
    """Audit Finding #1: KVCachePolicy hardcodes its internal
    RNG to ``random.Random(42)``. The adapter must override this
    with ``cfg.seed`` so two runs at different seeds actually
    produce different victim sequences. Without this, every CTM+
    benchmark cell silently used seed 42 internally."""
    try:
        from ctm_bench.policies import CTMPlusPolicyAdapter
        adapter_a = CTMPlusPolicyAdapter(BenchConfig(max_blocks=8, seed=11))
        adapter_b = CTMPlusPolicyAdapter(BenchConfig(max_blocks=8, seed=99))
    except ImportError:
        pytest.skip("kv_policy not installed")
    # The wrapped policy's RNG state is observable via its first
    # random sample. Two different seeds must produce different
    # samples.
    sample_a = adapter_a._policy._rng.random()  # noqa: SLF001
    sample_b = adapter_b._policy._rng.random()  # noqa: SLF001
    assert sample_a != sample_b


def test_ctm_plus_adapter_default_does_not_set_ema_alpha():
    """When BenchConfig.attention_ema_alpha is None, the adapter
    must not pass it to KVCachePolicy — the production default
    should be preserved unchanged."""
    try:
        from ctm_bench.policies import CTMPlusPolicyAdapter
        adapter = CTMPlusPolicyAdapter(BenchConfig(max_blocks=8))
    except ImportError:
        pytest.skip("kv_policy not installed")
    # Production default in KVCachePolicy is currently 0.1.
    # If this test fails after a production-default change, both
    # the default and this test should be updated together.
    assert adapter._policy.ema_alpha == 0.1  # noqa: SLF001


def test_ctm_plus_adapter_constructs_or_raises_clear_import_error():
    """The CTM+ adapter requires ``kv_policy`` on sys.path. Either
    it loads cleanly (sibling KVPolicy package present) or it
    raises a clear ImportError pointing at the expected path."""
    try:
        policy = get_policy("ctm_plus", BenchConfig(max_blocks=8))
    except ImportError as exc:
        msg = str(exc)
        assert "kv_policy" in msg
        assert "KVPolicy" in msg
        return
    # If construction succeeded, verify the basic protocol surface.
    policy.register_sequence(0)
    policy.on_access(0, _ctx())
    victims = policy.select_victims(1)
    assert isinstance(victims, list)
