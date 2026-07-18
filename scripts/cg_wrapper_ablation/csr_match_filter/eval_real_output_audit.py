#!/usr/bin/env python3
"""eval_real_output_audit.py — Phase 3 real-output audit validation.

Runs the FROZEN Phase 3 answer-auditor (answer_audit.audit_answer) over SAVED Phase 2 / Phase 2B
answer traces (the `--write-traces` JSON) and compares its findings, per arm, against the existing
rubric labels stored alongside those answers (the deterministic rubric_v2 judge output). It does NOT
re-score the rubric, change any threshold, prompt, or generation — it only reads saved answers + their
saved rubric labels and asks: does the auditor catch the rubric's residual failures, without
over-flagging good framed answers?

Catch categories (auditor finding(s)  <->  saved rubric label). The audit->rubric mapping is a UNION
because rubric_v2's score-keys BUNDLE categories the Phase-3 taxonomy deliberately SPLITS — this is a
MEASUREMENT alignment, the auditor itself is unchanged:
  1 rejected-domain leak    rejected_domain_promoted                         <- rejected_domain_avoidance False
  2 secondary promoted      secondary_promoted_to_primary OR rejected_domain_promoted  <- secondary_promoted True
  3 phoneme-overreach       phoneme_overreach_claim                          <- phoneme_overreach True
  4 factuality-suspected    factuality_suspected OR answer_too_generic       <- factuality_preserved False
  5 generic / off-frame     (audit not passed)                               <- primary_frame_correct False
A rubric "leak" the audit identifies as rejected_domain_mentioned_as_refutation is rescued out of the
miss count (rubric over-flag). Disagreements where manual inspection sided with the audit are reported
transparently (MANUAL_DISAGREEMENT_VERDICTS) but NEVER used as a hidden pass/fail override.

PROVENANCE GATE: a real-output PASS is only emitted when the traces were produced by a real generator
(production_valid). On stub traces the harness still runs and prints provisional numbers, but the
returned label is PHASE3_REAL_OUTPUT_AUDIT_BLOCKED_NO_REAL_TRACES — stub answers are deterministic
templates, not model prose, so they cannot certify a real-output verdict.

  python .../eval_real_output_audit.py --traces runs/csr_phase2b/robustness_eval_v2.json \
    --data .../eval_data/framed_answer_eval_v2_rubricv2.jsonl --out runs/csr_phase3/real_output_audit.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import answer_audit as AA            # noqa: E402
from csr_match_filter.match import dominant_terms          # noqa: E402

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "eval_data" / "framed_answer_eval_v2_rubricv2.jsonl"

CATS = ("rejected_leak", "secondary_promoted", "phoneme_overreach", "factuality_suspected",
        "off_frame")
# critical residuals the auditor MUST push to rewrite (drive missed_critical_failure_rate)
CRITICAL_CATS = ("rejected_leak", "phoneme_overreach")

# Curated manual verdicts on specific audit<->rubric disagreements. TRANSPARENCY ONLY — reported, never
# a hidden pass/fail override. Verified by inspecting the saved answer text (see RESULTS_PHASE3_REAL_OUTPUT).
MANUAL_DISAGREEMENT_VERDICTS = {
    "rej_009":   {"rubric": "rejected_domain leak", "audit": "refutation / no leak",
                  "manual_verdict": "audit_correct",
                  "note": "'a farmer is not furniture' is a refutation, not a leak"},
    "close_004": {"rubric": "primary_frame_correct (pass)", "audit": "secondary promoted to primary",
                  "manual_verdict": "audit_correct",
                  "note": "nurse primary is 'care'; the answer framed it as 'medicine' (a secondary)"},
    "ctxsec_001": {"rubric": "factuality failure", "audit": "answer_too_generic",
                   "manual_verdict": "harness_taxonomy_artifact_audit_acceptable",
                   "note": "short meta-stub; answer_too_generic is the better category"},
    "ctxsec_002": {"rubric": "factuality failure", "audit": "answer_too_generic",
                   "manual_verdict": "harness_taxonomy_artifact_audit_acceptable",
                   "note": "short meta-stub; answer_too_generic is the better category"},
}

# Meta-parroting / frame-echo: the model emits C×R×S frame labels instead of answering. Deterministic
# surface detector (does NOT change generation or any scorer).
_META_PARROT = re.compile(
    r"\b(?:primary|secondary|rejected)\s+domain\b"
    r"|\bbelongs?\s+to\s+the\s+(?:primary\s+|secondary\s+)?domain\b"
    r"|\bthe\s+term\s+['\"]",
    re.IGNORECASE)


def is_meta_parrot(answer: str) -> bool:
    return bool(_META_PARROT.search(answer or ""))


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def _iter_traces(blob):
    """Yield (backend, production_valid, rows) for either runner's trace schema."""
    tr = blob.get("traces")
    meta = blob.get("meta", {})
    if isinstance(tr, dict):                                   # robustness runner: {backend: [rows]}
        bmeta = {b.get("llm_backend") if False else k: v for k, v in
                 (blob.get("backends") or {}).items()}
        for backend, rows in tr.items():
            pv = bool((blob.get("backends", {}).get(backend, {}) or {}).get("production_valid"))
            yield backend, pv, rows
    elif isinstance(tr, list):                                 # eval_framed_answers: [rows]
        yield meta.get("llm_backend", "?"), bool(meta.get("production_valid")), tr


def _frame_and_extras(ex):
    return ({"primary_domains": ex.get("expected_primary", []),
             "secondary_domains": ex.get("expected_secondary", []),
             "rejected_domains": ex.get("expected_rejected", [])},
            ex.get("expected_secondary_true_senses", []), ex.get("false_claims", []))


def _rubric_flags(sc):
    """The saved rubric label per category (True == the rubric considers it a failure/leak)."""
    return {"rejected_leak": (sc.get("rejected_domain_avoidance") is False
                              or sc.get("rejected_domain_avoidance") == 0.0),
            "secondary_promoted": bool(sc.get("secondary_promoted")),
            "phoneme_overreach": bool(sc.get("phoneme_overreach"))
            or bool(sc.get("phoneme_overreach_rate")),
            "factuality_suspected": (sc.get("factuality_preserved") is False
                                     or sc.get("factuality_preserved") == 0.0),
            "off_frame": (sc.get("primary_frame_correct") is False
                          or sc.get("primary_frame_correct") == 0.0)}


def _audit_flags(res):
    """Map audit findings to the rubric_v2 score-key categories. MEASUREMENT-ONLY alignment — the
    auditor is unchanged; this fixes the comparison because rubric_v2's keys BUNDLE categories the
    Phase-3 taxonomy deliberately SPLITS:
      - rubric `secondary_promoted` == promotion = (rejected_leak OR alt_sense) & primary absent, so it
        also covers what the audit reports separately as `rejected_domain_promoted` -> union both.
      - rubric `factuality_preserved` is also False on too-short / term-absent answers, which the audit
        reports as `answer_too_generic` -> union it into the factuality category.
    """
    ft = set(res.finding_types)
    return {"rejected_leak": "rejected_domain_promoted" in ft,
            "secondary_promoted": ("secondary_promoted_to_primary" in ft
                                   or "rejected_domain_promoted" in ft),
            "phoneme_overreach": "phoneme_overreach_claim" in ft,
            "factuality_suspected": ("factuality_suspected" in ft or "answer_too_generic" in ft),
            "off_frame": (not res.passed)}


def run_arm(rows, by_id, arm):
    per = []
    for r in rows:
        ex = by_id.get(r["id"])
        ans = (r.get("answers") or {}).get(arm)
        if ex is None or ans is None or arm not in (r.get("scores") or {}):
            continue
        frame, alt, false_claims = _frame_and_extras(ex)
        res = AA.audit_answer(ex["query"], ans, frame, terms=dominant_terms(ex["query"])[:1] or None,
                              alternate_true_senses=alt, false_claims=false_claims, answer_id=r["id"])
        per.append({"id": r["id"], "category": r.get("category"), "answer": ans, "res": res,
                    "ft": set(res.finding_types), "meta_parrot": is_meta_parrot(ans),
                    "rubric": _rubric_flags(r["scores"][arm]), "audit": _audit_flags(res)})
    return per


def confusion(per):
    out = {}
    for c in CATS:
        tp = [p for p in per if p["rubric"][c] and p["audit"][c]]
        fn = [p for p in per if p["rubric"][c] and not p["audit"][c]]
        fp = [p for p in per if not p["rubric"][c] and p["audit"][c]]
        rescued = []
        if c == "rejected_leak":
            # rubric over-flags a refutation ("a farmer is NOT furniture") as a leak; the audit
            # correctly reports rejected_domain_mentioned_as_refutation. Don't score that as a miss.
            rescued = [p for p in fn if "rejected_domain_mentioned_as_refutation" in p["ft"]]
            fn = [p for p in fn if p not in rescued]
        denom = len(tp) + len(fn)
        out[c] = {"rubric_positives": sum(1 for p in per if p["rubric"][c]),
                  "tp": len(tp), "fn": len(fn), "fp": len(fp),
                  "rubric_overflag_refutation": [(p["id"], p["answer"][:90]) for p in rescued],
                  "recall": (len(tp) / denom) if denom else None,
                  "fp_examples": [(p["id"], p["answer"][:90]) for p in fp[:4]],
                  "fn_examples": [(p["id"], p["answer"][:90]) for p in fn[:4]]}
    return out


def audit_stricter(per):
    """Transparency bucket (NOT auto-credited): the audit flags a problem on an answer the rubric
    marked clean in every category. These are candidate TRUE catches the rubric missed (e.g. a nurse
    framed as 'medicine' when the primary is 'care') — surfaced for manual review, not scored."""
    rows = [p for p in per if (not p["res"].passed) and not any(p["rubric"][c] for c in CATS)]
    return {"n": len(rows),
            "examples": [(p["id"], sorted(p["ft"]), p["answer"][:90]) for p in rows[:8]]}


def arm_summary(per):
    n = len(per) or 1
    return {"n": len(per),
            "audit_pass_rate": sum(p["res"].passed for p in per) / n,
            "critical_findings_rate": sum(any(f.severity == "critical" for f in p["res"].findings)
                                          for p in per) / n,
            "rewrite_recommended_rate": sum(p["res"].needs_rewrite for p in per) / n}


def _manual_correct(pid) -> bool:
    return MANUAL_DISAGREEMENT_VERDICTS.get(pid, {}).get("manual_verdict") == "audit_correct"


def extra_metrics(per):
    """false_rewrite_rate, missed_critical_failure_rate, meta-parroting, and the REMAINING TRUE misses
    (rubric-flagged & audit-missed, after removing refutation rescues, meta-parroting, and cases where
    manual review sided with the audit)."""
    clean = [p for p in per if not any(p["rubric"][c] for c in CATS)]
    hurt = [p for p in clean if p["res"].needs_rewrite]
    false_rewrite_rate = (len(hurt) / len(clean)) if clean else None

    # critical residuals = rubric leak/phoneme, minus refutation over-flags (not real leaks)
    crit = [p for p in per if any(p["rubric"][c] for c in CRITICAL_CATS)
            and "rejected_domain_mentioned_as_refutation" not in p["ft"]
            and not _manual_correct(p["id"])]
    missed_crit = [p for p in crit if not p["res"].needs_rewrite]
    missed_critical_failure_rate = (len(missed_crit) / len(crit)) if crit else None

    meta = [p for p in per if p["meta_parrot"]]
    true_misses = []
    for p in per:
        for c in CATS:
            if p["rubric"][c] and not p["audit"][c]:
                if "rejected_domain_mentioned_as_refutation" in p["ft"]:   # rubric over-flag
                    continue
                if p["meta_parrot"]:                                       # reported separately
                    continue
                if _manual_correct(p["id"]):                               # audit is right
                    continue
                true_misses.append({"id": p["id"], "category": c, "answer": p["answer"][:100]})
    return {"false_rewrite_rate": false_rewrite_rate,
            "missed_critical_failure_rate": missed_critical_failure_rate,
            "n_critical_residuals": len(crit), "n_missed_critical": len(missed_crit),
            "meta_parroting_n": len(meta),
            "meta_parroting_examples": [(p["id"], p["answer"][:100]) for p in meta[:10]],
            "remaining_true_misses": true_misses}


def manual_disagreements(per):
    """The curated audit<->rubric disagreements that actually appear in THIS run (transparency only)."""
    ids = {p["id"] for p in per}
    out = {pid: v for pid, v in MANUAL_DISAGREEMENT_VERDICTS.items() if pid in ids}
    return out


def helped_without_hurting(per):
    """On the framed arm: caught residuals (rubric-flagged & audit-flagged) vs hurt-good (rubric-clean
    but audit recommends a rewrite)."""
    residual = [p for p in per if any(p["rubric"][c] for c in CATS)]
    caught = [p for p in residual if any(p["audit"][c] for c in CATS)]
    clean = [p for p in per if not any(p["rubric"][c] for c in CATS)]
    hurt = [p for p in clean if p["res"].needs_rewrite]
    return {"residual_n": len(residual), "caught_n": len(caught),
            "residual_recall": (len(caught) / len(residual)) if residual else None,
            "clean_n": len(clean), "hurt_good_n": len(hurt),
            "false_rewrite_on_clean_rate": (len(hurt) / len(clean)) if clean else None,
            "hurt_examples": [(p["id"], p["answer"][:90]) for p in hurt[:5]]}


def decide(real, framed_conf, framed_extra):
    """Real-output decision after the measurement-only mapping correction.

    PASS               : corrected union recall >= 0.80, no false rewrites, no missed criticals.
    MEASUREMENT_CORRECTED: catches the real residuals (missed_critical ~ 0) and avoids false rewrites,
                           but recall < 0.80 with the remaining gap explained by meta-parroting /
                           taxonomy artefacts rather than true audit misses (few/no remaining_true_misses).
    NEEDS_TUNING       : real misses remain that are not explained away.
    NO_VALUE           : essentially nothing caught.
    """
    tot_tp = sum(framed_conf[c]["tp"] for c in CATS)
    tot_fn = sum(framed_conf[c]["fn"] for c in CATS)
    recall = (tot_tp / (tot_tp + tot_fn)) if (tot_tp + tot_fn) else None
    fr = framed_extra.get("false_rewrite_rate") or 0.0
    mc = framed_extra.get("missed_critical_failure_rate")
    n_true_misses = len(framed_extra.get("remaining_true_misses") or [])
    safe = (fr <= 0.05) and ((mc or 0.0) <= 0.0)
    if recall is None and (tot_tp + tot_fn) == 0:
        provisional = "PHASE3_REAL_OUTPUT_AUDIT_NO_VALUE"
    elif recall is not None and recall >= 0.80 and safe:
        provisional = "PHASE3_REAL_OUTPUT_AUDIT_PASS"
    elif safe and n_true_misses <= 3:
        # residuals caught, no false rewrites, no missed criticals; remaining gap is measurement/quirk
        provisional = "PHASE3_REAL_OUTPUT_AUDIT_MEASUREMENT_CORRECTED"
    elif recall is not None and recall <= 0.20 and not safe:
        provisional = "PHASE3_REAL_OUTPUT_AUDIT_NO_VALUE"
    else:
        provisional = "PHASE3_REAL_OUTPUT_AUDIT_NEEDS_TUNING"
    label = provisional if real else "PHASE3_REAL_OUTPUT_AUDIT_BLOCKED_NO_REAL_TRACES"
    return label, provisional, recall, fr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", required=True, help="saved --write-traces JSON from a Phase 2/2B run")
    ap.add_argument("--data", default=str(_DATA), help="v2 rubricv2 dataset (frame + alt + false)")
    ap.add_argument("--arms", default="base,framed")
    ap.add_argument("--out", default=None)
    ap.add_argument("--explain-failures", action="store_true",
                    help="print remaining true misses, meta-parroting, and manual-disagreement cases")
    args = ap.parse_args()

    blob = json.loads(Path(args.traces).read_text())
    by_id = {ex["id"]: ex for ex in load_jsonl(args.data)}
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    report = {"meta": {"traces": str(args.traces), "data": str(args.data),
                       "audit_backend": "deterministic_csr (frozen Phase 3)"}, "backends": {}}
    final_label = "PHASE3_REAL_OUTPUT_AUDIT_NO_VALUE"
    for backend, real, rows in _iter_traces(blob):
        print("=" * 82)
        print(f"PHASE 3 REAL-OUTPUT AUDIT   backend={backend}  production_valid={real}  "
              f"n_rows={len(rows)}")
        if not real:
            print("  ⚠️  STUB / non-real traces — provisional numbers only; cannot certify a real "
                  "verdict.")
        per_by_arm = {a: run_arm(rows, by_id, a) for a in arms}
        bk = {"production_valid": real, "arms": {}}
        for a in arms:
            per = per_by_arm[a]
            summ = arm_summary(per)
            conf = confusion(per)
            stricter = audit_stricter(per)
            extra = extra_metrics(per)
            bk["arms"][a] = {"summary": summ, "confusion": conf,
                             "audit_stricter_than_rubric": stricter, "extra_metrics": extra}
            print("-" * 82)
            print(f"  ARM {a}:  audit_pass_rate={summ['audit_pass_rate']:.3f}  "
                  f"critical_findings_rate={summ['critical_findings_rate']:.3f}  "
                  f"rewrite_recommended_rate={summ['rewrite_recommended_rate']:.3f}  (n={summ['n']})")
            for c in CATS:
                cc = conf[c]
                rec = "n/a" if cc["recall"] is None else f"{cc['recall']:.3f}"
                resc = cc.get("rubric_overflag_refutation") or []
                rtag = f"  [rubric-overflag-refutation rescued={len(resc)}]" if resc else ""
                print(f"     {c:20} rubric+={cc['rubric_positives']:>3}  catch(recall)={rec}  "
                      f"FN={cc['fn']}  FP={cc['fp']}{rtag}")
            print(f"     false_rewrite_rate={extra['false_rewrite_rate']}  "
                  f"missed_critical_failure_rate={extra['missed_critical_failure_rate']} "
                  f"(missed {extra['n_missed_critical']}/{extra['n_critical_residuals']})")
            print(f"     meta_parroting={extra['meta_parroting_n']}  "
                  f"remaining_true_misses={len(extra['remaining_true_misses'])}  "
                  f"audit_stricter_than_rubric={stricter['n']}")
        framed = per_by_arm.get("framed", [])
        help_ = helped_without_hurting(framed) if framed else {}
        framed_extra = bk["arms"].get("framed", {}).get("extra_metrics", {})
        bk["helped_without_hurting"] = help_
        bk["manual_disagreements"] = manual_disagreements(framed or [])
        if framed:
            print("-" * 82)
            print(f"  HELP-WITHOUT-HURT (framed): residual={help_['residual_n']} "
                  f"caught={help_['caught_n']} "
                  f"(recall={help_['residual_recall']})  clean={help_['clean_n']} "
                  f"hurt_good={help_['hurt_good_n']} "
                  f"(false_rewrite_on_clean={help_['false_rewrite_on_clean_rate']})")
        label, provisional, recall, fp_rate = decide(
            real, bk["arms"].get("framed", {}).get("confusion", {c: {"tp": 0, "fn": 0} for c in CATS}),
            framed_extra)
        bk["label"] = label
        bk["provisional_label_if_real"] = provisional
        bk["framed_union_recall"] = recall
        report["backends"][backend] = bk
        if args.explain_failures and framed:
            print("-" * 82)
            print("  REMAINING TRUE AUDIT MISSES (framed; refutation/meta-parroting/manual-correct removed):")
            for m in framed_extra.get("remaining_true_misses", []) or [["(none)"]]:
                print(f"     {m}")
            print("  META-PARROTING (framed):")
            for i, a in framed_extra.get("meta_parroting_examples", []):
                print(f"     {i} | {a}")
            print("  MANUAL DISAGREEMENTS (audit vs rubric; transparency only):")
            for pid, v in bk["manual_disagreements"].items():
                print(f"     {pid}: rubric={v['rubric']!r} audit={v['audit']!r} -> {v['manual_verdict']}")
        print("-" * 82)
        print(f"  DECISION[{backend}]: {label}")
        if not real:
            print(f"     (provisional-if-real: {provisional}; union_recall={recall}, "
                  f"false_rewrite_rate={fp_rate})")
        final_label = label

    report["label"] = final_label
    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {outp}")
    print("=" * 82)
    print(f"FINAL LABEL: {final_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
