"""W3 capacity / density model — how many more KV tokens fit per unit of NAND
silicon when bulk goes to dense QLC, at preserved quality.

This is the *robust*, unconditional half of W3 (the latency half, in
run_tiered.py, is conditional on access pattern). Capacity is deterministic, so
this is an analytical model, not a simulation — the right tool for the job.

Two quality-preserving density levers compound:
  1. Quantization  : int4_protected stores fewer logical bits/token than bf16,
                     at bf16-parity quality (measured ~1.8× net, incl. sidecar).
  2. Cell density  : QLC packs 4 bits/cell vs TLC's 3. Bulk 4-bit codes are
                     error-tolerant (already lossy-quantized + ECC), so they
                     ride QLC; the precision-critical *protected* bits stay on
                     the more reliable TLC.

Honest nuance surfaced by this model: SLC (1 bit/cell) is the WORST tier for
capacity, so the capacity-optimal placement puts protected on TLC — the
*opposite* of the latency-optimal placement (protected→SLC for speed). The
protect mask is the placement signal; the chosen tier depends on the objective.
The one objective-independent win is **bulk → QLC**.
"""
from __future__ import annotations

from dataclasses import dataclass

BITS_PER_CELL = {"SLC": 1, "TLC": 3, "QLC": 4}
_BF16_BITS = 16


@dataclass
class KVGeometry:
    """Per-token KV size from model geometry. elements/token = 2 (K,V) · L · H · D."""

    name: str
    layers: int
    kv_heads: int
    head_dim: int

    def elements_per_token(self) -> int:
        return 2 * self.layers * self.kv_heads * self.head_dim

    def bf16_bits_per_token(self) -> int:
        return self.elements_per_token() * _BF16_BITS


@dataclass
class ProtectScheme:
    """int4_protected / prot-int8 storage profile.

    net_density_vs_bf16  : measured logical compression at preserved quality
                           (~1.78–1.83× from INT4_PROTECTED_VC_BRIEF / PHASE6N).
    protected_bit_fraction (φ): share of the stored bits that are precision-
                           critical and must stay on a reliable (non-QLC) tier.
    """

    net_density_vs_bf16: float = 1.80
    protected_bit_fraction: float = 0.25

    def stored_bits_per_token(self, geom: KVGeometry) -> float:
        return geom.bf16_bits_per_token() / self.net_density_vs_bf16


# Placement policies → physical cells per token.
def cells_per_token(geom: KVGeometry, scheme: ProtectScheme, placement: str) -> float:
    if placement == "bf16_tlc":  # no quantization, uniform TLC (absolute baseline)
        return geom.bf16_bits_per_token() / BITS_PER_CELL["TLC"]

    bits = scheme.stored_bits_per_token(geom)  # int4_protected logical bits
    if placement == "int4prot_tlc":            # quantization only, uniform TLC
        return bits / BITS_PER_CELL["TLC"]
    if placement == "int4prot_qlc":            # max density (reliability-aggressive)
        return bits / BITS_PER_CELL["QLC"]
    if placement == "tiered":                  # W3: protected→TLC, bulk→QLC
        phi = scheme.protected_bit_fraction
        return phi * bits / BITS_PER_CELL["TLC"] + (1.0 - phi) * bits / BITS_PER_CELL["QLC"]
    raise ValueError(f"unknown placement {placement!r}")


def tokens_per_silicon(geom: KVGeometry, scheme: ProtectScheme, placement: str, n_cells: float) -> float:
    """KV tokens stored in a FIXED physical cell budget (≈ fixed silicon cost)."""
    return n_cells / cells_per_token(geom, scheme, placement)


# A 1 TB-class silicon budget, expressed as cells, held fixed across placements
# (1 TB of TLC rating = 1e12·8 bits / 3 bits-per-cell).
SILICON_1TB_TLC_CELLS = 1e12 * 8 / 3

_PLACEMENTS = [
    ("bf16 / TLC (baseline)", "bf16_tlc"),
    ("int4_protected / TLC", "int4prot_tlc"),
    ("int4_protected / tiered (protected→TLC, bulk→QLC)", "tiered"),
    ("int4_protected / all-QLC (max, reliability-aggressive)", "int4prot_qlc"),
]

MODELS = [
    KVGeometry("Llama-3.1-8B", layers=32, kv_heads=8, head_dim=128),
    KVGeometry("Qwen2.5-7B", layers=28, kv_heads=4, head_dim=128),
    KVGeometry("Mistral-7B-v0.3", layers=32, kv_heads=8, head_dim=128),
]


def report(scheme: ProtectScheme | None = None, n_cells: float = SILICON_1TB_TLC_CELLS) -> None:
    scheme = scheme or ProtectScheme()
    print("W3 capacity model — KV tokens per ~1 TB-class silicon budget (fixed cells)")
    print(f"int4_protected net density vs bf16 = {scheme.net_density_vs_bf16}×, "
          f"protected bit-fraction φ = {scheme.protected_bit_fraction}\n")

    for geom in MODELS:
        base = tokens_per_silicon(geom, scheme, "bf16_tlc", n_cells)
        uni = tokens_per_silicon(geom, scheme, "int4prot_tlc", n_cells)
        print(f"{geom.name}  (KV {geom.bf16_bits_per_token() // 8 // 1024} KiB/token bf16)")
        print(f"  {'placement':<52}{'Mtokens':>9}{'×bf16':>8}{'×int4p':>8}")
        for label, pl in _PLACEMENTS:
            tok = tokens_per_silicon(geom, scheme, pl, n_cells)
            print(f"  {label:<52}{tok/1e6:>9.2f}{tok/base:>8.2f}{tok/uni:>8.2f}")
        print()

    # The unconditional W3 marginal gain (tiered vs uniform-int4-TLC).
    g = MODELS[0]
    w3 = tokens_per_silicon(g, scheme, "tiered", n_cells) / tokens_per_silicon(g, scheme, "int4prot_tlc", n_cells)
    print(f"W3 marginal capacity gain (bulk→QLC tiering, on top of int4_protected): {w3:.2f}×")
    print("This is UNCONDITIONAL (monotone in bulk fraction; no access-pattern dependence) —")
    print("the robust half of W3, vs the conditional latency result in run_tiered.py.")


if __name__ == "__main__":
    report()
