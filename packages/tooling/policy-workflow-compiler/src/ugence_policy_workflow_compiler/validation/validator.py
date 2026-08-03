"""The policy-pack validator orchestrator.

Runs the structural, provenance, secret, determinism, and (optionally)
authority-boundary checks over a pack and returns a single
:class:`ValidationReport`. Coverage is validated separately by the compiler once
assurance has been generated (see :mod:`.coverage`).
"""

from __future__ import annotations

from typing import List, Optional

from ..compiler.capability_registry import CapabilityRegistry, DEFAULT_REGISTRY
from ..models.policy_pack import PolicyPack
from . import provenance as _prov
from . import references as _ref
from .errors import Severity, ValidationDiagnostic, ValidationReport


class PolicyPackValidator:
    """Deterministic validator producing a structured :class:`ValidationReport`."""

    def __init__(self, registry: CapabilityRegistry = DEFAULT_REGISTRY) -> None:
        self._registry = registry

    def validate(self, pack: PolicyPack) -> ValidationReport:
        diagnostics: List[ValidationDiagnostic] = []
        # Schema first: an unsupported schema is fatal and short-circuits the rest.
        schema = _prov.check_schema_version(pack)
        diagnostics.extend(schema)
        if any(d.severity is Severity.FATAL for d in schema):
            return ValidationReport(
                policy_pack_id=pack.pack_id, diagnostics=tuple(diagnostics)
            )
        diagnostics.extend(_ref.check_all(pack, self._registry))
        diagnostics.extend(_prov.check_provenance(pack))
        diagnostics.extend(_prov.check_secrets(pack))
        diagnostics.extend(_prov.check_determinism(pack))
        diagnostics = _dedupe(diagnostics)
        return ValidationReport(
            policy_pack_id=pack.pack_id, diagnostics=tuple(diagnostics)
        )


def _dedupe(diagnostics: List[ValidationDiagnostic]) -> List[ValidationDiagnostic]:
    """Stable de-duplication and deterministic ordering of diagnostics."""
    seen = set()
    unique: List[ValidationDiagnostic] = []
    for d in diagnostics:
        key = (d.code, d.severity.value, d.object_id, d.message)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    # Deterministic order: severity rank, code, object id.
    severity_rank = {
        Severity.FATAL: 0,
        Severity.ERROR: 1,
        Severity.REVIEW_REQUIRED: 2,
        Severity.WARNING: 3,
        Severity.INFO: 4,
    }
    unique.sort(key=lambda d: (severity_rank[d.severity], d.code, d.object_id))
    return unique


def validate_policy_pack(
    pack: PolicyPack, registry: Optional[CapabilityRegistry] = None
) -> ValidationReport:
    """Convenience wrapper: validate ``pack`` and return its report."""
    return PolicyPackValidator(registry or DEFAULT_REGISTRY).validate(pack)
