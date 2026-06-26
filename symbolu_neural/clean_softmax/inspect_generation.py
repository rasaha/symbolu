"""Determine which Symbol-U patent algorithms actually participate in generation.

NOT a quality/accuracy/benchmark test. The only goal: for each patent algorithm,
decide whether it is connected, executed, changes hidden states, changes logits,
changes the generated tokens, or is an effective no-op / not connected.

Method:
1. Trace one instrumented forward over the clean_softmax `full` model: record
   per-module execution order, input/output shapes, and whether each module
   changes the hidden state (residual L2) and the logits (vs module-off).
2. Reference autoregressive generation with fixed (prompt, seed, temp, top_k,
   top_p). Then ABLATE one module at a time (forward-time pass-through / nulled
   entropy) and regenerate with identical settings; diff the token sequences.
3. Classify every listed patent algorithm (including those not wired into this
   pipeline) and print counts + the final answer.

Run (after training a `full` checkpoint, see README):
    python -m symbolu_neural.clean_softmax.inspect_generation --ckpt runs/clean/full/ckpt.pt
"""
from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional, Set

import torch
import torch.nn.functional as F

from .generate import load_checkpoint, _filter_logits
from .augment import TypedHeadBank


# --------------------------------------------------------------------------- #
# Instrumented forward that mirrors SymbolUSoftmaxModel.forward exactly, but
# supports per-module ablation and records a trace on the first call.
# --------------------------------------------------------------------------- #
def traced_forward(model, ids: torch.Tensor, disabled: Set[str],
                   trace: Optional[List[dict]] = None) -> torch.Tensor:
    cfg = model.cfg

    def rec(name, executed, x_in, x_out, hid_change=None):
        if trace is not None:
            trace.append({
                "module": name, "executed": executed,
                "in_shape": tuple(x_in.shape) if x_in is not None else None,
                "out_shape": tuple(x_out.shape) if x_out is not None else None,
                "hidden_change_l2": (None if hid_change is None else round(hid_change, 6)),
            })

    h = model.lm.hidden(ids)
    rec("backbone_softmax", True, ids, h)

    if getattr(cfg, "extra_plain_block", False) and hasattr(model, "extra_block"):
        h2 = model.extra_block(h); rec("extra_plain_block(control)", True, h, h2,
                                       (h2 - h).norm().item()); h = h2

    ent = None
    if cfg.typed_heads and hasattr(model, "heads"):
        if "typed_heads" in disabled:
            rec("typed_heads(Vritti/Aspect/Guna/Kosha)", False, h, h)
            ent = torch.zeros(h.shape[0], h.shape[1], 3, device=h.device)
        else:
            tout = model.heads(h)
            ent = TypedHeadBank.entropies(tout)
            rec("typed_heads(Vritti/Aspect/Guna/Kosha)", True, h, tout["log_p_v"])
        if "entropy" in disabled:
            ent = torch.zeros_like(ent)
            rec("entropy_calc", False, h, ent)
        else:
            rec("entropy_calc", True, h, ent)

    if cfg.entropy_refine and hasattr(model, "refine") and ent is not None:
        if "refine" in disabled:
            rec("recursive_refinement", False, h, h, 0.0)
        else:
            h2, _ = model.refine(h, ent)
            rec("recursive_refinement", True, h, h2, (h2 - h).norm().item()); h = h2

    if cfg.memory and hasattr(model, "memory") and ent is not None:
        if "memory" in disabled:
            rec("deferred_insight_memory", False, h, h, 0.0)
        else:
            h2, _ = model.memory(h, ent)
            rec("deferred_insight_memory", True, h, h2, (h2 - h).norm().item()); h = h2

    return model.lm.logits(h)


@torch.no_grad()
def gen_tokens(model, tok, disabled: Set[str], prompt: str, n: int,
               temperature: float, top_k: int, top_p: float, seed: int) -> List[int]:
    g = torch.Generator().manual_seed(seed)
    block = model.cfg.backbone.max_seq
    ids = tok.encode(prompt).unsqueeze(0)
    if ids.numel() == 0:
        ids = torch.zeros(1, 1, dtype=torch.long)
    for _ in range(n):
        logits = traced_forward(model, ids[:, -block:], disabled)[0, -1]
        if temperature <= 0:
            nxt = logits.argmax().view(1, 1)
        else:
            probs = _filter_logits(logits / temperature, top_k, top_p).softmax(-1)
            nxt = torch.multinomial(probs, 1, generator=g).view(1, 1)
        ids = torch.cat([ids, nxt], dim=1)
    return ids[0].tolist()


# Patent-algorithm registry. `wired` flags whether it exists in THIS pipeline.
# `ablate` is the disabled-set key (None => cannot be ablated because not wired).
REGISTRY = [
    ("syllable/phoneme preprocessing", False, None),
    ("Vritti head", True, "typed_heads"),
    ("Aspect head", True, "typed_heads"),
    ("Guna head", True, "typed_heads"),
    ("Kosha head", True, "typed_heads"),
    ("Context-Vritti coupling", False, None),
    ("Entropy calculation", True, "entropy"),
    ("Entropy modulation (a'/b'/g')", False, None),
    ("Recursive refinement", True, "refine"),
    ("Resonance coefficient (lambda_res)", False, None),
    ("Stitching", False, None),
    ("Deferred Insight memory", True, "memory"),
    ("Experience anchors", False, None),
    ("Mirror logic", False, None),     # only a flag upstream; no op here
    ("DHA / delivery", False, None),
    ("Governance gates", False, None),
    ("Safety boundary", False, None),
    ("Personalization", False, None),
    ("Multimodal fusion", False, None),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--prompt", default="The model ")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--top-p", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    model, tok, ablation = load_checkpoint(args.ckpt)
    gp = dict(prompt=args.prompt, n=args.n, temperature=args.temperature,
              top_k=args.top_k, top_p=args.top_p, seed=args.seed)

    # ---- 1) single-forward trace (execution order, shapes, hidden change) ----
    ids = tok.encode(args.prompt).unsqueeze(0)
    if ids.numel() == 0:
        ids = torch.zeros(1, 1, dtype=torch.long)
    trace: List[dict] = []
    base_logits = traced_forward(model, ids, set(), trace)
    print(f"checkpoint={args.ckpt}  ablation={ablation}")
    print("\n--- execution trace (one forward) ---")
    print(f"{'order':>5} {'module':40s} {'exec':>5} {'in_shape':>16} {'out_shape':>16} {'Δhidden_L2':>11}")
    for i, t in enumerate(trace):
        print(f"{i:5d} {t['module']:40s} {str(t['executed']):>5} "
              f"{str(t['in_shape']):>16} {str(t['out_shape']):>16} "
              f"{('' if t['hidden_change_l2'] is None else t['hidden_change_l2']):>11}")

    # ---- refinement diagnostics (halting prob, steps, residual norms, gate) ----
    if getattr(model.cfg, "entropy_refine", False) and hasattr(model, "refine"):
        with torch.no_grad():
            h0 = model.lm.hidden(ids)
            ent0 = TypedHeadBank.entropies(model.heads(h0))
            _, diag = model.refine(h0, ent0)
        print("\n--- recursive refinement diagnostics ---")
        for k in ("steps_used", "halt_p_mean", "gate_mean", "residual_pre_gate_norm",
                  "residual_post_gate_norm", "entropy_gate_mean"):
            v = diag[k]
            print(f"  {k:26s} = {float(v):.6f}")

    # thresholds: deltas below these are numerical noise / effective no-ops.
    HID_THRESH = 1e-3
    LOG_THRESH = 1e-4

    # logits-change per ablatable module (single teacher-forced forward)
    logit_change: Dict[str, float] = {}
    for key in ("typed_heads", "entropy", "refine", "memory"):
        lo = traced_forward(model, ids, {key})
        logit_change[key] = (base_logits - lo).abs().max().item()

    # ---- 2) reference generation + per-module ablation ----
    ref = gen_tokens(model, tok, set(), **gp)
    ref_txt = tok.decode(ref)
    print("\n--- reference generation ---")
    print(repr(ref_txt))

    abl_results: Dict[str, dict] = {}
    for key in ("typed_heads", "entropy", "refine", "memory"):
        toks = gen_tokens(model, tok, {key}, **gp)
        diffs = sum(1 for a, b in zip(ref, toks) if a != b)
        first = next((i for i, (a, b) in enumerate(zip(ref, toks)) if a != b), None)
        abl_results[key] = {"differing_positions": diffs, "first_divergence": first,
                            "text": tok.decode(toks)}
        print(f"\n[ablate {key}] differing_tokens={diffs}/{len(ref)} "
              f"first_div={first}  logitΔmax={logit_change[key]:.3e}")

    # ---- 3) per-algorithm table ----
    def status_for(name, wired, ablate):
        if not wired:
            if name == "Mirror logic":
                return ("No(flag only)", "No", "No", "No", "No", "PLACEHOLDER")
            return ("Yes(elsewhere)", "No", "No", "No", "No", "NOT CONNECTED")
        # wired:
        if ablate in ("typed_heads", "entropy"):           # sensor: gates, no direct hidden write
            changed = abl_results[ablate]["differing_positions"] > 0
            lc = logit_change[ablate] > LOG_THRESH
            st = "ACTIVE" if changed else ("PARTIALLY ACTIVE" if lc else "INACTIVE")
            return ("Yes", "Yes", "No", "Indirect" if lc else "No",
                    "Yes" if changed else "No", st)
        # actuator: refine / memory
        hid = any(t["module"].startswith(_disp(ablate)) and t["executed"]
                  and (t["hidden_change_l2"] or 0) > HID_THRESH for t in trace)
        changed = abl_results[ablate]["differing_positions"] > 0
        lc = logit_change[ablate] > LOG_THRESH
        # executed but no observable influence on tokens => INACTIVE (no-op)
        st = "ACTIVE" if changed else (
            "PARTIALLY ACTIVE" if (hid or lc) else "INACTIVE")
        return ("Yes", "Yes", "Yes" if hid else "No", "Yes" if lc else "No",
                "Yes" if changed else "No", st)

    def _disp(key):
        return {"refine": "recursive_refinement",
                "memory": "deferred_insight_memory"}[key]

    print("\n--- PER-ALGORITHM TABLE ---")
    hdr = ("Algorithm", "Impl", "Exec", "ΔHidden", "ΔLogits", "ΔOutput", "Status")
    print(f"{hdr[0]:36s}{hdr[1]:>14}{hdr[2]:>6}{hdr[3]:>9}{hdr[4]:>10}{hdr[5]:>9}  {hdr[6]}")
    counts = {"impl": 0, "exec": 0, "hid": 0, "log": 0, "out": 0,
              "placeholder": 0, "disconnected": 0}
    table = []
    for name, wired, ablate in REGISTRY:
        impl, ex, hid, log, out, st = status_for(name, wired, ablate)
        print(f"{name:36s}{impl:>14}{ex:>6}{hid:>9}{log:>10}{out:>9}  {st}")
        table.append({"algorithm": name, "implemented": impl, "executed": ex,
                      "changes_hidden": hid, "changes_logits": log,
                      "changes_output": out, "status": st})
        if wired:
            counts["impl"] += 1
            if ex == "Yes":
                counts["exec"] += 1
            if hid == "Yes":
                counts["hid"] += 1
            if log == "Yes":
                counts["log"] += 1
            if out == "Yes":
                counts["out"] += 1
        if st == "PLACEHOLDER":
            counts["placeholder"] += 1
        if st == "NOT CONNECTED":
            counts["disconnected"] += 1

    print("\n--- FINAL COUNTS ---")
    print(f"1. implemented (wired into this pipeline): {counts['impl']}")
    print(f"2. executed during generation            : {counts['exec']}")
    print(f"3. influence hidden states               : {counts['hid']}")
    print(f"4. influence logits                      : {counts['log']}")
    print(f"5. influence generated text              : {counts['out']}")
    print(f"6. placeholders                          : {counts['placeholder']}")
    print(f"7. disconnected                          : {counts['disconnected']}")
    alive = sum(1 for r in table if r["status"] in ("ACTIVE", "PARTIALLY ACTIVE"))
    truly = sum(1 for r in table if r["changes_output"] == "Yes")
    print(f"\nFINAL ANSWER: patent algorithms genuinely participating (ACTIVE/PARTIALLY "
          f"ACTIVE) = {alive}; of those that actually change generated tokens = {truly}.")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({"trace": trace, "logit_change": logit_change,
                       "ablations": abl_results, "table": table,
                       "counts": counts, "alive": alive, "changes_output": truly},
                      f, indent=2)
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()
