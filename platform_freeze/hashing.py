"""Deterministic tree / suite / snapshot hashing (Task 5/10).

Reproducible SHA-256 hashes over package source trees, conformance suites, and
canonical JSON. Excludes ``__pycache__`` so hashes are stable across runs.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: pathlib.Path) -> str:
    return _sha(path.read_bytes())


def tree_hash(pkg: str, *, include_tests: bool = True) -> str:
    root = REPO / pkg
    entries = []
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        if not include_tests and "tests" in p.parts:
            continue
        entries.append((str(p.relative_to(root)), file_hash(p)))
    payload = json.dumps(entries, sort_keys=True)
    return _sha(payload.encode())


def tree_manifest(pkg: str, *, include_tests: bool = True) -> dict:
    root = REPO / pkg
    files = {}
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        if not include_tests and "tests" in p.parts:
            continue
        files[str(p.relative_to(root))] = file_hash(p)
    return {"package": pkg, "file_count": len(files), "tree_hash": tree_hash(
        pkg, include_tests=include_tests), "files": files}


def conformance_hash(pkg: str) -> str:
    """Hash the conformance suite files that certify a package."""
    root = REPO / pkg / "conformance"
    if not root.exists():
        return ""
    entries = [(str(p.relative_to(root)), file_hash(p))
               for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts]
    return _sha(json.dumps(entries, sort_keys=True).encode())


def canonical_hash(obj) -> str:
    return _sha(json.dumps(obj, sort_keys=True, default=str).encode())
