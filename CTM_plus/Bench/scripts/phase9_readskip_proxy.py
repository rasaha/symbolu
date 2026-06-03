#!/usr/bin/env python3
"""Phase 9 — intra-sequence READ-SKIP proxy via sliding-window attention.

WHY: the Step-0 read-skip prize (a single long sequence skipping its own cold
middle) is NOT implemented (see PHASE9_READSKIP_NOT_IMPLEMENTED.md) and would be
a kernel build. Before building, DE-RISK the decision cheaply: a model with
sliding-window attention (SWA) already does intra-sequence read-skip (a FIXED
StreamingLLM pattern — attend only the last W tokens, physically skip older
reads). So toggling SWA on/off on the SAME model, on a long needle-in-haystack,
measures Step-0's two IFs WITHOUT building anything:

  (1) THROUGHPUT: does read-skip (SWA on) decode faster at long context than full
      attention (SWA off)? SWA caps per-step reads at W, so its decode tps should
      stay high as context grows; full attention's tps drops.
  (2) QUALITY (the H2O risk): a needle older than W tokens is UNREADABLE under
      SWA -> retrieval dies for early/mid depths. This quantifies what read-skip
      costs in quality. A needle at depth-fraction d in an L-token context sits
      ~(1-d)*L tokens from the end, so it is inside the window iff (1-d)*L <= W,
      i.e. d >= 1 - W/L.

This is a PROXY: SWA is a fixed window, not attention-guided (real read-skip
would keep sinks + high-attention too). If even this fixed proxy loses too much
quality OR shows no throughput win, the attention-guided kernel is not worth
building. If it wins throughput AND the quality cliff is only for deep needles
(which sinks+high-attention retention would rescue), that justifies the build.

Reuses the locked needle item builder + classifier from phase6k12_hard_needle.

Usage (on the GPU pod):
  # $0 CPU self-test (no model):
  python phase9_readskip_proxy.py --selftest
  # cheap preflight — confirm the SWA toggle actually takes effect (~$0.05):
  python phase9_readskip_proxy.py --model mistralai/Mistral-7B-Instruct-v0.1 \
      --sliding-window 4096 --check-window
  # one cell (run twice: window on, then off=0):
  python phase9_readskip_proxy.py --model mistralai/Mistral-7B-Instruct-v0.1 \
      --sliding-window 4096 --context-tokens 16000 --depths 0.1,0.5,0.9 \
      --items 4 --out swa_on.json
  python phase9_readskip_proxy.py --model mistralai/Mistral-7B-Instruct-v0.1 \
      --sliding-window 0 --context-tokens 16000 --depths 0.1,0.5,0.9 \
      --items 4 --out swa_off.json
  # (phase9_readskip_proxy.sh runs both cells + combines the report.)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Reuse the locked needle building blocks (stdlib-only at import time).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase6k12_hard_needle import _code, _filler, classify  # noqa: E402


def build_depth_item(context_tokens: int, depth_frac: float, rng):
    """A single-needle haystack with the needle at a CONTROLLED depth.

    Returns (prompt, expected, distractors, mode). depth_frac in [0,1]: 0.0 =
    needle at the very start (oldest, first to fall outside an SWA window),
    1.0 = needle just before the question (newest, always inside the window).
    ~12 tokens/filler-sentence.
    """
    _EST = 12
    total_sents = max(30, context_tokens // _EST)
    before = max(0, int(round(depth_frac * total_sents)))
    after = max(0, total_sents - before)
    code = _code(rng)
    label = "ALPHA"
    needle = f"The access code for section {label} is {code}."
    body = f"{_filler(before)} {needle} {_filler(after)}"
    q = (f"\n\nQuestion: What is the access code for section {label}? "
         f"Answer with only the code.")
    return body + q, code, [], "multi"


def _effective_sliding_window(llm) -> object:
    """Best-effort read of the window the engine actually applied — so the
    operator can confirm the override TOOK before spending on a full run."""
    cfg = None
    for path in ("llm_engine.model_config", "engine.model_config"):
        obj = llm
        try:
            for attr in path.split("."):
                obj = getattr(obj, attr)
            cfg = obj
            break
        except AttributeError:
            continue
    if cfg is None:
        return "unknown"
    for getter in ("get_sliding_window",):
        if hasattr(cfg, getter):
            try:
                return getattr(cfg, getter)()
            except Exception:
                pass
    hf = getattr(cfg, "hf_config", None)
    return getattr(hf, "sliding_window", "unknown") if hf else "unknown"


def run_cell(args) -> int:
    from vllm import LLM, SamplingParams  # GPU-only import

    # sliding_window override: >0 forces a window (read-skip ON); 0/negative
    # forces FULL attention (read-skip OFF) by setting it null.
    sw = args.sliding_window
    hf_overrides = {"sliding_window": (sw if sw and sw > 0 else None)}

    llm = LLM(
        model=args.model,
        max_model_len=args.max_model_len,
        enforce_eager=True,
        gpu_memory_utilization=args.gpu_util,
        hf_overrides=hf_overrides,
    )
    effective = _effective_sliding_window(llm)
    print(f"[proxy] model={args.model} requested_sliding_window={sw} "
          f"effective_sliding_window={effective}", flush=True)
    if args.check_window:
        print("[proxy] --check-window: toggle confirmed; not generating. "
              "Compare effective_sliding_window for the on vs off invocations "
              "BEFORE trusting the full run.", flush=True)
        return 0
    if sw and sw > 0 and effective in (None, "unknown", 0):
        print("[proxy] WARNING: requested a window but the engine reports "
              f"{effective!r} — the override may not have taken (model may not "
              "support SWA in this vLLM build). Results would be invalid.",
              flush=True)

    import random
    rng = random.Random(args.seed)
    sp = SamplingParams(temperature=0.0, max_tokens=args.max_gen)

    # The model is an INSTRUCT model — feed it via its chat template, or it
    # behaves like a base completion model and emits ~nothing (the bug that made
    # the first run score 0/4 even at full attention / depth 0.95). Fall back to
    # a Mistral [INST] wrapper if the tokenizer exposes no template.
    tok = llm.get_tokenizer()

    def _wrap(prompt: str) -> str:
        try:
            return tok.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False, add_generation_prompt=True)
        except Exception:
            return f"[INST] {prompt} [/INST]"

    if args.sanity:
        # Cheap (~30s) harness validity check: a SHORT-context needle right
        # before the question MUST be retrieved, or the elicitation is broken
        # (independent of read-skip). Prints the raw answer so you can eyeball it.
        prompt, expected, distractors, mode = build_depth_item(800, 0.95, rng)
        out = llm.generate([_wrap(prompt)], sp)
        text = out[0].outputs[0].text
        verdict = classify(text, expected, distractors, mode)
        print(f"[proxy][sanity] expected={expected!r} got={text[:80]!r} -> {verdict}",
              flush=True)
        print("[proxy][sanity] " + ("PASS — elicitation works; run the full proxy."
              if verdict == "HIT" else
              "FAIL — model isn't answering the needle; the quality cliff would be "
              "uninterpretable. Try a stronger instruct model or check formatting."),
              flush=True)
        return 0 if verdict == "HIT" else 3

    depths = [float(x) for x in args.depths.split(",") if x.strip()]
    per_depth = {}
    decode_tokens_total = 0
    decode_time_total = 0.0
    for d in depths:
        hits = 0
        n = args.items
        for _ in range(n):
            prompt, expected, distractors, mode = build_depth_item(
                args.context_tokens, d, rng)
            t0 = time.perf_counter()
            out = llm.generate([_wrap(prompt)], sp)
            dt = time.perf_counter() - t0
            text = out[0].outputs[0].text
            n_gen = len(out[0].outputs[0].token_ids)
            decode_tokens_total += n_gen
            decode_time_total += dt
            if classify(text, expected, distractors, mode) == "HIT":
                hits += 1
        # is this depth inside the window? (1-d)*L <= W
        inside = (sw and sw > 0 and (1.0 - d) * args.context_tokens <= sw)
        per_depth[f"{d:.2f}"] = {
            "hit_rate": round(hits / n, 3),
            "items": n,
            "needle_inside_window": bool(inside) if (sw and sw > 0) else None,
        }
        print(f"[proxy] depth={d:.2f} hit_rate={hits}/{n} "
              f"inside_window={per_depth[f'{d:.2f}']['needle_inside_window']}",
              flush=True)

    tps = (decode_tokens_total / decode_time_total) if decode_time_total else 0.0
    n_items = sum(v["items"] for v in per_depth.values()) or 1
    mean_gen = decode_tokens_total / n_items
    # A working baseline answers with a few tokens; ~1 token/gen means the model
    # emitted ~nothing (degenerate) -> hit rates are meaningless for this cell.
    degenerate = mean_gen < 3.0
    result = {
        "model": args.model,
        "requested_sliding_window": sw,
        "effective_sliding_window": effective if isinstance(effective, (int, type(None))) else str(effective),
        "read_skip": bool(sw and sw > 0),
        "context_tokens": args.context_tokens,
        "max_model_len": args.max_model_len,
        "decode_tps": round(tps, 2),
        "decode_tokens": decode_tokens_total,
        "mean_gen_tokens": round(mean_gen, 2),
        "degenerate_baseline": degenerate,
        "per_depth_hit_rate": per_depth,
    }
    if degenerate:
        print(f"[proxy] WARNING: mean_gen_tokens={mean_gen:.2f} (<3) — this cell is "
              "DEGENERATE (model emitted ~nothing). Hit rates are meaningless; the "
              "context is likely out-of-distribution for this model's attention "
              "(e.g. full attention beyond a sliding-window model's training "
              "length). Lower --context-tokens into the model's viable band.",
              flush=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(f"[proxy] wrote {out_path}\n{json.dumps(result, indent=2)}", flush=True)
    return 0


def _selftest() -> int:
    import random
    rng = random.Random(0)
    # Needle placement: depth 0.0 -> almost all filler AFTER the needle;
    # depth 1.0 -> almost all filler BEFORE it. The needle text is present.
    p0, exp0, _, _ = build_depth_item(3000, 0.0, rng)
    p1, exp1, _, _ = build_depth_item(3000, 1.0, rng)
    assert f"is {exp0}." in p0 and f"is {exp1}." in p1
    # depth 0.0 -> needle near the front; depth 1.0 -> needle near the end.
    assert p0.index("access code") < len(p0) * 0.5, "depth 0.0 should be early"
    assert p1.index("access code") > len(p1) * 0.5, "depth 1.0 should be late"
    # classifier still works on a trivial echo.
    assert classify(f"the code is {exp0}", exp0, [], "multi") == "HIT"
    assert classify("nope", exp0, [], "multi") in ("MISS_K", "NEAR_V")
    # inside-window arithmetic: L=16000,W=4096 -> threshold d>=0.744.
    L, W = 16000, 4096
    assert (1 - 0.9) * L <= W and not ((1 - 0.5) * L <= W)
    print("phase9 read-skip proxy self-test: PASS")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="mistralai/Mistral-7B-Instruct-v0.1")
    ap.add_argument("--sliding-window", type=int, default=4096,
                    help=">0 forces a window (read-skip ON); 0/neg = full attention (OFF)")
    ap.add_argument("--context-tokens", type=int, default=16000)
    ap.add_argument("--depths", default="0.1,0.5,0.9")
    ap.add_argument("--items", type=int, default=4)
    ap.add_argument("--max-gen", type=int, default=32)
    ap.add_argument("--max-model-len", type=int, default=32768)
    ap.add_argument("--gpu-util", type=float, default=0.85)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="readskip_proxy.json")
    ap.add_argument("--check-window", action="store_true",
                    help="load the model + print the effective window, then exit (cheap toggle preflight)")
    ap.add_argument("--sanity", action="store_true",
                    help="one short-context depth-0.95 needle; must HIT or the "
                         "elicitation is broken (cheap harness-validity check)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    return run_cell(args)


if __name__ == "__main__":
    sys.exit(main())
