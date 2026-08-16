"""No implicit wall clock exists anywhere in the package (§10).

Every instant the authority uses is injected by the caller. This is asserted
structurally over the whole source tree, not merely observed in one code path,
so a future change that reaches for the system clock fails here.
"""

from __future__ import annotations

import ast
import pathlib

import ugence_uvi_policy_authority

PKG_ROOT = pathlib.Path(ugence_uvi_policy_authority.__file__).resolve().parent

BANNED_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
    ("time", "time"),
    ("time", "monotonic"),
    ("time", "time_ns"),
}
BANNED_NAMES = {"now", "utcnow", "monotonic", "perf_counter", "time_ns"}


def _sources():
    return sorted(PKG_ROOT.rglob("*.py"))


def test_no_module_calls_a_system_clock():
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                owner = func.value
                owner_name = owner.id if isinstance(owner, ast.Name) else (
                    owner.attr if isinstance(owner, ast.Attribute) else ""
                )
                if (owner_name, func.attr) in BANNED_CALLS or func.attr in BANNED_NAMES:
                    offenders.append(f"{path.name}: {owner_name}.{func.attr}()")
            elif isinstance(func, ast.Name) and func.id in BANNED_NAMES:
                offenders.append(f"{path.name}: {func.id}()")
    assert not offenders, offenders


def test_the_time_module_is_never_imported():
    for path in _sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(a.name.split(".")[0] == "time" for a in node.names), path
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] != "time", path


def test_the_literal_tokens_are_absent_from_the_source():
    for path in _sources():
        source = path.read_text()
        for banned in ("datetime.now(", "datetime.utcnow(", "time.time(", ".utcnow()"):
            assert banned not in source, (path.name, banned)


def test_every_timestamp_bearing_entry_point_takes_an_explicit_instant():
    import inspect

    from ugence_uvi_policy_authority.api import issue_policy, resolve_policy, revoke_policy

    assert "issued_at" in inspect.signature(issue_policy).parameters
    assert "as_of" in inspect.signature(resolve_policy).parameters
    assert "revoked_at" in inspect.signature(revoke_policy).parameters
    # None of them defaults to anything — the caller must supply the instant.
    for fn, name in (
        (issue_policy, "issued_at"),
        (resolve_policy, "as_of"),
        (revoke_policy, "revoked_at"),
    ):
        assert inspect.signature(fn).parameters[name].default is inspect.Parameter.empty
