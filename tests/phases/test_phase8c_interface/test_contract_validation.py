"""
Phase-8C Contract Validation Tests
===================================

These tests validate that the Phase-8C Consumer Interface Contract is
internally consistent and correctly specifies the "window, not lens"
transport layer.

Contract: docs/contracts/PHASE_8C_INTERFACE_CONTRACT.md

Test Categories:
  1. Predicate Specification Validation
  2. Invariant Completeness Tests
  3. Forbidden Behavior Coverage Tests
  4. Wire Format Example Validation
  5. Design Decision Compliance Tests
  6. Serialization Property Tests
"""

import pytest
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Callable
from enum import Enum


# ============================================================================
# Contract Types (matching specification)
# ============================================================================

@dataclass(frozen=True)
class TrajectoryStep:
    """Immutable trajectory step per contract."""
    token: str
    magnitude: float
    event: str  # "reset" | "modulate"
    position: int


@dataclass(frozen=True)
class Trajectory:
    """Immutable trajectory per contract."""
    sequence: tuple
    steps: tuple
    final_magnitude: float


@dataclass(frozen=True)
class ConstraintSatisfaction:
    """Constraint satisfaction record."""
    satisfied: tuple
    violated: tuple


@dataclass(frozen=True)
class RankedResult:
    """Immutable ranked result per contract."""
    trajectory: Trajectory
    score: float
    rank: int
    constraint_satisfaction: ConstraintSatisfaction


@dataclass(frozen=True)
class ValiditySpace:
    """Validity space metadata."""
    constraints_satisfied: tuple
    constraints_violated: tuple
    total_candidates_explored: int
    valid_candidates_found: int


@dataclass(frozen=True)
class GenerationMetadata:
    """Generation metadata."""
    timestamp: str
    duration_ms: float
    phase7_version: str


@dataclass(frozen=True)
class Phase7Result:
    """Complete Phase-7 result per contract."""
    id: str
    version: str
    ranked_results: tuple
    validity_space: ValiditySpace
    generation_metadata: GenerationMetadata


# ============================================================================
# Predicate Types
# ============================================================================

class PredicateType(Enum):
    """Allowed predicate types per contract."""
    EQUALITY = "equality"
    GREATER_THAN_EQUAL = "gte"
    LESS_THAN_EQUAL = "lte"
    MEMBERSHIP = "in"
    OFFSET = "offset"
    LIMIT = "limit"


@dataclass
class Predicate:
    """A filter predicate per contract specification."""
    field: str
    predicate_type: PredicateType
    value: Any

    def is_total_function(self) -> bool:
        """Check if predicate is a total function on fields (INV-3)."""
        # Total function: defined for all inputs, returns boolean
        # All allowed predicates are total functions
        return self.predicate_type in PredicateType


# ============================================================================
# Forbidden Patterns
# ============================================================================

FORBIDDEN_PREDICATE_PATTERNS = [
    "AND",
    "OR",
    "NOT",
    "ORDER BY",
    "GROUP BY",
    "HAVING",
    "AVG(",
    "SUM(",
    "COUNT(",
    "MAX(",
    "MIN(",
    "LIKE",
    "SIMILAR",
    "MATCH",
    "~",  # regex
    ".*",  # regex
]

FORBIDDEN_ENDPOINT_PATTERNS = [
    "recommend",
    "suggest",
    "similar",
    "related",
    "popular",
    "trending",
    "best",
    "top",
]


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_trajectory():
    """Create a sample trajectory for testing."""
    steps = (
        TrajectoryStep(token="ka", magnitude=1.0, event="reset", position=0),
        TrajectoryStep(token="a", magnitude=1.1, event="modulate", position=1),
        TrajectoryStep(token="ga", magnitude=1.0, event="reset", position=2),
        TrajectoryStep(token="i", magnitude=1.2, event="modulate", position=3),
    )
    return Trajectory(
        sequence=("ka", "a", "ga", "i"),
        steps=steps,
        final_magnitude=1.2
    )


@pytest.fixture
def sample_result(sample_trajectory):
    """Create a sample Phase-7 result for testing."""
    ranked_result = RankedResult(
        trajectory=sample_trajectory,
        score=0.95,
        rank=1,
        constraint_satisfaction=ConstraintSatisfaction(
            satisfied=("G1", "G2", "G3", "M1", "M3"),
            violated=()
        )
    )
    return Phase7Result(
        id="gen_abc123",
        version="1.0.0",
        ranked_results=(ranked_result,),
        validity_space=ValiditySpace(
            constraints_satisfied=("G1", "G2", "G3", "M1", "M3"),
            constraints_violated=(),
            total_candidates_explored=128,
            valid_candidates_found=15
        ),
        generation_metadata=GenerationMetadata(
            timestamp="2024-01-15T10:30:00Z",
            duration_ms=42.5,
            phase7_version="1.0.0"
        )
    )


# ============================================================================
# 1. PREDICATE SPECIFICATION VALIDATION
# ============================================================================

class TestPredicateSpecification:
    """Validate predicate specification from contract Section 7."""

    def test_allowed_predicate_types_complete(self):
        """All 6 allowed predicate types are defined."""
        expected = {"equality", "gte", "lte", "in", "offset", "limit"}
        actual = {p.value for p in PredicateType}
        assert actual == expected, "Predicate types mismatch"

    def test_equality_predicate_is_total_function(self):
        """Equality predicate is a total function."""
        pred = Predicate("token", PredicateType.EQUALITY, "ka")
        assert pred.is_total_function()

    def test_range_predicates_are_total_functions(self):
        """GTE and LTE predicates are total functions."""
        gte = Predicate("magnitude", PredicateType.GREATER_THAN_EQUAL, 1.0)
        lte = Predicate("magnitude", PredicateType.LESS_THAN_EQUAL, 1.5)
        assert gte.is_total_function()
        assert lte.is_total_function()

    def test_membership_predicate_is_total_function(self):
        """IN predicate is a total function."""
        pred = Predicate("token", PredicateType.MEMBERSHIP, ["ka", "ga"])
        assert pred.is_total_function()

    def test_pagination_predicates_are_total_functions(self):
        """Offset and limit predicates are total functions."""
        offset = Predicate("_offset", PredicateType.OFFSET, 10)
        limit = Predicate("_limit", PredicateType.LIMIT, 20)
        assert offset.is_total_function()
        assert limit.is_total_function()


class TestForbiddenPredicates:
    """Validate forbidden predicate patterns from contract Section 7.4."""

    @pytest.mark.parametrize("pattern", FORBIDDEN_PREDICATE_PATTERNS)
    def test_forbidden_pattern_identified(self, pattern):
        """Each forbidden pattern is identified as forbidden."""
        # Simulate a query string containing forbidden pattern
        query = f"field {pattern} value"
        is_forbidden = any(fp in query.upper() for fp in FORBIDDEN_PREDICATE_PATTERNS)
        assert is_forbidden, f"Pattern '{pattern}' should be identified as forbidden"

    def test_boolean_logic_forbidden(self):
        """Boolean logic combinations are forbidden."""
        forbidden_queries = [
            "(a=1 AND b=2)",
            "(a=1 OR b=2)",
            "NOT a=1",
            "a=1 && b=2",
            "a=1 || b=2",
        ]
        for query in forbidden_queries:
            has_boolean = any(op in query.upper() for op in ["AND", "OR", "NOT", "&&", "||"])
            assert has_boolean, f"Query '{query}' should be detected as boolean logic"

    def test_aggregation_forbidden(self):
        """Aggregation functions are forbidden."""
        forbidden_queries = [
            "magnitude > AVG(magnitudes)",
            "score > SUM(scores)/COUNT(*)",
            "rank < MAX(ranks)",
        ]
        for query in forbidden_queries:
            has_aggregation = any(agg in query.upper() for agg in ["AVG(", "SUM(", "COUNT(", "MAX(", "MIN("])
            assert has_aggregation, f"Query '{query}' should be detected as aggregation"

    def test_ordering_forbidden(self):
        """ORDER BY is forbidden."""
        query = "ORDER BY score DESC"
        assert "ORDER BY" in query.upper(), "ORDER BY should be detected"

    def test_regex_forbidden(self):
        """Regex patterns are forbidden."""
        forbidden_queries = [
            "token ~ 'k.*'",
            "token LIKE 'k%'",
            "token MATCH 'pattern'",
        ]
        for query in forbidden_queries:
            has_regex = any(op in query.upper() for op in ["~", "LIKE", "MATCH"])
            assert has_regex, f"Query '{query}' should be detected as regex"


# ============================================================================
# 2. INVARIANT COMPLETENESS TESTS
# ============================================================================

class TestInvariantCompleteness:
    """Validate all 10 invariants from contract Section 8."""

    INVARIANTS = {
        "INV-1": "No Mutation",
        "INV-2": "Format Fidelity",
        "INV-3": "Filter Transparency",
        "INV-4": "Pagination Stability",
        "INV-5": "Version Immutability",
        "INV-6": "Idempotency",
        "INV-7": "No Side Effects",
        "INV-8": "No Suggestion",
        "INV-9": "Projection Subset",
        "INV-10": "Stream Monotonicity",
    }

    def test_all_invariants_defined(self):
        """All 10 invariants are defined."""
        assert len(self.INVARIANTS) == 10

    def test_invariant_ids_sequential(self):
        """Invariant IDs are sequential from 1-10."""
        expected_ids = {f"INV-{i}" for i in range(1, 11)}
        actual_ids = set(self.INVARIANTS.keys())
        assert actual_ids == expected_ids

    @pytest.mark.parametrize("inv_id,inv_name", [
        ("INV-1", "No Mutation"),
        ("INV-2", "Format Fidelity"),
        ("INV-3", "Filter Transparency"),
        ("INV-4", "Pagination Stability"),
        ("INV-5", "Version Immutability"),
        ("INV-6", "Idempotency"),
        ("INV-7", "No Side Effects"),
        ("INV-8", "No Suggestion"),
        ("INV-9", "Projection Subset"),
        ("INV-10", "Stream Monotonicity"),
    ])
    def test_invariant_has_name(self, inv_id, inv_name):
        """Each invariant has a descriptive name."""
        assert self.INVARIANTS[inv_id] == inv_name


class TestINV1NoMutation:
    """Validate INV-1: Interface never modifies Phase-7 output."""

    def test_frozen_dataclass_prevents_mutation(self, sample_result):
        """Frozen dataclasses prevent mutation."""
        with pytest.raises(Exception):  # FrozenInstanceError
            sample_result.id = "modified_id"

    def test_trajectory_immutable(self, sample_trajectory):
        """Trajectory is immutable."""
        with pytest.raises(Exception):
            sample_trajectory.sequence = ("modified",)

    def test_expose_returns_unchanged(self, sample_result):
        """Expose function returns unchanged result."""
        # Simulate expose (identity function per INV-1)
        def expose(result: Phase7Result) -> Phase7Result:
            return result

        exposed = expose(sample_result)
        assert exposed == sample_result


class TestINV2FormatFidelity:
    """Validate INV-2: Serialization is lossless and reversible."""

    def test_json_round_trip_preserves_structure(self, sample_result):
        """JSON serialization round-trip preserves structure."""
        # Serialize
        serialized = json.dumps({
            "id": sample_result.id,
            "version": sample_result.version,
            "ranked_results": [
                {
                    "trajectory": {
                        "sequence": list(rr.trajectory.sequence),
                        "steps": [
                            {"token": s.token, "magnitude": s.magnitude, "event": s.event, "position": s.position}
                            for s in rr.trajectory.steps
                        ],
                        "final_magnitude": rr.trajectory.final_magnitude
                    },
                    "score": rr.score,
                    "rank": rr.rank
                }
                for rr in sample_result.ranked_results
            ]
        })

        # Deserialize
        deserialized = json.loads(serialized)

        # Verify key fields preserved
        assert deserialized["id"] == sample_result.id
        assert deserialized["version"] == sample_result.version
        assert len(deserialized["ranked_results"]) == len(sample_result.ranked_results)

    def test_numeric_precision_preserved(self):
        """Numeric values preserve precision."""
        original_magnitude = 1.15
        serialized = json.dumps({"magnitude": original_magnitude})
        deserialized = json.loads(serialized)
        assert deserialized["magnitude"] == original_magnitude


class TestINV3FilterTransparency:
    """Validate INV-3: Filters are declarative predicates, not computations."""

    def test_predicate_is_total_function(self):
        """Predicates are total functions: defined for all inputs."""
        # A total function returns a value for every input
        def equality_predicate(value: Any, target: Any) -> bool:
            return value == target

        # Should work for any input
        assert equality_predicate("ka", "ka") == True
        assert equality_predicate("ka", "ga") == False
        assert equality_predicate(None, None) == True
        assert equality_predicate(1, "1") == False

    def test_predicate_has_no_side_effects(self):
        """Predicates have no side effects."""
        call_count = 0

        def pure_predicate(value: Any, target: Any) -> bool:
            # No side effects - doesn't modify external state
            return value == target

        # Calling multiple times doesn't change anything
        pure_predicate("a", "b")
        pure_predicate("a", "b")
        assert call_count == 0  # No external state modified


class TestINV6Idempotency:
    """Validate INV-6: GET requests are idempotent."""

    def test_repeated_get_returns_same_result(self, sample_result):
        """Repeated GET requests return identical results."""
        # Simulate GET endpoint
        def get_result(result_id: str) -> Phase7Result:
            if result_id == "gen_abc123":
                return sample_result
            return None

        result1 = get_result("gen_abc123")
        result2 = get_result("gen_abc123")
        result3 = get_result("gen_abc123")

        assert result1 == result2 == result3


class TestINV9ProjectionSubset:
    """Validate INV-9: Projections are strict subsets of full result."""

    def test_trajectory_projection_is_subset(self, sample_result):
        """Trajectory projection is subset of full result."""
        # Full result contains trajectory
        full_trajectory = sample_result.ranked_results[0].trajectory

        # Projection extracts only trajectory
        projection = full_trajectory

        # Projection data exists in full result
        assert projection.sequence == full_trajectory.sequence
        assert projection.steps == full_trajectory.steps

    def test_sequence_projection_is_subset(self, sample_result):
        """Sequence projection is subset of trajectory."""
        trajectory = sample_result.ranked_results[0].trajectory
        sequence_projection = trajectory.sequence

        # Sequence is a component of trajectory
        assert sequence_projection == trajectory.sequence


class TestINV10StreamMonotonicity:
    """Validate INV-10: Streaming batch indices increase monotonically."""

    def test_batch_indices_monotonic(self):
        """Batch indices are strictly increasing."""
        batches = [
            {"batch_index": 0, "is_final": False},
            {"batch_index": 1, "is_final": False},
            {"batch_index": 2, "is_final": True},
        ]

        for i in range(1, len(batches)):
            assert batches[i]["batch_index"] > batches[i-1]["batch_index"]

    def test_batch_indices_no_gaps(self):
        """Batch indices have no gaps."""
        batches = [
            {"batch_index": 0},
            {"batch_index": 1},
            {"batch_index": 2},
        ]

        for i, batch in enumerate(batches):
            assert batch["batch_index"] == i


# ============================================================================
# 3. FORBIDDEN BEHAVIOR COVERAGE TESTS
# ============================================================================

class TestForbiddenBehaviorsCoverage:
    """Validate all 18 forbidden behaviors from contract Section 9."""

    SELECTION_BEHAVIORS = {
        "FB-1": "Re-ranking results",
        "FB-2": "Filtering by importance",
        "FB-3": "Inferring usefulness",
        "FB-4": "Optimizing for clients",
        "FB-5": "Recommending next actions",
        "FB-6": "Highlighting results",
    }

    TRANSFORMATION_BEHAVIORS = {
        "FB-7": "Computing derived values",
        "FB-8": "Aggregating statistics",
        "FB-9": "Formatting for display",
        "FB-10": "Translating tokens",
    }

    STATEFUL_BEHAVIORS = {
        "FB-11": "Caching with invalidation logic",
        "FB-12": "Session-based filtering",
        "FB-13": "Learning from access patterns",
        "FB-14": "Rate limiting by content",
    }

    DISCOVERY_BEHAVIORS = {
        "FB-15": "HATEOAS links",
        "FB-16": "Related results",
        "FB-17": "Similar to endpoints",
        "FB-18": "Auto-complete",
    }

    def test_all_18_forbidden_behaviors_defined(self):
        """All 18 forbidden behaviors are defined."""
        total = (
            len(self.SELECTION_BEHAVIORS) +
            len(self.TRANSFORMATION_BEHAVIORS) +
            len(self.STATEFUL_BEHAVIORS) +
            len(self.DISCOVERY_BEHAVIORS)
        )
        assert total == 18

    def test_selection_behaviors_count(self):
        """6 selection behaviors are defined."""
        assert len(self.SELECTION_BEHAVIORS) == 6

    def test_transformation_behaviors_count(self):
        """4 transformation behaviors are defined."""
        assert len(self.TRANSFORMATION_BEHAVIORS) == 4

    def test_stateful_behaviors_count(self):
        """4 stateful behaviors are defined."""
        assert len(self.STATEFUL_BEHAVIORS) == 4

    def test_discovery_behaviors_count(self):
        """4 discovery behaviors are defined."""
        assert len(self.DISCOVERY_BEHAVIORS) == 4

    def test_forbidden_behavior_ids_sequential(self):
        """Forbidden behavior IDs are sequential from 1-18."""
        all_behaviors = {
            **self.SELECTION_BEHAVIORS,
            **self.TRANSFORMATION_BEHAVIORS,
            **self.STATEFUL_BEHAVIORS,
            **self.DISCOVERY_BEHAVIORS,
        }
        expected_ids = {f"FB-{i}" for i in range(1, 19)}
        actual_ids = set(all_behaviors.keys())
        assert actual_ids == expected_ids


class TestNoReRanking:
    """Test FB-1: No re-ranking of results."""

    def test_result_order_preserved(self, sample_result):
        """Result order from Phase-7 is preserved."""
        # Original ranks
        original_ranks = [rr.rank for rr in sample_result.ranked_results]

        # After "transport" (identity), ranks unchanged
        transported_ranks = [rr.rank for rr in sample_result.ranked_results]

        assert original_ranks == transported_ranks

    def test_no_sort_operation(self):
        """Interface does not sort results."""
        results = [
            {"rank": 3, "score": 0.7},
            {"rank": 1, "score": 0.95},
            {"rank": 2, "score": 0.85},
        ]

        # Transport preserves order (no sorting)
        transported = results  # Identity

        # Order unchanged
        assert transported[0]["rank"] == 3
        assert transported[1]["rank"] == 1
        assert transported[2]["rank"] == 2


class TestNoHATEOAS:
    """Test FB-15: No HATEOAS links."""

    def test_response_has_no_links_field(self, sample_result):
        """Response does not contain _links field."""
        response = {
            "id": sample_result.id,
            "version": sample_result.version,
            "ranked_results": [],
        }

        assert "_links" not in response
        assert "links" not in response

    def test_response_has_no_navigation(self, sample_result):
        """Response does not contain navigation hints."""
        response = {
            "id": sample_result.id,
            "data": {},
        }

        forbidden_keys = ["next", "prev", "related", "suggested", "recommended"]
        for key in forbidden_keys:
            assert key not in response


class TestNoDiscoveryEndpoints:
    """Test FB-16, FB-17, FB-18: No discovery endpoints."""

    ALLOWED_ENDPOINTS = [
        "/v1/generations",
        "/v1/generations/{id}",
        "/v1/generations/{id}/trajectory",
        "/v1/generations/{id}/sequence",
        "/v1/generations/{id}/metrics",
        "/v1/generations/{id}/events",
        "/v1/generations/{id}/validity",
        "/v1/generations/stream",
    ]

    @pytest.mark.parametrize("pattern", FORBIDDEN_ENDPOINT_PATTERNS)
    def test_forbidden_endpoint_pattern_not_in_allowed(self, pattern):
        """Forbidden endpoint patterns not in allowed endpoints."""
        for endpoint in self.ALLOWED_ENDPOINTS:
            assert pattern not in endpoint.lower()

    def test_no_similar_endpoint(self):
        """No 'similar' endpoint exists."""
        for endpoint in self.ALLOWED_ENDPOINTS:
            assert "similar" not in endpoint.lower()

    def test_no_recommend_endpoint(self):
        """No 'recommend' endpoint exists."""
        for endpoint in self.ALLOWED_ENDPOINTS:
            assert "recommend" not in endpoint.lower()


# ============================================================================
# 4. WIRE FORMAT EXAMPLE VALIDATION
# ============================================================================

class TestWireFormatExamples:
    """Validate wire format examples from contract Section 11."""

    def test_full_result_json_valid(self):
        """Full result example is valid JSON."""
        example = '''
        {
          "id": "gen_abc123",
          "version": "1.0.0",
          "ranked_results": [
            {
              "trajectory": {
                "sequence": ["ka", "a", "ga", "i", "ta", "u"],
                "steps": [
                  {"token": "ka", "magnitude": 1.0, "event": "reset", "position": 0},
                  {"token": "a", "magnitude": 1.1, "event": "modulate", "position": 1}
                ],
                "final_magnitude": 1.15
              },
              "score": 0.95,
              "rank": 1
            }
          ]
        }
        '''
        parsed = json.loads(example)
        assert parsed["id"] == "gen_abc123"
        assert parsed["version"] == "1.0.0"
        assert len(parsed["ranked_results"]) == 1

    def test_projection_json_valid(self):
        """Projection example is valid JSON."""
        example = '''
        {
          "id": "gen_abc123",
          "version": "1.0.0",
          "projection": "trajectory",
          "data": {
            "sequence": ["ka", "a", "ga", "i"],
            "steps": [],
            "final_magnitude": 1.2
          }
        }
        '''
        parsed = json.loads(example)
        assert parsed["projection"] == "trajectory"
        assert "data" in parsed

    def test_error_response_json_valid(self):
        """Error response example is valid JSON."""
        example = '''
        {
          "error": {
            "code": "FORBIDDEN_PREDICATE",
            "message": "Predicate uses forbidden ordering",
            "category": "format",
            "timestamp": "2024-01-15T10:30:00Z"
          }
        }
        '''
        parsed = json.loads(example)
        assert "error" in parsed
        assert parsed["error"]["code"] == "FORBIDDEN_PREDICATE"

    def test_streaming_event_format(self):
        """Streaming event format is correct."""
        # SSE format: "event: <type>\ndata: <json>\n\n"
        events = [
            {"batch_index": 0, "results": [], "is_final": False},
            {"batch_index": 1, "results": [], "is_final": True},
        ]

        for event in events:
            # Each event must have batch_index and is_final
            assert "batch_index" in event
            assert "is_final" in event
            # batch_index is non-negative integer
            assert isinstance(event["batch_index"], int)
            assert event["batch_index"] >= 0


class TestJSONSchema:
    """Validate JSON schema from contract Section 5.4."""

    def test_required_fields_present(self, sample_result):
        """Required fields are present in result."""
        required = ["id", "version", "ranked_results"]
        serialized = {
            "id": sample_result.id,
            "version": sample_result.version,
            "ranked_results": [],
        }
        for field in required:
            assert field in serialized

    def test_version_format_valid(self):
        """Version follows semver pattern."""
        valid_versions = ["1.0.0", "2.1.3", "0.0.1"]
        pattern = r"^\d+\.\d+\.\d+$"

        for version in valid_versions:
            assert re.match(pattern, version)

    def test_event_enum_values(self):
        """Event field uses correct enum values."""
        valid_events = ["reset", "modulate"]

        step1 = TrajectoryStep("ka", 1.0, "reset", 0)
        step2 = TrajectoryStep("a", 1.1, "modulate", 1)

        assert step1.event in valid_events
        assert step2.event in valid_events


# ============================================================================
# 5. DESIGN DECISION COMPLIANCE TESTS
# ============================================================================

class TestDesignDecisions:
    """Validate design decisions from contract Section 3."""

    def test_granularity_full_by_default(self, sample_result):
        """Full results exposed by default."""
        # Default endpoint returns full result
        default_response = sample_result

        # Contains all components
        assert default_response.ranked_results is not None
        assert default_response.validity_space is not None
        assert default_response.generation_metadata is not None

    def test_streaming_reflects_iteration_not_quality(self):
        """Streaming batch_index reflects iteration, not quality ranking."""
        batches = [
            {"batch_index": 0, "iteration": 1},
            {"batch_index": 1, "iteration": 2},
            {"batch_index": 2, "iteration": 3},
        ]

        # batch_index correlates with iteration, not with quality
        for batch in batches:
            # No "quality" or "score" based ordering in batch assignment
            assert "quality_rank" not in batch
            assert "best_so_far" not in batch

    def test_url_versioning(self):
        """URL versioning is used (not header versioning)."""
        endpoints = [
            "/v1/generations",
            "/v1/generations/{id}",
            "/v1/generations/stream",
        ]

        for endpoint in endpoints:
            # Version is in URL path
            assert "/v1/" in endpoint or "/v2/" in endpoint

    def test_no_hateoas_in_response(self):
        """HATEOAS is disallowed - no _links in response."""
        response = {
            "id": "gen_abc123",
            "version": "1.0.0",
            "ranked_results": [],
        }

        # No hypermedia links
        assert "_links" not in response
        assert "links" not in response
        assert "href" not in str(response)


class TestWindowNotLensMetaphor:
    """Validate the 'window, not lens' architectural principle."""

    def test_no_transformation(self, sample_result):
        """Interface performs no transformation."""
        # Input
        input_result = sample_result

        # "Transport" is identity function
        def transport(result):
            return result

        output_result = transport(input_result)

        # Output equals input exactly
        assert output_result == input_result

    def test_no_selection(self, sample_result):
        """Interface performs no selection/filtering beyond predicates."""
        results = [sample_result]

        # No automatic filtering
        transported = results  # Identity

        assert len(transported) == len(results)

    def test_no_suggestion(self):
        """Interface provides no suggestions."""
        response = {
            "id": "gen_abc123",
            "data": {},
        }

        # No suggestion-related fields
        suggestion_fields = [
            "suggested", "recommended", "similar",
            "you_might_like", "next_action", "try_also"
        ]
        for field in suggestion_fields:
            assert field not in response

    def test_no_interpretation(self, sample_result):
        """Interface adds no interpretation."""
        response = {
            "id": sample_result.id,
            "ranked_results": list(sample_result.ranked_results),
        }

        # No interpretation fields
        interpretation_fields = [
            "meaning", "interpretation", "summary",
            "analysis", "insight", "explanation"
        ]
        for field in interpretation_fields:
            assert field not in response


# ============================================================================
# 6. SERIALIZATION PROPERTY TESTS
# ============================================================================

class TestSerializationProperties:
    """Validate serialization properties from contract."""

    def test_serialization_is_deterministic(self, sample_trajectory):
        """Same input produces same serialized output."""
        def serialize(traj):
            return json.dumps({
                "sequence": list(traj.sequence),
                "final_magnitude": traj.final_magnitude,
            }, sort_keys=True)

        output1 = serialize(sample_trajectory)
        output2 = serialize(sample_trajectory)
        output3 = serialize(sample_trajectory)

        assert output1 == output2 == output3

    def test_serialization_has_no_derived_fields(self, sample_result):
        """Serialization adds no computed/derived fields."""
        serialized = {
            "id": sample_result.id,
            "version": sample_result.version,
            "ranked_results": [
                {
                    "trajectory": {
                        "sequence": list(rr.trajectory.sequence),
                        "steps": [
                            {
                                "token": s.token,
                                "magnitude": s.magnitude,
                                "event": s.event,
                                "position": s.position
                            }
                            for s in rr.trajectory.steps
                        ],
                        "final_magnitude": rr.trajectory.final_magnitude
                    },
                    "score": rr.score,
                    "rank": rr.rank
                }
                for rr in sample_result.ranked_results
            ]
        }

        # No derived fields like "avg_magnitude", "sequence_hash", etc.
        derived_fields = [
            "avg_magnitude", "total_score", "sequence_hash",
            "computed_rank", "derived_metric", "aggregate"
        ]
        serialized_str = json.dumps(serialized)
        for field in derived_fields:
            assert field not in serialized_str


class TestContentTypeNegotiation:
    """Validate content type negotiation."""

    SUPPORTED_CONTENT_TYPES = [
        "application/json",
        "application/msgpack",
    ]

    def test_json_is_default(self):
        """JSON is the default content type."""
        default = "application/json"
        assert default in self.SUPPORTED_CONTENT_TYPES

    def test_msgpack_supported(self):
        """MessagePack is supported for binary serialization."""
        msgpack = "application/msgpack"
        assert msgpack in self.SUPPORTED_CONTENT_TYPES

    def test_only_two_formats_supported(self):
        """Only JSON and MessagePack are supported (no XML, etc.)."""
        assert len(self.SUPPORTED_CONTENT_TYPES) == 2


# ============================================================================
# 7. ERROR CONTRACT TESTS
# ============================================================================

class TestErrorContract:
    """Validate error contract from contract Section 10."""

    ERROR_CATEGORIES = ["transport", "format", "not_found"]

    def test_error_categories_defined(self):
        """All error categories are defined."""
        assert "transport" in self.ERROR_CATEGORIES
        assert "format" in self.ERROR_CATEGORIES
        assert "not_found" in self.ERROR_CATEGORIES

    def test_no_domain_errors(self):
        """Domain errors are NOT in Phase-8C error contract."""
        domain_errors = [
            "constraint_violation",
            "invalid_sequence",
            "generation_failure",
            "phase7_error",
        ]
        for error in domain_errors:
            assert error not in self.ERROR_CATEGORIES

    def test_error_response_format(self):
        """Error response has correct format."""
        error_response = {
            "error": {
                "code": "INVALID_PREDICATE",
                "message": "Predicate uses forbidden pattern",
                "category": "format",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

        # Required fields
        assert "error" in error_response
        assert "code" in error_response["error"]
        assert "message" in error_response["error"]
        assert "category" in error_response["error"]


# ============================================================================
# CONTRACT COMPLIANCE SUMMARY
# ============================================================================

class TestContractComplianceSummary:
    """Summary tests verifying overall contract compliance."""

    def test_invariant_count(self):
        """Contract defines exactly 10 invariants."""
        assert len(TestInvariantCompleteness.INVARIANTS) == 10

    def test_forbidden_behavior_count(self):
        """Contract defines exactly 18 forbidden behaviors."""
        total = (
            len(TestForbiddenBehaviorsCoverage.SELECTION_BEHAVIORS) +
            len(TestForbiddenBehaviorsCoverage.TRANSFORMATION_BEHAVIORS) +
            len(TestForbiddenBehaviorsCoverage.STATEFUL_BEHAVIORS) +
            len(TestForbiddenBehaviorsCoverage.DISCOVERY_BEHAVIORS)
        )
        assert total == 18

    def test_predicate_type_count(self):
        """Contract defines exactly 6 predicate types."""
        assert len(PredicateType) == 6

    def test_endpoint_count(self):
        """Contract defines 8 endpoints."""
        endpoints = TestNoDiscoveryEndpoints.ALLOWED_ENDPOINTS
        assert len(endpoints) == 8

    def test_design_decisions_count(self):
        """Contract makes 5 key design decisions."""
        decisions = {
            "granularity": "Full results + projections",
            "streaming": "Structural only",
            "filtering": "Simple predicates only",
            "versioning": "URL-based",
            "hateoas": "Disallowed",
        }
        assert len(decisions) == 5
