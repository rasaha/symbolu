"""
Engine Tier Demo
================

Demonstrates all three engine tiers:
1. Enterprise Search (Pure STL)
2. Enterprise Chat (STL + 7B)
3. Consumer (STL + 768D + LLM)

Run:
    python -m symbolu.engine.demo
"""

from symbolu.engine import (
    create_engine,
    EngineTier,
    EnterpriseSearchEngine,
    EnterpriseChatEngine,
    ConsumerEngine,
)


def demo_enterprise_search():
    """Demo Enterprise Tier 1: Pure STL."""
    print("=" * 70)
    print("ENTERPRISE TIER 1: Pure STL (Search/Classification)")
    print("=" * 70)
    print()

    engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)

    # Classification
    print("1. Intent Classification")
    print("-" * 40)

    queries = [
        "Deploy the K8s cluster now",
        "Explain quantum entanglement",
        "Write a poem about nature",
        "I'm feeling anxious today",
    ]

    for query in queries:
        result = engine.classify(query)
        print(f"  Query: \"{query}\"")
        print(f"    Intent: {result.intent}")
        print(f"    Confidence: {result.confidence:.0%}")
        print(f"    Latency: {result.latency_ms:.2f}ms")
        print()

    # Search/ranking
    print("2. Search/Ranking")
    print("-" * 40)

    candidates = [
        "Introduction to Machine Learning",
        "Quantum Computing Fundamentals",
        "Cooking Italian Pasta",
        "Advanced Physics Concepts",
    ]

    result = engine.search("quantum physics theory", candidates)
    print(f"  Query: \"quantum physics theory\"")
    print(f"  Ranked results:")
    for i, doc in enumerate(result.metadata["ranked"]):
        score = result.metadata["scores"][doc]
        print(f"    {i+1}. {doc} (score: {score:.3f})")
    print(f"  Latency: {result.latency_ms:.2f}ms")
    print()


def demo_enterprise_chat():
    """Demo Enterprise Tier 2: STL + 7B."""
    print("=" * 70)
    print("ENTERPRISE TIER 2: STL + 7B (Specialized Chat)")
    print("=" * 70)
    print()

    engine = create_engine(tier=EngineTier.ENTERPRISE_CHAT)

    print("1. Routed Generation")
    print("-" * 40)

    queries = [
        "Explain the theory of relativity",
        "Write a haiku about the moon",
        "Deploy the application to production",
        "I need someone to talk to",
    ]

    for query in queries:
        result = engine.generate(query)
        print(f"  Query: \"{query}\"")
        print(f"    Routed to: {result.model_used}")
        print(f"    Intent: {result.intent}")
        print(f"    Confidence: {result.confidence:.0%}")
        print(f"    Response: {result.response[:60]}...")
        print(f"    Latency: {result.latency_ms:.2f}ms")
        print()

    # Routing statistics
    print("2. Routing Statistics")
    print("-" * 40)

    test_queries = [
        "How does photosynthesis work?",
        "Calculate the derivative",
        "Write a story about dragons",
        "Create a logo design",
        "Run the test suite",
        "Schedule a meeting",
        "I feel lonely",
        "Help me understand my emotions",
        "What is the meaning of life?",
        "Why do we exist?",
    ]

    stats = engine.get_routing_stats(test_queries)
    print(f"  Total queries: {stats['total_queries']}")
    print(f"  Distribution:")
    for intent, count in stats['distribution'].items():
        pct = stats['percentages'][intent]
        print(f"    {intent}: {count} ({pct:.0f}%)")
    print()


def demo_consumer():
    """Demo Consumer: STL + 768D + LLM."""
    print("=" * 70)
    print("CONSUMER: STL + 768D + Cascading LLM")
    print("=" * 70)
    print()

    engine = create_engine(tier=EngineTier.CONSUMER)

    print("1. Cascading Generation")
    print("-" * 40)

    queries = [
        # High confidence - should skip 768D, use 7B
        ("Write a poem about love", "Should skip 768D"),
        # Lower confidence - may use 768D, then decide
        ("Analyze the implications", "May use 768D"),
        # Complex - likely uses 768D and possibly 175B
        ("Discuss the epistemological ramifications of quantum mechanics", "Complex query"),
    ]

    for query, note in queries:
        result = engine.generate(query)
        print(f"  Query: \"{query}\"")
        print(f"    Note: {note}")
        print(f"    Model used: {result.model_used}")
        print(f"    Used 768D: {result.metadata.get('used_768d', False)}")
        print(f"    Final confidence: {result.confidence:.0%}")
        print(f"    STL confidence: {result.stl_signal['confidence']:.0%}")
        if result.semantic_signal and result.semantic_signal.get('used'):
            print(f"    768D boost: {result.semantic_signal.get('boost', 0):.0%}")
        print(f"    Response: {result.response[:50]}...")
        print(f"    Latency: {result.latency_ms:.2f}ms")
        print()

    # Cascade statistics
    print("2. Cascade Statistics")
    print("-" * 40)

    test_queries = [
        "Write a poem",
        "Explain physics",
        "Deploy the app",
        "How do I feel better?",
        "What is consciousness?",
        "Create a logo",
        "Run tests",
        "Calculate the integral of x squared",
        "The socioeconomic implications of AI",
        "Analyze quantum decoherence effects",
    ]

    stats = engine.get_cascade_stats(test_queries)
    print(f"  Total queries: {stats['total']}")
    print(f"  Skipped 768D: {stats['skipped_768d']} ({stats['768d_skip_rate']:.0f}%)")
    print(f"  Used 768D: {stats['used_768d']}")
    print(f"  Used 7B: {stats['used_7b']} ({stats['7b_usage_rate']:.0f}%)")
    print(f"  Used 175B: {stats['used_175b']} ({stats['175b_usage_rate']:.0f}%)")
    print()


def demo_comparison():
    """Compare all three tiers."""
    print("=" * 70)
    print("TIER COMPARISON")
    print("=" * 70)
    print()

    query = "Explain how neural networks learn"

    # Enterprise Search
    search_engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)
    search_result = search_engine.classify(query)

    # Enterprise Chat
    chat_engine = create_engine(tier=EngineTier.ENTERPRISE_CHAT)
    chat_result = chat_engine.generate(query)

    # Consumer
    consumer_engine = create_engine(tier=EngineTier.CONSUMER)
    consumer_result = consumer_engine.generate(query)

    print(f"Query: \"{query}\"")
    print()

    print("┌─────────────────────┬────────────────────┬────────────────────┬────────────────────┐")
    print("│                     │ Enterprise Search  │ Enterprise Chat    │ Consumer           │")
    print("├─────────────────────┼────────────────────┼────────────────────┼────────────────────┤")
    print(f"│ Intent              │ {search_result.intent:<18} │ {chat_result.intent:<18} │ {consumer_result.intent:<18} │")
    print(f"│ Confidence          │ {search_result.confidence:<18.0%} │ {chat_result.confidence:<18.0%} │ {consumer_result.confidence:<18.0%} │")
    print(f"│ Model Used          │ {'N/A':<18} │ {chat_result.model_used:<18} │ {consumer_result.model_used:<18} │")
    print(f"│ Used 768D           │ {'No':<18} │ {'No':<18} │ {str(consumer_result.metadata.get('used_768d', False)):<18} │")
    print(f"│ Latency (ms)        │ {search_result.latency_ms:<18.2f} │ {chat_result.latency_ms:<18.2f} │ {consumer_result.latency_ms:<18.2f} │")
    print(f"│ Has Response        │ {'No':<18} │ {'Yes':<18} │ {'Yes':<18} │")
    print("└─────────────────────┴────────────────────┴────────────────────┴────────────────────┘")
    print()


def main():
    """Run all demos."""
    demo_enterprise_search()
    demo_enterprise_chat()
    demo_consumer()
    demo_comparison()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
    ┌────────────────────┬─────────────────────────────────────────────┐
    │ Tier               │ Best For                                    │
    ├────────────────────┼─────────────────────────────────────────────┤
    │ Enterprise Search  │ Classification, filtering, retrieval        │
    │                    │ No LLM needed, fastest, cheapest            │
    ├────────────────────┼─────────────────────────────────────────────┤
    │ Enterprise Chat    │ Specialized chat with domain expertise      │
    │                    │ 25x cost savings with 7B models             │
    ├────────────────────┼─────────────────────────────────────────────┤
    │ Consumer           │ Full capability with smart cascading        │
    │                    │ 85% skip 768D, most use 7B, edge→175B       │
    └────────────────────┴─────────────────────────────────────────────┘
    """)


if __name__ == "__main__":
    main()
