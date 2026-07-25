"""Configurable resource-consumption limits and text/source-code checks.

All limits live in one immutable :class:`EvidenceLimits` object so they can be
injected and tuned per deployment. Defaults are generous (they never trip on
ordinary evidence); safety tests pass small limits directly to the check
functions. Every check fails **closed** with a typed error — nothing is
partially accepted.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import TextLimitError

MiB = 1024 * 1024


@dataclass(frozen=True)
class EvidenceLimits:
    # global input
    max_input_bytes: int = 25 * MiB
    # text / source code
    max_characters: int = 5_000_000
    max_lines: int = 200_000
    max_line_length: int = 100_000
    max_null_bytes: int = 0
    max_invalid_utf_ratio: float = 0.30
    # archive (DOCX/ZIP)
    max_archive_entries: int = 2_000
    max_entry_bytes: int = 25 * MiB
    max_total_uncompressed_bytes: int = 100 * MiB
    max_compression_ratio: float = 100.0
    max_path_depth: int = 16
    max_xml_bytes: int = 25 * MiB
    # JSON
    max_json_bytes: int = 10 * MiB
    max_json_depth: int = 64
    max_json_fields: int = 50_000
    max_json_array_length: int = 200_000
    max_json_total_scalars: int = 500_000
    max_json_string_length: int = 1_000_000
    # CSV
    max_csv_bytes: int = 10 * MiB
    max_csv_rows: int = 200_000
    max_csv_columns: int = 2_000
    max_csv_cell_length: int = 100_000
    max_csv_total_cells: int = 2_000_000
    max_csv_header_length: int = 100_000


DEFAULT_LIMITS = EvidenceLimits()


def check_input_size(byte_len: int, limits: EvidenceLimits = DEFAULT_LIMITS) -> None:
    if byte_len > limits.max_input_bytes:
        raise TextLimitError(
            f"input of {byte_len} bytes exceeds max_input_bytes={limits.max_input_bytes}"
        )


def looks_binary(raw: bytes, text: str, limits: EvidenceLimits = DEFAULT_LIMITS) -> bool:
    """Heuristic: true if content is likely binary mislabeled as text."""
    if text.count("\x00") > limits.max_null_bytes:
        return True
    if not text:
        return False
    replacements = text.count("�")
    return (replacements / len(text)) > limits.max_invalid_utf_ratio


def check_text_limits(
    raw: bytes, text: str, limits: EvidenceLimits = DEFAULT_LIMITS
) -> tuple[str, ...]:
    """Validate a decoded text body. Returns warnings; raises on hard limits.

    Deterministic invalid-UTF policy: sequences are *replaced* (never silently
    discarded) and surface a ``INVALID_UTF_REPLACED`` warning; content that is
    predominantly undecodable or contains null bytes is rejected as binary.
    """
    if len(text) > limits.max_characters:
        raise TextLimitError(
            f"{len(text)} characters exceeds max_characters={limits.max_characters}"
        )
    lines = text.split("\n")
    if len(lines) > limits.max_lines:
        raise TextLimitError(f"{len(lines)} lines exceeds max_lines={limits.max_lines}")
    longest = max((len(ln) for ln in lines), default=0)
    if longest > limits.max_line_length:
        raise TextLimitError(
            f"longest line {longest} exceeds max_line_length={limits.max_line_length}"
        )
    if looks_binary(raw, text, limits):
        raise TextLimitError("content appears binary (null bytes or undecodable) — not text")

    warnings: list[str] = []
    if "�" in text:
        warnings.append("INVALID_UTF_REPLACED")
    return tuple(warnings)
