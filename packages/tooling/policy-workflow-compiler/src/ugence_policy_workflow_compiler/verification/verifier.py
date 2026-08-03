"""Compiled-package verification.

Re-checks a compiled package for internal consistency: the recomputed logical
digest matches the recorded one, the IR passes authority boundaries, coverage is
complete, the capability manifest matches the IR's referenced capabilities, and
the audit schema carries the baseline fields. Verification is deterministic and
offline — it recomputes, it never trusts.
"""

from __future__ import annotations

from typing import List

from ..compiler.release import CompiledReleasePackage
from ..models.audit import BASELINE_AUDIT_FIELDS
from ..validation import authority_boundaries as _boundaries
from .reports import VerificationCheck, VerificationReport


class CompiledPackageVerifier:
    """Deterministically verifies a :class:`CompiledReleasePackage`."""

    def verify(self, package: CompiledReleasePackage) -> VerificationReport:
        checks: List[VerificationCheck] = []

        recomputed = package.recompute_digest()
        checks.append(
            VerificationCheck(
                name="logical_digest_reproducible",
                passed=recomputed == package.structural_digest,
                detail=f"recorded={package.structural_digest} recomputed={recomputed}",
            )
        )
        checks.append(
            VerificationCheck(
                name="manifest_digest_matches",
                passed=package.manifest.structural_digest == package.structural_digest,
                detail=package.manifest.structural_digest,
            )
        )

        violations = _boundaries.check_ir(package.workflow_ir)
        checks.append(
            VerificationCheck(
                name="authority_boundaries",
                passed=not violations,
                detail=(
                    "no violations"
                    if not violations
                    else "; ".join(v.message for v in violations)
                ),
            )
        )

        coverage = package.coverage_matrix
        checks.append(
            VerificationCheck(
                name="coverage_complete",
                passed=coverage.complete,
                detail=(
                    "complete"
                    if coverage.complete
                    else f"uncovered={list(coverage.uncovered_object_ids)}"
                ),
            )
        )

        ir_caps = set(package.workflow_ir.referenced_capabilities)
        manifest_caps = set(package.capability_manifest.referenced_capabilities)
        checks.append(
            VerificationCheck(
                name="capability_manifest_matches_ir",
                passed=ir_caps == manifest_caps,
                detail=f"ir={sorted(ir_caps)} manifest={sorted(manifest_caps)}",
            )
        )

        schema_fields = {f.name for f in package.audit_schema.fields}
        missing = [f for f in BASELINE_AUDIT_FIELDS if f not in schema_fields]
        checks.append(
            VerificationCheck(
                name="audit_schema_baseline_present",
                passed=not missing,
                detail="present" if not missing else f"missing={missing}",
            )
        )

        return VerificationReport(
            policy_pack_id=package.policy_pack.pack_id,
            structural_digest=package.structural_digest,
            checks=tuple(checks),
        )


def verify_compiled_package(package: CompiledReleasePackage) -> VerificationReport:
    """Convenience wrapper around :meth:`CompiledPackageVerifier.verify`."""
    return CompiledPackageVerifier().verify(package)
