"""Predictive Capacity Intelligence — Phase 2 (shadow forecasting + replay evaluation).

This additive, pure-stdlib leaf subpackage answers, in SHADOW mode only:

    Given the capacity history available at event time, what capacity pressure is likely at
    a future horizon, how uncertain is that prediction, and how well has the method
    performed in replay?

Architecture (nothing here feeds the live controller decision path)::

    CanonicalCapacityState history
              ↓  series validation + strict event-time ordering
    CanonicalCapacitySeries
              ↓  leakage-safe input window (event_time <= cutoff, invariant-checked)
    ForecastInputWindow
              ↓  deterministic baseline forecaster (persistence / linear trend)
    CapacityForecast          (point estimate + uncertainty  OR  typed abstention)
              ↓  controlled service path binds window + config + output
    CapacityForecastEvidence  (immutable, sha256 content-identity digest)
              ↓  shadow replay against strictly-later actual observations
    ForecastEvaluationRecord  + deterministic aggregate evaluation report

Boundary: a FORECAST is descriptive capacity intelligence. It is NOT a recommendation, a
risk evaluation, an authority, or an execution instruction. Every forecast and every
evidence artifact carries ``advisory_only=True``, ``shadow_only=True``,
``actuation_performed=False``, ``authority_class=ADVISORY``, ``execution_capability=NONE``.
This layer imports no Risk Authority / ActionGate / execution-assurance package, performs no
network / subprocess / credential / LLM activity, and adds no runtime dependency.

Predictive-quality status: the shipped forecasters are deterministic BASELINES verified for
implementation correctness only. Absent evaluation on representative external workloads
against preregistered acceptance thresholds, forecast accuracy is
``PREDICTIVE_QUALITY_NOT_ESTABLISHED``.
"""

from __future__ import annotations

from .abstention import (
    FORECAST_STATUS_ABSTAINED,
    FORECAST_STATUS_FORECAST,
    AbstentionReason,
)
from .targets import (
    ForecastTarget,
    REPLICAS_UNIT,
    TARGET_SIGNAL_NAME,
    SignalDomain,
    TargetError,
    TargetSample,
    domain_for,
    extract_sample,
    extract_measurement,
)
from .series import (
    CANONICAL_SERIES_SCHEMA_VERSION,
    CanonicalCapacitySeries,
    DuplicateTimestampPolicy,
    OrderingPolicy,
    SeriesConstructionPolicy,
    SeriesError,
    SeriesErrorReason,
)
from .window import (
    FEATURE_CONFIG_SCHEMA_VERSION,
    INPUT_WINDOW_SCHEMA_VERSION,
    NORMALIZED_UNIT,
    CadenceInfo,
    FeatureConfig,
    ForecastHorizon,
    ForecastInputWindow,
    ForecastValueSpace,
    HORIZON_5M,
    HORIZON_15M,
    HORIZON_60M,
    MissingnessInfo,
    NormalizationApplicabilityError,
    WindowError,
    build_input_window,
)
from .forecasters import (
    BaselineForecaster,
    ForecasterError,
    LinearTrendForecaster,
    PersistenceForecaster,
)
from .uncertainty import (
    UNCERTAINTY_CONFIG_SCHEMA_VERSION,
    UncertaintyConfig,
    UncertaintyError,
    UncertaintyInterval,
    UncertaintyMethod,
    compute_uncertainty,
    interval_from_residuals,
    rolling_origin_residuals,
)
from .forecast import (
    CAPACITY_FORECAST_SCHEMA_VERSION,
    CapacityForecast,
    ForecastError,
)
from .evidence import (
    ADMISSION_POLICY_SCHEMA_VERSION,
    FORECAST_EVIDENCE_SCHEMA_VERSION,
    AdmissionPolicy,
    CapacityForecastEvidence,
    ForecastServiceError,
    forecast_from_observations,
    forecast_with_evidence,
    generate_forecast,
)
from .evaluation import (
    AGGREGATE_EVALUATION_SCHEMA_VERSION,
    EVALUATION_RECORD_SCHEMA_VERSION,
    AggregateEvaluation,
    EvaluationError,
    EvaluationStatus,
    ForecastEvaluationRecord,
    aggregate_evaluations,
    evaluate_forecast,
    unscored_record,
)
from .evaluation_forecasters import (
    DAILY_PERIOD_SECONDS,
    HarmonicPhaseForecaster,
    SeasonalNaiveForecaster,
)
from .calibration import (
    CALIBRATION_RESIDUALS_SCHEMA_VERSION,
    CalibrationProvider,
    CalibrationResiduals,
    validate_calibration,
)
from .calibration_bank import (
    DEFAULT_BANK_CAP,
    PrequentialResidualBank,
    ReplayCalibrationProvider,
    ResidualEntry,
    cutoff_sequence_digest,
    is_calibration_origin,
)
from .replay import (
    ReplayError,
    ReplayEvaluationResult,
    default_cutoffs,
    run_replay_evaluation,
)

__all__ = [
    # abstention
    "FORECAST_STATUS_ABSTAINED", "FORECAST_STATUS_FORECAST", "AbstentionReason",
    # targets
    "ForecastTarget", "REPLICAS_UNIT", "TARGET_SIGNAL_NAME", "SignalDomain", "TargetError",
    "TargetSample", "domain_for", "extract_sample", "extract_measurement",
    # series
    "CANONICAL_SERIES_SCHEMA_VERSION", "CanonicalCapacitySeries",
    "DuplicateTimestampPolicy", "OrderingPolicy", "SeriesConstructionPolicy", "SeriesError",
    "SeriesErrorReason",
    # window
    "FEATURE_CONFIG_SCHEMA_VERSION", "INPUT_WINDOW_SCHEMA_VERSION", "NORMALIZED_UNIT",
    "CadenceInfo", "FeatureConfig", "ForecastHorizon", "ForecastInputWindow",
    "ForecastValueSpace", "HORIZON_5M", "HORIZON_15M", "HORIZON_60M", "MissingnessInfo",
    "NormalizationApplicabilityError", "WindowError", "build_input_window",
    # forecasters
    "BaselineForecaster", "ForecasterError", "LinearTrendForecaster", "PersistenceForecaster",
    # uncertainty
    "UNCERTAINTY_CONFIG_SCHEMA_VERSION", "UncertaintyConfig", "UncertaintyError",
    "UncertaintyInterval", "UncertaintyMethod", "compute_uncertainty", "interval_from_residuals", "rolling_origin_residuals",
    # forecast contract
    "CAPACITY_FORECAST_SCHEMA_VERSION", "CapacityForecast", "ForecastError",
    # evidence + service
    "ADMISSION_POLICY_SCHEMA_VERSION", "FORECAST_EVIDENCE_SCHEMA_VERSION", "AdmissionPolicy",
    "CapacityForecastEvidence", "ForecastServiceError", "forecast_with_evidence",
    "forecast_from_observations", "generate_forecast",
    # evaluation
    "AGGREGATE_EVALUATION_SCHEMA_VERSION", "EVALUATION_RECORD_SCHEMA_VERSION",
    "AggregateEvaluation", "EvaluationError", "EvaluationStatus", "ForecastEvaluationRecord",
    "aggregate_evaluations", "evaluate_forecast", "unscored_record",
    # replay
    "ReplayError",
    "DAILY_PERIOD_SECONDS", "HarmonicPhaseForecaster", "SeasonalNaiveForecaster",
    "CALIBRATION_RESIDUALS_SCHEMA_VERSION", "CalibrationProvider", "CalibrationResiduals",
    "validate_calibration", "DEFAULT_BANK_CAP", "PrequentialResidualBank",
    "ReplayCalibrationProvider", "ResidualEntry", "cutoff_sequence_digest",
    "is_calibration_origin", "ReplayEvaluationResult", "default_cutoffs", "run_replay_evaluation",
]
