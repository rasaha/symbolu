"""Workflow IR v1 canonicalization compatibility ratchet (ADR §9 `[R]`).

**What this guards.** One cross-component artifact contract: the Policy Workflow
Compiler and the Agent Workforce Composer must derive *identical canonical bytes
and fingerprints* for the same ``workflow_ir.v1`` semantic value, under the frozen
``WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION == "0.1.0"``.

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
    corpus_ids = {vid for vid, _ in V.accepted_vectors()}
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
    failures = compare_accepted(V.accepted_vectors(), _compiler_dumps, _awc_dumps,
                                _goldens()["vectors"])
    assert not failures, "Workflow IR v1 canonicalization compatibility broken:\n  " + \
        "\n  ".join(failures)


def test_rejection_parity_over_the_corpus():
    """A value one implementation accepts and the other refuses is a compatibility
    failure. Messages are not compared -- neither publishes its text as contract."""
    failures = compare_rejected(V.rejected_vectors(), _compiler_dumps, _awc_dumps)
    assert not failures, "Workflow IR v1 rejection parity broken:\n  " + "\n  ".join(failures)


def test_pretty_encoding_agrees_on_the_ir():
    """``dumps_pretty`` has no AWC counterpart by name, but the two must still
    agree on the *ordered object* an indented encoding renders. Guarding the
    projection keeps on-disk package files reproducible from either side."""
    ir = dict(V.accepted_vectors())["model_ir"]
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
