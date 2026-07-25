"""Content extraction — raw submission -> text and/or named fields.

Dependency-free (stdlib only). Text formats decode directly; DOCX is read via
``zipfile`` + XML (real extraction, no third-party library); PDF uses a minimal
extractor for uncompressed text streams. Structured formats (JSON/CSV/
STRUCTURED_RESPONSE) yield a field mapping so downstream quarantine can operate
per field.

Explicitly out of scope (documented limitations):
* PDF: only uncompressed ``(...) Tj`` / ``TJ`` text operators; no OCR, no
  FlateDecode streams. Scanned/compressed PDFs extract empty text.
* No video/audio decoding — transcripts are provided as text.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Dict

from ..errors import ContentExtractionError, UnsupportedFormatError
from .cleaners import decode_bytes
from .models import STRUCTURED_FORMATS, EvidenceFormat


@dataclass(frozen=True)
class ExtractedContent:
    """Result of content extraction."""

    text: str = ""
    fields: Dict[str, str] = field(default_factory=dict)
    is_structured: bool = False


# --- text formats ----------------------------------------------------------
def _parse_text(content: bytes, fields: Dict[str, str] | None) -> ExtractedContent:
    return ExtractedContent(text=decode_bytes(content))


# --- DOCX (stdlib zipfile + XML) ------------------------------------------
_WT_RE = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.DOTALL)
_PARA_RE = re.compile(r"</w:p>")


def _parse_docx(content: bytes, fields: Dict[str, str] | None) -> ExtractedContent:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ContentExtractionError(f"invalid DOCX submission: {exc}") from exc
    # Split into paragraphs, join the w:t runs within each.
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


# --- PDF (minimal, uncompressed text operators) ---------------------------
_PDF_TEXT_RE = re.compile(r"\((?:\\.|[^\\()])*\)")


def _parse_pdf(content: bytes, fields: Dict[str, str] | None) -> ExtractedContent:
    text_data = content.decode("latin-1", errors="replace")
    out: list[str] = []
    # Extract text shown by BT..ET blocks via (string) Tj / TJ operators.
    for block in re.findall(r"BT(.*?)ET", text_data, re.DOTALL):
        for literal in _PDF_TEXT_RE.findall(block):
            inner = literal[1:-1]
            inner = (
                inner.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
                .replace("\\n", "\n").replace("\\r", "\n").replace("\\t", "\t")
            )
            out.append(inner)
        out.append("\n")
    return ExtractedContent(text="".join(out).strip())


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


def _parse_json(content: bytes, fields: Dict[str, str] | None) -> ExtractedContent:
    if fields is not None:
        return ExtractedContent(fields=dict(fields), is_structured=True)
    try:
        obj = json.loads(decode_bytes(content))
    except json.JSONDecodeError as exc:
        raise ContentExtractionError(f"invalid JSON submission: {exc}") from exc
    return ExtractedContent(fields=_flatten_json(obj), is_structured=True)


def _parse_csv(content: bytes, fields: Dict[str, str] | None) -> ExtractedContent:
    if fields is not None:
        return ExtractedContent(fields=dict(fields), is_structured=True)
    text = decode_bytes(content)
    reader = csv.DictReader(io.StringIO(text))
    columns: Dict[str, list[str]] = {}
    try:
        for row in reader:
            for col, val in row.items():
                if col is None:
                    continue
                columns.setdefault(col, []).append(val or "")
    except csv.Error as exc:
        raise ContentExtractionError(f"invalid CSV submission: {exc}") from exc
    flat = {col: "\n".join(vals) for col, vals in columns.items()}
    return ExtractedContent(fields=flat, is_structured=True)


def _parse_structured_response(
    content: bytes, fields: Dict[str, str] | None
) -> ExtractedContent:
    if fields is not None:
        return ExtractedContent(fields=dict(fields), is_structured=True)
    return _parse_json(content, None)


_PARSERS: Dict[EvidenceFormat, Callable[[bytes, Dict[str, str] | None], ExtractedContent]] = {
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


def extract(fmt: EvidenceFormat, content: bytes, fields: Dict[str, str] | None = None) -> ExtractedContent:
    """Extract content for a declared format. Raises for unsupported formats."""
    parser = _PARSERS.get(fmt)
    if parser is None:
        raise UnsupportedFormatError(f"no parser registered for format {fmt.value}")
    result = parser(content, fields)
    # A structured format with no parseable fields is a hard extraction error.
    if fmt in STRUCTURED_FORMATS and not result.fields:
        raise ContentExtractionError(f"no fields extracted for structured format {fmt.value}")
    return result
