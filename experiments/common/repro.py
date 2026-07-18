"""Reproducibility metadata capture — no manual bookkeeping.

Every experiment run records git hash, Python/numpy versions, seed, runtime,
configuration, and sha256 of generated outputs, via :func:`collect_metadata`
or the :func:`timed` context.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path


def git_hash() -> str:
    try:
        root = Path(__file__).resolve().parents[2]
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _pkg_version(name: str) -> str:
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", "unknown")
    except Exception:
        return "absent"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_metadata(config: dict | None = None, seed: int | None = None,
                     runtime_s: float | None = None,
                     outputs: dict | None = None) -> dict:
    """Assemble the standard reproducibility record."""
    return {
        "git_hash": git_hash(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": _pkg_version("numpy"),
        "seed": seed,
        "runtime_s": round(runtime_s, 3) if runtime_s is not None else None,
        "config": config or {},
        "output_sha256": outputs or {},
    }


@contextmanager
def timed():
    """``with timed() as t: ...; t['runtime_s']`` after the block."""
    rec: dict = {}
    t0 = time.perf_counter()
    try:
        yield rec
    finally:
        rec["runtime_s"] = time.perf_counter() - t0
