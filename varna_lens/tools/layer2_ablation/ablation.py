#!/usr/bin/env python3
"""Bounded 4-arm ablation of the Layer-2 synthesis bridge, post-B1.12 migration.

Core question: does an intermediate synthesis vocabulary add value beyond the authoritative B1.12
vṛtti payload? Four arms, same frozen inputs, same synthesis template, differing ONLY in the
pole→text transform:

  A  Direct B1.12 payload         — the authoritative vṛtti text, verbatim (no bridge)
  B  Legacy Layer-2 bridge        — H._bridge (layer2_bridge_vocab.json), unchanged; unresolved recorded
  C  Deterministic compression    — non-semantic shortening of the B1.12 text (no new ontology)
  D  No symbolic payload          — control

Discipline: no model, no scoring vocabulary, no authored labels, no old-lexicon runtime read, no change
to the B1.12 mapping / parser / renderer. Deterministic. Arm C uses ONLY the allowed operations
(clause selection, first-sentence extraction, parenthetical removal, punctuation normalization, fixed
max length, stable order).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_VL = Path(__file__).resolve().parent.parent.parent          # varna_lens/
sys.path.insert(0, str(_VL))
import varna_lens as V                    # noqa: E402  (engine: tokenizer + active B1.12 lexicon)
import sample_text_rule_harness as H      # noqa: E402  (legacy Layer-2 bridge: _bridge, BRIDGE)

# The Layer-2 synthesis template, verbatim from H.synthesize — shared by every arm so only the
# pole→text transform differs.
TEMPLATE_SEED = "{binding} moves toward {liberating}"
TEMPLATE_TRANS = "{liberating} is the resolving principle"
UNRESOLVED = "[unresolved]"


# ---------------------------------------------------------------------------------------------------
# Layer-1 pole stream (faithful to H.profile's role logic, but tokenizer-agnostic so the ablation
# corpus can include IAST Sanskrit words — ś / ṣ / conjunct kṣ — that the g2p-only harness can't take).
def pole_stream(word):
    """Return the ordered poles Layer-2 synthesis actually consumes:
       seed.binding, seed.liberating (ONSET_SEED consonant) and trans.liberating (last consonant).
    Each pole is {role, pole, key, state} where `state` is the RAW active-lexicon value (B1.12)."""
    ph, warn, src = V.auto_phonemes(word)
    cons = [(i, k) for i, (t, k, _s) in enumerate(ph) if t == "C" and k in V.LEX["consonants"]]
    poles = []
    if not cons:
        return {"word": word, "src": src, "poles": [], "warn": warn}
    first_i, first_k = cons[0]
    last_i, last_k = cons[-1]
    seed = V.LEX["consonants"][first_k]
    poles.append({"role": "ONSET_SEED", "pole": "binding", "key": first_k, "state": seed["binding_state"]})
    poles.append({"role": "ONSET_SEED", "pole": "liberating", "key": first_k, "state": seed["liberating_state"]})
    if last_k != first_k or last_i != first_i:
        trans = V.LEX["consonants"][last_k]
        poles.append({"role": "TRANSFORMER", "pole": "liberating", "key": last_k, "state": trans["liberating_state"]})
    return {"word": word, "src": src, "poles": poles, "warn": warn}


# ---------------------------------------------------------------------------------------------------
# Arm C — deterministic, non-semantic compression (ALLOWED ops only).
_PAREN = re.compile(r"\s*\([^)]*\)")
_WS = re.compile(r"\s+")
# clause boundaries, in priority order (em-dash gloss head, then sentence/clause separators).
_CLAUSE_DELIMS = [" — ", "—", "; ", ";", ". "]
COMPRESS_MAX = 80


def compress(text, max_len=COMPRESS_MAX):
    """Deterministic shortening: parenthetical removal → first-clause selection → punctuation/whitespace
    normalization → fixed max length at a word boundary. No summarization, no rewriting, no new labels."""
    s = _PAREN.sub("", str(text))                       # parenthetical removal
    cut = len(s)
    for d in _CLAUSE_DELIMS:                             # first-clause / first-sentence selection
        j = s.find(d)
        if 0 <= j < cut:
            cut = j
    s = s[:cut]
    s = _WS.sub(" ", s).strip().strip(" ,;:—-/")        # punctuation normalization
    if len(s) > max_len:                                # fixed max length, at a word boundary
        s = s[:max_len].rsplit(" ", 1)[0].strip().strip(" ,;:—-/")
    return s


# ---------------------------------------------------------------------------------------------------
# Arm transforms: pole state → downstream text.
def _t_direct(state):
    return H._gloss(state) if not isinstance(state, str) else state    # verbatim B1.12 text


def _t_legacy(state):
    return H._bridge(state) or UNRESOLVED                              # bridge phrase or [unresolved]


def _t_compress(state):
    return compress(_t_direct(state))


ARM_TRANSFORMS = {"A_direct": _t_direct, "B_legacy": _t_legacy, "C_compress": _t_compress}


def render_arm(stream, arm):
    """Fill the shared synthesis template using arm `arm` (A/B/C). Arm D returns no payload."""
    if arm == "D_none":
        return {"arm": arm, "payload": "", "clauses": [], "pole_texts": []}
    T = ARM_TRANSFORMS[arm]
    poles = stream["poles"]
    if not poles:
        return {"arm": arm, "payload": "", "clauses": [], "pole_texts": []}
    texts = [T(p["state"]) for p in poles]
    clauses = [TEMPLATE_SEED.format(binding=texts[0], liberating=texts[1])]
    if len(poles) >= 3:
        clauses.append(TEMPLATE_TRANS.format(liberating=texts[2]))
    return {"arm": arm, "payload": ", and ".join(clauses), "clauses": clauses, "pole_texts": texts}


ARMS = ["A_direct", "B_legacy", "C_compress", "D_none"]


def render_all(word):
    stream = pole_stream(word)
    return {"word": word, "src": stream["src"], "poles": stream["poles"],
            "arms": {a: render_arm(stream, a) for a in ARMS}}


if __name__ == "__main__":
    import json
    for w in (sys.argv[1:] or ["love", "śānti", "kṣamā"]):
        r = render_all(w)
        print(f"\n=== {w} ({r['src']}) ===")
        for a in ARMS:
            print(f"  {a:11} {r['arms'][a]['payload'][:120]}")
