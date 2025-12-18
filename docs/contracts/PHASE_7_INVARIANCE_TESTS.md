PHASE-7 INVARIANCE TESTS SPECIFICATION
Version: 1.0
Date: 2025-12-18
Type: Test Specification (No Implementation)

================================================================================
PURPOSE
================================================================================

This document specifies invariance properties that any Phase-7 implementation
MUST satisfy. These are mechanical, testable properties derived from the
Phase-7 Target Contract.

This is a specification only. No test code is provided.
Tests are deterministic and reproducible.

================================================================================
1. INVARIANCE CATEGORIES
================================================================================

I1: DETERMINISM
    Same inputs always produce identical outputs.

I2: IDEMPOTENCE
    Repeated execution produces same results.

I3: ORDERING STABILITY
    Result ordering is deterministic and reproducible.

I4: ERROR DETERMINISM
    Same invalid inputs produce identical errors.

I5: SIMULATION FIDELITY
    Phase-7 does not alter Phase-6 behavior.

I6: ISOLATION
    Phase-7 does not modify external state.

I7: COMPLETENESS CONSISTENCY
    Completeness assessment is deterministic.

================================================================================
2. INVARIANCE TEST SPECIFICATIONS
================================================================================

==============================================================================
I1: DETERMINISM INVARIANCE
==============================================================================

Property:
  For any valid (target, generation_config, selection_config) triple,
  executing Phase-7 N times produces N identical result sets.

Test I1.1: Basic Determinism
  Given:
    target = { "final_magnitude": ">= 1.2", "len(steps)": "<= 5" }
    generation_config = { max_sequence_length: 5, max_candidates: 1000 }
    selection_config = { max_results: 10, scoring_mode: "distance" }

  Procedure:
    results_1 = execute_phase7(target, generation_config, selection_config)
    results_2 = execute_phase7(target, generation_config, selection_config)
    ... (repeat 50 times)

  Assert:
    All result sets are byte-wise identical
    results_1 == results_2 == ... == results_50

Test I1.2: Determinism Across Constraint Orderings
  Given:
    target_a = { "final_magnitude": ">= 1.2", "len(steps)": "<= 5" }
    target_b = { "len(steps)": "<= 5", "final_magnitude": ">= 1.2" }
    (same constraints, different ordering in specification)

  Procedure:
    results_a = execute_phase7(target_a, config, selection)
    results_b = execute_phase7(target_b, config, selection)

  Assert:
    results_a == results_b
    Constraint ordering does not affect output

Test I1.3: Determinism With Maximum Candidates
  Given:
    target = { "final_magnitude": "> 1.0" }
    config_a = { max_candidates: 100 }
    config_b = { max_candidates: 100 }

  Procedure:
    results_a = execute_phase7(target, config_a, selection)
    results_b = execute_phase7(target, config_b, selection)

  Assert:
    results_a == results_b
    Same max_candidates produces same subset

==============================================================================
I2: IDEMPOTENCE INVARIANCE
==============================================================================

Property:
  Executing Phase-7 multiple times in sequence produces same results
  as executing once. Phase-7 has no side effects that affect future runs.

Test I2.1: Sequential Execution Idempotence
  Given:
    target = { "final_magnitude": ">= 1.3", "len(steps)": "== 4" }

  Procedure:
    results_1 = execute_phase7(target, config, selection)
    results_2 = execute_phase7(target, config, selection)
    results_3 = execute_phase7(target, config, selection)

  Assert:
    results_1 == results_2 == results_3
    No drift or accumulation across runs

Test I2.2: Interleaved Execution Idempotence
  Given:
    target_x = { "final_magnitude": ">= 1.2" }
    target_y = { "len(steps)": "== 3" }

  Procedure:
    results_x1 = execute_phase7(target_x, config, selection)
    results_y1 = execute_phase7(target_y, config, selection)
    results_x2 = execute_phase7(target_x, config, selection)
    results_y2 = execute_phase7(target_y, config, selection)

  Assert:
    results_x1 == results_x2
    results_y1 == results_y2
    Execution of Y does not affect results of X

==============================================================================
I3: ORDERING STABILITY INVARIANCE
==============================================================================

Property:
  Result ordering is deterministic. Ties are broken consistently.

Test I3.1: Tie-Breaking Determinism
  Given:
    target = { "final_magnitude": ">= 1.0" }
    (Many sequences will tie with score 0 in binary mode)
    selection_config = { scoring_mode: "binary" }

  Procedure:
    results_1 = execute_phase7(target, config, selection)
    results_2 = execute_phase7(target, config, selection)

  Assert:
    Order of results_1 == order of results_2
    Tie-breaking is lexicographic and stable

Test I3.2: Score Ordering Consistency
  Given:
    target = { "final_magnitude": "== 1.5" }
    selection_config = { scoring_mode: "distance" }

  Procedure:
    results = execute_phase7(target, config, selection)

  Assert:
    For all i < j: results[i].score <= results[j].score
    Results are sorted by score ascending (distance mode)

Test I3.3: Rank Assignment Consistency
  Given:
    target = { "len(steps)": "<= 6", "final_magnitude": ">= 1.1" }

  Procedure:
    results = execute_phase7(target, config, selection)

  Assert:
    results[0].rank == 1
    results[i].rank == i + 1 for all i
    No gaps in rank sequence

==============================================================================
I4: ERROR DETERMINISM INVARIANCE
==============================================================================

Property:
  Invalid inputs produce identical error responses across executions.

Test I4.1: Invalid Target Field Error Determinism
  Given:
    target = { "harmony_score": 0.9 }  # invalid field

  Procedure:
    error_1 = execute_phase7(target, config, selection)  # expect error
    error_2 = execute_phase7(target, config, selection)  # expect error

  Assert:
    error_1.type == error_2.type == "UNKNOWN_TARGET_FIELD"
    error_1.field == error_2.field == "harmony_score"

Test I4.2: Contradictory Constraint Error Determinism
  Given:
    target = { "final_magnitude": "> 2.0", "final_magnitude": "< 1.0" }

  Procedure:
    error_1 = execute_phase7(target, config, selection)
    error_2 = execute_phase7(target, config, selection)

  Assert:
    error_1.type == error_2.type == "CONTRADICTORY_TARGET"
    Error details are identical

Test I4.3: Vacuous Target Error Determinism
  Given:
    target = { }  # empty

  Procedure:
    error_1 = execute_phase7(target, config, selection)
    error_2 = execute_phase7(target, config, selection)

  Assert:
    error_1.type == error_2.type == "VACUOUS_TARGET"

Test I4.4: Invalid Numeric Literal Error Determinism
  Given:
    target = { "final_magnitude": "== Infinity" }

  Procedure:
    error_1 = execute_phase7(target, config, selection)
    error_2 = execute_phase7(target, config, selection)

  Assert:
    error_1.type == error_2.type == "INVALID_NUMERIC_LITERAL"
    error_1.value == error_2.value == "Infinity"

==============================================================================
I5: SIMULATION FIDELITY INVARIANCE
==============================================================================

Property:
  Phase-7 invokes Phase-6 without modification. Phase-6 outputs are
  passed through unchanged.

Test I5.1: Phase-6 Output Preservation
  Given:
    sequence = ["ka", "a", "i", "ga"]
    direct_result = phase6_analyze(sequence)

    target = { "len(steps)": "== 4" }
    phase7_results = execute_phase7(target, config, selection)
    phase7_trajectory = find_result_by_sequence(phase7_results, sequence)

  Assert:
    phase7_trajectory.final_magnitude == direct_result.final_magnitude
    phase7_trajectory.steps == direct_result.steps
    Phase-7 does not transform Phase-6 output

Test I5.2: Phase-6 Configuration Unchanged
  Given:
    sequence = ["ka", "a"]
    config_before = get_phase6_config()

    execute_phase7(target, config, selection)

    config_after = get_phase6_config()

  Assert:
    config_before == config_after
    Phase-7 does not modify Phase-6 configuration

Test I5.3: Phase-6 Error Propagation
  Given:
    target that would generate invalid sequence ["a"] (vowel-initial)
    (This should not happen if generation is correct, but test anyway)

  If Phase-7 somehow passes ["a"] to Phase-6:
  Assert:
    Phase-6 error is captured in Phase-7 errors list
    Error type matches Phase-6 error type
    No silent swallowing of Phase-6 errors

==============================================================================
I6: ISOLATION INVARIANCE
==============================================================================

Property:
  Phase-7 execution does not modify any external state.

Test I6.1: Phase-4A Ontology Unchanged
  Given:
    ontology_hash_before = hash(phase4a_frozen_data)

    execute_phase7(target, config, selection)

    ontology_hash_after = hash(phase4a_frozen_data)

  Assert:
    ontology_hash_before == ontology_hash_after
    Frozen ontology is never modified

Test I6.2: No File System Side Effects
  Given:
    fs_snapshot_before = snapshot_relevant_directories()

    execute_phase7(target, config, selection)

    fs_snapshot_after = snapshot_relevant_directories()

  Assert:
    fs_snapshot_before == fs_snapshot_after
    No files created, modified, or deleted

Test I6.3: No Global State Mutation
  Given:
    global_state_before = capture_global_state()

    execute_phase7(target, config, selection)

    global_state_after = capture_global_state()

  Assert:
    global_state_before == global_state_after
    No module-level or singleton state changes

==============================================================================
I7: COMPLETENESS CONSISTENCY INVARIANCE
==============================================================================

Property:
  Completeness assessment is deterministic and consistent.

Test I7.1: Completeness Level Determinism
  Given:
    target = { "final_magnitude": ">= 1.3", "len(steps)": "<= 5" }

  Procedure:
    report_1 = validate_completeness(target, config)
    report_2 = validate_completeness(target, config)

  Assert:
    report_1.level == report_2.level
    report_1.warnings == report_2.warnings
    Completeness assessment is reproducible

Test I7.2: Discrimination Detection Consistency
  Given:
    target_discriminating = { "final_magnitude": ">= 1.5" }
    target_non_discriminating = { "steps[0].event": "reset" }

  Procedure:
    report_d = validate_completeness(target_discriminating, config)
    report_n = validate_completeness(target_non_discriminating, config)

  Assert:
    report_d.discrimination_ratio > 0
    report_n.discrimination_ratio == 0 (or warning issued)
    Discrimination is correctly detected

Test I7.3: Boundedness Detection Consistency
  Given:
    target_bounded = { "len(steps)": "<= 5" }
    target_unbounded = { "final_magnitude": ">= 1.5" }  # no length bound
    config_with_max = { max_sequence_length: 10 }
    config_without_max = { max_sequence_length: null }

  Procedure:
    report_1 = validate_completeness(target_bounded, config_without_max)
    report_2 = validate_completeness(target_unbounded, config_with_max)
    report_3 = validate_completeness(target_unbounded, config_without_max)

  Assert:
    report_1.bounded == true (explicit bound)
    report_2.bounded == true (config bound)
    report_3.bounded == false (no bound anywhere)

================================================================================
3. TEST EXECUTION REQUIREMENTS
================================================================================

REPRODUCIBILITY
  All tests must be executable with:
    - Fixed random seed (if any randomness exists, which it should not)
    - Deterministic iteration order over sets/dicts
    - No timing dependencies
    - No external service dependencies

ISOLATION
  Each test must:
    - Start from clean state
    - Not depend on prior test execution
    - Not leave artifacts affecting subsequent tests

COVERAGE
  Implementation test suite must include:
    - All I1-I7 invariance categories
    - At least 3 tests per category
    - Edge cases for each invariance

REGRESSION
  Any invariance violation is a critical bug.
  Invariance tests run on every commit.
  No invariance test may be skipped or marked expected-fail.

================================================================================
4. INVARIANCE VIOLATION SEVERITY
================================================================================

CRITICAL (Blocks Release):
  - I1 (Determinism): Any non-determinism
  - I4 (Error Determinism): Inconsistent error responses
  - I5 (Simulation Fidelity): Phase-6 output modification
  - I6 (Isolation): External state mutation

HIGH (Must Fix Before Merge):
  - I2 (Idempotence): Side effects between runs
  - I3 (Ordering Stability): Non-deterministic ordering

MEDIUM (Should Fix):
  - I7 (Completeness Consistency): Inconsistent completeness assessment

================================================================================
5. IMPLEMENTATION CHECKLIST
================================================================================

For Phase-7 implementation to be considered invariant-compliant:

[ ] I1.1: Basic determinism verified (50+ iterations)
[ ] I1.2: Constraint ordering independence verified
[ ] I1.3: Bounded enumeration determinism verified
[ ] I2.1: Sequential idempotence verified
[ ] I2.2: Interleaved idempotence verified
[ ] I3.1: Tie-breaking determinism verified
[ ] I3.2: Score ordering verified
[ ] I3.3: Rank assignment verified
[ ] I4.1: Invalid field error determinism verified
[ ] I4.2: Contradictory constraint error determinism verified
[ ] I4.3: Vacuous target error determinism verified
[ ] I4.4: Invalid literal error determinism verified
[ ] I5.1: Phase-6 output preservation verified
[ ] I5.2: Phase-6 config unchanged verified
[ ] I5.3: Phase-6 error propagation verified
[ ] I6.1: Ontology unchanged verified
[ ] I6.2: No file system side effects verified
[ ] I6.3: No global state mutation verified
[ ] I7.1: Completeness level determinism verified
[ ] I7.2: Discrimination detection verified
[ ] I7.3: Boundedness detection verified

================================================================================
END OF SPECIFICATION
================================================================================
