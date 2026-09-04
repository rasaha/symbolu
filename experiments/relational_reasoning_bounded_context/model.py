"""BTRR model wrapper. torch is imported lazily so the package stays importable without torch.

The reasoning architecture is the frozen single-hop backbone (SoftmaxTransformerLM) parameterized only by
the Amendment-002 representation/sequence capacity (vocab 211, max_seq 3904). Reasoning depth/width/heads/
FFN and the training recipe are unchanged; only lexical + sequence capacity increase.
"""
from __future__ import annotations

import hashlib

from .config import (ARM_ABS, ARMS, D_FF, D_MODEL, DROPOUT, EXPECTED_REASONING_BLOCK_PARAMS,
                     EXPECTED_TOTAL_PARAMS, MAX_SEQ_LEN, N_HEADS, N_LAYERS, VOCAB_SIZE, arm_param_count,
                     backbone_param_count)


def analytic_parameter_count(arm: str = ARM_ABS) -> tuple[int, int]:
    """(total, reasoning_block) params, computed torch-free from the frozen config of `arm`."""
    total, blocks = arm_param_count(arm)
    spec = ARMS[arm]
    assert total == spec["expected_total_params"], (arm, total, spec["expected_total_params"])
    assert blocks == spec["expected_reasoning_block_params"], (arm, blocks)
    if arm == ARM_ABS:
        assert (total, blocks) == (EXPECTED_TOTAL_PARAMS, EXPECTED_REASONING_BLOCK_PARAMS)
    return total, blocks


def reasoning_block_delta_vs_original() -> int:
    """Reasoning-block parameter delta vs the original single-hop recipe (must be 0)."""
    return backbone_param_count(VOCAB_SIZE, MAX_SEQ_LEN)[1] - backbone_param_count(200, 1024)[1]


def build_model(initialization_seed: int, arm: str = ARM_ABS):
    """Build the torch model for `arm` (lazy import). ABS (default) is byte-identical to the pre-arm
    build. Asserts the runtime param count matches the arm's analytic count."""
    import torch  # lazy
    from symbolu_neural.clean_softmax.backbone import BackboneConfig, SoftmaxTransformerLM

    spec = ARMS[arm]
    kwargs = {}
    if spec["positional_mechanism"] == "rope":
        kwargs = {"positional": "rope", "rope_theta": float(spec["rope_theta"])}
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(initialization_seed))
        model = SoftmaxTransformerLM(BackboneConfig(
            vocab_size=VOCAB_SIZE, d_model=D_MODEL, n_layers=N_LAYERS, n_heads=N_HEADS,
            d_ff=D_FF, max_seq=MAX_SEQ_LEN, dropout=DROPOUT, **kwargs))
    total = sum(p.numel() for p in model.parameters())
    if total != spec["expected_total_params"]:
        raise AssertionError(f"{spec['name']}: runtime param count {total} != expected "
                             f"{spec['expected_total_params']}")
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
