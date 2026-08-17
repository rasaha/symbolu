"""Trusted Readiness Orchestration around the GV-3R-b evaluator.

An **additive integration capability**, not a new roadmap milestone. One
canonical entry point (:func:`assess_readiness`) wraps the merged deterministic
evaluator in a **fail-closed trust boundary**: the exact ``ReadinessPolicy``
must resolve through a configured shared Policy Authority boundary at the
evaluation instant, every gate result and every compensating control must be
attested by a configured verifier under the complete tenant / subject / context
/ target / policy / gate / time binding, and only sanitized inputs reach
``evaluate_readiness``.

It implements requirements that are **already ratified** — UVI ADR D-1, D-16,
§19 and §23.2 ("fail closed on unsigned/unapproved/expired/revoked/superseded/
digest-mismatched policy artifacts"), and Policy Authority ADR §10.4 — and
defines no new milestone of its own. It sits operationally **between** the
merged deterministic evaluator (M-3R.2) and the still-open ``M-3R.3``, which
continues to own the Intelligence/Capability/Adoption catalogs and
``AssessedSystemBinding`` wiring; neither is implemented here.

It adds **no second classification algorithm** and defines **no new readiness
classification**: the readiness tier is selected by exactly one function,
exactly once, and never by this package.

The production defaults deny. Nothing here resolves a policy or verifies an
input on its own, and no allow-all or "testing" verifier exists in this
distribution — configuring a real resolver or verifier is a composition-root
trust decision.
"""

from __future__ import annotations

from .authority import PolicyAuthorityReadinessPolicyResolver
from .codes import (
    ORCHESTRATOR_ID,
    READINESS_ORCHESTRATOR_VERSION,
    ReadinessAssessmentStatus,
    ReadinessInputVerificationStatus,
    ReadinessTrustAdvisoryState,
    ReadinessTrustGapCode,
)
from .contracts import (
    ConditionSetVerification,
    ConditionVerificationRequest,
    GateResultVerification,
    GateVerificationRequest,
    ReadinessAssessmentRequest,
)
from .deny import (
    DenyAllConditionSetVerifier,
    DenyAllGateResultVerifier,
    DenyAllReadinessPolicyResolver,
)
from .errors import ReadinessAssessmentError
from .protocols import ConditionSetVerifier, GateResultVerifier, ReadinessPolicyResolver
from .service import assess_readiness
from .trace import (
    ConditionVerificationSummary,
    GateVerificationSummary,
    ReadinessAssessmentDisposition,
    ReadinessAssessmentOutcome,
    ReadinessAssessmentTrace,
)

__all__ = [
    "ORCHESTRATOR_ID",
    "READINESS_ORCHESTRATOR_VERSION",
    "ReadinessAssessmentError",
    "ReadinessAssessmentStatus",
    "ReadinessInputVerificationStatus",
    "ReadinessTrustAdvisoryState",
    "ReadinessTrustGapCode",
    "ReadinessAssessmentRequest",
    "GateVerificationRequest",
    "GateResultVerification",
    "ConditionVerificationRequest",
    "ConditionSetVerification",
    "GateVerificationSummary",
    "ConditionVerificationSummary",
    "ReadinessAssessmentDisposition",
    "ReadinessAssessmentTrace",
    "ReadinessAssessmentOutcome",
    "ReadinessPolicyResolver",
    "GateResultVerifier",
    "ConditionSetVerifier",
    "DenyAllReadinessPolicyResolver",
    "DenyAllGateResultVerifier",
    "DenyAllConditionSetVerifier",
    "PolicyAuthorityReadinessPolicyResolver",
    "assess_readiness",
]
