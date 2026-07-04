#!/usr/bin/env python3
"""B1 read-only example extractor — show the packets where a control (default R=random) beat or tied A.

RUN THIS ON THE RUNPOD, where the data lives:
    experiments/primitive_sequence_recovery/b1_judge_packets_full.jsonl   (scorer-only: truth + text)
    experiments/primitive_sequence_recovery/b1_judge_responses_<slug>_v2.jsonl  (per judge)

It is strictly READ-ONLY: no model, no re-judge, no re-score, no frozen artifact modified, and it
writes NOTHING unless you pass --dump-file. It reuses the FROZEN scorer's own
load_truth / load_judges / a_win / aggregate (from run_b1_score.py), so the per-packet majority and the
per-control win-rate it prints match run_b1_score.py EXACTLY. It cannot change the verdict.

A-win convention (same as the scorer):  1 = A judged better · 0 = the control judged better · 0.5 = tie.
"majority" per packet = MEDIAN of the surviving judges' A-win scores (stays in {0, 0.5, 1}).

Examples:
    python3 show_b1_control_examples.py                       # R, primary, ties+losses, text preview
    python3 show_b1_control_examples.py --control S           # scrambled instead of random
    python3 show_b1_control_examples.py --which lose          # only packets where the control STRICTLY beat A
    python3 show_b1_control_examples.py --stratum privative
    python3 show_b1_control_examples.py --full-text --limit 25
    python3 show_b1_control_examples.py --dump-file r_beats_a.jsonl   # save the shown packets as JSONL
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_score as S   # noqa: E402  FROZEN scorer: load_truth/load_judges/a_win/aggregate/verify_frozen


def load_text():
    """display_id -> {'task_text', 'by_id': {'Output 1': text, 'Output 2': text}} from packets_full."""
    if not S.TRUTH_FILE.exists():
        print(f"[FAIL] {S.TRUTH_FILE.name} not found on this machine — run this ON THE POD.")
        raise SystemExit(1)
    m = {}
    for ln in S.TRUTH_FILE.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        p = json.loads(ln)
        m[p["display_id"]] = {"task_text": p.get("task_text", ""),
                              "by_id": {o["id"]: o["text"] for o in p["outputs"]}}
    return m


def preview(t, n, full):
    t = " ".join((t or "").split())
    return t if full else (t[:n] + ("…" if len(t) > n else ""))


def main():
    ap = argparse.ArgumentParser(description="Show B1 packets where a control beat/tied A (read-only).")
    ap.add_argument("--control", default="R", help="control arm to inspect: D/R/S/C/X (default R)")
    ap.add_argument("--stratum", default="primary", choices=["primary", "privative"])
    ap.add_argument("--which", default="tieloss", choices=["lose", "tieloss", "all", "win"],
                    help="lose=control strictly beat A · tieloss=tie or loss (default) · win=A won · all")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--chars", type=int, default=240, help="preview length per output (ignored with --full-text)")
    ap.add_argument("--full-text", action="store_true")
    ap.add_argument("--dump-file", default=None, help="write the shown packets to this JSONL (post-verdict)")
    args = ap.parse_args()

    if args.control not in S.B.CO_PRIMARIES:
        print(f"[FAIL] --control must be one of {list(S.B.CO_PRIMARIES)}")
        raise SystemExit(1)

    ok, bad = S.verify_frozen()
    print(f"[{'ok' if ok else 'FAIL'}] frozen integrity (read-only; nothing modified)"
          + (f" — CHANGED: {bad}" if bad else ""))
    choices, kept, _attn = S.load_judges()
    truth = S.load_truth()
    text = load_text()
    print(f"[ok] judges kept: {kept}")

    # Sanity anchor: reproduce the scorer's item-clustered win-rate for this control/stratum.
    agg, _f, _n = S.aggregate(choices, kept, truth, args.stratum)
    a = agg.get(args.control)
    if a:
        print(f"[anchor] A-vs-{args.control} ({args.stratum}) item-clustered win_rate={a['win_rate']:.4f} "
              f"n_items={a['n_items']} n_packets={a['n_packets']}")

    # Per-packet majority for every packet of this control/stratum -> counts + the filtered list.
    counts = {"A_win": 0, "tie": 0, "control_win": 0}
    rows = []
    for did, meta in truth.items():
        if meta["stratum"] != args.stratum or meta["control"] != args.control:
            continue
        votes = [(j, choices[j][did]) for j in kept if did in choices[j]]
        if not votes:
            continue
        aw = statistics.median([S.a_win(ch, meta["truth"]) for _j, ch in votes])
        cls = "A_win" if aw == 1 else ("tie" if aw == 0.5 else "control_win")
        counts[cls] += 1
        keep = (args.which == "all"
                or (args.which == "lose" and cls == "control_win")
                or (args.which == "tieloss" and cls in ("tie", "control_win"))
                or (args.which == "win" and cls == "A_win"))
        if keep:
            rows.append((did, meta, votes, aw, cls))

    print(f"[summary] A-vs-{args.control} {args.stratum}: A_win={counts['A_win']} tie={counts['tie']} "
          f"{args.control}_win={counts['control_win']}  (per-packet majority over kept judges)")

    rows.sort(key=lambda r: (r[3], r[1]["task"], r[1]["key_word"]))   # losses first, then by task/word
    shown = rows[:args.limit]
    print(f"\n===== {len(shown)} of {len(rows)} '{args.which}' packets (A vs {args.control}, {args.stratum}) "
          f"| A-win: 1=A better, 0={args.control} better, 0.5=tie =====")

    dump = []
    for did, meta, votes, aw, cls in shown:
        a_id = "Output 1" if meta["truth"].get("Output 1") == "A" else "Output 2"
        c_id = "Output 2" if a_id == "Output 1" else "Output 1"
        tx = text.get(did, {"task_text": "", "by_id": {}})
        a_txt, c_txt = tx["by_id"].get(a_id, ""), tx["by_id"].get(c_id, "")
        print(f"\n--- {did} | word={meta['key_word']} | {meta['task']} | model={meta['model']} "
              f"seed={meta['seed']} | majority={cls} (A-win={aw}) ---")
        print("    votes: " + ", ".join(f"{j.split('-')[0]}:{ch}" for j, ch in votes))
        print(f"    TASK : {preview(tx['task_text'], args.chars, args.full_text)}")
        print(f"    [A = {a_id}] {preview(a_txt, args.chars, args.full_text)}")
        print(f"    [{args.control} = {c_id}] {preview(c_txt, args.chars, args.full_text)}")
        dump.append({"display_id": did, "key_word": meta["key_word"], "task": meta["task"],
                     "model": meta["model"], "seed": meta["seed"], "control": args.control,
                     "majority": cls, "a_win": aw, "votes": {j: ch for j, ch in votes},
                     "task_text": tx["task_text"], "A_text": a_txt, f"{args.control}_text": c_txt})

    if args.dump_file:
        outp = HERE / args.dump_file
        with outp.open("w", encoding="utf-8") as fh:
            for d in dump:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"\n[wrote] {outp.name} ({len(dump)} rows). Post-verdict sample; A/control labels included "
              f"(the verdict is already known). This does NOT touch any frozen artifact.")

    print("\nRead-only. Verdict UNCHANGED: RANDOM_OR_SCRAMBLED_MATCHES. Track B BLOCKED. "
          "Structure, not validated meaning.")


if __name__ == "__main__":
    main()
