"""Behavioural tests for the replay / record-and-replay framework.

The framework is the §9-row-#3 industry-features-roadmap pick.
These tests pin the load-bearing contracts:

* :class:`ReplayBundle` round-trip is byte-identical (in-memory
  dict → JSON → dict → ReplayBundle).
* Strict load validation rejects missing fields, malformed
  records, bad versions.
* :func:`compare_replay` returns ``matches_recorded == True``
  on bit-identical input + correctly localises every per-field /
  per-step divergence on a perturbation.
* :func:`replay_bundle` runs a caller-supplied factory + applies
  the comparator.
* The bundle JSON is canonical (sorted keys, deterministic).
* Composition with the existing
  :class:`TrustShapedEpisodeRecord` validator (the bundle can't
  smuggle a malformed record past the gate).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.trust_diagnostics import (
    RolloutAggregation,
    TrustShapedEpisodeRecord,
)
from symbolu_robotics.bcvf_autonomous.replay import (
    BUNDLE_VERSION,
    ReplayBundle,
    ReplayBundleError,
    ReplayBundleVersionError,
    ReplayResult,
    build_replay_bundle,
    compare_replay,
    load_replay_bundle,
    render_replay_bundle_text,
    replay_bundle,
    save_replay_bundle,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_record(
    T: int = 5,
    M: int = 3,
    *,
    cost_value: float = 0.0,
) -> TrustShapedEpisodeRecord:
    """Build a fully-populated record that passes strict
    validation (every per-step array shape matches ``n_steps``)."""
    return TrustShapedEpisodeRecord(
        n_steps=T,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=np.full((T, M), 1.0 / M),
        per_step_costs=np.full((T, M), cost_value),
        per_step_residuals=np.zeros((T, M)),
        per_step_ema_mean=np.zeros((T, M)),
        per_step_ema_std=np.zeros((T, M)),
        per_step_bcvf_total=np.zeros(T),
        per_step_deadband_active_count=np.zeros(T, dtype=np.int64),
        per_step_deadband_fired=np.zeros(T, dtype=bool),
        per_step_is_excluded=np.zeros((T, M), dtype=bool),
        per_step_gate_activations=np.zeros(T, dtype=np.int64),
        per_step_v2_state=[""] * T,
        per_step_v2_signal=np.zeros(T),
        per_step_consec_suspect=np.zeros((T, M), dtype=np.int64),
        per_step_consec_ok=np.zeros((T, M), dtype=np.int64),
    )


def _build_bundle(record: TrustShapedEpisodeRecord = None, **kwargs) -> ReplayBundle:
    if record is None:
        record = _make_record()
    defaults = {
        "run_config": {"seed": 42, "scenario": "S1_normal_driving"},
        "recorded_record": record,
        "episode_id": "ep_test_1",
        "recorded_at": "2026-05-05T12:00:00+00:00",
        "package_version": "0.4.0",
    }
    defaults.update(kwargs)
    return build_replay_bundle(**defaults)


# --------------------------------------------------------------------------- #
# Bundle construction + validation
# --------------------------------------------------------------------------- #


def test_bundle_construction_with_valid_record_succeeds():
    bundle = _build_bundle()
    assert bundle.bundle_version == BUNDLE_VERSION
    assert bundle.package_version == "0.4.0"
    assert bundle.episode_id == "ep_test_1"


def test_bundle_construction_rejects_empty_episode_id():
    with pytest.raises(ReplayBundleError, match="episode_id"):
        _build_bundle(episode_id="")


def test_bundle_construction_rejects_non_semver_package_version():
    """package_version must be valid semver — replay surfaces a
    structured drift between record-time and replay-time."""
    with pytest.raises(ReplayBundleError, match="semver"):
        _build_bundle(package_version="not-a-version")


def test_bundle_construction_rejects_non_dict_run_config():
    record = _make_record()
    with pytest.raises(ReplayBundleError, match="run_config"):
        ReplayBundle(
            bundle_version=BUNDLE_VERSION,
            package_version="0.4.0",
            recorded_at="2026-05-05",
            episode_id="ep",
            run_config="not a dict",  # type: ignore[arg-type]
            recorded_record=record.to_dict(),
            recorded_collision=False,
            recorded_total_steps=5,
        )


def test_bundle_construction_rejects_negative_recorded_total_steps():
    record = _make_record()
    with pytest.raises(ReplayBundleError, match="recorded_total_steps"):
        ReplayBundle(
            bundle_version=BUNDLE_VERSION,
            package_version="0.4.0",
            recorded_at="2026-05-05",
            episode_id="ep",
            run_config={},
            recorded_record=record.to_dict(),
            recorded_collision=False,
            recorded_total_steps=-1,
        )


def test_bundle_construction_validates_embedded_record():
    """A malformed recorded_record can't be smuggled past the
    strict validator at construction time."""
    record_dict = _make_record().to_dict()
    # Corrupt: per_step_weights shape != (n_steps, M).
    record_dict["per_step_weights"] = [[1.0, 0.0, 0.0]]  # only one row, n_steps=5
    with pytest.raises(ReplayBundleError, match="recorded_record"):
        ReplayBundle(
            bundle_version=BUNDLE_VERSION,
            package_version="0.4.0",
            recorded_at="2026-05-05",
            episode_id="ep",
            run_config={},
            recorded_record=record_dict,
            recorded_collision=False,
            recorded_total_steps=5,
        )


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #


def test_bundle_to_dict_then_from_dict_round_trips():
    bundle = _build_bundle()
    d = bundle.to_dict()
    bundle2 = ReplayBundle.from_dict(d)
    assert bundle2.bundle_version == bundle.bundle_version
    assert bundle2.package_version == bundle.package_version
    assert bundle2.episode_id == bundle.episode_id
    assert bundle2.run_config == bundle.run_config
    assert bundle2.recorded_collision == bundle.recorded_collision


def test_bundle_dict_serialisation_is_json_compatible():
    bundle = _build_bundle()
    text = json.dumps(bundle.to_dict(), sort_keys=True)
    parsed = json.loads(text)
    bundle2 = ReplayBundle.from_dict(parsed)
    assert bundle2.episode_id == bundle.episode_id


def test_render_replay_bundle_text_uses_canonical_serialisation():
    bundle = _build_bundle()
    text = render_replay_bundle_text(bundle)
    assert text.endswith("\n")  # diff-friendly trailing newline
    parsed = json.loads(text)
    # Sorted keys → bundle_version comes before recorded_at.
    assert text.index('"bundle_version"') < text.index('"recorded_at"')


def test_render_replay_bundle_text_is_deterministic():
    bundle = _build_bundle()
    a = render_replay_bundle_text(bundle)
    b = render_replay_bundle_text(bundle)
    assert a == b


def test_save_and_load_replay_bundle_round_trips(tmp_path):
    bundle = _build_bundle()
    out = tmp_path / "bundle.json"
    save_replay_bundle(bundle, out)
    bundle2 = load_replay_bundle(out)
    assert bundle2.episode_id == bundle.episode_id
    assert bundle2.run_config == bundle.run_config


# --------------------------------------------------------------------------- #
# Strict load validation
# --------------------------------------------------------------------------- #


def test_load_rejects_missing_path(tmp_path):
    with pytest.raises(ReplayBundleError, match="not found"):
        load_replay_bundle(tmp_path / "does_not_exist.json")


def test_load_rejects_invalid_json(tmp_path):
    out = tmp_path / "bad.json"
    out.write_text("not { valid json", encoding="utf-8")
    with pytest.raises(ReplayBundleError, match="JSON"):
        load_replay_bundle(out)


def test_from_dict_rejects_non_dict_input():
    with pytest.raises(ReplayBundleError, match="dict"):
        ReplayBundle.from_dict([1, 2, 3])  # type: ignore[arg-type]


def test_from_dict_rejects_missing_required_fields():
    bundle = _build_bundle()
    payload = bundle.to_dict()
    del payload["episode_id"]
    with pytest.raises(ReplayBundleError, match="missing required fields"):
        ReplayBundle.from_dict(payload)


def test_from_dict_rejects_unsupported_bundle_version():
    bundle = _build_bundle()
    payload = bundle.to_dict()
    payload["bundle_version"] = "99.0"
    with pytest.raises(ReplayBundleVersionError, match="bundle_version"):
        ReplayBundle.from_dict(payload)


# --------------------------------------------------------------------------- #
# compare_replay — bit-identity gate
# --------------------------------------------------------------------------- #


def test_compare_replay_bit_identical_records_match():
    record = _make_record()
    bundle = _build_bundle(record=record)
    res = compare_replay(bundle, record)
    assert res.matches_recorded is True
    assert res.per_field_divergences == ()
    assert res.per_step_divergences == ()


def test_compare_replay_diverging_costs_localises_field():
    record_a = _make_record(cost_value=0.0)
    record_b = _make_record(cost_value=1.5)
    bundle = _build_bundle(record=record_a)
    res = compare_replay(bundle, record_b)
    assert res.matches_recorded is False
    assert "per_step_costs" in res.per_field_divergences
    # Every tick differs because every cost cell differs.
    assert res.per_step_divergences == tuple(range(5))


def test_compare_replay_diverging_at_single_tick_localises_index():
    record_a = _make_record()
    record_b = _make_record()
    record_b.per_step_costs[2, 1] = 99.0  # tick 2, predictor 1
    bundle = _build_bundle(record=record_a)
    res = compare_replay(bundle, record_b)
    assert res.matches_recorded is False
    assert "per_step_costs" in res.per_field_divergences
    assert res.per_step_divergences == (2,)


def test_compare_replay_diverging_n_steps_flags_structural_field():
    record_a = _make_record(T=5)
    record_b = _make_record(T=7)
    bundle = _build_bundle(record=record_a)
    res = compare_replay(bundle, record_b)
    assert res.matches_recorded is False
    assert "n_steps" in res.per_field_divergences


def test_compare_replay_diverging_v2_state_flags_field():
    record_a = _make_record()
    record_b = _make_record()
    record_b.per_step_v2_state = ["engaged"] * 5
    bundle = _build_bundle(record=record_a)
    res = compare_replay(bundle, record_b)
    assert res.matches_recorded is False
    assert "per_step_v2_state" in res.per_field_divergences


def test_compare_replay_rejects_non_record_input():
    bundle = _build_bundle()
    with pytest.raises(ReplayBundleError, match="TrustShapedEpisodeRecord"):
        compare_replay(bundle, "not a record")  # type: ignore[arg-type]


def test_compare_replay_result_carries_package_version_at_replay():
    """ReplayResult must report the replay-time package version
    so a Class-A divergence can be pinpointed against record-time."""
    bundle = _build_bundle()
    res = compare_replay(bundle, _make_record())
    assert res.package_version_at_replay
    # The version must parse as semver-ish.
    assert "." in res.package_version_at_replay


def test_compare_replay_result_flags_package_version_drift():
    bundle = _build_bundle(package_version="0.0.1")
    res = compare_replay(bundle, _make_record())
    # Replay-time version is the live autonomy version
    # (currently 0.4.0). Drift should be flagged.
    assert res.package_version_drift is True


def test_compare_replay_result_no_drift_on_matching_versions():
    """Building a bundle with the live autonomy version reports
    no version drift."""
    from symbolu_robotics.bcvf_autonomous._version import __version__
    bundle = _build_bundle(package_version=__version__)
    res = compare_replay(bundle, _make_record())
    assert res.package_version_drift is False


# --------------------------------------------------------------------------- #
# replay_bundle — full path with caller-supplied factory
# --------------------------------------------------------------------------- #


def test_replay_bundle_calls_factory_with_run_config_dict():
    bundle = _build_bundle()
    captured = {}

    def factory(run_config_dict):
        captured["cfg"] = run_config_dict
        return _make_record()

    replay_bundle(bundle, factory)
    assert captured["cfg"] == bundle.run_config


def test_replay_bundle_returns_match_when_factory_reproduces_record():
    record = _make_record()
    bundle = _build_bundle(record=record)
    res = replay_bundle(bundle, lambda cfg: record)
    assert res.matches_recorded is True


def test_replay_bundle_returns_divergence_when_factory_produces_different():
    bundle = _build_bundle(record=_make_record(cost_value=0.0))
    res = replay_bundle(bundle, lambda cfg: _make_record(cost_value=1.0))
    assert res.matches_recorded is False
    assert "per_step_costs" in res.per_field_divergences


def test_replay_bundle_rejects_non_callable_factory():
    bundle = _build_bundle()
    with pytest.raises(ReplayBundleError, match="callable"):
        replay_bundle(bundle, "not callable")  # type: ignore[arg-type]


def test_replay_bundle_rejects_factory_returning_non_record():
    bundle = _build_bundle()
    with pytest.raises(ReplayBundleError, match="TrustShapedEpisodeRecord"):
        replay_bundle(bundle, lambda cfg: {"not": "a record"})


# --------------------------------------------------------------------------- #
# build_replay_bundle factory
# --------------------------------------------------------------------------- #


def test_build_replay_bundle_uses_record_n_steps_when_total_steps_omitted():
    record = _make_record(T=12)
    bundle = build_replay_bundle(
        run_config={},
        recorded_record=record,
        episode_id="ep",
    )
    assert bundle.recorded_total_steps == 12


def test_build_replay_bundle_resolves_package_version_from_module():
    """Default package_version should come from the live autonomy
    __version__ — a contributor bumping the version automatically
    bumps the bundle's record-time field."""
    from symbolu_robotics.bcvf_autonomous._version import __version__
    bundle = build_replay_bundle(
        run_config={},
        recorded_record=_make_record(),
        episode_id="ep",
    )
    assert bundle.package_version == __version__


def test_build_replay_bundle_resolves_recorded_at_from_clock():
    """Default recorded_at should be a non-empty ISO 8601 string."""
    bundle = build_replay_bundle(
        run_config={},
        recorded_record=_make_record(),
        episode_id="ep",
    )
    assert bundle.recorded_at
    # ISO 8601 should contain a T separator (date + time).
    assert "T" in bundle.recorded_at


# --------------------------------------------------------------------------- #
# recorded_episode_record convenience
# --------------------------------------------------------------------------- #


def test_recorded_episode_record_property_returns_typed_record():
    record = _make_record()
    bundle = _build_bundle(record=record)
    parsed = bundle.recorded_episode_record
    assert isinstance(parsed, TrustShapedEpisodeRecord)
    assert parsed.n_steps == record.n_steps
    assert parsed.M == record.M


# --------------------------------------------------------------------------- #
# Composition with TrustShapedEpisodeRecord validator
# --------------------------------------------------------------------------- #


def test_bundle_validation_uses_episode_record_from_dict_validator():
    """A perturbation that the existing episode_record_from_dict
    rejects must also fail bundle construction — the bundle
    cannot smuggle a malformed record past the validator."""
    record_dict = _make_record().to_dict()
    del record_dict["per_step_weights"]  # missing required key
    with pytest.raises(ReplayBundleError):
        ReplayBundle(
            bundle_version=BUNDLE_VERSION,
            package_version="0.4.0",
            recorded_at="2026-05-05",
            episode_id="ep",
            run_config={},
            recorded_record=record_dict,
            recorded_collision=False,
            recorded_total_steps=5,
        )
