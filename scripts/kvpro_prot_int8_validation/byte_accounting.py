"""KVPro prot-int8 validation — Phase 2 byte accounting (CPU).

Two layers of evidence, kept strictly separate:

  MODELED   : analytical bytes/token/head/layer from the repo's own accounting model
              (experiments/.../accounting.py geometry), for bf16 (prot_B=2) vs int8 (prot_B=1).
  MEASURED  : real torch tensor .nbytes for the actual sidecar tensor k_protect_ext
              (NB,BS,H,n_protect) as bf16 vs uint8, PLUS the int8 dequant-constant metadata
              (_prot_qmin/_prot_qscale, 2*(H,n_protect) f32), i.e. host/tensor-storage bytes.

  RESOURCE_BLOCKED : actual GPU allocator-requested/reserved/peak bytes — no CUDA device here.

Nothing here measures GPU allocator granularity. "Real allocated GPU bytes" is RESOURCE_BLOCKED.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "experiments" / "kvpro_v3_symmetric_residual"))
import accounting as ACC   # noqa: E402  repo analytical model

ART = REPO / "artifacts" / "prot_int8"
ART.mkdir(parents=True, exist_ok=True)

D, BS, H = 128, 32, 4      # Qwen2.5-7B kv geometry
NB = 64                    # blocks (2048 tokens) for the measured tensor


def modeled_total(n_protect: int, prot_B: int) -> float:
    g = ACC.Geom(name="x", D=D, BS=BS, n_protect=n_protect, prot_B=prot_B, H_kv=H, n_layers=28)
    comp = ACC._components(g)
    return sum(comp.values())


def run():
    rows = []
    for pct in [0, 1, 2, 4, 8]:
        n_protect = 0 if pct == 0 else round(pct / 100 * D)
        # ---- MODELED bytes/token/head/layer ----
        prot_bf16 = n_protect * 2
        prot_int8 = n_protect * 1
        total_bf16 = modeled_total(n_protect, 2) if n_protect else modeled_total(1, 2) - 2
        total_int8 = modeled_total(n_protect, 1) if n_protect else total_bf16
        prot_saved = prot_bf16 - prot_int8
        total_saved_pct = (100.0 * (total_bf16 - total_int8) / total_bf16) if total_bf16 else 0.0
        prot_saved_pct = (100.0 * prot_saved / prot_bf16) if prot_bf16 else 0.0

        # ---- MEASURED tensor-storage bytes (real torch tensors) ----
        if n_protect:
            ext_bf16 = torch.zeros((NB, BS, H, n_protect), dtype=torch.bfloat16)
            ext_uint8 = torch.zeros((NB, BS, H, n_protect), dtype=torch.uint8)
            qmin = torch.zeros((H, n_protect), dtype=torch.float32)
            qscale = torch.zeros((H, n_protect), dtype=torch.float32)
            meas_bf16 = ext_bf16.nbytes
            meas_int8 = ext_uint8.nbytes + qmin.nbytes + qscale.nbytes    # int8 + amortized metadata
            meas_int8_payload_only = ext_uint8.nbytes
            const_bytes = qmin.nbytes + qscale.nbytes
            tokens = NB * BS
            const_per_token = const_bytes / tokens
        else:
            meas_bf16 = meas_int8 = meas_int8_payload_only = const_bytes = 0
            const_per_token = 0.0

        rows.append({
            "protect_pct": pct, "n_protect": n_protect,
            # modeled per-token/head/layer
            "MODELED_prot_bf16_B": prot_bf16, "MODELED_prot_int8_B": prot_int8,
            "MODELED_prot_saved_B": prot_saved, "MODELED_prot_saved_pct": round(prot_saved_pct, 2),
            "MODELED_total_bf16_B": round(total_bf16, 2), "MODELED_total_int8_B": round(total_int8, 2),
            "MODELED_total_saved_pct": round(total_saved_pct, 3),
            # measured tensor storage over NB*BS=2048 tokens
            "MEAS_sidecar_bf16_bytes": meas_bf16,
            "MEAS_sidecar_int8_payload_bytes": meas_int8_payload_only,
            "MEAS_int8_const_metadata_bytes": const_bytes,
            "MEAS_sidecar_int8_total_bytes": meas_int8,
            "MEAS_const_bytes_per_token": round(const_per_token, 5),
            "MEAS_net_saved_bytes": meas_bf16 - meas_int8,
            "MEAS_net_saved_pct": round(100.0 * (meas_bf16 - meas_int8) / meas_bf16, 3) if meas_bf16 else 0.0,
            "GPU_allocated_reserved_peak": "RESOURCE_BLOCKED (no CUDA device)",
        })

    with open(ART / "byte_accounting.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("wrote byte_accounting.csv")
    print(f"\n{'pct':>3} {'n_prot':>6} {'prot bf16->int8':>16} {'prot%':>7} "
          f"{'total bf16->int8 (B/tok/hd/L)':>30} {'total%':>7} {'MEAS net% (with meta)':>22}")
    for r in rows:
        print(f"{r['protect_pct']:>3} {r['n_protect']:>6} "
              f"{str(r['MODELED_prot_bf16_B'])+'->'+str(r['MODELED_prot_int8_B']):>16} "
              f"{r['MODELED_prot_saved_pct']:>6.1f}% "
              f"{str(r['MODELED_total_bf16_B'])+'->'+str(r['MODELED_total_int8_B']):>30} "
              f"{r['MODELED_total_saved_pct']:>6.2f}% {r['MEAS_net_saved_pct']:>21.2f}%")
    print("\nNote: 'total' = full int4_protected K/V read stream (packed K/V + scales + xmins + protect).")
    print("The int8 sidecar halves ONLY the protect sub-stream; net saving of the TOTAL stream is small.")
    print("GPU allocator-reserved/peak bytes: RESOURCE_BLOCKED (no CUDA device in this environment).")


if __name__ == "__main__":
    run()
