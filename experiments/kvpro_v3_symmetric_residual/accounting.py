"""KVPro V3 Gate-1 — analytical metadata / bandwidth / instruction accounting (Phase E).

Computes, from the ACTUAL tensor geometry, the read-bandwidth and instruction work each candidate
removes. These are ANALYTICAL facts (not measured TPS). Decode is memory-bandwidth-bound at long
context, so bytes/token is the throughput-relevant proxy — but this module does NOT claim a TPS gain.

Per-decode-token read cost is dominated by the per-KV-position, per-head, per-layer bytes (the kernel
re-reads all prior KV every step). We report that unit + full-context totals.

Units (D=128, BS=32, v_group_size=32 -> v_n_groups=4, bf16 sidecars=2B):
  packed K   = D/2 bytes (int4)                       = 64
  packed V   = D/2 bytes                              = 64
  K scale    = D * sidecar_B / BS  (per-block amort)  = 8
  K xmin     = D * sidecar_B / BS                     = 8
  V scale    = v_n_groups * sidecar_B  (per-token)    = 8
  V xmin     = v_n_groups * sidecar_B                 = 8
  K protect  = n_protect * prot_B     (per-token)     = 12 (bf16) / 6 (int8)   [scattered]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Geom:
    name: str
    D: int = 128
    BS: int = 32
    v_group_size: int = 32
    n_protect: int = 6            # ~4% of 128 (mask-dependent; override per real mask)
    sidecar_B: int = 2           # bf16
    prot_B: int = 2              # bf16 protect (use 1 for prot-int8)
    H_kv: int = 4
    n_layers: int = 28

    @property
    def v_n_groups(self) -> int:
        return self.D // self.v_group_size


def _components(g: Geom) -> Dict[str, float]:
    return {
        "packed_K": g.D / 2,
        "packed_V": g.D / 2,
        "K_scale": g.D * g.sidecar_B / g.BS,
        "K_xmin": g.D * g.sidecar_B / g.BS,
        "V_scale": g.v_n_groups * g.sidecar_B,
        "V_xmin": g.v_n_groups * g.sidecar_B,
        "K_protect": g.n_protect * g.prot_B,
    }


# which xmin streams each candidate removes
_REMOVES = {
    "affine": set(),
    "S1": {"K_xmin", "V_xmin"},
    "S2": {"K_xmin", "V_xmin"},          # + tiny per-layer bias (amortized ~0/token, added below)
    "S3": {"V_xmin"},                    # affine K, symmetric V
    "S4": {"K_xmin"},                    # symmetric K, affine V
}


def account(g: Geom, context_len: int = 8192) -> Dict[str, Dict]:
    comp = _components(g)
    base = sum(comp.values())            # affine bytes/token/head/layer
    out = {}
    for cand, removed in _REMOVES.items():
        removed_bytes = sum(comp[k] for k in removed)
        # S2 coarse bias: per-(H,D) [K] and per-(H,group) [V] per LAYER, amortized over context_len.
        bias_add = 0.0
        if cand == "S2":
            bias_add = (g.D * g.sidecar_B + g.v_n_groups * g.sidecar_B) / max(1, context_len)
        total = base - removed_bytes + bias_add
        # instruction: symmetric drops the +xmin add per element (K and/or V), adds sign-extend (~1 op).
        adds_removed = 0
        if cand in ("S1", "S2", "S4"):
            adds_removed += g.D          # K: one +xmin per channel/token/head removed
        if cand in ("S1", "S2", "S3"):
            adds_removed += g.D          # V
        out[cand] = {
            "bytes_per_tok_head_layer": round(total, 3),
            "bytes_removed": round(removed_bytes - bias_add, 3),
            "pct_reduction_vs_affine": round(100.0 * (base - total) / base, 2),
            "xmin_fully_removed": {"K": ("K_xmin" in removed), "V": ("V_xmin" in removed)},
            "affine_adds_removed_per_tok_head": adds_removed,
            "sign_extend_added_per_tok_head": (g.D if cand in ("S1", "S2", "S4") else 0)
                                             + (g.D if cand in ("S1", "S2", "S3") else 0),
            # full-context totals (all heads, all layers) — storage/bandwidth scale
            "MB_per_1k_tok_all_heads_layers": round(
                total * g.H_kv * g.n_layers * 1000 / 1e6, 3),
        }
    out["_affine_bytes_per_tok_head_layer"] = round(base, 3)
    out["_geom"] = g.__dict__ | {"v_n_groups": g.v_n_groups}
    return out


QWEN2_5_7B = Geom(name="Qwen2.5-7B", H_kv=4, n_layers=28)
LLAMA3_1_8B = Geom(name="Llama-3.1-8B", H_kv=8, n_layers=32)


def _print(g: Geom, ctx: int = 8192):
    a = account(g, ctx)
    base = a["_affine_bytes_per_tok_head_layer"]
    print(f"\n=== {g.name}  (D={g.D} BS={g.BS} v_groups={g.v_n_groups} n_protect={g.n_protect} "
          f"prot_B={g.prot_B} H_kv={g.H_kv} L={g.n_layers}, ctx={ctx}) ===")
    print(f"affine baseline: {base:.1f} B/token/head/layer")
    print(f"{'cand':6} {'B/tok/hd/L':>11} {'reduction%':>10} {'xmin_removed(K,V)':>18} {'adds_removed':>12}")
    for c in ("affine", "S1", "S2", "S3", "S4"):
        r = a[c]
        print(f"{c:6} {r['bytes_per_tok_head_layer']:>11.2f} {r['pct_reduction_vs_affine']:>9.2f}% "
              f"{str((r['xmin_fully_removed']['K'], r['xmin_fully_removed']['V'])):>18} "
              f"{r['affine_adds_removed_per_tok_head']:>12}")
    print("NOTE: reduction% is READ-BANDWIDTH (decode is bandwidth-bound) — NOT a measured TPS gain. "
          "Protect (scattered) remains after xmin removal and likely becomes the next metadata bottleneck.")


if __name__ == "__main__":
    for g in (QWEN2_5_7B, LLAMA3_1_8B):
        _print(g)
    # prot-int8 variant (halves protect bytes) — informational, orthogonal axis.
    _print(Geom(name="Qwen2.5-7B (prot-int8)", H_kv=4, n_layers=28, prot_B=1))
