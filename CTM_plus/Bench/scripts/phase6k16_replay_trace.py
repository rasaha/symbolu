#!/usr/bin/env python3
# Phase 6K.16d — replay-trace A/B for the graphs+APC tail bug.
#
# Runs the SAME hit-sequence workload under eager and under CUDA graphs with
# INT4_PROTECTED_REPLAY_TRACE armed (host-window dumps from the 6B.2 hook:
# pre/post counters, stage signatures, buffer identities, allocation events,
# finalized-block bytes). --compare diffs the two traces step-by-step and
# prints the FIRST diverging (step, field) — the frozen/stale quantity.
#
# Usage (pod, venv-vllm):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
#   python Bench/scripts/phase6k16_replay_trace.py --mode eager  --trace /tmp/rt_eager.jsonl  --model $M
#   python Bench/scripts/phase6k16_replay_trace.py --mode graphs --trace /tmp/rt_graphs.jsonl --model $M
#   python Bench/scripts/phase6k16_replay_trace.py --compare /tmp/rt_eager.jsonl /tmp/rt_graphs.jsonl
#   python Bench/scripts/phase6k16_replay_trace.py --selftest   # CPU

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break

# Fields whose VALUES must match step-for-step between eager and graphs
# (until the first true divergence). Identity fields (ids) are compared
# WITHIN a trace for stability, not across traces (addresses differ).
VALUE_FIELDS = ("is_decode", "seq_lens", "slot_mapping", "bt_tail",
                "live_sids", "stash_seq_ids",
                "counters_presync", "counters_postsync")
POST_FIELDS = ("counters_post", "stage_sig", "finalized")
ID_FIELDS = ("pool_ids", "impl0_slot_buf_id", "stash_slot_idx_id",
             "seq_lens_id", "bt_id")


def run_mode(args):
    os.environ["INT4_PROTECTED_REPLAY_TRACE"] = args.trace
    Path(args.trace).unlink(missing_ok=True)
    import kv_policy.int4_protected  # noqa: F401
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from phase6k16_prefix_gates import build_workload
    prefix, code, _ = build_workload()

    kw = dict(model=args.model, max_model_len=args.max_model_len,
              gpu_memory_utilization=args.gpu_util,
              enable_prefix_caching=True)
    if args.mode == "graphs":
        os.environ["INT4_PROTECTED_APC_ALLOW_GRAPHS"] = "1"
        kw["enforce_eager"] = False
        print("[rt] graphs mode (APC_ALLOW_GRAPHS=1 — exercising the open edge)")
    else:
        kw["enforce_eager"] = True
    llm = Int4ProtectedLLM(**kw)
    sp = SamplingParams(temperature=0.0, max_tokens=args.gen)
    # warm (populates the prefix cache), then ONE hit sequence; gen long
    # enough to guarantee >=1 block crossing during decode.
    llm.generate([prefix + "Summarize the above in one sentence."], sp)
    out = llm.generate(
        [prefix + "What is the vault access code? Answer with only the code."],
        sp)
    txt = out[0].outputs[0].text
    n = sum(1 for _ in open(args.trace)) if Path(args.trace).exists() else 0
    print(f"[rt] mode={args.mode} trace={args.trace} records={n}")
    print(f"[rt] needle answered: {txt[:60]!r}  (code={code}, "
          f"{'HIT' if code in txt else 'MISS'})")
    return 0


def _load(path):
    pre, post = {}, {}
    for line in open(path):
        r = json.loads(line)
        (pre if r.get("phase") == "pre" else post)[r["step"]] = r
    return pre, post


def _diff(a, b, label, fields, out):
    for f in fields:
        va, vb = a.get(f), b.get(f)
        if va != vb:
            out.append((label, f, va, vb))


def compare(eager_path, graphs_path):
    e_pre, e_post = _load(eager_path)
    g_pre, g_post = _load(graphs_path)
    print("\n" + "=" * 78)
    print(f"REPLAY-TRACE DIFF — eager({len(e_pre)} steps) vs "
          f"graphs({len(g_pre)} steps)")
    print("=" * 78)

    # 1. WITHIN-trace identity stability (the object-identity check).
    for name, pre in (("eager", e_pre), ("graphs", g_pre)):
        ids0, drift = None, []
        reallocs = []
        for s in sorted(pre):
            r = pre[s]
            cur = {f: r.get(f) for f in ID_FIELDS}
            if ids0 is None:
                ids0 = cur
            elif cur != ids0:
                drift.append((s, {f: (ids0[f], cur[f]) for f in ID_FIELDS
                                  if cur[f] != ids0[f]}))
            for ev in r.get("alloc_events") or []:
                reallocs.append((s, ev))
        print(f"  [{name}] buffer identities: "
              f"{'STABLE' if not drift else f'DRIFT at {drift[:2]}'}")
        late = [(s, ev) for s, ev in reallocs if s > 0]
        print(f"  [{name}] alloc events after step 0: "
              f"{'none' if not late else late[:3]}")

    # 2. Cross-trace value diff, step-aligned on DECODE steps.
    e_dec = [s for s in sorted(e_pre) if e_pre[s].get("is_decode")]
    g_dec = [s for s in sorted(g_pre) if g_pre[s].get("is_decode")]
    n = min(len(e_dec), len(g_dec))
    first = None
    for k in range(n):
        diffs = []
        _diff(e_pre[e_dec[k]], g_pre[g_dec[k]], "pre", VALUE_FIELDS, diffs)
        ep, gp = e_post.get(e_dec[k]), g_post.get(g_dec[k])
        if ep and gp:
            _diff(ep, gp, "post", POST_FIELDS, diffs)
        if diffs:
            first = (k, diffs)
            break
    if first is None:
        print(f"\n  NO DIVERGENCE across {n} aligned decode steps — the "
              f"traced state surface is identical; the bug is OUTSIDE it "
              f"(extend the surface).")
    else:
        k, diffs = first
        print(f"\n  FIRST DIVERGENCE at aligned decode step {k} "
              f"(eager step {e_dec[k]}, graphs step {g_dec[k]}):")
        for label, f, va, vb in diffs[:6]:
            print(f"    [{label}] {f}:")
            print(f"        eager : {json.dumps(va)[:160]}")
            print(f"        graphs: {json.dumps(vb)[:160]}")
        print("\n  -> the first differing field above is the frozen/stale "
              "quantity (or its immediate downstream).")
    print("=" * 78)
    return 0 if first is None else 1


def selftest():
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("phase6k16_replay_trace selftest")
    a, b = "/tmp/_rt_a.jsonl", "/tmp/_rt_b.jsonl"
    rec = {"step": 0, "phase": "pre", "is_decode": True, "seq_lens": [500],
           "counters_presync": {"1": {"slot": 0, "pool": [5, 14, 0],
                                      "state_ints": [5, 14]}},
           "pool_ids": {"k_stage_pool": 111}}
    post = {"step": 0, "phase": "post",
            "counters_post": {"1": {"slot": 0, "pool": [6, 14, 1],
                                    "state_ints": [5, 14]}}}
    for p in (a, b):
        with open(p, "w") as f:
            f.write(json.dumps(rec) + "\n")
            f.write(json.dumps(post) + "\n")
    check("identical traces -> no divergence", compare(a, b) == 0)
    bad = dict(post)
    bad["counters_post"] = {"1": {"slot": 0, "pool": [0, -1, 1],
                                  "state_ints": [5, 14]}}
    with open(b, "w") as f:
        f.write(json.dumps(rec) + "\n")
        f.write(json.dumps(bad) + "\n")
    check("counter divergence detected", compare(a, b) == 1)
    # hook trace helpers importable + writer rt helpers behave
    from kv_policy.phase5b_4c_paged_writer import (
        rt_path, rt_alloc_event, rt_drain_events,
    )
    os.environ.pop("INT4_PROTECTED_REPLAY_TRACE", None)
    rt_alloc_event("x", object())          # disarmed -> no-op
    check("disarmed alloc_event is no-op", rt_drain_events() == [])
    os.environ["INT4_PROTECTED_REPLAY_TRACE"] = "/tmp/_rt.jsonl"

    class _T:
        shape = (4,)
    rt_alloc_event("slot_idx_buf", _T(), "grew_to=16")
    ev = rt_drain_events()
    check("armed alloc_event recorded", len(ev) == 1
          and ev[0]["kind"] == "slot_idx_buf")
    os.environ.pop("INT4_PROTECTED_REPLAY_TRACE", None)
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="6K.16d replay-trace A/B")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mode", choices=["eager", "graphs"])
    ap.add_argument("--compare", nargs=2, metavar=("EAGER", "GRAPHS"))
    ap.add_argument("--trace", default="/tmp/rt.jsonl")
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--gen", type=int, default=40)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.compare:
        return compare(*args.compare)
    if args.mode:
        return run_mode(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
