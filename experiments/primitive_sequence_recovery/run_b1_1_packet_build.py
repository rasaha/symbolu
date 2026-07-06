#!/usr/bin/env python3
"""B1.1 BLINDED PAIRWISE JUDGE-PACKET BUILDER — pure data reshaping.

Reads the audited raw generation JSONL and builds blinded pairwise judge packets (A vs each of the 7
controls), holding target_word / task_id / model_id / seed fixed per pair. Judge-facing packets carry only
opaque IDs + task instruction + two neutrally-labelled outputs — NO arm/control/bridge/conditioning/varṇa/
Sanskrit/model-provenance. Arm truth lives ONLY in the private manifest (for scoring).

NO models, NO judging, NO scoring. Does not modify frozen artifacts or the freeze manifest, change the B1
verdict (RANDOM_OR_SCRAMBLED_MATCHES), or unblock Track B (BLOCKED). Structure, not validated meaning.

    python3 experiments/primitive_sequence_recovery/run_b1_1_packet_build.py \
        [raw.jsonl] [expected_raw_sha256]
"""
from __future__ import annotations
import collections, hashlib, json, pathlib, random, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_1_generation as R                         # leak_scan + frozen-config loading (no model)

RAW = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "b1_1_outputs_raw/b1_1_raw_outputs.jsonl"
EXPECT_RAW_SHA = sys.argv[2] if len(sys.argv) > 2 else \
    "f7df36cd901e1f0676a0c1a0fd6cf449af2826d3a257831b82bbf74a1be3b662"
OUTDIR = HERE / "b1_1_judge_packets"
CONTROLS = ["D", "S", "R_same", "R_deranged", "R_domain", "C", "X"]     # A vs each -> 7 comparisons
COMPARISONS = [f"A_vs_{c}" for c in CONTROLS]
EXPECTED_WORDS, EXPECTED_TASKS, EXPECTED_MODELS, EXPECTED_SEEDS = 25, 6, 2, 2
EXPECTED_ROWS, EXPECTED_PACKETS = 4800, 4200
SHUFFLE_SEED = None                                     # loaded from frozen seeds config below
RUBRIC = ("Judge which response better accomplishes the task. Consider quality and correctness only; "
          "ignore length and style.")
PRIVATE_FIELD_NAMES = ("arm", "control_type", "conditioning_text", "prompt_text", "model_id",
                       "model_revision", "seed", "manifest_sha256", "run_id", "bridge")

blockers, flags, info = [], [], []


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---- 0. verify frozen + load configs ----
man = R.verify_frozen_or_abort(require_frozen=True)
cfg = R.load_frozen_configs(man)
lex = cfg["lexicon"]
gen = cfg["generation"]
SHUFFLE_SEED = cfg["seeds"]["judge_packet_shuffle_seed"]        # frozen 50513
if SHUFFLE_SEED != 50513:
    flags.append(f"judge_packet_shuffle_seed is {SHUFFLE_SEED}, expected 50513")


def task_instruction(word, task_id):
    return gen["task_templates"][task_id]["exact_prompt"].format(target_word=word)


# ---- 1. load raw + matrix verification ----
raw_bytes = RAW.read_bytes()
raw_sha = sha(raw_bytes)
if EXPECT_RAW_SHA and raw_sha != EXPECT_RAW_SHA:
    blockers.append(f"raw sha256 {raw_sha[:16]} != expected {EXPECT_RAW_SHA[:16]}")
rows = [json.loads(l) for l in raw_bytes.decode("utf-8").splitlines() if l.strip()]
by_key = {r["key"]: r for r in rows}
ok_rows = [r for r in rows if r.get("status") == "ok"]

words = sorted({r["target_word"] for r in rows})
tasks = sorted({r["task_id"] for r in rows})
arms = sorted({r["arm"] for r in rows})
models = sorted({r["model_id"] for r in rows})
seeds = sorted({r["seed"] for r in rows})

if len(rows) != EXPECTED_ROWS:
    blockers.append(f"row count {len(rows)} != {EXPECTED_ROWS}")
if len(ok_rows) != EXPECTED_ROWS:
    blockers.append(f"ok rows {len(ok_rows)} != {EXPECTED_ROWS} (errors present)")
if not all(r.get("mock") is False for r in rows):
    blockers.append("not all rows are real (mock=false) — refusing to build packets from mock/partial data")
if (len(words), len(tasks), len(models), len(seeds)) != (EXPECTED_WORDS, EXPECTED_TASKS, EXPECTED_MODELS, EXPECTED_SEEDS):
    blockers.append(f"matrix dims {(len(words), len(tasks), len(models), len(seeds))} != "
                    f"{(EXPECTED_WORDS, EXPECTED_TASKS, EXPECTED_MODELS, EXPECTED_SEEDS)}")
if set(arms) != set(R.ARMS):
    blockers.append(f"arms {arms} != {sorted(R.ARMS)}")
# is_b1_1_evidence: authoritative real-marker is mock=false; None expected on pre-label-fix runs
if any(r.get("is_b1_1_evidence") is False and r.get("mock") is False for r in rows):
    blockers.append("is_b1_1_evidence=False on a real row (wrongly marked not-evidence)")
elif any(r.get("is_b1_1_evidence") is not True for r in rows):
    info.append("is_b1_1_evidence is None (not True) on rows generated before the label fix; expected. "
                "Authoritative real-marker is mock=false, which is correct on all rows.")

# ---- 2. build logical comparison units (canonical order, then seeded shuffle) ----
units = []
missing = []
for w in words:
    for t in tasks:
        for m in models:
            for s in seeds:
                a_key = f"{w}|{t}|A|{m}|{s}"
                if a_key not in by_key:
                    missing.append(a_key); continue
                for c in CONTROLS:
                    c_key = f"{w}|{t}|{c}|{m}|{s}"
                    if c_key not in by_key:
                        missing.append(c_key); continue
                    units.append({"word": w, "task": t, "model": m, "seed": s, "control": c,
                                  "a_key": a_key, "c_key": c_key})
if missing:
    blockers.append(f"{len(missing)} matched rows missing (e.g. {missing[:3]}) — cannot pair")
# canonical sort BEFORE shuffle so ordering is deterministic regardless of dict order
units.sort(key=lambda u: (u["word"], u["task"], u["model"], u["seed"], CONTROLS.index(u["control"])))
rng = random.Random(SHUFFLE_SEED)
rng.shuffle(units)                                     # packet_id order carries no arm/order info

# ---- 3. render blinded packets + private truth map ----
blinded, truth_map = [], {}
left_right = collections.Counter()          # count of A in position 1 vs 2 (should be ~balanced)
for i, u in enumerate(units, 1):
    pid = f"P{i:05d}"
    a_text = by_key[u["a_key"]].get("generation_text") or ""
    c_text = by_key[u["c_key"]].get("generation_text") or ""
    a_pos = rng.choice([1, 2])              # deterministic left/right randomization
    left_right[a_pos] += 1
    o1_id = sha(f"{SHUFFLE_SEED}|{pid}|1".encode())[:12]
    o2_id = sha(f"{SHUFFLE_SEED}|{pid}|2".encode())[:12]
    if a_pos == 1:
        o1_text, o2_text, o1_arm, o2_arm = a_text, c_text, "A", u["control"]
    else:
        o1_text, o2_text, o1_arm, o2_arm = c_text, a_text, u["control"], "A"
    blinded.append({
        "packet_id": pid, "target_word": u["word"], "task_id": u["task"],
        "task_instruction": task_instruction(u["word"], u["task"]),
        "output_1": {"id": o1_id, "text": o1_text},
        "output_2": {"id": o2_id, "text": o2_text},
        "rubric": RUBRIC,
    })
    truth_map[pid] = {
        "target_word": u["word"], "task_id": u["task"], "model_id": u["model"], "seed": u["seed"],
        "control_type": u["control"], "comparison": f"A_vs_{u['control']}", "arm_pair": ["A", u["control"]],
        "a_output_position": a_pos, "output_1_id": o1_id, "output_1_arm": o1_arm,
        "output_2_id": o2_id, "output_2_arm": o2_arm,
        "raw_key_A": u["a_key"], "raw_key_control": u["c_key"],
    }

# ---- 4. leak scan (judge-facing fields only) + structural blinding check ----
# R.leak_scan is authoritative (IAST diacritics, Sanskrit source-labels, varṇa names, arm labels). The
# extra meta list is NARROW on purpose: only experiment-jargon that a model would never naturally emit in
# these tasks. Deliberately EXCLUDES common English words (bridge/resonance/conditioning) and ambiguous
# tokens (H2 = hydrogen, B1 = vitamin) that real creative outputs legitimately contain and that do NOT
# reveal the arm.
VARNA_META = ("varṇa", "varna", "sanskrit", "vṛtti", "vritti")
leak_hits, struct_leak = [], []
per_field_leak = collections.Counter()
for p in blinded:
    facing = " \n ".join([p["task_instruction"], p["output_1"]["text"], p["output_2"]["text"]])
    total, hits = R.leak_scan(facing, lex)
    low = facing.lower()
    meta_hit = [w for w in VARNA_META if w.lower() in low]
    if total or meta_hit:
        for cat, toks in hits.items():
            if toks:
                per_field_leak[cat] += len(toks)
        if meta_hit:
            per_field_leak["meta_terms"] += len(meta_hit)
        if len(leak_hits) < 10:
            leak_hits.append({"packet_id": p["packet_id"],
                              "hits": {k: v for k, v in hits.items() if v}, "meta": meta_hit})
    # structural: no private field name should appear as a KEY in the judge packet
    for bad in PRIVATE_FIELD_NAMES:
        if bad in p or bad in p.get("output_1", {}) or bad in p.get("output_2", {}):
            struct_leak.append((p["packet_id"], bad))
if per_field_leak:
    blockers.append(f"LEAK in judge-facing packets: {dict(per_field_leak)} (e.g. {leak_hits[:2]})")
if struct_leak:
    blockers.append(f"private field leaked into judge packet structure: {struct_leak[:3]}")

# ---- 5. private-metadata completeness (for scoring) ----
REQ_TRUTH = ("control_type", "comparison", "a_output_position", "output_1_arm", "output_2_arm",
             "raw_key_A", "raw_key_control", "model_id", "seed", "task_id", "target_word")
incomplete = [pid for pid, tm in truth_map.items() if any(k not in tm for k in REQ_TRUTH)]
if incomplete:
    blockers.append(f"{len(incomplete)} packets have incomplete private metadata (e.g. {incomplete[:3]})")

# ---- 6. counts ----
if len(blinded) != EXPECTED_PACKETS:
    blockers.append(f"packet count {len(blinded)} != {EXPECTED_PACKETS}")
per_comparison = collections.Counter(tm["comparison"] for tm in truth_map.values())

# ---- 7. write files ----
OUTDIR.mkdir(parents=True, exist_ok=True)
blinded_path = OUTDIR / "blinded_pairwise_packets.jsonl"
sample_path = OUTDIR / "blinded_pairwise_packets.sample.jsonl"
manifest_path = OUTDIR / "blinded_pairwise_packet_manifest.json"

blinded_text = "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in blinded)
blinded_path.write_text(blinded_text, encoding="utf-8")

# stratified sample: up to 6 packets per comparison, spread across tasks -> ~42
sample, per_c = [], collections.Counter()
for p in blinded:                                       # blinded is already seeded-shuffled
    c = truth_map[p["packet_id"]]["comparison"]
    if per_c[c] < 6:
        sample.append(p); per_c[c] += 1
    if len(sample) >= 45:
        break
sample_text = "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in sample)
sample_path.write_text(sample_text, encoding="utf-8")
# re-scan the sample explicitly (it is committed)
sample_leak = sum(R.leak_scan(" ".join([p["task_instruction"], p["output_1"]["text"], p["output_2"]["text"]]),
                              lex)[0] for p in sample)
if sample_leak:
    blockers.append(f"sample packet leak: {sample_leak}")

blinded_sha = sha(blinded_text.encode())
sample_sha = sha(sample_text.encode())
manifest = {"B1_1_BLINDED_PACKET_MANIFEST": {
    "status": None,          # filled after verdict
    "scope": "blinded pairwise judge packets — NO judging, NO scoring, NO model calls",
    "raw_output_path": str(RAW), "raw_output_sha256": raw_sha, "raw_output_rows": len(rows),
    "n_packets": len(blinded), "expected_packets": EXPECTED_PACKETS,
    "comparisons": COMPARISONS, "controls": CONTROLS,
    "judge_packet_shuffle_seed": SHUFFLE_SEED,
    "left_right_balance": {"A_in_output_1": left_right[1], "A_in_output_2": left_right[2]},
    "blinded_file": "blinded_pairwise_packets.jsonl", "blinded_file_sha256": blinded_sha,
    "sample_file": "blinded_pairwise_packets.sample.jsonl", "sample_file_sha256": sample_sha,
    "sample_count": len(sample),
    "judge_view_fields": ["packet_id", "target_word", "task_id", "task_instruction", "output_1", "output_2", "rubric"],
    "judge_choices": ["output_1_better", "output_2_better", "tie_no_preference", "both_bad"],
    "scoring_note": "map judge choice -> A-win via truth_map[packet_id].a_output_position; "
                    "primary A_vs_R_deranged/R_domain/R_same (item-clustered paired bootstrap, Holm).",
    "b1_verdict_anchor": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_anchor": "BLOCKED",
    "positive_cap": "LIMITED_GENERATION_UTILITY", "crux": "R_deranged",
    "frozen_manifest_status": man["manifest_status"],
    "truth_map": truth_map,
}}

status = ("BLOCKED" if blockers else ("REVIEW_REQUIRED" if flags else "PASS_PACKET_BUILD"))
manifest["B1_1_BLINDED_PACKET_MANIFEST"]["status"] = status
manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
manifest_path.write_text(manifest_text, encoding="utf-8")

# ---- 8. reports ----
report = {
    "artifact": "b1_1_blinded_packet_build_report", "status": status,
    "raw_output_sha256": raw_sha, "raw_output_sha256_match": (raw_sha == EXPECT_RAW_SHA) if EXPECT_RAW_SHA else None,
    "raw_rows": len(rows), "packet_count": len(blinded), "expected_packet_count": EXPECTED_PACKETS,
    "comparisons": COMPARISONS, "per_comparison_counts": dict(per_comparison),
    "shuffle_seed": SHUFFLE_SEED,
    "left_right_randomization": {"A_in_output_1": left_right[1], "A_in_output_2": left_right[2]},
    "leak_scan": {"judge_facing_leak_categories": dict(per_field_leak), "structural_leak": struct_leak[:5],
                  "sample_leak": sample_leak, "examples": leak_hits[:5]},
    "sample_count": len(sample), "private_metadata_complete": not incomplete,
    "files": {"blinded": str(blinded_path), "blinded_sha256": blinded_sha,
              "sample": str(sample_path), "sample_sha256": sample_sha,
              "manifest": str(manifest_path)},
    "judging_run": False, "scoring_run": False,
    "blockers": blockers, "flags": flags, "info": info,
    "anchors": {"b1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b": "BLOCKED"},
    "non_claims": ["no judging", "no scoring", "no model calls", "structure not validated meaning"],
    "next_gate": "B1_1_JUDGE_RUN_PRECHECK",
}
(HERE / "B1_1_BLINDED_PACKET_BUILD_REPORT.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

md = f"""# B1.1 Blinded Packet-Build Report

## Status: `{status}`

Blinded pairwise judge packets (A vs each control) built from the audited raw generation JSONL. **Pure data
reshaping — no models, no judging, no scoring.** Does not change the B1 verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`) or unblock Track B (**BLOCKED**). **Structure, not validated meaning.**

## Inputs
- raw: `{RAW}` · sha256 `{raw_sha}` · match `{(raw_sha == EXPECT_RAW_SHA) if EXPECT_RAW_SHA else None}` · rows **{len(rows)}**

## Packets
- **{len(blinded)}** packets (expected **{EXPECTED_PACKETS}** = 25×6×2×2×7)
- comparisons: {', '.join(COMPARISONS)}
- per-comparison: {dict(per_comparison)}
- shuffle seed: **{SHUFFLE_SEED}** · left/right: A in output_1 = {left_right[1]}, output_2 = {left_right[2]}

## Blinding & leak scan
- judge-facing fields: packet_id · target_word · task_id · task_instruction · output_1 · output_2 · rubric
- **judge-facing leak categories: {dict(per_field_leak) or 'NONE'}** · structural leak: {struct_leak[:3] or 'NONE'} · sample leak: {sample_leak}
- arm truth stored ONLY in the private manifest `truth_map` (not judge-facing).

## Private metadata (for scoring)
- complete: **{not incomplete}** — each packet has control_type, comparison, a_output_position, per-output arm, raw keys, model, seed, task, word.

## Files
- `{blinded_path.name}` (sha `{blinded_sha[:16]}`)
- `{sample_path.name}` ({len(sample)} packets, sha `{sample_sha[:16]}`)
- `{manifest_path.name}` (counts + hashes + private truth_map)

## Blockers ({len(blockers)})
{chr(10).join('- ' + b for b in blockers) or '_none_'}

## Flags ({len(flags)}) / Info ({len(info)})
{chr(10).join('- flag: ' + f for f in flags) or ''}
{chr(10).join('- info: ' + i for i in info) or '_none_'}

## Final status
```
packet_build:          {status}
packets / expected:    {len(blinded)} / {EXPECTED_PACKETS}
judge-facing leak:     {sum(per_field_leak.values())}
private metadata:      {'complete' if not incomplete else 'INCOMPLETE'}
judging run:           NO
scoring run:           NO
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
```
`R_deranged` remains the crux. Next gate: **B1_1_JUDGE_RUN_PRECHECK**. **Structure, not validated meaning.**
"""
(HERE / "B1_1_BLINDED_PACKET_BUILD_REPORT.md").write_text(md, encoding="utf-8")

print(f"STATUS: {status}")
print(f"  raw sha match: {(raw_sha == EXPECT_RAW_SHA) if EXPECT_RAW_SHA else None} | rows {len(rows)}")
print(f"  packets {len(blinded)} / {EXPECTED_PACKETS} | per_comparison {dict(per_comparison)}")
print(f"  shuffle_seed {SHUFFLE_SEED} | A_in_out1 {left_right[1]} A_in_out2 {left_right[2]}")
print(f"  judge-facing leak {dict(per_field_leak) or 'NONE'} | struct {struct_leak[:2] or 'NONE'} | sample_leak {sample_leak}")
print(f"  private_metadata_complete {not incomplete} | sample {len(sample)}")
print(f"  blockers {len(blockers)} | flags {len(flags)} | info {len(info)}")
for b in blockers: print("   BLOCKER:", b)
for f in flags: print("   FLAG:", f)
for i in info: print("   info:", i)
print(f"  wrote {blinded_path}, {sample_path}, {manifest_path}")
print("  wrote B1_1_BLINDED_PACKET_BUILD_REPORT.{json,md}")
print("  NO judging, NO scoring, NO model calls. Track B BLOCKED. Next: B1_1_JUDGE_RUN_PRECHECK.")
