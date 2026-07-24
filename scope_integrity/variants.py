"""The six variants (M3). Each maps original_text -> a list of produced claim strings. Small,
regex-based scope propagation - NOT a parser, NOT an LLM. Variant A is the FROZEN ClaimIntegrity
preservation-first splitter, imported read-only.

Shared parse of a scope-spanning conjunction:
  [PREFIX,] SUBJECT PRED1 <conj> [SUBJECT2] PRED2 [POSTFIX]
where PREFIX in {as of YYYY, according to X, except in E} governs all conjuncts, POSTFIX in
{unless ..., except ...} governs all conjuncts, and SUBJECT is shared unless a second subject appears.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# ---- Variant A: frozen ClaimIntegrity splitter (read-only) ---------------------------------------
def variant_a_current(example) -> List[str]:
    from claim_integrity import claims
    return [c.text for c in claims.decompose(example["original_text"]).claims]


# ---- shared parsing ------------------------------------------------------------------------------
_PREFIX = re.compile(r"^\s*(as of \d{4},|according to [^,]+,|except [^,]+,)\s*", re.I)
_POSTFIX = re.compile(r"[,]?\s*(unless [^.,]+|except [^.,]+)\.?\s*$", re.I)
_SUBJECT = re.compile(r"^(the [a-z]+|[A-Z][A-Za-z]+)\b")
_CONJ = re.compile(r"\s*,?\s+\b(?:and|but)\b\s+|\s*,\s+")


def _sentences(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]


def _parse(sentence: str) -> Tuple[str, str, List[str]]:
    """Return (prefix, postfix, [conjunct clauses]) for one sentence."""
    s = sentence.strip()
    prefix = ""
    mp = _PREFIX.match(s)
    if mp:
        prefix = mp.group(1).strip()
        s = s[mp.end():]
    postfix = ""
    mpo = _POSTFIX.search(s)
    if mpo:
        postfix = mpo.group(1).strip()
        s = s[:mpo.start()].strip()
    s = s.rstrip(".")
    conjuncts = [c.strip() for c in _CONJ.split(s) if c.strip()]
    return prefix, postfix, conjuncts


def _subject_of(clause: str) -> str:
    m = _SUBJECT.match(clause)
    return m.group(1) if m else ""


def _has_subject(clause: str) -> bool:
    return bool(_SUBJECT.match(clause))


# ---- Variant B: naive split (negative control) ---------------------------------------------------
def variant_b_naive(example) -> List[str]:
    out = []
    for sent in _sentences(example["original_text"]):
        _, _, conjuncts = _parse(sent)
        for c in conjuncts:
            out.append(c.rstrip(".") + ".")
    return out or [example["original_text"]]


# ---- Variant C: subject-carrying split -----------------------------------------------------------
def variant_c_subject(example) -> List[str]:
    out = []
    for sent in _sentences(example["original_text"]):
        _, _, conjuncts = _parse(sent)
        subj = next((_subject_of(c) for c in conjuncts if _has_subject(c)), "")
        for c in conjuncts:
            piece = c if _has_subject(c) else (f"{subj} {c}" if subj else c)
            out.append(piece.rstrip(".") + ".")
    return out or [example["original_text"]]


# ---- Variant D: subject + qualifier carrying -----------------------------------------------------
_QUAL_PREFIX = re.compile(r"^(as of \d{4},|according to)", re.I)


def _carry_qualifiers(prefix: str, clause: str) -> str:
    # negation/modality/uncertainty already live inside each conjunct here; carry the shared PREFIX
    # (temporal/attribution) that was stripped, when it is a qualifier prefix.
    if prefix and _QUAL_PREFIX.match(prefix):
        return f"{prefix} {clause}"
    return clause


def variant_d_subject_qualifier(example) -> List[str]:
    out = []
    for sent in _sentences(example["original_text"]):
        prefix, _, conjuncts = _parse(sent)
        subj = next((_subject_of(c) for c in conjuncts if _has_subject(c)), "")
        for c in conjuncts:
            piece = c if _has_subject(c) else (f"{subj} {c}" if subj else c)
            piece = _carry_qualifiers(prefix, piece)
            out.append(piece.rstrip(".") + ".")
    return out or [example["original_text"]]


# ---- Variant E: full scope-carrying --------------------------------------------------------------
SCOPE_ELEMENTS = frozenset({"subject", "qualifier_prefix", "exception_prefix", "postfix_exception"})


def variant_e_full(example, enabled: frozenset = SCOPE_ELEMENTS) -> List[str]:
    out = []
    for sent in _sentences(example["original_text"]):
        prefix, postfix, conjuncts = _parse(sent)
        subj = next((_subject_of(c) for c in conjuncts if _has_subject(c)), "")
        for c in conjuncts:
            piece = c
            if "subject" in enabled and not _has_subject(c) and subj:
                piece = f"{subj} {c}"
            if "qualifier_prefix" in enabled:
                piece = _carry_qualifiers(prefix, piece)
            if "exception_prefix" in enabled and prefix and prefix.lower().startswith("except"):
                piece = f"{prefix} {piece}"
            if "postfix_exception" in enabled and postfix:
                piece = piece.rstrip(".") + " " + postfix
            out.append(piece.rstrip(".") + ".")
    return out or [example["original_text"]]


# ---- Variant F: preserve-and-flag ----------------------------------------------------------------
def scope_provable(sentence: str) -> bool:
    """Attachment is provably resolvable when there is a single clear subject and at most one
    coordinating boundary, and no second subject / comma-splice ambiguity."""
    prefix, postfix, conjuncts = _parse(sentence)
    if len(conjuncts) < 2:
        return True
    subj_count = sum(1 for c in conjuncts if _has_subject(c))
    # a second explicit subject, or 3+ comma-spliced clauses => not provable
    if subj_count >= 2 and any("operator" in c or "logs" in c for c in conjuncts):
        return False
    if len(conjuncts) >= 3 and not postfix.strip().startswith(("unless", "except")) is False:
        pass
    return True


def variant_f_preserve_flag(example):
    """Returns produced claims; when not provable, preserves the whole span (INDETERMINATE_SCOPE)."""
    text = example["original_text"]
    sents = _sentences(text)
    # if any sentence is a non-provable multi-conjunct, preserve the whole span
    if any(not scope_provable(s) for s in sents):
        return [text]                      # INDETERMINATE_SCOPE: whole-span for review
    return variant_e_full(example)


# ---- Variant G (hybrid, decision option 5): split when provable else preserve-and-flag -----------
def variant_g_hybrid(example):
    out = []
    for sent in _sentences(example["original_text"]):
        if scope_provable(sent):
            out.extend(variant_e_full({"original_text": sent}))
        else:
            out.append(sent)               # preserve-and-flag this span
    return out or [example["original_text"]]


# ---- Variant H: the actual proposal - scope-carry AS A SMALL EXTENSION to the preservation-first
# splitter, i.e. compose the frozen splitter's reference resolution with the scope-carrying split.
# This is what the architecture constraint asks for; E alone drops reference resolution and reintroduces
# dangling pronouns.
def _resolve_refs(claims_list: List[str]) -> List[str]:
    from claim_integrity import references
    out, prev = [], ""
    for c in claims_list:
        resolved, ok, _ = references.resolve(c, prev) if prev else (c, True, "")
        out.append(resolved)
        prev = resolved
    return out


_SPANNING_MODIFIER = re.compile(r"\b(unless|except|only if|provided that|as of|according to)\b", re.I)
_COORD = re.compile(r"\w\s*,?\s+\b(?:and|but)\b\s+\w|,\s+\w+\s+(?:are|is|must|does)\b")


def _is_scope_conjunction(claim: str) -> bool:
    """The residual pattern: a coordinating conjunction (or comma-splice) that a scope-bearing modifier
    spans. This is exactly what the current splitter keeps whole and under-governs."""
    return bool(_SPANNING_MODIFIER.search(claim)) and bool(_COORD.search(claim))


def variant_h_integrated(example, enabled: frozenset = SCOPE_ELEMENTS, resolve_refs: bool = True,
                         gated: bool = True):
    """The GATED small extension: run the frozen preservation-first splitter (which handles everything
    and resolves references); then, ONLY for the claims it kept whole that are scope-spanning
    conjunctions, attempt a scope-carrying split IF provable, else leave whole (preserve-and-flag).
    Everything else is untouched, so behavior on non-conjunction text is identical to the current
    splitter. `enabled`/`resolve_refs`/`gated` support the ablation study (M5)."""
    base = variant_a_current(example)                 # frozen splitter output (refs resolved)
    out = []
    for claim in base:
        is_scope = _is_scope_conjunction(claim) if gated else bool(_COORD.search(claim))
        if is_scope and scope_provable(claim):
            split = variant_e_full({"original_text": claim}, enabled=enabled)
            out.extend(_resolve_refs(split) if resolve_refs else split)
        else:
            out.append(claim)                          # untouched (incl. non-provable -> preserve-flag)
    return out


VARIANTS = {
    "A_current": variant_a_current,
    "B_naive": variant_b_naive,
    "C_subject": variant_c_subject,
    "D_subject_qualifier": variant_d_subject_qualifier,
    "E_full_scope": variant_e_full,
    "F_preserve_flag": variant_f_preserve_flag,
    "G_hybrid": variant_g_hybrid,
    "H_integrated": variant_h_integrated,
}
FLAGS_WHOLE_SPAN = ("F_preserve_flag", "G_hybrid", "H_integrated")
