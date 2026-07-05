#!/usr/bin/env python3
"""B1.1 POST-GENERATION RAW-OUTPUT AUDIT — descriptive only.

NO judging, NO scoring, NO packet building, NO model calls. Reads the raw generation JSONL and reports:
coverage (full frozen matrix), schema completeness, flags, manifest binding + frozen integrity, and a
LEAK RE-SCAN over every generation_text / prompt_text / conditioning_text (per b1_1_leak_and_packet_config).
Writes B1_1_POST_GENERATION_RAW_OUTPUT_AUDIT.{json,md} and prints a summary.

    python3 b1_1_post_generation_audit.py [path/to/b1_1_raw_outputs.jsonl] [expected_sha256]
"""
from __future__ import annotations
import collections, hashlib, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent      # experiments/primitive_sequence_recovery
sys.path.insert(0, str(HERE))
import run_b1_1_generation as R                        # leak_scan + frozen-config loading (no model)

RAW = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "b1_1_outputs_raw/b1_1_raw_outputs.jsonl"
EXPECT_SHA = sys.argv[2] if len(sys.argv) > 2 else "f7df36cd901e1f0676a0c1a0fd6cf449af2826d3a257831b82bbf74a1be3b662"

REQUIRED_FIELDS = ["run_id", "manifest_sha256", "model_id", "model_revision", "task_id", "target_word",
                   "arm", "prompt_id", "prompt_text", "conditioning_text", "generation_text", "decoding",
                   "seed", "timestamp", "status", "key", "mock"]
ARMS = list(R.ARMS)
flags, blockers = [], []

# ---- 0. file hash + load ----
raw_bytes = RAW.read_bytes()
file_sha = hashlib.sha256(raw_bytes).hexdigest()
rows = [json.loads(l) for l in raw_bytes.decode("utf-8").splitlines() if l.strip()]
sha_ok = (file_sha == EXPECT_SHA) if EXPECT_SHA else None
if EXPECT_SHA and not sha_ok:
    blockers.append(f"sha256 mismatch: file {file_sha[:16]} != expected {EXPECT_SHA[:16]}")

# ---- 1. status / schema ----
status_counts = collections.Counter(r.get("status") for r in rows)
ok_rows = [r for r in rows if r.get("status") == "ok"]
err_rows = [r for r in rows if r.get("status") != "ok"]
missing_fields = sorted({f for r in rows for f in REQUIRED_FIELDS if f not in r})
if missing_fields:
    blockers.append(f"rows missing required fields: {missing_fields}")
empty_gen = [r["key"] for r in ok_rows if not (r.get("generation_text") or "").strip()]
if empty_gen:
    flags.append(f"{len(empty_gen)} ok rows have EMPTY generation_text (e.g. {empty_gen[:3]})")

# ---- 2. coverage (full frozen matrix, each cell exactly once via status=ok) ----
words = sorted({r["target_word"] for r in rows})
arms = sorted({r["arm"] for r in rows})
tasks = sorted({r["task_id"] for r in rows})
models = sorted({r["model_id"] for r in rows})
seeds = sorted({r["seed"] for r in rows})
expected_cells = len(words) * len(arms) * len(tasks) * len(models) * len(seeds)
uniq_ok_keys = {r["key"] for r in ok_rows}
dup_keys = [k for k, c in collections.Counter(r["key"] for r in rows).items() if c > 1]
coverage_full = (len(uniq_ok_keys) == expected_cells == 4800 and set(arms) == set(ARMS))
if not coverage_full:
    flags.append(f"coverage: {len(uniq_ok_keys)} unique ok keys vs expected {expected_cells} (want 4800)")
if dup_keys:
    flags.append(f"{len(dup_keys)} duplicate keys (e.g. {dup_keys[:3]}) — expected on --resume, else investigate")
per_arm = collections.Counter(r["arm"] for r in ok_rows)
per_model = collections.Counter(r["model_id"] for r in ok_rows)

# ---- 3. flags: mock / evidence ----
mock_vals = collections.Counter(r.get("mock") for r in rows)
evid_vals = collections.Counter(r.get("is_b1_1_evidence") for r in rows)
all_real = all(r.get("mock") is False for r in rows)
if not all_real:
    blockers.append(f"NOT all rows are real (mock=false): {dict(mock_vals)}")
# is_b1_1_evidence may be None on this run (generated before the label fix); authoritative flag is mock=false
if any(r.get("is_b1_1_evidence") is not True for r in rows):
    flags.append("is_b1_1_evidence not True on all rows (this run predates the label fix; None is expected; "
                 "authoritative real-marker is mock=false, which is correct).")

# ---- 4. manifest binding + frozen integrity ----
row_manifest_shas = {r.get("manifest_sha256") for r in rows}
manifest_file = HERE / "b1_1_freeze_manifest.json"
cur_manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
manifest_single = len(row_manifest_shas) == 1
manifest_matches_current = (row_manifest_shas == {cur_manifest_sha})
if not manifest_single:
    blockers.append(f"rows carry >1 manifest_sha256: {row_manifest_shas}")
if not manifest_matches_current:
    flags.append(f"row manifest_sha256 {list(row_manifest_shas)[0][:16] if manifest_single else '??'} != "
                 f"current manifest file sha {cur_manifest_sha[:16]} (manifest changed since the run?)")
try:
    man = R.verify_frozen_or_abort(require_frozen=True)      # re-hash all 12 bound artifacts
    frozen_ok = True
except SystemExit as e:
    frozen_ok = False; blockers.append(f"frozen integrity FAILED: {e}")

# ---- 5. LEAK RE-SCAN over model-facing + model-produced text ----
cfg = R.load_frozen_configs(man) if 'man' in dir() and frozen_ok else \
      R.load_frozen_configs(R.verify_frozen_or_abort(require_frozen=False))
lex = cfg["lexicon"]
leak = {"generation_text": {"total": 0, "by_cat": collections.Counter(), "by_arm": collections.Counter(),
                            "examples": []},
        "prompt_text": {"total": 0, "by_cat": collections.Counter(), "examples": []},
        "conditioning_text": {"total": 0, "by_cat": collections.Counter(), "examples": []}}
for r in rows:
    for field in ("generation_text", "prompt_text", "conditioning_text"):
        txt = r.get(field) or ""
        t, hits = R.leak_scan(txt, lex)
        if t:
            leak[field]["total"] += t
            for cat, toks in hits.items():
                if toks:
                    leak[field]["by_cat"][cat] += len(toks)
            if field == "generation_text":
                leak[field]["by_arm"][r["arm"]] += t
            if len(leak[field]["examples"]) < 8:
                leak[field]["examples"].append({"key": r["key"], "arm": r["arm"],
                                                "hits": {k: v for k, v in hits.items() if v}})
gen_leak_total = leak["generation_text"]["total"]
prompt_leak_total = leak["prompt_text"]["total"] + leak["conditioning_text"]["total"]
if prompt_leak_total:
    blockers.append(f"LEAK in model-facing prompt/conditioning text: {prompt_leak_total} hits "
                    "(should be 0 — render-only verified clean).")
# generation_text leak is a REVIEW flag (model may echo Sanskrit/diacritics); not necessarily a blocker,
# but must be handled before judge packets (repair/blind) per leak_and_packet_config.
if gen_leak_total:
    flags.append(f"generation_text leak hits: {gen_leak_total} across arms {dict(leak['generation_text']['by_arm'])} "
                 f"— MUST be handled (repair/blind) before judge packets; check for arm-correlated Sanskrit/IAST.")

# ---- verdict ----
status = "PASS_RAW_OUTPUT_AUDIT" if not blockers and not flags else \
         ("BLOCKED" if blockers else "REVIEW_REQUIRED")

report = {
    "artifact": "b1_1_post_generation_raw_output_audit",
    "status": status,
    "scope": "descriptive audit only — NO judging, NO scoring, NO packets, NO model calls",
    "raw_path": str(RAW), "file_sha256": file_sha, "expected_sha256": EXPECT_SHA, "sha256_match": sha_ok,
    "total_rows": len(rows), "status_counts": dict(status_counts),
    "ok_rows": len(ok_rows), "error_rows": len(err_rows),
    "coverage": {"words": len(words), "arms": arms, "tasks": tasks, "models": models, "seeds": seeds,
                 "expected_cells": expected_cells, "unique_ok_keys": len(uniq_ok_keys),
                 "coverage_full_4800": coverage_full, "duplicate_keys": len(dup_keys),
                 "per_arm_ok": dict(per_arm), "per_model_ok": dict(per_model)},
    "schema": {"missing_fields": missing_fields, "empty_generation_rows": len(empty_gen)},
    "flags_row": {"mock_values": {str(k): v for k, v in mock_vals.items()},
                  "is_b1_1_evidence_values": {str(k): v for k, v in evid_vals.items()},
                  "all_real_mock_false": all_real},
    "manifest": {"row_manifest_shas": [s[:16] for s in row_manifest_shas],
                 "current_manifest_sha256": cur_manifest_sha, "single": manifest_single,
                 "matches_current": manifest_matches_current, "frozen_integrity_ok": frozen_ok},
    "leak_rescan": {
        "prompt_conditioning_leak_total": prompt_leak_total,
        "generation_text_leak_total": gen_leak_total,
        "generation_by_arm": dict(leak["generation_text"]["by_arm"]),
        "generation_by_category": dict(leak["generation_text"]["by_cat"]),
        "prompt_by_category": dict(leak["prompt_text"]["by_cat"]),
        "conditioning_by_category": dict(leak["conditioning_text"]["by_cat"]),
        "generation_examples": leak["generation_text"]["examples"],
    },
    "blockers": blockers, "flags": flags,
    "anchors": {"b1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b": "BLOCKED",
                "positive_cap": "LIMITED_GENERATION_UTILITY", "crux": "R_deranged"},
    "non_claims": ["no judging", "no scoring", "no packets", "not a verdict", "structure not validated meaning"],
    "next_gate": "B1_1_POST_GENERATION_LEAK_SCAN / B1_1_BLINDED_PACKET_BUILD (separately approved) — "
                 "handle any generation_text leak first.",
}
(HERE / "B1_1_POST_GENERATION_RAW_OUTPUT_AUDIT.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

md = f"""# B1.1 Post-Generation Raw-Output Audit

## Status: `{status}`

Descriptive audit of the raw B1.1 generation JSONL. **No judging, no scoring, no packet building, no model
calls.** Does not change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`) or unblock Track B (**BLOCKED**).
**Structure, not validated meaning.**

## File
- path: `{RAW}`
- sha256: `{file_sha}` · expected `{EXPECT_SHA}` · **match: {sha_ok}**

## Rows & status
- total rows: **{len(rows)}** · ok: **{len(ok_rows)}** · error: **{len(err_rows)}** · status_counts: {dict(status_counts)}

## Coverage
- words {len(words)} · arms {arms} · tasks {tasks} · models {len(models)} · seeds {seeds}
- expected cells: **{expected_cells}** · unique ok keys: **{len(uniq_ok_keys)}** · **full 4800: {coverage_full}** · duplicate keys: {len(dup_keys)}
- per-arm (ok): {dict(per_arm)}
- per-model (ok): {dict(per_model)}

## Schema & flags
- missing required fields: {missing_fields or 'NONE'} · empty generation rows: {len(empty_gen)}
- mock values: {dict(mock_vals)} · all real (mock=false): **{all_real}**
- is_b1_1_evidence values: {dict(evid_vals)}  *(None expected — run predates the label fix; mock=false is the authoritative real-marker)*

## Manifest binding & frozen integrity
- row manifest_sha256 (unique): {[s[:16] for s in row_manifest_shas]} · matches current manifest: **{manifest_matches_current}** · frozen integrity: **{frozen_ok}**

## Leak re-scan (blinding)
- **prompt/conditioning leak (must be 0): {prompt_leak_total}**
- generation_text leak hits: **{gen_leak_total}** · by arm: {dict(leak['generation_text']['by_arm'])} · by category: {dict(leak['generation_text']['by_cat'])}
- (generation-text leaks, if any, must be repaired/blinded before judge packets; watch for arm-correlated Sanskrit/IAST.)

## Blockers ({len(blockers)})
{chr(10).join('- ' + b for b in blockers) or '_none_'}

## Flags ({len(flags)})
{chr(10).join('- ' + f for f in flags) or '_none_'}

## Final status
```
audit_status:          {status}
rows / ok / error:     {len(rows)} / {len(ok_rows)} / {len(err_rows)}
coverage_full_4800:    {coverage_full}
all_real (mock=false): {all_real}
frozen_integrity:      {frozen_ok}
prompt/cond leak:      {prompt_leak_total}
generation leak:       {gen_leak_total}
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
```
`R_deranged` remains the crux. **Structure, not validated meaning.** No judging/scoring performed.
"""
(HERE / "B1_1_POST_GENERATION_RAW_OUTPUT_AUDIT.md").write_text(md, encoding="utf-8")

print(f"STATUS: {status}")
print(f"  file_sha256 match: {sha_ok} ({file_sha[:16]})")
print(f"  rows {len(rows)} | ok {len(ok_rows)} | error {len(err_rows)} | full4800 {coverage_full}")
print(f"  all_real(mock=false) {all_real} | frozen_integrity {frozen_ok} | manifest_matches {manifest_matches_current}")
print(f"  prompt/cond leak {prompt_leak_total} | generation leak {gen_leak_total} "
      f"{dict(leak['generation_text']['by_arm']) if gen_leak_total else ''}")
print(f"  blockers {len(blockers)} | flags {len(flags)}")
for b in blockers: print("   BLOCKER:", b)
for f in flags: print("   FLAG:", f)
print("  wrote B1_1_POST_GENERATION_RAW_OUTPUT_AUDIT.{json,md}")
print("  NO judging, NO scoring, NO packets. Track B BLOCKED.")
