#!/usr/bin/env python3
"""Phase 9 — decode-time attention-guided RETENTION harness (quality gate).

Tests the ONE remaining bet for the read-skip kernel:
  Can decode-time attention-observed retention recover Needle/random-code quality
  (and preserve basic MMLU) while keeping only a SPARSE subset of historical KV?

CORRECTNESS / quality-gate harness, NOT the optimized CUDA kernel. Keeps the full
KV cache and MASKS attention to dropped historical positions (positions/rotary
exact; inefficient but faithful). Decide whether the kernel is worth building.

WHY decode-time attention (and why prefill relevance was WRONG):
  v1 ranked tokens by hidden-state cosine to the QUESTION. The answer is a RANDOM
  code the question never names, so payload tokens scored low and were dropped.
  Correct signal = attention the GENERATED-token queries pay back into historical
  KV blocks: the model reveals which blocks it is actually retrieving from.

BASELINE DISCIPLINE: retention is only evaluated once `full_attention` is
near-perfect (>= 0.95 on needle). Otherwise the run is INVALID — a wobbly
baseline can't judge a policy. Use --calibrate to stabilise the baseline first.

Run:
  python phase9_decode_retention_harness.py --selftest          # CPU logic
  python phase9_decode_retention_harness.py --calibrate         # baseline only, many seeds
  python phase9_decode_retention_harness.py --smoke             # all policies, small
  python phase9_decode_retention_harness.py --context-lens 4096 \
      --depths 0.10,0.30,0.50,0.70,0.90 --seeds 4 --output-json out.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import random
import re
import string
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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
    max_new_tokens: int = 24


POLICIES = ("full_attention", "recent_only", "sink_recent",
            "decode_attention_retention")
BASELINE_MIN = 0.95           # full_attention needle floor below which = INVALID

# ------------------------------------------------------- synthetic tasks ------

_SECTIONS = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF"]
# The payload must be ARBITRARY (so it isn't question-relevant -> prefill cosine
# can't find it) yet HIGHLY COPYABLE. A random 9-char code is NOT copyable: a 7B
# model mis-transcribes ~1 char in 6 even under full attention (calibration found
# 0.84), capping the baseline below the 0.95 floor and testing copy-fidelity, not
# retention. Real words are in-vocabulary and copied near-perfectly, so a 3-word
# passphrase keeps the payload arbitrary while making full attention near-perfect.
_WORDS = ["CRIMSON", "FALCON", "MEADOW", "GRANITE", "VELVET", "HARBOR", "COBALT",
          "EMBER", "WILLOW", "CIPHER", "LUNAR", "NOMAD", "QUARTZ", "RAVEN",
          "SAFFRON", "TUNDRA", "ZEPHYR", "ONYX", "MARBLE", "CEDAR", "THORN",
          "GLACIER", "COMET", "BASIL", "INDIGO", "WALNUT", "SIERRA", "MONSOON",
          "PEWTER", "BRAMBLE", "FJORD", "LICHEN", "KESTREL", "OBSIDIAN",
          "CINDER", "JUNIPER"]


def random_code(rng: random.Random) -> str:
    """Arbitrary, highly-copyable 3-word passphrase, e.g. 'CRIMSON-FALCON-MEADOW'.
    Arbitrary (not question-relevant) yet copied near-perfectly by the model, so
    the baseline measures RETENTION, not character-copy fidelity."""
    return "-".join(rng.sample(_WORDS, 3))


def _filler(n: int) -> str:
    return " ".join(f"Log entry {i}: nominal status, no action required."
                    for i in range(n))


def build_needle_single(context_tokens: int, depth: float, rng: random.Random):
    """Single random-code needle at `depth`, in an EXPLICIT record format so
    full attention is near-perfect. Returns (user, code, question, needle_text)."""
    total = max(30, context_tokens // 11)
    before = max(0, int(round(depth * total)))
    after = max(0, total - before)
    section = rng.choice(_SECTIONS)
    code = random_code(rng)
    needle = f"SECTION {section} ACCESS CODE: {code}"
    question = (f"\n\nReturn only the exact access code for SECTION {section}. "
                f"Do not include any other text.")
    user = (f"The context below contains one hidden access-code record.\n\n"
            f"{_filler(before)} {needle}. {_filler(after)}{question}")
    return user, code, question, needle


def build_needle_multi(context_tokens: int, depth: float, rng: random.Random):
    """Three sections, distinct codes; ask ONE. Catches whether retention keeps
    the CORRECT payload, not merely any code."""
    total = max(45, context_tokens // 11)
    sections = rng.sample(_SECTIONS, 3)
    codes = [random_code(rng) for _ in sections]
    want = rng.randrange(3)
    depths = [0.2, 0.55, 0.85]
    depths[want] = depth
    order = sorted(range(3), key=lambda k: depths[k])
    parts = ["The context below contains hidden access-code records."]
    last = 0.0
    for k in order:
        gap = max(1, int((depths[k] - last) * total))
        parts.append(_filler(gap))
        parts.append(f"SECTION {sections[k]} ACCESS CODE: {codes[k]}.")
        last = depths[k]
    parts.append(_filler(max(1, int((1.0 - last) * total))))
    question = (f"\n\nReturn only the exact access code for SECTION "
                f"{sections[want]}. Do not include any other text.")
    needle = f"SECTION {sections[want]} ACCESS CODE: {codes[want]}"
    return " ".join(parts) + question, codes[want], question, needle


_CODE_RE = re.compile(r"[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}")


def _alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def match_code(generated: str, expected: str) -> Tuple[bool, str, str]:
    """Robust code match. Returns (hit, reason, normalized_generated).
    reason in {exact, substring, code_regex, none}. Tolerant of surrounding
    quotes/punctuation/whitespace and hyphen-vs-space; logs WHICH rule matched."""
    g = generated.strip()
    stripped = g.strip(" \n\t\r\"'`.,:;()[]{}")
    norm_g = _alnum(generated)
    norm_e = _alnum(expected)
    if stripped.upper() == expected.upper():
        return True, "exact", stripped
    if norm_e and norm_e in norm_g:
        return True, "substring", g
    for m in _CODE_RE.findall(generated.upper()):
        if _alnum(m) == norm_e:
            return True, "code_regex", g
    return False, "none", g

# -------------------------------------------------- pure retention logic ------


def select_retained_blocks(n_hist_blocks: int, block_score: List[float],
                           sink_blocks: set, recent_blocks: set,
                           budget_blocks: int, neighbor: int) -> set:
    """PURE (CPU-testable). pinned = sink ∪ recent; take top `budget_blocks` of
    the rest by score; expand ±neighbor. Returns the retained block-id set."""
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
        self._newline_ids = {i for i in
                             (self.tok.encode("\n", add_special_tokens=False) or [])}

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
        return ids, span

    def run_case(self, policy: str, user_content: str, expected: str,
                 needle_text: str, task: str, context_len: int, depth: float,
                 seed: int) -> dict:
        torch = self.torch
        cfg = self.cfg
        ids, span_idx = self._encode(user_content, expected)
        prompt_len = len(ids)
        bs = cfg.block_size
        n_hist_blocks = (prompt_len + bs - 1) // bs
        needle_block_ids = sorted({i // bs for i in span_idx})
        sinks = sink_block_set(cfg)
        recents = recent_block_set(cfg, prompt_len)
        budget_blocks = cfg.attention_budget_tokens // bs

        def blocks_to_token_mask(retained: set):
            m = torch.zeros(prompt_len, dtype=torch.long)
            for p in range(prompt_len):
                if (p // bs) in retained:
                    m[p] = 1
            return m

        if policy == "full_attention":
            retained = set(range(n_hist_blocks))
        elif policy == "recent_only":
            retained = set(recents) | {0}
        elif policy == "sink_recent":
            retained = set(sinks) | set(recents)
        else:
            retained = set(range(n_hist_blocks))
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

        def hist_mask_for(rset):
            return blocks_to_token_mask(rset).to(device)

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
                out = self.model(torch.tensor([[next_tok]], device=device),
                                 past_key_values=cache, attention_mask=attn_mask,
                                 use_cache=True, output_attentions=need_attn)
            cache = out.past_key_values
            cached_len += 1
            if need_attn:
                new = [0.0] * n_hist_blocks
                for layer_attn in out.attentions:
                    a = layer_attn[0, :, -1, :prompt_len].float().sum(0)
                    for p in range(prompt_len):
                        new[p // bs] += float(a[p])
                nl = max(1, len(out.attentions))
                new = [x / nl for x in new]
                d = cfg.score_decay
                block_score = [d * o + (1 - d) * n
                               for o, n in zip(block_score, new)]
                if step >= cfg.observe_steps - 1:
                    retained_final = select_retained_blocks(
                        n_hist_blocks, block_score, sinks, recents,
                        budget_blocks, cfg.neighbor_blocks)
            next_tok = int(out.logits[0, -1].argmax())
            gen_ids.append(next_tok)
            if next_tok in self._newline_ids and len(gen_ids) > 1:
                break

        text = self.tok.decode(gen_ids, skip_special_tokens=True)
        ret = retained_final if observe else retained
        hit, reason, norm = match_code(text, expected)
        other = sorted({m for m in _CODE_RE.findall(text.upper())
                        if _alnum(m) != _alnum(expected)})
        return {
            "task": task, "policy": policy, "context_len": context_len,
            "depth": depth, "seed": seed, "hit": hit, "match_reason": reason,
            "needle_retained": needle_retained(needle_block_ids, ret),
            "prompt_len_tokens": prompt_len,
            "needle_text": needle_text,
            "expected_answer": expected,
            "generated_text": text[:200],
            "normalized_generated": norm[:120],
            "expected_in_generated": _alnum(expected) in _alnum(text),
            "other_code_like": other[:5],
            "needle_token_span": [span_idx[0], span_idx[-1]] if span_idx else [-1, -1],
            "needle_block_ids": needle_block_ids,
            "retained_block_ids": sorted(ret)[:64] + (["..."] if len(ret) > 64 else []),
            "n_retained_blocks": len(ret), "n_hist_blocks": n_hist_blocks,
        }

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
        correct = 0
        for stem, opts, ans in self.MCQ:
            body = stem + "\n" + "\n".join(f"{k}) {v}" for k, v in opts.items())
            body += "\n\nAnswer with only the letter."
            r = self.run_case(policy, body, ans, "", "mmlu", 0, 0.0, 0)
            g = r["generated_text"].strip().upper()
            if g[:1] == ans or f"{ans})" in g or opts[ans].upper() in g:
                correct += 1
        return {"accuracy": round(correct / len(self.MCQ), 3), "n": len(self.MCQ)}

# --------------------------------------------------------- orchestration ------


def classify_decision(summary: dict) -> str:
    fa = summary.get("full_attention", {})
    dr = summary.get("decode_attention_retention", {})
    needle_fa = fa.get("needle_overall")
    needle_dr = dr.get("needle_overall")
    mmlu_fa = fa.get("mmlu_accuracy")
    mmlu_dr = dr.get("mmlu_accuracy")
    if needle_fa is None or needle_fa < BASELINE_MIN:
        return (f"INVALID — full_attention needle baseline {needle_fa} < "
                f"{BASELINE_MIN}. Stabilise the baseline (--calibrate) BEFORE "
                "judging retention; a wobbly yardstick can't evaluate a policy.")
    if needle_dr is None:
        return "INVALID — decode_attention_retention produced no needle result."
    nd = needle_fa - needle_dr
    md = (mmlu_fa - mmlu_dr) if (mmlu_fa is not None and mmlu_dr is not None) else 0.0
    if nd <= 0.10 and md <= 0.10:
        return (f"GREEN — decode_attention_retention within ~10% of full "
                f"(needle Δ={nd:.2f}, mmlu Δ={md:.2f}). Kernel worth building.")
    retain_rate = dr.get("needle_retained_rate")
    if retain_rate is not None and retain_rate >= 0.6 and nd > 0.10:
        return (f"RED-ish — needles ARE retained ({retain_rate:.2f}) but answers "
                f"still fail (needle Δ={nd:.2f}): generation/attention-path issue, "
                "NOT selection. Fix the masked-decode path before parking.")
    if retain_rate is not None and retain_rate < 0.6:
        return (f"YELLOW/RED — selection keeps needles only {retain_rate:.2f} of "
                f"the time (needle Δ={nd:.2f}). Tune block_size/observe_steps/"
                "budget/neighbors; if unmovable -> RED, park the kernel.")
    return (f"YELLOW — retention helps but short of full (needle Δ={nd:.2f}, "
            f"mmlu Δ={md:.2f}); tune before committing.")


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
            slot = summary[p]["by_depth"].setdefault(
                key, {"hit": 0, "n": 0, "retained": 0})
            slot["hit"] += r["hit"]; slot["n"] += 1
            slot["retained"] += r["needle_retained"]
    return summary


def print_console(summary: dict, decision: str):
    print("\n" + "=" * 70)
    print("PHASE 9 — decode-time retention harness")
    print("=" * 70)
    for p in POLICIES:
        s = summary.get(p)
        if not s:
            continue
        print(f"\nPolicy: {p}")
        print(f"  Needle overall hit : {s['needle_overall']}")
        print(f"  Needle retained    : {s['needle_retained_rate']}")
        print(f"  MMLU smoke         : {s['mmlu_accuracy']}")
        for k, v in sorted(s["by_depth"].items()):
            print(f"    {k:<34} hit {v['hit']}/{v['n']}  "
                  f"retained {v['retained']}/{v['n']}")
    print("\nDECISION:", decision)


def run_harness(cfg, context_lens, depths, seeds, tasks, policies=POLICIES):
    eng = Engine(cfg)
    results, errors = [], []
    for task in tasks:
        builder = (build_needle_single if task == "needle_random_code"
                   else build_needle_multi)
        for ctx in context_lens:
            for depth in depths:
                for seed in range(seeds):
                    rng = random.Random(hash((task, ctx, depth, seed)) & 0xffffffff)
                    user, code, _q, needle = builder(ctx, depth, rng)
                    for policy in policies:
                        try:
                            results.append(eng.run_case(
                                policy, user, code, needle, task, ctx, depth, seed))
                        except Exception as e:
                            errors.append({"policy": policy, "task": task,
                                           "ctx": ctx, "depth": depth,
                                           "seed": seed, "error": repr(e)})
                            print(f"[harness] ERROR {policy} {task} ctx{ctx} "
                                  f"d{depth} s{seed}: {e}", flush=True)
    mmlu = {p: eng.run_mmlu_smoke(p) for p in policies}
    summary = aggregate(results, mmlu)
    decision = classify_decision(summary)
    return {"model": cfg.model, "config": dataclasses.asdict(cfg),
            "results": results, "summary": summary, "errors": errors,
            "decision": decision}


def run_calibration(cfg, depths, seeds, context_len) -> dict:
    """full_attention ONLY, many seeds — stabilise + dump every failing case."""
    eng = Engine(cfg)
    results, fails = [], []
    for depth in depths:
        for seed in range(seeds):
            rng = random.Random(hash(("cal", context_len, depth, seed)) & 0xffffffff)
            user, code, _q, needle = build_needle_single(context_len, depth, rng)
            r = eng.run_case("full_attention", user, code, needle,
                             "needle_random_code", context_len, depth, seed)
            results.append(r)
            if not r["hit"]:
                fails.append(r)
    hit = sum(r["hit"] for r in results)
    rate = round(hit / len(results), 3)
    print("\n" + "=" * 70)
    print(f"BASELINE CALIBRATION — full_attention @ ctx{context_len}")
    print(f"  needle hit rate: {hit}/{len(results)} = {rate}  "
          f"(floor for valid eval: {BASELINE_MIN})")
    print("=" * 70)
    if fails:
        print(f"\n{len(fails)} FAILING CASES (verbose):")
        for r in fails:
            print(f"\n  depth={r['depth']} seed={r['seed']} "
                  f"prompt_len={r['prompt_len_tokens']} reason={r['match_reason']}")
            print(f"    needle   : {r['needle_text']}")
            print(f"    expected : {r['expected_answer']}")
            print(f"    generated: {r['generated_text']!r}")
            print(f"    normalized: {r['normalized_generated']!r}  "
                  f"expected_in_generated={r['expected_in_generated']}  "
                  f"other_codes={r['other_code_like']}")
    verdict = ("BASELINE OK — proceed to evaluate retention." if rate >= BASELINE_MIN
               else f"BASELINE TOO LOW ({rate} < {BASELINE_MIN}) — fix prompt/"
               "matching/gen before judging retention.")
    print("\n" + verdict)
    return {"mode": "calibration", "context_len": context_len, "rate": rate,
            "config": dataclasses.asdict(cfg), "results": results,
            "verdict": verdict}

# ---------------------------------------------------------------- selftest ----


def _selftest() -> int:
    cfg = Config(block_size=32, sink_tokens=64, recent_tokens=128,
                 attention_budget_tokens=64, neighbor_blocks=1)
    assert sink_block_set(cfg) == {0, 1}
    rb = recent_block_set(cfg, 1000)
    assert min(rb) == (1000 - 128) // 32 and max(rb) == 999 // 32, rb
    n = 40
    score = [0.0] * n
    score[20] = 5.0
    ret = select_retained_blocks(n, score, {0, 1}, {38, 39}, 2, 1)
    assert 20 in ret and {19, 21} <= ret and {0, 1, 38, 39} <= ret, ret
    assert not needle_retained([20], {0, 38, 39})
    assert needle_retained([20], ret)
    # robust matching: exact / substring / spaced / punctuation / reject.
    assert match_code("Q7M-42X-L9P", "Q7M-42X-L9P")[:2] == (True, "exact")
    assert match_code('"Q7M-42X-L9P".', "Q7M-42X-L9P")[0]
    assert match_code("The code is Q7M-42X-L9P.", "Q7M-42X-L9P")[:2] == (True, "substring")
    assert match_code("answer: q7m 42x l9p", "Q7M-42X-L9P")[0]   # spaces/case
    assert match_code("ABC-123-XYZ", "Q7M-42X-L9P")[:2] == (False, "none")
    # builders: 4-tuple, explicit needle, copyable 3-word passphrase present.
    u, c, q, nd = build_needle_single(2000, 0.3, random.Random(1))
    assert "ACCESS CODE:" in nd and c in nd and c.count("-") == 2
    assert "Return only the exact access code" in q
    um, cm, _q, ndm = build_needle_multi(2000, 0.9, random.Random(2))
    assert um.count(cm) == 1 and "ACCESS CODE:" in ndm and cm.count("-") == 2
    # guard at 0.95.
    assert classify_decision({"full_attention": {"needle_overall": 0.9},
                              "decode_attention_retention": {}}).startswith("INVALID")
    assert classify_decision(
        {"full_attention": {"needle_overall": 1.0, "mmlu_accuracy": 1.0},
         "decode_attention_retention": {"needle_overall": 0.95,
                                        "needle_retained_rate": 1.0,
                                        "mmlu_accuracy": 1.0}}).startswith("GREEN")
    print("decode retention harness self-test: PASS")
    return 0

# -------------------------------------------------------------------- main ----


def _cfg(a) -> Config:
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
    ap.add_argument("--max-new-tokens", type=int, default=24)
    ap.add_argument("--context-lens", default="4096,8192")
    ap.add_argument("--depths", default="0.10,0.30,0.50,0.70,0.90")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--tasks", default="needle_random_code,multi_needle")
    ap.add_argument("--output-json", default="phase9_decode_retention.json")
    ap.add_argument("--smoke", action="store_true",
                    help="small: ctx 4096, depths 0.1/0.5/0.9, 2 seeds, all policies")
    ap.add_argument("--calibrate", action="store_true",
                    help="full_attention ONLY, many seeds; verbose failing cases")
    ap.add_argument("--calibrate-seeds", type=int, default=16)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    cfg = _cfg(a)
    depths = [float(x) for x in a.depths.split(",") if x.strip()]
    if a.calibrate:
        out = run_calibration(cfg, depths, a.calibrate_seeds,
                              int(a.context_lens.split(",")[0]))
    else:
        if a.smoke:
            ctx, depths, seeds, tasks = [4096], [0.10, 0.50, 0.90], 2, \
                ["needle_random_code"]
        else:
            ctx = [int(x) for x in a.context_lens.split(",") if x.strip()]
            seeds = a.seeds
            tasks = [t for t in a.tasks.split(",") if t.strip()]
        out = run_harness(cfg, ctx, depths, seeds, tasks)
        print_console(out["summary"], out["decision"])
        print(f"\n{len(out['results'])} cases, {len(out['errors'])} errors")
    Path(a.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output_json).write_text(json.dumps(out, indent=2))
    print(f"wrote {a.output_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
