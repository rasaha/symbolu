"""KV-compression method MEMORY comparison — analytical bytes/element.

⚠️ ANALYTICAL ESTIMATES from each method's PUBLIC description, NOT measured. The
robust conclusions rest on hard facts (Hadamard rotation is parameter-free →
~0 storage; int4_protected's 1.8× net is measured). Competitor quality is their
CLAIM — verify by running their code (see the GPU head-to-head plan).

Methods:
  bf16            — reference (16 b/elem)
  int4 (naive)    — 4-bit + per-group scale/zero
  int4_protected  — your scheme; measured ~1.8× net of the sidecar+protected tax
  GEAR            — 4-bit + low-rank residual + sparse outliers (2403.05527)
  SAW-INT4        — token-wise 4-bit + block-diagonal Hadamard rotation (2604.19157)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Params:
    group_size: int = 64            # quant group for per-group scale/zero
    int4prot_net_density: float = 1.80   # measured (VC brief / PHASE6N), vs bf16
    gear_rank_frac: float = 0.02    # low-rank residual rank as frac of min(n,d)
    gear_sparse_frac: float = 0.02  # outlier fraction kept at fp16 + index
    n: int = 2048                   # tokens (for low-rank amortization)
    d: int = 4096                   # hidden (K+V channel count proxy)

    def scale_bits(self) -> float:
        return 2 * 16 / self.group_size            # fp16 scale + zero per group

    def bits_per_elem(self, method: str) -> float:
        s = self.scale_bits()
        if method == "bf16":
            return 16.0
        if method == "int4 (naive)":
            return 4.0 + s
        if method == "int4_protected":
            return 16.0 / self.int4prot_net_density            # measured net (incl. sidecar+protected)
        if method == "SAW-INT4":
            # token-wise int4 + Hadamard rotation. Rotation is PARAMETER-FREE → +0 storage.
            return 4.0 + s
        if method == "GEAR":
            rank = self.gear_rank_frac * min(self.n, self.d)
            lowrank = rank * (self.n + self.d) * 16 / (self.n * self.d)   # U,V at fp16, amortized
            sparse = self.gear_sparse_frac * (16 + 24)                    # outlier value + ~24b index
            return 4.0 + s + lowrank + sparse
        raise ValueError(method)


METHODS = ["bf16", "int4 (naive)", "int4_protected", "GEAR", "SAW-INT4"]
# claimed quality on each method's own eval (NOT measured here — verify)
_QUALITY = {
    "bf16": "reference",
    "int4 (naive)": "degraded (the problem)",
    "int4_protected": "near-bf16 (MEASURED: needle 15/15, greedy bit-identical)",
    "GEAR": "near-lossless (CLAIMED 2403.05527)",
    "SAW-INT4": "near-lossless on Qwen3 (CLAIMED) BUT MEASURED 0% needle on Qwen2.5-7B-Instruct — does not generalize (see SAW_INT4_QWEN_HEADTOHEAD_RESULTS.md)",
}


def report(p: Params | None = None) -> None:
    p = p or Params()
    bf16 = p.bits_per_elem("bf16")
    print("KV-method MEMORY comparison — analytical bits/element (NOT measured; competitor quality = their claim)\n")
    print(f"{'method':<18}{'bits/elem':>10}{'×bf16 density':>15}   quality")
    print("-" * 78)
    for m in METHODS:
        b = p.bits_per_elem(m)
        print(f"{m:<18}{b:>10.2f}{bf16 / b:>15.2f}   {_QUALITY[m]}")
    saw = bf16 / p.bits_per_elem("SAW-INT4")
    prot = bf16 / p.bits_per_elem("int4_protected")
    print(f"\n  SAW-INT4 / int4_protected density ratio = {saw / prot:.2f}×")
    print("  → If SAW-INT4's near-lossless claim holds on your models, it is ~2× DENSER than")
    print("    int4_protected (rotation is free; you pay a sidecar) AND serving-native.")
    print("    That would invert int4_protected's density lead. THIS is the comparison to run.")
    print("\n  Caveat: GEAR/SAW bits/elem are estimates from public descriptions; their quality is")
    print("  claimed, not measured here. Run the GPU head-to-head (same models + needle/PPL/")
    print("  greedy-agreement + throughput) before drawing conclusions.")


if __name__ == "__main__":
    report()
