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
LEX = json.loads((_HERE / "lexicon.json").read_text())
CONS, VOW = LEX["consonants"], LEX["vowels"]

# surface → lexicon key (longest match first). ASCII read as IAST-ish (ch=cha, c=ca, sh=śa).
_CONS = [("kṣ", "ksha"), ("kh", "kha"), ("gh", "gha"), ("ch", "cha"), ("jh", "jha"), ("ṭh", "ttha"),
         ("ḍh", "ddha"), ("th", "tha"), ("dh", "dha"), ("ph", "pha"), ("bh", "bha"), ("ṅ", "nga"),
         ("ñ", "nya"), ("ṇ", "nna"), ("ṭ", "tta"), ("ḍ", "dda"), ("ś", "sha"), ("ṣ", "ssa"), ("x", "ksha"),
         ("k", "ka"), ("g", "ga"), ("c", "ca"), ("j", "ja"), ("t", "ta"), ("d", "da"), ("n", "na"),
         ("p", "pa"), ("b", "ba"), ("m", "ma"), ("y", "ya"), ("r", "ra"), ("l", "la"), ("v", "va"),
         ("w", "va"), ("s", "sa"), ("h", "ha")]
_VOW = [("ai", "ai"), ("au", "au"), ("aa", "aa"), ("ā", "aa"), ("ii", "ii"), ("ī", "ii"), ("uu", "uu"),
        ("ū", "uu"), ("ṁ", "am"), ("ṃ", "am"), ("ḥ", "ah"), ("a", "a"), ("i", "i"), ("u", "u"),
        ("e", "e"), ("o", "o")]

# ARPAbet (cmudict) → varṇa key, for --g2p English words (approximate: English phonology ≠ varṇas).
_ARPA_C = {"P": "pa", "B": "ba", "T": "ta", "D": "da", "K": "ka", "G": "ga", "M": "ma", "N": "na",
           "NG": "nga", "F": "pha", "V": "va", "TH": "tha", "DH": "dha", "S": "sa", "Z": "sa",
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


def read(phonemes):
    ann = annotate(phonemes)
    cons = [a for a in ann if a["type"] == "C" and a["data"]]
    out = {"sequence": ann, "n_consonants": len(cons)}
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
    # n>=2: OVERLAPPING PAIRS (R2). Each adjacent pair: 1st = +(giver/source), 2nd = −(receiver/result).
    # A middle consonant is the − of the pair on its left and the + of the pair on its right.
    # R1 (create/destroy from vowel order) is a SEPARATE tag shown per consonant.
    n = len(cons)
    for i, c in enumerate(cons):
        c["role"] = "giver(+)" if i == 0 else ("receiver(−)" if i == n - 1 else "receiver(−) / giver(+)")
    pairs = []
    for i in range(n - 1):
        a, b = cons[i], cons[i + 1]
        pairs.append({"plus": a["data"], "plus_pol": a["polarity"],
                      "minus": b["data"], "minus_pol": b["polarity"]})
    out["pairs"] = pairs
    out["rule"] = f"R2 overlapping pairs ({n} consonants → {n - 1} pair{'s' if n > 2 else ''}); R1 per consonant"
    out["essence"] = "   ,   ".join(
        f"«{p['plus']['iast']}»(+ {_short(p['plus']['leading_vritti'])}) → "
        f"«{p['minus']['iast']}»(− {_short(p['minus']['leading_vritti'])})" for p in pairs)
    out["pairs_short"] = " , ".join(f"{p['plus']['iast']}⁺→{p['minus']['iast']}⁻" for p in pairs)
    out["essence_short"] = " → ".join(_short(c["data"]["leading_vritti"]) for c in cons)
    out["counter_reading"] = "Liberation chain: " + " → ".join(_short(c["data"]["counter_vritti"]) for c in cons)
    return out


def format_reading(word, src, out, warnings):
    L = [f"WORD: {word}    [segmenter={src}]    rule={out['rule']}",
         "  acoustic sequence:"]
    for a in out["sequence"]:
        if a["type"] == "C":
            d = a["data"]
            if d:
                L.append(f"    {a['surface']:<4} C  {a['key']:<5} {d['iast']:<4}  "
                         f"[{a['polarity'].upper()}{(' / ' + a.get('role','')) if a.get('role') else ''}]  "
                         f"{d['leading_vritti']}   (counter: {d['counter_vritti']})")
            else:
                L.append(f"    {a['surface']:<4} C  (no lexicon entry for {a['key']})")
        else:
            d = a["data"]
            L.append(f"    {a['surface']:<4} V  {d['iast']:<7} {d['positive']} / (shadow) {d['negative']}"
                     f"   ·  {d['bridge']}")
    if out.get("pairs"):
        L.append("")
        L.append(f"  overlapping pairs (R2):  {out.get('pairs_short','')}")
        for p in out["pairs"]:
            pd = "" if p["plus_pol"] == "created" else " (destroyed)"
            md = "" if p["minus_pol"] == "created" else " (destroyed)"
            L.append(f"    «{p['plus']['iast']}»(+){pd} {p['plus']['leading_vritti']}"
                     f"  →  «{p['minus']['iast']}»(−){md} {p['minus']['leading_vritti']}")
    L += ["", f"  ESSENCE: {out['essence']}"]
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


def analyze(word, *, g2p=False, varnas=None):
    """Segment + read one word. Returns (out|None, src, warnings)."""
    if varnas:
        ph, warn = phonemes_explicit(varnas); src = "explicit"
    elif g2p:
        ph, warn = phonemes_cmudict(word); src = "cmudict(English)"
    else:
        ph, warn = phonemes_roman(word); src = "roman/IAST"
    if not ph:
        return None, src, warn
    return read(ph), src, warn


def _norm_verdict(v):
    v = (v or "").strip().lower()
    if v.startswith("f"):
        return "flowed"
    if v.startswith("st"):
        return "stretched"
    if v.startswith("m"):
        return "missed"
    return ""


def run_batch(path: Path, log_path: Path, *, g2p=False, interactive=False, show=True):
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
            out, src, warn = analyze(word, g2p=g2p)
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
    ap.add_argument("--g2p", action="store_true", help="English acoustic breakdown via nltk-cmudict (approx)")
    ap.add_argument("--varnas", help="explicit acoustic order, e.g. 'k,a,l,a' or 'ka,la' (authoritative)")
    ap.add_argument("--batch", help="run a word-list file (one word per line) through the lens in one pass")
    ap.add_argument("--interactive", action="store_true", help="with --batch: prompt actual+verdict per word")
    ap.add_argument("--tally", help="read a filled log CSV and print the flowed/stretched/missed tally")
    ap.add_argument("--log", default=None, help="predict/check CSV (default for --batch: varna_predict_check_log.csv)")
    ap.add_argument("--actual", default="", help="actual meaning (for --log)")
    ap.add_argument("--verdict", choices=("flowed", "stretched", "missed"), help="your honest verdict (--log)")
    args = ap.parse_args(argv)

    if args.tally:
        tally_csv(Path(args.tally)); return 0
    if args.batch:
        log = Path(args.log or "varna_predict_check_log.csv")
        run_batch(Path(args.batch), log, g2p=args.g2p, interactive=args.interactive)
        return 0

    if not args.word and not args.varnas:
        ap.error("give a word, --varnas, --batch, or --tally")
    if args.varnas:
        ph, warn = phonemes_explicit(args.varnas); src = "explicit"
    elif args.g2p:
        ph, warn = phonemes_cmudict(args.word); src = "cmudict(English)"
    else:
        ph, warn = phonemes_roman(args.word); src = "roman/IAST"
    if not ph:
        print(f"could not segment {args.word!r}: {warn}"); return 2
    out = read(ph)
    print(format_reading(args.word or args.varnas, src, out, warn))
    if args.log:
        if not args.verdict:
            ap.error("--log needs --verdict (flowed/stretched/missed) and ideally --actual")
        log_row(Path(args.log), args.word or args.varnas, out, args.actual, args.verdict)
        print(f"\n  [logged → {args.log}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
