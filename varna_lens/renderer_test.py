#!/usr/bin/env python3
"""Tests for ASG Reflection Renderer v2 (asg_renderer.py).

Verifies the renderer is deterministic, honest, and read-only with respect to the engine:
  1. trajectory roles are deterministic (stable across runs)
  2. ⤳ is the ONLY source of transformation/easing language (essence_line)
  3. the deterministic chain is always present
  4. forbidden truth-claim words never appear (all modes)
  5. the renderer does not alter engine output
  6. river and kill match their expected role structure

Run: python renderer_test.py   (non-zero exit on any failure)
"""
import sys

import varna_lens as V
import asg_renderer as R


def _check(cond, msg, fails):
    if not cond:
        fails.append(msg)
    return cond


def main():
    fails = []

    # 6 + 1: river/kill role structure, and determinism (run twice)
    expected = {"river": ["SOURCE", "INTEGRATION", "INTEGRATION", "RESOLUTION"],
                "kill": ["SOURCE", "INTEGRATION", "RESOLUTION"]}
    for w, exp in expected.items():
        t1 = R.trajectory(w)["trajectory"]
        t2 = R.trajectory(w)["trajectory"]
        _check(t1 == exp, f"role structure {w}: got {t1}, expected {exp}", fails)
        _check(t1 == t2, f"roles not deterministic for {w}: {t1} vs {t2}", fails)

    # 2: ⤳ is the only source of transformation/easing language (essence_line)
    for w in ["river", "kill", "eva", "compassion", "freedom"]:
        traj = R.trajectory(w)
        has_transform_beat = any(s["transform"] for s in traj["stages"])
        line = R.render(w, mode="essence_line")["layer3_reflection"].lower()
        has_easing = any(m in line for m in R.EASING_MARKERS)
        _check(has_easing == has_transform_beat,
               f"easing/⤳ mismatch for {w}: easing={has_easing} transform_beat={has_transform_beat}", fails)
    # explicit zero-⤳ control
    eva = R.trajectory("eva")
    _check(not any(s["transform"] for s in eva["stages"]), "eva unexpectedly has a ⤳ beat", fails)
    eva_line = R.render("eva", mode="essence_line")["layer3_reflection"].lower()
    _check(not any(m in eva_line for m in R.EASING_MARKERS),
           f"eva (no ⤳) produced easing language: {eva_line!r}", fails)

    # 3 + 4: chain always present; forbidden words never appear (all modes, several words)
    for w in ["river", "kill", "xozence", "cognade", "temple", "wife"]:
        for m in R.MODES:
            res = R.render(w, mode=m)
            _check(bool(res["layer1_engine"]["chain"]), f"missing deterministic chain: {w}/{m}", fails)
            txt = R.format_text(res)
            _check(res["layer1_engine"]["chain"] in txt, f"chain not surfaced in output: {w}/{m}", fails)
            v = R.honesty_violations(res["layer3_reflection"])
            _check(not v, f"forbidden words {v} in {w}/{m}: {res['layer3_reflection']!r}", fails)
            _check(res["honesty_ok"], f"honesty_ok false for {w}/{m}", fails)

    # 5: renderer does not alter engine output
    snap_before = {w: V.analyze(w, model="op", hybrid=True)[0]["essence_short"]
                   for w in ["river", "kill", "temple", "compassion"]}
    for w in snap_before:
        for m in R.MODES:
            R.render(w, mode=m)
    snap_after = {w: V.analyze(w, model="op", hybrid=True)[0]["essence_short"] for w in snap_before}
    _check(snap_before == snap_after, "renderer altered engine output", fails)

    # single-metaphor: only the controlling element's bank is used
    for w in ["river", "kill", "temple"]:
        traj = R.trajectory(w)
        ctrl = traj["controlling_element"]
        imgs = R._images(traj["stages"], ctrl)
        bank = set(R.ELEMENT_IMAGE[ctrl].values())
        _check(all(i in bank for i in imgs), f"mixed-metaphor leak for {w} (ctrl={ctrl})", fails)

    print(f"renderer_test: {'PASS' if not fails else 'FAIL'} "
          f"({len(fails)} failure(s))")
    for f in fails:
        print("  [FAIL]", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
