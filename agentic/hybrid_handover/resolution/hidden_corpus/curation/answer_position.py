#!/usr/bin/env python3
"""Answer-position / ordering bias audit over ACCEPTED pilot cases. Reports
corpus-level shortcut correlations; flags any that are excessive (>0.8)."""

from __future__ import annotations

from .records import accepted_candidates


def _order_of(c, cite):
    for d in c["documents"]:
        if d["citation"] == cite:
            return d["order"]
    return None


def audit():
    answered = [c for c in accepted_candidates() if not c["ann_abstain"]]
    n = len(answered)
    last = first = table_governs = appendix_governs = longest_governs = 0
    abst_by_diff = {}
    for c in accepted_candidates():
        if c["ann_abstain"]:
            from .difficulty_rubric import rubric_level
            lvl = rubric_level(c["difficulty_factors"])
            abst_by_diff[lvl] = abst_by_diff.get(lvl, 0) + 1
    for c in answered:
        gov = set(c["ann_governing"])
        orders = [d["order"] for d in c["documents"]]
        maxo, mino = max(orders), min(orders)
        gov_orders = [_order_of(c, g) for g in gov if _order_of(c, g) is not None]
        if gov_orders and max(gov_orders) == maxo:
            last += 1
        if gov_orders and min(gov_orders) == mino:
            first += 1
        types = c["ann_graph"]["nodes"]
        if any(types.get(g) == "Table" for g in gov):
            table_governs += 1
        if any("appendix" in g.lower() for g in gov):
            appendix_governs += 1
        # longest doc governs
        longest = max(c["documents"], key=lambda d: len(d["text"]))
        if longest["citation"] in gov:
            longest_governs += 1

    def rate(x):
        return round(x / n, 3) if n else None
    corr = {
        "governing_is_last_doc": rate(last),
        "governing_is_first_doc": rate(first),
        "table_governs_when_present": rate(table_governs),
        "appendix_governs_when_present": rate(appendix_governs),
        "longest_doc_governs": rate(longest_governs),
        "abstention_by_difficulty": abst_by_diff,
        "n_answered": n,
    }
    flags = [k for k, v in corr.items()
             if isinstance(v, float) and (v is not None) and (v > 0.8)]
    return {"correlations": corr, "excessive_flags": flags}
