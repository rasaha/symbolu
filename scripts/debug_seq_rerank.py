#!/usr/bin/env python3
"""Quick diagnostic: why does seq-rerank get 0% pass@1 on HumanEval?"""
import subprocess
import sys
import tempfile

# ── Test 1: Does run_unit_tests work at ALL with a known-good function? ──
print("=" * 60)
print("TEST 1: run_unit_tests with a known-good function")
print("=" * 60)

known_good_code = '''
from typing import List

def has_close_elements(numbers: List[float], threshold: float) -> bool:
    for idx, elem in enumerate(numbers):
        for idx2, elem2 in enumerate(numbers):
            if idx != idx2:
                distance = abs(elem - elem2)
                if distance < threshold:
                    return True
    return False
'''

test_code = '''
def check(candidate):
    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True
    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False
    assert candidate([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) == True
'''

entry_point = "has_close_elements"
full_code = known_good_code + "\n" + test_code + f"\ncheck({entry_point})\n"

# Test 1a: subprocess with env={"PATH": ""}
print("\n1a) subprocess with env={'PATH': ''} (current code):")
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=True) as tmp:
        tmp.write(full_code)
        tmp.flush()
        result = subprocess.run(
            [sys.executable, tmp.name],
            capture_output=True,
            timeout=10,
            env={"PATH": ""},
        )
        print(f"  returncode = {result.returncode}")
        if result.returncode != 0:
            print(f"  STDERR: {result.stderr.decode()[:500]}")
        else:
            print("  PASSED")
except Exception as e:
    print(f"  EXCEPTION: {e}")

# Test 1b: subprocess with inherited env
print("\n1b) subprocess with inherited env:")
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=True) as tmp:
        tmp.write(full_code)
        tmp.flush()
        result = subprocess.run(
            [sys.executable, tmp.name],
            capture_output=True,
            timeout=10,
        )
        print(f"  returncode = {result.returncode}")
        if result.returncode != 0:
            print(f"  STDERR: {result.stderr.decode()[:500]}")
        else:
            print("  PASSED")
except Exception as e:
    print(f"  EXCEPTION: {e}")

# Test 1c: in-process exec
print("\n1c) in-process exec:")
try:
    exec_globals = {}
    exec(full_code, exec_globals)
    print("  PASSED")
except Exception as e:
    print(f"  EXCEPTION: {e}")


# ── Test 2: What does the model actually generate? ──
print("\n" + "=" * 60)
print("TEST 2: What does the model generate?")
print("=" * 60)

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = "microsoft/phi-3.5-mini-instruct"
    print(f"Loading {model_name}...")
    # Try without trust_remote_code first (built-in phi3 is compatible
    # with transformers 5.x; the custom modeling_phi3.py uses removed
    # cache.seen_tokens attribute).
    for trust_remote in (False, True):
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=trust_remote
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=trust_remote,
                low_cpu_mem_usage=True,
            )
            if trust_remote:
                print("  (loaded with trust_remote_code=True)")
            break
        except (ValueError, KeyError, ImportError) as e:
            if trust_remote:
                raise
            print(f"  Native loading failed ({e}), retrying with "
                  "trust_remote_code=True...")
            continue
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.eval()

    # Use a simple HumanEval prompt
    prompt = '''from typing import List


def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """ Check if in given list of numbers, are any two numbers closer to each other than
    given threshold.
    >>> has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3)
    True
    >>> has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05)
    False
    """
'''

    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(model.device)
    P = input_ids.shape[1]
    print(f"  Prompt length: {P} tokens")

    # Generate 3 candidates
    outputs = model.generate(
        input_ids,
        attention_mask=torch.ones_like(input_ids),
        max_new_tokens=128,
        num_return_sequences=3,
        do_sample=True,
        temperature=0.8,
        top_p=0.95,
        pad_token_id=tokenizer.pad_token_id,
    )

    from symbolu.ontological.bcvf_seq_reranking import fix_completion_indent

    for k in range(3):
        cand_ids = outputs[k, P:]
        cand_text = tokenizer.decode(cand_ids, skip_special_tokens=True)
        cand_text_fixed = fix_completion_indent(prompt, cand_text)
        full_fn = prompt + cand_text_fixed

        print(f"\n--- Candidate {k} ({len(cand_ids)} tokens) ---")
        print(repr(cand_text[:300]))
        print(f"\n  Full code to execute:\n{full_fn[:500]}")

        # Try executing it
        exec_code = full_fn + "\n" + test_code + f"\ncheck({entry_point})\n"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=True
            ) as tmp:
                tmp.write(exec_code)
                tmp.flush()
                result = subprocess.run(
                    [sys.executable, tmp.name],
                    capture_output=True,
                    timeout=10,
                    env={"PATH": ""},
                )
                if result.returncode == 0:
                    print("  EXECUTION: PASSED")
                else:
                    stderr = result.stderr.decode()[:300]
                    print(f"  EXECUTION: FAILED (rc={result.returncode})")
                    print(f"  STDERR: {stderr}")
        except Exception as e:
            print(f"  EXECUTION: EXCEPTION {e}")

except ImportError:
    print("  (torch/transformers not available, skipping model test)")
except Exception as e:
    print(f"  ERROR: {e}")
