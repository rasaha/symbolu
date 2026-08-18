"""Deterministic builders for the benchmark-contract test suite.

Every value is a fixed literal. Nothing here reads a clock, an environment
variable, a random source or the filesystem, so two runs on two machines build
byte-identical contracts and therefore identical digests — which is what makes
the pinned digest vectors meaningful.

The builders take keyword overrides so a test can move exactly one coordinate
and assert exactly one consequence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ugence_benchmark_registry.api import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkApprovalReference,
    BenchmarkCoordinate,
    BenchmarkEffectivePeriod,
    BenchmarkLifecycleState,
    BenchmarkMeasurementSemantics,
    BenchmarkScope,
    BenchmarkSourceRequirements,
    BenchmarkSupersessionDeclaration,
    CanonicalBenchmarkDefinitionIdentity,
)

#: A fixed, obviously-synthetic content digest. Not derived from any real
#: benchmark content: BR-1 never holds content, only the declared digest.
CONTENT_DIGEST = "a" * 64
OTHER_CONTENT_DIGEST = "b" * 64

EFFECTIVE_FROM = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
EFFECTIVE_TO = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
INSIDE = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
BEFORE = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


def scope(**kw) -> BenchmarkScope:
    values = {"kind": BenchmarkScope.for_tenant("tenant-alpha").kind,
              "tenant_id": "tenant-alpha"}
    values.update(kw)
    return BenchmarkScope(**values)


def coordinate(**kw) -> BenchmarkCoordinate:
    values = {
        "benchmark_id": "bmk-support-resolution-time",
        "benchmark_family": "operational-efficiency",
        "benchmark_version": "1.4.0",
        "scope": scope(),
        "geography": BenchmarkApplicabilityCoordinate.applicable("EU"),
        "domain": BenchmarkApplicabilityCoordinate.applicable("customer-support"),
    }
    values.update(kw)
    return BenchmarkCoordinate(**values)


def measurement(**kw) -> BenchmarkMeasurementSemantics:
    values = {
        "intended_outcome_ref": "outcome-faster-resolution",
        "metric_ref": "metric-median-resolution-minutes",
        "unit": "minutes",
        "measurement_protocol_ref": "protocol-ticket-timestamp-v2",
        "population_ref": "cohort-tier1-inbound",
        "aggregation_semantics_ref": "aggregation-median-per-week",
        "observation_window_ref": "window-trailing-90d",
    }
    values.update(kw)
    return BenchmarkMeasurementSemantics(**values)


def effective_period(**kw) -> BenchmarkEffectivePeriod:
    if kw:
        return BenchmarkEffectivePeriod(**kw)
    return BenchmarkEffectivePeriod.bounded(EFFECTIVE_FROM, EFFECTIVE_TO)


def source_requirements(**kw) -> BenchmarkSourceRequirements:
    values = {
        "source_ref": "source-industry-panel-2026",
        # Deliberately supplied out of sorted order: the contract normalizes an
        # order-irrelevant set, so this and the sorted spelling share a digest.
        "provenance_requirement_refs": (
            "provenance-independent-audit",
            "provenance-attributable-producer",
        ),
    }
    values.update(kw)
    return BenchmarkSourceRequirements(**values)


def approval(**kw) -> BenchmarkApprovalReference:
    values = {
        "approval_ref": "approval-bmk-2026-0142",
        "approval_authority_ref": "authority-benchmark-governance-board",
        "approved_content_digest": CONTENT_DIGEST,
    }
    values.update(kw)
    return BenchmarkApprovalReference(**values)


def identity(**kw) -> CanonicalBenchmarkDefinitionIdentity:
    values = {
        "coordinate": coordinate(),
        "content_digest": CONTENT_DIGEST,
        "measurement": measurement(),
        "effective_period": effective_period(),
        "source_requirements": source_requirements(),
        "approval": approval(),
        "publisher_id": "publisher-benchmark-authoring-office",
        "lifecycle_state": BenchmarkLifecycleState.REGISTERED,
        "supersession": BenchmarkSupersessionDeclaration.undetermined(),
    }
    values.update(kw)
    return CanonicalBenchmarkDefinitionIdentity(**values)


def minimal_identity(**kw) -> CanonicalBenchmarkDefinitionIdentity:
    """The smallest identity the contracts admit.

    Platform-wide scope, both applicability coordinates explicitly
    ``NOT_APPLICABLE``, an open-ended effective period, one provenance
    requirement, and the earliest lifecycle state. Every §15 coordinate is still
    present — "minimal" here means minimal *content*, never a missing
    coordinate, because no coordinate can be omitted.
    """

    values = {
        "coordinate": BenchmarkCoordinate(
            benchmark_id="bmk-min",
            benchmark_family="family-min",
            benchmark_version="0.1.0",
            scope=BenchmarkScope.platform_wide(),
            geography=BenchmarkApplicabilityCoordinate.not_applicable(),
            domain=BenchmarkApplicabilityCoordinate.not_applicable(),
        ),
        "content_digest": CONTENT_DIGEST,
        "measurement": BenchmarkMeasurementSemantics(
            intended_outcome_ref="o",
            metric_ref="m",
            unit="u",
            measurement_protocol_ref="p",
            population_ref="c",
            aggregation_semantics_ref="a",
            observation_window_ref="w",
        ),
        "effective_period": BenchmarkEffectivePeriod.open_ended(EFFECTIVE_FROM),
        "source_requirements": BenchmarkSourceRequirements(
            source_ref="s", provenance_requirement_refs=("r",)
        ),
        "approval": BenchmarkApprovalReference(
            approval_ref="ap",
            approval_authority_ref="auth",
            approved_content_digest=CONTENT_DIGEST,
        ),
        "publisher_id": "pub",
        "lifecycle_state": BenchmarkLifecycleState.AUTHORED,
        "supersession": BenchmarkSupersessionDeclaration.undetermined(),
    }
    values.update(kw)
    return CanonicalBenchmarkDefinitionIdentity(**values)
