"""Cross-stack KV-quant quality client over an OpenAI-compatible endpoint.

Runs the SAME needle / hard-needle prompt set at temperature 0 against ANY
server (SAW-INT4's SGLang, int4_protected's vLLM, a bf16 reference) and reports:
  * needle and HARD-needle retrieval accuracy (the tail where int4_protected's
    protected channels are supposed to matter)
  * greedy agreement vs a reference run (exact-match + char-prefix)
  * tokens/sec
This is the decisive QUALITY-EDGE vs DOMINATED test, comparable across the two
methods' different serving frameworks.

`run` needs `openai` + a live server (GPU). Prompt-gen + scoring + compare are
pure-stdlib and CPU-testable via an injected mock generator.

Workflow (on the pod):
  # one run per method, each against its own server, SAME --seed:
  python -m ndol.experiments.openai_kv_eval run --base-url http://127.0.0.1:30000/v1 \
      --model Qwen/Qwen2.5-7B-Instruct --label bdr --out /workspace/run_bdr.jsonl
  # (repeat: bf16, int4, int4_protected against their endpoints, same --seed)
  python -m ndol.experiments.openai_kv_eval compare --runs /workspace/run_bf16.jsonl,... --ref bf16
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
from typing import Callable, Optional

_SUBJ = ["The committee", "A sensor array", "The field archive", "The cooling unit",
         "A courier drone", "The audit ledger", "The orbital probe", "A relay node"]
_VERB = ["recorded", "transmitted", "recalibrated", "rejected", "buffered", "encrypted"]
_OBJ = ["a fragment", "the residual", "an anomaly", "the manifest", "a checksum", "the payload"]


def _filler(rng: random.Random, n: int) -> str:
    return " ".join(f"{rng.choice(_SUBJ)} {rng.choice(_VERB)} {rng.choice(_OBJ)} "
                    f"#{rng.randint(100, 999)} at stage {i}." for i in range(n))


def make_prompts(n_needle: int = 20, n_hard: int = 20, ctx_sentences: int = 120, seed: int = 0) -> list[dict]:
    """needle = one planted code + direct query; hard_needle = several distractor codes
    scattered through a long context, query targets ONE by attribute (long-distance
    retrieval + distractors — the failure mode cheap quant noise causes)."""
    rng = random.Random(seed)
    out = []
    for i in range(n_needle):
        code = rng.randint(10000, 99999)
        body = f"{_filler(rng, ctx_sentences // 2)} The secret access code is {code}. {_filler(rng, ctx_sentences // 2)}"
        out.append({"id": f"needle_{i}", "kind": "needle", "answer": str(code),
                    "prompt": f"{body}\n\nQuestion: what is the secret access code? Reply with only the number."})
    for i in range(n_hard):
        tags = ["RED", "BLUE", "GREEN", "AMBER", "SILVER"]
        rng.shuffle(tags)
        codes = {t: rng.randint(10000, 99999) for t in tags}
        target = rng.choice(tags)
        chunks = []
        for t in tags:
            chunks.append(_filler(rng, max(1, ctx_sentences // len(tags))))
            chunks.append(f"The {t} code is {codes[t]}.")
        out.append({"id": f"hard_{i}", "kind": "hard_needle", "answer": str(codes[target]),
                    "prompt": " ".join(chunks) + f"\n\nQuestion: what is the {target} code? Reply with only the number."})
    return out


# --------------------------- run against an endpoint ------------------------ #
def _openai_generate(base_url: str, model: str, max_tokens: int) -> Callable[[str], tuple[str, int]]:
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key="dummy")

    def g(prompt: str) -> tuple[str, int]:
        r = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=max_tokens)
        txt = r.choices[0].message.content or ""
        n = r.usage.completion_tokens if getattr(r, "usage", None) else len(txt.split())
        return txt, n

    return g


def run_endpoint(prompts: list[dict], *, label: str, generate: Callable[[str], tuple[str, int]],
                 out_path: Optional[str] = None) -> list[dict]:
    recs = []
    for p in prompts:
        t0 = time.time()
        txt, n_tok = generate(p["prompt"])
        recs.append({"id": p["id"], "kind": p["kind"], "answer": p["answer"], "label": label,
                     "output": txt, "n_out_tokens": n_tok, "latency_s": time.time() - t0})
    if out_path:
        with open(out_path, "w") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
    return recs


# --------------------------- scoring + comparison --------------------------- #
def _hit(rec: dict) -> bool:
    return rec["answer"] in (rec.get("output") or "")


def score(recs: list[dict]) -> dict:
    out = {}
    for k in ("needle", "hard_needle"):
        sub = [r for r in recs if r["kind"] == k]
        out[k] = (sum(_hit(r) for r in sub) / len(sub)) if sub else float("nan")
    toks = sum(r.get("n_out_tokens", 0) for r in recs)
    lat = sum(r.get("latency_s", 0.0) for r in recs)
    out["tokens_per_s"] = (toks / lat) if lat > 0 else float("nan")
    return out


def _prefix_ratio(a: str, b: str) -> float:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n / max(1, max(len(a), len(b)))


def agreement(recs: list[dict], ref: list[dict]) -> dict:
    refmap = {r["id"]: (r.get("output") or "") for r in ref}
    exact, pref = [], []
    for r in recs:
        if r["id"] not in refmap:
            continue
        o, ro = (r.get("output") or ""), refmap[r["id"]]
        exact.append(1.0 if o == ro else 0.0)
        pref.append(_prefix_ratio(o, ro))
    return {"exact_match": statistics.mean(exact) if exact else float("nan"),
            "char_prefix": statistics.mean(pref) if pref else float("nan")}


def load_run(path: str) -> list[dict]:
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def compare(runs: dict[str, list[dict]], ref_label: str) -> dict:
    ref = runs[ref_label]
    rows = {}
    for label, recs in runs.items():
        s = score(recs)
        a = agreement(recs, ref)
        rows[label] = {**s, "agree_exact": a["exact_match"], "agree_prefix": a["char_prefix"]}
    return rows


def _verdict(rows: dict) -> str:
    # decision heuristic on QUALITY only (memory/throughput judged separately in the doc).
    saw = next((k for k in rows if k.lower() in ("bdr", "saw", "saw-int4")), None)
    prot = next((k for k in rows if "prot" in k.lower() or "kvpro" in k.lower()), None)
    if not (saw and prot):
        return "need both an int4_protected and a SAW/BDR run labeled to decide"
    d = rows[prot]["hard_needle"] - rows[saw]["hard_needle"]
    if d >= 0.05:
        return (f"QUALITY-EDGE (quality only): int4_protected hard-needle +{d:.2f} over SAW — "
                "this is the tail edge; weigh against SAW's ~2× memory advantage.")
    if d <= -0.05:
        return "SAW ahead on hard-needle too → with its memory win, leans DOMINATED."
    return ("PARITY on hard-needle → quality is a wash; SAW's ~2× lower memory + serving-native "
            "kernel → leans DOMINATED. (Confirm memory + throughput per the protocol.)")


# ----------------------------------- CLI ------------------------------------ #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cross-stack KV-quant quality client (needle/hard-needle/agreement)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the prompt set against one OpenAI endpoint")
    r.add_argument("--base-url", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--label", required=True, help="method label, e.g. bf16 / int4 / int4_protected / bdr")
    r.add_argument("--out", required=True)
    r.add_argument("--n-needle", type=int, default=20)
    r.add_argument("--n-hard", type=int, default=20)
    r.add_argument("--ctx-sentences", type=int, default=120)
    r.add_argument("--max-tokens", type=int, default=64)
    r.add_argument("--seed", type=int, default=0)

    c = sub.add_parser("compare", help="compare runs; report quality table + verdict")
    c.add_argument("--runs", required=True, help="comma list of run jsonl files")
    c.add_argument("--ref", default="bf16", help="reference label for greedy agreement")

    args = ap.parse_args(argv)

    if args.cmd == "run":
        prompts = make_prompts(args.n_needle, args.n_hard, args.ctx_sentences, args.seed)
        gen = _openai_generate(args.base_url, args.model, args.max_tokens)
        recs = run_endpoint(prompts, label=args.label, generate=gen, out_path=args.out)
        s = score(recs)
        print(f"[{args.label}] needle={s['needle']:.3f} hard_needle={s['hard_needle']:.3f} "
              f"tok/s={s['tokens_per_s']:.1f}  ({len(recs)} prompts) → {args.out}")
        return 0

    runs = {}
    for path in args.runs.split(","):
        recs = load_run(path.strip())
        runs[recs[0]["label"]] = recs
    rows = compare(runs, args.ref)
    print(f"{'method':<16}{'needle':>8}{'hard':>8}{'agree_x':>9}{'agree_pfx':>11}{'tok/s':>9}")
    for label, m in rows.items():
        print(f"{label:<16}{m['needle']:>8.3f}{m['hard_needle']:>8.3f}"
              f"{m['agree_exact']:>9.3f}{m['agree_prefix']:>11.3f}{m['tokens_per_s']:>9.1f}")
    print(f"\n  QUALITY verdict: {_verdict(rows)}")
    print("  (Memory + throughput decided separately — see docs/SAW_INT4_QWEN_HEADTOHEAD_RESULTS.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
