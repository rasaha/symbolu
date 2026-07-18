"""Executable demonstrations (14). Run:

    python -m cyber_security.behavioral_biometrics.demos.demo

Each demo prints a compact, machine-readable result. No raw input is ever printed
(keyboard is class-only by construction). All identity/coupling numbers here are on
SYNTHETIC_TEST_ONLY data and carry NO biometric claim.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from cyber_security.behavioral_biometrics import (
    analysis,
    collector,
    coupling,
    features,
    pilot,
    privacy,
    quality,
    schema,
    splits,
    synthetic,
    tasks,
    verdicts,
)


class _Clk:
    def __init__(self):
        self.t = 0.0

    def mono(self):
        self.t += 0.0005
        return self.t


def _collector():
    return collector.Collector(collector.CollectorClock(monotonic=_Clk().mono,
                                                        wall_iso=lambda: "2026-01-01T09:00:00"))


def _drive_keyboard(col, keys, t0=0.5, flight=0.14, dwell=0.08, context=None):
    t = t0
    for k in keys:
        col.ingest(modality="keyboard", type="key_down", t_source=t, t_monotonic=t,
                   raw_key=k, context=context)
        col.ingest(modality="keyboard", type="key_up", t_source=t + dwell, t_monotonic=t + dwell,
                   raw_key=k, context=context)
        t += flight
    return t


def _drive_pointer(col, n, t0, dt=0.02, context=None):
    x, y, t = 0.5, 0.5, t0
    for i in range(n):
        x = min(1.0, max(0.0, x + 0.01))
        y = min(1.0, max(0.0, y + 0.005))
        col.ingest(modality="pointer", type="move", t_source=t, t_monotonic=t,
                   payload={"x": x, "y": y}, context=context)
        t += dt
    return t


# ---- 1-3: record sessions through the real collector ----

def demo_01_fixed_copy() -> Dict[str, Any]:
    col = _collector()
    col.start_session(participant_pseudonym="p_demo", task_id="fixed_copy", trial_id="t1",
                      device_id="dev1")
    _drive_keyboard(col, list("the quick brown fox") * 8, context={"task_stage": "type"})
    s = col.stop_session()
    return {"demo": "01_fixed_copy_typing", "valid": schema.is_valid(s),
            "n_events": len(s["events"]), "raw_leaks": privacy.find_raw_content_leaks(s),
            "first_kbd_payload": s["events"][0]["payload"]}


def demo_02_pointer() -> Dict[str, Any]:
    col = _collector()
    col.start_session(participant_pseudonym="p_demo", task_id="point_click", trial_id="t2",
                      device_id="dev1")
    _drive_pointer(col, 400, 0.5, context={"task_stage": "acquire"})
    s = col.stop_session()
    return {"demo": "02_pointer_task", "valid": schema.is_valid(s), "n_events": len(s["events"])}


def demo_03_mixed() -> Dict[str, Any]:
    col = _collector()
    col.start_session(participant_pseudonym="p_demo", task_id="mixed_workflow", trial_id="t3",
                      device_id="dev1")
    t = _drive_keyboard(col, list("field one") * 6, context={"task_stage": "type"})
    _drive_pointer(col, 200, t, context={"task_stage": "point"})
    s = col.stop_session()
    mods = sorted({e["modality"] for e in s["events"]})
    return {"demo": "03_mixed_kbd_pointer", "valid": schema.is_valid(s), "modalities": mods}


# ---- 4: suppress a sensitive field ----

def demo_04_suppress_sensitive() -> Dict[str, Any]:
    col = _collector()
    pol = privacy.PrivacyPolicy(suppressed_regions={"password"})
    col.start_session(participant_pseudonym="p_demo", task_id="fixed_copy", trial_id="t4",
                      device_id="dev1", policy=pol)
    _drive_keyboard(col, list("public"), context={"task_stage": "type", "active_region": "public"})
    _drive_keyboard(col, list("secret"), t0=5.0,
                    context={"task_stage": "type", "active_region": "password"})
    s = col.stop_session()
    sens = [e for e in s["events"] if e["context"]["active_region"] == "password"]
    return {"demo": "04_suppress_sensitive_field",
            "sensitive_events_have_no_key_id": all("key_id" not in e["payload"] for e in sens),
            "sensitive_region_marked": all(e["payload"].get("region") == "SUPPRESSED" for e in sens),
            "raw_leaks": privacy.find_raw_content_leaks(s)}


# ---- 5: detect missing / reordered events ----

def demo_05_missing_reordered() -> Dict[str, Any]:
    s = synthetic.generate_session(participant="p_demo", device="dev1", task_id="mixed_workflow",
                                   session_id="s5", trial_id="t5", seed=5)
    n = len(s["events"])
    clean = quality.analyze(s)
    # corrupt: reorder ~8% of adjacent pairs and report a heavy drop rate
    ev = s["events"]
    for i in range(0, int(n * 0.16), 2):
        ev[i], ev[i + 1] = ev[i + 1], ev[i]
    s["collector_stats"]["dropped"] = int(n * 0.15)
    q = quality.analyze(s)
    return {"demo": "05_detect_missing_reordered",
            "clean_verdict": clean["verdict"], "corrupted_verdict": q["verdict"],
            "reorder_rate": round(q["metrics"]["reorder_rate"], 4),
            "drop_rate": round(q["metrics"]["drop_rate"], 4),
            "detected_reasons": q["reasons"]}


# ---- 6: detect excessive jitter ----

def demo_06_jitter() -> Dict[str, Any]:
    clean = quality.analyze(synthetic.generate_session(
        participant="p", device="d", task_id="t", session_id="c6", trial_id="t", seed=6))
    jittery = quality.analyze(synthetic.generate_session(
        participant="p", device="d", task_id="t", session_id="j6", trial_id="t", seed=6,
        jitter_s=0.05))
    return {"demo": "06_detect_jitter", "clean_verdict": clean["verdict"],
            "clean_jitter_ms": round(clean["metrics"]["jitter_ms"], 2),
            "jittery_verdict": jittery["verdict"],
            "jittery_jitter_ms": round(jittery["metrics"]["jitter_ms"], 2)}


# ---- 7-8: deterministic feature extraction ----

def demo_07_08_deterministic_features() -> Dict[str, Any]:
    s = synthetic.generate_session(participant="p", device="d", task_id="mixed_workflow",
                                   session_id="s7", trial_id="t", seed=7, coupling_user_gain=0.5)
    r1, r2 = features.extract(s), features.extract(s)
    kbd_same = r1["marginal"] == r2["marginal"] and any(k.startswith("kbd.") for k in r1["marginal"])
    ptr_same = any(k.startswith("ptr.") for k in r1["marginal"])
    return {"demo": "07_08_deterministic_features", "keyboard_reproducible": bool(kbd_same),
            "pointer_features_present": bool(ptr_same),
            "kbd.dwell.mean": round(r1["marginal"].get("kbd.dwell.mean", 0), 5),
            "ptr.vel.mean": round(r1["marginal"].get("ptr.vel.mean", 0), 5)}


# ---- 9-10: context-aligned coupling + shuffled controls ----

def demo_09_10_coupling_controls() -> Dict[str, Any]:
    s = synthetic.generate_session(participant="p", device="d", task_id="mixed_workflow",
                                   session_id="s9", trial_id="t", seed=9, coupling_user_gain=0.8,
                                   coupling_task_gain=0.3)
    c = coupling.extract(s)
    return {"demo": "09_10_coupling_and_controls",
            "real_xcorr": round(c["xcorr_max_abs"], 3),
            "shuffled_xcorr": round(c["xcorr_max_abs__shuf"], 3),
            "context_matched_xcorr": round(c["xcorr_max_abs__ctxm"], 3),
            "resid_vs_shuffled": round(c["resid_vs_shuf"], 3),
            "resid_vs_context": round(c["resid_vs_ctxm"], 3),
            "note": "real should exceed shuffled; residual-vs-context isolates user-specificity"}


# ---- 11: leakage-safe splits ----

def demo_11_splits() -> Dict[str, Any]:
    coh = synthetic.generate_cohort(n_participants=10, sessions_per=4, second_device=True)
    recs = [features.extract(x) for x in coh]
    out = {}
    for name, fn in (("session_disjoint", splits.session_disjoint),
                     ("live_impostor_only", splits.live_impostor_only),
                     ("device_instance", splits.device_instance),
                     ("participant_disjoint", splits.participant_disjoint)):
        plan = fn(recs)
        out[name] = {"leakage_violations": splits.check_leakage(plan, recs),
                     "n_test_rows": len(plan.labeled_test())}
    return {"demo": "11_leakage_safe_splits", "splits": out}


# ---- 12: train/evaluate marginal baseline ----

def demo_12_baseline() -> Dict[str, Any]:
    coh = synthetic.generate_cohort(n_participants=12, sessions_per=4)
    recs = [features.extract(x) for x in coh]
    plan = splits.session_disjoint(recs, seed=1)
    C = analysis.marginal_identity(recs, plan)
    return {"demo": "12_marginal_baseline_on_synthetic", "auc_point": round(C["auc"]["point"], 3),
            "auc_ci": [round(C["auc"]["lo"], 3), round(C["auc"]["hi"], 3)],
            "note": "SYNTHETIC_TEST_ONLY — not a biometric result"}


# ---- 13: refuse positive verdict from synthetic ----

def demo_13_refuse_synthetic() -> Dict[str, Any]:
    coh = synthetic.generate_cohort(n_participants=12, sessions_per=4, coupling_user_gain=0.6)
    recs = [features.extract(x) for x in coh]
    qs = [dict(quality.analyze(s), participant=s["session_meta"]["participant_pseudonym"]) for s in coh]
    plan = splits.session_disjoint(recs, seed=1)
    C = analysis.marginal_identity(recs, plan)
    D = analysis.coupling_residual(recs, plan)
    mv = verdicts.marginal_signal_verdict(recs, C, qs)
    cv = verdicts.coupling_verdict(recs, D, None, qs)
    return {"demo": "13_refuse_positive_from_synthetic",
            "marginal_verdict": mv["verdict"], "coupling_verdict": cv["verdict"],
            "refused": mv["verdict"].endswith("SYNTHETIC_NO_VERDICT")
                       and cv["verdict"].endswith("SYNTHETIC_NO_VERDICT")}


# ---- 14: pilot-quality report ----

def demo_14_pilot_report() -> Dict[str, Any]:
    coh = synthetic.generate_cohort(n_participants=12, sessions_per=4, coupling_user_gain=0.5,
                                    second_device=True)
    report = pilot.run_pilot(coh)
    return {"demo": "14_pilot_report", "summary": pilot.summary_lines(report),
            "instrumentation": report["instrumentation_verdict"]["verdict"],
            "marginal_verdict": report["marginal_signal_verdict"]["verdict"],
            "coupling_verdict": report["coupling_verdict"]["verdict"]}


DEMOS = [demo_01_fixed_copy, demo_02_pointer, demo_03_mixed, demo_04_suppress_sensitive,
         demo_05_missing_reordered, demo_06_jitter, demo_07_08_deterministic_features,
         demo_09_10_coupling_controls, demo_11_splits, demo_12_baseline,
         demo_13_refuse_synthetic, demo_14_pilot_report]


def main() -> int:
    results: List[Dict[str, Any]] = []
    for fn in DEMOS:
        results.append(fn())
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
