"""
COHERA Python SDK surface tests.

These are stub-level tests that exercise the Python API shape: attention
config defaults and GQA validation, SovereignState round-trip, and the
fused phase-attention entry point. They do not require a COHERA device.
"""

import pytest

from cohera import (
    AttentionConfig,
    DType,
    KoshaMode,
    PhaseAttention,
    SovereignState,
    SovereignStateProjector,
    phase_attention,
    phase_attention_fused,
    project_to_sovereign_state,
)
from cohera.tensor import (
    SOVEREIGN_BHAVA_DIM,
    SOVEREIGN_GUNA_DIM,
    SOVEREIGN_KOSHA_DIM,
    SOVEREIGN_RESERVED_DIM,
    SOVEREIGN_TOTAL_DIM,
    SOVEREIGN_VRITTI_DIM,
)


# ----- AttentionConfig / PhaseAttention -----

def test_default_attention_config_is_mha_bf16_full():
    cfg = AttentionConfig()
    assert cfg.num_kv_heads == 0           # 0 -> MHA
    assert cfg.dtype == DType.BF16
    assert cfg.window_size == -1           # full attention
    assert cfg.rope_dim == 0               # RoPE disabled
    assert cfg.rope_freqs is None


def test_mistral_7b_config_valid():
    attn = PhaseAttention(
        dim=4096,
        heads=32,
        num_kv_heads=8,
        causal=True,
        dtype=DType.BF16,
        window_size=4096,
        rope_dim=128,
    )
    assert attn.head_dim == 128
    assert attn.num_kv_heads == 8
    assert attn.head_group_size == 4
    assert attn.causal is True


def test_mha_when_num_kv_heads_equals_num_heads():
    attn = PhaseAttention(dim=768, heads=12, num_kv_heads=12)
    assert attn.num_kv_heads == 12
    assert attn.head_group_size == 1


def test_gqa_divisibility_rejected():
    with pytest.raises(ValueError, match="divisible"):
        PhaseAttention(dim=4096, heads=32, num_kv_heads=7)


def test_phase_attention_returns_three_tuple():
    cfg = AttentionConfig(embed_dim=768, num_heads=12)
    out, coherence, state_delta = phase_attention(query=None, config=cfg)
    assert isinstance(coherence, float)
    assert isinstance(state_delta, float)


# ----- Fused entry point -----

def test_fused_requires_key_and_value():
    cfg = AttentionConfig()
    with pytest.raises(ValueError, match="query"):
        phase_attention_fused(query=None, key=object(), value=object(), config=cfg)
    with pytest.raises(ValueError, match="key and value"):
        phase_attention_fused(query=object(), key=None, value=object(), config=cfg)
    with pytest.raises(ValueError, match="key and value"):
        phase_attention_fused(query=object(), key=object(), value=None, config=cfg)


def test_fused_returns_three_tuple():
    cfg = AttentionConfig(embed_dim=4096, num_heads=32, num_kv_heads=8,
                          causal=True, dtype=DType.BF16, rope_dim=128)
    q, k, v = object(), object(), object()
    result = phase_attention_fused(q, k, v, config=cfg)
    assert len(result) == 3


# ----- SovereignState -----

def test_sovereign_state_layout_constants():
    assert SOVEREIGN_BHAVA_DIM == 12
    assert SOVEREIGN_KOSHA_DIM == 5
    assert SOVEREIGN_VRITTI_DIM == 5
    assert SOVEREIGN_GUNA_DIM == 6
    assert SOVEREIGN_RESERVED_DIM == 4
    assert SOVEREIGN_TOTAL_DIM == 32


def test_sovereign_state_default_is_32d_zero():
    s = SovereignState()
    vec = s.to_vector()
    assert len(vec) == 32
    assert all(v == 0.0 for v in vec)


def test_sovereign_state_roundtrip():
    vec = [float(i) / 32.0 for i in range(32)]
    s = SovereignState.from_vector(vec)
    assert s.to_vector() == vec
    assert len(s.bhava) == 12
    assert len(s.kosha) == 5
    assert len(s.vritti) == 5
    assert len(s.guna) == 6
    assert len(s.reserved) == 4


def test_sovereign_state_rejects_wrong_length():
    with pytest.raises(ValueError):
        SovereignState.from_vector([0.0] * 31)
    with pytest.raises(ValueError):
        SovereignState(bhava=[0.0] * 11)


def test_sovereign_state_dominant_accessors():
    bhava = [0.0] * 12
    bhava[7] = 1.0
    vritti = [0.0] * 5
    vritti[2] = 1.0
    s = SovereignState(bhava=bhava, vritti=vritti)
    assert s.dominant_bhava == 7
    assert s.dominant_vritti == 2


# ----- SovereignStateProjector -----

def test_projector_intermediate_dim_matches_reference():
    # mistral_cg reference: 4096 -> 1024 -> 32
    proj = SovereignStateProjector(hidden_dim=4096)
    assert proj.intermediate_dim == 1024
    assert proj.kosha_mode == KoshaMode.SIGMOID


def test_projector_custom_intermediate_dim():
    proj = SovereignStateProjector(hidden_dim=4096, intermediate_dim=512)
    assert proj.intermediate_dim == 512


def test_project_to_sovereign_state_returns_sovereign_state():
    s = project_to_sovereign_state(hidden=None, hidden_dim=4096)
    assert isinstance(s, SovereignState)
    assert len(s.to_vector()) == 32
