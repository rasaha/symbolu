"""Text normalization.

Removes transport artifacts and normalizes encoding/whitespace **without
altering semantic content**. Two profiles exist because "normalize whitespace"
is not safe for all formats:

* ``PROSE`` — full normalization: NFC Unicode, tabs→spaces, collapse repeated
  spaces, strip trailing whitespace per line. Safe for prose (TEXT, MARKDOWN,
  transcripts).
* ``CODE_SAFE`` — minimal: NFC Unicode, strip BOM/zero-width/control artifacts,
  normalize line endings, strip trailing whitespace per line, but preserve
  internal runs of spaces and tabs. Used for SOURCE_CODE / JSON / CSV, where
  indentation and spacing are semantically significant.

Both profiles: normalize line endings to ``\\n``, decode invalid UTF-8
defensively, and remove BOM and zero-width transport characters.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum

# Zero-width / BOM / non-character transport artifacts to strip.
_ZERO_WIDTH = "﻿​‌‍⁠"
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAILING_WS_RE = re.compile(r"[ \t]+(?=\n)")
_MULTISPACE_RE = re.compile(r" {2,}")


class NormalizationProfile(str, Enum):
    PROSE = "PROSE"
    CODE_SAFE = "CODE_SAFE"


def decode_bytes(content: bytes) -> str:
    """Decode bytes to text, repairing invalid UTF-8 rather than failing."""
    return content.decode("utf-8", errors="replace")


def _strip_transport_artifacts(text: str) -> str:
    # Remove BOM / zero-width characters and control chars (except \n and \t).
    for ch in _ZERO_WIDTH:
        text = text.replace(ch, "")
    return _CONTROL_RE.sub("", text)


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_text(
    text: str, profile: NormalizationProfile = NormalizationProfile.PROSE
) -> str:
    """Normalize text under the given profile. Idempotent."""
    text = unicodedata.normalize("NFC", text)
    text = _strip_transport_artifacts(text)
    text = _normalize_line_endings(text)

    if profile is NormalizationProfile.PROSE:
        text = text.replace("\t", " ")
        text = _MULTISPACE_RE.sub(" ", text)

    # Strip trailing whitespace on each line (safe for both profiles).
    text = _TRAILING_WS_RE.sub("", text)
    # Strip a single leading BOM-equivalent newline noise / trailing newline run.
    return text.strip("\n")
