"""
Entity/predicate normalization + direction resolution (deterministic).

- normalize_entity: lower-case, strip articles/quantifiers and punctuation, collapse
  whitespace, so surface variants map to a canonical key ("The Acme Corp." -> "acme corp").
- resolve_direction: given the matched predicate ``Form`` and the entity on each side of
  the predicate, return (subject, object, Direction). For a PASSIVE form the by-agent
  (right side) becomes the subject and the left side the object; the normalized direction
  is then always SUBJECT_TO_OBJECT unless a side is missing.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import Form
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import Direction

_ARTICLES = ("the ", "a ", "an ", "all ", "any ", "our ", "its ", "their ")


def normalize_entity(text: str) -> str:
    t = (text or "").strip().lower().strip(".,;:\"'()")
    for art in _ARTICLES:
        if t.startswith(art):
            t = t[len(art):]
    t = re.sub(r"\s+", " ", t).strip()
    return t


def resolve_direction(form: Form, left: Optional[str], right: Optional[str]
                      ) -> Tuple[Optional[str], Optional[str], Direction]:
    if left is None or right is None:
        # only one side present -> direction cannot be fixed
        subj = left if left is not None else right
        return (subj, None, Direction.UNCLEAR)
    if form is Form.PASSIVE:
        # "OBJECT is <verb> by SUBJECT" -> subject = right (agent), object = left
        return (right, left, Direction.SUBJECT_TO_OBJECT)
    return (left, right, Direction.SUBJECT_TO_OBJECT)
