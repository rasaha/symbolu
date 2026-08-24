"""O-1's null-coupling on the selection-dependent fields, enforced mechanically.

Owner decision O-1 makes three fields nullable and binds them to one selector:

* ``recommended_disposition: CandidateDisposition | None``
* ``requested_review_action: ReviewAction | None``
* ``requested_review_destination_role_ref: str | None``

When ``selected_candidate_id`` is ``None``, all three are ``None``. The coupling is
what keeps the advisory honest: a disposition or a routing request standing next to
no selected candidate is a recommendation about nothing, and a consumer cannot tell
whether the selection was lost or the routing was invented.

**The coupling is scoped to one bearer (OD-3).** It applies to ``ProposerAdvisory``
and to nothing else. ``requested_review_action`` also appears on ``CandidateAdvisory``,
where it is the candidate's **own** proposed routing: required, non-null, and not
selection-dependent at all. A guard that matched the field name globally would demand a
selector on the candidate record and force that field nullable, which contradicts the
ratified contract. The bearer, the selector and the three dependents are therefore
pinned together as one registry, and a class that merely shares a field name is not
touched.

Like the other S1 guards, this one is written to hold **before** the contract exists.
The parts that need no contract — the reference model of the rule, and the scanners —
are checked today. The parts that need the fields arm themselves the moment the bearer
declares one, and then require, of that class:

* the selector is declared on the same class, so the coupling is local and checkable;
* every dependent field's annotation admits ``None``;
* the coupling is enforced by code in that class, not left to prose;
* and, where the type can be constructed with everything unset, a mismatched
  combination is actually rejected at runtime.

**What this guard does not reach.** O-1's second clause — that a dependent field
matches the selected candidate and that candidate's permitted routing — is a
statement about values a stage that has candidates produces. Nothing in this package
has candidates, so nothing here can check it. It is recorded as an obligation on that
stage in the readiness ADR rather than silently treated as covered.
"""
from __future__ import annotations

import ast
import pathlib
import typing

import pytest

import ugence_agentic_proposer as ap

SRC = pathlib.Path(ap.__file__).resolve().parent

#: The ONE contract the O-1 coupling binds (OD-3). Not a name pattern: an exact
#: bearer. ``CandidateAdvisory.requested_review_action`` shares a name with a dependent
#: field and is a different field — required, non-null, the candidate's own routing.
SELECTION_BEARER = "ProposerAdvisory"
#: The selector every dependent field is bound to, on the bearer.
SELECTION_FIELD = "selected_candidate_id"
#: The three fields O-1 makes nullable and couples to the selector, on the bearer.
DEPENDENT_FIELDS = (
    "recommended_disposition",
    "requested_review_action",
    "requested_review_destination_role_ref",
)
#: The pinned registry, asserted by equality below so it cannot be widened to other
#: contracts or narrowed to fewer fields without a self-test failing.
SELECTION_COUPLING = {
    SELECTION_BEARER: {"selector": SELECTION_FIELD, "dependents": DEPENDENT_FIELDS},
}
#: Contracts that declare a name matching a dependent field but are NOT bearers. Named
#: so the exclusion is deliberate and visible rather than a silent consequence.
NON_BEARERS_SHARING_A_FIELD_NAME = ("CandidateAdvisory",)
#: Names that make a class member the enforcement of a rule rather than a datum:
#: a pydantic validator, a dataclass hook, or a plainly named check.
ENFORCEMENT_MARKERS = (
    "model_validator", "field_validator", "root_validator", "validator",
    "__post_init__", "__attrs_post_init__", "check", "validate",
)


def _sources():
    return sorted(SRC.rglob("*.py"))


# --------------------------------------------------------------------------- #
# Scanners
# --------------------------------------------------------------------------- #

def _admits_none(annotation):
    """Whether an annotation declares that ``None`` is an allowed value.

    ``Optional[X]``, ``X | None``, ``Union[X, None]``, and the same written as a
    string forward reference. A bare ``X`` does not, and neither does ``Any``: O-1
    asks for a declared nullability, and a field that merely happens to accept
    anything declares nothing.
    """
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return False
    names = {n.id for n in ast.walk(annotation) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(annotation) if isinstance(n, ast.Attribute)}
    if "Optional" in names:
        return True
    if any(isinstance(n, ast.Constant) and n.value is None for n in ast.walk(annotation)):
        return True
    return False


def _annotated_fields(node):
    """``{field: annotation node}`` for one class body."""
    return {stmt.target.id: stmt.annotation for stmt in node.body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)}


def _classes_with_dependent_fields(source, filename="<sample>"):
    """Every **bearer** class in ``source`` declaring a selection-dependent field.

    Bearer-scoped by OD-3: a class is examined only when its name is in
    ``SELECTION_COUPLING``. A non-bearer that happens to declare a field of the same
    name — ``CandidateAdvisory.requested_review_action`` — is not a selection-dependent
    field and is deliberately not reached.
    """
    tree = ast.parse(source, filename=filename)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name not in SELECTION_COUPLING:
            continue
        fields = _annotated_fields(node)
        if set(fields) & set(SELECTION_COUPLING[node.name]["dependents"]):
            found.append((node, fields))
    return found


def _unconditionally_typed_dependents(fields):
    """Dependent fields in ``fields`` whose annotation does not admit ``None``."""
    return sorted(name for name in DEPENDENT_FIELDS
                  if name in fields and not _admits_none(fields[name]))


def _enforces_the_coupling(node):
    """Whether a class body carries code that reads the selector and the dependents.

    A validator, hook or check that names the selector and every dependent field it
    declares. Prose in a docstring is not enforcement, so only executable members
    count; the names are read from the member's own source.
    """
    declared = set(_annotated_fields(node)) & set(DEPENDENT_FIELDS)
    for stmt in node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorators = {ast.unparse(d) for d in stmt.decorator_list}
        marked = (any(marker in stmt.name for marker in ENFORCEMENT_MARKERS)
                  or any(marker in text for text in decorators
                         for marker in ENFORCEMENT_MARKERS))
        if not marked:
            continue
        body = "\n".join(ast.unparse(child) for child in stmt.body)
        if SELECTION_FIELD in body and all(name in body for name in declared):
            return True
    return False


# --------------------------------------------------------------------------- #
# Scanner self-tests
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("annotation", [
    "Optional[CandidateDisposition]",
    "CandidateDisposition | None",
    "None | CandidateDisposition",
    "Union[CandidateDisposition, None]",
    "typing.Optional[str]",
    "'CandidateDisposition | None'",
    '"Optional[str]"',
])
def test_the_annotation_reader_sees_a_declared_null(annotation):
    assert _admits_none(ast.parse(annotation, mode="eval").body)


@pytest.mark.parametrize("annotation", [
    "CandidateDisposition",
    "str",
    "Any",
    "list[str]",
    "'CandidateDisposition'",
])
def test_the_annotation_reader_rejects_an_undeclared_null(annotation):
    assert not _admits_none(ast.parse(annotation, mode="eval").body)


def test_the_class_scanner_finds_a_dependent_field():
    found = _classes_with_dependent_fields(
        "class A:\n    unrelated: str\n\n"
        "class ProposerAdvisory:\n    selected_candidate_id: str | None\n"
        "    recommended_disposition: CandidateDisposition | None\n")
    assert [node.name for node, _ in found] == ["ProposerAdvisory"]


def test_the_class_scanner_flags_an_unconditionally_typed_dependent():
    (_, fields), = _classes_with_dependent_fields(
        "class ProposerAdvisory:\n    selected_candidate_id: str | None\n"
        "    recommended_disposition: CandidateDisposition\n"
        "    requested_review_action: ReviewAction | None\n")
    assert _unconditionally_typed_dependents(fields) == ["recommended_disposition"]


COUPLED_SAMPLE = (
    "class ProposerAdvisory:\n"
    "    selected_candidate_id: str | None\n"
    "    recommended_disposition: CandidateDisposition | None\n"
    "\n"
    "    @model_validator(mode='after')\n"
    "    def _check_selection(self):\n"
    "        if self.selected_candidate_id is None and self.recommended_disposition is not None:\n"
    "            raise ValueError('dependent field set without a selected candidate')\n"
    "        return self\n"
)

UNCOUPLED_SAMPLES = (
    # No enforcement at all: the rule lives only in the docstring.
    "class ProposerAdvisory:\n"
    "    '''When selected_candidate_id is None, recommended_disposition is None.'''\n"
    "    selected_candidate_id: str | None\n"
    "    recommended_disposition: CandidateDisposition | None\n",
    # A validator that never reads the selector: it cannot be checking the coupling.
    "class ProposerAdvisory:\n"
    "    selected_candidate_id: str | None\n"
    "    recommended_disposition: CandidateDisposition | None\n"
    "\n"
    "    @model_validator(mode='after')\n"
    "    def _check(self):\n"
    "        if self.recommended_disposition is None:\n"
    "            raise ValueError('x')\n"
    "        return self\n",
    # A validator that reads the selector but ignores one declared dependent.
    "class ProposerAdvisory:\n"
    "    selected_candidate_id: str | None\n"
    "    recommended_disposition: CandidateDisposition | None\n"
    "    requested_review_action: ReviewAction | None\n"
    "\n"
    "    @model_validator(mode='after')\n"
    "    def _check(self):\n"
    "        if self.selected_candidate_id is None and self.recommended_disposition:\n"
    "            raise ValueError('x')\n"
    "        return self\n",
)


def test_the_coupling_scanner_sees_an_enforced_coupling():
    (node, _), = _classes_with_dependent_fields(COUPLED_SAMPLE)
    assert _enforces_the_coupling(node)


@pytest.mark.parametrize("sample", UNCOUPLED_SAMPLES, ids=("prose", "no-selector", "partial"))
def test_the_coupling_scanner_rejects_an_unenforced_coupling(sample):
    (node, _), = _classes_with_dependent_fields(sample)
    assert not _enforces_the_coupling(node)


# --------------------------------------------------------------------------- #
# The rule itself, on a reference implementation
# --------------------------------------------------------------------------- #

def _reference_model():
    """A model implementing O-1, so the rule is stated executably rather than in prose.

    This is not the contract and does not stand in for it. It exists so the
    behavioural assertions below run against something today, and so the shape the
    contract must have is written down in code that is executed.
    """
    pydantic = pytest.importorskip("pydantic")

    class Advisory(pydantic.BaseModel):
        selected_candidate_id: typing.Optional[str] = None
        recommended_disposition: typing.Optional[str] = None
        requested_review_action: typing.Optional[str] = None
        requested_review_destination_role_ref: typing.Optional[str] = None

        @pydantic.model_validator(mode="after")
        def _dependents_follow_the_selection(self):
            """Both directions. Presence with presence, absence with absence.

            This is the LOCAL invariant only. It proves nothing about any referenced
            candidate set: this model holds no set and no candidates, and a validator
            that claimed otherwise would be asserting what it cannot see.
            """
            if self.selected_candidate_id is None:
                set_anyway = [name for name in DEPENDENT_FIELDS
                              if getattr(self, name) is not None]
                if set_anyway:
                    raise ValueError(f"set without a selected candidate: {set_anyway}")
            else:
                missing = [name for name in DEPENDENT_FIELDS
                           if getattr(self, name) is None]
                if missing:
                    raise ValueError(f"selected candidate with no {missing}")
            return self

    return Advisory


def test_the_reference_model_permits_an_unselected_advisory():
    assert _reference_model()().selected_candidate_id is None


@pytest.mark.parametrize("field", DEPENDENT_FIELDS)
def test_the_reference_model_rejects_a_dependent_without_a_selection(field):
    pydantic = pytest.importorskip("pydantic")
    with pytest.raises(pydantic.ValidationError):
        _reference_model()(**{field: "X"})


def test_the_reference_model_permits_dependents_with_a_selection():
    model = _reference_model()(
        selected_candidate_id="cand-1",
        recommended_disposition="RECOMMEND_WITHHOLD",
        requested_review_action="ROUTE_APPROVAL_BUNDLE",
        requested_review_destination_role_ref="role:approver",
    )
    assert model.recommended_disposition == "RECOMMEND_WITHHOLD"


# --------------------------------------------------------------------------- #
# O-1, enforced over the package as it stands
# --------------------------------------------------------------------------- #

def _declared_dependent_classes():
    """Every class in ``src`` declaring a selection-dependent field, if any yet do."""
    found = []
    for path in _sources():
        for node, fields in _classes_with_dependent_fields(
                path.read_text(encoding="utf-8"), filename=str(path)):
            found.append((f"{path.name}:{node.name}", node, fields))
    return found


@pytest.mark.parametrize("label,node,fields", _declared_dependent_classes(),
                         ids=lambda v: str(v)[:48])
def test_a_dependent_field_is_declared_with_its_selector(label, node, fields):
    assert SELECTION_FIELD in fields, (
        f"{label} declares a selection-dependent field without {SELECTION_FIELD}: "
        "the coupling cannot be checked on this class")
    assert _admits_none(fields[SELECTION_FIELD]), (
        f"{label}: {SELECTION_FIELD} must itself admit None")


@pytest.mark.parametrize("label,node,fields", _declared_dependent_classes(),
                         ids=lambda v: str(v)[:48])
def test_every_dependent_field_admits_none(label, node, fields):
    offenders = _unconditionally_typed_dependents(fields)
    assert not offenders, f"{label}: not nullable: {offenders}"


@pytest.mark.parametrize("label,node,fields", _declared_dependent_classes(),
                         ids=lambda v: str(v)[:48])
def test_the_coupling_is_enforced_in_code(label, node, fields):
    assert _enforces_the_coupling(node), (
        f"{label} declares selection-dependent fields but enforces no coupling to "
        f"{SELECTION_FIELD}")


def _live_annotations(attr):
    annotations = dict(getattr(attr, "__annotations__", {}) or {})
    model_fields = getattr(attr, "model_fields", None)
    if isinstance(model_fields, dict):
        annotations.update({n: f.annotation for n, f in model_fields.items()})
    return annotations


def _live_types_with_dependent_fields():
    """The live bearer types only (OD-3). ``__name__`` is used, not the export name, so
    a bearer re-exported under an alias is still reached and a non-bearer aliased to a
    bearer's export name is not."""
    found = []
    for name in dir(ap):
        attr = getattr(ap, name)
        if not isinstance(attr, type) or getattr(attr, "__name__", None) not in SELECTION_COUPLING:
            continue
        annotations = _live_annotations(attr)
        if set(annotations) & set(SELECTION_COUPLING[attr.__name__]["dependents"]):
            found.append((name, attr, annotations))
    return found


def _live_non_bearers_sharing_a_field_name():
    """Live types named in ``NON_BEARERS_SHARING_A_FIELD_NAME`` that actually exist."""
    found = []
    for name in dir(ap):
        attr = getattr(ap, name)
        if isinstance(attr, type) and getattr(attr, "__name__", None) in NON_BEARERS_SHARING_A_FIELD_NAME:
            found.append((name, attr, _live_annotations(attr)))
    return found


@pytest.mark.parametrize("name,model,annotations", _live_types_with_dependent_fields(),
                         ids=lambda v: str(v)[:40])
def test_a_live_dependent_field_accepts_none(name, model, annotations):
    """The runtime twin: the declared type must actually admit ``None``."""
    for field in DEPENDENT_FIELDS:
        if field not in annotations:
            continue
        assert type(None) in typing.get_args(annotations[field]), (
            f"{name}.{field} does not accept None at runtime")


@pytest.mark.parametrize("name,model,annotations", _live_types_with_dependent_fields(),
                         ids=lambda v: str(v)[:40])
def test_a_live_model_rejects_a_dependent_without_a_selection(name, model, annotations):
    """Behaviour, not annotation. Runs only where the type can be built with nothing
    set — otherwise the required fields are unknown here and the source-level
    coupling check is what binds."""
    try:
        model()
    except Exception:  # noqa: BLE001 - required fields unknown; the source scan binds
        pytest.skip(f"{name} cannot be constructed with everything unset")
    for field in DEPENDENT_FIELDS:
        if field not in annotations:
            continue
        with pytest.raises(Exception):  # noqa: B017 - any rejection satisfies O-1
            model(**{field: "X"})


def test_the_coupling_is_pinned_to_the_ratified_fields():
    """O-1's field names, asserted by equality so the set cannot be quietly reduced."""
    assert SELECTION_FIELD == "selected_candidate_id"
    assert DEPENDENT_FIELDS == (
        "recommended_disposition",
        "requested_review_action",
        "requested_review_destination_role_ref",
    )


def test_the_bearer_registry_is_pinned():
    """OD-3's bearer scoping, asserted by equality.

    Narrowing the registry (dropping the bearer), redirecting it (renaming the bearer)
    or widening it (adding a contract) all fail here, so the scoping cannot drift into
    either a global name match or a disarmed guard.
    """
    assert SELECTION_BEARER == "ProposerAdvisory"
    assert SELECTION_COUPLING == {
        "ProposerAdvisory": {
            "selector": "selected_candidate_id",
            "dependents": (
                "recommended_disposition",
                "requested_review_action",
                "requested_review_destination_role_ref",
            ),
        },
    }
    assert NON_BEARERS_SHARING_A_FIELD_NAME == ("CandidateAdvisory",)
    assert set(SELECTION_COUPLING) & set(NON_BEARERS_SHARING_A_FIELD_NAME) == set()


# --------------------------------------------------------------------------- #
# OD-3 mutation probes — the bearer scoping, and the coupling in both directions
# --------------------------------------------------------------------------- #

#: A bearer declaring the selector and all three dependents.
BEARER_SAMPLE = (
    "class ProposerAdvisory:\n"
    "    selected_candidate_id: str | None\n"
    "    recommended_disposition: Disposition | None\n"
    "    requested_review_action: ReviewAction | None\n"
    "    requested_review_destination_role_ref: str | None\n"
    "    @model_validator(mode='after')\n"
    "    def _couple(self):\n"
    "        if self.selected_candidate_id is None:\n"
    "            assert self.recommended_disposition is None\n"
    "            assert self.requested_review_action is None\n"
    "            assert self.requested_review_destination_role_ref is None\n"
    "        return self\n"
)


def test_the_relationship_arms_on_the_bearer():
    """The four-field relationship is seen on ``ProposerAdvisory``."""
    found = _classes_with_dependent_fields(BEARER_SAMPLE)
    assert [node.name for node, _ in found] == ["ProposerAdvisory"]
    _, fields = found[0]
    assert SELECTION_FIELD in fields
    assert set(DEPENDENT_FIELDS) <= set(fields)


def test_the_bearer_without_its_selector_fails():
    """A bearer declaring dependents but no selector is caught."""
    sample = "class ProposerAdvisory:\n    recommended_disposition: Disposition | None\n"
    found = _classes_with_dependent_fields(sample)
    assert found, "the guard did not arm on the bearer"
    _, fields = found[0]
    assert SELECTION_FIELD not in fields


@pytest.mark.parametrize("other", NON_BEARERS_SHARING_A_FIELD_NAME)
def test_an_identically_named_field_on_another_class_is_not_reached(other):
    """OD-3. ``CandidateAdvisory.requested_review_action`` is the candidate's own
    required routing. Sharing a name with a dependent field does not make it one, and
    the guard must not demand a selector or nullability of it."""
    sample = (
        f"class {other}:\n"
        "    candidate_id: str\n"
        "    requested_review_action: ReviewAction\n"
    )
    assert _classes_with_dependent_fields(sample) == [], (
        f"{other} was treated as a selection-dependent bearer")


def test_a_non_bearer_and_a_bearer_in_one_module_are_told_apart():
    """Both in one file: only the bearer arms."""
    found = _classes_with_dependent_fields(
        "class CandidateAdvisory:\n    requested_review_action: ReviewAction\n"
        + BEARER_SAMPLE)
    assert [node.name for node, _ in found] == ["ProposerAdvisory"]


def test_a_renamed_bearer_registry_stops_seeing_the_bearer():
    """The scoping is load-bearing: point the registry elsewhere and the real bearer
    goes unexamined. This is why ``test_the_bearer_registry_is_pinned`` exists."""
    import unittest.mock
    with unittest.mock.patch.dict(
            "tests.test_selection_dependent_fields.SELECTION_COUPLING",
            {"SomethingElse": SELECTION_COUPLING[SELECTION_BEARER]}, clear=True):
        assert _classes_with_dependent_fields(BEARER_SAMPLE) == []


def test_null_selector_with_all_dependents_null_passes():
    model = _reference_model()
    assert model().selected_candidate_id is None


def test_null_selector_with_a_non_null_dependent_fails_at_runtime():
    model = _reference_model()
    for field in DEPENDENT_FIELDS:
        with pytest.raises(Exception):
            model(**{field: "X"})


def test_non_null_selector_with_all_dependents_non_null_passes_locally():
    model = _reference_model()
    built = model(selected_candidate_id="cand-1",
                  **{field: "X" for field in DEPENDENT_FIELDS})
    assert built.selected_candidate_id == "cand-1"


@pytest.mark.parametrize("omitted", DEPENDENT_FIELDS)
def test_non_null_selector_with_any_null_dependent_fails(omitted):
    model = _reference_model()
    values = {field: "X" for field in DEPENDENT_FIELDS if field != omitted}
    with pytest.raises(Exception):
        model(selected_candidate_id="cand-1", **values)


@pytest.mark.parametrize("name,model,annotations", _live_non_bearers_sharing_a_field_name(),
                         ids=lambda v: str(v)[:40])
def test_a_live_non_bearer_keeps_its_field_required_and_non_null(name, model, annotations):
    """Arms with the contract. ``CandidateAdvisory.requested_review_action`` must stay
    required and non-null — the opposite of what the dependent fields require."""
    annotation = annotations.get("requested_review_action")
    if annotation is None:
        pytest.skip(f"{name} declares no requested_review_action")
    assert type(None) not in typing.get_args(annotation), (
        f"{name}.requested_review_action must not admit None: it is the candidate's "
        "own required routing, not a selection-dependent field")


def test_the_local_rule_is_not_a_correspondence_claim():
    """The reference model enforces presence-with-presence and absence-with-absence and
    nothing else. It holds no candidate set, so it cannot and does not establish that a
    dependent value matches the selected candidate — that is the builder's obligation
    and the replay verifier's, recorded in the readiness ADR."""
    model = _reference_model()
    built = model(selected_candidate_id="does-not-resolve-anywhere",
                  **{field: "arbitrary" for field in DEPENDENT_FIELDS})
    assert built.recommended_disposition == "arbitrary"
