"""Fixed ontology tables for the API control-protocol pilot.

The pilot steers along three target axes (calm / active / heavy ≈
sattva / rajas / tamas). Each axis maps deterministically to:

  - a `symbolu_state`   : the Sanskrit ontology fields (guna/vritti/kosha/aspect/
                          resonance) — the part whose value is in question.
  - a `response_policy` : plain-English actionable instruction (tone/style/
                          prefer/avoid) — the part that any LLM can actually follow.

The whole empirical question is whether `symbolu_state` adds anything over
`response_policy` (which is itself just natural-language instruction in JSON).
"""
from __future__ import annotations

from typing import Dict, List

AXES = ["calm", "active", "heavy"]

SYMBOLU_STATE: Dict[str, dict] = {
    "calm": {"guna": "sattva", "vritti": "pramana", "kosha": "manomaya",
             "aspect": "clarity", "resonance": 0.72},
    "active": {"guna": "rajas", "vritti": "kshipta", "kosha": "pranamaya",
               "aspect": "drive", "resonance": 0.55},
    "heavy": {"guna": "tamas", "vritti": "mudha", "kosha": "annamaya",
              "aspect": "density", "resonance": 0.31},
}

RESPONSE_POLICY: Dict[str, dict] = {
    "calm": {"tone": "calm", "style": "direct",
             "prefer": ["clarity", "grounded reasoning"],
             "avoid": ["speculation", "emotional escalation"]},
    "active": {"tone": "energetic", "style": "brisk",
               "prefer": ["momentum", "vivid concrete verbs"],
               "avoid": ["hedging", "passivity"]},
    "heavy": {"tone": "somber", "style": "weighty",
              "prefer": ["gravity", "slow deliberate phrasing"],
              "avoid": ["levity", "brightness"]},
}

# Plain-English tone words an instruction-follower keys on (offline adherence proxy).
TONE_LEXICON: Dict[str, List[str]] = {
    "calm": ["calm", "gentle", "quiet", "serene", "peaceful", "soothing", "still",
             "tranquil", "grounded", "clear", "measured"],
    "active": ["energetic", "lively", "brisk", "vivid", "dynamic", "fast", "eager",
               "vibrant", "driving", "punchy", "momentum"],
    "heavy": ["somber", "heavy", "grave", "weighty", "dark", "bleak", "slow",
              "sombre", "leaden", "solemn", "ponderous"],
}

# Random-but-valid vocab to fill random/shuffled packets without obvious tells.
RANDOM_VOCAB = {
    "guna": ["sattva", "rajas", "tamas"],
    "vritti": ["pramana", "viparyaya", "vikalpa", "nidra", "smriti"],
    "kosha": ["annamaya", "pranamaya", "manomaya", "vijnanamaya", "anandamaya"],
    "aspect": ["clarity", "drive", "density", "flux", "stillness"],
}
