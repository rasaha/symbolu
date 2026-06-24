"""Fixed word/name set for the NON-LEXICAL utility test (PREREG_UTILITY_SIGNAL.md).

Each entry: {word, language, category, pronunciation, use_case}
  category : sanskrit_spiritual | english_everyday | brand_name | emotionally_loaded | neutral_control
  pronunciation : 'roman' (literal IAST/letters) | 'g2p' (English pronunciation) | explicit varṇas
  use_case : journaling | naming | creative | affective
NO target meaning is stored — this is a utility test, not meaning recovery.
"""

# (word, pronunciation)  — category + use_case applied per block below
_SANSKRIT = [  # use_case: journaling
    ("dharma", "roman"), ("karma", "roman"), ("mokṣa", "roman"), ("ānanda", "roman"), ("śānti", "roman"),
    ("bhakti", "roman"), ("vairāgya", "roman"), ("tapas", "roman"), ("dhyāna", "roman"), ("satya", "roman"),
    ("ahimsā", "roman"), ("sevā", "roman"), ("kṣamā", "roman"), ("viveka", "roman"), ("samādhi", "roman"),
    ("prema", "roman"), ("śraddhā", "roman"), ("titikṣā", "roman"), ("santoṣa", "roman"), ("maitrī", "roman"),
    ("karuṇā", "roman"), ("dāna", "roman"), ("yoga", "roman"), ("guru", "roman"), ("sādhanā", "roman"),
]
_ENGLISH = [  # use_case: creative
    ("river", "g2p"), ("mountain", "g2p"), ("morning", "g2p"), ("window", "g2p"), ("harbor", "g2p"),
    ("lantern", "g2p"), ("thunder", "g2p"), ("garden", "g2p"), ("mirror", "g2p"), ("ember", "g2p"),
    ("anchor", "g2p"), ("meadow", "g2p"), ("compass", "g2p"), ("orchard", "g2p"), ("willow", "g2p"),
    ("bridge", "g2p"), ("harvest", "g2p"), ("shadow", "g2p"), ("current", "g2p"), ("hollow", "g2p"),
    ("threshold", "g2p"), ("beacon", "g2p"), ("furnace", "g2p"), ("marrow", "g2p"), ("tidal", "g2p"),
]
_BRANDS = [  # use_case: naming  (mix of real + plausible invented names; read literally)
    ("Nike", "roman"), ("Tesla", "roman"), ("Kodak", "roman"), ("Lyra", "roman"), ("Verda", "roman"),
    ("Soma", "roman"), ("Nimbus", "roman"), ("Aria", "roman"), ("Kintsu", "roman"), ("Vela", "roman"),
    ("Orin", "roman"), ("Cael", "roman"), ("Mira", "roman"), ("Tovo", "roman"), ("Lumen", "roman"),
    ("Saga", "roman"), ("Halo", "roman"), ("Onda", "roman"), ("Faye", "roman"), ("Rune", "roman"),
    ("Zephyr", "roman"), ("Cobalt", "roman"), ("Indra", "roman"), ("Nova", "roman"), ("Brio", "roman"),
]
_EMOTIONAL = [  # use_case: affective
    ("grief", "g2p"), ("longing", "g2p"), ("rage", "g2p"), ("tenderness", "g2p"), ("dread", "g2p"),
    ("awe", "g2p"), ("shame", "g2p"), ("hope", "g2p"), ("envy", "g2p"), ("relief", "g2p"),
    ("yearning", "g2p"), ("courage", "g2p"), ("sorrow", "g2p"), ("delight", "g2p"), ("loneliness", "g2p"),
    ("gratitude", "g2p"), ("anguish", "g2p"), ("serenity", "g2p"), ("panic", "g2p"), ("wonder", "g2p"),
    ("contempt", "g2p"), ("compassion", "g2p"), ("despair", "g2p"), ("joy", "g2p"),
]
_NEUTRAL = [  # use_case: journaling (control: words with little inherent affect)
    ("table", "g2p"), ("gravel", "g2p"), ("plastic", "g2p"), ("ledger", "g2p"), ("socket", "g2p"),
    ("pavement", "g2p"), ("stapler", "g2p"), ("cardboard", "g2p"), ("nozzle", "g2p"), ("bracket", "g2p"),
    ("canister", "g2p"), ("gasket", "g2p"), ("pixel", "g2p"), ("invoice", "g2p"), ("turbine", "g2p"),
    ("folder", "g2p"), ("magnet", "g2p"), ("rubber", "g2p"), ("concrete", "g2p"), ("spindle", "g2p"),
    ("conduit", "g2p"), ("granite", "g2p"), ("velcro", "roman"), ("lattice", "g2p"), ("monitor", "g2p"),
]


def load():
    rows = []
    for w, p in _SANSKRIT:
        rows.append({"word": w, "language": "sa", "category": "sanskrit_spiritual", "pronunciation": p,
                     "use_case": "journaling"})
    for w, p in _ENGLISH:
        rows.append({"word": w, "language": "en", "category": "english_everyday", "pronunciation": p,
                     "use_case": "creative"})
    for w, p in _BRANDS:
        rows.append({"word": w, "language": "xx", "category": "brand_name", "pronunciation": p,
                     "use_case": "naming"})
    for w, p in _EMOTIONAL:
        rows.append({"word": w, "language": "en", "category": "emotionally_loaded", "pronunciation": p,
                     "use_case": "affective"})
    for w, p in _NEUTRAL:
        rows.append({"word": w, "language": "en", "category": "neutral_control", "pronunciation": p,
                     "use_case": "journaling"})
    return rows


if __name__ == "__main__":
    from collections import Counter
    rows = load()
    print(f"{len(rows)} words")
    print("by category:", dict(Counter(r["category"] for r in rows)))
    print("by use_case:", dict(Counter(r["use_case"] for r in rows)))
