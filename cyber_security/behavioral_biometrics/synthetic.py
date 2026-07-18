"""Synthetic session generators — SYNTHETIC_TEST_ONLY.

For software testing, pipeline validation, failure-mode fixtures, and reproducibility
ONLY. Every session is stamped ``data_provenance = SYNTHETIC_TEST_ONLY`` so the
verdict layer refuses to emit any positive identity/coupling claim from it.

The generator has explicit, deterministic knobs for a per-user marginal offset, a
device offset, task/context-induced coupling, and user-specific cross-modal coupling,
so the analysis code can be exercised against known ground truth. NONE of this is a
biometric claim — it is a test oscillator with a known answer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics import schema
from cyber_security.behavioral_biometrics.version import COLLECTOR_VERSION, SYNTHETIC_MARKER

_KEY_MIX = (["letter"] * 12 + ["space"] * 3 + ["backspace"] * 1 + ["punctuation"] * 1)


def _seed(*parts) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]
    return int(h, 16)


@dataclass
class UserProfile:
    dwell_mu: float
    flight_mu: float
    base_speed: float
    curviness: float
    coupling_user_gain: float
    user_lag_s: float


def profile_for(participant: str, base_seed: int, user_scale: float,
                coupling_user_gain: float) -> UserProfile:
    rng = np.random.default_rng(_seed(base_seed, "user", participant))
    return UserProfile(
        dwell_mu=0.09 + user_scale * rng.normal(0, 0.02),
        flight_mu=0.16 + user_scale * rng.normal(0, 0.04),
        base_speed=0.9 + user_scale * rng.normal(0, 0.25),
        curviness=0.5 + user_scale * abs(rng.normal(0, 0.3)),
        coupling_user_gain=coupling_user_gain * (0.5 + abs(rng.normal(0, 0.5))),
        user_lag_s=0.05 + 0.15 * rng.random(),
    )


def generate_session(*, participant: str, device: str, task_id: str, session_id: str,
                     trial_id: str, seed: int, role: str = "verification",
                     condition: str = "genuine", day: int = 0,
                     user_scale: float = 1.0, device_scale: float = 0.3,
                     coupling_user_gain: float = 0.0, coupling_task_gain: float = 0.0,
                     n_keys: int = 160, duration: float = 32.0,
                     jitter_s: float = 0.0, drop_rate: float = 0.0,
                     device_bound: bool = False) -> Dict[str, Any]:
    """Generate ONE synthetic multimodal session with known ground truth."""
    rng = np.random.default_rng(_seed(seed, participant, device, session_id))
    prof = profile_for(participant, seed, user_scale, coupling_user_gain)
    dev_off = np.random.default_rng(_seed(seed, "dev", device)).normal(0, device_scale)
    # device-bound: user marginal is swamped by a device*user interaction term
    dwell_mu = prof.dwell_mu + (dev_off if device_bound else 0.3 * dev_off)
    flight_mu = prof.flight_mu + (0.5 * dev_off if device_bound else 0.1 * dev_off)
    base_speed = max(0.2, prof.base_speed + 0.4 * dev_off)

    events: List[Dict[str, Any]] = []
    seq = [0]

    def add(modality, typ, t_source, payload, stage):
        if drop_rate and rng.random() < drop_rate:
            return
        jt = float(rng.normal(0, jitter_s)) if jitter_s else 0.0
        t = float(t_source + jt)
        seq[0] += 1
        ctx = schema.default_context()
        ctx.update({"task_stage": stage, "active_region": "field_1",
                    "screen_id": "task", "expected_interaction": modality})
        events.append(schema.new_event(
            seq=seq[0], modality=modality, type=typ, t_monotonic=t, t_source=t,
            t_receipt=t + 0.001, t_wall="", clock_domain="synthetic",
            sampling_interval=None, payload=payload, context=ctx))

    # --- keyboard stream ---
    t = 0.5
    kbd_times = []
    stage_seq = ["warmup", "type", "type", "review"]
    for i in range(n_keys):
        stage = stage_seq[min(len(stage_seq) - 1, int(t / duration * len(stage_seq)))]
        flight = float(max(0.03, rng.lognormal(np.log(max(0.05, flight_mu)), 0.35)))
        t += flight
        if t > duration:
            break
        dwell = float(max(0.02, rng.lognormal(np.log(max(0.03, dwell_mu)), 0.3)))
        kc = _KEY_MIX[int(rng.integers(0, len(_KEY_MIX)))]
        kid = f"k:{kc}:{int(rng.integers(0, 26)):02d}" if kc in ("letter", "punctuation") else f"k:{kc}"
        add("keyboard", "key_down", t, {"key_class": kc, "key_id": kid}, stage)
        add("keyboard", "key_up", t + dwell, {"key_class": kc, "key_id": kid}, stage)
        kbd_times.append(t)

    # --- keyboard rate signal for coupling ---
    grid = np.linspace(0, duration, max(64, int(duration * 20)))
    rate = np.zeros_like(grid)
    for kt in kbd_times:
        rate += np.exp(-0.5 * ((grid - kt) / 0.1) ** 2)
    rate_z = (rate - rate.mean()) / (rate.std() + 1e-9)

    # --- pointer stream, speed modulated by (user-lagged) keyboard rate + task ---
    # realistic ~50 Hz pointer sampling
    px, py = 0.5, 0.5
    n_moves = int(duration * 50)
    for i in range(n_moves):
        tm = (i + 1) / n_moves * duration
        stage = stage_seq[min(len(stage_seq) - 1, int(tm / duration * len(stage_seq)))]
        lag_idx = np.searchsorted(grid, tm - prof.user_lag_s)
        lag_idx = min(max(lag_idx, 0), len(rate_z) - 1)
        task_mod = coupling_task_gain * (1.0 if stage == "type" else -0.5)
        user_mod = prof.coupling_user_gain * rate_z[lag_idx]
        speed = max(0.01, base_speed * (1.0 + user_mod + task_mod) + rng.normal(0, 0.15))
        ang = rng.normal(0, prof.curviness)
        px = float(np.clip(px + speed * 0.02 * np.cos(ang), 0, 1))
        py = float(np.clip(py + speed * 0.02 * np.sin(ang), 0, 1))
        add("pointer", "move", tm, {"x": px, "y": py, "speed": speed}, stage)
        if i % 20 == 19:
            add("pointer", "button_down", tm + 0.001, {"x": px, "y": py, "button": "left"}, stage)
            add("pointer", "button_up", tm + 0.09, {"x": px, "y": py, "button": "left"}, stage)

    events.sort(key=lambda e: e["t_source"])
    for i, e in enumerate(events):
        e["seq"] = i + 1

    meta = schema.SessionMeta(
        participant_pseudonym=participant, session_id=session_id, task_id=task_id,
        trial_id=trial_id, device_id=device, device_class="laptop", os="synthetic",
        app_version="synthetic", collector_version=COLLECTOR_VERSION,
        session_start=f"2026-01-0{max(1, day + 1)}T09:00:00", role=role, condition=condition,
        data_provenance=SYNTHETIC_MARKER,
        consent={"granted": True, "purpose": "synthetic_test", "revoked": False},
        notes=f"SYNTHETIC_TEST_ONLY day={day}")
    return {"session_meta": meta.to_dict(), "events": events,
            "collector_stats": {"dropped": 0, "emitted": len(events)}}


def generate_cohort(*, n_participants: int = 12, sessions_per: int = 4, seed: int = 20260712,
                    coupling_user_gain: float = 0.0, coupling_task_gain: float = 0.0,
                    device_bound: bool = False, second_device: bool = False,
                    user_scale: float = 1.0) -> List[Dict[str, Any]]:
    """A synthetic pilot cohort with genuine + same-task live-impostor trials across
    >=2 days. Ground-truth participant is the pseudonym. SYNTHETIC_TEST_ONLY."""
    sessions: List[Dict[str, Any]] = []
    participants = [f"synthP{ i:02d}" for i in range(n_participants)]
    for pi, p in enumerate(participants):
        device = f"dev_{pi:02d}_a"
        for s in range(sessions_per):
            day = 0 if s < sessions_per // 2 else 1
            role = "enrollment" if s == 0 else "verification"
            sessions.append(generate_session(
                participant=p, device=device, task_id="mixed_workflow",
                session_id=f"{p}_s{s}", trial_id=f"{p}_t{s}", seed=seed, role=role,
                condition="genuine", day=day, user_scale=user_scale,
                coupling_user_gain=coupling_user_gain, coupling_task_gain=coupling_task_gain,
                device_bound=device_bound))
        # same-task, same-device live impostor: a DIFFERENT actor's behavior, on the
        # target's device, labeled with the TARGET identity it is attacking.
        impostor = participants[(pi + 1) % n_participants]
        imp = generate_session(
            participant=impostor, device=device, task_id="mixed_workflow",
            session_id=f"{p}_imp", trial_id=f"{p}_imp", seed=seed, role="verification",
            condition="live_impostor", day=1, user_scale=user_scale,
            coupling_user_gain=coupling_user_gain, coupling_task_gain=coupling_task_gain,
            device_bound=device_bound)
        imp["session_meta"]["participant_pseudonym"] = p          # claimed (target) identity
        imp["session_meta"]["notes"] += f" impostor_actor={impostor}"
        sessions.append(imp)
        if second_device:
            sessions.append(generate_session(
                participant=p, device=f"dev_{pi:02d}_b", task_id="mixed_workflow",
                session_id=f"{p}_dev2", trial_id=f"{p}_dev2", seed=seed, role="verification",
                condition="genuine", day=1, user_scale=user_scale,
                coupling_user_gain=coupling_user_gain, coupling_task_gain=coupling_task_gain,
                device_bound=device_bound))
    return sessions
