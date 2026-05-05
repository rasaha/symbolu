"""``ReplayBundle`` — the recall-investigator's recording artifact.

A :class:`ReplayBundle` ties together the configuration that
produced an episode + the per-tick output the runtime recorded.
A recall investigator opens one bundle, runs it through the
current code, and either confirms bit-identity (clean replay)
or surfaces a divergence localising a kernel diff.

The bundle is JSON-serialisable + strict on load — corrupt
artifacts fail loudly rather than silently producing wrong
replays. See ``REPLAY_FRAMEWORK_DESIGN.md`` for the full
design rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .._version import __version__ as _autonomy_version
from ..analysis.io import episode_record_from_dict
from ..trust_diagnostics import TrustShapedEpisodeRecord
from .errors import ReplayBundleError, ReplayBundleVersionError


#: Bundle-format schema version. Bumps when the on-disk JSON
#: shape changes in a non-backward-compatible way. The loader
#: rejects bundles whose ``bundle_version`` doesn't match.
BUNDLE_VERSION = "1.0"


_REQUIRED_FIELDS = (
    "bundle_version",
    "package_version",
    "recorded_at",
    "episode_id",
    "run_config",
    "recorded_record",
    "recorded_collision",
    "recorded_total_steps",
)


_SEMVER_PATTERN = re.compile(
    r"^\d+\.\d+\.\d+"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclass(frozen=True)
class ReplayBundle:
    """One recall-investigation bundle.

    Fields are populated at record time and pinned by tests.
    See ``REPLAY_FRAMEWORK_DESIGN.md`` §2 for the per-field
    rationale + auditor-facing description.
    """

    #: Schema version of the bundle format itself. Bumps when
    #: the on-disk JSON shape changes; loader rejects mismatches.
    bundle_version: str

    #: ``bcvf_autonomous.__version__`` at record time. Replay
    #: surfaces a version mismatch loud (Class-A divergence in
    #: the design doc's §5 taxonomy).
    package_version: str

    #: ISO 8601 timestamp of when the original episode ran.
    recorded_at: str

    #: Caller-provided identifier — typically vehicle ID + trip
    #: ID + timestamp.
    episode_id: str

    #: Full ``RunConfig`` serialised. The reconstructor rebuilds
    #: the runner from this dict + re-runs the episode.
    run_config: Dict[str, Any]

    #: The original ``TrustShapedEpisodeRecord.to_dict()`` output
    #: — what the field saw. Replay compares its reconstruction
    #: against this byte-by-byte.
    recorded_record: Dict[str, Any]

    #: Whether the original episode collided.
    recorded_collision: bool

    #: Number of ticks the original episode ran.
    recorded_total_steps: int

    #: Free-form caller annotations (vehicle ID, fleet,
    #: deployment partner, scenario classification, recall-case
    #: ID). Not interpreted by the framework.
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.bundle_version:
            raise ReplayBundleError("bundle_version must be non-empty")
        if not self.package_version:
            raise ReplayBundleError("package_version must be non-empty")
        if not _SEMVER_PATTERN.match(self.package_version):
            raise ReplayBundleError(
                f"package_version {self.package_version!r} is not a valid "
                "semver string — replay surface needs a structured "
                "version to compare across record / replay times"
            )
        if not self.episode_id:
            raise ReplayBundleError("episode_id must be non-empty")
        if not isinstance(self.run_config, dict):
            raise ReplayBundleError(
                f"run_config must be a dict; got {type(self.run_config).__name__}"
            )
        if not isinstance(self.recorded_record, dict):
            raise ReplayBundleError(
                f"recorded_record must be a dict; got "
                f"{type(self.recorded_record).__name__}"
            )
        if self.recorded_total_steps < 0:
            raise ReplayBundleError(
                f"recorded_total_steps must be ≥ 0; got "
                f"{self.recorded_total_steps}"
            )
        if not isinstance(self.metadata, dict):
            raise ReplayBundleError(
                f"metadata must be a dict; got "
                f"{type(self.metadata).__name__}"
            )
        # Validate the embedded record by parsing it through the
        # existing strict validator. A malformed record can't be
        # smuggled past this gate — the same discipline
        # ``analysis/io.py`` enforces.
        try:
            episode_record_from_dict(self.recorded_record)
        except (ValueError, KeyError, TypeError) as exc:
            raise ReplayBundleError(
                f"recorded_record fails validation: {exc}"
            ) from exc

    # ----- serialisation ----- #

    def to_dict(self) -> Dict[str, Any]:
        """Plain-dict view for JSON serialisation."""
        return {
            "bundle_version": self.bundle_version,
            "package_version": self.package_version,
            "recorded_at": self.recorded_at,
            "episode_id": self.episode_id,
            "run_config": dict(self.run_config),
            "recorded_record": dict(self.recorded_record),
            "recorded_collision": bool(self.recorded_collision),
            "recorded_total_steps": int(self.recorded_total_steps),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ReplayBundle":
        """Strict load. Missing fields, bad versions, malformed
        records all raise :class:`ReplayBundleError` at load
        time — corrupt artifacts fail loud rather than producing
        a silently-wrong replay."""
        if not isinstance(payload, dict):
            raise ReplayBundleError(
                f"replay bundle payload must be a dict; got "
                f"{type(payload).__name__}"
            )
        missing = [f for f in _REQUIRED_FIELDS if f not in payload]
        if missing:
            raise ReplayBundleError(
                f"replay bundle missing required fields: {missing}"
            )
        # Schema-version gate: a future bump must reject older
        # loaders rather than guess at the new shape.
        if payload["bundle_version"] != BUNDLE_VERSION:
            raise ReplayBundleVersionError(
                f"bundle_version {payload['bundle_version']!r} does not "
                f"match this loader's supported version {BUNDLE_VERSION!r}"
            )
        return cls(
            bundle_version=str(payload["bundle_version"]),
            package_version=str(payload["package_version"]),
            recorded_at=str(payload["recorded_at"]),
            episode_id=str(payload["episode_id"]),
            run_config=dict(payload["run_config"]),
            recorded_record=dict(payload["recorded_record"]),
            recorded_collision=bool(payload["recorded_collision"]),
            recorded_total_steps=int(payload["recorded_total_steps"]),
            metadata=dict(payload.get("metadata", {})),
        )

    @property
    def recorded_episode_record(self) -> TrustShapedEpisodeRecord:
        """Convenience: parse the embedded record dict to a
        :class:`TrustShapedEpisodeRecord`. Cached re-parsing — the
        validator runs once at construction time so this re-parse
        is just for caller convenience."""
        return episode_record_from_dict(self.recorded_record)


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #


def build_replay_bundle(
    *,
    run_config: Dict[str, Any],
    recorded_record: TrustShapedEpisodeRecord,
    episode_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    recorded_collision: bool = False,
    recorded_total_steps: Optional[int] = None,
    package_version: Optional[str] = None,
    recorded_at: Optional[str] = None,
) -> ReplayBundle:
    """Build a :class:`ReplayBundle` from in-memory components.

    Used both by the runner's end-of-episode capture path and by
    post-hoc bundle construction from a deployment partner's
    legacy JSON dumps.

    Args:
        run_config: ``RunConfig`` serialised as a dict (use
            ``runner._run_config_to_dict`` or equivalent — the
            framework doesn't impose a serialisation; any
            JSON-serialisable dict the reconstructor can re-
            inflate works).
        recorded_record: the in-memory
            :class:`TrustShapedEpisodeRecord` produced by the
            runner.
        episode_id: caller identifier — typically vehicle ID +
            trip ID + timestamp.
        metadata: optional free-form annotations.
        recorded_collision: original-episode collision flag.
        recorded_total_steps: original-episode tick count.
            Defaults to ``recorded_record.n_steps``.
        package_version: override for the package-version field;
            defaults to the package's installed version. Tests
            inject a fixed value for determinism.
        recorded_at: ISO 8601 timestamp; defaults to UTC ``now``.
    """
    if package_version is None:
        package_version = _autonomy_version
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc).isoformat()
    if recorded_total_steps is None:
        recorded_total_steps = int(recorded_record.n_steps)
    return ReplayBundle(
        bundle_version=BUNDLE_VERSION,
        package_version=str(package_version),
        recorded_at=str(recorded_at),
        episode_id=str(episode_id),
        run_config=dict(run_config),
        recorded_record=recorded_record.to_dict(),
        recorded_collision=bool(recorded_collision),
        recorded_total_steps=int(recorded_total_steps),
        metadata=dict(metadata or {}),
    )
