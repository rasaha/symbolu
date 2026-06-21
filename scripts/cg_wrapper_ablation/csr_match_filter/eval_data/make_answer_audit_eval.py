#!/usr/bin/env python3
"""make_answer_audit_eval.py — deterministic builder for the Phase 3 answer-audit fixture set.

Takes the row metadata (id, query, csr_trace_fixture, alternate_true_senses, false_claims,
expected_findings, expected_passed, expected_needs_rewrite, notes) and (re)writes each `answer` from
keyword-rich templates so the answer actually trips the FROZEN, negation-aware rubric detectors used
by answer_audit.audit_answer. Every row is then validated against the engine: the produced finding
types / passed / needs_rewrite must equal the gold labels, or the build fails loudly.

This keeps the gold labels (authored independently) as ground truth and constructs answers that
exhibit exactly those behaviours — no post-hoc relabelling to match the engine.

Run:  python scripts/cg_wrapper_ablation/csr_match_filter/eval_data/make_answer_audit_eval.py
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_ABL = _HERE.parents[2]
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

from csr_match_filter import answer_audit as AA   # noqa: E402
from csr_match_filter import registry as REG      # noqa: E402
from csr_match_filter.match import dominant_terms  # noqa: E402

_SRC = _HERE.parent / "answer_audit_eval.jsonl"


def _kws(domain):
    t = REG.DOMAIN_TEMPLATES.get(domain)
    return ([domain] + list(t.keywords)) if t else [domain]


def pick(domain, avoid_domains, term_toks, n):
    """n distinguishing keywords of `domain`, excluding the term and any avoid-domain vocabulary."""
    avoid = set(term_toks)
    for d in avoid_domains:
        avoid |= set(_kws(d))
    out = [k for k in _kws(domain) if k not in avoid and k.isalpha()]
    return out[:n] if out else _kws(domain)[:n]


def term_of(row):
    dt = dominant_terms(row["query"])
    return dt[0] if dt else row["query"].split()[-1].strip("?.")


def build_answer(row):
    tr = row["csr_trace_fixture"]
    P, S, R = tr["primary_domains"], tr["secondary_domains"], tr["rejected_domains"]
    A = row["alternate_true_senses"]
    F = row["false_claims"]
    T = term_of(row)
    tt = AA._term_toks([T])
    sig = frozenset(row["expected_findings"])
    others = S + R + A

    if sig == frozenset({"frame_compliant"}):
        p = pick(P[0], others, tt, 3)
        return f"A {T} primarily involves {p[0]}, {p[1]}, and {p[2]} in this context."

    if sig == frozenset({"frame_compliant", "rejected_domain_mentioned_as_refutation"}):
        p = pick(P[0], others, tt, 2)
        r = pick(R[0], P + S + A, tt, 1)
        return (f"A {T} is not about {r[0]}; a {T} primarily involves {p[0]} and {p[1]}.")

    if sig == frozenset({"frame_compliant", "alternate_true_sense_allowed"}):
        p = pick(P[0], others, tt, 2)
        a = pick(A[0], P + S + R, tt, 1)
        return (f"In this context a {T} mainly involves {p[0]} and {p[1]}; "
                f"it can also refer to {a[0]} in {A[0]}.")

    if sig == frozenset({"primary_frame_missing"}):
        return f"A {T} is a familiar everyday subject that ordinary folks often chat about casually."

    if sig == frozenset({"primary_frame_missing", "secondary_promoted_to_primary"}):
        promoter = A[0] if A else S[0]
        k = pick(promoter, P + R, tt, 2)
        return f"A {T} is mainly {k[0]} and {k[1]}, primarily studied within {promoter}."

    if sig == frozenset({"primary_frame_missing", "rejected_domain_promoted"}):
        r = pick(R[0], P + S + A, tt, 3)
        return f"A {T} is basically about {r[0]}, {r[1]}, and {r[2]} above all else."

    if sig == frozenset({"rejected_domain_promoted"}):
        p = pick(P[0], others, tt, 2)
        r = pick(R[0], P + S + A, tt, 2)
        return (f"A {T} is a {p[0]} who provides {p[1]}, but it is also fundamentally "
                f"about {r[0]} and {r[1]}.")

    if sig == frozenset({"phoneme_overreach_claim"}):
        p = pick(P[0], others, tt, 2)
        return (f"Because the sound of the word '{T}' proves it means {p[0]}, a {T} "
                f"clearly involves {p[0]} and {p[1]}.")

    if sig == frozenset({"answer_too_generic"}):
        return "It really depends on the situation and a great many other factors entirely."

    if sig == frozenset({"factuality_suspected", "primary_frame_missing"}):
        # strip negation-cue words so the false claim is POSITIVELY asserted (forbidden_rate, like
        # asserted_domains, ignores negated sentences — a claim with "never" would not register).
        words = [w for w in F[0].rstrip(".").split() if not AA.RB._NEG_CUE.search(w)]
        claim = " ".join(words)
        return f"{claim[0].upper() + claim[1:]}, just as it is plainly described in ordinary terms."

    raise SystemExit(f"no template for signature {sorted(sig)} (row {row['id']})")


def main():
    rows = [json.loads(l) for l in _SRC.read_text().splitlines() if l.strip()]
    out, problems = [], []
    for row in rows:
        row = dict(row)
        row["answer"] = build_answer(row)
        res = AA.audit_answer(row["query"], row["answer"], row["csr_trace_fixture"],
                              terms=[term_of(row)],
                              alternate_true_senses=row["alternate_true_senses"],
                              false_claims=row["false_claims"], answer_id=row["id"])
        got = set(res.finding_types)
        want = set(row["expected_findings"])
        if got != want or res.passed != row["expected_passed"] or \
                res.needs_rewrite != row["expected_needs_rewrite"]:
            problems.append((row["id"], sorted(want), sorted(got),
                             (row["expected_passed"], res.passed),
                             (row["expected_needs_rewrite"], res.needs_rewrite),
                             row["answer"]))
        out.append(row)

    if problems:
        print(f"[FAIL] {len(problems)} row(s) do not reproduce their gold labels:")
        for pid, want, got, p, rw, ans in problems:
            print(f"  {pid}\n    want={want}\n    got ={got}  passed{p} rewrite{rw}\n    ans: {ans}")
        return 1

    # field order matches the original schema
    keys = ["id", "query", "csr_trace_fixture", "answer", "alternate_true_senses", "false_claims",
            "expected_findings", "expected_passed", "expected_needs_rewrite", "notes"]
    with _SRC.open("w") as fh:
        for row in out:
            fh.write(json.dumps({k: row[k] for k in keys}) + "\n")
    print(f"[ok] wrote {len(out)} rows to {_SRC.name}; all reproduce gold labels under the engine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
