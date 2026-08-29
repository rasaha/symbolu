"""The decision classes the guard-coverage ADR added, measured on the engine itself.

Three of the four operators the ADR ratified cannot be checked by running the sweep over
the packages in the tree:

* **D-GC-5 (else-arm)** has exactly one member in the two candidate packages and it lives
  in ``risk-integration``, which this change deliberately does not sweep. An operator with
  no member in any swept package is an operator nothing exercises, so it is exercised here.
* **D-GC-4 (helper-admission)** has 14 members in ``capacity-bounds-policy``, but the
  sweep measures the *suite*, not the mutation: a mutation that silently did nothing would
  report ten survivors just as convincingly as a correct one. These tests assert the
  mutated source.
* **the additive classes must stay off where they are not declared** — guard-coverage ADR
  §1 says nothing in it reclassifies a guard in ``authorization-contracts`` or
  ``policy-authenticity``, and an engine that switched a class on globally would renumber
  both checked-in inventories.

D-GC-6 (``module:Class.method`` mint sites) and D-GC-7 (the recalibrated ``_TYPE_READS``)
are checked against the plugin literal the sweep actually writes, for the same reason the
message-only tests read it rather than transcribing it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SWEEP = REPO / "scripts" / "cloud_scaling" / "guard_sweep.py"

_spec = importlib.util.spec_from_file_location("_guard_sweep_under_test", SWEEP)
guard_sweep = importlib.util.module_from_spec(_spec)
# Registered before execution: ``dataclasses`` resolves a frozen class's annotations
# through ``sys.modules[cls.__module__]``, and a module that is not there yet fails at
# import rather than at first use.
sys.modules[_spec.name] = guard_sweep
_spec.loader.exec_module(guard_sweep)


SYNTHETIC = '''
class Refused(Exception):
    pass


def _require_thing(value):
    if not isinstance(value, str):
        raise Refused("not a string")


def admit(value):
    _require_thing(value)
    bound = _require_thing(value)
    return bound


def dispatch(value):
    if isinstance(value, str):
        return "text"
    elif isinstance(value, int):
        return "number"
    else:
        raise Refused("unsupported type")
'''


def _synthetic_config(tmp_path: Path, monkeypatch, **overrides):
    """A one-module package on disk, so ``inventory()`` reads real source."""

    src = tmp_path / "pkg" / "src" / "synthetic"
    src.mkdir(parents=True)
    (src / "shapes.py").write_text(SYNTHETIC.lstrip("\n"), encoding="utf-8")
    monkeypatch.setattr(guard_sweep, "REPO", tmp_path)
    fields = dict(
        key="synthetic",
        package_dir="pkg",
        dist_name="synthetic",
        mint_site="",
        module_order=("shapes.py",),
        refusal_calls=frozenset(),
        tuple_refusals=False,
        recorded=(),
    )
    fields.update(overrides)
    return guard_sweep.PackageConfig(**fields)


# --- D-GC-4: helper-admission call sites ------------------------------------------


def test_a_statement_level_call_to_a_raising_helper_is_inventoried(tmp_path, monkeypatch):
    config = _synthetic_config(
        tmp_path, monkeypatch, decision_classes=frozenset({"helper-admission"})
    )
    calls = [g for g in guard_sweep.inventory(config) if g.kind == "helper-admission"]
    assert [g.condition for g in calls] == ["_require_thing(value)"], (
        "exactly the unbound call qualifies: the bound one is an Assign, and deleting it "
        "would change what the program computes rather than only what it refuses"
    )


def test_call_deletion_replaces_the_call_and_leaves_the_bound_one_alone(
    tmp_path, monkeypatch
):
    config = _synthetic_config(
        tmp_path, monkeypatch, decision_classes=frozenset({"helper-admission"})
    )
    guard = next(g for g in guard_sweep.inventory(config) if g.kind == "helper-admission")
    guard_sweep.mutate(config, guard, tmp_path / "pkg")
    mutated = (tmp_path / "pkg" / "src" / "synthetic" / "shapes.py").read_text()
    assert "    pass\n    bound = _require_thing(value)" in mutated
    compile(mutated, "shapes.py", "exec")


# --- D-GC-5: else-arm refusals -----------------------------------------------------


def test_a_terminal_else_that_refuses_is_inventoried_and_an_elif_is_not(
    tmp_path, monkeypatch
):
    config = _synthetic_config(
        tmp_path, monkeypatch, decision_classes=frozenset({"else-arm"})
    )
    arms = [g for g in guard_sweep.inventory(config) if g.kind == "else-arm"]
    assert len(arms) == 1, "the ``elif`` is already inventoried on the ``if`` layer"
    assert arms[0].condition == "else of: isinstance(value, int)"
    assert arms[0].shape == "raise"


def test_the_else_row_points_at_the_else_line_not_its_body(tmp_path, monkeypatch):
    """A row that points at the ``raise`` is a row a reader cannot check against §4.3."""

    config = _synthetic_config(
        tmp_path, monkeypatch, decision_classes=frozenset({"else-arm"})
    )
    arm = next(g for g in guard_sweep.inventory(config) if g.kind == "else-arm")
    line = SYNTHETIC.lstrip("\n").splitlines()[arm.lineno - 1]
    assert line.strip() == "else:"


def test_else_arm_deletion_lets_an_unrecognised_type_fall_through(tmp_path, monkeypatch):
    config = _synthetic_config(
        tmp_path, monkeypatch, decision_classes=frozenset({"else-arm"})
    )
    arm = next(g for g in guard_sweep.inventory(config) if g.kind == "else-arm")
    guard_sweep.mutate(config, arm, tmp_path / "pkg")
    path = tmp_path / "pkg" / "src" / "synthetic" / "shapes.py"
    mutated = path.read_text()
    assert "    else:\n        pass\n" in mutated
    namespace: dict = {}
    exec(compile(mutated, "shapes.py", "exec"), namespace)  # noqa: S102 - our own source
    assert namespace["dispatch"](object()) is None, (
        "the weakening direction is admission: an unrecognised type must now fall through "
        "silently rather than be refused"
    )


# --- the classes stay off where they are not declared -------------------------------


def test_the_additive_classes_are_off_by_default(tmp_path, monkeypatch):
    config = _synthetic_config(tmp_path, monkeypatch)
    assert {g.kind for g in guard_sweep.inventory(config)} == {"if"}


@pytest.mark.parametrize("package", ["authorization-contracts", "policy-authenticity"])
def test_phase_5a_and_5b_declare_no_additive_class(package):
    """Guard-coverage ADR §1, as a check rather than a promise.

    Enabling a class for either package would renumber a checked-in inventory and re-open
    its sweep under a different denominator, which §1 forecloses.
    """

    assert guard_sweep.PACKAGES[package].decision_classes == frozenset()


def test_capacity_bounds_policy_declares_both():
    config = guard_sweep.PACKAGES["capacity-bounds-policy"]
    assert config.decision_classes == frozenset({"helper-admission", "else-arm"})


# --- D-GC-6: mint sites through a class ---------------------------------------------


def _plugin_source() -> str:
    match = re.search(r"_MINT_PLUGIN = '''(.*?)\n'''", SWEEP.read_text(encoding="utf-8"), re.S)
    assert match, "the mint plugin literal is no longer where the tests expect it"
    return match.group(1)


MINT_SHAPES = '''
class Minter:
    def describe(self, value):
        return {"described": value}


def coordinate(value):
    return ("coordinate", value)
'''

MINT_TEST = '''
from _mint_shapes import Minter

def test_it_mints_three_times():
    minter = Minter()
    for value in ("a", "b", "c"):
        assert minter.describe(value)["described"] == value
'''


@pytest.mark.parametrize(
    "site, expected", [("_mint_shapes:Minter.describe", 3), ("_mint_shapes:coordinate", 0)]
)
def test_the_mint_counter_resolves_a_method_and_still_resolves_a_function(
    tmp_path, site, expected
):
    """``module:Class.method`` counts the method; ``module:function`` keeps its meaning.

    The second half is the strict-widening claim: an existing configuration must count
    exactly what it counted before, which for an uncalled function is zero.
    """

    (tmp_path / "_ugence_mint_counter.py").write_text(_plugin_source(), encoding="utf-8")
    (tmp_path / "_mint_shapes.py").write_text(MINT_SHAPES, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_mint.py").write_text(MINT_TEST, encoding="utf-8")
    out = tmp_path / ".ugence-mints"
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
         "-p", "_ugence_mint_counter", "--tb=no"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **os.environ,
            "PYTHONPATH": str(tmp_path),
            "UGENCE_MINT_SITE": site,
            "UGENCE_MINT_OUT": str(out),
        },
    )
    assert out.exists(), "the plugin wrote no report; it did not load"
    assert json.loads(out.read_text(encoding="utf-8"))["mints"] == expected


def test_a_package_that_leaves_a_mint_uncovered_names_it():
    """ADR §5 accepts partial coverage only when the uncovered mint is disclosed."""

    for config in guard_sweep.PACKAGES.values():
        for entry in config.uncovered_mints:
            site, why = entry
            assert site and why.strip(), f"{config.key} discloses an unexplained mint"


# --- D-GC-7: the recalibrated typed-read vocabulary ---------------------------------


def _type_reads() -> re.Pattern:
    match = re.search(r"_TYPE_READS = _re\.compile\(\n(.*?)\n\)\n", _plugin_source(), re.S)
    assert match, "the typed-read vocabulary is no longer a named pattern"
    # Parenthesised: the vocabulary is written as implicitly concatenated literals across
    # lines, and their indentation is a syntax error to ``eval`` on its own.
    literal = "(" + "".join(line.strip() for line in match.group(1).splitlines()) + ")"
    return re.compile(eval(literal))  # noqa: S307 - our own literal


@pytest.mark.parametrize(
    "statement",
    [
        "assert outcome.rejection_reason is AdapterRejectionReason.EXPIRED",
        "assert outcome.abstention_reason == 'no recommendation'",
        "assert outcome.status is AdapterOutcomeStatus.RISK_DECISION",
        "assert error.reason is Reason.FIELD_EMPTY",
        (
            "assert outcome.rejection_reason is X and 'expired' in outcome.detail"
        ),
    ],
)
def test_a_qualified_accessor_reads_the_typed_half(statement):
    """The exact miss D-GC-7 was ruled on: ``\\.reason\\b`` required a literal ``.reason``.

    The last case is the one the ADR reproduces: it asserts the typed reason *and* the
    prose, and the old vocabulary classified it message-only.
    """

    assert _type_reads().search(statement)


@pytest.mark.parametrize(
    "statement",
    [
        "assert 'expired' in str(exc.value)",
        "assert 'expired' in outcome.detail",
        "assert 'expired' in exc.args[0]",
    ],
)
def test_a_message_read_is_still_not_a_typed_read(statement):
    """Recalibration widened the typed half; it must not have swallowed the other one."""

    assert not _type_reads().search(statement)


# --- regressions found by adversarial audit -----------------------------------------

AUDIT_SHAPES = '''
class Refused(Exception):
    pass


class Ledger:
    def append(self, row):
        if row is None:
            raise Refused("no row")


def _require(value):
    if value is None:
        raise Refused("required")


def collect(rows, logger):
    out = []
    _require(rows)
    for r in rows:
        out.append(r)
    logger.append("collected")
    return sum(out)
'''


def test_a_method_call_is_not_a_helper_admission_site(tmp_path, monkeypatch):
    """The audit's false positive: `list.append` scored KILLED as if it were a guard.

    A package defining a raising `Ledger.append` puts the bare name `append` into
    `_raising_helpers`, which keys its fixpoint on `node.name` alone. The selector used to
    fall back to `getattr(func, "attr", None)`, so `out.append(r)` matched. Deleting that
    call changes what the program *computes*, the suite fails, and the engine credits a
    kill the guard never earned — inflating numerator and denominator together, silently,
    because a false-positive row looks exactly like a real one in the inventory.
    """

    src = tmp_path / "pkg" / "src" / "synthetic"
    src.mkdir(parents=True)
    (src / "shapes.py").write_text(AUDIT_SHAPES.lstrip("\n"), encoding="utf-8")
    monkeypatch.setattr(guard_sweep, "REPO", tmp_path)
    config = guard_sweep.PackageConfig(
        key="synthetic",
        package_dir="pkg",
        dist_name="synthetic",
        mint_site="",
        module_order=("shapes.py",),
        refusal_calls=frozenset(),
        tuple_refusals=False,
        recorded=(),
        decision_classes=frozenset({"helper-admission"}),
    )
    admissions = [
        g for g in guard_sweep.inventory(config) if g.kind == "helper-admission"
    ]
    assert [g.condition for g in admissions] == ["_require(rows)"], (
        "only the bare module-level call qualifies; `out.append(r)` and "
        "`logger.append(...)` are method calls on objects this package does not define"
    )


def test_the_raising_set_is_narrowed_to_module_level_functions():
    """`append` stays in the raw raising set; it must not survive the narrowing."""

    import ast as _ast

    src_dir = REPO / "packages" / "integration" / "cloud-scaling-capacity-bounds-policy"
    config = guard_sweep.PACKAGES["capacity-bounds-policy"]
    raw = guard_sweep._raising_helpers(config)
    narrowed = guard_sweep._module_level_raising_helpers(config, raw)
    assert narrowed <= raw
    # Every narrowed name really is a module-level def in this package.
    module_level = set()
    for path in sorted(config.src.glob("*.py")):
        for node in _ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                module_level.add(node.name)
    assert narrowed <= module_level
    assert "__post_init__" in raw and "__post_init__" not in narrowed, (
        "a method that raises stays in the raw set and must not be selectable"
    )
    assert src_dir.is_dir()


@pytest.mark.parametrize("kind", ["staticmethod", "classmethod", "plain"])
def test_the_mint_counter_puts_the_descriptor_back(tmp_path, kind):
    """`getattr` on a class unwraps staticmethod/classmethod; writing back a plain
    function re-introduces an implicit first argument and every call raises TypeError.

    That fails loudly rather than manufacturing a kill — a red baseline voids the sweep —
    but it voids a sweep that should have run, and `adapter.py`'s `_canonical_projection`
    is a staticmethod, so it is the next mint site in the package this was written for.
    """

    decorator = "" if kind == "plain" else f"    @{kind}\n"
    first = {"plain": "self", "classmethod": "cls", "staticmethod": ""}[kind]
    signature = f"({first}, value)" if first else "(value)"
    shapes = f'''
class Minter:
{decorator}    def describe{signature}:
        return {{"described": value}}
'''
    body = '''
from _mint_shapes import Minter

def test_it_mints_three_times():
    minter = Minter()
    for value in ("a", "b", "c"):
        assert minter.describe(value)["described"] == value
'''
    (tmp_path / "_ugence_mint_counter.py").write_text(_plugin_source(), encoding="utf-8")
    (tmp_path / "_mint_shapes.py").write_text(shapes.lstrip("\n"), encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_mint.py").write_text(body, encoding="utf-8")
    out = tmp_path / ".ugence-mints"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
         "-p", "_ugence_mint_counter", "--tb=short"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **os.environ,
            "PYTHONPATH": str(tmp_path),
            "UGENCE_MINT_SITE": "_mint_shapes:Minter.describe",
            "UGENCE_MINT_OUT": str(out),
        },
    )
    assert result.returncode == 0, (
        f"the patched {kind} broke the program under test:\n{result.stdout[-2000:]}"
    )
    assert json.loads(out.read_text(encoding="utf-8"))["mints"] == 3
