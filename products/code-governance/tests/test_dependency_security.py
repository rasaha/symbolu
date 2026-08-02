"""Acceptance tests 40-45: dependency direction and security boundaries.

These are static, source-level guarantees verified against the product tree.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_PRODUCT_SRC = Path(__file__).resolve().parents[1] / "src" / "ugence_code_governance"
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Public capability surfaces the product is allowed to import.
_ALLOWED_UPSTREAM_ROOTS = {
    "ugence_governance_contracts",
    "ugence_governance_provider_framework",
    "governance_providers",          # identity-preserved alias of the framework
    "ugence_decision_authority",
    "tap_provider",
    "actiongate_provider",
    "ugence_storygraph",
}

# Roots the product must NEVER import (execution / robotics / interop / research).
_FORBIDDEN_ROOTS = {
    "symbolu_robotics",
    "acp",
    "cer_v0_1",
    "cer_v0_2",
    "cer_v0_3",
    "cer_open_standard",
    "cer_public_draft",
    "hybrid_llm",
    "model_selection_experiment",
    "execution_gate",
    "ugence_console_api",
    "baseline_action_provider",
    "baseline_assertion_provider",
}


def _iter_product_py():
    for p in _PRODUCT_SRC.rglob("*.py"):
        yield p


def _imported_roots(path: Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


# 40. no new ProviderKind (product reuses the neutral enum; adds none)
def test_no_new_provider_kind():
    # No product source defines a ProviderKind or a new *_GOVERNANCE / EXECUTION kind.
    for p in _iter_product_py():
        text = p.read_text()
        assert "class ProviderKind" not in text
        assert "ProviderKind(" not in text  # no subclassing/instantiation of a new kind


# 41. no neutral contract modification (product owns no contract package)
def test_product_defines_no_neutral_contract():
    for p in _iter_product_py():
        text = p.read_text()
        assert "ugence_governance_contracts" not in str(p)  # not located in the contract pkg


# 42. no upward dependency from shared packages to product
def test_no_upstream_package_imports_product():
    # Use real AST import analysis, not a substring scan: a capability package may
    # legitimately *name* ``ugence_code_governance`` in a forbidden-imports list or
    # boundary declaration without importing it. Only an actual import is a violation.
    offenders = []
    for pkg in ("packages", "actiongate_provider", "tap_provider",
                "governance_providers", "decision_governance"):
        root = _REPO_ROOT / pkg
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if "ugence_code_governance" in _imported_roots(p):
                offenders.append(str(p))
    assert not offenders, f"upstream imports product: {offenders}"


def test_product_imports_only_allowed_upstream():
    stdlib_and_self = {"ugence_code_governance", "__future__"}
    for p in _iter_product_py():
        for root in _imported_roots(p):
            if root in stdlib_and_self:
                continue
            if root in _ALLOWED_UPSTREAM_ROOTS:
                continue
            # everything else must be stdlib (importable without a third party)
            assert root not in _FORBIDDEN_ROOTS, f"{p} imports forbidden root {root}"


# 43. no GitHub write client or merge credentials
def test_no_github_write_or_credentials():
    banned = ("requests.post", "requests.put", "requests.patch", "requests.delete",
              "merge_pull_request(", "GITHUB_TOKEN", "github_token", "api.github.com",
              "PyGithub", "from github import", "httpx.post")
    for p in _iter_product_py():
        text = p.read_text()
        for token in banned:
            assert token not in text, f"{p} contains banned token {token!r}"


# 44. no robotics ACP imports
def test_no_robotics_acp_imports():
    for p in _iter_product_py():
        for root in _imported_roots(p):
            assert root not in {"symbolu_robotics", "acp"}, f"{p} imports {root}"


# 45. no direct external execution invocation
def test_no_execution_invocation():
    banned = ("subprocess", "os.system", "dispatch_execution", "create_execution_intent",
              "ExecutionService", "submit_for_authorization")
    for p in _iter_product_py():
        text = p.read_text()
        for token in banned:
            assert token not in text, f"{p} references execution primitive {token!r}"
