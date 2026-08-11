"""Package boundary + declared-dependency discipline (CM-TA1).

The integration package imports EXACTLY its two declared cores and nothing else from
the monorepo. It must NOT reach into unrelated products/apps/research trees, must NOT
introduce a reverse dependency (neither core imports this package), and must NOT pull in
a provider SDK in the base install.
"""

from __future__ import annotations

import ast
import pathlib

import ugence_cm_token_accounting_runtime

PKG = pathlib.Path(ugence_cm_token_accounting_runtime.__file__).resolve().parent
ROOT = pathlib.Path(__file__).resolve().parents[2]  # context-minimization-token-accounting-runtime/

_ALLOWED_MONOREPO_ROOTS = {
    "ugence_cm_token_accounting_runtime",
    "ugence_context_minimization",
    "ugence_agent_runtime",
}

_FORBIDDEN_ROOTS = {
    "symbolu", "agentic", "ai_hiring", "domains", "applications", "experiments",
    "trading", "trading2", "cyber_security", "robotics_reliability_bench",
    "ugence_console_api", "risk_authority", "ugence_risk_authority_runtime",
}

# Provider SDKs / tokenizers that must NEVER appear in the base install.
_FORBIDDEN_THIRD_PARTY = {
    "openai", "anthropic", "google", "genai", "cohere", "mistralai", "tiktoken",
    "transformers", "torch", "tokenizers", "vertexai",
}


def _iter_imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield node.module.split(".")[0]


def test_only_declared_cores_and_no_forbidden_roots():
    for py in PKG.rglob("*.py"):
        for root in _iter_imports(py):
            assert root not in _FORBIDDEN_ROOTS, f"{py.name} reaches forbidden root {root}"
            assert root not in _FORBIDDEN_THIRD_PARTY, f"{py.name} imports provider SDK/tokenizer {root}"


def test_pyproject_declares_only_the_two_cores():
    text = (ROOT / "pyproject.toml").read_text()
    assert "ugence-context-minimization>=0.2.0" in text
    assert "ugence-agent-runtime>=0.7.0" in text
    for bad in _FORBIDDEN_THIRD_PARTY:
        assert bad not in text, f"pyproject declares a provider SDK/tokenizer: {bad}"


def test_cores_do_not_import_this_package():
    """Reverse-dependency guard: neither core references the integration namespace."""
    import ugence_context_minimization
    import ugence_agent_runtime

    for core in (ugence_context_minimization, ugence_agent_runtime):
        core_dir = pathlib.Path(core.__file__).resolve().parent
        for py in core_dir.rglob("*.py"):
            for root in _iter_imports(py):
                assert root != "ugence_cm_token_accounting_runtime", (
                    f"reverse dependency: {py} imports the integration package"
                )


def test_py_typed_shipped():
    assert (PKG / "py.typed").is_file()


def test_public_surface_present():
    import ugence_cm_token_accounting_runtime as itg

    for name in (
        "RuntimeTokenAccountingBridge", "translate_attempt", "MappingUsageNormalizer",
        "settle_budget_from_usage", "settle_budget_from_summary", "BudgetEstimateExceeded",
    ):
        assert hasattr(itg, name), name


def test_version():
    import ugence_cm_token_accounting_runtime as itg

    assert itg.__version__ == "0.1.0"
