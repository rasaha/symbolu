"""KV-aware QAT primitive — train-time fake-quant that EXACTLY mirrors the
inference INT4 KV distortion, with a straight-through estimator (STE).

This is the correctness-critical core of the KV-aware training experiment
(see ``Bench/scripts/KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md``). The experiment
asks whether *training* the model to tolerate int4 KV removes the post-hoc
sidecar tax (the +4.7 GB that makes int4_protected footprint-negative). For that
to be a valid test, the model must adapt to the **same** distortion it will face
at serving time — train/inference quantization parity is non-negotiable.

We get that parity for free by reusing ``INT4CacheKVRouteA.round_trip_kv`` (the
identical quantize→dequantize the serving path applies) inside the training
forward. The ONLY thing we add is the STE: ``round_trip_kv`` contains round/clamp
ops whose gradient is ~zero almost everywhere, so a naive backward would send no
signal to the weights. The STE returns the lossy value in the forward but passes
the gradient straight through (identity) in the backward, exactly as in weight
QAT. No new quantizer, no second code path — that is the whole point.

CPU-testable; no torch import at module load (kept inside the functions) so this
file imports cleanly in the stub/CPU harness.
"""
from __future__ import annotations

from typing import Any, Tuple


def ste_fake_quant(x, q):
    """Straight-through fake-quant.

    Forward returns the quantized tensor ``q`` EXACTLY; backward passes the
    gradient straight through to ``x`` (identity). ``q`` must be the (no-grad)
    quantized view of ``x``. Classic STE identity ``x + (q - x).detach()``:
    the value collapses to ``q`` (``x + q - x``), while ``d/dx = 1`` because the
    correction term is detached. ``x`` carries the graph; ``q`` need not.
    """
    return x + (q - x).detach()


def kv_qat_round_trip(manager: Any, key, value) -> "Tuple[Any, Any]":
    """Train-time fake-quant for the KV cache that mirrors inference exactly.

    Reuses ``manager.round_trip_kv`` (the SAME compress→decompress the serving
    path applies — INT4CacheKVRouteA) so the model adapts to the IDENTICAL
    distortion it meets at decode: parity by construction, not by re-derivation.
    STE (above) makes it differentiable. Returns ``(k_fake, v_fake)`` carrying
    the inference-lossy *values* with full gradient flow back to K/V.

    Drop this into a HF attention ``forward`` right after the q/k/v projection +
    RoPE, replacing ``k, v`` with ``k_fake, v_fake`` before the attention scores
    (the install hook is sketched in the design doc). ``manager`` must have
    ``num_kv_heads`` set so ``round_trip_kv`` can reshape the 2-D layout.
    """
    import torch
    with torch.no_grad():
        k_lossy, v_lossy = manager.round_trip_kv(key, value)
    return ste_fake_quant(key, k_lossy), ste_fake_quant(value, v_lossy)


def rotary_module(model):
    """The transformers modeling module whose ``apply_rotary_pos_emb`` the model's
    attention calls — resolved from ``model.config.model_type`` so the post-RoPE
    hook works across qwen2 / mistral / llama / ... not just qwen2. (The attention
    forward looks the function up in this module's namespace at call time, so
    patching the module binding takes effect.)"""
    import importlib
    mt = getattr(getattr(model, "config", None), "model_type", None) or ""
    mod = importlib.import_module(f"transformers.models.{mt}.modeling_{mt}")
    if not hasattr(mod, "apply_rotary_pos_emb"):
        raise RuntimeError(
            f"{mod.__name__} has no apply_rotary_pos_emb — the post-RoPE hook needs "
            f"adapting for model_type={mt!r}")
    return mod


def _selftest() -> None:
    """CPU self-test: STE forward-parity + identity-backward, and that the KV
    wrapper byte-matches the manager's round_trip_kv on BOTH K and V while
    keeping gradient flow. Real-manager parity is then by construction (the
    wrapper literally calls round_trip_kv)."""
    import torch
    torch.manual_seed(0)

    # 1) STE primitive: forward == q exactly; backward == identity.
    x = torch.randn(8, 16, requires_grad=True)
    q = (x.detach() * 8).round() / 8               # arbitrary no-grad quantization
    y = ste_fake_quant(x, q)
    assert torch.equal(y, q), "STE forward must equal the quantized tensor q"
    y.sum().backward()
    assert torch.equal(x.grad, torch.ones_like(x)), "STE backward must be identity"

    # 2) KV wrapper: forward byte-matches round_trip_kv on K and V; grad is STE.
    class _FakeMgr:
        """Stand-in for INT4CacheKVRouteA.round_trip_kv (deterministic int4-ish
        round-trip). The real manager makes the wrapper parity-correct for free."""
        def round_trip_kv(self, k, v):
            rt = lambda t: (t * 4).round().clamp(-32, 31) / 4
            return rt(k), rt(v)

    mgr = _FakeMgr()
    k = torch.randn(4, 32, requires_grad=True)
    v = torch.randn(4, 32, requires_grad=True)
    kf, vf = kv_qat_round_trip(mgr, k, v)
    with torch.no_grad():
        k_ref, v_ref = mgr.round_trip_kv(k, v)
    assert torch.equal(kf, k_ref) and torch.equal(vf, v_ref), \
        "fake-quant forward must byte-match the inference round_trip_kv"
    (kf.sum() + vf.sum()).backward()
    assert torch.equal(k.grad, torch.ones_like(k)), "K grad must be STE identity"
    assert torch.equal(v.grad, torch.ones_like(v)), "V grad must be STE identity"

    print("kv_aware_qat self-test: PASS")


if __name__ == "__main__":
    _selftest()
