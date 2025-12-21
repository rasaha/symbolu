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

Usage:
    python -m symbolu.engine.agi_demo
"""

from symbolu.engine import create_engine, EngineTier, AGILevel
from symbolu.ontology.backbone import InsightMode


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

5. THREE TIERS:
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


if __name__ == "__main__":
    run_demo()
    compare_tiers()
