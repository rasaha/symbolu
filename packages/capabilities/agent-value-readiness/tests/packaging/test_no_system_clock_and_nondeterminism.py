"""No hidden input exists anywhere in the package.

Every instant, and every decision, is a function of what the caller supplied.
This is asserted **structurally over the whole source tree**, not merely observed
in one code path, so a future change that reaches for a clock, a random number,
a uuid, the environment or the network fails here rather than in production.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import ugence_agent_value_readiness

PKG_ROOT = pathlib.Path(ugence_agent_value_readiness.__file__).resolve().parent

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
BANNED_MODULES = {
    "time",
    "random",
    "secrets",
    "uuid",
    "os",
    "socket",
    "http",
    "urllib",
    "requests",
    "subprocess",
    "threading",
    "asyncio",
}


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


def test_no_clock_randomness_environment_or_network_module_is_imported():
    offenders = {}
    for path in _sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots = {node.module.split(".")[0]}
            bad = roots & BANNED_MODULES
            if bad:
                offenders.setdefault(str(path.relative_to(PKG_ROOT)), set()).update(bad)
    assert not offenders, offenders


def test_the_literal_clock_tokens_are_absent_from_the_source():
    for path in _sources():
        source = path.read_text()
        for banned in ("datetime.now(", "datetime.utcnow(", "time.time(", ".utcnow()"):
            assert banned not in source, (path.name, banned)


def test_no_module_level_mutable_global_can_carry_state_between_assessments():
    """Module state would make one assessment depend on an earlier one."""

    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if not isinstance(target, ast.Name) or target.id.startswith("__"):
                    continue
                value = node.value
                if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                    offenders.append(f"{path.name}: {target.id}")
                elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                    if value.func.id in {"list", "dict", "set"}:
                        offenders.append(f"{path.name}: {target.id}")
    assert not offenders, offenders


def test_every_time_bearing_entry_point_takes_an_explicit_instant():
    from ugence_agent_value_readiness.api import assess_readiness, evaluate_readiness

    assert "evaluation_time" in inspect.signature(evaluate_readiness).parameters
    assert (
        inspect.signature(evaluate_readiness).parameters["evaluation_time"].default
        is inspect.Parameter.empty
    )
    # The orchestrator takes its instant from the request, which has no default.
    import dataclasses

    from ugence_agent_value_readiness.api import ReadinessAssessmentRequest

    field = {f.name: f for f in dataclasses.fields(ReadinessAssessmentRequest)}[
        "evaluation_time"
    ]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING
    assert "request" in inspect.signature(assess_readiness).parameters


def test_the_orchestration_defaults_are_all_deny():
    """Every injected boundary defaults to ``None``, which denies."""

    from ugence_agent_value_readiness.api import assess_readiness

    parameters = inspect.signature(assess_readiness).parameters
    for name in ("policy_resolver", "gate_verifier", "condition_verifier"):
        assert parameters[name].default is None, name
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY, name
