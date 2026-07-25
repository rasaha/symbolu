"""Decision Governance Middleware — **public API surface**.

This package is the *stable, supported* import surface for consumers (domains and
applications). Import governance concepts from here:

    from decision_governance.api.services import DecisionCaseService
    from decision_governance.api.contracts import DecisionRecord, DecisionOutcome
    from decision_governance.api.ports import LinkedRecordPort

rather than from the kernel's internal implementation modules
(``decision_governance.services.case_decision_service`` etc.). The internal
modules remain importable for backward compatibility, but only the symbols
re-exported here are covered by the versioning guarantees in
``decision_governance.version``.

Public API modules:

* ``contracts``      — governance record models + their status/outcome/authority enums
* ``services``       — the governance services (the engine)
* ``ports``          — the provider-neutral seams (LinkedRecord, ControlPlane, ExternalExecution)
* ``repositories``   — repository ports + in-memory reference adapters
* ``vocabulary``     — the reason-code / uncertainty taxonomy
* ``audit``          — audit event contract, catalog, namespace partition, service
* ``identity``       — actor identity + provider
* ``policy``         — access policy, permissions, grants
* ``errors``         — the typed error taxonomy
* ``common``         — clock / id-factory / canonical-hash utilities (for adapter authors)

Object identity is preserved: every symbol here *is* the same object as its
internal definition, so ``isinstance``, hashing, and serialization are identical
whichever path a caller used.
"""

from __future__ import annotations

from ..version import __version__

from . import (
    audit,
    common,
    contracts,
    errors,
    identity,
    policy,
    ports,
    repositories,
    services,
    vocabulary,
)

__all__ = [
    "__version__",
    "contracts",
    "services",
    "ports",
    "repositories",
    "vocabulary",
    "audit",
    "identity",
    "policy",
    "errors",
    "common",
]
