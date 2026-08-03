"""The governed-workflow compiler orchestrator.

Composes the deterministic stages: validate -> (approval gate) -> synthesize IR ->
authority-boundary check -> generate assurance -> coverage check -> generate audit
schema -> build capability manifest -> content-address -> assemble compiled package.

``compile`` runs the whole pipeline and returns a :class:`CompilationResult`. It
never approves a pack and never mutates a capability's behavior; it only emits
artifacts derived from the approved objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..approval.records import compute_pack_digest
from ..approval.service import ApprovalService
from ..models.approvals import HumanApprovalRecord
from ..models.assurance import AssuranceManifest
from ..models.audit import AuditSchema
from ..models.common import PolicyPackStatus
from ..models.policy_pack import PolicyPack
from ..validation import authority_boundaries as _boundaries
from ..validation.coverage import check_coverage
from ..validation.errors import Severity, ValidationDiagnostic, ValidationReport
from ..validation.validator import PolicyPackValidator
from .assurance_generation import AssuranceGenerator
from .audit_schema import AuditSchemaGenerator
from .capability_registry import CapabilityRegistry, DEFAULT_REGISTRY
from .release import (
    CompiledReleasePackage,
    ReleaseManifest,
    build_capability_manifest,
    compute_logical_digest,
)
from .synthesis import WorkflowSynthesizer
from .workflow_ir import WorkflowIR


class CompilationError(RuntimeError):
    """Raised when compilation cannot proceed (invalid or unapproved pack)."""

    def __init__(self, message: str, report: ValidationReport) -> None:
        super().__init__(message)
        self.report = report


@dataclass(frozen=True)
class CompilationResult:
    """Everything a compile run produces."""

    success: bool
    validation_report: ValidationReport
    workflow_ir: Optional[WorkflowIR] = None
    assurance_manifest: Optional[AssuranceManifest] = None
    audit_schema: Optional[AuditSchema] = None
    compiled_package: Optional[CompiledReleasePackage] = None
    logical_digest: str = ""

    @property
    def diagnostics(self):
        return self.validation_report.diagnostics


class GovernedWorkflowCompiler:
    """Deterministic Policy-Pack -> Governed-Workflow compiler."""

    def __init__(self, registry: CapabilityRegistry = DEFAULT_REGISTRY) -> None:
        self._registry = registry
        self._validator = PolicyPackValidator(registry)
        self._synth = WorkflowSynthesizer(registry)
        self._assurance = AssuranceGenerator()
        self._audit = AuditSchemaGenerator()
        self._approval = ApprovalService()

    # -- validate-only -------------------------------------------------------

    def validate(self, pack: PolicyPack) -> ValidationReport:
        return self._validator.validate(pack)

    # -- synthesis-only (no approval required; used for preview/equivalence) --

    def synthesize(self, pack: PolicyPack) -> WorkflowIR:
        ir = self._synth.synthesize(pack)
        violations = _boundaries.check_ir(ir)
        if violations:
            raise CompilationError(
                "authority-boundary violation in synthesized IR",
                _boundary_report(pack.pack_id, violations),
            )
        return ir

    def generate_assurance(self, pack: PolicyPack) -> AssuranceManifest:
        return self._assurance.generate(pack)

    # -- full compile --------------------------------------------------------

    def compile(
        self,
        pack: PolicyPack,
        approval: Optional[HumanApprovalRecord] = None,
        *,
        require_approval: bool = True,
    ) -> CompilationResult:
        report = self._validator.validate(pack)
        if not report.ok:
            return CompilationResult(success=False, validation_report=report)

        # Approval gate. Only an APPROVED pack with a valid, non-self approval may
        # compile into a release artifact.
        if require_approval:
            check = self._approval.check(pack, approval)
            if check.rejected:
                diagnostics = list(report.diagnostics) + [
                    ValidationDiagnostic(
                        code="APPROVAL_REQUIRED",
                        severity=Severity.ERROR,
                        object_id=pack.pack_id,
                        message=reason,
                        suggested_remediation="supply a valid human approval for this pack digest",
                    )
                    for reason in check.reasons
                ]
                return CompilationResult(
                    success=False,
                    validation_report=report.model_copy(
                        update={"diagnostics": tuple(diagnostics)}
                    ),
                )

        # Stage 3 — synthesis + authority-boundary enforcement.
        ir = self._synth.synthesize(pack)
        violations = _boundaries.check_ir(ir)
        if violations:
            return CompilationResult(
                success=False,
                validation_report=_merge(report, _boundary_report(pack.pack_id, violations)),
            )

        # Stage 4 — assurance + coverage + audit schema.
        assurance = self._assurance.generate(pack)
        coverage_diags = check_coverage(pack, assurance)
        if coverage_diags:
            return CompilationResult(
                success=False,
                validation_report=_merge(
                    report,
                    ValidationReport(
                        policy_pack_id=pack.pack_id, diagnostics=tuple(coverage_diags)
                    ),
                ),
                workflow_ir=ir,
                assurance_manifest=assurance,
            )
        audit_schema = self._audit.generate(pack)

        # Stage 5 subset — capability manifest, content addressing, package.
        capability_manifest = build_capability_manifest(ir, self._registry)
        logical_digest = compute_logical_digest(
            pack, ir, capability_manifest, assurance, assurance.coverage_matrix, audit_schema
        )
        compiled_pack = pack.with_status(PolicyPackStatus.COMPILED)
        manifest = ReleaseManifest(
            policy_pack_id=pack.pack_id,
            policy_pack_version=pack.version,
            schema_version=pack.schema_version,
            compiler_distribution_version=_dist_version(),
            structural_digest=logical_digest,
        )
        package = CompiledReleasePackage(
            manifest=manifest,
            policy_pack=compiled_pack,
            workflow_ir=ir,
            capability_manifest=capability_manifest,
            assurance_manifest=assurance,
            coverage_matrix=assurance.coverage_matrix,
            audit_schema=audit_schema,
            approval_record=approval,
            validation_report=report,
            structural_digest=logical_digest,
            release_metadata={"pack_structural_digest": compute_pack_digest(pack)},
        )
        return CompilationResult(
            success=True,
            validation_report=report,
            workflow_ir=ir,
            assurance_manifest=assurance,
            audit_schema=audit_schema,
            compiled_package=package,
            logical_digest=logical_digest,
        )


def _dist_version() -> str:
    from ..version import DISTRIBUTION_VERSION

    return DISTRIBUTION_VERSION


def _boundary_report(pack_id: str, violations) -> ValidationReport:
    diagnostics = tuple(
        ValidationDiagnostic(
            code="AUTHORITY_BOUNDARY_VIOLATION",
            severity=Severity.FATAL,
            object_id=v.node_id,
            message=v.message,
            suggested_remediation="assign the node's function to the capability that owns that authority",
        )
        for v in violations
    )
    return ValidationReport(policy_pack_id=pack_id, diagnostics=diagnostics)


def _merge(a: ValidationReport, b: ValidationReport) -> ValidationReport:
    return ValidationReport(
        policy_pack_id=a.policy_pack_id,
        diagnostics=tuple(a.diagnostics) + tuple(b.diagnostics),
    )


def compile_policy_pack(
    pack: PolicyPack,
    approval: Optional[HumanApprovalRecord] = None,
    *,
    registry: Optional[CapabilityRegistry] = None,
    require_approval: bool = True,
) -> CompilationResult:
    """Convenience wrapper around :meth:`GovernedWorkflowCompiler.compile`."""
    return GovernedWorkflowCompiler(registry or DEFAULT_REGISTRY).compile(
        pack, approval, require_approval=require_approval
    )
