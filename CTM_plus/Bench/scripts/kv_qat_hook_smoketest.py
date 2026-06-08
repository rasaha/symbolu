#!/usr/bin/env python3
"""KV-QAT hook smoke-test — de-risk the attention-hook wiring before the full pilot.

Staged + lean diagnostic version. Proves end-to-end that the int4 fake-quant wires
into a real Qwen2 attention stack and passes gradients through the round-trip to
the weights. Runs on CPU, tiny, no HF download. Each stage logs (flushed) so a hard
failure (e.g. OOM "Killed") pinpoints the culprit instead of dying silently.

Lean choices (a prior run got SIGKILL'd at the first model forward — host-RAM OOM,
not the quantizer): CUDA hidden (drops the cu12x context's host-RAM footprint),
single thread, use_cache=False, sliding_window off, max_pos=64, input (1, 8).

Run:
    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_hook_smoketest.py

Honest scope: hooks the k_proj / v_proj OUTPUT (pre-RoPE for K) — the right,
version-stable place to prove WIRING + gradient flow. The full pilot must move the
K hook POST-RoPE for serving parity (round_trip_kv quantizes rotated K at
inference); a known refinement, flagged so it isn't forgotten.
"""
from __future__ import annotations

import os
import sys

# CPU-only BEFORE importing torch: avoids the CUDA context's host-RAM (the likely
# cause of the earlier "Killed"); this smoke test needs no GPU.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    try:
        import torch
        torch.set_num_threads(1)
        import transformers
        from transformers import Qwen2Config, Qwen2ForCausalLM
    except Exception as e:  # noqa: BLE001
        log(f"SMOKE-TEST CANNOT RUN: need torch + transformers ({e})")
        return 2

    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA
    from kv_policy.kv_aware_qat import ste_fake_quant

    torch.manual_seed(0)
    log(f"[env] torch {torch.__version__}  transformers {transformers.__version__}  (CPU-only)")

    HEADS, H_KV, HID = 4, 2, 256
    HEAD_DIM = HID // HEADS                      # 64
    KVD = H_KV * HEAD_DIM                        # 128 = k/v_proj out features

    mgr = INT4CacheKVRouteA(
        k_group_size=32, v_group_size=32, asymmetric=True, bits=4, sink_size=0,
        num_kv_heads=H_KV, kernel_backend="dequant_fallback",
    )

    # --- STAGE 0: round_trip_kv in ISOLATION (quantizer, independent of the model) ---
    log("[stage0] round_trip_kv on a (8,128) tensor ...")
    k0, v0 = torch.randn(8, KVD), torch.randn(8, KVD)
    k0l, v0l = mgr.round_trip_kv(k0, v0)
    d0 = (k0l - k0).abs().max().item()
    assert k0l.shape == k0.shape and d0 > 0, "round_trip_kv no-op or wrong shape"
    log(f"[stage0] OK  shapes {tuple(k0l.shape)}  |Δk|max={d0:.4f}")

    # --- STAGE 1: STE gradient identity on that same distortion ---------------------
    x = torch.randn(8, KVD, requires_grad=True)
    with torch.no_grad():
        xl, _ = mgr.round_trip_kv(x, x)
    y = ste_fake_quant(x, xl)
    y.sum().backward()
    assert torch.equal(x.grad, torch.ones_like(x)), "STE backward not identity"
    log("[stage1] OK  STE forward==round_trip, backward==identity")

    # --- STAGE 2: tiny 2-layer Qwen2 (random weights, no download) ------------------
    cfg = Qwen2Config(
        vocab_size=512, hidden_size=HID, intermediate_size=512,
        num_hidden_layers=2, num_attention_heads=HEADS, num_key_value_heads=H_KV,
        head_dim=HEAD_DIM, max_position_embeddings=64, sliding_window=None,
        use_cache=False,
    )
    cfg._attn_implementation = "eager"
    log("[stage2] building 2L Qwen2 ...")
    model = Qwen2ForCausalLM(cfg)
    model.config.use_cache = False
    model.train()
    log(f"[stage2] built  hidden={HID} heads={HEADS} kv_heads={H_KV} head_dim={HEAD_DIM} "
        f"k/v_proj_out={KVD}")

    # --- STAGE 3: install fake-quant hooks on every k_proj / v_proj -----------------
    state = {"fired": 0, "max_abs_delta": 0.0, "parity_ok": True}

    def make_hook(which: str):
        def hook(module, inputs, out):
            shape = out.shape
            flat = out.reshape(-1, shape[-1])              # (num_tokens, kv_heads*head_dim)
            with torch.no_grad():
                k_l, v_l = mgr.round_trip_kv(flat, flat)
            lossy = k_l if which == "k" else v_l
            fake = ste_fake_quant(flat, lossy)
            state["fired"] += 1
            state["max_abs_delta"] = max(
                state["max_abs_delta"], (fake.detach() - flat.detach()).abs().max().item())
            if not torch.allclose(fake.detach(), lossy, atol=1e-5, rtol=0.0):
                state["parity_ok"] = False
            return fake.reshape(shape)
        return hook

    n_hooked = 0
    for name, module in model.named_modules():
        leaf = name.rsplit(".", 1)[-1]
        if leaf in ("k_proj", "v_proj"):
            module.register_forward_hook(make_hook("k" if leaf == "k_proj" else "v"))
            n_hooked += 1
    assert n_hooked == cfg.num_hidden_layers * 2, f"hooked {n_hooked}, expected 4"
    log(f"[stage3] installed {n_hooked} hooks")

    # --- STAGE 4: two training steps (forward+backward+step), CPU, tiny input -------
    opt = torch.optim.SGD([p for p in model.parameters() if p.requires_grad], lr=1e-3)
    input_ids = torch.randint(0, cfg.vocab_size, (1, 8))
    losses, kgradnorms = [], []
    for step in range(2):
        log(f"[stage4] step {step}: forward ...")
        opt.zero_grad(set_to_none=True)
        out = model(input_ids=input_ids, labels=input_ids)
        lossval = float(out.loss.detach())            # detach: float() on a grad tensor warns
        log(f"[stage4] step {step}: backward (loss={lossval:.4f}) ...")
        out.loss.backward()
        kp = model.model.layers[0].self_attn.k_proj.weight
        kgradnorms.append(0.0 if kp.grad is None else float(kp.grad.norm()))
        opt.step()
        losses.append(lossval)
        log(f"[stage4] step {step}: done  k_proj.grad_norm={kgradnorms[-1]:.4e}")

    # --- verdict --------------------------------------------------------------------
    kp = model.model.layers[0].self_attn.k_proj.weight
    checks = {
        "hook fired on every proj/step": state["fired"] == cfg.num_hidden_layers * 2 * 2,
        "fake-quant changed K/V (not a no-op)": state["max_abs_delta"] > 0.0,
        "model saw round_trip_kv output (parity)": state["parity_ok"],
        "loss finite": all(l == l and abs(l) != float("inf") for l in losses),
        "grad flows THROUGH int4 round-trip to k_proj": (
            kp.grad is not None and kgradnorms[-1] > 0.0
            and torch.isfinite(kp.grad).all().item()),
    }
    log("\n--- KV-QAT hook smoke-test ---")
    for k, v in checks.items():
        log(f"  [{'PASS' if v else 'FAIL'}] {k}")
    log(f"  (fired={state['fired']}, max|Δ K/V|={state['max_abs_delta']:.4f}, "
        f"loss {losses[0]:.3f}->{losses[1]:.3f}, k_grad {kgradnorms[0]:.2e}->{kgradnorms[1]:.2e})")
    ok = all(checks.values())
    log("kv_qat_hook_smoketest: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
