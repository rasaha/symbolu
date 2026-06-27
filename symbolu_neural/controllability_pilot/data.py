"""Smoke dataset for the controllability pilot.

Three SEMANTICALLY-defined target axes (calm / active / heavy, i.e.
sattva / rajas / tamas-like). The axis is defined by MEANING, not by sound — that
is deliberate: the pilot asks whether the *phonological* Symbol-U code can steer a
*semantic* axis better than matched controls. If the axis were defined by Symbol-U
itself the test would be circular.

Deterministic: the corpus is built from fixed per-axis vocab + templates with a
fixed seed, so runs reproduce exactly. `make_corpus()` returns labeled sentences;
`prompts()` returns neutral generation seeds.
"""
from __future__ import annotations

import random
from typing import Dict, List, Tuple

AXES = ["calm", "active", "heavy"]

# Semantic vocab per axis (meaning-defined; sound is incidental).
VOCAB: Dict[str, Dict[str, List[str]]] = {
    "calm": {
        "adj": ["quiet", "gentle", "soft", "serene", "tranquil", "mellow",
                "placid", "tender", "smooth", "peaceful"],
        "noun": ["lake", "meadow", "breeze", "evening", "garden", "valley",
                 "stream", "dusk", "shore", "calm"],
        "verb": ["rests", "drifts", "settles", "lulls", "soothes", "eases",
                 "floats", "softens", "quiets", "calms"],
    },
    "active": {
        "adj": ["bright", "swift", "lively", "vivid", "dynamic", "eager",
                "brisk", "vibrant", "keen", "energetic"],
        "noun": ["runner", "spark", "engine", "rally", "current", "flame",
                 "rocket", "dancer", "race", "surge"],
        "verb": ["sprints", "leaps", "races", "surges", "blazes", "charges",
                 "darts", "bursts", "drives", "rushes"],
    },
    "heavy": {
        "adj": ["grim", "heavy", "dark", "dull", "dense", "bleak",
                "somber", "weary", "thick", "leaden"],
        "noun": ["burden", "gloom", "shadow", "weight", "void", "ruin",
                 "ash", "fog", "stone", "grave"],
        "verb": ["crushes", "sinks", "drags", "looms", "weighs", "smothers",
                 "grinds", "buries", "dims", "drowns"],
    },
}

TEMPLATES = [
    "the {adj} {noun} {verb}",
    "a {adj} {noun} {verb} here",
    "the {noun} {verb} in the {adj} air",
    "{adj} and {adj2} the {noun} {verb}",
    "the {adj} {noun} slowly {verb}",
    "every {noun} {verb} so {adj}",
]

PROMPTS = ["the", "a", "it", "they", "we", "there", "this", "and"]


def make_corpus(per_axis: int = 60, seed: int = 0) -> List[Tuple[str, str]]:
    rng = random.Random(seed)
    out: List[Tuple[str, str]] = []
    for axis in AXES:
        v = VOCAB[axis]
        for _ in range(per_axis):
            t = rng.choice(TEMPLATES)
            s = t.format(
                adj=rng.choice(v["adj"]),
                adj2=rng.choice(v["adj"]),
                noun=rng.choice(v["noun"]),
                verb=rng.choice(v["verb"]),
            )
            out.append((s, axis))
    rng.shuffle(out)
    return out


def axis_lexicons() -> Dict[str, List[str]]:
    """Flat keyword set per axis for the transparent lexicon scorer."""
    return {a: sorted({w for grp in VOCAB[a].values() for w in grp}) for a in AXES}


def prompts() -> List[str]:
    return list(PROMPTS)


if __name__ == "__main__":
    c = make_corpus()
    print(f"{len(c)} sentences, axes={AXES}")
    for s, a in c[:6]:
        print(f"  [{a:6}] {s}")
