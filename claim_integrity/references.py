"""Reference resolution (Phase 9 core; expanded in Phase 16). Resolves a leading anaphor in a
dependent span to the subject of its antecedent, so a decomposed unit is self-contained and does not
carry a dangling pronoun downstream. Deterministic, conservative: if the antecedent subject cannot be
identified, the pronoun is left and the unit is marked unresolved (REFERENCE_ERROR / ESCALATE), never
guessed.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

_ANAPHOR = re.compile(r"^(\s*)(it|they|this|that|these|those|he|she|its|their)\b", re.I)
# subject = leading noun phrase of a span, up to the first verb-ish token
_SUBJECT = re.compile(r"^\s*(the [a-z]+|[A-Z][a-z]+)", re.I)


def antecedent_subject(prev_span: str) -> Optional[str]:
    m = _SUBJECT.match(prev_span)
    return m.group(1) if m else None


def resolve(span: str, prev_span: str) -> Tuple[str, bool, str]:
    """Return (resolved_text, resolved_ok, antecedent). If the span opens with an anaphor and an
    antecedent subject is found, substitute it; else leave the pronoun and flag unresolved."""
    m = _ANAPHOR.match(span)
    if not m:
        return span, True, ""
    subj = antecedent_subject(prev_span)
    if not subj:
        return span, False, ""
    resolved = _ANAPHOR.sub(m.group(1) + subj, span, count=1)
    return resolved, True, subj
