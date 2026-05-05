"""``CalibrationSet`` — versioned, signed, drift-checkable
deployment bundle.

A :class:`CalibrationSet` ties the per-deployment tuning knobs
into a single artifact a fleet operator distributes, signs,
and version-controls. The bundle is JSON-serialisable + hash-
identified + kernel-version-validated. See
``CALIBRATION_DESIGN.md`` for the full design rationale.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .._version import __version__ as _autonomy_version
from . import _serialisation as ser
from .errors import (
    CalibrationDigestError,
    CalibrationSetError,
    CalibrationVersionError,
)


_REQUIRED_FIELDS = (
    "calibration_id",
    "kernel_version",
    "created_at",
    "bcvf_config",
    "consumer_v2_config",
    "bicycle_config",
    "realtime_budget",
    "dds_qos_profile",
    "safety_state_config",
    "per_predictor_failure_thresholds",
    "expected_metrics",
    "metadata",
    "digest",
)


_SEMVER_PATTERN = re.compile(
    r"^\d+\.\d+\.\d+"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def _canonical_json(payload: Dict[str, Any]) -> str:
    """Canonical JSON for digest computation: sorted keys,
    no whitespace, ensure_ascii=True, allow_nan=False. Same
    byte-output for semantically-equal dicts is the load-
    bearing property — the digest is computed over this string.

    Audit-fix Finding 3: ``allow_nan=False`` rejects NaN /
    +Inf / -Inf at digest time. The default ``json.dumps``
    behaviour serialises non-finite floats as ``NaN`` /
    ``Infinity`` literals — non-RFC-8259 + would silently
    break a deployment partner's downstream JSON tooling. The
    framework refuses non-finite inputs loud rather than emit
    them.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _compute_digest(payload_without_digest: Dict[str, Any]) -> str:
    """SHA-256 over the canonical JSON of the bundle dict
    *without* the digest field. The digest can't be computed
    over a payload that already contains itself."""
    return hashlib.sha256(
        _canonical_json(payload_without_digest).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class CalibrationSet:
    """One deployment-ready calibration bundle.

    Frozen + hash-identified + kernel-version-validated. See
    ``CALIBRATION_DESIGN.md`` §2 for the per-field rationale.
    """

    calibration_id: str
    kernel_version: str
    created_at: str
    bcvf_config: Dict[str, Any]
    consumer_v2_config: Dict[str, Any]
    bicycle_config: Dict[str, Any]
    realtime_budget: Dict[str, Any]
    dds_qos_profile: Dict[str, Any]
    safety_state_config: Dict[str, Any]
    per_predictor_failure_thresholds: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )
    expected_metrics: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )
    metadata: Dict[str, Any] = field(default_factory=dict)
    digest: str = ""

    def __post_init__(self) -> None:
        if not self.calibration_id or not self.calibration_id.strip():
            raise CalibrationSetError(
                "calibration_id must be a non-empty, non-whitespace string"
            )
        if not self.kernel_version or not self.kernel_version.strip():
            raise CalibrationSetError(
                "kernel_version must be a non-empty, non-whitespace string"
            )
        if not _SEMVER_PATTERN.match(self.kernel_version):
            raise CalibrationSetError(
                f"kernel_version {self.kernel_version!r} is not a valid "
                "semver string"
            )
        if not self.created_at or not self.created_at.strip():
            raise CalibrationSetError(
                "created_at must be a non-empty, non-whitespace ISO 8601 string"
            )
        try:
            datetime.fromisoformat(self.created_at)
        except ValueError as exc:
            raise CalibrationSetError(
                f"created_at {self.created_at!r} is not a valid ISO 8601 "
                f"timestamp: {exc}"
            ) from exc
        # Validate every embedded config dict by re-instantiating
        # its source dataclass. Catches missing keys / bad types
        # at construction so a malformed config can't ride into
        # the bundle.
        ser.validate_config_dict("bcvf_config", self.bcvf_config, ser.bcvf_config_from_dict)
        ser.validate_config_dict("consumer_v2_config", self.consumer_v2_config, ser.consumer_v2_config_from_dict)
        ser.validate_config_dict("bicycle_config", self.bicycle_config, ser.bicycle_config_from_dict)
        ser.validate_config_dict("realtime_budget", self.realtime_budget, ser.realtime_budget_from_dict)
        ser.validate_config_dict("dds_qos_profile", self.dds_qos_profile, ser.dds_qos_profile_from_dict)
        ser.validate_config_dict("safety_state_config", self.safety_state_config, ser.safety_state_config_from_dict)
        # Per-predictor failure thresholds: each value validates
        # as a FailureConfig.
        if not isinstance(self.per_predictor_failure_thresholds, dict):
            raise CalibrationSetError(
                "per_predictor_failure_thresholds must be a dict"
            )
        for predictor_name, payload in self.per_predictor_failure_thresholds.items():
            ser.validate_config_dict(
                f"per_predictor_failure_thresholds[{predictor_name!r}]",
                payload,
                ser.failure_config_from_dict,
            )
        # expected_metrics: each entry is a dict with min / max
        # numeric fields.
        if not isinstance(self.expected_metrics, dict):
            raise CalibrationSetError("expected_metrics must be a dict")
        for metric, bounds in self.expected_metrics.items():
            if not isinstance(bounds, dict):
                raise CalibrationSetError(
                    f"expected_metrics[{metric!r}] must be a dict; got "
                    f"{type(bounds).__name__}"
                )
            if "min" not in bounds or "max" not in bounds:
                raise CalibrationSetError(
                    f"expected_metrics[{metric!r}] must have 'min' + "
                    "'max' keys"
                )
            try:
                lo = float(bounds["min"])
                hi = float(bounds["max"])
            except (TypeError, ValueError) as exc:
                raise CalibrationSetError(
                    f"expected_metrics[{metric!r}] min/max must be "
                    f"numeric: {exc}"
                ) from exc
            # Audit-fix Finding 3: NaN bounds used to slip past
            # ``lo > hi`` (NaN comparisons are all False) and
            # silently disable drift detection for the metric —
            # an observed value of any size against a NaN range
            # produces no alert. Reject loud at construction.
            if not math.isfinite(lo) or not math.isfinite(hi):
                raise CalibrationSetError(
                    f"expected_metrics[{metric!r}] min/max must be "
                    f"finite; got min={lo}, max={hi}. NaN / Inf bounds "
                    "would silently disable drift detection for the "
                    "metric."
                )
            if lo > hi:
                raise CalibrationSetError(
                    f"expected_metrics[{metric!r}] min ({lo}) must be ≤ "
                    f"max ({hi})"
                )
        if not isinstance(self.metadata, dict):
            raise CalibrationSetError(
                f"metadata must be a dict; got {type(self.metadata).__name__}"
            )

    # ----- digest / identity ----- #

    def computed_digest(self) -> str:
        """Compute the SHA-256 digest over this bundle's
        canonical JSON, *excluding* the ``digest`` field itself.

        Use this to verify integrity:
        ``bundle.computed_digest() == bundle.digest``."""
        payload = self._payload_without_digest()
        return _compute_digest(payload)

    def _payload_without_digest(self) -> Dict[str, Any]:
        return {
            "calibration_id": self.calibration_id,
            "kernel_version": self.kernel_version,
            "created_at": self.created_at,
            "bcvf_config": copy.deepcopy(self.bcvf_config),
            "consumer_v2_config": copy.deepcopy(self.consumer_v2_config),
            "bicycle_config": copy.deepcopy(self.bicycle_config),
            "realtime_budget": copy.deepcopy(self.realtime_budget),
            "dds_qos_profile": copy.deepcopy(self.dds_qos_profile),
            "safety_state_config": copy.deepcopy(self.safety_state_config),
            "per_predictor_failure_thresholds": copy.deepcopy(
                self.per_predictor_failure_thresholds
            ),
            "expected_metrics": copy.deepcopy(self.expected_metrics),
            "metadata": copy.deepcopy(self.metadata),
        }

    @property
    def matches_running_kernel(self) -> bool:
        """``True`` if ``self.kernel_version`` matches the live
        ``bcvf_autonomous.__version__``."""
        return self.kernel_version == _autonomy_version

    # ----- serialisation ----- #

    def to_dict(self) -> Dict[str, Any]:
        """Plain-dict view for JSON serialisation. Uses
        deepcopy on nested dicts so caller mutation can't leak
        back into the bundle's frozen state."""
        d = self._payload_without_digest()
        d["digest"] = self.digest
        return d

    @classmethod
    def from_dict(
        cls,
        payload: Dict[str, Any],
        *,
        verify_digest: bool = True,
        allow_version_drift: bool = False,
    ) -> "CalibrationSet":
        """Strict load. Missing fields, malformed configs, bad
        digest, bad kernel version all raise
        :class:`CalibrationSetError` (or subclass) at load time.

        Audit-fix Finding 2: the kernel-version check now fires
        from ``from_dict`` itself (gated by
        ``allow_version_drift``). Previously the check only ran
        in :func:`load_calibration_set` — an in-memory caller
        feeding a payload from HTTP / DB / IPC bypassed the
        version-drift detector entirely. Now the discipline is
        path-independent.

        Audit-fix Finding 3: ordering tightened — digest
        verification fires BEFORE the heavyweight embedded-
        config validation. A corrupted bundle short-circuits
        without paying full validation cost. Reduces a
        DoS-by-malformed-bundle surface a recall vault loading
        thousands of bundles would otherwise pay.
        """
        if not isinstance(payload, dict):
            raise CalibrationSetError(
                f"calibration payload must be a dict; got "
                f"{type(payload).__name__}"
            )
        missing = [f for f in _REQUIRED_FIELDS if f not in payload]
        if missing:
            raise CalibrationSetError(
                f"calibration bundle missing required fields: {missing}"
            )
        # Audit-fix Finding 3 (ordering): digest-first + version-
        # check-first, before paying the embedded-config validation
        # cost in CalibrationSet.__post_init__.
        recorded_digest = str(payload["digest"])
        recorded_kernel_version = str(payload["kernel_version"])
        if verify_digest:
            payload_no_digest = {
                k: copy.deepcopy(v) for k, v in payload.items()
                if k != "digest"
            }
            expected = _compute_digest(payload_no_digest)
            if recorded_digest != expected:
                raise CalibrationDigestError(
                    f"calibration digest mismatch: bundle records "
                    f"{recorded_digest!r}, recomputed {expected!r}. "
                    "Either the bundle was tampered with / hand-edited, "
                    "or the canonical-serialisation rules drifted "
                    "between record-time and load-time."
                )
        if (
            not allow_version_drift
            and recorded_kernel_version != _autonomy_version
        ):
            raise CalibrationVersionError(
                f"calibration kernel_version "
                f"{recorded_kernel_version!r} does not match running "
                f"bcvf_autonomous version {_autonomy_version!r}. Pass "
                "allow_version_drift=True if you've verified the "
                "kernel changes between record-time and load-time "
                "don't affect your tuning."
            )
        # Now construct, paying the embedded-config validation
        # cost. A bundle that survived the digest + version
        # checks above is at least structurally trusted.
        return cls(
            calibration_id=str(payload["calibration_id"]),
            kernel_version=recorded_kernel_version,
            created_at=str(payload["created_at"]),
            bcvf_config=copy.deepcopy(payload["bcvf_config"]),
            consumer_v2_config=copy.deepcopy(payload["consumer_v2_config"]),
            bicycle_config=copy.deepcopy(payload["bicycle_config"]),
            realtime_budget=copy.deepcopy(payload["realtime_budget"]),
            dds_qos_profile=copy.deepcopy(payload["dds_qos_profile"]),
            safety_state_config=copy.deepcopy(payload["safety_state_config"]),
            per_predictor_failure_thresholds=copy.deepcopy(
                payload["per_predictor_failure_thresholds"]
            ),
            expected_metrics=copy.deepcopy(payload["expected_metrics"]),
            metadata=copy.deepcopy(payload.get("metadata", {})),
            digest=recorded_digest,
        )


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #


def build_calibration_set(
    *,
    calibration_id: str,
    bcvf_config,
    consumer_v2_config,
    bicycle_config,
    realtime_budget,
    dds_qos_profile,
    safety_state_config,
    per_predictor_failure_thresholds: Optional[Dict[str, Any]] = None,
    expected_metrics: Optional[Dict[str, Dict[str, float]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    kernel_version: Optional[str] = None,
    created_at: Optional[str] = None,
) -> CalibrationSet:
    """Build a :class:`CalibrationSet` from in-memory config
    objects. Uses the per-config serialisation helpers; computes
    the digest after every other field is fixed.

    Args:
        calibration_id: caller identifier, e.g.
            ``"oem-X-fleet-A-v2"``.
        bcvf_config: a :class:`BCVFConfig` instance.
        consumer_v2_config: a :class:`ConsumerV2Config`.
        bicycle_config: a :class:`BicycleConfig`.
        realtime_budget: a :class:`RealTimeBudget`.
        dds_qos_profile: a :class:`DDSQoSProfile`.
        safety_state_config: a :class:`SafetyStateMachineConfig`.
        per_predictor_failure_thresholds: optional dict mapping
            predictor name → :class:`FailureConfig`. Empty dict
            if omitted.
        expected_metrics: optional dict mapping metric path →
            ``{"min": float, "max": float}``. Empty dict if
            omitted.
        metadata: optional free-form caller annotations.
        kernel_version: override; defaults to the live
            ``bcvf_autonomous.__version__``.
        created_at: ISO 8601 timestamp; defaults to UTC ``now``.
    """
    if kernel_version is None:
        kernel_version = _autonomy_version
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    failures_serialised: Dict[str, Dict[str, Any]] = {}
    if per_predictor_failure_thresholds:
        for name, cfg in per_predictor_failure_thresholds.items():
            failures_serialised[str(name)] = ser.failure_config_to_dict(cfg)
    # Audit-fix Finding 5: single-pass construction. The previous
    # implementation built the bundle TWICE (once with digest=""
    # to compute the canonical JSON, then again with the digest
    # set), which ran the embedded-config validation pass twice
    # per call. For a fleet operator generating thousands of
    # bundles this was 2x wasted work. Now we compute the digest
    # against a hand-rolled payload dict (matching
    # _payload_without_digest's shape), then construct the
    # final CalibrationSet exactly once.
    payload_no_digest = {
        "calibration_id": str(calibration_id),
        "kernel_version": str(kernel_version),
        "created_at": str(created_at),
        "bcvf_config": ser.bcvf_config_to_dict(bcvf_config),
        "consumer_v2_config": ser.consumer_v2_config_to_dict(consumer_v2_config),
        "bicycle_config": ser.bicycle_config_to_dict(bicycle_config),
        "realtime_budget": ser.realtime_budget_to_dict(realtime_budget),
        "dds_qos_profile": ser.dds_qos_profile_to_dict(dds_qos_profile),
        "safety_state_config": ser.safety_state_config_to_dict(safety_state_config),
        "per_predictor_failure_thresholds": failures_serialised,
        "expected_metrics": copy.deepcopy(expected_metrics or {}),
        "metadata": copy.deepcopy(metadata or {}),
    }
    # Audit-fix Finding 3 (companion): the canonical-JSON
    # serialisation has ``allow_nan=False``; non-finite values
    # anywhere in the bundle raise ``ValueError`` from json.
    # Wrap as CalibrationSetError so the framework's typed
    # error hierarchy stays consistent — same discipline
    # validate_config_dict applies to embedded-config gates.
    try:
        digest = _compute_digest(payload_no_digest)
    except ValueError as exc:
        raise CalibrationSetError(
            f"calibration bundle contains non-finite values "
            f"(NaN / Inf) that cannot be serialised to canonical "
            f"JSON: {exc}"
        ) from exc
    return CalibrationSet(
        calibration_id=payload_no_digest["calibration_id"],
        kernel_version=payload_no_digest["kernel_version"],
        created_at=payload_no_digest["created_at"],
        bcvf_config=payload_no_digest["bcvf_config"],
        consumer_v2_config=payload_no_digest["consumer_v2_config"],
        bicycle_config=payload_no_digest["bicycle_config"],
        realtime_budget=payload_no_digest["realtime_budget"],
        dds_qos_profile=payload_no_digest["dds_qos_profile"],
        safety_state_config=payload_no_digest["safety_state_config"],
        per_predictor_failure_thresholds=payload_no_digest[
            "per_predictor_failure_thresholds"
        ],
        expected_metrics=payload_no_digest["expected_metrics"],
        metadata=payload_no_digest["metadata"],
        digest=digest,
    )
