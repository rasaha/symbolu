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
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
#: The canonicalizer was extracted to the ``ugence-jcs`` leaf distribution; the
#: clean-room consumes it. Independence is unchanged, so the same forbidden set is
#: applied to that source tree too (see test_extracted_jcs_leaf_is_independent).
JCS_SRC = os.path.join(REPO_ROOT, "packages", "jcs", "src", "ugence_jcs")
#: The single first-party import the clean-room is allowed to make. It is a
#: standard-library-only, authority-neutral canonicalization leaf that carries no
#: reference code; every other absolute import must still be stdlib.
ALLOWED_FIRST_PARTY = {"ugence_jcs"}

# Top-level module names the clean-room must never import.
FORBIDDEN_TOP = {"action_gate_ref", "cer_v0_1", "cer_v0_2", "symbolu_robotics"}
# Any cer_v0_3 sub-package other than the clean-room itself is also off-limits
# (the original-side profiles/producers/acp_db/control_plane are reference impls).
FORBIDDEN_CER_V0_3_SUB = {"profiles", "producers", "acp_db", "control_plane",
                          "envelope", "actuation", "conformance"}

STDLIB = set(getattr(sys, "stdlib_module_names", set()))


def _py_files(tree):
    for root, _dirs, files in os.walk(tree):
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(root, fn)


def _cleanroom_files():
    return _py_files(CLEANROOM)


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
            if top in ALLOWED_FIRST_PARTY:
                continue  # extracted stdlib-only canonicalization leaf
            if top not in STDLIB:
                non_stdlib.append((os.path.basename(path), full))
    # The clean-room records ZERO third-party dependencies (no external JCS lib).
    assert not non_stdlib, f"clean-room used non-stdlib imports: {non_stdlib}"


def test_extracted_jcs_leaf_is_independent():
    """``ugence_jcs`` — the extracted canonicalizer — imports no reference code.

    The clean-room's independence claim now spans two trees, so the forbidden set
    is enforced on both. Without this, permitting ``ugence_jcs`` above would let
    reference code re-enter through the extracted leaf.
    """
    assert os.path.isdir(JCS_SRC), f"extracted JCS leaf not found at {JCS_SRC}"
    offenders = []
    for path in _py_files(JCS_SRC):
        for top, level, full in _imports(path):
            if level > 0:
                continue
            if top in FORBIDDEN_TOP or top == "cer_v0_3":
                offenders.append((path, full))
    assert not offenders, f"ugence_jcs imported reference code: {offenders}"


def test_extracted_jcs_leaf_is_stdlib_only():
    """``ugence_jcs`` records ZERO third-party dependencies (no external JCS lib)."""
    non_stdlib = []
    for path in _py_files(JCS_SRC):
        for top, level, full in _imports(path):
            if level > 0 or not top:
                continue
            if top == "ugence_jcs":
                continue  # own package
            if top not in STDLIB:
                non_stdlib.append((os.path.basename(path), full))
    assert not non_stdlib, f"ugence_jcs used non-stdlib imports: {non_stdlib}"


def test_cleanroom_files_present():
    names = {os.path.basename(p) for p in _cleanroom_files()}
    assert {"canon.py", "digest.py", "cer.py", "profiles.py", "errors.py"} <= names
