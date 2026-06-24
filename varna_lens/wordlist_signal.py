"""Curated wordlist for the acoustic-signal pre-registered test (PREREG_ACOUSTIC_SIGNAL.md).

Each entry: (lang, word, gloss, valence, pron)
  lang   : 'sa' Sanskrit | 'en' English | 'ja' Japanese | 'zh' Mandarin | 'ur' Urdu/Persian
  gloss  : short true meaning (the target the blind judge must recover)
  valence: 'p' positive | 'n' negative | '0' neutral   (for valence-matched distractor sampling)
  pron   : how to segment to sounds — 'roman' (literal IAST), 'g2p' (English pronunciation),
           or an explicit native-phonetics varṇa list e.g. 'k,o,k,o,r,o'.

NOTE: pronunciations are the *defensible native* forms (NOT an interpreter's preferred respelling);
e.g. kokoro = k,o,k,o,r,o (no phantom /h/). This is required for the blind test to be fair.
"""

# (word, gloss, valence) — Sanskrit, read literally as IAST (pron='roman')
_SA = [
    ("kāla", "time", "0"), ("lobha", "greed", "n"), ("moha", "delusion", "n"), ("kāma", "desire", "0"),
    ("krodha", "anger", "n"), ("bhaya", "fear", "n"), ("prema", "love", "p"), ("jala", "water", "0"),
    ("agni", "fire", "0"), ("vāyu", "wind", "0"), ("manas", "mind", "0"), ("deha", "body", "0"),
    ("jīva", "soul", "p"), ("mṛtyu", "death", "n"), ("satya", "truth", "p"), ("dharma", "righteousness", "p"),
    ("karma", "action", "0"), ("māyā", "illusion", "n"), ("śānti", "peace", "p"), ("ānanda", "bliss", "p"),
    ("duḥkha", "suffering", "n"), ("sukha", "happiness", "p"), ("jñāna", "knowledge", "p"),
    ("bhakti", "devotion", "p"), ("yoga", "union", "p"), ("guru", "teacher", "p"), ("rāja", "king", "0"),
    ("deva", "god", "p"), ("asura", "demon", "n"), ("nara", "man", "0"), ("nārī", "woman", "0"),
    ("putra", "son", "0"), ("mātā", "mother", "p"), ("pitā", "father", "0"), ("gṛha", "house", "0"),
    ("vana", "forest", "0"), ("parvata", "mountain", "0"), ("nadī", "river", "0"), ("sūrya", "sun", "p"),
    ("candra", "moon", "0"), ("tārā", "star", "0"), ("puṣpa", "flower", "p"), ("vṛkṣa", "tree", "0"),
    ("phala", "fruit", "0"), ("anna", "food", "p"), ("kṣudhā", "hunger", "n"), ("nidrā", "sleep", "0"),
    ("svapna", "dream", "0"), ("netra", "eye", "0"), ("hasta", "hand", "0"), ("pāda", "foot", "0"),
    ("mukha", "face", "0"), ("hṛdaya", "heart", "p"), ("rakta", "blood", "0"), ("rūpa", "form", "0"),
    ("rasa", "essence", "p"), ("bala", "strength", "p"), ("vidyā", "knowledge", "p"),
    ("avidyā", "ignorance", "n"), ("śatru", "enemy", "n"), ("mitra", "friend", "p"), ("loka", "world", "0"),
    ("svarga", "heaven", "p"), ("naraka", "hell", "n"), ("pāpa", "sin", "n"), ("puṇya", "merit", "p"),
    ("dāna", "charity", "p"), ("himsā", "violence", "n"), ("ahimsā", "nonviolence", "p"),
    ("kṣamā", "forgiveness", "p"), ("māna", "pride", "n"), ("śakti", "power", "p"), ("vīra", "hero", "p"),
]

# (word, gloss, valence) — English, read by pronunciation (pron='g2p')
_EN = [
    ("time", "time", "0"), ("love", "love", "p"), ("war", "war", "n"), ("peace", "peace", "p"),
    ("hope", "hope", "p"), ("fear", "fear", "n"), ("fire", "fire", "0"), ("water", "water", "0"),
    ("earth", "earth", "0"), ("wind", "wind", "0"), ("light", "light", "p"), ("dark", "darkness", "n"),
    ("truth", "truth", "p"), ("dream", "dream", "0"), ("death", "death", "n"), ("life", "life", "p"),
    ("mind", "mind", "0"), ("soul", "soul", "p"), ("body", "body", "0"), ("anger", "anger", "n"),
    ("greed", "greed", "n"), ("joy", "joy", "p"), ("pain", "pain", "n"), ("friend", "friend", "p"),
    ("enemy", "enemy", "n"), ("king", "king", "0"), ("god", "god", "p"), ("money", "money", "0"),
    ("power", "power", "p"), ("food", "food", "p"), ("sleep", "sleep", "0"), ("heart", "heart", "p"),
    ("blood", "blood", "0"), ("hand", "hand", "0"), ("stone", "stone", "0"), ("tree", "tree", "0"),
]

# (word, gloss, valence, pron) — cross-lingual probe, pinned to native phonetics
_X = [
    ("ja", "kokoro", "heart", "p", "k,o,k,o,r,o"), ("ja", "ai", "love", "p", "ai"),
    ("ja", "yume", "dream", "0", "y,u,m,e"), ("ja", "yama", "mountain", "0", "y,a,m,a"),
    ("ja", "hana", "flower", "p", "h,a,n,a"), ("ja", "kami", "spirit", "p", "k,a,m,i"),
    ("zh", "dao", "way", "0", "d,au"), ("zh", "ren", "benevolence", "p", "r,e,n"),
    ("zh", "qi", "energy", "p", "ch,i"), ("zh", "shan", "mountain", "0", "sh,a,n"),
    ("zh", "min", "people", "0", "m,i,n"), ("zh", "tian", "heaven", "p", "t,i,a,n"),
    ("ur", "ishq", "love", "p", "i,s,k"), ("ur", "nur", "light", "p", "n,uu,r"),
    ("ur", "jaan", "soul", "p", "j,aa,n"), ("ur", "dil", "heart", "p", "d,i,l"),
    ("ur", "dost", "friend", "p", "d,o,s,t"), ("ur", "gham", "sorrow", "n", "gh,a,m"),
]


def load():
    """Return list of dicts: {lang, word, gloss, valence, pron}."""
    rows = []
    for w, g, v in _SA:
        rows.append({"lang": "sa", "word": w, "gloss": g, "valence": v, "pron": "roman"})
    for w, g, v in _EN:
        rows.append({"lang": "en", "word": w, "gloss": g, "valence": v, "pron": "g2p"})
    for lang, w, g, v, pron in _X:
        rows.append({"lang": lang, "word": w, "gloss": g, "valence": v, "pron": pron})
    return rows


if __name__ == "__main__":
    rows = load()
    from collections import Counter
    print(f"{len(rows)} words")
    print("by lang:", dict(Counter(r["lang"] for r in rows)))
    print("by valence:", dict(Counter(r["valence"] for r in rows)))
