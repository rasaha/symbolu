"""The claim "this distribution cannot reach api.openai.com", asserted structurally.

The same scan the unit runs over itself, plus the one-way dependency: this package
imports the unit's public surface and nothing of its ``postgres`` subpackage; the
unit imports nothing of this package.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_model_egress_unit as meu
import ugence_model_egress_provider_openai as pkg

SRC = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)
MEU_SRC = pathlib.Path(meu.__file__).resolve().parent
MEU_SOURCES = sorted(p for p in MEU_SRC.rglob("*.py") if "__pycache__" not in p.parts)

FORBIDDEN_IMPORTS = frozenset({
    "http", "httpx", "requests", "urllib", "urllib3", "socket", "ssl", "asyncio",
    "aiohttp", "websockets", "grpc", "ftplib", "telnetlib", "smtplib", "subprocess",
    "openai", "anthropic", "mistralai", "cohere", "google", "boto3",
    "litellm", "langchain", "transformers", "ollama", "psycopg", "os", "sys", "time",
})

STDLIB_ALLOWED = {"__future__", "dataclasses", "datetime", "enum", "hashlib", "json", "typing"}


def _imports(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append(node.module)
    return found


def _dotted_names(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts, cursor = [], node
            while isinstance(cursor, ast.Attribute):
                parts.append(cursor.attr)
                cursor = cursor.value
            if isinstance(cursor, ast.Name):
                parts.append(cursor.id)
                found.add(".".join(reversed(parts)))
        elif isinstance(node, ast.Name):
            found.add(node.id)
    return found


def test_the_source_tree_is_not_empty():
    assert {p.name for p in SOURCES} == {"__init__.py", "provider.py", "transport.py", "version.py"}


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_module_imports_anything_that_could_reach_a_vendor(path):
    roots = {name.split(".")[0] for name in _imports(path)}
    assert not roots & FORBIDDEN_IMPORTS, (path.name, sorted(roots & FORBIDDEN_IMPORTS))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_every_import_is_stdlib_on_the_allowlist_or_the_unit_or_this_package(path):
    for name in _imports(path):
        root = name.split(".")[0]
        assert root in STDLIB_ALLOWED | {"ugence_model_egress_unit", "ugence_model_egress_provider_openai"}, (path.name, name)
        assert not name.startswith("ugence_model_egress_unit.postgres"), (
            f"{path.name} reaches into the exchange; the adapter sees only the provider seam")
        assert name != "ugence_model_egress_unit.postgres"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_module_reads_the_environment_a_clock_or_a_file(path):
    used = _dotted_names(path)
    forbidden = {"os.environ", "os.getenv", "getenv", "environ", "open", "datetime.now",
                 "datetime.utcnow", "datetime.datetime.now", "date.today", "time.time",
                 "time.monotonic", "input", "eval", "exec", "__import__"}
    assert not used & forbidden, (path.name, sorted(used & forbidden))


def _unit_declared_requirements() -> list:
    """From the installed distribution's metadata when the unit is installed (CI
    installs it into site-packages), else from the source tree's manifest."""

    import importlib.metadata as metadata
    try:
        return list(metadata.requires("ugence-model-egress-unit") or [])
    except metadata.PackageNotFoundError:
        pyproject = MEU_SRC.parent.parent / "pyproject.toml"
        assert pyproject.exists(), "neither an installed unit nor its source manifest was found"
        return [pyproject.read_text(encoding="utf-8")]


def test_the_unit_never_imports_this_package():
    for path in MEU_SOURCES:
        assert not any(name.startswith("ugence_model_egress_provider_openai") for name in _imports(path)), path
    for requirement in _unit_declared_requirements():
        assert "model-egress-provider-openai" not in requirement.replace("_", "-"), requirement


def test_the_declared_posture_matches_the_source():
    assert pkg.LIVE_VENDOR_EGRESS is False and pkg.ENFORCEMENT_ENABLED is False
    assert pkg.MATURITY == meu.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"
    assert pkg.VENDOR == "openai" and pkg.DESIGNATED_MODEL == "gpt-5.4-mini-2026-03-17"
    assert meu.is_pinned_snapshot(pkg.DESIGNATED_MODEL)
    assert pkg.FakeTransport.NON_PRODUCTION is True
    assert pkg.OpenAIResponsesProvider.NON_PRODUCTION is True


def test_no_module_carries_a_credential_shape():
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for shape in ("sk-", "eyJ", "AIza", "BEGIN PRIVATE KEY", "BEGIN RSA"):
            assert shape not in text, (path.name, shape)
