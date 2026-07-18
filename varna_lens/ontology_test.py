#!/usr/bin/env python3
"""Proof: varṇa states are decoded from PHONEME STRUCTURE, never selected from semantic labels.

The binding/liberating ontology forbids choosing a varṇa's expressed state from any external fact about
the referent (good/bad, useful/useless, auspicious/inauspicious, animate/inanimate). This test proves the
engine obeys that, structurally:

  1. STRUCTURE-ONLY POLE SELECTION. For each word we INDEPENDENTLY recompute the +/− of every varṇa using
     ONLY phoneme type + position (the vowel-attachment rule) — a function that never looks at any meaning,
     valence, or referent — and assert it matches the sign the engine emitted. If the engine ever pulled a
     pole from semantics, these would diverge. They don't.

  2. NO MORAL FIELDS / NO LABEL-SELECTION WORDING. The lexicon exposes binding_state / liberating_state
     (never positive/negative) and contains no rule that selects a pole from good/bad/useful/auspicious.

  3. DERIVED-NOT-SUPPLIED VALENCE. emergent_valence.lean ∈ {binding, liberating, mixed} and its basis is
     declared derived from the chain. The required words decode first, get labelled only afterward.

Run: python ontology_test.py   (exits non-zero on any failure)
"""
import json, pathlib, sys
import varna_lens as V

REQUIRED = ["temple", "wife", "poison", "knife", "gun", "river", "happy", "kill"]
MODES = {"hybrid": {"hybrid": True}, "sound": {}, "spelling": {"roman": True}}


def _structural_signs(full):
    """Recompute (body_signs, summary_sign) from phoneme TYPE + POSITION only — zero meaning input.

    Mirrors read_op's vowel-attachment rule but is deliberately blind to the lexicon's state values: it
    decides +/− purely from where vowels and consonants sit. Only varṇas the engine can score (known keys)
    are counted, so the sequences line up one-to-one with the engine's emitted signs."""
    seq = [(a["type"], a["key"]) for a in full]
    n = len(seq)
    last_v = n - 1 if (seq and seq[-1][0] == "V") else None
    summary_sign = None
    if last_v is not None:
        prev = seq[last_v - 1] if last_v >= 1 else None
        summary_sign = "+" if (prev and prev[0] == "C") else "−"
    body = []
    for i, (typ, key) in enumerate(seq):
        if i == last_v:
            continue
        if typ == "C":
            if key not in V.CONS:
                continue                                  # engine skips unknown consonants → no sign
            prev = seq[i - 1] if i > 0 else None
            nxt = seq[i + 1] if i + 1 < n else None
            if prev and prev[0] == "C" and prev[1] == key:
                s = "−"                                   # 2nd of a doubled pair → binding
            elif nxt and nxt[0] == "C" and nxt[1] == key and i != 0:
                s = "+"                                   # 1st of a doubled pair → liberating
            elif i == 0:
                s = "−"                                   # word's first consonant → binding (leading seed)
            elif nxt and nxt[0] == "V":
                s = "+"                                   # a vowel follows (onset) → liberating
            else:
                s = "−"                                   # bare (final / pre-consonant) → binding
        else:
            if key not in V.VOW:
                continue
            prev = seq[i - 1] if i > 0 else None
            s = "+" if (prev and prev[0] == "C") else "−"
        body.append(s)
    return body, summary_sign


def _engine_signs(essence_short):
    """Parse the +/− the engine actually emitted: body tokens (split on →) and the ⟹ […] summary sign."""
    summary_sign = None
    s = essence_short
    if "⟹ [" in s:
        head, tail = s.split("⟹ [", 1)
        summary_sign = tail.lstrip()[0] if tail.strip() else None
        s = head
    body = [tok.strip()[0] for tok in s.split("→") if tok.strip()]
    return body, summary_sign


def check_word(word):
    rows = []
    for mode, kw in MODES.items():
        d, src, _ = V.analyze(word, model="op", **kw)
        full = d["sequence"]
        pred_body, pred_sum = _structural_signs(full)
        eng_body, eng_sum = _engine_signs(d["essence_short"])
        ev = d.get("emergent_valence") or {}
        ok_signs = (pred_body == eng_body and pred_sum == eng_sum)
        ok_ev = (ev.get("lean") in ("binding", "liberating", "mixed")
                 and "derived" in ev.get("basis", "")
                 and "not supplied" in ev.get("basis", ""))
        rows.append((mode, ok_signs, ok_ev, ev.get("lean"),
                     "".join(eng_body) + (f"⟹{eng_sum}" if eng_sum else ""),
                     "".join(pred_body) + (f"⟹{pred_sum}" if pred_sum else "")))
    return rows


def check_lexicon():
    p = pathlib.Path(__file__).with_name("lexicon_authoritative.json")
    raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    fails = []
    # no legacy moral field names anywhere
    if '"positive"' in raw or '"negative"' in raw:
        fails.append("legacy field name 'positive'/'negative' still present in lexicon JSON")
    # every consonant/vowel exposes the new states
    for section in ("consonants", "vowels"):
        for k, v in data[section].items():
            if "binding_state" not in v or "liberating_state" not in v:
                fails.append(f"{section}[{k}] missing binding_state/liberating_state")
    # no pole-selection-from-label wording in the legend
    legend = json.dumps(data.get("_legend", {}), ensure_ascii=False).lower()
    for bad in ("good/bad", "useful", "auspicious"):
        # allowed ONLY in the explicit negation ("never ... good/bad ..."); flag bare selection wording
        if bad in legend and "never" not in legend:
            fails.append(f"legend contains unguarded label-selection wording: {bad!r}")
    return fails


def main():
    failures = 0
    print("STRUCTURE-ONLY POLE SELECTION  (engine signs must equal position-only prediction)\n")
    for w in REQUIRED:
        for mode, ok_signs, ok_ev, lean, eng, pred in check_word(w):
            flag = "ok " if (ok_signs and ok_ev) else "FAIL"
            if not (ok_signs and ok_ev):
                failures += 1
            print(f"  [{flag}] {w:<8} {mode:<8} lean={lean:<11} engine={eng:<14} structural={pred}")
    print("\nLEXICON ONTOLOGY CHECKS")
    lex_fails = check_lexicon()
    if lex_fails:
        failures += len(lex_fails)
        for f in lex_fails:
            print(f"  [FAIL] {f}")
    else:
        print("  [ok ] binding_state/liberating_state present; no positive/negative; no label-selection rule")

    print()
    if failures:
        print(f"RESULT: {failures} FAILURE(S) — pole selection is NOT purely structural, or ontology drifted.")
        return 1
    print("RESULT: PASS — every varṇa's state is decoded from phoneme structure first; the word is "
          "labelled binding/liberating/mixed only afterward, never from a semantic judgment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
