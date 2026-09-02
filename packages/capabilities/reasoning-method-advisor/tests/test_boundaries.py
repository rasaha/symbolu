"""Boundary test (spec §1, row B): the advisor imports no runtime, no engine,
no capability beyond its declared contract dependencies, and no network or
LLM SDK; and performs no I/O and no clock read at all (advised_at is caller-supplied)."""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[4]
SRC = REPO / "packages" / "capabilities" / "reasoning-method-advisor" / "src" / "ugence_reasoning_method_advisor"

FORBIDDEN = {
    "agentic", "agentic_framework", "reasoning_workflows", "adaptive_prompts", "external_actions", "symbolu",
    "ugence_readiness_comparison", "ugence_agentic_proposer", "ugence_agent_workforce_composer", "ugence_agent_runtime",
    "ugence_agent_value_readiness", "governed_value", "ugence_context_minimization", "ugence_policy_authority",
    "openai", "anthropic", "requests", "httpx", "socket", "urllib", "subprocess", "os", "random", "time",
}
ALLOWED = {"ugence_reasoning_method_governance", "ugence_governance_contracts", "ugence_uvi_policy_contracts", "ugence_jcs",
           "__future__", "dataclasses", "datetime", "decimal", "enum", "re", "typing"}
FORBIDDEN_CALLS = {"open", "input", "print", "exec", "eval", "compile", "__import__"}


def _modules():
    seen = {}
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    seen.setdefault(a.name.split(".")[0], set()).add(path.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                seen.setdefault(node.module.split(".")[0], set()).add(path.name)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, f"{path.name} calls {node.func.id}"
                if node.func.id in ("import_module", "__import__") and node.args and isinstance(node.args[0], ast.Constant):
                    seen.setdefault(str(node.args[0].value).split(".")[0], set()).add(path.name)
    return seen


def test_no_forbidden_import():
    seen = _modules()
    assert not (set(seen) & FORBIDDEN), set(seen) & FORBIDDEN


def test_only_declared_imports():
    seen = _modules()
    assert set(seen) <= ALLOWED, set(seen) - ALLOWED


def test_no_clock_read_anywhere():
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("datetime.now(", "datetime.utcnow(", "date.today(", "time.time(", "monotonic("):
            assert needle not in text, f"{path.name} reads a clock: {needle}"


def test_slice_1_packages_do_not_import_the_advisor():
    for pkg in ("reasoning-method-governance", "readiness-comparison", "agent-value-readiness"):
        src = REPO / "packages" / "capabilities" / pkg / "src"
        for path in src.rglob("*.py"):
            assert "ugence_reasoning_method_advisor" not in path.read_text(encoding="utf-8"), path
