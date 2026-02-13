"""
Claims-to-Tests Matrix Integrity Check
=======================================

Validates that every test file referenced in the claims-to-tests matrix
actually exists in the repository.  This prevents the matrix from going
stale as files are moved or renamed.

Run in CI to enforce matrix freshness.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = REPO_ROOT / "docs" / "reviews" / "CLAIMS_TO_TESTS_MATRIX.md"

# Test paths referenced in the matrix (relative to repo root).
# Keep in sync with docs/reviews/CLAIMS_TO_TESTS_MATRIX.md Section 1.
REFERENCED_TEST_FILES = [
    # A. Complexity & Scaling
    "symbolu/ontological/test_phase_attention.py",
    # B. Determinism & Auditability
    "tests/ontology_router/test_ontological_router_r1.py",
    "tests/explainability/test_telemetry_schema.py",
    "tests/test_ledger_replay_verifier.py",
    # C. Semantic Grounding
    "tests/integration/test_sovereign_integration.py",
    # D. Hallucination Detection
    "symbolu/agentic_framework/tests/test_confidence_gate.py",
    # E. Confidence-Gated Compute
    # (same as D — test_confidence_gate.py)
    # F. Context & Retrieval
    "test_needle_haystack.py",
    "eval_passkey.py",
    # I. Ontology Governance
    "tests/test_ontology_freeze_contract.py",
    # J. Coherence & Stability
    "tests/test_phase48_macro_stability_regulator.py",
    "tests/test_phase49_unified_temporal_stability.py",
    # K. Security
    "symbolu/mechanical/pipeline/integration_tests/test_adversarial_po1_p9.py",
    "tests/unit/service/test_api_security.py",
    # L. Production Readiness
    # (covered by CI workflows, not individual test files)
]

REFERENCED_CI_WORKFLOWS = [
    ".github/workflows/ontology-freeze-ci.yml",
    ".github/workflows/pipeline-ci.yml",
    ".github/workflows/telemetry-audit-ci.yml",
    ".github/workflows/backbone-ci.yml",
    ".github/workflows/formula-drift-ci.yml",
    ".github/workflows/gcc-safety-ci.yml",
]


class TestClaimsMatrixIntegrity(unittest.TestCase):
    """Verify the claims-to-tests matrix references valid files."""

    def test_matrix_document_exists(self):
        self.assertTrue(
            MATRIX_PATH.exists(),
            f"Claims matrix not found: {MATRIX_PATH}",
        )

    def test_all_referenced_test_files_exist(self):
        missing = []
        for rel_path in REFERENCED_TEST_FILES:
            full_path = REPO_ROOT / rel_path
            if not full_path.exists():
                missing.append(rel_path)
        self.assertEqual(
            missing, [],
            f"Referenced test files not found:\n  " + "\n  ".join(missing),
        )

    def test_all_referenced_ci_workflows_exist(self):
        missing = []
        for rel_path in REFERENCED_CI_WORKFLOWS:
            full_path = REPO_ROOT / rel_path
            if not full_path.exists():
                missing.append(rel_path)
        self.assertEqual(
            missing, [],
            f"Referenced CI workflows not found:\n  " + "\n  ".join(missing),
        )

    def test_matrix_has_validation_summary(self):
        content = MATRIX_PATH.read_text()
        self.assertIn("Validation Summary", content)
        self.assertIn("VALIDATED", content)
        self.assertIn("UNVALIDATED", content)

    def test_matrix_has_all_claim_categories(self):
        content = MATRIX_PATH.read_text()
        expected_categories = [
            "Complexity & Scaling",
            "Determinism & Auditability",
            "Semantic Grounding",
            "Hallucination Detection",
            "Confidence-Gated Compute",
            "Context & Retrieval",
            "Cost & Efficiency",
            "Accuracy & Routing",
            "Ontology Governance",
            "Coherence & Stability",
            "Security",
            "Production Readiness",
        ]
        for cat in expected_categories:
            self.assertIn(
                cat, content,
                f"Missing claim category in matrix: {cat}",
            )

    def test_master_table_rows_have_all_columns(self):
        """Every claim row in Section 1 master tables should have 5 columns."""
        content = MATRIX_PATH.read_text()

        # Extract only Section 1 (between "## 1)" and "## 2)")
        section1_match = re.search(
            r"## 1\).*?(?=## 2\))", content, re.DOTALL,
        )
        self.assertIsNotNone(section1_match, "Section 1 not found in matrix")
        section1 = section1_match.group(0)

        # Match rows like "| CS-1 | ... |"
        claim_row_pattern = re.compile(
            r"^\|\s*[A-Z]{2}-\d+\s*\|",
            re.MULTILINE,
        )
        rows = claim_row_pattern.findall(section1)
        self.assertGreater(len(rows), 0, "No claim rows found in Section 1")

        # Every claim row should have exactly 5 pipe-delimited columns
        full_row_pattern = re.compile(
            r"^\|\s*[A-Z]{2}-\d+\s*\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|",
            re.MULTILINE,
        )
        full_rows = full_row_pattern.findall(section1)
        self.assertEqual(
            len(rows), len(full_rows),
            "Some Section 1 claim rows have missing columns (expected 5 columns)",
        )


if __name__ == "__main__":
    unittest.main()
