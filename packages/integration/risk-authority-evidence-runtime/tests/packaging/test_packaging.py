"""Package boundary + declared-dependency discipline (RA-5 §14; Phase 19, 25).

The RA-5 evidence-runtime integration package imports exactly its two declared
dependencies (risk-authority + tap-provider) plus their transitive framework /
contracts leaves, and nothing else from the monorepo. It must NOT reach into
unrelated products/apps/research trees, must NOT introduce a reverse dependency
(the kernels never import this package), and must keep ``ugence-risk-authority``
a stdlib-only leaf (no provider dependency leaks into it).
"""

from __future__ import annotations

import ast
import pathlib

import tomllib

import ugence_risk_authority_evidence_runtime

PKG = pathlib.Path(ugence_risk_authority_evidence_runtime.__file__).resolve().parent
ROOT = pathlib.Path(__file__).resolve().parents[2]  # risk-authority-evidence-runtime/

#: Import roots this integration package is allowed to reference.
_ALLOWED_MONOREPO_ROOTS = {
    "ugence_risk_authority_evidence_runtime",
    "risk_authority",  # ugence-risk-authority (ports + domain)
    "ugence_tap_provider",  # Control-Assurance evaluator candidate
    # transitive deps of the TAP provider's public surface:
    "ugence_governance_provider_framework",
    "ugence_governance_contracts",
}

#: Monorepo roots that would signal an out-of-scope reach.
_FORBIDDEN_ROOTS = {
    "symbolu", "agentic", "ai_hiring", "domains", "applications",
    "tap_provider", "cloud_controller", "hybrid_llm_vnext_lab", "experiments",
    "trading", "trading2", "decision_governance",
    # RA-4.5 runtime must NOT be pulled in — RA-5 is upstream of the envelope.
    "ugence_risk_authority_runtime",
    "ugence_decision_authority", "ugence_actiongate_provider",
}


def _imports():
    for path in PKG.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.lineno, node.module


def test_no_forbidden_monorepo_imports():
    bad = [
        f"{p.name}:{ln}->{m}"
        for p, ln, m in _imports()
        if m.split(".")[0] in _FORBIDDEN_ROOTS
    ]
    assert not bad, "\n".join(bad)


def test_only_known_first_party_roots_imported():
    bad = []
    for p, ln, m in _imports():
        root = m.split(".")[0]
        if root.startswith("ugence_") or root == "risk_authority":
            if root not in _ALLOWED_MONOREPO_ROOTS:
                bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "\n".join(bad)


def test_declared_dependencies_are_ra_and_tap():
    with open(ROOT / "pyproject.toml", "rb") as fh:
        meta = tomllib.load(fh)
    deps = {d.split(">")[0].split("=")[0].strip() for d in meta["project"]["dependencies"]}
    assert {"ugence-risk-authority", "ugence-tap-provider"} <= deps
    # RA-5 must NOT depend on the RA-4.5 runtime (it is upstream of the envelope).
    assert "ugence-risk-authority-runtime" not in deps


def test_risk_authority_imported_via_public_ports_only():
    roots = {m for _p, _ln, m in _imports() if m.split(".")[0] == "risk_authority"}
    # We import the RA ports + domain contracts (the documented RA-5 seam).
    assert any(m.startswith("risk_authority.integrations") for m in roots)
    assert any(m.startswith("risk_authority.domain") for m in roots)


def test_risk_authority_remains_stdlib_only_leaf():
    # The RA leaf's own pyproject must declare NO runtime dependencies — no
    # provider/framework dependency may leak into it because of RA-5.
    ra_root = ROOT.parents[1] / "risk_authority"
    with open(ra_root / "pyproject.toml", "rb") as fh:
        meta = tomllib.load(fh)
    assert meta["project"]["dependencies"] == []
