"""BTRR model wrapper. torch is imported lazily so the package stays importable without torch.

The reasoning architecture is the frozen single-hop backbone (SoftmaxTransformerLM) parameterized only by
the Amendment-002 representation/sequence capacity (vocab 211, max_seq 3904). Reasoning depth/width/heads/
FFN and the training recipe are unchanged; only lexical + sequence capacity increase.
"""
from __future__ import annotations

import hashlib

from .config import (D_FF, D_MODEL, DROPOUT, EXPECTED_REASONING_BLOCK_PARAMS, EXPECTED_TOTAL_PARAMS,
                     MAX_SEQ_LEN, N_HEADS, N_LAYERS, VOCAB_SIZE, backbone_param_count)


def analytic_parameter_count() -> tuple[int, int]:
    """(total, reasoning_block) params, computed torch-free from the frozen config."""
    total, blocks = backbone_param_count(VOCAB_SIZE, MAX_SEQ_LEN)
    assert total == EXPECTED_TOTAL_PARAMS, (total, EXPECTED_TOTAL_PARAMS)
    assert blocks == EXPECTED_REASONING_BLOCK_PARAMS, (blocks, EXPECTED_REASONING_BLOCK_PARAMS)
    return total, blocks


def reasoning_block_delta_vs_original() -> int:
    """Reasoning-block parameter delta vs the original single-hop recipe (must be 0)."""
    return backbone_param_count(VOCAB_SIZE, MAX_SEQ_LEN)[1] - backbone_param_count(200, 1024)[1]


def build_model(initialization_seed: int):
    """Build the torch model (lazy import). Asserts the runtime param count matches the analytic count."""
    import torch  # lazy
    from symbolu_neural.clean_softmax.backbone import BackboneConfig, SoftmaxTransformerLM

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(initialization_seed))
        model = SoftmaxTransformerLM(BackboneConfig(
            vocab_size=VOCAB_SIZE, d_model=D_MODEL, n_layers=N_LAYERS, n_heads=N_HEADS,
            d_ff=D_FF, max_seq=MAX_SEQ_LEN, dropout=DROPOUT))
    total = sum(p.numel() for p in model.parameters())
    if total != EXPECTED_TOTAL_PARAMS:
        raise AssertionError(f"runtime param count {total} != expected {EXPECTED_TOTAL_PARAMS}")
    return model


def parameter_digest_from_bytes(state_bytes: bytes) -> str:
    """Deterministic checkpoint identity digest (torch-free helper)."""
    return hashlib.sha256(state_bytes).hexdigest()


def parameter_digest(model) -> str:
    """sha256 over the sorted torch state_dict (name, dtype, shape, raw bytes)."""
    import torch  # lazy
    h = hashlib.sha256()
    for name, p in sorted(model.state_dict().items()):
        h.update(name.encode("utf-8"))
        h.update(str(p.dtype).encode("ascii"))
        h.update(str(tuple(p.shape)).encode("ascii"))
        h.update(bytes(p.detach().cpu().contiguous().flatten().view(torch.uint8).tolist()))
    return h.hexdigest()
