"""Content extraction — raw submission -> text and/or named fields.

Dependency-free (stdlib only). Every parser routes through the Phase-2.5 safety
modules: text formats through text limits (binary-mislabel + size), DOCX through
archive-safety, JSON/CSV through structured limits. Extraction never *infers*
success — it returns the content plus any warnings, and the pipeline assigns an
explicit :class:`ExtractionStatus`.

Documented PDF limitations: only uncompressed ``(...) Tj`` / ``TJ`` text; no OCR,
no FlateDecode. Encrypted PDFs raise; ambiguous image-only/compressed PDFs are
routed for manual review; empty text is reported EMPTY by the pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from ..errors import (
    ContentExtractionError,
    EncryptedContentError,
    ManualReviewRequiredError,
    UnsupportedFormatError,
)
from .archive_safety import read_entry_bounded, inspect_archive
from .cleaners import decode_bytes
from .limits import DEFAULT_LIMITS, EvidenceLimits, check_text_limits
from .models import STRUCTURED_FORMATS, EvidenceFormat
from .structured_limits import check_csv_bounded, parse_json_bounded


@dataclass(frozen=True)
class ExtractedContent:
    text: str = ""
    fields: Dict[str, str] = field(default_factory=dict)
    is_structured: bool = False
    warnings: tuple[str, ...] = ()
    manual_review: bool = False


# --- text formats ----------------------------------------------------------
def _parse_text(content: bytes, fields, limits: EvidenceLimits) -> ExtractedContent:
    text = decode_bytes(content)
    warnings = check_text_limits(content, text, limits)  # raises on hard limits
    return ExtractedContent(text=text, warnings=warnings)


# --- DOCX (archive-safe stdlib zip + XML) ---------------------------------
_WT_RE = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.DOTALL)
_PARA_RE = re.compile(r"</w:p>")


def _parse_docx(content: bytes, fields, limits: EvidenceLimits) -> ExtractedContent:
    inspect_archive(content, limits)  # raises on unsafe/malformed archive
    xml = read_entry_bounded(content, "word/document.xml", limits).decode(
        "utf-8", errors="replace"
    )
    paragraphs = []
    for para in _PARA_RE.split(xml):
        runs = _WT_RE.findall(para)
        if runs:
            paragraphs.append(_unescape_xml("".join(runs)))
    return ExtractedContent(text="\n".join(paragraphs))


def _unescape_xml(text: str) -> str:
    return (
        text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&quot;", '"').replace("&apos;", "'")
    )


# --- PDF (minimal, classified) --------------------------------------------
_PDF_TEXT_RE = re.compile(r"\((?:\\.|[^\\()])*\)")


def _parse_pdf(content: bytes, fields, limits: EvidenceLimits) -> ExtractedContent:
    if b"/Encrypt" in content:
        raise EncryptedContentError("encrypted PDF cannot be extracted (no OCR/decrypt)")
    text_data = content.decode("latin-1", errors="replace")
    out: list[str] = []
    for block in re.findall(r"BT(.*?)ET", text_data, re.DOTALL):
        for literal in _PDF_TEXT_RE.findall(block):
            inner = literal[1:-1]
            inner = (
                inner.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
                .replace("\\n", "\n").replace("\\r", "\n").replace("\\t", "\t")
            )
            out.append(inner)
        out.append("\n")
    text = "".join(out).strip()
    if not text:
        # Ambiguous: compressed/scanned/image-only vs. genuinely empty. If the
        # PDF carries compressed streams or images we cannot decode, route for
        # manual review rather than accept empty content.
        if b"FlateDecode" in content or b"/Image" in content or b"/XObject" in content:
            raise ManualReviewRequiredError(
                "PDF has no extractable native text (compressed/scanned); manual review"
            )
    return ExtractedContent(text=text)


# --- structured formats ----------------------------------------------------
def _flatten_json(obj: object, prefix: str = "") -> Dict[str, str]:
    flat: Dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            flat.update(_flatten_json(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flat.update(_flatten_json(v, f"{prefix}[{i}]"))
    else:
        flat[prefix] = "" if obj is None else str(obj)
    return flat


def _parse_json(content: bytes, fields, limits: EvidenceLimits) -> ExtractedContent:
    if fields is not None:
        return ExtractedContent(fields=dict(fields), is_structured=True)
    obj = parse_json_bounded(content, limits)  # raises on malformed / over-limit
    return ExtractedContent(fields=_flatten_json(obj), is_structured=True)


def _parse_csv(content: bytes, fields, limits: EvidenceLimits) -> ExtractedContent:
    if fields is not None:
        return ExtractedContent(fields=dict(fields), is_structured=True)
    check_csv_bounded(content, limits)  # raises on malformed / over-limit
    import csv
    import io

    text = decode_bytes(content)
    reader = csv.DictReader(io.StringIO(text))
    columns: Dict[str, list[str]] = {}
    for row in reader:
        for col, val in row.items():
            if col is None:
                continue
            columns.setdefault(col, []).append(val or "")
    flat = {col: "\n".join(vals) for col, vals in columns.items()}
    return ExtractedContent(fields=flat, is_structured=True)


def _parse_structured_response(content: bytes, fields, limits: EvidenceLimits) -> ExtractedContent:
    if fields is not None:
        return ExtractedContent(fields=dict(fields), is_structured=True)
    return _parse_json(content, None, limits)


_PARSERS: Dict[EvidenceFormat, Callable[..., ExtractedContent]] = {
    EvidenceFormat.TEXT: _parse_text,
    EvidenceFormat.MARKDOWN: _parse_text,
    EvidenceFormat.SOURCE_CODE: _parse_text,
    EvidenceFormat.INTERVIEW_TRANSCRIPT: _parse_text,
    EvidenceFormat.WORK_SAMPLE: _parse_text,
    EvidenceFormat.PORTFOLIO_ARTIFACT: _parse_text,
    EvidenceFormat.DOCX: _parse_docx,
    EvidenceFormat.PDF: _parse_pdf,
    EvidenceFormat.JSON: _parse_json,
    EvidenceFormat.CSV: _parse_csv,
    EvidenceFormat.STRUCTURED_RESPONSE: _parse_structured_response,
}


def extract(
    fmt: EvidenceFormat,
    content: bytes,
    fields: Optional[Dict[str, str]] = None,
    limits: EvidenceLimits = DEFAULT_LIMITS,
) -> ExtractedContent:
    """Extract content for a declared format. Raises typed errors for failures."""
    parser = _PARSERS.get(fmt)
    if parser is None:
        raise UnsupportedFormatError(f"no parser registered for format {fmt.value}")
    result = parser(content, fields, limits)
    if fmt in STRUCTURED_FORMATS and not result.fields:
        raise ContentExtractionError(f"no fields extracted for structured format {fmt.value}")
    return result
