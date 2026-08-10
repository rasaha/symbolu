"""Shared scenario helpers for the RA-5 trusted-evidence-runtime suite.

Builds the finance refund-review vertical slice (mirroring the RA reference
scenario) but driven through the PRODUCTION path: a TAP-backed Control-Assurance
evaluator and the production evidence admitter, composed by
``RiskAuthorityEvidenceRuntime``. Evidence is stamped with a correct integrity
digest bound to the case's tenant/workflow/policy context so admission accepts it;
adversarial tests deliberately break one binding at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional

from ugence_tap_provider.api import TapEngine, TapOutcome, TapRule, build_tap_provider

from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain import (
    AuthorityGrant,
    AuthorityType,
    Predicate,
    PredicateOp,
    RiskClass,
    RuleEffect,
    Scope,
    WorkflowIR,
    WorkflowRule,
    WorkflowStatus,
)
from risk_authority.integrations import InMemoryWorkflowIRSource

import dataclasses

from ugence_risk_authority_evidence_runtime import (
    ProductionEvidenceAdmission,
    RiskAuthorityEvidenceRuntime,
    StaticTrustedIngress,
    TapControlAssurance,
    stamp_admitted_evidence,
)
from risk_authority.domain.evidence import ControlEvidenceRecord

FIXED_NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant_123"
OTHER_TENANT = "tenant_999"
ACTOR = "agent_finance_07"
MODEL = "model_xyz"
PRINCIPAL = "risk-office-prod"
KEY_ID = "risk-key-2026-08"
MAX_REFUND_MINOR = 500000

REQUIRED_CONTROLS = (
    "MODEL_PROVENANCE_VALID",
    "HUMAN_OVERSIGHT_VALID",
    "BIAS_EVALUATION_CURRENT",
)

FINANCE_SCOPE = Scope(
    purposes=("CUSTOMER_REFUND_REVIEW",),
    tools_allow=("crm.read", "refund.prepare"),
    tools_deny=("refund.execute", "email.external"),
    data_allow=("CUSTOMER_PII", "TRANSACTION_DATA"),
    data_deny=("HEALTH_DATA", "EMPLOYEE_HR"),
    destinations=("internal://finance",),
    models=(MODEL,),
    actors=(ACTOR,),
    max_autonomy_level=2,
    max_transaction_minor_units=MAX_REFUND_MINOR,
)


def build_workflow() -> WorkflowIR:
    return WorkflowIR(
        workflow_ir_id="finance-ai-risk",
        version="4.1.0",
        status=WorkflowStatus.ACTIVE,
        rules=(
            WorkflowRule(
                rule_id="FIN-12",
                conditions=(
                    Predicate("risk_class", PredicateOp.IN, ["HIGH", "CRITICAL"]),
                    Predicate("domain", PredicateOp.EQ, "FINANCE"),
                ),
                required_controls=REQUIRED_CONTROLS,
                effect=RuleEffect.DENY_UNLESS_ALL,
            ),
        ),
        source_refs=("CORP-AI-04",),
        effective_at=FIXED_NOW,
    ).with_digest()


WORKFLOW = build_workflow()
WORKFLOW_DIGEST = WORKFLOW.digest
POLICY_DIGEST = WORKFLOW_DIGEST  # policy_digest == WorkflowIR digest today (§6)


def build_grant() -> AuthorityGrant:
    return AuthorityGrant(
        principal_id=PRINCIPAL,
        tenant_id=TENANT,
        authority_type=AuthorityType.RISK_APPROVAL,
        domains=("FINANCE",),
        allowed_risk_classes=(RiskClass.LOW, RiskClass.MEDIUM, RiskClass.HIGH),
        max_autonomy=2,
        delegated_by="enterprise-risk-office",
        grantable_scope=FINANCE_SCOPE,
    )


def make_tap_provider(
    outcomes: Optional[Mapping[str, TapRule]] = None,
    *,
    explicit_support: bool = True,
):
    """A real in-process TAP provider. ``outcomes`` maps control_id → TapRule.

    Production GRANT requires an EXPLICIT affirmative determination (RA-5 audit
    H-1), never support presumed from mere evidence presence. So by default this
    installs an explicit ``SUPPORTED @ coverage 1.0`` rule for every required
    control, and overlays any ``outcomes`` on top. Pass ``explicit_support=False``
    to build a rule-less engine whose evidence-derived SUPPORTED is *presumptive*
    (used by the adversarial no-determination test).
    """

    rules: dict[str, TapRule] = {}
    if explicit_support:
        rules = {
            c: TapRule(outcome=TapOutcome.SUPPORTED, evidence_coverage=1.0)
            for c in REQUIRED_CONTROLS
        }
    if outcomes:
        rules.update(dict(outcomes))
    engine = TapEngine(rules=rules)
    return build_tap_provider(engine)


def make_failing_provider(fail: str):
    """A TAP provider whose engine raises a native failure (unavailable/timeout)."""

    engine = TapEngine(fail=fail)
    return build_tap_provider(engine)


class DeploymentChannelIngress:
    """Test stand-in for a deployment's REAL authenticated-channel verifier.

    Unlike the shipped conformance ``StaticTrustedIngress`` — which production mode
    now rejects (RA-5 audit F-1) because it is only a fixed-posture stand-in — this
    carries **no** ``is_reference_ingress`` marker: it models the mTLS /
    workload-identity / signed-token verifier a deployment injects. It lives in
    test code on purpose; the production package must not ship a permissive
    always-trusting ingress, or F-1's guardrail would just be re-openable under a
    new name. ``trusted=False`` models an unauthenticated caller channel.
    """

    def __init__(self, *, trusted: bool) -> None:
        self._trusted = bool(trusted)

    def is_trusted(self, evidence, *, now):
        return self._trusted


def build_runtime(
    *,
    tap_provider=None,
    control_assurance=None,
    evidence_admission=None,
    evidence_ingress=None,
    clock=lambda: FIXED_NOW,
) -> RiskAuthorityEvidenceRuntime:
    source = InMemoryWorkflowIRSource()
    source.register(build_workflow())
    key = SigningKeyRecord(KEY_ID, SigningKey.from_seed(bytes(range(32))))
    if control_assurance is None:
        provider = tap_provider if tap_provider is not None else make_tap_provider()
        control_assurance = TapControlAssurance(provider)
    runtime = RiskAuthorityEvidenceRuntime(
        workflow_source=source,
        key_record=key,
        clock=clock,
        evidence_admission=evidence_admission or ProductionEvidenceAdmission(),
        control_assurance=control_assurance,
        # The finance scenario's evidence arrives over a deployment's real
        # authenticated producer channel (RA-5 §13; audit H-2, F-1) — NOT the
        # conformance stand-in, which production now refuses. Adversarial tests
        # override this with an untrusted-channel verifier to prove fabricated
        # caller evidence is dropped.
        evidence_ingress=evidence_ingress or DeploymentChannelIngress(trusted=True),
    )
    runtime.application.authority.add_grant(build_grant())
    return runtime


def tamper(record: ControlEvidenceRecord, **changes: object) -> ControlEvidenceRecord:
    """Return a copy of ``record`` with fields changed but digests left intact.

    Adversarial-test helper (moved out of the production ``admission`` module,
    RA-5 audit INFO-2): the returned record's content no longer matches its
    ``digest``/``admission_digest``, so the production admitter rejects it.
    """

    return dataclasses.replace(record, **changes)  # type: ignore[arg-type]


def make_evidence(
    evidence_id: str,
    *,
    tenant_id: str = TENANT,
    subject: str = ACTOR,
    workflow_ir_digest: str = WORKFLOW_DIGEST,
    policy_digest: str = POLICY_DIGEST,
    valid_until: Optional[datetime] = None,
    observed_at: datetime = FIXED_NOW,
    source_type: str = "attestation",
    source_identity: str = "provenance-service",
    producer: str = "ra5-production-admission",
    producer_version: str = "1",
):
    """A well-formed AdmittedEvidence bound to the finance case context."""

    if valid_until is None:
        valid_until = FIXED_NOW + timedelta(hours=24)
    return stamp_admitted_evidence(
        evidence_id=evidence_id,
        tenant_id=tenant_id,
        source_type=source_type,
        source_identity=source_identity,
        subject=subject,
        workflow_ir_digest=workflow_ir_digest,
        policy_digest=policy_digest,
        observed_at=observed_at,
        valid_until=valid_until,
        admitted_at=FIXED_NOW,
        producer=producer,
        producer_version=producer_version,
        provenance={"channel": "trusted"},
    )


def full_evidence_and_map():
    """One admitted evidence record per required control + the control→evidence map."""

    records = tuple(
        make_evidence(f"ev_{ctrl.lower()}") for ctrl in REQUIRED_CONTROLS
    )
    mapping = {
        ctrl: (f"ev_{ctrl.lower()}",) for ctrl in REQUIRED_CONTROLS
    }
    return records, mapping


@dataclass(frozen=True)
class CaseParams:
    case_id: str = "rdc_prod_1"
    tenant_id: str = TENANT


def create_case(runtime: RiskAuthorityEvidenceRuntime, params: CaseParams = CaseParams()):
    from risk_authority.api.schemas import CreateCaseRequest

    return runtime.create_case(
        CreateCaseRequest(
            tenant_id=params.tenant_id,
            case_id=params.case_id,
            subject_id=ACTOR,
            model_id=MODEL,
            purpose="CUSTOMER_REFUND_REVIEW",
            domain="FINANCE",
            jurisdictions=("US",),
            tools=("crm.read", "refund.prepare"),
            autonomy_level=2,
            data_classes=("CUSTOMER_PII", "TRANSACTION_DATA"),
            workflow_ir_id="finance-ai-risk",
            inherent_risk=RiskClass.HIGH,
            residual_risk=RiskClass.MEDIUM,
        )
    )


