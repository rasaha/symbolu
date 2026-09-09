"""Dependency boundary: stdlib + the two contract leaves + the authority's API.

AST-scans every module and asserts the readiness leaf never imports
``governed-value``, any other capability/product/authority package, or a
third-party runtime dependency (ADR §21).

Trusted orchestration adds exactly one new arrow — ``ugence_policy_authority``
— and it is kept honest here in four ways:

1. only the authority's **public** surface may be imported (never ``.core``,
   never ``.adapters``, never any other private module);
2. only the ``orchestration`` subpackage may import it at all, so the GV-3R-b
   evaluator and the GV-3R-a contracts stay independently usable;
3. the arrow is one-way — the authority imports no readiness module;
4. nothing resembling a permissive verifier ships in the distribution.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_agent_value_readiness

PKG_ROOT = pathlib.Path(ugence_agent_value_readiness.__file__).resolve().parent
SELF = "ugence_agent_value_readiness"
AUTHORITY = "ugence_policy_authority"
DEPS = {"ugence_governance_contracts", "ugence_uvi_policy_contracts"}
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    "governed_value", "ugence_governed_value",
    "governance_providers", "decision_governance", "actiongate_provider",
    "tap_provider", "ai_hiring", "ugence_console_api", "risk_authority",
    "platform_freeze", "pydantic", "numpy", "torch", "pandas", "fastapi",
}

#: The only modules of the shared authority this package may name. Everything
#: else — ``ugence_policy_authority.core.*``, ``.adapters.*`` — is an internal.
AUTHORITY_PUBLIC_MODULES = {AUTHORITY, f"{AUTHORITY}.api"}


def _module_names(path: pathlib.Path) -> set[str]:
    """Every fully-qualified absolute module name imported by ``path``."""

    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                names.add(node.module)
    return names


def _roots(path: pathlib.Path) -> set[str]:
    return {name.split(".")[0] for name in _module_names(path)}


def _sources(root: pathlib.Path = PKG_ROOT):
    return sorted(root.rglob("*.py"))


# --------------------------------------------------------------------------- #
# The merged boundary, unchanged
# --------------------------------------------------------------------------- #
def test_no_prohibited_imports():
    offenders = {}
    for p in _sources():
        bad = _roots(p) & PROHIBITED
        if bad:
            offenders[str(p.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_stdlib_self_contract_leaves_and_the_authority():
    allowed = _STDLIB | {SELF, "__future__", AUTHORITY} | DEPS
    strays = {}
    for p in _sources():
        for r in _roots(p):
            if r not in allowed:
                strays.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(r)
    assert not strays, strays


# --------------------------------------------------------------------------- #
# The new arrow onto the shared Policy Authority
# --------------------------------------------------------------------------- #
def test_only_the_authoritys_public_api_is_imported():
    offenders = {}
    for p in _sources():
        for name in _module_names(p):
            if name.split(".")[0] != AUTHORITY:
                continue
            if name not in AUTHORITY_PUBLIC_MODULES:
                offenders.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(name)
    assert not offenders, offenders


def test_only_the_orchestration_subpackage_may_import_the_authority():
    """The GV-3R-a contracts and the GV-3R-b evaluator stay authority-free."""

    offenders = []
    for p in _sources():
        relative = p.relative_to(PKG_ROOT)
        if AUTHORITY in _roots(p) and relative.parts[0] != "orchestration":
            offenders.append(str(relative))
    assert not offenders, offenders


def test_the_evaluator_and_contract_modules_import_no_authority_module():
    for subpackage in ("contracts", "evaluation"):
        for p in _sources(PKG_ROOT / subpackage):
            assert AUTHORITY not in _roots(p), p


def test_the_authority_never_imports_this_package():
    """The arrow is one-way; a reverse dependency would be a cycle."""

    import ugence_policy_authority

    authority_root = pathlib.Path(ugence_policy_authority.__file__).resolve().parent
    for p in sorted(authority_root.rglob("*.py")):
        assert SELF not in _roots(p), p


def test_the_authority_never_imports_any_engine():
    import ugence_policy_authority

    engines = {SELF, "governed_value", "ugence_governed_value", "risk_authority"}
    authority_root = pathlib.Path(ugence_policy_authority.__file__).resolve().parent
    for p in sorted(authority_root.rglob("*.py")):
        assert not (_roots(p) & engines), p


# --------------------------------------------------------------------------- #
# Nothing permissive ships
# --------------------------------------------------------------------------- #
PERMISSIVE_TOKENS = (
    "allowall",
    "allow_all",
    "acceptall",
    "accept_all",
    "trustall",
    "trust_all",
    "alwaysvalid",
    "always_valid",
    "alwaysverified",
    "always_verified",
    "fakeverifier",
    "fake_verifier",
    "stubverifier",
    "stub_verifier",
    "testverifier",
    "test_verifier",
    "dummyverifier",
    "dummy_verifier",
    "insecure",
    "bypass",
    "skip_verification",
    "disable_verification",
)


def test_no_permissive_verifier_or_resolver_class_is_defined_in_the_package():
    offenders = []
    for p in _sources():
        tree = ast.parse(p.read_text(), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                lowered = node.name.lower().replace("-", "_")
                for token in PERMISSIVE_TOKENS:
                    if token in lowered:
                        offenders.append(f"{p.name}: {node.name}")
    assert not offenders, offenders


def test_the_public_api_exports_no_permissive_implementation():
    """Every exported verifier/resolver is a protocol, a deny-all, or the adapter."""

    from ugence_agent_value_readiness import api

    #: Injection seams — declarations, not implementations.
    protocols = {"ReadinessPolicyResolver", "GateResultVerifier", "ConditionSetVerifier"}
    #: The deny-by-default production defaults.
    deny_all = {
        "DenyAllReadinessPolicyResolver",
        "DenyAllGateResultVerifier",
        "DenyAllConditionSetVerifier",
    }
    #: The one concrete implementation: a forwarder onto the shared authority's
    #: public trusted-resolution service. It resolves nothing itself.
    adapters = {"PolicyAuthorityReadinessPolicyResolver"}

    exported = {name for name in api.__all__ if name.endswith(("Verifier", "Resolver"))}
    assert exported == protocols | deny_all | adapters, sorted(exported)

    # Each seam really is a Protocol — a declaration with no behaviour to trust.
    for name in protocols:
        assert getattr(getattr(api, name), "_is_protocol", False) is True, name


def test_the_deny_all_implementations_actually_deny():
    from ugence_policy_authority.api import PolicyResolutionStatus
    from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyReference

    from ugence_agent_value_readiness.api import (
        DenyAllConditionSetVerifier,
        DenyAllGateResultVerifier,
        DenyAllReadinessPolicyResolver,
    )

    import datetime as _dt
    import hashlib as _hashlib

    reference = PolicyReference(
        policy_id="p",
        policy_family=PolicyFamily.READINESS,
        version="1",
        content_digest=_hashlib.sha256(b"x").hexdigest(),
    )
    resolution = DenyAllReadinessPolicyResolver().resolve_readiness_policy(
        reference=reference,
        expected_tenant_id="",
        as_of=_dt.datetime(2026, 6, 1, tzinfo=_dt.timezone.utc),
    )
    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.policy is None and resolution.record is None

    # The verifiers have no constructor switch that could make them permissive.
    import inspect

    for cls in (DenyAllGateResultVerifier, DenyAllConditionSetVerifier):
        assert list(inspect.signature(cls).parameters) == []
