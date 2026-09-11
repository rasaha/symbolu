"""No network, no vendor SDK, no driver, no credential reader; a clock and files only in cli.py and drift.py."""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_model_egress_unit as meu
import ugence_model_egress_provider_openai as adapter
import ugence_model_egress_validation as pkg

SRC = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)

FORBIDDEN_IMPORTS = frozenset({
    "http", "httpx", "requests", "urllib", "urllib3", "socket", "ssl", "asyncio", "aiohttp", "websockets",
    "grpc", "ftplib", "telnetlib", "smtplib", "subprocess", "openai", "anthropic", "google", "boto3",
    "litellm", "langchain", "psycopg", "os",
})
STDLIB_ALLOWED = {"__future__", "argparse", "dataclasses", "datetime", "json", "pathlib", "sys", "typing", "uuid"}
FIRST_PARTY = {"ugence_model_egress_unit", "ugence_model_egress_provider_openai", "ugence_model_egress_validation"}


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append(node.module)
    return out


def _dotted(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts, cur = [], node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                found.add(".".join(reversed(parts)))
        elif isinstance(node, ast.Name):
            found.add(node.id)
    return found


def test_the_source_tree_is_what_the_readme_says():
    assert {p.name for p in SOURCES} == {"__init__.py", "__main__.py", "cli.py", "drift.py", "harness.py",
                                          "report.py", "rows.py", "secret_shapes.py", "version.py"}


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_module_imports_anything_that_could_reach_a_network_or_a_vendor(path):
    roots = {n.split(".")[0] for n in _imports(path)}
    assert not roots & FORBIDDEN_IMPORTS, sorted(roots & FORBIDDEN_IMPORTS)
    assert roots <= STDLIB_ALLOWED | FIRST_PARTY, sorted(roots - STDLIB_ALLOWED - FIRST_PARTY)
    assert not any(n.startswith("ugence_model_egress_unit.postgres") for n in _imports(path)), "the exchange is not this package's"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_clock_and_environment_reads_are_confined(path):
    used = _dotted(path)
    assert not used & {"os.environ", "os.getenv", "getenv", "environ", "input", "eval", "exec", "__import__"}
    clocks = {"datetime.now", "datetime.utcnow", "datetime.datetime.now", "date.today", "time.time", "time.monotonic"}
    if path.name != "cli.py":
        assert not used & clocks, sorted(used & clocks)


def test_neither_the_unit_nor_the_adapter_imports_this_package():
    for root in (pathlib.Path(meu.__file__).parent, pathlib.Path(adapter.__file__).parent):
        for path in root.rglob("*.py"):
            assert not any(n.startswith("ugence_model_egress_validation") for n in _imports(path)), path


def test_the_declared_posture():
    assert pkg.LIVE_VENDOR_EGRESS is False and pkg.ENFORCEMENT_ENABLED is False
    assert pkg.MATURITY == meu.MATURITY == adapter.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"
    assert meu.COMMISSIONING_STATUS == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"


def test_no_module_carries_a_credential_shape():
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for shape in ("sk-proj-", "sk-svcacct-", "AIza", "BEGIN PRIVATE KEY", "ya29."):
            assert shape not in text.replace('"sk-svcacct-"', "").replace('"sk-proj-"', "").replace('"AIza"', "").replace('"ya29."', ""), (path.name, shape)
