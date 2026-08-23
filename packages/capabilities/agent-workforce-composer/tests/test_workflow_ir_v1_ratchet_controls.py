"""Negative controls for the Workflow IR v1 canonicalization ratchet.

A ratchet nobody has seen fail is an assumption, not a guard. Each control drives
the comparison harness with a deliberately broken encoder and asserts the harness
reports the specific failure -- proving the ratchet detects drift rather than
merely passing.

No production source is modified. Every control injects a fake encoder that wraps
the real one, so the distributions under test are untouched throughout.
"""
from __future__ import annotations

import pytest

from . import _ir_v1_compat_vectors as V
from ._ir_v1_ratchet_harness import (
    build_golden_payload, compare_accepted, compare_rejected, digest_of,
)

pytest.importorskip("ugence_policy_workflow_compiler")

from ugence_agent_workforce_composer import canonical as _awc            # noqa: E402
from ugence_policy_workflow_compiler.serialization import canonical_json as _cj  # noqa: E402


def _compiler(value):
    return _cj.dumps(value)


def _awc_dumps(value):
    return _awc.canonical_json(value)


def _goldens():
    return build_golden_payload(V.accepted_vectors(), _compiler,
                                V.CORPUS_VERSION, V.PINNED_DIGEST_COMPILER_VERSION)["vectors"]


def _one_byte_worse(fn):
    """Wrap an encoder so exactly one byte of its output differs."""
    def wrapped(value):
        out = fn(value)
        return out[:-1] + ("X" if out[-1:] != "X" else "Y")
    return wrapped


# -- control 1: drift in the compiler only ---------------------------------- #

def test_detects_one_byte_change_in_compiler_output_only():
    failures = compare_accepted(V.accepted_vectors(), _one_byte_worse(_compiler),
                                _awc_dumps, _goldens())
    assert failures
    assert any("PAIRWISE drift" in f for f in failures)
    assert any("compiler drifted from golden" in f for f in failures)


# -- control 2: drift in AWC only ------------------------------------------- #

def test_detects_one_byte_change_in_awc_output_only():
    failures = compare_accepted(V.accepted_vectors(), _compiler,
                                _one_byte_worse(_awc_dumps), _goldens())
    assert failures
    assert any("PAIRWISE drift" in f for f in failures)
    assert any("AWC drifted from golden" in f for f in failures)


# -- control 3: SYMMETRIC drift -- the case pairwise equivalence cannot see -- #

def test_detects_symmetric_drift_that_pairwise_equivalence_would_miss():
    """Both implementations change together and still agree with each other.

    Pairwise comparison passes here; only the golden anchor catches it. This is
    the control that justifies requiring both obligations.
    """
    broken_c, broken_a = _one_byte_worse(_compiler), _one_byte_worse(_awc_dumps)
    vectors = V.accepted_vectors()

    # The two broken encoders still agree with each other...
    assert all(broken_c(v) == broken_a(v) for _, v in vectors)
    # ...and pairwise-only comparison therefore reports nothing.
    pairwise_only = [f for f in compare_accepted(vectors, broken_c, broken_a, _goldens())
                     if "PAIRWISE drift" in f]
    assert not pairwise_only

    # The golden anchor catches it.
    failures = compare_accepted(vectors, broken_c, broken_a, _goldens())
    assert failures
    assert any("drifted from golden" in f for f in failures)
    assert any("digest drifted from golden" in f for f in failures)


# -- control 4: a new vector with no committed golden ----------------------- #

def test_detects_a_new_vector_missing_its_golden():
    goldens = _goldens()
    goldens.pop("model_ir")
    failures = compare_accepted(V.accepted_vectors(), _compiler, _awc_dumps, goldens)
    assert any("model_ir" in f and "no committed golden entry" in f for f in failures)


# -- control 5: acceptance / rejection disagreement ------------------------- #

def test_detects_acceptance_disagreement_on_a_rejected_vector():
    """One side starts accepting a value the corpus pins as rejected."""
    lenient = lambda value: "\"accepted\""            # noqa: E731 - a stand-in encoder
    failures = compare_rejected(V.rejected_vectors(), lenient, _awc_dumps)
    assert failures
    assert all("ACCEPTANCE DISAGREEMENT" in f for f in failures)
    assert any("compiler accepted it, AWC refused it" in f for f in failures)

    failures = compare_rejected(V.rejected_vectors(), _compiler, lenient)
    assert any("AWC accepted it, compiler refused it" in f for f in failures)


def test_detects_both_sides_accepting_a_pinned_rejection():
    lenient = lambda value: "\"accepted\""            # noqa: E731
    failures = compare_rejected(V.rejected_vectors(), lenient, lenient)
    assert failures
    assert all("BOTH accepted" in f for f in failures)


# -- control 6: the harness's own digest anchoring -------------------------- #

def test_detects_a_tampered_golden_digest():
    goldens = _goldens()
    goldens["model_ir"] = dict(goldens["model_ir"], digest=digest_of("something else"))
    failures = compare_accepted(V.accepted_vectors(), _compiler, _awc_dumps, goldens)
    assert any("digest drifted from golden" in f for f in failures)


# -- control 7: the structural domain guard --------------------------------- #

def test_domain_guard_would_reject_an_out_of_domain_field():
    """The guard in the ratchet flags a v1 model field whose type lands in the
    region where the two canonicalizers disagree. Proven on a stand-in model, so
    no production model is touched."""
    import datetime
    import enum
    import typing

    from pydantic import BaseModel

    class _Stand(BaseModel):
        ok_str: str
        ok_int: int
        drifts: datetime.datetime          # AWC encodes it; the compiler refuses it

    allowed_scalars = {str, int, bool, type(None)}

    def _acceptable(annotation) -> bool:
        origin = typing.get_origin(annotation)
        if origin is not None:
            return all(_acceptable(a) for a in typing.get_args(annotation) if a is not Ellipsis)
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return True
        return annotation in allowed_scalars

    offenders = [n for n, f in _Stand.model_fields.items() if not _acceptable(f.annotation)]
    assert offenders == ["drifts"]

    # And the divergence the guard exists to prevent is real, not hypothetical:
    m = _Stand(ok_str="a", ok_int=1, drifts=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc))
    with pytest.raises(TypeError):
        _compiler(m)
    assert _awc_dumps(m)          # AWC encodes the same value without complaint
