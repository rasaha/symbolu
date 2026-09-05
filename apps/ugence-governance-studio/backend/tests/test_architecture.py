"""Architecture boundary tests (§4, §28).

Assert the API is a thin orchestration layer: it imports only the PUBLIC AWC
surface, duplicates no planning logic, imports no runtime/product package, and
ships no frontend or database dependency.
"""
from __future__ import annotations

import os

import ugence_governance_studio_api as pkg

_ROOT = os.path.dirname(pkg.__file__)

# Prohibited imports (§4). Private submodules of every allowlisted package, plus
# database drivers and frontend packages, stay prohibited under owner ruling SD-1
# (``EXPLICIT_PUBLIC_ALLOWLIST``): the boundary widens ONLY through the public
# entry points enumerated in ``_PUBLIC_ENTRY_ALLOWLIST`` below, and this test is
# retained rather than weakened.
_PROHIBITED_IMPORTS = (
    # AWC private submodules.
    "from ugence_agent_workforce_composer.eligibility",
    "from ugence_agent_workforce_composer.ranking",
    "from ugence_agent_workforce_composer.composition import",
    "from ugence_agent_workforce_composer.permissions",
    "from ugence_agent_workforce_composer.fallback",
    "from ugence_agent_workforce_composer.plan import",
    # Compiler private submodules (the public entry points are allowlisted below).
    "from ugence_policy_workflow_compiler.compiler.",
    "from ugence_policy_workflow_compiler.validation",
    "from ugence_policy_workflow_compiler.models.",
    # Agent Runtime private submodules (only the curated ``api`` surface is allowed).
    "from ugence_agent_runtime.runtime",
    "from ugence_agent_runtime.providers",
    "from ugence_agent_runtime.persistence",
    "from ugence_agent_runtime.orchestration",
    "from ugence_agent_runtime.governance",
    # Policy / Decision Authority private submodules.
    "from ugence_policy_authority.core.issuance",
    "from ugence_policy_authority.core.ed25519",
    "from ugence_decision_authority.decisions.",
    # Still entirely out of scope for the studio.
    "agentic.agentic_framework",
    "model_selection",
    "action_clearance",
    "actiongate",
    "risk_authority",
    "ugence_durable_execution",
    # Database drivers and frontend packages stay prohibited (SD-1, verbatim).
    "import flask", "import django", "import sqlalchemy", "sqlite3",
    "import psycopg", "import pymysql",
    "import react", "next.js",
)

# The only permitted AWC import forms.
_PERMITTED_AWC = (
    "import ugence_agent_workforce_composer.api",
    "from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint",
)

# --------------------------------------------------------------------------- #
# SD-1 — the explicit public-entry-point allowlist
# --------------------------------------------------------------------------- #
# Ruled 2026-09-05: the studio backend boundary widens ONLY through an explicit
# per-package allowlist of public entry points. A package reaches the studio by
# having one documented public surface listed here, or it does not reach the
# studio at all. Every entry corresponds to a line in the screen map of
# ``docs/GOVERNED_AGENT_STUDIO_V1_SCREEN_AUDIT.md``; nothing else was added.
_PUBLIC_ENTRY_ALLOWLIST = {
    "ugence_agent_workforce_composer": _PERMITTED_AWC,
    "ugence_policy_workflow_compiler": (
        "from ugence_policy_workflow_compiler import ",
        "import ugence_policy_workflow_compiler",
    ),
    "ugence_agent_constitution_activation": (
        "from ugence_agent_constitution_activation import ",
        "import ugence_agent_constitution_activation",
    ),
    "ugence_agent_constitution_policy": (
        "from ugence_agent_constitution_policy import ",
        "import ugence_agent_constitution_policy",
    ),
    "ugence_policy_authority": (
        "from ugence_policy_authority import ",
        "import ugence_policy_authority",
    ),
    "ugence_decision_authority": (
        "from ugence_decision_authority import ",
        "import ugence_decision_authority",
    ),
    "ugence_agent_runtime": (
        "import ugence_agent_runtime.api",
        "from ugence_agent_runtime.api import ",
    ),
}

# SD-2 — permanently outside the allowlist. These are authority acts, and the
# studio never performs one. Named here so an attempt to add one fails loudly
# rather than passing review as an ordinary import.
_PERMANENTLY_EXCLUDED = (
    "issue_constitution",
    "activate_constitution",
    "issue_policy",
    "revoke_policy",
    "PolicyRevocation",
)


def _py_files():
    for dirpath, _dirs, files in os.walk(_ROOT):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_no_prohibited_imports():
    for path in _py_files():
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        for token in _PROHIBITED_IMPORTS:
            assert token not in text, f"{token!r} in {os.path.basename(path)}"


def test_only_public_awc_import():
    """Every AWC import line is one of the two permitted public forms."""
    for path in _py_files():
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if "ugence_agent_workforce_composer" in stripped and \
                        (stripped.startswith("import ") or stripped.startswith("from ")):
                    assert any(stripped.startswith(p) for p in _PERMITTED_AWC), stripped


_BACKEND_ROOT = os.path.dirname(os.path.dirname(_ROOT))  # .../backend


def test_no_duplicated_planning_logic():
    """Every planning verb in the orchestration service is a delegated public AWC
    call; the service defines no eligibility/ranking/composition/scoring of its own."""
    delegated = ("awc.evaluate_", "awc.rank_", "awc.compose_agent_team",
                 "awc.build_agent_team_plan", "awc.compare_agent_team_plans")
    orch_path = os.path.join(_ROOT, "services", "orchestration.py")
    with open(orch_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert all(token in text for token in delegated)
    # no home-grown scoring arithmetic in the service (delegation only)
    for banned in ("normalized_bp =", "weighted_contribution =", "total_score =",
                   "def _compute_score", "def _rank_candidates"):
        assert banned not in text


def test_no_frontend_or_database_dependency():
    import tomllib
    with open(os.path.join(_BACKEND_ROOT, "pyproject.toml"), "rb") as fh:
        data = tomllib.load(fh)
    deps = " ".join(data["project"]["dependencies"]).lower()
    for banned in ("react", "next", "flask", "django", "sqlalchemy", "psycopg", "pymysql"):
        assert banned not in deps


def test_awc_dependency_declared():
    import tomllib
    with open(os.path.join(_BACKEND_ROOT, "pyproject.toml"), "rb") as fh:
        data = tomllib.load(fh)
    deps = " ".join(data["project"]["dependencies"])
    assert "ugence-agent-workforce-composer" in deps


# --------------------------------------------------------------------------- #
# SD-1 / SD-2 enforcement
# --------------------------------------------------------------------------- #
def _import_lines():
    """Every import statement in the backend source, with its file."""
    for path in _py_files():
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    yield os.path.basename(path), stripped


def test_every_governance_import_is_an_allowlisted_public_entry_point():
    """SD-1: a governance package reaches the studio only through a listed surface.

    This is the widening ruling made testable. Adding a package to the studio now
    means adding one documented public entry point here — not reaching into
    whatever module happens to expose the needed symbol.
    """
    violations = []
    for filename, line in _import_lines():
        for package, permitted in _PUBLIC_ENTRY_ALLOWLIST.items():
            if package not in line:
                continue
            if not any(line.startswith(form) for form in permitted):
                violations.append(f"{filename}: {line}")
    assert violations == [], (
        "imports outside the SD-1 public-entry-point allowlist:\n  "
        + "\n  ".join(violations)
    )


def test_no_package_outside_the_allowlist_is_imported():
    """A Ugence governance package that is not allowlisted must not appear at all."""
    known = set(_PUBLIC_ENTRY_ALLOWLIST)
    violations = []
    for filename, line in _import_lines():
        for token in line.replace(",", " ").split():
            if not token.startswith("ugence_"):
                continue
            root = token.split(".")[0]
            if root.startswith("ugence_governance_studio_api"):
                continue
            if root not in known:
                violations.append(f"{filename}: {line}")
                break
    assert violations == [], (
        "package imported without an SD-1 allowlist entry:\n  " + "\n  ".join(violations)
    )


def test_private_submodules_stay_prohibited_for_allowlisted_packages():
    """SD-1 widened the boundary; it did not open the packages.

    Asserted structurally rather than by the substring list alone: any dotted
    ``from <allowlisted>.<submodule> import`` is a private reach unless the exact
    form is allowlisted (the Agent Runtime ``api`` surface is the only such case).
    """
    violations = []
    for filename, line in _import_lines():
        if not line.startswith("from ugence_"):
            continue
        module = line.split()[1]
        root = module.split(".")[0]
        if root not in _PUBLIC_ENTRY_ALLOWLIST or root == "ugence_governance_studio_api":
            continue
        if "." not in module:
            continue  # top-level public surface
        if any(line.startswith(form) for form in _PUBLIC_ENTRY_ALLOWLIST[root]):
            continue  # an explicitly allowlisted dotted surface
        violations.append(f"{filename}: {line}")
    assert violations == [], (
        "private submodule reach into an allowlisted package:\n  "
        + "\n  ".join(violations)
    )


def _code_without_prose(path: str) -> str:
    """Source with docstrings and comments removed.

    Naming a permanently-excluded entry point while *explaining* why the studio does
    not call it is the opposite of calling it, and a scan that could not tell the
    difference would push the boundary documentation out of the code that implements
    it — which is where it is most useful.
    """
    import ast

    tree = ast.parse(open(path, "r", encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)  # comments are dropped by the parser


def test_authority_acts_are_permanently_excluded():
    """SD-2: the studio never issues, activates, revokes, grants, authorizes,
    clears or executes. The named authority entry points must not be *called*."""
    violations = []
    for path in _py_files():
        code = _code_without_prose(path)
        for symbol in _PERMANENTLY_EXCLUDED:
            if symbol in code:
                violations.append(f"{os.path.basename(path)}: {symbol}")
    assert violations == [], (
        "authority act referenced in the studio backend:\n  " + "\n  ".join(violations)
    )


def test_the_authority_exclusion_scan_catches_a_real_call(tmp_path):
    """A guard that cannot fail is not a guard."""
    offender = tmp_path / "offender.py"
    offender.write_text(
        '"""A docstring mentioning issue_policy must NOT trip this."""\n'
        "def go(registry):\n"
        "    return registry.issue_policy()\n"
    )
    code = _code_without_prose(str(offender))
    assert "issue_policy" in code, "a real call must survive prose stripping"

    innocent = tmp_path / "innocent.py"
    innocent.write_text('"""We never call issue_policy or activate_constitution."""\n')
    assert "issue_policy" not in _code_without_prose(str(innocent))


def test_the_architecture_test_is_retained_not_weakened():
    """SD-1 says the test is retained. Guard against a future edit that keeps the
    file but empties its teeth."""
    assert len(_PROHIBITED_IMPORTS) >= 20
    assert len(_PUBLIC_ENTRY_ALLOWLIST) >= 6
    for banned in ("import flask", "import django", "import sqlalchemy", "sqlite3",
                   "import psycopg", "import pymysql"):
        assert banned in _PROHIBITED_IMPORTS, f"{banned} must stay prohibited"
