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


def _names(node):
    """Every bare name referenced anywhere inside ``node``."""
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _refers_to_status(node):
    return STATUS_TYPE in _names(node)


def _refers_to_reserved_position(node):
    return bool(_names(node) & set(RESERVED_POSITION_TYPES))


def _called_name(call):
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


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

    Five shapes, because a projection can be written five ways and prose forbidding
    one of them forbids none of the others.
    """
    tree = ast.parse(source, filename=filename)
    found = []
    # 1. Conversion: a scope that reads an auditor status and builds a reserved value.
    for scope in _scopes(tree):
        if not _refers_to_status(scope):
            continue
        for node in ast.walk(scope):
            if isinstance(node, ast.Call) and _called_name(node) in RESERVED_POSITION_TYPES:
                found.append(("conversion-call", _called_name(node)))
    for node in ast.walk(tree):
        # 2. Lookup table mapping one vocabulary onto the other, in either direction.
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is None or value is None:
                    continue
                pair = (_refers_to_status(key), _refers_to_reserved_position(value))
                reverse = (_refers_to_reserved_position(key), _refers_to_status(value))
                if all(pair) or all(reverse):
                    found.append(("lookup-table", ast.unparse(node)[:60]))
        # 3. Annotation admitting both vocabularies in one field.
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            ann = node.annotation
            if _refers_to_status(ann) and _refers_to_reserved_position(ann):
                found.append(("union-annotation", ast.unparse(ann)))
            # 4. A reserved-position field defaulted or assigned from a status.
            if (_refers_to_reserved_position(ann) and node.value is not None
                    and _refers_to_status(node.value)):
                found.append(("status-valued-field", ast.unparse(ann)))
        # 5. A status-in / outcome-out function is a conversion whatever its body.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            annotations = [a.annotation for a in
                           list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
                           if a.annotation is not None]
            takes_status = any(_refers_to_status(a) for a in annotations)
            returns_reserved = (node.returns is not None
                                and _refers_to_reserved_position(node.returns))
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
                if annotation in (TerminalOutcome, CandidateDisposition):
                    fields.append((attr, name, annotation))
                elif isinstance(annotation, str) and annotation in RESERVED_POSITION_TYPES:
                    fields.append((attr, name, annotation))
    return fields


@pytest.mark.parametrize(
    "owner,name,annotation",
    _reserved_position_fields(),
    ids=lambda v: getattr(v, "__name__", str(v)),
)
def test_a_reserved_position_field_rejects_every_auditor_status(owner, name, annotation):
    """Every auditor status must be refused by every outcome/disposition field.

    Parametrized over what the package defines, so this arms itself with the first
    such field rather than needing to be remembered then.
    """
    target = annotation if isinstance(annotation, type) else {
        "TerminalOutcome": TerminalOutcome,
        "CandidateDisposition": CandidateDisposition,
    }[annotation]
    for status in SemanticAuditorFindingStatus:
        with pytest.raises((ValueError, TypeError)):
            target(status.value)


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
