"""USE phase scheduler — decentralized cross-die bus arbiter (§6.5).

This is the one place a Cognade USE primitive reaches the storage tier. Bus
scheduling wants the *splay state* (transfer windows maximally spread so they
tile the shared bus without colliding), which is the state of MINIMUM phase
coherence. So we run the USE engine in reverse — repulsive coupling — i.e.
U1–U5 with the objective sign flipped:

    U1  C[i,j] = cos(φ_i − φ_j)                  (W=1, instantaneous)
    U2  minimise  C_total = Σ_{i<j} w_ij·C[i,j]  (flip: minimise, not maximise)
    U3  ∂C_total/∂φ_i = −Σ_j w_ij·sin(φ_i − φ_j)
    U4  Δφ_i = +α·Σ_j w_ij·sin(φ_i − φ_j)        (flip the sign → descend coherence)
    U5  |ΔC_total| < ε for T consecutive iters    (schedule has settled)

Coupling weights w_ij ∝ δ_i·δ_j (transfer-window fractions) so wide-window dies
are pushed further apart — the *weighted* splay the closed-form 2πi/N can't give
for heterogeneous (mixed-tier) dies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

TWO_PI = 2.0 * math.pi


@dataclass
class ScheduleResult:
    phases: list[float]
    iterations: int
    converged: bool
    coherence: float       # C_total at convergence (low ⇒ good splay)
    contention_us: float   # modeled bus-collision time added to the batch


@dataclass
class PhaseScheduler:
    alpha: float = 0.1        # U4 learning rate
    eps: float = 1e-3         # U5 threshold
    stable_iters: int = 10    # U5 T
    max_iters: int = 2000

    # -- U1/U2: weighted total coherence ----------------------------------- #
    def coherence(self, phases: list[float], weights: list[float]) -> float:
        n = len(phases)
        tot = wsum = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                w = weights[i] * weights[j]
                tot += w * math.cos(phases[i] - phases[j])
                wsum += w
        return tot / wsum if wsum else 0.0

    # -- circular overlap of transfer windows → bus-collision time --------- #
    def contention(self, phases: list[float], widths: list[float], t_cycle: float) -> float:
        n = len(phases)
        overlap_rad = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                d = abs(phases[i] - phases[j]) % TWO_PI
                d = min(d, TWO_PI - d)
                # window half-widths in radians: width = 2π·δ → half = π·δ
                needed = math.pi * (widths[i] + widths[j])
                if needed > d:
                    overlap_rad += needed - d
        return overlap_rad / TWO_PI * t_cycle

    # -- U3/U4/U5: converge to the (weighted) splay state ------------------ #
    def schedule(self, t_r: list[float], t_xfer: list[float]) -> ScheduleResult:
        n = len(t_r)
        if n == 0:
            return ScheduleResult([], 0, True, 0.0, 0.0)
        if n == 1:
            return ScheduleResult([0.0], 0, True, 0.0, 0.0)

        t_cycle = max(tr + tx for tr, tx in zip(t_r, t_xfer))
        widths = [tx / t_cycle for tx in t_xfer]   # δ_i
        weights = widths[:]                          # coupling ∝ δ
        phases = [TWO_PI * i / n for i in range(n)]  # round-robin init

        prev_c = self.coherence(phases, weights)
        stable = it = 0
        for it in range(1, self.max_iters + 1):
            new = phases[:]
            for i in range(n):
                grad = sum(
                    weights[i] * weights[j] * math.sin(phases[i] - phases[j])
                    for j in range(n)
                    if j != i
                )
                new[i] = (phases[i] + self.alpha * grad) % TWO_PI  # repulsive
            phases = new
            c = self.coherence(phases, weights)
            if abs(c - prev_c) < self.eps:
                stable += 1
                if stable >= self.stable_iters:
                    break
            else:
                stable = 0
            prev_c = c

        return ScheduleResult(
            phases=phases,
            iterations=it,
            converged=stable >= self.stable_iters,
            coherence=self.coherence(phases, weights),
            contention_us=self.contention(phases, widths, t_cycle),
        )
