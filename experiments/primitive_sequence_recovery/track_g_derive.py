"""Track G — deterministic derivation of the real polarity vector A from a frozen varṇa table.

The real (A) polarity vector is NOT authored per word. It is derived, deterministically, from:
  - the word's varṇa sequence,
  - the frozen `track_g_varna_polarity_table.json` (per-varṇa signed axis contributions),
  - a fixed aggregation rule (sum signed contributions across varṇas, threshold to sign).
R (random flip) and B (scramble) are deterministic transforms of the derived A. No per-word A
override is permitted. A missing varṇa-table entry fails loudly. No LLM, no scoring, no network.

The varṇa table is itself researcher-authored and high-DOF (see its status flags): a positive Track
G result would remain exploratory architecture-bound utility, never ontological evidence.
"""
from __future__ import annotations

import json
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent


def load_table(path):
    t = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if t.get("artifact_type") != "track_g_varna_polarity_table":
        raise ValueError("not a track_g_varna_polarity_table")
    return t


def axis_order(axes_path):
    return [a["axis_id"] for a in json.loads(pathlib.Path(axes_path).read_text(encoding="utf-8"))["axes"]]


def axis_poles(axes_path):
    return {a["axis_id"]: (a["positive_pole"], a["negative_pole"])
            for a in json.loads(pathlib.Path(axes_path).read_text(encoding="utf-8"))["axes"]}


def derive_A(varna_seq, table, axes):
    """Sum signed per-varṇa contributions across the sequence, threshold each axis to a sign.
    Missing varṇa or unknown axis -> KeyError (fails loudly). No per-word override."""
    acc = {ax: 0 for ax in axes}
    for v in varna_seq:
        entry = table["varnas"].get(v)
        if entry is None:
            raise KeyError(f"varṇa {v!r} missing from polarity table")
        for ax, s in entry["axis_contributions"].items():
            if ax not in acc:
                raise KeyError(f"unknown axis {ax!r} in table entry {v!r}")
            acc[ax] += s
    return {ax: (1 if acc[ax] > 0 else -1 if acc[ax] < 0 else 0) for ax in axes}


def random_flip(vec):
    """R: deterministic sign flip of the derived A vector."""
    return {ax: -s for ax, s in vec.items()}


def scramble(vec, seed, case_id):
    """B: seeded permutation of the derived A signs across axes (multiset of signs preserved)."""
    axes = list(vec)
    signs = [vec[a] for a in axes]
    random.Random(f"{seed}:{case_id}").shuffle(signs)
    return dict(zip(axes, signs))


def describe(vec, poles):
    """Render a signed vector as a generic orientation over English axis poles (no varṇa/root)."""
    parts = [poles[a][0] if s > 0 else poles[a][1] for a, s in vec.items() if s != 0]
    return ("toward: " + ", ".join(parts)) if parts else "no clear orientation"
