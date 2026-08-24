"""The package defines no local JSON-canonicalization function.

Owner decision D2: the only permitted implementation of proposal identity is a call
into ``ugence_jcs``. A second canonicalizer — even a "temporary" helper, a fallback
behind a flag, or a test fixture — would create a competing exact-identity substrate,
which is precisely what D2 forbids. So this scans ``src`` and ``tests`` alike — a
canonicalizer parked in a test fixture is still a second canonicalizer.

The scan is a glob over both trees, so a module added later is covered by default;
``test_scan_covers_the_s1_enforcement_modules_by_name`` additionally pins the three
S1 enforcement guards by name, and
``test_every_module_in_the_package_is_scanned_or_named_as_exempt`` closes the
general case, so a file can only be scanned or explicitly exempt.

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

#: Calls INTO the permitted substrate, which the text scan must not mistake for local
#: hashing. D7 requires identity to be produced by ``ugence_jcs.canonical_sha256_hex``;
#: that spelling contains ``sha256``, so without this the rule D7 mandates and the rule
#: D2 enforces would be jointly unsatisfiable. Masked before the scan, longest first,
#: so only these exact spellings are exempt — a bare ``hashlib.sha256`` in the same
#: position still carries ``hashlib`` and an unmasked ``sha256``, and a locally defined
#: ``canonical_*`` is caught by the definition scan regardless.
PERMITTED_SUBSTRATE_CALLS = (
    "ugence_jcs.canonical_sha256_hex",
    "ugence_jcs.canonical_bytes",
    "ugence_jcs.canonical_string",
    "canonical_sha256_hex",
    "canonical_bytes",
    "canonical_string",
)


def _suspect_text(body):
    """Suspect substrings in ``body``, with permitted substrate calls masked out."""
    masked = body
    for call in sorted(PERMITTED_SUBSTRATE_CALLS, key=len, reverse=True):
        masked = masked.replace(call, "<permitted-substrate-call>")
    return [s for s in SUSPECT_TEXT if s in masked]

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


#: Text the scan must flag: identity computed here, however it is spelled.
LOCAL_HASHING_SAMPLES = (
    "import hashlib\nadvisory_digest = hashlib.sha256(payload).hexdigest()\n",
    "from hashlib import sha256\nadvisory_digest = sha256(payload).hexdigest()\n",
    "blob = json.dumps(value, sort_keys=True, separators=(',', ':'))\n",
    "digest = blake2b(payload).hexdigest()\n",
)

#: Text the scan must permit: identity produced by the one permitted substrate.
#: D7 mandates exactly this call, so a scan that flagged it would leave D7 and D2
#: jointly unsatisfiable — no source could both compute identity and pass.
PERMITTED_SUBSTRATE_SAMPLES = (
    "import ugence_jcs\nadvisory_digest = ugence_jcs.canonical_sha256_hex(payload)\n",
    "from ugence_jcs import canonical_sha256_hex\nadvisory_digest = canonical_sha256_hex(payload)\n",
    "import ugence_jcs\nblob = ugence_jcs.canonical_bytes(payload)\n",
)


@pytest.mark.parametrize("sample", LOCAL_HASHING_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_text_scan_flags_local_hashing(sample):
    assert _suspect_text(sample), "the text scan stopped seeing local hashing"


@pytest.mark.parametrize("sample", PERMITTED_SUBSTRATE_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_text_scan_permits_the_declared_substrate(sample):
    assert not _suspect_text(sample), "the permitted substrate call was flagged"


def test_masking_the_substrate_call_does_not_mask_local_hashing():
    """The exemption is the exact call spelling, not the word ``sha256``.

    A module that calls the substrate AND hashes locally is still caught: masking
    removes only the permitted spellings, leaving the local call fully visible.
    """
    both = ("import hashlib\nimport ugence_jcs\n"
            "a = ugence_jcs.canonical_sha256_hex(payload)\n"
            "b = hashlib.sha256(payload).hexdigest()\n")
    assert "hashlib" in _suspect_text(both)
    assert "sha256" in _suspect_text(both)


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
    found = _suspect_text(path.read_text(encoding="utf-8"))
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


#: The modules discharging S1's three [R] enforcement obligations. They are named
#: here, not just swept up by the glob, because each of them reasons about identity
#: fields and about the permitted identity substrate — which is exactly the place a
#: "temporary" helper computing an identity locally would be convenient to write.
#: A module dropping out of the scan must fail here rather than pass quietly.
S1_ENFORCEMENT_MODULES = (
    "test_no_auditor_status_projection.py",
    "test_advisory_contract_shape.py",
    "test_role_projection_bounds.py",
)


def test_scan_covers_the_s1_enforcement_modules_by_name():
    scanned = {p.name for p in _package_files()}
    missing = [m for m in S1_ENFORCEMENT_MODULES if m not in scanned]
    assert not missing, f"outside the scan: {missing}"


def test_every_module_in_the_package_is_scanned_or_named_as_exempt():
    """No third category. A file is scanned, or it is one of the two exemptions."""
    exempt = {SELF.name, VERIFIER.name}
    on_disk = {p.name for tree in SCANNED_TREES for p in tree.rglob("*.py")
               if not any(part in {"build", "dist", ".venv", "__pycache__"}
                          for part in p.parts)}
    on_disk |= {VERIFIER.name}
    unaccounted = on_disk - {p.name for p in _package_files()} - exempt
    assert not unaccounted, f"neither scanned nor exempt: {sorted(unaccounted)}"


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
    assert "ugence-jcs>=0.2.0" in pyproject
