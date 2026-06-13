"""W3 sensitivity sweeps — does any layout improvement push the marginal past
1.25× or 1.5×, *honestly*, under a conservative ECC/RBER model and an
iso-reliability baseline?

Extends ndol/sim/w3_capacity.py with:
  * differentiated per-region ECC strength (error-tolerant bulk may target a
    relaxed UBER → higher code rate), via base_eff(target);
  * per-page packing (mixed pages force bulk to the strong target; compacted
    bulk pages can relax — NAND ECC is per-codeword/page);
  * protected tier choice incl. high-ECC QLC and replicated QLC;
  * K/V-split scenarios (which sets the protected fraction);
  * an ISO-RELIABILITY baseline: the densest *uniform-strong* layout (every bit
    meets the protected UBER), i.e. all-QLC at the protected target — NOT raw
    capacity. W3 must beat THAT to claim a real win.
  * DWPD endurance gating per tier.

Conservatism: bulk is lossy 4-bit, so it may target a relaxed UBER, but NOT
zero ECC (a raw-QLC bit error rate of ~2e-2 corrupts ~8% of 4-bit codes — too
much), so the relaxation is capped.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .w3_capacity import h2

# base_eff = fraction of the Shannon limit (1-H2) a real code reaches for a given
# UBER target. Stronger target -> more parity margin -> lower efficiency. Bulk
# (lossy) may use a relaxed target; we cap relaxation at 1e-4 (still real ECC).
BASE_EFF = {"1e-15": 0.85, "1e-12": 0.87, "1e-9": 0.90, "1e-6": 0.94, "1e-4": 0.97}
STRONG = "1e-15"


@dataclass
class Phys:
    density: dict = field(default_factory=lambda: {"SLC": 1, "TLC": 3, "QLC": 4})
    rber: dict = field(default_factory=lambda: {"SLC": 1e-6, "TLC": 5e-3, "QLC": 2e-2})
    pe: dict = field(default_factory=lambda: {"SLC": 60000, "TLC": 3000, "QLC": 1000})
    op: float = 1.10
    align: float = 1.03
    waf: float = 1.1

    def code_rate(self, tier: str, target: str) -> float:
        return max(0.0, BASE_EFF[target] * (1.0 - h2(self.rber[tier])))

    def usable(self, tier: str, target: str) -> float:
        return self.density[tier] * self.code_rate(tier, target) / self.op

    def sustainable_dwpd(self, tier: str, years: float = 3.0) -> float:
        return self.pe[tier] / (365.0 * years * self.waf)

    def tier_viable(self, tier: str, dwpd: float, years: float = 3.0) -> bool:
        return self.sustainable_dwpd(tier, years) >= dwpd


@dataclass
class Layout:
    """A W3 layout. Fractions are of KV *elements*; protected bits at prot_bits,
    bulk at bulk_bits, plus amortized sidecar. compacted=True lets bulk pages use
    the relaxed target; mixed pages force bulk to the protected (strong) target."""
    p_protect: float = 0.04
    prot_bits: float = 16.0          # protected = high precision (bf16) — conservative
    bulk_bits: float = 4.0
    sidecar_bits: float = 0.5
    tier_prot: str = "TLC"
    tier_bulk: str = "QLC"
    target_prot: str = STRONG
    target_bulk: str = "1e-6"        # relaxed (error-tolerant bulk)
    repl_prot: float = 1.0           # replication factor for protected (>=1)
    compacted: bool = True

    def cells_per_token(self, ph: Phys, E: int) -> float:
        prot_logical = E * self.p_protect * (self.prot_bits + self.sidecar_bits)
        bulk_logical = E * (1 - self.p_protect) * (self.bulk_bits + self.sidecar_bits)
        bulk_target = self.target_bulk if self.compacted else self.target_prot
        u_p = ph.usable(self.tier_prot, self.target_prot)
        u_b = ph.usable(self.tier_bulk, bulk_target)
        return (self.repl_prot * prot_logical * ph.align / u_p
                + bulk_logical * ph.align / u_b)


def total_logical_bits(lay: Layout, E: int) -> float:
    return E * (lay.p_protect * (lay.prot_bits + lay.sidecar_bits)
                + (1 - lay.p_protect) * (lay.bulk_bits + lay.sidecar_bits))


def iso_reliability_baseline_cells(lay: Layout, ph: Phys, E: int) -> float:
    """Densest UNIFORM layout that meets the protected (strong) UBER on every
    bit — the fair baseline. = all bits, strong ECC, on the densest tier."""
    tot = total_logical_bits(lay, E)
    return min(tot * ph.align / ph.usable(t, STRONG) for t in ("TLC", "QLC"))


def naive_int4prot_tlc_cells(lay: Layout, ph: Phys, E: int) -> float:
    """The earlier (looser) baseline: everything on TLC, strong ECC, for continuity."""
    return total_logical_bits(lay, E) * ph.align / ph.usable("TLC", STRONG)


def E_default() -> int:
    return 2 * 32 * 8 * 128   # Llama-3.1-8B class


def main() -> None:
    ph = Phys()
    E = E_default()
    base_layout = Layout()
    iso = iso_reliability_baseline_cells(base_layout, ph, E)
    naive = naive_int4prot_tlc_cells(base_layout, ph, E)

    print("W3 SENSITIVITY (conservative ECC/RBER; iso-reliability baseline)\n")
    print(f"baseline (iso-reliability, densest uniform-strong) = {iso:,.0f} cells/token")
    print(f"  (= all-QLC at the protected UBER — the FAIR baseline, not raw capacity)")
    print(f"reference (naive int4_protected/TLC-strong)         = {naive:,.0f} cells/token\n")
    print("(marginals below recompute the baseline per layout — SAME data, only "
          "placement/ECC differ — the fair comparison)\n")

    def marginal(lay: Layout) -> tuple[float, float]:
        c = lay.cells_per_token(ph, E)
        # Fair: baseline holds the SAME quantized data (same p/bits) as this layout.
        return iso_reliability_baseline_cells(lay, ph, E) / c, naive_int4prot_tlc_cells(lay, ph, E) / c

    best = 0.0
    best_desc = ""

    # 1. protected-fraction sweep ------------------------------------------------
    print("1. PROTECTED FRACTION (compacted, prot→TLC-strong, bulk→QLC-1e-6)")
    print(f"   {'p':>6}{'×iso':>9}{'×naive':>9}")
    for p in (0.01, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20):
        m_iso, m_nv = marginal(Layout(p_protect=p))
        print(f"   {p:>6.2f}{m_iso:>9.2f}{m_nv:>9.2f}")
        if m_iso > best:
            best, best_desc = m_iso, f"p_protect={p}"

    # 2. protected tier choice ---------------------------------------------------
    print("\n2. PROTECTED TIER (p=0.04, bulk→QLC-1e-6, compacted)")
    print(f"   {'tier_prot':>16}{'×iso':>9}{'×naive':>9}")
    for desc, lay in [
        ("SLC-strong", Layout(tier_prot="SLC")),
        ("TLC-strong", Layout(tier_prot="TLC")),
        ("QLC-strong (high-ECC)", Layout(tier_prot="QLC", target_prot=STRONG)),
        ("QLC-replicated×2", Layout(tier_prot="QLC", target_prot="1e-9", repl_prot=2.0)),
    ]:
        m_iso, m_nv = marginal(lay)
        print(f"   {desc:>16}{m_iso:>9.2f}{m_nv:>9.2f}")
        if m_iso > best:
            best, best_desc = m_iso, f"protected_tier={desc}"

    # 3. page packing ------------------------------------------------------------
    print("\n3. PAGE PACKING (p=0.04, prot→TLC, bulk→QLC)")
    print(f"   {'packing':>12}{'bulk target':>13}{'×iso':>9}{'×naive':>9}")
    for desc, comp in [("mixed", False), ("compacted", True)]:
        lay = Layout(compacted=comp)
        m_iso, m_nv = marginal(lay)
        bt = lay.target_bulk if comp else lay.target_prot
        print(f"   {desc:>12}{bt:>13}{m_iso:>9.2f}{m_nv:>9.2f}")
        if m_iso > best:
            best, best_desc = m_iso, f"packing={desc}"

    # 4. K/V split (sets protected fraction) -------------------------------------
    print("\n4. K/V SPLIT (which/how much is protected → effective p)")
    print(f"   {'scope':>22}{'p_eff':>7}{'×iso':>9}{'×naive':>9}")
    for desc, p in [("both K+V", 0.08), ("K only", 0.04), ("V only", 0.04),
                    ("selected heads (¼)", 0.02), ("selected heads (1/8)", 0.01)]:
        m_iso, m_nv = marginal(Layout(p_protect=p))
        print(f"   {desc:>22}{p:>7.2f}{m_iso:>9.2f}{m_nv:>9.2f}")

    # 5. metadata policy (static mask, amortized) --------------------------------
    print("\n5. METADATA POLICY (static per-model mask, amortized /token)")
    mask_bits_per_token = {"raw (1b/group)": 0.02, "replicated×3": 0.06, "parity-coded": 0.03}
    for desc, mbpe in mask_bits_per_token.items():
        extra_cells = E * mbpe * ph.align / ph.usable("TLC", STRONG)
        c = Layout().cells_per_token(ph, E)
        print(f"   {desc:>16}: +{extra_cells:,.0f} cells/token ({100*extra_cells/c:.3f}% — negligible)")

    # 6. (baseline already iso-reliability above; show vs raw all-QLC for contrast)
    raw_allqlc = total_logical_bits(Layout(), E) * ph.align / (ph.density["QLC"] / ph.op)
    print("\n6. BASELINE CONTRAST")
    print(f"   iso-reliability baseline (fair) : {iso:,.0f} cells/token")
    print(f"   raw all-QLC (no ECC, unfair)    : {raw_allqlc:,.0f} cells/token "
          f"→ W3/raw = {raw_allqlc / Layout().cells_per_token(ph, E):.2f}× (the misleading number)")

    # 7. workload DWPD endurance gating ------------------------------------------
    print("\n7. WORKLOAD DWPD — which tiers are endurance-viable (3-yr life)")
    print(f"   {'DWPD':>6}{'SLC':>6}{'TLC':>6}{'QLC':>6}   note")
    for dwpd in (0.1, 0.3, 1.0, 3.0, 10.0):
        v = {t: "ok" if ph.tier_viable(t, dwpd) else "DEAD" for t in ("SLC", "TLC", "QLC")}
        note = "" if v["QLC"] == "ok" else "→ bulk can't use QLC; tiering ≠ capacity here"
        print(f"   {dwpd:>6.1f}{v['SLC']:>6}{v['TLC']:>6}{v['QLC']:>6}   {note}")

    # ---- best achievable, scanning the realistic-conservative envelope ----------
    print("\n=== BEST W3 MARGINAL (conservative envelope) ===")
    # most favorable *honest* config: tiny protected on dense tier, compacted,
    # bulk relaxed to 1e-4 (cap), protected on high-ECC QLC so it's not penalized.
    aggressive = Layout(p_protect=0.01, tier_prot="QLC", target_prot=STRONG,
                        tier_bulk="QLC", target_bulk="1e-4", compacted=True)
    m_iso_a, m_nv_a = marginal(aggressive)
    print(f"  most-favorable-honest (p=1%, all-QLC, bulk UBER 1e-4, compacted):")
    print(f"    ×iso-reliability = {m_iso_a:.3f}   ×naive-TLC = {m_nv_a:.3f}")
    best = max(best, m_iso_a)
    print(f"\n  best W3 marginal vs iso-reliability baseline = {best:.3f}×")
    print(f"  exceeds 1.25×? {'YES' if best >= 1.25 else 'NO'}")
    print(f"  exceeds 1.50×? {'YES' if best >= 1.50 else 'NO'}")


if __name__ == "__main__":
    main()
