"""O-4's ASCII-only rule for identifiers and references, enforced mechanically.

Owner decision O-4 keeps identifier and reference fields ASCII, matched against::

    ^[A-Za-z0-9][A-Za-z0-9._:/-]*$

and applies that restriction to identifiers and references ONLY — never to claims,
reasons, summaries or any other human-readable text.

**Why the restriction is required, and why it stops where it does.** This capability
computes identity through ``ugence_jcs`` with an empty ``nfc_paths`` profile, so no
string is Unicode-normalized before it is canonicalized. Two spellings of the same
identifier that differ only by normalization form therefore canonicalize to different
bytes and produce different identities, while reading identically to a human and
comparing equal after any downstream normalization. Restricting identifiers to ASCII
removes the ambiguity at the only place it can do damage: the values consumers match,
route and join on. Human-readable text has no such role — it is carried, not matched —
and an ASCII bar there would be a defect, not a safeguard: it would reject the
languages the proposer's reasons are written in.

Both halves are enforced. The first check below demonstrates the normalization
hazard against the real substrate rather than asserting it, so the rule's premise is
evidence in this repository rather than a claim in a docstring.

The field-level rules are written to hold before the contract exists: they arm
themselves with the first annotated field this package declares.
"""
from __future__ import annotations

import ast
import pathlib
import re
import unicodedata

import pytest

import ugence_agentic_proposer as ap

SRC = pathlib.Path(ap.__file__).resolve().parent

#: O-4's pattern, verbatim. Pinned by equality below so it cannot be widened.
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"

#: Suffixes and names that make a field an identifier or a reference: a value other
#: parties match, route or join on.
IDENTIFIER_SUFFIXES = (
    "_id", "_ids", "_ref", "_refs", "_key", "_keys", "_uri", "_uris",
    "_urn", "_code", "_codes", "_slug",
)
IDENTIFIER_NAMES = ("id", "ref", "uri", "urn")

#: Markers of human-readable text: carried for a person to read, never matched on.
#: O-4 bars the ASCII restriction here.
FREE_TEXT_MARKERS = (
    "reason", "summary", "claim", "text", "note", "notes", "description",
    "rationale", "message", "title", "comment", "justification", "explanation",
    "label", "narrative",
)

#: Keywords through which a string constraint reaches a field.
CONSTRAINT_KEYWORDS = ("pattern", "regex")


def _sources():
    return sorted(SRC.rglob("*.py"))


# --------------------------------------------------------------------------- #
# The premise: an empty NFC profile makes spelling load-bearing
# --------------------------------------------------------------------------- #

def test_an_unnormalized_identifier_would_change_identity():
    """O-4's premise, demonstrated against the substrate this package uses.

    With an empty ``nfc_paths`` profile, two spellings of one identifier that differ
    only by Unicode normalization form canonicalize to different bytes — so they are
    two identities to a machine and one identifier to a reader. The pattern rejects
    both spellings, which is how the ambiguity is removed rather than managed.
    """
    ugence_jcs = pytest.importorskip("ugence_jcs")
    composed = unicodedata.normalize("NFC", "r\u00f4le-1")
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert (ugence_jcs.canonical_sha256_hex({"role_ref": composed})
            != ugence_jcs.canonical_sha256_hex({"role_ref": decomposed}))
    assert not _matches_the_rule(composed)
    assert not _matches_the_rule(decomposed)


def test_the_substrate_is_used_with_an_empty_normalization_profile():
    """The premise holds only while the profile stays empty. If a later stage passes
    a non-empty ``nfc_paths``, this fails and O-4 is reopened rather than silently
    resting on a profile that changed."""
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "nfc_paths":
                    continue
                if not _is_empty_collection(keyword.value):
                    offenders.append(f"{path.name}: {ast.unparse(node)}")
    assert not offenders, f"a non-empty normalization profile is in use: {offenders}"


def _is_empty_collection(node):
    """Whether a node spells an empty collection literal."""
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return not node.elts
    if isinstance(node, ast.Call):
        called = (node.func.id if isinstance(node.func, ast.Name)
                  else node.func.attr if isinstance(node.func, ast.Attribute) else "")
        return called in {"frozenset", "set"} and not node.args
    return False


# --------------------------------------------------------------------------- #
# Scanners
# --------------------------------------------------------------------------- #

def _matches_the_rule(value):
    """Whether ``value`` satisfies O-4's pattern.

    Applied with ``fullmatch``. ``re.match`` is not equivalent here: Python's ``$``
    also matches immediately before a trailing newline, so ``re.match`` admits
    ``"role\n"`` — a value that reads as an identifier, canonicalizes as a different
    one, and would be the first thing to try against a rule stated as a pattern.
    ``test_match_alone_is_not_the_rule`` pins the difference.
    """
    return re.fullmatch(IDENTIFIER_PATTERN, value) is not None


def _is_identifier_field(name):
    """Whether a field name carries an identifier or a reference.

    Checked before the free-text test, so ``reason_code`` — a code, matched on — is
    an identifier rather than free text, while ``reason`` is free text.
    """
    lowered = name.lower()
    return lowered in IDENTIFIER_NAMES or lowered.endswith(IDENTIFIER_SUFFIXES)


def _is_free_text_field(name):
    """Whether a field name carries human-readable text."""
    if _is_identifier_field(name):
        return False
    lowered = name.lower()
    return any(marker in lowered for marker in FREE_TEXT_MARKERS)


def _string_constants(tree):
    """Module-level ``NAME = "..."`` bindings, so a pattern reached through a constant
    is resolved to the string it holds."""
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            constants[node.target.id] = node.value.value
    return constants


def _constraints_on(node, constants):
    """Every string constraint reaching the field declared by ``node``.

    Reads both spellings a constraint arrives in: a keyword on the field's value
    (``Field(pattern=...)``, ``constr(pattern=...)``) and one inside its annotation
    (``Annotated[str, StringConstraints(pattern=...)]``). Values given as a module
    constant are resolved through ``constants``.
    """
    found = set()
    subtrees = [node.annotation] + ([node.value] if node.value is not None else [])
    for subtree in subtrees:
        for inner in ast.walk(subtree):
            if not isinstance(inner, ast.Call):
                continue
            for keyword in inner.keywords:
                if keyword.arg not in CONSTRAINT_KEYWORDS:
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    found.add(value.value)
                elif isinstance(value, ast.Name) and value.id in constants:
                    found.add(constants[value.id])
                else:
                    found.add(ast.unparse(value))
    return found


def _fields_of(source, filename="<sample>"):
    """``[(class, field, constraints)]`` for every annotated field in ``source``."""
    tree = ast.parse(source, filename=filename)
    constants = _string_constants(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                out.append((node.name, stmt.target.id, _constraints_on(stmt, constants)))
    return out


# --------------------------------------------------------------------------- #
# The pattern's own behaviour
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("value", [
    "cand-1", "role.ref", "urn:ugence:role:reviewer", "a", "A1",
    "path/to/thing", "some.thing", "0",
])
def test_the_pattern_accepts_an_ascii_identifier(value):
    assert _matches_the_rule(value)


@pytest.mark.parametrize("value", [
    "",                     # nothing is not an identifier
    "-leading",             # must start alphanumeric
    ".leading",
    " leading",
    "with space",
    "r\u00f4le-1",          # non-ASCII, composed
    "ro\u0302le-1",         # the same, decomposed
    "\uff52ole",            # fullwidth latin
    "role\u200b1",          # zero-width joiner hidden inside
    "role\n",               # a trailing newline is not an identifier
    "\u0440ole-1",          # cyrillic homoglyph
])
def test_the_pattern_rejects_anything_but_an_ascii_identifier(value):
    assert not _matches_the_rule(value)


def test_match_alone_is_not_the_rule():
    """How the pattern is applied is part of the rule.

    ``re.match`` accepts a trailing newline against ``$``; ``re.fullmatch`` does not.
    Stating the pattern without stating the application would leave the rule one
    convenience call away from admitting a value it names as invalid.
    """
    assert re.match(IDENTIFIER_PATTERN, "role\n") is not None
    assert re.fullmatch(IDENTIFIER_PATTERN, "role\n") is None


def test_the_pattern_is_pinned_to_the_ratified_text():
    """O-4's pattern, by equality. A widened character class fails here."""
    assert IDENTIFIER_PATTERN == r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"


# --------------------------------------------------------------------------- #
# Scanner self-tests
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", [
    "candidate_id", "selected_candidate_id", "role_ref",
    "requested_review_destination_role_ref", "idempotency_key", "source_uri",
    "reason_code", "id", "ref",
])
def test_the_field_classifier_sees_an_identifier(name):
    assert _is_identifier_field(name)
    assert not _is_free_text_field(name)


@pytest.mark.parametrize("name", [
    "reason", "summary", "claim", "rationale", "review_note",
    "description", "escalation_message", "explanation",
])
def test_the_field_classifier_sees_human_readable_text(name):
    assert _is_free_text_field(name)
    assert not _is_identifier_field(name)


@pytest.mark.parametrize("name", ["kind", "created_at", "entries", "count"])
def test_the_field_classifier_leaves_everything_else_alone(name):
    """A field that is neither is governed by neither rule. Classifying by default
    would either force a pattern onto a timestamp or bar one from a reference."""
    assert not _is_identifier_field(name)
    assert not _is_free_text_field(name)


@pytest.mark.parametrize("sample,expected", [
    ("class A:\n    role_ref: str = Field(pattern=r'%s')\n" % IDENTIFIER_PATTERN,
     {IDENTIFIER_PATTERN}),
    ("class A:\n    role_ref: constr(pattern=r'%s')\n" % IDENTIFIER_PATTERN,
     {IDENTIFIER_PATTERN}),
    ("class A:\n    role_ref: Annotated[str, StringConstraints(pattern=r'%s')]\n"
     % IDENTIFIER_PATTERN, {IDENTIFIER_PATTERN}),
    ("class A:\n    role_ref: str = Field(regex=r'^.*$')\n", {"^.*$"}),
    ("class A:\n    role_ref: str\n", set()),
])
def test_the_constraint_scanner_reads_every_spelling(sample, expected):
    (_, _, constraints), = _fields_of(sample)
    assert constraints == expected


def test_the_constraint_scanner_resolves_a_pattern_held_in_a_constant():
    sample = ("RE = r'%s'\n\nclass A:\n    role_ref: str = Field(pattern=RE)\n"
              % IDENTIFIER_PATTERN)
    (_, _, constraints), = _fields_of(sample)
    assert constraints == {IDENTIFIER_PATTERN}


# --------------------------------------------------------------------------- #
# O-4, enforced over the package as it stands
# --------------------------------------------------------------------------- #

def _declared_fields():
    found = []
    for path in _sources():
        for class_name, field, constraints in _fields_of(
                path.read_text(encoding="utf-8"), filename=str(path)):
            found.append((f"{path.name}:{class_name}.{field}", field, constraints))
    return found


@pytest.mark.parametrize("label,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_an_identifier_field_carries_the_ratified_pattern(label, field, constraints):
    """Arms with the first identifier field: it must be validated, and by this
    pattern rather than a lookalike."""
    if not _is_identifier_field(field):
        pytest.skip(f"{label} is not an identifier or a reference")
    assert constraints, f"{label} is an identifier with no ASCII validation"
    assert constraints == {IDENTIFIER_PATTERN}, (
        f"{label} is validated by something other than the ratified pattern: "
        f"{sorted(constraints)}")


@pytest.mark.parametrize("label,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_no_free_text_field_carries_the_identifier_pattern(label, field, constraints):
    """The other half of O-4, and the half a lexical scan gets wrong: an ASCII bar on
    a reason or a summary rejects the languages those are written in."""
    if not _is_free_text_field(field):
        pytest.skip(f"{label} is not human-readable text")
    assert IDENTIFIER_PATTERN not in constraints, (
        f"{label} is human-readable text restricted to ASCII identifiers")


def test_the_rule_is_pinned_to_identifiers_and_references_only():
    """O-4's scope, asserted directly: the same value is governed one way as an
    identifier and not at all as text."""
    assert _is_identifier_field("decision_reason_code")
    assert _is_free_text_field("decision_reason")
    assert IDENTIFIER_SUFFIXES[:3] == ("_id", "_ids", "_ref")
    assert "reason" in FREE_TEXT_MARKERS and "claim" in FREE_TEXT_MARKERS
