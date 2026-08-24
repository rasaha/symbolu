"""The package defines no local JSON-canonicalization function.

Owner decision D2: the only permitted implementation of proposal identity is a call
into ``ugence_jcs``. A second canonicalizer — even a "temporary" helper, a fallback
behind a flag, or a test fixture — would create a competing exact-identity substrate,
which is precisely what D2 forbids. So this scans ``src`` and ``tests`` alike — a
canonicalizer parked in a test fixture is still a second canonicalizer.

Two files are outside that scan, and neither is a hole:

* this guard module, which necessarily names every pattern it hunts for;
* ``verify_agentic_proposer_distribution.py``, packaging tooling that hashes built
  wheel and sdist FILES to report artifact identity and build reproducibility. It
  runs at build time, ships in no wheel, and canonicalizes no proposal. The test
  below pins that exemption to that one filename so it cannot widen.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
SELF = pathlib.Path(__file__).resolve()
#: Build-time packaging tooling that hashes artifact files, not proposals.
VERIFIER = PKG_ROOT / "verify_agentic_proposer_distribution.py"
#: The directories that carry the capability. Everything in them is scanned.
SCANNED_TREES = (PKG_ROOT / "src", PKG_ROOT / "tests")

#: Names that would signal a canonicalizer or an identity digest defined here.
SUSPECT_DEF_SUBSTRINGS = (
    "canonical", "canonicalize", "canon", "jcs", "rfc8785", "normalize_json",
    "serialize_stable", "stable_json", "fingerprint", "digest", "proposal_id",
)

#: Source text that would signal canonicalization or hashing, wherever it appears.
SUSPECT_TEXT = (
    "sort_keys", "rfc8785", "RFC 8785", "separators=(", "utf-16-be",
    "hashlib", "sha256", "sha3_", "blake2",
)

#: Modules whose presence would mean identity is being computed locally.
FORBIDDEN_IMPORTS = {"hashlib", "hmac", "binascii", "struct"}


def _package_files():
    for tree in SCANNED_TREES:
        for path in sorted(tree.rglob("*.py")):
            if path.resolve() in (SELF, VERIFIER.resolve()):
                continue
            if any(part in {"build", "dist", ".venv", "__pycache__"} for part in path.parts):
                continue
            yield path


def test_package_has_files_to_scan():
    assert list(_package_files())


@pytest.mark.parametrize("path", list(_package_files()), ids=lambda p: p.name)
def test_no_canonicalization_or_digest_function_is_defined(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            lowered = node.name.lower()
            for suspect in SUSPECT_DEF_SUBSTRINGS:
                if suspect in lowered:
                    offenders.append(node.name)
    assert not offenders, f"{path.name} defines {offenders}"


@pytest.mark.parametrize("path", list(_package_files()), ids=lambda p: p.name)
def test_no_canonicalization_or_hashing_source_text(path):
    body = path.read_text(encoding="utf-8")
    found = [s for s in SUSPECT_TEXT if s in body]
    assert not found, f"{path.name} contains {found}"


@pytest.mark.parametrize("path", list(_package_files()), ids=lambda p: p.name)
def test_no_hashing_module_is_imported(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [a.name for a in node.names
                          if a.name.split(".")[0] in FORBIDDEN_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                offenders.append(node.module)
    assert not offenders, f"{path.name} imports {offenders}"


def test_json_is_not_used_to_canonicalize():
    """``json.dumps`` with ordering or separator control is a canonicalizer."""
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name not in ("dumps", "dump"):
                continue
            kwargs = {kw.arg for kw in node.keywords}
            assert not (kwargs & {"sort_keys", "separators", "ensure_ascii"}), \
                f"{path.name} calls json.{name} with canonicalization arguments"


def test_scan_covers_both_src_and_tests():
    """The scan is only meaningful if it actually reaches both trees."""
    scanned = {p.parent.name for p in _package_files()}
    assert "ugence_agentic_proposer" in scanned and "tests" in scanned


def test_the_only_exempt_file_is_the_packaging_verifier():
    """The exemption is one named build-time script, and it ships in no wheel.

    If the verifier ever grew a canonicalizer it would still be outside the scan, so
    this pins what the exemption covers: it hashes file bytes for artifact identity,
    and it is not part of the distributed package.
    """
    assert VERIFIER.is_file()
    body = VERIFIER.read_text(encoding="utf-8")
    # Hashing in the verifier is over file bytes only.
    assert "_sha256(path: Path)" in body
    assert "path.read_bytes()" in body
    # It is packaging tooling: setuptools ships only src/, so it is not in the wheel.
    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'where = ["src"]' in pyproject


def test_ugence_jcs_is_the_declared_identity_substrate():
    """D2 is recorded in the packaging metadata, not only in prose."""
    pyproject = (PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "ugence-jcs>=0.1.0" in pyproject
