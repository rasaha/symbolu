"""
Projection Read-Only Tests
==========================

Verify that projections do not mutate inputs:
    - Snapshot payload unchanged after projection
    - Request unchanged after projection
    - Deep comparison via dataclasses.asdict or equivalent
"""

import copy
import json
import pytest
from dataclasses import asdict, is_dataclass

from symbolu.ontology.projection import (
    FrozenSnapshot,
    InputRef,
    InputRefKind,
    OntologicalLayer,
    ProjectionProfile,
    OutputMode,
    Strictness,
    ProjectionOptions,
    ProjectionRequest,
    run_projection,
)


# =============================================================================
# Helper Functions
# =============================================================================

def deep_copy_value(value):
    """Create a deep copy of a value for comparison."""
    if is_dataclass(value) and not isinstance(value, type):
        # Convert dataclass to dict for comparison
        return asdict(value)
    elif isinstance(value, dict):
        return {k: deep_copy_value(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        result = [deep_copy_value(item) for item in value]
        return tuple(result) if isinstance(value, tuple) else result
    elif hasattr(value, '__dict__'):
        return copy.deepcopy(value.__dict__)
    else:
        return copy.deepcopy(value)


def values_equal(before, after):
    """Compare two values for equality after potential mutation."""
    if type(before) != type(after):
        return False
    if isinstance(before, dict):
        if set(before.keys()) != set(after.keys()):
            return False
        return all(values_equal(before[k], after[k]) for k in before.keys())
    elif isinstance(before, (list, tuple)):
        if len(before) != len(after):
            return False
        return all(values_equal(b, a) for b, a in zip(before, after))
    else:
        return before == after


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mutable_dict_payload():
    """Create a mutable dict payload for testing."""
    return {
        "key": "value",
        "count": 42,
        "nested": {
            "inner": [1, 2, 3],
            "flag": True
        },
        "items": [
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"}
        ]
    }


@pytest.fixture
def mutable_list_payload():
    """Create a mutable list payload for testing."""
    return [
        {"type": "a", "val": 1},
        {"type": "b", "val": 2},
        {"type": "a", "val": 1},
        [1, 2, 3],
        (4, 5, 6),
    ]


@pytest.fixture
def sample_input_ref():
    """Create a sample input reference."""
    return InputRef(
        kind=InputRefKind.GENERIC,
        object_id="f1e2d3c4b5a69788796a5b4c3d2e1f00"
    )


@pytest.fixture
def sample_options():
    """Create sample projection options."""
    return ProjectionOptions(
        include_ledger=True,
        max_artifacts=100,
        output_mode=OutputMode.NON_TEXTUAL,
        strictness=Strictness.STRICT
    )


# =============================================================================
# Snapshot Read-Only Tests
# =============================================================================

class TestSnapshotReadOnly:
    """Test that snapshot is not mutated during projection."""

    def test_dict_payload_unchanged_thinking(self, mutable_dict_payload, sample_input_ref, sample_options):
        """Dict payload should not be mutated by THINKING layer."""
        payload_before = deep_copy_value(mutable_dict_payload)

        snapshot = FrozenSnapshot(
            snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            payload=mutable_dict_payload,
            content_hash="deadbeefcafebabe1234567890abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run projection
        run_projection(snapshot, request)

        # Compare payload
        payload_after = deep_copy_value(snapshot.payload)
        assert values_equal(payload_before, payload_after), "Payload was mutated by THINKING layer"

    def test_dict_payload_unchanged_meta_observing(self, mutable_dict_payload, sample_input_ref, sample_options):
        """Dict payload should not be mutated by META_OBSERVING layer."""
        payload_before = deep_copy_value(mutable_dict_payload)

        snapshot = FrozenSnapshot(
            snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            payload=mutable_dict_payload,
            content_hash="deadbeefcafebabe1234567890abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.WITNESSES,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run projection
        run_projection(snapshot, request)

        # Compare payload
        payload_after = deep_copy_value(snapshot.payload)
        assert values_equal(payload_before, payload_after), "Payload was mutated by META_OBSERVING layer"

    def test_list_payload_unchanged_unifying(self, mutable_list_payload, sample_input_ref, sample_options):
        """List payload should not be mutated by UNIFYING layer."""
        payload_before = deep_copy_value(mutable_list_payload)

        snapshot = FrozenSnapshot(
            snapshot_id="b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7",
            payload=mutable_list_payload,
            content_hash="cafebabe12345678deadbeef90abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.UNIFYING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run projection
        run_projection(snapshot, request)

        # Compare payload
        payload_after = deep_copy_value(snapshot.payload)
        assert values_equal(payload_before, payload_after), "Payload was mutated by UNIFYING layer"

    def test_snapshot_ids_unchanged(self, mutable_dict_payload, sample_input_ref, sample_options):
        """Snapshot IDs should not be mutated."""
        snapshot = FrozenSnapshot(
            snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            payload=mutable_dict_payload,
            content_hash="deadbeefcafebabe1234567890abcdef"
        )

        original_snapshot_id = snapshot.snapshot_id
        original_content_hash = snapshot.content_hash

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run projection
        run_projection(snapshot, request)

        assert snapshot.snapshot_id == original_snapshot_id
        assert snapshot.content_hash == original_content_hash


# =============================================================================
# Request Read-Only Tests
# =============================================================================

class TestRequestReadOnly:
    """Test that request is not mutated during projection."""

    def test_request_unchanged_after_projection(self, mutable_dict_payload, sample_input_ref, sample_options):
        """Request should not be mutated by projection."""
        snapshot = FrozenSnapshot(
            snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            payload=mutable_dict_payload,
            content_hash="deadbeefcafebabe1234567890abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Deep copy request before
        request_before = asdict(request)

        # Run projection
        run_projection(snapshot, request)

        # Compare request
        request_after = asdict(request)
        assert request_before == request_after, "Request was mutated by projection"

    def test_input_ref_unchanged(self, mutable_dict_payload, sample_options):
        """InputRef should not be mutated by projection."""
        input_ref = InputRef(
            kind=InputRefKind.PHASE5_RESULT,
            object_id="f1e2d3c4b5a69788796a5b4c3d2e1f00"
        )

        original_kind = input_ref.kind
        original_object_id = input_ref.object_id

        snapshot = FrozenSnapshot(
            snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            payload=mutable_dict_payload,
            content_hash="deadbeefcafebabe1234567890abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run projection
        run_projection(snapshot, request)

        assert input_ref.kind == original_kind
        assert input_ref.object_id == original_object_id

    def test_options_unchanged(self, mutable_dict_payload, sample_input_ref):
        """ProjectionOptions should not be mutated by projection."""
        options = ProjectionOptions(
            include_ledger=True,
            max_artifacts=50,
            output_mode=OutputMode.NON_TEXTUAL,
            strictness=Strictness.AUDIT_STRICT
        )

        original_options = asdict(options)

        snapshot = FrozenSnapshot(
            snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            payload=mutable_dict_payload,
            content_hash="deadbeefcafebabe1234567890abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.WITNESSES,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.AUDIT,
            options=options
        )

        # Run projection
        run_projection(snapshot, request)

        options_after = asdict(options)
        assert original_options == options_after, "Options were mutated by projection"


# =============================================================================
# Multiple Run Read-Only Tests
# =============================================================================

class TestMultipleRunsReadOnly:
    """Test read-only across multiple runs."""

    def test_100_runs_no_mutation(self, mutable_list_payload, sample_input_ref, sample_options):
        """Payload should remain unchanged after 100 projection runs."""
        payload_before = deep_copy_value(mutable_list_payload)

        snapshot = FrozenSnapshot(
            snapshot_id="c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7b8",
            payload=mutable_list_payload,
            content_hash="1234567890abcdefdeadbeefcafebabe"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.UNIFYING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run 100 times
        for i in range(100):
            run_projection(snapshot, request)
            payload_after = deep_copy_value(snapshot.payload)
            assert values_equal(payload_before, payload_after), f"Payload mutated on run {i+1}"

    def test_all_layers_no_mutation(self, mutable_dict_payload, sample_input_ref, sample_options):
        """All implemented layers should not mutate payload."""
        payload_before = deep_copy_value(mutable_dict_payload)

        snapshot = FrozenSnapshot(
            snapshot_id="d4e5f6a7b8c9d0e1f2a3b4c5d6a7b8c9",
            payload=mutable_dict_payload,
            content_hash="abcdef1234567890deadbeefcafebabe"
        )

        for layer in [OntologicalLayer.COGNITION, OntologicalLayer.WITNESSES, OntologicalLayer.UNIFYING]:
            request = ProjectionRequest(
                snapshot_id=snapshot.snapshot_id,
                layer=layer,
                input_ref=sample_input_ref,
                projection_profile=ProjectionProfile.STANDARD,
                options=sample_options
            )

            run_projection(snapshot, request)

            payload_after = deep_copy_value(snapshot.payload)
            assert values_equal(payload_before, payload_after), f"Payload mutated by {layer.name}"


# =============================================================================
# JSON Serialization Read-Only Tests
# =============================================================================

class TestJsonSerializationReadOnly:
    """Test read-only by comparing JSON serializations."""

    def test_json_unchanged_after_projection(self, mutable_dict_payload, sample_input_ref, sample_options):
        """JSON serialization of payload should be identical before/after."""
        json_before = json.dumps(mutable_dict_payload, sort_keys=True)

        snapshot = FrozenSnapshot(
            snapshot_id="e5f6a7b8c9d0e1f2a3b4c5d6a7b8c9d0",
            payload=mutable_dict_payload,
            content_hash="beefcafedeadbeef1234567890abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run projection
        run_projection(snapshot, request)

        json_after = json.dumps(snapshot.payload, sort_keys=True)
        assert json_before == json_after, "JSON serialization changed after projection"


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
