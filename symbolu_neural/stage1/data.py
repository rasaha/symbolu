"""Stage-1 dataset: JSONL -> tokenized ids + unit-pooling alignment + labels.

Schema (one JSON object per line). Labels are per-UNIT lists; a unit is a
syllable if you provide one, else a word.

    {
      "text": "the world feels chaotic",      # optional if "units" given
      "units": ["the", "world", "feels", "chaotic"],   # syllables or words
      "vritti": ["memory", "misperception", "valid_cognition", "imagination"],
      "aspect": ["thinking", "forming", "reasoning", "purposing"],
      "guna":   [...],   "kosha": [...]         # optional
    }

If "units" is absent, the text is whitespace-split into word units. Any label
list shorter/longer than the units is index-aligned and padded with IGNORE.

Alignment strategy: each unit is tokenized separately (no special tokens) and
the ids are concatenated into a single sequence, so the frozen backbone still
attends across the whole input while we retain exact per-unit token spans. A
pooling matrix P:[U,L] (mean or sum over each unit's tokens) maps token hidden
states to per-unit representations. This avoids offset-mapping fragility and
works identically for the toy char backbone and a real HF tokenizer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
from torch.utils.data import Dataset

from .labels import IGNORE, name_to_idx, CARDINALITY

HEADS = ("vritti", "aspect", "guna", "kosha")


def load_jsonl(path: str) -> List[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# --------------------------------------------------------------------------- #
# Tokenizers: both return (input_ids: List[int], unit_ranges: List[(s,e)])
# --------------------------------------------------------------------------- #
class CharTokenizer:
    """Dependency-free char tokenizer for the toy/CPU path."""

    def __init__(self, vocab_size: int = 256):
        self.vocab_size = vocab_size

    def encode_units(self, units: List[str]) -> Tuple[List[int], List[Tuple[int, int]]]:
        ids: List[int] = []
        ranges: List[Tuple[int, int]] = []
        for i, u in enumerate(units):
            if i > 0:
                ids.append(min(ord(" "), self.vocab_size - 1))  # separator
            s = len(ids)
            for ch in u:
                ids.append(min(ord(ch), self.vocab_size - 1))
            ranges.append((s, len(ids)))
        return ids, ranges


class HFTokenizer:
    """Wraps a HuggingFace fast/slow tokenizer (real-data path)."""

    def __init__(self, name: str):
        from transformers import AutoTokenizer  # lazy
        self.tok = AutoTokenizer.from_pretrained(name)
        self.vocab_size = self.tok.vocab_size

    def encode_units(self, units: List[str]) -> Tuple[List[int], List[Tuple[int, int]]]:
        ids: List[int] = []
        ranges: List[Tuple[int, int]] = []
        for i, u in enumerate(units):
            piece = self.tok.encode(((" " if i > 0 else "") + u),
                                    add_special_tokens=False)
            s = len(ids)
            ids.extend(piece)
            ranges.append((s, len(ids)))
        return ids, ranges


@dataclass
class Example:
    input_ids: List[int]
    unit_ranges: List[Tuple[int, int]]
    labels: Dict[str, List[int]]   # head -> per-unit class idx (IGNORE if none)
    units: List[str]


class GroundingDataset(Dataset):
    def __init__(self, rows: List[dict], tokenizer, shuffle_labels: bool = False,
                 seed: int = 0):
        self.examples: List[Example] = []
        for row in rows:
            units = row.get("units") or (
                row["text"].split() if "text" in row else None)
            if not units:
                continue
            ids, ranges = tokenizer.encode_units(units)
            if not ids:
                continue
            labels: Dict[str, List[int]] = {}
            for head in HEADS:
                raw = row.get(head)
                if raw is None:
                    labels[head] = [IGNORE] * len(units)
                else:
                    labels[head] = [
                        name_to_idx(head, raw[j]) if j < len(raw) else IGNORE
                        for j in range(len(units))]
            self.examples.append(Example(ids, ranges, labels, units))
        if shuffle_labels:
            self._global_shuffle(seed)

    def _global_shuffle(self, seed: int) -> None:
        """CONTROL: globally permute each head's labels across ALL units so the
        marginal class balance is preserved but every feature<->label relation
        is destroyed. A grounded head should then collapse to the majority
        baseline on held-out data (accuracy kill-criterion bites)."""
        rng = torch.Generator().manual_seed(seed)
        for head in HEADS:
            pos = [(i, j) for i, e in enumerate(self.examples)
                   for j, y in enumerate(e.labels[head]) if y != IGNORE]
            if not pos:
                continue
            vals = [self.examples[i].labels[head][j] for i, j in pos]
            perm = torch.randperm(len(vals), generator=rng).tolist()
            for (i, j), p in zip(pos, perm):
                self.examples[i].labels[head][j] = vals[p]

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, i: int) -> Example:
        return self.examples[i]

    def label_counts(self, head: str) -> Dict[int, int]:
        counts: Dict[int, int] = {}
        for ex in self.examples:
            for y in ex.labels[head]:
                if y != IGNORE:
                    counts[y] = counts.get(y, 0) + 1
        return counts


def make_collate(pool: str = "mean"):
    assert pool in ("mean", "sum")

    def collate(batch: List[Example]) -> Dict[str, torch.Tensor]:
        B = len(batch)
        Lmax = max(len(e.input_ids) for e in batch)
        Umax = max(len(e.unit_ranges) for e in batch)
        input_ids = torch.zeros(B, Lmax, dtype=torch.long)
        attn = torch.zeros(B, Lmax, dtype=torch.long)
        P = torch.zeros(B, Umax, Lmax)
        unit_mask = torch.zeros(B, Umax, dtype=torch.bool)
        labels = {h: torch.full((B, Umax), IGNORE, dtype=torch.long) for h in HEADS}
        for b, e in enumerate(batch):
            L = len(e.input_ids)
            input_ids[b, :L] = torch.tensor(e.input_ids)
            attn[b, :L] = 1
            for u, (s, t) in enumerate(e.unit_ranges):
                span = max(t - s, 1)
                w = 1.0 / span if pool == "mean" else 1.0
                P[b, u, s:t] = w
                unit_mask[b, u] = True
            for h in HEADS:
                ys = e.labels[h]
                labels[h][b, :len(ys)] = torch.tensor(ys)
        return {"input_ids": input_ids, "attention_mask": attn,
                "pool": P, "unit_mask": unit_mask, "labels": labels}

    return collate
