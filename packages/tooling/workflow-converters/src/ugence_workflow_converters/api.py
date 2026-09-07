"""Public API of the Ugence Workflow Converters.

    from ugence_workflow_converters.api import convert, write_outputs, ConversionRefused

    outcome = convert("n8n", export_bytes)      # ConversionOutcome, or ConversionRefused
    write_outputs(outcome, "out/")              # three files, nothing else

Every format name goes through :func:`convert`, which refuses, with a typed code, a
format that is not implemented (``UNSUPPORTED_FORMAT``) or one the owner deferred
(``DEFERRED_FORMAT``). The three outputs are the DRAFT pack, the sealed report and,
when the draft validated, the preview Workflow IR. There is no fourth output and no
side channel: nothing is fetched, executed, cached or kept.
"""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ugence_policy_workflow_compiler.api import PolicyPack
from ugence_policy_workflow_compiler.serialization import canonical_json

from .n8n import convert_n8n_export
from .preview import PREVIEW_STATUS, build_preview, summarize_preview
from .report import (
    ConversionRefused,
    ConversionReport,
    ConversionState,
    RefusalCode,
    RowOutcome,
)
from .version import (
    CLAIM,
    CONVERSION_REPORT_SCHEMA,
    DEFERRED_FORMATS,
    DEFERRED_REASON,
    DISTRIBUTION_VERSION,
    IMPLEMENTED_FORMATS,
    NEXT_FORMAT,
    PREVIEW_SCHEMA,
    VersionInfo,
    version_info,
)

__all__ = [
    "CLAIM",
    "CONVERSION_REPORT_SCHEMA",
    "DEFERRED_FORMATS",
    "DEFERRED_REASON",
    "DISTRIBUTION_VERSION",
    "IMPLEMENTED_FORMATS",
    "NEXT_FORMAT",
    "PREVIEW_SCHEMA",
    "PREVIEW_STATUS",
    "OUTPUT_FILES",
    "ConversionOutcome",
    "ConversionRefused",
    "ConversionReport",
    "ConversionState",
    "RefusalCode",
    "RowOutcome",
    "VersionInfo",
    "convert",
    "write_outputs",
    "version_info",
]

#: The only files a conversion writes, by role.
OUTPUT_FILES = {
    "pack": "policy_pack.draft.json",
    "report": "conversion_report.json",
    "preview": "preview_workflow_ir.v1.json",
}


@dataclass(frozen=True)
class ConversionOutcome:
    format: str
    pack: PolicyPack
    report: ConversionReport
    preview: Optional[Dict[str, Any]]
    connections: Tuple[Tuple[str, str], ...]

    @property
    def pack_document(self) -> Dict[str, Any]:
        return self.pack.model_dump(mode="json")


def convert(format_name: str, data: bytes, *, preview: bool = True) -> ConversionOutcome:
    name = (format_name or "").strip().lower()
    if name in DEFERRED_FORMATS:
        raise ConversionRefused(RefusalCode.DEFERRED_FORMAT, f"{name}: {DEFERRED_REASON}")
    if name not in IMPLEMENTED_FORMATS:
        raise ConversionRefused(RefusalCode.UNSUPPORTED_FORMAT,
                                f"{name!r} is not a converter of this build; implemented: {', '.join(IMPLEMENTED_FORMATS)}; next: {NEXT_FORMAT}")
    pack, report, connections = convert_n8n_export(data)
    preview_doc = build_preview(pack, report) if preview else None
    sealed = report.model_copy(update={"preview": summarize_preview(preview_doc)}).sealed()
    return ConversionOutcome(format=name, pack=pack, report=sealed, preview=preview_doc, connections=tuple(connections))


def write_outputs(outcome: ConversionOutcome, out_dir: str) -> List[str]:
    """Write the pack, the report and (if any) the preview under ``out_dir``; return the paths."""
    root = pathlib.Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    documents = [
        (OUTPUT_FILES["pack"], outcome.pack_document),
        (OUTPUT_FILES["report"], outcome.report.as_document()),
    ]
    if outcome.preview is not None:
        documents.append((OUTPUT_FILES["preview"], outcome.preview))
    for filename, document in documents:
        path = root / filename
        path.write_text(canonical_json.dumps_pretty(document) + "\n", encoding="utf-8")
        written.append(os.fspath(path))
    return written
