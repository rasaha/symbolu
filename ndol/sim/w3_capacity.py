"""W3 capacity + endurance model — rigorous, conservative.

Hardens the earlier optimistic "2.22x tokens/GB" density figure by accounting
for what actually consumes physical NAND: ECC parity (which GROWS with cell
density because RBER rises), over-provisioning, alignment, sidecar/mask
metadata — and by checking ENDURANCE (QLC's low P/E budget vs KV write churn),
which can bind before capacity does.

Scope (per the W1-collapse finding): read-skip is approximate heavy-hitter
retention and is NOT modeled as novelty here; flash offload is integration
context. The only wedge under test is W3 — placing the int4_protected
*protect-mask* structure across NAND reliability tiers.

Systems compared:
  1. bf16 / TLC                      (baseline)
  2. int4 uniform / TLC
  3. int4_protected / TLC            (quantization only, uniform tier)
  4. int4_protected / W3 tiered      (protected bits -> TLC, 4-bit bulk -> QLC)
  5. int4_protected / all-QLC        (capacity ceiling, reliability-aggressive)

Capacity metric (silicon-normalized so cell density is captured honestly):
    tokens_per_GB = C_cells / cells_per_token
where C_cells is the silicon that yields 1 GB of *usable* data at TLC, and
    cells_per_token = sum_region( logical_bits_region * align / usable_bits_per_cell(tier) )
    usable_bits_per_cell(tier) = density(tier) * ECC_code_rate(RBER(tier)) / OP
    ECC_code_rate(rber) = max(0, eta * (1 - H2(rber)))          # Shannon BSC, LDPC eff. eta
    H2(p) = -p log2 p - (1-p) log2(1-p)                          # binary entropy

Endurance (write-once-read-many KV):
    sustainable_DWPD(tier) = PE_budget(tier) / (365 * life_years * WAF)
    lifetime_years(tier, dwpd) = PE_budget(tier) / (365 * dwpd * WAF)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

TIERS = ("SLC", "TLC", "QLC")


def h2(p: float) -> float:
    """Binary entropy (bits). H2(0)=0."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def ecc_code_rate(rber: float, eta: float) -> float:
    """Usable data fraction of raw bits to hit a target UBER from this RBER, via
    the Shannon BSC limit (1 - H2(rber)) discounted by LDPC efficiency eta.
    Higher RBER -> more parity -> lower code rate. Clipped at 0 (infeasible)."""
    return max(0.0, eta * (1.0 - h2(rber)))


@dataclass
class Params:
    # model geometry (Llama-3.1-8B class): elements/token = 2 * L * H * D
    layers: int = 32
    kv_heads: int = 8
    head_dim: int = 128

    # quantization (anchored to measured int4_protected net density vs bf16)
    int4prot_net_density: float = 1.80      # measured (VC brief / PHASE6N): ~1.78-1.83x
    int4_bits_per_elem: float = 4.0
    sidecar_bits_per_elem: float = 0.5      # group scale/zero, amortized
    # (static per-model protect mask is amortized ≈ 0/token and is already
    #  inside the measured net density below, so it is not added separately)
    bulk_bit_fraction: float = 0.75         # phi: QLC-eligible (4-bit bulk) share of int4prot bits

    # physical overheads
    align_overhead: float = 1.03            # page/block padding
    op_factor: float = 1.10                 # over-provisioning / endurance reserve
    eta_ecc: float = 0.90                   # LDPC efficiency vs Shannon

    # per-tier physics (conservative, end-of-life)
    density: dict = field(default_factory=lambda: {"SLC": 1, "TLC": 3, "QLC": 4})
    rber: dict = field(default_factory=lambda: {"SLC": 1e-6, "TLC": 5e-3, "QLC": 2e-2})
    pe_budget: dict = field(default_factory=lambda: {"SLC": 60000, "TLC": 3000, "QLC": 1000})

    # endurance
    waf: float = 1.1                        # write amplification (write-once-read-many -> low)
    life_years: float = 3.0

    def elements_per_token(self) -> int:
        return 2 * self.layers * self.kv_heads * self.head_dim

    def bf16_bits_per_token(self) -> float:
        return self.elements_per_token() * 16.0

    def int4_bits_per_token(self) -> float:
        return self.elements_per_token() * (self.int4_bits_per_elem + self.sidecar_bits_per_elem)

    def int4prot_bits_per_token(self) -> float:
        # anchored to the measured net density (which already includes int4_protected's
        # own sidecar + static protect-mask overhead)
        return self.bf16_bits_per_token() / self.int4prot_net_density

    def usable_bits_per_cell(self, tier: str) -> float:
        return self.density[tier] * ecc_code_rate(self.rber[tier], self.eta_ecc) / self.op_factor


# region = (logical_bits, tier)
def _cells_per_token(p: Params, regions: list[tuple[float, str]]) -> float:
    return sum(bits * p.align_overhead / p.usable_bits_per_cell(tier) for bits, tier in regions)


def systems(p: Params) -> dict[str, list[tuple[float, str]]]:
    B = p.int4prot_bits_per_token()
    phi = p.bulk_bit_fraction
    return {
        "bf16 / TLC": [(p.bf16_bits_per_token(), "TLC")],
        "int4 / TLC": [(p.int4_bits_per_token(), "TLC")],
        "int4_protected / TLC": [(B, "TLC")],
        "W3 (protected→TLC, bulk→QLC)": [((1 - phi) * B, "TLC"), (phi * B, "QLC")],
        "int4_protected / all-QLC": [(B, "QLC")],
    }


def tokens_per_gb(p: Params) -> dict[str, float]:
    c_cells = 8e9 / p.usable_bits_per_cell("TLC")   # silicon yielding 1 GB usable at TLC
    return {name: c_cells / _cells_per_token(p, regions) for name, regions in systems(p).items()}


def sustainable_dwpd(p: Params, tier: str) -> float:
    return p.pe_budget[tier] / (365.0 * p.life_years * p.waf)


def lifetime_years(p: Params, tier: str, dwpd: float) -> float:
    return p.pe_budget[tier] / (365.0 * dwpd * p.waf)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _fmt(t: float) -> str:
    return f"{t/1000:.2f}k"


def report(p: Params | None = None) -> None:
    p = p or Params()
    tpg = tokens_per_gb(p)
    base = tpg["bf16 / TLC"]
    uni = tpg["int4_protected / TLC"]

    print("W3 CAPACITY + ENDURANCE MODEL (conservative)\n")
    print(f"geometry: {p.elements_per_token()} KV elem/token "
          f"({p.bf16_bits_per_token()/8/1024:.0f} KiB/token bf16); "
          f"int4_protected net density {p.int4prot_net_density}x; "
          f"QLC-eligible bulk fraction φ={p.bulk_bit_fraction}")
    print(f"ECC: Shannon BSC, η={p.eta_ecc}; OP={p.op_factor}; align={p.align_overhead}")
    print("usable data bits/cell after ECC+OP: "
          + ", ".join(f"{t}={p.usable_bits_per_cell(t):.3f}" for t in TIERS))
    print(f"  (naive density would be SLC=1/TLC=3/QLC=4; QLC/TLC after ECC = "
          f"{p.usable_bits_per_cell('QLC')/p.usable_bits_per_cell('TLC'):.3f}× vs naive 1.333×)\n")

    print(f"{'system':<34}{'tokens/GB':>12}{'×bf16':>8}{'×int4p':>8}")
    print("-" * 62)
    for name in systems(p):
        t = tpg[name]
        print(f"{name:<34}{_fmt(t):>12}{t/base:>8.2f}{t/uni:>8.2f}")

    print("\nENDURANCE (write-once-read-many; sustainable DWPD for "
          f"{p.life_years:.0f}-yr life, WAF={p.waf}):")
    for tier in TIERS:
        print(f"  {tier}: P/E={p.pe_budget[tier]:>6}  sustainable ≈ {sustainable_dwpd(p, tier):.2f} DWPD"
              f"   (life at 10 DWPD: {lifetime_years(p, tier, 10):.2f} yr)")

    print("\n--- SENSITIVITY: W3 ×bf16 vs QLC end-of-life RBER (collapse check) ---")
    print(f"{'RBER_QLC':>10}{'QLC bits/cell':>15}{'W3 ×bf16':>10}{'W3 ×int4p':>11}{'verdict':>14}")
    for rber_q in (1e-2, 2e-2, 3e-2, 5e-2, 7e-2, 1e-1):
        pp = Params(**{**p.__dict__, "rber": {**p.rber, "QLC": rber_q}})
        t = tokens_per_gb(pp)
        w3 = t["W3 (protected→TLC, bulk→QLC)"]
        ucell = pp.usable_bits_per_cell("QLC")
        verdict = "holds" if w3 / base >= 2.0 else ("weak" if w3 / base >= 1.9 else "collapsed")
        print(f"{rber_q:>10.0e}{ucell:>15.3f}{w3/base:>10.2f}{w3/t['int4_protected / TLC']:>11.2f}{verdict:>14}")

    print("\n--- SENSITIVITY: W3 ×int4p vs QLC-eligible bulk fraction φ ---")
    print(f"{'φ_bulk':>8}{'W3 ×bf16':>10}{'W3 ×int4p':>11}")
    for phi in (0.50, 0.60, 0.70, 0.75, 0.80, 0.90):
        pp = Params(**{**p.__dict__, "bulk_bit_fraction": phi})
        t = tokens_per_gb(pp)
        w3 = t["W3 (protected→TLC, bulk→QLC)"]
        print(f"{phi:>8.2f}{w3/base:>10.2f}{w3/t['int4_protected / TLC']:>11.2f}")

    print("\n--- SENSITIVITY: ECC efficiency η ---")
    print(f"{'η':>6}{'QLC/TLC bits':>14}{'W3 ×bf16':>10}")
    for eta in (0.80, 0.85, 0.90, 0.95):
        pp = Params(**{**p.__dict__, "eta_ecc": eta})
        t = tokens_per_gb(pp)
        ratio = pp.usable_bits_per_cell("QLC") / pp.usable_bits_per_cell("TLC")
        print(f"{eta:>6.2f}{ratio:>14.3f}{t['W3 (protected→TLC, bulk→QLC)']/t['bf16 / TLC']:>10.2f}")


if __name__ == "__main__":
    report()
