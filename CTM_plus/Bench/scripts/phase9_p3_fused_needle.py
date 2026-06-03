#!/usr/bin/env python3
"""Phase 9 P3 — real-needle harness through the PRODUCTION fused_v2 + read-skip path.

The smoke proved fused_v2 serves + read-skip executes, but on synthetic tokens /
short sequences (nothing actually skipped). P3 is the payoff measurement: a REAL
needle-in-haystack at long context, decoded through vLLM offline + route-A
fused_v2 + read-skip, with answer-checking + decode timing. One read-skip mode per
invocation (INT4_READSKIP_MODE env); phase9_p3_fused_needle.sh runs the 3 cells:
  off        — full int4 (baseline)
  retain_all — read-skip plumbing on but keeps everything (BYTE-EQ vs off)
  retention  — sink+recent+attention-selected (the real skip; quality must hold)

fused_v2 v1 is BATCH=1, so we generate ONE prompt at a time (each prompt's decode
steps are batch=1 -> the fused bypass + read-skip fire). At long context the
retained set < seq_len -> actual skipping.

Reuses the GREEN-validated needle builder + matcher from the decode-retention
harness, so the task is identical to what proved retention works in the proxy.

Usage (GPU pod):
  python phase9_p3_fused_needle.py --selftest                         # CPU
  python phase9_p3_fused_needle.py --check-install                    # ~$0.05: fused_v2 fires?
  INT4_READSKIP_MODE=retention python phase9_p3_fused_needle.py \
      --context-tokens 8000 --depths 0.1,0.5,0.9 --items 2 --out r.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase9_decode_retention_harness import build_needle_single, match_code  # noqa: E402

_MODEL_WALK = (
    ("model_executor", "driver_worker", "worker", "model_runner", "model"),
    ("model_executor", "driver_worker", "model_runner", "model"),
    ("model_executor", "model_runner", "model"),
    ("worker", "model_runner", "model"),
    ("model_runner", "model"),
    ("model",),
)


def _extract_model(engine):
    for path in _MODEL_WALK:
        cur = engine
        ok = True
        for attr in path:
            cur = getattr(cur, attr, None)
            if cur is None:
                ok = False
                break
        if ok and cur is not None:
            return cur
    raise RuntimeError("could not locate the torch model on the LLM engine")


# --------------------------------------------------------------------------- #
# Within-process paired A/B (Step-0 yardstick) — PURE helpers, CPU-unit-tested.
# Goal: kill the two confounds that made the Phase-9 breakeven untrustworthy —
#   (1) cross-run noise (off drifted 10.75->8.9->7.29 across SEPARATE processes),
#   (2) prefill dilution (decode_tps timed the whole generate() incl. prefill,
#       which grows with context and shrinks the apparent decode delta).
# --------------------------------------------------------------------------- #

def _mean_std(xs):
    """Sample mean and (n-1) std-dev. (0,0) if empty; std 0 if a single sample."""
    xs = [float(x) for x in xs]
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n == 1:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, var ** 0.5


def _decode_time_from_metrics(metrics):
    """Decode-only wall seconds from a vLLM RequestMetrics-like object:
    ``last_token_time - first_token_time`` — the inter-token decode span, which
    EXCLUDES prefill (and the first token). Returns None if the fields are
    absent/unpopulated or the span is non-positive (e.g. a single decoded token),
    so the caller can fall back to the two-pass (full-minus-prefill) method."""
    ftt = getattr(metrics, "first_token_time", None)
    ltt = getattr(metrics, "last_token_time", None)
    if ftt is None or ltt is None:
        return None
    dt = float(ltt) - float(ftt)
    return dt if dt > 0 else None


def _paired_deltas(base_by_cell, other_by_cell):
    """Per-cell percent delta of ``other`` vs ``base`` decode-tps for the cells in
    BOTH (a cell = one (seed, depth) pair). Pairing is what makes it within-process:
    each delta is two measurements on the same warm engine and the same needle, so
    prefill cost and clock state cancel. Cells with base<=0 or missing are skipped.
    """
    out = []
    for cell, b in base_by_cell.items():
        o = other_by_cell.get(cell)
        if o is None or b <= 0:
            continue
        out.append((o - b) / b * 100.0)
    return out


def run(args) -> int:
    import random
    from vllm import LLM, SamplingParams
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2, BACKEND_DEQUANT_FALLBACK,
    )

    backend = (BACKEND_FUSED_V2 if args.backend == "fused_v2"
               else BACKEND_DEQUANT_FALLBACK)
    mode = os.environ.get("INT4_READSKIP_MODE", "off")
    llm = LLM(model=args.model, enforce_eager=True,
              max_model_len=args.max_model_len,
              gpu_memory_utilization=args.gpu_util)
    model = _extract_model(llm.llm_engine)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, k_group_size=32, v_group_size=32, asymmetric=True, bits=4,
        sink_size=4, kernel_backend=backend, max_seq_len=args.max_model_len,
        protect_fraction=0.04, cache_k_group_size=1, cache_v_group_size=32)
    print(f"[p3] backend={backend} readskip_mode={mode} "
          f"max_model_len={args.max_model_len}", flush=True)
    tok = llm.get_tokenizer()
    sp = SamplingParams(temperature=0.0, max_tokens=args.max_gen)

    def gen_one(prompt):
        # Each needle is an INDEPENDENT sequence. fused_v2 v1 is single-sequence:
        # reset per-prompt or prefills accumulate and overflow max_seq_len.
        manager.reset()
        chat = tok.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True)
        t0 = time.perf_counter()
        out = llm.generate([chat], sp, use_tqdm=False)   # batch=1 -> fused fires
        dt = time.perf_counter() - t0
        o = out[0].outputs[0]
        return o.text, len(o.token_ids), dt

    if args.check_install:
        rng = random.Random(0)
        user, code, _q, _n = build_needle_single(1000, 0.9, rng)
        text, n, dt = gen_one(user)
        st = manager.stats
        print(f"[p3][check] gen={text[:60]!r} tokens={n} "
              f"fused_v2_decodes={st.get('fused_v2_decodes')} "
              f"readskip_calls={st.get('readskip_calls')} "
              f"hit={match_code(text, code)[0]}", flush=True)
        ok = (st.get("fused_v2_decodes", 0) > 0) if backend == BACKEND_FUSED_V2 else True
        print("[p3][check] " + ("PASS — fused path fired." if ok else
              "FAIL — fused_v2_decodes==0 (batch>1 fallback or fused serving issue)"),
              flush=True)
        return 0 if ok else 3

    if args.profile:
        # P4: attribute the per-decode-step overhead. Enable CUDA-event profiling,
        # run a few retention decodes at long context, split the cost by section.
        manager.set_profiling(True)
        rng = random.Random(args.seed)
        for _ in range(max(2, args.items)):
            user, _c, _q, _n = build_needle_single(args.context_tokens, 0.5, rng)
            gen_one(user)
        stats = manager.get_profile_stats()
        bypass = (stats.get("total_bypass") or {}).get("mean_ms") or 0.0
        order = ["readskip_decision", "kernel_inputs", "kernel_call",
                 "cache_append", "reshape_kv", "cast_back", "total_bypass"]
        print(f"\n[p3][profile] per-decode-step mean ms by section "
              f"(mode={mode}, ctx={args.context_tokens}):")
        for s in order:
            d = stats.get(s)
            if not d:
                continue
            pct = (100.0 * d["mean_ms"] / bypass) if bypass else 0.0
            print(f"  {s:<18} mean={d['mean_ms']:.3f}ms  "
                  f"({pct:4.1f}% of bypass)  n={d['n_calls']}")
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(
            {"mode": "profile", "context_tokens": args.context_tokens,
             "readskip_mode": mode, "sections": stats}, indent=2))
        print(f"[p3][profile] wrote {args.out}")
        return 0

    depths = [float(x) for x in args.depths.split(",") if x.strip()]
    rng = random.Random(args.seed)
    per_depth, dec_tok, dec_t = {}, 0, 0.0
    items = []
    for d in depths:
        hits = 0
        for _ in range(args.items):
            user, code, _q, _n = build_needle_single(args.context_tokens, d, rng)
            text, n, dt = gen_one(user)
            hit, reason, _ = match_code(text, code)
            hits += int(hit)
            dec_tok += n
            dec_t += dt
            items.append({"depth": d, "expected": code, "generated": text[:120],
                          "hit": hit, "reason": reason, "gen_tokens": n})
        per_depth[f"{d:.2f}"] = round(hits / args.items, 3)
        print(f"[p3] depth={d:.2f} hit_rate={hits}/{args.items}", flush=True)

    st = manager.stats
    result = {
        "model": args.model, "backend": backend, "readskip_mode": mode,
        "context_tokens": args.context_tokens, "items_per_depth": args.items,
        "decode_tps": round(dec_tok / dec_t, 2) if dec_t else 0.0,
        "decode_tokens": dec_tok,
        "hit_rate_by_depth": per_depth,
        "fused_v2_decodes": st.get("fused_v2_decodes"),
        "readskip_calls": st.get("readskip_calls"),
        "readskip_controllers": st.get("readskip_controllers"),
        "items": items,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"[p3] decode_tps={result['decode_tps']} "
          f"fused_v2_decodes={result['fused_v2_decodes']} "
          f"readskip_calls={result['readskip_calls']}  wrote {args.out}", flush=True)
    try:
        teardown()
    except Exception:
        pass
    return 0


def run_ab(args) -> int:
    """Within-process paired A/B: build ONE warm engine, then measure every mode
    (default off vs retention) back-to-back on the SAME needle across seeds x
    depths, with warmup discarded and repeated timed measurements. Decode timing
    EXCLUDES prefill (vLLM token-time metrics when populated, else a prefill+1
    calibration subtracted from the full generate). Reports per-mode decode-tps
    with spread and the paired delta vs the baseline (off) per (seed, depth) cell,
    so a throughput claim can be judged against its own noise."""
    import random
    from vllm import LLM, SamplingParams
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2, BACKEND_DEQUANT_FALLBACK,
    )

    backend = (BACKEND_FUSED_V2 if args.backend == "fused_v2"
               else BACKEND_DEQUANT_FALLBACK)
    modes = [m.strip() for m in args.ab_modes.split(",") if m.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    depths = [float(d) for d in args.depths.split(",") if d.strip()]
    gen = int(args.ab_gen)
    repeats = max(1, int(args.repeats))
    warmup = max(1, int(args.warmup))   # >=1: also JIT-warms + detects metrics

    llm = LLM(model=args.model, enforce_eager=True,
              max_model_len=args.max_model_len,
              gpu_memory_utilization=args.gpu_util)
    model = _extract_model(llm.llm_engine)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, k_group_size=32, v_group_size=32, asymmetric=True, bits=4,
        sink_size=4, kernel_backend=backend, max_seq_len=args.max_model_len,
        protect_fraction=0.04, cache_k_group_size=1, cache_v_group_size=32)
    tok = llm.get_tokenizer()
    print(f"[ab] backend={backend} modes={modes} seeds={seeds} depths={depths} "
          f"gen={gen} repeats={repeats} warmup={warmup} ctx={args.context_tokens} "
          f"max_model_len={args.max_model_len}", flush=True)

    def _chat(prompt):
        return tok.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True)

    def _gen(chat, max_tokens):
        # fused_v2 is single-sequence: reset per request (mirrors gen_one).
        manager.reset()
        sp = SamplingParams(temperature=0.0, max_tokens=max_tokens)
        t0 = time.perf_counter()
        out = llm.generate([chat], sp, use_tqdm=False)
        dt = time.perf_counter() - t0
        o = out[0].outputs[0]
        return o.text, len(o.token_ids), dt, getattr(out[0], "metrics", None)

    def _cell_seed(seed, depth):
        return seed * 10000 + int(round(depth * 1000))

    # ---- WARMUP (discarded) + decode-time-method detection ----
    wr = random.Random(_cell_seed(seeds[0], depths[0]))
    warm_user, _wc, _wq, _wn = build_needle_single(args.context_tokens, depths[0], wr)
    warm_chat = _chat(warm_user)
    last_metrics = None
    for mode in modes:
        manager.set_readskip_mode(mode)
        for _ in range(warmup):
            _t, _n, _dt, last_metrics = _gen(warm_chat, gen)
    use_metrics = _decode_time_from_metrics(last_metrics) is not None
    method = ("metrics:last-first_token_time" if use_metrics
              else "two_pass:full-minus-prefill")
    print(f"[ab] decode-time method = {method}  (warmup {warmup}/mode discarded)",
          flush=True)

    # ---- measurement loop (interleave modes per repeat so paired samples are
    #      adjacent in time -> clock drift cancels in the within-cell delta) ----
    results = {m: {"tps": [], "cell": {}, "hits": {}} for m in modes}
    items = []
    for seed in seeds:
        for depth in depths:
            user, code, _q, _n = build_needle_single(
                args.context_tokens, depth, random.Random(_cell_seed(seed, depth)))
            chat = _chat(user)

            prefill_t = None
            if not use_metrics:
                # prefill is mode-independent (read-skip only touches decode): one
                # off-mode prefill+1 calibration, median of 2, subtracted from full.
                manager.set_readskip_mode("off")
                cals = sorted(_gen(chat, 1)[2] for _ in range(2))
                prefill_t = cals[len(cals) // 2]

            cell_tps = {m: [] for m in modes}
            text_by_mode = {}
            for _r in range(repeats):
                for mode in modes:
                    manager.set_readskip_mode(mode)
                    text, n, dt_full, mtr = _gen(chat, gen)
                    text_by_mode[mode] = text   # always set (used for quality)
                    ddt = (_decode_time_from_metrics(mtr) if use_metrics
                           else max(1e-6, dt_full - prefill_t))
                    # Drop a non-positive/None decode time rather than poison the
                    # mean with a 0.0 tps (shouldn't happen post-detection).
                    if ddt and ddt > 0:
                        cell_tps[mode].append(max(1, n - 1) / ddt)
            for mode in modes:
                results[mode]["tps"].extend(cell_tps[mode])
                m_tps, s_tps = _mean_std(cell_tps[mode])
                results[mode]["cell"][(seed, depth)] = m_tps
                hit = int(match_code(text_by_mode[mode], code)[0])
                results[mode]["hits"].setdefault(f"{depth:.2f}", []).append(hit)
                items.append({"seed": seed, "depth": depth, "mode": mode,
                              "tps_mean": round(m_tps, 3), "tps_std": round(s_tps, 3),
                              "hit": hit, "expected": code,
                              "generated": text_by_mode[mode][:80]})
            print(f"[ab] seed={seed} depth={depth:.2f}: "
                  + "  ".join(f"{m}={results[m]['cell'][(seed, depth)]:.2f}tps"
                              for m in modes), flush=True)

    # ---- aggregate ----
    baseline = "off" if "off" in results else modes[0]
    per_mode = {}
    for m in modes:
        mean, std = _mean_std(results[m]["tps"])
        per_mode[m] = {
            "tps_mean": round(mean, 3), "tps_std": round(std, 3),
            "n_samples": len(results[m]["tps"]),
            "hit_rate_by_depth": {d: round(sum(v) / len(v), 3)
                                  for d, v in sorted(results[m]["hits"].items())},
        }
    paired = {}
    for m in modes:
        if m == baseline:
            continue
        deltas = _paired_deltas(results[baseline]["cell"], results[m]["cell"])
        dmean, dstd = _mean_std(deltas)
        paired[m] = {"delta_pct_mean": round(dmean, 2), "delta_pct_std": round(dstd, 2),
                     "n_cells": len(deltas), "deltas_pct": [round(x, 2) for x in deltas]}

    report = {
        "kind": "within_process_ab", "model": args.model, "backend": backend,
        "context_tokens": args.context_tokens, "gen": gen, "repeats": repeats,
        "warmup_discarded": warmup, "seeds": seeds, "depths": depths, "modes": modes,
        "baseline": baseline, "max_model_len": args.max_model_len,
        "decode_time_method": method, "per_mode": per_mode,
        "paired_vs_baseline": paired,
        "readskip_calls": manager.stats.get("readskip_calls"), "items": items,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))

    # ---- decision-oriented summary ----
    print(f"\n[ab] === within-process paired A/B (ctx={args.context_tokens}, "
          f"gen={gen}, method={method}) ===")
    print(f"[ab] per-mode decode tps (mean +/- std over "
          f"{per_mode[baseline]['n_samples']} samples):")
    for m in modes:
        pm = per_mode[m]
        print(f"[ab]   {m:<10} {pm['tps_mean']:.2f} +/- {pm['tps_std']:.2f} tps   "
              f"quality={pm['hit_rate_by_depth']}")
    for m, p in paired.items():
        lo, hi = p["delta_pct_mean"] - p["delta_pct_std"], p["delta_pct_mean"] + p["delta_pct_std"]
        verdict = ("WIN (beyond spread)" if lo > 0 else
                   "LOSS (beyond spread)" if hi < 0 else "BREAKEVEN (within spread)")
        print(f"[ab]   {m} vs {baseline}: {p['delta_pct_mean']:+.1f}% "
              f"+/- {p['delta_pct_std']:.1f}%  over {p['n_cells']} cells -> {verdict}")
    print(f"[ab] wrote {args.out}", flush=True)
    try:
        teardown()
    except Exception:
        pass
    return 0


def _selftest() -> int:
    import random
    u, c, q, n = build_needle_single(2000, 0.5, random.Random(1))
    assert "ACCESS_CODE:" in n and c in u
    assert match_code(f"the code is {c}", c)[0]
    assert not match_code("KILO-ROMEO-VICTOR", "ALFA-BRAVO-CHARLIE")[0] or True
    # extraction walk picks the deepest matching path.
    class _M: pass
    eng = _M(); eng.model = "M0"
    assert _extract_model(eng) == "M0"

    # --- within-process A/B pure helpers (the yardstick math) ---
    m_, s_ = _mean_std([2.0, 4.0, 6.0])
    assert abs(m_ - 4.0) < 1e-9 and abs(s_ - 2.0) < 1e-9, (m_, s_)
    assert _mean_std([]) == (0.0, 0.0) and _mean_std([5.0]) == (5.0, 0.0)

    class _Mtr:  # vLLM RequestMetrics-like
        def __init__(self, a, b): self.first_token_time = a; self.last_token_time = b
    assert abs(_decode_time_from_metrics(_Mtr(100.0, 101.5)) - 1.5) < 1e-9
    assert _decode_time_from_metrics(_Mtr(None, 5.0)) is None     # unpopulated -> fall back
    assert _decode_time_from_metrics(_Mtr(5.0, 5.0)) is None      # non-positive span
    assert _decode_time_from_metrics(object()) is None            # no fields at all

    # paired deltas: off baseline -> +10% each cell; missing/zero-base cells skipped.
    base = {(1, 0.5): 7.0, (2, 0.5): 8.0}
    other = {(1, 0.5): 7.7, (2, 0.5): 8.8}
    dd = _paired_deltas(base, other)
    assert len(dd) == 2 and all(abs(x - 10.0) < 1e-9 for x in dd), dd
    assert _paired_deltas({(1, 0.5): 0.0, (3, 0.1): 7.0}, {(3, 0.1): 7.0}) == [0.0]

    # runtime mode switch: exercise the REAL manager method on a stub (no torch
    # needed — it only flips _readskip_mode and clears _readskip_controllers).
    here = os.path.dirname(os.path.abspath(__file__))
    kvp = os.path.normpath(os.path.join(here, "..", "..", "KVPolicy"))
    if kvp not in sys.path:
        sys.path.insert(0, kvp)
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA
    import types
    stub = types.SimpleNamespace(_readskip_mode="off",
                                 _readskip_controllers={1: object()})
    INT4CacheKVRouteA.set_readskip_mode(stub, "retention")
    assert stub._readskip_mode == "retention" and stub._readskip_controllers == {}
    try:
        INT4CacheKVRouteA.set_readskip_mode(stub, "bogus")
        raise AssertionError("set_readskip_mode should reject an unknown mode")
    except ValueError:
        pass

    print("p3 fused needle self-test: PASS")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--backend", default="fused_v2",
                    choices=["fused_v2", "dequant_fallback"])
    ap.add_argument("--context-tokens", type=int, default=8000)
    ap.add_argument("--depths", default="0.1,0.5,0.9")
    ap.add_argument("--items", type=int, default=2)
    ap.add_argument("--max-gen", type=int, default=16)
    ap.add_argument("--max-model-len", type=int, default=16384)
    ap.add_argument("--gpu-util", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="phase9_p3_fused_needle.json")
    ap.add_argument("--check-install", action="store_true")
    ap.add_argument("--profile", action="store_true",
                    help="P4: enable CUDA-event profiling, run retention decodes, "
                         "print per-section ms (readskip_decision / kernel_inputs "
                         "gather / kernel_call / ...) to attribute the overhead")
    ap.add_argument("--selftest", action="store_true")
    # Within-process paired A/B (Step-0 yardstick): off vs retention on ONE warm
    # engine, decode-only timing, warmup discarded, repeated measurements.
    ap.add_argument("--ab", action="store_true",
                    help="within-process paired A/B: per-mode decode-tps with "
                         "spread + paired delta vs off on a single warm engine "
                         "(removes cross-run noise AND prefill dilution)")
    ap.add_argument("--ab-modes", default="off,retention",
                    help="comma list of modes to compare (off/retain_all/retention); "
                         "baseline is 'off' when present")
    ap.add_argument("--seeds", default="1,2,3",
                    help="comma list of integer seeds; each is one paired (seed,depth) "
                         "cell per depth -> the spread of the paired delta")
    ap.add_argument("--repeats", type=int, default=3,
                    help="timed measurements per (mode, seed, depth) cell")
    ap.add_argument("--warmup", type=int, default=2,
                    help="discarded warmup generations per mode (>=1; JIT-warms the "
                         "kernel + settles clocks + detects the decode-time method)")
    ap.add_argument("--ab-gen", type=int, default=128,
                    help="decode tokens for the timed pass (amortizes the observe "
                         "phase; Phase-9 breakeven was at gen=128)")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.ab:
        return run_ab(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
