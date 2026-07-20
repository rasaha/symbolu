#!/usr/bin/env python3
"""
Blinding enforcement. The independent-annotator artifact must never carry any
author-only field. Checked structurally on the projected annotator record.
"""

from __future__ import annotations

from .schema import AnnotatorRecord

_BANNED = set(AnnotatorRecord.BANNED_FIELDS)


def annotator_is_blind(annot_dict: dict) -> list[str]:
    """Return the list of banned (author-only) keys present; empty = blind."""
    return sorted(k for k in annot_dict if k in _BANNED)
