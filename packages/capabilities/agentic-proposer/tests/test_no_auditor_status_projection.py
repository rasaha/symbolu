"""D6's standing rule, enforced mechanically: no auditor status becomes an outcome.

Owner decision D6 reserves ``INDETERMINATE`` **by position**, and carries a standing
rule with a wider reach than that one term: no ``SemanticAuditorFindingStatus`` value
may be copied, mapped, coerced or defaulted into a ``TerminalOutcome`` or
``CandidateDisposition`` field. ``CONSISTENT`` becoming a terminal outcome would
breach it exactly as ``INDETERMINATE`` would.

The ADR records that obligation as ``[R]``: S1 must reject any such assignment or
conversion, and the test must land with the first outcome- or disposition-typed
field. This module is that test. It has two halves and neither waits on the other:

* a SOURCE half that rejects the shapes a projection takes — a conversion call, a
  lookup table, a union annotation, a status-valued assignment to an outcome field,
  a status-in/outcome-out function. It runs today, over today's sources.
* a RUNTIME half that is parametrized over every outcome- or disposition-typed field
  the package actually defines, and asserts each rejects every auditor status. It is
  empty only while no such field exists, and arms itself the moment one lands —
  which is what "lands with the first such field" requires of a test written before
  the field it guards.

The source half is self-tested against synthetic samples below, so a detector that
silently stopped matching would fail here rather than report a clean scan.
"""
from __future__ import annotations

import ast
import dataclasses
import enum
import importlib
import pathlib
import pkgutil
import typing

import pydantic
import pytest

import ugence_agentic_proposer as ap
from ugence_agentic_proposer.vocabulary import (
    CandidateDisposition,
    SemanticAuditorFindingStatus,
    TerminalOutcome,
)

SRC = pathlib.Path(ap.__file__).resolve().parent

#: The two positions D6 reserves. A status reaching either one is the violation.
RESERVED_POSITION_TYPES = ("TerminalOutcome", "CandidateDisposition")
STATUS_TYPE = "SemanticAuditorFindingStatus"


#: The three vocabularies this module tracks, by their canonical names.
TRACKED_TYPES = RESERVED_POSITION_TYPES + (STATUS_TYPE,)


def _aliases(tree):
    """Map every local binding back to the canonical type name it refers to.

    A projection written through an alias is the same projection. ``import ... as T``
    and ``from ... import TerminalOutcome as T`` both bind ``T`` to
    ``TerminalOutcome``; without this, the scan sees an untracked name and reports a
    clean module. Module bindings (``from . import vocabulary``) need no entry —
    ``vocabulary.TerminalOutcome`` is resolved by attribute name below.
    """
    bound = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in TRACKED_TYPES:
                    bound[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                tail = alias.name.split(".")[-1]
                if tail in TRACKED_TYPES:
                    bound[alias.asname or tail] = tail
    return bound


def _resolve(node, aliases):
    """The canonical type name ``node`` denotes, or "" if it denotes none of them.

    Resolves three spellings of the same reference: the bare name, an alias bound by
    an import, and an attribute access on a module (``vocabulary.TerminalOutcome``).
    """
    if isinstance(node, ast.Name):
        canonical = aliases.get(node.id, node.id)
        return canonical if canonical in TRACKED_TYPES else ""
    if isinstance(node, ast.Attribute):
        return node.attr if node.attr in TRACKED_TYPES else ""
    return ""


def _names(node, aliases=None):
    """Every canonical type name referenced anywhere inside ``node``.

    Aliased and module-qualified references resolve to the same canonical name as
    the bare one, so every shape below sees through both.
    """
    aliases = {} if aliases is None else aliases
    found = set()
    for child in ast.walk(node):
        canonical = _resolve(child, aliases)
        if canonical:
            found.add(canonical)
    return found


def _refers_to_status(node, aliases=None):
    return STATUS_TYPE in _names(node, aliases)


def _refers_to_reserved_position(node, aliases=None):
    return bool(_names(node, aliases) & set(RESERVED_POSITION_TYPES))


def _called_name(call, aliases=None):
    return _resolve(call.func, {} if aliases is None else aliases)


def _reserved_member_accesses(scope, aliases):
    """Reads of a member OF a reserved vocabulary: ``TerminalOutcome.ABSTAIN``,
    ``T[name]``, ``vocabulary.CandidateDisposition.DEFER``.

    Constructing the value is only one way to reach it. Selecting a member reaches
    the same place and is how a projection is most naturally written — an if/elif
    ladder or a ``return TerminalOutcome.ABSTAIN`` guarded by a status check never
    calls the enum at all.
    """
    found = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Attribute):
            owner = _resolve(node.value, aliases)
            if owner in RESERVED_POSITION_TYPES:
                found.append(f"{owner}.{node.attr}")
        elif isinstance(node, ast.Subscript):
            owner = _resolve(node.value, aliases)
            if owner in RESERVED_POSITION_TYPES:
                found.append(f"{owner}[...]")
    return found


def _scopes(tree):
    """Yield each scope to judge as a unit: every function body, then the module.

    Shape 1 needs a scope rather than a single expression, because a conversion is
    routinely written so the status never appears inside the call's own parentheses
    — ``TerminalOutcome(s.value)`` guarded by an ``isinstance`` check two lines up is
    still a conversion. A scope that both reads an auditor status and constructs a
    reserved-position value is the violation; keeping the two in separate scopes is
    how lawful code that touches both vocabularies is written.
    """
    functions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for node in functions:
        yield node
    inner = {id(c) for f in functions for c in ast.walk(f)}
    for stmt in tree.body:
        if id(stmt) not in inner:
            yield stmt


def _projections(source, filename="<sample>"):
    """Return every place ``source`` moves an auditor status into a reserved position.

    Six shapes, because a projection can be written six ways and prose forbidding
    one of them forbids none of the others. Every shape resolves aliased and
    module-qualified references, so renaming an import does not evade the scan.
    """
    tree = ast.parse(source, filename=filename)
    aliases = _aliases(tree)
    found = []
    # 1. Conversion: a scope that reads an auditor status and builds a reserved value.
    # 6. Member access: the same scope selecting a reserved value instead of building it.
    for scope in _scopes(tree):
        if not _refers_to_status(scope, aliases):
            continue
        for node in ast.walk(scope):
            if isinstance(node, ast.Call) and _called_name(node, aliases) in RESERVED_POSITION_TYPES:
                found.append(("conversion-call", _called_name(node, aliases)))
        for access in _reserved_member_accesses(scope, aliases):
            found.append(("reserved-member-access", access))
    for node in ast.walk(tree):
        # 2. Lookup table mapping one vocabulary onto the other, in either direction.
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is None or value is None:
                    continue
                pair = (_refers_to_status(key, aliases), _refers_to_reserved_position(value, aliases))
                reverse = (_refers_to_reserved_position(key, aliases), _refers_to_status(value, aliases))
                if all(pair) or all(reverse):
                    found.append(("lookup-table", ast.unparse(node)[:60]))
        # 3. Annotation admitting both vocabularies in one field.
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            ann = node.annotation
            if _refers_to_status(ann, aliases) and _refers_to_reserved_position(ann, aliases):
                found.append(("union-annotation", ast.unparse(ann)))
            # 4. A reserved-position field defaulted or assigned from a status.
            if (_refers_to_reserved_position(ann, aliases) and node.value is not None
                    and _refers_to_status(node.value, aliases)):
                found.append(("status-valued-field", ast.unparse(ann)))
        # 5. A status-in / outcome-out function is a conversion whatever its body.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            annotations = [a.annotation for a in
                           list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
                           if a.annotation is not None]
            takes_status = any(_refers_to_status(a, aliases) for a in annotations)
            returns_reserved = (node.returns is not None
                                and _refers_to_reserved_position(node.returns, aliases))
            if takes_status and returns_reserved:
                found.append(("status-to-outcome-function", node.name))
    return found


#: Samples the source half must flag. One per shape, so a detector that lost a shape
#: fails here instead of quietly reporting a clean package.
PROJECTION_SAMPLES = (
    "def f(s):\n    return TerminalOutcome(s.value) if isinstance(s, SemanticAuditorFindingStatus) else None\n",
    "TABLE = {SemanticAuditorFindingStatus.CONSISTENT: TerminalOutcome.PROPOSAL}\n",
    "class M:\n    outcome: TerminalOutcome | SemanticAuditorFindingStatus\n",
    "class M:\n    disposition: CandidateDisposition = SemanticAuditorFindingStatus.INDETERMINATE\n",
    "def project(status: SemanticAuditorFindingStatus) -> TerminalOutcome:\n    raise NotImplementedError\n",
    # Shape 6: selecting the value rather than constructing it. An if/elif ladder or
    # a guarded return never calls the enum, so shape 1 alone would let it through.
    ("def f(s):\n"
     "    if isinstance(s, SemanticAuditorFindingStatus):\n"
     "        return TerminalOutcome.ABSTAIN\n"
     "    return None\n"),
    ("def f(s: SemanticAuditorFindingStatus):\n"
     "    return TerminalOutcome[s.name]\n"),
    # The same six shapes written through an import alias.
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def f(s):\n"
     "    return T(s.value) if isinstance(s, S) else None\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, CandidateDisposition as D\n"
     "TABLE = {S.CONSISTENT: D.DEFER}\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def project(status: S) -> T:\n    raise NotImplementedError\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def f(s):\n"
     "    if isinstance(s, S):\n        return T.ABSTAIN\n    return None\n"),
    # And through a module-qualified reference.
    ("from . import vocabulary\n"
     "def f(s):\n"
     "    if isinstance(s, vocabulary.SemanticAuditorFindingStatus):\n"
     "        return vocabulary.TerminalOutcome(s.value)\n"),
    ("from . import vocabulary\n"
     "def f(s):\n"
     "    if isinstance(s, vocabulary.SemanticAuditorFindingStatus):\n"
     "        return vocabulary.TerminalOutcome.ABSTAIN\n"),
    ("from . import vocabulary\n"
     "def project(status: vocabulary.SemanticAuditorFindingStatus)"
     " -> vocabulary.TerminalOutcome:\n    raise NotImplementedError\n"),
    # A pydantic validator coercing a status into a reserved-position field.
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "class M:\n"
     "    @field_validator('outcome', mode='before')\n"
     "    def _coerce(cls, v):\n"
     "        if v is S.INDETERMINATE:\n            return T.ABSTAIN\n"
     "        return v\n"),
)

#: Samples that must NOT be flagged: the two vocabularies may coexist in a module,
#: be imported together, and be carried in separate fields. Only crossing is barred.
CLEAN_SAMPLES = (
    "from .vocabulary import SemanticAuditorFindingStatus, TerminalOutcome\n",
    "class M:\n    outcome: TerminalOutcome\n    finding: SemanticAuditorFindingStatus\n",
    "def read(status: SemanticAuditorFindingStatus) -> str:\n    return status.value\n",
    "OUTCOMES = {TerminalOutcome.ABSTAIN: 'no recommendation'}\n",
    ("def read(status: SemanticAuditorFindingStatus) -> str:\n    return status.value\n"
     "\n\ndef decide() -> TerminalOutcome:\n    return TerminalOutcome.ABSTAIN\n"),
    # The same separation, written through an alias and a module reference: resolving
    # aliases must not make lawful code fail, only make evasion impossible.
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "def read(status: S) -> str:\n    return status.value\n"
     "\n\ndef decide() -> T:\n    return T.ABSTAIN\n"),
    ("from . import vocabulary\n"
     "def decide() -> vocabulary.TerminalOutcome:\n"
     "    return vocabulary.TerminalOutcome.ABSTAIN\n"),
    ("from .vocabulary import SemanticAuditorFindingStatus as S, TerminalOutcome as T\n"
     "class M:\n    outcome: T\n    finding: S\n"),
)


@pytest.mark.parametrize("sample", PROJECTION_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_detector_flags_every_projection_shape(sample):
    assert _projections(sample), "a projection shape stopped being detected"


@pytest.mark.parametrize("sample", CLEAN_SAMPLES, ids=lambda s: s.split("\n")[0][:40])
def test_the_detector_does_not_flag_lawful_coexistence(sample):
    assert not _projections(sample)


def test_sources_exist_to_scan():
    assert sorted(SRC.rglob("*.py"))


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_no_source_projects_an_auditor_status_into_a_reserved_position(path):
    found = _projections(path.read_text(encoding="utf-8"), filename=str(path))
    assert not found, f"{path.name} projects an auditor status: {found}"


def _modules():
    yield ap
    for info in pkgutil.walk_packages(ap.__path__, ap.__name__ + "."):
        yield importlib.import_module(info.name)


def _is_reserved_position(annotation):
    """Whether ``annotation`` puts a value in a position D6 reserves.

    A union arm counts. ``TerminalOutcome | SemanticAuditorFindingStatus`` is the
    projection itself, so a field carrying it must be collected and judged, not
    passed over for not being the bare enum.
    """
    if isinstance(annotation, str):
        return annotation in RESERVED_POSITION_TYPES
    candidates = {annotation} | set(typing.get_args(annotation))
    return bool(candidates & {TerminalOutcome, CandidateDisposition})


def _reserved_position_fields():
    """Every declared field typed as a terminal outcome or a candidate disposition.

    Covers pydantic models and dataclasses alike, since either could carry the first
    such field. Empty until S1 defines a contract that has one.
    """
    fields = []
    seen = set()
    for module in _modules():
        for attr in vars(module).values():
            if not isinstance(attr, type) or attr in seen:
                continue
            seen.add(attr)
            annotations = dict(getattr(attr, "__annotations__", {}) or {})
            if dataclasses.is_dataclass(attr):
                annotations = {f.name: f.type for f in dataclasses.fields(attr)}
            model_fields = getattr(attr, "model_fields", None)
            if isinstance(model_fields, dict):
                annotations = {name: f.annotation for name, f in model_fields.items()}
            for name, annotation in annotations.items():
                if _is_reserved_position(annotation):
                    fields.append((attr, name, annotation))
    return fields


def _declared_annotation(owner, name):
    """The annotation ``owner`` declares for ``name``, whatever kind of type it is."""
    model_fields = getattr(owner, "model_fields", None)
    if isinstance(model_fields, dict) and name in model_fields:
        return model_fields[name].annotation
    if dataclasses.is_dataclass(owner):
        for field in dataclasses.fields(owner):
            if field.name == name:
                return field.type
    return dict(getattr(owner, "__annotations__", {}) or {}).get(name)


def _resolve_annotation(annotation):
    """A string annotation (``from __future__ import annotations``) as its type."""
    if isinstance(annotation, str):
        return {
            "TerminalOutcome": TerminalOutcome,
            "CandidateDisposition": CandidateDisposition,
            STATUS_TYPE: SemanticAuditorFindingStatus,
        }.get(annotation, annotation)
    return annotation


@pytest.mark.parametrize(
    "owner,name,annotation",
    _reserved_position_fields(),
    ids=lambda v: getattr(v, "__name__", str(v)),
)
def test_a_reserved_position_field_rejects_every_auditor_status(owner, name, annotation):
    """Every auditor status must be refused by ``owner.name`` itself.

    Parametrized over what the package defines, so this arms itself with the first
    such field rather than needing to be remembered then.

    The assertion is against the field's own declared annotation, read back off the
    owner — not against the bare enum. Testing the enum would pass for a field
    annotated ``TerminalOutcome | SemanticAuditorFindingStatus``, which is the
    projection D6 forbids; the union is admitted by the field and refused by the
    enum, so only the field can answer the question.
    """
    declared = _declared_annotation(owner, name)
    assert declared is not None, f"{owner.__name__}.{name} has no readable annotation"
    resolved = _resolve_annotation(declared)

    # The status vocabulary must not be admissible in the field at all, directly or
    # as one arm of a union.
    admitted = {resolved} | set(typing.get_args(resolved))
    assert SemanticAuditorFindingStatus not in admitted, (
        f"{owner.__name__}.{name} admits {STATUS_TYPE}: {declared!r}")

    adapter = pydantic.TypeAdapter(resolved)
    for status in SemanticAuditorFindingStatus:
        # Neither the member nor its wire value may validate into this field.
        for candidate in (status, status.value):
            with pytest.raises((pydantic.ValidationError, ValueError, TypeError)):
                adapter.validate_python(candidate)


def test_no_auditor_status_value_is_admissible_in_a_reserved_position():
    """The enums themselves make the projection impossible, term by term.

    This is what keeps the rule wider than INDETERMINATE: it holds for CONSISTENT,
    INCONSISTENT and CONFLICTING too, and would fail if any of them were added to
    either reserved vocabulary later.
    """
    reserved_values = ({m.value for m in TerminalOutcome}
                       | {m.value for m in CandidateDisposition})
    for status in SemanticAuditorFindingStatus:
        assert status.value not in reserved_values
        for target in (TerminalOutcome, CandidateDisposition):
            with pytest.raises(ValueError):
                target(status.value)
            with pytest.raises(KeyError):
                target[status.name]


def test_the_three_vocabularies_are_distinct_types():
    """Projection by subclassing, aliasing or re-basing is closed off too."""
    for target in (TerminalOutcome, CandidateDisposition):
        assert not issubclass(SemanticAuditorFindingStatus, target)
        assert not issubclass(target, SemanticAuditorFindingStatus)
        assert set(SemanticAuditorFindingStatus) & set(target) == set()
    assert issubclass(SemanticAuditorFindingStatus, enum.Enum)
