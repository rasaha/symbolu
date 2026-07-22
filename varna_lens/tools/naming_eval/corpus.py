#!/usr/bin/env python3
"""Frozen naming-evaluation corpus. Deterministic; no model. Each item carries a naming brief +
constraints and a `seed_concept` (the concept a Symbolic Profile is built from for Arms B/C/D).

Seeds span English and Sanskrit (incl. ś / ṣ / conjunct-kṣ) so the profile exercises the frozen
parser + B1.12 mapping across the difficult cases the task requires.
"""
from __future__ import annotations

# category, id, brief, constraints{}, seed_concept, note
CORPUS = [
    # ---- Brand names — 10 industries -----------------------------------------------------------
    {"id": "brand_ai", "category": "brand", "industry": "AI startup",
     "brief": "Name an AI startup building autonomous research agents.",
     "constraints": {"language": "English", "market": "US/EU", "length": "<=10", "pronounceable": True},
     "seed_concept": "insight"},
    {"id": "brand_pharma", "category": "brand", "industry": "pharmaceutical",
     "brief": "Name a pharmaceutical company focused on regenerative medicine.",
     "constraints": {"language": "English", "market": "global", "length": "<=12", "multilingual_safe": True},
     "seed_concept": "renewal"},
    {"id": "brand_fintech", "category": "brand", "industry": "fintech",
     "brief": "Name a fintech offering trustworthy cross-border payments.",
     "constraints": {"language": "English", "market": "global", "premium": True},
     "seed_concept": "trust"},
    {"id": "brand_electronics", "category": "brand", "industry": "consumer electronics",
     "brief": "Name a premium consumer-electronics brand for audio devices.",
     "constraints": {"language": "English", "market": "global", "premium": True, "length": "<=9"},
     "seed_concept": "clarity"},
    {"id": "brand_edu", "category": "brand", "industry": "education",
     "brief": "Name an online education platform for lifelong learners.",
     "constraints": {"language": "English", "market": "global", "pronounceable": True},
     "seed_concept": "curiosity"},
    {"id": "brand_enterprise", "category": "brand", "industry": "enterprise software",
     "brief": "Name enterprise workflow-orchestration software.",
     "constraints": {"language": "English", "market": "US/EU", "professional": True},
     "seed_concept": "order"},
    {"id": "brand_health", "category": "brand", "industry": "healthcare",
     "brief": "Name a healthcare company for compassionate remote care.",
     "constraints": {"language": "English", "market": "global", "multilingual_safe": True},
     "seed_concept": "compassion"},
    {"id": "brand_auto", "category": "brand", "industry": "automotive",
     "brief": "Name an electric-vehicle marque conveying speed and calm control.",
     "constraints": {"language": "English", "market": "global", "premium": True},
     "seed_concept": "swift"},
    {"id": "brand_gaming", "category": "brand", "industry": "gaming",
     "brief": "Name a gaming studio known for bold, imaginative worlds.",
     "constraints": {"language": "English", "market": "global", "distinctive": True},
     "seed_concept": "courage"},
    {"id": "brand_industrial", "category": "brand", "industry": "industrial",
     "brief": "Name an industrial-robotics firm emphasizing reliability.",
     "constraints": {"language": "English", "market": "global", "professional": True},
     "seed_concept": "stability"},

    # ---- Product names — multiple constraints ---------------------------------------------------
    {"id": "prod_premium_short", "category": "product", "industry": "consumer electronics",
     "brief": "Name a flagship noise-cancelling headphone.",
     "constraints": {"language": "English", "market": "global", "premium": True, "short": True,
                     "length": "<=6", "pronounceable": True, "multilingual_safe": True},
     "seed_concept": "silence"},
    {"id": "prod_multilingual", "category": "product", "industry": "fintech",
     "brief": "Name a global savings product usable in 20 languages.",
     "constraints": {"language": "neutral", "market": "global", "multilingual_safe": True,
                     "pronounceable": True, "length": "<=8"},
     "seed_concept": "growth"},
    {"id": "prod_suffix", "category": "product", "industry": "enterprise software",
     "brief": "Name an analytics module; must end with the suffix '-iq'.",
     "constraints": {"language": "English", "market": "US/EU", "required_suffix": "iq", "length": "<=10"},
     "seed_concept": "knowledge"},

    # ---- Agent names ----------------------------------------------------------------------------
    {"id": "agent_support", "category": "agent", "industry": "AI",
     "brief": "Name a customer-support AI agent that is patient and clear.",
     "constraints": {"language": "English", "market": "global", "pronounceable": True},
     "seed_concept": "patience"},
    {"id": "agent_finance", "category": "agent", "industry": "AI",
     "brief": "Name a finance copilot conveying prudence and precision.",
     "constraints": {"language": "English", "market": "global", "professional": True},
     "seed_concept": "prudence"},
    {"id": "agent_medical", "category": "agent", "industry": "AI",
     "brief": "Name a medical assistant agent conveying care and rigor.",
     "constraints": {"language": "English", "market": "global", "multilingual_safe": True},
     "seed_concept": "care"},
    {"id": "agent_coding", "category": "agent", "industry": "AI",
     "brief": "Name a coding assistant conveying focus and craft.",
     "constraints": {"language": "English", "market": "global", "pronounceable": True},
     "seed_concept": "focus"},

    # ---- Portfolio tasks ------------------------------------------------------------------------
    {"id": "portfolio_rename", "category": "portfolio", "industry": "enterprise software",
     "brief": "Rename three sibling products (data, workflow, insight) into one consistent family.",
     "constraints": {"language": "English", "market": "US/EU", "family_consistency": True,
                     "avoid_collision": True, "differentiate_siblings": True},
     "seed_concept": "order"},
    {"id": "portfolio_family", "category": "portfolio", "industry": "AI",
     "brief": "Name a family of four agents (support, finance, medical, coding) with shared identity.",
     "constraints": {"language": "English", "market": "global", "family_consistency": True,
                     "differentiate_siblings": True},
     "seed_concept": "assistance"},

    # ---- Difficult cases ------------------------------------------------------------------------
    {"id": "hard_similar", "category": "difficult", "industry": "AI",
     "brief": "Differentiate from a competitor named 'Aara'; propose distinct-sounding names.",
     "constraints": {"language": "English", "market": "global", "avoid_similarity_to": "Aara"},
     "seed_concept": "clarity"},
    {"id": "hard_multiling_ambig", "category": "difficult", "industry": "consumer",
     "brief": "Name a snack brand; avoid negative meanings across major languages.",
     "constraints": {"language": "neutral", "market": "global", "multilingual_safe": True},
     "seed_concept": "delight"},
    {"id": "hard_sanskrit", "category": "difficult", "industry": "wellness",
     "brief": "Name a meditation app from a Sanskrit-origin concept of inner stillness.",
     "constraints": {"language": "Sanskrit-origin", "market": "global", "pronounceable": True},
     "seed_concept": "śānti"},
    {"id": "hard_sanskrit2", "category": "difficult", "industry": "wellness",
     "brief": "Name a forgiveness-themed journaling product from a Sanskrit concept.",
     "constraints": {"language": "Sanskrit-origin", "market": "global", "pronounceable": True},
     "seed_concept": "kṣamā"},
    {"id": "hard_conjunct", "category": "difficult", "industry": "AI",
     "brief": "Name a security product from a conjunct-heavy Sanskrit seed (protection).",
     "constraints": {"language": "Sanskrit-origin", "market": "global"},
     "seed_concept": "rakṣā"},
    {"id": "hard_invented", "category": "difficult", "industry": "AI",
     "brief": "Propose invented (non-dictionary) names for a data-privacy startup.",
     "constraints": {"language": "invented", "market": "global", "pronounceable": True, "length": "<=8"},
     "seed_concept": "shield"},
    {"id": "hard_competing", "category": "difficult", "industry": "AI",
     "brief": "Two co-founders favor 'calm' vs 'drive' as the brand feeling; propose names for each.",
     "constraints": {"language": "English", "market": "global"},
     "seed_concept": "balance"},
]


def by_category():
    out = {}
    for it in CORPUS:
        out.setdefault(it["category"], []).append(it)
    return out


if __name__ == "__main__":
    from collections import Counter
    print(f"corpus items: {len(CORPUS)}")
    for c, n in sorted(Counter(i["category"] for i in CORPUS).items()):
        print(f"  {c}: {n}")
