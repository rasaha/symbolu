"""Governance-provider framework dependency rules (enforced) — canonical package.

The rules are unchanged from the pre-migration ``governance_providers`` suite;
only the scan target moves to the canonical source tree
``ugence_governance_provider_framework``. The framework:

* is never imported by the kernel;
* consumes only the public ``decision_governance.api`` facade (kernel-bound
  adapters only);
* never imports a consuming layer or a concrete/product provider;
* keeps the neutral contracts free of domain vocabulary;
* imports standalone (via the canonical namespace and via the legacy shim);
* keeps its CORE importable without Decision Authority.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
import sys

# packages/governance-provider-framework/tests/boundaries -> repo root
REPO = pathlib.Path(__file__).resolve().parents[4]
KERNEL = REPO / "decision_governance"
FRAMEWORK = REPO / "packages" / "governance-provider-framework" / "src" / "ugence_governance_provider_framework"


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
           if m.split(".")[0] in ("governance_providers", "ugence_governance_provider_framework")]
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


def test_framework_core_does_not_import_a_bounded_capability():
    """The framework CORE (everything except the kernel-bound ``adapters``) must not
    import Decision Authority or any bounded capability, so the core installs and
    imports without Decision Authority (GPF3/GPF9/§16)."""
    forbidden = {"decision_governance", "ugence_decision_authority", "tap_provider",
                 "actiongate_provider", "acp", "storygraph", "ugence_storygraph",
                 "agent_runtime_v2", "control_plane", "ai_control_plane_v3"}
    bad = []
    for p, ln, m in _imports(FRAMEWORK):
        if "adapters" in p.parts:
            continue  # adapters are the designed, optional kernel seam
        if m.split(".")[0] in forbidden:
            bad.append(f"{p.relative_to(FRAMEWORK)}:{ln}->{m}")
    assert not bad, "framework core must not import a bounded capability:\n" + "\n".join(bad)


def test_generic_contracts_have_no_domain_terms():
    """The neutral contracts must not encode any domain or product vocabulary."""
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


def _standalone(code: str) -> subprocess.CompletedProcess:
    env_paths = [
        str(REPO / "packages" / "governance-provider-framework" / "src"),
        str(REPO / "packages" / "governance-contracts" / "src"),
        str(REPO / "packages" / "capabilities" / "decision-authority" / "src"),
        str(REPO),
    ]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(env_paths))
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)


def test_canonical_framework_imports_standalone():
    code = (
        "import ugence_governance_provider_framework.api, "
        "ugence_governance_provider_framework.conformance, "
        "ugence_governance_provider_framework.reference, "
        "ugence_governance_provider_framework.adapters; print('ok')"
    )
    result = _standalone(code)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_legacy_namespace_imports_standalone():
    code = (
        "import governance_providers.api, governance_providers.conformance, "
        "governance_providers.reference, governance_providers.adapters; print('ok')"
    )
    result = _standalone(code)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_core_imports_without_decision_authority():
    """The pure core imports even when the Decision Authority kernel facade is
    forced absent — only ``.adapters``/``.api`` need it."""
    code = (
        "import sys\n"
        "sys.modules['decision_governance'] = None  # simulate DA absent\n"
        "import ugence_governance_provider_framework\n"
        "import ugence_governance_provider_framework.registry\n"
        "import ugence_governance_provider_framework.resolution\n"
        "import ugence_governance_provider_framework.configuration\n"
        "import ugence_governance_provider_framework.observability\n"
        "import ugence_governance_provider_framework.fingerprint\n"
        "import ugence_governance_provider_framework.version\n"
        "import ugence_governance_provider_framework.conformance\n"
        "import ugence_governance_provider_framework.reference\n"
        "print('ok')"
    )
    result = _standalone(code)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
