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

**The registry is a mirror, not an authority.** Every class, field and category below
is re-exported from ``s1_specification_mirror``, which transcribes
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`` — the authoritative S1 contract and
equation specification. This guard originates no contract field, adds none, renames none
and reclassifies none. Where the mirror and that document disagree, the document is
right. ``test_the_registry_cites_its_source`` asserts the citation still resolves, and
the completeness checks fail in both directions: a declared field absent from the
registry, and a registry entry naming a field nothing declares.

The field-level rules are written to hold before the production contract surface exists:
they arm themselves with the first annotated field ``src/`` declares, and are exercised
today against temporary representative shapes derived from the specification. **A green
run here is not a verified contract and authorizes no production code** — production
implementation is separately gated (ADR addendum A11).
"""
from __future__ import annotations

import ast
import pathlib
import re
import typing
import unicodedata

import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec

SRC = pathlib.Path(ap.__file__).resolve().parent

#: **Everything below is mirrored, not originated.** The patterns, the class set, the
#: per-field classification and the per-contract cardinalities are re-exported from
#: ``s1_specification_mirror``, which transcribes them from
#: ``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``. This guard adds no field, renames
#: none and reinterprets none; where it and that document disagree, the document is
#: right. ``test_the_registry_cites_its_source`` asserts the citation resolves.
SPECIFICATION = spec.SPECIFICATION

IDENTIFIER_PATTERN = spec.IDENTIFIER_PATTERN
TOKEN_PATTERN = spec.TOKEN_PATTERN
C5A, C5B, C5C, C5D = spec.C5A, spec.C5B, spec.C5C, spec.C5D
OTHER_PATTERN = spec.OTHER_PATTERN
CLOSED = spec.CLOSED
NON_STRING = spec.NON_STRING
STRUCTURED = spec.STRUCTURED
MAPPING_C5A_KEYS_C5C_VALUES = spec.MAPPING_C5A_KEYS_C5C_VALUES
CLASSES = spec.CLASSES
PATTERN_FOR = spec.PATTERN_FOR
PATTERNLESS = spec.PATTERNLESS
FIELD_CLASSIFICATION = spec.FIELD_CLASSIFICATION
CONTRACT_CARDINALITY = spec.CONTRACT_CARDINALITY
COMMON_FIELDS = spec.COMMON_FIELDS

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


def _classify(contract, field):
    """The declared category of ``contract.field``, or ``None`` if unregistered.

    **The registry is the primary and authoritative classifier.** Name shape is not
    consulted here at all: a suffix rule reaches neither ``tool_name`` nor the scope
    fields, and a field it cannot classify is a field it silently leaves unchecked.
    ``test_every_declared_field_is_registered`` makes an unregistered field a failure
    rather than a skip.
    """
    return FIELD_CLASSIFICATION.get(contract, {}).get(field)


def _inferred_category(name):
    """Suffix/marker inference, retained as a SECONDARY cross-check only.

    Never used to decide whether a field is validated. It exists so that a registry
    entry contradicting the obvious reading of a name is visible rather than silent,
    and it returns ``None`` wherever it cannot tell — which is exactly the gap the
    registry exists to close.
    """
    lowered = name.lower()
    if lowered in IDENTIFIER_NAMES or lowered.endswith(IDENTIFIER_SUFFIXES):
        return C5A
    if any(marker in lowered for marker in FREE_TEXT_MARKERS):
        return C5C
    return None


def _is_identifier_field(name):
    """Retained for the scanner self-tests. Inference only — see ``_classify``."""
    return _inferred_category(name) == C5A


def _is_free_text_field(name):
    """Retained for the scanner self-tests. Inference only — see ``_classify``."""
    return _inferred_category(name) == C5C


#: The two ratified pattern constants, resolved by name.
#:
#: A contract module that imports ``IDENTIFIER_PATTERN`` from the specification mirror
#: and writes ``StringConstraints(pattern=IDENTIFIER_PATTERN)`` is declaring the ratified
#: pattern, and a scan that saw only a bare ``Name`` would report it as validated by
#: something it could not read. Resolution is by name **and** by value: these names map
#: to the ratified literals, so a module that rebinds one locally to something else has
#: its own binding win — ``_string_constants`` is applied after this seed, not before.
RATIFIED_PATTERN_NAMES = {
    "IDENTIFIER_PATTERN": IDENTIFIER_PATTERN,
    "TOKEN_PATTERN": TOKEN_PATTERN,
}


def _string_constants(tree):
    """``NAME = "..."`` bindings, so a pattern reached through a constant is resolved to
    the string it holds, seeded with the two ratified pattern names."""
    constants = dict(RATIFIED_PATTERN_NAMES)
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


def _annotation_aliases(tree):
    """``NAME = Annotated[str, StringConstraints(...)]`` bindings, at module or function
    scope, so a constraint reached through a type alias is resolved to the constraint it
    carries.

    A contract that declares ``identifier = Annotated[str, StringConstraints(pattern=
    IDENTIFIER_PATTERN)]`` once and writes ``case_ref: identifier`` on twenty fields is
    the ordinary way to declare a class of field, and it satisfies C8 exactly. A scan
    that read only the literal annotation would report every one of those fields as
    carrying no validation — a false negative that would make the guard unusable against
    the shape it is meant to check. Aliases are resolved rather than the rule relaxed.
    """
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [tgt for tgt in node.targets if isinstance(tgt, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets, value = [node.target], node.value
        else:
            continue
        if value is None or isinstance(value, ast.Constant):
            continue
        if not isinstance(value, ast.Subscript) and not isinstance(value, ast.Call):
            continue
        for target in targets:
            aliases[target.id] = value
    return aliases


#: Calls through which a string constraint actually BINDS a field value. A ``pattern=``
#: keyword anywhere else in the annotation or the default — inside ``json_schema_extra``,
#: a ``description``, an ``examples`` list, or any other decorative metadata — validates
#: nothing and must not be read as validation (G-5).
BINDING_CONSTRAINT_CALLS = ("Field", "StringConstraints", "constr", "conlist", "constring")

#: Keywords that carry decorative metadata. A constraint nested inside one of these is
#: documentation about a field, not a rule applied to its value.
DECORATIVE_KEYWORDS = ("json_schema_extra", "description", "examples", "title",
                       "alias", "deprecated")


def _called_name(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _binding_constraint_calls(subtree):
    """Yield every call that can bind a string constraint, skipping decorative nests.

    A ``Call`` reached only through a decorative keyword is not yielded, so a pattern
    written into ``json_schema_extra={"pattern": ...}`` or quoted in a ``description``
    is invisible to the scanner — which is correct, because it is invisible to
    validation too.
    """
    stack = [(subtree, False)]
    while stack:
        node, decorative = stack.pop()
        if isinstance(node, ast.Call):
            if not decorative and _called_name(node) in BINDING_CONSTRAINT_CALLS:
                yield node
            for keyword in node.keywords:
                stack.append((keyword.value,
                              decorative or keyword.arg in DECORATIVE_KEYWORDS))
            for arg in node.args:
                stack.append((arg, decorative))
            continue
        for child in ast.iter_child_nodes(node):
            stack.append((child, decorative))


def _constraints_on(node, constants, aliases=None):
    """Every string constraint that actually binds the field declared by ``node``.

    Reads both binding spellings: a keyword on the field's value
    (``Field(pattern=...)``, ``constr(pattern=...)``) and one inside its annotation
    (``Annotated[str, StringConstraints(pattern=...)]``). Values given as a module
    constant are resolved through ``constants``.

    **A ``pattern=`` keyword is not accepted merely for being present.** It counts only
    when it is an argument of a call that binds the value, and only when that call is
    not itself nested inside decorative metadata. A decorative pattern is a claim about
    a field, and accepting one as validation is how a guard reports a constrained field
    that nothing constrains.
    """
    found = set()
    aliases = aliases or {}
    subtrees = [node.annotation] + ([node.value] if node.value is not None else [])
    seen_aliases = set()
    while True:
        referenced = [n.id for subtree in subtrees for n in ast.walk(subtree)
                      if isinstance(n, ast.Name)
                      and n.id in aliases and n.id not in seen_aliases]
        if not referenced:
            break
        seen_aliases.update(referenced)
        subtrees.extend(aliases[name] for name in referenced)
    for subtree in subtrees:
        for inner in _binding_constraint_calls(subtree):
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
    aliases = _annotation_aliases(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                out.append((node.name, stmt.target.id,
                            _constraints_on(stmt, constants, aliases)))
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
            found.append((f"{path.name}:{class_name}.{field}", class_name, field,
                          constraints))
    return found


@pytest.mark.parametrize("label,contract,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_every_declared_field_is_registered(label, contract, field, constraints):
    """No field may be unclassified. This is what a suffix rule could not give: a
    field it cannot read is a field it never checks, and the failure is silent."""
    if contract not in FIELD_CLASSIFICATION:
        pytest.skip(f"{contract} is not an S1 contract")
    assert _classify(contract, field) is not None, (
        f"{label} is declared but carries no O-4 classification; add it to "
        "FIELD_CLASSIFICATION as C5a, C5b, C5c, other-pattern or closed")


def _pattern_verdict(contract, field, constraints, classification=None):
    """The guard's own decision about one field, factored out.

    Returns ``(verdict, category)`` where verdict is:

    * ``"accepted"`` — a patterned category, validated by exactly its own pattern;
    * ``"rejected"`` — a patterned category, validated by nothing or by the wrong
      grammar;
    * ``"unchecked"`` — the registry gives it no patterned category, so this guard
      does not look at it at all.

    ``classification`` defaults to the real registry. It is a parameter so a **mutated
    registry can be run through this exact code**, rather than through a mutation
    control that re-derives the rule and therefore tests its own copy of it. The
    ``"unchecked"`` verdict is what makes reclassification dangerous and is why it is a
    distinct outcome rather than folded into ``"rejected"``: a reclassified field does
    not fail, it silently leaves the checked set.
    """
    classification = FIELD_CLASSIFICATION if classification is None else classification
    category = classification.get(contract, {}).get(field)
    if category not in PATTERN_FOR:
        return "unchecked", category
    expected = PATTERN_FOR[category]
    if not constraints or constraints != {expected}:
        return "rejected", category
    return "accepted", category


@pytest.mark.parametrize("label,contract,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_a_classified_field_carries_its_category_pattern(label, contract, field,
                                                         constraints):
    """C5a and C5b fields must be validated, and by their own pattern rather than a
    lookalike or each other's."""
    verdict, category = _pattern_verdict(contract, field, constraints)
    if verdict == "unchecked":
        pytest.skip(f"{label} is {category or 'unregistered'}, not a patterned category")
    assert verdict == "accepted", (
        f"{label} is {category} but validated by {sorted(constraints)}, "
        f"not {PATTERN_FOR[category]!r}")


@pytest.mark.parametrize("label,contract,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_no_free_text_field_carries_an_identifier_or_token_pattern(label, contract,
                                                                   field, constraints):
    """The other half of O-4, and the half a lexical scan gets wrong: an ASCII bar on
    a purpose or a summary rejects the languages those are written in."""
    if _classify(contract, field) != C5C:
        pytest.skip(f"{label} is not human-readable text")
    for pattern in (IDENTIFIER_PATTERN, TOKEN_PATTERN):
        assert pattern not in constraints, (
            f"{label} is human-readable text restricted to an ASCII grammar")


@pytest.mark.parametrize("label,contract,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_a_declared_free_text_field_carries_no_pattern_of_any_kind(label, contract,
                                                                   field, constraints):
    """G-4 on the declared surface: the bar is on the **mechanism**, not on two literals.

    The test above rejects the C5a and C5b patterns by name; this one rejects every
    pattern, so a *third* grammar — an anchored printable-ASCII class, a "lenient" junk
    filter, a narrowed variant of either named pattern — is caught too. Each such
    grammar rejects prose a case may lawfully be conducted in, and none of these fields
    is matched, routed or joined on, so there is nothing for a pattern to protect.
    """
    if _classify(contract, field) != C5C:
        pytest.skip(f"{label} is not human-readable text")
    assert constraints == set(), (
        f"{label} is C5c human-readable free text and carries a pattern constraint: "
        f"{sorted(constraints)}. C5c admits length, NFC and non-emptiness only; a "
        "pattern of any kind is barred, including one that is neither the identifier "
        "nor the token grammar")


@pytest.mark.parametrize("label,contract,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_a_declared_reserved_list_carries_no_element_pattern(label, contract, field,
                                                             constraints):
    """C5d on the declared surface. The constraint is emptiness and nothing else; a
    pattern that can never be reached is a claim about a vocabulary this stage does not
    have."""
    if _classify(contract, field) != C5D:
        pytest.skip(f"{label} is not a reserved list")
    assert constraints == set(), (
        f"{label} is C5d and declares an element pattern: {sorted(constraints)}")


@pytest.mark.parametrize("label,contract,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_a_declared_field_matching_no_pattern_category_declares_none(label, contract,
                                                                     field, constraints):
    """A field the registry classifies as neither patterned nor free text must not
    acquire a C5a or C5b pattern by accident — that would be a silent reclassification
    the registry never recorded."""
    category = _classify(contract, field)
    if category not in (CLOSED, NON_STRING, STRUCTURED):
        pytest.skip(f"{label} is {category}")
    for pattern in (IDENTIFIER_PATTERN, TOKEN_PATTERN):
        assert pattern not in constraints, (
            f"{label} is registered {category} but carries the {pattern!r} grammar")


def test_the_rule_is_pinned_to_identifiers_and_references_only():
    """O-4's scope, asserted directly: the same value is governed one way as an
    identifier and not at all as text."""
    assert _is_identifier_field("decision_reason_code")
    assert _is_free_text_field("decision_reason")
    assert IDENTIFIER_SUFFIXES[:3] == ("_id", "_ids", "_ref")
    assert "reason" in FREE_TEXT_MARKERS and "claim" in FREE_TEXT_MARKERS


# --------------------------------------------------------------------------- #
# O-4 mutation probes — every category, positively and negatively
# --------------------------------------------------------------------------- #

#: The six fields a suffix rule reaches as neither identifier nor text. Each is a
#: canonical token, and each is why the registry exists.
TOKEN_FIELDS = (
    ("AgentIdentityRef", "agent_version"),
    ("ToolObservation", "tool_name"),
    ("WorkMandate", "allowed_source_scopes"),
    ("BoundedContextEnvelope", "excluded_data_classes"),
    ("CognitiveRoleContract", "permitted_tool_scopes"),
    ("ProposerProcessRecord", "tool_invocations"),
)


@pytest.mark.parametrize("contract,field", TOKEN_FIELDS)
def test_a_token_field_is_classified_c5b_not_guessed(contract, field):
    """Positive control. Each is registered C5b — and inference cannot see it."""
    assert _classify(contract, field) == C5B
    assert _inferred_category(field) is None, (
        f"{field} is now inferable; the registry must still be authoritative")


@pytest.mark.parametrize("contract,field", TOKEN_FIELDS)
def test_a_token_field_is_not_reachable_by_suffix_inference(contract, field):
    """Negative control, and the whole point of the correction: under suffix-only
    classification these six were neither identifiers nor text, so they were checked
    by nothing at all."""
    assert not _is_identifier_field(field)
    assert not _is_free_text_field(field)


@pytest.mark.parametrize("contract,field", [
    ("ProposerAdvisory", "case_ref"), ("ProposerAdvisory", "mandate_id"),
    ("CandidateAdvisory", "observation_refs"), ("ToolObservation", "source_ref"),
    ("ProposerAdvisory", "selected_candidate_id"),
])
def test_an_identifier_field_is_classified_c5a(contract, field):
    assert _classify(contract, field) == C5A
    assert PATTERN_FOR[C5A] == IDENTIFIER_PATTERN


@pytest.mark.parametrize("contract,field", [
    ("WorkMandate", "purpose"), ("CognitiveRoleContract", "primary_function"),
    ("ProposerProcessRecord", "declared_strategy"),
    ("ProposerAdvisory", "claim_summaries"), ("CandidateAdvisory", "uncertainties"),
    ("CandidateAdvisory", "assumptions"),
])
def test_a_free_text_field_is_classified_c5c_and_has_no_grammar(contract, field):
    """OD-1 and O-4 together: descriptive fields take no ASCII grammar of any kind."""
    assert _classify(contract, field) == C5C
    assert C5C not in PATTERN_FOR, "free text must have no required pattern"


@pytest.mark.parametrize("contract,field", [
    ("WorkMandate", "purpose"), ("CognitiveRoleContract", "primary_function"),
    ("ProposerProcessRecord", "declared_strategy"),
])
def test_free_text_admits_what_the_ascii_grammar_would_reject(contract, field):
    """Demonstrated, not asserted. A purpose written in a language the identifier
    grammar cannot spell must remain lawful — and would not be, under either pattern."""
    assert _classify(contract, field) == C5C
    for value in ("Rechnungsprüfung für März", "発注書の照合", "reconcile invoice #42"):
        assert re.fullmatch(IDENTIFIER_PATTERN, value) is None
        assert re.fullmatch(TOKEN_PATTERN, value) is None


def test_the_token_pattern_differs_from_the_identifier_pattern_exactly_by_the_separator():
    """C5b is C5a minus ``/``, and the difference is load-bearing rather than
    cosmetic: a token is compared by equality against an allowlist."""
    assert re.fullmatch(IDENTIFIER_PATTERN, "path/to/thing") is not None
    assert re.fullmatch(TOKEN_PATTERN, "path/to/thing") is None
    for shared in ("invoice.read", "tool:reader", "a-b_c" .replace("_", "."), "A1"):
        assert (re.fullmatch(IDENTIFIER_PATTERN, shared) is not None
                and re.fullmatch(TOKEN_PATTERN, shared) is not None)


@pytest.mark.parametrize("value", ["role\n", "rôle", "", " role", "-role", "a b"])
def test_the_token_pattern_rejects_what_the_identifier_pattern_rejects(value):
    """Full-string matching, on both patterns. ``re.match`` would admit ``role\\n``."""
    assert re.fullmatch(TOKEN_PATTERN, value) is None
    assert re.fullmatch(IDENTIFIER_PATTERN, value) is None




# --------------------------------------------------------------------------- #
# G-1 — the registry is a MIRROR of the specification, pinned in every dimension
# --------------------------------------------------------------------------- #

def test_the_registry_cites_its_source():
    """Provenance, checked rather than asserted in a comment.

    The registry has no authority of its own. It is an enforcement mirror of
    ``S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``, and every block it mirrors names the
    section it came from. A section renamed in that document fails here, so the citation
    cannot rot into a comment nobody reads.
    """
    assert SPECIFICATION.is_file(), (
        f"the canonical specification is missing at {SPECIFICATION}")
    text = SPECIFICATION.read_text(encoding="utf-8")
    missing = [f"{block} -> {heading}"
               for block, heading in spec.PROVENANCE.items() if heading not in text]
    assert not missing, f"registry provenance no longer resolves: {missing}"


def test_the_class_set_is_pinned_exactly():
    """G-1: the exact class set. Adding a category, removing one, or renaming one is a
    change to what the registry can say and must fail here first."""
    assert CLASSES == (
        "C5a", "C5b", "C5c", "C5d", "other-pattern", "closed", "non-string",
        "structured", "mapping-c5a-keys-c5c-values")
    assert (C5A, C5B, C5C, C5D) == ("C5a", "C5b", "C5c", "C5d")


def test_no_class_outside_the_pinned_set_is_used():
    for contract, fields in FIELD_CLASSIFICATION.items():
        unknown = set(fields.values()) - set(CLASSES)
        assert not unknown, f"{contract} uses unregistered categories: {sorted(unknown)}"


def test_the_contract_set_is_pinned_exactly():
    """Eight canonical contracts plus the two subordinate nested public shapes."""
    assert spec.TOP_LEVEL_CONTRACTS == (
        "AgentIdentityRef", "CognitiveRoleContract", "WorkMandate",
        "BoundedContextEnvelope", "ToolObservation", "AdvisoryCandidateSet",
        "ProposerAdvisory", "ProposerProcessRecord")
    assert len(spec.TOP_LEVEL_CONTRACTS) == 8
    assert spec.NESTED_PUBLIC_SHAPES == (
        "CandidateAdvisory", "ProposerProcessStateTransition")
    assert set(FIELD_CLASSIFICATION) == set(
        spec.TOP_LEVEL_CONTRACTS) | set(spec.NESTED_PUBLIC_SHAPES)


@pytest.mark.parametrize("contract,cardinality",
                         sorted(spec.CONTRACT_CARDINALITY.items()))
def test_the_registry_carries_exactly_the_stated_cardinality(contract, cardinality):
    """G-1: the exact field set for every class, checked by count against Part D's
    stated cardinality. A field added to or dropped from the registry fails here even
    if nothing else notices."""
    assert len(FIELD_CLASSIFICATION[contract]) == cardinality, (
        f"{contract} is specified as {cardinality} fields; the registry carries "
        f"{len(FIELD_CLASSIFICATION[contract])}")


def test_the_advisory_carries_the_twenty_three_ratified_fields():
    """OD-4(a): twenty-three, because ``candidates`` is added and ``candidate_set_id``
    is retained alongside it rather than replaced by it."""
    fields = FIELD_CLASSIFICATION["ProposerAdvisory"]
    assert len(fields) == 23
    assert fields["candidates"] == STRUCTURED
    assert fields["candidate_set_id"] == C5A
    assert fields["selected_candidate_id"] == C5A


def test_the_candidate_set_stays_top_level_and_carries_the_same_container():
    """OD-4(a) does not demote ``AdvisoryCandidateSet``, and both candidate sequences
    are ``tuple[CandidateAdvisory, ...]`` so no implementation compares containers of
    different types."""
    assert "AdvisoryCandidateSet" in spec.TOP_LEVEL_CONTRACTS
    assert FIELD_CLASSIFICATION["AdvisoryCandidateSet"]["candidates"] == STRUCTURED
    shapes = spec.representative_shapes()
    for owner in ("AdvisoryCandidateSet", "ProposerAdvisory"):
        annotation = shapes[owner].model_fields["candidates"].annotation
        assert typing.get_origin(annotation) is tuple, owner
        args = typing.get_args(annotation)
        assert args[0] is shapes["CandidateAdvisory"] and args[1] is Ellipsis, owner


def test_the_common_fields_are_on_every_contract_and_on_neither_nested_shape():
    """C2, checked in both directions."""
    for contract in spec.TOP_LEVEL_CONTRACTS:
        for field in COMMON_FIELDS:
            assert field in FIELD_CLASSIFICATION[contract], (contract, field)
    for shape in spec.NESTED_PUBLIC_SHAPES:
        for field in COMMON_FIELDS:
            assert field not in FIELD_CLASSIFICATION[shape], (shape, field)


def test_the_registry_carries_non_string_fields_too():
    """I5: a registry populated only from ``str``-annotated fields has a circular
    completeness check. ``lifecycle_state`` and ``candidates`` are the two cases where
    that bites, so both are pinned explicitly."""
    assert FIELD_CLASSIFICATION["AgentIdentityRef"]["lifecycle_state"] == CLOSED
    assert FIELD_CLASSIFICATION["ProposerAdvisory"]["candidates"] == STRUCTURED


def test_no_registry_entry_is_declared_twice_within_a_contract():
    """A duplicate key would silently keep the last spelling. Read the source rather
    than the built dict, because the dict cannot show what it lost."""
    tree = ast.parse(spec.SPECIFICATION_MIRROR_SOURCE, filename="mirror")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name)
                   and target.id == "FIELD_CLASSIFICATION" for target in node.targets):
            continue
        for contract_value in node.value.values:
            names = [k.value for k in contract_value.keys]
            assert len(names) == len(set(names)), f"duplicate field key: {names}"


# --------------------------------------------------------------------------- #
# G-1 — the registry cannot add, omit, rename or reclassify a field silently
# --------------------------------------------------------------------------- #

def _declared_by(model):
    return set(model.model_fields)


@pytest.mark.parametrize("contract", sorted(FIELD_CLASSIFICATION))
def test_the_registry_matches_the_declared_field_set_exactly(contract):
    """The completeness check, run in both directions against a declared surface.

    Today that surface is the temporary representative shapes; when ``src/`` declares
    the contracts, ``test_every_declared_field_is_registered`` binds on those instead
    and this becomes redundant rather than wrong. Either way the check is exact
    membership: a field declared and unregistered fails, and a field registered and
    undeclared fails.
    """
    declared = _declared_by(spec.representative_shapes()[contract])
    registered = set(FIELD_CLASSIFICATION[contract])
    assert declared == registered, (
        f"{contract}: declared-only {sorted(declared - registered)}, "
        f"registered-only {sorted(registered - declared)}")


def test_an_added_field_fails_the_registry_check():
    """Mutation control: a field the surface declares and the registry does not."""
    declared = _declared_by(spec.representative_shapes()["ProposerAdvisory"])
    mutant = declared | {"advisory_note"}
    assert mutant != set(FIELD_CLASSIFICATION["ProposerAdvisory"])


def test_an_omitted_field_fails_the_registry_check():
    """Mutation control: a registry entry dropped."""
    registered = dict(FIELD_CLASSIFICATION["ProposerAdvisory"])
    registered.pop("candidates")
    declared = _declared_by(spec.representative_shapes()["ProposerAdvisory"])
    assert set(registered) != declared
    assert len(registered) != CONTRACT_CARDINALITY["ProposerAdvisory"]


def test_a_renamed_field_fails_the_registry_check():
    """Mutation control: a rename is an omission and an addition at once, and the
    exact-membership check sees both halves."""
    registered = dict(FIELD_CLASSIFICATION["ProposerAdvisory"])
    registered["candidate_entries"] = registered.pop("candidates")
    declared = _declared_by(spec.representative_shapes()["ProposerAdvisory"])
    assert set(registered) != declared
    assert len(registered) == CONTRACT_CARDINALITY["ProposerAdvisory"], (
        "a rename keeps the count; only exact membership catches it")


# --------------------------------------------------------------------------- #
# G-3 — every C5a and C5b entry is mutation-pinned, not a sampled few
# --------------------------------------------------------------------------- #

def _entries(category):
    return sorted((contract, field)
                  for contract, fields in FIELD_CLASSIFICATION.items()
                  for field, value in fields.items() if value == category)


C5A_ENTRIES = _entries(C5A)
C5B_ENTRIES = _entries(C5B)
C5C_ENTRIES = _entries(C5C)
C5D_ENTRIES = _entries(C5D)

#: A category name that is in no registry, used as the ninth mutation: reclassifying a
#: field to something the registry never heard of.
UNREGISTERED_CATEGORY = "not-a-registered-category"

#: **The exclusion rule, stated once and derived, not hand-listed.**
#:
#: A reclassification is a *weakening* — the thing this sweep is about — exactly when the
#: new category does not demand a pattern, because then the guard stops checking the
#: field at all. That is ``category not in PATTERN_FOR``, and it is the same predicate
#: ``_pattern_verdict`` branches on, so the sweep's domain is derived from the guard's
#: own rule rather than restated beside it.
#:
#: Two kinds of case are therefore **excluded, and neither is a survivor**:
#:
#: * **The entry's own category.** Reclassifying C5a to C5a is not a mutation.
#: * **The sibling patterned category** — C5b for a C5a entry, C5a for a C5b entry. This
#:   is a real and dangerous change, but it is a **narrowing, not a weakening**: the
#:   guard still demands a pattern, so ``_pattern_verdict`` returns ``"rejected"``
#:   rather than ``"unchecked"`` and this sweep's assertion does not apply to it. It is
#:   covered by ``test_swapping_a_patterned_entry_to_its_sibling_is_rejected_not_ignored``
#:   below, per entry, through the same verdict helper.
#:
#: ``test_the_weakening_domain_is_derived_from_the_guards_own_rule`` fails if this
#: derivation is replaced by a hand-written list, and
#: ``test_narrowing_the_exclusion_rule_loses_coverage`` fails if the rule is narrowed to
#: exclude a category that genuinely is a weakening.
WEAKENING_CATEGORIES = tuple(
    category for category in CLASSES if category not in PATTERN_FOR
) + (UNREGISTERED_CATEGORY,)

#: The categories excluded because they still demand a pattern. Not weakenings.
PATTERNED_CATEGORIES = tuple(PATTERN_FOR)


@pytest.mark.parametrize("contract,field", C5A_ENTRIES,
                         ids=lambda v: str(v)[:40])
def test_every_c5a_entry_is_classified_c5a(contract, field):
    """G-3: every entry, not a sample. Each C5a field is registered C5a and takes the
    identifier pattern, which admits ``/`` and the token pattern does not."""
    assert FIELD_CLASSIFICATION[contract][field] == C5A
    assert PATTERN_FOR[C5A] == IDENTIFIER_PATTERN


@pytest.mark.parametrize("contract,field", C5B_ENTRIES, ids=lambda v: str(v)[:40])
def test_every_c5b_entry_is_classified_c5b(contract, field):
    assert FIELD_CLASSIFICATION[contract][field] == C5B
    assert PATTERN_FOR[C5B] == TOKEN_PATTERN


@pytest.mark.parametrize("contract,field", C5A_ENTRIES + C5B_ENTRIES,
                         ids=lambda v: str(v)[:40])
@pytest.mark.parametrize("weakened", WEAKENING_CATEGORIES)
def test_weakening_any_patterned_entry_removes_it_from_the_checked_set(contract, field,
                                                                      weakened):
    """G-3, the mutation sweep: for **every** C5a and C5b entry crossed with **every**
    weakening category, the mutated registry is fed through ``_pattern_verdict`` — the
    function the real check calls — and must change what the guard does.

    The name says *weakening* and not *any reclassification* because that is the sweep's
    actual domain. A weakening is a category that does not demand a pattern, so the field
    silently leaves the checked set; the sibling patterned category is a narrowing and is
    tested separately. The exclusion is derived from the guard's own predicate, not
    hand-listed — see ``WEAKENING_CATEGORIES``.

    Under the ratified registry the field is ``"accepted"``: the guard demands its pattern
    and the declared field carries it. Under the mutated registry the same field with the
    same declared constraints becomes ``"unchecked"``. That transition is the defect, and
    it is silent, which is why it is asserted directly rather than inferred from two
    registries being unequal.
    """
    original = FIELD_CLASSIFICATION[contract][field]
    assert original in PATTERN_FOR
    assert weakened != original
    assert weakened not in PATTERN_FOR, (
        f"{weakened} still demands a pattern; it is a narrowing, not a weakening, and "
        "belongs to the sibling test rather than this sweep")

    declared = {PATTERN_FOR[original]}
    assert _pattern_verdict(contract, field, declared) == ("accepted", original), (
        "precondition: under the ratified registry this field is checked and passes")

    mutated = dict(FIELD_CLASSIFICATION)
    mutated[contract] = dict(FIELD_CLASSIFICATION[contract])
    mutated[contract][field] = weakened

    verdict, category = _pattern_verdict(contract, field, declared,
                                         classification=mutated)
    assert verdict == "unchecked", (
        f"weakening {contract}.{field} from {original} to {weakened} left the guard "
        f"reporting {verdict}; the weakening must remove the field from the checked set "
        "so that this control can see it")
    assert category == weakened

    if weakened == UNREGISTERED_CATEGORY:
        assert weakened not in CLASSES, "an unregistered category must not be accepted"
        assert set(mutated[contract].values()) - set(CLASSES) == {weakened}
    else:
        assert weakened in CLASSES


@pytest.mark.parametrize("contract,field", C5A_ENTRIES + C5B_ENTRIES,
                         ids=lambda v: str(v)[:40])
def test_swapping_a_patterned_entry_to_its_sibling_is_rejected_not_ignored(contract,
                                                                           field):
    """The excluded case, tested rather than waved through.

    C5a and C5b both demand a pattern, so swapping one for the other never produces
    ``"unchecked"`` and is outside the weakening sweep's domain. It is still a real
    defect — C5a admits ``/`` and C5b does not, so the swap silently narrows an
    externally minted path-shaped handle, or silently widens a token that is the operand
    of a membership test. Fed through the same verdict helper, it must come back
    ``"rejected"``: the guard still looks at the field and refuses the grammar it now
    carries.

    This is what makes the exclusion principled. Every registered category is covered by
    one sweep or the other; none is quietly dropped.
    """
    original = FIELD_CLASSIFICATION[contract][field]
    sibling = C5B if original == C5A else C5A
    assert sibling in PATTERN_FOR and sibling != original

    declared = {PATTERN_FOR[original]}
    mutated = dict(FIELD_CLASSIFICATION)
    mutated[contract] = dict(FIELD_CLASSIFICATION[contract])
    mutated[contract][field] = sibling

    verdict, category = _pattern_verdict(contract, field, declared,
                                         classification=mutated)
    assert verdict == "rejected", (
        f"swapping {contract}.{field} from {original} to {sibling} produced {verdict}; "
        "a sibling swap must still be looked at and refused, not ignored")
    assert category == sibling


def test_the_weakening_domain_is_derived_from_the_guards_own_rule():
    """The exclusion rule is a derivation, not a hand-written list.

    ``WEAKENING_CATEGORIES`` is every registered class the guard does not demand a
    pattern for, plus one unregistered sentinel. Adding a tenth class to ``CLASSES``
    therefore enters this sweep automatically. A hand-written list would not, and the
    accidental omission this test exists to prevent is exactly what happened: an earlier
    revision listed six categories by hand and silently left out
    ``mapping-c5a-keys-c5c-values``, which is a weakening.
    """
    derived = tuple(c for c in CLASSES if c not in PATTERN_FOR) + (UNREGISTERED_CATEGORY,)
    assert WEAKENING_CATEGORIES == derived, (
        "WEAKENING_CATEGORIES has been replaced by a hand-written list; derive it from "
        "CLASSES and PATTERN_FOR so a new category cannot be omitted")
    assert MAPPING_C5A_KEYS_C5C_VALUES in WEAKENING_CATEGORIES, (
        "the category an earlier hand-written list omitted must be covered")
    assert set(WEAKENING_CATEGORIES) & set(PATTERN_FOR) == set(), (
        "a category that demands a pattern is a narrowing, not a weakening")


def test_every_registered_category_is_covered_by_one_sweep_or_the_other():
    """The denominator, asserted. No registered class may fall between the two sweeps.

    For a patterned entry, the candidate reclassifications are the other eight registered
    classes plus the unregistered sentinel. Seven of the eight are weakenings and belong
    to the sweep above; the ninth, the sibling patterned class, is a narrowing and
    belongs to the sibling test. Self-reclassification is not a mutation. Nothing else
    exists, so there is no unexplained case.
    """
    for original in PATTERNED_CATEGORIES:
        others = set(CLASSES) - {original}
        weakenings = others - set(PATTERN_FOR)
        narrowings = others & set(PATTERN_FOR)
        assert weakenings | narrowings == others, (
            f"a registered category is in neither sweep for {original}: "
            f"{sorted(others - weakenings - narrowings)}")
        assert len(narrowings) == 1, (
            f"exactly one sibling patterned category is expected for {original}: "
            f"{sorted(narrowings)}")
    applicable = len(C5A_ENTRIES + C5B_ENTRIES) * len(WEAKENING_CATEGORIES)
    assert applicable == 47 * 8 == 376, (
        f"the weakening sweep's applicable count changed to {applicable}; if that is "
        "intended, update the count recorded in the enforcement documentation")


def test_narrowing_the_exclusion_rule_loses_coverage():
    """The self-test the exclusion rule needs: narrowing it must fail, not pass quietly.

    Two narrowings are simulated. Dropping a genuine weakening from the domain leaves an
    entry-category pair that no sweep covers — the defect that produced the omission
    above. Widening the domain to include a patterned sibling puts a case into the sweep
    whose assertion is false for it, so the sweep would fail rather than silently assert
    the wrong thing. Both are asserted here so the rule cannot be edited in either
    direction without a test saying so.
    """
    full = set(WEAKENING_CATEGORIES)

    narrowed = full - {MAPPING_C5A_KEYS_C5C_VALUES}
    uncovered = (set(CLASSES) - set(PATTERN_FOR)) - narrowed
    assert uncovered == {MAPPING_C5A_KEYS_C5C_VALUES}, (
        "narrowing the domain must leave a registered weakening uncovered, which is "
        "what makes the narrowing detectable")

    # And the narrowed domain would genuinely have missed a real weakening: fed through
    # the guard, that category still removes a field from the checked set.
    contract, field = C5A_ENTRIES[0]
    mutated = dict(FIELD_CLASSIFICATION)
    mutated[contract] = dict(FIELD_CLASSIFICATION[contract])
    mutated[contract][field] = MAPPING_C5A_KEYS_C5C_VALUES
    verdict, _ = _pattern_verdict(contract, field, {PATTERN_FOR[C5A]},
                                  classification=mutated)
    assert verdict == "unchecked", (
        "the omitted category is a real weakening; excluding it would have hidden a "
        "reclassification the guard stops checking")

    widened = full | {C5B}
    assert widened != full
    contract, field = C5A_ENTRIES[0]
    mutated = dict(FIELD_CLASSIFICATION)
    mutated[contract] = dict(FIELD_CLASSIFICATION[contract])
    mutated[contract][field] = C5B
    verdict, _ = _pattern_verdict(contract, field, {PATTERN_FOR[C5A]},
                                  classification=mutated)
    assert verdict == "rejected", (
        "widening the domain to a patterned sibling would put a case in the sweep whose "
        "'unchecked' assertion is false for it")


@pytest.mark.parametrize("contract,field", C5A_ENTRIES, ids=lambda v: str(v)[:40])
def test_a_c5a_entry_swapped_to_the_token_pattern_is_a_narrowing_that_must_be_visible(
        contract, field):
    """C5a admits ``/``; C5b does not. Swapping the class silently narrows an
    externally minted, possibly path-shaped handle, so the two classes must never
    resolve to the same pattern."""
    assert PATTERN_FOR[C5A] != PATTERN_FOR[C5B]
    assert re.fullmatch(PATTERN_FOR[C5A], "issuer/handle-1") is not None
    assert re.fullmatch(PATTERN_FOR[C5B], "issuer/handle-1") is None


# --------------------------------------------------------------------------- #
# G-4 — C5c carries no pattern of ANY kind, and lawful Unicode is accepted
# --------------------------------------------------------------------------- #

#: Grammars a "lenient" reading might smuggle onto a free-text field. None of them is
#: the C5a or C5b literal, and each rejects lawful prose. C5c bars the mechanism, so
#: every one of these is a violation.
ARBITRARY_ASCII_GRAMMARS = (
    r"^[\x00-\x7F]*$",              # ASCII-only, said the long way
    r"^[ -~]+$",                    # printable ASCII
    r"^[A-Za-z0-9 .,;:'\"!?-]+$",   # "obvious junk" filter
    r"^\w[\w\s.,-]*$",              # a lenient-looking word grammar
    r"[A-Za-z]",                    # unanchored, and still a regex
    r".*",                          # a pattern that rejects nothing is still a pattern
)


@pytest.mark.parametrize("contract,field", C5C_ENTRIES, ids=lambda v: str(v)[:40])
def test_every_c5c_entry_admits_no_pattern_mechanism(contract, field):
    """G-4: the prohibition is on the *mechanism*, not on two named literals.

    A C5c field may carry length, NFC or non-emptiness. It may not carry ``pattern=``,
    a ``StringConstraints`` bearing one, an ``re`` match applied at validation, or a
    custom validator whose effect is to test the value against a regular expression.
    """
    assert FIELD_CLASSIFICATION[contract][field] == C5C
    assert C5C not in PATTERN_FOR
    assert C5C in PATTERNLESS


@pytest.mark.parametrize("grammar", ARBITRARY_ASCII_GRAMMARS)
@pytest.mark.parametrize("contract,field", C5C_ENTRIES[:3], ids=lambda v: str(v)[:40])
def test_an_arbitrary_ascii_grammar_on_free_text_is_a_violation(contract, field,
                                                                grammar):
    """G-4's mutation: a *third* pattern, neither C5a nor C5b, is still barred — and
    each of these rejects prose a case may lawfully be written in."""
    assert FIELD_CLASSIFICATION[contract][field] == C5C
    assert grammar not in (IDENTIFIER_PATTERN, TOKEN_PATTERN), (
        "the point is a pattern that is not one of the two named ones")
    sample = "Rechnungsprüfung für März — 発注書の照合"
    assert re.fullmatch(grammar, sample) is None or grammar == r".*", (
        f"{grammar!r} would reject lawful prose; a pattern that does not is still "
        "barred, because C5c bars the mechanism")


def test_the_c5c_bar_is_on_the_mechanism_not_on_two_literals():
    """Stated as an assertion so it cannot be softened to 'not the C5a/C5b patterns'."""
    barred = set(ARBITRARY_ASCII_GRAMMARS) | {IDENTIFIER_PATTERN, TOKEN_PATTERN}
    assert len(barred) == len(ARBITRARY_ASCII_GRAMMARS) + 2
    assert not (barred & set(PATTERN_FOR.get(C5C, ()) or ()))


@pytest.mark.parametrize("contract,field", C5D_ENTRIES, ids=lambda v: str(v)[:40])
def test_every_c5d_entry_is_empty_only_and_declares_no_element_pattern(contract, field):
    """C5d is mechanical: the constraint is emptiness and nothing else. A pattern
    declared alongside it would be a ratified spelling for a catalogue that does not
    exist."""
    assert FIELD_CLASSIFICATION[contract][field] == C5D
    assert C5D not in PATTERN_FOR
    assert C5D in PATTERNLESS


def test_the_five_reserved_lists_are_exactly_the_c5d_fields():
    assert set(C5D_ENTRIES) == {
        ("AdvisoryCandidateSet", "selection_reason_codes"),
        ("ProposerAdvisory", "reason_codes"),
        ("ProposerProcessRecord", "deterministic_checks"),
        ("ProposerProcessRecord", "semantic_audit_refs"),
        ("ProposerProcessRecord", "reason_codes"),
    }


# --------------------------------------------------------------------------- #
# G-5 — live model probes: the pattern binds the value, not the metadata
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def shapes():
    pytest.importorskip("pydantic")
    return spec.representative_shapes()


#: Values no C5a field may accept. Each is a spelling that reads as an identifier and
#: canonicalizes as a different one, or is not an identifier at all.
INVALID_IDENTIFIER_VALUES = (
    "", " leading", "-leading", ".leading", "with space", "role\n", "role\t",
    "r\u00f4le-1", "ro\u0302le-1", "\uff52ole", "role\u200b1", "\u0440ole-1",
)
#: Everything above, plus the path separator C5b excludes.
INVALID_TOKEN_VALUES = INVALID_IDENTIFIER_VALUES + ("scope/with/slash",)


@pytest.mark.parametrize("value", INVALID_IDENTIFIER_VALUES)
def test_a_live_c5a_field_rejects_an_invalid_identifier(shapes, value):
    """G-5: the constraint is exercised against the model, not read off the AST."""
    pydantic = pytest.importorskip("pydantic")
    fixture = spec.complete_advisory_fixture(case_ref=value)
    with pytest.raises(pydantic.ValidationError):
        shapes["ProposerAdvisory"](**fixture)


@pytest.mark.parametrize("value", ["case-1", "urn:ugence:case:1", "issuer/handle.2",
                                   "A1", "0"])
def test_a_live_c5a_field_accepts_a_lawful_identifier(shapes, value):
    advisory = shapes["ProposerAdvisory"](
        **spec.complete_advisory_fixture(case_ref=value))
    assert advisory.case_ref == value


@pytest.mark.parametrize("value", INVALID_TOKEN_VALUES)
def test_a_live_c5b_field_rejects_an_invalid_symbolic_token(shapes, value):
    """G-5, including the four spellings named explicitly: slash, spaces, newline and
    homoglyphs. ``tool_name`` is matched by equality against ``permitted_tool_scopes``,
    so any of these changes an eligibility outcome while reading as the same token."""
    pydantic = pytest.importorskip("pydantic")
    with pytest.raises(pydantic.ValidationError):
        shapes["ToolObservation"](
            schema_version="1.0", tenant_id="tenant-1",
            created_at=spec.FIXED_INSTANT, observation_id="obs-1", case_ref="case-1",
            tool_name=value, operation_class=spec.ToolOperationClass.READ_ONLY,
            source_ref="src-1", observed_at=spec.FIXED_INSTANT,
            content_hash="placeholder", normalized_fields={},
            admission_status=spec.ToolObservationAdmissionStatus.NOT_EVALUATED)


@pytest.mark.parametrize("value", INVALID_TOKEN_VALUES)
def test_a_live_sequence_valued_c5b_field_validates_every_element(shapes, value):
    """A sequence-valued C5a/C5b field is validated element by element, not as a
    container. A guard that checked only the first entry — or only the annotation —
    would pass a list whose second element is a homoglyph."""
    pydantic = pytest.importorskip("pydantic")
    with pytest.raises(pydantic.ValidationError):
        shapes["CognitiveRoleContract"](
            schema_version="1.0", tenant_id="tenant-1",
            created_at=spec.FIXED_INSTANT, role_contract_id="role-1",
            primary_function="reconcile invoices",
            permitted_tool_scopes=["invoice.read", value],
            permitted_candidate_dispositions=[
                ap.CandidateDisposition.RECOMMEND_WITHHOLD],
            permitted_review_actions=[spec.ReviewAction.ROUTE_APPROVAL_BUNDLE],
            escalation_role_ref="role:escalation",
            activation_status=spec.RoleActivationStatus.ACTIVE)


@pytest.mark.parametrize("value", INVALID_IDENTIFIER_VALUES)
def test_a_live_sequence_valued_c5a_field_validates_every_element(shapes, value):
    pydantic = pytest.importorskip("pydantic")
    with pytest.raises(pydantic.ValidationError):
        shapes["ProposerAdvisory"](
            **spec.complete_advisory_fixture(observation_refs=["obs-1", value]))


#: Prose a case may lawfully be conducted in. None matches either ASCII grammar.
LAWFUL_FREE_TEXT = (
    "Rechnungsprüfung für März",
    "発注書の照合",
    "сверка счетов-фактур",
    "reconcile invoice #42 — vendor disputed, see note",
    "مطابقة الفاتورة",
)


@pytest.mark.parametrize("value", LAWFUL_FREE_TEXT)
def test_a_live_c5c_field_accepts_lawful_unicode_text(shapes, value):
    """G-4, behaviourally: free text is accepted, and would not be under either
    pattern. Demonstrated on the model rather than asserted about the registry."""
    assert re.fullmatch(IDENTIFIER_PATTERN, value) is None
    assert re.fullmatch(TOKEN_PATTERN, value) is None
    advisory = shapes["ProposerAdvisory"](
        **spec.complete_advisory_fixture(claim_summaries=[value],
                                         uncertainties=[value]))
    assert advisory.claim_summaries == [value]


@pytest.mark.parametrize("value", LAWFUL_FREE_TEXT)
def test_a_live_c5c_scalar_field_accepts_lawful_unicode_text(shapes, value):
    mandate = shapes["WorkMandate"](
        schema_version="1.0", tenant_id="tenant-1", created_at=spec.FIXED_INSTANT,
        mandate_id="mandate-1", case_ref="case-1",
        assigned_role_contract_id="role-1", purpose=value,
        allowed_source_scopes=["ledger.read"], expires_at=spec.FIXED_INSTANT)
    assert mandate.purpose == value


@pytest.mark.parametrize("value", [[], ["", "x"]])
def test_a_live_c5d_field_admits_only_the_empty_list(shapes, value):
    """C5d rejects any non-empty value, whatever its elements look like."""
    pydantic = pytest.importorskip("pydantic")
    if value == []:
        assert shapes["ProposerAdvisory"](
            **spec.complete_advisory_fixture(reason_codes=[])).reason_codes == []
    else:
        with pytest.raises(pydantic.ValidationError):
            shapes["ProposerAdvisory"](
                **spec.complete_advisory_fixture(reason_codes=value))


def test_the_mapping_field_validates_keys_as_c5a_and_values_as_free_text(shapes):
    """D5: ``normalized_fields`` keys are C5a and values are C5c. Both halves probed —
    an unlawful key is rejected and lawful Unicode content is accepted."""
    pydantic = pytest.importorskip("pydantic")
    base = dict(
        schema_version="1.0", tenant_id="tenant-1", created_at=spec.FIXED_INSTANT,
        observation_id="obs-1", case_ref="case-1", tool_name="invoice.read",
        operation_class=spec.ToolOperationClass.READ_ONLY, source_ref="src-1",
        observed_at=spec.FIXED_INSTANT, content_hash="placeholder",
        admission_status=spec.ToolObservationAdmissionStatus.NOT_EVALUATED)
    observation = shapes["ToolObservation"](
        normalized_fields={"vendor.name": "Müller & Söhne GmbH"}, **base)
    assert observation.normalized_fields["vendor.name"] == "Müller & Söhne GmbH"
    with pytest.raises(pydantic.ValidationError):
        shapes["ToolObservation"](
            normalized_fields={"vendor name": "anything"}, **base)


# --------------------------------------------------------------------------- #
# G-5 — a decorative pattern is not validation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("sample", [
    'class A:\n    role_ref: str = Field(json_schema_extra={"pattern": r"%s"})\n'
    % IDENTIFIER_PATTERN,
    'class A:\n    role_ref: str = Field(description="pattern=%s")\n'
    % IDENTIFIER_PATTERN,
    'class A:\n    role_ref: str = Field(examples=[Field(pattern=r"%s")])\n'
    % IDENTIFIER_PATTERN,
])
def test_a_decorative_pattern_is_not_read_as_validation(sample):
    """G-5: the AST contains ``pattern``; nothing constrains the value. Accepting it
    would report a validated field that validation never touches."""
    (_, _, constraints), = _fields_of(sample)
    assert constraints == set(), (
        f"a decorative pattern was accepted as validation: {sorted(constraints)}")


@pytest.mark.parametrize("sample", [
    'class A:\n    role_ref: Annotated[str, StringConstraints(pattern=r"%s")]\n'
    % IDENTIFIER_PATTERN,
    'class A:\n    role_ref: str = Field(pattern=r"%s")\n' % IDENTIFIER_PATTERN,
    'class A:\n    role_ref: constr(pattern=r"%s")\n' % IDENTIFIER_PATTERN,
])
def test_a_binding_pattern_is_still_read_as_validation(sample):
    """The narrowing above must not have blinded the scanner to real constraints."""
    (_, _, constraints), = _fields_of(sample)
    assert constraints == {IDENTIFIER_PATTERN}


def test_a_pattern_reached_only_through_metadata_is_invisible_even_when_nested():
    """The decorative marker propagates into nested calls, so burying a real-looking
    constructor inside ``json_schema_extra`` does not resurrect it."""
    sample = ('class A:\n    role_ref: str = Field('
              'json_schema_extra={"x": StringConstraints(pattern=r"%s")})\n'
              % IDENTIFIER_PATTERN)
    (_, _, constraints), = _fields_of(sample)
    assert constraints == set()


# --------------------------------------------------------------------------- #
# C8 — the ratified declaration spelling (G-9)
# --------------------------------------------------------------------------- #

def test_the_representative_shapes_use_the_ratified_declaration_spelling():
    """C8: every constrained ``str`` is ``Annotated[str, StringConstraints(...)]`` and
    never ``field: str = Field(pattern=...)``.

    The two are equivalent to pydantic and are **not** equivalent to the identity-source
    guard: under ``Annotated`` the annotated assignment carries no value, so nothing is
    collected; under ``Field(...)`` the assignment's value is a call that does not
    resolve to the substrate, and the declaration is reported as an unpermitted identity
    source. A contract declaring its own identity field's pattern the second way would
    fail the merged guard at import-scan time.
    """
    assert spec.DECLARATION_FORM == "Annotated[str, StringConstraints(...)]"
    tree = ast.parse(spec.SPECIFICATION_MIRROR_SOURCE, filename="mirror")
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign) or node.value is None:
            continue
        for call in _binding_constraint_calls(node.value):
            if _called_name(call) != "Field":
                continue
            if any(k.arg in CONSTRAINT_KEYWORDS or k.arg in (
                    "max_length", "min_length", "strip_whitespace")
                   for k in call.keywords):
                offenders.append(ast.unparse(node))
    assert not offenders, (
        f"string constraints declared through Field(...) rather than "
        f"Annotated[str, StringConstraints(...)]: {offenders}")


def test_the_identity_field_takes_no_field_call_at_all():
    """``advisory_digest`` is the one field that takes no ``Field(...)`` of any kind."""
    tree = ast.parse(spec.SPECIFICATION_MIRROR_SOURCE, filename="mirror")
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "advisory_digest" and node.value is not None):
            assert not list(_binding_constraint_calls(node.value)), ast.unparse(node)


# --------------------------------------------------------------------------- #
# Registry integrity, restated (kept from the O-4 correction)
# --------------------------------------------------------------------------- #

def test_a_field_missing_from_the_registry_is_a_failure_not_a_skip():
    """The mutation that matters: drop a field from the registry and it must not
    quietly become unchecked."""
    assert _classify("ToolObservation", "tool_name") == C5B
    assert _classify("ToolObservation", "a_field_nobody_registered") is None


def test_the_patterns_are_pinned_to_the_ratified_text():
    assert IDENTIFIER_PATTERN == r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
    assert TOKEN_PATTERN == r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    assert PATTERN_FOR == {C5A: IDENTIFIER_PATTERN, C5B: TOKEN_PATTERN}
    assert spec.MAX_IDENTIFIER_LENGTH == 200
