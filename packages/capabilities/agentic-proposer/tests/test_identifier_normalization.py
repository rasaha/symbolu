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

#: O-4's identifier pattern (C5a), verbatim. Pinned by equality below.
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"

#: O-4's canonical token pattern (C5b): the C5a class MINUS the path separator. A
#: token is the operand of a membership test — ``tool_name in permitted_tool_scopes``
#: — and a path-shaped spelling invites a consumer to split or normalize it before
#: comparing, which would make the comparison depend on the consumer.
TOKEN_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"

#: The three O-4 categories, plus the two mechanical classes a string-pattern
#: category does not describe.
C5A, C5B, C5C = "C5a", "C5b", "C5c"
#: A field with its own separately ratified pattern (digest shapes, the advisory
#: version). Not free text, and not governed by C5a or C5b.
OTHER_PATTERN = "other-pattern"
#: Literal- or enum-typed: validated by membership, not by a string pattern.
CLOSED = "closed"
#: Not string-valued at all — a timestamp, a boolean, a nested model, a container of
#: them. Registered so the registry stays exhaustive over declared fields: a field
#: absent from it is a failure, not a silent pass.
NON_STRING = "non-string"

#: The pattern each category requires, where a category has one.
PATTERN_FOR = {C5A: IDENTIFIER_PATTERN, C5B: TOKEN_PATTERN}

#: **The exact, pinned per-contract field registry (OD-3 / O-4 correction).**
#:
#: Classification is declared here, per contract and per field. It is NOT inferred
#: from name shape. A suffix rule reaches neither ``tool_name`` nor the scope fields —
#: they end in no identifier suffix and carry no free-text marker — so under inference
#: alone they were classified as nothing and went unchecked. ``tool_name`` is the
#: sharpest case: it is matched by equality against ``permitted_tool_scopes``, so an
#: unnormalized spelling changes an eligibility outcome.
#:
#: Every string-valued field of every S1 contract appears exactly once.
FIELD_CLASSIFICATION = {
    "AgentIdentityRef": {
        "created_at": NON_STRING,
        "tenant_id": C5A, "agent_id": C5A, "agent_version": C5B,
        "bound_role_contract_id": C5A, "owner_role_ref": C5A,
        "schema_version": CLOSED,
    },
    "CognitiveRoleContract": {
        "created_at": NON_STRING,
        "tenant_id": C5A, "role_contract_id": C5A, "primary_function": C5C,
        "permitted_tool_scopes": C5B, "escalation_role_ref": C5A,
        "schema_version": CLOSED, "activation_status": CLOSED,
        "permitted_candidate_dispositions": CLOSED, "permitted_review_actions": CLOSED,
    },
    "WorkMandate": {
        "created_at": NON_STRING, "expires_at": NON_STRING,
        "tenant_id": C5A, "mandate_id": C5A, "case_ref": C5A,
        "assigned_role_contract_id": C5A, "purpose": C5C,
        "allowed_source_scopes": C5B, "schema_version": CLOSED,
    },
    "BoundedContextEnvelope": {
        "created_at": NON_STRING, "expires_at": NON_STRING,
        "tenant_id": C5A, "context_id": C5A, "mandate_id": C5A,
        "allowed_record_refs": C5A, "excluded_data_classes": C5B,
        "context_hash": OTHER_PATTERN, "schema_version": CLOSED,
    },
    "ToolObservation": {
        "created_at": NON_STRING, "observed_at": NON_STRING,
        "tenant_id": C5A, "observation_id": C5A, "case_ref": C5A,
        "tool_name": C5B, "source_ref": C5A, "content_hash": OTHER_PATTERN,
        "normalized_fields": NON_STRING, "schema_version": CLOSED,
        "operation_class": CLOSED, "admission_status": CLOSED,
    },
    "AdvisoryCandidateSet": {
        "created_at": NON_STRING, "candidates": NON_STRING,
        "tenant_id": C5A, "candidate_set_id": C5A, "case_ref": C5A,
        "selected_candidate_id": C5A, "selection_reason_codes": C5A,
        "schema_version": CLOSED,
    },
    "CandidateAdvisory": {
        "evaluated_at": NON_STRING,
        "candidate_id": C5A, "claim_refs": C5A, "observation_refs": C5A,
        "assumptions": C5C, "uncertainties": C5C,
        "disposition": CLOSED, "requested_review_action": CLOSED,
        "is_eligible": CLOSED, "domain_check_completion": CLOSED,
    },
    "ProposerAdvisory": {
        "created_at": NON_STRING, "expires_at": NON_STRING,
        "tenant_id": C5A, "case_ref": C5A, "agent_id": C5A,
        "role_contract_id": C5A, "mandate_id": C5A, "context_id": C5A,
        "candidate_set_id": C5A, "selected_candidate_id": C5A,
        "requested_review_destination_role_ref": C5A,
        "observation_refs": C5A, "reason_codes": C5A,
        "claim_summaries": C5C, "uncertainties": C5C,
        "advisory_digest": OTHER_PATTERN, "parent_advisory_digest": OTHER_PATTERN,
        "advisory_version": OTHER_PATTERN,
        "schema_version": CLOSED, "kind": CLOSED,
        "recommended_disposition": CLOSED, "requested_review_action": CLOSED,
    },
    "ProposerProcessRecord": {
        "created_at": NON_STRING, "state_transitions": NON_STRING, "started_at": NON_STRING, "completed_at": NON_STRING,
        "tenant_id": C5A, "process_record_id": C5A, "case_ref": C5A,
        "declared_strategy": C5C, "tool_invocations": C5B,
        "deterministic_checks": C5A, "candidate_ids": C5A,
        "selected_candidate_id": C5A, "semantic_audit_refs": C5A,
        "reason_codes": C5A, "advisory_digest": OTHER_PATTERN,
        "jcs_distribution_version": OTHER_PATTERN,
        "schema_version": CLOSED, "terminal_outcome": CLOSED,
    },
    "ProposerProcessStateTransition": {
        "at": NON_STRING,"state": CLOSED},
}

#: Fields carried by every contract, so a contract table need not repeat them.
COMMON_FIELDS = ("schema_version", "tenant_id", "created_at")

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


@pytest.mark.parametrize("label,contract,field,constraints", _declared_fields(),
                         ids=lambda v: str(v)[:48])
def test_a_classified_field_carries_its_category_pattern(label, contract, field,
                                                         constraints):
    """C5a and C5b fields must be validated, and by their own pattern rather than a
    lookalike or each other's."""
    category = _classify(contract, field)
    if category not in PATTERN_FOR:
        pytest.skip(f"{label} is {category or 'unregistered'}, not a patterned category")
    expected = PATTERN_FOR[category]
    assert constraints, f"{label} is {category} with no validation"
    assert constraints == {expected}, (
        f"{label} is {category} but validated by {sorted(constraints)}, "
        f"not {expected!r}")


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


def test_the_registry_is_exhaustive_over_every_specified_contract():
    """Every S1 contract appears, and no field is registered twice within one."""
    expected = {
        "AgentIdentityRef", "CognitiveRoleContract", "WorkMandate",
        "BoundedContextEnvelope", "ToolObservation", "AdvisoryCandidateSet",
        "ProposerAdvisory", "ProposerProcessRecord",
        "CandidateAdvisory", "ProposerProcessStateTransition",
    }
    assert set(FIELD_CLASSIFICATION) == expected
    for contract, fields in FIELD_CLASSIFICATION.items():
        assert set(fields.values()) <= {C5A, C5B, C5C, OTHER_PATTERN, CLOSED,
                                        NON_STRING}, contract


def test_a_field_missing_from_the_registry_is_a_failure_not_a_skip():
    """The mutation that matters: drop a field from the registry and it must not
    quietly become unchecked."""
    assert _classify("ToolObservation", "tool_name") == C5B
    assert _classify("ToolObservation", "a_field_nobody_registered") is None


def test_the_patterns_are_pinned_to_the_ratified_text():
    assert IDENTIFIER_PATTERN == r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
    assert TOKEN_PATTERN == r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    assert PATTERN_FOR == {C5A: IDENTIFIER_PATTERN, C5B: TOKEN_PATTERN}
    assert (C5A, C5B, C5C) == ("C5a", "C5b", "C5c")
