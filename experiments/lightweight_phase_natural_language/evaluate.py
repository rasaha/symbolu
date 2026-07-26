"""
evaluate.py — per-task metrics at the <A> answer position.

Metrics per task family:
    accuracy         : argmax at <A> == answer token
    swap_rate        : (binding tasks) pred is a *distractor* value from the same context
    stale_rate       : (supersession) pred is the superseded (stale) value
    source_acc       : (source_attr) accuracy of predicting the source token
    abstain_acc      : (insufficient) accuracy of predicting INSUFFICIENT
    unsupported_rate : (insufficient) pred is a concrete value (confident wrong answer)
    ppl              : (lm) validation perplexity / next-token accuracy on prose

Everything runs under no_grad; no training signal leaks.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List

import torch
import torch.nn.functional as F

from .datasets import Example, Tokenizer
from .train import _collate


@torch.no_grad()
def evaluate(model, examples: List[Example], tok: Tokenizer, device="cpu",
             batch_size: int = 32) -> Dict[str, Dict]:
    model.eval()
    by_task: Dict[str, List[Example]] = defaultdict(list)
    for e in examples:
        by_task[e.task].append(e)

    results: Dict[str, Dict] = {}
    for task, exs in by_task.items():
        correct = 0
        total = 0
        swap = 0
        stale = 0
        unsupported = 0
        nll_sum = 0.0
        ntok = 0
        ntok_correct = 0
        for i in range(0, len(exs), batch_size):
            batch = exs[i:i + batch_size]
            ids, labels, ans_pos, ans_id = _collate(batch, tok.pad_id, device)
            logits, _ = model(ids)
            ar = torch.arange(ids.size(0), device=device)
            ans_logits = logits[ar, ans_pos]
            pred = ans_logits.argmax(-1)
            correct += (pred == ans_id).sum().item()
            total += len(batch)
            # LM perplexity / next-token accuracy on the full (pad-masked) sequence
            lp = logits[:, :-1]
            tgt = labels[:, 1:]
            mask = tgt != -100
            nll = F.cross_entropy(lp.reshape(-1, lp.size(-1)), tgt.reshape(-1),
                                  ignore_index=-100, reduction="sum")
            nll_sum += nll.item(); ntok += mask.sum().item()
            ntok_correct += ((lp.argmax(-1) == tgt) & mask).sum().item()
            # task-specific
            for j, e in enumerate(batch):
                p = pred[j].item()
                if task in ("entity_binding", "multi_candidate"):
                    dv = [tok.id(v) for v in e.meta.get("distractor_values", [])]
                    if p in dv:
                        swap += 1
                if task == "supersession":
                    if p == tok.id(e.meta["stale"]):
                        stale += 1
                if task == "insufficient":
                    # any value token counts as unsupported confident answer
                    w = tok.itos[p]
                    if w.startswith("$"):
                        unsupported += 1
        r = {
            "n": total,
            "accuracy": correct / max(1, total),
            "next_token_acc": ntok_correct / max(1, ntok),
            "ppl": math.exp(nll_sum / max(1, ntok)),
        }
        if task in ("entity_binding", "multi_candidate"):
            r["swap_rate"] = swap / max(1, total)
        if task == "supersession":
            r["stale_rate"] = stale / max(1, total)
        if task == "source_attr":
            r["source_acc"] = r["accuracy"]
        if task == "insufficient":
            r["abstain_acc"] = r["accuracy"]
            r["unsupported_rate"] = unsupported / max(1, total)
        results[task] = r
    return results
