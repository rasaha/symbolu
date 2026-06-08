#!/usr/bin/env python3
"""KV-QAT hook smoke-test — de-risk the ONE fragile part of the training pilot.

Purpose (from KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md): before committing GPU-hours
to a real KV-aware fine-tune, prove end-to-end that

  1. the int4 fake-quant WIRES INTO a real Qwen2 attention stack,
  2. it applies the EXACT inference distortion (INT4CacheKVRouteA.round_trip_kv),
  3. gradients flow THROUGH the int4 round-trip (the STE) to the trainable weights,
  4. two optimizer steps run with a finite loss.

It is deliberately tiny and self-contained: a 2-layer Qwen2 built from config with
RANDOM weights (no HF download), on CPU. If this passes, the hook + STE mechanism is
sound and the full pilot is "just" a LoRA + data + eval wrapper around it.

Run:
    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_hook_smoketest.py

Honest scope: this hooks the k_proj / v_proj OUTPUT (pre-RoPE for K) — the right,
version-stable place to prove WIRING + gradient flow. The full pilot must move the
K hook to POST-RoPE for serving parity (round_trip_kv quantizes rotated K at
inference); that's a known refinement, called out here so it isn't forgotten.
"""
from __future__ import annotations

import sys


def main() -> int:
    try:
        import torch
        import transformers
        from transformers import Qwen2Config, Qwen2ForCausalLM
    except Exception as e:  # noqa: BLE001
        print(f"SMOKE-TEST CANNOT RUN: need torch + transformers ({e})")
        return 2

    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA
    from kv_policy.kv_aware_qat import ste_fake_quant

    torch.manual_seed(0)
    print(f"[env] torch {torch.__version__}  transformers {transformers.__version__}")

    # --- 1. tiny 2-layer Qwen2, random weights, CPU, eager attention ---------
    H_KV = 2
    cfg = Qwen2Config(
        vocab_size=1024, hidden_size=256, intermediate_size=512,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=H_KV,
        max_position_embeddings=2048, attn_implementation="eager",
    )
    cfg._attn_implementation = "eager"
    model = Qwen2ForCausalLM(cfg)
    model.train()
    head_dim = cfg.hidden_size // cfg.num_attention_heads
    print(f"[model] 2L Qwen2  hidden={cfg.hidden_size} heads={cfg.num_attention_heads} "
          f"kv_heads={H_KV} head_dim={head_dim}  (k/v_proj out = {H_KV*head_dim})")

    # --- 2. the int4 manager whose round_trip_kv IS the inference distortion --
    #     dequant_fallback path = pure-torch naive int4 = the B1 (0% protect) arm.
    mgr = INT4CacheKVRouteA(
        k_group_size=32, v_group_size=32, asymmetric=True, bits=4, sink_size=0,
        num_kv_heads=H_KV, kernel_backend="dequant_fallback",
    )

    state = {"fired": 0, "max_abs_delta": 0.0, "parity_ok": True}

    def make_hook(which: str):
        def hook(module, inputs, out):
            orig_shape = out.shape
            hd = orig_shape[-1]
            flat = out.reshape(-1, hd)                      # (num_tokens, kv_heads*head_dim)
            with torch.no_grad():
                k_lossy, v_lossy = mgr.round_trip_kv(flat, flat)
            lossy = k_lossy if which == "k" else v_lossy
            fake = ste_fake_quant(flat, lossy)
            # instrumentation: hook fired, distortion non-trivial, forward parity
            state["fired"] += 1
            state["max_abs_delta"] = max(
                state["max_abs_delta"], (fake.detach() - flat.detach()).abs().max().item())
            # model must SEE the round_trip output (to float eps — STE x+(q-x) can
            # differ from q by a ULP; that's parity for training purposes).
            if not torch.allclose(fake.detach(), lossy, atol=1e-5, rtol=0.0):
                state["parity_ok"] = False
            return fake.reshape(orig_shape)
        return hook

    n_hooked = 0
    for name, module in model.named_modules():
        leaf = name.rsplit(".", 1)[-1]
        if leaf in ("k_proj", "v_proj"):
            module.register_forward_hook(make_hook("k" if leaf == "k_proj" else "v"))
            n_hooked += 1
    if n_hooked == 0:
        print("FAIL: found no k_proj/v_proj modules to hook")
        return 1
    print(f"[hook] installed on {n_hooked} proj modules "
          f"(expect {cfg.num_hidden_layers*2})")

    # --- 3. two training steps; check loss finite + grads flow through STE ----
    opt = torch.optim.SGD([p for p in model.parameters() if p.requires_grad], lr=1e-3)
    input_ids = torch.randint(0, cfg.vocab_size, (2, 24))   # (batch, seq)
    losses = []
    for step in range(2):
        opt.zero_grad(set_to_none=True)
        out = model(input_ids=input_ids, labels=input_ids)
        loss = out.loss
        loss.backward()
        # k_proj.weight gradient can ONLY reach the loss through the K path, which
        # now runs through the int4 fake-quant — so a finite non-zero grad here is
        # PROOF the STE passed gradient through the round-trip.
        kp = model.model.layers[0].self_attn.k_proj.weight
        opt.step()
        losses.append(float(loss))
        print(f"[step {step}] loss={float(loss):.4f}  "
              f"k_proj.grad_norm={0.0 if kp.grad is None else float(kp.grad.norm()):.4e}")

    # --- 4. verdict ----------------------------------------------------------
    kp = model.model.layers[0].self_attn.k_proj.weight
    checks = {
        "hook fired on every proj/step": state["fired"] == cfg.num_hidden_layers * 2 * 2,
        "fake-quant changed K/V (not a no-op)": state["max_abs_delta"] > 0.0,
        "model saw round_trip_kv output (parity)": state["parity_ok"],
        "loss finite": all(l == l and abs(l) != float("inf") for l in losses),
        "grad flows THROUGH int4 round-trip to k_proj": (
            kp.grad is not None and float(kp.grad.norm()) > 0.0
            and torch.isfinite(kp.grad).all().item()),
    }
    print("\n--- KV-QAT hook smoke-test ---")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"  (fired={state['fired']}, max|Δ K/V|={state['max_abs_delta']:.4f}, "
          f"loss {losses[0]:.3f}->{losses[1]:.3f})")
    ok = all(checks.values())
    print("kv_qat_hook_smoketest: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
