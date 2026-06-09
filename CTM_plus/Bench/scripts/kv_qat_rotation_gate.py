#!/usr/bin/env python3
# Learned-rotation HARD-TAIL GATE — the real go/no-go for "delete the KV tax".
#
# THE DECISION THIS MAKES
#   The recon screen (kv_qat_learned_rotation.py) asks "is K rotatable?" cheaply.
#   This asks the question that actually decides shipping: does learned-rotation +
#   PER-TENSOR K hold the HARD TAIL as well as the per-channel + protect design it
#   would replace? It runs free-generation token-agreement vs bf16 for THREE arms
#   and gates on arm 3 >= arm 2:
#     arm 1  bf16                         -> 1.0 reference (NOT the bar)
#     arm 2  per-channel + protect        -> the BASELINE TO MATCH (round_trip_kv)
#     arm 3  learned-R post-RoPE + per-tensor K  -> the lever
#
# WHY THIS GATE, NOT THE EXTERNAL ONES
#   * Hard-tail FREE-GENERATION agreement (use_cache=False, full requant) -- NOT
#     PPL and NOT multiple-choice accuracy (TruthfulQA/HellaSwag), both near-ceiling
#     and insensitive (the "too easy" trap). recon != downstream.
#   * The bar is per-channel+PROTECT (~0.74 on this hard metric), NOT bf16 (1.0):
#     even protect doesn't reach bf16 here, so requiring "98% of bf16" is the wrong,
#     impossible bar. Learned rotation only has to MATCH the design it replaces.
#   * Rotation is applied POST-RoPE to BOTH Q and K (verified: pre-RoPE by a general
#     R breaks attention). R is per (layer, head); GQA Q-heads use their KV-head's R.
#
# Run:
#   python CTM_plus/Bench/scripts/kv_qat_rotation_gate.py --selftest        # CPU, injection math
#   PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_rotation_gate.py \
#       --model Qwen/Qwen2.5-7B-Instruct --n-prompts 16 --gen 48           # pod, 3-arm gate
#
# numpy core (injection math + gate logic) is CPU-tested here; the 3-arm model run
# is pod-only (lazy torch). End-to-end on the pod is UNVERIFIED here by construction.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from kv_qat_learned_rotation import per_tensor_rt, learn_rotation  # noqa: E402


# --------------------------------------------------------------------------- #
# Injection math (CPU-testable). Same op the GPU hook performs, in numpy.
# --------------------------------------------------------------------------- #
def rotate_per_head(x: np.ndarray, R: np.ndarray) -> np.ndarray:
    """x:[H,T,D] (one batch), R:[H,D,D] per-head orthogonal. Returns x@R per head."""
    return np.einsum("htd,hde->hte", x, R)


def arm3_k_path(k: np.ndarray, R: np.ndarray, bits: int = 4) -> np.ndarray:
    """The arm-3 K transform: rotate post-RoPE K per head -> per-TENSOR int4 ->
    dequant (still rotated; attention sees rotated Q too). k:[H,T,D], R:[H,D,D]."""
    kr = rotate_per_head(k, R)
    out = np.empty_like(kr)
    for h in range(kr.shape[0]):
        out[h] = per_tensor_rt(kr[h], bits)        # one scale per (head) -> no per-channel tax
    return out


def attn_scores(q: np.ndarray, k: np.ndarray) -> np.ndarray:
    """[H,Tq,D],[H,Tk,D] -> [H,Tq,Tk] per-head QK^T."""
    return np.einsum("hqd,hkd->hqk", q, k)


def gate_verdict(agree_bf16: float, agree_perchan: float, agree_learned: float,
                 margin: float = 0.01) -> dict:
    """arm3 must MATCH arm2 (per-channel+protect), not bf16. bf16 is the 1.0 ref."""
    delta = agree_learned - agree_perchan
    label = ("PASS" if delta >= -margin else "FAIL")
    return {
        "bf16_ref": round(agree_bf16, 4),
        "per_channel_protect": round(agree_perchan, 4),     # the bar
        "learned_per_tensor": round(agree_learned, 4),
        "learned_minus_baseline": round(delta, 4),
        "verdict": label,
        "note": ("learned per-tensor matches/exceeds per-channel+protect on the hard tail"
                 if label == "PASS" else
                 "learned per-tensor LOSES the hard tail vs per-channel+protect -> ship hybrid"),
    }


# --------------------------------------------------------------------------- #
# GPU mode: the 3-arm free-generation gate (pod only).
# --------------------------------------------------------------------------- #
def run_gpu(args) -> int:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    sys.path.insert(0, str(_HERE.parent.parent / "KVPolicy"))
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA
    from kv_policy.kv_aware_qat import rotary_module
    import kv_qat_gen_eval as ge   # reuse build_prompts + the per-channel hook

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(args.model)
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(dev).eval()
    model.config.use_cache = False
    cfg = model.config
    n_layers = cfg.num_hidden_layers
    n_kv = cfg.num_key_value_heads
    n_q = cfg.num_attention_heads
    D = cfg.hidden_size // n_q
    grp = n_q // n_kv                                   # GQA group size
    mgr = INT4CacheKVRouteA(k_group_size=args.group_size, v_group_size=args.group_size,
                            asymmetric=True, bits=4, sink_size=0, num_kv_heads=n_kv,
                            kernel_backend="dequant_fallback")
    prompts = ge.build_prompts(torch, tok, args.n_prompts, args.prompt_len,
                               args.dataset, args.dataset_config)
    print(f"[gate] model={args.model} layers={n_layers} q_heads={n_q} kv_heads={n_kv} "
          f"D={D} gqa={grp}  (free-gen, use_cache=False)", flush=True)

    # --- calibrate: collect post-RoPE K per (layer, kv-head), learn R, attribute by call order ---
    print("[gate] calibrating learned R per (layer, kv-head)...", flush=True)
    qm = rotary_module(model)
    orig = qm.apply_rotary_pos_emb
    Kbuf = {li: [] for li in range(n_layers)}
    state = {"i": 0}

    def cap(q, k, cos, sin, *a, **kw):
        qe, ke = orig(q, k, cos, sin, *a, **kw)
        li = state["i"] % n_layers
        if len(Kbuf[li]) < 1:                          # one chunk/layer is enough to learn R
            Kbuf[li].append(ke.detach().float().cpu().numpy()[0])   # [n_kv, T, D]
        state["i"] += 1
        return qe, ke
    qm.apply_rotary_pos_emb = cap
    with torch.no_grad():
        model(prompts[0].to(dev))
    qm.apply_rotary_pos_emb = orig

    R = np.zeros((n_layers, n_kv, D, D), dtype=np.float32)
    for li in range(n_layers):
        kl = Kbuf[li][0]                               # [n_kv, T, D]
        for h in range(n_kv):
            R[li, h], _, _ = learn_rotation(kl[h], iters=args.iters, seed=1)
    Rt = torch.tensor(R, device=dev, dtype=torch.float32)
    print(f"[gate] learned {n_layers*n_kv} rotations (D={D}).", flush=True)

    # --- arm-3 hook: post-RoPE rotate Q (by KV-head's R) + rotate+per-tensor-quant K ---
    def install_learned_hook():
        st = {"i": 0}
        def pt_quant(x):                               # per-tensor int4 over last dim group
            qmv = 7
            s = x.abs().amax(dim=(-2, -1), keepdim=True) / qmv
            s = torch.where(s == 0, torch.ones_like(s), s)
            return torch.clamp(torch.round(x / s), -qmv, qmv) * s
        def rope(q, k, cos, sin, *a, **kw):
            qe, ke = orig(q, k, cos, sin, *a, **kw)
            li = st["i"] % n_layers; st["i"] += 1
            Rl = Rt[li]                                # [n_kv, D, D]
            Rq = Rl.repeat_interleave(grp, dim=0)      # [n_q, D, D] (GQA expand)
            qr = torch.einsum("bhtd,hde->bhte", qe.float(), Rq).to(qe.dtype)
            kr = torch.einsum("bhtd,hde->bhte", ke.float(), Rl)
            kr = pt_quant(kr).to(ke.dtype)
            return qr, kr
        qm.apply_rotary_pos_emb = rope
        # V: same int4 V as the per-channel arm, to isolate the K scheme.
        def vhook(m, inp, out):
            shape = out.shape
            flat = out.reshape(-1, shape[-1])
            _, vl = mgr.round_trip_kv(flat, flat)
            return vl.reshape(shape)
        handles = [m.register_forward_hook(vhook)
                   for n, m in model.named_modules() if n.rsplit(".", 1)[-1] == "v_proj"]
        def restore():
            qm.apply_rotary_pos_emb = orig
            for hh in handles:
                hh.remove()
        return restore

    @torch.no_grad()
    def gen(ids):
        out = model.generate(ids, max_new_tokens=args.gen, do_sample=False, num_beams=1,
                             use_cache=False, pad_token_id=pad)
        return out[0, ids.shape[1]:]

    def agreement(install):
        matched = total = 0
        for ids in prompts:
            ids = ids.to(dev)
            g_ref = gen(ids)
            restore = install()
            try:
                g = gen(ids)
            finally:
                restore()
            n = min(g_ref.numel(), g.numel())
            matched += int((g_ref[:n] == g[:n]).sum()); total += n
        return matched / max(1, total)

    a_perchan = agreement(lambda: ge.install_int4_inference_hooks(torch, model, mgr))
    a_learned = agreement(install_learned_hook)
    v = gate_verdict(1.0, a_perchan, a_learned, margin=args.margin)
    print("\n[gate] 3-arm hard-tail free-generation agreement vs bf16:")
    for k_, val in v.items():
        print(f"  {k_:24s} {val}")
    print(f"\n[gate] {v['verdict']}: {v['note']}")
    return 0


# --------------------------------------------------------------------------- #
# Selftest (CPU): the injection math + gate logic
# --------------------------------------------------------------------------- #
def selftest() -> int:
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("kv_qat_rotation_gate selftest")
    rng = np.random.default_rng(0)
    H, T, D = 4, 16, 64
    q = rng.standard_normal((H, T, D)); k = rng.standard_normal((H, T, D))
    R = np.stack([np.linalg.qr(rng.standard_normal((D, D)))[0] for _ in range(H)])

    base = attn_scores(q, k)
    # rotated Q + rotated K (no quant) must EXACTLY preserve per-head QK^T.
    qr = rotate_per_head(q, R)
    kr = rotate_per_head(k, R)
    check("rotated Q & K preserve attention exactly (no quant)",
          np.abs(attn_scores(qr, kr) - base).max() < 1e-9)
    # rotated Q + rotated+per-tensor-quant K: error shrinks to ~0 as bits grow.
    s4 = np.abs(attn_scores(qr, arm3_k_path(k, R, 4)) - base).max()
    s12 = np.abs(attn_scores(qr, arm3_k_path(k, R, 12)) - base).max()
    check("quant error in rotated path shrinks with bits (12-bit << 4-bit)", s12 < s4 * 0.2)
    check("12-bit rotated-per-tensor path ~ exact", s12 / (np.abs(base).max()) < 0.02)

    # gate logic: PASS iff learned >= per-channel (within margin); bf16 is only the ref.
    p = gate_verdict(1.0, 0.74, 0.75)
    check("gate PASS when learned >= per-channel+protect", p["verdict"] == "PASS")
    f = gate_verdict(1.0, 0.74, 0.60)
    check("gate FAIL when learned loses the hard tail", f["verdict"] == "FAIL")
    n = gate_verdict(1.0, 0.74, 0.735)
    check("gate tolerates noise within margin (0.735 vs 0.74 -> PASS)", n["verdict"] == "PASS")
    # bf16 is NOT the bar: learned 0.75 passes even though it's far below bf16 1.0.
    check("bf16 (1.0) is the reference, not the bar", p["verdict"] == "PASS")

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Learned-rotation hard-tail gate (3-arm free-gen)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--group-size", type=int, default=32)
    ap.add_argument("--n-prompts", type=int, default=16)
    ap.add_argument("--prompt-len", type=int, default=128)
    ap.add_argument("--gen", type=int, default=48)
    ap.add_argument("--iters", type=int, default=300, help="Cayley iterations per (layer,head)")
    ap.add_argument("--margin", type=float, default=0.01, help="how far below per-channel still PASS")
    ap.add_argument("--dataset", default="Salesforce/wikitext")
    ap.add_argument("--dataset-config", default="wikitext-103-raw-v1")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run_gpu(args)


if __name__ == "__main__":
    raise SystemExit(main())
