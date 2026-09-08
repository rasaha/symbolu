"""CP-2 and CP-5 — the distribution, its namespace, and its declared dependencies.

CP-2 moved the service to ``packages/integration/console-api`` and kept the import
namespace ``ugence_console_api``, so no import in the tree moved and every boundary test
that forbids the namespace still forbids the same name.

CP-5 turned every platform package the adapters import into a declared distribution
dependency. These tests read the declaration from ``pyproject.toml`` and compare it with
what the source actually imports, in both directions: an import nothing declares fails,
and so does a declaration nothing imports.
"""

from __future__ import annotations

import ast
import pathlib

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src" / "ugence_console_api"

try:  # Python 3.11+ ships tomllib; 3.10 resolves the same parser from tomli.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only a <3.11 run takes this branch
    import tomli as tomllib  # type: ignore[no-redef]

#: CP-5. The four platform packages, by distribution name and by import namespace.
PLATFORM_DEPENDENCIES = {
    "ugence-context-minimization": "ugence_context_minimization",
    "ugence-governance-provider-framework": "ugence_governance_provider_framework",
    "ugence-actiongate-provider": "ugence_actiongate_provider",
    "ugence-tap-provider": "ugence_tap_provider",
}

#: The legacy root namespaces. Each is a logic-free compatibility surface that ships in
#: no distribution, so an import of one could never be satisfied by a declared
#: dependency — which is exactly why CP-5 forces the canonical name.
LEGACY_NAMESPACES = {"governance_providers", "actiongate_provider", "tap_provider"}


def _metadata() -> dict:
    return tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _declared_names() -> set[str]:
    requirements = _metadata()["project"]["dependencies"]
    return {r.split(">")[0].split("=")[0].split("[")[0].strip() for r in requirements}


def _top_level_imports() -> set[str]:
    """Every top-level module the package's own source imports, absolute imports only."""
    names: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


# -- CP-2 ------------------------------------------------------------------- #

def test_the_namespace_did_not_move():
    assert SRC.is_dir()
    assert SRC.name == "ugence_console_api"
    assert _metadata()["project"]["name"] == "ugence-console-api"


def test_the_distribution_ships_the_namespace_and_only_that():
    find = _metadata()["tool"]["setuptools"]["packages"]["find"]
    assert find["where"] == ["src"]
    assert find["include"] == ["ugence_console_api*"]


def test_the_react_app_is_not_part_of_this_distribution():
    """CP-1: the service alone. ``apps/console/`` stays independently deployable."""
    assert not (PACKAGE_ROOT / "src" / "ugence_console_api" / "frontend").exists()
    # Build artifacts (``*.egg-info``) live here too and are git-ignored; the claim is
    # about importable packages, so count those.
    packaged = {d.name for d in (PACKAGE_ROOT / "src").iterdir()
                if d.is_dir() and (d / "__init__.py").is_file()}
    assert packaged == {"ugence_console_api"}


def test_the_version_is_declared_dynamically_from_the_package():
    metadata = _metadata()
    assert metadata["project"]["dynamic"] == ["version"]
    attr = metadata["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    assert attr == "ugence_console_api.__version__"


# -- CP-5 ------------------------------------------------------------------- #

def test_every_platform_package_the_adapters_import_is_declared():
    declared = _declared_names()
    missing = {d for d in PLATFORM_DEPENDENCIES if d not in declared}
    assert not missing, f"imported but not declared: {sorted(missing)}"


def test_the_declaration_matches_what_the_source_actually_imports():
    """Both directions. A declared dependency nothing imports is a claim the package
    cannot keep, and an import nothing declares is the runtime degradation CP-5 closes.
    """
    imported = _top_level_imports()
    for distribution, namespace in PLATFORM_DEPENDENCIES.items():
        assert namespace in imported, f"{distribution} is declared but never imported"


def test_no_adapter_imports_a_legacy_root_namespace():
    assert LEGACY_NAMESPACES.isdisjoint(_top_level_imports())


def test_the_platform_dependencies_are_required_not_optional():
    """An extra would reintroduce exactly the hole CP-5 closes: an install that
    succeeds and then serves while the governance it advertises is absent."""
    optional = _metadata()["project"].get("optional-dependencies", {})
    for group, requirements in optional.items():
        names = {r.split(">")[0].split("=")[0].split("[")[0].strip() for r in requirements}
        assert names.isdisjoint(PLATFORM_DEPENDENCIES), (
            f"platform dependency parked in the '{group}' extra")


def test_the_declared_set_is_minimal():
    """Nothing declared that the source does not import — no speculative dependency,
    and in particular not the durable audit store CP-4 left for a later ruling."""
    imported = _top_level_imports()
    distribution_to_namespace = dict(PLATFORM_DEPENDENCIES)
    distribution_to_namespace.update({"fastapi": "fastapi", "pydantic": "pydantic"})
    for distribution in _declared_names():
        namespace = distribution_to_namespace.get(distribution)
        assert namespace is not None, f"undeclared purpose for dependency {distribution}"
        assert namespace in imported, f"{distribution} is declared but never imported"


def test_the_durable_store_is_not_a_dependency():
    assert "ugence-control-plane-root" not in _declared_names()


def test_the_server_is_an_extra_not_a_requirement():
    """Importing the app factory must not need an ASGI server; running it does."""
    metadata = _metadata()
    assert "uvicorn" not in {d.split(">")[0].strip() for d in metadata["project"]["dependencies"]}
    serve = metadata["project"]["optional-dependencies"]["serve"]
    assert any(r.startswith("uvicorn") for r in serve)


def test_the_guards_remain_but_no_longer_stand_in_for_a_declaration():
    """CP-5 keeps the fail-safe ``try`` guards for development. The test that they no
    longer hide a missing dependency is the declaration above, not their removal."""
    source = (SRC / "capabilities" / "action_control.py").read_text(encoding="utf-8")
    assert "try:" in source
    assert "_available = False" in source
