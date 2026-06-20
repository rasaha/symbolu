#!/usr/bin/env python3
"""smoke_generate.py — one base-vs-wrapper generation with diagnostics (Task 5).

Sanity-checks the GPU plumbing before the full ablation: loads the model + (optionally) the
trained CG head, generates a short continuation under arm A (base) and arm B (full wrapper) for
one prompt, and prints both outputs plus the K0/K1 diagnostics (gate, correction norm, logit KL,
top-1 flip, and the gate=0 == base check).

Usage (env-driven, see README.md):
    MODEL_ID=mistralai/Mistral-7B-v0.3 CG_CHECKPOINT=/path/best_model.pt \
        python scripts/cg_wrapper_ablation/smoke_generate.py "What is 12 * 8?"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cg_ablation.arms import ARMS_BY_NAME  # noqa: E402
from cg_ablation.runtime import (  # noqa: E402
    build_wrapper,
    generate,
    parse_env,
    prompt_logit_diag,
    detect_csr_present,
)


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Q: A box has 6 rows of 8 apples. How many apples? A:"
    cfg = parse_env()
    print(f"== smoke :: model={cfg.model_id} ckpt={cfg.checkpoint} dtype={cfg.dtype} ==")
    wrapper, tok = build_wrapper(cfg)
    print(f"CSR present in forward path: {detect_csr_present(wrapper)} (arm E gated on this)")

    base_arm = ARMS_BY_NAME["A_base"]
    full_arm = ARMS_BY_NAME["B_full"]
    gate0_arm = ARMS_BY_NAME["D_gate0"]

    print("\n--- BASE (arm A) ---")
    base = generate(wrapper, tok, prompt, base_arm, max_new_tokens=64)
    print(base["text"])

    print("\n--- WRAPPER (arm B, full CG) ---")
    full = generate(wrapper, tok, prompt, full_arm, max_new_tokens=64)
    print(full["text"])
    print(f"  diag: {full['diag']}")

    print("\n--- DIAGNOSTICS (teacher-forced on prompt) ---")
    diag_B = prompt_logit_diag(wrapper, tok, prompt, base_arm, full_arm)
    print(f"  B vs base: KL={diag_B['logit_kl_vs_base']:.3e}  "
          f"flip={diag_B['top1_flip_rate_vs_base']:.3%}  "
          f"gate={diag_B['adapter_gate']:.4f}  "
          f"corr/hidden={diag_B['correction_to_hidden_ratio']:.3e}")

    diag_D = prompt_logit_diag(wrapper, tok, prompt, base_arm, gate0_arm)
    k0_ok = diag_D["max_abs_logit_diff_vs_base"] <= 1e-4
    print(f"  K0 (gate0 == base): max|Δlogit|={diag_D['max_abs_logit_diff_vs_base']:.3e} "
          f"-> {'PASS' if k0_ok else 'FAIL (hidden coupling!)'}")

    inert = (diag_B["logit_kl_vs_base"] < 1e-3
             and diag_B["top1_flip_rate_vs_base"] < 5e-3
             and diag_B["correction_to_hidden_ratio"] < 1e-2)
    print(f"\n  K1 (inert?) -> {'INERT (wrapper changes ~nothing)' if inert else 'ACTIVE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
