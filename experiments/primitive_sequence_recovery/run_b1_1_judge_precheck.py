#!/usr/bin/env python3
"""B1.1 JUDGE-RUN PRECHECK — no-model readiness verification for the B1.1 judge run.

Verifies freeze integrity, packet integrity, judge-view conversion integrity, leakage, B1-judge-script
compatibility, judge-panel config, judge-model cache presence, output-path policy, and the exact judge-run
command / wrapper. NO LLM judging, NO scoring, NO model downloads, NO judge-output creation. Stdlib + file
inspection only.

    python3 experiments/primitive_sequence_recovery/run_b1_1_judge_precheck.py
"""
from __future__ import annotations
import collections, hashlib, json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_1_generation as R                          # leak_scan + frozen-config loading (no model)

PKTDIR = HERE / "b1_1_judge_packets"
BLINDED = PKTDIR / "blinded_pairwise_packets.jsonl"
PKT_MANIFEST = PKTDIR / "blinded_pairwise_packet_manifest.json"
SAMPLE = PKTDIR / "blinded_pairwise_packets.sample.jsonl"
VIEW = PKTDIR / "b1_1_judge_view.jsonl"
VIEW_MANIFEST = PKTDIR / "b1_1_judge_view_manifest.json"
JUDGE_SCRIPT = HERE / "run_b1_llm_judge.py"
JUDGE_PANEL_CFG = HERE / "b1_1_judge_panel_config.json"
EXPECT_PACKETS = 4200
JUDGES = ["meta-llama/Llama-3.1-8B-Instruct", "meta-llama/Meta-Llama-3-8B-Instruct", "google/gemma-2-9b-it"]
EXPECTED_OUT_DIR = "experiments/primitive_sequence_recovery/b1_1_judge_outputs/"
FORBIDDEN_SUBSTR = ("A_vs_", "R_deranged", "R_domain", "R_same", "control_arm", "conditioning",
                    "varṇa", "varna", "sanskrit")

blockers, flags, info = [], [], []


def loadl(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---- 1. manifest / freeze verification ----
freeze = {}
try:
    man = R.verify_frozen_or_abort(require_frozen=True)
    freeze = {"frozen": man.get("manifest_status") == "FROZEN",
              "generation_authorized": man.get("generation_authorized"),
              "freeze_status": man.get("freeze_status")}
    if man.get("generation_authorized") is not False:
        blockers.append("manifest generation_authorized is not False")
except SystemExit as e:
    blockers.append(f"frozen verification failed: {e}")
lex = R.load_frozen_configs(man)["lexicon"] if freeze.get("frozen") else \
      R.load_frozen_configs(R.verify_frozen_or_abort(require_frozen=False))["lexicon"]

# ---- 2. packet integrity ----
pkt = {"blinded_exists": BLINDED.exists(), "manifest_exists": PKT_MANIFEST.exists(),
       "sample_exists": SAMPLE.exists()}
if not BLINDED.exists():
    blockers.append("blinded_pairwise_packets.jsonl missing")
    packets = []
else:
    packets = loadl(BLINDED)
pkt["packet_count"] = len(packets)
if len(packets) != EXPECT_PACKETS:
    blockers.append(f"packet count {len(packets)} != {EXPECT_PACKETS}")
pm = json.loads(PKT_MANIFEST.read_text(encoding="utf-8"))["B1_1_BLINDED_PACKET_MANIFEST"] \
    if PKT_MANIFEST.exists() else {}
truth = pm.get("truth_map", {})
per_comp = collections.Counter(t.get("comparison") for t in truth.values())
pkt["per_comparison"] = dict(per_comp)
if PKT_MANIFEST.exists():
    if len(truth) != len(packets):
        blockers.append(f"truth_map size {len(truth)} != packet count {len(packets)}")
    if set(per_comp) != {f"A_vs_{c}" for c in ("D", "S", "R_same", "R_deranged", "R_domain", "C", "X")}:
        blockers.append(f"comparisons in truth_map != the 7 expected: {sorted(per_comp)}")
    if per_comp and (min(per_comp.values()) != 600 or max(per_comp.values()) != 600):
        blockers.append(f"per-comparison counts not all 600: {dict(per_comp)}")
    REQ_TRUTH = ("comparison", "a_output_position", "output_1_arm", "output_2_arm", "raw_key_A",
                 "raw_key_control", "model_id", "seed", "task_id", "target_word")
    incomplete = [pid for pid, tm in truth.items() if any(k not in tm for k in REQ_TRUTH)]
    if incomplete:
        blockers.append(f"{len(incomplete)} truth entries incomplete (e.g. {incomplete[:3]})")
    pkt["truth_complete"] = not incomplete
else:
    blockers.append("packet manifest (truth_map) missing — scoring cannot map results")

# ---- 3. judge-view conversion integrity ----
jv = {"view_exists": VIEW.exists()}
if not VIEW.exists():
    blockers.append("b1_1_judge_view.jsonl missing — run run_b1_1_packets_to_judge_view.py first")
    views = []
else:
    views = loadl(VIEW)
jv["view_count"] = len(views)
if len(views) != EXPECT_PACKETS:
    blockers.append(f"judge-view count {len(views)} != {EXPECT_PACKETS}")
disp_ids = [v.get("display_id") for v in views]
jv["unique_display_ids"] = len(set(disp_ids))
if len(set(disp_ids)) != len(views):
    blockers.append("judge-view display_ids not unique")
bad_view = []
for v in views:
    ok = (set(v.keys()) == {"display_id", "key_word", "task_text", "outputs"}
          and isinstance(v.get("outputs"), list) and len(v["outputs"]) == 2
          and all(set(o.keys()) == {"id", "text"} for o in v["outputs"]))
    if not ok:
        bad_view.append(v.get("display_id"))
if bad_view:
    blockers.append(f"{len(bad_view)} judge-view records have wrong shape (e.g. {bad_view[:3]})")
jv["all_records_well_formed"] = not bad_view
# display_id maps back to truth
if truth:
    unmapped = [d for d in disp_ids if d not in truth]
    if unmapped:
        blockers.append(f"{len(unmapped)} view display_ids not in truth_map (mapping broken)")
    jv["all_mappable_to_truth"] = not unmapped

# ---- 4. leak check (blinded packets + judge view) ----
def scan_records(records, fields_getter):
    total, substr_hits, examples = 0, [], []
    for rec in records:
        blob = " \n ".join(fields_getter(rec))
        t, hits = R.leak_scan(blob, lex)
        total += t
        for s in FORBIDDEN_SUBSTR:
            if s in json.dumps(rec, ensure_ascii=False):
                substr_hits.append((rec.get("display_id") or rec.get("packet_id"), s))
        if (t or substr_hits) and len(examples) < 5:
            examples.append({"id": rec.get("display_id") or rec.get("packet_id"),
                             "hits": {k: v for k, v in hits.items() if v}})
    return total, substr_hits, examples

view_leak, view_substr, view_ex = scan_records(
    views, lambda v: [v["task_text"], v["outputs"][0]["text"], v["outputs"][1]["text"]])
pkt_leak, pkt_substr, pkt_ex = scan_records(
    packets, lambda p: [p["task_instruction"], p["output_1"]["text"], p["output_2"]["text"]])
leak = {"judge_view_leak": view_leak, "judge_view_substr": view_substr[:5],
        "packet_leak": pkt_leak, "packet_substr": pkt_substr[:5]}
if view_leak or view_substr:
    blockers.append(f"LEAK in judge-view: leak={view_leak} substr={view_substr[:3]}")
if pkt_leak or pkt_substr:
    blockers.append(f"LEAK in blinded packets: leak={pkt_leak} substr={pkt_substr[:3]}")

# ---- 5. B1 judge script compatibility (text inspection) ----
js = {}
if not JUDGE_SCRIPT.exists():
    blockers.append("run_b1_llm_judge.py missing")
    src = ""
else:
    src = JUDGE_SCRIPT.read_text(encoding="utf-8")
checks_txt = {
    "JUDGE_PROMPT": "JUDGE_PROMPT" in src,
    "parser_extract_balanced": "_extract_balanced" in src or "parse_judge_response" in src,
    "missing_final_brace_repair": "missing_final_brace" in src,
    "build_attention_checks": "build_attention_checks" in src,
    "attention_seed_90311": "90311" in src,
    "n_attention_24": "N_ATTENTION = 24" in src or "N_ATTENTION=24" in src,
    "attention_exclusion_rule": "attention_excluded" in src,
    "real_judge_adapter": "LlamaJudgeAdapter" in src,
    "declared_panel_has_3_models": all(j in src for j in JUDGES),
    "judge_view_schema_task_text_outputs": 'view["task_text"]' in src and 'view["outputs"]' in src,
}
js["text_checks"] = checks_txt
for k, v in checks_txt.items():
    if not v:
        blockers.append(f"judge script missing/!= expected: {k}")
# detect the hardcoded input/output paths -> wrapper needed for B1.1
hardcoded_view = 'JUDGE_VIEW = HERE / "b1_judge_view.jsonl"' in src
out_dir_here = "OUT_DIR = HERE" in src
js["reads_hardcoded_b1_view"] = hardcoded_view
js["writes_to_here_b1_prefix"] = out_dir_here
wrapper_needed = hardcoded_view or out_dir_here
if wrapper_needed:
    flags.append("B1 judge reads hardcoded JUDGE_VIEW=b1_judge_view.jsonl and writes b1_judge_responses_* "
                 "to HERE; a thin B1.1 wrapper is required to point it at the B1.1 view + a separate output "
                 "dir (see judge_run_command). Non-blocking adaptation.")

# ---- 6. judge panel config ----
jp = json.loads(JUDGE_PANEL_CFG.read_text(encoding="utf-8")) if JUDGE_PANEL_CFG.exists() else {}
jpc = {
    "three_models": jp.get("judge_model_ids") == JUDGES,
    "meta_llama3_accept_with_caveat": (jp.get("judge_caveats", {}).get("meta_llama3_status")
                                       == "WARNING_ACCEPTANCE_REQUIRED"),
    "no_post_hoc_judge_selection": jp.get("no_post_hoc_judge_selection") is True,
    "replacement_policy": bool(jp.get("replacement_policy")),
    "parser_rules": bool(jp.get("parser_rules")),
    "output_schema": bool(jp.get("output_schema")),
}
# ACCEPT_WITH_CAVEAT decision must be recorded in the frozen manifest
jpc["accept_with_caveat_in_manifest"] = (
    freeze.get("frozen") and man.get("judge_panel_warning_decision", {}).get("decision") == "ACCEPT_WITH_CAVEAT")
for k, v in jpc.items():
    if not v:
        blockers.append(f"judge panel config check failed: {k}")

# ---- 6b. judge-model cache presence (existence + size only; no download, no load) ----
hf_home = os.environ.get("HF_HOME") or str(pathlib.Path.home() / ".cache/huggingface")
hub = pathlib.Path(hf_home) / "hub"
cache = {"hf_home": hf_home, "hub_exists": hub.exists(), "models": {}}
if hub.exists():
    for j in JUDGES:
        d = hub / f"models--{j.replace('/', '--')}"
        if d.exists():
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            cache["models"][j] = {"present": True, "gb": round(size / 1e9, 1)}
            if size < 5e9:
                flags.append(f"judge model {j} cache only {round(size/1e9,1)}GB — may be truncated")
        else:
            cache["models"][j] = {"present": False}
            blockers.append(f"judge model {j} not in cache {hub}")
else:
    info.append(f"HF cache hub not found at {hub} — model-cache presence not verifiable in this "
                "environment (verify on the model-access host: all three judge dirs must be ~15-18GB).")

# ---- 7/8. output-path policy + judge-run command / wrapper ----
wrapper_code = (
    "# experiments/primitive_sequence_recovery/run_b1_1_judge.py  (to author at B1_1_JUDGE_RUN)\n"
    "import pathlib, sys\n"
    "HERE = pathlib.Path(__file__).resolve().parent\n"
    "sys.path.insert(0, str(HERE))\n"
    "import run_b1_llm_judge as J          # reuse frozen prompt/parser/attention/adapters/panel\n"
    "J.JUDGE_VIEW = HERE / 'b1_1_judge_packets' / 'b1_1_judge_view.jsonl'\n"
    "J.OUT_DIR   = HERE / 'b1_1_judge_outputs'\n"
    "J.OUT_DIR.mkdir(parents=True, exist_ok=True)\n"
    "if __name__ == '__main__':\n"
    "    J.main()\n")
judge_run_command = ("tmux new -s b11_judge ; "
                     "python3 experiments/primitive_sequence_recovery/run_b1_1_judge.py --judge all")

# ---- verdict ----
status = ("BLOCKED" if blockers else ("REVIEW_REQUIRED" if flags else "PASS_JUDGE_PRECHECK"))

report = {
    "artifact": "b1_1_judge_run_precheck_report", "status": status,
    "scope": "no-model readiness precheck — NO LLM judging, NO scoring, NO downloads, NO judge outputs",
    "freeze": freeze, "packet_integrity": pkt, "judge_view_integrity": jv, "leak_check": leak,
    "judge_script_compat": js, "judge_panel_config": jpc, "model_cache": cache,
    "judge_output_dir_policy": {"expected_dir": EXPECTED_OUT_DIR,
                                "per_judge_file": "b1_judge_responses_<slug>.jsonl (from run_b1_llm_judge)",
                                "no_overwrite_without_resume": True, "created_now": False},
    "judge_run": {"wrapper_needed": wrapper_needed, "wrapper_path": "run_b1_1_judge.py",
                  "wrapper_code": wrapper_code, "command": judge_run_command,
                  "note": "wrapper reuses the FROZEN B1 judge prompt/parser/attention/adapters/panel "
                          "verbatim; only overrides input/output paths. Do NOT modify run_b1_llm_judge.py."},
    "judging_run": False, "scoring_run": False,
    "blockers": blockers, "flags": flags, "info": info,
    "anchors": {"b1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b": "BLOCKED",
                "positive_cap": "LIMITED_GENERATION_UTILITY", "crux": "R_deranged"},
    "non_claims": ["no judging", "no scoring", "no model calls", "structure not validated meaning"],
    "next_gate": ("B1_1_JUDGE_RUN" if status == "PASS_JUDGE_PRECHECK" else
                  "B1_1_JUDGE_PRECHECK_ADJUDICATION" if status == "REVIEW_REQUIRED" else
                  "B1_1_JUDGE_PRECHECK_FIX"),
}
(HERE / "B1_1_JUDGE_RUN_PRECHECK_REPORT.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

md = f"""# B1.1 Judge-Run Precheck Report

## Status: `{status}`

No-model readiness verification for the B1.1 judge run. **No LLM judging, no scoring, no downloads, no judge
outputs.** Does not change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`) or unblock Track B (**BLOCKED**).
**Structure, not validated meaning.**

## 1. Freeze
- frozen: **{freeze.get('frozen')}** · generation_authorized: **{freeze.get('generation_authorized')}** · {freeze.get('freeze_status')}

## 2. Packet integrity
- blinded packets: {pkt.get('packet_count')} (want {EXPECT_PACKETS}) · manifest: {pkt.get('manifest_exists')} · sample: {pkt.get('sample_exists')}
- per-comparison: {pkt.get('per_comparison')}
- truth_map complete: {pkt.get('truth_complete')}

## 3. Judge-view integrity
- view count: {jv.get('view_count')} (want {EXPECT_PACKETS}) · unique display_ids: {jv.get('unique_display_ids')}
- all records well-formed (display_id/key_word/task_text/outputs[2]): {jv.get('all_records_well_formed')}
- all mappable to truth via display_id==packet_id: {jv.get('all_mappable_to_truth')}

## 4. Leak check
- judge-view leak: **{leak['judge_view_leak']}** · substr: {leak['judge_view_substr'] or 'NONE'}
- blinded-packet leak: **{leak['packet_leak']}** · substr: {leak['packet_substr'] or 'NONE'}

## 5. B1 judge script compatibility
{chr(10).join(f"- [{'ok' if v else 'FAIL'}] {k}" for k, v in checks_txt.items())}
- reads hardcoded B1 view path: **{js.get('reads_hardcoded_b1_view')}** · writes to HERE (b1 prefix): **{js.get('writes_to_here_b1_prefix')}**
- **wrapper needed: {wrapper_needed}** (see §8)

## 6. Judge panel config + model cache
{chr(10).join(f"- [{'ok' if v else 'FAIL'}] {k}" for k, v in jpc.items())}
- HF cache hub: `{cache['hf_home']}/hub` (exists: {cache['hub_exists']})
- models: {cache['models'] or 'not verifiable here (check on pod)'}

## 7. Judge output path policy
- expected dir: `{EXPECTED_OUT_DIR}` · per-judge file: `b1_judge_responses_<slug>.jsonl` · no overwrite without resume · **not created now**

## 8. Judge-run command / wrapper (author at B1_1_JUDGE_RUN — do NOT run now)
The committed B1 judge reads a hardcoded `JUDGE_VIEW=b1_judge_view.jsonl` and writes to `HERE`. Reuse it
verbatim via a thin wrapper that only overrides the paths (do **not** edit `run_b1_llm_judge.py`):

```python
{wrapper_code}```
Run (multi-hour; 3 models × ~4224 items):
```
{judge_run_command}
```

## Blockers ({len(blockers)})
{chr(10).join('- ' + b for b in blockers) or '_none_'}

## Flags ({len(flags)}) / Info ({len(info)})
{chr(10).join('- flag: ' + f for f in flags) or ''}
{chr(10).join('- info: ' + i for i in info) or '_none_'}

## Final status
```
precheck:              {status}
packets / views:       {pkt.get('packet_count')} / {jv.get('view_count')} (want {EXPECT_PACKETS})
judge-view leak:       {leak['judge_view_leak']}
wrapper needed:        {wrapper_needed}
judging run:           NO
scoring run:           NO
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
```
Next gate: **{report['next_gate']}**. `R_deranged` remains the crux. **Structure, not validated meaning.**
"""
(HERE / "B1_1_JUDGE_RUN_PRECHECK_REPORT.md").write_text(md, encoding="utf-8")

print(f"STATUS: {status}")
print(f"  packets {pkt.get('packet_count')} | views {jv.get('view_count')} | "
      f"view_leak {leak['judge_view_leak']} | packet_leak {leak['packet_leak']}")
print(f"  judge-script compat all-ok: {all(checks_txt.values())} | wrapper_needed {wrapper_needed}")
print(f"  panel-config all-ok: {all(jpc.values())} | cache_hub_exists {cache['hub_exists']}")
print(f"  blockers {len(blockers)} | flags {len(flags)} | info {len(info)}")
for b in blockers: print("   BLOCKER:", b)
for f in flags: print("   FLAG:", f)
for i in info: print("   info:", i)
print(f"  wrote B1_1_JUDGE_RUN_PRECHECK_REPORT.{{json,md}} | next: {report['next_gate']}")
print("  NO judging, NO scoring, NO model calls. Track B BLOCKED.")
