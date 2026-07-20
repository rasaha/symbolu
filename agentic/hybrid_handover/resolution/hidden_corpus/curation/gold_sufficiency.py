#!/usr/bin/env python3
"""Gold-sufficiency audit for accepted pilot cases (evaluation-side)."""

from __future__ import annotations

import re

from .records import accepted_candidates, opaque_id


def _norm(s):
    return re.sub(r"\s+", " ", s.lower()).strip()


def audit():
    issues = []
    for c in accepted_candidates():
        cid = opaque_id(c)
        doctext = " ".join(_norm(d["text"]) for d in c["documents"])
        g = c["ann_graph"]
        nodes = set(g["nodes"])
        # 1. every edge has provenance whose needle appears in some document
        for (s, t, d) in g["edges"]:
            key = f"{s}|{t}|{d}"
            needle = c["provenance"].get(key)
            if not needle:
                issues.append((cid, "edge_without_provenance", key))
            elif _norm(needle) not in doctext:
                issues.append((cid, "provenance_not_in_docs", key))
        # 2. governing consistency
        if c["ann_abstain"]:
            if c["ann_governing"]:
                issues.append((cid, "abstain_with_governing", cid))
        else:
            if not c["ann_governing"]:
                issues.append((cid, "answer_without_governing", cid))
            for gk in c["ann_governing"]:
                if gk not in nodes:
                    issues.append((cid, "governing_not_a_node", gk))
        # 3. packet follows abstain
        if c["ann_abstain"] and c["ann_packet"] != {"abstain": True}:
            issues.append((cid, "abstain_packet_mismatch", str(c["ann_packet"])))
        # 4. answer not obtainable from question wording (notice/penalty number)
        q = _norm(c["question"])
        pkt = c["ann_packet"]
        if not c["ann_abstain"]:
            nd = pkt.get("notice_days")
            if nd is not None and (f" {nd} " in f" {q} " or f"({nd})" in q):
                issues.append((cid, "answer_in_question", f"notice {nd}"))
    return issues
