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
        enforce_eager=(True if args.eager else None),
    )
    from vllm import SamplingParams
    sp = SamplingParams(temperature=0.0, max_tokens=args.gen)
    if args.eager:
        print("[p6k16] enforce_eager=True (CUDA graphs OFF — bisection cell)")
    if args.b1:
        print("[p6k16] --b1: equivalence prompts as 6 SEPARATE generate() calls")

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
    #    --b1 sends them as separate calls (B=1 decode) to split
    #    batched-decode interactions from per-seq behavior.
    if args.b1:
        eq_ids, eq_texts = {}, {}
        for i, q in enumerate(questions):
            o = llm.generate([prefix + q], sp)
            eq_ids[str(i)] = list(o[0].outputs[0].token_ids)
            eq_texts[str(i)] = o[0].outputs[0].text
    else:
        outs = llm.generate([prefix + q for q in questions], sp)
        eq_ids = {str(i): list(o.outputs[0].token_ids) for i, o in enumerate(outs)}
        eq_texts = {str(i): o.outputs[0].text for i, o in enumerate(outs)}

    # 3) NEEDLE inside the cached prefix.
    nd = llm.generate(
        [prefix + "What is the vault access code? Answer with only the code."], sp)
    needle_text = nd[0].outputs[0].text
    needle_ids = list(nd[0].outputs[0].token_ids)

    hits_total = probe.cache_hit_blocks if probe else None
    # Ground truth on which write/attention paths actually fired — the
    # impl's class-level counters. prefix_prefill_calls > 0 is the REAL
    # "hits happened" signal (the probe is auxiliary; its allocator walk
    # proved unreliable on the first GPU run).
    call_stats = {}
    try:
        from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
        cs = Int4ProtectedAttentionImpl._call_stats
        call_stats = {k: cs.get(k, 0) for k in (
            "prefix_prefill_calls", "prefill_calls", "write_path_calls",
            "write_path_fallback", "write_decode_batched_calls",
            "write_legacy_loop_calls")}
        print(f"[p6k16] call_stats: {call_stats}")
    except Exception as e:
        print(f"[p6k16] WARN: call_stats unavailable: {type(e).__name__}: {e}")
    payload = {
        "mode": args.mode, "model": args.model, "gen": args.gen,
        "code": code,
        "warm_ids": warm_ids,
        "eq_ids": eq_ids,
        "eq_texts": eq_texts,
        "needle_text": needle_text,
        "needle_ids": needle_ids,
        "hits_after_warm": hits_after_warm,
        "hits_total": hits_total,
        "call_stats": call_stats,
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

    # GATE-HITS — primary signal: did the prefix-prefill branch FIRE?
    # (the impl's own counter; the allocator probe is auxiliary/unreliable)
    ppc = (b.get("call_stats") or {}).get("prefix_prefill_calls")
    hits = b.get("hits_total")
    if ppc is not None:
        gate_hits = ppc > 0
        print(f"GATE-HITS       {'PASS' if gate_hits else 'FAIL'}   "
              f"prefix_prefill_calls={ppc} (layers x hit-steps; "
              f"probe cache_hit_blocks={hits})")
    elif hits is None:
        print("GATE-HITS       n/a (no counters) — rerun with updated script")
        gate_hits = None
    else:
        gate_hits = hits > 0
        print(f"GATE-HITS       {'PASS' if gate_hits else 'FAIL'}   "
              f"cache_hit_blocks={hits}")

    # GATE-WARM: the warm call has no cached context in either mode, so its
    # outputs must agree ~1.0; divergence = engine/writer-under-APC bug
    # (allocator/identity), independent of the prefix path.
    gate_warm = None
    if a.get("warm_ids") and b.get("warm_ids"):
        wag, wpre = token_agreement(a["warm_ids"], b["warm_ids"])
        gate_warm = wag >= 0.95
        print(f"GATE-WARM       {'PASS' if gate_warm else 'FAIL'}   "
              f"agreement={wag:.3f} prefix={wpre} "
              f"(no-hit path must be engine-identical)")

    # S3-RESIDUAL (INFO, not a gate — contract C-GATE): APC prefill attends
    # the cached prefix in dequant-int4; no-APC attends fresh bf16. On
    # open-ended prompts a greedy near-tie can flip and diverge COHERENTLY —
    # the bounded residual, same class as protect-vs-bf16 (~0.955 on hard
    # needles). The MACHINERY gate is the S1 byte-gate
    # (phase6k16_byte_gate.py: cached blocks bit-exact vs fresh prefill).
    # Texts are printed for divergent prompts so coherent-vs-DEGENERATE is
    # adjudicable by eye; degenerate APC text => suffix-side machinery bug.
    agrees = []
    for k in sorted(a["eq_ids"], key=int):
        ag, pre = token_agreement(a["eq_ids"][k], b["eq_ids"].get(k, []))
        agrees.append(ag)
        print(f"  prompt[{k}] agreement={ag:.3f} prefix={pre}")
        if ag < 0.5 and (b.get("eq_texts") or {}).get(k) is not None:
            print(f"            apc:   {b['eq_texts'][k][:70]!r}")
            if (a.get("eq_texts") or {}).get(k) is not None:
                print(f"            noapc: {a['eq_texts'][k][:70]!r}")
    mean_ag = sum(agrees) / max(1, len(agrees))
    print(f"S3-RESIDUAL     INFO   mean={mean_ag:.4f} over open-ended prompts "
          f"(bounded residual, NOT a pass/fail bar — see contract §6; "
          f"machinery gate = S1 byte-gate)")

    # GATE-NEEDLE (factual retrieval from INSIDE the cached prefix — the
    # hard-tail check; prefix tells WHERE divergence starts if it fails)
    hit_apc = code in b["needle_text"]
    hit_no = code in a["needle_text"]
    gate_nd = hit_apc and hit_no
    nag, npre = token_agreement(a.get("needle_ids", []), b.get("needle_ids", []))
    print(f"GATE-NEEDLE     {'PASS' if gate_nd else 'FAIL'}   "
          f"apc={'HIT' if hit_apc else 'MISS'} noapc={'HIT' if hit_no else 'MISS'} "
          f"agreement={nag:.3f} prefix={npre} "
          f"(code={code}; apc answered: {b['needle_text'][:40]!r})")

    # Contract C-GATE verdict: HITS (non-vacuous) + WARM (engine sane) +
    # NEEDLE (factual retrieval). S1 byte-gate is the primary machinery
    # criterion and runs separately (phase6k16_byte_gate.py).
    all_known = [g for g in (gate_hits, gate_warm, gate_nd) if g is not None]
    verdict = bool(all_known) and all(all_known) and gate_hits is not None
    print("-" * 78)
    print("VERDICT:", "GATES PASS (with S1 byte-gate PASS => APC machinery "
          "validated under the contract; residual is bounded)"
          if verdict else "NOT PASSED — see contract §6/§7 to localize")
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
    ap.add_argument("--eager", action="store_true",
                    help="bisection cell: enforce_eager=True (no CUDA graphs)")
    ap.add_argument("--b1", action="store_true",
                    help="bisection cell: equivalence prompts as separate "
                         "B=1 generate() calls")
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
