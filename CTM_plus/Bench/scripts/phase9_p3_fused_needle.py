#!/usr/bin/env python3
"""Phase 9 P3 — real-needle harness through the PRODUCTION fused_v2 + read-skip path.

The smoke proved fused_v2 serves + read-skip executes, but on synthetic tokens /
short sequences (nothing actually skipped). P3 is the payoff measurement: a REAL
needle-in-haystack at long context, decoded through vLLM offline + route-A
fused_v2 + read-skip, with answer-checking + decode timing. One read-skip mode per
invocation (INT4_READSKIP_MODE env); phase9_p3_fused_needle.sh runs the 3 cells:
  off          — full int4 (baseline)
  retain_all   — read-skip plumbing on but keeps everything (BYTE-EQ vs off)
  retention    — sink+recent+attention-selected (the real skip; quality must hold)
  score_noskip — score on the normal cadence but read all (isolates scoring cost;
                 quality identical to off). Decompose: (score_noskip-off)=scoring,
                 (retain_all-off)=gather-all, (retention-off)=net.

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


def _profile_section_rows(per_mode, order, baseline):
    """Side-by-side per-section profiler rows for the paired profiler: a list of
    ``(section, {mode: mean_ms}, {non_baseline_mode: delta_ms_vs_baseline})`` in
    ``order``, skipping sections absent from every mode. This is what attributes a
    gap — e.g. ``kernel_inputs`` (the host gather) or the observe-phase scoring not
    shrinking. PURE; CPU-unit-tested."""
    modes = list(per_mode.keys())
    base = per_mode.get(baseline, {}).get("sections", {})
    rows = []
    for sec in order:
        cells, deltas, present = {}, {}, False
        for m in modes:
            ms = per_mode[m].get("sections", {}).get(sec)
            cells[m] = ms
            if ms is not None:
                present = True
                if m != baseline and base.get(sec) is not None:
                    deltas[m] = round(ms - base[sec], 4)
        if present:
            rows.append((sec, cells, deltas))
    return rows


def _engine_kwargs(args):
    """Shared vLLM ``LLM(...)`` kwargs for all three engine builders (profile /
    --ab / bf16_ref), so they can't drift. ``--hf-overrides`` (a JSON object) is
    passed straight to ``LLM(hf_overrides=...)`` — its purpose is to inject
    ``rope_scaling`` (YaRN) so a 32K-native model (Qwen2.5-7B) can run the 48-64K
    read-skip CROSSOVER experiment past its native window. Empty -> stock defaults
    (byte-for-byte the prior behavior)."""
    # enable_chunked_prefill pinned False: vLLM V0 AUTO-enables it at
    # max_model_len > 32768 (every >32K crossover cell). Route-A's prefill
    # write hooks are not chunk-validated, and the bf16 reference must use
    # the same single-shot prefill for comparability.
    kw = dict(enforce_eager=True, max_model_len=args.max_model_len,
              gpu_memory_utilization=args.gpu_util,
              enable_chunked_prefill=False)
    raw = (getattr(args, "hf_overrides", "") or "").strip()
    if raw:
        import json
        ov = json.loads(raw)
        if not isinstance(ov, dict):
            raise SystemExit("--hf-overrides must be a JSON object, got: " + raw)
        kw["hf_overrides"] = ov
        print(f"[engine] hf_overrides={ov}", flush=True)
    return kw


def run(args) -> int:
    import random
    from vllm import LLM, SamplingParams
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2, BACKEND_DEQUANT_FALLBACK,
    )

    backend = (BACKEND_FUSED_V2 if args.backend == "fused_v2"
               else BACKEND_DEQUANT_FALLBACK)
    mode = os.environ.get("INT4_READSKIP_MODE", "off")
    llm = LLM(model=args.model, **_engine_kwargs(args))
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


def _build_fused_engine(args):
    """Build the vLLM engine + install the route-A manager. Returns
    (llm, manager, teardown, tok, backend). Shared by --ab and --profile-ab."""
    from vllm import LLM
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2, BACKEND_DEQUANT_FALLBACK,
    )
    backend = (BACKEND_FUSED_V2 if args.backend == "fused_v2"
               else BACKEND_DEQUANT_FALLBACK)
    llm = LLM(model=args.model, **_engine_kwargs(args))
    model = _extract_model(llm.llm_engine)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, k_group_size=32, v_group_size=32, asymmetric=True, bits=4,
        sink_size=4, kernel_backend=backend, max_seq_len=args.max_model_len,
        protect_fraction=0.04, cache_k_group_size=1, cache_v_group_size=32)
    return llm, manager, teardown, llm.get_tokenizer(), backend


def run_ab(args) -> int:
    """Within-process paired A/B: build ONE warm engine, then measure every mode
    (default off vs retention) back-to-back on the SAME needle across seeds x
    depths, with warmup discarded and repeated timed measurements. Decode timing
    EXCLUDES prefill (vLLM token-time metrics when populated, else a prefill+1
    calibration subtracted from the full generate). Reports per-mode decode-tps
    with spread, the paired delta vs the baseline (off) per (seed, depth) cell, and
    the read-skip diagnostics (how much was ACTUALLY skipped + observe/steady step
    split), so a throughput claim can be judged against its own noise and cause."""
    import random
    from vllm import SamplingParams

    modes = [m.strip() for m in args.ab_modes.split(",") if m.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    depths = [float(d) for d in args.depths.split(",") if d.strip()]
    gen = int(args.ab_gen)
    repeats = max(1, int(args.repeats))
    warmup = max(1, int(args.warmup))   # >=1: also JIT-warms + detects metrics

    llm, manager, teardown, tok, backend = _build_fused_engine(args)
    print(f"[ab] backend={backend} modes={modes} seeds={seeds} depths={depths} "
          f"gen={gen} repeats={repeats} warmup={warmup} ctx={args.context_tokens} "
          f"max_model_len={args.max_model_len} "
          f"kernel_scores={manager.stats.get('readskip_kernel_scores')} "
          f"inkernel={manager.stats.get('readskip_inkernel')}", flush=True)

    def _chat(prompt):
        return tok.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True)

    def _gen(chat, max_tokens):
        # fused_v2 is single-sequence: reset per request (mirrors gen_one).
        manager.reset()
        # ignore_eos: the needle ANSWER is short (~7 tokens), so natural EOS ends
        # decode inside the observe window and read-skip never amortizes. Forcing
        # the full `max_tokens` decode is what measures the gen=N regime (quality
        # is detected from the early tokens regardless; match_code scans the text).
        sp = SamplingParams(temperature=0.0, max_tokens=max_tokens, ignore_eos=True)
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
    manager.clear_readskip_stats()   # skip-fraction reflects the MEASURED phase only

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

    st = manager.stats
    skip_diag = {
        "steady_skip_frac": st.get("readskip_steady_skip_frac"),
        "steady_retained_mean": st.get("readskip_steady_retained_mean"),
        "steady_seq_mean": st.get("readskip_steady_seq_mean"),
        "observe_steps": st.get("readskip_observe_steps"),
        "steady_steps": st.get("readskip_steady_steps"),
    }
    report = {
        "kind": "within_process_ab", "model": args.model, "backend": backend,
        "context_tokens": args.context_tokens, "gen": gen, "repeats": repeats,
        "warmup_discarded": warmup, "seeds": seeds, "depths": depths, "modes": modes,
        "baseline": baseline, "max_model_len": args.max_model_len,
        "decode_time_method": method, "per_mode": per_mode,
        "paired_vs_baseline": paired,
        "readskip_calls": st.get("readskip_calls"), "skip_diag": skip_diag,
        "readskip_kernel_scores": st.get("readskip_kernel_scores"),
        "readskip_inkernel": st.get("readskip_inkernel"),
        "items": items,
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
    if skip_diag["steady_steps"]:
        print(f"[ab] retention skip: steady skip_frac="
              f"{skip_diag['steady_skip_frac']:.1%} "
              f"(retained ~{skip_diag['steady_retained_mean']:.0f} of "
              f"~{skip_diag['steady_seq_mean']:.0f}); steps observe="
              f"{skip_diag['observe_steps']} steady={skip_diag['steady_steps']} "
              f"(observe steps re-read all + re-score -> use --profile-ab to time them)")
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


def run_profile_ab(args) -> int:
    """Paired per-section profiler. In ONE process, profile each mode (off vs
    retention) over a few long-context needle decodes and print the per-decode-step
    cost broken down by section (kernel_call / readskip_decision / kernel_inputs
    gather / cache_append / ...) side by side with the off->mode delta, PLUS
    retention's observe-vs-steady total_bypass split + skip fraction. This
    attributes WHERE a gap is (e.g. the observe phase eating the skip savings, or
    the host gather not shrinking). Profiling adds CUDA syncs that perturb timing,
    so this is SEPARATE from --ab (which gives the clean tps verdict)."""
    import random
    from vllm import SamplingParams

    modes = [m.strip() for m in args.ab_modes.split(",") if m.strip()]
    gen = int(args.ab_gen)
    items = max(1, int(args.items))
    depth = [float(d) for d in args.depths.split(",") if d.strip()][0]

    llm, manager, teardown, tok, backend = _build_fused_engine(args)
    print(f"[prof-ab] backend={backend} modes={modes} ctx={args.context_tokens} "
          f"gen={gen} items={items} depth={depth}", flush=True)

    def _gen(prompt):
        manager.reset()
        chat = tok.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True)
        llm.generate([chat],
                     SamplingParams(temperature=0.0, max_tokens=gen, ignore_eos=True),
                     use_tqdm=False)

    # Warmup (discarded) per mode to JIT-compile the kernel shapes before timing.
    warm_user, _wc, _wq, _wn = build_needle_single(
        args.context_tokens, depth, random.Random(args.seed))
    for mode in modes:
        manager.set_readskip_mode(mode)
        _gen(warm_user)

    per_mode = {}
    for mode in modes:
        manager.set_readskip_mode(mode)
        manager.clear_profile()
        manager.clear_readskip_stats()
        manager.set_profiling(True)
        rng = random.Random(args.seed + 1)
        for _ in range(items):
            u, _c, _q, _n = build_needle_single(args.context_tokens, depth, rng)
            _gen(u)
        manager.set_profiling(False)
        sections = manager.get_profile_stats()
        st = manager.stats
        per_mode[mode] = {
            "sections": {k: round(v["mean_ms"], 4) for k, v in sections.items()
                         if isinstance(v, dict) and "mean_ms" in v},
            "total_bypass_split": sections.get("total_bypass_split"),
            "skip_frac": st.get("readskip_steady_skip_frac"),
            "observe_steps": st.get("readskip_observe_steps"),
            "steady_steps": st.get("readskip_steady_steps"),
        }

    order = ["kernel_call", "readskip_decision", "kernel_inputs", "cache_append",
             "reshape_kv", "cast_back", "total_bypass"]
    baseline = "off" if "off" in per_mode else modes[0]
    rows = _profile_section_rows(per_mode, order, baseline)

    report = {"kind": "profile_ab", "model": args.model, "backend": backend,
              "context_tokens": args.context_tokens, "gen": gen, "items": items,
              "depth": depth, "modes": modes, "baseline": baseline,
              "per_mode": per_mode,
              "section_order": order, "max_model_len": args.max_model_len}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))

    # ---- side-by-side attribution table ----
    others = [m for m in modes if m != baseline]
    hdr = f"{'section':<18} " + "".join(f"{m:>12}" for m in modes)
    hdr += "".join(f"{('Δ '+m):>12}" for m in others)
    print(f"\n[prof-ab] === per-decode-step ms by section "
          f"(ctx={args.context_tokens}, gen={gen}) ===")
    print("[prof-ab] " + hdr)
    for sec, cells, deltas in rows:
        line = f"{sec:<18} " + "".join(
            (f"{cells[m]:>12.4f}" if cells.get(m) is not None else f"{'-':>12}")
            for m in modes)
        line += "".join(
            (f"{deltas[m]:>+12.4f}" if m in deltas else f"{'-':>12}") for m in others)
        print("[prof-ab] " + line)
    for m in modes:
        sp = per_mode[m].get("total_bypass_split")
        if sp:
            obs = sp.get("observe", {}); std = sp.get("steady", {})
            print(f"[prof-ab] {m} total_bypass split: "
                  f"observe={obs.get('mean_ms', float('nan')):.3f}ms"
                  f"(n={obs.get('n', 0)}) vs steady="
                  f"{std.get('mean_ms', float('nan')):.3f}ms(n={std.get('n', 0)}) "
                  f"-> observe steps cost "
                  f"{(obs.get('mean_ms', 0) / std['mean_ms']):.1f}x a steady step"
                  if std.get("mean_ms") else "")
        if per_mode[m]["steady_steps"]:
            print(f"[prof-ab] {m} steady skip_frac={per_mode[m]['skip_frac']:.1%} "
                  f"(observe={per_mode[m]['observe_steps']} "
                  f"steady={per_mode[m]['steady_steps']} steps)")
    print(f"[prof-ab] wrote {args.out}", flush=True)
    try:
        teardown()
    except Exception:
        pass
    return 0


# Step-0 cost model's modeled net read-skip speedup vs full-int4 (off) at long
# context (PHASE9_STEP0_FINDINGS). The paired Δ% target line: (1.9 - 1) * 100.
COST_MODEL_TARGET_X = 1.9


def run_bf16_ref(args) -> int:
    """bf16 REFERENCE (gap #4): vanilla vLLM — NO int4, NO read-skip — on the same
    needle, with the same decode-only timing + warmup + repeats. This is the
    ABSOLUTE scale the off<->retention paired delta sits against: int4_protected is
    a density play and is SLOWER than bf16 on its own (capstone 0.22-0.54x); the
    whole point of read-skip is to claw decode throughput back toward (or past)
    bf16 at long context. Separate process (no manager installed), so it is a
    reference LINE, not a within-process paired delta — compare with that caveat."""
    import random
    from vllm import LLM, SamplingParams

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    depths = [float(d) for d in args.depths.split(",") if d.strip()]
    gen = int(args.ab_gen)
    repeats = max(1, int(args.repeats))
    warmup = max(1, int(args.warmup))

    # Vanilla engine — deliberately NOT installing the int4 route-A manager.
    llm = LLM(model=args.model, **_engine_kwargs(args))
    tok = llm.get_tokenizer()
    print(f"[bf16] vanilla bf16 reference (no int4/read-skip) seeds={seeds} "
          f"depths={depths} gen={gen} repeats={repeats} ctx={args.context_tokens} "
          f"max_model_len={args.max_model_len}", flush=True)

    def _cell_seed(seed, depth):
        return seed * 10000 + int(round(depth * 1000))

    def _gen(prompt, max_tokens):
        chat = tok.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True)
        sp = SamplingParams(temperature=0.0, max_tokens=max_tokens, ignore_eos=True)
        t0 = time.perf_counter()
        out = llm.generate([chat], sp, use_tqdm=False)
        dt = time.perf_counter() - t0
        o = out[0].outputs[0]
        return o.text, len(o.token_ids), dt, getattr(out[0], "metrics", None)

    # warmup (discarded) + decode-time-method detection (mirror run_ab).
    wu, _c, _q, _n = build_needle_single(
        args.context_tokens, depths[0], random.Random(_cell_seed(seeds[0], depths[0])))
    last_metrics = None
    for _ in range(warmup):
        _t, _nn, _dt, last_metrics = _gen(wu, gen)
    use_metrics = _decode_time_from_metrics(last_metrics) is not None
    method = ("metrics:last-first_token_time" if use_metrics
              else "two_pass:full-minus-prefill")
    print(f"[bf16] decode-time method = {method} (warmup {warmup} discarded)",
          flush=True)

    tps_samples, hits = [], {}
    for seed in seeds:
        for depth in depths:
            user, code, _q, _n = build_needle_single(
                args.context_tokens, depth, random.Random(_cell_seed(seed, depth)))
            prefill_t = None
            if not use_metrics:
                prefill_t = sorted(_gen(user, 1)[2] for _ in range(2))[1]
            text = None
            for _r in range(repeats):
                text, n, dt_full, mtr = _gen(user, gen)
                ddt = (_decode_time_from_metrics(mtr) if use_metrics
                       else max(1e-6, dt_full - prefill_t))
                if ddt and ddt > 0:
                    tps_samples.append(max(1, n - 1) / ddt)
            hits.setdefault(f"{depth:.2f}", []).append(int(match_code(text, code)[0]))

    mean, std = _mean_std(tps_samples)
    report = {"kind": "bf16_ref", "model": args.model, "context_tokens": args.context_tokens,
              "gen": gen, "repeats": repeats, "warmup_discarded": warmup,
              "seeds": seeds, "depths": depths, "max_model_len": args.max_model_len,
              "decode_time_method": method, "tps_mean": round(mean, 3),
              "tps_std": round(std, 3), "n_samples": len(tps_samples),
              "hit_rate_by_depth": {d: round(sum(v) / len(v), 3)
                                    for d, v in sorted(hits.items())}}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"[bf16] decode tps = {mean:.2f} +/- {std:.2f} (n={len(tps_samples)})  "
          f"quality={report['hit_rate_by_depth']}  wrote {args.out}", flush=True)
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

    # --- paired profiler: section table (off baseline, retention deltas) ---
    pm = {"off": {"sections": {"kernel_call": 5.0, "kernel_inputs": 0.1,
                               "total_bypass": 6.0}},
          "retention": {"sections": {"kernel_call": 2.0, "kernel_inputs": 1.2,
                                     "total_bypass": 5.0}}}
    rows = _profile_section_rows(
        pm, ["kernel_call", "kernel_inputs", "missing", "total_bypass"], "off")
    assert {r[0] for r in rows} == {"kernel_call", "kernel_inputs", "total_bypass"}
    kc = next(r for r in rows if r[0] == "kernel_call")
    assert kc[1]["retention"] == 2.0 and abs(kc[2]["retention"] + 3.0) < 1e-9, kc
    ki = next(r for r in rows if r[0] == "kernel_inputs")
    assert abs(ki[2]["retention"] - 1.1) < 1e-9, ki   # gather got pricier under retention

    # runtime mode switch: exercise the REAL manager method on a stub (no torch
    # needed — it only flips _readskip_mode and clears _readskip_controllers).
    here = os.path.dirname(os.path.abspath(__file__))
    kvp = os.path.normpath(os.path.join(here, "..", "..", "KVPolicy"))
    if kvp not in sys.path:
        sys.path.insert(0, kvp)
    from kv_policy.int4_cache_kv_route_a import (
        INT4CacheKVRouteA, _observe_steady_split)
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
    # clear_readskip_stats zeroes the cumulative diagnostics (real method, stub).
    stub2 = types.SimpleNamespace(
        _readskip_calls=5, _readskip_observe_steps=8, _readskip_steady_steps=120,
        _readskip_retained_tokens=132000, _readskip_seq_tokens=960000)
    INT4CacheKVRouteA.clear_readskip_stats(stub2)
    assert stub2._readskip_steady_steps == 0 and stub2._readskip_seq_tokens == 0

    # observe/steady split (real module helper): observe steps cost more.
    spl = _observe_steady_split(
        [10.0, 2.0, 11.0],
        [("retention", True, 8, 8), ("retention", False, 8, 1),
         ("retention", True, 8, 8)])
    assert spl["observe"]["n"] == 2 and spl["steady"]["n"] == 1, spl
    assert _observe_steady_split([1.0], [("off", None, 8, 8)]) == {}  # off not classified

    # The REAL accumulation glue (_readskip_active_positions) on stubs: observe
    # steps read all (retained==seq), steady steps skip, counters + meta track it.
    class _Cache:
        seq_len = 4096
        def block_attention_scores(self, query, block_size, use_kernel=False):
            sc = [0.0] * ((self.seq_len + block_size - 1) // block_size)
            sc[40] = 9.0
            return sc
    mgr = types.SimpleNamespace(
        _readskip_mode="retention", _readskip_calls=0, _readskip_block_size=32,
        _readskip_sink_tokens=64, _readskip_recent_tokens=512,
        _readskip_budget_tokens=512, _readskip_neighbor=1, _readskip_observe=3,
        _readskip_refresh=0, _readskip_decay=0.8, _readskip_kernel_scores=False,
        _readskip_controllers={}, _readskip_observe_steps=0, _readskip_steady_steps=0,
        _readskip_retained_tokens=0, _readskip_seq_tokens=0, _last_readskip_meta=None)
    c0 = _Cache()       # ONE instance -> ONE controller (keyed by id(cache)).
    for _ in range(8):  # Do NOT pass a throwaway _Cache() per iter and rely on
        # CPython recycling its id() — that's allocator-dependent (passes on some
        # boxes, gives 8 fresh controllers -> all "observe" on others).
        INT4CacheKVRouteA._readskip_active_positions(mgr, c0, query=object())
    assert mgr._readskip_observe_steps == 3 and mgr._readskip_steady_steps == 5
    sf = 1 - mgr._readskip_retained_tokens / mgr._readskip_seq_tokens
    assert 0.5 < sf < 0.99 and mgr._last_readskip_meta[0] == "retention", sf

    # score_noskip (Stage-A diagnostic): scores on the SAME cadence as retention
    # (pays the cost, advances the controller, records the would-be skip fraction)
    # but ALWAYS returns None -> read all, no gather. Quality == off by construction.
    scored = {"n": 0}
    class _CacheCount(_Cache):
        def block_attention_scores(self, query, block_size, use_kernel=False):
            scored["n"] += 1
            return super().block_attention_scores(query, block_size, use_kernel)
    mgr2 = types.SimpleNamespace(**{**mgr.__dict__})
    mgr2._readskip_mode = "score_noskip"
    mgr2._readskip_calls = 0; mgr2._readskip_controllers = {}
    mgr2._readskip_observe_steps = 0; mgr2._readskip_steady_steps = 0
    mgr2._readskip_retained_tokens = 0; mgr2._readskip_seq_tokens = 0
    cc = _CacheCount()                                  # one instance -> one controller
    rets = [INT4CacheKVRouteA._readskip_active_positions(mgr2, cc, query=object())
            for _ in range(8)]
    assert all(r is None for r in rets), "score_noskip must read all (None)"
    # scoring happens exactly on observe steps (cost paid on the normal cadence)
    assert scored["n"] == mgr2._readskip_observe_steps > 0, (scored, mgr2._readskip_observe_steps)
    assert mgr2._readskip_calls == 8 and mgr2._last_readskip_meta[0] == "score_noskip"
    # would-be skip fraction still recorded (safe offline replay) despite reading all
    assert mgr2._readskip_seq_tokens > 0 and mgr2._readskip_retained_tokens > 0

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
    ap.add_argument("--hf-overrides", default="",
                    help="JSON object passed to vLLM LLM(hf_overrides=...). Use to "
                         "inject rope_scaling (YaRN) for >native-window context, "
                         "e.g. the 48-64K read-skip crossover on Qwen2.5-7B: "
                         "'{\"rope_scaling\":{\"rope_type\":\"yarn\",\"factor\":2.0,"
                         "\"original_max_position_embeddings\":32768}}'")
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
                    help="comma list of modes to compare "
                         "(off/retain_all/retention/score_noskip); baseline is 'off' "
                         "when present. For the cost decomposition use "
                         "off,score_noskip,retain_all,retention: Δ% vs off gives "
                         "scoring overhead / gather-all tax / net respectively")
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
    ap.add_argument("--profile-ab", action="store_true",
                    help="paired per-section profiler: off vs retention per-step "
                         "cost by section (+ observe/steady split + skip fraction) "
                         "in one process, to attribute WHERE a gap is. SEPARATE "
                         "from --ab because profiling perturbs the tps timing.")
    ap.add_argument("--bf16-ref", action="store_true",
                    help="bf16 reference (gap #4): vanilla vLLM, no int4/read-skip, "
                         "same needle + decode-only timing. The absolute scale the "
                         "off<->retention paired delta sits against (separate engine).")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.profile_ab:
        return run_profile_ab(args)
    if args.bf16_ref:
        return run_bf16_ref(args)
    if args.ab:
        return run_ab(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
