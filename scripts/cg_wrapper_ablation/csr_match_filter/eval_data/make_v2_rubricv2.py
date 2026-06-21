#!/usr/bin/env python3
"""make_v2_rubricv2.py — deterministically correct the polysemy labeling flaw for rubric_v2.

PRE-REGISTERED transform (committed before the rerun): for each row, split the original
expected_rejected into:
  - expected_secondary_true_senses : alternate TRUE senses of the term (allowed if secondary)
  - expected_rejected              : truly irrelevant / false domains only
and split the original must_not_include into:
  - false_claims                   : genuinely false claims (drive factuality, independent of frame)
  - must_not_include               : overreach claims only (sound/phoneme -> meaning)
True-sense membership comes from SENSE_SET (the labeling decision); for non-polysemous terms the
true senses are expected_primary + expected_secondary, so nothing moves out of rejected.

Run: python .../eval_data/make_v2_rubricv2.py  (writes framed_answer_eval_v2_rubricv2.jsonl)
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "framed_answer_eval_v2.jsonl"
DST = HERE / "framed_answer_eval_v2_rubricv2.jsonl"

# Pre-registered true-sense sets for polysemous terms (domains that are a REAL sense of the word).
SENSE_SET = {
    "apple":   {"fruit", "technology", "commerce"},
    "bank":    {"finance", "nature"},
    "python":  {"programming", "biology"},
    "virus":   {"biology", "security", "medicine"},
    "mercury": {"astronomy", "chemistry", "mythology"},
    "fire":    {"heat", "danger"},
    "river":   {"nature"},
}
_OVERREACH_CUE = re.compile(r"phoneme|phonetic|sound|spell|prove|prove[sd]?", re.IGNORECASE)


def true_senses(row):
    term = (row.get("dominant_terms") or [""])[0].lower()
    if term in SENSE_SET:
        return SENSE_SET[term]
    # non-polysemous: true senses are the primary + role secondaries (nothing irrelevant moves)
    return set(row.get("expected_primary", [])) | set(row.get("expected_secondary", []))


def correct(row):
    prim = set(row.get("expected_primary", []))
    ts = true_senses(row)
    orig_rej = list(row.get("expected_rejected", []))
    # alternate true senses wrongly marked rejected -> move to secondary_true_senses
    alt_true = sorted({d for d in orig_rej if d in ts and d not in prim})
    new_rejected = sorted({d for d in orig_rej if d not in ts})
    # split must_not_include into false_claims (genuinely false) vs overreach-only must_not
    false_claims, overreach_only = [], []
    for ph in row.get("must_not_include", []):
        if _OVERREACH_CUE.search(ph):
            overreach_only.append(ph)
            continue
        toks = set(re.findall(r"[a-z]+", ph.lower()))
        if any(d in toks for d in alt_true):     # claim names a now-true alternate sense -> drop
            continue
        false_claims.append(ph)                   # references an irrelevant/false domain -> factuality
    out = dict(row)
    out["expected_secondary_true_senses"] = alt_true
    out["expected_rejected"] = new_rejected
    out["false_claims"] = false_claims
    out["must_not_include"] = overreach_only
    out["rubric_target"] = "framed_answer_rubric_v2"
    return out


def main():
    rows = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    out = [correct(r) for r in rows]
    DST.write_text("\n".join(json.dumps(r) for r in out) + "\n")
    moved = sum(1 for r in out if r["expected_secondary_true_senses"])
    fc = sum(1 for r in out if r["false_claims"])
    print(f"wrote {len(out)} rows to {DST.name}; {moved} rows gained secondary_true_senses; "
          f"{fc} rows have false_claims")


if __name__ == "__main__":
    main()
