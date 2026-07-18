#!/usr/bin/env python3
"""B1.1 judge-output POSTCHECK — reconstruct per-judge provenance + verify completeness from the judge
output files. NO models, NO scoring, NO verdict. Rebuilds the frozen attention checks (seed 90311) to
recompute attn_fail/exclusion; verifies coverage (4200 real + 24 attn per judge), parse health,
duplicates, and view-id coverage. Writes a report and prints a per-judge table.

    python3 experiments/primitive_sequence_recovery/run_b1_1_judge_postcheck.py
"""
from __future__ import annotations
import collections, hashlib, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_llm_judge as J          # DECLARED_JUDGES, build_attention_checks, attention_excluded, etc.

OUTDIR = HERE / "b1_1_judge_outputs"
VIEW = HERE / "b1_1_judge_packets" / "b1_1_judge_view.jsonl"
EXPECT_REAL = 4200
N_JUDGES_MIN = 3                                       # B1 JUDGING n_judges_min

blockers, flags, info, per_judge = [], [], [], []

attn = J.build_attention_checks()                     # frozen: n=24, seed 90311
attn_correct = {a["display_id"]: a["_attn_correct"] for a in attn}
n_attn = len(attn)
view_ids = ({json.loads(l)["display_id"] for l in VIEW.read_text(encoding="utf-8").splitlines() if l.strip()}
            if VIEW.exists() else set())

kept = 0
for jid in J.DECLARED_JUDGES:
    slug = J.judge_slug(jid)
    path = OUTDIR / f"b1_judge_responses_{slug}.jsonl"
    if not path.exists():
        blockers.append(f"missing judge output: {path.name}")
        per_judge.append({"judge": slug, "present": False})
        continue
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    real = [r for r in recs if r.get("kind") == "real"]
    attn_recs = [r for r in recs if r.get("kind") == "attn"]
    real_ids = [r["display_id"] for r in real]
    dups = [d for d, c in collections.Counter(real_ids).items() if c > 1]
    parse_fail = sum(1 for r in recs if not r.get("parse_ok"))
    repaired = sum(1 for r in recs if r.get("parse_repair"))
    flagged = sum(1 for r in real if (not r.get("parse_ok")) or r.get("choice") in J.FLAGGED_CHOICES)
    attn_fail = sum(1 for r in attn_recs if r.get("choice") != attn_correct.get(r["display_id"]))
    excluded = J.attention_excluded(attn_fail, n_attn)
    choice_dist = dict(collections.Counter(r.get("choice") for r in real))
    missing = (view_ids - set(real_ids)) if view_ids else set()
    out_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    if len(real) != EXPECT_REAL:
        blockers.append(f"{slug}: real {len(real)} != {EXPECT_REAL}")
    if len(attn_recs) != n_attn:
        blockers.append(f"{slug}: attn {len(attn_recs)} != {n_attn}")
    if dups:
        blockers.append(f"{slug}: {len(dups)} duplicate real display_ids (resume/mixing issue)")
    if view_ids and missing:
        blockers.append(f"{slug}: {len(missing)} view ids missing from output (e.g. {sorted(missing)[:3]})")
    if repaired:
        info.append(f"{slug}: {repaired} records used missing-final-brace repair (frozen, allowed).")
    if excluded:
        flags.append(f"{slug}: EXCLUDED by attention rule (attn_fail {attn_fail}/{n_attn}).")
    else:
        kept += 1
    per_judge.append({"judge": slug, "present": True, "n_records": len(recs), "n_real": len(real),
                      "n_attn": len(attn_recs), "attn_fail": attn_fail, "excluded": excluded,
                      "parse_fail": parse_fail, "repaired": repaired, "flagged": flagged,
                      "choice_distribution": choice_dist, "duplicate_real_ids": len(dups),
                      "missing_view_ids": len(missing), "out_sha256": out_sha})

if kept < N_JUDGES_MIN:
    blockers.append(f"only {kept} judges kept (< min {N_JUDGES_MIN}); replacement policy / adjudication "
                    "required before scoring (no post-hoc selection).")

status = ("BLOCKED" if blockers else ("REVIEW_REQUIRED" if flags else "PASS_JUDGE_POSTCHECK"))

report = {
    "artifact": "b1_1_judge_output_postcheck", "status": status,
    "scope": "reconstructed provenance + completeness — NO models, NO scoring, NO verdict",
    "expected_real_per_judge": EXPECT_REAL, "n_attention": n_attn,
    "judges_kept": kept, "n_judges_min": N_JUDGES_MIN, "per_judge": per_judge,
    "blockers": blockers, "flags": flags, "info": info,
    "anchors": {"b1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b": "BLOCKED",
                "positive_cap": "LIMITED_GENERATION_UTILITY", "crux": "R_deranged"},
    "non_claims": ["no scoring", "no verdict", "choices only", "structure not validated meaning"],
    "next_gate": ("B1_1_SCORING" if status == "PASS_JUDGE_POSTCHECK" else
                  "B1_1_JUDGE_EXCLUSION_ADJUDICATION" if status == "REVIEW_REQUIRED" else
                  "B1_1_JUDGE_RUN_FIX"),
}
(HERE / "B1_1_JUDGE_RUN_POSTCHECK_REPORT.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

md = [f"# B1.1 Judge-Output Postcheck\n\n## Status: `{status}`\n",
      "Reconstructed per-judge provenance + completeness from the judge output files. **No models, no "
      "scoring, no verdict.** B1 verdict `RANDOM_OR_SCRAMBLED_MATCHES`; Track B **BLOCKED**. Structure, not "
      "validated meaning.\n",
      f"- judges kept: **{kept}** / min {N_JUDGES_MIN} · expected real per judge: **{EXPECT_REAL}** · "
      f"attention: **{n_attn}**\n",
      "| judge | records | real | attn | attn_fail | excluded | parse_fail | repaired | flagged | dups |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for p in per_judge:
    if p.get("present"):
        md.append(f"| {p['judge']} | {p['n_records']} | {p['n_real']} | {p['n_attn']} | {p['attn_fail']} | "
                  f"{p['excluded']} | {p['parse_fail']} | {p['repaired']} | {p['flagged']} | "
                  f"{p['duplicate_real_ids']} |")
    else:
        md.append(f"| {p['judge']} | MISSING | | | | | | | | |")
md += ["",
       "## Choice distributions (real items)"]
for p in per_judge:
    if p.get("present"):
        md.append(f"- **{p['judge']}**: {p['choice_distribution']}")
md += ["", f"## Blockers ({len(blockers)})", "\n".join('- ' + b for b in blockers) or "_none_",
       "", f"## Flags ({len(flags)})", "\n".join('- ' + f for f in flags) or "_none_",
       "", f"## Info ({len(info)})", "\n".join('- ' + i for i in info) or "_none_",
       "", "```", f"postcheck:     {status}", f"judges_kept:   {kept}/{N_JUDGES_MIN}",
       "B1 verdict:    RANDOM_OR_SCRAMBLED_MATCHES (unchanged)", "Track B:       BLOCKED", "```",
       f"Next gate: **{report['next_gate']}**. `R_deranged` remains the crux. Structure, not validated meaning."]
(HERE / "B1_1_JUDGE_RUN_POSTCHECK_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"STATUS: {status} | judges_kept {kept}/{N_JUDGES_MIN}")
print(f"{'judge':<26} {'real':>5} {'attn':>4} {'aFail':>5} {'excl':>5} {'pFail':>5} {'repair':>6} {'flag':>5} {'dup':>4}")
for p in per_judge:
    if p.get("present"):
        print(f"{p['judge']:<26} {p['n_real']:>5} {p['n_attn']:>4} {p['attn_fail']:>5} "
              f"{str(p['excluded']):>5} {p['parse_fail']:>5} {p['repaired']:>6} {p['flagged']:>5} "
              f"{p['duplicate_real_ids']:>4}")
    else:
        print(f"{p['judge']:<26} MISSING")
for b in blockers: print("  BLOCKER:", b)
for f in flags: print("  FLAG:", f)
for i in info: print("  info:", i)
print(f"  wrote B1_1_JUDGE_RUN_POSTCHECK_REPORT.{{json,md}} | next: {report['next_gate']}")
print("  NO scoring, NO verdict. Track B BLOCKED.")
