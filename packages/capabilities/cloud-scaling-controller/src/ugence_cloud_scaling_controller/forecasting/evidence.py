"""``CapacityForecastEvidence`` and the controlled forecast service path.

Evidence is produced only through :func:`forecast_with_evidence`, which runs the *real*
input-window construction, the *real* forecaster, and the *real* uncertainty calibration,
then binds their outputs into an immutable evidence artifact with a deterministic
``sha256:`` content digest. A caller cannot forge evidence by supplying a fabricated
forecast — the forecast in the evidence is the one this path computed.

The service also owns the *admission* decision: it converts the facts a window records
(sample count, staleness, missingness, cadence irregularity, unit consistency, forecast
domain, calibration sample count) into either a point forecast or a typed abstention,
under an explicit :class:`AdmissionPolicy` whose safe defaults reject/abstain.

The digest covers every authoritative field (schema versions, subject/tenant, source-series
and input-window digests, cutoff/forecast-for, target/horizon, model id/version and config
digest, feature-config digest, normalization-policy digest, the forecast-or-abstention
output, and the uncertainty method/config). It EXCLUDES only ``evidence_produced_at`` (a
production timestamp) and ``diagnostic_annotation`` (a non-authoritative human note that
must not contradict the structured evidence). The digest is a content IDENTITY — not a
signature, an authorization, or any claim about forecast accuracy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from ..canonical.evidence import AUTHORITY_CLASS_ADVISORY, EXECUTION_CAPABILITY_NONE
from ..canonical.identity import CapacitySubject
from ..canonical.measurement import Measurement, Unit
from ..canonical.normalization import (
    NormalizationError,
    NormalizationPolicy,
    normalize_signal,
)
from ..canonical.serialization import content_digest
from ..version import __version__ as CONTROLLER_PACKAGE_VERSION
from .abstention import (
    FORECAST_STATUS_ABSTAINED,
    FORECAST_STATUS_FORECAST,
    AbstentionReason,
)
from .forecast import CAPACITY_FORECAST_SCHEMA_VERSION, CapacityForecast
from .forecasters import BaselineForecaster
from .series import CanonicalCapacitySeries, SeriesError, SeriesErrorReason, _as_utc
from .targets import (
    TARGET_SIGNAL_NAME,
    ForecastTarget,
    domain_for,
    extract_measurement,
)
from .uncertainty import (
    UncertaintyConfig,
    UncertaintyInterval,
    UncertaintyMethod,
    compute_uncertainty,
)
from .window import (
    FeatureConfig,
    ForecastHorizon,
    ForecastInputWindow,
    ForecastValueSpace,
    NormalizationApplicabilityError,
    build_input_window,
)

FORECAST_EVIDENCE_SCHEMA_VERSION = "capacity-forecast-evidence-1"
ADMISSION_POLICY_SCHEMA_VERSION = "capacity-forecast-admission-1"

# Excluded from the identity digest (documented above).
DIGEST_EXCLUDED_FIELDS = ("evidence_digest", "evidence_produced_at", "diagnostic_annotation")


class ForecastServiceError(ValueError):
    """Raised when the forecast service is invoked incorrectly (fail closed)."""


@dataclass(frozen=True)
class AdmissionPolicy:
    """Explicit thresholds converting window facts into forecast-or-abstain decisions.

    Safe defaults reject/abstain: regular cadence required, out-of-domain forecasts
    abstain, and a bounded staleness/missingness. All thresholds are disclosed via the
    policy digest in evidence.
    """

    policy_id: str = "admission-strict-default"
    min_history: int = 1
    max_staleness_seconds: Optional[float] = 300.0
    max_missing_fraction: float = 0.5
    require_regular_cadence: bool = True
    max_irregular_gaps: int = 0
    allow_out_of_domain: bool = False
    schema_version: str = ADMISSION_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or self.policy_id == "":
            raise ForecastServiceError("policy_id must be a non-empty string")
        if isinstance(self.min_history, bool) or not isinstance(self.min_history, int) or self.min_history < 1:
            raise ForecastServiceError("min_history must be an int >= 1")
        if self.max_staleness_seconds is not None:
            v = self.max_staleness_seconds
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                raise ForecastServiceError("max_staleness_seconds must be a real number >= 0 or None")
        if not (0.0 <= self.max_missing_fraction <= 1.0):
            raise ForecastServiceError("max_missing_fraction must be in [0, 1]")
        if isinstance(self.max_irregular_gaps, bool) or not isinstance(self.max_irregular_gaps, int) or self.max_irregular_gaps < 0:
            raise ForecastServiceError("max_irregular_gaps must be an int >= 0")

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "min_history": self.min_history,
            "max_staleness_seconds": self.max_staleness_seconds,
            "max_missing_fraction": self.max_missing_fraction,
            "require_regular_cadence": self.require_regular_cadence,
            "max_irregular_gaps": self.max_irregular_gaps,
            "allow_out_of_domain": self.allow_out_of_domain,
        }

    def digest(self) -> str:
        return content_digest("forecast_admission_policy", self.schema_version, self.to_canonical_dict())


def _unavailable_uncertainty(config: UncertaintyConfig, reason: str) -> UncertaintyInterval:
    return UncertaintyInterval(
        method=config.method.value,
        requested_coverage=config.requested_coverage,
        calibration_sample_count=0,
        available=False,
        unavailable_reason=reason,
        calibration_window_id=config.calibration_window_id,
    )


def _unit_label(window: ForecastInputWindow) -> str:
    units = window.units_present
    if len(units) == 1:
        return units[0]
    if len(units) == 0:
        return ""
    return "inconsistent"


_APPLICABILITY_REASON = {
    "missing_normalization_policy": AbstentionReason.MISSING_NORMALIZATION_POLICY,
    "inconsistent_unit": AbstentionReason.INCONSISTENT_UNIT,
    "unsupported_target": AbstentionReason.UNSUPPORTED_TARGET,
}


def _forecast_and_window(
    series: CanonicalCapacitySeries,
    target: ForecastTarget,
    cutoff: datetime,
    horizon: ForecastHorizon,
    forecaster: BaselineForecaster,
    *,
    normalization_policy: Optional[NormalizationPolicy],
    feature_config: FeatureConfig,
    uncertainty_config: UncertaintyConfig,
    admission_policy: AdmissionPolicy,
    correlation_id: Optional[str],
    expected_subject: Optional[CapacitySubject],
    forecast_space: ForecastValueSpace,
) -> Tuple[CapacityForecast, ForecastInputWindow]:
    """Core deterministic decision: build the window, then forecast or abstain."""
    if not isinstance(series, CanonicalCapacitySeries):
        raise ForecastServiceError("series must be a CanonicalCapacitySeries")
    if not isinstance(forecaster, BaselineForecaster):
        raise ForecastServiceError("forecaster must be a BaselineForecaster")
    if not isinstance(forecast_space, ForecastValueSpace):
        raise ForecastServiceError("forecast_space must be a ForecastValueSpace")

    # A RAW probe window is always built (leakage-safe) so even an abstention binds a real
    # window and every space-independent gate reads raw facts (units/cadence/missingness).
    probe = build_input_window(series, target, cutoff, horizon, feature_config)
    model_config_digest = forecaster.config_digest()

    def _make(
        window: ForecastInputWindow,
        status: str,
        *,
        point: Optional[float],
        reason: Optional[AbstentionReason],
        uncertainty: UncertaintyInterval,
        warnings: Tuple[str, ...] = (),
    ) -> CapacityForecast:
        return CapacityForecast(
            schema_version=CAPACITY_FORECAST_SCHEMA_VERSION,
            subject=series.subject,
            correlation_id=correlation_id,
            target=target,
            forecast_cutoff=cutoff,
            horizon=horizon,
            forecast_for=window.forecast_for,
            model_id=forecaster.model_id,
            model_version=forecaster.model_version,
            status=status,
            unit=_unit_label(window),
            input_window_digest=window.digest(),
            model_config_digest=model_config_digest,
            uncertainty=uncertainty,
            point_estimate=point,
            abstention_reason=reason,
            warnings=warnings,
            value_space=window.value_space,
            normalization_applied=window.normalization_applied,
        )

    def _abstain(reason: AbstentionReason, window: ForecastInputWindow) -> Tuple[CapacityForecast, ForecastInputWindow]:
        return _make(
            window, FORECAST_STATUS_ABSTAINED,
            point=None, reason=reason,
            uncertainty=_unavailable_uncertainty(uncertainty_config, "abstained"),
        ), window

    # --- structural gates ----------------------------------------------------------
    if expected_subject is not None:
        if series.subject.workload_id != expected_subject.workload_id:
            return _abstain(AbstentionReason.SUBJECT_MISMATCH, probe)
        if series.subject != expected_subject:
            return _abstain(AbstentionReason.TENANT_SCOPE_MISMATCH, probe)

    if not forecaster.supports_target(target):
        return _abstain(AbstentionReason.UNSUPPORTED_TARGET, probe)
    if not forecaster.supports_horizon(horizon):
        return _abstain(AbstentionReason.UNSUPPORTED_HORIZON, probe)
    if normalization_policy is None:
        return _abstain(AbstentionReason.MISSING_NORMALIZATION_POLICY, probe)
    if not isinstance(normalization_policy, NormalizationPolicy):
        raise ForecastServiceError("normalization_policy must be a NormalizationPolicy or None")

    # --- data-quality gates (raw facts) --------------------------------------------
    if len(probe.units_present) > 1:
        return _abstain(AbstentionReason.INCONSISTENT_UNIT, probe)
    if any(not math.isfinite(v) for v in probe.values):  # defensive; measurements are finite
        return _abstain(AbstentionReason.INVALID_MEASUREMENT, probe)

    # Input-domain enforcement: every raw observation must lie within its SignalDomain
    # (bounds + integer semantics from the Phase-1 authority). Never clamp/round/coerce.
    for s in probe.samples:
        if not domain_for(s.unit).contains(s.value):
            return _abstain(AbstentionReason.INVALID_MEASUREMENT, probe)

    effective_min = max(admission_policy.min_history, forecaster.min_history)
    if probe.sample_count < effective_min:
        return _abstain(AbstentionReason.INSUFFICIENT_HISTORY, probe)

    if admission_policy.max_staleness_seconds is not None and probe.last_event_time is not None:
        staleness = (_as_utc(cutoff) - _as_utc(probe.last_event_time)).total_seconds()
        if staleness > admission_policy.max_staleness_seconds:
            return _abstain(AbstentionReason.STALE_HISTORY, probe)

    if probe.missingness.missing_fraction > admission_policy.max_missing_fraction:
        return _abstain(AbstentionReason.EXCESSIVE_MISSINGNESS, probe)

    if admission_policy.require_regular_cadence and (
        probe.cadence.irregular_gap_count > admission_policy.max_irregular_gaps
    ):
        return _abstain(AbstentionReason.IRREGULAR_CADENCE, probe)

    # --- normalization applicability (Phase-1 authority) ---------------------------
    signal = TARGET_SIGNAL_NAME.get(target)
    if signal is not None:
        if normalization_policy.method_by_signal.get(signal) is None:
            return _abstain(AbstentionReason.MISSING_NORMALIZATION_POLICY, probe)
        # Validate the supplied policy actually applies to these observations' unit.
        s0 = probe.samples[0]
        try:
            normalize_signal(signal, Measurement(s0.value, Unit(s0.unit)), normalization_policy)
        except (NormalizationError, ValueError):
            return _abstain(AbstentionReason.INCONSISTENT_UNIT, probe)
    elif forecast_space is ForecastValueSpace.NORMALIZED:
        # e.g. RUNNING_REPLICAS: projected without conversion, cannot be normalized.
        return _abstain(AbstentionReason.UNSUPPORTED_TARGET, probe)

    # --- working window (raw reference digest, or explicitly normalized) -----------
    try:
        window = build_input_window(
            series, target, cutoff, horizon, feature_config,
            normalization_policy=normalization_policy, forecast_space=forecast_space,
        )
    except NormalizationApplicabilityError as exc:
        return _abstain(_APPLICABILITY_REASON.get(exc.reason, AbstentionReason.MISSING_NORMALIZATION_POLICY), probe)

    # --- point estimate ------------------------------------------------------------
    point = forecaster.point_estimate(window)
    if point is None:
        return _abstain(AbstentionReason.INSUFFICIENT_HISTORY, window)
    if not math.isfinite(point):
        return _abstain(AbstentionReason.INVALID_MEASUREMENT, window)

    warnings: Tuple[str, ...] = ()

    # --- output-domain gate (bounds AND integer semantics; never clamp) ------------
    unit_label = _unit_label(window)
    domain = domain_for(unit_label) if unit_label else None
    if domain is not None and not domain.contains(point):
        if not admission_policy.allow_out_of_domain:
            return _abstain(AbstentionReason.FORECAST_OUTSIDE_DOMAIN, window)
        warnings = warnings + (
            f"forecast {point!r} is outside the admissible {unit_label} domain "
            f"[{domain.lower}, {domain.upper}]{' (integer-valued)' if domain.integer else ''}; "
            "retained by explicit allow_out_of_domain policy",
        )

    # --- uncertainty ---------------------------------------------------------------
    uncertainty = compute_uncertainty(window, forecaster, point, uncertainty_config)
    if (
        uncertainty_config.method is not UncertaintyMethod.NONE
        and not uncertainty.available
        and uncertainty.insufficient_calibration
        and not uncertainty_config.allow_point_only_when_uncalibrated
    ):
        return _abstain(AbstentionReason.INSUFFICIENT_CALIBRATION_HISTORY, window)
    if not uncertainty.available and uncertainty.insufficient_calibration:
        warnings = warnings + (
            "uncertainty interval unavailable (insufficient calibration residuals); "
            "retained as a point-only forecast by explicit policy",
        )

    return _make(
        window, FORECAST_STATUS_FORECAST,
        point=point, reason=None, uncertainty=uncertainty, warnings=warnings,
    ), window


def generate_forecast(
    series: CanonicalCapacitySeries,
    target: ForecastTarget,
    cutoff: datetime,
    horizon: ForecastHorizon,
    forecaster: BaselineForecaster,
    *,
    normalization_policy: Optional[NormalizationPolicy],
    feature_config: Optional[FeatureConfig] = None,
    uncertainty_config: Optional[UncertaintyConfig] = None,
    admission_policy: Optional[AdmissionPolicy] = None,
    correlation_id: Optional[str] = None,
    expected_subject: Optional[CapacitySubject] = None,
    forecast_space: ForecastValueSpace = ForecastValueSpace.PROJECTED_WITHOUT_CONVERSION,
) -> CapacityForecast:
    """Produce a :class:`CapacityForecast` (point or typed abstention) — no evidence."""
    forecast, _window = _forecast_and_window(
        series, target, cutoff, horizon, forecaster,
        normalization_policy=normalization_policy,
        feature_config=feature_config or FeatureConfig(),
        uncertainty_config=uncertainty_config or UncertaintyConfig(),
        admission_policy=admission_policy or AdmissionPolicy(),
        correlation_id=correlation_id,
        expected_subject=expected_subject,
        forecast_space=forecast_space,
    )
    return forecast


@dataclass(frozen=True)
class CapacityForecastEvidence:
    """Immutable evidence artifact binding the window, model config, and forecast output."""

    evidence_schema_version: str
    series_schema_version: str
    input_window_schema_version: str
    forecast_schema_version: str
    controller_package_version: str

    source_series_digest: str
    input_window_digest: str
    feature_config_digest: str
    admission_policy_digest: str
    uncertainty_config_digest: str
    model_config_digest: str
    normalization_policy_id: Optional[str]
    normalization_policy_digest: Optional[str]

    forecast: CapacityForecast
    evidence_produced_at: datetime
    diagnostic_annotation: str = ""

    authority_class: str = AUTHORITY_CLASS_ADVISORY
    execution_capability: str = EXECUTION_CAPABILITY_NONE
    advisory_only: bool = True
    shadow_only: bool = True
    actuation_performed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.forecast, CapacityForecast):
            raise ForecastServiceError("forecast must be a CapacityForecast")
        if self.advisory_only is not True or self.shadow_only is not True:
            raise ForecastServiceError("evidence must be advisory-only and shadow-only")
        if self.actuation_performed is not False:
            raise ForecastServiceError("actuation_performed must be False")
        if self.authority_class != AUTHORITY_CLASS_ADVISORY:
            raise ForecastServiceError("authority_class must be ADVISORY")
        if self.execution_capability != EXECUTION_CAPABILITY_NONE:
            raise ForecastServiceError("execution_capability must be NONE")

    def to_canonical_dict(self, *, include_digest: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "evidence_schema_version": self.evidence_schema_version,
            "series_schema_version": self.series_schema_version,
            "input_window_schema_version": self.input_window_schema_version,
            "forecast_schema_version": self.forecast_schema_version,
            "controller_package_version": self.controller_package_version,
            "source_series_digest": self.source_series_digest,
            "input_window_digest": self.input_window_digest,
            "feature_config_digest": self.feature_config_digest,
            "admission_policy_digest": self.admission_policy_digest,
            "uncertainty_config_digest": self.uncertainty_config_digest,
            "model_config_digest": self.model_config_digest,
            "normalization_policy_id": self.normalization_policy_id,
            "normalization_policy_digest": self.normalization_policy_digest,
            "forecast": self.forecast.to_canonical_dict(),
            "evidence_produced_at": self.evidence_produced_at,
            "diagnostic_annotation": self.diagnostic_annotation,
            "authority_class": self.authority_class,
            "execution_capability": self.execution_capability,
            "advisory_only": self.advisory_only,
            "shadow_only": self.shadow_only,
            "actuation_performed": self.actuation_performed,
        }
        if include_digest:
            data["evidence_digest"] = self.digest()
        return data

    def _digest_payload(self) -> Dict[str, Any]:
        data = self.to_canonical_dict(include_digest=False)
        for excluded in DIGEST_EXCLUDED_FIELDS:
            data.pop(excluded, None)
        return data

    def digest(self) -> str:
        """Deterministic ``sha256:`` identity over all authoritative fields."""
        return content_digest(
            "capacity_forecast_evidence", self.evidence_schema_version, self._digest_payload()
        )


def forecast_with_evidence(
    series: CanonicalCapacitySeries,
    target: ForecastTarget,
    cutoff: datetime,
    horizon: ForecastHorizon,
    forecaster: BaselineForecaster,
    *,
    normalization_policy: Optional[NormalizationPolicy],
    feature_config: Optional[FeatureConfig] = None,
    uncertainty_config: Optional[UncertaintyConfig] = None,
    admission_policy: Optional[AdmissionPolicy] = None,
    correlation_id: Optional[str] = None,
    expected_subject: Optional[CapacitySubject] = None,
    forecast_space: ForecastValueSpace = ForecastValueSpace.PROJECTED_WITHOUT_CONVERSION,
    evidence_produced_at: Optional[datetime] = None,
    diagnostic_annotation: str = "",
) -> CapacityForecastEvidence:
    """Controlled service path: build window → forecast/abstain → bind evidence.

    ``evidence_produced_at`` is a caller-supplied trusted timestamp (never generated in
    this deterministic path); it defaults to the cutoff so the call stays clock-free and
    deterministic, and it is excluded from the evidence identity digest.
    """
    feature_config = feature_config or FeatureConfig()
    uncertainty_config = uncertainty_config or UncertaintyConfig()
    admission_policy = admission_policy or AdmissionPolicy()

    forecast, window = _forecast_and_window(
        series, target, cutoff, horizon, forecaster,
        normalization_policy=normalization_policy,
        feature_config=feature_config,
        uncertainty_config=uncertainty_config,
        admission_policy=admission_policy,
        correlation_id=correlation_id,
        expected_subject=expected_subject,
        forecast_space=forecast_space,
    )
    produced_at = evidence_produced_at if evidence_produced_at is not None else cutoff
    if not isinstance(produced_at, datetime):
        raise ForecastServiceError("evidence_produced_at must be a datetime")

    return CapacityForecastEvidence(
        evidence_schema_version=FORECAST_EVIDENCE_SCHEMA_VERSION,
        series_schema_version=series.schema_version,
        input_window_schema_version=window.schema_version,
        forecast_schema_version=forecast.schema_version,
        controller_package_version=CONTROLLER_PACKAGE_VERSION,
        source_series_digest=series.digest(),
        input_window_digest=window.digest(),
        feature_config_digest=feature_config.digest(),
        admission_policy_digest=admission_policy.digest(),
        uncertainty_config_digest=uncertainty_config.digest(),
        model_config_digest=forecaster.config_digest(),
        normalization_policy_id=(normalization_policy.policy_id if normalization_policy else None),
        normalization_policy_digest=(normalization_policy.digest() if normalization_policy else None),
        forecast=forecast,
        evidence_produced_at=produced_at,
        diagnostic_annotation=diagnostic_annotation,
    )


# Series-construction failures that a controlled admission boundary converts into typed,
# evidence-producing abstentions (everything else re-raises — never silently swallowed).
_SERIES_ERROR_ABSTENTION = {
    SeriesErrorReason.INVALID_TIME_ORDER: AbstentionReason.INVALID_TIME_ORDER,
    SeriesErrorReason.CONFLICTING_DUPLICATE: AbstentionReason.CONFLICTING_DUPLICATE,
    SeriesErrorReason.DUPLICATE_TIMESTAMP: AbstentionReason.CONFLICTING_DUPLICATE,
    SeriesErrorReason.CROSS_SUBJECT: AbstentionReason.SUBJECT_MISMATCH,
    SeriesErrorReason.CROSS_TENANT: AbstentionReason.TENANT_SCOPE_MISMATCH,
}


def _construction_abstention_forecast(
    observations, target, cutoff, horizon, forecaster, correlation_id, reason,
) -> CapacityForecast:
    """Build a typed abstention forecast when a series could not be constructed.

    Binds a deterministic input-window digest over the (sorted) rejected observation
    digests + the failure reason, so the evidence records *which* inputs were rejected and
    *why* without implying a usable window ever existed."""
    obs = list(observations)
    subject = obs[0].subject
    forecast_for = cutoff + horizon.delta
    rejected = {
        "reason": reason.value,
        "rejected_state_digests": sorted(o.digest() for o in obs),
        "subject": subject.to_canonical_dict(),
        "target": target.value,
        "cutoff": cutoff,
        "forecast_for": forecast_for,
    }
    window_digest = content_digest("forecast_input_window_rejected", "capacity-forecast-window-1", rejected)
    return CapacityForecast(
        schema_version=CAPACITY_FORECAST_SCHEMA_VERSION,
        subject=subject,
        correlation_id=correlation_id,
        target=target,
        forecast_cutoff=cutoff,
        horizon=horizon,
        forecast_for=forecast_for,
        model_id=forecaster.model_id,
        model_version=forecaster.model_version,
        status=FORECAST_STATUS_ABSTAINED,
        unit="",
        input_window_digest=window_digest,
        model_config_digest=forecaster.config_digest(),
        uncertainty=UncertaintyInterval(
            method="none", requested_coverage=0.5, calibration_sample_count=0,
            available=False, unavailable_reason="series_construction_failed"),
        point_estimate=None,
        abstention_reason=reason,
    )


def forecast_from_observations(
    observations,
    target: ForecastTarget,
    cutoff: datetime,
    horizon: ForecastHorizon,
    forecaster: BaselineForecaster,
    *,
    normalization_policy: Optional[NormalizationPolicy],
    series_policy=None,
    feature_config: Optional[FeatureConfig] = None,
    uncertainty_config: Optional[UncertaintyConfig] = None,
    admission_policy: Optional[AdmissionPolicy] = None,
    correlation_id: Optional[str] = None,
    expected_subject: Optional[CapacitySubject] = None,
    forecast_space: ForecastValueSpace = ForecastValueSpace.PROJECTED_WITHOUT_CONVERSION,
    evidence_produced_at: Optional[datetime] = None,
    diagnostic_annotation: str = "",
) -> CapacityForecastEvidence:
    """Controlled admission boundary: build the series from raw observations, mapping the
    expected *data-quality* construction failures (invalid event-time order, conflicting/
    duplicate timestamps, cross-subject/tenant contamination) to typed, evidence-producing
    abstentions. Any other error (a programming/type error) is NOT swallowed — it re-raises.

    This is what makes ``INVALID_TIME_ORDER`` and ``CONFLICTING_DUPLICATE`` reachable as
    typed Phase-2 abstentions while the strict :meth:`CanonicalCapacitySeries.build` API and
    its fail-closed exceptions are preserved for callers that want them.
    """
    obs = list(observations)
    if not obs:
        raise ForecastServiceError("forecast_from_observations requires >= 1 observation")
    try:
        series = CanonicalCapacitySeries.build(obs, series_policy)
    except SeriesError as exc:
        mapped = _SERIES_ERROR_ABSTENTION.get(exc.reason)
        if mapped is None:
            raise  # empty/type/naive-timestamp etc. remain hard failures (not swallowed)
        forecast = _construction_abstention_forecast(
            obs, target, cutoff, horizon, forecaster, correlation_id, mapped)
        produced_at = evidence_produced_at if evidence_produced_at is not None else cutoff
        return CapacityForecastEvidence(
            evidence_schema_version=FORECAST_EVIDENCE_SCHEMA_VERSION,
            series_schema_version="capacity-series-1",
            input_window_schema_version="capacity-forecast-window-1",
            forecast_schema_version=forecast.schema_version,
            controller_package_version=CONTROLLER_PACKAGE_VERSION,
            source_series_digest="sha256:series-not-constructed",
            input_window_digest=forecast.input_window_digest,
            feature_config_digest=(feature_config or FeatureConfig()).digest(),
            admission_policy_digest=(admission_policy or AdmissionPolicy()).digest(),
            uncertainty_config_digest=(uncertainty_config or UncertaintyConfig()).digest(),
            model_config_digest=forecaster.config_digest(),
            normalization_policy_id=(normalization_policy.policy_id if normalization_policy else None),
            normalization_policy_digest=(normalization_policy.digest() if normalization_policy else None),
            forecast=forecast,
            evidence_produced_at=produced_at,
            diagnostic_annotation=diagnostic_annotation,
        )

    return forecast_with_evidence(
        series, target, cutoff, horizon, forecaster,
        normalization_policy=normalization_policy,
        feature_config=feature_config,
        uncertainty_config=uncertainty_config,
        admission_policy=admission_policy,
        correlation_id=correlation_id,
        expected_subject=expected_subject,
        forecast_space=forecast_space,
        evidence_produced_at=evidence_produced_at,
        diagnostic_annotation=diagnostic_annotation,
    )


__all__ = [
    "FORECAST_EVIDENCE_SCHEMA_VERSION",
    "ADMISSION_POLICY_SCHEMA_VERSION",
    "DIGEST_EXCLUDED_FIELDS",
    "ForecastServiceError",
    "AdmissionPolicy",
    "CapacityForecastEvidence",
    "generate_forecast",
    "forecast_with_evidence",
    "forecast_from_observations",
]
