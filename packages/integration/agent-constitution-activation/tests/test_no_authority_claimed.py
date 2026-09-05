"""Orchestration, not authority — and the prose cannot quietly acquire one.

The reserved-vocabulary and compute-claim scans are re-asserted here exactly as
the conformance package carries them. The lifecycle-verb bar is **tailored, and
the tailoring is the ruled design**: `ACC-IA-BASE` ratified a package whose
purpose is to orchestrate issuance and to *activate* a constitution by deriving
its reference map — so ``issue_constitution`` and ``activate_constitution`` are
this package's lawful vocabulary, with the acting authority being the Policy
Authority under injected trust. What stays barred is the authority this package
must never hold: role and agent lifecycle (`OD-C4=A`), revocation (no
revocation seam exists here), approval semantics, and suspension — the words
below name those, and none may appear as a defined callable or exported name.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
import ugence_agent_constitution_activation as activation
import ugence_agentic_proposer as ap

DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = DIST_ROOT / "src" / "ugence_agent_constitution_activation"
MODULES = sorted(SRC.glob("*.py"))

#: Every term a name or a message here must not contain, uppercased.
BARRED_TERMS = (
    tuple(sorted(ap.RESERVED_AUTHORITY_VOCABULARY))
    + tuple(sorted(o.value for o in ap.TerminalOutcome))
    + tuple(sorted(d.value for d in ap.CandidateDisposition))
)

#: Compute and provisioning claims. Activation grants no compute, quota or
#: evidence access, and a receipt carries no provisioning meaning.
COMPUTE_CLAIM_MARKERS = (
    "budget",
    "quota",
    "token_count",
    "max_tokens",
    "tier",
    "provider",
    "compute",
)

#: The authority this package must never hold: role/agent lifecycle, revocation,
#: approval semantics, suspension. ``activate``/``issue`` are deliberately NOT
#: here — see the module docstring.
AUTHORITY_VERB_MARKERS = (
    "mint_",
    "suspend",
    "unsuspend",
    "ratify",
    "revoke",
    "reinstate",
    "enroll",
    "enrol",
    "authorize",
    "authorise",
    "approve",
    "replace_role",
)


def _defined_class_names(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _string_literals(path: pathlib.Path) -> list:
    """Every message string written in this module.

    Docstrings and ``__all__`` entries are excluded, on the conformance scan's
    own rationale: neither is a message a caller ever reads, and this package's
    prose deliberately *names* the terms it must not emit.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))
    excluded = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                excluded.add(id(first.value))
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            for element in ast.walk(node.value):
                excluded.add(id(element))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in excluded:
                out.append(node.value)
    return out


def test_the_barred_term_set_is_the_real_one_and_is_not_empty():
    assert "EXPIRED" in BARRED_TERMS
    assert "UNSUPPORTED" in BARRED_TERMS
    assert "SUPPORTED" in BARRED_TERMS
    assert "ABSTAIN" in BARRED_TERMS
    assert len(BARRED_TERMS) >= 19


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_class_defined_here_names_a_reserved_term(module):
    for name in _defined_class_names(module):
        upper = name.upper()
        hits = [term for term in BARRED_TERMS if term in upper]
        assert not hits, f"{module.name}:{name} names {hits}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_message_written_here_names_a_reserved_term(module):
    for literal in _string_literals(module):
        upper = literal.upper()
        hits = [term for term in BARRED_TERMS if term in upper]
        assert not hits, f"{module.name}: {literal!r} names {hits}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_source_name_claims_compute_or_provisioning(module):
    tree = ast.parse(module.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    for name in names:
        hits = [m for m in COMPUTE_CLAIM_MARKERS if m in name.lower()]
        assert not hits, f"{module.name}:{name} claims {hits}"


def test_no_source_callable_bears_a_barred_authority_verb():
    """`OD-C4=A` plus this round's own bars: no revocation, no approval
    semantics, no role or agent lifecycle — measured over defined callables."""

    for module in MODULES:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lowered = node.name.lower()
                hits = [m for m in AUTHORITY_VERB_MARKERS if m in lowered]
                assert not hits, f"{module.name}:{node.name} claims {hits}"


def test_the_exported_surface_claims_no_barred_authority():
    for name in activation.__all__:
        lowered = name.lower()
        assert not [m for m in COMPUTE_CLAIM_MARKERS if m in lowered], name
        assert not [m for m in AUTHORITY_VERB_MARKERS if m in lowered], name


def test_no_exported_name_maps_a_failure_to_an_operational_outcome():
    """`OD-C3=B`: a report row and a typed refusal, never a disposition."""

    for name in activation.__all__:
        lowered = name.lower()
        for forbidden in ("disposition", "outcome", "verdict", "decision"):
            assert forbidden not in lowered, name


def test_the_exported_surface_carries_no_verified_boolean():
    for name in activation.__all__:
        assert "verified" not in name.lower(), name


def test_no_module_defines_a_permissive_verifier_or_mints_identity():
    """Approval stays external; no verification is fabricated; no coordinate is
    minted; no registry is created. The reachable trust is injected, and every
    coordinate this package handles was derived by the authority's adapter."""

    for module in MODULES:
        source = module.read_text(encoding="utf-8")
        for forbidden in (
            "def verify_approval",
            "ApprovalVerification(",
            "AllowAll",
            "PolicyCoordinate(",
            "InMemoryPolicyRegistry",
        ):
            assert forbidden not in source, f"{module.name} contains {forbidden}"


def test_the_root_exposes_no_revocation_seam():
    """Revocation remains the authority's own signed act; a root that could
    revoke would be an authority. Measured over the class's public methods."""

    methods = [
        name
        for name in dir(activation.ActivationRoot)
        if not name.startswith("_")
    ]
    assert sorted(methods) == [
        "activate_constitution",
        "constitution_resolver",
        "issue_constitution",
        "preflight_issuance",
    ]
