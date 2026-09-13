"""The import boundary, the clock-free rule, and the structural inability to classify.

The owner's Stage 1 authorization says the package must remain inert: "no classifier,
routing execution, admission enforcement, memory reader or writer, runtime registration,
or operative policy content." These tests make that mechanical over source, AST and
metadata, so inertness is a property of the package rather than a promise about it.
"""

from __future__ import annotations

import ast
import pathlib
import sys

try:  # Python 3.11+ ships tomllib; 3.10 resolves the same parser from tomli.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only a <3.11 run takes this branch
    import tomli as tomllib  # type: ignore[no-redef]

import ugence_change_effect_records as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_change_effect_records", "ugence_governance_contracts"}

#: Anything a classifier, replay harness, sampler, admission boundary, store or network
#: client would need, and the neighbours whose work this package must not duplicate.
FORBIDDEN = {
    "ugence_governance_provider_framework", "governance_providers",
    "ugence_policy_authority", "ugence_trusted_evidence_authority",
    "ugence_control_plane_root", "ugence_governed_review_service",
    "ugence_tap_provider", "ugence_actiongate_provider",
    "ugence_agent_assurance_evidence", "ugence_ai_system_registry",
    "ugence_data_use_admission", "ugence_execution_reservation",
    "sqlite3", "sqlalchemy", "psycopg", "redis", "pydantic", "requests", "httpx",
    "urllib", "socket", "http", "numpy", "scipy", "pandas", "sklearn",
    "random", "secrets", "time", "threading", "asyncio", "subprocess", "os",
}


def _imported_modules() -> set[str]:
    found: set[str] = set()
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def test_nothing_forbidden_is_imported():
    assert not _imported_modules() & FORBIDDEN


def test_every_import_is_stdlib_or_the_one_declared_first_party_dependency():
    outside = _imported_modules() - STDLIB - ALLOWED_FIRST_PARTY
    assert not outside, outside


def test_the_declared_dependency_set_is_exactly_one_package():
    data = tomllib.loads((DIST / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.8.0"]


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input; a package that reads a clock is not replayable."""

    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for forbidden in ("datetime.now", "datetime.utcnow", "time.time", "date.today"):
            assert forbidden not in text, f"{path.name} reads a clock: {forbidden}"


def test_no_randomness_is_drawn_anywhere():
    """A party that can choose a seed can choose a sample; this package chooses none."""

    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for forbidden in ("random.", "secrets.", "uuid4", "getrandbits"):
            assert forbidden not in text, f"{path.name} draws randomness: {forbidden}"


def test_nothing_here_is_named_as_if_it_classified_or_admitted():
    """A function that sounds like a decision invites being used as one."""

    forbidden_names = (
        "classify", "route", "replay", "project", "recompute", "admit", "enforce",
        "authorize", "resolve_policy", "sample", "draw", "verify_bundle", "derive_bundle",
        "apply", "transition", "register",
    )
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not any(node.name.startswith(f) for f in forbidden_names), (
                    f"{path.name}:{node.name}")


def test_the_package_exposes_no_callable_that_takes_two_records():
    """Cross-record computation is the Stage 2 and Stage 3 boundaries' work, not this.

    Nothing here may accept two records and return a conclusion about them, which is
    what a projection, a verification or a succession check would have to do.
    """

    import inspect

    from ugence_change_effect_records import records as records_module

    record_names = {cls.__name__ for cls in pkg.RECORD_TYPES}
    for name, value in inspect.getmembers(records_module, inspect.isfunction):
        if name.startswith("_"):
            continue
        annotations = [
            str(p.annotation) for p in inspect.signature(value).parameters.values()
        ]
        hits = [a for a in annotations if any(r in a for r in record_names)]
        assert len(hits) < 2, f"{name} takes {len(hits)} records"


def test_the_maturity_posture_is_stated_and_enforcement_is_off():
    assert pkg.MATURITY == "REFERENCE_GRADE_CONTRACT_ONLY"
    assert pkg.ENFORCEMENT_ENABLED is False
    assert "4.2.10" in pkg.RULE_VERSION


def test_the_readme_states_what_the_package_never_does_in_its_first_lines():
    head = (DIST / "README.md").read_text(encoding="utf-8")[:1200].upper()
    assert "NEVER" in head
    for word in ("CLASSIF", "ADMIT", "REGISTER"):
        assert word in head, word
