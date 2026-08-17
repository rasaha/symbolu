"""Typed adapter errors.

Every error here signals a **fail-closed** condition: the adapter could not produce a
safe typed result, so it produced none. No error path mints authority, reaches the Risk
Authority evaluation seam, or degrades into an approval — the adapter has no field or
code path that could express one.

The split between an *error* and a typed *outcome* is deliberate:

* :mod:`~ugence_cloud_scaling_risk_integration.authenticity` and
  :mod:`~ugence_cloud_scaling_risk_integration.projection` are pure functions and
  **raise** these errors, so a caller composing them directly cannot ignore a failure;
* :class:`~ugence_cloud_scaling_risk_integration.adapter.CloudScalingRiskAdapter`
  catches them at its boundary and returns the typed non-evaluation outcome
  (:class:`~ugence_cloud_scaling_risk_integration.outcomes.CloudScalingRiskOutcome`)
  that the ADR §12 failure table requires.

Each distinguishable failure has its **own error class** rather than a shared class the
adapter would have to tell apart by inspecting a message. Message-matching would make the
mapping from failure to typed audit reason depend on prose that a later edit could break
silently, so the distinction is carried in the type system instead.
"""

from __future__ import annotations

__all__ = [
    "CloudScalingRiskIntegrationError",
    "AdapterConfigurationError",
    "RecommendationInputError",
    "UnsupportedRecommendationSourceError",
    "RecommendationAuthenticityError",
    "MissingIndependentDigestError",
    "RecommendationValidityError",
    "RecommendationNotYetValidError",
    "ProjectionError",
    "NonExecutableInvariantError",
]


class CloudScalingRiskIntegrationError(ValueError):
    """Base class for every fail-closed Phase 4C adapter error."""


class AdapterConfigurationError(CloudScalingRiskIntegrationError):
    """The adapter was constructed with an unsafe or incomplete configuration.

    Raised when the injected evaluation seam or trusted clock is missing or does not
    satisfy its narrow port. The adapter never substitutes a default: it holds no
    resolver, no authority, no evidence source, no policy and no clock of its own, so
    an absent dependency is a construction failure rather than something to fill in.
    """


class RecommendationInputError(CloudScalingRiskIntegrationError):
    """The input is not an accepted controller artifact, or is malformed.

    Covers any strict-reconstruction failure reported by the controller's own
    ``from_dict``: unknown field, missing field, non-canonical value, or an internally
    inconsistent record.
    """


class UnsupportedRecommendationSourceError(RecommendationInputError):
    """The input is not an accepted controller artifact at all.

    A foreign or duck-typed object, a mapping with no explicit ``schema_version``, or a
    mapping carrying an unrecognized canonical schema tag. Distinguished from a malformed
    *recommendation* because the two are different audit facts: one says "this is not the
    contract", the other says "this is the contract, and it does not hold together".
    """


class RecommendationAuthenticityError(CloudScalingRiskIntegrationError):
    """The recommendation's source authenticity could not be established.

    Raised when the independently carried (or caller-supplied expected) recommendation
    digest is absent, malformed, or does not equal the digest recomputed from the
    reconstructed recommendation. See the module docstring of
    :mod:`~ugence_cloud_scaling_risk_integration.authenticity` for exactly what this
    check does and does not prove.
    """


class MissingIndependentDigestError(RecommendationAuthenticityError):
    """No independent digest expectation was available to check against.

    Raised — rather than falling back to comparing the object's digest with itself —
    when a live recommendation arrives with no ``expected_recommendation_digest`` and no
    carried canonical digest. A self-comparison would always succeed and prove nothing,
    so the adapter declines to claim an authenticity it cannot establish.
    """


class RecommendationValidityError(CloudScalingRiskIntegrationError):
    """The recommendation has expired at the trusted evaluation time."""


class RecommendationNotYetValidError(RecommendationValidityError):
    """The recommendation's validity window has not opened at the trusted time."""


class ProjectionError(CloudScalingRiskIntegrationError):
    """A safe neutral subject projection could not be constructed.

    Raised when a required subject fact is absent (tenant, workload id, forecast
    evidence reference), when a controller value is not canonically representable at the
    Risk Authority boundary (non-NFC string, naive timestamp, non-integer magnitude), or
    when the locally recomputed binding chain fails to reconcile.
    """


class NonExecutableInvariantError(CloudScalingRiskIntegrationError):
    """A result carried an execution/authorization flag that was not ``False``.

    Phase 4C terminates at a non-executable decision. A forged ``True`` is **rejected**,
    never normalized to ``False`` — normalizing would silently launder the very claim
    the invariant exists to refuse.
    """
