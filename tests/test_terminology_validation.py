"""Pytest wrapper for the Ugence Decision Governance terminology validator.

Runs `scripts/validate_terminology.py` over the current architecture documents
and asserts the canonical vocabulary holds. Documentation-only; no runtime code
is exercised.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_terminology.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_terminology", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_terminology_validator_passes():
    mod = _load()
    assert mod.run(REPO_ROOT) == 0, "terminology validation reported violations"


def test_governed_docs_exist():
    mod = _load()
    for rel in mod.GOVERNED_DOCS + mod.AMENDED_DOCS:
        assert (REPO_ROOT / rel).is_file(), f"expected governed/amended doc missing: {rel}"
