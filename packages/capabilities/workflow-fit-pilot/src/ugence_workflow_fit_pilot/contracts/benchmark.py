"""§3.2 Benchmark manifest: the exact ordered case-digest set, bound to its head."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

from ugence_governance_contracts.api import BenchmarkReference
from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode

from .._canon import digest_of, require_digest, require_nonblank, require_tzaware, settle_digest
from ..errors import PilotError, PilotErrorCode

BENCHMARK_MANIFEST_SCHEMA_VERSION = "workflow_fit_pilot.benchmark_manifest.v1"


def case_list_digest(case_digests: Tuple[str, ...]) -> str:
    """The benchmark head's content_digest: the JCS digest of the ordered case-digest list."""
    return digest_of(list(case_digests))


def require_count(value: object, name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or (positive and value == 0):
        raise PilotError(PilotErrorCode.COUNT_INVALID, f"{name} must be a {'positive' if positive else 'non-negative'} integer")
    return value


@dataclass(frozen=True)
class BenchmarkManifest:
    schema_version: str
    benchmark: BenchmarkReference
    case_digests: Tuple[str, ...]
    case_count: int
    issuer_identity: str
    issued_at: datetime
    benchmark_manifest_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BENCHMARK_MANIFEST_SCHEMA_VERSION:
            raise PilotError(PilotErrorCode.SCHEMA_VERSION_UNSUPPORTED, f"BenchmarkManifest.schema_version must be {BENCHMARK_MANIFEST_SCHEMA_VERSION}")
        if not isinstance(self.benchmark, BenchmarkReference):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "BenchmarkManifest.benchmark must be a BenchmarkReference")
        if not isinstance(self.case_digests, tuple) or not self.case_digests:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "BenchmarkManifest.case_digests must be a non-empty tuple")
        for d in self.case_digests:
            require_digest(d, "BenchmarkManifest.case_digests item")
        if list(self.case_digests) != sorted(self.case_digests) or len(set(self.case_digests)) != len(self.case_digests):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "BenchmarkManifest.case_digests must be ascending and unique")
        require_count(self.case_count, "BenchmarkManifest.case_count", positive=True)
        if self.case_count != len(self.case_digests):
            raise PilotError(PilotErrorCode.COUNT_INVALID, "BenchmarkManifest.case_count must equal len(case_digests)")
        if self.benchmark.content_digest != case_list_digest(self.case_digests):
            raise PilotError(PilotErrorCode.BENCHMARK_HEAD_MISMATCH, "benchmark.content_digest is not the digest of the ordered case list")
        require_nonblank(self.issuer_identity, "BenchmarkManifest.issuer_identity")
        require_tzaware(self.issued_at, "BenchmarkManifest.issued_at")
        settle_digest(self, "benchmark_manifest_digest", digest_of(self, exclude=("benchmark_manifest_digest",)))


__all__ = ["BENCHMARK_MANIFEST_SCHEMA_VERSION", "BenchmarkManifest", "case_list_digest", "require_count"]
