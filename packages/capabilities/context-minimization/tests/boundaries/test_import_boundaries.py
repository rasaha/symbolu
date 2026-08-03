"""Import-boundary tests (AST-based, not substring) — required scenario 45.

The canonical core is a leaf: standard library + self only. It must import no
ActionGate, product, provider, robotics, experiment, model, or tokenizer package.
Concrete adapters may import the core; the core imports none of them.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_context_minimization

PKG_ROOT = pathlib.Path(ugence_context_minimization.__file__).resolve().parent
SELF = "ugence_context_minimization"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    # ActionGate / governance authority
    "action_gate_ref", "action_gateway", "actiongate_provider", "cyber_security",
    "tap_provider", "decision_governance", "governance_providers",
    "ugence_governance_contracts", "baseline_action_provider",
    "baseline_assertion_provider",
    # products / console / experiments / research
    "ugence_console_api", "experiments", "actiongate_context_ablation",
    "cer_v0_1", "cer_v0_2", "cer_v0_3", "robotics_reliability_bench",
    "symbolu_robotics", "agentic", "agent_runtime_migration", "ai_hiring",
    "domains", "applications", "platform_freeze",
    # models / tokenizers / heavy deps
    "torch", "transformers", "huggingface_hub", "tokenizers", "sentencepiece",
    "numpy", "pandas", "sklearn", "openai", "anthropic", "requests", "pydantic",
    "fastapi",
}


def _import_roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import within the package
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_prohibited_imports():
    offenders: dict[str, list[str]] = {}
    for p in PKG_ROOT.rglob("*.py"):
        bad = _import_roots(p) & PROHIBITED
        if bad:
            offenders[str(p.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_stdlib_and_self():
    allowed = _STDLIB | {SELF, "__future__"}
    strays: dict[str, set[str]] = {}
    for p in PKG_ROOT.rglob("*.py"):
        for r in _import_roots(p):
            if r not in allowed:
                strays.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(r)
    assert not strays, strays
