"""Clean-room boundary enforcement (deliverable 14).

Statically (AST) proves the clean-room package imports NONE of the reference
implementation and depends only on the Python standard library plus its own
relative modules. If this test fails, the differential-conformance evidence is
void (the "independent" implementation would have leaked reference code).
"""
from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLEANROOM = os.path.normpath(os.path.join(HERE, "..", "cleanroom"))

# Top-level module names the clean-room must never import.
FORBIDDEN_TOP = {"action_gate_ref", "cer_v0_1", "cer_v0_2", "symbolu_robotics"}
# Any cer_v0_3 sub-package other than the clean-room itself is also off-limits
# (the original-side profiles/producers/acp_db/control_plane are reference impls).
FORBIDDEN_CER_V0_3_SUB = {"profiles", "producers", "acp_db", "control_plane",
                          "envelope", "actuation", "conformance"}

STDLIB = set(getattr(sys, "stdlib_module_names", set()))


def _cleanroom_files():
    for root, _dirs, files in os.walk(CLEANROOM):
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(root, fn)


def _imports(path):
    """Yield (module_top, level, full) for each import in the file."""
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], 0, alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".")[0] if mod else ""
            yield top, node.level, mod


def test_no_reference_imports():
    offenders = []
    for path in _cleanroom_files():
        for top, level, full in _imports(path):
            if level > 0:
                continue  # relative import -> within the clean-room package
            if top in FORBIDDEN_TOP:
                offenders.append((path, full))
            if top == "cer_v0_3":
                parts = full.split(".")
                if len(parts) >= 2 and parts[1] in FORBIDDEN_CER_V0_3_SUB:
                    offenders.append((path, full))
    assert not offenders, f"clean-room imported reference code: {offenders}"


def test_only_stdlib_absolute_imports():
    """Every absolute import must be stdlib (records any third-party dependency)."""
    non_stdlib = []
    for path in _cleanroom_files():
        for top, level, full in _imports(path):
            if level > 0 or not top:
                continue
            if top in ("cer_v0_3", "cleanroom"):
                continue  # own package
            if top not in STDLIB:
                non_stdlib.append((os.path.basename(path), full))
    # The clean-room records ZERO third-party dependencies (no external JCS lib).
    assert not non_stdlib, f"clean-room used non-stdlib imports: {non_stdlib}"


def test_cleanroom_files_present():
    names = {os.path.basename(p) for p in _cleanroom_files()}
    assert {"canon.py", "digest.py", "cer.py", "profiles.py", "errors.py"} <= names
