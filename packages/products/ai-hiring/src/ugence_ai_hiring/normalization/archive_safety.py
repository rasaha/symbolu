"""Defensive ZIP/DOCX archive inspection.

DOCX is a ZIP container, so it must be inspected before extraction to block
archive-expansion attacks. Reads are **in-memory and bounded** — nothing is
written to the filesystem. Structural failures (not a zip, encrypted entry)
raise :class:`ContentExtractionError`; abuse (bomb, ratio, traversal, oversize)
raises :class:`ArchiveSafetyError`. Both fail closed.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from ..errors import ArchiveSafetyError, ContentExtractionError
from .limits import DEFAULT_LIMITS, EvidenceLimits


@dataclass(frozen=True)
class ArchiveReport:
    entry_count: int
    total_uncompressed: int
    max_ratio: float


def _is_unsafe_path(name: str, max_depth: int) -> bool:
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return True  # absolute path
    parts = name.replace("\\", "/").split("/")
    if ".." in parts:
        return True  # path traversal
    return len([p for p in parts if p]) > max_depth


def inspect_archive(
    content: bytes, limits: EvidenceLimits = DEFAULT_LIMITS
) -> ArchiveReport:
    """Validate an archive's structure and resource bounds without extracting it."""
    if len(content) > limits.max_input_bytes:
        raise ArchiveSafetyError(
            f"archive of {len(content)} bytes exceeds max_input_bytes"
        )
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ContentExtractionError(f"not a valid archive: {exc}") from exc

    infos = zf.infolist()
    if len(infos) > limits.max_archive_entries:
        raise ArchiveSafetyError(
            f"{len(infos)} entries exceeds max_archive_entries={limits.max_archive_entries}"
        )

    total = 0
    max_ratio = 0.0
    for info in infos:
        if getattr(info, "flag_bits", 0) & 0x1:
            raise ContentExtractionError("archive contains an encrypted entry")
        if _is_unsafe_path(info.filename, limits.max_path_depth):
            raise ArchiveSafetyError(f"unsafe archive path: {info.filename!r}")
        if info.file_size > limits.max_entry_bytes:
            raise ArchiveSafetyError(
                f"entry {info.filename!r} size {info.file_size} exceeds max_entry_bytes"
            )
        total += info.file_size
        if total > limits.max_total_uncompressed_bytes:
            raise ArchiveSafetyError(
                "total uncompressed size exceeds max_total_uncompressed_bytes"
            )
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            max_ratio = max(max_ratio, ratio)
            if ratio > limits.max_compression_ratio:
                raise ArchiveSafetyError(
                    f"entry {info.filename!r} compression ratio {ratio:.1f} exceeds "
                    f"max_compression_ratio={limits.max_compression_ratio}"
                )
    return ArchiveReport(len(infos), total, max_ratio)


def read_entry_bounded(
    content: bytes, name: str, limits: EvidenceLimits = DEFAULT_LIMITS
) -> bytes:
    """Read a single named entry with an XML/byte ceiling (in-memory)."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        try:
            info = zf.getinfo(name)
        except KeyError as exc:
            raise ContentExtractionError(f"archive missing required entry {name!r}") from exc
        if info.file_size > limits.max_xml_bytes:
            raise ArchiveSafetyError(
                f"entry {name!r} uncompressed size exceeds max_xml_bytes"
            )
        with zf.open(info) as fh:
            data = fh.read(limits.max_xml_bytes + 1)
    if len(data) > limits.max_xml_bytes:
        raise ArchiveSafetyError(f"entry {name!r} exceeds max_xml_bytes on read")
    return data
