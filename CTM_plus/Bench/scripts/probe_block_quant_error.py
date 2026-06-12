#!/usr/bin/env python3
# probe_block_quant_error.py — per-block quantization-error diagnostics for the
# dynamic-protect decision. ONE GPU run captures everything; every later
# question is answerable offline from the artifacts (summary.json + npz).
#
# What it does:
#   1. Runs a STOCK bf16 vLLM engine (no int4 kernel needed — we measure the
#      MATH, not the kernel) over a mixed prompt corpus, hooking every layer's
#      attention to capture post-RoPE K, V and a sample of q rows at prefill.
#   2. Replays the EXACT validated quantization (imports
#      kv_policy.int4_per_channel_kv.quantize_per_channel_int4, group=32,
#      asymmetric, bits=4) under multiple policies per layer:
#        noprot      — int4 everywhere (what protect buys)
#        cur_bf16    — int4 + artifact protect mask channels kept exact
#        prot_int8   — protect channels stored int8 (proposal: halve sidecar)
#        mask sweep  — fresh max-abs masks at 1/2/3/4/6/8% (bf16 protect)
#        sens@4%     — sensitivity-ranked mask (E|q_d| x channel error)
#   3. Dynamic-protect CDF: per-(layer, block) max error under cur policy ->
#      % blocks exceeding each threshold + int8-fallback bytes cost at 100K.
#   4. Score-space SNR: |q·Δk| noise vs std(q·K) signal per layer (the local
#      mechanism of near-tie flips), GQA-mapped.
#
# Artifacts (out-dir): summary.json (all aggregates + config),
#   blocks.npz (per layer/block/head max+mean err, cur & noprot),
#   channels.npz (per layer/head/channel max-abs, sensitivity, in-mask).
#
# Usage (pod):
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
#   pkill -9 -f vllm; sleep 2
#   python CTM_plus/Bench/scripts/probe_block_quant_error.py --model $M --out-dir /tmp/qerr
#   python CTM_plus/Bench/scripts/probe_block_quant_error.py --selftest   # CPU+torch, no GPU/vllm
#
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

for _r in (Path("/workspace/symbolu/CTM_plus"), Path(__file__).resolve().parent.parent):
    if (_r / "KVPolicy").is_dir() and str(_r / "KVPolicy") not in sys.path:
        sys.path.insert(0, str(_r / "KVPolicy"))
        break

GROUP = 32            # block-local group size (== kernel block_size)
BITS = 4
PCT_SWEEP = (0.01, 0.02, 0.03, 0.04, 0.06, 0.08)
THRESH_QUANTILES = (0.50, 0.75, 0.90, 0.95, 0.99, 0.999)


# ---------------------------------------------------------------------------
# Quant policies (all reuse the validated reference quantizer)
# ---------------------------------------------------------------------------
def _quant_err(x, bits, group=GROUP):
    """|x - dequant(quant(x))| with the exact validated math. x: (S,H,D)."""
    import torch
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4)
    q, scale, off = quantize_per_channel_int4(
        x, group_size=group, asymmetric=True, bits=bits)
    dq = dequantize_per_channel_int4(q, scale, offset=off, group_size=group,
                                     dtype=torch.float32)
    return (x.to(torch.float32) - dq).abs()


def policy_errors(k, mask):
    """k: (S,H,D) float; mask: (H,D) bool (protected=True).
    Returns dict of policy -> per-element |err| (S,H,D)."""
    import torch
    S = (k.shape[0] // GROUP) * GROUP
    k = k[:S].to(torch.float32)
    err4 = _quant_err(k, bits=BITS)
    out = {"noprot": err4}
    if mask is not None:
        m = mask.to(k.device)
        cur = err4.clone()
        cur[:, m] = 0.0                                   # bf16 protect = exact
        out["cur_bf16"] = cur
        if m.any():
            err8 = _quant_err(k, bits=8)                  # int8, same groups
            p8 = err4.clone()
            p8[:, m] = err8[:, m]                         # protected -> int8 err
            out["prot_int8"] = p8
    return out


def fresh_mask(stat, pct):
    """Top-pct channels per head by `stat` (H,D) -> bool mask (H,D)."""
    import torch
    H, D = stat.shape
    n = max(1, round(D * pct))
    idx = stat.topk(n, dim=-1).indices
    m = torch.zeros(H, D, dtype=torch.bool, device=stat.device)
    m.scatter_(1, idx, True)
    return m


def _p99(t):
    """p99 that survives torch.quantile's ~2^24-element input limit by
    strided subsampling (error fields are ~stationary across positions)."""
    f = t.flatten()
    if f.numel() > 8_000_000:
        f = f[:: (f.numel() // 8_000_000) + 1]
    return float(f.quantile(0.99))


def block_max_err(err):
    """(S,H,D) -> per (block, head) max err: (S//GROUP, H)."""
    S = (err.shape[0] // GROUP) * GROUP
    return err[:S].view(-1, GROUP, *err.shape[1:]).amax(dim=1).amax(dim=-1)


def tag_cdf(block_err_flat, thresholds):
    """% of blocks whose max err exceeds each threshold (monotone non-inc)."""
    out = []
    n = max(1, block_err_flat.numel())
    for t in thresholds:
        out.append(float((block_err_flat > t).sum()) / n)
    return out


# ---------------------------------------------------------------------------
# GPU capture
# ---------------------------------------------------------------------------
def _corpus(tok, sizes):
    bases = [
        "The quarterly logistics review noted that warehouse seven shipped on "
        "schedule while the northern depot lagged by two days. ",
        "def quantize(x, scale, zero):\n    q = round(x / scale) + zero\n    "
        "return clamp(q, 0, 15)\n# per-channel affine quantization helper\n",
        "Operations log: subsystem nominal, telemetry within bounds, no "
        "anomalies recorded during the interval under review. ",
        "In the matter of the estate, the court finds that the testator's "
        "intent, as evidenced by the holographic codicil, controls. ",
    ]
    prompts = []
    for i, n in enumerate(sizes):
        base = bases[i % len(bases)]
        ids = tok(base * (n // 12 + 4))["input_ids"][:n]
        prompts.append(tok.decode(ids))
    return prompts


def run_gpu(args):
    import torch
    from vllm import LLM, SamplingParams

    mask_path = os.environ.get("PROTECT_MASK_PATH", "")
    art_mask = None
    if mask_path and Path(mask_path).exists():
        art = torch.load(mask_path, map_location="cpu", weights_only=False)
        t = art["mask"] if isinstance(art, dict) and "mask" in art else art
        art_mask = t.to(torch.bool)                      # (L, H, D)
        print(f"[qerr] artifact mask loaded: {tuple(art_mask.shape)} from {mask_path}")
    else:
        print("[qerr] WARNING: no PROTECT_MASK_PATH artifact — 'cur_bf16'/'prot_int8' "
              "policies will use the FRESH 4% max-abs mask instead (labeled in summary).")

    llm = LLM(model=args.model, max_model_len=args.mml,
              gpu_memory_utilization=args.gpu_util, enforce_eager=True,
              enable_chunked_prefill=False, max_num_seqs=2)
    tok = llm.get_tokenizer()

    # locate per-layer attention modules (name: model.layers.N.self_attn.attn)
    inner = llm.llm_engine.model_executor.driver_worker.model_runner.model
    attns = {}
    for name, mod in inner.named_modules():
        if name.endswith(".self_attn.attn"):
            try:
                attns[int(name.split(".layers.")[1].split(".")[0])] = mod
            except (IndexError, ValueError):
                pass
    L = len(attns)
    print(f"[qerr] hooked {L} attention layers")

    cap_k = {i: [] for i in attns}      # CPU fp16 (T,H,D)
    cap_v = {i: [] for i in attns}
    cap_q = {i: [] for i in attns}      # sampled rows (R,HQ,DQ)
    g = torch.Generator().manual_seed(7)

    def mk_hook(idx):
        def hook(_mod, hin):
            q, k, v = hin[0], hin[1], hin[2]
            if k.shape[0] <= 1:          # decode step — prefill only
                return
            T = k.shape[0]
            cap_k[idx].append(k.detach().view(T, -1, 128).to("cpu", torch.float16))
            cap_v[idx].append(v.detach().view(T, -1, 128).to("cpu", torch.float16))
            r = torch.randperm(T, generator=g)[:args.q_rows]
            cap_q[idx].append(q.detach()[r.to(q.device)]
                              .view(len(r), -1, 128).to("cpu", torch.float16))
        return hook

    handles = [m.register_forward_pre_hook(mk_hook(i)) for i, m in attns.items()]
    sizes = [int(s) for s in args.prompt_sizes.split(",")]
    prompts = _corpus(tok, sizes)
    sp = SamplingParams(temperature=0.0, max_tokens=1)
    for p in prompts:
        llm.generate([p], sp, use_tqdm=False)
    for h in handles:
        h.remove()
    n_tok = sum(t.shape[0] for t in cap_k[min(cap_k)])
    print(f"[qerr] captured {n_tok} tokens x {L} layers (K,V,q-sample)")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    outdir = Path(args.out_dir); outdir.mkdir(parents=True, exist_ok=True)
    summary = {"model": args.model, "tokens": n_tok, "layers": L,
               "group": GROUP, "bits": BITS, "prompt_sizes": sizes,
               "mask_path": mask_path or None,
               "corpus_sha": hashlib.sha1(("".join(prompts)).encode()).hexdigest()[:12],
               "per_layer": {}, "global": {}}
    blocks_cur, blocks_nop, chan_rows = [], [], []
    glob = {}

    for li in sorted(cap_k):
        k = torch.cat(cap_k[li]).to(dev, torch.float32)   # (S,H,D)
        v = torch.cat(cap_v[li]).to(dev, torch.float32)
        qs = torch.cat(cap_q[li]).to(dev, torch.float32)  # (R,HQ,D)
        cap_k[li] = cap_v[li] = cap_q[li] = None
        S, H, D = k.shape
        HQ = qs.shape[1]
        gqa = HQ // H

        chan_max = k.abs().amax(dim=0)                    # (H,D)
        # sensitivity = E|q_d| (q-heads mapped onto kv head) x unprot chan err
        qmean = qs.abs().mean(dim=0).view(H, gqa, D).mean(dim=1)   # (H,D)

        amask = art_mask[li].to(dev) if art_mask is not None else fresh_mask(chan_max, 0.04)
        errs = policy_errors(k, amask)
        chan_err_nop = errs["noprot"].mean(dim=0)         # (H,D)
        smask = fresh_mask(qmean * chan_err_nop, 0.04)

        row = {}
        kstd = float(k.std())
        for nm, e in errs.items():
            row[nm] = {"mean": float(e.mean()), "p99": _p99(e),
                       "max": float(e.max()), "mean_over_kstd": float(e.mean()) / kstd}
        # mask-size sweep + sensitivity mask (bf16-protect variants of noprot)
        for pct in PCT_SWEEP:
            m = fresh_mask(chan_max, pct)
            e = errs["noprot"].clone(); e[:, m] = 0.0
            row[f"fresh{int(pct*100)}pct"] = {"mean": float(e.mean())}
        e = errs["noprot"].clone(); e[:, smask] = 0.0
        row["sens4pct"] = {"mean": float(e.mean()),
                           "overlap_with_artifact": float((smask & amask).sum())
                           / max(1, int(amask.sum()))}
        # V (same validated math, labeled: K-style per-channel groups)
        row["v_int4"] = {"mean": float(_quant_err(v[: (S // GROUP) * GROUP], BITS).mean())}

        # score-space SNR (GQA-mapped): noise = q·(dq(k)-k), signed delta
        # under the CURRENT policy (int4 groups, protected channels exact).
        kq = k[: (S // GROUP) * GROUP]
        from kv_policy.int4_per_channel_kv import (
            quantize_per_channel_int4, dequantize_per_channel_int4)
        qq, sc, of = quantize_per_channel_int4(kq, group_size=GROUP,
                                               asymmetric=True, bits=BITS)
        dq = dequantize_per_channel_int4(qq, sc, offset=of, group_size=GROUP,
                                         dtype=torch.float32)
        dq[:, amask] = kq[:, amask]                       # protect exact
        delta = (dq - kq)                                 # (S,H,D) signed
        tsub = torch.randperm(kq.shape[0], generator=g)[: min(2048, kq.shape[0])]
        kk, dd = kq[tsub.to(dev)], delta[tsub.to(dev)]
        qg = qs.view(-1, H, gqa, D)
        strue = torch.einsum("rhgd,thd->rhgt", qg, kk)
        snoise = torch.einsum("rhgd,thd->rhgt", qg, dd)
        row["score"] = {"std_true": float(strue.std()), "std_noise": float(snoise.std()),
                        "snr": float(strue.std() / max(1e-9, snoise.std())),
                        "p99_noise_over_std_true":
                        _p99(snoise.abs()) / float(strue.std())}

        be_cur = block_max_err(errs["cur_bf16"])          # (B,H)
        be_nop = block_max_err(errs["noprot"])
        blocks_cur.append(be_cur.to("cpu", torch.float16))
        blocks_nop.append(be_nop.to("cpu", torch.float16))
        chan_rows.append(torch.stack([chan_max, qmean, chan_err_nop,
                                      amask.float(), smask.float()]).to("cpu", torch.float16))
        summary["per_layer"][str(li)] = row
        for nm in ("noprot", "cur_bf16", "prot_int8"):
            if nm in row:
                glob.setdefault(nm, []).append(row[nm]["mean"])
        del k, v, qs, errs, delta
        if dev == "cuda":
            torch.cuda.empty_cache()
        print(f"[qerr] layer {li:2d}: cur={row['cur_bf16']['mean']:.5f} "
              f"noprot={row['noprot']['mean']:.5f} int8prot={row['prot_int8']['mean']:.5f} "
              f"snr={row['score']['snr']:.0f}", flush=True)

    # ---- dynamic-protect CDF over ALL blocks (current policy) ----
    import numpy as np
    bc = torch.cat([b.flatten() for b in blocks_cur]).to(torch.float32)
    bn = torch.cat([b.flatten() for b in blocks_nop]).to(torch.float32)
    th = [float(bc.quantile(q)) for q in THRESH_QUANTILES]
    cdf = tag_cdf(bc, th)
    # int8-fallback K cost per tagged block per layer: +16 KiB (32tok x 8h x 128d)
    blocks_100k = 100_000 // GROUP
    cost_gib = [frac * blocks_100k * summary["layers"] * 16 * 1024 / 2**30 for frac in cdf]
    summary["global"] = {
        "policy_mean_err": {nm: sum(v) / len(v) for nm, v in glob.items()},
        "dynamic_tag": {"thresholds_abs": th,
                        "quantiles": list(THRESH_QUANTILES),
                        "frac_blocks_tagged": cdf,
                        "int8_fallback_gib_per_100k_session": cost_gib},
        "block_err_cur": {"p50": float(bc.quantile(.5)), "p99": float(bc.quantile(.99)),
                          "max": float(bc.max())},
        "block_err_noprot": {"p50": float(bn.quantile(.5)), "p99": float(bn.quantile(.99)),
                             "max": float(bn.max())},
    }
    np.savez_compressed(outdir / "blocks.npz",
                        cur=torch.stack(blocks_cur).numpy(),
                        noprot=torch.stack(blocks_nop).numpy())
    np.savez_compressed(outdir / "channels.npz",
                        rows=torch.stack(chan_rows).numpy(),
                        fields=np.array(["chan_max", "q_sens", "chan_err_noprot",
                                         "artifact_mask", "sens_mask"]))
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    _print_report(summary)
    print(f"[qerr] artifacts: {outdir}/summary.json, blocks.npz, channels.npz")
    return 0


def _print_report(s):
    g = s["global"]; pm = g["policy_mean_err"]
    print("\n" + "=" * 90)
    print(f"BLOCK QUANT ERROR — {s['model'].split('/')[-1]}  "
          f"({s['tokens']} tokens, {s['layers']} layers, group={s['group']})")
    print("=" * 90)
    base = pm.get("noprot", 1e-9)
    for nm in ("noprot", "cur_bf16", "prot_int8"):
        if nm in pm:
            print(f"  {nm:<10} mean|err| = {pm[nm]:.5f}   "
                  f"({pm[nm]/base*100:5.1f}% of no-protect)")
    dt = g["dynamic_tag"]
    print("-" * 90)
    print("  dynamic-protect CDF (block max-err under CURRENT policy):")
    print(f"  {'quantile':>9} {'threshold':>11} {'%blocks>T':>10} {'int8-fallback GiB/100K':>24}")
    for q, t, f, c in zip(dt["quantiles"], dt["thresholds_abs"],
                          dt["frac_blocks_tagged"], dt["int8_fallback_gib_per_100k_session"]):
        print(f"  {q:>9} {t:>11.5f} {f*100:>9.2f}% {c:>22.3f}")
    print("=" * 90)


# ---------------------------------------------------------------------------
# Selftest (CPU + torch; no vllm / GPU)
# ---------------------------------------------------------------------------
def _selftest():
    import torch
    fails = []

    def check(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}")
        if not c:
            fails.append(n)

    torch.manual_seed(0)
    S, H, D = 128, 2, 32
    k = torch.randn(S, H, D)
    k[:, :, 3] *= 25.0           # planted outlier channel
    k[:, :, 17] *= 18.0
    mask = torch.zeros(H, D, dtype=torch.bool); mask[:, [3, 17]] = True

    errs = policy_errors(k, mask)
    check("protect reduces error vs no-protect",
          errs["cur_bf16"].mean() < errs["noprot"].mean() * 0.8)
    check("int8-protect within 5% of bf16-protect mean err",
          errs["prot_int8"].mean() <= errs["cur_bf16"].mean() * 1.05
          + 0.02 * errs["noprot"].mean())
    means = []
    chan_max = k.abs().amax(dim=0)
    for pct in PCT_SWEEP:
        m = fresh_mask(chan_max, pct)
        e = errs["noprot"].clone(); e[:, m] = 0.0
        means.append(float(e.mean()))
    check("mask sweep monotone non-increasing",
          all(a >= b - 1e-9 for a, b in zip(means, means[1:])))
    be = block_max_err(errs["cur_bf16"]).flatten()
    cdf = tag_cdf(be, [float(be.quantile(q)) for q in (0.5, 0.9, 0.99)])
    check("tag CDF monotone non-increasing",
          all(a >= b - 1e-12 for a, b in zip(cdf, cdf[1:])))
    err = _quant_err(k, bits=BITS)
    blk = k[: (S // GROUP) * GROUP].view(-1, GROUP, H, D)
    rng = (blk.amax(1) - blk.amin(1)) / 15.0
    per_blk_max = err.view(-1, GROUP, H, D).amax(1)
    check("roundtrip err bounded by ~scale/2 per group",
          bool((per_blk_max <= rng * 0.5 + 1e-4).all()))
    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="per-block quant-error diagnostics "
                                 "(dynamic-protect decision data)")
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--prompt-sizes", default="2048,4096,4096,8192,8192",
                    help="token sizes of the capture corpus")
    ap.add_argument("--mml", type=int, default=12288)
    ap.add_argument("--gpu-util", type=float, default=0.45)
    ap.add_argument("--q-rows", type=int, default=32,
                    help="sampled q rows per layer per prompt (score SNR)")
    ap.add_argument("--out-dir", default="/tmp/qerr")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    return run_gpu(args)


if __name__ == "__main__":
    raise SystemExit(main())
