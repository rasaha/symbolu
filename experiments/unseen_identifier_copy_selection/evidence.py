"""Evidence and run-manifest emission for the unseen-identifier diagnostic (Decision 7).

Every artifact is written ATOMICALLY (temp file + os.replace), under the explicit output directory
ONLY, with canonical JSON (sorted keys, ASCII, fixed separators). A run directory carries an
INCOMPLETE-RUN marker that is cleared only on success; a non-empty target directory and any overwrite
are refused (fail-closed). This module performs no training, evaluation, or seed consumption — it is
pure file assembly and is exercised only by fixture tests writing to temporary directories.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .manifest import canonical_json

INCOMPLETE_MARKER = ".incomplete"


class EvidenceError(RuntimeError):
    """Raised (fail-closed) on any output-path violation: non-empty dir, overwrite, escape."""


def run_dir(output_dir: str, seed: int, cohort: str) -> str:
    """The frozen per-run directory layout: <output-dir>/<seed>/<cohort>/."""
    return os.path.join(os.path.abspath(output_dir), str(int(seed)), cohort)


def _assert_contained(base: str, target: str) -> None:
    base_abs = os.path.abspath(base)
    target_abs = os.path.abspath(target)
    if os.path.commonpath([base_abs, target_abs]) != base_abs:
        raise EvidenceError(f"refusing to write outside the output directory: {target_abs!r}")


def prepare_run_dir(output_dir: str, seed: int, cohort: str) -> str:
    """Create an empty run directory and drop an incomplete-run marker. Refuses a non-empty dir."""
    path = run_dir(output_dir, seed, cohort)
    if os.path.isdir(path) and os.listdir(path):
        raise EvidenceError(f"refusing to reuse a non-empty run directory: {path!r}")
    os.makedirs(path, exist_ok=True)
    marker = os.path.join(path, INCOMPLETE_MARKER)
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("run in progress; cleared only on successful completion\n")
    return path


def atomic_write_text(directory: str, name: str, text: str, *, overwrite: bool = False) -> str:
    """Atomically write `text` to <directory>/<name>. Refuses to overwrite unless explicitly allowed."""
    target = os.path.join(directory, name)
    _assert_contained(directory, target)
    if os.path.exists(target) and not overwrite:
        raise EvidenceError(f"refusing to overwrite existing artifact: {target!r}")
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return target


def atomic_write_json(directory: str, name: str, obj, *, overwrite: bool = False) -> str:
    """Atomically write `obj` as CANONICAL JSON (sorted keys, ASCII, fixed separators)."""
    return atomic_write_text(directory, name, canonical_json(obj) + "\n", overwrite=overwrite)


def finalize_run_dir(path: str) -> None:
    """Clear the incomplete-run marker, marking the run complete. Idempotent."""
    marker = os.path.join(path, INCOMPLETE_MARKER)
    if os.path.exists(marker):
        os.remove(marker)


def is_incomplete(path: str) -> bool:
    return os.path.exists(os.path.join(path, INCOMPLETE_MARKER))


@dataclass(frozen=True)
class WrittenEvidence:
    run_directory: str
    files: tuple[str, ...]


def write_run_evidence(
    output_dir: str,
    *,
    seed: int,
    cohort: str,
    traces: list[dict],
    manifest: dict,
) -> WrittenEvidence:
    """Write per-example traces and the run manifest atomically, then clear the incomplete marker.

    Not an aggregate-only package: the per-example traces are always emitted alongside the manifest."""
    path = prepare_run_dir(output_dir, seed, cohort)
    written = []
    written.append(atomic_write_json(path, "traces.json", traces))
    written.append(atomic_write_json(path, "manifest.json", manifest))
    finalize_run_dir(path)
    return WrittenEvidence(run_directory=path, files=tuple(written))
