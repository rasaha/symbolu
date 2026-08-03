"""Compiled-package file I/O.

Writes a :class:`CompiledReleasePackage` to a directory as canonical JSON files and
reads it back. File content is reproducible (canonical key ordering); the logical
digest is recomputed from content, never from filesystem metadata.
"""

from __future__ import annotations

import pathlib
from typing import Union

from ..compiler.release import PACKAGE_FILES, CompiledReleasePackage
from . import canonical_json

PathLike = Union[str, pathlib.Path]


def _write(path: pathlib.Path, value) -> None:
    path.write_text(canonical_json.dumps_pretty(value), encoding="utf-8")


def write_package(package: CompiledReleasePackage, directory: PathLike) -> pathlib.Path:
    """Write ``package`` as canonical JSON files under ``directory``."""
    out = pathlib.Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "manifest.json", package.manifest)
    _write(out / "policy_pack.json", package.policy_pack)
    _write(out / "workflow_ir.json", package.workflow_ir)
    _write(out / "capability_manifest.json", package.capability_manifest)
    _write(out / "assurance_manifest.json", package.assurance_manifest)
    _write(out / "coverage_matrix.json", package.coverage_matrix)
    _write(out / "audit_schema.json", package.audit_schema)
    _write(
        out / "approval_record.json",
        package.approval_record if package.approval_record is not None else {},
    )
    _write(out / "validation_report.json", package.validation_report)
    _write(
        out / "structural_digest.json",
        {
            "structural_digest": package.structural_digest,
            "release_metadata": package.release_metadata,
        },
    )
    return out


def read_manifest(directory: PathLike) -> dict:
    """Read a package's manifest.json as a dict."""
    path = pathlib.Path(directory) / "manifest.json"
    return canonical_json.loads(path.read_text(encoding="utf-8"))


def read_package_files(directory: PathLike) -> dict:
    """Read every package file into a dict keyed by file name."""
    base = pathlib.Path(directory)
    out = {}
    for name in PACKAGE_FILES:
        path = base / name
        if path.exists():
            out[name] = canonical_json.loads(path.read_text(encoding="utf-8"))
    return out
