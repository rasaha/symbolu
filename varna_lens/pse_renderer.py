#!/usr/bin/env python3
"""PSE Reflection Renderer v2 — deterministic phoneme trajectory → authored reflection.

Implements `PSE_RENDERER_V2_DESIGN.md`. This is a RENDERING layer only: it reads the frozen engine's output
(`varna_lens.analyze`) and converts it into prose. It does NOT change the ontology, decoding rules, or pole
assignment, and it never alters engine output (it only reads).

Pipeline:  Deterministic Engine → Phoneme Trajectory (deterministic) → Authoring (prompt + deterministic
fallback) → three-layer output (Engine / Trajectory / Reflection). Layer 3 is always visibly downstream of
Layers 1–2, and the deterministic chain is preserved in every output. No truth claims are ever made.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from collections import Counter

import varna_lens as V

# ----- lexicon (read-only; for elemental imagery) ---------------------------------------------------
_LEX = None
def _expanded(key):
    global _LEX
    if _LEX is None:
        p = pathlib.Path(__file__).with_name("lexicon_authoritative.json")
        _LEX = json.loads(p.read_text(encoding="utf-8"))["consonants"]
    return (_LEX.get(key) or {}).get("expanded_properties") or {}


def _element_of(key):
    """Map a varṇa's source `elemental` string to one of {earth,water,fire,air,ether}, else None."""
    s = (_expanded(key).get("elemental") or "").lower()
    if not s:
        return None
    if "fire" in s or "agni" in s:
        return "fire"
    if "water" in s or "jala" in s or "liquid" in s:
        return "water"
    if "solid" in s or "kṣiti" in s or "ksiti" in s or "earth" in s or "pṛthv" in s or "prithv" in s:
        return "earth"
    if "air" in s or "vāyu" in s or "vayu" in s or "wind" in s or "gas" in s:
        return "air"
    if "ether" in s or "ākāśa" in s or "akash" in s or "space" in s or "void" in s:
        return "ether"
    return None


# ----- honesty filter -------------------------------------------------------------------------------
FORBIDDEN = ["means", "proves", "reveals", "reveal", "objectively", "objective meaning",
             "true meaning", "decodes reality", "decodes", "represents", "signifies", "hidden meaning"]
PREFERRED = ["evokes", "suggests", "opens", "carries", "moves through", "reflects", "tends toward"]


def honesty_violations(text):
    """Forbidden truth-claim tokens present in `text` (case-insensitive). Empty list = clean."""
    low = text.lower()
    return [w for w in FORBIDDEN if w in low]


# ----- parsing engine output (read-only) ------------------------------------------------------------
def _parse_essence_short(es):
    """(body, summary): body = [(sign, has_transform, gloss)] per scored varṇa; summary = (sign, gloss) of
    the whole-word essence (final vowel ⟹) or None. Pure parse of the engine's essence_short string."""
    summary = None
    s = es
    if "⟹ [" in s:
        head, tail = s.split("⟹ [", 1)
        inner = tail.strip().rstrip("]")
        if inner:
            summary = (inner[0], inner[1:].split("⤳")[0].strip())
        s = head
    body = []
    for tok in s.split(" → "):
        tok = tok.strip()
        if not tok:
            continue
        body.append((tok[0], "⤳" in tok, tok[1:].split("⤳")[0].strip()))
    return body, summary


def _surviving_keys(seq):
    """Varṇa keys aligned 1:1 with essence_short body tokens (engine skips the final vowel and any
    consonant with no lexicon entry — mirror that exactly)."""
    n = len(seq)
    last_v = n - 1 if (n and seq[-1]["type"] == "V") else None
    out = []
    for i, b in enumerate(seq):
        if i == last_v:
            continue
        if b["type"] == "C" and b["key"] not in V.CONS:
            continue
        out.append(b["key"])
    return out


# ----- Layer 2: the Phoneme Trajectory (deterministic) ---------------------------------------------
def _role(i, sign, has_transform):
    if i == 0:
        return "SOURCE"
    if sign == "+":
        return "INTEGRATION"
    if has_transform:
        return "TRANSFORMATION"
    return "TENSION"


def trajectory(word, by="hybrid"):
    """Deterministic trajectory from engine output. Returns the three-layer data (no LLM, no mutation)."""
    kw = {"hybrid": {"hybrid": True}, "sound": {}, "spelling": {"roman": True}}.get(by, {"hybrid": True})
    d, src, _warn = V.analyze(word, model="op", **kw)
    seq = d["sequence"]
    body, summary = _parse_essence_short(d["essence_short"])
    keys = _surviving_keys(seq)
    n = min(len(keys), len(body))

    stages = []
    for i in range(n):
        sign, has_tr, gloss = body[i]
        stages.append({"key": keys[i], "sign": sign, "transform": has_tr, "gloss": gloss,
                       "role": _role(i, sign, has_tr), "element": _element_of(keys[i])})

    if summary is not None:                                  # final vowel → its own RESOLUTION stage
        ess_key = seq[-1]["key"] if (seq and seq[-1]["type"] == "V") else None
        stages.append({"key": ess_key, "sign": summary[0], "transform": False, "gloss": summary[1],
                       "role": "RESOLUTION", "element": _element_of(ess_key) if ess_key else None})
        res_sign = summary[0]
    elif stages:                                             # no final vowel → last varṇa becomes RESOLUTION
        stages[-1]["role"] = "RESOLUTION"
        res_sign = stages[-1]["sign"]
    else:
        res_sign = None

    valence = (d.get("emergent_valence") or {}).get("lean", "mixed")
    n_transform = sum(1 for s in stages if s["transform"])
    density = n_transform / max(1, len(stages))
    ctrl = _controlling_element(stages, valence)
    tone, tone_parts = _tone(valence, density, res_sign)

    layer1 = {"chain": d.get("essence_short"), "interaction": d.get("essence"),
              "essence": d.get("whole_word_essence"), "valence": valence}
    return {"word": word, "by": by, "source": src,
            "layer1": layer1,
            "trajectory": [s["role"] for s in stages],
            "controlling_element": ctrl, "tone": tone, "tone_parts": tone_parts,
            "stages": stages}


def _controlling_element(stages, valence):
    if stages and stages[-1].get("element"):                 # 1. resolution element
        return stages[-1]["element"]
    elems = [s["element"] for s in stages if s.get("element")]
    if elems:                                                # 2. modal element (tie → earliest)
        c = Counter(elems)
        top = max(c.values())
        for e in elems:
            if c[e] == top:
                return e
    if stages and stages[0].get("element"):                  # 3. source element
        return stages[0]["element"]
    return {"binding": "earth", "liberating": "air", "mixed": "water"}.get(valence, "water")  # 4. valence


def _tone(valence, density, res_sign):
    weight = {"binding": "grounded", "liberating": "expansive", "mixed": "turning"}.get(valence, "turning")
    flow = "flowing" if density >= 0.5 else "steady"
    resolution = {"+": "resolved", "−": "open"}.get(res_sign, "suspended")
    primary = flow if density >= 0.5 else weight
    return f"{primary}·{resolution}", {"weight": weight, "flow": flow, "resolution": resolution}


# ----- imagery banks (label → image; single sustained metaphor) -------------------------------------
# Easing/transformation language appears ONLY in the "transform" entry of each element — so it can surface
# only on a beat that carries a ⤳ (a worldly consonant). Non-transform entries are free of easing words.
ELEMENT_IMAGE = {
    "earth": {"source": "settles like a seed in dark ground", "tension": "presses inward like packed stone",
              "integration": "takes root and holds", "transform": "gives way like hard ground",
              "resolution": "comes to rest on solid ground"},
    "water": {"source": "opens like a current finding its source", "tension": "pools and pulls inward",
              "integration": "runs clear and finds its level", "transform": "loosens and lets go like a current",
              "resolution": "comes to rest in steady flow"},
    "fire": {"source": "sparks like a first kindling", "tension": "holds like banked heat",
             "integration": "steadies into a warm coal", "transform": "eases from flare to glow",
             "resolution": "settles into a low, lasting ember"},
    "air": {"source": "draws inward like a breath", "tension": "holds like a charged pause",
            "integration": "settles into an even draft", "transform": "eases outward like a breath",
            "resolution": "opens into clear air"},
    "ether": {"source": "opens like a clearing space", "tension": "waits like a taut silence",
              "integration": "settles into open space", "transform": "widens and eases like stillness",
              "resolution": "comes to rest in spaciousness"},
}
EASING_MARKERS = ["gives way", "loosens", "lets go", "eases", "widens and eases"]

ELEMENT_TAGS = {"earth": ["grounded", "solid"], "water": ["flowing", "clear"], "fire": ["warm", "kindled"],
                "air": ["light", "open"], "ether": ["spacious", "still"]}

MANTRA = {
    "earth": ["Stand in the ground that holds you.", "Let what is heavy grow still.", "Root, and stay rooted.",
              "Soft is also strong.", "Stand in the ground that holds you."],
    "water": ["Find the current and keep to it.", "Run clear, run low.", "Stay with the steady pull.",
              "Soft is also strong.", "Find the current and keep to it."],
    "fire": ["Hold the ember low and steady.", "Let it warm, not burn.", "Where it would harden, keep it kind.",
             "Soft is also strong.", "Hold the ember low and steady."],
    "air": ["Draw the breath and hold it light.", "Stay open, stay clear.", "Carry little, carry it well.",
            "Soft is also strong.", "Draw the breath and hold it light."],
    "ether": ["Rest in the space that opens.", "Let the silence stay.", "Carry less; carry it well.",
              "Soft is also strong.", "Rest in the space that opens."],
}


def _beat_image(stage, ctrl):
    bank = ELEMENT_IMAGE[ctrl]
    if stage["transform"]:
        return bank["transform"]
    return bank.get(stage["role"].lower(), bank["integration"])


def _images(stages, ctrl):
    out = []
    for s in stages:
        img = _beat_image(s, ctrl)
        if not out or out[-1] != img:                        # drop consecutive duplicates
            out.append(img)
    return out


def _join(parts):
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] + ", and " + parts[1]
    return parts[0] + ", " + ", ".join(parts[1:-1]) + ", and " + parts[-1]


# ----- deterministic fallback renderers (one per mode) ----------------------------------------------
def _tags(traj):
    t = list(ELEMENT_TAGS.get(traj["controlling_element"], []))
    t.append(traj["tone_parts"]["weight"])
    t.append(traj["tone_parts"]["resolution"])
    seen, out = set(), []
    for x in t:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def _fallback(word, traj, mode):
    ctrl = traj["controlling_element"]
    stages = traj["stages"]
    imgs = _images(stages, ctrl)
    body = _join(imgs)

    if mode == "essence_line":
        return f"{word.capitalize()} {body}."
    if mode == "reflection":
        return (f"You might notice how {word.lower()} {body}. Where in you does that movement live "
                f"today? There are no right answers — the reading is the one you bring.")
    if mode == "brand_persona":
        return (f"{word.capitalize()} reads like a form that {body}. It evokes "
                f"{', '.join(_tags(traj))} — tends toward a {traj['tone_parts']['weight']} feel.")
    if mode == "name_description":
        return f"{word.capitalize()} — evokes {', '.join(_tags(traj))}; {imgs[0] if imgs else 'a quiet form'}."
    if mode == "mantra":
        return "\n".join(MANTRA[ctrl])
    if mode == "elemental_tableau":
        return "; ".join(i[0].upper() + i[1:] for i in imgs) + "."
    if mode == "micro_myth":
        seed = imgs[0] if imgs else "a small beginning"
        turn = next((_beat_image(s, ctrl) for s in stages if s["transform"]),
                    imgs[1] if len(imgs) > 1 else seed)
        end = imgs[-1] if imgs else seed
        return (f"It begins: it {seed}. Then a turn comes — it {turn}. "
                f"In the end it {end}: a small thing that held, and stayed.")
    raise ValueError(f"unknown mode: {mode}")


# ----- Layer 3 authoring prompt ---------------------------------------------------------------------
MODE_SPEC = {
    "essence_line": "ONE sentence weaving SOURCE→RESOLUTION; neutral voice; end on the resolution image.",
    "reflection": "One short paragraph; second-person, invitational; end with an open question to the reader.",
    "brand_persona": "2–3 sentences; third person; the mood/character the name projects; end with a tag row.",
    "name_description": "One compact line plus 3–5 mood tags ('evokes / tends toward').",
    "mantra": "3–5 short rhythmic lines; second-person, invocational; a repeatable closing line.",
    "elemental_tableau": "A single sensory scene built ONLY from the controlling element; impersonal.",
    "micro_myth": "2–3 sentences: seed → trial/turn → resolution; third person, mythic; lightly held.",
}


def render_prompt(traj, mode):
    beats = "\n".join(f"    {s['role']} · {s['sign']}{'⤳' if s['transform'] else ''} · "
                      f"image: {_beat_image(s, traj['controlling_element'])}" for s in traj["stages"])
    return f"""You are the authoring voice of PSE (Phoneme Symbolic Engine). You render a DETERMINISTIC
phoneme trajectory into prose. You are a rendering layer, not an interpreter: narrate the MOVEMENT given to
you. Never claim the word's true or hidden meaning.

HONESTY RULES (hard):
- NEVER: {', '.join(FORBIDDEN)}, signifies, "is".
- ALWAYS prefer: {', '.join(PREFERRED)}.
- Narrate MOVEMENT, never property labels. Render every pole as an IMAGE, not a word.

FIXED INPUTS (do not add, drop, or reorder stages):
- Word / form: {traj['word']}
- Phoneme Trajectory (roles, in order): {' → '.join(traj['trajectory'])}
- Beats (role · sign · image):
{beats}
- Controlling element (use ONLY this register): {traj['controlling_element']}
- Tone tag (match diction to this): {traj['tone']}
- Mode: {mode} → {MODE_SPEC[mode]}

CONSTRAINTS:
- Sustain ONE metaphor, the controlling element. Do not introduce other elements.
- Transformation/easing language is allowed ONLY on beats marked with ⤳.
- "+" beats are affirmation/anchoring, not change. SOURCE opens; RESOLUTION closes.
- Clause/line count ≈ number of beats. Obey the mode's voice, length, and ending.

OUTPUT: only the Layer-3 prose for {mode}. No headings, no restating the trajectory.
"""


# ----- top-level render -----------------------------------------------------------------------------
MODES = list(MODE_SPEC)


def render(word, mode="essence_line", by="hybrid", use_llm=False):
    """Render a word into the three layers. Layer 3 = LLM if explicitly enabled AND clean, else the
    deterministic fallback. The deterministic chain (Layer 1) is always present."""
    if mode not in MODE_SPEC:
        raise ValueError(f"unknown mode {mode!r}; choose from {MODES}")
    traj = trajectory(word, by)
    prompt = render_prompt(traj, mode)

    text = None
    if use_llm:                                              # uses the EXISTING reflect.call_llm; never auto-called
        try:
            from reflect import call_llm
            out = call_llm(prompt)
            if out and not honesty_violations(out):
                text = out.strip()
        except Exception:
            text = None
    if text is None:
        text = _fallback(word, traj, mode)

    return {"word": word, "mode": mode, "by": by,
            "layer1_engine": traj["layer1"],
            "layer2_trajectory": {"trajectory": traj["trajectory"],
                                  "controlling_element": traj["controlling_element"],
                                  "tone": traj["tone"],
                                  "beats": [{"role": s["role"], "sign": s["sign"], "transform": s["transform"],
                                             "image": _beat_image(s, traj["controlling_element"])}
                                            for s in traj["stages"]]},
            "layer3_reflection": text,
            "prompt": prompt,
            "honesty_ok": not honesty_violations(text)}


def format_text(res):
    """Three-layer human-readable output; the deterministic chain is always shown."""
    L = [f"# PSE — \"{res['word']}\"  ·  mode={res['mode']}  ·  read={res['by']}", "",
         "LAYER 1 — Deterministic Engine",
         f"  chain:   {res['layer1_engine']['chain']}",
         f"  essence: {res['layer1_engine']['essence']}    valence: {res['layer1_engine']['valence']}", "",
         "LAYER 2 — Phoneme Trajectory",
         f"  {' → '.join(res['layer2_trajectory']['trajectory'])}",
         f"  controlling element: {res['layer2_trajectory']['controlling_element']}    "
         f"tone: {res['layer2_trajectory']['tone']}", "",
         "LAYER 3 — Reflection",
         "  " + res["layer3_reflection"].replace("\n", "\n  ")]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="PSE Reflection Renderer v2 (deterministic trajectory → authored reflection).")
    ap.add_argument("word")
    ap.add_argument("--mode", choices=MODES, default="essence_line")
    ap.add_argument("--by", choices=["hybrid", "sound", "spelling"], default="hybrid")
    ap.add_argument("--all", action="store_true", help="render every mode")
    ap.add_argument("--prompt", action="store_true", help="also print the LLM authoring prompt")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    a = ap.parse_args(argv)

    modes = MODES if a.all else [a.mode]
    for i, m in enumerate(modes):
        res = render(a.word, mode=m, by=a.by)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            if i:
                print()
            print(format_text(res))
            if a.prompt:
                print("\n----- AUTHORING PROMPT -----\n" + res["prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
