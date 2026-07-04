#!/usr/bin/env python3
"""Real deterministic conditioning builder for the H2 Track B B1 dry-run — NO MODEL, NO SCORING.

Produces the ACTUAL per-(word, arm) conditioning cores used by the committed harmonized generator
(64b0f40), for the 25 eval words, so the B1 dry-run harness can render real conditioning instead of
mock placeholders — while still calling NO model and doing NO scoring.

Cores exactly match the committed `generation_conditioning_prompt_demo` logic:
  A = L2 synthesis (true G2P, vowel_mode field_only)   R = random bridge process line (seed "R:{w}")
  S = scrambled bridge process line (fixed scramble)   C = surface facts (onset/vowels/final/positions)
  X = fixed neutral filler                             D = dictionary sense + synonyms (loadable table)

Loadable inputs: b1_eval_wordlist.json, b1_eval_dtable.json (D-table transcribed verbatim from
bcb604e). No lexicon / Layer-1/2 semantic-table changes; no D-sense re-authoring.

NOT a model run, NOT scoring, NOT evidence. Does not freeze B0 / approve B1 / unblock Track B.
"""
from __future__ import annotations

import functools
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
_VARNA = HERE.parents[1] / "varna_lens"           # symbolu/varna_lens
sys.path.insert(0, str(_VARNA))
import varna_lens as V                              # noqa: E402  (g2p + lexicon; import is cmudict-free)
import sample_text_rule_harness as H               # noqa: E402  (profile, synthesize, BRIDGE)
import generation_conditioning_prompt_demo as G    # noqa: E402  (committed arm-core helpers + WRAPPER)

_WORDLIST_JSON = HERE / "b1_eval_wordlist.json"
_DTABLE_JSON = HERE / "b1_eval_dtable.json"

X_CORE = "this item has no additional symbolic orientation; read the wording in the ordinary way"


def load_wordlist():
    d = json.loads(_WORDLIST_JSON.read_text(encoding="utf-8"))
    return tuple(d["primary"]), tuple(d["privative"])


def load_dtable():
    return json.loads(_DTABLE_JSON.read_text(encoding="utf-8"))["entries"]


PRIMARY, PRIVATIVE = load_wordlist()
DTABLE = load_dtable()
EVAL_WORDS = PRIMARY + PRIVATIVE


class ConditioningUnavailable(RuntimeError):
    """Raised if a real core cannot be built (e.g. G2P missing, or word not in the D-table)."""


def _profile(word):
    return H.profile(word, vowel_mode="field_only")


def _core_A(word, prof):
    syn, _ = H.synthesize(prof)
    return syn


def _core_R(word):
    vals = list(H.BRIDGE.values())
    r = random.Random(f"R:{word}")
    return G._process_line(r.choice(vals), r.choice(vals), r.choice(vals))


def _core_S(word, prof):
    sb, sl, tl = G._pole_keys(prof)
    scr = G._scrambled_bridge()
    b1 = scr.get(sb) or "[unresolved]"
    b2 = scr.get(sl) or "[unresolved]"
    b3 = scr.get(tl) or "[unresolved]"
    return G._process_line(b1, b2, b3)


def _core_C(word, prof):
    cons = [u for u in prof["units"] if u["type"] == "C"]
    vows = [u for u in prof["units"] if u["type"] == "V"]
    onset = cons[0]["arpa"] if cons else "—"
    coda = cons[-1]["arpa"] if cons else "—"
    return (f"onset '{onset}', {len(vows)} vowel nucleus(es), final '{coda}', "
            f"{len(cons)} consonant positions")


def _core_D(word):
    e = DTABLE.get(word.lower())
    if not e:
        raise ConditioningUnavailable(f"no D-table entry for {word!r}")
    return f"{word} — {e['gloss']}; related senses: {', '.join(e['synonyms'])}"


@functools.lru_cache(maxsize=None)
def real_core(word, arm):
    """Bare per-arm conditioning core (deterministic). A/S/C need true G2P; D needs the loadable
    table. Matches the committed harmonized generator exactly. Cached (deterministic)."""
    if arm == "X":
        return X_CORE
    if arm == "R":
        return _core_R(word)
    if arm == "D":
        return _core_D(word)
    prof = _profile(word)                            # A / S / C need the profile
    if arm == "A":
        return _core_A(word, prof)
    if arm == "S":
        return _core_S(word, prof)
    if arm == "C":
        return _core_C(word, prof)
    raise ValueError(f"unknown arm {arm!r}")


def real_conditioning_slot(word, arm, wrapper=None):
    """Full conditioning slot (shared frame + bare core) as the model would receive it (before the
    Task block). Uses the committed harmonized wrapper by default."""
    wrapper = wrapper or G.WRAPPER
    return wrapper.format(conditioning=real_core(word, arm), task="_").split("\n\nTask:\n")[0]


def render_all(words=None, arms=("A", "R", "S", "C", "X", "D")):
    """Return {(word, arm): core} for every combination. Raises if any fails to render."""
    words = words or EVAL_WORDS
    out = {}
    for w in words:
        for a in arms:
            out[(w, a)] = real_core(w, a)
    return out


def main():
    print("b1_real_conditioning — deterministic real conditioning (no model, no scoring)")
    grid = render_all()
    print(f"rendered {len(grid)} (word,arm) cores over {len(EVAL_WORDS)} words × 6 arms")
    a_unres = [w for w in EVAL_WORDS if "[unresolved]" in real_core(w, "A")]
    s_unres = [w for w in EVAL_WORDS if "[unresolved]" in real_core(w, "S")]
    print(f"A [unresolved]: {a_unres or 'none'} | S [unresolved]: {s_unres or 'none'}")


if __name__ == "__main__":
    main()
