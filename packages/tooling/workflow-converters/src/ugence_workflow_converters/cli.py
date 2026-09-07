"""Command-line interface.

    ugence-workflow-converters version
    ugence-workflow-converters formats
    ugence-workflow-converters convert n8n <export.json> --out DIR [--no-preview]

Also runnable as ``python -m ugence_workflow_converters``. Offline, deterministic,
credential-free. Exit 0 on a conversion (PARTIAL included: the report says what did
not translate), 2 on a refusal (nothing written), 1 on a usage error.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import asdict
from typing import Optional

from .api import (
    DEFERRED_FORMATS,
    DEFERRED_REASON,
    IMPLEMENTED_FORMATS,
    NEXT_FORMAT,
    ConversionRefused,
    convert,
    version_info,
    write_outputs,
)


def _print(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def cmd_version(_args) -> int:
    _print(asdict(version_info()))
    return 0


def cmd_formats(_args) -> int:
    _print({"implemented": list(IMPLEMENTED_FORMATS), "next": NEXT_FORMAT,
            "deferred": {name: DEFERRED_REASON for name in DEFERRED_FORMATS}})
    return 0


def cmd_convert(args) -> int:
    data = pathlib.Path(args.export).read_bytes()
    try:
        outcome = convert(args.format, data, preview=not args.no_preview)
    except ConversionRefused as exc:
        _print({"refused": True, "code": exc.code.value, "message": exc.message, "written": []})
        return 2
    written = write_outputs(outcome, args.out)
    report = outcome.report
    _print({
        "refused": False,
        "conversion_state": report.conversion_state.value,
        "claim": report.claim,
        "pack_id": report.pack.pack_id,
        "pack_status": report.pack.status,
        "validation_ok": report.validation.ok,
        "mapped": sum(1 for r in report.mapping_table if r.outcome.value == "MAPPED"),
        "unmapped": sum(1 for r in report.mapping_table if r.outcome.value == "UNMAPPED"),
        "unsupported": len(report.unsupported_constructs),
        "semantic_loss_warnings": len(report.semantic_loss_warnings),
        "governance_gaps": len(report.governance_gaps),
        "preview": report.preview.status if report.preview else None,
        "report_digest": report.report_digest,
        "written": written,
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ugence-workflow-converters", description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version").set_defaults(func=cmd_version)
    sub.add_parser("formats").set_defaults(func=cmd_formats)
    conv = sub.add_parser("convert", help="convert one export into a DRAFT pack, a report and a preview IR")
    conv.add_argument("format", help="source format: " + ", ".join(IMPLEMENTED_FORMATS))
    conv.add_argument("export", help="path of the export file (JSON)")
    conv.add_argument("--out", required=True, help="directory to write the three outputs into")
    conv.add_argument("--no-preview", action="store_true", help="write the pack and the report only")
    conv.set_defaults(func=cmd_convert)
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
