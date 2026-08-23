"""Workflow IR v1 canonicalization compatibility ratchet (ADR §9 `[R]`).

**What this guards.** One cross-component artifact contract: the Policy Workflow
Compiler and the Agent Workforce Composer must derive *identical canonical bytes
and fingerprints* for the same ``workflow_ir.v1`` semantic value, under the frozen
``WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION == "0.1.0"``.

**Normative scope.** Only ``NORMATIVE_V1_REACHABLE`` vectors -- values structurally
reachable through the v1 schema or its three documented digest preimages -- define
that contract, and only they are golden-anchored here. Values both canonicalizers
merely happen to accept (``float``, ``-0.0``, ``set``, ``frozenset``, ``bool``,
``None``) are **not** v1 capabilities and live in
``test_workflow_ir_v1_canonicalization_diagnostics.py``, where they cannot fail this
gate. The two implementations' *internal* projection mechanisms may differ; only
output over the reachable domain must agree.

**What this is not.** Not a shared canonicalization contract, not a ratification of
either implementation, not authorization, signing or truth, and not evidence that
Risk Authority, Policy Authority, Cloud Scaling Controller or Producer Attestation
should converge on anything. Extraction of a shared package remains rejected; the
governing architecture remains domain-owned canonicalization.

**Why two obligations and not one.** Pairwise equivalence alone cannot see
*symmetric* drift -- both implementations could change together and still agree
with each other. Every vector is therefore also anchored to a committed golden
(``tests/fixtures/workflow_ir_v1_canonical_golden.json``), which only a reviewed
fixture change can move.

**Dependency posture.** This is a test-only pairing. Neither distribution's source
gains an import of the other; ``test_v2_determinism_and_boundaries.py`` in the
compiler continues to enforce that, and nothing here weakens it.
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from . import _ir_v1_compat_vectors as V
from ._ir_v1_ratchet_harness import compare_accepted, compare_rejected, digest_of

#: Set in the CI job that installs both distributions. When set, an unimportable
#: compiler is a FAILURE, not a skip -- a permanently skipped test is not a ratchet.
_REQUIRED = os.environ.get("WORKFLOW_IR_V1_RATCHET_REQUIRED") == "1"

_compiler_import_error = None
try:
    from ugence_policy_workflow_compiler.serialization import canonical_json as _compiler_cj
    from ugence_policy_workflow_compiler.version import WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION
except Exception as exc:                                   # noqa: BLE001
    _compiler_import_error = exc
    _compiler_cj = None
    WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION = None

from ugence_agent_workforce_composer import canonical as _awc_canonical

if _compiler_import_error is not None and _REQUIRED:
    raise RuntimeError(
        "WORKFLOW_IR_V1_RATCHET_REQUIRED=1 but ugence_policy_workflow_compiler is not "
        f"importable ({_compiler_import_error!r}). The ratchet must actually run in this "
        "configuration; a skip here would report enforcement that did not happen.")

pytestmark = pytest.mark.skipif(
    _compiler_import_error is not None,
    reason=("ugence_policy_workflow_compiler not installed; the ratchet runs in the CI jobs "
            "that install both distributions (see WORKFLOW_IR_V1_RATCHET_REQUIRED)"))

_GOLDEN_PATH = pathlib.Path(__file__).resolve().parent / "fixtures" / "workflow_ir_v1_canonical_golden.json"


def _goldens():
    return json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))


def _compiler_dumps(value):
    return _compiler_cj.dumps(value)


def _awc_dumps(value):
    return _awc_canonical.canonical_json(value)


# -- the pinned identity ---------------------------------------------------- #

def test_pinned_against_the_frozen_v1_digest_version():
    """The corpus is pinned to one canonicalization identity. If the compiler's
    frozen v1 digest version moves, these vectors no longer describe it."""
    golden = _goldens()
    assert WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION == "0.1.0"
    assert golden["pinned_digest_compiler_version"] == "0.1.0"
    assert V.PINNED_DIGEST_COMPILER_VERSION == "0.1.0"
    assert golden["corpus_version"] == V.CORPUS_VERSION


def test_golden_file_covers_exactly_the_corpus():
    """No vector without a golden, and no orphan golden without a vector."""
    golden_ids = set(_goldens()["vectors"])
    corpus_ids = {vid for vid, _ in V.normative_vectors()}
    assert not corpus_ids - golden_ids, f"vectors missing a golden: {sorted(corpus_ids - golden_ids)}"
    assert not golden_ids - corpus_ids, f"orphan goldens: {sorted(golden_ids - corpus_ids)}"


def test_golden_entries_are_internally_consistent():
    """Each entry's digest is the digest of its own canonical bytes."""
    bad = [vid for vid, e in _goldens()["vectors"].items()
           if digest_of(e["canonical_bytes"]) != e["digest"]]
    assert not bad, f"golden entries whose digest does not match their bytes: {bad}"


# -- the ratchet ------------------------------------------------------------ #

def test_pairwise_and_golden_equivalence_over_the_corpus():
    """Both implementations agree with each other AND with the committed golden."""
    failures = compare_accepted(V.normative_vectors(), _compiler_dumps, _awc_dumps,
                                _goldens()["vectors"])
    assert not failures, "Workflow IR v1 canonicalization compatibility broken:\n  " + \
        "\n  ".join(failures)


def test_structural_exclusion_parity():
    """Values the v1 schema must keep out of a valid model are refused by both.

    This is an exclusion check, not a published canonicalization guarantee: it
    anchors no golden and freezes no bytes. Messages are not compared -- neither
    implementation publishes its exception text as contract.
    """
    failures = compare_rejected(V.structural_exclusion_vectors(), _compiler_dumps, _awc_dumps)
    assert not failures, "Workflow IR v1 rejection parity broken:\n  " + "\n  ".join(failures)


def test_vector_classification_matches_the_live_schema():
    """Every normative vector uses only value types the v1 schema can actually reach.

    The classification is audited against the live models rather than trusted, so a
    vector cannot be labelled normative -- and thereby freeze bytes -- for a type
    ``workflow_ir.v1`` does not admit. This is what stops test coverage from being
    mistaken for contract scope.
    """
    import enum

    from pydantic import BaseModel

    reachable = V.reachable_value_types()

    def _classes(value, path):
        """Every runtime type in the value tree, nested values included."""
        if isinstance(value, BaseModel):
            yield BaseModel, path
            for name, item in value.__dict__.items():
                yield from _classes(item, f"{path}.{name}")
            return
        if isinstance(value, enum.Enum):
            yield enum.Enum, path
            return
        if isinstance(value, dict):
            yield dict, path
            for k, item in value.items():
                yield type(k), f"{path}[key]"
                yield from _classes(item, f"{path}[{k!r}]")
            return
        if isinstance(value, (list, tuple)):
            yield type(value), path
            for i, item in enumerate(value):
                yield from _classes(item, f"{path}[{i}]")
            return
        yield type(value), path

    offenders = []
    for vector_id, value in V.normative_vectors():
        for cls, path in _classes(value, vector_id):
            if cls not in reachable:
                offenders.append(f"{path}: {cls.__name__} is not reachable from workflow_ir.v1")
    assert not offenders, (
        "normative vectors must contain only v1-reachable types; move these to "
        f"diagnostic_vectors(): {sorted(set(offenders))}")


def test_every_vector_carries_exactly_one_class():
    classes = V.vector_classes()
    ids = ([v for v, _ in V.normative_vectors()] + [v for v, _ in V.diagnostic_vectors()]
           + [v for v, _ in V.structural_exclusion_vectors()])
    assert len(ids) == len(set(ids)), "a vector id appears in more than one class"
    assert set(classes) == set(ids)
    assert set(classes.values()) == {"NORMATIVE_V1_REACHABLE", "NON_NORMATIVE_DIAGNOSTIC",
                                     "STRUCTURAL_EXCLUSION"}


def test_golden_anchors_only_normative_vectors():
    """Diagnostics and exclusions must never reach the frozen gate."""
    golden_ids = set(_goldens()["vectors"])
    classes = V.vector_classes()
    non_normative = {vid for vid in golden_ids if classes.get(vid) != "NORMATIVE_V1_REACHABLE"}
    assert not non_normative, f"non-normative vectors anchored in the golden: {sorted(non_normative)}"


def test_pretty_encoding_agrees_on_the_ir():
    """``dumps_pretty`` has no AWC counterpart by name, but the two must still
    agree on the *ordered object* an indented encoding renders. Guarding the
    projection keeps on-disk package files reproducible from either side."""
    ir = dict(V.normative_vectors())["model_ir"]
    assert _compiler_cj.to_canonical_obj(ir) == _awc_canonical.to_canonical_obj(ir)


# -- the structural reason the domains cannot silently diverge -------------- #

def test_workflow_ir_v1_declares_no_field_outside_the_agreed_domain():
    """The two canonicalizers differ on model-embedded ``datetime``/``date``/
    ``Decimal``/``UUID``/``bytes`` (AWC's ``model_dump(mode="json")`` encodes them;
    the compiler's ``mode="python"`` refuses them). That divergence is unreachable
    from ``workflow_ir.v1`` only because no v1 field declares such a type.

    This test is what keeps that true. Adding such a field to a v1 model would move
    the artifact into the domain where the two implementations disagree, and that
    is an explicit compatibility decision -- not a model edit.
    """
    from ugence_policy_workflow_compiler.compiler.workflow_ir import (
        WorkflowEdge, WorkflowIR, WorkflowNode,
    )
    import enum
    import typing

    from pydantic import BaseModel

    allowed_scalars = {str, int, bool, type(None)}
    offenders = []

    def _walk(model, seen):
        if model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            if not _acceptable(field.annotation, seen):
                offenders.append(f"{model.__name__}.{name}: {field.annotation!r}")

    def _acceptable(annotation, seen) -> bool:
        origin = typing.get_origin(annotation)
        if origin is not None:
            return all(_acceptable(a, seen) for a in typing.get_args(annotation)
                       if a is not Ellipsis)
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return True
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            # Nested v1 objects are in-domain exactly when their own fields are.
            _walk(annotation, seen)
            return True
        return annotation in allowed_scalars

    seen: set = set()
    for model in (WorkflowNode, WorkflowEdge, WorkflowIR):
        _walk(model, seen)
    assert not offenders, (
        "workflow_ir.v1 declares a field outside the domain the compiler and AWC "
        f"canonicalize identically: {offenders}")


def test_extra_forbid_blocks_undeclared_fields_from_introducing_exotic_types():
    """A declared-field audit is not enough on its own: an undeclared field could
    carry an excluded type in. ``extra="forbid"`` is what closes that, so assert it
    at the config level AND prove the refusal at runtime."""
    import datetime

    import pydantic

    from ugence_policy_workflow_compiler.compiler.workflow_ir import (
        NodeKind, WorkflowEdge, WorkflowIR, WorkflowNode,
    )
    from ugence_policy_workflow_compiler.models.common import (
        AuthorityDisposition, CapabilityId,
    )

    for model in (WorkflowNode, WorkflowEdge, WorkflowIR):
        assert model.model_config.get("extra") == "forbid", model.__name__
        assert model.model_config.get("frozen") is True, model.__name__

    with pytest.raises(pydantic.ValidationError):
        WorkflowNode(
            node_id="n", kind=NodeKind.TERMINAL_OUTCOME,
            owning_capability=CapabilityId.COMPILER,
            disposition=AuthorityDisposition.ADVISORY,
            smuggled=datetime.datetime.now(datetime.timezone.utc),  # undeclared
        )


def test_nested_runtime_values_cannot_carry_an_excluded_type():
    """Nesting must not be a bypass. A v1 model reached through ``WorkflowIR.nodes``
    is validated the same way as a top-level one, so an excluded value cannot ride
    in one level down."""
    import datetime

    import pydantic

    from ugence_policy_workflow_compiler.compiler.workflow_ir import (
        NodeKind, WorkflowIR, WorkflowNode,
    )
    from ugence_policy_workflow_compiler.models.common import (
        AuthorityDisposition, CapabilityId,
    )

    exotic = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)

    # 1. an excluded value in a declared string field of a NESTED node
    with pytest.raises(pydantic.ValidationError):
        WorkflowIR(policy_pack_id="p", policy_pack_version=1,
                   nodes=(WorkflowNode(node_id="n", kind=NodeKind.TERMINAL_OUTCOME,
                                       owning_capability=CapabilityId.COMPILER,
                                       disposition=AuthorityDisposition.ADVISORY,
                                       label=exotic),))
    # 2. an excluded value inside a nested tuple-of-strings field
    with pytest.raises(pydantic.ValidationError):
        WorkflowNode(node_id="n", kind=NodeKind.TERMINAL_OUTCOME,
                     owning_capability=CapabilityId.COMPILER,
                     disposition=AuthorityDisposition.ADVISORY,
                     input_object_ids=("ok", exotic))
    # 3. an excluded value as a whole nested node
    with pytest.raises(pydantic.ValidationError):
        WorkflowIR(policy_pack_id="p", policy_pack_version=1, nodes=(exotic,))


def test_a_future_schema_change_admitting_an_excluded_type_fails_review():
    """The domain guard is the review trigger. Proven on a stand-in model shaped
    like a v1 model that has gained a ``datetime`` field: the same walk that passes
    on the real schema flags it, so such a change cannot land silently."""
    import datetime
    import enum
    import typing

    from pydantic import BaseModel, ConfigDict

    class _FutureNode(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")
        node_id: str
        decided_at: datetime.datetime            # the hypothetical admission

    class _FutureIR(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")
        nodes: typing.Tuple[_FutureNode, ...] = ()

    allowed = {str, int, bool, type(None)}
    offenders = []

    def _walk(model, seen):
        if model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            if not _ok(field.annotation, seen):
                offenders.append(f"{model.__name__}.{name}")

    def _ok(annotation, seen):
        origin = typing.get_origin(annotation)
        if origin is not None:
            return all(_ok(a, seen) for a in typing.get_args(annotation) if a is not Ellipsis)
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return True
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            _walk(annotation, seen)
            return True
        return annotation in allowed

    _walk(_FutureIR, set())
    # Flagged through NESTING, not only at the top level.
    assert offenders == ["_FutureNode.decided_at"]
