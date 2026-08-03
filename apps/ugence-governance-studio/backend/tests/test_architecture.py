"""Architecture boundary tests (§4, §28).

Assert the API is a thin orchestration layer: it imports only the PUBLIC AWC
surface, duplicates no planning logic, imports no runtime/product package, and
ships no frontend or database dependency.
"""
from __future__ import annotations

import os

import ugence_governance_studio_api as pkg

_ROOT = os.path.dirname(pkg.__file__)

# Prohibited imports (§4): private AWC/compiler modules, runtime & product packages.
_PROHIBITED_IMPORTS = (
    "from ugence_agent_workforce_composer.eligibility",
    "from ugence_agent_workforce_composer.ranking",
    "from ugence_agent_workforce_composer.composition import",
    "from ugence_agent_workforce_composer.permissions",
    "from ugence_agent_workforce_composer.fallback",
    "from ugence_agent_workforce_composer.plan import",
    "import ugence_policy_workflow_compiler",
    "agentic.agentic_framework",
    "agent_runtime",
    "model_selection",
    "action_clearance",
    "actiongate",
    "import flask", "import django", "import sqlalchemy", "sqlite3",
    "import react", "next.js",
)

# The only permitted AWC import forms.
_PERMITTED_AWC = (
    "import ugence_agent_workforce_composer.api",
    "from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint",
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
