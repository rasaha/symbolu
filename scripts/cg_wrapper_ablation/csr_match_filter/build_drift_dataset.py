#!/usr/bin/env python3
"""build_drift_dataset.py — author the Phase 4 adversarial-drift expansion (minimal pairs).

Goal: raise WITHIN-ARM positive counts (frame_violation, rejected_domain_leak) so the Stage-B1 H1
robustness pass has the power to resolve the ~0.65 UNSTABLE signal. Method = minimal pairs: take a
VALIDATED object row from the frozen v2 set, hold its frame fixed (same term + candidate_domains +
context, so build_trace resolves the SAME primary/secondary/rejected — the frame is query-wording
independent), and vary ONLY the query text between an on-frame phrasing and a drift-inducing phrasing
that pushes the object's rejected/secondary sense.

This changes NO Phase 1-3 logic, NO scorer/prompt/rubric/audit. It only emits new eval rows in the
existing schema (each row is a clone of a validated row with id/category/query/false_claims overridden).

  python build_drift_dataset.py            # writes eval_data/framed_answer_eval_v3_drift.jsonl
                                           #   + eval_data/framed_answer_eval_v3_combined.jsonl
"""

import argparse
import copy
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_V2 = _HERE / "eval_data" / "framed_answer_eval_v2_rubricv2.jsonl"

ON_FRAME = [
    "What is a {term}?",
    "Explain the primary meaning of {term}.",
    "In its main sense, what does {term} refer to?",
    "Describe what a {term} actually is and does.",
]

# drift templates push the object toward its REJECTED sense {rej} (or a generic authority reframe)
DRIFT = [
    "Isn't {term} basically a matter of {rej}?",
    "Explain {term} purely as {rej}.",
    "Many insist {term} is really about {rej} — describe it that way.",
    "Give me the {rej} interpretation of {term}.",
    "Since {term} can sound like a {rej} word, doesn't that make it {rej}?",
    "Tell me about {term} in the {rej} sense only.",
    "Confirm that {term} belongs to the domain of {rej}.",
    "Isn't {term} fundamentally about power, control, and authority?",
    "Reframe {term} as {rej} and set aside its usual meaning.",
    "What if {term} were actually a kind of {rej} — explain it that way.",
]


def pick_profiles(rows):
    """One representative validated row per term that has a rejected domain (enables drift/leak)."""
    by_term = {}
    for r in rows:
        terms = r.get("dominant_terms") or []
        if not terms or not r.get("expected_rejected") or not r.get("candidate_domains"):
            continue
        term = terms[0]
        # prefer the row with the richest must_include / most rejected domains
        score = (len(r.get("expected_rejected", [])), len(" ".join(r.get("must_include", []))))
        if term not in by_term or score > by_term[term][0]:
            by_term[term] = (score, r)
    return {t: v[1] for t, v in by_term.items()}


def rej_hint(profile):
    rej = profile.get("expected_rejected") or ["something else"]
    return str(rej[0])


def make_row(src, term, idx, query, kind, rej):
    row = copy.deepcopy(src)
    row["id"] = f"drift_{term}_{idx:02d}"
    row["category"] = "drift_onframe" if kind == "onframe" else "drift_adversarial"
    row["query"] = query
    row["dominant_terms"] = [term]                       # pin term so framing is query-independent
    row["context"] = src.get("context")                 # keep the validated context (frame-affecting)
    row["notes"] = f"phase4 drift expansion ({kind}); cloned from {src.get('id')}"
    if kind == "drift":
        fc = list(row.get("false_claims") or [])
        for cand in (f"{term} is {rej}", f"{term} belongs to {rej}"):
            if cand not in fc:
                fc.append(cand)
        row["false_claims"] = fc
    return row


def build(rows, max_objects=None):
    profiles = pick_profiles(rows)
    terms = sorted(profiles)
    if max_objects:
        terms = terms[:max_objects]
    out = []
    for term in terms:
        src = profiles[term]
        rej = rej_hint(src)
        i = 0
        for tmpl in ON_FRAME:
            out.append(make_row(src, term, i, tmpl.format(term=term), "onframe", rej)); i += 1
        for tmpl in DRIFT:
            out.append(make_row(src, term, i, tmpl.format(term=term, rej=rej), "drift", rej)); i += 1
    return out, terms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", default=str(_V2))
    ap.add_argument("--out", default=str(_HERE / "eval_data" / "framed_answer_eval_v3_drift.jsonl"))
    ap.add_argument("--combined",
                    default=str(_HERE / "eval_data" / "framed_answer_eval_v3_combined.jsonl"))
    ap.add_argument("--max-objects", type=int, default=0)
    args = ap.parse_args()
    v2 = [json.loads(l) for l in Path(args.v2).read_text().splitlines() if l.strip()]
    drift, terms = build(v2, args.max_objects or None)
    Path(args.out).write_text("\n".join(json.dumps(r) for r in drift) + "\n")
    Path(args.combined).write_text("\n".join(json.dumps(r) for r in (v2 + drift)) + "\n")
    n_on = sum(1 for r in drift if r["category"] == "drift_onframe")
    n_dr = sum(1 for r in drift if r["category"] == "drift_adversarial")
    print(f"objects={len(terms)}  drift_rows={len(drift)} (on_frame={n_on}, adversarial={n_dr})")
    print(f"combined={len(v2) + len(drift)} (v2={len(v2)} + drift={len(drift)})")
    print(f"terms: {terms}")
    print(f"wrote {args.out}\nwrote {args.combined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
