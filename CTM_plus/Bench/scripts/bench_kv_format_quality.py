#!/usr/bin/env python3
# KV-format quality eval — does NVFP4 (Blackwell's native 4-bit) hold quality like int4-protected?
#
# STRATEGIC QUESTION (two parts):
#   (a) plain NVFP4 vs int4-protected  -> if NVFP4 alone matches, Blackwell COMMODITIZES the moat.
#   (b) NVFP4-protected vs int4-protected -> if only *protected* NVFP4 matches, the protection IP
#       TRANSFERS into the FP4 era (KVPro = the quality layer on whatever 4-bit the hardware blesses).
#
# KEY INSIGHT: quality is set by the QUANTIZATION, not the hardware. Blackwell's FP4 tensor cores just do
# the same math faster, so we can measure NVFP4 *quality* by EMULATING the format numerically on any GPU
# (A100 here). Only the SPEED (1.00x) needs Blackwell. So this prices the commoditization risk BEFORE any
# hardware bet.
#
# METHOD: monkeypatch torch's scaled_dot_product_attention to quantize->dequantize K and V (post-RoPE,
# exactly the tensors attention consumes = the KV-cache contents) with the chosen format, then measure
# teacher-forced perplexity over fixed text. Compare formats on the DISCRIMINATING model (Qwen2.5-7B,
# where fp8 collapsed and int4-protected held) plus a clean one.
#
#   python CTM_plus/Bench/scripts/bench_kv_format_quality.py --model Qwen/Qwen2.5-7B-Instruct
#   python CTM_plus/Bench/scripts/bench_kv_format_quality.py --model Qwen/Qwen3-8B          # needs newer venv
#   python CTM_plus/Bench/scripts/bench_kv_format_quality.py --selftest                     # CPU, quant math
#
# HONEST caveats: (1) emulation matches Blackwell's *result*, not its speed. (2) protection here selects
# outlier channels by max-abs (a proxy); the real product calibrates importance, so real int4-protected
# may do slightly better. (3) scale/xmin stored at fp32 here (the sim isolates the 4-bit+protection
# quality effect, not the sidecar-precision tax). (4) both K and V are protected uniformly.
from __future__ import annotations
import argparse, math, os, sys

PPL_GATE = 0.01   # FROZEN: a format "holds" if its PPL is within 1% of bf16 (same gate as the fp8 eval)

# E2M1 (FP4) positive grid — the 8 representable magnitudes of 1-sign/2-exp/1-mantissa float4.
_E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
_E2M1_MAX = 6.0
_E4M3_MAX = 448.0


def _round_e2m1(x):
    """Round a tensor to the nearest E2M1 (FP4) value, preserving sign. Pure; works on CPU/GPU."""
    import torch
    grid = x.new_tensor(_E2M1)
    sign = x.sign()
    mag = x.abs().clamp(max=_E2M1_MAX)
    idx = (mag.unsqueeze(-1) - grid).abs().argmin(dim=-1)   # nearest grid magnitude
    return sign * grid[idx]


def _round_e4m3(x):
    """Round to fp8 e4m3 via the native torch dtype (saturating)."""
    import torch
    return x.to(torch.float8_e4m3fn).to(x.dtype)


def _fp8_qdq(x):
    """Per-tensor-amax fp8-e4m3 (the *fair* fp8 — a proper scale, unlike vLLM's default scale=1.0)."""
    scale = (x.abs().amax() / _E4M3_MAX).clamp(min=1e-8)
    return _round_e4m3(x / scale) * scale


def _nvfp4_qdq(x, block=16):
    """NVFP4: E2M1 elements, per-`block` e4m3 scale, per-tensor fp32 global scale (two-level)."""
    import torch
    D = x.shape[-1]
    if D % block:
        return _fp8_qdq(x)   # safety: non-divisible head_dim -> skip (shouldn't happen; hd=128)
    g_amax = x.abs().amax().clamp(min=1e-8)
    g_scale = g_amax / (_E2M1_MAX * _E4M3_MAX)                     # per-tensor fp32 scale
    xb = x.reshape(*x.shape[:-1], D // block, block)
    b_amax = xb.abs().amax(dim=-1, keepdim=True).clamp(min=1e-8)
    b_scale = (b_amax / _E2M1_MAX)                                 # fp32 per-block scale (map amax->6.0)
    b_scale = (_round_e4m3(b_scale / g_scale) * g_scale).clamp(min=1e-8)   # store block scale in e4m3
    xq = _round_e2m1(xb / b_scale) * b_scale
    return xq.reshape_as(x)


def _protect_mask(x, protect_frac):
    """Boolean [D] mask of the top-`protect_frac` channels (by max-abs) — the outlier channels."""
    import torch
    D = x.shape[-1]
    imp = x.reshape(-1, D).abs().amax(dim=0)                       # per-channel importance
    k = max(1, int(round(protect_frac * D)))
    m = torch.zeros(D, dtype=torch.bool, device=x.device)
    m[torch.topk(imp, k).indices] = True
    return m


def _int4_affine_qdq(x, group=32):
    """Affine (asymmetric) int4 per group along the last dim."""
    import torch
    D = x.shape[-1]
    g = group if D % group == 0 else D
    xg = x.reshape(*x.shape[:-1], D // g, g)
    xmin = xg.amin(dim=-1, keepdim=True)
    scale = ((xg.amax(dim=-1, keepdim=True) - xmin) / 15.0).clamp(min=1e-8)
    xq = torch.round((xg - xmin) / scale).clamp(0, 15)
    return (xq * scale + xmin).reshape_as(x)


def _protected(x, base_qdq, protect_frac):
    """Protect the top-`protect_frac` outlier channels at bf16, EXCLUDING them from the base quantizer's
    scale computation. This is the whole point of protection: an outlier must NOT inflate its group/block
    scale and wreck its neighbors. (Leaving it in — the naive version — makes protection near-useless.)"""
    mask = _protect_mask(x, protect_frac)              # [D]
    x_clean = x.clone()
    x_clean[..., mask] = 0.0                            # remove outliers before computing scales
    out = base_qdq(x_clean)
    out[..., mask] = x[..., mask]                       # restore outliers at full (bf16) precision
    return out


def quant_dequant(x, fmt, protect_frac=0.04):
    """Emulate storing `x` (a K or V tensor, [..., head_dim]) in `fmt` and reading it back."""
    if fmt == "bf16":
        return x
    if fmt == "fp8":
        return _fp8_qdq(x)
    if fmt == "int4_protected":
        return _protected(x, _int4_affine_qdq, protect_frac)
    if fmt == "nvfp4":
        return _nvfp4_qdq(x)
    if fmt == "nvfp4_protected":
        return _protected(x, _nvfp4_qdq, protect_frac)
    raise ValueError(f"unknown format {fmt!r}")


def verdict(rows):
    """rows[fmt] = ppl. Return (notes, strategic_conclusion)."""
    notes, base = [], rows.get("bf16")
    if not base or math.isinf(base):
        return ["no bf16 baseline"], "INVALID"
    d = {}
    for fmt, ppl in rows.items():
        if fmt == "bf16":
            notes.append(f"bf16           PPL {ppl:8.4f}  (baseline, gate = within {PPL_GATE*100:.0f}%)"); continue
        dd = (ppl - base) / base
        d[fmt] = dd
        tag = "HOLDS" if dd <= PPL_GATE else "DEGRADED"
        notes.append(f"{fmt:<14} PPL {ppl:8.4f}  = {dd*100:+7.2f}% vs bf16  [{tag}]")
    i4 = d.get("int4_protected"); n4 = d.get("nvfp4"); n4p = d.get("nvfp4_protected")
    holds = lambda v: v is not None and v <= PPL_GATE
    if holds(n4) and holds(i4):
        c = ("NVFP4 (plain) matches int4-protected -> on this model Blackwell COMMODITIZES the 4-bit tier: "
             "per-block scales alone hold quality, protection unneeded. Moat shifts to governance.")
    elif holds(n4p) and not holds(n4):
        c = ("Plain NVFP4 fails but NVFP4-PROTECTED holds -> the protection IP TRANSFERS to FP4. KVPro = "
             "the quality layer on top of NVFP4 (protection still required on outlier models). Moat survives.")
    elif holds(i4) and not holds(n4p):
        c = ("int4-protected holds but NVFP4-protected does not -> the int4 FORMAT retains a quality edge "
             "(but is slow without Blackwell). Re-examine protection params on NVFP4 before concluding.")
    elif not holds(i4):
        c = ("int4-protected itself does not hold on this model/config -> check protect-frac / this isn't a "
             "discriminating case. Use an outlier-heavy model (Qwen2.5).")
    else:
        c = "Mixed — read the per-format deltas above; not a clean commoditize/transfer signal."
    return notes, c


_PROSE = (
    "The harbor town woke slowly under a grey sky as gulls argued over the night's leftovers. Negotiators "
    "returned to the table after a three-day recess, each side claiming the other had moved first. A "
    "biologist studying the reef found coral recovering in the cooler patches, a small sign of resilience. "
    "Markets opened higher on easing inflation, though analysts warned a single quarter proves little. The "
    "old library reopened with a new wing for local archives. Early snow stranded hikers later guided down "
    "by thermal cameras. A software team chose reliability over new features, a decision its engineers had "
    "urged for years. The orchestra rehearsed a rarely heard symphony, the conductor coaxing a warmer tone "
    "from the strings. Farmers debated planting early, weighing frost against a longer season. A historian "
    "found letters showing the treaty nearly collapsed over river rights. A clinic's screening program "
    "caught several cases early, when treatment is simplest. A cartographer found an island gone from the "
    "survey, reclaimed by rising tides. Engineers load-tested the bridge with trucks of water barrels. A "
    "curator catalogued photographs no one alive could name. The comet drew crowds to rooftops who never "
    "looked up. A teacher taught forty children across six grades in one room. Divers found the wreck's "
    "timbers preserved by the cold. A court ruled the old right to gather seaweed could not be sold. The "
    "pianist chased a phrasing she could hear but not yet play. After the drought the river ran the color "
    "of weak tea for a week. A linguist recording the last speakers of a dialect heard them disagree about "
    "the word for dusk. Volunteers replanting the burned hill chose species that would hold the soil first. "
    "The auditor found the error in a rounding rule applied inconsistently for years. A chef known for "
    "excess served five plain dishes, each nearly perfect. Researchers watched birds learn to open sugar "
    "packets, a skill that spread across the city in a summer. "
)


def _selftest():
    import torch
    fails = []
    def ck(n, c):
        print(f"  [{'PASS' if c else 'FAIL'}] {n}"); (fails.append(n) if not c else None)
    # E2M1 grid rounding
    x = torch.tensor([0.0, 0.4, 0.7, 2.4, 5.0, 7.0, -3.1])
    q = _round_e2m1(x)
    ck("e2m1 0.4->0.5", abs(q[1].item() - 0.5) < 1e-6)
    ck("e2m1 2.4->2.0", abs(q[3].item() - 2.0) < 1e-6)
    ck("e2m1 7.0->6.0 (clamp)", abs(q[5].item() - 6.0) < 1e-6)
    ck("e2m1 keeps sign", q[6].item() < 0)
    ck("e2m1 exact grid value", abs(_round_e2m1(torch.tensor([3.0]))[0].item() - 3.0) < 1e-6)
    # e4m3
    ck("e4m3 1.0 exact", abs(_round_e4m3(torch.tensor([1.0]))[0].item() - 1.0) < 1e-6)
    # bf16 identity
    t = torch.randn(4, 128)
    ck("bf16 is identity", torch.equal(quant_dequant(t, "bf16"), t))
    # constant block -> nvfp4 near-exact
    cst = torch.full((2, 32), 1.5)
    ck("nvfp4 exact on grid-constant", (_nvfp4_qdq(cst) - cst).abs().max().item() < 1e-4)
    # NVFP4 per-block scaling works: block-constant grid data across a wide magnitude range -> NVFP4
    # gives each 16-block its own scale (near-exact), while per-tensor fp8 accumulates error on the big
    # blocks. (NB: NVFP4-vs-fp8 on a *single concentrated* outlier channel is DATA-DEPENDENT — a
    # concentrated outlier forces a large block scale that hurts its 15 block-mates, while e4m3's float
    # range handles moderate spreads. That's precisely what the real experiment MEASURES; not assumed.)
    blk = torch.full((8, 16), 2.0) * (4.0 ** torch.arange(8)).unsqueeze(1)     # block b = 2 * 4^b
    zc = blk.reshape(1, 128)
    ck("nvfp4 near-exact on block-constant grid",
       (_nvfp4_qdq(zc) - zc).abs().max().item() < 1e-2 * zc.abs().max().item())
    # correct control = SAME 4-bit budget: NVFP4 (per-block) vs naive per-tensor FP4. (fp8 has 2x the
    # bits, so comparing NVFP4-error to fp8-error is apples-to-oranges — fp8 SHOULD win on quality.)
    def _fp4_pt(t):
        s = (t.abs().amax() / _E2M1_MAX).clamp(min=1e-8); return _round_e2m1(t / s) * s
    ck("nvfp4 << per-tensor-FP4 (block scaling wins at equal 4-bit)",
       (_nvfp4_qdq(zc) - zc).abs().mean().item() < (_fp4_pt(zc) - zc).abs().mean().item())
    # THE KEY INVARIANT (the bug we hit in v1): protection must EXCLUDE outliers from the scale, so an
    # outlier's block-mates survive. channel 0 is a 100x outlier in block 0; protecting it must rescue
    # channels 1..15 — their block scale no longer sees the outlier.
    torch.manual_seed(0)
    zz = torch.randn(16, 16); zz[:, 0] *= 100.0
    mates_plain = (_nvfp4_qdq(zz)[:, 1:] - zz[:, 1:]).abs().mean().item()
    mates_prot = (quant_dequant(zz, "nvfp4_protected", 1 / 16.)[:, 1:] - zz[:, 1:]).abs().mean().item()
    ck("protection rescues an outlier's block-mates (exclusion works)", mates_prot < 0.5 * mates_plain)
    # Protection: keeps outlier channels ~exact and never worsens error.
    z = torch.randn(64, 128); z[:, 7] *= 60.0
    e_n4 = (quant_dequant(z, "nvfp4") - z).abs().mean().item()
    ck("nvfp4_protected <= nvfp4 (protection helps)",
       (quant_dequant(z, "nvfp4_protected") - z).abs().mean().item() <= e_n4 + 1e-9)
    ck("nvfp4_protected keeps outlier channel ~exact",
       (quant_dequant(z, "nvfp4_protected")[:, 7] - z[:, 7]).abs().max().item() < 1e-3)
    ck("int4_protected keeps outlier channel ~exact",
       (quant_dequant(z, "int4_protected")[:, 7] - z[:, 7]).abs().max().item() < 1e-3)
    # verdict wiring
    _, c1 = verdict({"bf16": 8.0, "int4_protected": 8.02, "nvfp4": 8.03, "nvfp4_protected": 8.02})
    ck("verdict: plain NVFP4 holds -> commoditize", "COMMODITIZES" in c1)
    _, c2 = verdict({"bf16": 8.0, "int4_protected": 8.02, "nvfp4": 40.0, "nvfp4_protected": 8.05})
    ck("verdict: only protected holds -> transfers", "TRANSFERS" in c2)
    print("ALL PASS" if not fails else f"{len(fails)} FAIL")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="KV-format quality: NVFP4 (+protected) vs int4-protected via emulation")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--formats", default="bf16,fp8,int4_protected,nvfp4,nvfp4_protected")
    ap.add_argument("--context", type=int, default=4096)
    ap.add_argument("--ppl-start-frac", type=float, default=0.5)
    ap.add_argument("--protect-frac", type=float, default=0.04)
    ap.add_argument("--text-file", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    import torch
    import torch.nn.functional as F
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
            print(f"  WARNING: wikitext load failed ({type(e).__name__}: {e}); using built-in prose "
                  "(SHORT, ~384 tok). `pip install datasets hf_transfer` or pass --text-file for real context.")
            text = _PROSE
    ids = tok(text)["input_ids"]
    if len(ids) < args.context:
        print(f"  NOTE: only {len(ids)} real tokens (< {args.context}); measuring at ctx={len(ids)} (no tiling).")
    ids = ids[:args.context]
    input_ids = torch.tensor([ids], device="cuda")
    start = max(1, int(args.ppl_start_frac * input_ids.shape[1]))

    print(f"\nKV-format quality — {args.model.split('/')[-1]} ctx={input_ids.shape[1]} "
          f"tail>={args.ppl_start_frac:.0%} protect={args.protect_frac:.0%}  (NVFP4 EMULATED — quality only)")
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa", device_map="cuda").eval()

    # Patch attention: quantize K,V (post-RoPE = the cached tensors) with the active format.
    active = {"fmt": "bf16", "calls": 0}
    _orig_sdpa = F.scaled_dot_product_attention
    def _patched(query, key, value, *a, **k):
        active["calls"] += 1
        if active["fmt"] != "bf16":
            key = quant_dequant(key, active["fmt"], args.protect_frac)
            value = quant_dequant(value, active["fmt"], args.protect_frac)
        return _orig_sdpa(query, key, value, *a, **k)
    F.scaled_dot_product_attention = _patched

    def ppl_for(fmt):
        active["fmt"] = fmt
        labels = input_ids.clone(); labels[:, :start] = -100        # score only the tail
        with torch.no_grad():
            loss = model(input_ids, labels=labels).loss.item()
        return math.exp(loss)

    rows = {}
    for fmt in [f.strip() for f in args.formats.split(",") if f.strip()]:
        rows[fmt] = ppl_for(fmt)
        print(f"  {fmt:<16} PPL {rows[fmt]:8.4f}")
    F.scaled_dot_product_attention = _orig_sdpa

    # VALIDITY GUARDS — a silent no-patch would make every format == bf16 and FALSELY read as
    # "NVFP4 commoditizes." Refuse a verdict unless the patch fired AND quant actually moved PPL.
    if active["calls"] == 0:
        print("\n[INVALID] the sdpa patch never fired — this transformers build routes attention "
              "elsewhere (flash/eager, or a local import). No KV quant was applied. Tell me the "
              "transformers version and I'll patch the right symbol.")
        return 2
    if "fp8" in rows and "bf16" in rows and abs(rows["fp8"] - rows["bf16"]) < 1e-6:
        print("\n[INVALID] fp8 PPL is byte-identical to bf16 -> quantization is a no-op (patch fired but "
              "did not alter K/V). Results not trustworthy.")
        return 2

    print("\n-- verdict --")
    notes, conclusion = verdict(rows)
    for n in notes:
        print("  " + n)
    print("\n" + conclusion)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
