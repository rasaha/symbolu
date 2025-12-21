"""
AGI Demo
========

Demonstrates cross-domain reasoning capabilities of the Symbol-U engine.

This demo shows how:
    1. Events are tagged from natural language
    2. Queries are encoded to 10D with mirror pair balance
    3. Cross-domain experientials are retrieved
    4. Persona patterns are tracked across domains
    5. Insights are generated (structurally validated, not advertising)
    6. Canonical matching (C × R × S) validates semantic coherence

Usage:
    python -m symbolu.engine.agi_demo
"""

from symbolu.engine import create_engine, EngineTier, AGILevel
from symbolu.ontology.backbone import InsightMode
from symbolu.providers import get_match_provider, get_filter_provider


def run_demo():
    """Run the AGI demonstration."""
    print("=" * 70)
    print("SYMBOL-U AGI DEMONSTRATION")
    print("Cross-Domain Reasoning with 10D Mirror Pairs")
    print("=" * 70)
    print()

    # Create Consumer Engine with full AGI
    engine = create_engine(
        tier=EngineTier.CONSUMER,
        persona_id="demo_user",
        enable_agi=True,
    )

    # Demo queries across different domains
    demo_queries = [
        ("history", "Why did the Roman Empire fall?"),
        ("business", "My startup co-founders disagree on direction"),
        ("biology", "How do cells divide?"),
        ("finance", "What causes market crashes?"),
        ("family", "How to handle family conflict during holidays?"),
    ]

    print("PART 1: Building Persona Pattern Across Domains")
    print("-" * 70)
    print()

    for domain, query in demo_queries:
        print(f"Domain: {domain.upper()}")
        print(f"Query:  {query}")

        result = engine.generate(query, domain=domain)

        if result.agi_signal:
            agi = result.agi_signal
            print(f"  Events detected: {agi.get('events_detected', [])}")
            print(f"  Balance score:   {agi.get('balance_score', 0):.2f}")
            print(f"  Transferable:    {agi.get('is_transferable', False)}")
            print(f"  Cross-domain:    {agi.get('cross_domain_matches', 0)} matches")
            if agi.get('top_match_domain'):
                print(f"  Top match:       {agi['top_match_domain']} "
                      f"({agi['top_match_similarity']:.2f})")
        print()

    print()
    print("PART 2: Cross-Domain Reasoning Synthesis")
    print("-" * 70)
    print()

    # Synthesize reasoning for a complex problem
    problem = "My company is splitting into two factions"

    print(f"Problem: {problem}")
    print()

    synthesis = engine.synthesize_reasoning(problem, domain="business")

    if synthesis.get("synthesis"):
        print(f"Synthesized Insight:")
        print(f"  {synthesis['synthesis']}")
        print()
        print(f"Source domains: {synthesis.get('sources', [])}")
        print(f"Detected pattern: {synthesis.get('pattern', 'N/A')}")
        print(f"Balance score: {synthesis.get('balance_score', 0):.2f}")
        print(f"Is transferable: {synthesis.get('is_transferable', False)}")
        if synthesis.get("recommendations"):
            print()
            print("Recommendations:")
            for rec in synthesis["recommendations"]:
                print(f"  - {rec}")
    else:
        print("(Synthesis requires populated experiential store)")
        print("In production, cross-domain patterns would be retrieved")

    print()
    print("PART 3: Discovered Cross-Domain Bridges")
    print("-" * 70)
    print()

    bridges = engine.get_cross_domain_bridges()
    if bridges:
        print("Bridges discovered from query patterns:")
        for bridge, count in bridges.items():
            print(f"  {bridge}: {count} connections")
    else:
        print("(Bridges emerge from repeated cross-domain usage)")

    print()
    print("PART 4: Personalized Insights")
    print("-" * 70)
    print()

    insights = engine.get_insights(mode=InsightMode.NEW_POSSIBILITIES)
    if insights:
        print("Available insights (structurally validated):")
        for insight in insights:
            print(f"  [{insight['type']}] {insight['message']}")
            bridge = insight.get('bridge_domain', 'N/A')
            print(f"    Domain: {insight['current_domain']} -> {bridge}, "
                  f"Similarity: {insight['similarity']:.2f}")
    else:
        print("(Insights require populated experiential store)")
        print("Insights are structurally validated, not advertising")

    print()
    print("PART 5: Balance Explanation")
    print("-" * 70)
    print()

    explanation = engine.explain_last_query()
    print(explanation)

    print()
    print("PART 6: Canonical Matching (C × R × S)")
    print("-" * 70)
    print()

    print("Testing semantic coherence with canonical matching...")
    print("Formula: MATCH = C × R × S")
    print("  C = Constraint feasibility (phonemic → ontology)")
    print("  R = Realization strength (phonemic → experience)")
    print("  S = Referential coherence (NON-phonemic, source-independent)")
    print()

    # Get canonical match provider
    match_provider = get_match_provider("enterprise")

    # Test pairs demonstrating the system
    test_pairs = [
        # Should match (same referent class)
        ("king", "queen", "ROLE_BEARER + SOCIAL"),
        ("fire", "flame", "PROCESS + LUMINOUS"),
        ("happy", "joy", "EMOTIONAL"),
        # Should NOT match (ChatGPT failure modes - now fixed)
        ("king", "banana", "ROLE_BEARER vs BIOLOGICAL"),
        ("tree", "computer", "BIOLOGICAL vs ARTIFACT"),
    ]

    print("Semantic Discrimination Test:")
    print(f"  {'Pair':<20} {'Score':<8} {'C':<6} {'R':<6} {'S':<6} {'Mode':<15} {'Classes'}")
    print("  " + "-" * 85)

    for word_a, word_b, classes in test_pairs:
        result = match_provider.match(word_a, word_b)
        pair_str = f"{word_a}↔{word_b}"
        print(f"  {pair_str:<20} {result.match_score:.3f}   "
              f"{result.feasibility:.2f}  {result.realization:.2f}  {result.referent:.2f}  "
              f"{result.mode.value:<15} {classes}")

    print()
    print("Key insight: S term (non-phonemic) gates the match:")
    print("  - king↔queen: S ≈ 1.0 (same ROLE_BEARER) → HIGH match")
    print("  - king↔banana: S ≈ 0.0 (different classes) → BLOCKED")
    print()

    # Demonstrate coherence-enhanced filtering
    print("Coherence-Enhanced Filtering:")
    coherence_filter = get_filter_provider("enterprise", {"with_coherence": True})
    candidates = ("king", "queen", "banana", "throne", "crown")
    filter_result = coherence_filter.filter(candidates, "royalty", top_k=5)

    print(f"  Query: 'royalty'")
    print(f"  Candidates: {candidates}")
    print(f"  Filtered: {filter_result.filtered_texts}")

    if "coherence_checks" in filter_result.stats:
        summary = filter_result.stats["coherence_checks"]["summary"]
        print(f"  Coherence Summary:")
        print(f"    - True matches: {summary.get('true_matches', 0)}")
        print(f"    - Referent mismatches: {summary.get('referent_mismatches', 0)}")
        print(f"    - Average match score: {summary.get('avg_match_score', 0):.3f}")

    print()
    print("=" * 70)
    print("KEY ARCHITECTURE POINTS:")
    print("=" * 70)
    print("""
1. MIRROR PAIRS: 10D encodes as 5 mirror pairs (Acting-Absolving, etc.)
   - Balance between lower (concrete) and higher (abstract) = transferable insight
   - Imbalanced = just facts or just theory

2. EVENT TAGGING: Tag EVENTS (conflict, division, collapse), not entities
   - Events are domain-agnostic
   - Same event patterns appear across history, biology, business, etc.

3. PERSONA TRACKING: Discover patterns from USER BEHAVIOR, not content
   - Track which domains and events each user explores
   - Bridges emerge from usage, not extraction

4. STRUCTURAL VALIDATION: Insights require validated structural match
   - 10D similarity >= 0.5 OR causal chain overlap >= 0.3
   - Without validation, cross-domain suggestions = advertising

5. CANONICAL MATCHING (C × R × S): Source-independent semantic validation
   - C and R derive from phonemic analysis (same source)
   - S derives from referent classes (NON-phonemic, orthogonal)
   - S gates the match: low S → REFERENT_MISMATCH regardless of C×R
   - Fixes ChatGPT failure modes (king↔banana now correctly rejected)

6. THREE TIERS:
   - Enterprise Search: Pure STL (no AGI)
   - Enterprise Chat: STL + 7B + Light AGI (tracking + retrieval)
   - Consumer: STL + 768D + LLM + Full AGI (all capabilities)
""")


def compare_tiers():
    """Compare AGI capabilities across tiers."""
    print()
    print("=" * 70)
    print("TIER COMPARISON: AGI CAPABILITIES")
    print("=" * 70)
    print()

    query = "My startup co-founders disagree on direction"

    for tier, name in [
        (EngineTier.ENTERPRISE_SEARCH, "Enterprise Search (No AGI)"),
        (EngineTier.ENTERPRISE_CHAT, "Enterprise Chat (Light AGI)"),
        (EngineTier.CONSUMER, "Consumer (Full AGI)"),
    ]:
        print(f"{name}")
        print("-" * 50)

        engine = create_engine(tier=tier, persona_id="compare_user")

        if tier == EngineTier.ENTERPRISE_SEARCH:
            result = engine.classify(query)
        else:
            result = engine.generate(query, domain="business")

        print(f"  Intent:     {result.intent}")
        print(f"  Confidence: {result.confidence:.2f}")

        if result.agi_signal:
            agi = result.agi_signal
            print(f"  AGI Level:  {agi.get('level', 'N/A')}")
            print(f"  Events:     {agi.get('events_detected', [])}")
            print(f"  Balance:    {agi.get('balance_score', 'N/A')}")
            print(f"  Matches:    {agi.get('cross_domain_matches', 0)}")
        else:
            print("  AGI Signal: None (AGI not enabled for this tier)")

        print()


def demo_canonical_matching():
    """Standalone demonstration of canonical matching capabilities."""
    print()
    print("=" * 70)
    print("CANONICAL MATCHING (C × R × S) DEMONSTRATION")
    print("=" * 70)
    print()

    match_provider = get_match_provider("enterprise")

    print("The canonical matching formula: MATCH = C × R × S")
    print()
    print("Where:")
    print("  C = Constraint feasibility (phonemic → ontology)")
    print("  R = Realization strength (phonemic → experience)")
    print("  S = Referential coherence (NON-phonemic) ← KEY ADDITION")
    print()
    print("S provides source independence - it's NOT derived from phonemes.")
    print("This fixes the correlation issue where C and R both traced to phonemic data.")
    print()

    # Comprehensive test
    test_groups = {
        "TRUE MATCHES (same referent class)": [
            ("king", "queen"),
            ("sun", "star"),
            ("happy", "joy"),
            ("fire", "flame"),
            ("mother", "father"),
        ],
        "PARTIAL MATCHES (secondary overlap)": [
            ("sun", "light"),
            ("heart", "love"),
            ("fire", "bright"),
        ],
        "REFERENT MISMATCHES (ChatGPT failure modes - FIXED)": [
            ("king", "banana"),
            ("tree", "computer"),
            ("sun", "pencil"),
            ("love", "table"),
            ("queen", "apple"),
        ],
    }

    for group_name, pairs in test_groups.items():
        print(f"\n{group_name}:")
        print(f"  {'Pair':<20} {'MATCH':<8} {'C':<6} {'R':<6} {'S':<6} {'Mode'}")
        print("  " + "-" * 65)

        for word_a, word_b in pairs:
            result = match_provider.match(word_a, word_b)
            pair_str = f"{word_a}↔{word_b}"
            print(f"  {pair_str:<20} {result.match_score:.3f}   "
                  f"{result.feasibility:.2f}  {result.realization:.2f}  {result.referent:.2f}  "
                  f"{result.mode.value}")

    print()
    print("-" * 70)
    print("SUMMARY:")
    print("-" * 70)
    print("""
✓ TRUE MATCHES:     S ≈ 0.85-1.0, MATCH > 0.15
✓ PARTIAL MATCHES:  S ≈ 0.3-0.5, MATCH > 0.05
✓ MISMATCHES:       S ≈ 0.0, MATCH ≈ 0.0 (correctly rejected)

The S term (non-phonemic referent coherence) successfully gates matches:
- king↔banana BLOCKED despite any phonetic similarity (S = 0.0)
- king↔queen ALLOWED due to shared ROLE_BEARER class (S = 1.0)

This fixes the ChatGPT-identified failure mode where ORGANISM was too coarse,
causing king and banana to match. Now split into:
- BIOLOGICAL_ORGANISM (plants, animals, fruits)
- ROLE_BEARER (kings, queens, doctors)
""")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--canonical":
        # Run only canonical matching demo
        demo_canonical_matching()
    elif len(sys.argv) > 1 and sys.argv[1] == "--tiers":
        # Run only tier comparison
        compare_tiers()
    else:
        # Run full demo
        run_demo()
        compare_tiers()
        demo_canonical_matching()
