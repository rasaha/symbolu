"""Fixed role/function word set for the ARCHETYPE test (PREREG_ARCHETYPE_SIGNAL.md).

Each entry: {word, pron, domain, from_state, to_state}
  - The archetype is the role's TRANSFORMATION (from_state -> to_state), authored from the role's
    function ALONE, BEFORE any varṇa chain was computed. No archetype was fitted to a chain.
  - pron : 'g2p' (English pronunciation via cmudict) for all role words here.
  - domain : a coarse grouping for per-domain breakdown (non-gating).

This is NOT meaning-recovery: there is no dictionary gloss to identify. The target is the
transformation a word's role enacts (doctor: suffering -> healing).
"""

# (word, domain, from_state, to_state)  — all read by English pronunciation (g2p)
_WORDS = [
    # care
    ("doctor",      "care",       "suffering",      "healing"),
    ("nurse",       "care",       "pain",           "comfort"),
    ("mother",      "care",       "vulnerability",  "nourishment"),
    ("healer",      "care",       "wound",          "wholeness"),
    ("midwife",     "care",       "labor",          "birth"),
    # order / authority
    ("judge",       "order",      "dispute",        "resolution"),
    ("king",        "order",      "disorder",       "order"),
    ("leader",      "order",      "division",       "unity"),
    ("guardian",    "order",      "danger",         "safety"),
    ("counselor",   "order",      "confusion",      "clarity"),
    # protection / provision
    ("warrior",     "protection", "threat",         "protection"),
    ("hunter",      "protection", "scarcity",       "provision"),
    ("shepherd",    "protection", "scattered",      "gathered"),
    ("guide",       "protection", "lost",           "direction"),
    # spirit
    ("monk",        "spirit",     "attachment",     "detachment"),
    ("priest",      "spirit",     "ordinary",       "sacred"),
    ("prophet",     "spirit",     "blindness",      "vision"),
    # knowledge
    ("teacher",     "knowledge",  "ignorance",      "understanding"),
    ("scientist",   "knowledge",  "mystery",        "knowledge"),
    ("philosopher", "knowledge",  "question",       "wisdom"),
    # craft / making
    ("farmer",      "craft",      "seed",           "harvest"),
    ("builder",     "craft",      "raw material",   "structure"),
    ("smith",       "craft",      "ore",            "tool"),
    ("engineer",    "craft",      "problem",        "solution"),
    ("merchant",    "craft",      "need",           "exchange"),
    # expression
    ("artist",      "expression", "inner image",    "outer form"),
    ("musician",    "expression", "silence",        "harmony"),
    ("dancer",      "expression", "stillness",      "motion"),
    ("poet",        "expression", "feeling",        "word"),
    # discovery
    ("explorer",    "discovery",  "unknown",        "discovery"),
]


def load():
    return [{"word": w, "pron": "g2p", "domain": dom, "from_state": fr, "to_state": to}
            for (w, dom, fr, to) in _WORDS]


if __name__ == "__main__":
    from collections import Counter
    rows = load()
    print(f"{len(rows)} role words")
    print("by domain:", dict(Counter(r["domain"] for r in rows)))
    for r in rows:
        print(f"  {r['word']:12} {r['from_state']} -> {r['to_state']}")
