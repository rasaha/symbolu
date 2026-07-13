"""A conservative, recall-favoring rule-based P0 detector.

This is NOT a learned model and NOT the product. It is a transparent keyword/regex
protector used to estimate the *deployable* protected fraction and the
precision/recall a simple rule set achieves against ground-truth critical units.
It is intentionally over-broad (favoring recall) so the experiment can observe the
precision/compression-ceiling tension (DETECTOR_PRECISION_BOTTLENECK) rather than
assume it away.
"""

from __future__ import annotations

import re

from .units import Context

_NEGATION = re.compile(r"\b(not|never|no|don't|cannot|can't|must not|unless|except|without)\b", re.I)
_NUMERIC = re.compile(r"\d")
_IDENTIFIER = re.compile(r"(://|arn:|sha256:|[A-Za-z]+://|\b[A-Z]{2,}-\d+\b)")
_APPROVAL = re.compile(r"\b(approv|dual control|sign-off|authoriz)", re.I)
_POLICY = re.compile(r"\b(must|shall|forbid|policy|exception|only if|require|prohibit)", re.I)
_EVIDENCE = re.compile(r"\b(backup|simulation|artifact|attestation|rollback|evidence)", re.I)

_RULES = (_NEGATION, _NUMERIC, _IDENTIFIER, _APPROVAL, _POLICY, _EVIDENCE)


def is_protected(text: str) -> bool:
    return any(r.search(text) for r in _RULES)


def protect(ctx: Context) -> set:
    """Return the set of unit ids the conservative detector marks P0."""
    return {u.id for u in ctx.units if is_protected(u.text)}
