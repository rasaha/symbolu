#!/usr/bin/env python3
# Phase 6K.16 — GPU validation gates for prefix caching (APC) on int4_protected.
#
# Runs the Tier-1 dequant-context prefill (kv_policy/phase6k16_prefix_prefill.py)
# against three gates, venv-vllm (vLLM 0.7.3 + int4_protected):
#
#   GATE-HITS       prefix-cache hits actually OCCUR in the apc run
#                   (cache_hit_blocks > 0 via the Phase 3A prefix_hit_probe) —
#                   otherwise the other gates are vacuous.
#   GATE-AGREEMENT  greedy outputs with APC on vs off agree (mean token
#                   agreement >= 0.90; report exact). NOT expected to be 1.0
#                   bit-exact: APC-off prefill attends FRESH bf16 context,
#                   APC-on attends DEQUANT(int4) context — the diff is the
#                   int4 quantization error on prefill attention only.
#   GATE-NEEDLE     a code buried INSIDE the cached prefix is retrieved in the
#                   apc run (and the noapc control) — the hard-tail check.
#
# Usage (pod, venv-vllm; Llama mask already calibrated):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
#   python Bench/scripts/phase6k16_prefix_gates.py --mode noapc --out /tmp/p6k16_noapc.json --model $M
#   python Bench/scripts/phase6k16_prefix_gates.py --mode apc   --out /tmp/p6k16_apc.json   --model $M
#   python Bench/scripts/phase6k16_prefix_gates.py --compare /tmp/p6k16_noapc.json /tmp/p6k16_apc.json
#   python Bench/scripts/phase6k16_prefix_gates.py --selftest        # CPU, no model

from __future__ import annotations

import argparse
import json
import os
import random
import string
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

BLOCK = 32
N_PREFIX_BLOCKS = 16          # shared prefix ~512 tokens => 16 cacheable blocks
AGREEMENT_GATE = 0.90


def _filler(n_sent, tag=""):
    return " ".join(
        f"Background note {tag}{i}: routine operations continued without incident."
        for i in range(n_sent)
    )


def build_workload(seed=1234):
    """Shared prefix (needle buried mid-prefix) + distinct suffix questions.
    Deterministic. Returns (prefix, code, questions)."""
    rng = random.Random(seed)
    code = "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    pre = _filler(18, "a")
    post = _filler(18, "b")
    prefix = (f"{pre} The vault access code is {code}. {post} ")
    questions = [
        "Summarize the document above in one sentence.",
        "How many distinct topics does the document cover? Answer briefly.",
        "Is the document about routine operations? Answer yes or no.",
        "Quote one sentence from the document verbatim.",
        "What is the overall tone of the document? One word.",
        "Does the document mention any incident? Answer yes or no.",
    ]
    return prefix, code, questions


def token_agreement(ref, test):
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


def _resolve_block_manager(llm):
    eng = llm.llm_engine
    cands = []
    sched = getattr(eng, "scheduler", None)
    if isinstance(sched, (list, tuple)) and sched:
        cands.append(sched[0])
    elif sched is not None:
        cands.append(sched)
    for s in cands:
        bm = getattr(s, "block_manager", None)
        if bm is not None:
            return bm
    return None


def run_mode(args):
    if args.mode == "apc":
        # Self-contained: the factory + backend guards honor this env.
        os.environ["INT4_PROTECTED_ALLOW_PREFIX_CACHING"] = "1"
        print("[p6k16] INT4_PROTECTED_ALLOW_PREFIX_CACHING=1 (Tier-1 path enabled)")
    import kv_policy.int4_protected  # noqa: F401  (registers backend)
    from kv_policy.int4_protected import Int4ProtectedLLM

    llm = Int4ProtectedLLM(
        model=args.model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_util,
        enable_prefix_caching=(args.mode == "apc"),
    )
    from vllm import SamplingParams
    sp = SamplingParams(temperature=0.0, max_tokens=args.gen)

    probe = None
    if args.mode == "apc":
        try:
            from kv_policy.prefix_hit_probe import install_prefix_hit_probe
            bm = _resolve_block_manager(llm)
            if bm is not None:
                probe = install_prefix_hit_probe(block_manager=bm, block_size=BLOCK)
                print("[p6k16] prefix_hit_probe installed")
            else:
                print("[p6k16] WARN: block_manager not found; GATE-HITS will be n/a")
        except Exception as e:  # probe is best-effort; gates B/C still run
            print(f"[p6k16] WARN: probe install failed: {type(e).__name__}: {e}")

    prefix, code, questions = build_workload()

    # 1) WARM: populates the prefix blocks (apc) — separate generate() call so
    #    the later calls can HIT them. Same call made in noapc for parity.
    warm = llm.generate([prefix + "Summarize the above in one sentence."], sp)
    warm_ids = list(warm[0].outputs[0].token_ids)
    hits_after_warm = probe.cache_hit_blocks if probe else None

    # 2) EQUIVALENCE prompts: shared prefix + distinct questions.
    outs = llm.generate([prefix + q for q in questions], sp)
    eq_ids = {str(i): list(o.outputs[0].token_ids) for i, o in enumerate(outs)}

    # 3) NEEDLE inside the cached prefix.
    nd = llm.generate(
        [prefix + "What is the vault access code? Answer with only the code."], sp)
    needle_text = nd[0].outputs[0].text
    needle_ids = list(nd[0].outputs[0].token_ids)

    hits_total = probe.cache_hit_blocks if probe else None
    payload = {
        "mode": args.mode, "model": args.model, "gen": args.gen,
        "code": code,
        "warm_ids": warm_ids,
        "eq_ids": eq_ids,
        "needle_text": needle_text,
        "needle_ids": needle_ids,
        "hits_after_warm": hits_after_warm,
        "hits_total": hits_total,
        "prefix_blocks_possible": N_PREFIX_BLOCKS,
    }
    Path(args.out).write_text(json.dumps(payload))
    print(f"[p6k16] mode={args.mode} wrote {args.out}")
    if args.mode == "apc":
        print(f"[p6k16] cache_hit_blocks total={hits_total} (after warm={hits_after_warm})")
    return 0


def compare(noapc_path, apc_path):
    a = json.loads(Path(noapc_path).read_text())
    b = json.loads(Path(apc_path).read_text())
    assert a["mode"] == "noapc" and b["mode"] == "apc", "pass files as: noapc apc"
    code = a["code"]

    print("\n" + "=" * 78)
    print(f"PHASE 6K.16 GATES — APC on int4_protected ({b['model']})")
    print("=" * 78)

    # GATE-HITS
    hits = b.get("hits_total")
    if hits is None:
        print("GATE-HITS       n/a (probe unavailable) — check engine logs / rerun")
        gate_hits = None
    else:
        gate_hits = hits > 0
        print(f"GATE-HITS       {'PASS' if gate_hits else 'FAIL'}   "
              f"cache_hit_blocks={hits}")

    # GATE-AGREEMENT
    agrees = []
    for k in sorted(a["eq_ids"], key=int):
        ag, pre = token_agreement(a["eq_ids"][k], b["eq_ids"].get(k, []))
        agrees.append(ag)
        print(f"  prompt[{k}] agreement={ag:.3f} prefix={pre}")
    mean_ag = sum(agrees) / max(1, len(agrees))
    gate_ag = mean_ag >= AGREEMENT_GATE
    print(f"GATE-AGREEMENT  {'PASS' if gate_ag else 'FAIL'}   mean={mean_ag:.4f} "
          f"(gate >= {AGREEMENT_GATE}; NOT expected 1.0 — apc context is "
          f"dequant-int4, noapc context is fresh bf16)")

    # GATE-NEEDLE
    hit_apc = code in b["needle_text"]
    hit_no = code in a["needle_text"]
    gate_nd = hit_apc and hit_no
    print(f"GATE-NEEDLE     {'PASS' if gate_nd else 'FAIL'}   "
          f"apc={'HIT' if hit_apc else 'MISS'} noapc={'HIT' if hit_no else 'MISS'} "
          f"(code={code}; apc answered: {b['needle_text'][:40]!r})")

    all_known = [g for g in (gate_hits, gate_ag, gate_nd) if g is not None]
    verdict = all(all_known) and gate_hits is not None
    print("-" * 78)
    print("VERDICT:", "ALL GATES PASS — flip the factory default per the plan doc"
          if verdict else "NOT PASSED — keep the guard; debug per plan doc")
    print("=" * 78)
    return 0 if verdict else 1


def selftest():
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("phase6k16_prefix_gates selftest")
    p1, c1, q1 = build_workload()
    p2, c2, _ = build_workload()
    check("workload deterministic", p1 == p2 and c1 == c2)
    check("code embedded in prefix", c1 in p1)
    check("prefix long enough to cache",
          len(p1.split()) > N_PREFIX_BLOCKS * 2)  # >> BLOCK tokens of filler
    check("6 distinct questions", len(set(q1)) == 6)
    ag, pre = token_agreement([1, 2, 3, 4], [1, 2, 9, 4])
    check("agreement 3/4, prefix 2", abs(ag - 0.75) < 1e-9 and pre == 2)
    check("empty agreement", token_agreement([], [1]) == (0.0, 0))
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 6K.16 APC gates (vLLM 0.7.3)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mode", choices=["apc", "noapc"])
    ap.add_argument("--compare", nargs=2, metavar=("NOAPC", "APC"))
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--gen", type=int, default=32)
    ap.add_argument("--out", default="/tmp/p6k16_out.json")
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
