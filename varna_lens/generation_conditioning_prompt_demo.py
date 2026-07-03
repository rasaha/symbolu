#!/usr/bin/env python3
"""Generation-conditioning PROMPT-CONSTRUCTION demo — NO MODEL, NO GENERATION, NO SCORING.

Builds and prints format-matched *conditioning prompts* for six arms (A/R/S/C/X/D) around a user
task + key word, so the arms can be inspected side by side. It constructs prompts ONLY — it never
calls a model, never generates an answer, never scores anything.

Arms (only the conditioning slot changes; wrapper/format identical):
  A  real resonance conditioning   (Layer 1/2 synthesis of the key word, via the committed harness)
  R  random resonance conditioning (random pole-paraphrases through the same text template)
  S  scrambled resonance           (key-word structure with a permuted bridge table)
  C  surface/phoneme/coda-only     (sound-structure, no varṇa identity, no glosses)
  X  context-only / neutral slot
  D  dictionary-only semantic expansion (lexical senses; NOT resonance)

Framing: this is a PROMPT-CONSTRUCTION DEMO. It is NOT a model run, NOT evidence, NOT scored, NOT a
Track G rescue, NOT Track B support. The reframed objective (engineering utility: does real resonance
conditioning steer/improve generation better than controls?) has an INFORMED-NEGATIVE prior — Track F
already returned CORRECTNESS_DEGRADED. No arm claims resonance is true; no ontology / Sanskrit /
semantic-truth / word-origin claims.
"""
from __future__ import annotations

import argparse
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sample_text_rule_harness as H   # noqa: E402  (Layer 1/2 harness: profile, synthesize, BRIDGE)

BANNER = "EXPLORATORY_PROMPT_CONSTRUCTION_ONLY — no model call, not scored, not evidence"
WRAPPER = ("[soft orientation — does not override the task]\n"
           "{conditioning}\n\n"
           "Task:\n{task}")
ARMS = ("A", "R", "S", "C", "X", "D")
SCRAMBLE_SEED = "gen_cond_scramble_v1"

# phrases that would turn a conditioning prompt into a truth/ontology claim — never allowed
FORBIDDEN_CLAIMS = ("therefore the word", "this proves", "proves that", "sanskrit", "varna", "varṇa",
                    "encodes", "ontolog", "true meaning", "the word means", "word means")

# FROZEN illustrative dictionary/synonym field for arm D (demo only; not a runtime lookup)
DICT = {
    "mercy": {"gloss": "compassion or forbearance shown toward another",
              "synonyms": ["compassion", "clemency", "leniency", "forgiveness", "kindness"]},
    "love": {"gloss": "deep affection or attachment",
             "synonyms": ["affection", "care", "fondness", "devotion", "tenderness"]},
    "anger": {"gloss": "strong displeasure or hostility",
              "synonyms": ["rage", "fury", "hostility", "irritation", "resentment"]},
    "peace": {"gloss": "freedom from disturbance; calm",
              "synonyms": ["calm", "tranquility", "harmony", "quiet", "serenity"]},
}


class ForbiddenClaim(ValueError):
    """Raised if a constructed prompt would assert ontology/Sanskrit/semantic-truth."""


def _process_line(b1, b2, b3):
    return f"{b1} moves toward {b2}, and {b3} is the resolving principle"


def _scrambled_bridge():
    keys, vals = list(H.BRIDGE), list(H.BRIDGE.values())
    random.Random(SCRAMBLE_SEED).shuffle(vals)
    return dict(zip(keys, vals))


def _pole_keys(prof):
    """Canonical (seed_binding, seed_liberating, transformer_liberating) gloss keys from a profile."""
    units = prof["units"]
    seed = next((r for r in units if r["role"] == "ONSET_SEED"), None)
    trans = next((r for r in reversed(units) if r["role"] == "TRANSFORMER"), None)
    sb = sl = tl = None
    if seed:
        e = H._lex_entry("C", seed["key"])
        if e:
            sb, sl = H._canon(e["binding_state"]), H._canon(e["liberating_state"])
    if trans and trans is not seed:
        e = H._lex_entry("C", trans["key"])
        if e:
            tl = H._canon(e["liberating_state"])
    return sb, sl, tl


def _conditioning_texts(key_word):
    """Return {arm: conditioning_text}, plus (g2p_ok, warnings). Never calls a model."""
    warnings = []
    try:
        prof = H.profile(key_word)
        g2p_ok = True
    except H.G2PUnavailable as e:
        prof, g2p_ok = None, False
        warnings.append(str(e))

    texts = {}
    # A — real resonance (Layer 1/2 synthesis)
    if g2p_ok:
        a_syn, _ = H.synthesize(prof)
        if "[unresolved]" in a_syn:
            warnings.append("A: some poles unbridged → [unresolved] (harness did not invent)")
        texts["A"] = ("A latent-process reading (an internal orientation, not a definition; a "
                      f"stylistic prior only) can be read as: {a_syn}. Use as a soft tonal/conceptual "
                      "guide; it may orient the generation toward that movement.")
    else:
        texts["A"] = "[G2P_UNAVAILABLE — arm A not constructed]"

    # R — random resonance (random pole-paraphrases through the same template)
    vals = list(H.BRIDGE.values())
    r = random.Random(f"R:{key_word}")
    texts["R"] = ("A randomized orientation (control; not derived from the key word): "
                  f"{_process_line(r.choice(vals), r.choice(vals), r.choice(vals))}. "
                  "Use as a soft tonal/conceptual guide.")

    # S — scrambled resonance (key-word structure, permuted bridge attachments)
    if g2p_ok:
        sb, sl, tl = _pole_keys(prof)
        scr = _scrambled_bridge()
        b1 = scr.get(sb) or "[unresolved]"; b2 = scr.get(sl) or "[unresolved]"; b3 = scr.get(tl) or "[unresolved]"
        texts["S"] = ("A scrambled-attachment orientation (control; key-word structure with permuted "
                      f"associations): {_process_line(b1, b2, b3)}. Use as a soft tonal/conceptual guide.")
    else:
        texts["S"] = "[G2P_UNAVAILABLE — arm S not constructed]"

    # C — surface / phoneme / coda-only (structure, no glosses)
    if g2p_ok:
        cons = [u for u in prof["units"] if u["type"] == "C"]
        vows = [u for u in prof["units"] if u["type"] == "V"]
        onset = cons[0]["arpa"] if cons else "—"; coda = cons[-1]["arpa"] if cons else "—"
        texts["C"] = (f"Sound-structure only (control; no associations): onset '{onset}', {len(vows)} "
                      f"vowel nucleus(es), final '{coda}', {len(cons)} consonant positions. "
                      "Use as a soft rhythmic/tonal guide.")
    else:
        texts["C"] = "[G2P_UNAVAILABLE — arm C not constructed]"

    # X — neutral
    texts["X"] = "Use the user task as written; no additional symbolic orientation."

    # D — dictionary-only semantic expansion (clearly separate from resonance)
    d = DICT.get(key_word.lower())
    if d:
        texts["D"] = ("Dictionary/synonym field (control; lexical senses, not resonance): "
                      f"{key_word} — {d['gloss']}; related senses: {', '.join(d['synonyms'])}. "
                      "Use as a soft conceptual guide.")
    else:
        texts["D"] = (f"Dictionary/synonym field (control; not resonance): [no entry for '{key_word}' "
                      "in this demo's frozen table].")
    return texts, g2p_ok, warnings


def build_prompts(user_task, key_word):
    """Return {arm: full_prompt}. Same wrapper for every arm; only the conditioning slot differs.
    Raises ForbiddenClaim if any prompt would assert ontology/Sanskrit/semantic-truth."""
    texts, _g2p_ok, _warn = _conditioning_texts(key_word)
    prompts = {}
    for arm in ARMS:
        p = WRAPPER.format(conditioning=texts[arm], task=user_task)
        low = p.lower()
        for bad in FORBIDDEN_CLAIMS:
            if bad in low:
                raise ForbiddenClaim(f"arm {arm} prompt contains forbidden claim {bad!r}")
        prompts[arm] = p
    return prompts


def render_demo(user_task, key_word):
    texts, g2p_ok, warnings = _conditioning_texts(key_word)
    prompts = build_prompts(user_task, key_word)
    lines = [BANNER, f"key_word: {key_word!r} | g2p_for_A: {'ok' if g2p_ok else 'UNAVAILABLE'}",
             f"user_task: {user_task!r}"]
    for arm in ARMS:
        lines.append(f"\n----- ARM {arm} -----")
        lines.append(prompts[arm])
    if warnings:
        lines.append("\nwarnings: " + " | ".join(warnings))
    lines.append("\nno_model_called: true | no_generated_answer_produced: true | not_scored: true")
    lines.append(BANNER)
    return "\n".join(lines)


_SAMPLES = [
    ("mercy", "Write a short reflective paragraph about mercy."),
    ("love", "Write a gentle message about love."),
    ("anger", "Write a short metaphor about anger."),
    ("peace", "Write a calming paragraph about peace."),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic generation-conditioning PROMPT demo "
                                             "(no model, no generation, no scoring).")
    ap.add_argument("--key", default=None, help="key word")
    ap.add_argument("--task", default=None, help="user task text")
    args = ap.parse_args(argv)
    if args.key and args.task:
        print(render_demo(args.task, args.key))
    else:
        for kw, task in _SAMPLES:
            print(render_demo(task, kw))
            print("\n" + "=" * 88 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
