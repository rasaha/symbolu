"""GV-3R-c — trusted readiness orchestration around the GV-3R-b evaluator.

One canonical entry point (:func:`assess_readiness`) wraps the merged
deterministic evaluator in a **fail-closed trust boundary**: the exact
``ReadinessPolicy`` must resolve through a configured shared Policy Authority
boundary at the evaluation instant, every gate result and every compensating
control must be attested by a configured verifier under the complete tenant /
subject / context / target / policy / gate / time binding, and only sanitized
inputs reach ``evaluate_readiness``.

It adds **no second classification algorithm**: the readiness tier is selected
by exactly one function, exactly once, and never by this package.

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
