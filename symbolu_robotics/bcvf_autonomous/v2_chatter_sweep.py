"""Consumer V2 chatter-reduction sweep — paired V1 vs V2 promotion gate.

Implements the audit's recommendation: re-run the §6.1 responsive
scenario at the V1 validated config with V2 (Schmitt-triggered
consumer) enabled vs disabled, and decide whether to promote V2
to default. The audit's two gates:

1. **Chatter rate.** Does V2 reduce per-step argmax flips
   (the V1 chatter signal the audit explicitly flagged) by a
   material margin?

2. **Rescue preservation.** Does V2 preserve V1's rescue pattern?

A subtlety the smoke run surfaced: V2's chatter benefit only
shows up on **nominal / borderline** scenarios where the BCVF
signal stays below ``engage_threshold`` — V2 stays UNIFORM and
suppresses the V1 softmin's per-tick noise. On strongly-failing
scenarios (``S3_map_error_accel``) V2 engages immediately and
stays engaged, so the V1 pipeline runs unchanged and V2 has no
chatter effect there.

The promotion gate therefore runs **two scenarios paired**:
* ``S1_normal_driving`` for the chatter-reduction gate (V2 must
  reduce per-step argmax flips materially when BCVF is quiet).
* ``S3_map_error_accel`` for the rescue-preservation gate (V2
  must not break a V1 rescue).

If both gates pass, V2 is recommended for promotion to default
in :class:`RunConfig.v2_enabled`. Per-scenario sweeps + the
combined decision are recorded in
:class:`V2PromotionDecisionResult`.
"""

from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .core import BCVFConfig, CostOrder
from .mppi_planner import MPPIConfig, PerfCostConfig
from .predictors.base import BicycleConfig
from .runner import RunConfig, Runner
from .scenarios import get_scenario, scenario_to_run_config
from .trust import ConsumerV2Config


# --------------------------------------------------------------------------- #
# Config + result dataclasses
# --------------------------------------------------------------------------- #


@dataclass
class V2ChatterSweepConfig:
    """Knobs for :func:`run_v2_chatter_sweep`."""

    scenario_name: str = "S3_map_error_accel"
    N: int = 21
    base_seed: int = 1000
    output_dir: str = "results/v2_chatter_sweep"
    # V2 hysteresis settings — match the production-recommended defaults.
    v2_engage_threshold: float = 0.5
    v2_disengage_threshold: float = 0.2
    v2_T_engage: int = 3
    v2_T_disengage: int = 5
    # Acceptance gates.
    chatter_min_median_reduction: float = 0.5
    chatter_min_v2_win_rate: float = 0.7
    # Smaller K/H for fast smoke iteration; production sweep should
    # use the §6.1 validated config from scenario_to_run_config().
    mppi_rollouts: int = 256
    mppi_horizon: Optional[int] = None  # None = use scenario default


@dataclass
class V2ChatterPerSeed:
    """Per-seed paired observation."""

    seed: int
    v1_argmax_flips: int
    v2_argmax_flips: int
    v1_total_steps: int
    v2_total_steps: int
    v1_collision: bool
    v2_collision: bool
    v1_flip_rate: float
    v2_flip_rate: float
    flip_rate_reduction: float   # (v1_rate - v2_rate) / max(v1_rate, eps)
    v2_state_distribution: Dict[str, int]   # {"uniform": n, "engaged": m}


@dataclass
class V2ChatterSweepResult:
    """Aggregated sweep output."""

    config: V2ChatterSweepConfig
    n_seeds: int
    per_seed: List[V2ChatterPerSeed]
    # Chatter-reduction stats
    median_v1_flip_rate: float
    median_v2_flip_rate: float
    median_flip_rate_reduction: float
    v2_wins_per_seed: int
    v2_win_rate: float
    chatter_gate_pass: bool
    # Rescue preservation stats
    v1_collision_count: int
    v2_collision_count: int
    v1_rescue_v2_collide: int    # V2 broke a V1 rescue
    v1_collide_v2_rescue: int    # V2 turned a V1 collision into a rescue
    rescue_gate_pass: bool
    mcnemar_p_v2_worse: float    # one-sided "is V2 significantly worse?"
    # Headline
    promotion_recommended: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": dataclasses.asdict(self.config),
            "n_seeds": self.n_seeds,
            "median_v1_flip_rate": self.median_v1_flip_rate,
            "median_v2_flip_rate": self.median_v2_flip_rate,
            "median_flip_rate_reduction": self.median_flip_rate_reduction,
            "v2_wins_per_seed": self.v2_wins_per_seed,
            "v2_win_rate": self.v2_win_rate,
            "chatter_gate_pass": self.chatter_gate_pass,
            "v1_collision_count": self.v1_collision_count,
            "v2_collision_count": self.v2_collision_count,
            "v1_rescue_v2_collide": self.v1_rescue_v2_collide,
            "v1_collide_v2_rescue": self.v1_collide_v2_rescue,
            "rescue_gate_pass": self.rescue_gate_pass,
            "mcnemar_p_v2_worse": self.mcnemar_p_v2_worse,
            "promotion_recommended": self.promotion_recommended,
            "per_seed": [dataclasses.asdict(s) for s in self.per_seed],
        }


# --------------------------------------------------------------------------- #
# Mid-level helpers
# --------------------------------------------------------------------------- #


def _v1_run_config(
    cfg: V2ChatterSweepConfig, seed: int,
) -> RunConfig:
    """V1 reference config: §6.1 validated A3 (V1 BCVF) without V2."""
    scenario = get_scenario(cfg.scenario_name)
    bcvf = BCVFConfig(
        gate_threshold=0.05, gate_beta=400.0, huber_delta=0.5,
        lever_arm=2.5, weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=False, anchor_index=0, dt=0.1,
        cost_order=CostOrder.SECOND, lambda_c=1.0,
    )
    mppi = MPPIConfig(
        num_rollouts=cfg.mppi_rollouts,
        horizon=cfg.mppi_horizon or 50,
        dt=0.1, lambda_c=1.0, bcvf_config=bcvf,
    )
    perf = PerfCostConfig()
    bicycle = BicycleConfig()

    rc = scenario_to_run_config(scenario, bcvf, mppi, perf, bicycle, seed=seed)
    rc.ema_alpha = 0.05
    rc.deadband_k_sigma = 2.0
    rc.trust_diagnostics_enabled = True
    rc.v2_enabled = False
    return rc


def _v2_run_config(
    cfg: V2ChatterSweepConfig, seed: int,
) -> RunConfig:
    """V2 config: same as V1 with the §14a Schmitt trigger turned on."""
    rc = _v1_run_config(cfg, seed)
    rc.v2_enabled = True
    rc.v2_engage_threshold = cfg.v2_engage_threshold
    rc.v2_disengage_threshold = cfg.v2_disengage_threshold
    rc.v2_T_engage = cfg.v2_T_engage
    rc.v2_T_disengage = cfg.v2_T_disengage
    return rc


def _argmax_flips(per_step_weights: np.ndarray) -> int:
    """Number of ticks where argmax(weights) changed from the previous tick."""
    if per_step_weights.shape[0] < 2:
        return 0
    a = np.argmax(per_step_weights, axis=1)
    return int(np.sum(a[1:] != a[:-1]))


def _collision_from_run(result) -> bool:
    return bool(getattr(result, "collision", False))


def _v2_state_counts(states: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {"uniform": 0, "engaged": 0, "": 0}
    for s in states:
        out[s] = out.get(s, 0) + 1
    return out


# --------------------------------------------------------------------------- #
# McNemar (one-sided)
# --------------------------------------------------------------------------- #


def _binomial_tail_geq(k: int, n: int, p: float = 0.5) -> float:
    """Same primitive used in pilot/sign_test.py — kept local to avoid a
    cross-package import (pilot is a sibling, not an upstream).

    Returns ``P(X >= k)`` for ``X ~ Binomial(n, p)`` via the log-PMF
    recurrence; the loop accumulates ``P(X=1)..P(X=k-1)`` so that for
    ``k == 1`` the range is empty and ``cdf`` stays at ``P(X = 0)``.
    The previous implementation placed the break at the end of the
    loop body, which never fired for ``k == 1`` and silently returned
    ``P(X >= 1) = 0.0`` instead of the correct tail.
    """
    if n <= 0:
        return 1.0 if k <= 0 else 0.0
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    log_p = math.log(p)
    log_q = math.log(1.0 - p) if p < 1.0 else float("-inf")
    log_pmf = n * log_q
    cdf = math.exp(log_pmf)   # P(X = 0)
    for i in range(1, k):
        log_pmf = log_pmf + math.log((n - i + 1) / i) + log_p - log_q
        cdf += math.exp(log_pmf)
    return max(0.0, min(1.0, 1.0 - cdf))


def _mcnemar_one_sided_v2_worse(b: int, c: int) -> float:
    """One-sided McNemar exact p-value for "V2 is worse than V1".

    ``b`` = V1 rescue, V2 collide   (V2 broke a V1 rescue)
    ``c`` = V1 collide, V2 rescue   (V2 fixed a V1 collision)

    Test: H0 P(V2 worse) <= P(V2 better);  H1 P(V2 worse) > P(V2 better).
    Returns P(X >= b) for X ~ Binomial(b + c, 0.5). p > 0.05 ⇒ V2 is
    not significantly worse than V1.
    """
    n = b + c
    if n == 0:
        return 1.0
    return _binomial_tail_geq(b, n, 0.5)


# --------------------------------------------------------------------------- #
# Top-level entry point
# --------------------------------------------------------------------------- #


def run_v2_chatter_sweep(
    config: Optional[V2ChatterSweepConfig] = None,
    write_artifacts: bool = True,
) -> V2ChatterSweepResult:
    """Run the V1-vs-V2 paired chatter sweep.

    For each of ``N`` seeds the runner executes the scenario twice —
    once with V2 disabled (V1 reference) and once with V2 enabled —
    on identical predictor RNG state and identical control noise.
    Per-seed argmax-flip count and collision outcome are captured.
    """
    cfg = config or V2ChatterSweepConfig()
    out_path = Path(cfg.output_dir)
    if write_artifacts:
        out_path.mkdir(parents=True, exist_ok=True)

    per_seed: List[V2ChatterPerSeed] = []
    for i in range(cfg.N):
        seed = cfg.base_seed + i

        rc_v1 = _v1_run_config(cfg, seed)
        runner_v1 = Runner(rc_v1)
        run_v1 = runner_v1.run()
        diag_v1 = runner_v1.trust_diagnostics()
        flips_v1 = _argmax_flips(diag_v1.per_step_weights)
        T_v1 = diag_v1.n_steps
        collide_v1 = _collision_from_run(run_v1)

        rc_v2 = _v2_run_config(cfg, seed)
        runner_v2 = Runner(rc_v2)
        run_v2 = runner_v2.run()
        diag_v2 = runner_v2.trust_diagnostics()
        flips_v2 = _argmax_flips(diag_v2.per_step_weights)
        T_v2 = diag_v2.n_steps
        collide_v2 = _collision_from_run(run_v2)

        rate_v1 = flips_v1 / max(T_v1 - 1, 1)
        rate_v2 = flips_v2 / max(T_v2 - 1, 1)
        reduction = (
            (rate_v1 - rate_v2) / rate_v1
            if rate_v1 > 1e-12 else 0.0
        )

        per_seed.append(V2ChatterPerSeed(
            seed=seed,
            v1_argmax_flips=flips_v1,
            v2_argmax_flips=flips_v2,
            v1_total_steps=T_v1,
            v2_total_steps=T_v2,
            v1_collision=collide_v1,
            v2_collision=collide_v2,
            v1_flip_rate=rate_v1,
            v2_flip_rate=rate_v2,
            flip_rate_reduction=reduction,
            v2_state_distribution=_v2_state_counts(diag_v2.per_step_v2_state),
        ))

    # Chatter-reduction stats
    v1_rates = np.array([s.v1_flip_rate for s in per_seed])
    v2_rates = np.array([s.v2_flip_rate for s in per_seed])
    median_v1 = float(np.median(v1_rates))
    median_v2 = float(np.median(v2_rates))
    median_reduction = float(np.median([s.flip_rate_reduction for s in per_seed]))
    v2_wins = sum(
        1 for s in per_seed if s.v2_flip_rate < s.v1_flip_rate - 1e-9
    )
    v2_win_rate = v2_wins / max(len(per_seed), 1)
    chatter_pass = (
        median_reduction >= cfg.chatter_min_median_reduction
        and v2_win_rate >= cfg.chatter_min_v2_win_rate
    )

    # Rescue preservation stats
    v1_col = sum(1 for s in per_seed if s.v1_collision)
    v2_col = sum(1 for s in per_seed if s.v2_collision)
    b_v2_broke = sum(
        1 for s in per_seed if (not s.v1_collision) and s.v2_collision
    )
    c_v2_fixed = sum(
        1 for s in per_seed if s.v1_collision and (not s.v2_collision)
    )
    p_v2_worse = _mcnemar_one_sided_v2_worse(b_v2_broke, c_v2_fixed)
    rescue_pass = b_v2_broke <= c_v2_fixed and p_v2_worse > 0.05

    promotion = chatter_pass and rescue_pass

    result = V2ChatterSweepResult(
        config=cfg,
        n_seeds=len(per_seed),
        per_seed=per_seed,
        median_v1_flip_rate=median_v1,
        median_v2_flip_rate=median_v2,
        median_flip_rate_reduction=median_reduction,
        v2_wins_per_seed=v2_wins,
        v2_win_rate=v2_win_rate,
        chatter_gate_pass=chatter_pass,
        v1_collision_count=v1_col,
        v2_collision_count=v2_col,
        v1_rescue_v2_collide=b_v2_broke,
        v1_collide_v2_rescue=c_v2_fixed,
        rescue_gate_pass=rescue_pass,
        mcnemar_p_v2_worse=p_v2_worse,
        promotion_recommended=promotion,
    )

    if write_artifacts:
        with open(out_path / "v2_chatter_sweep.json", "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        _write_report_md(out_path / "v2_chatter_sweep_report.md", result)

    return result


@dataclass
class V2PromotionDecisionResult:
    """Combined promotion decision over a chatter scenario + a rescue scenario."""

    chatter_sweep: V2ChatterSweepResult
    rescue_sweep: V2ChatterSweepResult
    promotion_recommended: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chatter_sweep": self.chatter_sweep.to_dict(),
            "rescue_sweep": self.rescue_sweep.to_dict(),
            "promotion_recommended": self.promotion_recommended,
        }


def run_v2_promotion_decision(
    chatter_scenario: str = "S1_normal_driving",
    rescue_scenario: str = "S3_map_error_accel",
    N: int = 10,
    base_seed: int = 1000,
    output_dir: Union[str, Path] = "results/v2_promotion_decision",
    chatter_min_median_reduction: float = 0.5,
    chatter_min_v2_win_rate: float = 0.7,
    mppi_rollouts: int = 64,
    write_artifacts: bool = True,
) -> V2PromotionDecisionResult:
    """Run two paired sweeps + combine into a single promotion decision.

    The chatter scenario tests V2's headline benefit (per-step argmax
    flip reduction when BCVF is below engage_threshold). The rescue
    scenario tests V2's headline cost (does it break the §6.1 rescue
    pattern?). Promotion requires the chatter gate to pass on the
    chatter scenario AND the rescue gate to pass on the rescue
    scenario.
    """
    out_path = Path(output_dir)
    if write_artifacts:
        out_path.mkdir(parents=True, exist_ok=True)

    chatter_cfg = V2ChatterSweepConfig(
        scenario_name=chatter_scenario,
        N=N,
        base_seed=base_seed,
        output_dir=str(out_path / "chatter"),
        chatter_min_median_reduction=chatter_min_median_reduction,
        chatter_min_v2_win_rate=chatter_min_v2_win_rate,
        mppi_rollouts=mppi_rollouts,
    )
    rescue_cfg = V2ChatterSweepConfig(
        scenario_name=rescue_scenario,
        N=N,
        base_seed=base_seed + 10_000,
        output_dir=str(out_path / "rescue"),
        # Chatter gate is informational only on the rescue scenario.
        chatter_min_median_reduction=0.0,
        chatter_min_v2_win_rate=0.0,
        mppi_rollouts=mppi_rollouts,
    )

    chatter_result = run_v2_chatter_sweep(chatter_cfg, write_artifacts)
    rescue_result = run_v2_chatter_sweep(rescue_cfg, write_artifacts)

    promotion = (
        chatter_result.chatter_gate_pass and rescue_result.rescue_gate_pass
    )

    decision = V2PromotionDecisionResult(
        chatter_sweep=chatter_result,
        rescue_sweep=rescue_result,
        promotion_recommended=promotion,
    )

    if write_artifacts:
        with open(out_path / "promotion_decision.json", "w", encoding="utf-8") as f:
            json.dump(decision.to_dict(), f, indent=2)
        _write_promotion_report_md(out_path / "promotion_decision_report.md", decision)

    return decision


def _write_promotion_report_md(path: Path, decision: V2PromotionDecisionResult) -> None:
    cs = decision.chatter_sweep
    rs = decision.rescue_sweep
    lines = []
    lines.append("# Consumer V2 Promotion Decision")
    lines.append("")
    lines.append(
        f"Chatter scenario: `{cs.config.scenario_name}` (N = {cs.n_seeds})  ·  "
        f"Rescue scenario: `{rs.config.scenario_name}` (N = {rs.n_seeds})"
    )
    lines.append("")
    lines.append("## Chatter gate (V2 must reduce per-step argmax flips when BCVF is quiet)")
    lines.append("")
    lines.append(
        f"- Median V1 flip rate: {cs.median_v1_flip_rate:.4f}  ·  "
        f"V2: {cs.median_v2_flip_rate:.4f}"
    )
    lines.append(
        f"- Median per-seed reduction: **{cs.median_flip_rate_reduction:.1%}** "
        f"(threshold ≥ {cs.config.chatter_min_median_reduction:.0%})"
    )
    lines.append(
        f"- V2-wins-per-seed: {cs.v2_wins_per_seed}/{cs.n_seeds} "
        f"({cs.v2_win_rate:.1%}, threshold ≥ {cs.config.chatter_min_v2_win_rate:.0%})"
    )
    lines.append(
        f"- **Chatter gate: {'PASS' if cs.chatter_gate_pass else 'FAIL'}**"
    )
    lines.append("")
    lines.append("## Rescue gate (V2 must not break the V1 rescue pattern)")
    lines.append("")
    lines.append(
        f"- V1 collisions: {rs.v1_collision_count}/{rs.n_seeds}  ·  "
        f"V2: {rs.v2_collision_count}/{rs.n_seeds}"
    )
    lines.append(
        f"- V2 broke a V1 rescue: {rs.v1_rescue_v2_collide}  ·  "
        f"V2 fixed a V1 collision: {rs.v1_collide_v2_rescue}"
    )
    lines.append(
        f"- McNemar one-sided p (V2 worse): {rs.mcnemar_p_v2_worse:.4f}"
    )
    lines.append(
        f"- **Rescue gate: {'PASS' if rs.rescue_gate_pass else 'FAIL'}**"
    )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    if decision.promotion_recommended:
        lines.append("**PROMOTE V2 TO DEFAULT.**")
        lines.append("")
        lines.append(
            "Both gates pass. Recommended action: flip "
            "`RunConfig.v2_enabled` default from `False` to `True` "
            "and update the VC brief to drop the \"V2 is opt-in\" "
            "caveat in favor of \"actuator-grade chatter immunity by default.\""
        )
    else:
        lines.append("**DO NOT PROMOTE.**")
        lines.append("")
        if not cs.chatter_gate_pass:
            lines.append(
                f"- Chatter gate failed on `{cs.config.scenario_name}`. "
                "V2 either did not reduce per-step argmax flips by the "
                "required margin, or did not win on enough seeds. The "
                "scenario may already be above V2's engage threshold "
                "(V2 stays ENGAGED → V1 pipeline runs unchanged) — "
                "consider tuning `engage_threshold` lower or re-running "
                "on a quieter scenario."
            )
        if not rs.rescue_gate_pass:
            lines.append(
                f"- Rescue gate failed on `{rs.config.scenario_name}`. "
                "V2 introduced collisions where V1 rescued. Investigate "
                "the per-seed JSON for the `v1_rescue_v2_collide` cases."
            )
        lines.append("")
        lines.append(
            "V2 stays opt-in. The brief's `\"V2 is opt-in, not yet default\"` "
            "caveat remains in force."
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_report_md(path: Path, result: V2ChatterSweepResult) -> None:
    cfg = result.config
    lines = []
    lines.append("# Consumer V2 Chatter-Reduction Sweep")
    lines.append("")
    lines.append(
        f"Scenario: `{cfg.scenario_name}`  ·  N = {result.n_seeds}  ·  "
        f"V2 thresholds engage/disengage = "
        f"{cfg.v2_engage_threshold}/{cfg.v2_disengage_threshold}  ·  "
        f"T_engage/T_disengage = {cfg.v2_T_engage}/{cfg.v2_T_disengage}"
    )
    lines.append("")
    lines.append("## Chatter reduction")
    lines.append("")
    lines.append(
        f"- Median V1 argmax-flip rate: **{result.median_v1_flip_rate:.4f}**"
    )
    lines.append(
        f"- Median V2 argmax-flip rate: **{result.median_v2_flip_rate:.4f}**"
    )
    lines.append(
        f"- Median per-seed reduction: **{result.median_flip_rate_reduction:.1%}**"
    )
    lines.append(
        f"- Per-seed V2-wins-on-flip-rate: "
        f"**{result.v2_wins_per_seed}/{result.n_seeds}** "
        f"({result.v2_win_rate:.1%})"
    )
    lines.append(
        f"- Chatter-reduction gate: "
        f"**{'PASS' if result.chatter_gate_pass else 'FAIL'}** "
        f"(requires median reduction ≥ {cfg.chatter_min_median_reduction:.0%} "
        f"AND V2-win rate ≥ {cfg.chatter_min_v2_win_rate:.0%})"
    )
    lines.append("")
    lines.append("## Rescue preservation")
    lines.append("")
    lines.append(
        f"- V1 collisions: **{result.v1_collision_count} / {result.n_seeds}**"
    )
    lines.append(
        f"- V2 collisions: **{result.v2_collision_count} / {result.n_seeds}**"
    )
    lines.append(
        f"- V2 broke a V1 rescue (V1 nominal → V2 collision): "
        f"**{result.v1_rescue_v2_collide}**"
    )
    lines.append(
        f"- V2 fixed a V1 collision (V1 collision → V2 nominal): "
        f"**{result.v1_collide_v2_rescue}**"
    )
    lines.append(
        f"- McNemar one-sided p (V2 worse than V1): "
        f"**{result.mcnemar_p_v2_worse:.4f}**"
    )
    lines.append(
        f"- Rescue-preservation gate: "
        f"**{'PASS' if result.rescue_gate_pass else 'FAIL'}** "
        "(requires V2 not introducing more collisions than it prevents AND "
        "p > 0.05 in the V2-worse direction)"
    )
    lines.append("")
    lines.append("## Promotion decision")
    lines.append("")
    lines.append(
        f"**{'PROMOTE V2 TO DEFAULT' if result.promotion_recommended else 'DO NOT PROMOTE'}**"
    )
    if result.promotion_recommended:
        lines.append("")
        lines.append(
            "Both gates pass. The recommended action is to flip "
            "`RunConfig.v2_enabled` default from `False` to `True` and "
            "drop the \"V2 is opt-in, not yet default\" caveat from the "
            "VC brief."
        )
    else:
        lines.append("")
        lines.append(
            "At least one gate failed. V2 stays opt-in. Consider tuning "
            "the V2 thresholds, increasing N, or examining the failing "
            "gate's evidence in the per-seed JSON."
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
