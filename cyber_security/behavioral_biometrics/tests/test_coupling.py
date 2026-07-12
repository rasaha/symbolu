"""Coupling candidates + matched controls (shuffle / context)."""

from __future__ import annotations

from cyber_security.behavioral_biometrics import coupling, features, synthetic


def _rec(gain=0.8, task=0.2, seed=1):
    s = synthetic.generate_session(participant="p", device="d", task_id="mixed_workflow",
                                   session_id="s", trial_id="t", seed=seed,
                                   coupling_user_gain=gain, coupling_task_gain=task)
    return coupling.extract(s)


def test_real_coupling_exceeds_shuffled_control():
    c = _rec(gain=1.0, task=0.0)
    assert c["coupling_available"] == 1.0
    assert c["xcorr_max_abs"] > c["xcorr_max_abs__shuf"]
    assert c["resid_vs_shuf"] > 0.0


def test_no_injected_coupling_small_residual():
    c = _rec(gain=0.0, task=0.0)
    # with no user coupling, real should not greatly exceed the shuffled control
    assert c["resid_vs_shuf"] < 0.3


def test_context_matched_control_present():
    c = _rec(gain=0.8, task=0.6)
    for stat in ("xcorr_max_abs", "correlogram_peak", "cca_mean_corr"):
        assert f"{stat}__ctxm" in c
        assert f"{stat}__shuf" in c


def test_coupling_view_selects_matched_slots():
    rec = {"coupling": _rec(gain=0.8)}
    real = coupling.coupling_view(rec, "real")
    shuf = coupling.coupling_view(rec, "shuf")
    assert set(real) == set(shuf)  # identical feature slots, different (control) values
    assert real["cpl.xcorr_max_abs"] >= shuf["cpl.xcorr_max_abs"]


def test_coupling_deterministic():
    a = _rec(gain=0.7, seed=5)
    b = _rec(gain=0.7, seed=5)
    assert a == b


def test_unavailable_when_single_modality():
    from cyber_security.behavioral_biometrics import schema
    events = [schema.new_event(seq=i + 1, modality="keyboard", type="key_down",
                               t_monotonic=i * 0.1, t_source=i * 0.1, t_receipt=i * 0.1,
                               payload={"key_class": "letter"}) for i in range(20)]
    c = coupling.extract({"session_meta": {"session_id": "s"}, "events": events})
    assert c["coupling_available"] == 0.0
