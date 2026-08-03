"""Machine-readable format capability matrix.

The single source of truth for how each format is supported, its limitations,
and its failure behavior. The README and API docs must reference this rather
than claiming blanket "PDF supported".
"""

from __future__ import annotations

from enum import Enum

from ..domain.base import DomainModel
from .models import EvidenceFormat


class SupportLevel(str, Enum):
    FULL = "FULL"
    LIMITED = "LIMITED"
    STRUCTURED_ONLY = "STRUCTURED_ONLY"
    TEXT_ONLY = "TEXT_ONLY"
    UNSUPPORTED = "UNSUPPORTED"


class FormatCapability(DomainModel):
    format: EvidenceFormat
    support_level: SupportLevel
    parser: str
    supported_features: tuple[str, ...]
    unsupported_features: tuple[str, ...]
    resource_limits: tuple[str, ...]
    failure_behavior: str
    evaluation_eligibility_rule: str


_TEXT_LIMITS = ("max_input_bytes", "max_characters", "max_lines", "max_line_length")
_ELIGIBILITY = "eligible only when status in {SUCCEEDED, SUCCEEDED_WITH_WARNINGS}"

CAPABILITY_MATRIX: dict[EvidenceFormat, FormatCapability] = {
    EvidenceFormat.TEXT: FormatCapability(
        format=EvidenceFormat.TEXT, support_level=SupportLevel.FULL, parser="text-decode",
        supported_features=("utf-8 decode", "profile-aware normalization"),
        unsupported_features=("binary content",),
        resource_limits=_TEXT_LIMITS, failure_behavior="block on binary/oversize",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.MARKDOWN: FormatCapability(
        format=EvidenceFormat.MARKDOWN, support_level=SupportLevel.FULL, parser="text-decode",
        supported_features=("utf-8 decode",), unsupported_features=("embedded binaries",),
        resource_limits=_TEXT_LIMITS, failure_behavior="block on binary/oversize",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.SOURCE_CODE: FormatCapability(
        format=EvidenceFormat.SOURCE_CODE, support_level=SupportLevel.FULL, parser="text-decode",
        supported_features=("code-safe normalization (indentation preserved)",),
        unsupported_features=("compiled binaries",),
        resource_limits=_TEXT_LIMITS, failure_behavior="block on binary/oversize",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.INTERVIEW_TRANSCRIPT: FormatCapability(
        format=EvidenceFormat.INTERVIEW_TRANSCRIPT, support_level=SupportLevel.TEXT_ONLY,
        parser="text-decode", supported_features=("transcript text",),
        unsupported_features=("audio/video decoding",),
        resource_limits=_TEXT_LIMITS, failure_behavior="block on binary/oversize",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.WORK_SAMPLE: FormatCapability(
        format=EvidenceFormat.WORK_SAMPLE, support_level=SupportLevel.TEXT_ONLY,
        parser="text-decode", supported_features=("text work products",),
        unsupported_features=("binary artifacts",),
        resource_limits=_TEXT_LIMITS, failure_behavior="block on binary/oversize",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.PORTFOLIO_ARTIFACT: FormatCapability(
        format=EvidenceFormat.PORTFOLIO_ARTIFACT, support_level=SupportLevel.TEXT_ONLY,
        parser="text-decode", supported_features=("text artifacts / references",),
        unsupported_features=("images", "binaries"),
        resource_limits=_TEXT_LIMITS, failure_behavior="block on binary/oversize",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.JSON: FormatCapability(
        format=EvidenceFormat.JSON, support_level=SupportLevel.STRUCTURED_ONLY,
        parser="json-bounded",
        supported_features=("field extraction", "duplicate-key rejection"),
        unsupported_features=("streaming JSON", "non-utf8 encodings"),
        resource_limits=("max_json_bytes", "max_json_depth", "max_json_fields",
                         "max_json_array_length", "max_json_string_length"),
        failure_behavior="block on malformed/over-limit",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.CSV: FormatCapability(
        format=EvidenceFormat.CSV, support_level=SupportLevel.STRUCTURED_ONLY,
        parser="csv-bounded", supported_features=("column extraction",),
        unsupported_features=("arbitrary dialects",),
        resource_limits=("max_csv_bytes", "max_csv_rows", "max_csv_columns",
                         "max_csv_cell_length"),
        failure_behavior="block on malformed/over-limit",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.STRUCTURED_RESPONSE: FormatCapability(
        format=EvidenceFormat.STRUCTURED_RESPONSE, support_level=SupportLevel.STRUCTURED_ONLY,
        parser="json-bounded / provided-fields",
        supported_features=("named field extraction",),
        unsupported_features=("free-form binary",),
        resource_limits=("max_json_fields", "max_json_string_length"),
        failure_behavior="block on malformed/over-limit",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.DOCX: FormatCapability(
        format=EvidenceFormat.DOCX, support_level=SupportLevel.LIMITED,
        parser="zip+xml (stdlib)",
        supported_features=("paragraph text from document.xml", "archive-safety checks"),
        unsupported_features=("images", "embedded objects", "encrypted DOCX",
                              "tracked-changes semantics"),
        resource_limits=("max_archive_entries", "max_entry_bytes",
                         "max_total_uncompressed_bytes", "max_compression_ratio",
                         "max_xml_bytes"),
        failure_behavior="block on unsafe archive / malformed; empty text is EMPTY",
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
    EvidenceFormat.PDF: FormatCapability(
        format=EvidenceFormat.PDF, support_level=SupportLevel.LIMITED,
        parser="native-text (uncompressed operators)",
        supported_features=("bounded native-text extraction from uncompressed streams",),
        unsupported_features=("OCR", "scanned/image-only pages", "encrypted PDFs",
                              "FlateDecode/compressed streams", "complex layouts"),
        resource_limits=("max_input_bytes", "max_characters"),
        failure_behavior=(
            "empty text → EMPTY (blocked); encrypted → ENCRYPTED; ambiguous "
            "image-only vs unsupported → MANUAL_REVIEW_REQUIRED"
        ),
        evaluation_eligibility_rule=_ELIGIBILITY,
    ),
}


def get_capability(fmt: EvidenceFormat) -> FormatCapability:
    return CAPABILITY_MATRIX[fmt]
