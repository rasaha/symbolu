"""Kernel dependency rules & import hygiene (canonical package layout).

Enforces the architectural boundaries of the bounded Decision Authority kernel,
now living at ``packages/capabilities/decision-authority/src/ugence_decision_authority``:

* the kernel imports nothing from a consuming layer (``ai_hiring`` / ``domains`` /
  ``applications``);
* the kernel (and its public ``api``) import standalone with ONLY the canonical
  ``src`` on the path — the third-party-consumer condition;
* no circular imports across the kernel's own modules.
"""

from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys

CANON_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
KERNEL_ROOT = CANON_SRC / "ugence_decision_authority"
# The bounded capability must import NO other Ugence capability, provider, product,
# platform service, domain, application, console, or research package (§17).
FORBIDDEN_ROOTS = (
    "ai_hiring", "domains", "applications",
    "governance_providers", "actiongate_provider", "tap_provider",
    "baseline_action_provider", "baseline_assertion_provider",
    "cyber_security", "symbolu_robotics", "agent_runtime_migration", "agentic",
    "model_selection_pilot", "model_selection_experiment",
    "ugence_console_api", "control_plane", "ai_control_plane_v3",
    "cer_v0_1", "cer_v0_2", "cer_v0_3", "symbolu", "ugence_storygraph",
    "enterprise_validation_pilot", "comparative_governance_benchmark",
)
# The ONLY external runtime dependency the kernel is allowed to import.
ALLOWED_THIRD_PARTY = {"pydantic"}


def _env_canonical_only():
    """A subprocess env whose ONLY governance path is the canonical src — so a
    consuming layer is not even importable (strongest isolation)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CANON_SRC)
    return env


def _kernel_modules():
    for p in KERNEL_ROOT.rglob("*.py"):
        if "__pycache__" in p.parts or "tests" in p.parts:
            continue
        yield p


def test_kernel_never_imports_a_consuming_layer():
    violations = []
    for path in _kernel_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets = [node.module]
            for t in targets:
                if t.split(".")[0] in FORBIDDEN_ROOTS:
                    violations.append(f"{path.relative_to(KERNEL_ROOT)}:{node.lineno} -> {t}")
    assert not violations, "kernel imports a consuming layer:\n" + "\n".join(violations)


def test_kernel_imports_standalone_as_a_third_party_package():
    code = (
        "import ugence_decision_authority, ugence_decision_authority.api, "
        "ugence_decision_authority.conformance, ugence_decision_authority.services, "
        "ugence_decision_authority.audit, ugence_decision_authority.policy, sys; "
        "leaked=[m for m in sys.modules "
        "if m.split('.')[0] in ('ai_hiring','domains','applications')]; "
        "assert not leaked, leaked; print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, env=_env_canonical_only())
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_all_kernel_modules_import_without_cycles():
    """Import every kernel module fresh in one interpreter — a cycle would raise."""
    modules = sorted(
        ".".join(p.relative_to(CANON_SRC).with_suffix("").parts)
        for p in _kernel_modules()
    )
    modules = [m for m in modules if not m.endswith("__init__")]
    code = "import importlib, sys\n"
    code += "mods = " + repr(modules) + "\n"
    code += "[importlib.import_module(m) for m in mods]\n"
    code += "print('imported', len(mods))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, env=_env_canonical_only())
    assert result.returncode == 0, result.stderr
    assert "imported" in result.stdout


def test_public_api_is_importable_in_isolation():
    code = (
        "from ugence_decision_authority.api import services, contracts, ports, "
        "repositories, vocabulary, audit, identity, policy, errors, common; "
        "print('api-ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, env=_env_canonical_only())
    assert result.returncode == 0, result.stderr
    assert "api-ok" in result.stdout


def test_kernel_external_imports_are_only_pydantic_and_stdlib():
    """Leafward dependency direction (§17): every external top-level import is
    stdlib, pydantic, or the kernel itself — no other Ugence package, and no
    undeclared third-party dependency."""
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    external = set()
    for path in _kernel_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in ("ugence_decision_authority", "__future__") or n in stdlib:
                    continue
                external.add(n)
    assert external <= ALLOWED_THIRD_PARTY, \
        f"undeclared/forbidden third-party imports: {sorted(external - ALLOWED_THIRD_PARTY)}"
