"""``replay_bundle`` + ``compare_replay`` — the bit-identity gate.

Two-layer API:

* :func:`compare_replay` is the pure comparator — takes a
  :class:`ReplayBundle` plus a freshly-reconstructed
  :class:`TrustShapedEpisodeRecord`, returns a typed
  :class:`ReplayResult` naming any per-field / per-step
  divergences.
* :func:`replay_bundle` is the convenience wrapper that takes a
  bundle plus a ``runner_factory`` callable and runs the full
  re-record + compare pipeline. Caller supplies the factory
  because re-inflating a ``RunConfig`` dict back into a real
  :class:`Runner` is integration-specific (the dict shape is
  whatever the caller's runner serialised — the replay
  framework doesn't impose one).

See ``REPLAY_FRAMEWORK_DESIGN.md`` §4 + §5 for the full design
of bit-identity + the divergence taxonomy.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

import numpy as np

from .._version import __version__ as _autonomy_version
from ..analysis.io import episode_record_from_dict
from ..trust_diagnostics import TrustShapedEpisodeRecord
from .bundle import ReplayBundle
from .errors import ReplayBundleError


@dataclass(frozen=True)
class ReplayResult:
    """The verdict of replaying one bundle.

    Fields:

    * ``bundle`` — the bundle that was replayed.
    * ``reconstructed_record`` — the freshly-recorded episode
      record from re-running the bundle's config.
    * ``matches_recorded`` — bit-identity verdict.
    * ``per_field_divergences`` — named fields that differ. E.g.
      ``"per_step_weights"``, ``"n_steps"``, ``"per_step_v2_state"``.
    * ``per_step_divergences`` — tick indices where any per-step
      array differs. Cross-references with
      ``per_field_divergences`` for "field X at tick T".
    * ``package_version_at_replay`` — the package version doing
      the replay (compare against ``bundle.package_version`` for
      a Class-A divergence pinpoint).
    """

    bundle: ReplayBundle
    reconstructed_record: TrustShapedEpisodeRecord
    matches_recorded: bool
    per_field_divergences: Tuple[str, ...]
    per_step_divergences: Tuple[int, ...]
    package_version_at_replay: str

    @property
    def package_version_drift(self) -> bool:
        """``True`` if the replay package version differs from the
        record-time package version. Class-A divergence indicator."""
        return self.bundle.package_version != self.package_version_at_replay


# Per-step array fields the comparator walks. Mirrors the keys
# in ``TrustShapedEpisodeRecord.to_dict()`` that are per-step
# arrays of shape ``(T,)`` or ``(T, M)``. Listed explicitly so a
# new per-step field added to ``TrustShapedEpisodeRecord`` fails
# this test loud (rather than silently skipping the new field
# in the comparator).
_PER_STEP_ARRAY_FIELDS: Tuple[str, ...] = (
    "per_step_weights",
    "per_step_costs",
    "per_step_residuals",
    "per_step_ema_mean",
    "per_step_ema_std",
    "per_step_bcvf_total",
    "per_step_deadband_active_count",
    "per_step_deadband_fired",
    "per_step_is_excluded",
    "per_step_gate_activations",
    "per_step_v2_signal",
    "per_step_consec_suspect",
    "per_step_consec_ok",
)

_SCALAR_FIELDS: Tuple[str, ...] = (
    "n_steps",
    "M",
    "exclusion_T",
)


def _arrays_equal(a: np.ndarray, b: np.ndarray) -> bool:
    """Bit-identity check for numpy arrays. Enforces shape, dtype,
    and value equality (NaN-positions matched via ``equal_nan=True``).

    Audit-fix Finding 2: ``np.array_equal`` alone is value-only
    — an int64 → int32 dtype flip with the same numeric values
    used to slip past undetected. Bit-identity is the framework's
    contract; a kernel commit changing a per-step array's dtype
    changes the bytes-on-disk and may change downstream
    arithmetic (int32 overflow, etc.). The dtype check surfaces
    the divergence loud, which is the §5 Class-A behaviour the
    framework promises.
    """
    if a.shape != b.shape:
        return False
    if a.dtype != b.dtype:
        return False
    return bool(np.array_equal(a, b, equal_nan=True))


def _per_step_divergence_indices(a: np.ndarray, b: np.ndarray) -> List[int]:
    """Indices along the first axis where ``a[i] != b[i]``.
    Defensive about shape mismatches: returns ``[-1]`` to flag
    "structural divergence — re-record".
    """
    if a.shape != b.shape:
        return [-1]
    if a.ndim == 0:
        return []
    # Per-tick comparison: for (T,) arrays, walk i; for (T, M)
    # arrays, reduce over axis 1.
    diff_mask = a != b
    # NaN handling: NaN != NaN is True under numpy; treat
    # NaN-at-same-position as equal (matches ``equal_nan=True``).
    nan_mask = np.isnan(a) & np.isnan(b) if a.dtype.kind == "f" else None
    if nan_mask is not None:
        diff_mask = diff_mask & ~nan_mask
    if diff_mask.ndim > 1:
        diff_mask = diff_mask.any(axis=tuple(range(1, diff_mask.ndim)))
    return [int(i) for i, flag in enumerate(diff_mask) if flag]


def compare_replay(
    bundle: ReplayBundle,
    reconstructed_record: TrustShapedEpisodeRecord,
) -> ReplayResult:
    """Compare a freshly-reconstructed
    :class:`TrustShapedEpisodeRecord` against a bundle's recorded
    record. Returns a :class:`ReplayResult` with field-level +
    tick-level divergence localisation.

    The comparison uses ``np.array_equal(equal_nan=True)`` for
    numeric arrays. Structural divergence (different shape, n_steps
    differs, M differs) lands in ``per_field_divergences`` with
    the offending field's name; it does NOT enumerate
    ``per_step_divergences`` since the per-step view is undefined
    when the shapes differ.
    """
    if not isinstance(reconstructed_record, TrustShapedEpisodeRecord):
        raise ReplayBundleError(
            "reconstructed_record must be a TrustShapedEpisodeRecord; "
            f"got {type(reconstructed_record).__name__}"
        )
    recorded = episode_record_from_dict(bundle.recorded_record)
    field_divergences: List[str] = []
    step_divergences_set: set = set()

    # ---- scalar fields ----
    for field_name in _SCALAR_FIELDS:
        recorded_v = getattr(recorded, field_name)
        replayed_v = getattr(reconstructed_record, field_name)
        if recorded_v != replayed_v:
            field_divergences.append(field_name)

    # ---- per-step array fields ----
    # If n_steps or M already differ, every per-step array will
    # diverge; flag the structural fields only and skip the
    # per-step walk to avoid noise.
    if recorded.n_steps != reconstructed_record.n_steps:
        # Already in field_divergences from the scalar pass.
        pass
    if recorded.M != reconstructed_record.M:
        # Already in field_divergences from the scalar pass.
        pass

    for field_name in _PER_STEP_ARRAY_FIELDS:
        a = getattr(recorded, field_name)
        b = getattr(reconstructed_record, field_name)
        if not _arrays_equal(a, b):
            field_divergences.append(field_name)
            for idx in _per_step_divergence_indices(a, b):
                if idx >= 0:
                    step_divergences_set.add(idx)

    # ---- per_step_v2_state — list of strings, not an ndarray ----
    if list(recorded.per_step_v2_state) != list(reconstructed_record.per_step_v2_state):
        field_divergences.append("per_step_v2_state")

    # ---- aggregation enum ----
    if recorded.aggregation != reconstructed_record.aggregation:
        field_divergences.append("aggregation")

    matches = not field_divergences
    return ReplayResult(
        bundle=bundle,
        reconstructed_record=reconstructed_record,
        matches_recorded=matches,
        per_field_divergences=tuple(field_divergences),
        per_step_divergences=tuple(sorted(step_divergences_set)),
        package_version_at_replay=str(_autonomy_version),
    )


def replay_bundle(
    bundle: ReplayBundle,
    runner_factory: Callable[[Dict[str, Any]], TrustShapedEpisodeRecord],
) -> ReplayResult:
    """Full-path replay: re-run the bundle's config via the
    caller-provided ``runner_factory``, then compare bit-identity.

    Args:
        bundle: the bundle to replay.
        runner_factory: callable taking the bundle's
            ``run_config`` dict + producing the freshly-recorded
            :class:`TrustShapedEpisodeRecord`. Caller supplies
            this because re-inflating a ``RunConfig`` dict back
            into a :class:`Runner` is integration-specific. A
            simple integrator typically wraps:

                def factory(run_config_dict):
                    cfg = my_runconfig_from_dict(run_config_dict)
                    runner = Runner(cfg)
                    runner.run()
                    return runner.trust_diagnostics

            The replay framework doesn't impose a serialisation
            because the runner's ``RunConfig`` carries
            integration-specific knobs (failure injection paths,
            scenario overrides, etc.) the framework can't
            reasonably round-trip in a generic way.
    """
    if not callable(runner_factory):
        raise ReplayBundleError(
            "runner_factory must be callable (run_config_dict) -> "
            "TrustShapedEpisodeRecord"
        )
    # Audit-fix Finding 3: deepcopy the run_config before handing
    # it to the factory. A factory that mutates its input (path
    # normalisation, default overrides) used to corrupt the
    # bundle's record-time view via shallow-copy aliasing.
    reconstructed = runner_factory(copy.deepcopy(bundle.run_config))
    if not isinstance(reconstructed, TrustShapedEpisodeRecord):
        raise ReplayBundleError(
            "runner_factory must return a TrustShapedEpisodeRecord; "
            f"got {type(reconstructed).__name__}"
        )
    return compare_replay(bundle, reconstructed)
