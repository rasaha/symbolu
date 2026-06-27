"""Distant-supervision lexicon for grounding Vritti / Aspect heads.

HONESTY: there is no ground-truth annotation standard for "Vritti". This is a
documented WEAK / DISTANT-supervision lexicon — word -> category by a curated rule.
It is a legitimate, standard NLP technique and a large step up from surface-feature
labels (vowel count), because the categories are *semantically meaningful*. But it
is NOT ground truth: it tests whether the backbone linearly encodes these
lexically-defined semantic categories, validated by (a) a shuffled-label control and
(b) generalization to UNSEEN words. It does not prove the patent's Vritti is real.

Vritti (5): epistemic/affective state.  Aspect (10): functional/semantic role.
Overlapping words resolve to the first listed category (priority order below).
"""
from __future__ import annotations

import re
from typing import Dict, Optional

VRITTI_WORDS = {
    "valid_cognition": "fact true know knows real proof certain evident clear sure "
                       "correct valid exists confirmed verified knowledge actual",
    "imagination":     "imagine dream suppose maybe perhaps could might possibly "
                       "fantasy invent create wonder hypothesis would story fiction hypothetical",
    "misperception":   "not no wrong false error mistake illusion confuse confused "
                       "doubt deny fail incorrect myth never cannot lie misleading",
    "inertness":       "still idle rest sleep quiet calm dull empty nothing void "
                       "blank inert passive motionless numb dormant inactive",
    "memory":          "remember recall memory past was were had ago history old "
                       "before once remembered ancient former recollect previously",
}

ASPECT_WORDS = {
    "acting":     "do act make run move build go take push pull work perform execute drive",
    "tagging":    "name label tag call thing object identity term word title naming",
    "forming":    "form shape structure frame pattern order arrange design construct compose",
    "thinking":   "think believe feel want fear desire consider hope worry mind",
    "directing":  "direct lead control guide command manage steer govern rule aim",
    "reasoning":  "reason because therefore thus logic infer deduce argue since hence conclude",
    "purposing":  "purpose goal why meaning intent mission value sake objective",
    "observing":  "observe watch see notice witness look perceive view monitor regard",
    "unifying":   "unite join whole together all one unity connect merge combine total",
    "absolute":   "absolute being source infinite eternal ultimate essence truth pure beyond origin",
}

VRITTI_NAMES = list(VRITTI_WORDS)
ASPECT_NAMES = list(ASPECT_WORDS)


def _build(spec: Dict[str, str]) -> Dict[str, int]:
    m: Dict[str, int] = {}
    for idx, (_, words) in enumerate(spec.items()):
        for w in words.split():
            m.setdefault(w, idx)          # first category wins
    return m


VRITTI_MAP = _build(VRITTI_WORDS)
ASPECT_MAP = _build(ASPECT_WORDS)


def normalize(word: str) -> str:
    return re.sub(r"[^a-z]", "", word.lower())


def vritti_label(word: str) -> Optional[int]:
    return VRITTI_MAP.get(normalize(word))


def aspect_label(word: str) -> Optional[int]:
    return ASPECT_MAP.get(normalize(word))


def coverage() -> Dict[str, int]:
    return {"vritti_words": len(VRITTI_MAP), "aspect_words": len(ASPECT_MAP),
            "vritti_classes": len(VRITTI_WORDS), "aspect_classes": len(ASPECT_WORDS)}
