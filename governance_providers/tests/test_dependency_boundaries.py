"""Phase 5F — governance-provider framework dependency rules (enforced)."""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
KERNEL = REPO / "decision_governance"
FRAMEWORK = REPO / "governance_providers"


def _imports(root: pathlib.Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.lineno, node.module


def test_kernel_never_imports_the_framework():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(KERNEL)
           if m.split(".")[0] == "governance_providers"]
    assert not bad, bad


def test_framework_consumes_only_public_kernel_api():
    bad = []
    for p, ln, m in _imports(FRAMEWORK):
        if m == "decision_governance" or (
                m.startswith("decision_governance.") and not m.startswith("decision_governance.api")):
            bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "framework must use decision_governance.api only:\n" + "\n".join(bad)


def test_framework_never_imports_consuming_layers_or_products():
    forbidden_roots = {"ai_hiring", "domains", "applications"}
    product_terms = re.compile(r"\b(tap|actiongate|action_gate)\b", re.IGNORECASE)
    bad = []
    for p, ln, m in _imports(FRAMEWORK):
        if m.split(".")[0] in forbidden_roots or product_terms.search(m):
            bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, bad


def test_generic_contracts_have_no_domain_terms():
    """The neutral contracts must not encode any domain or product vocabulary."""
    # Domain vocabulary is forbidden in the neutral contracts. Documentation
    # *forward-references* to the future products (TAP / ActionGate) are allowed
    # and expected; product coupling is prevented by the import scan above, not by
    # banning their names from docstrings.
    domain_terms = re.compile(
        r"\b(hiring|candidate|resume|interview|employee|recruiter|applicant|"
        r"procurement|purchase|supplier|budget|invoice)\b", re.IGNORECASE)
    offenders = {}
    for sub in ("contracts", "metadata.py", "registry", "resolution.py"):
        target = FRAMEWORK / sub
        files = target.rglob("*.py") if target.is_dir() else [target]
        for f in files:
            hits = sorted(set(domain_terms.findall(f.read_text())))
            if hits:
                offenders[f.name] = hits
    assert not offenders, offenders


def test_framework_imports_standalone_without_cycles_or_monorepo_paths():
    code = (
        "import sys; "
        "import governance_providers.api, governance_providers.conformance, "
        "governance_providers.reference, governance_providers.adapters; "
        "print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
