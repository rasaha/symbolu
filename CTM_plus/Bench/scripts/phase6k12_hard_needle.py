#!/usr/bin/env python3
# Phase 6K.12 — HARDER needle eval (de-saturates the easy needle test).
#
# Clean post-fix 6J showed naive int4 already at ceiling on the easy needle
# (0.96-1.00), so the needle gate can't discriminate the protect mask. This
# eval stresses retrieval so naive drops off ceiling and a protect advantage
# (if any) can show. Modes:
#   multi      — several labelled codes at different depths; ask for ONE by label
#                (selective attention among many).
#   distractor — one real code + look-alike codes (1-char edits) scattered;
#                ask for the real one by its unique label (exact V discrimination).
#   conflict   — "code is X" early, "code updated to Y" later; ask CURRENT code
#                (recency / position).
#   qa         — bury a fact ("guard is <Name>, door code <code>"); ask a
#                question needing it (retrieval + output format).
#
# Per item we score exact-match and a failure bucket:
#   HIT / NEAR_V (attended, near-miss/look-alike -> V precision) /
#   MISS_K (no answer-shaped output -> K) / COLLAPSE / FORMAT (right content,
#   leaked the wrong field too).
#
# Cells: bf16 / naive / protected (same env knobs as bench_phase6j).
#
# Usage:
#   python CTM_plus/Bench/scripts/phase6k12_hard_needle.py --selftest        # CPU, no model
#   # one cell:
#   CELL=protected ENFORCE_EAGER=1 PHASE6E_FUSED_WRITER=1 \
#     python CTM_plus/Bench/scripts/phase6k12_hard_needle.py --worker --mml 8192
#   # full driver (bf16/naive/protected):
#   python CTM_plus/Bench/scripts/phase6k12_hard_needle.py --mml 8192 2>&1 | tee /tmp/phase6k12.log

import argparse
import json
import os
import random
import re
import string
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

CELLS = ["bf16", "naive", "protected"]
NAIVE_MASK_DEFAULT = "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_naive.pt"
_CODE_RE = re.compile(r"[A-Z0-9]{5,8}")
MODES = ["multi", "distractor", "conflict", "qa"]
_NAMES = ["Marcus", "Priya", "Diego", "Hassan", "Yuki", "Olga", "Tomas", "Nadia"]
_SECTIONS = ["ALPHA", "BRAVO", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL"]


def _code(rng):
    return "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(6))


def _lookalike(code, rng):
    i = rng.randrange(len(code))
    repl = rng.choice(string.ascii_uppercase + string.digits)
    while repl == code[i]:
        repl = rng.choice(string.ascii_uppercase + string.digits)
    return code[:i] + repl + code[i + 1:]


def _lev(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _filler(n):
    return " ".join(
        f"Background note {i}: routine operations continued without incident."
        for i in range(n)
    )


def build_item(mode, target_tokens, rng):
    """Returns (prompt, expected, distractors, question_tag).

    target_tokens is the desired TOTAL prompt size; keep it well under
    max_model_len so there is room to generate. ~12 tokens/filler-sentence,
    split across 3 depth bands.
    """
    _EST_TOK_PER_SENT = 12
    n_fill = max(20, target_tokens // (3 * _EST_TOK_PER_SENT))
    seg = _filler(n_fill)
    segs = [seg, _filler(n_fill), _filler(n_fill)]  # 3 depth bands

    if mode == "multi":
        labels = rng.sample(_SECTIONS, 3)
        codes = [_code(rng) for _ in labels]
        want = rng.randrange(3)
        inj = [f"The access code for section {labels[k]} is {codes[k]}." for k in range(3)]
        body = f"{segs[0]} {inj[0]} {segs[1]} {inj[1]} {segs[2]} {inj[2]}"
        q = f"\n\nQuestion: What is the access code for section {labels[want]}? Answer with only the code."
        return body + q, codes[want], [c for i, c in enumerate(codes) if i != want], "multi"

    if mode == "distractor":
        real = _code(rng)
        looks = [_lookalike(real, rng) for _ in range(3)]
        label = rng.choice(_SECTIONS)
        inj_real = f"The OFFICIAL access code for section {label} is {real}."
        inj_looks = [f"An old, expired code was {l}." for l in looks]
        body = (f"{segs[0]} {inj_looks[0]} {segs[1]} {inj_real} "
                f"{inj_looks[1]} {segs[2]} {inj_looks[2]}")
        q = f"\n\nQuestion: What is the OFFICIAL access code for section {label}? Answer with only the code."
        return body + q, real, looks, "distractor"

    if mode == "conflict":
        old, new = _code(rng), _code(rng)
        body = (f"{segs[0]} The access code is {old}. {segs[1]} "
                f"Correction: the access code has been updated; the access code is now {new}. {segs[2]}")
        q = "\n\nQuestion: What is the CURRENT access code? Answer with only the code."
        return body + q, new, [old], "conflict"

    # qa
    name = rng.choice(_NAMES)
    code = _code(rng)
    body = (f"{segs[0]} The night guard on duty is named {name}, and the vault door code is {code}. {segs[1]} {segs[2]}")
    q = "\n\nQuestion: What is the name of the night guard on duty? Answer with only the name."
    return body + q, name, [code], "qa"


def _collapsed(text):
    w = text.split()
    if len(w) < 6:
        return False
    longest = cur = 1
    for a, b in zip(w, w[1:]):
        cur = cur + 1 if a == b else 1
        longest = max(longest, cur)
    return len(set(w)) / len(w) < 0.4 or longest >= 4


def classify(text, expected, distractors, mode):
    if _collapsed(text):
        return "COLLAPSE"
    low = text.lower()
    has_exp = expected.lower() in low
    has_dis = any(d.lower() in low for d in distractors)
    if has_exp and has_dis:
        return "FORMAT"          # right answer present but leaked a wrong field too
    if has_exp:
        return "HIT"
    if has_dis:
        return "NEAR_V"          # emitted a look-alike / wrong-but-related answer
    if mode == "qa":
        if re.search(r"\b[A-Z][a-z]{2,}\b", text):
            return "NEAR_V"      # produced a name, wrong one
        return "MISS_K"
    codes = _CODE_RE.findall(text)
    if any(_lev(c, expected) <= 2 for c in codes):
        return "NEAR_V"
    if codes:
        return "NEAR_V"
    return "MISS_K"


# ----------------------------------------------------------------------- worker
def run_worker(mml, items_per_mode):
    cell = os.environ.get("CELL", "protected")
    eager = os.environ.get("ENFORCE_EAGER", "1").strip() in ("1", "true", "yes")
    os.environ.pop("PHASE6B3_FORCE_EAGER", None)
    if cell == "naive":
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "1"
        os.environ["PROTECT_MASK_PATH"] = os.environ.get("NAIVE_MASK_PATH", NAIVE_MASK_DEFAULT)
    elif cell == "protected":
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "0"
        os.environ.pop("PROTECT_MASK_PATH", None)

    from vllm import SamplingParams
    if cell == "bf16":
        from vllm import LLM
        llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=mml,
                  gpu_memory_utilization=0.5, dtype="bfloat16",
                  max_num_seqs=8, enforce_eager=eager)
    else:
        from kv_policy.int4_protected import Int4ProtectedLLM
        llm = Int4ProtectedLLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=mml,
                               gpu_memory_utilization=0.5, max_num_seqs=8, enforce_eager=eager)

    sp = SamplingParams(temperature=0.0, max_tokens=16)
    rng = random.Random(1234)
    buckets = defaultdict(lambda: defaultdict(int))
    samples = []
    qa_outputs = []
    try:
        tok = llm.get_tokenizer()
    except Exception:
        tok = None
    _logged = False
    for mode in MODES:
        for _ in range(items_per_mode):
            prompt, expected, distractors, _ = build_item(mode, mml // 2, rng)
            if not _logged and tok is not None:
                try:
                    plen = len(tok.encode(prompt))
                    print(f"[6k12 {cell}] first prompt ~= {plen} tok "
                          f"(max_model_len={mml}, gen={sp.max_tokens}, "
                          f"headroom={mml - plen - sp.max_tokens})", flush=True)
                except Exception:
                    pass
                _logged = True
            try:
                text = llm.generate([prompt], sp)[0].outputs[0].text
            except Exception as e:
                buckets[mode]["ERROR"] += 1
                if len(samples) < 8:
                    samples.append({"mode": mode, "expected": expected,
                                    "bucket": "ERROR", "out": str(e)[:70]})
                continue
            b = classify(text, expected, distractors, mode)
            buckets[mode][b] += 1
            if mode == "qa":
                # Full raw output so FORMAT can be adjudicated: was the answer
                # present-but-unformatted, or semantically wrong?
                qa_outputs.append({"expected": expected, "distractors": distractors,
                                   "bucket": b, "output": text})
            if len(samples) < 8:
                samples.append({"mode": mode, "expected": expected,
                                "bucket": b, "out": text[:60]})

    n_total = items_per_mode * len(MODES)
    tot = {k: sum(buckets[m].get(k, 0) for m in MODES)
           for k in ("HIT", "NEAR_V", "MISS_K", "COLLAPSE", "FORMAT", "ERROR")}
    n_hit = tot["HIT"]
    n_format = tot["FORMAT"]
    # Two metrics (per request):
    #   strict_accuracy    = HIT / total            (FORMAT counts AGAINST)
    #   retrieval_accuracy = HIT / (total - FORMAT)  (FORMAT EXCLUDED as ambiguous
    #     = HIT / (HIT + NEAR_V + MISS_K + COLLAPSE + ERROR))
    # Adjudicate FORMAT via qa_outputs below: present-but-unformatted vs wrong.
    summary = {
        "cell": cell, "mml": mml, "eager": eager, "items_per_mode": items_per_mode,
        "n_total": n_total,
        "strict_accuracy": round(n_hit / max(1, n_total), 3),
        "retrieval_accuracy": round(n_hit / max(1, n_total - n_format), 3),
        "buckets": {m: dict(buckets[m]) for m in MODES},
        "totals": tot,
        "qa_outputs": qa_outputs,
        "samples": samples,
    }
    out = os.environ.get("OUTPUT", f"/tmp/phase6k12_{cell}_mml{mml}.json")
    Path(out).write_text(json.dumps(summary, indent=2))
    print(f"\n[6k12 {cell} mml{mml}] strict_accuracy={summary['strict_accuracy']} "
          f"(HIT/total) | retrieval_accuracy={summary['retrieval_accuracy']} "
          f"(HIT/(total-FORMAT)) | totals={summary['totals']}")
    for m in MODES:
        print(f"    {m:10s}: {dict(buckets[m])}")
    _fmt = [q for q in qa_outputs if q["bucket"] == "FORMAT"]
    if _fmt:
        print("    qa FORMAT raw outputs (is the answer present? -> retrieved-but-unformatted):")
        for q in _fmt[:5]:
            print(f"      expected={q['expected']!r}  out={q['output']!r}")
    print(f"[6k12] wrote {out}", flush=True)
    return 0


# ----------------------------------------------------------------------- driver
def run_driver(mml, items_per_mode):
    naive_mask = Path(os.environ.get("NAIVE_MASK_PATH", NAIVE_MASK_DEFAULT))
    rows = []
    for cell in CELLS:
        out = f"/tmp/phase6k12_{cell}_mml{mml}.json"
        env = dict(os.environ)
        env.update({"CELL": cell, "OUTPUT": out, "NAIVE_MASK_PATH": str(naive_mask)})
        env.setdefault("PHASE6E_FUSED_WRITER", "1")
        env.setdefault("ENFORCE_EAGER", "1")
        env.pop("PHASE6B3_FORCE_EAGER", None)
        print(f"\n=== 6k12 driver: cell={cell} mml={mml} ===", flush=True)
        subprocess.run([sys.executable, __file__, "--worker",
                        "--mml", str(mml), "--items", str(items_per_mode)],
                       env=env, check=False)
        try:
            rows.append(json.loads(Path(out).read_text()))
        except Exception as e:
            rows.append({"cell": cell, "error": str(e)[:60]})

    print("\n" + "=" * 96)
    print(f"PHASE 6K.12 — HARD needle (mml={mml}, {items_per_mode}/mode, {len(MODES)} modes)")
    print("=" * 96)
    print("  strict   = HIT / total                 (FORMAT counts AGAINST)")
    print("  retrieval= HIT / (total - FORMAT)       (FORMAT EXCLUDED as ambiguous)")
    print("  FORMAT = answer present but verbose/leaked other field (adjudicate via qa raw below)")
    print(f"  {'cell':>10} | {'strict':>6} {'retr':>6} | {'HIT':>4} {'NEAR_V':>6} "
          f"{'MISS_K':>6} {'COLLAPSE':>8} {'FORMAT':>6} {'ERROR':>5}")
    print("  " + "-" * 84)
    strict_a, retr_a = {}, {}
    for r in rows:
        if "error" in r:
            print(f"  {r.get('cell','?'):>10} | ERROR {r['error']}")
            continue
        t = r["totals"]
        strict_a[r["cell"]] = r["strict_accuracy"]
        retr_a[r["cell"]] = r["retrieval_accuracy"]
        print(f"  {r['cell']:>10} | {r['strict_accuracy']:>6.3f} {r['retrieval_accuracy']:>6.3f} | "
              f"{t['HIT']:>4} {t['NEAR_V']:>6} {t['MISS_K']:>6} {t['COLLAPSE']:>8} "
              f"{t['FORMAT']:>6} {t.get('ERROR',0):>5}")
    if "naive" in retr_a and "protected" in retr_a:
        print(f"\n  prot-naive gap:  strict {strict_a['protected']-strict_a['naive']:+.3f}   "
              f"retrieval {retr_a['protected']-retr_a['naive']:+.3f}")
    # qa raw outputs so FORMAT can be adjudicated (present-but-unformatted vs wrong)
    print("\n  --- qa FORMAT raw outputs (answer present => retrieved-but-unformatted) ---")
    any_fmt = False
    for r in rows:
        if "error" in r:
            continue
        fmt = [q for q in r.get("qa_outputs", []) if q["bucket"] == "FORMAT"][:3]
        if fmt:
            any_fmt = True
            print(f"  [{r['cell']}]")
            for q in fmt:
                print(f"     expected={q['expected']!r}  out={q['output']!r}")
    if not any_fmt:
        print("  (no FORMAT items)")
    print("  NEAR_V-heavy => V-bound; MISS_K-heavy => K-bound.")
    print("=" * 96, flush=True)
    return 0


def _selftest():
    rng = random.Random(0)
    ok = True
    for mode in MODES:
        prompt, expected, distractors, tag = build_item(mode, 2048, rng)
        assert tag == mode and expected and "Question:" in prompt
        # canned outputs exercise each bucket
        assert classify(f" The answer is {expected}.", expected, distractors, mode) == "HIT"
        assert classify(" pérdida pérdida pérdida pérdida pérdida pérdida", expected, distractors, mode) == "COLLAPSE"
        if distractors:
            assert classify(f" It is {distractors[0]}.", expected, distractors, mode) == "NEAR_V"
            assert classify(f" {expected} (or maybe {distractors[0]})", expected, distractors, mode) == "FORMAT"
        miss = classify(" The document is about routine operations.", expected, distractors, mode)
        assert miss in ("MISS_K", "NEAR_V"), miss
        print(f"  selftest {mode:10s}: expected={expected!r} distractors={distractors} OK")
    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mml", type=int, default=8192)
    ap.add_argument("--items", type=int, default=6, help="items per mode")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if args.worker:
        return run_worker(args.mml, args.items)
    return run_driver(args.mml, args.items)


if __name__ == "__main__":
    raise SystemExit(main())
