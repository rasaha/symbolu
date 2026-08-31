"""No wall clock and no ambient environment input anywhere in the package.

ADR §22.9/§22.10: canonicalization and evaluation read no clock, and every
evaluation instant is an explicit caller parameter. §22.2 additionally requires
canonical bytes to be a pure function of the payload, which rules out locale,
timezone-database, environment-variable, filesystem and network input.

These are structural AST scans over the whole source tree, not observations of
one code path, so a future change that reaches for any of them fails here.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import pathlib

import ugence_trusted_evidence_authority

PKG_ROOT = pathlib.Path(ugence_trusted_evidence_authority.__file__).resolve().parent

BANNED_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
    ("time", "time"),
    ("time", "monotonic"),
    ("time", "time_ns"),
}
BANNED_NAMES = {"now", "utcnow", "today", "monotonic", "perf_counter", "time_ns"}

#: Modules that would make output depend on something other than the payload.
BANNED_MODULES = {
    "time", "os", "sys", "random", "secrets", "locale", "gettext", "platform",
    "socket", "subprocess", "pathlib", "shutil", "tempfile", "glob",
    "urllib", "http", "requests", "zoneinfo", "calendar", "uuid", "getpass",
}

BANNED_TOKENS = (
    "datetime.now(",
    "datetime.utcnow(",
    "datetime.today(",
    "time.time(",
    ".utcnow()",
    "os.environ",
    "getenv(",
    "open(",
    "default=str",
    "default=repr",
    "repr(",
)


def _sources():
    return sorted(PKG_ROOT.rglob("*.py"))


def test_no_module_calls_a_system_clock():
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                owner = func.value
                owner_name = (
                    owner.id
                    if isinstance(owner, ast.Name)
                    else (owner.attr if isinstance(owner, ast.Attribute) else "")
                )
                if (owner_name, func.attr) in BANNED_CALLS or func.attr in BANNED_NAMES:
                    offenders.append(f"{path.name}: {owner_name}.{func.attr}()")
            elif isinstance(func, ast.Name) and func.id in BANNED_NAMES:
                offenders.append(f"{path.name}: {func.id}()")
    assert not offenders, offenders


def test_no_nondeterminism_or_environment_module_is_imported():
    offenders = {}
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            bad = roots & BANNED_MODULES
            if bad:
                offenders.setdefault(path.name, set()).update(bad)
    assert not offenders, offenders


def _code_only(path: pathlib.Path) -> str:
    """The module's executable text with comments and string literals removed.

    Scanning raw source would match the module's own prose — the canonicalization
    docstring, for instance, *documents* that it has no ``repr()`` fallback. Only
    real code is checked.
    """

    import io
    import tokenize

    pieces = []
    with io.open(path, "rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            if token.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
                continue
            pieces.append(token.string)
    return " ".join(pieces)


def test_the_banned_literal_tokens_are_absent_from_the_executable_source():
    for path in _sources():
        code = _code_only(path).replace(" ", "")
        for banned in BANNED_TOKENS:
            assert banned.replace(" ", "") not in code, (path.name, banned)


def test_astimezone_is_always_called_with_an_explicit_target():
    """The zero-argument form would infer the machine's local zone."""

    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "astimezone"
            ):
                assert node.args, f"{path.name}: bare astimezone() infers the local zone"


def test_json_dumps_is_never_given_a_permissive_default_hook():
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "dumps"
            ):
                keywords = {kw.arg for kw in node.keywords}
                assert "default" not in keywords, (
                    f"{path.name}: a json default= hook would serialize unknown "
                    "objects instead of failing closed (ADR §22.8)"
                )
                assert "sort_keys" in keywords and "separators" in keywords, path.name


def test_every_instant_bearing_entry_point_takes_an_explicit_instant():
    from ugence_trusted_evidence_authority.api import (
        CanonicalEvidenceIdentity,
        EvidenceVerificationRequest,
    )

    for method in ("is_valid_at", "temporal_refusal_at"):
        signature = inspect.signature(getattr(CanonicalEvidenceIdentity, method))
        parameter = signature.parameters["instant"]
        assert parameter.default is inspect.Parameter.empty, method

    as_of = {f.name: f for f in dataclasses.fields(EvidenceVerificationRequest)}["as_of"]
    assert as_of.default is dataclasses.MISSING
    assert as_of.default_factory is dataclasses.MISSING


def test_canonical_output_does_not_depend_on_the_process_environment():
    """Same payload, twice, with the ambient environment perturbed in between."""

    import os

    from _builders import identity

    ident = identity()
    first = ident.canonical_bytes()
    saved = {k: os.environ.get(k) for k in ("TZ", "LANG", "LC_ALL", "PYTHONHASHSEED")}
    try:
        os.environ["TZ"] = "Asia/Kolkata"
        os.environ["LANG"] = "de_DE.UTF-8"
        os.environ["LC_ALL"] = "de_DE.UTF-8"
        assert ident.canonical_bytes() == first
        assert ident.canonical_digest() == identity().canonical_digest()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
