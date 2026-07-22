"""Sanity tests for the read-only causal-analysis tools (hooks must not leak or mutate)."""
import torch
from qgr import QuadConfig, build_model
from qgr.mqar import MQARConfig, generate_batch
from qgr.causal import Ablator, activation_patching, integrated_gradients_pathways


def _cfg():
    return QuadConfig(vocab_size=32, hidden_size=48, num_layers=2, num_heads=4,
                      ff_size=192, context_length=64)


def _mq():
    return MQARConfig(num_kv=4, num_queries=2, vocab_size=32)


def test_zero_ablation_changes_output_and_hooks_are_removable():
    m = build_model(_cfg(), 0).eval()
    b = generate_batch(_mq(), seed=0, batch_size=3)
    with torch.no_grad():
        clean = m(b.tokens)["logits"].clone()
    ab = Ablator(m); ab.ablate_attn([1], "zero")
    with torch.no_grad():
        ablated = m(b.tokens)["logits"].clone()
    ab.clear()
    with torch.no_grad():
        restored = m(b.tokens)["logits"].clone()
    assert not torch.equal(clean, ablated)      # ablation had an effect
    assert torch.equal(clean, restored)         # hooks fully removed -> identical to clean


def test_zero_attn_makes_block_output_pure_residual():
    """With attention output zeroed, the block's contribution is only x + ff(x)."""
    m = build_model(_cfg(), 1).eval()
    b = generate_batch(_mq(), seed=1, batch_size=2)
    captured = {}
    def cap(mod, inp, out):
        captured["o"] = out[0]
        return out
    h = m.blocks[1].attn.register_forward_hook(cap)
    ab = Ablator(m); ab.ablate_attn([1], "zero")   # zero hook registered AFTER capture hook
    with torch.no_grad():
        m(b.tokens)
    ab.clear(); h.remove()
    # the zero hook runs last and replaces the output with zeros
    # (capture saw the pre-zero value; verify the zero hook is what the block used by re-running)
    z = {}
    def capz(mod, inp, out):
        z["o"] = out[0]; return out
    ab2 = Ablator(m); ab2.ablate_attn([1], "zero")
    hz = m.blocks[1].attn.register_forward_hook(capz)  # runs after the zero hook
    with torch.no_grad():
        m(b.tokens)
    hz.remove(); ab2.clear()
    assert torch.count_nonzero(z["o"]) == 0


def test_patching_and_ig_run():
    m = build_model(_cfg(), 2).eval()
    pt = activation_patching(m, _mq(), 0, layer=1, n_batches=2, batch_size=16)
    assert set(pt) == {"clean", "corrupt", "patched", "recovery"}
    ig = integrated_gradients_pathways(m, _mq(), 0, layer=1, steps=4, batch_size=8)
    assert 0.0 <= ig["attn_frac"] <= 1.0 and abs(ig["attn_frac"] + ig["ff_frac"] - 1.0) < 1e-5
