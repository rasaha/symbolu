#!/usr/bin/env python3
"""
Synthetic Retrieval Data Test for Phase Attention Transformer.

Tests controlled retrieval patterns:
1. Key-Value Retrieval: Given facts, retrieve specific values
2. UUID Passkey: Random codes hidden in noise
3. Multi-Fact Retrieval: Multiple retrievals from same context
4. Ordered List: Remember sequence positions

These tests are more controlled than Needle-in-Haystack and help
diagnose specific retrieval capabilities.
"""

import argparse
import json
import random
import string
import time
from datetime import datetime
from pathlib import Path

import torch
import torch.nn.functional as F
from tqdm import tqdm

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import PhaseTransformer, HybridPhaseTransformer


# Model presets matching train.py
MODEL_PRESETS = {
    "tiny": {"embed_dim": 256, "num_heads": 4, "num_layers": 4, "ff_dim": 1024},
    "small": {"embed_dim": 512, "num_heads": 8, "num_layers": 8, "ff_dim": 2048},
    "medium": {"embed_dim": 768, "num_heads": 12, "num_layers": 12, "ff_dim": 3072},
    "large": {"embed_dim": 1024, "num_heads": 16, "num_layers": 16, "ff_dim": 4096},
}


class SimpleTokenizer:
    """Simple word-based tokenizer fallback."""

    def __init__(self, vocab_size: int = 50257):
        self.vocab_size = vocab_size
        self.word_to_id = {}
        self.id_to_word = {}
        self.next_id = 256  # Reserve 0-255 for bytes

    def encode(self, text: str) -> list:
        """Encode text to token ids."""
        words = text.split()
        ids = []
        for word in words:
            if word not in self.word_to_id:
                self.word_to_id[word] = self.next_id
                self.id_to_word[self.next_id] = word
                self.next_id = (self.next_id + 1) % self.vocab_size
            ids.append(self.word_to_id[word])
        return ids

    def decode(self, ids: list) -> str:
        """Decode token ids to text."""
        words = []
        for id in ids:
            if id in self.id_to_word:
                words.append(self.id_to_word[id])
            else:
                words.append(f"[{id}]")
        return " ".join(words)


def get_tokenizer():
    """Get tokenizer with fallback."""
    try:
        import tiktoken
        return tiktoken.get_encoding("gpt2")
    except ImportError:
        try:
            from transformers import GPT2Tokenizer
            return GPT2Tokenizer.from_pretrained("gpt2")
        except ImportError:
            print("Warning: Using simple tokenizer fallback")
            return SimpleTokenizer()


class SyntheticRetrievalTest:
    """Generate and test synthetic retrieval tasks."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

        # Fact templates for key-value retrieval
        self.fact_templates = [
            "The {category} of {entity} is {value}.",
            "{entity} has a {category} of {value}.",
            "For {entity}, the {category} is {value}.",
        ]

        self.categories = ["capital", "color", "number", "code", "key", "password"]
        self.entities = [
            "Alpha", "Beta", "Gamma", "Delta", "Epsilon",
            "Zeta", "Eta", "Theta", "Iota", "Kappa",
            "Lambda", "Mu", "Nu", "Xi", "Omicron",
            "France", "Germany", "Japan", "Brazil", "Canada"
        ]

        # Filler text for padding
        self.filler_sentences = [
            "The quick brown fox jumps over the lazy dog.",
            "A journey of a thousand miles begins with a single step.",
            "To be or not to be, that is the question.",
            "All that glitters is not gold.",
            "The early bird catches the worm.",
            "Actions speak louder than words.",
            "Knowledge is power in the modern world.",
            "Time flies when you are having fun.",
            "Every cloud has a silver lining.",
            "Practice makes perfect in all endeavors.",
        ]

    def generate_random_value(self, category: str) -> str:
        """Generate a random value for a category."""
        if category in ["capital", "color"]:
            return random.choice(["Red", "Blue", "Green", "Paris", "Tokyo", "Berlin", "Rome"])
        elif category == "number":
            return str(random.randint(100, 999))
        elif category in ["code", "key", "password"]:
            return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return "unknown"

    def generate_filler(self, target_tokens: int) -> str:
        """Generate filler text to reach target token count."""
        filler = []
        current_tokens = 0

        while current_tokens < target_tokens:
            sentence = random.choice(self.filler_sentences)
            filler.append(sentence)
            current_tokens += len(self.tokenizer.encode(sentence))

        return " ".join(filler)

    def create_key_value_test(self, context_length: int, num_facts: int = 5) -> dict:
        """Create a key-value retrieval test."""
        facts = []
        for _ in range(num_facts):
            entity = random.choice(self.entities)
            category = random.choice(self.categories)
            value = self.generate_random_value(category)
            template = random.choice(self.fact_templates)
            fact = template.format(entity=entity, category=category, value=value)
            facts.append({"entity": entity, "category": category, "value": value, "text": fact})

        # Target fact to query
        target = random.choice(facts)

        # Build context with facts distributed throughout
        tokens_per_section = context_length // (num_facts + 1)

        sections = []
        for i, fact in enumerate(facts):
            filler = self.generate_filler(tokens_per_section - 20)
            sections.append(filler + " " + fact["text"])

        # Add final filler
        sections.append(self.generate_filler(tokens_per_section))

        context = " ".join(sections)

        # Create question
        question = f" Question: What is the {target['category']} of {target['entity']}? Answer:"

        return {
            "context": context,
            "question": question,
            "answer": target["value"],
            "facts": facts,
            "target": target,
            "type": "key_value"
        }

    def create_uuid_passkey_test(self, context_length: int) -> dict:
        """Create a UUID passkey retrieval test (like needle but with random code)."""
        # Generate random passkey
        passkey = ''.join(random.choices(string.digits, k=8))

        # Create the passkey statement
        passkey_statement = f"The secret passkey is: {passkey}. Remember this code."

        # Generate filler
        filler_before = self.generate_filler(context_length // 2)
        filler_after = self.generate_filler(context_length // 2)

        context = filler_before + " " + passkey_statement + " " + filler_after
        question = " Question: What is the secret passkey? Answer: The passkey is"

        return {
            "context": context,
            "question": question,
            "answer": passkey,
            "type": "uuid_passkey"
        }

    def create_multi_fact_test(self, context_length: int, num_questions: int = 3) -> dict:
        """Create a test with multiple retrievals from the same context."""
        num_facts = num_questions + 2  # Extra facts as distractors

        facts = []
        used_pairs = set()

        while len(facts) < num_facts:
            entity = random.choice(self.entities)
            category = random.choice(self.categories)
            pair = (entity, category)

            if pair not in used_pairs:
                used_pairs.add(pair)
                value = self.generate_random_value(category)
                template = random.choice(self.fact_templates)
                fact = template.format(entity=entity, category=category, value=value)
                facts.append({"entity": entity, "category": category, "value": value, "text": fact})

        # Select facts to query
        query_facts = random.sample(facts, num_questions)

        # Build context
        tokens_per_section = context_length // (num_facts + 1)
        sections = []

        for fact in facts:
            filler = self.generate_filler(tokens_per_section - 20)
            sections.append(filler + " " + fact["text"])

        sections.append(self.generate_filler(tokens_per_section))
        random.shuffle(sections)  # Randomize order

        context = " ".join(sections)

        # Create multi-question
        questions = []
        answers = []
        for qf in query_facts:
            questions.append(f"What is the {qf['category']} of {qf['entity']}?")
            answers.append(qf["value"])

        question = " Questions: " + " ".join([f"{i+1}. {q}" for i, q in enumerate(questions)]) + " Answers:"

        return {
            "context": context,
            "question": question,
            "answers": answers,
            "query_facts": query_facts,
            "type": "multi_fact"
        }

    def create_ordered_list_test(self, context_length: int, list_length: int = 5) -> dict:
        """Create a test for remembering ordered sequences."""
        # Generate random items
        items = [''.join(random.choices(string.ascii_uppercase, k=4)) for _ in range(list_length)]

        # Create the list statement
        list_text = f"The ordered list is: {', '.join(items)}. This is the complete sequence."

        # Pick random position to query
        position = random.randint(1, list_length)

        # Generate context
        filler_before = self.generate_filler(context_length // 2)
        filler_after = self.generate_filler(context_length // 2)

        context = filler_before + " " + list_text + " " + filler_after
        question = f" Question: What is item number {position} in the ordered list? Answer: Item {position} is"

        return {
            "context": context,
            "question": question,
            "answer": items[position - 1],
            "items": items,
            "position": position,
            "type": "ordered_list"
        }


def load_model(checkpoint_path: str, model_size: str, max_context: int, device: str):
    """Load model from checkpoint."""
    preset = MODEL_PRESETS[model_size]

    # Try hybrid first, fall back to phase
    try:
        model = HybridPhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=max_context + 1024,
            dropout=0.0,
            local_layers=2,
            window_size=128,
            local_backend="unfold",
        )
    except Exception as e:
        print(f"HybridPhaseTransformer failed: {e}, trying PhaseTransformer")
        model = PhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=max_context + 1024,
            dropout=0.0,
        )

    # Load checkpoint
    checkpoint = torch.load(checkpoint_path, map_location=device)
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"], strict=False)
    elif "model" in checkpoint:
        model.load_state_dict(checkpoint["model"], strict=False)
    else:
        model.load_state_dict(checkpoint, strict=False)

    model.to(device)
    model.eval()

    return model


def check_answer(model, tokenizer, context: str, question: str, expected: str, device: str) -> dict:
    """Check if model retrieves the correct answer."""
    # Encode input
    full_input = context + question
    input_ids = tokenizer.encode(full_input)
    input_tensor = torch.tensor([input_ids], device=device)

    # Generate continuation
    with torch.no_grad():
        # Get logits for next token prediction
        outputs = model(input_tensor)

        # Generate a few tokens
        generated = []
        current_input = input_tensor

        for _ in range(len(expected) + 10):  # Generate slightly more than expected
            outputs = model(current_input)
            next_token_logits = outputs[:, -1, :]
            next_token = torch.argmax(next_token_logits, dim=-1)
            generated.append(next_token.item())
            current_input = torch.cat([current_input, next_token.unsqueeze(0)], dim=1)

            # Stop if we've generated enough
            if len(generated) > len(expected) + 5:
                break

    generated_text = tokenizer.decode(generated)

    # Check if expected answer appears in generated text
    is_correct = expected.lower() in generated_text.lower()

    # Also check first token match for simple answers
    expected_first_token = tokenizer.encode(" " + expected)[0] if expected else None
    first_token_match = generated[0] == expected_first_token if expected_first_token and generated else False

    return {
        "correct": is_correct or first_token_match,
        "generated": generated_text[:50],  # Truncate for display
        "expected": expected,
        "first_token_match": first_token_match
    }


def run_test(args):
    """Run synthetic retrieval tests."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load tokenizer
    tokenizer = get_tokenizer()

    # Load model
    print(f"Loading checkpoint from {args.checkpoint}")
    model = load_model(args.checkpoint, args.model_size, args.max_context, device)
    print(f"Model loaded: {sum(p.numel() for p in model.parameters())/1e6:.1f}M parameters")

    # Initialize test generator
    test_gen = SyntheticRetrievalTest(tokenizer)

    # Context lengths to test
    context_lengths = [1024, 2048, 4096, 8192]
    if args.max_context >= 16384:
        context_lengths.append(16384)
    if args.max_context >= 32768:
        context_lengths.append(32768)

    results = {
        "test_date": datetime.now().isoformat(),
        "checkpoint": args.checkpoint,
        "model_size": args.model_size,
        "tests": []
    }

    print("\n" + "=" * 70)
    print("  SYNTHETIC RETRIEVAL TESTS")
    print("=" * 70)

    total_correct = 0
    total_tests = 0

    for ctx_len in context_lengths:
        if ctx_len > args.max_context:
            continue

        print(f"\n--- Context Length: {ctx_len} tokens ---")

        test_results = {"context_length": ctx_len, "tests": {}}

        # Test 1: Key-Value Retrieval
        print("\n1. Key-Value Retrieval:")
        kv_correct = 0
        for i in range(args.num_samples):
            test_data = test_gen.create_key_value_test(ctx_len)
            result = check_answer(model, tokenizer, test_data["context"],
                                  test_data["question"], test_data["answer"], device)
            if result["correct"]:
                kv_correct += 1
            print(f"   Sample {i+1}: {'✓' if result['correct'] else '✗'} "
                  f"(expected: {test_data['answer']}, got: {result['generated'][:20]})")

        kv_accuracy = kv_correct / args.num_samples * 100
        test_results["tests"]["key_value"] = {"correct": kv_correct, "total": args.num_samples, "accuracy": kv_accuracy}
        total_correct += kv_correct
        total_tests += args.num_samples
        print(f"   Accuracy: {kv_accuracy:.1f}%")

        # Test 2: UUID Passkey
        print("\n2. UUID Passkey Retrieval:")
        uuid_correct = 0
        for i in range(args.num_samples):
            test_data = test_gen.create_uuid_passkey_test(ctx_len)
            result = check_answer(model, tokenizer, test_data["context"],
                                  test_data["question"], test_data["answer"], device)
            if result["correct"]:
                uuid_correct += 1
            print(f"   Sample {i+1}: {'✓' if result['correct'] else '✗'} "
                  f"(expected: {test_data['answer']}, got: {result['generated'][:20]})")

        uuid_accuracy = uuid_correct / args.num_samples * 100
        test_results["tests"]["uuid_passkey"] = {"correct": uuid_correct, "total": args.num_samples, "accuracy": uuid_accuracy}
        total_correct += uuid_correct
        total_tests += args.num_samples
        print(f"   Accuracy: {uuid_accuracy:.1f}%")

        # Test 3: Ordered List
        print("\n3. Ordered List Retrieval:")
        list_correct = 0
        for i in range(args.num_samples):
            test_data = test_gen.create_ordered_list_test(ctx_len)
            result = check_answer(model, tokenizer, test_data["context"],
                                  test_data["question"], test_data["answer"], device)
            if result["correct"]:
                list_correct += 1
            print(f"   Sample {i+1}: {'✓' if result['correct'] else '✗'} "
                  f"(expected: {test_data['answer']}, got: {result['generated'][:20]})")

        list_accuracy = list_correct / args.num_samples * 100
        test_results["tests"]["ordered_list"] = {"correct": list_correct, "total": args.num_samples, "accuracy": list_accuracy}
        total_correct += list_correct
        total_tests += args.num_samples
        print(f"   Accuracy: {list_accuracy:.1f}%")

        results["tests"].append(test_results)

    # Summary
    overall_accuracy = total_correct / total_tests * 100 if total_tests > 0 else 0
    results["overall"] = {"correct": total_correct, "total": total_tests, "accuracy": overall_accuracy}

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"\nOverall Accuracy: {overall_accuracy:.1f}% ({total_correct}/{total_tests})")

    print("\nBy Context Length:")
    for test in results["tests"]:
        ctx_correct = sum(t["correct"] for t in test["tests"].values())
        ctx_total = sum(t["total"] for t in test["tests"].values())
        ctx_acc = ctx_correct / ctx_total * 100 if ctx_total > 0 else 0
        print(f"  {test['context_length']:>6} tokens: {ctx_acc:>5.1f}%")

    print("\nBy Test Type (averaged across context lengths):")
    test_types = ["key_value", "uuid_passkey", "ordered_list"]
    for tt in test_types:
        tt_correct = sum(t["tests"].get(tt, {}).get("correct", 0) for t in results["tests"])
        tt_total = sum(t["tests"].get(tt, {}).get("total", 0) for t in results["tests"])
        tt_acc = tt_correct / tt_total * 100 if tt_total > 0 else 0
        print(f"  {tt:>15}: {tt_acc:>5.1f}%")

    # Save results
    output_file = f"synthetic_retrieval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Synthetic Retrieval Data Test")
    parser.add_argument("--checkpoint", type=str, default="checkpoints/best.pt",
                        help="Path to model checkpoint")
    parser.add_argument("--model_size", type=str, default="tiny",
                        choices=["tiny", "small", "medium", "large"],
                        help="Model size preset")
    parser.add_argument("--max_context", type=int, default=8192,
                        help="Maximum context length to test")
    parser.add_argument("--num_samples", type=int, default=3,
                        help="Number of samples per test type per context length")

    args = parser.parse_args()
    run_test(args)


if __name__ == "__main__":
    main()
