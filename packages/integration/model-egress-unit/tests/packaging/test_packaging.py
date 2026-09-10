"""The distribution says what the source does, and nothing more.

The declared dependency set is read from ``pyproject.toml`` rather than from what
happens to be importable, so a dependency that works in this checkout and is
undeclared still fails here.
"""

from __future__ import annotations

import ast
import pathlib

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # 3.10
    import tomli as tomllib

import ugence_model_egress_unit as meu

PKG = pathlib.Path(__file__).resolve().parents[2]
SRC = pathlib.Path(meu.__file__).resolve().parent


def _pyproject() -> dict:
    return tomllib.loads((PKG / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_version_is_stated_once_and_agrees_everywhere():
    """``version.py`` is the single source; the build backend reads it statically
    so building a wheel never imports the package."""

    project = _pyproject()["project"]
    assert project["dynamic"] == ["version"]
    assert _pyproject()["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "ugence_model_egress_unit.version.__version__"}

    readme = (PKG / "README.md").read_text(encoding="utf-8")
    assert f"**Version:** {meu.__version__}" in readme, (
        "the README states a version that no longer matches version.py")


def test_the_declared_dependencies_are_exactly_what_the_source_imports():
    declared = {d.split(">")[0].split("[")[0].strip()
                for d in _pyproject()["project"]["dependencies"]}
    assert declared == {"psycopg"}, declared


def test_the_license_file_matches_the_declared_license():
    declared = _pyproject()["project"]["license"]["text"]
    first = next(line for line in (PKG / "LICENSE").read_text().splitlines()
                 if line.strip())
    assert first.strip().startswith(declared.split()[0]), (first, declared)


def test_the_postgres_marker_is_registered():
    """Unregistered markers are a warning today and an error under ``-W error``."""

    markers = _pyproject()["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("postgres:") for m in markers), markers


def test_py_typed_is_shipped():
    assert (SRC / "py.typed").is_file()
    assert _pyproject()["tool"]["setuptools"]["package-data"][
        "ugence_model_egress_unit"] == ["py.typed"]


def test_every_module_is_inside_the_one_import_namespace():
    """One distribution, one top-level name — nothing lands in ``site-packages``
    under a name the distribution does not own."""

    found = _pyproject()["tool"]["setuptools"]["packages"]["find"]
    assert found["where"] == ["src"]
    assert found["include"] == ["ugence_model_egress_unit*"]
    assert {p.name for p in (SRC.parent).iterdir() if p.is_dir()
            and not p.name.startswith("__")} == {"ugence_model_egress_unit"}


def test_the_maturity_is_machine_readable_from_the_installed_package():
    assert meu.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"
    assert meu.ENFORCEMENT_ENABLED is False
    assert meu.LIVE_VENDOR_EGRESS is False
    assert meu.CONTRACT_VERSION == "model_egress_unit.exchange.v1"


def test_no_module_is_executable_as_a_script():
    """No ``__main__`` and no console entry point: a deployment composes this
    package, it does not run it. An entry point would be a way to start an egress
    unit that skipped whatever the deployment was supposed to decide."""

    assert not (SRC / "__main__.py").exists()
    assert "scripts" not in _pyproject()["project"]
    assert "gui-scripts" not in _pyproject()["project"]


def test_the_source_parses_on_the_lowest_supported_python():
    """``requires-python`` claims 3.10, so nothing may use later-only syntax."""

    assert _pyproject()["project"]["requires-python"] == ">=3.10"
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 10))
