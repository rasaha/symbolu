"""KVPro prot-int8 — real-model greedy/teacher-forced parity, C (P8prod) vs B (affine).

Fills the gap token_agreement.py leaves: it only loops fp/affine/S1-S4 and never emits P8prod.
This reuses the SAME fake-quant backend (fakequant_model) and the calibrated v2 mask (k_min/k_max),
so P8prod == the Phase-6N prot_int8 math. POD-ONLY (needs GPU + model + mask).

Two metrics, kept separate (per the harness's own discipline):
  teacher_forced : per-position next-token argmax over a fixed text — the stable, low-noise signal.
  autoregressive : greedy free generation (do_sample=False) — high-variance after first divergence;
                   reported but NOT the basis of any parity claim.

Primary comparison is C (P8prod) vs B (affine). fp is included as context.
Writes greedy_parity.csv. CPU-safe imports; the actual run needs CUDA.

Usage:
  python mistral_greedy_parity.py \
    --model /workspace/models/mistral-7b-instruct-v0.3 \
    --mask "$PROTECT_MASK_PATH" \
    --out /workspace/symbolu/artifacts/prot_int8_mistral/greedy_parity.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXP = os.path.abspath(os.path.join(_HERE, "..", "..", "experiments", "kvpro_v3_symmetric_residual"))
sys.path.insert(0, _EXP)

# representative prompts spanning the requested categories
PROMPTS = {
    "factual_qa":   "Question: What is the capital of Australia? Answer:",
    "arithmetic":   "Compute step by step: 347 + 589 = ",
    "code":         "def fibonacci(n):\n    \"\"\"Return the n-th Fibonacci number.\"\"\"\n",
    "instruction":  "List three primary colors, one per line:\n1.",
    "summarize":    "Summarize in one sentence: The field report logged a measurement, a checksum, "
                    "and a timestamp before the shift change, then the operator signed off.",
    "repeated":     "na " * 40,
    "retrieval":    "The access code is 7F3-QX9. Remember it. Filler. " * 8 + " The access code is",
}


def main(argv=None):
    ap = argparse.ArgumentParser(description="C(P8prod) vs B(affine) greedy/teacher-forced parity")
    ap.add_argument("--model", default="/workspace/models/mistral-7b-instruct-v0.3")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--gen-tokens", type=int, default=48)
    ap.add_argument("--out", default=os.path.join(_EXP, "greedy_parity.csv"))
    args = ap.parse_args(argv)
    if not args.mask or not os.path.isfile(args.mask):
        print(f"[FAIL] mask missing: {args.mask!r}", file=sys.stderr)
        return 2

    import torch  # noqa
    import fakequant_model as FQ
    model, tok = FQ.load_model(args.model)
    masks = FQ.load_masks(args.mask)
    if FQ._PROT_KMIN is None:
        print("[FAIL] mask has no k_min/k_max — P8prod (INT8) needs the v2 calibrated artifact.",
              file=sys.stderr)
        return 3

    rows = []
    tf_match_all = ar_match_all = 0
    tf_positions = 0
    for name, text in PROMPTS.items():
        # teacher-forced argmax per position, per cell
        pred = {}
        for cell in ("fp", "affine", "P8prod"):
            ids, _ = FQ.teacher_forced_argmax(model, tok, text, cell, masks)
            pred[cell] = ids
        n = min(len(pred["affine"]), len(pred["P8prod"]))
        eqCB = (pred["affine"][:n] == pred["P8prod"][:n])
        tf_agree_CB = 100.0 * eqCB.float().mean().item()
        # first teacher-forced divergence position (C vs B)
        div = int((~eqCB).nonzero()[0].item()) if (~eqCB).any() else -1
        tf_bitident_CB = bool(eqCB.all())
        tf_match_all += int(eqCB.sum().item()); tf_positions += n

        # autoregressive greedy strings (secondary, noisy)
        gen = {c: FQ.generate(model, tok, text, c, masks, max_new_tokens=args.gen_tokens)
               for c in ("affine", "P8prod")}
        ar_exact_CB = gen["affine"] == gen["P8prod"]
        # common-prefix length in characters (proxy; token-level needs ids)
        cp = 0
        for a, b in zip(gen["affine"], gen["P8prod"]):
            if a != b:
                break
            cp += 1
        ar_match_all += int(ar_exact_CB)

        rows.append({
            "prompt": name, "n_positions": n,
            "TF_agree_C_vs_B_pct": round(tf_agree_CB, 3),
            "TF_bit_identical_C_vs_B": tf_bitident_CB,
            "TF_first_divergence_pos": div,
            "AR_greedy_exact_C_vs_B": ar_exact_CB,
            "AR_common_prefix_chars": cp,
        })
        print(f"  {name:12} TF C-vs-B={tf_agree_CB:6.2f}% (bitident={tf_bitident_CB}, "
              f"1st div @{div})  AR exact={ar_exact_CB} (prefix {cp} chars)")

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print(f"\nwrote {args.out}")
    print(f"SUMMARY C(P8prod) vs B(affine): teacher-forced token agreement = "
          f"{100.0*tf_match_all/max(1,tf_positions):.3f}% over {tf_positions} positions; "
          f"autoregressive-exact on {ar_match_all}/{len(rows)} prompts.")
    print("NOTE: teacher-forced is the stable signal. Autoregressive drift is expected for ANY KV "
          "quantization (even B vs full-BF16), so it is not a parity criterion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
