"""BCVF Autonomous — Lemma 1 invariance demo.

Phase 3's success gate (§3C.13) and Phase 4's acceptance criterion
(§4C.13) both call out **Lemma 1 invariance** as the structural claim
that differentiates second-order BCVF from zeroth-order heuristics:

    "S5 (constant bias): BCVF (A3) shows near-zero cost; 0th-order (A1)
     shows elevated cost — the Lemma 1 invariance is visible in the table"

The V1 planner's closed-loop architecture (§3B.5) uses ``anchor=M1`` for
J_perf. With M1 always reliable, failures on M2/M3/M4 never mislead the
planned path, so the collision-rate A0-vs-A3 contrast that §4C.13 gate 2
anticipates is **not producible** without a planner rework (V2 work). The
signal-level contrast, however, **is** producible — and is exactly what
Lemma 1 predicts.

This demo measures J_BCVF directly on the predictor rollout ensemble for
three canonical scenarios and three cost orders, then prints the
diagnostic table that a Phase 4 ablation table row would contain.

Run:
    python -m symbolu_robotics.bcvf_autonomous.demos.lemma1_invariance
"""

from __future__ import annotations

import numpy as np

from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig,
    CostOrder,
    FailureConfig,
    compute_bcvf_cost,
    create_predictor_set,
)


HORIZON = 50
CONTROLS = np.stack([np.full(HORIZON, 8.0), np.zeros(HORIZON)], axis=-1)


def _cfg(order: CostOrder) -> BCVFConfig:
    return BCVFConfig(
        gate_threshold=0.2,
        gate_beta=100.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3),
        dt=0.1,
        cost_order=order,
    )


def _bcvf_across_orders(preds):
    trajs = [p.predict(CONTROLS) for p in preds.values()]
    return {
        order.name: compute_bcvf_cost(trajs, _cfg(order)).total_cost
        for order in (CostOrder.ZEROTH, CostOrder.FIRST, CostOrder.SECOND)
    }


def _s1_no_failure(seed: int = 0):
    return create_predictor_set(seed=seed)


def _s5_constant_bias(seed: int = 0):
    preds = create_predictor_set(seed=seed, gnss_failure_type="constant_bias")
    preds["M4"].set_failure(
        FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.0)
    )
    return preds


def _s6_lidar_accelerating(seed: int = 0):
    preds = create_predictor_set(seed=seed)
    preds["M2"].set_failure(
        FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.5)
    )
    return preds


SCENARIO_BUILDERS = {
    "S1_no_failure": _s1_no_failure,
    "S5_constant_bias": _s5_constant_bias,
    "S6_lidar_accelerating": _s6_lidar_accelerating,
}


def run(seed: int = 0):
    rows = {}
    for name, build in SCENARIO_BUILDERS.items():
        rows[name] = _bcvf_across_orders(build(seed=seed))
    return rows


def pretty_print(rows):
    header = f"{'Scenario':24s}  {'ZEROTH':>10s}  {'FIRST':>10s}  {'SECOND':>10s}"
    print(header)
    print("-" * len(header))
    for name, r in rows.items():
        print(
            f"{name:24s}  {r['ZEROTH']:10.2f}  {r['FIRST']:10.2f}  {r['SECOND']:10.2f}"
        )
    print()
    # Lemma 1 contrast: S5 cost relative to S1 noise floor.
    s1, s5, s6 = rows["S1_no_failure"], rows["S5_constant_bias"], rows["S6_lidar_accelerating"]
    print("Response to constant bias (S5) relative to noise floor (S1):")
    for order in ("ZEROTH", "FIRST", "SECOND"):
        ratio = s5[order] / max(s1[order], 1e-9)
        print(f"  {order:6s}: S5/S1 = {ratio:7.1f}x")
    print()
    print("Discrimination between constant bias (S5) and real failure (S6):")
    for order in ("ZEROTH", "FIRST", "SECOND"):
        ratio = s6[order] / max(s5[order], 1e-9)
        print(f"  {order:6s}: S6/S5 = {ratio:7.1f}x  (higher = better discrimination)")


def main():
    rows = run()
    pretty_print(rows)


if __name__ == "__main__":  # pragma: no cover
    main()
