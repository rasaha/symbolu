"""The claim "this package cannot call a model vendor", asserted structurally.

A constant saying ``LIVE_VENDOR_EGRESS = False`` is a comment. These tests read
the source tree instead, so the claim fails the moment someone adds an HTTP
client — including in a module nobody remembered to update the constant for.
"""

from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys
import textwrap

import pytest

import ugence_model_egress_unit as meu

SRC = pathlib.Path(meu.__file__).resolve().parent
SOURCES = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _imported_roots(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_source_tree_is_not_empty():
    """Guards every scan below: a glob that matched nothing would pass them all."""

    assert len(SOURCES) >= 8, SOURCES


# --- no vendor egress --------------------------------------------------------

#: Anything that could open a socket, and every vendor SDK this repository knows
#: about. The point is not the list's completeness — it is that adding egress
#: means importing *something*, and the network-capable stdlib names are the
#: chokepoint everything else goes through.
FORBIDDEN_IMPORTS = frozenset({
    "http", "httpx", "requests", "urllib", "urllib3", "socket", "ssl",
    "aiohttp", "websockets", "grpc", "ftplib", "telnetlib", "smtplib",
    "openai", "anthropic", "mistralai", "cohere", "google", "boto3",
    "litellm", "langchain", "transformers", "ollama",
})


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_module_imports_anything_that_could_reach_a_vendor(path):
    offending = _imported_roots(path) & FORBIDDEN_IMPORTS
    assert not offending, (
        f"{path.name} imports {sorted(offending)}. This package's whole posture is "
        f"that it cannot call a model vendor; adding egress is an owner decision "
        f"(OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md, D-2), not a dependency.")


def test_the_declared_posture_matches_the_source():
    assert meu.LIVE_VENDOR_EGRESS is False
    assert meu.ENFORCEMENT_ENABLED is False
    assert meu.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"


def _dotted_names(path: pathlib.Path) -> set:
    """Every ``a.b.c`` and bare name that appears in *code* — never in a docstring.

    The scans below use this rather than substring matching, which would trip on
    a docstring explaining the very rule it enforces (and did, before this).
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts = []
            cursor = node
            while isinstance(cursor, ast.Attribute):
                parts.append(cursor.attr)
                cursor = cursor.value
            if isinstance(cursor, ast.Name):
                parts.append(cursor.id)
                found.add(".".join(reversed(parts)))
        elif isinstance(node, ast.Name):
            found.add(node.id)
    return found


def test_no_module_reads_a_credential_from_the_environment():
    """No key handling anywhere, so there is nothing for a deployment to supply.

    The environment reaches the test suite (which needs a DSN) but never the
    distribution: a package that read a vendor key would be one configuration
    value away from being able to use it.
    """

    for path in SOURCES:
        used = _dotted_names(path)
        offending = {n for n in used
                     if n in {"os.environ", "os.getenv", "getenv", "environ"}}
        assert not offending, (path.name, offending)


# --- the dependency direction ------------------------------------------------

def test_the_only_third_party_dependency_is_the_database_driver():
    """Declared in ``pyproject.toml`` and nowhere contradicted by the source."""

    stdlib_and_self = {
        "__future__", "ast", "dataclasses", "datetime", "enum", "hashlib", "json",
        "pathlib", "typing", "unicodedata", "uuid", "functools", "subprocess",
        "ugence_model_egress_unit",
    }
    third_party = set()
    for path in SOURCES:
        third_party |= _imported_roots(path) - stdlib_and_self
    assert third_party == {"psycopg"}, third_party


def test_only_the_postgres_subpackage_imports_the_driver():
    """No module outside ``postgres/`` names the driver. Necessary, not sufficient —
    see the transitive test below, which is the one that has teeth."""

    for path in SOURCES:
        if "psycopg" in _imported_roots(path):
            assert path.parent.name == "postgres", (
                f"{path.name} imports psycopg outside the postgres subpackage")


def test_the_package_imports_with_no_database_driver_at_all():
    """The claim, tested by removing the driver rather than by reasoning about imports.

    This is the test that was missing, and CI is what found the gap. The scan
    above reads *direct* imports and passed while the real chain —
    ``__init__ → reconcile → postgres.exchange → psycopg`` — was three deep and
    broken. Every test in this suite was green; the CI step that uninstalled
    psycopg and tried to import the package failed on all three Pythons.

    A structural test that reasons about imports is not a substitute for taking
    the dependency away and looking. This runs in a subprocess so the blocked
    import cannot be satisfied by a module the parent already loaded.
    """

    program = textwrap.dedent(
        """
        import sys

        class Block:
            def find_module(self, name, path=None):
                if name == "psycopg" or name.startswith("psycopg."):
                    return self
            def load_module(self, name):
                raise ImportError("No module named %r (blocked)" % name)

        sys.meta_path.insert(0, Block())

        import ugence_model_egress_unit as meu
        assert meu.LIVE_VENDOR_EGRESS is False
        assert meu.DeterministicFakeProvider().maturity == "FIXTURE_ONLY"
        assert meu.RequestNotClaimable is not None
        assert "psycopg" not in sys.modules
        print("OK")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(SRC.parent)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_the_store_still_needs_the_driver():
    """The other half. Without it, a package that had quietly stopped talking to
    PostgreSQL at all would satisfy the test above."""

    program = textwrap.dedent(
        """
        import sys

        class Block:
            def find_module(self, name, path=None):
                if name == "psycopg" or name.startswith("psycopg."):
                    return self
            def load_module(self, name):
                raise ImportError("No module named %r (blocked)" % name)

        sys.meta_path.insert(0, Block())
        try:
            import ugence_model_egress_unit.postgres
        except ImportError:
            print("REFUSED")
        else:
            raise SystemExit("the store imported without a driver")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(SRC.parent)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REFUSED" in result.stdout


def test_the_package_imports_no_first_party_package():
    """It composes a store and a provider and depends on no other Ugence package,
    so it cannot drag the governance kernel into an egress deployment unit."""

    for path in SOURCES:
        first_party = {r for r in _imported_roots(path)
                       if r.startswith("ugence_") or r in {"decision_governance",
                                                           "governance_providers"}}
        assert first_party <= {"ugence_model_egress_unit"}, (path.name, first_party)


# --- determinism -------------------------------------------------------------

def test_nothing_in_the_package_reads_a_wall_clock():
    """Every instant is passed in. A module that called ``now()`` would make the
    reconciler's sweep unreproducible and the digests dependent on when they were
    taken."""

    clocks = {"datetime.now", "datetime.utcnow", "date.today", "datetime.today",
              "time.time", "time.monotonic", "time.time_ns"}
    for path in SOURCES:
        offending = _dotted_names(path) & clocks
        assert not offending, (path.name, offending)


def test_the_wall_clock_scan_can_fail(tmp_path):
    """The scan above proves nothing unless a clock call would actually trip it —
    and its first version did not, because it matched its own docstring."""

    planted = tmp_path / "planted.py"
    planted.write_text("import datetime\nx = datetime.datetime.now()\n")
    assert "datetime.datetime.now" in _dotted_names(planted)

    prose_only = tmp_path / "prose.py"
    prose_only.write_text('"""There is no datetime.now() in this module."""\n')
    assert not (_dotted_names(prose_only) & {"datetime.now"})


def test_the_public_surface_is_explicit():
    assert meu.__all__ == sorted(set(meu.__all__), key=meu.__all__.index)
    for name in meu.__all__:
        assert hasattr(meu, name), name
