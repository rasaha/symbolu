#!/bin/bash
# =============================================================================
# Sovereign-1 Phase 2 Unit Test Runner
# =============================================================================
#
# This script runs all Phase 2 unit tests to verify:
# - PIDGovernor: Vritti detection, authority gating, gradient flow
# - SovereignTransformer: AmbidextrousLayer mode switching, Virtual Nexus
# - SovereignGunaComputer: Shannon entropy, variance, cosine similarity
# - DeterministicPhonemeEncoder: Determinism, feature structure
# - ReferentLookup: Class encoding
#
# CRITICAL CHECKS:
# 1. Gradients flow correctly through all modules
# 2. AmbidextrousLayer correctly switches between quadratic and phase modes
# 3. PIDGovernor doesn't zero out gradients
# 4. Guna conservation property holds (S+R+T = 1.0)
#
# Usage:
#   ./scripts/run_phase2_tests.sh          # Run all tests
#   ./scripts/run_phase2_tests.sh -v       # Verbose output
#   ./scripts/run_phase2_tests.sh -k pid   # Run only PID tests
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Sovereign-1 Phase 2 Unit Tests"
echo "=============================================="
echo ""
echo "Project: $PROJECT_ROOT"
echo "Python:  $(python --version 2>&1)"
echo ""

# Check dependencies
echo "Checking dependencies..."
python -c "import torch; print(f'  PyTorch: {torch.__version__}')" || {
    echo "ERROR: PyTorch not installed. Install with:"
    echo "  pip install torch"
    exit 1
}

python -c "import pytest; print(f'  pytest: {pytest.__version__}')" || {
    echo "ERROR: pytest not installed. Install with:"
    echo "  pip install pytest"
    exit 1
}

echo ""
echo "Running tests..."
echo "=============================================="

# Run pytest with any additional arguments passed to this script
python -m pytest tests/test_sovereign_phase2.py "$@" \
    --tb=short \
    -W ignore::DeprecationWarning

TEST_EXIT_CODE=$?

echo ""
echo "=============================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED (exit code: $TEST_EXIT_CODE)"
fi
echo "=============================================="

exit $TEST_EXIT_CODE
