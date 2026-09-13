"""Ugence Change Effect Records — the contracts-only record shapes of the GERL chain.

    THIS PACKAGE HOLDS THE SHAPES A CLASSIFICATION CHAIN IS WRITTEN IN.
    IT NEVER CLASSIFIES, MEASURES, REPLAYS, PROJECTS, ROUTES, RESOLVES POLICY,
    ADMITS, SAMPLES, READS OR WRITES GOVERNED MEMORY, OR REGISTERS ANYTHING.

Stage 1 substrate under ``docs/architecture/ADR_UGENCE_CHANGE_EFFECT_CLASSIFIER_SCOPING.md``
and ``docs/architecture/STAGE1_CHANGE_EFFECT_CLASSIFIER_CONTRACTS_SCOPING.md`` (item 3.3,
with the admission succession data of item 3.6), scoped against GERL target classification
version 4.2.10 and its recorded erratum, which an outside-family reviewer ruled RATIFIED
WITH ONE CONFORMANCE CORRECTION. Ratifying a design authorizes no operation: no component
this package describes exists, and none is reachable from any runtime path here.

**Contracts only.** Thirteen frozen, digest-bound record types; the canonical-bytes
profile of rule section 6a; the chain and obligation identifier derivations; closed
vocabularies; the admission succession and control-register transition tables as data;
and the refusal-code register. **No classifier, no replay harness, no projection, no
routing, no policy resolver, no sampler, no admission boundary, no store, no clock, no
network** — so the lines the rulings draw are held structurally rather than by discipline.

What the types do **not** do is the point of them:

* They compute nothing across records. Every digest is supplied by a caller; no type
  resolves, dereferences or verifies another record.
* They recompute no projection and re-apply no routing rule. A FinalResolutionRecord
  carries the assertion that the effective obligation set is empty; the Stage 3 verifier
  recomputes it rather than believing it, and nothing here recomputes anything.
* They derive no closure bundle. The evaluator signs a raw evaluation result and the
  policy-governance-owned mapping produces the bundle; this package holds it.
* They drive no state machine. The succession and transition tables are data, and the
  guarantee behind them is the audit root's conditional append, which is not here.

A record is a shape, not a finding, and not a permission.
"""

from __future__ import annotations

from ._canon import (
    INT64_MAX,
    INT64_MIN,
    canonical_json,
    domain_digest,
    iso,
    normalize_tenant,
    normalize_text,
    profile,
    require_digest,
    require_nonempty,
    require_ordinal,
    require_tzaware,
)
from .admission import (
    COMMITTING_CLAIM,
    CONTROL_REGISTER_TRANSITIONS,
    DOCUMENTARY_CLAIM,
    LEGAL_SUCCESSIONS,
    RECOVERY_OUTCOMES,
    RESERVATION_REFUSAL_BY_STATE,
    TERMINAL_CONTROL_STATES,
)
from .errors import CanonicalFormRefused, ChangeEffectRecordsError, ContractViolation
from .identifiers import IntroducingRole, assign_ordinals, chain_id, obligation_id
from .records import (
    RECORD_TYPES,
    AdmissionClaimRecord,
    AdmissionCompletionRecord,
    AdmissionReservationRecord,
    AdmissionResolutionRecord,
    AuthorizationBinding,
    BlockingObligation,
    ClassificationRecord,
    ClosureEffectBundle,
    ConfirmationAmendment,
    FinalResolutionRecord,
    InvestigationClosureRecord,
    InvestigationExtensionRecord,
    InvestigationRecord,
    PrimitiveEffect,
    RegistryEffectResult,
    ResolutionRevocationRecord,
    RevocationImpactRecord,
    SampleBinding,
)
from .refusals import CODES_RAISED_HERE, REFUSAL_CODES
from .version import (
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    MATURITY,
    RULE_VERSION,
    __version__,
)
from .vocabulary import (
    AdmissionState,
    ClaimKind,
    ClosureOutcome,
    CompletionAbsence,
    ControlRegisterState,
    EffectClass,
    EvaluationStatus,
    JurisdictionalRoute,
    ObligationKind,
    PrimitiveEffectKind,
    RemediationRequirement,
    RevocationOrdering,
    ReviewOutcome,
)

__all__ = [
    # version and posture
    "__version__", "CONTRACT_VERSION", "RULE_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    # errors
    "ChangeEffectRecordsError", "ContractViolation", "CanonicalFormRefused",
    # canonical bytes, the section 6a profile
    "profile", "canonical_json", "domain_digest", "normalize_text", "normalize_tenant",
    "require_nonempty", "require_digest", "require_ordinal", "require_tzaware", "iso",
    "INT64_MIN", "INT64_MAX",
    # identifiers
    "chain_id", "obligation_id", "assign_ordinals", "IntroducingRole",
    # vocabularies
    "EvaluationStatus", "EffectClass", "JurisdictionalRoute", "ObligationKind",
    "ClosureOutcome", "PrimitiveEffectKind", "AdmissionState", "ClaimKind",
    "ControlRegisterState", "RevocationOrdering", "CompletionAbsence",
    "RemediationRequirement", "ReviewOutcome",
    # record parts
    "RegistryEffectResult", "BlockingObligation", "PrimitiveEffect", "ClosureEffectBundle",
    "SampleBinding",
    # the thirteen records
    "ClassificationRecord", "ConfirmationAmendment", "InvestigationRecord",
    "InvestigationExtensionRecord", "InvestigationClosureRecord", "FinalResolutionRecord",
    "AuthorizationBinding", "ResolutionRevocationRecord", "RevocationImpactRecord",
    "AdmissionReservationRecord", "AdmissionClaimRecord", "AdmissionCompletionRecord",
    "AdmissionResolutionRecord", "RECORD_TYPES",
    # admission succession and the control register, as data
    "LEGAL_SUCCESSIONS", "CONTROL_REGISTER_TRANSITIONS", "TERMINAL_CONTROL_STATES",
    "RESERVATION_REFUSAL_BY_STATE", "RECOVERY_OUTCOMES", "COMMITTING_CLAIM",
    "DOCUMENTARY_CLAIM",
    # refusal register
    "REFUSAL_CODES", "CODES_RAISED_HERE",
]
