#!/usr/bin/env python3
# TurboQuant on OUR stack — hard-tail free-generation agreement vs bf16.
#
# WHAT THIS MEASURES (and why it's not DeepSeek's snippet)
#   DeepSeek's example just generates text and prints it -- no quality signal. This
#   measures the thing that decides it: free-generation token-agreement vs bf16, the
#   SAME metric as kv_qat_rotation_gate.py, so the result sits directly next to the
#   gate's anchors (naive per-channel 0.2357 / protect 0.2656 / learned-rotation 0.0404).
#
# THE TWO CONFIGS THAT MATTER (label them honestly)
#   * sym4  (bits=4, K and V both 4-bit)  -> the ACTUAL tax-deletion test. DeepSeek
#     concedes this "fails catastrophically on Qwen." This is the real question:
#     does TurboQuant give true 4-bit on Qwen's K? (predicted: no, per our 5 lines.)
#   * k8v4  (key_bits=8, value_bits=4)    -> DeepSeek's Qwen recommendation. Keeps K
#     at 8-bit -> this is NOT tax-deletion (8-bit K is LARGER than our 4-bit+protect K).
#     If it passes quality, it's a different, less-compressed scheme, not a tax win.
#
# REGIME CAVEAT: TurboQuantCache requires use_cache=True (incremental), whereas the
#   gate's naive/protect/learned numbers were use_cache=False (full requant, harsher).
#   So this script's bf16 baseline ALSO runs use_cache=True (regime-matched here);
#   cross-comparison to the gate's 0.24/0.27/0.04 is INDICATIVE, not exact.
#
# Install (system-python, same env as the gate):
#   pip install turboquant            # or: pip install turboquant[gpu]
#
# Run (pod):
#   PYTHONPATH=KVPolicy python Bench/scripts/turboquant_test.py \
#       --model Qwen/Qwen2.5-7B-Instruct --configs sym4,k8v4 --n-prompts 16 --gen 48
#
#   CPU math check (anywhere):
#   python Bench/scripts/turboquant_test.py --selftest

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# --------------------------------------------------------------------------- #
# Agreement metric (CPU-testable) -- identical definition to the gate.
# --------------------------------------------------------------------------- #
def token_agreement(ref, test):
    """ref, test: 1-D int sequences. Returns (agreement_frac, common_prefix_len)."""
    n = min(len(ref), len(test))
    if n == 0:
        return 0.0, 0
    matched = sum(1 for i in range(n) if ref[i] == test[i])
    pre = 0
    for i in range(n):
        if ref[i] == test[i]:
            pre += 1
        else:
            break
    return matched / n, pre


def read_verdict(spec: str, agree: float) -> str:
    """Bits-aware, regime-honest. The tax-deletion question is the LOW-bit (<=4) config;
    >=8-bit 'working' is NOT a tax win (8-bit K >= our 4-bit). Do NOT compare these
    use_cache=True numbers to the gate's use_cache=False anchors as a 'beats protect'
    claim -- different regime."""
    kw = _cache_kwargs(spec)
    bits = kw.get("bits", min([v for k, v in kw.items() if k.endswith("bits")] or [0]))
    if bits <= 4:                                  # the tax-deletion-relevant config
        if agree < 0.15:
            return "CATASTROPHIC -- the 4-bit (tax-deletion) config fails: the low-bit K wall"
        return ("4-bit survives here -- worth a WITHIN-REGIME protect/naive comparison + a "
                "real memory check before believing it")
    return ("8-bit works, but 8-bit K is NOT tax-deletion (>= our 4-bit) -- quality here "
            "doesn't address the tax. (use_cache=True is gentler than the gate; this number "
            "is NOT comparable to protect 0.27.)")


# --------------------------------------------------------------------------- #
# Cache factory: parse a config spec -> TurboQuantCache(**kwargs), defensively.
# --------------------------------------------------------------------------- #
def _cache_kwargs(spec: str) -> dict:
    """sym4/sym3/sym2 -> bits=N ; kAvB -> key_bits=A, value_bits=B."""
    spec = spec.strip().lower()
    if spec.startswith("sym"):
        return {"bits": int(spec[3:])}
    if spec.startswith("k") and "v" in spec:
        k, v = spec[1:].split("v")
        return {"key_bits": int(k), "value_bits": int(v)}
    raise ValueError(f"bad config spec: {spec!r} (use sym4 / sym3 / sym2 / k8v4 ...)")


def _make_cache(spec: str):
    from turboquant import TurboQuantCache  # noqa: F401
    kw = _cache_kwargs(spec)
    try:
        return TurboQuantCache(**kw)
    except TypeError as e:
        if "key_bits" in kw or "value_bits" in kw:
            raise SystemExit(
                f"This turboquant package is SYMMETRIC-ONLY: TurboQuantCache(bits=N).\n"
                f"It has NO key_bits/value_bits -> DeepSeek's 'asymmetric for Qwen' API was\n"
                f"fabricated. Use sym4 / sym8 (and note: even if asymmetric existed, K@8-bit\n"
                f"is not tax-deletion). Rejected: {e}")
        import inspect
        raise SystemExit(
            f"TurboQuantCache(**{kw}) rejected: {e}\n"
            f"Actual signature: {inspect.signature(TurboQuantCache.__init__)}")


# --------------------------------------------------------------------------- #
# GPU/pod: measure agreement vs bf16 for each config.
# --------------------------------------------------------------------------- #
def run_gpu(args) -> int:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:  # noqa: BLE001
        print(f"CANNOT RUN: need torch + transformers ({e})"); return 2
    try:
        import turboquant  # noqa: F401
    except Exception as e:  # noqa: BLE001
        print(f"CANNOT RUN: `pip install turboquant` first ({e})"); return 2
    sys.path.insert(0, str(_HERE.parent.parent / "KVPolicy"))
    import kv_qat_gen_eval as ge   # reuse the exact prompt builder

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(args.model)
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16).to(dev).eval()
    prompts = ge.build_prompts(torch, tok, args.n_prompts, args.prompt_len,
                               args.dataset, args.dataset_config)
    print(f"[turbo] model={args.model} dev={dev} n={args.n_prompts} gen={args.gen} "
          f"configs={args.configs}  (use_cache=True; bf16 baseline same regime)", flush=True)

    @torch.no_grad()
    def gen(ids, cache):
        out = model.generate(ids, max_new_tokens=args.gen, do_sample=False, num_beams=1,
                             use_cache=True, past_key_values=cache, pad_token_id=pad)
        return out[0, ids.shape[1]:].tolist()

    # bf16 reference (use_cache=True), computed ONCE -> all arms compared to the same ref.
    refs = [gen(ids.to(dev), None) for ids in prompts]

    # int4 baselines (naive per-channel / protect) IN THE SAME use_cache=True regime, so
    # TurboQuant is finally apples-to-apples (not the cross-regime gate anchors). vLLM-free.
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA
    from kv_policy.kv_aware_qat import rotary_module
    n_kv = model.config.num_key_value_heads
    D = model.config.hidden_size // model.config.num_attention_heads
    mgr = INT4CacheKVRouteA(k_group_size=32, v_group_size=32, asymmetric=True, bits=4,
                            sink_size=0, num_kv_heads=n_kv, kernel_backend="dequant_fallback")
    qm = rotary_module(model); orig = qm.apply_rotary_pos_emb

    def _v_handles():
        def vhook(m, inp, out):
            flat = out.reshape(-1, out.shape[-1])
            return mgr.round_trip_kv(flat, flat)[1].reshape(out.shape)
        return [mm.register_forward_hook(vhook)
                for n, mm in model.named_modules() if n.rsplit(".", 1)[-1] == "v_proj"]

    def install_protect():                              # per-channel int4 + top-4% protect (K), int4 V
        qmv = 7; n_p = max(1, round(0.04 * D))
        def protect_k(ke):
            x = ke.float()
            s = x.abs().amax(dim=2, keepdim=True) / qmv
            s = torch.where(s == 0, torch.ones_like(s), s)
            kq = torch.clamp(torch.round(x / s), -qmv, qmv) * s
            idx = x.abs().amax(dim=2).topk(n_p, dim=-1).indices
            mask = torch.zeros_like(x, dtype=torch.bool)
            mask.scatter_(3, idx.unsqueeze(2).expand(-1, -1, x.shape[2], -1), True)
            return torch.where(mask, x, kq).to(ke.dtype)
        def rope(q, k, cos, sin, *a, **kw):
            qe, ke = orig(q, k, cos, sin, *a, **kw); return qe, protect_k(ke)
        qm.apply_rotary_pos_emb = rope
        hs = _v_handles()
        def restore():
            qm.apply_rotary_pos_emb = orig
            for h in hs: h.remove()
        return restore

    def arm_tokens(spec, ids):
        if spec == "naive":
            r = ge.install_int4_inference_hooks(torch, model, mgr)
            try: return gen(ids, None)
            finally: r()
        if spec == "protect":
            r = install_protect()
            try: return gen(ids, None)
            finally: r()
        return gen(ids, _make_cache(spec))              # sym* -> TurboQuantCache

    results = {}
    for spec in [c for c in args.configs.split(",") if c.strip()]:
        matched = total = prefix = 0
        for ids, ref in zip(prompts, refs):
            test = arm_tokens(spec, ids.to(dev))
            a, p = token_agreement(ref, test)
            n = min(len(ref), len(test))
            matched += int(a * n); total += n; prefix += p
        agree = matched / max(1, total); results[spec] = agree
        label = spec if spec in ("naive", "protect") else f"{spec} {_cache_kwargs(spec)}"
        print(f"\n[turbo] config={label}")
        print(f"  free-gen agreement vs bf16 = {agree:.4f}  mean_prefix={prefix/len(prompts):.1f}/{args.gen}")
        if spec not in ("naive", "protect"):
            print(f"  -> {read_verdict(spec, agree)}")

    # WITHIN-REGIME verdict: the honest comparison (all use_cache=True).
    if "protect" in results and "sym4" in results:
        d = results["sym4"] - results["protect"]
        print(f"\n[turbo] WITHIN-REGIME (use_cache=True, apples-to-apples):")
        print(f"        naive {results.get('naive', float('nan')):.4f} | protect {results['protect']:.4f} "
              f"| TurboQuant sym4 {results['sym4']:.4f}")
        verdict = ("MATCHES/BEATS protect -> a real Llama win; now do the MEMORY check "
                   "(does TurboQuant's radii metadata < our per-channel+protect tax?)"
                   if d >= -0.01 else
                   f"LOSES to protect by {d:.3f} -> 4-bit TurboQuant does not match the protected design")
        print(f"        sym4 - protect = {d:+.4f}  -> {verdict}")
    return 0


# --------------------------------------------------------------------------- #
# Selftest (CPU): the agreement metric + verdict logic
# --------------------------------------------------------------------------- #
def selftest() -> int:
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("turboquant_test selftest")
    a, p = token_agreement([1, 2, 3, 4], [1, 2, 9, 4])
    check("agreement counts matches (3/4)", abs(a - 0.75) < 1e-9)
    check("common prefix stops at first mismatch (2)", p == 2)
    a, p = token_agreement([1, 2, 3], [1, 2, 3])
    check("identical -> 1.0 agreement, full prefix", a == 1.0 and p == 3)
    a, p = token_agreement([], [1])
    check("empty ref -> 0.0", a == 0.0 and p == 0)
    check("config sym4 -> bits=4", _cache_kwargs("sym4") == {"bits": 4})
    check("config k8v4 -> key/value bits", _cache_kwargs("k8v4") == {"key_bits": 8, "value_bits": 4})
    check("verdict: sym4 @ 0.036 -> 4-bit wall (catastrophic)",
          "CATASTROPHIC" in read_verdict("sym4", 0.036))
    check("verdict: sym8 @ 0.70 -> 8-bit works but NOT tax-deletion",
          "NOT tax-deletion" in read_verdict("sym8", 0.70))
    check("verdict: sym4 @ 0.30 -> 4-bit survives -> needs within-regime check",
          "WITHIN-REGIME" in read_verdict("sym4", 0.30))
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure TurboQuant free-gen agreement vs bf16")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--configs", default="sym4,sym8",
                    help="comma list of symmetric bits: sym4 (tax-deletion test) / sym8 "
                         "(sanity: isolates low-bit vs integration) / sym3 / sym2. "
                         "NOTE: this package is symmetric-only -- no k8v4 (DeepSeek's "
                         "asymmetric API does not exist).")
    ap.add_argument("--n-prompts", type=int, default=16)
    ap.add_argument("--prompt-len", type=int, default=128)
    ap.add_argument("--gen", type=int, default=48)
    ap.add_argument("--dataset", default="Salesforce/wikitext")
    ap.add_argument("--dataset-config", default="wikitext-103-raw-v1")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run_gpu(args)


if __name__ == "__main__":
    raise SystemExit(main())
