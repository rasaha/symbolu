"""Specification §2 — catalog, catalog ref, method ref, entry, implementation evidence.

``ImplementationStatus`` is DERIVED from evidence and never declared; an entry
constructed with an ``implementation_status`` keyword is refused. Entry types
may not carry scalar resource labels (advisor note §5 prohibitions).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import ClassVar, FrozenSet, Tuple

from ..errors import ContractError, ContractErrorCode
from ._util import (
    digest_of,
    guard_kwargs,
    require_digest,
    require_member,
    require_nonblank,
    require_str_tuple,
    require_tzaware,
    settle_digest,
)

CATALOG_SCHEMA_VERSION = "reasoning_method.catalog.v1"

# Mirror of agentic.agentic_framework.adaptive_prompts.ComplexitySignal values,
# pinned by tests/packaging/test_vocabulary_pins.py under a test-only file load.
# The runtime module is never imported here (boundary test).
COMPLEXITY_SIGNAL_TOKENS: FrozenSet[str] = frozenset(
    {
        "multi_part_question",
        "causal_reasoning",
        "comparison_request",
        "abstract_concept",
        "conditional_logic",
        "temporal_reasoning",
        "creative_synthesis",
        "domain_expertise",
        "ambiguity_detected",
        "meta_reasoning",
    }
)

# Field names an entry type may never declare: a scalar resource label is an
# unratified ordering (advisor note §5). Checked at class definition.
SCALAR_LABEL_FIELD_NAMES: FrozenSet[str] = frozenset(
    {
        "cost",
        "cost_class",
        "cost_label",
        "latency",
        "latency_class",
        "latency_label",
        "resource_level",
        "resource_label",
        "resource_class",
        "expense",
        "price",
    }
)


class ImplementationEvidenceKind(str, Enum):
    CONCRETE_CLASS_REGISTERED = "CONCRETE_CLASS_REGISTERED"
    STUB_EXECUTION_COMPLETED = "STUB_EXECUTION_COMPLETED"
    UNIT_TESTS_PRESENT = "UNIT_TESTS_PRESENT"
    EXECUTION_RECORD_EMITTED = "EXECUTION_RECORD_EMITTED"


class ImplementationStatus(str, Enum):
    EXECUTABLE_TESTED = "EXECUTABLE_TESTED"
    EXECUTABLE_UNTESTED = "EXECUTABLE_UNTESTED"
    REGISTERED_NOT_EXECUTED = "REGISTERED_NOT_EXECUTED"
    NO_IMPLEMENTATION_EVIDENCE = "NO_IMPLEMENTATION_EVIDENCE"


def derive_implementation_status(kinds: FrozenSet[ImplementationEvidenceKind]) -> ImplementationStatus:
    registered = ImplementationEvidenceKind.CONCRETE_CLASS_REGISTERED in kinds
    executed = ImplementationEvidenceKind.STUB_EXECUTION_COMPLETED in kinds
    tested = ImplementationEvidenceKind.UNIT_TESTS_PRESENT in kinds
    if registered and executed and tested:
        return ImplementationStatus.EXECUTABLE_TESTED
    if registered and executed:
        return ImplementationStatus.EXECUTABLE_UNTESTED
    if registered:
        return ImplementationStatus.REGISTERED_NOT_EXECUTED
    return ImplementationStatus.NO_IMPLEMENTATION_EVIDENCE


@dataclass(frozen=True)
class ImplementationEvidence:
    kind: ImplementationEvidenceKind
    ref: str
    observed_at: datetime

    def __post_init__(self) -> None:
        require_member(self.kind, ImplementationEvidenceKind, "ImplementationEvidence.kind", ContractErrorCode.REF_BLANK_FIELD)
        require_nonblank(self.ref, "ImplementationEvidence.ref")
        require_tzaware(self.observed_at, "ImplementationEvidence.observed_at")


@dataclass(frozen=True)
class ReasoningMethodCatalogRef:
    catalog_id: str
    catalog_version: str
    catalog_digest: str

    def __post_init__(self) -> None:
        require_nonblank(self.catalog_id, "ReasoningMethodCatalogRef.catalog_id")
        require_nonblank(self.catalog_version, "ReasoningMethodCatalogRef.catalog_version")
        require_digest(self.catalog_digest, "ReasoningMethodCatalogRef.catalog_digest")


@dataclass(frozen=True)
class ReasoningMethodRef:
    catalog: ReasoningMethodCatalogRef
    method_id: str
    method_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, ReasoningMethodCatalogRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReasoningMethodRef.catalog must be a ReasoningMethodCatalogRef")
        require_nonblank(self.method_id, "ReasoningMethodRef.method_id")
        require_nonblank(self.method_version, "ReasoningMethodRef.method_version")

    @property
    def sort_key(self) -> Tuple[str, str]:
        return (self.method_id, self.method_version)


@dataclass(frozen=True)
class ReasoningMethodEntry:
    method_id: str
    method_version: str
    display_name: str
    implementation_evidence: Tuple[ImplementationEvidence, ...]
    declared_signals: Tuple[str, ...]
    requirement_refs: Tuple[str, ...]
    runtime_binding_ref: str = ""
    policy_refs: Tuple[str, ...] = ()

    _forbidden_field_names: ClassVar[FrozenSet[str]] = SCALAR_LABEL_FIELD_NAMES

    def __init_subclass__(cls, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init_subclass__(**kwargs)
        declared = set(getattr(cls, "__annotations__", {}))
        bad = sorted(declared & SCALAR_LABEL_FIELD_NAMES)
        if bad:
            raise ContractError(
                ContractErrorCode.SCALAR_LABEL_FIELD_PRESENT,
                f"{cls.__name__} declares scalar resource label field(s) {', '.join(bad)}",
            )

    def __post_init__(self) -> None:
        require_nonblank(self.method_id, "ReasoningMethodEntry.method_id")
        require_nonblank(self.method_version, "ReasoningMethodEntry.method_version")
        require_nonblank(self.display_name, "ReasoningMethodEntry.display_name")
        if not isinstance(self.implementation_evidence, tuple) or not all(
            isinstance(e, ImplementationEvidence) for e in self.implementation_evidence
        ):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReasoningMethodEntry.implementation_evidence must be a tuple of ImplementationEvidence")
        require_str_tuple(self.declared_signals, "ReasoningMethodEntry.declared_signals")
        unknown = sorted(set(self.declared_signals) - COMPLEXITY_SIGNAL_TOKENS)
        if unknown:
            raise ContractError(ContractErrorCode.SIGNAL_TOKEN_UNKNOWN, f"unknown signal token(s): {', '.join(unknown)}")
        require_str_tuple(self.requirement_refs, "ReasoningMethodEntry.requirement_refs")
        require_str_tuple(self.policy_refs, "ReasoningMethodEntry.policy_refs")
        if not isinstance(self.runtime_binding_ref, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReasoningMethodEntry.runtime_binding_ref must be a string")

    @property
    def implementation_status(self) -> ImplementationStatus:
        return derive_implementation_status(frozenset(e.kind for e in self.implementation_evidence))

    @property
    def sort_key(self) -> Tuple[str, str]:
        return (self.method_id, self.method_version)


guard_kwargs(ReasoningMethodEntry, ("implementation_status",), ContractErrorCode.STATUS_DECLARED_NOT_DERIVED)


@dataclass(frozen=True)
class ReasoningMethodCatalog:
    schema_version: str
    catalog_id: str
    catalog_version: str
    entries: Tuple[ReasoningMethodEntry, ...]
    issuer_identity: str
    issued_at: datetime
    catalog_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReasoningMethodCatalog.schema_version")
        require_nonblank(self.catalog_id, "ReasoningMethodCatalog.catalog_id")
        require_nonblank(self.catalog_version, "ReasoningMethodCatalog.catalog_version")
        require_nonblank(self.issuer_identity, "ReasoningMethodCatalog.issuer_identity")
        require_tzaware(self.issued_at, "ReasoningMethodCatalog.issued_at")
        if not isinstance(self.entries, tuple) or not all(isinstance(e, ReasoningMethodEntry) for e in self.entries):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ReasoningMethodCatalog.entries must be a tuple of ReasoningMethodEntry")
        keys = [e.sort_key for e in self.entries]
        if len(set(keys)) != len(keys):
            raise ContractError(ContractErrorCode.CATALOG_DUPLICATE_ENTRY, "duplicate (method_id, method_version) in catalog")
        if keys != sorted(keys):
            raise ContractError(ContractErrorCode.CATALOG_UNSORTED, "catalog entries must be sorted by (method_id, method_version)")
        settle_digest(self, "catalog_digest", digest_of(self, exclude=("catalog_digest",)))

    def ref(self) -> ReasoningMethodCatalogRef:
        return ReasoningMethodCatalogRef(self.catalog_id, self.catalog_version, self.catalog_digest)

    def method_ref(self, method_id: str, method_version: str) -> ReasoningMethodRef:
        for e in self.entries:
            if e.method_id == method_id and e.method_version == method_version:
                return ReasoningMethodRef(self.ref(), method_id, method_version)
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"no catalog entry ({method_id!r}, {method_version!r})")


__all__ = [
    "CATALOG_SCHEMA_VERSION",
    "COMPLEXITY_SIGNAL_TOKENS",
    "SCALAR_LABEL_FIELD_NAMES",
    "ImplementationEvidenceKind",
    "ImplementationStatus",
    "ImplementationEvidence",
    "derive_implementation_status",
    "ReasoningMethodCatalogRef",
    "ReasoningMethodRef",
    "ReasoningMethodEntry",
    "ReasoningMethodCatalog",
]
