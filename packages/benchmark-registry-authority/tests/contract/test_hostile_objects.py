"""§07 — no attacker-controlled code is ever invoked, at any depth.

The suites here plant each of four forgeries at **every** nested site the
contract graph actually contains, and assert on the side-effect recorder rather
than only on the raised error. An error proves *something* went wrong; an empty
recorder proves the hostile object's own validator was never given control.
"""

from __future__ import annotations

import dataclasses
import pathlib

import pytest

import _builders as fx
import _hostile
from _graph import dataclass_edges, max_depth
from ugence_benchmark_registry_authority.api import (
    BenchmarkRegistryCanonicalizationError,
    canonical_bytes,
    canonical_digest,
)

#: The deepest root in the package — a revocation event reaches through the
#: registration event, the admission decision, the submission record, the
#: publisher envelope and the exact BR-1 locator to its scope and applicability
#: coordinates, plus a second path through the revocation envelope.
DEEPEST_ROOT = fx.revocation_event


def _all_edges():
    root = DEEPEST_ROOT()
    return [
        (path, depth)
        for _parent, _name, _child, path, depth in dataclass_edges(root)
    ]


def _plant(root, target_path, factory):
    """Replace the node at ``target_path`` with a forgery, in place.

    Building the forgery runs its own ``__post_init__`` once — the attacker
    constructing their own object. The recorder is armed *after* that, so it
    answers only whether the **package** later gave that code control.
    """

    for parent, name, child, path, _depth in dataclass_edges(root):
        if path == target_path:
            object.__setattr__(parent, name, factory(child))
            _hostile.arm()
            return True
    return False


@pytest.fixture(autouse=True)
def _clean_recorder():
    _hostile.reset()
    yield
    _hostile.reset()


def test_happy_the_deepest_root_canonicalizes_before_anything_is_planted():
    """A probe that passed because its fixture was already broken is worthless."""

    _hostile.arm()
    assert canonical_digest(DEEPEST_ROOT())
    assert _hostile.INVOCATIONS == []


def test_the_graph_is_genuinely_deep_enough_to_be_worth_walking():
    """If the graph were two levels deep, 'at every depth' would prove little."""

    assert max_depth(DEEPEST_ROOT()) >= 6


@pytest.mark.parametrize("factory_name,factory", _hostile.HOSTILE_FACTORIES)
@pytest.mark.parametrize("target_path,depth", _all_edges())
def test_a_hostile_object_at_every_depth_is_refused_and_never_invoked(
    factory_name, factory, target_path, depth
):
    """Plant each forgery at each nested site: refused, and its code never runs."""

    root = DEEPEST_ROOT()
    assert _plant(root, target_path, factory), target_path
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(root)
    assert _hostile.INVOCATIONS == [], (
        f"{factory_name} at {target_path} (depth {depth}) had its own "
        "validation method invoked; the encoder must identify the expected "
        "class by identity and call the trusted exact class's __post_init__, "
        "never one resolved through the instance"
    )


@pytest.mark.parametrize("factory_name,factory", _hostile.HOSTILE_FACTORIES)
def test_a_hostile_root_is_refused_and_never_invoked(factory_name, factory):
    root = factory(fx.submission_record())
    _hostile.arm()
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(root)
    assert _hostile.INVOCATIONS == []


def test_the_metaclass_forgery_really_does_compare_equal_to_the_genuine_class():
    """Prove the forgery is a real threat, not a strawman the check happens to catch.

    If the registry used ``in`` or ``[]`` on a dict, this class object would be
    found there — it hashes the same and compares equal. Identity comparison is
    what refuses it.
    """

    genuine = fx.publisher_envelope()
    forged = _hostile.metaclass_forged(genuine)
    assert type(forged) == type(genuine)  # noqa: E721 - the forgery, demonstrated
    assert hash(type(forged)) == hash(type(genuine))
    assert type(forged) is not type(genuine)
    _hostile.reset()


def test_the_same_name_forgery_really_does_match_name_and_module():
    genuine = fx.publisher_envelope()
    forged = _hostile.same_name_same_module(genuine)
    assert type(forged).__name__ == type(genuine).__name__
    assert type(forged).__module__ == type(genuine).__module__
    assert type(forged) is not type(genuine)
    _hostile.reset()


def test_the_subclass_forgery_really_does_pass_isinstance():
    """Which is exactly why no boundary in this package uses ``isinstance``."""

    genuine = fx.publisher_envelope()
    forged = _hostile.subclass_override(genuine)
    assert isinstance(forged, type(genuine))
    assert type(forged) is not type(genuine)
    _hostile.reset()


@pytest.mark.parametrize("factory_name,factory", _hostile.HOSTILE_FACTORIES)
def test_a_forgery_is_refused_by_the_constructor_of_every_payload_that_nests_it(
    factory_name, factory
):
    """Refusal is not only at canonicalization: constructors refuse it too."""

    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryContractError,
        BenchmarkRegistrationEventPayload,
        BenchmarkSubmissionRecordPayload,
    )

    forged_envelope = factory(fx.publisher_envelope())
    _hostile.arm()
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkSubmissionRecordPayload(
            publisher_submission_envelope=forged_envelope,
            declared_registry_authority_identity=fx.REGISTRY_AUTHORITY_IDENTITY,
            declared_recorded_at=fx.RECORDED_AT,
        )
    forged_decision = factory(fx.admission_decision())
    _hostile.arm()
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkRegistrationEventPayload(
            admission_decision=forged_decision,
            declared_recorded_at=fx.RECORDED_AT,
        )
    assert _hostile.INVOCATIONS == []


def test_every_nested_site_in_the_graph_was_actually_covered():
    """Guard against the parametrization silently collapsing to nothing."""

    edges = _all_edges()
    assert len(edges) >= 12
    assert len({path for path, _ in edges}) == len(edges)
    assert dataclasses.is_dataclass(DEEPEST_ROOT())


def test_revalidation_calls_the_trusted_exact_class_never_the_instance():
    """§07's step 3 spelling, asserted on the source itself.

    ``expected_class.__post_init__(node)`` and ``node.__post_init__()`` are
    *behaviourally* identical here, because step 2 has already proved
    ``type(node) is expected_class`` — which is exactly why a behavioural test
    cannot distinguish them, and why the ratification states the spelling as a
    requirement in its own right rather than leaving it to be inferred.

    The requirement is defence in depth: it means the ordering guarantee does
    not silently become load-bearing for the invocation. If the exact-type proof
    were ever weakened or reordered, the instance-resolved spelling would hand
    control to an attacker's method while the trusted-class spelling still would
    not. Asserting the spelling keeps that property from depending on a
    neighbouring check staying where it is.
    """

    canonical = (
        pathlib.Path(__file__).resolve().parents[2]
        / "src"
        / "ugence_benchmark_registry_authority"
        / "contracts"
        / "canonical.py"
    )
    source = canonical.read_text()
    code = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    body = code.split('"""', 2)[-1]
    assert "cls.__post_init__(contract)" in body
    assert "contract.__post_init__()" not in body
    assert ".__post_init__()" not in body
