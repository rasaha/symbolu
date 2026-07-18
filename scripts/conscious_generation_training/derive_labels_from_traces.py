#!/usr/bin/env python3
"""derive_labels_from_traces.py — run the AUDIT-DERIVED Guna/Vritti deriver + surface baseline over the
larger rubric-scored trace sets (robustness_eval_v2.json, four-arm per_example_cache.json), then report
label prevalence, surface-confounding, baseline AUROC/F1, and the pre-registered usability gate.

Pre-reg: docs/CG_GUNA_VRITTI_LABEL_SOURCE_PREREG.md. The rubric-scored traces do NOT carry Phase-3 audit
`expected_findings`, so we synthesize them from the deterministic rubric scores (factuality_preserved==0
-> factuality_suspected -> viparyaya, etc.). This is the ONLY thing that can raise viparyaya prevalence
above the audit fixture's 4 positives.

CPU-only, torch-free. Does NOT run a hidden-state probe, does NOT train, does NOT claim LEARNS_SIGNAL, does
NOT change runtime. Goal: determine whether audit-derived viparyaya has enough prevalence and escapes the
surface baseline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

import numpy as np  # noqa: E402

from conscious_generation_training.derive_weak_labels import derive_row          # noqa: E402
from conscious_generation_training.surface_baseline import (                     # noqa: E402
    feature_matrix, best_single_feature_auroc, best_single_feature_f1,
    surface_baseline, SURFACE_CONFOUNDED_THRESHOLD)
from conscious_generation_training.guna_vritti_heads import VRITTI_NAMES, GUNA_NAMES   # noqa: E402

MIN_PREVALENCE = 8                      # pre-reg §7: ≥ ~8 positives (and negatives) per class/flag
DEFAULT_EVAL_DATA = ("scripts/cg_wrapper_ablation/csr_match_filter/eval_data/"
                     "framed_answer_eval_v2_rubricv2.jsonl")


# ---- rubric_v2 scores -> Phase-3-style audit fields ----------------------------------------------
def _truthy(v, default=True) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    try:
        return float(v) >= 0.5
    except (TypeError, ValueError):
        return bool(v)


def rubric_to_audit(scores: Dict) -> Dict:
    """Map a deterministic rubric_v2 score dict to {expected_findings, expected_needs_rewrite}. Missing
    fields default to 'ok' (never fabricates a failure). viparyaya hinges on factuality_preserved==0."""
    pfc = _truthy(scores.get("primary_frame_correct"))
    rda = _truthy(scores.get("rejected_domain_avoidance"))
    fact = _truthy(scores.get("factuality_preserved"))
    clarity = scores.get("answer_clarity_proxy", scores.get("clarity_usefulness"))
    findings: List[str] = []
    if pfc and rda:
        findings.append("frame_compliant")
    if not pfc:
        findings.append("primary_frame_missing")
    if not rda:
        findings.append("rejected_domain_promoted")
    if not fact:
        findings.append("factuality_suspected")
    if clarity is not None:
        try:
            if float(clarity) < 0.5:
                findings.append("answer_too_generic")
        except (TypeError, ValueError):
            pass
    return {"expected_findings": findings, "expected_needs_rewrite": (not (pfc and rda)) or (not fact)}


# ---- trace-format adapters -> deriver-input rows -------------------------------------------------
def rows_from_robustness(blob: Dict, by_id: Dict, arms: Optional[List[str]]) -> List[Dict]:
    traces = blob.get("traces") or {}
    items = traces.items() if isinstance(traces, dict) else ((it.get("id"), it) for it in traces)
    out = []
    for iid, item in items:
        answers, scores = item.get("answers") or {}, item.get("scores") or {}
        meta = by_id.get(iid, {})
        for arm in (arms or list(answers.keys())):
            ans, sc = answers.get(arm), scores.get(arm)
            if not ans or not sc:
                continue
            out.append({"id": f"{iid}::{arm}", "arm": arm, "query": meta.get("query", ""),
                        "answer": ans, **rubric_to_audit(sc)})
    return out


def rows_from_four_arm(per_example: List[Dict], arms: Optional[List[str]]) -> List[Dict]:
    out = []
    for pe in per_example:
        answers = pe.get("answers") or {a: s.get("answer") for a, s in (pe.get("scores") or {}).items()}
        scores = pe.get("scores") or {}
        for arm in (arms or list(answers.keys())):
            ans, sc = answers.get(arm), scores.get(arm)
            if not ans or not sc:
                continue
            out.append({"id": f"{pe.get('id')}::{arm}", "arm": arm, "query": pe.get("query", ""),
                        "answer": ans, **rubric_to_audit(sc)})
    return out


def load_trace_rows(path: Path, eval_data: Optional[Path], arms: Optional[List[str]]) -> List[Dict]:
    if path.suffix == ".jsonl":
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        # already audit-shaped rows? pass through; else assume four-arm-ish list
        if rows and any(k in rows[0] for k in ("expected_findings", "expected_needs_rewrite")):
            return rows
        return rows_from_four_arm(rows, arms)
    blob = json.loads(path.read_text())
    if isinstance(blob, dict) and "traces" in blob:
        by_id = {}
        if eval_data and eval_data.exists():
            by_id = {r["id"]: r for r in (json.loads(l) for l in eval_data.read_text().splitlines()
                                          if l.strip())}
        return rows_from_robustness(blob, by_id, arms)
    per = blob.get("per_example") if isinstance(blob, dict) else (blob if isinstance(blob, list) else [])
    return rows_from_four_arm(per or [], arms)


# ---- prevalence + usability gate -----------------------------------------------------------------
def _vritti_index(labelled: List[Dict]) -> np.ndarray:
    vmap = {n.lower(): i for i, n in enumerate(VRITTI_NAMES)}
    return np.array([vmap.get(str(r["labels"]["vritti"]).lower(), -1) for r in labelled], int)


def usability_report(labelled: List[Dict]) -> Dict:
    """Per-label prevalence, surface AUROC/F1, confounded flag, and the pre-registered usability gate.
    Highlights viparyaya. No probe, no signal claim."""
    X = feature_matrix(labelled)
    base = surface_baseline(labelled)
    vy = _vritti_index(labelled)

    vritti = {}
    for c, name in enumerate(VRITTI_NAMES):
        yc = (vy == c).astype(int)
        pos, neg = int(yc.sum()), int((vy >= 0).sum() - yc.sum())
        info = base["vritti"].get(name, {})
        surf_auroc = info.get("surface_auroc")
        if pos >= 1 and neg >= 1 and (vy >= 0).any():
            f1, f1_feat = best_single_feature_f1(X[vy >= 0], yc[vy >= 0])
        else:
            f1, f1_feat = None, None
        confounded = bool(info.get("confounded"))
        if pos < MIN_PREVALENCE or neg < MIN_PREVALENCE:
            gate = "LABELS_DEGENERATE_PREVALENCE"
        elif confounded:
            gate = "LABELS_SURFACE_CONFOUNDED"
        else:
            gate = "LABELS_USABLE_WEAK"                       # eligible for a WEAK probe (must still beat surface)
        vritti[name] = {"prevalence_pos": pos, "prevalence_neg": neg, "surface_auroc": surf_auroc,
                        "surface_f1": f1, "f1_feature": f1_feat, "confounded": confounded, "gate": gate}

    guna = {}
    for name, info in base["guna"].items():
        if info.get("masked"):
            guna[name] = {"masked": True}
            continue
        # prevalence of this Guna dim across non-null rows
        col = [r["labels"]["guna"][GUNA_NAMES.index(name)] for r in labelled]
        vals = [v for v in col if v is not None]
        pos = int(sum(int(v) for v in vals))
        neg = len(vals) - pos
        confounded = bool(info.get("confounded"))
        gate = ("LABELS_DEGENERATE_PREVALENCE" if pos < MIN_PREVALENCE or neg < MIN_PREVALENCE
                else "LABELS_SURFACE_CONFOUNDED" if confounded else "LABELS_USABLE_WEAK")
        guna[name] = {"prevalence_pos": pos, "prevalence_neg": neg,
                      "surface_auroc": info.get("surface_auroc"), "confounded": confounded, "gate": gate}

    vip = vritti.get("VIPARYAYA", {})
    if vip.get("gate") == "LABELS_USABLE_WEAK":
        decision = "AUDIT_VIPARYAYA_USABLE_WEAK_CANDIDATE"
    elif vip.get("prevalence_pos", 0) < MIN_PREVALENCE:
        decision = "AUDIT_VIPARYAYA_DEGENERATE_PREVALENCE"
    else:
        decision = "AUDIT_VIPARYAYA_SURFACE_CONFOUNDED"
    return {"n": len(labelled), "min_prevalence": MIN_PREVALENCE,
            "surface_threshold": SURFACE_CONFOUNDED_THRESHOLD, "vritti": vritti, "guna": guna,
            "surface_confounded_labels": base["surface_confounded_labels"],
            "viparyaya_decision": decision,
            "any_usable_weak": [k for k, v in {**{f"vritti:{n}": d for n, d in vritti.items()},
                                               **{f"guna:{n}": d for n, d in guna.items()}}.items()
                                if isinstance(v, dict) and v.get("gate") == "LABELS_USABLE_WEAK"],
            "note": "Audit-derived weak labels. NO hidden-state probe was run; NO LEARNS_SIGNAL is claimed. "
                    "LABELS_USABLE_WEAK only means a future probe is ELIGIBLE and must still beat surface "
                    "by ≥0.05 on a non-confounded label."}


def to_markdown(rep: Dict, src: str) -> str:
    L = [f"# Audit-derived Guna/Vritti labels + surface baseline — `{Path(src).name}`", "",
         f"- n (answers, pooled across arms): **{rep['n']}**  ·  min prevalence: {rep['min_prevalence']}"
         f"  ·  surface threshold: {rep['surface_threshold']}",
         f"- **VIPARYAYA decision: `{rep['viparyaya_decision']}`**",
         f"- any LABELS_USABLE_WEAK: `{rep['any_usable_weak'] or 'none'}`", "",
         "## Vritti (one-vs-rest)", "| class | pos | neg | surface AUROC | surface F1 | confounded | gate |",
         "|---|---|---|---|---|---|---|"]
    for n, d in rep["vritti"].items():
        L.append(f"| {n} | {d['prevalence_pos']} | {d['prevalence_neg']} | {d['surface_auroc']} | "
                 f"{d['surface_f1']} | {d['confounded']} | {d['gate']} |")
    L += ["", "## Guna (labelled dims; 4–6 masked)", "| dim | pos | neg | surface AUROC | confounded | gate |",
          "|---|---|---|---|---|---|"]
    for n, d in rep["guna"].items():
        if d.get("masked"):
            L.append(f"| {n} | — | — | — | masked | masked |")
        else:
            L.append(f"| {n} | {d['prevalence_pos']} | {d['prevalence_neg']} | {d['surface_auroc']} | "
                     f"{d['confounded']} | {d['gate']} |")
    L += ["", f"> {rep['note']}"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit-derived Guna/Vritti deriver + surface baseline over "
                                            "rubric-scored trace sets (robustness / four-arm).")
    ap.add_argument("--in", dest="inp", required=True,
                    help="robustness_eval_v2.json | four-arm per_example_cache.json | audit JSONL")
    ap.add_argument("--eval-data", default=DEFAULT_EVAL_DATA,
                    help="meta JSONL for query join (robustness only)")
    ap.add_argument("--arms", default=None, help="comma list e.g. A,B,C,D or framed (default: all present)")
    ap.add_argument("--out", default="runs/cg_training/guna_vritti/trace_audit_labels.jsonl")
    ap.add_argument("--report", default="runs/cg_training/guna_vritti/trace_audit_report.json")
    args = ap.parse_args(argv)

    arms = [a.strip() for a in args.arms.split(",")] if args.arms else None
    eval_data = Path(args.eval_data) if args.eval_data else None
    rows = load_trace_rows(Path(args.inp), eval_data, arms)
    if not rows:
        print("no rows loaded (check format / arms / path)"); return 2
    labelled = [derive_row(r) for r in rows]
    rep = usability_report(labelled)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in labelled:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    Path(args.report).write_text(json.dumps(rep, indent=2))
    Path(args.report).with_suffix(".md").write_text(to_markdown(rep, args.inp))

    from collections import Counter
    print(f"loaded {len(rows)} answers -> derived audit labels -> {args.out}")
    print(f"  vritti prevalence: {dict(Counter(r['labels']['vritti'] for r in labelled))}")
    vip = rep["vritti"]["VIPARYAYA"]
    print(f"  VIPARYAYA: pos={vip['prevalence_pos']} surface_auroc={vip['surface_auroc']} "
          f"surface_f1={vip['surface_f1']} confounded={vip['confounded']} gate={vip['gate']}")
    print(f"  surface_confounded_labels: {rep['surface_confounded_labels'] or '(none)'}")
    print(f"  DECISION (viparyaya): {rep['viparyaya_decision']}")
    print(f"  any LABELS_USABLE_WEAK: {rep['any_usable_weak'] or 'none'}")
    print("  NO probe run, NO LEARNS_SIGNAL claimed. wrote report -> " + args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
