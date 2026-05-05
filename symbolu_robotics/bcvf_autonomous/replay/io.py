"""JSON I/O helpers for :class:`ReplayBundle`.

Mirrors the strict-validation discipline of
``analysis/io.py``: corrupt artifacts fail loudly at load
time rather than silently producing wrong replays.

The on-disk format is canonical JSON (sorted keys, 2-space
indent, trailing newline) so a snapshot test can pin byte-
equality against ``ReplayBundle.to_dict()``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

from .bundle import ReplayBundle
from .errors import ReplayBundleError


def save_replay_bundle(
    bundle: ReplayBundle,
    path: Union[str, Path],
) -> None:
    """Write a :class:`ReplayBundle` to disk as canonical JSON.

    Sorted keys + 2-space indent + trailing newline so the
    output is diff-friendly and snapshot-stable.
    """
    path = Path(path)
    text = json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def load_replay_bundle(path: Union[str, Path]) -> ReplayBundle:
    """Load a :class:`ReplayBundle` from disk. Strict validation:
    every load failure (missing keys, bad version, malformed
    record) raises :class:`ReplayBundleError`."""
    path = Path(path)
    if not path.exists():
        raise ReplayBundleError(
            f"replay bundle not found at {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReplayBundleError(
            f"replay bundle at {path} is not valid JSON: {exc}"
        ) from exc
    return ReplayBundle.from_dict(payload)


def render_replay_bundle_text(bundle: ReplayBundle) -> str:
    """Same canonical serialisation as :func:`save_replay_bundle`
    but returns the string instead of writing. Used by tests +
    by callers wiring the bundle into other pipelines."""
    return json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
