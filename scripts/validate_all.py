#!/usr/bin/env python3
"""
Validation Script for Phase/Hybrid Models
==========================================

Runs both LRA and Unified LLM tests sequentially to validate
Phase Attention O(n) complexity and training stability.

Usage:
    python scripts/validate_all.py
    python scripts/validate_all.py --quick        # Fast validation (500 steps each)
    python scripts/validate_all.py --full         # Full validation (2000 steps each)
"""

import subprocess
import sys
import time
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_banner():
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}   SYMBOLU PHASE ATTENTION VALIDATION{RESET}")
    print(f"{BOLD}   O(n) Efficient Attention at Scale{RESET}")
    print(f"{BOLD}{'='*70}{RESET}\n")


def run_test(name: str, cmd: list, timeout: int = 1800) -> tuple[bool, float, str]:
    """Run a test command and return success, duration, output."""
    print(f"{BLUE}[TEST]{RESET} {name}")
    print(f"  Command: {' '.join(cmd)}")
    print()

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent,
        )
        duration = time.time() - start

        # Print output
        if result.stdout:
            for line in result.stdout.split('\n')[-30:]:  # Last 30 lines
                print(f"  {line}")

        if result.returncode == 0:
            print(f"\n{GREEN}[PASS]{RESET} {name} completed in {duration:.1f}s")
            return True, duration, result.stdout
        else:
            print(f"\n{RED}[FAIL]{RESET} {name} failed (exit code {result.returncode})")
            if result.stderr:
                print(f"  Error: {result.stderr[-500:]}")
            return False, duration, result.stderr

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        print(f"\n{YELLOW}[TIMEOUT]{RESET} {name} timed out after {timeout}s")
        return False, duration, "Timeout"
    except Exception as e:
        duration = time.time() - start
        print(f"\n{RED}[ERROR]{RESET} {name}: {e}")
        return False, duration, str(e)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate Phase Attention models")
    parser.add_argument("--quick", action="store_true", help="Quick validation (500 steps)")
    parser.add_argument("--full", action="store_true", help="Full validation (2000 steps)")
    parser.add_argument("--lra-only", action="store_true", help="Only run LRA test")
    parser.add_argument("--llm-only", action="store_true", help="Only run LLM test")
    parser.add_argument("--seq-len", type=int, default=8192, help="Sequence length")
    args = parser.parse_args()

    print_banner()

    # Determine steps
    if args.full:
        lra_steps = 2000
        llm_steps = 2000
    elif args.quick:
        lra_steps = 500
        llm_steps = 500
    else:
        lra_steps = 1000
        llm_steps = 1000

    print(f"  Configuration:")
    print(f"    LRA Steps: {lra_steps}")
    print(f"    LLM Steps: {llm_steps}")
    print(f"    Sequence Length: {args.seq_len}")
    print()

    results = []

    # Test 1: LRA Pathfinder
    if not args.llm_only:
        lra_cmd = [
            sys.executable, "train_lra.py",
            "--task", "pathfinder",
            "--model-type", "phase",
            "--seq-len", str(args.seq_len),
            "--max-steps", str(lra_steps),
            "--gradient-checkpointing",
            "--log-every", "50",
            "--eval-every", "200",
        ]
        success, duration, output = run_test("LRA Pathfinder (Phase)", lra_cmd)
        results.append(("LRA Pathfinder", success, duration))

    # Test 2: Unified LLM Hybrid
    if not args.lra_only:
        llm_cmd = [
            sys.executable, "train_unified_llm.py",
            "--model-type", "hybrid",
            "--max-seq-len", str(args.seq_len),
            "--steps", str(llm_steps),
            "--gradient-checkpointing",
            "--log-every", "25",
            "--eval-every", "100",
        ]
        success, duration, output = run_test("Unified LLM (Hybrid)", llm_cmd)
        results.append(("Unified LLM Hybrid", success, duration))

    # Summary
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}   VALIDATION SUMMARY{RESET}")
    print(f"{BOLD}{'='*70}{RESET}\n")

    all_passed = True
    for name, success, duration in results:
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {name}: {duration:.1f}s")
        if not success:
            all_passed = False

    print()
    if all_passed:
        print(f"{GREEN}{BOLD}All tests passed!{RESET}")
        return 0
    else:
        print(f"{RED}{BOLD}Some tests failed.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
