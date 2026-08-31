"""This boundary claims no authority, and its prose cannot quietly acquire one.

The scans here are the conformance-side half of the §5.4 proof obligation: no
reserved authority term, terminal-outcome value or candidate-disposition value
in any error name or message template; no compute authorization; no
consequential execution authority; and no operational disposition for a
structural conformance failure — which remains deliberately unruled
(`OD-C3=B`), so nothing here may name one. The one channel a resolution-reason
token may use is the exception's ``reason`` attribute, asserted separately in
the resolution suite.

**The uppercased-substring rule matters.** The Agentic Proposer's own guard
uppercases the text and tests substring containment, and its reserved vocabulary
contains terms that appear inside ordinary English words. A guard that compared
whole words would miss exactly the collisions the rule exists to catch, so this
one uses the same rule.

**What it scans, and what it deliberately does not.** Classes *defined here* and
string literals *written here*. Authority names this package raises or imports
carry reserved substrings the authority owns and this package neither chose nor
may rename; scanning imported names would turn a correct fail-closed refusal
into a test failure.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
import ugence_agent_constitution_conformance as conformance
import ugence_agentic_proposer as ap

DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = DIST_ROOT / "src" / "ugence_agent_constitution_conformance"
MODULES = sorted(SRC.glob("*.py"))

#: Every term a name or a message here must not contain, uppercased.
BARRED_TERMS = (
    tuple(sorted(ap.RESERVED_AUTHORITY_VOCABULARY))
    + tuple(sorted(o.value for o in ap.TerminalOutcome))
    + tuple(sorted(d.value for d in ap.CandidateDisposition))
)

#: Compute and provisioning claims. Conformance grants no compute, quota or
#: evidence access, and its answer carries no provisioning meaning.
COMPUTE_CLAIM_MARKERS = (
    "budget",
    "quota",
    "token_count",
    "max_tokens",
    "tier",
    "provider",
    "compute",
)

#: Role-lifecycle and authorization verbs. `OD-C4=A`: the roles this boundary
#: reads about are referenced; nothing here mints, activates, ends or authorizes.
AUTHORITY_VERB_MARKERS = (
    "mint_",
    "activate",
    "suspend",
    "ratify",
    "revoke",
    "replace_role",
    "authorize",
    "authorise",
)


def _defined_class_names(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _string_literals(path: pathlib.Path) -> list:
    """Every message string written in this module.

    F-string literal segments are included: a reserved term interpolated *around*
    a substitution is still reserved text in the message a caller reads.

    Two kinds of literal are excluded, because neither is a message a caller ever
    sees and treating them as one would measure the wrong thing: **docstrings**
    (this package's prose deliberately *names* the terms it must not emit) and
    **``__all__`` entries** (an export list is a list of names, not message
    text).
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
    """A scan built from an empty or hand-copied list would measure nothing."""

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


def test_the_exported_surface_claims_no_compute_and_no_lifecycle_authority():
    for name in conformance.__all__:
        lowered = name.lower()
        assert not [m for m in COMPUTE_CLAIM_MARKERS if m in lowered], name
        assert not [m for m in AUTHORITY_VERB_MARKERS if m in lowered], name


def test_no_source_callable_bears_a_lifecycle_verb():
    """`OD-C4=A`, measured over defined function and method names: a callable
    bearing a transition verb would be an operation, and none may exist here."""

    for module in MODULES:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lowered = node.name.lower()
                hits = [m for m in AUTHORITY_VERB_MARKERS if m in lowered]
                assert not hits, f"{module.name}:{node.name} claims {hits}"


def test_the_verifier_answer_is_a_bool_and_no_disposition_type_exists():
    """`OD-C3=B`: no exported name maps a failure to an operational outcome."""

    for name in conformance.__all__:
        lowered = name.lower()
        for forbidden in ("disposition", "outcome", "verdict", "decision"):
            assert forbidden not in lowered, name


def test_the_exported_surface_carries_no_verified_boolean():
    """`[R]` No ``verified`` boolean is ratified anywhere in this work: a
    returned artifact existing at all, and a plain predicate answer, are the
    evidence. ``verifier``-the-role-word appears in no export either — the one
    exported verifier is the predicate function itself."""

    for name in conformance.__all__:
        assert "verified" not in name.lower(), name


def test_no_module_defines_a_permissive_approval_verifier():
    """Approval stays external, and production ships only a deny-by-default one.

    ``def verify_approval`` rather than the bare method name: the resolver
    *requires* a caller-supplied verifier and names the method it must
    implement, which is the opposite of defining one.
    """

    for module in MODULES:
        source = module.read_text(encoding="utf-8")
        for forbidden in ("def verify_approval", "ApprovalVerification(", "AllowAll"):
            assert forbidden not in source, f"{module.name} contains {forbidden}"


def test_no_module_holds_a_registry_or_mints_a_coordinate():
    """The reachable set is injected; nothing here creates a coordinate."""

    for module in MODULES:
        source = module.read_text(encoding="utf-8")
        assert "PolicyCoordinate(" not in source, module.name
        assert "InMemoryPolicyRegistry" not in source, module.name
