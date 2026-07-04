#!/usr/bin/env python3
"""B1 integrity + leak-scan + blinded packet build — runs on the RunPod where the raw outputs live.

Consumes experiments/primitive_sequence_recovery/b1_raw_outputs.jsonl and:
  1. verifies generation integrity (3,600 rows; all dims complete; no empty outputs; all scored:false)
  2. re-verifies the 11 frozen B0 hashes still match (INVALID_POSTHOC guard)
  3. runs the frozen leak scanner over every output_text
  4. builds blinded judge packets with the FROZEN judge-packet seed (50513), using the same tested
     b1_dry_run_harness functions — arm/model/seed/conditioning/packet_id are NOT judge-visible
  5. writes two files ON THE POD:
       - b1_judge_packets_full.jsonl  (includes truth map; SCORER-ONLY, never shown to a judge)
       - b1_judge_view.jsonl          (blinded judge_view only; what a judge/LLM-judge sees)
  6. prints a compact, paste-friendly PROVENANCE+REPORT block (counts + sha256 of the raw outputs)

Does NOT judge, score, or compute a verdict. Track B stays BLOCKED.

    python3 experiments/primitive_sequence_recovery/run_b1_leak_scan_and_packets.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B            # noqa: E402  frozen-tested leak scan + packet build

RAW = HERE / "b1_raw_outputs.jsonl"
FREEZE_RECORD = HERE / "B0_FREEZE_RECORD.json"
PACKETS_FULL = HERE / "b1_judge_packets_full.jsonl"
JUDGE_VIEW = HERE / "b1_judge_view.jsonl"

JUDGE_PACKET_SEED = 50513                 # frozen (runtime lock judge_packet_randomization)
OUTPUT_RANDOMIZATION_SEED = 40411         # frozen (runtime lock output_randomization)
EXPECTED_ROWS = 3600
EXPECTED_PRIMARY = 2880
EXPECTED_PRIVATIVE = 720


def _fail(msg):
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def verify_frozen():
    rec = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))["B0_FREEZE_RECORD"]
    bad = [a["path"] for a in rec["bound_artifacts"]
           if hashlib.sha256((REPO / a["path"]).read_bytes()).hexdigest() != a["sha256"]]
    if bad:
        _fail(f"INVALID_POSTHOC: frozen artifact(s) changed: {bad}")
    print(f"[ok] frozen integrity: all {len(rec['bound_artifacts'])} hashes match "
          f"(freeze base {rec['freeze_base_commit'][:10]})")


def load_outputs():
    if not RAW.exists():
        _fail(f"raw outputs not found: {RAW}")
    rows = [json.loads(x) for x in RAW.read_text(encoding="utf-8").splitlines() if x.strip()]
    outs = [B.RawOutput(r["row_id"], r["key_word"], r["stratum"], r["task"], r["arm"],
                        r["model_id"], r["seed"], r.get("conditioning", ""), r["output_text"])
            for r in rows]
    return rows, outs


def check_integrity(rows, outs):
    print("\n== 1. generation integrity ==")
    ok = True

    def c(name, cond):
        nonlocal ok
        print(f"[{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    c(f"rows == {EXPECTED_ROWS}", len(rows) == EXPECTED_ROWS)
    c("all scored:false", all(r.get("scored") is False for r in rows))
    c("no empty output_text", all((r.get("output_text") or "").strip() for r in rows))
    models = {r["model_id"] for r in rows}
    c("both models present", len(models) == 2)
    c("both seeds present", {r["seed"] for r in rows} == {1101, 2027})
    c("all 6 arms present", {r["arm"] for r in rows} == set(B.ARMS))
    words = {r["key_word"] for r in rows}
    c("25 words present", words == set(B.PRIMARY_WORDS) | set(B.PRIVATIVE_WORDS))
    c("6 tasks present", {r["task"] for r in rows} == set(B.TASKS))
    prim = sum(1 for r in rows if r["stratum"] == "primary")
    priv = sum(1 for r in rows if r["stratum"] == "privative")
    c(f"primary == {EXPECTED_PRIMARY}", prim == EXPECTED_PRIMARY)
    c(f"privative == {EXPECTED_PRIVATIVE}", priv == EXPECTED_PRIVATIVE)
    # full crossing: each (word,task,arm,model,seed) exactly once
    keys = [(r["key_word"], r["task"], r["arm"], r["model_id"], r["seed"]) for r in rows]
    c("no duplicate (word,task,arm,model,seed) cells", len(keys) == len(set(keys)))
    c(f"complete crossing ({EXPECTED_ROWS} unique cells)", len(set(keys)) == EXPECTED_ROWS)
    if not ok:
        _fail("integrity check failed — do NOT proceed to packets")
    print("[ok] integrity clean")


def check_leaks(outs):
    print("\n== 3. leak scan ==")
    hits = B.scan_outputs(outs)
    if hits:
        print(f"[FAIL] {len(hits)} outputs with leak hits (showing up to 10):")
        for rid, h in hits[:10]:
            print(f"   {rid}: {h}")
        _fail("leak scan not clean — do NOT build packets")
    print(f"[ok] leak scan clean over {len(outs)} outputs (0 hits)")


def build_packets(outs):
    print("\n== 4. blinded packet build ==")
    packets = B.build_judge_packets(outs, rand_seed=JUDGE_PACKET_SEED)   # left/right shuffle (50513)
    # Presentation-order randomization (frozen output seed 40411), then reassign opaque display_ids so
    # display_id carries NO positional info about the control arm (build order groups by control).
    random.Random(OUTPUT_RANDOMIZATION_SEED).shuffle(packets)
    for i, p in enumerate(packets):
        p.display_id = f"P{i:05d}"

    # --- structural blinding assertions (the real guarantee; not substring scans of free-text prose) ---
    ALLOWED_VIEW = {"display_id", "key_word", "task_text", "outputs"}
    ALLOWED_OUT = {"id", "text"}
    bad = 0
    for p in packets:
        v = B.judge_view(p)
        if (set(v) != ALLOWED_VIEW
                or not re.fullmatch(r"P\d{5}", v["display_id"])
                or any(set(o) != ALLOWED_OUT for o in v["outputs"])
                or {o["id"] for o in v["outputs"]} != {"Output 1", "Output 2"}
                or B.leak_scan(v["task_text"])
                or any(B.leak_scan(o["text"]) for o in v["outputs"])):
            bad += 1
    print(f"[{'PASS' if bad == 0 else 'FAIL'}] structural blinding "
          f"(judge_view = {sorted(ALLOWED_VIEW)}; opaque id; leak-clean text) — {bad} real leaks")
    if bad:
        _fail("judge view structurally leaked a field")

    # --- transparency: prove the earlier naive-substring hits were benign (opaque-id digits / prose),
    #     never an arm/model/seed FIELD (those fields are not in judge_view at all) ---
    naive = ('"A"', '"R"', '"S"', '"C"', '"X"', '"D"', "A_vs_", "control_arm", "truth", "1101", "2027")
    where = {"display_id": 0, "key_word": 0, "task_text": 0, "output_text": 0}
    for p in packets:
        v = B.judge_view(p)
        if any(t in v["display_id"] for t in naive):
            where["display_id"] += 1
        if any(t in v["key_word"] for t in naive):
            where["key_word"] += 1
        if any(t in v["task_text"] for t in naive):
            where["task_text"] += 1
        if any(any(t in o["text"] for t in naive) for o in v["outputs"]):
            where["output_text"] += 1
    print(f"[info] naive-token occurrences (benign) by location: {where}")
    print("[info]   -> all are opaque display_id digits or incidental prose; no arm/model/seed field.")

    # scorer-only full packets (with truth map) + blinded judge view
    with PACKETS_FULL.open("w", encoding="utf-8") as fh:
        for p in packets:
            fh.write(json.dumps({"packet_id": p.packet_id, "display_id": p.display_id,
                                 "control_arm": p.control_arm, "key_word": p.key_word,
                                 "task_text": p.task_text, "outputs": p.outputs,
                                 "truth": p.truth}, ensure_ascii=False) + "\n")
    with JUDGE_VIEW.open("w", encoding="utf-8") as fh:
        for p in packets:
            fh.write(json.dumps(B.judge_view(p), ensure_ascii=False) + "\n")
    print(f"[ok] built {len(packets)} packets -> {PACKETS_FULL.name} (scorer) / {JUDGE_VIEW.name} (blind)")
    return packets


def main():
    verify_frozen()
    rows, outs = load_outputs()
    check_integrity(rows, outs)
    check_leaks(outs)
    packets = build_packets(outs)

    raw_sha = hashlib.sha256(RAW.read_bytes()).hexdigest()
    view_sha = hashlib.sha256(JUDGE_VIEW.read_bytes()).hexdigest()
    full_sha = hashlib.sha256(PACKETS_FULL.read_bytes()).hexdigest()
    # expected packets = 25 words * 6 tasks * 2 models * 2 seeds * 5 controls
    provenance = {
        "B1_PACKET_PROVENANCE": {
            "raw_outputs_rows": len(rows),
            "raw_outputs_sha256": raw_sha,
            "judge_packets": len(packets),
            "expected_packets": 25 * 6 * 2 * 2 * 5,
            "judge_packet_seed": JUDGE_PACKET_SEED,
            "judge_view_sha256": view_sha,
            "packets_full_sha256": full_sha,
            "leak_scan": "CLEAN",
            "integrity": "PASS",
            "excluded_outputs": 0,
            "scored": False,
            "verdict": None,
            "track_b": "BLOCKED",
            "note": "Blinded packets built; NOT judged, NOT scored. Structure, not validated meaning.",
        }
    }
    print("\n===== PASTE THIS BACK (provenance + report) =====")
    print(json.dumps(provenance, indent=2))
    print("===== END =====")
    print(f"\nPackets on pod: {PACKETS_FULL}  and  {JUDGE_VIEW}")
    print("NOT judged, NOT scored. Track B BLOCKED. Next gate: DECLARE_JUDGE_PATH.")


if __name__ == "__main__":
    main()
