"""H6 — packaging-phase boundary tests.

The product package is a **packaging layer only**: it adds no governance,
decision, authorization, or execution semantics; introduces no new lifecycle
states or authorities; imports no vendor SDK; and drives only the deterministic
in-memory adapters. It reaches the frozen platform exclusively through the
already-validated hiring services and the public provider contracts — never
kernel internals or a production transport.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

PRODUCT_MODULES = [
    "ai_hiring/product/__init__.py",
    "ai_hiring/product/__main__.py",
    "ai_hiring/product/version.py",
    "ai_hiring/product/config.py",
    "ai_hiring/product/composition.py",
    "ai_hiring/product/accountability.py",
    "ai_hiring/product/demo.py",
    "ai_hiring/product/cli.py",
]

VENDOR_SDKS = ("openai", "anthropic", "mistralai", "boto3", "smtplib", "sendgrid",
               "twilio", "workday", "greenhouse", "lever", "googleapiclient",
               "requests", "httpx", "sqlalchemy", "psycopg2")

BANNED_TRANSPORT = ("requests.", "smtplib", "urllib.request", "socket.socket", "boto3")


def _imports(rel):
    tree = ast.parse((REPO / rel).read_text(), filename=rel)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module
        elif isinstance(node, ast.Import):
            for a in node.names:
                yield node.lineno, a.name


def test_product_imports_no_vendor_sdks():
    violations = []
    for rel in PRODUCT_MODULES:
        for lineno, mod in _imports(rel):
            if mod.split(".")[0] in VENDOR_SDKS:
                violations.append(f"{rel}:{lineno} vendor-sdk -> {mod}")
    assert not violations, "H6 vendor-SDK violations:\n" + "\n".join(violations)


def test_product_does_not_import_kernel_internals():
    # The packaging layer reaches the kernel only *transitively* through the
    # already-validated hiring/validation services — never decision_governance
    # internals, and not even decision_governance directly.
    violations = []
    for rel in PRODUCT_MODULES:
        for lineno, mod in _imports(rel):
            top = mod.split(".")[0]
            if top == "decision_governance":
                violations.append(f"{rel}:{lineno} imports kernel directly -> {mod}")
            if top == "governance_providers" and not (
                mod.startswith("governance_providers.api")
                or mod.startswith("governance_providers.contracts")
                or mod.startswith("governance_providers.reference")
            ):
                violations.append(f"{rel}:{lineno} provider-internal -> {mod}")
            if top in ("tap_provider", "actiongate_provider"):
                violations.append(f"{rel}:{lineno} provider-impl -> {mod}")
    assert not violations, "H6 kernel/provider boundary violations:\n" + "\n".join(violations)


def test_product_uses_no_production_transport():
    for rel in PRODUCT_MODULES:
        s = (REPO / rel).read_text()
        for banned in BANNED_TRANSPORT:
            assert banned not in s, f"{rel} uses production transport {banned}"


def test_product_adds_no_new_lifecycle_states_or_authorities():
    from ai_hiring.actions.status import ActionProposalStatus
    from ai_hiring.recommendations.status import RecommendationStatus
    assert len(list(ActionProposalStatus)) == 13
    assert len(list(RecommendationStatus)) == 6


def test_product_config_restricts_to_deterministic_simulation():
    from ai_hiring.product.config import ExecutionMode, _SUPPORTED_MODES
    assert _SUPPORTED_MODES == frozenset({ExecutionMode.DETERMINISTIC_SIMULATION})


def test_product_never_certifies_production():
    from ai_hiring.product import version_info
    assert version_info().production_certified is False
