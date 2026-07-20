#!/usr/bin/env python3
"""
Multi-level duplicate / reasoning-template detection. Lexical similarity alone
never rejects a case; a QUARANTINE recommendation requires MULTIPLE signals
indicating a shared reasoning template.

Signals:
  1. exact normalised-text duplicate
  2. character-3gram cosine similarity
  3. token 3-shingle Jaccard similarity
  4. structural graph signature (edge-type multiset + node-type multiset + degree seq)
  5. reasoning-template fingerprint (governance-operation path + abstain + governing pattern)
"""

from __future__ import annotations

import math
import re
from collections import Counter


def norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _char_ngrams(text: str, n: int = 3) -> Counter:
    t = norm_text(text)
    return Counter(t[i:i + n] for i in range(max(0, len(t) - n + 1)))


def char_ngram_sim(a: str, b: str) -> float:
    ca, cb = _char_ngrams(a), _char_ngrams(b)
    if not ca or not cb:
        return 0.0
    common = set(ca) & set(cb)
    dot = sum(ca[k] * cb[k] for k in common)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    return round(dot / (na * nb), 4) if na and nb else 0.0


def _shingles(text: str, k: int = 3) -> set:
    toks = norm_text(text).split()
    return {tuple(toks[i:i + k]) for i in range(max(0, len(toks) - k + 1))}


def shingle_sim(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return round(len(sa & sb) / len(sa | sb), 4)


def graph_signature(graph: dict) -> tuple:
    edges = graph.get("edges", [])
    etypes = tuple(sorted(t for (_s, t, _d) in edges))
    ntypes = tuple(sorted(graph.get("nodes", {}).values()))
    deg = Counter()
    for (s, _t, d) in edges:
        deg[s] += 1
        deg[d] += 1
    degseq = tuple(sorted(deg.values(), reverse=True))
    return (etypes, ntypes, degseq)


def template_fingerprint(graph: dict) -> tuple:
    """Governance-operation path + abstain + governing count."""
    ops = tuple(sorted({t for (_s, t, _d) in graph.get("edges", [])
                        if t in ("supersedes", "overrides", "governs_over",
                                 "exception_to", "references", "conflicts_with",
                                 "same_as", "effective_after", "amends")}))
    return (ops, bool(graph.get("abstain")), len(graph.get("governing", [])))


def similarity(a_text: str, a_graph: dict, b_text: str, b_graph: dict) -> dict:
    return {
        "exact_text_dup": norm_text(a_text) == norm_text(b_text),
        "char_ngram": char_ngram_sim(a_text, b_text),
        "shingle": shingle_sim(a_text, b_text),
        "same_graph_signature": graph_signature(a_graph) == graph_signature(b_graph),
        "same_template_fingerprint": template_fingerprint(a_graph) == template_fingerprint(b_graph),
    }


def quarantine_recommended(sig: dict) -> bool:
    """Quarantine only for a genuinely SHARED reasoning template: near-identical
    text AND identical structure. Sharing a single governance operation type (a
    common template fingerprint) across otherwise-different cases is NOT a
    duplicate — that is the same capability with different content, which is
    exactly what the corpus should contain.
    """
    if sig["exact_text_dup"]:
        return True
    near_identical_text = sig["char_ngram"] >= 0.9 and sig["shingle"] >= 0.5
    same_structure = sig["same_graph_signature"]
    return near_identical_text and same_structure
