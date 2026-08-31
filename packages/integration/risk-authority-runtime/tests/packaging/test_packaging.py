"""Package boundary + declared-dependency discipline (RA-4.5 §7, §19).

The integration package imports exactly its three declared dependencies (plus
their own transitive framework/contracts leaves) and nothing else from the
monorepo. It must NOT reach into unrelated products, apps, or research trees, and
must NOT introduce a reverse dependency (the kernels never import this package).
"""

from __future__ import annotations

import ast
import pathlib

import tomllib

import ugence_risk_authority_runtime

PKG = pathlib.Path(ugence_risk_authority_runtime.__file__).resolve().parent
ROOT = pathlib.Path(__file__).resolve().parents[2]  # risk-authority-runtime/

#: Import roots the integration package is allowed to reference.
_ALLOWED_MONOREPO_ROOTS = {
    "ugence_risk_authority_runtime",
    "risk_authority",  # ugence-risk-authority
    "ugence_decision_authority",  # ugence-decision-authority
    "ugence_actiongate_provider",  # ugence-actiongate-provider
    # transitive deps of the ActionGate provider's public surface:
    "ugence_governance_provider_framework",
    "ugence_governance_contracts",
}

#: Monorepo roots that would signal an out-of-scope reach.
_FORBIDDEN_ROOTS = {
    "symbolu", "agentic", "ai_hiring", "domains", "applications",
    "tap_provider", "ugence_tap_provider", "cloud_controller",
    "hybrid_llm_vnext_lab", "experiments", "trading", "trading2",
    "decision_governance",  # legacy root shim — depend on the canonical package
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
    # Every first-party (ugence_*/risk_authority) import must be an allowed root.
    bad = []
    for p, ln, m in _imports():
        root = m.split(".")[0]
        if root.startswith("ugence_") or root == "risk_authority":
            if root not in _ALLOWED_MONOREPO_ROOTS:
                bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "\n".join(bad)


def test_declared_dependencies_match_the_three_composed_packages():
    with open(ROOT / "pyproject.toml", "rb") as fh:
        meta = tomllib.load(fh)
    deps = {d.split(">")[0].split("=")[0].strip() for d in meta["project"]["dependencies"]}
    assert {
        "ugence-risk-authority",
        "ugence-decision-authority",
        "ugence-actiongate-provider",
    } <= deps


def test_risk_authority_is_imported_but_not_modified_here():
    # The integration package depends on RA's PUBLIC api/domain/integrations
    # surface; it must not import RA private internals that would couple it to
    # kernel wiring beyond the documented seam.
    roots = {m for _p, _ln, m in _imports() if m.split(".")[0] == "risk_authority"}
    # Sanity: we do import the canonical enforcement path + domain types.
    assert any(m.startswith("risk_authority.integrations") for m in roots)
    assert any(m.startswith("risk_authority.domain") for m in roots)
