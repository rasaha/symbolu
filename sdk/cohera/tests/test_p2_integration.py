"""
P2 integration tests: model-aware device init + MistralCG/Hybrid accelerators
+ HF binding helper.
"""

import math

import pytest

from cohera import (
    DType,
    HybridOntologicalAccelerator,
    HybridOntologicalConfig,
    KoshaMode,
    MistralCGAccelerator,
    MistralCGConfig,
    ModelDeviceContext,
    SovereignState,
    bind_mistral_to_cohera,
    initialize_for_model,
)


# ----- initialize_for_model -----

def test_initialize_for_mistral_cg_defaults():
    ctx = initialize_for_model("mistral_cg", {
        "hidden_dim": 4096, "num_heads": 32, "num_kv_heads": 8,
        "rope_dim": 128, "window_size": 4096,
    })
    assert isinstance(ctx, ModelDeviceContext)
    assert ctx.hidden_dim == 4096
    assert ctx.num_heads == 32
    assert ctx.num_kv_heads == 8
    assert ctx.head_dim == 128
    assert ctx.rope_dim == 128
    assert ctx.rope_freqs_handle is not None
    assert len(ctx.rope_freqs_handle) == 64          # rope_dim // 2
    # Mistral RoPE base = 10000 -> freq[0] = 1 / 10000^0 = 1.0
    assert math.isclose(ctx.rope_freqs_handle[0], 1.0)
    assert ctx.layer_harmonics == ()                 # mistral_cg has no hybrid ladder


def test_initialize_for_hybrid_populates_harmonics():
    ctx = initialize_for_model("hybrid", {
        "hidden_dim": 256, "num_heads": 8,
    })
    assert ctx.num_kv_heads == 8                     # defaults to MHA
    assert len(ctx.layer_harmonics) == 12
    # log-spaced from 1e5 to 1
    assert math.isclose(ctx.layer_harmonics[0], 1e5, rel_tol=1e-3)
    assert math.isclose(ctx.layer_harmonics[-1], 1.0, rel_tol=1e-3)


def test_initialize_rejects_unsupported_model_type():
    with pytest.raises(ValueError, match="Unsupported model_type"):
        initialize_for_model("gpt2", {"hidden_dim": 768, "num_heads": 12})


def test_initialize_rejects_bad_gqa_divisibility():
    with pytest.raises(ValueError, match="divisible"):
        initialize_for_model("mistral_cg", {
            "hidden_dim": 4096, "num_heads": 32, "num_kv_heads": 7,
        })


# ----- MistralCGAccelerator -----

def test_mistral_cg_default_config_matches_mistral_7b():
    cfg = MistralCGConfig()
    assert cfg.hidden_dim == 4096
    assert cfg.num_heads == 32
    assert cfg.num_kv_heads == 8
    assert cfg.rope_dim == 128
    assert cfg.window_size == 4096
    assert cfg.causal is True
    assert cfg.dtype == DType.BF16
    assert cfg.phase_adapter_hidden == 1024


def test_mistral_cg_accelerator_wires_context():
    ctx = initialize_for_model("mistral_cg", {
        "hidden_dim": 4096, "num_heads": 32, "num_kv_heads": 8,
        "rope_dim": 128, "window_size": 4096,
    })
    acc = MistralCGAccelerator(context=ctx)
    assert acc.head_dim == 128
    assert acc.phase_attn.num_kv_heads == 8
    assert acc.phase_attn.head_group_size == 4
    assert acc.phase_attn.rope_dim == 128
    # state_projector defaults to hidden // 4
    assert acc.state_projector.intermediate_dim == 1024
    # Intent projector shape: 12 Bhavas -> num_heads
    assert acc.intent_projector_shape == (12, 32)
    # Phase adapter shape: H -> 1024 -> hidden_dim
    assert acc.phase_adapter_shape == (32, 1024, 4096)


def test_mistral_cg_rejects_bad_hidden_dim():
    with pytest.raises(ValueError, match="hidden_dim"):
        MistralCGAccelerator(MistralCGConfig(hidden_dim=4097, num_heads=32))


def test_mistral_cg_forward_returns_expected_keys():
    acc = MistralCGAccelerator()
    # Stub tensors: sentinels accepted end-to-end
    q, k, v = object(), object(), object()
    out = acc.forward(hidden=object(), query=q, key=k, value=v, delta_bhava=None)
    assert set(out.keys()) == {"state", "output", "coherence", "state_delta", "adapter"}
    assert isinstance(out["state"], SovereignState)
    assert out["adapter"] is None                    # ablation path


# ----- HybridOntologicalAccelerator -----

def test_hybrid_default_is_12_layers_mha():
    acc = HybridOntologicalAccelerator()
    assert len(acc.blocks) == 12
    assert len(acc.layer_harmonics) == 12
    for i, block in enumerate(acc.blocks):
        assert block.ontology_layer == i
        assert block.num_kv_heads == block.heads     # MHA


def test_hybrid_rejects_bad_harmonics_length():
    with pytest.raises(ValueError, match="layer_harmonics"):
        HybridOntologicalAccelerator(HybridOntologicalConfig(layer_harmonics=(1.0, 2.0)))


def test_hybrid_forward_layer_index_bounds():
    acc = HybridOntologicalAccelerator()
    with pytest.raises(IndexError):
        acc.forward_layer(object(), 12)


def test_hybrid_forward_traces_per_layer():
    acc = HybridOntologicalAccelerator()
    out = acc.forward(object())
    assert len(out["coherence_per_layer"]) == 12
    assert len(out["state_delta_per_layer"]) == 12
    assert out["witness_layer_idx"] == 9
    assert out["unifying_layer_idx"] == 10


# ----- bind_mistral_to_cohera -----

def test_bind_from_hf_config_dict():
    hf_cfg = {
        "hidden_size": 4096,
        "num_attention_heads": 32,
        "num_key_value_heads": 8,
        "sliding_window": 4096,
        "rope_theta": 10000.0,
        "torch_dtype": "bfloat16",
    }
    acc, tok = bind_mistral_to_cohera(hf_cfg)
    assert tok is None
    assert isinstance(acc, MistralCGAccelerator)
    assert acc.config.num_kv_heads == 8
    assert acc.config.rope_dim == 128                # defaults to head_dim
    assert acc.config.window_size == 4096
    assert acc.config.dtype == DType.BF16


def test_bind_respects_overrides():
    hf_cfg = {
        "hidden_size": 4096, "num_attention_heads": 32,
        "num_key_value_heads": 8, "rope_theta": 10000.0,
    }
    acc, _ = bind_mistral_to_cohera(hf_cfg, overrides={"torch_dtype": "float16"})
    assert acc.config.dtype == DType.FP16


def test_bind_handles_missing_sliding_window():
    hf_cfg = {"hidden_size": 4096, "num_attention_heads": 32}
    acc, _ = bind_mistral_to_cohera(hf_cfg)
    assert acc.config.window_size == -1              # full attention
