"""No authority claimed, and no reserved vocabulary emitted — measured, not asserted.

This is the runtime half of the ratified proof obligation. Three distinct scans,
because the ruling names three distinct things:

1. **Names and messages** carry no reserved authority term, no terminal outcome
   and no candidate disposition — scanned **uppercased, as a substring**, which is
   the rule the Agentic Proposer's own refusal guard applies. A whole-word
   comparison would miss exactly the collisions the rule exists to catch.
2. **A ``PolicyResolutionReason`` token reaches a caller only through the
   ``reason`` attribute.** This is why (1) is not sufficient on its own: two of
   the authority's reasons *are* reserved terms under the uppercased-substring
   rule — ``EXPIRED`` verbatim, and ``SUPERSESSION_REFERENCE_UNSUPPORTED``
   containing both ``UNSUPPORTED`` and ``SUPPORTED`` — so interpolating the
   authority's own reason into a message would make this package emit reserved
   authority vocabulary without anyone choosing to.
3. **No compute authorization and no execution authority** appears in the
   exported surface: no budget, quota, token count, capability tier or provider
   name, and no name that mints, activates, ends or authorizes anything.

**What the scans deliberately exclude.** Docstrings, because this package's prose
names the terms it must not emit; ``__all__`` entries, because an export list is a
list of names rather than message text; and class names the *authority* owns,
which this package neither chose nor may rename.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
import ugence_agentic_proposer as ap
import ugence_agentic_proposer_strategy_permission_runtime as runtime
from _permission_runtime_fixtures import issued_world, make_request
from ugence_agentic_proposer_strategy_permission_runtime import (
    StrategyPolicyUnresolvedError,
)
from ugence_policy_authority.api import PolicyResolutionReason

DIST_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = DIST_ROOT / "src" / "ugence_agentic_proposer_strategy_permission_runtime"
MODULES = sorted(SRC.glob("*.py"))

BARRED_TERMS = (
    tuple(sorted(ap.RESERVED_AUTHORITY_VOCABULARY))
    + tuple(sorted(o.value for o in ap.TerminalOutcome))
    + tuple(sorted(d.value for d in ap.CandidateDisposition))
)

REASON_TOKENS = tuple(sorted(reason.value for reason in PolicyResolutionReason))

COMPUTE_CLAIM_MARKERS = (
    "budget",
    "quota",
    "token_count",
    "max_tokens",
    "tier",
    "provider",
    "compute",
)

AUTHORITY_VERB_MARKERS = (
    "mint_",
    "activate",
    "suspend",
    "ratify",
    "revoke_role",
    "replace_role",
    "authorize",
    "authorise",
    "grant",
)


def _defined_class_names(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _message_literals(path: pathlib.Path) -> list:
    """Every message string written in this module.

    F-string literal segments are included: a reserved term interpolated *around*
    a substitution is still reserved text in the message a caller reads.
    Docstrings and ``__all__`` entries are excluded — see this module's docstring.
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
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in excluded
    ]


# --------------------------------------------------------------------------- #
# The scans measure the real vocabularies
# --------------------------------------------------------------------------- #


def test_the_barred_term_set_is_the_real_one_and_carries_the_disclosed_collisions():
    for term in ("EXPIRED", "UNSUPPORTED", "SUPPORTED", "ABSTAIN", "ESCALATE"):
        assert term in BARRED_TERMS, term
    assert len(BARRED_TERMS) >= 19


def test_the_two_disclosed_reason_collisions_are_real():
    """Stated in the design, verified here rather than taken on trust."""

    reserved = {t.upper() for t in ap.RESERVED_AUTHORITY_VOCABULARY}
    assert "EXPIRED" in reserved
    assert PolicyResolutionReason.EXPIRED.value.upper() in reserved

    supersession = PolicyResolutionReason.SUPERSESSION_REFERENCE_UNSUPPORTED.value.upper()
    assert "UNSUPPORTED" in supersession
    assert "SUPPORTED" in supersession
    assert {"UNSUPPORTED", "SUPPORTED"} <= reserved


def test_the_scan_uses_the_uppercased_substring_rule_not_whole_words():
    """A whole-word rule would pass a message containing the collisions above."""

    sample = "the version is expired"
    assert not any(term in sample.split() for term in BARRED_TERMS)
    assert any(term in sample.upper() for term in BARRED_TERMS)


# --------------------------------------------------------------------------- #
# 1. Names and messages
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_class_defined_here_names_a_reserved_term(module):
    for name in _defined_class_names(module):
        hits = [term for term in BARRED_TERMS if term in name.upper()]
        assert not hits, f"{module.name}:{name} names {hits}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_message_written_here_names_a_reserved_term(module):
    for literal in _message_literals(module):
        hits = [term for term in BARRED_TERMS if term in literal.upper()]
        assert not hits, f"{module.name}: {literal!r} names {hits}"


def test_no_error_class_in_the_exported_taxonomy_names_a_reserved_term():
    for name in runtime.__all__:
        obj = getattr(runtime, name)
        if isinstance(obj, type) and issubclass(obj, Exception):
            hits = [term for term in BARRED_TERMS if term in obj.__name__.upper()]
            assert not hits, f"{obj.__name__} names {hits}"


# --------------------------------------------------------------------------- #
# 2. The reason token reaches a caller only through the attribute
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_message_written_here_names_a_resolution_reason(module):
    for literal in _message_literals(module):
        hits = [token for token in REASON_TOKENS if token in literal.upper()]
        assert not hits, f"{module.name}: {literal!r} names {hits}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_interpolates_a_reason_into_prose(module):
    """Structural, not textual: no reason value reaches an f-string or a format call."""

    tree = ast.parse(module.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            rendered = ast.unparse(node)
            assert "reason" not in rendered, f"{module.name}: {rendered}"


@pytest.mark.parametrize("reason", list(PolicyResolutionReason), ids=lambda r: r.value)
def test_a_raised_reason_is_readable_on_the_attribute_and_absent_from_the_message(reason):
    """The message and every exception argument, which is what a caller reads.

    Deliberately **not** ``repr()``. The ratified class name
    ``StrategyPolicyUnresolvedError`` contains ``RESOLVED`` under the same
    uppercased-substring rule, and ``repr()`` renders the class name — so a
    ``repr`` assertion would condemn the name the design itself chose. The ruling
    governs message text: a reason must not be interpolated into prose a caller
    reads. It does not rename the taxonomy, and this test does not either.
    """

    error = StrategyPolicyUnresolvedError(
        "the policy authority did not return a policy version; the "
        "machine-readable cause is carried on the reason attribute",
        reason=reason,
    )
    assert error.reason is reason
    assert reason.value not in str(error).upper()
    for argument in error.args:
        assert reason.value not in str(argument).upper()


def test_the_ratified_class_name_collision_is_known_rather_than_undetected():
    """Disclosed rather than discovered later, and deliberately not worked around.

    ``StrategyPolicyUnresolvedError`` is the name the design's failure matrix
    gives this class. Under the uppercased-substring rule its name contains the
    ``RESOLVED`` reason token — a coincidence of English, not a leak: the rule
    exists so that the *authority's cause* does not reach a caller as prose, and a
    class name that says a resolution did not happen discloses no cause at all.
    """

    assert PolicyResolutionReason.RESOLVED.value in (
        StrategyPolicyUnresolvedError.__name__.upper()
    )
    # What the rule actually protects still holds: no cause in the message.
    error = StrategyPolicyUnresolvedError("x", reason=PolicyResolutionReason.REVOKED)
    assert PolicyResolutionReason.REVOKED.value not in str(error).upper()


def test_a_real_refusal_carries_the_reason_on_the_attribute_only():
    """Exercised through the genuine pipeline rather than a constructed exception."""

    from _permission_runtime_fixtures import T_AFTER

    _, _, _, resolver = issued_world()
    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request(as_of=T_AFTER))

    assert excinfo.value.reason is PolicyResolutionReason.EXPIRED
    message = str(excinfo.value).upper()
    for token in REASON_TOKENS:
        assert token not in message, token
    for term in BARRED_TERMS:
        assert term not in message, term


def test_every_error_in_the_taxonomy_exposes_the_reason_attribute():
    """A caller reads one attribute, whichever failure it caught."""

    for name in runtime.__all__:
        obj = getattr(runtime, name)
        if isinstance(obj, type) and issubclass(
            obj, runtime.StrategyPermissionResolverError
        ):
            assert hasattr(obj, "reason")


# --------------------------------------------------------------------------- #
# 3. No compute authorization, no execution authority
# --------------------------------------------------------------------------- #


def test_the_exported_surface_claims_no_compute_and_no_lifecycle_authority():
    for name in runtime.__all__:
        lowered = name.lower()
        assert not [m for m in COMPUTE_CLAIM_MARKERS if m in lowered], name
        assert not [m for m in AUTHORITY_VERB_MARKERS if m in lowered], name


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


def test_the_exported_surface_is_exactly_the_ratified_shape():
    """The resolver, its error family, and **one** composition helper. Nothing else.

    §8's delta table is what `S2B-PF-BASE` ratified, and its runtime row names
    exactly those three things — a composition helper in the singular, where the
    same table uses plurals for the family package's categories, and no constant
    anywhere in any row.
    """

    exported = set(runtime.__all__)
    assert "PolicyAuthorityStrategyPolicyResolver" in exported
    errors = {
        name
        for name in exported
        if isinstance(getattr(runtime, name), type)
        and issubclass(getattr(runtime, name), Exception)
    }
    assert len(errors) == 7, sorted(errors)
    assert exported == {
        "__version__",
        "PolicyAuthorityStrategyPolicyResolver",
        "build_strategy_policy_resolver",
        *errors,
    }
    helpers = exported - errors - {"__version__", "PolicyAuthorityStrategyPolicyResolver"}
    assert helpers == {"build_strategy_policy_resolver"}, helpers


@pytest.mark.parametrize(
    "name", ["with_strategy_permission_adapter", "HISTORICAL_RESOLUTION"]
)
def test_the_two_demoted_names_are_internal_and_not_re_exported(name):
    """Owner ruling `SURFACE=B`: internal, and reachable only through their modules.

    Left as package attributes they would sit outside ``__all__`` while still
    looking like surface — the "enough to look supported, not enough to be"
    shape this work refuses elsewhere. So they are not re-exported at all.
    """

    assert name not in runtime.__all__
    assert not hasattr(runtime, name), f"{name} is still re-exported from the package"


def test_the_demoted_names_still_exist_where_they_belong():
    """Demoted, not deleted: the behaviour they name is unchanged."""

    from ugence_agentic_proposer_strategy_permission_runtime.composition import (
        with_strategy_permission_adapter,
    )
    from ugence_agentic_proposer_strategy_permission_runtime.resolver import (
        HISTORICAL_RESOLUTION,
    )

    assert callable(with_strategy_permission_adapter)
    assert HISTORICAL_RESOLUTION is not None


def test_no_exported_name_asserts_its_own_trustworthiness():
    """`[R]` No ``verified`` boolean is ratified anywhere in this work."""

    for name in runtime.__all__:
        assert "verified" not in name.lower()
