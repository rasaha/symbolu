"""Constructor bypass — ``object.__setattr__`` corruption at every node, every depth.

``@dataclass(frozen=True)`` stops ordinary assignment. It does **not** stop
``object.__setattr__``, which writes straight into the instance dictionary and
is available to any code in the process. An artifact corrupted that way is
internally self-consistent, compares equal to nothing in particular, and would
canonicalize happily under any encoder that trusted construction-time validation
alone.

This suite walks the deepest contract graph, corrupts **every scalar field of
every reachable node** with a value its public constructor would have refused,
and asserts the corruption is caught **before a single byte is produced**.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import Enum

import pytest

import _builders as fx
from _graph import dataclass_edges
from ugence_benchmark_registry_authority.api import (
    BenchmarkRegistryCanonicalizationError,
    canonical_bytes,
    canonical_digest,
)

DEEPEST_ROOT = fx.revocation_event


def _corruptions(value):
    """Values the field's own constructor would have refused, by field type."""

    if isinstance(value, Enum):
        return [(value.value, "a bare string spelling of an enum member")]
    if isinstance(value, datetime):
        return [
            (value.replace(tzinfo=None), "a naive datetime"),
            ("2026-01-01T00:00:00Z", "a string instead of a datetime"),
        ]
    if isinstance(value, str):
        return [
            ("", "an empty identifier"),
            (f" {value} ", "a padded identifier"),
            ("é", "a non-NFC string"),
        ]
    return []


def _nodes(root):
    """Every reachable dataclass node, root included, with its path."""

    yield root, "$"
    for _parent, _name, child, path, _depth in dataclass_edges(root):
        yield child, path


def _cases():
    root = DEEPEST_ROOT()
    seen = set()
    cases = []
    for node, path in _nodes(root):
        for f in dataclasses.fields(node):
            value = getattr(node, f.name)
            if dataclasses.is_dataclass(value):
                continue
            for corrupt, label in _corruptions(value):
                # A "corruption" equal to the value already there corrupts
                # nothing. The applicability coordinates legitimately carry an
                # empty value when they declare NOT_APPLICABLE, so an empty
                # string is their genuine state, not a bypass.
                if corrupt == value:
                    continue
                key = f"{path}.{f.name}::{label}"
                if key in seen:
                    continue
                seen.add(key)
                cases.append((path, f.name, corrupt, label))
    return cases


CASES = _cases()


def _apply(root, target_path, field_name, corrupt):
    for node, path in _nodes(root):
        if path == target_path:
            object.__setattr__(node, field_name, corrupt)
            return True
    return False


def test_happy_the_uncorrupted_graph_canonicalizes():
    assert canonical_digest(DEEPEST_ROOT())


def test_the_sweep_actually_covers_every_node_and_a_lot_of_fields():
    """Guard against the case generator silently collapsing."""

    root = DEEPEST_ROOT()
    node_count = len(list(_nodes(root)))
    covered = {path for path, _f, _c, _l in CASES}
    assert node_count >= 13
    assert len(covered) == node_count
    assert len(CASES) >= 60


@pytest.mark.parametrize(
    "target_path,field_name,corrupt,label",
    [(p, f, c, l) for p, f, c, l in CASES],
    ids=[f"{p}.{f}[{l}]" for p, f, c, l in CASES],
)
def test_corrupting_any_field_of_any_node_is_refused_before_any_byte(
    target_path, field_name, corrupt, label
):
    root = DEEPEST_ROOT()
    assert _apply(root, target_path, field_name, corrupt), target_path
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(root)


def test_a_frozen_contract_still_refuses_ordinary_assignment():
    record = fx.submission_record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.declared_recorded_at = fx.RECORDED_AT  # type: ignore[misc]


def test_corrupting_a_predecessor_declared_outcome_is_caught_by_revalidation():
    """The specific corruption the state machine depends on being caught."""

    from ugence_benchmark_registry_authority.api import BenchmarkAdmissionOutcome

    event = fx.registration_event()
    object.__setattr__(
        event.admission_decision,
        "declared_outcome",
        BenchmarkAdmissionOutcome.REJECTED,
    )
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(event)


def test_corrupting_a_predecessor_actor_identity_is_caught_by_revalidation():
    """Collapsing four-party separation after construction is still refused."""

    event = fx.registration_event()
    envelope = (
        event.admission_decision.submission_record.publisher_submission_envelope
    )
    object.__setattr__(
        envelope, "publisher_identity", fx.REGISTRY_AUTHORITY_IDENTITY
    )
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(event)


def test_corruption_is_refused_and_never_repaired():
    """A revalidation failure never silently fixes the object."""

    record = fx.submission_record()
    object.__setattr__(record, "declared_registry_authority_identity", "")
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(record)
    assert record.declared_registry_authority_identity == ""
