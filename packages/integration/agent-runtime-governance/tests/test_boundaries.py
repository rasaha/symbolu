"""Boundaries asserted, not promised.

1. Agent Runtime gains no import from this package.
2. This package re-implements no composition logic — it calls the ratified engine.
3. It carries no credentials and reaches no live system.
4. Its maturity claim matches what actually exists.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[4]
RUNTIME_SRC = REPO / "packages" / "runtime" / "agent-runtime" / "src"
PKG_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


def _py(root: pathlib.Path):
    yield from root.rglob("*.py")


def test_agent_runtime_gains_no_import_from_this_package():
    offenders = [
        str(p.relative_to(REPO))
        for p in _py(RUNTIME_SRC)
        if "ugence_agent_runtime_governance" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"the dependency must stay one-way; found: {offenders}"


def test_agent_runtime_still_imports_no_concrete_governance():
    """The runtime's own neutrality is the reason this package can exist at all: it
    depends on nothing concrete, so a concrete adapter can be injected."""
    offenders = []
    for p in _py(RUNTIME_SRC):
        text = p.read_text(encoding="utf-8")
        for concrete in ("ugence_risk_authority_runtime", "import risk_authority",
                         "ugence_decision_authority", "ugence_actiongate"):
            if concrete in text:
                offenders.append(f"{p.name}: {concrete}")
    assert offenders == [], f"Agent Runtime must stay concrete-free; found: {offenders}"


COMPOSITION_SYMBOLS = (
    # If any of these appear in this package's source, composition has been
    # re-implemented here instead of delegated to the package that owns it.
    "apply_restrictions",
    "effective_scope_violations",
    "_decide",
    "EFFECTIVE_SCOPE_EMPTY",
)


def test_this_package_re_implements_no_composition_logic():
    offenders = []
    for p in _py(PKG_SRC):
        text = p.read_text(encoding="utf-8")
        # Strip docstrings and comments: naming a symbol while explaining the boundary
        # is the opposite of re-implementing it.
        tree = ast.parse(text)
        code = ast.unparse(_strip_docstrings(tree))
        for symbol in COMPOSITION_SYMBOLS:
            if symbol in code:
                offenders.append(f"{p.name}: {symbol}")
    assert offenders == [], (
        f"composition logic must be delegated, never restated here: {offenders}"
    )


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return tree


def test_the_hook_calls_the_ratified_composition_engine():
    """Positive counterpart to the test above: the engine is actually used."""
    from ugence_agent_runtime_governance.hook import GovernedExecutionHook
    from ugence_risk_authority_runtime.composition import RiskAuthorityCompositionEngine

    source = inspect.getsource(GovernedExecutionHook)
    assert "self._engine.compose(" in source, "the hook must delegate to compose()"

    hook = GovernedExecutionHook(source=object())
    assert isinstance(hook._engine, RiskAuthorityCompositionEngine)  # noqa: SLF001


def test_the_recheck_is_wired_not_reimplemented():
    """RA-6 already ships ``make_pre_effect_recheck``; this package supplies the
    resolver and nothing else."""
    from ugence_agent_runtime_governance import recheck

    source = inspect.getsource(recheck)
    assert "make_pre_effect_recheck" in source
    for reimplemented in ("check_authority_status", "RevocationState(", "def _verify"):
        assert reimplemented not in source.split('"""')[-1], (
            f"{reimplemented} suggests the recheck was rebuilt rather than wired"
        )


BANNED = (
    "ExecutionMode.LIVE", "AWS_SECRET", "password=", "api_key",
    "private_key", "signing_key", "SigningKey(",
)


def test_no_credentials_and_no_live_execution():
    offenders = []
    for p in _py(PKG_SRC):
        text = p.read_text(encoding="utf-8")
        for token in BANNED:
            if token in text:
                offenders.append(f"{p.name}: {token}")
    assert offenders == [], f"credential or live-execution tokens found: {offenders}"


def test_the_package_never_constructs_an_envelope_or_a_decision():
    """It projects what it is given. Minting either would make it an authority."""
    offenders = []
    for p in _py(PKG_SRC):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in (
                    "RiskAuthorizationEnvelope",
                    "GovernedExecutionDecision",
                    "RiskAuthorityMachineResult",
                ):
                    offenders.append(f"{p.name}: {node.func.id}(...)")
    assert offenders == [], f"this package must mint nothing; found: {offenders}"


def test_maturity_is_stated_honestly():
    from ugence_agent_runtime_governance import maturity

    m = maturity()
    assert m["pilot_validated"] is False
    assert m["production_certified"] is False
    assert m["stage"] == "Core implemented"
    assert "ProductionContainmentError" in m["known_gaps"]
    assert "no sink" in m["known_gaps"]


def test_readme_does_not_overclaim():
    readme = (pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text()
    lowered = readme.lower().replace("*", "").replace("_", " ")
    for claim in ("production-ready", "production ready", "pilot-validated",
                  "production-certified"):
        idx = 0
        while (idx := lowered.find(claim, idx)) != -1:
            window = lowered[max(0, idx - 40):idx]
            assert "not" in window or "never" in window, (
                f"README claims {claim!r}; context: "
                f"...{lowered[max(0, idx - 60):idx + len(claim)]}"
            )
            idx += len(claim)
