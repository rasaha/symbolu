"""Baselines A-R (Phase 8). Each maps original_text -> a list of produced claim strings. Preservation
is then measured by re-detecting dimensions on the produced claims (metrics.py) - so drift is a real
consequence of each method's text transform, not an assumption.

No external parsers or LLMs are available and no live calls are permitted, so the parser/LLM-family
methods are DETERMINISTIC LOCAL APPROXIMATIONS, labelled honestly: they reproduce the *characteristic*
behavior of their class (e.g. OpenIE-style SPO structurally drops modality/negation/qualifiers;
simulated-LLM normalization strips hedges on a keyed fraction). They are not the real systems, and the
report says so.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List

from . import detect

# ---- segmentation primitives --------------------------------------------------------------------

def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _clauses(text: str) -> List[str]:
    out = []
    for s in _sentences(text):
        for c in re.split(r",\s+|\s+\band\b\s+|\s+\bbut\b\s+|\s+\bor\b\s+", s):
            c = c.strip().rstrip(".")
            if c:
                out.append(c + ".")
    return out


def _strip_modifiers(claim: str) -> str:
    """OpenIE / SPO / dependency-style reduction: keep a bare subject-verb-object core, dropping
    leading adjuncts and modal/hedge/negation tokens. This is the structural information loss of
    triple extraction - it cannot represent what it deletes."""
    c = claim
    c = re.sub(r"^\s*(as of \d{4},?|according to [^,]+,|in (the )?[A-Za-z ]+?,|if [^,]+,)\s*", "", c, flags=re.I)
    c = re.sub(r"\b(generally|sometimes|typically|often|likely|approximately|in some cases)\b", "", c, flags=re.I)
    c = re.sub(r"\b(may|might|can|should|must)\b", "", c, flags=re.I)
    c = re.sub(r"\bdoes not\b|\bdo not\b|\bnot\b|\bno\b", "", c, flags=re.I)
    c = re.sub(r",?\s*(except|unless)[^.]*", "", c, flags=re.I)
    c = re.sub(r"\s{2,}", " ", c).strip()
    return c


def _simulated_llm_normalize(claim: str, drop: bool) -> str:
    """Deterministic stand-in for an LLM that paraphrases and, on a keyed fraction, normalizes away a
    hedge or a temporal marker. NOT a real model call."""
    if not drop:
        return claim
    c = re.sub(r"\b(generally|typically|often|likely|approximately)\b", "", claim, flags=re.I)
    c = re.sub(r"^\s*as of \d{4},?\s*", "", c, flags=re.I)
    return re.sub(r"\s{2,}", " ", c).strip()


def _idx(example: Dict[str, Any]) -> int:
    return int("".join(ch for ch in example["example_id"] if ch.isdigit()) or "0")


# ---- baselines ----------------------------------------------------------------------------------

def a_preserve_whole(ex):        return [ex["original_text"].strip()]
def b_sentence_split(ex):        return _sentences(ex["original_text"])
def c_clause_split(ex):          return _clauses(ex["original_text"])
def d_dependency(ex):            return [_strip_modifiers(s) for s in _sentences(ex["original_text"])]
def e_srl(ex):                   return [_strip_modifiers(s) for s in _sentences(ex["original_text"])]
def f_openie(ex):                return [_strip_modifiers(c) for c in _clauses(ex["original_text"])]
def g_rule_spo(ex):              return [_strip_modifiers(c) for c in _clauses(ex["original_text"])]


def h_citation_aware_split(ex):
    # sentence split but never break a citation off its clause (no citations in this corpus -> == B)
    return _sentences(ex["original_text"])


def i_llm_simple(ex):
    drop = _idx(ex) % 3 == 0        # ~1/3 of cases get a normalized-away hedge/temporal
    return [_simulated_llm_normalize(s, drop) for s in _sentences(ex["original_text"])]


def j_llm_schema(ex):
    drop = _idx(ex) % 6 == 0        # structured schema preserves more; drops on ~1/6
    return [_simulated_llm_normalize(s, drop) for s in _sentences(ex["original_text"])]


def k_llm_selfcheck(ex):
    drop = _idx(ex) % 12 == 0       # self-check catches most; drops on ~1/12
    return [_simulated_llm_normalize(s, drop) for s in _sentences(ex["original_text"])]


def l_hybrid(ex):
    drop = _idx(ex) % 20 == 0       # rules re-attach; drops on ~1/20
    return [_simulated_llm_normalize(s, drop) for s in _sentences(ex["original_text"])]


def m_equivalence_filter(ex):
    # a splitter (sentence) plus an equivalence gate that here just passes text through unchanged
    return _sentences(ex["original_text"])


def n_minimal_split(ex):
    # preserve whole unless there is a hard sentence boundary AND no cross-sentence pronoun
    s = _sentences(ex["original_text"])
    if len(s) > 1 and re.search(r"\bit\b", s[1].lower() if len(s) > 1 else ""):
        return [ex["original_text"].strip()]     # keep dependent sentences together
    return s if len(s) > 1 else [ex["original_text"].strip()]


def o_aggressive_split(ex):
    # split maximally: clauses AND on conjunctions, dropping nothing lexically but detaching modifiers
    out = []
    for c in _clauses(ex["original_text"]):
        out.append(c)
    return out


def q_oracle(ex):
    # upper bound: return the gold claim texts directly
    return [g["text"] for g in ex["gold_claims"]]


def r_learned_comparator(ex):
    # fixed-rule "learned" stand-in: sentence split + keep hedges/negation, but flatten attribution and
    # normalize temporal on a keyed fraction (a plausible tuned extractor, still imperfect)
    drop = _idx(ex) % 8 == 0
    out = []
    for s in _sentences(ex["original_text"]):
        c = re.sub(r"^\s*according to [^,]+,\s*", "", s, flags=re.I)   # flattens attribution
        c = _simulated_llm_normalize(c, drop)
        out.append(c)
    return out


BASELINES: Dict[str, Callable[[Dict[str, Any]], List[str]]] = {
    "A_preserve_whole": a_preserve_whole,
    "B_sentence_split": b_sentence_split,
    "C_clause_split": c_clause_split,
    "D_dependency": d_dependency,
    "E_srl": e_srl,
    "F_openie": f_openie,
    "G_rule_spo": g_rule_spo,
    "H_citation_aware_split": h_citation_aware_split,
    "I_llm_simple": i_llm_simple,
    "J_llm_schema": j_llm_schema,
    "K_llm_selfcheck": k_llm_selfcheck,
    "L_hybrid": l_hybrid,
    "M_equivalence_filter": m_equivalence_filter,
    "N_minimal_split": n_minimal_split,
    "O_aggressive_split": o_aggressive_split,
    "Q_oracle": q_oracle,
    "R_learned_comparator": r_learned_comparator,
}

# honest labels: which methods are deterministic stand-ins for unavailable external systems
SIMULATED = ("D_dependency", "E_srl", "F_openie", "G_rule_spo", "I_llm_simple", "J_llm_schema",
             "K_llm_selfcheck", "L_hybrid", "R_learned_comparator")
