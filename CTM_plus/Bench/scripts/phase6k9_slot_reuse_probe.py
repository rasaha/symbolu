#!/usr/bin/env python3
# Phase 6K.9 — does int4 decode collapse ACCUMULATE across sequential requests
# in one process (stale writer / slot / staging state)?
#
# 6K.8 showed the residual pérdida-collapse is non-deterministic, hits BOTH
# eager and graph and BOTH naive and protected, and that in ONE eager process
# the "capital ×6" block was clean but a LATER block collapsed — i.e. it seems
# to grow with request history. This probe isolates that:
#
#   * run a pool of short prompts SEQUENTIALLY in one Int4ProtectedLLM process
#   * per request record: idx, prompt, N, output, collapse flag, and
#     (best-effort) the writer pool state (active slots / max seq_pos / max
#     stage_count) so we can watch state drift
#   * Phase A = no reset ; Phase B = reset the writer aux pools before each
#     request. If B's collapse rate << A's, stale writer state IS the cause.
#   * matrix driver compares: {naive,protected} × {FUSED 0,1} × {eager T,F}
#
# The reset zeroes the writer's staging + sentinel + seq_pos pools (and clears
# SeqStates) — NOT vLLM's block tables — to force "fresh sequence" state.
#
# Usage:
#   # one config (worker):
#   CELL=protected PHASE6E_FUSED_WRITER=1 ENFORCE_EAGER=1 \
#     python CTM_plus/Bench/scripts/phase6k9_slot_reuse_probe.py --worker
#   # full matrix (spawns one subprocess per config):
#   python CTM_plus/Bench/scripts/phase6k9_slot_reuse_probe.py 2>&1 | tee /tmp/phase6k9.log
#
# Env (worker): CELL=naive|protected  ENFORCE_EAGER=0|1
#   PHASE6E_FUSED_WRITER=0|1 (inherited)  N6K9=<requests per phase>
#   NAIVE_MASK_PATH=...  (driver) MATRIX_CELLS / MATRIX_FUSED / MATRIX_EAGER

import json
import os
import subprocess
import sys
from pathlib import Path

PROMPTS = [
    "List three primary colors and their names.",
    "What is the capital of France? Answer in one sentence.",
    "In one sentence, explain what photosynthesis is and why it matters.",
    "Give me a one-line definition of machine learning in plain English.",
    "Summarize the water cycle in one short sentence for a child.",
    "Name two programming languages and one use case for each, briefly.",
    "What is 17 plus 26? Answer with just the number.",
    "Who wrote Romeo and Juliet? Answer in one sentence.",
    "Explain gravity in one simple sentence.",
    "Write a one-sentence description of the ocean.",
]
NAIVE_MASK_DEFAULT = "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_naive.pt"


def _collapsed(text: str) -> bool:
    words = text.split()
    if len(words) < 6:
        return False
    distinct_ratio = len(set(words)) / len(words)
    longest = cur = 1
    for a, b in zip(words, words[1:]):
        cur = cur + 1 if a == b else 1
        longest = max(longest, cur)
    top_count = max((words.count(w) for w in set(words)), default=0)
    return distinct_ratio < 0.4 or longest >= 4 or top_count >= 6


# ---------------------------------------------------------------- writer access
def _locate_writers(llm):
    """Best-effort: return {layer_idx: PagedKVWriter} for allocated writers."""
    writers = {}
    try:
        model = llm.llm_engine.model_executor.driver_worker.model_runner.model
    except Exception:
        return writers
    for mod in model.modules():
        impl = getattr(getattr(mod, "attn", None), "impl", None) or getattr(mod, "impl", None)
        if impl is None or type(impl).__name__ != "Int4ProtectedAttentionImpl":
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is not None and getattr(w, "_allocated", False):
            writers.setdefault(getattr(w, "layer_idx", len(writers)), w)
    return writers


def _pool_state(writers):
    """Compact summary of layer-0 writer pool state (drift indicator)."""
    if not writers:
        return None
    w = writers[min(writers)]
    try:
        import torch  # noqa
        bid = w._k_stage_block_id_pool
        return {
            "active_slots": int((bid != -1).sum()) if bid is not None else -1,
            "max_seq_pos": int(w._seq_pos_pool.max()) if w._seq_pos_pool is not None else -1,
            "max_stage_count": int(w._k_stage_count_pool.max()) if w._k_stage_count_pool is not None else -1,
        }
    except Exception:
        return None


def _reset_writers(writers) -> int:
    n = 0
    for w in writers.values():
        try:
            if w._k_stage_block_id_pool is not None:
                w._k_stage_block_id_pool.fill_(-1)
            if w._k_stage_count_pool is not None:
                w._k_stage_count_pool.zero_()
            if w._seq_pos_pool is not None:
                w._seq_pos_pool.zero_()
            if w._k_stage_pool is not None:
                w._k_stage_pool.zero_()
            try:
                w._seq_states.clear()
            except Exception:
                pass
            n += 1
        except Exception:
            pass
    return n


# ---------------------------------------------------------------------- worker
def run_worker() -> int:
    cell = os.environ.get("CELL", "protected")
    eager = os.environ.get("ENFORCE_EAGER", "1").strip() in ("1", "true", "yes")
    fused = os.environ.get("PHASE6E_FUSED_WRITER", "1")
    n_req = int(os.environ.get("N6K9", str(len(PROMPTS))))
    # Let our explicit enforce_eager win over any inherited force-eager switch.
    os.environ.pop("PHASE6B3_FORCE_EAGER", None)

    # Per-cell knobs MUST be set before the writer's lazy-alloc (first prefill).
    if cell == "naive":
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "1"
        os.environ["PROTECT_MASK_PATH"] = os.environ.get("NAIVE_MASK_PATH", NAIVE_MASK_DEFAULT)
    else:
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "0"
        os.environ.pop("PROTECT_MASK_PATH", None)  # default calibrated 4pct

    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    tag = f"cell={cell} fused={fused} eager={eager}"
    print(f"\n[6k9 worker] {tag}  n_req={n_req}", flush=True)
    llm = Int4ProtectedLLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=8192,
        gpu_memory_utilization=0.5, max_num_seqs=8, enforce_eager=eager,
    )
    sp = SamplingParams(temperature=0.0, max_tokens=24)

    def gen(p):
        o = llm.generate([p], sp)[0]
        return len(o.prompt_token_ids), o.outputs[0].text

    seq = [PROMPTS[i % len(PROMPTS)] for i in range(n_req)]
    writers = {}

    def run_phase(label, reset_each):
        recs = []
        nonlocal writers
        for i, p in enumerate(seq):
            if reset_each and writers:
                _reset_writers(writers)
            n_in, text = gen(p)
            if not writers:
                writers = _locate_writers(llm)
            recs.append({"i": i, "n": n_in, "collapsed": _collapsed(text),
                         "text": text[:70], "pool": _pool_state(writers)})
            print(f"  [{label}] req#{i:>2} N={n_in:>3} "
                  f"[{'COLLAPSE' if recs[-1]['collapsed'] else 'ok':8s}] "
                  f"pool={recs[-1]['pool']} {text[:60]!r}", flush=True)
        return recs

    print(f"\n--- Phase A (NO reset) — {tag} ---")
    A = run_phase("A", reset_each=False)
    print(f"\n--- Phase B (reset writer pools before each) — {tag} ---")
    B = run_phase("B", reset_each=True)

    def rate(recs):
        return sum(r["collapsed"] for r in recs) / max(1, len(recs))

    def first_collapse(recs):
        for r in recs:
            if r["collapsed"]:
                return r["i"]
        return -1

    half = max(1, len(A) // 2)
    summary = {
        "cell": cell, "fused": fused, "eager": eager,
        "writers_found": len(writers),
        "A_collapse_rate": round(rate(A), 3),
        "A_first_collapse_idx": first_collapse(A),
        "A_firsthalf_rate": round(rate(A[:half]), 3),
        "A_secondhalf_rate": round(rate(A[half:]), 3),
        "B_collapse_rate_reset": round(rate(B), 3),
        "reset_helps": rate(B) < rate(A) - 0.1,
        "accumulates": rate(A[half:]) > rate(A[:half]) + 0.1,
    }
    out_path = os.environ.get("OUTPUT", f"/tmp/phase6k9_{cell}_fused{fused}_eager{int(eager)}.json")
    Path(out_path).write_text(json.dumps({"summary": summary, "A": A, "B": B}, indent=2))
    print(f"\n[6k9 worker] SUMMARY {tag}: {summary}")
    print(f"[6k9 worker] wrote {out_path}\n", flush=True)
    return 0


# ---------------------------------------------------------------------- driver
def run_driver() -> int:
    cells = os.environ.get("MATRIX_CELLS", "protected,naive").split(",")
    fused = os.environ.get("MATRIX_FUSED", "1,0").split(",")
    eagers = os.environ.get("MATRIX_EAGER", "1,0").split(",")
    naive_mask = Path(os.environ.get("NAIVE_MASK_PATH", NAIVE_MASK_DEFAULT))
    if "naive" in cells and not naive_mask.exists():
        print(f"FAIL: naive mask not found at {naive_mask} "
              f"(run make_phase6j_naive_protect_mask.py). Set NAIVE_MASK_PATH or drop 'naive'.")
        return 2

    rows = []
    for c in cells:
        for f in fused:
            for e in eagers:
                out = f"/tmp/phase6k9_{c}_fused{f}_eager{e}.json"
                env = dict(os.environ)
                env.update({"CELL": c, "PHASE6E_FUSED_WRITER": f, "ENFORCE_EAGER": e,
                            "OUTPUT": out, "NAIVE_MASK_PATH": str(naive_mask)})
                env.pop("PHASE6B3_FORCE_EAGER", None)
                print(f"\n=== 6k9 driver: cell={c} fused={f} eager={e} ===", flush=True)
                subprocess.run([sys.executable, __file__, "--worker"], env=env, check=False)
                try:
                    rows.append(json.loads(Path(out).read_text())["summary"])
                except Exception as exc:
                    rows.append({"cell": c, "fused": f, "eager": e, "error": str(exc)[:60]})

    print("\n" + "=" * 92)
    print("PHASE 6K.9 — collapse accumulation matrix")
    print("=" * 92)
    print(f"  {'cell':>10} {'fused':>5} {'eager':>5} | {'A_rate':>6} {'A_1st':>5} "
          f"{'A_h1':>5} {'A_h2':>5} | {'B(reset)':>8} {'reset_helps':>11} {'accum':>6}")
    print("  " + "-" * 88)
    for r in rows:
        if "error" in r:
            print(f"  {r['cell']:>10} {r['fused']:>5} {r['eager']:>5} | ERROR {r['error']}")
            continue
        print(f"  {r['cell']:>10} {r['fused']:>5} {str(r['eager']):>5} | "
              f"{r['A_collapse_rate']:>6} {r['A_first_collapse_idx']:>5} "
              f"{r['A_firsthalf_rate']:>5} {r['A_secondhalf_rate']:>5} | "
              f"{r['B_collapse_rate_reset']:>8} {str(r['reset_helps']):>11} {str(r['accumulates']):>6}")
    print("\n  READ:")
    print("   * accum=True (A_h2 > A_h1)  -> collapse GROWS with request history (stale state).")
    print("   * reset_helps=True          -> zeroing writer pools between reqs clears it")
    print("     => stale writer/slot/staging state is the cause (mode-independent).")
    print("   * compare eager vs graph rows for the same cell/fused: graph-only extra")
    print("     collapse = capture/precapture-hook init on top of the shared stale-state bug.")
    print("=" * 92 + "\n", flush=True)
    return 0


def main() -> int:
    if "--worker" in sys.argv:
        return run_worker()
    return run_driver()


if __name__ == "__main__":
    sys.exit(main())
