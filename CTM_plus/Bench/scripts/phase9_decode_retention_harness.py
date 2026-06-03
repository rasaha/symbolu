#!/usr/bin/env python3
"""Phase 9 — decode-time attention-guided RETENTION harness (quality gate).

Tests the ONE remaining bet for the read-skip kernel:
  Can decode-time attention-observed retention recover Needle/random-code quality
  (and preserve basic MMLU) while keeping only a SPARSE subset of historical KV?

This is a CORRECTNESS / quality-gate harness, NOT the optimized CUDA kernel.
It keeps the full KV cache and MASKS attention to dropped historical positions
(positions/rotary stay exact; inefficient but faithful — the spec's allowed
"mask attention each step" path). Decide whether the kernel is worth building;
do not build it here.

WHY decode-time attention (and why prefill relevance was WRONG):
  v1 ranked context tokens by hidden-state cosine to the QUESTION. The answer is
  a RANDOM code the question never names, so the payload tokens scored low and
  were dropped — a structural flaw, not a test of the bet. The correct signal is
  the attention the GENERATED-token queries pay back into historical KV blocks:
  the model reveals which blocks it is actually retrieving from while it answers.

Policies compared (same KV budget):
  full_attention             — baseline, no dropping.
  recent_only                — recent window (+ BOS) only.
  sink_recent                — sink/instruction/BOS blocks + recent window.
  decode_attention_retention — sinks + recent + top-attended historical blocks
                               (+ neighbors), observed over the first
                               `observe_steps` generated tokens, EMA-refreshed.

MANDATORY per-case logging (so failures are diagnosable):
  needle_token_span, needle_block_ids, retained_block_ids, needle_retained,
  generated_text, hit. Without needle_retained we cannot tell selection failure
  from generation failure.

Decision rule (printed): GREEN / YELLOW / RED / INVALID — see README section.

Run (GPU pod):
  python phase9_decode_retention_harness.py --selftest                # CPU logic
  python phase9_decode_retention_harness.py --smoke                   # the deliverable smoke
  python phase9_decode_retention_harness.py --context-lens 4096,8192 \
      --depths 0.1,0.3,0.5,0.7,0.9,0.95 --seeds 4 --output-json out.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import re
import string
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ------------------------------------------------------------------ config ----


@dataclasses.dataclass
class Config:
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    dtype: str = "bfloat16"
    device: str = "cuda"
    block_size: int = 32
    sink_tokens: int = 256
    recent_tokens: int = 2048
    observe_steps: int = 8
    attention_budget_tokens: int = 2048
    neighbor_blocks: int = 1
    refresh_every: int = 16
    score_decay: float = 0.8
    max_new_tokens: int = 32


POLICIES = ("full_attention", "recent_only", "sink_recent",
            "decode_attention_retention")

# ------------------------------------------------------- synthetic tasks ------

_SECTIONS = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF"]


def random_code(rng: random.Random) -> str:
    """Hyphenated random code, e.g. 'Q7M-42X-L9P' — NOT semantically related to
    the question (the whole point: prefill relevance cannot find it)."""
    def seg(n):
        return "".join(rng.choice(string.ascii_uppercase + string.digits)
                       for _ in range(n))
    return f"{seg(3)}-{seg(3)}-{seg(3)}"


def _filler(n: int) -> str:
    return " ".join(
        f"Log entry {i}: nominal status, no action required."
        for i in range(n))


def build_needle_single(context_tokens: int, depth: float, rng: random.Random
                        ) -> Tuple[str, str, str]:
    """Single random-code needle at `depth`. Returns
    (user_content, expected_code, question_str)."""
    total = max(30, context_tokens // 11)            # ~11 tokens/filler sentence
    before = max(0, int(round(depth * total)))
    after = max(0, total - before)
    section = rng.choice(_SECTIONS)
    code = random_code(rng)
    needle = f"The access code for section {section} is {code}."
    question = (f"\n\nQuestion: What is the access code for section {section}? "
                f"Answer with only the code.")
    user = f"{_filler(before)} {needle} {_filler(after)}{question}"
    return user, code, question


def build_needle_multi(context_tokens: int, depth: float, rng: random.Random
                       ) -> Tuple[str, str, str]:
    """Three sections with distinct random codes at spread depths; ask ONE.
    Catches whether retention keeps the CORRECT payload (not merely any code)."""
    total = max(45, context_tokens // 11)
    sections = rng.sample(_SECTIONS, 3)
    codes = [random_code(rng) for _ in sections]
    want = rng.randrange(3)
    # place the asked needle at `depth`; the other two at fixed spread spots.
    depths = [0.2, 0.55, 0.85]
    depths[want] = depth
    order = sorted(range(3), key=lambda k: depths[k])
    parts, last = [], 0.0
    for k in order:
        gap = max(1, int((depths[k] - last) * total))
        parts.append(_filler(gap))
        parts.append(f"The access code for section {sections[k]} is {codes[k]}.")
        last = depths[k]
    parts.append(_filler(max(1, int((1.0 - last) * total))))
    question = (f"\n\nQuestion: What is the access code for section "
                f"{sections[want]}? Answer with only the code.")
    return " ".join(parts) + question, codes[want], question


_CODE_RE = re.compile(r"[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}")


def code_hit(generated: str, expected: str) -> bool:
    """Exact or normalized (case/whitespace-insensitive) code match."""
    g = generated.upper().replace(" ", "")
    if expected.upper() in g:
        return True
    return any(m.upper() == expected.upper() for m in _CODE_RE.findall(
        generated.upper()))

# -------------------------------------------------- pure retention logic ------


def select_retained_blocks(n_hist_blocks: int, block_score: List[float],
                           sink_blocks: set, recent_blocks: set,
                           budget_blocks: int, neighbor: int) -> set:
    """PURE (CPU-testable) block selection.

    pinned = sink ∪ recent ; from the rest take the top `budget_blocks` by score,
    then expand by ±neighbor. Returns the retained block-id set."""
    pinned = set(sink_blocks) | set(recent_blocks)
    candidates = [b for b in range(n_hist_blocks) if b not in pinned]
    candidates.sort(key=lambda b: block_score[b], reverse=True)
    chosen = set(candidates[:max(0, budget_blocks)])
    retained = set(pinned) | chosen
    for b in list(chosen):
        for nb in range(b - neighbor, b + neighbor + 1):
            if 0 <= nb < n_hist_blocks:
                retained.add(nb)
    return retained


def sink_block_set(cfg: Config) -> set:
    return set(range((cfg.sink_tokens + cfg.block_size - 1) // cfg.block_size))


def recent_block_set(cfg: Config, prompt_len: int) -> set:
    start_tok = max(0, prompt_len - cfg.recent_tokens)
    return set(range(start_tok // cfg.block_size,
                     (prompt_len - 1) // cfg.block_size + 1))


def needle_retained(needle_block_ids: List[int], retained: set) -> bool:
    return all(b in retained for b in needle_block_ids)

# ------------------------------------------------------- the GPU engine -------


class Engine:
    """HF-transformers decode loop with per-step attention masking. GPU-only."""

    def __init__(self, cfg: Config):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.cfg = cfg
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(cfg.model)
        dt = {"bfloat16": torch.bfloat16, "float16": torch.float16,
              "float32": torch.float32}[cfg.dtype]
        self.model = AutoModelForCausalLM.from_pretrained(
            cfg.model, torch_dtype=dt, attn_implementation="eager",
            device_map=cfg.device)
        self.model.eval()

    def _encode(self, user_content: str, expected: str):
        chat = self.tok.apply_chat_template(
            [{"role": "user", "content": user_content}],
            tokenize=False, add_generation_prompt=True)
        enc = self.tok(chat, return_offsets_mapping=True,
                       add_special_tokens=False)
        ids, offs = enc["input_ids"], enc["offset_mapping"]
        cstart = chat.find(expected)
        cend = cstart + len(expected)
        span = [i for i, (a, b) in enumerate(offs) if a < cend and b > cstart]
        return ids, (span[0], span[-1]) if span else (-1, -1), span

    def run_case(self, policy: str, user_content: str, expected: str,
                 task: str, context_len: int, depth: float, seed: int) -> dict:
        torch = self.torch
        cfg = self.cfg
        ids, span, span_idx = self._encode(user_content, expected)
        prompt_len = len(ids)
        bs = cfg.block_size
        n_hist_blocks = (prompt_len + bs - 1) // bs
        needle_block_ids = sorted({i // bs for i in span_idx})
        sinks = sink_block_set(cfg)
        recents = recent_block_set(cfg, prompt_len)
        budget_blocks = cfg.attention_budget_tokens // bs

        # historical attend mask over blocks; True = attended.
        def blocks_to_token_mask(retained: set):
            m = torch.zeros(prompt_len, dtype=torch.long)
            for p in range(prompt_len):
                if (p // bs) in retained:
                    m[p] = 1
            return m

        if policy == "full_attention":
            retained = set(range(n_hist_blocks))
        elif policy == "recent_only":
            retained = set(recents) | {0}                  # + BOS
        elif policy == "sink_recent":
            retained = set(sinks) | set(recents)
        else:                                              # decode_attention_retention
            retained = set(range(n_hist_blocks))           # observe with full first
        observe = (policy == "decode_attention_retention")

        device = next(self.model.parameters()).device
        input_ids = torch.tensor([ids], device=device)
        block_score = [0.0] * n_hist_blocks
        retained_final = set(retained)

        with torch.no_grad():
            out = self.model(input_ids, use_cache=True)
            cache = out.past_key_values
        cached_len = prompt_len
        next_tok = int(out.logits[0, -1].argmax())
        gen_ids = [next_tok]

        def hist_mask_for(retained_set):
            return blocks_to_token_mask(retained_set).to(device)

        eos = self.tok.eos_token_id
        for step in range(cfg.max_new_tokens - 1):
            if next_tok == eos:
                break
            need_attn = observe and (step < cfg.observe_steps
                                     or (cfg.refresh_every > 0
                                         and step % cfg.refresh_every == 0))
            use_retained = (retained if (observe and step < cfg.observe_steps)
                            else retained_final)
            hmask = hist_mask_for(set(range(n_hist_blocks))
                                  if need_attn else use_retained)
            gen_part = torch.ones(cached_len - prompt_len + 1,
                                  dtype=torch.long, device=device)
            attn_mask = torch.cat([hmask, gen_part]).unsqueeze(0)
            with torch.no_grad():
                out = self.model(
                    torch.tensor([[next_tok]], device=device),
                    past_key_values=cache, attention_mask=attn_mask,
                    use_cache=True, output_attentions=need_attn)
            cache = out.past_key_values
            cached_len += 1
            if need_attn:
                # aggregate attention mass into historical blocks (mean layers,
                # sum heads), EMA per the spec.
                new = [0.0] * n_hist_blocks
                for layer_attn in out.attentions:
                    a = layer_attn[0, :, -1, :prompt_len].float().sum(0)  # [prompt_len]
                    for p in range(prompt_len):
                        new[p // bs] += float(a[p])
                nl = max(1, len(out.attentions))
                new = [x / nl for x in new]
                d = cfg.score_decay
                block_score = [d * o + (1 - d) * n for o, n in
                               zip(block_score, new)]
                if step >= cfg.observe_steps - 1:
                    retained_final = select_retained_blocks(
                        n_hist_blocks, block_score, sinks, recents,
                        budget_blocks, cfg.neighbor_blocks)
            next_tok = int(out.logits[0, -1].argmax())
            gen_ids.append(next_tok)

        text = self.tok.decode(gen_ids, skip_special_tokens=True)
        ret = retained_final if observe else retained
        return {
            "task": task, "policy": policy, "context_len": context_len,
            "depth": depth, "seed": seed,
            "hit": code_hit(text, expected),
            "needle_retained": needle_retained(needle_block_ids, ret),
            "needle_token_span": list(span),
            "needle_block_ids": needle_block_ids,
            "retained_block_ids": sorted(ret)[:64] + (
                ["..."] if len(ret) > 64 else []),
            "n_retained_blocks": len(ret), "n_hist_blocks": n_hist_blocks,
            "generated_text": text[:200], "expected_answer": expected,
        }

    # ---- tiny MMLU-like regression smoke (catches catastrophic breakage) ----
    MCQ = [
        ("The capital of France is", {"A": "Paris", "B": "Rome",
         "C": "Berlin", "D": "Madrid"}, "A"),
        ("Water is chemically", {"A": "NaCl", "B": "H2O", "C": "CO2",
         "D": "O2"}, "B"),
        ("The largest planet in the Solar System is", {"A": "Earth",
         "B": "Mars", "C": "Jupiter", "D": "Venus"}, "C"),
        ("2 + 2 equals", {"A": "3", "B": "5", "C": "22", "D": "4"}, "D"),
        ("The author of 'Romeo and Juliet' is", {"A": "Shakespeare",
         "B": "Dickens", "C": "Twain", "D": "Homer"}, "A"),
        ("The chemical symbol for gold is", {"A": "Ag", "B": "Au",
         "C": "Gd", "D": "Go"}, "B"),
    ]

    def run_mmlu_smoke(self, policy: str) -> dict:
        torch = self.torch
        correct = 0
        for stem, opts, ans in self.MCQ:
            body = stem + "\n" + "\n".join(f"{k}) {v}" for k, v in opts.items())
            body += "\n\nAnswer with only the letter."
            r = self.run_case(policy, body, ans_letter := ans, "mmlu",
                              0, 0.0, 0)
            # for MMLU the prompt is short (< budget) so retention keeps all;
            # we just check the letter appears first.
            g = r["generated_text"].strip().upper()
            if g[:1] == ans_letter or f"{ans_letter})" in g or \
               opts[ans_letter].upper() in g:
                correct += 1
        return {"accuracy": round(correct / len(self.MCQ), 3),
                "n": len(self.MCQ)}

# --------------------------------------------------------- orchestration ------


def classify_decision(summary: dict) -> str:
    fa = summary.get("full_attention", {})
    dr = summary.get("decode_attention_retention", {})
    needle_fa = fa.get("needle_overall")
    needle_dr = dr.get("needle_overall")
    mmlu_fa = fa.get("mmlu_accuracy")
    mmlu_dr = dr.get("mmlu_accuracy")
    if needle_fa is None or needle_fa < 0.9:
        return ("INVALID — full_attention needle baseline not near-perfect "
                f"({needle_fa}); generation/harness suspect, not a read-skip result.")
    if needle_dr is None:
        return "INVALID — decode_attention_retention produced no needle result."
    # needle quality + mmlu within ~5-10% of full.
    nd = needle_fa - needle_dr
    md = (mmlu_fa - mmlu_dr) if (mmlu_fa is not None and mmlu_dr is not None) else 0.0
    if nd <= 0.10 and md <= 0.10:
        return (f"GREEN — decode_attention_retention within ~10% of full "
                f"(needle Δ={nd:.2f}, mmlu Δ={md:.2f}). Kernel worth building.")
    # did it at least RETAIN needles? distinguish selection vs generation failure.
    retain_rate = dr.get("needle_retained_rate")
    if retain_rate is not None and retain_rate >= 0.6 and needle_dr < needle_fa - 0.10:
        return (f"RED-ish — needles ARE retained ({retain_rate:.2f}) but answers "
                f"still fail (needle Δ={nd:.2f}): generation/attention-path failure, "
                "not selection. Investigate the masking path before parking.")
    if retain_rate is not None and retain_rate < 0.6:
        return (f"YELLOW/RED — selection retains needles only {retain_rate:.2f} of "
                f"the time (needle Δ={nd:.2f}). Tune block_size/observe_steps/"
                "budget/neighbors; if unmovable -> RED, park the kernel.")
    return (f"YELLOW — retention helps but is short of full (needle Δ={nd:.2f}, "
            "mmlu Δ={md:.2f}); tune before committing.")


def aggregate(results: List[dict], mmlu: Dict[str, dict]) -> dict:
    summary = {}
    for p in POLICIES:
        rs = [r for r in results if r["policy"] == p]
        needle = [r for r in rs if r["task"] in ("needle_random_code", "multi_needle")]
        hit = sum(r["hit"] for r in needle)
        ret = sum(r["needle_retained"] for r in needle)
        summary[p] = {
            "needle_overall": round(hit / len(needle), 3) if needle else None,
            "needle_retained_rate": round(ret / len(needle), 3) if needle else None,
            "mmlu_accuracy": mmlu.get(p, {}).get("accuracy"),
            "by_depth": {},
        }
        for r in needle:
            key = f"{r['task']}|ctx{r['context_len']}|d{r['depth']}"
            slot = summary[p]["by_depth"].setdefault(key, {"hit": 0, "n": 0,
                                                           "retained": 0})
            slot["hit"] += r["hit"]; slot["n"] += 1
            slot["retained"] += r["needle_retained"]
    return summary


def print_console(summary: dict, decision: str):
    print("\n" + "=" * 70)
    print("PHASE 9 — decode-time retention harness")
    print("=" * 70)
    for p in POLICIES:
        s = summary[p]
        print(f"\nPolicy: {p}")
        print(f"  Needle overall hit : {s['needle_overall']}")
        print(f"  Needle retained    : {s['needle_retained_rate']}")
        print(f"  MMLU smoke         : {s['mmlu_accuracy']}")
        for k, v in sorted(s["by_depth"].items()):
            print(f"    {k:<34} hit {v['hit']}/{v['n']}  "
                  f"retained {v['retained']}/{v['n']}")
    print("\nDECISION:", decision)


def run_harness(cfg: Config, context_lens, depths, seeds, tasks) -> dict:
    eng = Engine(cfg)
    results, errors = [], []
    for task in tasks:
        builder = (build_needle_single if task == "needle_random_code"
                   else build_needle_multi)
        for ctx in context_lens:
            for depth in depths:
                for seed in range(seeds):
                    rng = random.Random(hash((task, ctx, depth, seed)) & 0xffffffff)
                    user, code, _q = builder(ctx, depth, rng)
                    for policy in POLICIES:
                        try:
                            results.append(eng.run_case(
                                policy, user, code, task, ctx, depth, seed))
                        except Exception as e:  # one bad case must not kill the run
                            errors.append({"policy": policy, "task": task,
                                           "ctx": ctx, "depth": depth,
                                           "seed": seed, "error": repr(e)})
                            print(f"[harness] ERROR {policy} {task} ctx{ctx} "
                                  f"d{depth} s{seed}: {e}", flush=True)
    mmlu = {p: eng.run_mmlu_smoke(p) for p in POLICIES}
    summary = aggregate(results, mmlu)
    decision = classify_decision(summary)
    return {"model": cfg.model, "config": dataclasses.asdict(cfg),
            "results": results, "summary": summary, "errors": errors,
            "decision": decision}

# ---------------------------------------------------------------- selftest ----


def _selftest() -> int:
    cfg = Config(block_size=32, sink_tokens=64, recent_tokens=128,
                 attention_budget_tokens=64, neighbor_blocks=1)
    # sink blocks = first 64/32 = 2 blocks {0,1}.
    assert sink_block_set(cfg) == {0, 1}, sink_block_set(cfg)
    # recent over prompt_len=1000: last 128 tokens -> blocks 27..31.
    rb = recent_block_set(cfg, 1000)
    assert min(rb) == (1000 - 128) // 32 and max(rb) == (999) // 32, rb
    # selection: a high-score middle block must be retained (the v1 failure mode
    # this whole harness exists to fix).
    n = 40
    score = [0.0] * n
    score[20] = 5.0
    ret = select_retained_blocks(n, score, {0, 1}, {38, 39}, budget_blocks=2,
                                 neighbor=1)
    assert 20 in ret, ("top-attended middle block must be retained", ret)
    assert {19, 21} <= ret, ("neighbors must be added", ret)
    assert {0, 1, 38, 39} <= ret, ("sinks+recent pinned", ret)
    # recent_only does NOT retain the middle needle; retention DOES.
    assert not needle_retained([20], {0} | {38, 39})
    assert needle_retained([20], ret)
    # code hit: exact + normalized + within text.
    assert code_hit("The code is Q7M-42X-L9P.", "Q7M-42X-L9P")
    assert code_hit("answer: q7m-42x-l9p", "Q7M-42X-L9P")
    assert not code_hit("ABC-123-XYZ", "Q7M-42X-L9P")
    # builders place the needle and the code is present + unique-ish.
    u, c, q = build_needle_single(2000, 0.3, random.Random(1))
    assert f"is {c}." in u and _CODE_RE.search(c) and "Question:" in q
    um, cm, _ = build_needle_multi(2000, 0.9, random.Random(2))
    assert um.count(cm) == 1 and _CODE_RE.search(cm)
    # decision-rule wiring.
    assert classify_decision({"full_attention": {"needle_overall": 0.5},
                              "decode_attention_retention": {}}).startswith("INVALID")
    assert classify_decision(
        {"full_attention": {"needle_overall": 1.0, "mmlu_accuracy": 1.0},
         "decode_attention_retention": {"needle_overall": 0.95,
                                        "needle_retained_rate": 1.0,
                                        "mmlu_accuracy": 1.0}}).startswith("GREEN")
    print("decode retention harness self-test: PASS")
    return 0

# -------------------------------------------------------------------- main ----


def _cfg_from_args(a) -> Config:
    return Config(model=a.model, dtype=a.dtype, device=a.device,
                  block_size=a.block_size, sink_tokens=a.sink_tokens,
                  recent_tokens=a.recent_tokens, observe_steps=a.observe_steps,
                  attention_budget_tokens=a.attention_budget_tokens,
                  neighbor_blocks=a.neighbor_blocks,
                  refresh_every=a.refresh_every, score_decay=a.score_decay,
                  max_new_tokens=a.max_new_tokens)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--block-size", type=int, default=32)
    ap.add_argument("--sink-tokens", type=int, default=256)
    ap.add_argument("--recent-tokens", type=int, default=2048)
    ap.add_argument("--observe-steps", type=int, default=8)
    ap.add_argument("--attention-budget-tokens", type=int, default=2048)
    ap.add_argument("--neighbor-blocks", type=int, default=1)
    ap.add_argument("--refresh-every", type=int, default=16)
    ap.add_argument("--score-decay", type=float, default=0.8)
    ap.add_argument("--max-new-tokens", type=int, default=32)
    ap.add_argument("--context-lens", default="4096,8192")
    ap.add_argument("--depths", default="0.10,0.30,0.50,0.70,0.90,0.95")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--tasks", default="needle_random_code,multi_needle")
    ap.add_argument("--output-json", default="phase9_decode_retention.json")
    ap.add_argument("--smoke", action="store_true",
                    help="small smoke: ctx 4096, depths 0.1/0.5/0.9, 2 seeds")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    cfg = _cfg_from_args(a)
    if a.smoke:
        ctx, depths, seeds = [4096], [0.10, 0.50, 0.90], 2
        tasks = ["needle_random_code"]
    else:
        ctx = [int(x) for x in a.context_lens.split(",") if x.strip()]
        depths = [float(x) for x in a.depths.split(",") if x.strip()]
        seeds = a.seeds
        tasks = [t for t in a.tasks.split(",") if t.strip()]
    out = run_harness(cfg, ctx, depths, seeds, tasks)
    Path(a.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output_json).write_text(json.dumps(out, indent=2))
    print_console(out["summary"], out["decision"])
    print(f"\nwrote {a.output_json}  ({len(out['results'])} cases, "
          f"{len(out['errors'])} errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
