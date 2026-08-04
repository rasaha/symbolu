"""Packaging helpers (P3E §6, §19).

Produces the ``frontend-build.json`` marker (version + deterministic build hash) that
the startup integrity gate checks. Used at image-build time and by tests.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import List

from . import FRONTEND_VERSION


def _iter_files(root: str) -> List[str]:
    out: List[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            out.append(os.path.join(dirpath, name))
    return sorted(out)


def frontend_build_hash(frontend_dir: str) -> str:
    h = hashlib.sha256()
    base = os.path.abspath(frontend_dir)
    for path in _iter_files(base):
        rel = os.path.relpath(path, base).replace(os.sep, "/")
        h.update(rel.encode("utf-8") + b"\0")
        with open(path, "rb") as fh:
            h.update(fh.read())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def write_frontend_marker(frontend_dir: str, marker_path: str, *, version: str = FRONTEND_VERSION) -> dict:
    marker = {"version": version, "build_hash": frontend_build_hash(frontend_dir)}
    os.makedirs(os.path.dirname(os.path.abspath(marker_path)), exist_ok=True)
    with open(marker_path, "w", encoding="utf-8") as fh:
        json.dump(marker, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return marker
