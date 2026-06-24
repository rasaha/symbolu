#!/usr/bin/env python3
"""Cross-linguistic convergence demo — the ENCODING direction (concept -> sound).

The observation: across many *unrelated* language families, the word for "mother" converges on a
nasal + open vowel (overwhelmingly /m/ → "ma"). This is NOT Sanskrit influence — it's independent
convergence, i.e. humans repeatedly *felt* the same sound fit the role. This is the one place the varṇa
intuition meets real, established data (Jakobson 1960, "Why 'Mama' and 'Papa'?"; Blasi et al. 2016, PNAS,
sound–meaning biases across ~4000+ languages).

Honesty: this is a HAND-CURATED illustrative sample (not a controlled typological study), forms are
romanized, and the pattern is strong but NOT universal — real exceptions are included, not hidden.
Cause is articulatory (an infant's earliest, easiest sound during nursing is a labial nasal), so the
varṇa system did not *create* the link — at best it *named* a quality the link already has.
"""
import re
import varna_lens as V

# (language, family, mother-word romanized)  — chosen to span independent families.
MOTHER = [
    ("English", "IE·Germanic", "mother"), ("German", "IE·Germanic", "mutter"),
    ("Dutch", "IE·Germanic", "moeder"), ("Spanish", "IE·Romance", "madre"),
    ("French", "IE·Romance", "maman"), ("Italian", "IE·Romance", "madre"),
    ("Portuguese", "IE·Romance", "mae"), ("Russian", "IE·Slavic", "mama"),
    ("Polish", "IE·Slavic", "matka"), ("Greek", "IE·Hellenic", "mana"),
    ("Hindi", "IE·Indo-Aryan", "maa"), ("Persian", "IE·Iranian", "madar"),
    ("Lithuanian", "IE·Baltic", "mama"), ("Welsh", "IE·Celtic", "mam"),
    ("Mandarin", "Sino-Tibetan", "mama"), ("Swahili", "Niger-Congo·Bantu", "mama"),
    ("Zulu", "Niger-Congo·Bantu", "umama"), ("Quechua", "Quechuan", "mama"),
    ("Tamil", "Dravidian", "amma"), ("Telugu", "Dravidian", "amma"),
    ("Arabic", "Afro-Asiatic", "mama"), ("Hebrew", "Afro-Asiatic", "ima"),
    ("Korean", "Koreanic", "eomma"), ("Navajo", "Na-Dene", "ama"),
    ("Hungarian", "Uralic", "anya"), ("Turkish", "Turkic", "anne"),
    ("Tagalog", "Austronesian", "nanay"), ("Igbo", "Niger-Congo", "nne"),
    ("Finnish", "Uralic", "aiti"), ("Japanese", "Japonic", "haha"),
    ("Georgian", "Kartvelian", "deda"),
]


def classify(word):
    w = word.lower()
    onset = next((c for c in w if c.isalpha()), "")
    has_nasal = bool(re.search(r"[mn]", w))
    if onset == "m":
        return "m-onset"
    if onset == "n":
        return "n-onset"
    if has_nasal:
        return "nasal-inside"
    return "no-nasal"


def main():
    rows = [(lang, fam, w, classify(w)) for lang, fam, w in MOTHER]
    n = len(rows)
    m_onset = sum(1 for *_, c in rows if c == "m-onset")
    nasal = sum(1 for *_, c in rows if c != "no-nasal")
    print(f"\n'MOTHER' across {n} languages from independent families\n" + "=" * 60)
    for lang, fam, w, c in rows:
        flag = "  <-- exception (no nasal)" if c == "no-nasal" else ""
        print(f"  {lang:11} {fam:18} {w:8} [{c}]{flag}")
    print("-" * 60)
    print(f"  /m/ onset            : {m_onset}/{n}  ({100*m_onset//n}%)")
    print(f"  any nasal (m or n)   : {nasal}/{n}  ({100*nasal//n}%)")
    print(f"  exceptions (no nasal): {n - nasal}/{n}  -> {[l for l,_,_,c in rows if c=='no-nasal']}")

    print("\nVarṇa reading of the m-initial forms (all converge on «Ma»):")
    for lang, fam, w, c in rows:
        if c == "m-onset":
            d, _s, _w = V.analyze(w.lower(), roman=True)
            print(f"  {w:8} -> {d['essence_short']}")
    ma = V.CONS["ma"]
    print(f"\n  Lexicon Ma: worldly = {ma['leading_vritti']}  |  counter = {ma['counter_vritti']}")
    print("\nHonest reading:")
    print("- The convergence is REAL and independent (not Sanskrit-sourced): a strong cross-family bias")
    print("  toward a nasal + open vowel for 'mother'. This supports the ENCODING direction.")
    print("- It is NOT universal (see exceptions) and its CAUSE is articulatory (Jakobson): the labial")
    print("  nasal is an infant's earliest nursing sound. So sound did not 'decode' mother — humans")
    print("  converged on an easy, warm sound, and traditions (incl. varṇa) later NAMED that quality.")
    print("- This is the one experiment the system could win HONESTLY: cross-linguistic phonetic")
    print("  iconicity (Blasi et al. 2016), grounded in real data — about SOUND, not the gloss decoder.")


if __name__ == "__main__":
    main()
