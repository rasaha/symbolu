"""EXPLORATORY analysis (NOT preregistered; NOT evidence for any verdict).

Answers, from data we already have (development seeds 9071-9073, authorized phase):
  (1) How does the model FAIL on unseen identifiers? Error-category breakdown from saved traces.
  (2) Memorize-vs-copy: when the model emits a valid code on an UNSEEN input, is that code
      (a) the correct one, (b) a wrong code from the CURRENT context, (c) a code from the
      TRAINING pool (=memorized regurgitation), or (d) a novel fabricated code?
  (3) Positional token accuracy (does it copy any characters, or nothing?).
  (4) A live attention/embedding snapshot on a regenerated dev model (seed 9071): where does the
      output position attend, seen vs unseen?

Uses only already-authorized development seeds; consumes no new seed; changes no frozen code.
"""
from __future__ import annotations

import collections
import json
import os

import torch

from experiments.unseen_identifier_copy_selection.config import SPLIT_IDS, IDENTIFIER_ALPHABET, IDENTIFIER_LENGTH
from experiments.unseen_identifier_copy_selection.runner import build_cohort
from experiments.unseen_identifier_copy_selection.identifiers import build_pools

DEV = (9071, 9072, 9073)
RUN = "results/unseen_identifier_copy_selection/run"


def wellformed(s):
    return len(s) == IDENTIFIER_LENGTH and all(c in IDENTIFIER_ALPHABET for c in s)


def load_traces(seed, cohort):
    return json.load(open(f"{RUN}/{seed}/{cohort}/traces.json"))


def cohort_index(seed, cohort):
    """hash -> Example (rebuilt deterministically to recover context + pools)."""
    c = build_cohort(seed, cohort, token="development")
    return {e.example_hash: e for s in SPLIT_IDS for e in c[s]}


def part1_categories():
    print("\n" + "=" * 78)
    print("(1) ERROR-CATEGORY BREAKDOWN  (pooled over dev seeds 9071-9073; answer-expected items)")
    print("=" * 78)
    for cohort in ("seen", "unseen"):
        agg = collections.Counter()
        n = 0
        for sd in DEV:
            for t in load_traces(sd, cohort):
                if t["expected_output"] == "INSUFFICIENT_EVIDENCE":
                    continue  # abstention items handled separately
                agg[t["parsed_category"]] += 1
                n += 1
        print(f"\n  cohort = {cohort}  (n={n} answer-expected)")
        for cat, c in sorted(agg.items(), key=lambda kv: -kv[1]):
            print(f"    {cat:28} {c:5}  ({100*c/n:5.1f}%)")


def part2_memorize_vs_copy():
    print("\n" + "=" * 78)
    print("(2) MEMORIZE-vs-COPY  — for VALID-code outputs on answer-expected items")
    print("=" * 78)
    for cohort in ("seen", "unseen"):
        train_pool = set()
        idx_by_seed = {}
        for sd in DEV:
            pools = build_pools(sd, token="development")
            train_pool_sd = set(pools["train"])
            idx_by_seed[sd] = (cohort_index(sd, cohort), train_pool_sd)
        buckets = collections.Counter()
        total_valid = 0
        for sd in DEV:
            idx, train_pool_sd = idx_by_seed[sd]
            for t in load_traces(sd, cohort):
                if t["expected_output"] == "INSUFFICIENT_EVIDENCE":
                    continue
                out = t["normalized_output"].strip()
                if not wellformed(out):
                    buckets["malformed/garbled"] += 1
                    continue
                total_valid += 1
                ex = idx[t["example_hash"]]
                ctx = set(ex.context_ids)
                if out == t["expected_output"]:
                    buckets["correct_copy"] += 1
                elif out in ctx:
                    buckets["wrong_code_from_context"] += 1
                elif out in train_pool_sd:
                    buckets["MEMORIZED_training_code"] += 1
                else:
                    buckets["fabricated_novel_code"] += 1
        print(f"\n  cohort = {cohort}  (valid 4-char outputs = {total_valid}; malformed shown too)")
        tot = sum(buckets.values())
        for k in ("correct_copy", "wrong_code_from_context", "MEMORIZED_training_code",
                  "fabricated_novel_code", "malformed/garbled"):
            c = buckets.get(k, 0)
            print(f"    {k:28} {c:5}  ({100*c/tot:5.1f}% of all outputs)")


def part3_positional_token_acc():
    print("\n" + "=" * 78)
    print("(3) POSITIONAL CHARACTER ACCURACY  (per-position exact char match; chance=1/36=2.8%)")
    print("=" * 78)
    for cohort in ("seen", "unseen"):
        pos_correct = [0] * IDENTIFIER_LENGTH
        n = 0
        for sd in DEV:
            for t in load_traces(sd, cohort):
                if t["expected_output"] == "INSUFFICIENT_EVIDENCE":
                    continue
                gold = t["expected_output"]
                got = t["normalized_output"].strip()
                n += 1
                for i in range(IDENTIFIER_LENGTH):
                    if i < len(got) and got[i] == gold[i]:
                        pos_correct[i] += 1
        print(f"\n  cohort = {cohort}  (n={n})")
        print("    position:  " + "  ".join(f"char{i+1}" for i in range(IDENTIFIER_LENGTH)))
        print("    accuracy:  " + "  ".join(f"{100*pos_correct[i]/n:4.1f}%" for i in range(IDENTIFIER_LENGTH)))


# ---------- (4) live attention/embedding snapshot ----------
_ATT = {}


def _capture_attention(model):
    """Monkeypatch each attention block to also store softmax weights (recomputed, read-only)."""
    import torch.nn.functional as F
    blocks = model.lm.blocks if hasattr(model.lm, "blocks") else None
    handles = []
    layers = []
    for name, mod in model.named_modules():
        if mod.__class__.__name__ == "CausalSelfAttention":
            layers.append((name, mod))

    def mk_hook(name):
        def pre_hook(mod, inp):
            x = inp[0]
            B, L, d = x.shape
            q, k, v = mod.qkv(x).split(d, dim=2)
            q = q.view(B, L, mod.h, mod.dk).transpose(1, 2)
            k = k.view(B, L, mod.h, mod.dk).transpose(1, 2)
            scores = (q @ k.transpose(-2, -1)) / (mod.dk ** 0.5)
            mask = torch.triu(torch.ones(L, L, dtype=torch.bool), diagonal=1)
            scores = scores.masked_fill(mask, float("-inf"))
            _ATT[name] = torch.softmax(scores, dim=-1).detach()
        return handles.append(mod.register_forward_pre_hook(pre_hook))

    for name, mod in layers:
        mk_hook(name)
    return handles, [n for n, _ in layers]


def part4_attention_snapshot():
    print("\n" + "=" * 78)
    print("(4) LIVE ATTENTION SNAPSHOT  — regenerate dev model (seed 9071, deterministic)")
    print("=" * 78)
    from experiments.unseen_identifier_copy_selection.training import train_cohort
    from experiments.unseen_identifier_copy_selection.evaluation import build_prompt_ids
    from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer
    from experiments.single_hop_typed_vs_prose.model import build_model

    seed = 9071
    seen = build_cohort(seed, "seen", token="development")
    unseen = build_cohort(seed, "unseen", token="development")
    seen_ex = [e for s in SPLIT_IDS for e in seen[s]]
    tok = LexicalTokenizer()
    ckpt_dir = "/tmp/uid_attn_ckpt"
    art = train_cohort(seed, "seen", seen_ex, ckpt_dir, device="cpu")
    model = build_model(0)
    model.load_state_dict(torch.load(art.checkpoint_path, map_location="cpu"))
    model.eval()
    handles, layer_names = _capture_attention(model)

    def answer_pos_attention_on_gold(example):
        """Run one C1 direct-copy example; measure how much the LAST prompt position attends to the
        4 context tokens that ARE the target identifier (the thing it must copy)."""
        prompt_ids = build_prompt_ids(example, tok)
        # locate the target id tokens inside the prompt (they are the copy source)
        target_ids = tok.encode(example.target_id) if example.target_id else []
        with torch.no_grad():
            _ = model(torch.tensor([prompt_ids]))
        # average attention (last query position) over heads & layers onto each key position
        L = len(prompt_ids)
        att = torch.stack([_ATT[n][0, :, L - 1, :].mean(0) for n in layer_names]).mean(0)  # [L]
        # find contiguous match of target_ids in prompt_ids
        mass = 0.0
        for i in range(len(prompt_ids) - len(target_ids) + 1):
            if prompt_ids[i:i + len(target_ids)] == target_ids:
                mass = float(att[i:i + len(target_ids)].sum())
                break
        return mass

    for cohort, cset in (("seen", seen), ("unseen", unseen)):
        masses = []
        for e in cset["C1"][:20]:  # C1 = direct copy: exactly one target to copy
            masses.append(answer_pos_attention_on_gold(e))
        avg = sum(masses) / len(masses)
        print(f"\n  cohort={cohort} C1 direct-copy: avg attention mass the output position puts on the")
        print(f"    target tokens it must copy = {avg:5.3f}  (uniform baseline ~ {IDENTIFIER_LENGTH}/prompt_len)")
    for h in handles:
        h.remove()


if __name__ == "__main__":
    part1_categories()
    part2_memorize_vs_copy()
    part3_positional_token_acc()
    part4_attention_snapshot()
    print("\n[exploratory — not preregistered, not a verdict]")
