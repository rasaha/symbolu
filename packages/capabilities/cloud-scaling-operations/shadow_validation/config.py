"""Explicit, immutable configuration for a read-only shadow-validation run.

Nothing is auto-discovered. Every value that scopes what may be observed — cluster,
context, namespaces, resource kinds/names, target cap, timeouts, TLS — must be supplied
explicitly. The config fails closed: it refuses production classification, wildcard
production namespaces, empty allowlists, unbounded target counts, disabled TLS, and any
execution mode other than SHADOW.

Fixture configs used in this phase are clearly marked as fake/local and can never be
mistaken for a real environment (see :meth:`ShadowValidationConfig.fixture`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from .contracts import (
    EVIDENCE_CLASS_FIXTURE,
    NOT_REAL_ENVIRONMENT_EVIDENCE,
    EXECUTION_MODE_SHADOW,
)

# Environment classifications that are acceptable for a shadow run. Production is never
# acceptable; "unclassified" (empty) is rejected.
NON_PRODUCTION_CLASSIFICATIONS = frozenset({
    "disposable_test_fixture",   # this phase's fake/local fixtures
    "disposable_test",
    "dedicated_test",
    "development",
    "staging",
    "isolated_nonprod",
})

# Substrings that mark a classification or namespace as production (rejected).
_PRODUCTION_MARKERS = ("prod", "production", "customer", "live")
_WILDCARDS = ("*", "all", "any", "")


class ShadowConfigError(ValueError):
    """Raised when a shadow configuration is unsafe or incomplete (fail closed)."""


@dataclass(frozen=True)
class ShadowValidationConfig:
    """Immutable, fully-explicit shadow-validation configuration."""

    environment_classification: str
    cluster_identifier: str
    context_name: str
    namespace_allowlist: Tuple[str, ...]
    resource_kind_allowlist: Tuple[str, ...]
    resource_name_allowlist: Tuple[str, ...]
    maximum_target_count: int
    request_timeout_seconds: float
    maximum_observation_age_seconds: float
    tls_verify: bool
    metrics_enabled: bool
    watch_enabled: bool
    audit_output_path: str
    evidence_output_path: str
    # SHADOW is the only permitted mode for this harness.
    execution_mode: str = EXECUTION_MODE_SHADOW
    # Transport is read-only; a mutation-enabled transport is refused.
    mutation_enabled: bool = False
    # Fixture provenance markers (empty for a would-be real config).
    fixture_markers: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self._validate()

    # -- validation --------------------------------------------------------- #
    def _validate(self) -> None:
        def reject(msg: str) -> None:
            raise ShadowConfigError(msg)

        cls = (self.environment_classification or "").strip()
        if not cls:
            reject("environment_classification is required (unclassified is refused)")
        if cls not in NON_PRODUCTION_CLASSIFICATIONS:
            reject(f"environment_classification {cls!r} is not an approved "
                   f"non-production class {sorted(NON_PRODUCTION_CLASSIFICATIONS)}")
        if any(m in cls.lower() for m in _PRODUCTION_MARKERS):
            reject(f"environment_classification {cls!r} looks like production")

        if not self.cluster_identifier or self.cluster_identifier in _WILDCARDS:
            reject("cluster_identifier is required and may not be a wildcard")
        if not self.context_name or self.context_name in _WILDCARDS:
            reject("context_name is required (implicit/current context is refused)")

        if not self.namespace_allowlist:
            reject("namespace_allowlist must be non-empty (fail closed)")
        for ns in self.namespace_allowlist:
            if not ns or ns in _WILDCARDS:
                reject(f"namespace {ns!r} is empty/wildcard")
            if any(m in ns.lower() for m in _PRODUCTION_MARKERS):
                reject(f"namespace {ns!r} looks like a production namespace")

        if not self.resource_kind_allowlist:
            reject("resource_kind_allowlist must be non-empty")
        if not self.resource_name_allowlist:
            reject("resource_name_allowlist must be non-empty")

        if not isinstance(self.maximum_target_count, int) or self.maximum_target_count <= 0:
            reject("maximum_target_count must be a positive, bounded integer")
        if self.maximum_target_count > 1000:
            reject("maximum_target_count is implausibly large (unbounded monitoring)")

        if self.request_timeout_seconds <= 0:
            reject("request_timeout_seconds must be > 0")
        if self.maximum_observation_age_seconds <= 0:
            reject("maximum_observation_age_seconds must be > 0")

        if self.tls_verify is not True:
            reject("tls_verify must be True (insecure TLS is refused)")
        if self.execution_mode != EXECUTION_MODE_SHADOW:
            reject("execution_mode must be SHADOW")
        if self.mutation_enabled:
            reject("mutation_enabled must be False (mutation transport is refused)")

    @property
    def is_fixture(self) -> bool:
        return EVIDENCE_CLASS_FIXTURE in self.fixture_markers

    def summary(self) -> dict:
        """A redaction-safe, JSON-serializable summary (no credentials present)."""
        return {
            "environment_classification": self.environment_classification,
            "cluster_identifier": self.cluster_identifier,
            "context_name": self.context_name,
            "namespace_allowlist": list(self.namespace_allowlist),
            "resource_kind_allowlist": list(self.resource_kind_allowlist),
            "resource_name_allowlist": list(self.resource_name_allowlist),
            "maximum_target_count": self.maximum_target_count,
            "request_timeout_seconds": self.request_timeout_seconds,
            "maximum_observation_age_seconds": self.maximum_observation_age_seconds,
            "tls_verify": self.tls_verify,
            "metrics_enabled": self.metrics_enabled,
            "watch_enabled": self.watch_enabled,
            "execution_mode": self.execution_mode,
            "mutation_enabled": self.mutation_enabled,
            "fixture_markers": list(self.fixture_markers),
            "is_fixture": self.is_fixture,
        }

    # -- fixtures ----------------------------------------------------------- #
    @classmethod
    def fixture(cls, **over) -> "ShadowValidationConfig":
        """A clearly-labelled FAKE_LOCAL_FIXTURE config for local harness runs."""
        d = dict(
            environment_classification="disposable_test_fixture",
            cluster_identifier="fake-cluster",
            context_name="fake-read-only-context",
            namespace_allowlist=("shadow-test",),
            resource_kind_allowlist=("Deployment", "StatefulSet",
                                     "HorizontalPodAutoscaler"),
            resource_name_allowlist=("frontend", "worker", "api"),
            maximum_target_count=20,
            request_timeout_seconds=10.0,
            maximum_observation_age_seconds=120.0,
            tls_verify=True,
            metrics_enabled=True,
            watch_enabled=True,
            audit_output_path="artifacts/shadow_harness_fixture/audit.jsonl",
            evidence_output_path="artifacts/shadow_harness_fixture",
            fixture_markers=(EVIDENCE_CLASS_FIXTURE, NOT_REAL_ENVIRONMENT_EVIDENCE),
        )
        d.update(over)
        return cls(**d)


__all__ = [
    "ShadowValidationConfig",
    "ShadowConfigError",
    "NON_PRODUCTION_CLASSIFICATIONS",
]
