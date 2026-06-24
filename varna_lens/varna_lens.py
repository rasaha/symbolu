#!/usr/bin/env python3
"""varna_lens.py — a PERSONAL, methodical lens for abstracting a word's "hidden essence" from a FROZEN
varna lexicon, under EXPLICIT acoustic rules.

  ⚠ Interpretive lens, NOT a claim about Sanskrit, NOT universal, and deliberately OUTSIDE the C×R×S engine
    (which firewalls sound→meaning). Discipline = frozen lexicon + fixed rules, applied identically every
    time, with a predict/check log to watch where it flows vs strains.

Lexicon: lexicon.json (consonants: leading binding vṛtti + liberating counter-pole; vowels: layer bridges).

Acoustic rules (your spec):
  (R1) ORDER / polarity:  a consonant FOLLOWED by a vowel (C→V, e.g. "ka") CREATES its vṛtti (+);
       a consonant NOT followed by a vowel (e.g. "ak", coda) DESTROYS / negates it (−).
  (R2) POSITION (two-consonant word):  the 1st consonant exerts a POSITIVE / forward influence;
       the 2nd exerts a NEGATIVE / reactive influence (rebounding on the first).
  e.g. kāla = Ka(+Āśā, forward) → La(+Krūratā, reactive) = "hope projected, rebounds as cruelty";
       ak   = k destroyed = "hope destroyed".

Segmentation into acoustic varṇas: default = literal IAST/roman tokenizer (faithful for transliterated
Sanskrit, which already writes every vowel). Use --g2p for English words via nltk-cmudict (ARPAbet→varṇa,
approximate). Use --varnas for full manual control (authoritative).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# Authoritative set (verbatim from Sanskrit_letters_full.docx). Map the file's positive/negative to the
# names the readers use internally: leading_vritti = NEGATIVE pole, counter_vritti = POSITIVE pole.
LEX = json.loads((_HERE / "lexicon_authoritative.json").read_text())
VOW = LEX["vowels"]
CONS = {k: {"iast": d["iast"], "leading_vritti": d["negative"], "counter_vritti": d["positive"]}
        for k, d in LEX["consonants"].items()}

# Varga (place-of-articulation family) + Devanāgarī, for DISPLAY clarity only — keeps the frozen meaning
# lexicon (iast/positive/negative) clean while making the retroflex Ṭa-varga vs dental ta-varga obvious.
_VARGA = {
    "ka": ("guttural · ka-varga", "क"), "kha": ("guttural · ka-varga", "ख"),
    "ga": ("guttural · ka-varga", "ग"), "gha": ("guttural · ka-varga", "घ"),
    "nga": ("guttural · ka-varga", "ङ"),
    "ca": ("palatal · ca-varga", "च"), "cha": ("palatal · ca-varga", "छ"),
    "ja": ("palatal · ca-varga", "ज"), "jha": ("palatal · ca-varga", "झ"),
    "nya": ("palatal · ca-varga", "ञ"),
    "tta": ("RETROFLEX · Ṭa-varga", "ट"), "ttha": ("RETROFLEX · Ṭa-varga", "ठ"),
    "dda": ("RETROFLEX · Ṭa-varga", "ड"), "ddha": ("RETROFLEX · Ṭa-varga", "ढ"),
    "nna": ("RETROFLEX · Ṭa-varga", "ण"),
    "ta": ("dental · ta-varga", "त"), "tha": ("dental · ta-varga", "थ"),
    "da": ("dental · ta-varga", "द"), "dha": ("dental · ta-varga", "ध"),
    "na": ("dental · ta-varga", "न"),
    "pa": ("labial · pa-varga", "प"), "pha": ("labial · pa-varga", "फ"),
    "ba": ("labial · pa-varga", "ब"), "bha": ("labial · pa-varga", "भ"),
    "ma": ("labial · pa-varga", "म"),
    "ya": ("semivowel · antaḥstha", "य"), "ra": ("semivowel · antaḥstha", "र"),
    "la": ("semivowel · antaḥstha", "ल"), "va": ("semivowel · antaḥstha", "व"),
    "sha": ("sibilant palatal · ūṣma", "श"), "ssa": ("sibilant RETROFLEX · ūṣma", "ष"),
    "sa": ("sibilant dental · ūṣma", "स"), "ha": ("aspirate · ūṣma", "ह"),
    "ksha": ("compound", "क्ष"),
}

# ITRANS-style ASCII for the retroflex (Ṭa-varga) letters, so you can WRITE them distinctly without
# diacritics: CAPITAL T D N (and Th Dh, Sh=ṣa) = retroflex; lowercase t d n (th dh, sh=śa) = dental/palatal.
# (These hit only the manual roman / --varnas path — English words still route through g2p.)
_RETRO_ASCII = [("Th", "ttha"), ("Dh", "ddha"), ("Sh", "ssa"),
                ("T", "tta"), ("D", "dda"), ("N", "nna")]

# surface → lexicon key (longest match first). ASCII read as IAST-ish (ch=cha, c=ca, sh=śa).
_CONS = _RETRO_ASCII + [
         ("kṣ", "ksha"), ("kh", "kha"), ("gh", "gha"), ("ch", "cha"), ("jh", "jha"), ("ṭh", "ttha"),
         ("ḍh", "ddha"), ("th", "tha"), ("dh", "dha"), ("ph", "pha"), ("bh", "bha"), ("sh", "sha"),
         ("ṅ", "nga"), ("ñ", "nya"), ("ṇ", "nna"), ("ṭ", "tta"), ("ḍ", "dda"), ("ś", "sha"),
         ("ṣ", "ssa"), ("x", "ksha"),
         ("k", "ka"), ("q", "ka"), ("g", "ga"), ("c", "ca"), ("j", "ja"), ("t", "ta"), ("d", "da"),
         ("n", "na"), ("p", "pa"), ("b", "ba"), ("m", "ma"), ("y", "ya"), ("r", "ra"), ("l", "la"),
         ("v", "va"), ("w", "va"), ("s", "sa"), ("h", "ha"), ("f", "pha")]
         # lowercase sh = Śa (palatal), Sh = Ṣa (retroflex); q = Ka (qāf→guttural); English f = Pha (p stays Pa)
_VOW = [("ai", "ai"), ("au", "au"), ("aa", "aa"), ("ā", "aa"), ("ii", "ii"), ("ī", "ii"), ("uu", "uu"),
        ("ū", "uu"), ("ṁ", "am"), ("ṃ", "am"), ("ḥ", "ah"), ("a", "a"), ("i", "i"), ("u", "u"),
        ("e", "e"), ("o", "o")]

# ARPAbet (cmudict) → varṇa key, for --g2p English words (approximate: English phonology ≠ varṇas).
_ARPA_C = {"P": "pa", "B": "ba", "T": "ta", "D": "da", "K": "ka", "G": "ga", "M": "ma", "N": "na",
           "NG": "nga", "F": "pha", "V": "va", "TH": "tha", "DH": "dda", "S": "sa", "Z": "sa",
           "SH": "sha", "ZH": "sha", "CH": "ca", "JH": "ja", "HH": "ha", "R": "ra", "L": "la",
           "W": "va", "Y": "ya", "DX": "da"}
_ARPA_V = {"AA": "aa", "AE": "a", "AH": "a", "AO": "o", "AW": "au", "AY": "ai", "EH": "e", "ER": "a",
           "EY": "e", "IH": "i", "IY": "ii", "OW": "o", "OY": "o", "UH": "u", "UW": "uu", "AX": "a"}


def _match(s, pos, table):
    for surf, key in table:
        if s.startswith(surf, pos):
            return key, len(surf)
    return None, 0


def phonemes_roman(word: str):
    """Literal acoustic tokenization (NO inherent-'a' injection, so ka ≠ ak). Returns ([(type,key,surf)],
    warnings). type ∈ {'C','V'}. IAST already writes every vowel, so this is faithful for Sanskrit."""
    s = word.strip()
    pos, out, warn = 0, [], []
    while pos < len(s):
        if s[pos] in " -·.,+":
            pos += 1
            continue
        ck, cl = _match(s, pos, _CONS)
        if ck:
            out.append(("C", ck, s[pos:pos + cl])); pos += cl; continue
        vk, vl = _match(s, pos, _VOW)
        if vk:
            out.append(("V", vk, s[pos:pos + vl])); pos += vl; continue
        warn.append(f"skipped {s[pos]!r}"); pos += 1
    return out, warn


def phonemes_cmudict(word: str):
    """English acoustic breakdown via nltk-cmudict → varṇa keys (approximate)."""
    from nltk.corpus import cmudict
    try:
        d = cmudict.dict()
    except LookupError:
        import nltk; nltk.download("cmudict", quiet=True); d = cmudict.dict()
    arpa = d.get(word.lower())
    if not arpa:
        return [], [f"'{word}' not in cmudict — try --varnas or romanized IAST"]
    out, warn = [], []
    for ph in arpa[0]:
        base = "".join(c for c in ph if c.isalpha())
        if base in _ARPA_V:
            out.append(("V", _ARPA_V[base], ph))
        elif base in _ARPA_C:
            out.append(("C", _ARPA_C[base], ph))
        else:
            warn.append(f"unmapped ARPAbet {ph}")
    return out, warn


def phonemes_explicit(spec: str):
    out, warn = [], []
    for tok in spec.replace(" ", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        seg, w = phonemes_roman(tok)
        out.extend(seg); warn.extend(w)
    return out, warn


_IAST_CHARS = set("āīūṛṝḷṅñṭḍṇśṣṁṃḥĀĪŪṚṜṄÑṬḌṆŚṢṀḤ")
_CMUDICT = None

def _in_cmudict(word):
    """True if the (ascii) word is a real English word in cmudict."""
    global _CMUDICT
    if _CMUDICT is None:
        try:
            from nltk.corpus import cmudict
            try:
                _CMUDICT = cmudict.dict()
            except LookupError:
                import nltk; nltk.download("cmudict", quiet=True); _CMUDICT = cmudict.dict()
        except Exception:
            _CMUDICT = {}
    return word.lower() in _CMUDICT

def auto_phonemes(word):
    """Route automatically: IAST diacritics -> literal Sanskrit; else a real English/other word in the
    pronunciation dictionary -> g2p (pronunciation); else literal fallback. Returns (phonemes, warn, src)."""
    if any(ch in word for ch in _IAST_CHARS):
        ph, w = phonemes_roman(word); return ph, w, "roman/IAST (auto: diacritics)"
    if _in_cmudict(word):
        ph, w = phonemes_cmudict(word); return ph, w, "g2p (auto: dictionary word)"
    ph, w = phonemes_roman(word); return ph, w, "roman (auto: fallback)"


def annotate(phonemes):
    """Tag each consonant with R1 polarity: 'created' if the NEXT phoneme is a vowel, else 'destroyed'."""
    ann = []
    for i, (typ, key, surf) in enumerate(phonemes):
        if typ == "C":
            nxt = phonemes[i + 1] if i + 1 < len(phonemes) else None
            polarity = "created" if (nxt and nxt[0] == "V") else "destroyed"
            ann.append({"type": "C", "key": key, "surface": surf, "polarity": polarity,
                        "data": CONS.get(key)})
        else:
            ann.append({"type": "V", "key": key, "surface": surf, "data": VOW.get(key)})
    return ann


def _short(v):
    return v.split("(")[0].strip() if "(" in v else v


def _verb(pol):
    return "CREATES" if pol == "created" else "DESTROYS"


def consonant_syllable_index(phonemes):
    """Map each phoneme index → its syllable index (pronounceable unit). Intervocalic single C = onset of
    the NEXT syllable; a cluster keeps the last C as the next onset and the rest as the current coda. So
    'karma' (k a r m a) → syllable 0 = 'kar' (k, r), syllable 1 = 'ma'."""
    vow = [i for i, (t, _, _) in enumerate(phonemes) if t == "V"]
    res = {}
    if not vow:
        for i, (t, _, _) in enumerate(phonemes):
            if t == "C":
                res[i] = 0
        return res
    for i in range(vow[0]):
        res[i] = 0                                            # leading onset → syllable 0
    for s, vi in enumerate(vow):
        res[vi] = s
    for s in range(len(vow) - 1):
        between = list(range(vow[s] + 1, vow[s + 1]))
        if len(between) == 1:
            res[between[0]] = s + 1                           # single intervocalic C → next onset
        elif len(between) > 1:
            for i in between[:-1]:
                res[i] = s                                    # cluster: coda of current
            res[between[-1]] = s + 1                          # last → next onset
    for i in range(vow[-1] + 1, len(phonemes)):
        res[i] = len(vow) - 1                                 # trailing coda → last syllable
    return res


def read_db(phonemes):
    """Distortion–Balance model: consonants in the FIRST pronounceable unit (syllable 0) take their
    NEGATIVE vṛtti (distortion seed); all later consonants take their POSITIVE vṛtti (balance)."""
    ann = annotate(phonemes)
    smap = consonant_syllable_index(phonemes)
    out = {"sequence": ann, "model": "distortion_balance"}
    dist, bal = [], []
    for i, a in enumerate(ann):
        if a["type"] != "C" or not a["data"]:
            continue
        if smap.get(i, 0) == 0:
            a["db"] = "distortion(−)"; a["vritti"] = a["data"]["leading_vritti"]; dist.append(a)
        else:
            a["db"] = "balance(+)"; a["vritti"] = a["data"]["counter_vritti"]; bal.append(a)
    if not dist:
        out.update(rule="db (no consonants)", essence="(none)", essence_short="")
        return out
    out["rule"] = f"distortion–balance ({len(dist)} distortion · {len(bal)} balance)"
    d = " · ".join(f"«{a['data']['iast']}» {a['vritti']}" for a in dist)
    b = " · ".join(f"«{a['data']['iast']}» {a['vritti']}" for a in bal) or "(none — monosyllable, all distortion)"
    out["essence"] = f"DISTORTION seed: {d}    →    BALANCE: {b}"
    out["essence_short"] = (" · ".join(_short(a["vritti"]) for a in dist) +
                            (" → " + " · ".join(_short(a["vritti"]) for a in bal) if bal else ""))
    out["distortion"] = [a["data"]["iast"] for a in dist]
    out["balance"] = [a["data"]["iast"] for a in bal]
    return out


def read_vp(phonemes):
    """Vowel-pole model (fully phonology-determined, zero free choices): a consonant FOLLOWED by a vowel
    (CV) takes its POSITIVE pole; a consonant with no vowel of its own (coda) takes its NEGATIVE pole."""
    ann = annotate(phonemes)
    out = {"sequence": ann, "model": "vowel_pole"}
    parts, shorts = [], []
    for a in ann:
        if a["type"] != "C" or not a["data"]:
            continue
        if a["polarity"] == "created":
            v, sign = a["data"]["counter_vritti"], "+"
        else:
            v, sign = a["data"]["leading_vritti"], "\u2212"
        a["vp"], a["vritti"] = sign, v
        parts.append(f"\u00ab{a['data']['iast']}\u00bb({sign}) {v}")
        shorts.append(sign + _short(v))
    if not parts:
        out.update(rule="vp (no consonants)", essence="(none)", essence_short="")
        return out
    out["rule"] = "vowel-pole (CV=+positive, coda=\u2212negative)"
    out["essence"] = " \u2192 ".join(parts)
    out["essence_short"] = " \u2192 ".join(shorts)
    return out


def read_op(phonemes):
    """THE single rule — WORLDLY-REFERENCE order-polarity (Option 1) + final-vowel summary.

    Every varṇa is read by its ONE worldly (bīja) propensity — the consonant's `leading_vritti`
    (the binding/manifest pole) and the vowel's worldly `positive` essence. The displayed meaning is
    ALWAYS that worldly propensity; the +/− sign only marks how the word's sound-order treats it:
      +  AFFIRMED  — the bīja activates the propensity (consonant has a vowel after it AND is not the
                     word's first sound; vowel has a consonant before it = anchored);
      −  DISSOLVING — the sound LEADS the word (the bare un-anchored first varṇa, vowel OR consonant) or
                     sits at a coda, so the structure is *eliminating* that worldly propensity (its
                     dissolution is what the reader reads as the spiritual pole — e.g. aim = ai
                     welfare-materialization, then m eliminates it).
    (Spiritual meaning is therefore DERIVED by dissolving the worldly pole, not printed as its own word —
    the per-letter dissolved/spiritual pole is still shown as "(counter: …)" in the full sequence view.)

    A FINAL vowel is REMOVED from the stitched chain and reported as the whole-word essence; removing it
    turns the preceding consonant into a coda (−, dissolving).

    DOUBLED consonant (two of the same in a row — happy pp, kill ll): the 1st occurrence takes the
    spiritual (counter) pole (+), the 2nd takes the worldly pole (−).

    CLUSTERED consonant (a vowel-less consonant sitting beside another consonant — karma rm, world rld):
    it is "clubbed" to its neighbour and takes the spiritual (counter) pole (+) instead of staying negative.
    A STANDALONE coda (vowel before it, no consonant beside it) stays worldly (−) — so war = …Ra⁻ and
    kāla = …La⁻ are preserved."""
    seq = list(phonemes)
    summary = None
    if seq and seq[-1][0] == "V":
        vt = seq.pop()
        vd = VOW.get(vt[1])
        prev = seq[-1] if seq else None
        spos = bool(prev and prev[0] == "C")
        if vd:
            # whole-word essence = the final vowel's WORLDLY essence (always); sign = anchored/dissolving.
            summary = {"iast": vd["iast"].split(" ")[0], "sign": "+" if spos else "−",
                       "essence": vd["positive"]}
    out = {"sequence": annotate(phonemes), "model": "order_polarity_worldly", "whole_word_essence": summary}
    parts, shorts = [], []
    n = len(seq)
    for i, (typ, key, surf) in enumerate(seq):
        if typ == "C":
            d = CONS.get(key)
            if not d:
                continue
            nxt = seq[i + 1] if i + 1 < n else None
            prev = seq[i - 1] if i > 0 else None
            nxt_v = bool(nxt and nxt[0] == "V")
            nxt_c = bool(nxt and nxt[0] == "C")
            prev_c = bool(prev and prev[0] == "C")
            if prev_c and prev[1] == key:
                # DOUBLED consonant (e.g. happy pp, kill ll): 2nd occurrence takes the WORLDLY pole
                pos = False; v = d["leading_vritti"]; iast = d["iast"]
            elif nxt_c and nxt[1] == key and i != 0:
                # DOUBLED consonant: 1st occurrence takes the SPIRITUAL (counter) pole — e.g. kill =
                # …La⁺ Compassion → La⁻ Cruelty ; happy = …Pa⁺ Affection → Pa⁻ Revulsion
                pos = True; v = d["counter_vritti"]; iast = d["iast"]
            elif i != 0 and not nxt_v and (nxt_c or prev_c):
                # CLUSTERED consonant: a vowel-less consonant that sits beside ANOTHER consonant is
                # "clubbed" to its neighbour and takes the SPIRITUAL (counter) pole (+), instead of staying
                # negative. (A *standalone* coda — vowel before, no consonant beside it — stays worldly −,
                # so war = …Ra⁻ Annihilation and kāla = …La⁻ Cruelty are preserved.)
                pos = True; v = d["counter_vritti"]; iast = d["iast"]
            else:
                # AFFIRMED (+) only if a vowel FOLLOWS it AND it is not the word's first sound. The leading
                # varṇa is always NEGATIVE/dissolving (a bare un-anchored seed); a standalone coda is − too.
                # Worldly pole shown. e.g. the = Ḍa⁻ ; kāla = Ka⁻ Hope → ā⁺ → La⁻ Cruelty.
                pos = nxt_v and i != 0
                v = d["leading_vritti"]          # the WORLDLY (bīja) propensity
                iast = d["iast"]
        else:
            d = VOW.get(key)
            prev = seq[i - 1] if i > 0 else None
            pos = bool(prev and prev[0] == "C")    # anchored by a preceding consonant
            v = d["positive"]                # vowel's WORLDLY active essence
            iast = d["iast"].split(" ")[0]
        sign = "+" if pos else "−"
        if typ == "C" and not pos:
            # a DISSOLVING consonant resolves its worldly pole INTO its spiritual counter-pole
            # (e.g. Ha− Darkness ⤳ Parā-vidyā; the = Ḍa− Shyness ⤳ Fearlessness)
            counter = _short(d["counter_vritti"])
            parts.append(f"«{iast}»({sign}) {_short(v)}  ⤳ {counter}")
            shorts.append(f"{sign}{_short(v)}⤳{counter}")
        else:
            parts.append(f"«{iast}»({sign}) {_short(v)}")
            shorts.append(sign + _short(v))
    out["rule"] = "worldly-reference order-polarity (+ affirmed / − dissolving; final vowel = whole-word essence)"
    out["essence"] = "  →  ".join(parts) if parts else "(none)"
    short = " → ".join(shorts)
    if summary:
        short += f"   ⟹ [{summary['sign']}{_short(summary['essence'])}]"
    out["essence_short"] = short
    return out


def read(phonemes, reverse=False, model="pair"):
    if model == "db":
        return read_db(phonemes)
    if model == "vp":
        return read_vp(phonemes)
    if model == "op":
        return read_op(phonemes)
    ann = annotate(phonemes)
    cons = [a for a in ann if a["type"] == "C" and a["data"]]
    out = {"sequence": ann, "n_consonants": len(cons), "reverse": reverse}
    if not cons:
        out.update(rule="none", essence="(no lexicon consonants)", essence_short="")
        return out
    if len(cons) == 1:
        c = cons[0]; c["role"] = "—"
        out["rule"] = "R1 (single consonant)"
        out["essence"] = f"«{c['data']['iast']}» {_verb(c['polarity'])} {c['data']['leading_vritti']}."
        out["essence_short"] = ("+" if c["polarity"] == "created" else "−") + _short(c["data"]["leading_vritti"])
        out["counter_reading"] = f"Liberation pole: {c['data']['counter_vritti']}"
        return out
    # n>=2: OVERLAPPING PAIRS (R2). Default: 1st = +(giver), 2nd = −(receiver). --reverse flips it so the
    # 2nd is +(giver) and causation runs backward (source = last letter). R1 polarity is a separate tag.
    n = len(cons)
    pairs = []
    for i in range(n - 1):
        a, b = cons[i], cons[i + 1]
        plus, minus = (b, a) if reverse else (a, b)
        pairs.append({"plus": plus["data"], "plus_pol": plus["polarity"],
                      "minus": minus["data"], "minus_pol": minus["polarity"]})
    if reverse:
        for i, c in enumerate(cons):
            c["role"] = "receiver(−)" if i == 0 else ("giver(+)" if i == n - 1 else "giver(+) / receiver(−)")
    else:
        for i, c in enumerate(cons):
            c["role"] = "giver(+)" if i == 0 else ("receiver(−)" if i == n - 1 else "receiver(−) / giver(+)")
    out["pairs"] = pairs
    direction = "2nd→1st (reverse)" if reverse else "1st→2nd"
    out["rule"] = f"R2 overlapping pairs ({n} cons → {n - 1} pair{'s' if n > 2 else ''}); dir={direction}"
    out["essence"] = "   ,   ".join(
        f"«{p['plus']['iast']}»(+ {_short(p['plus']['leading_vritti'])}) → "
        f"«{p['minus']['iast']}»(− {_short(p['minus']['leading_vritti'])})" for p in pairs)
    out["pairs_short"] = " , ".join(f"{p['plus']['iast']}⁺→{p['minus']['iast']}⁻" for p in pairs)
    chain = list(reversed(cons)) if reverse else cons          # causal order: source → result
    out["essence_short"] = " → ".join(_short(c["data"]["leading_vritti"]) for c in chain)
    out["counter_reading"] = "Liberation chain: " + " → ".join(_short(c["data"]["counter_vritti"]) for c in chain)
    return out


def format_reading(word, src, out, warnings):
    L = [f"WORD: {word}    [segmenter={src}]    rule={out['rule']}",
         "  acoustic sequence:"]
    for a in out["sequence"]:
        if a["type"] == "C":
            d = a["data"]
            if d:
                vg, dv = _VARGA.get(a["key"], ("", ""))
                L.append(f"    {a['surface']:<4} C  {dv} {d['iast']:<4} [{vg}]  "
                         f"[{a['polarity'].upper()}{(' / ' + a.get('role','')) if a.get('role') else ''}]  "
                         f"{d['leading_vritti']}   (counter: {d['counter_vritti']})")
            else:
                L.append(f"    {a['surface']:<4} C  (no lexicon entry for {a['key']})")
        else:
            d = a["data"]
            L.append(f"    {a['surface']:<4} V  {d['iast']:<7} {d['positive']} / (shadow) {d['negative']}")
    if out.get("pairs"):
        L.append("")
        L.append(f"  overlapping pairs (R2):  {out.get('pairs_short','')}")
        for p in out["pairs"]:
            pd = "" if p["plus_pol"] == "created" else " (destroyed)"
            md = "" if p["minus_pol"] == "created" else " (destroyed)"
            L.append(f"    «{p['plus']['iast']}»(+){pd} {p['plus']['leading_vritti']}"
                     f"  →  «{p['minus']['iast']}»(−){md} {p['minus']['leading_vritti']}")
    L += ["", f"  ESSENCE: {out['essence']}"]
    if out.get("whole_word_essence"):
        ws = out["whole_word_essence"]
        L.append(f"  WHOLE-WORD ESSENCE (final vowel {ws['iast']}): {ws['sign']} {ws['essence']}")
    if "counter_reading" in out:
        L.append(f"  {out['counter_reading']}")
    L.append(f"  (chain: {out.get('essence_short','')})")
    if warnings:
        L.append(f"  ⚠ {warnings}")
    L.append("  — interpretive lens; not a universal claim; not part of C×R×S —")
    return "\n".join(L)


LOG_HEADER = ["timestamp", "word", "predicted_essence", "actual_meaning", "verdict"]


def log_row(log_path: Path, word, out, actual, verdict):
    new = not log_path.exists()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(LOG_HEADER)
        w.writerow([datetime.now().isoformat(timespec="seconds"), word,
                    out.get("essence_short", "") if out else "(unparseable)", actual, verdict])


def analyze(word, *, g2p=False, varnas=None, roman=False, reverse=False, model="pair"):
    """Segment + read one word. Default = AUTO (g2p for dictionary words, literal for IAST/unknown)."""
    if varnas:
        ph, warn = phonemes_explicit(varnas); src = "explicit"
    elif g2p:
        ph, warn = phonemes_cmudict(word); src = "g2p (forced)"
    elif roman:
        ph, warn = phonemes_roman(word); src = "roman (forced)"
    else:
        ph, warn, src = auto_phonemes(word)
    if not ph:
        return None, src, warn
    return read(ph, reverse=reverse, model=model), src, warn


def _norm_verdict(v):
    v = (v or "").strip().lower()
    if v.startswith("f"):
        return "flowed"
    if v.startswith("st"):
        return "stretched"
    if v.startswith("m"):
        return "missed"
    return ""


def run_batch(path: Path, log_path: Path, *, g2p=False, interactive=False, show=True, reverse=False, model="pair"):
    """Run a word list (one per line; '#' comments; optional 'word<TAB/,/|>actual_meaning'). Appends a
    predict/check row per word to log_path. With --interactive it prompts for actual + verdict in one pass;
    otherwise it leaves verdict BLANK so you fill it offline WITHOUT bias (predict-then-check)."""
    words = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[\t,|]", line, 1)
        words.append((parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""))

    new = not log_path.exists()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    verdicts = Counter()
    with open(log_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(LOG_HEADER)
        for word, actual in words:
            out, src, warn = analyze(word, g2p=g2p, reverse=reverse, model=model)
            pred = out.get("essence_short", "") if out else "(unparseable)"
            verdict = ""
            if interactive:
                print("\n" + (format_reading(word, src, out, warn) if out
                              else f"WORD: {word}  — unparseable {warn}"))
                if not actual:
                    actual = input(f"  actual meaning of '{word}'? ").strip()
                verdict = _norm_verdict(input("  verdict [flowed/stretched/missed/skip]? "))
            elif show:
                line = f"  {word:<14} → {pred}"
                print(line + (f"   ⚠{warn}" if warn else ""))
            w.writerow([datetime.now().isoformat(timespec="seconds"), word, pred, actual, verdict])
            if verdict:
                verdicts[verdict] += 1
    print(f"\n[{len(words)} words → {log_path}]")
    if not interactive:
        print("  verdicts left BLANK — fill the 'verdict' column (flowed/stretched/missed) in the CSV,")
        print(f"  then:  python {Path(__file__).name} --tally {log_path}")
    if verdicts:
        _print_tally(verdicts, len(words))


def _print_tally(counts: Counter, total: int):
    judged = sum(counts.values())
    print(f"\n  TALLY  (judged {judged}/{total}):")
    for k in ("flowed", "stretched", "missed"):
        n = counts.get(k, 0)
        pct = (100.0 * n / judged) if judged else 0.0
        bar = "█" * int(round(pct / 5))
        print(f"    {k:<10} {n:>3}  {pct:5.1f}%  {bar}")
    if judged:
        print(f"\n  honest read: flowed {100*counts.get('flowed',0)/judged:.0f}% vs "
              f"missed {100*counts.get('missed',0)/judged:.0f}%  "
              f"— if flowed doesn't clearly beat missed on words you couldn't retrofit, it's the lens's "
              f"flexibility, not the language.")


def tally_csv(path: Path):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    counts = Counter(_norm_verdict(r.get("verdict", "")) for r in rows)
    counts.pop("", None)
    _print_tally(counts, len(rows))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Personal varna-essence lens (frozen lexicon + acoustic rules).")
    ap.add_argument("word", nargs="?", help="romanized word, e.g. kala / kāla / ak")
    ap.add_argument("--g2p", action="store_true", help="force g2p pronunciation (English/any language)")
    ap.add_argument("--roman", action="store_true", help="force literal IAST/roman reading (skip auto g2p)")
    ap.add_argument("--varnas", help="explicit acoustic order, e.g. 'k,a,l,a' or 'ka,la' (authoritative)")
    ap.add_argument("--batch", help="run a word-list file (one word per line) through the lens in one pass")
    ap.add_argument("--interactive", action="store_true", help="with --batch: prompt actual+verdict per word")
    ap.add_argument("--reverse", action="store_true", help="flip R2: 2nd consonant is +(giver); causation runs backward")
    ap.add_argument("--db", action="store_true", help="Distortion-Balance model: first syllable=negative(distortion), rest=positive(balance)")
    ap.add_argument("--pairs", action="store_true", help="(legacy) overlapping-pairs model")
    ap.add_argument("--vp-consonly", action="store_true", help="(legacy) vowel-pole on consonants only (no vowel meanings)")
    ap.add_argument("--tally", help="read a filled log CSV and print the flowed/stretched/missed tally")
    ap.add_argument("--log", default=None, help="predict/check CSV (default for --batch: varna_predict_check_log.csv)")
    ap.add_argument("--actual", default="", help="actual meaning (for --log)")
    ap.add_argument("--verdict", choices=("flowed", "stretched", "missed"), help="your honest verdict (--log)")
    args = ap.parse_args(argv)

    if args.tally:
        tally_csv(Path(args.tally)); return 0
    if args.batch:
        log = Path(args.log or "varna_predict_check_log.csv")
        run_batch(Path(args.batch), log, g2p=args.g2p, interactive=args.interactive, reverse=args.reverse, model=("pair" if (args.pairs or args.reverse) else "db" if args.db else "vp" if args.vp_consonly else "op"))
        return 0

    if not args.word and not args.varnas:
        ap.error("give a word, --varnas, --batch, or --tally")
    if args.varnas:
        ph, warn = phonemes_explicit(args.varnas); src = "explicit"
    elif args.g2p:
        ph, warn = phonemes_cmudict(args.word); src = "g2p (forced)"
    elif args.roman:
        ph, warn = phonemes_roman(args.word); src = "roman (forced)"
    else:
        ph, warn, src = auto_phonemes(args.word)
    if not ph:
        print(f"could not segment {args.word!r}: {warn}"); return 2
    out = read(ph, reverse=args.reverse, model=("pair" if (args.pairs or args.reverse) else "db" if args.db else "vp" if args.vp_consonly else "op"))
    print(format_reading(args.word or args.varnas, src, out, warn))
    if args.log:
        if not args.verdict:
            ap.error("--log needs --verdict (flowed/stretched/missed) and ideally --actual")
        log_row(Path(args.log), args.word or args.varnas, out, args.actual, args.verdict)
        print(f"\n  [logged → {args.log}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
