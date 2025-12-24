#!/usr/bin/env python3
"""
Tests for Acoustic Meaning Second Opinion Experiment
====================================================

Exactly 6 tests, one per invariant (INV-EXP-1 through INV-EXP-6).

Each test maps to exactly one invariant as specified in the experiment.
"""

import json
import sys
import pytest
from pathlib import Path

# Add the tools/experiments directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools" / "experiments"))

from acoustic_meaning_second_opinion import (
    analyze_acoustic_meaning,
    report_to_json,
    AcousticMeaningReport,
    INVARIANTS,
    FORBIDDEN_SEMANTIC_TERMS,
    DerivationType,
)


class TestAcousticMeaningSecondOpinion:
    """Test suite for acoustic meaning second opinion experiment."""

    # Proves INV-EXP-1: Must not output dictionary meaning as truth.
    # The report must never assert semantic meanings like "tub = container".
    # Any semantic inference must be flagged in forbidden_semantic_inferences_detected.
    def test_inv_exp_1_no_semantics(self):
        """
        Proves INV-EXP-1: Must not output dictionary meaning as truth.

        The report must:
        - NOT contain dictionary definitions as assertions
        - Flag any word that has a dictionary meaning in forbidden_semantic_inferences_detected
        """
        report = analyze_acoustic_meaning("tub")

        # Check that forbidden semantic terms are flagged
        assert len(report.forbidden_semantic_inferences_detected) > 0, (
            "INV-EXP-1 VIOLATION: Word 'tub' has dictionary meaning but "
            "nothing was flagged in forbidden_semantic_inferences_detected"
        )

        # Check that the flagged message mentions forbidden
        for msg in report.forbidden_semantic_inferences_detected:
            assert "FORBIDDEN" in msg.upper(), (
                f"INV-EXP-1 VIOLATION: Flagged message should contain 'FORBIDDEN': {msg}"
            )

        # Check that abstraction candidates do not assert dictionary meanings
        for candidate in report.abstraction_candidates:
            label = candidate.get("label", "")
            justification = candidate.get("justification", "")

            # Should not contain dictionary meaning words
            for term in ["container", "bathtub", "vessel", "basin"]:
                assert term not in label.lower(), (
                    f"INV-EXP-1 VIOLATION: Candidate label contains forbidden term '{term}'"
                )
                assert term not in justification.lower(), (
                    f"INV-EXP-1 VIOLATION: Candidate justification contains forbidden term '{term}'"
                )

    # Proves INV-EXP-2: Every abstraction candidate must cite which acoustic/vritti facts it used.
    # The source_facts field must be non-empty for every candidate.
    def test_inv_exp_2_traceability(self):
        """
        Proves INV-EXP-2: Every abstraction must cite acoustic/vritti facts.

        Every abstraction_candidate must have a non-empty source_facts list
        that explains what acoustic or vritti data it used.
        """
        report = analyze_acoustic_meaning("please")

        assert len(report.abstraction_candidates) > 0, (
            "Need at least one abstraction candidate to test traceability"
        )

        for idx, candidate in enumerate(report.abstraction_candidates):
            source_facts = candidate.get("source_facts", [])

            # Must have source facts
            assert isinstance(source_facts, list), (
                f"INV-EXP-2 VIOLATION: Candidate {idx} source_facts is not a list"
            )
            assert len(source_facts) > 0, (
                f"INV-EXP-2 VIOLATION: Candidate {idx} '{candidate.get('label')}' "
                "has empty source_facts - must cite acoustic/vritti facts"
            )

            # Source facts should reference acoustic or vritti data
            combined = " ".join(source_facts).lower()
            has_acoustic_ref = any(term in combined for term in [
                "acoustic", "sound_class", "vowel", "consonant", "unit"
            ])
            has_vritti_ref = any(term in combined for term in [
                "vritti", "weight", "distribution", "motion"
            ])

            assert has_acoustic_ref or has_vritti_ref, (
                f"INV-EXP-2 VIOLATION: Candidate {idx} source_facts must reference "
                f"acoustic or vritti data. Got: {source_facts}"
            )

    # Proves INV-EXP-3: Every claim is labeled RULE-BASED or HEURISTIC.
    # The derivation field must be exactly one of these two values.
    def test_inv_exp_3_labeling(self):
        """
        Proves INV-EXP-3: Every claim labeled RULE-BASED or HEURISTIC.

        Every abstraction_candidate must have a derivation field that is
        exactly "RULE-BASED" or "HEURISTIC".
        """
        report = analyze_acoustic_meaning("tub")

        assert len(report.abstraction_candidates) > 0, (
            "Need at least one abstraction candidate to test labeling"
        )

        valid_derivations = {
            DerivationType.RULE_BASED.value,
            DerivationType.HEURISTIC.value
        }

        for idx, candidate in enumerate(report.abstraction_candidates):
            derivation = candidate.get("derivation")

            assert derivation is not None, (
                f"INV-EXP-3 VIOLATION: Candidate {idx} missing derivation field"
            )
            assert derivation in valid_derivations, (
                f"INV-EXP-3 VIOLATION: Candidate {idx} derivation '{derivation}' "
                f"must be one of {valid_derivations}"
            )

        # Also verify motion_profile has derivation label
        motion_derivation = report.motion_profile.get("derivation")
        assert motion_derivation in valid_derivations, (
            f"INV-EXP-3 VIOLATION: motion_profile derivation '{motion_derivation}' "
            f"must be one of {valid_derivations}"
        )

    # Proves INV-EXP-4: Same input produces identical JSON (stable ordering).
    # Running the analysis twice with the same input must produce byte-identical JSON.
    def test_inv_exp_4_determinism(self):
        """
        Proves INV-EXP-4: Same input produces identical JSON output.

        Running analyze_acoustic_meaning twice with the same input
        must produce byte-identical JSON output.
        """
        # Run analysis twice
        report1 = analyze_acoustic_meaning("tub")
        report2 = analyze_acoustic_meaning("tub")

        # Convert to JSON
        json1 = report_to_json(report1)
        json2 = report_to_json(report2)

        # Must be byte-identical
        assert json1 == json2, (
            "INV-EXP-4 VIOLATION: Same input produced different JSON output.\n"
            f"First run:\n{json1[:500]}...\n\n"
            f"Second run:\n{json2[:500]}..."
        )

        # Also verify with different word
        report3 = analyze_acoustic_meaning("please")
        report4 = analyze_acoustic_meaning("please")
        json3 = report_to_json(report3)
        json4 = report_to_json(report4)

        assert json3 == json4, (
            "INV-EXP-4 VIOLATION: Determinism failed for word 'please'"
        )

        # Verify JSON is valid and parseable
        parsed1 = json.loads(json1)
        parsed3 = json.loads(json3)

        assert parsed1["input"] == "tub"
        assert parsed3["input"] == "please"

    # Proves INV-EXP-5: acoustic_units/signature is independent of abstraction_candidates.
    # The acoustic data must be computed before and independently of abstractions.
    def test_inv_exp_5_separation(self):
        """
        Proves INV-EXP-5: Acoustic data independent of abstraction candidates.

        The acoustic_units and acoustic_signature must be computed purely
        from the input text, independent of what abstractions are generated.
        """
        report = analyze_acoustic_meaning("tub")

        # Acoustic units should be present
        assert len(report.acoustic_units) > 0, (
            "INV-EXP-5 VIOLATION: No acoustic units generated"
        )

        # Acoustic signature should be present
        assert report.acoustic_signature, (
            "INV-EXP-5 VIOLATION: No acoustic signature generated"
        )

        # Verify acoustic units contain only acoustic properties (no semantic fields)
        for unit in report.acoustic_units:
            # Must have acoustic properties
            assert "sound_class" in unit, "Missing sound_class"
            assert "vowel_height" in unit, "Missing vowel_height"
            assert "consonant_count" in unit, "Missing consonant_count"

            # Must NOT have semantic fields
            assert "meaning" not in unit, (
                "INV-EXP-5 VIOLATION: acoustic_unit contains 'meaning' field"
            )
            assert "definition" not in unit, (
                "INV-EXP-5 VIOLATION: acoustic_unit contains 'definition' field"
            )
            assert "semantic" not in unit, (
                "INV-EXP-5 VIOLATION: acoustic_unit contains 'semantic' field"
            )

        # Verify signature is derived from units, not abstractions
        # Signature format should be like "VH-VX" (sound_class_initial + vowel_height_initial)
        sig_parts = report.acoustic_signature.split("-")
        assert len(sig_parts) == len(report.acoustic_units), (
            f"INV-EXP-5 VIOLATION: Signature parts ({len(sig_parts)}) "
            f"doesn't match unit count ({len(report.acoustic_units)})"
        )

        # Run with nonsense word to verify independence
        report_nonsense = analyze_acoustic_meaning("gsdf")
        # Should still produce acoustic data even without meaningful abstractions
        assert len(report_nonsense.acoustic_units) > 0, (
            "INV-EXP-5 VIOLATION: Nonsense word should still produce acoustic units"
        )
        assert report_nonsense.acoustic_signature, (
            "INV-EXP-5 VIOLATION: Nonsense word should still produce signature"
        )

    # Proves INV-EXP-6: Any semantic leap must be flagged and listed.
    # HEURISTIC candidates must have semantic_risk field, and high-risk items must be flagged.
    def test_inv_exp_6_risk_flagging(self):
        """
        Proves INV-EXP-6: Semantic leaps must be flagged.

        Every abstraction_candidate must have a semantic_risk field.
        HEURISTIC candidates should generally have higher risk than RULE-BASED.
        """
        report = analyze_acoustic_meaning("tub")

        valid_risk_levels = {"low", "medium", "high"}
        heuristic_risks = []
        rule_based_risks = []

        for idx, candidate in enumerate(report.abstraction_candidates):
            # Must have semantic_risk field
            risk = candidate.get("semantic_risk")
            assert risk is not None, (
                f"INV-EXP-6 VIOLATION: Candidate {idx} missing semantic_risk field"
            )
            assert risk in valid_risk_levels, (
                f"INV-EXP-6 VIOLATION: Candidate {idx} semantic_risk '{risk}' "
                f"must be one of {valid_risk_levels}"
            )

            # Track risks by derivation type
            derivation = candidate.get("derivation")
            if derivation == "HEURISTIC":
                heuristic_risks.append(risk)
            else:
                rule_based_risks.append(risk)

        # Verify that HEURISTIC candidates generally have higher risk
        # At least one heuristic should have medium or high risk
        if heuristic_risks:
            has_elevated_risk = any(r in {"medium", "high"} for r in heuristic_risks)
            assert has_elevated_risk, (
                "INV-EXP-6 VIOLATION: HEURISTIC candidates should have "
                "at least one medium/high semantic_risk to flag the semantic leap"
            )

        # Test with nonsense word - should have high risk abstractions
        report_nonsense = analyze_acoustic_meaning("gsdf")
        nonsense_risks = [
            c.get("semantic_risk") for c in report_nonsense.abstraction_candidates
            if c.get("derivation") == "HEURISTIC"
        ]
        if nonsense_risks:
            has_high_risk = any(r == "high" for r in nonsense_risks)
            assert has_high_risk, (
                "INV-EXP-6 VIOLATION: Nonsense word 'gsdf' should have "
                "at least one high semantic_risk heuristic candidate"
            )


# ============================================================================
# INVARIANT VERIFICATION HELPERS
# ============================================================================

class TestInvariantDefinitions:
    """Verify that invariants are properly defined in the module."""

    def test_all_invariants_defined(self):
        """Verify all 6 invariants are defined."""
        expected = ["INV-EXP-1", "INV-EXP-2", "INV-EXP-3", "INV-EXP-4", "INV-EXP-5", "INV-EXP-6"]
        for inv in expected:
            assert inv in INVARIANTS, f"Missing invariant definition: {inv}"

    def test_invariant_descriptions_non_empty(self):
        """Verify all invariant descriptions are non-empty."""
        for key, desc in INVARIANTS.items():
            assert desc and len(desc) > 10, f"Invariant {key} has insufficient description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
