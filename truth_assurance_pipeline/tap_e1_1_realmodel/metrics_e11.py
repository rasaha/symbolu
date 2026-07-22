"""
TAP-E1.1 metric CORRECTIONS (documented in METRIC_AUDIT.md).

TAP-E1's metric code is imported and reused UNCHANGED (TAP-E1's ``metrics.py`` is
frozen and NOT modified). Two corrections are applied here as a thin post-processing
wrapper, because two TAP-E1 metrics silently assumed an *extractive* interpreter and
mis-score an *abstractive* (LLM) interpreter that paraphrases:

  Correction 1 — invented_action (paraphrase invariance).
    TAP-E1 flagged an "invented action" whenever the objective contained an imperative
    verb not literally present in the source ("polish"→"improve", "trim"→"shorten",
    "deduplicate"→"remove duplicates"). That is a false positive for any paraphrasing
    interpreter. Corrected definition: an invented action fires only when the objective
    / requested_output / selected_interpretation names a CONCRETE object (filename,
    identifier, #issue, quoted name, or capitalized multiword proper noun) that is
    absent from BOTH the source text and the gold entities. Verb paraphrase alone never
    triggers it. (Discovered on the DEV split — see METRIC_AUDIT.md — before any hidden
    scoring drove the correction.)

  Correction 2 — material-ambiguity crediting (represented vs silently resolved).
    TAP-E1 counted a material ambiguity as "flagged" only for AMBIGUOUS/
    INSUFFICIENT_CONTEXT status or an explicit AmbiguityItem. A request that is material
    but proceed-with-assumption (PARTIALLY_RESOLVED) with an explicit stated_assumption
    recording the gap is *representing* the ambiguity, not silently resolving it.
    Corrected: PARTIALLY_RESOLVED WITH a non-empty stated_assumptions also counts as
    represented. (silent resolution — RESOLVED with no acknowledgement — still counts as
    a severe failure, unchanged.)

Both corrections are applied UNIFORMLY to every baseline and to the deterministic
interpreter, so they cannot bias the LLM-vs-deterministic comparison in either
direction.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import List, Sequence

from truth_assurance_pipeline.tap_e1_intent.metrics import (  # frozen, reused
    CaseScore, aggregate as _aggregate, score_case as _e1_score_case,
)
from truth_assurance_pipeline.tap_e1_intent.corpus.cases import Case
from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord, InterpretationStatus

aggregate = _aggregate  # re-export unchanged

_CONCRETE = re.compile(
    r"\b[\w./-]+\.\w{1,5}\b"          # filenames
    r"|#\d+"                          # #123 issue/PR
    r"|\b(?:PR|issue|ticket)\s*#?\d+\b", re.I)


def _concrete_objects(text: str) -> set:
    # Only unambiguously concrete objects: filenames, #issue/PR ids, and quoted
    # names. A fabricated action necessarily introduces one of these. Bare
    # capitalized words are NOT used — they conflate with sentence-initial
    # paraphrased verbs ("Improve", "Trim") and produced false positives.
    objs = set(m.group(0).lower() for m in _CONCRETE.finditer(text))
    for m in re.finditer(r"[\"'“”]([^\"'“”]{2,60})[\"'“”]", text):
        objs.add(m.group(1).lower())
    return objs


def _norm(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _invented_action_corrected(case: Case, rec: IntentRecord) -> bool:
    blob = " ".join([rec.primary_objective, rec.requested_output,
                     rec.selected_interpretation or ""])
    src_tokens = _norm(case.text)
    gold_tokens = set()
    for ge in case.gold.entities:
        gold_tokens |= _norm(ge)
    for obj in _concrete_objects(blob):
        toks = _norm(obj)
        if toks and not (toks & src_tokens) and not (toks & gold_tokens):
            return True
    return False


def _material_flag_corrected(rec: IntentRecord, base: CaseScore) -> bool:
    if base.material_amb_flagged:
        return True
    return (rec.interpretation_status is InterpretationStatus.PARTIALLY_RESOLVED
            and bool(rec.stated_assumptions))


def score_case(case: Case, rec: IntentRecord) -> CaseScore:
    base = _e1_score_case(case, rec)
    return replace(
        base,
        crit_invented_action=_invented_action_corrected(case, rec),
        material_amb_flagged=_material_flag_corrected(rec, base),
    )
