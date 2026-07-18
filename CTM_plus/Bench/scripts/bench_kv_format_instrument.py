#!/usr/bin/env python3
# Step 2/3 instrumentation for the QUALIFIED KV-format harness (bench_kv_format_quality.py).
#
# Runs AFTER Step 1 qualified the harness (int4_protected reproduces production HOLDS @ ~4% on
# Qwen2.5-7B). Two jobs, both on the REAL model path (not synthetic):
#
#   STEP 2 — instrument the real-model path + real-KV invariants:
#     * eval-level: mean CE, token-loss p50/p95/p99/max, NaN/Inf, PPL (cross-checks the qualified run)
#     * per-layer: K/V reconstruction MSE, protect-mask cardinality, NVFP4 e4m3 block-scale underflow rate
#     * invariants on REAL captured Qwen KV (not CPU synthetic): 0%protect==plain, 100%protect==bf16,
#       protected channel == bf16 source EXACTLY (protection REPLACES, never adds)
#
#   STEP 3 — investigate the 2% anomaly (NVFP4-protected @ 2% PPL >> plain NVFP4) WITHOUT calling it noise:
#     * freeze tokens + mask, run plain-NVFP4 and protected-NVFP4 through the SAME forward
#     * per-layer K reconstruction MSE for each; find the FIRST layer where protected diverges MORE
#       than plain; report whether the NVFP4 e4m3 underflow rate spikes there (mechanism test:
#       partial protection collapses de-outliered blocks' scale under a still-large per-tensor g_scale)
#
# It imports the quant primitives from the qualified harness, so the quantization math is identical by
# construction — the instrument only OBSERVES; it never re-implements the format.
#
#   python CTM_plus/Bench/scripts/bench_kv_format_instrument.py --model Qwen/Qwen2.5-7B-Instruct --protect-frac 0.02
from __future__ import annotations
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_kv_format_quality as H   # the QUALIFIED harness: single source of truth for the formats


def _pct(sorted_vals, q):
    """q-th percentile (q in [0,1]) of an already-sorted 1-D python list."""
    if not sorted_vals:
        return float("nan")
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return float(sorted_vals[i])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Step 2/3 instrumentation for the qualified KV-format harness")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--formats", default="bf16,fp8,int4_protected,nvfp4,nvfp4_protected")
    ap.add_argument("--context", type=int, default=4096)
    ap.add_argument("--ppl-start-frac", type=float, default=0.5)
    ap.add_argument("--protect-frac", type=float, default=0.02)   # default = the ANOMALY point
    ap.add_argument("--text-file", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    import torch
    import torch.nn.functional as F
    H.ensure_torchaudio_importable()
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model)
    if args.text_file:
        text = open(args.text_file).read()
    else:
        try:
            from datasets import load_dataset
            ds = load_dataset("wikitext", "wikitext-2-raw-v1", split="test")
            text = "\n\n".join(t for t in ds["text"] if t.strip())
        except Exception as e:
            print(f"  WARNING: wikitext load failed ({type(e).__name__}: {e}); using built-in prose.")
            text = H._PROSE
    ids = tok(text)["input_ids"][:args.context]
    input_ids = torch.tensor([ids], device="cuda")
    start = max(1, int(args.ppl_start_frac * input_ids.shape[1]))
    pf = args.protect_frac

    print(f"\n== KV-format INSTRUMENT — {args.model.split('/')[-1]} ctx={input_ids.shape[1]} "
          f"tail>={args.ppl_start_frac:.0%} protect={pf:.0%} ==")
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa", device_map="cuda").eval()

    # --- instrumented sdpa: quantize K/V exactly as the qualified harness, but also RECORD per-layer
    #     diagnostics. `rec` is reset per forward; one sdpa call == one decoder layer. ---
    rec = {"fmt": "bf16", "layer": 0, "per_layer": [], "cap_layer0_K": None}
    _orig_sdpa = F.scaled_dot_product_attention

    def _patched(query, key, value, *a, **k):
        li = rec["layer"]; rec["layer"] += 1
        fmt = rec["fmt"]
        if fmt == "bf16":
            if li == 0 and rec["cap_layer0_K"] is None:
                rec["cap_layer0_K"] = key.detach().clone()       # capture REAL KV for invariants
            return _orig_sdpa(query, key, value, *a, **k)
        # quantize via the qualified harness primitives (identical numerics)
        kq = H.quant_dequant(key, fmt, pf, is_key=True)
        vq = H.quant_dequant(value, fmt, pf, is_key=False)
        # per-layer diagnostics (observation only)
        k_mse = (kq.float() - key.float()).pow(2).mean().item()
        v_mse = (vq.float() - value.float()).pow(2).mean().item()
        d = {"layer": li, "k_mse": k_mse, "v_mse": v_mse,
             "k_nan": bool(torch.isnan(kq).any() or torch.isinf(kq).any()),
             "v_nan": bool(torch.isnan(vq).any() or torch.isinf(vq).any())}
        # attention-OUTPUT perturbation vs bf16 (the thing that actually propagates to PPL). Distinguishes
        # "reconstruction error" (k_mse) from "downstream distortion": a format can reconstruct K better
        # (lower k_mse) yet perturb the attention output MORE (the exact/coarse channel mix bends softmax).
        out_q = _orig_sdpa(query, kq, vq, *a, **k)
        out_ref = _orig_sdpa(query, key, value, *a, **k)
        d["attn_out_mse"] = float((out_q.float() - out_ref.float()).pow(2).mean().item())
        # mask cardinality (mean protected channels per head) for protected formats
        if fmt in ("int4_protected", "nvfp4_protected"):
            m = H._protect_mask(key, pf)
            d["mask_card"] = float(m.float().sum().item() / max(1, m.shape[-2] if m.dim() >= 3 else 1))
            # protection REPLACES not adds: protected positions must equal bf16 source exactly
            d["protect_exact"] = bool(torch.equal(kq[m.expand_as(kq)], key[m.expand_as(key)]))
        # NVFP4 e4m3 underflow rate on the K path (secondary probe)
        if fmt in ("nvfp4", "nvfp4_protected"):
            diag = {}
            if fmt == "nvfp4":
                H._nvfp4_qdq(key, diag=diag)
            else:                                                # protected: measure on the CLEANED tensor
                mask = H._protect_mask(key, pf)
                H._nvfp4_qdq(torch.where(mask, torch.zeros_like(key), key), diag=diag)
            d.update({kk: diag[kk] for kk in diag})
        # PRIMARY Step-3 probe (nvfp4_protected only): the global-scale COUPLING test — does protecting
        # some channels raise the recon error of the UNPROTECTED ones vs plain NVFP4 on the same tensor?
        # int4-per-channel has no such coupling (channels are independent); NVFP4's per-tensor g_scale does.
        if fmt == "nvfp4_protected":
            kq_plain = H._nvfp4_qdq(key)
            comp = (~H._protect_mask(key, pf).expand_as(key))
            d["k_mse_unprot_prot"] = float((kq.float() - key.float()).pow(2)[comp].mean().item())
            d["k_mse_unprot_plain"] = float((kq_plain.float() - key.float()).pow(2)[comp].mean().item())
            d["coupling_delta"] = d["k_mse_unprot_prot"] - d["k_mse_unprot_plain"]
        rec["per_layer"].append(d)
        return out_q                                             # reuse the already-computed quantized output

    F.scaled_dot_product_attention = _patched

    def run_format(fmt):
        """One forward; returns eval metrics + captured per-layer diagnostics."""
        rec["fmt"] = fmt; rec["layer"] = 0; rec["per_layer"] = []
        with torch.no_grad():
            logits = model(input_ids).logits[0].float()          # [S, V]
        shift_logits = logits[:-1]; shift_labels = input_ids[0, 1:]
        ce = F.cross_entropy(shift_logits, shift_labels, reduction="none")   # [S-1]
        tail = ce[start - 1:]
        nan = bool(torch.isnan(ce).any() or torch.isinf(ce).any())
        vals = sorted(tail.tolist())
        mean_ce = float(tail.mean().item())
        return {
            "fmt": fmt, "ppl": math.exp(mean_ce), "mean_ce": mean_ce, "nan_inf": nan,
            "tok_p50": _pct(vals, 0.50), "tok_p95": _pct(vals, 0.95),
            "tok_p99": _pct(vals, 0.99), "tok_max": _pct(vals, 1.0),
            "per_layer": [dict(x) for x in rec["per_layer"]],
        }

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    results = {}
    for fmt in formats:
        results[fmt] = run_format(fmt)
        r = results[fmt]
        print(f"  {fmt:<16} PPL {r['ppl']:9.4f}  meanCE {r['mean_ce']:7.4f}  "
              f"tok[p50 {r['tok_p50']:.3f} p95 {r['tok_p95']:.3f} p99 {r['tok_p99']:.3f} "
              f"max {r['tok_max']:.3f}]  NaN/Inf={r['nan_inf']}")

    # === STEP 2: real-KV invariants on captured layer-0 K (REAL Qwen KV, not synthetic) ===
    print("\n-- STEP 2: real-KV invariants (captured layer-0 Qwen K) --")
    K0 = rec["cap_layer0_K"]
    inv = {}
    if K0 is not None:
        inv["0pct==plain_int4"] = bool(torch.equal(H.quant_dequant(K0, "int4_protected", 0.0, is_key=True),
                                                   H._int4_k_prod(K0)))
        inv["0pct==plain_nvfp4"] = bool(torch.equal(H.quant_dequant(K0, "nvfp4_protected", 0.0, is_key=True),
                                                    H._nvfp4_qdq(K0)))
        inv["100pct==bf16_int4"] = bool(torch.equal(H.quant_dequant(K0, "int4_protected", 1.0, is_key=True), K0))
        inv["100pct==bf16_nvfp4"] = bool(torch.equal(H.quant_dequant(K0, "nvfp4_protected", 1.0, is_key=True), K0))
        mk = H._protect_mask(K0, pf)
        kpi = H.quant_dequant(K0, "int4_protected", pf, is_key=True)
        kpn = H.quant_dequant(K0, "nvfp4_protected", pf, is_key=True)
        inv["protect_replaces_int4"] = bool(torch.equal(kpi[mk.expand_as(kpi)], K0[mk.expand_as(K0)]))
        inv["protect_replaces_nvfp4"] = bool(torch.equal(kpn[mk.expand_as(kpn)], K0[mk.expand_as(K0)]))
        for kk, vv in inv.items():
            print(f"  [{'PASS' if vv else 'FAIL'}] {kk}")
    else:
        print("  (no layer-0 K captured — bf16 not in --formats?)")

    # === STEP 3: frozen-token trace — WHY is NVFP4-protected @ pf worse than plain NVFP4? ===
    # Primary probe: COUPLING — recon error of UNPROTECTED channels, protected-run vs plain, same tensor.
    # coupling_delta > 0 means protecting some channels HURT the others (per-tensor g_scale coupling) —
    # the concrete integration mechanism, measured on real Qwen KV. Secondary: overall K-MSE, underflow.
    print(f"\n-- STEP 3: per-layer trace, plain NVFP4 vs protected NVFP4 @ {pf:.0%} (same tokens) --")
    step3 = {"first_coupling_layer": None, "layers": []}
    if "nvfp4" in results and "nvfp4_protected" in results:
        pl_plain = {d["layer"]: d for d in results["nvfp4"]["per_layer"]}
        pl_prot = {d["layer"]: d for d in results["nvfp4_protected"]["per_layer"]}
        print(f"  {'layer':>5} {'unprot_pl':>11} {'unprot_pr':>11} {'couple_Δ':>11} "
              f"{'attnMSE_pl':>11} {'attnMSE_pr':>11} {'attnΔ':>11}  worse?")
        first = None
        for li in sorted(pl_plain):
            a = pl_plain[li]; b = pl_prot.get(li, {})
            up_pl = b.get("k_mse_unprot_plain", float("nan"))
            up_pr = b.get("k_mse_unprot_prot", float("nan"))
            cdel = b.get("coupling_delta", float("nan"))
            ao_pl = a.get("attn_out_mse", float("nan"))          # plain NVFP4 attention-output perturbation
            ao_pr = b.get("attn_out_mse", float("nan"))          # protected NVFP4 attention-output perturbation
            adel = ao_pr - ao_pl
            couples = cdel > 0
            attn_worse = adel > 0                                # protected perturbs attention MORE than plain
            if attn_worse and first is None:
                first = li
            print(f"  {li:>5} {up_pl:>11.5g} {up_pr:>11.5g} {cdel:>+11.4g} "
                  f"{ao_pl:>11.5g} {ao_pr:>11.5g} {adel:>+11.4g}  {'<<<' if attn_worse else ''}")
            step3["layers"].append({"layer": li, "unprot_plain": up_pl, "unprot_prot": up_pr,
                                    "coupling_delta": cdel, "attn_mse_plain": ao_pl,
                                    "attn_mse_prot": ao_pr, "attn_delta": adel,
                                    "recon_couples": couples, "attn_worse": attn_worse})
        step3["first_attn_worse_layer"] = first
        n_couple = sum(1 for x in step3["layers"] if x["recon_couples"])
        n_attn = sum(1 for x in step3["layers"] if x["attn_worse"])
        mean_cdel = sum(x["coupling_delta"] for x in step3["layers"]) / max(1, len(step3["layers"]))
        mean_adel = sum(x["attn_delta"] for x in step3["layers"]) / max(1, len(step3["layers"]))
        N = len(step3["layers"])
        print(f"\n  RECON: layers where protecting hurts unprotected channels (coupling_delta>0): {n_couple}/{N}"
              f"   mean coupling_delta {mean_cdel:+.5g}")
        print(f"  DOWNSTREAM: layers where protected perturbs attention MORE than plain: {n_attn}/{N}"
              f"   mean attn_delta {mean_adel:+.5g}   first at layer {first}")
        # Verdict — separate the reconstruction story from the downstream story:
        recon_bad = n_couple >= 0.5 * N and mean_cdel > 0
        attn_bad = n_attn >= 0.5 * N and mean_adel > 0
        if recon_bad and attn_bad:
            concl = ("COUPLING (recon) drives it: partial protection raises unprotected-channel error via "
                     "NVFP4's per-tensor g_scale AND perturbs attention more. int4-per-channel is immune. "
                     "Real format property, not noise. Fix: exclude protected from g_scale / per-block protect.")
        elif attn_bad and not recon_bad:
            concl = ("DOWNSTREAM: protected reconstructs K at least as well (coupling_delta<=0) yet perturbs "
                     "the ATTENTION OUTPUT more than plain — the exact/coarse channel mix bends softmax. The "
                     "PPL anomaly is an attention-distortion effect, not a reconstruction-MSE effect. Real, "
                     "not noise; specific to how NVFP4-protected mixes exact and block-scaled channels.")
        elif recon_bad and not attn_bad:
            concl = "RECON coupling present but attention output not worse on average — read the per-layer table."
        else:
            concl = ("Neither recon-coupling nor mean attention perturbation is worse for protected — the "
                     "anomaly concentrates in a few layers/tokens (see token p99/max and the <<< rows), not a "
                     "uniform effect. NOT noise until those specific rows are explained.")
        print("  " + concl)
        step3["conclusion"] = concl
        step3["recon_bad"] = bool(recon_bad); step3["attn_bad"] = bool(attn_bad)

    F.scaled_dot_product_attention = _orig_sdpa

    # dump artifact
    out = {"model": args.model, "ctx": input_ids.shape[1], "protect_frac": pf,
           "start": start, "results": {f: {k: v for k, v in results[f].items() if k != "per_layer"}
                                        for f in results},
           "per_layer": {f: results[f]["per_layer"] for f in results},
           "invariants": inv, "step3": step3}
    jpath = args.json_out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
        "scripts", "kvpro_kernel_recovery", f"nvfp4_instrument_pf{int(pf*100):02d}.json")
    jpath = os.path.abspath(jpath)
    try:
        with open(jpath, "w") as fh:
            json.dump(out, fh, indent=2)
        print(f"\n  [artifact] wrote {jpath}")
    except Exception as e:
        print(f"\n  [artifact] could not write json ({type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
