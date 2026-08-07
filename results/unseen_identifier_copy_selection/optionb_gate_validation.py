"""Reviewer-runnable validation of the corrected shortcut gate (exact binomial + Holm-Bonferroni).

Uses the IMPLEMENTED gate (`experiments...shortcuts._decide`) on SYNTHETIC families only — no reserved
seed is built or run. Demonstrates: (a) chance-level noise across the real family size (6 splits x 12
baselines = 72 comparisons) does NOT block; (b) a genuine leak blocks; (c) multiplicity does real work;
(d) the practical +0.05 leg is required. The authoritative checks live in
tests/experiments/unseen_identifier_copy_selection/test_shortcuts_complete.py.
"""
from __future__ import annotations

from experiments.unseen_identifier_copy_selection.config import CANDIDATE_COUNT
from experiments.unseen_identifier_copy_selection.shortcuts import BASELINE_NAMES, _decide

CHANCE = 1.0 / CANDIDATE_COUNT
SPLITS = ("C2", "C3", "C4", "C5", "C6", "C7")


def family(n=180, override=None):
    k0 = round(n * CHANCE)
    fam = {s: {b: [k0, n] for b in BASELINE_NAMES} for s in SPLITS}
    if override:
        s, b, k, nn = override
        fam[s][b] = [k, nn]
    return fam


def show(label, dec):
    blocked = {s: d["blocked"] for s, d in dec["per_split"].items() if d["blocked"]}
    print(f"  {label:52} all_pass={dec['all_pass']!s:5} m={dec['n_comparisons']:2} blocked={blocked or 'NONE'}")


if __name__ == "__main__":
    print("Corrected shortcut gate — exact one-sided binomial vs chance + Holm-Bonferroni FWER=0.05\n")
    show("all baselines at chance (72 comparisons)", _decide(family(), CHANCE))
    show("marginal noise 0.4056=73/180 in full family", _decide(family(override=("C2", "first_target", 73, 180)), CHANCE))
    show("SAME 73/180 tested ALONE (family of 1)", _decide({"C2": {"first_target": [73, 180]}}, CHANCE))
    show("genuine leak 0.60=108/180 in full family", _decide(family(override=("C2", "first_target", 108, 180)), CHANCE))
    show("tiny-but-significant 0.36 at n=10000", _decide(family(override=("C2", "first_target", 3600, 10000)), CHANCE))
    print("\n[synthetic only — no reserved seed built or run]")
