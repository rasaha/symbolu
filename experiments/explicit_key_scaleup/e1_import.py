"""Load the frozen E1 module (models.py / engine.py) from experiments/bindingslots_e1 UNCHANGED.

E1's sources do `import task as T` / `from models import ...` as top-level names, so they are loaded
with their own directory at the front of sys.path. Byte identity against the recorded sha256 digests is
asserted on every load: this package never copies or edits E1 code.
"""
from __future__ import annotations

import hashlib
import importlib
import pathlib
import sys

E1_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1"

# sha256 of the E1 sources at ratification (2026-09-04). Any drift => ExplicitKeyProtocolError.
E1_SOURCE_SHA256 = {
    "models.py": "bb30b388baffc6f03b4877efd47a65a3b01826a91d57021b325bdf939bc703c8",
    "task.py": "25471a88b292a5c9f42bee6a732838cbe507097ed5b26f9edfb084da298bd79d",
}


class ExplicitKeyProtocolError(RuntimeError):
    """E1 sources are not byte-identical to the ratified versions (or cannot be loaded)."""


def source_digests() -> dict:
    return {n: hashlib.sha256((E1_DIR / n).read_bytes()).hexdigest() for n in E1_SOURCE_SHA256}


def assert_e1_unchanged() -> None:
    got = source_digests()
    for n, want in E1_SOURCE_SHA256.items():
        if got[n] != want:
            raise ExplicitKeyProtocolError(f"E1 source {n} drifted: {got[n]} != ratified {want}")


def _load(name: str):
    if str(E1_DIR) not in sys.path:
        sys.path.insert(0, str(E1_DIR))
    mod = sys.modules.get(name)
    if mod is not None and not str(getattr(mod, "__file__", "")).startswith(str(E1_DIR)):
        raise ExplicitKeyProtocolError(f"top-level module {name!r} is shadowed by {mod.__file__}")
    mod = importlib.import_module(name)
    if not str(mod.__file__).startswith(str(E1_DIR)):
        raise ExplicitKeyProtocolError(f"{name} resolved outside the E1 directory: {mod.__file__}")
    return mod


def e1_task():
    """E1's frozen task module (torch-free); only PAD/SEP and VOCAB are consulted by this package."""
    assert_e1_unchanged()
    return _load("task")


def e1_models():
    """E1's frozen models module (requires torch): E1 and B0 classes, unchanged."""
    assert_e1_unchanged()
    e1_task()
    return _load("models")


def e1_engine():
    """E1's frozen engine (requires torch): collate / eval_e1 / eval_b0 / param_hash / set_determinism."""
    assert_e1_unchanged()
    e1_models()
    return _load("engine")
