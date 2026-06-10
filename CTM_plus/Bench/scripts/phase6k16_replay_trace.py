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

# Cross-mode comparison is SEMANTIC, not raw: eager and graphs differ
# legitimately in (a) slot numbers (capture dummies consume slots first),
# (b) SeqState ints (graphs: pool canonical, ints stale by design),
# (c) sync timing (eager syncs inside the forward, after the pre dump).
# What MUST match per (live_sids, seq_lens) step: the step INPUTS
# (slot_mapping, block-table tails) and the post-step SEMANTIC state —
# pool [count, block, seq_pos] per sid, stage content hash per sid, and
# finalized-block bytes at crossings. presync/postsync stay in the dump
# for human reading but are excluded from the cross-diff.
VALUE_FIELDS = ("is_decode", "slot_mapping", "bt_tail")
POST_FIELDS = ("counters_post", "stage_sig", "finalized")
ID_FIELDS = ("pool_ids", "impl0_slot_buf_id")


def _norm_post(r):
    """Mode-invariant view of a post record."""
    out = {}
    c = r.get("counters_post") or {}
    out["pool"] = {sid: (v or {}).get("pool") for sid, v in c.items()}
    sg = r.get("stage_sig") or {}
    out["stage_sha"] = {sid: (v or {}).get("sha1") for sid, v in sg.items()}
    out["stage_norm"] = {sid: (v or {}).get("norm") for sid, v in sg.items()}
    fin = r.get("finalized") or {}
    out["finalized"] = {
        sid: {"block": (v or {}).get("block"),
              "packed_sha": ((v or {}).get("packed_k") or {}).get("sha1"),
              "scale_sha": ((v or {}).get("k_scale") or {}).get("sha1")}
        for sid, v in fin.items()}
    # v4: the replayed READ's transient output — per-row last-block view
    # content (the spliced tail the kernel actually consumed) + the read's
    # cache_seqlens/slot buffer VALUES. Rows with seq<=0 are padding.
    vt = r.get("view_tail") or {}
    out["view_tail"] = {
        row: {"last_block": (v or {}).get("last_block"),
              "k_int4_sha": ((v or {}).get("k_int4") or {}).get("sha1"),
              "k_int4_norm": ((v or {}).get("k_int4") or {}).get("norm"),
              "k_scale_sha": ((v or {}).get("k_scale") or {}).get("sha1")}
        for row, v in vt.items()}
    csl = r.get("read_cache_seqlens")
    out["read_cache_seqlens"] = [s for s in (csl or []) if s > 0]
    return out


def _align_key(r):
    sids = r.get("live_sids")
    sl = r.get("seq_lens")
    if sids is None or sl is None:
        return None
    return (tuple(sorted(str(s) for s in sids)), tuple(sl))


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

    # 2. Cross-trace value diff, aligned by (live_sids, seq_lens) — robust
    # to step-count skew (graphs init adds steps) and overlapping seq-len
    # ranges between the warm and hit sequences.
    e_keyed = {}
    for s in sorted(e_pre):
        k = _align_key(e_pre[s])
        if k is not None and e_pre[s].get("is_decode") and k not in e_keyed:
            e_keyed[k] = s
    g_keyed = {}
    for s in sorted(g_pre):
        k = _align_key(g_pre[s])
        if k is not None and g_pre[s].get("is_decode") and k not in g_keyed:
            g_keyed[k] = s
    common = [k for k in g_keyed if k in e_keyed]
    common.sort(key=lambda k: g_keyed[k])
    print(f"  aligned decode steps: {len(common)} "
          f"(eager-only={len(e_keyed) - len(common)}, "
          f"graphs-only={len(g_keyed) - len(common)})")
    first = None
    for k in common:
        es, gs = e_keyed[k], g_keyed[k]
        diffs = []
        _diff(e_pre[es], g_pre[gs], "pre", VALUE_FIELDS, diffs)
        ep, gp = e_post.get(es), g_post.get(gs)
        if ep and gp:
            _diff(_norm_post(ep), _norm_post(gp), "post",
                  ("pool", "stage_sha", "stage_norm", "finalized",
                   "read_cache_seqlens", "view_tail"), diffs)
        if diffs:
            first = (k, es, gs, diffs)
            break
    if first is None:
        print(f"\n  NO DIVERGENCE across {len(common)} aligned decode steps — "
              f"the traced state surface is identical; the bug is OUTSIDE it "
              f"(extend the surface).")
    else:
        k, es, gs, diffs = first
        print(f"\n  FIRST DIVERGENCE at key sids={k[0]} seq_lens={k[1]} "
              f"(eager step {es}, graphs step {gs}):")
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
           "live_sids": [1],
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
