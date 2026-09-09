"""C5 — the contracts package is a leaf: stdlib + self only.

AST-scans every module in ``ugence_governance_contracts`` and asserts it imports
no capability, product, platform, console, provider-framework, or research
package, and no third-party runtime dependency.

This is also the **cycle proof** for the M-3R.3 assessed-system identity
contract. ``AssessedSystemBinding`` lives here (UVI ADR §20) and is consumed by
``ugence-agent-value-readiness``; the arrow must point one way only. Because
every binding field is a platform-neutral primitive, this leaf needs no UVI
policy shape, readiness enum, indicator type or assessment context to define it,
so ``governance-contracts -> uvi-policy-contracts -> governance-contracts`` is
structurally impossible, not merely avoided by convention.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_governance_contracts

PKG_ROOT = pathlib.Path(ugence_governance_contracts.__file__).resolve().parent
SELF = "ugence_governance_contracts"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    # Higher-level UVI / authority / risk packages. Listing them by name makes
    # the cycle governance-contracts -> uvi-policy-contracts -> governance-contracts
    # (and the readiness equivalent) a test failure rather than an import error.
    "ugence_agent_value_readiness", "ugence_uvi_policy_contracts",
    "ugence_policy_authority", "risk_authority", "ugence_governed_value",
    "governed_value", "ugence_decision_authority", "ugence_risk_authority",
    "governance_providers", "decision_governance", "actiongate_provider",
    "tap_provider", "baseline_action_provider", "baseline_assertion_provider",
    "ai_hiring", "domains", "applications", "ugence_console_api",
    "enterprise_validation_pilot", "comparative_governance_benchmark",
    "provider_heterogeneity_validation", "cer_v0_1", "cer_v0_2", "cer_v0_3",
    "agentic", "agent_runtime_migration", "symbolu_robotics", "experiments",
    "platform_freeze", "pydantic", "numpy", "torch", "pandas", "fastapi",
}


def _roots(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_prohibited_imports():
    offenders = {}
    for p in PKG_ROOT.rglob("*.py"):
        bad = _roots(p) & PROHIBITED
        if bad:
            offenders[str(p.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_stdlib_and_self():
    allowed = _STDLIB | {SELF, "__future__"}
    strays = {}
    for p in PKG_ROOT.rglob("*.py"):
        for r in _roots(p):
            if r not in allowed:
                strays.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(r)
    assert not strays, strays


def test_the_system_manifest_module_imports_no_uvi_authority_or_engine_package():
    """SM-1 (§26.3, ruled 2026-09-09) — asserted by name, not by coincidence.

    The two guards above already ``rglob`` the whole package, so this module is
    covered by them today. That coverage is incidental: it would survive a rename
    or a move that quietly took the manifest out of the scanned tree, and a guard
    that passes because it looked nowhere is the failure mode this repository has
    already been bitten by once. So the ruling's requirement is asserted directly —
    the file must exist, and it must import nothing outside the standard library.

    The placement argument depends on exactly this: ``SystemManifest`` may live in
    the neutral leaf **only because** its workflow and policy bindings are opaque
    ref-and-digest strings. The day one of them becomes a typed ``PolicyReference``,
    this test is what fails.
    """

    module = PKG_ROOT / "contracts" / "system_identity.py"
    assert module.is_file(), "system_identity.py is missing; this check would pass vacuously"

    roots = _roots(module)
    assert not (roots & PROHIBITED), sorted(roots & PROHIBITED)
    assert not (roots - (_STDLIB | {SELF, "__future__"})), sorted(
        roots - (_STDLIB | {SELF, "__future__"})
    )

    # The manifest really is defined here, so the assertions above are about it.
    from ugence_governance_contracts.api import SystemManifest

    assert SystemManifest.__module__.endswith("contracts.system_identity")
