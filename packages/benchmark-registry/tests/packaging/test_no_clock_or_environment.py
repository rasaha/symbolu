"""No wall clock, no ambient input, no nondeterminism (ADR §22.9, §22.10).

§22.9: "No wall clock inside canonicalization or evaluation."
§22.10: "Explicit caller-supplied evaluation instant — ``as_of`` / evaluation
time is a parameter, not an ambient read."

Asserted structurally over the whole source tree rather than behaviourally for
one code path, so a new module cannot reintroduce the pattern while every
existing test still passes.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest
import ugence_benchmark_registry
from ugence_benchmark_registry import api

PKG_ROOT = pathlib.Path(ugence_benchmark_registry.__file__).resolve().parent


def _sources():
    return sorted(PKG_ROOT.rglob("*.py"))


#: Every way to read a clock, a random source, an environment or a filesystem.
BANNED_CALLS = {
    "now", "utcnow", "today", "time", "monotonic", "perf_counter",
    "process_time", "time_ns", "gmtime", "localtime", "mktime",
    "random", "randint", "choice", "shuffle", "uuid1", "uuid4", "token_bytes",
    "getenv", "getenviron", "urandom", "gethostname", "getpid",
}

BANNED_MODULES = {
    "random", "secrets", "uuid", "os", "time", "socket", "getpass", "platform",
    "tempfile", "subprocess", "sys",
}


def test_no_module_imports_a_nondeterministic_source():
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
    assert not offenders, {k: sorted(v) for k, v in offenders.items()}


def test_no_module_calls_a_clock_or_a_random_source():
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else None
            )
            if name in BANNED_CALLS:
                offenders.append((path.name, name, node.lineno))
    assert not offenders, offenders


def test_astimezone_is_always_called_with_an_explicit_target():
    """The zero-argument form infers the local zone and is never used."""

    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "astimezone"
            ):
                assert node.args, (path.name, node.lineno)


def test_no_datetime_constructor_defaults_a_value():
    """No module manufactures an instant; every instant arrives from the caller."""

    for path in _sources():
        source = path.read_text(encoding="utf-8")
        for banned in ("datetime.now", "datetime.utcnow", "datetime.today",
                       "date.today", "time.time"):
            assert banned not in source, (path.name, banned)


def test_every_temporal_public_method_takes_the_instant_as_a_parameter():
    """§22.10 — the evaluation instant is a parameter, never an ambient read."""

    temporal = {
        "is_effective_at", "temporal_refusal_at", "structural_refusals_at",
    }
    found = set()
    for name in api.__all__:
        obj = getattr(api, name)
        if not isinstance(obj, type):
            continue
        for attribute in dir(obj):
            if attribute not in temporal:
                continue
            found.add(attribute)
            signature = inspect.signature(getattr(obj, attribute))
            parameters = [p for p in signature.parameters if p != "self"]
            assert parameters == ["instant"], (name, attribute, parameters)
            assert (
                signature.parameters["instant"].default is inspect.Parameter.empty
            ), (name, attribute)
    assert found == temporal, sorted(temporal - found)


def test_the_same_inputs_always_produce_the_same_outputs():
    import _builders as b

    identity = b.identity()
    digests = {identity.canonical_digest() for _ in range(10)}
    assert len(digests) == 1
    refusals = {identity.structural_refusals_at(b.INSIDE) for _ in range(10)}
    assert len(refusals) == 1


def test_no_module_reads_the_filesystem_or_the_network():
    for path in _sources():
        source = path.read_text(encoding="utf-8")
        for banned in ("open(", "Path(", "pathlib", "requests.", "urlopen",
                       "socket."):
            assert banned not in source, (path.name, banned)


@pytest.mark.parametrize("tz", ["UTC", "Pacific/Kiritimati", "Etc/GMT+12"])
def test_the_digest_is_independent_of_the_ambient_timezone(monkeypatch, tz):
    import _builders as b

    monkeypatch.setenv("TZ", tz)
    assert b.identity().canonical_digest() == (
        "f27044eafb0519399d71cac460d8820d5c0748aa8de9083346b394f434d93fd9"
    )
