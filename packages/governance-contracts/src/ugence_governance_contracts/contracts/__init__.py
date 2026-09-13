"""Provider contracts — three distinct, non-interchangeable governance families."""
from __future__ import annotations

from .base import BaseProvider, Provider
from .governed_read import (
    GovernedReadPort,
    GovernedReadRequest,
    ReadEligibility,
    ReadEligibilityStatus,
    ReadIneligibilityReason,
    ReadPurpose,
)
from .assertion import (
    AssertionCoverage,
    AssertionGovernanceProvider,
    AssertionGovernanceRequest,
    AssertionGovernanceResult,
)
from .action import (
    ActionGovernanceOutcome,
    ActionGovernanceProvider,
    ActionGovernanceRequest,
    ActionGovernanceResult,
)
from .execution import (
    ExecutionBusinessOutcome,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionObservation,
    ExternalExecutionProvider,
)
from .system_identity import (
    AssessedSystemBinding,
    ComponentBinding,
    SYSTEM_MANIFEST_COMPONENT_FAMILIES,
    SystemBindingAuthenticityStatus,
    SystemIdentityContractError,
    SystemManifest,
)
from .idempotency import (
    IdempotencyContractError,
    IdempotencyDisposition,
    IdempotencyKey,
    IdempotencyResolution,
    IdempotencyScope,
)
from .validity import (
    Validity,
    ValidityContractError,
    ValidityStatus,
)
from .audit import (
    AuditContractError,
    AuditReference,
)
from .data_classification import (
    DataClassificationContractError,
    DataClassificationLabel,
)
from .vendor_risk import (
    VendorRiskContractError,
    VendorRiskLabel,
)
from .assurance_finding import (
    AssuranceFindingContractError,
    AssuranceFindingLabel,
)
from .evidence import (
    AssessmentWindow,
    AttestationStatus,
    AttributionStatus,
    BenchmarkReference,
    ConfidenceBasis,
    EvidenceContractError,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceUsageScope,
    ForecastHorizon,
    MetricClaim,
    MetricObservation,
    PopulationSlice,
    SourceBasis,
    TransformationMethod,
    VerificationStatus,
)

__all__ = [
    # the governed-read port: declared here, implemented nowhere
    "GovernedReadPort", "GovernedReadRequest", "ReadEligibility",
    "ReadEligibilityStatus", "ReadIneligibilityReason", "ReadPurpose",
    "Provider", "BaseProvider",
    "AssertionGovernanceProvider", "AssertionGovernanceRequest",
    "AssertionGovernanceResult", "AssertionCoverage",
    "ActionGovernanceProvider", "ActionGovernanceRequest",
    "ActionGovernanceResult", "ActionGovernanceOutcome",
    "ExternalExecutionProvider", "ExecutionDispatchRequest",
    "ExecutionDispatchResult", "ExecutionObservation", "ExecutionBusinessOutcome",
    # GV-2E-a neutral evidence contracts (additive)
    "SourceBasis", "TransformationMethod", "AttestationStatus",
    "AttributionStatus", "VerificationStatus", "EvidenceUsageScope",
    "EvidenceContractError",
    "EvidenceReference", "EvidenceProvenance", "BenchmarkReference",
    "AssessmentWindow", "ForecastHorizon", "PopulationSlice", "ConfidenceBasis",
    "MetricClaim", "MetricObservation",
    # M-3R.3 neutral assessed-system identity (additive)
    "AssessedSystemBinding",
    "SystemBindingAuthenticityStatus",
    "SystemIdentityContractError",
    # G7 neutral idempotency contract (additive)
    "IdempotencyScope", "IdempotencyKey", "IdempotencyDisposition",
    "IdempotencyResolution", "IdempotencyContractError",
    # G8 neutral validity contract (additive)
    "ValidityStatus", "Validity", "ValidityContractError",
    # G4 neutral audit reference (additive)
    "AuditReference", "AuditContractError",
    # DE-5 neutral data-classification label (additive)
    "DataClassificationLabel", "DataClassificationContractError",
    # VR-5 neutral vendor-risk label (additive)
    "VendorRiskLabel", "VendorRiskContractError",
    # AE-5 neutral assurance-finding label (additive)
    "AssuranceFindingLabel", "AssuranceFindingContractError",
]
