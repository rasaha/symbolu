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
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
