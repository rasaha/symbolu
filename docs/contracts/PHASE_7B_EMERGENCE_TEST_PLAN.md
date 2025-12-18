PHASE-7B EMERGENCE TEST PLAN
Version: 1.0
Date: 2025-12-18
Type: Experiment Specification

================================================================================
PURPOSE
================================================================================

This document specifies concrete experiments to test the emergence hypothesis
of Phase-7B Compositional Targeting:

  "Properties can emerge through mechanical iteration over a validity space
   without being explicitly targeted, and without interpretation or learning."

These experiments are designed to falsify the hypothesis under adversarial
conditions before committing to Phase-8 (semantic boundary) or Phase-7
implementation.

================================================================================
HYPOTHESIS UNDER TEST
================================================================================

H₀ (Null): Compositional targeting produces only what is explicitly targeted.
           No emergent properties appear. Iteration is equivalent to single run.

H₁ (Alt):  Compositional targeting produces emergent properties that:
           - Are not explicitly targeted
           - Are mechanically measurable
           - Arise from validity space structure
           - Require iteration to appear

Goal: Reject H₀ with mechanical evidence, or identify where emergence fails.

================================================================================
EXPERIMENT 1: DIVERSITY EMERGENCE WITHOUT DIVERSITY TARGETS
================================================================================

OBJECTIVE
  Demonstrate that sequence diversity emerges purely from Exclusion Chains,
  without any diversity metric in the target specification.

SETUP
  Initial Target T₀:
    {
      "len(steps)": ">= 4",
      "len(steps)": "<= 6",
      "final_magnitude": ">= 1.1",
      "final_magnitude": "<= 1.4",
      "count(steps where event == 'modulate')": ">= 1"
    }

  Generation Config:
    max_sequence_length: 6
    max_candidates: 10000
    vowel_set: {a, i, u}
    consonant_set: {ka, ga, ta, da, pa, ba}  # subset for tractability

  Selection Config:
    max_results: 20
    scoring_mode: binary

PROCEDURE
  Iteration 0:
    R₀ = execute_phase7(T₀, gen_config, sel_config)
    found_sequences = set(R₀.results[0:10].sequences)

  Iteration n (for n = 1 to 9):
    Tₙ = T₀ + { "sequence NOT IN": found_sequences }
    Rₙ = execute_phase7(Tₙ, gen_config, sel_config)
    found_sequences = found_sequences.union(Rₙ.results[0:10].sequences)

  Total iterations: 10
  Expected found sequences: up to 100

METRICS (All Mechanical)

  M1.1: Pairwise Edit Distance Distribution
    For all pairs (sᵢ, sⱼ) in found_sequences:
      edit_distance(sᵢ, sⱼ) = Levenshtein distance on token sequences
    Compute:
      - mean_edit_distance
      - min_edit_distance
      - std_edit_distance

  M1.2: Template Coverage
    Template = abstract pattern replacing specific tokens with types
    Example: ["ka", "a", "ga"] → [C, V, C]
    Compute:
      - unique_templates_found
      - template_distribution (count per template)

  M1.3: Token Coverage
    Compute:
      - unique_consonants_used / total_consonants_available
      - unique_vowels_used / total_vowels_available

  M1.4: Iteration Diversity Growth
    For each iteration n:
      diversity_n = mean_edit_distance(found_sequences at iteration n)
    Compute:
      - diversity_growth_curve: [diversity_0, diversity_1, ..., diversity_9]

PASS CONDITIONS

  P1.1: Diversity Increase
    diversity_9 > diversity_0 * 1.2
    (At least 20% increase in mean edit distance)

  P1.2: Template Coverage
    unique_templates_found >= 0.5 * theoretical_max_templates
    (At least 50% of possible templates discovered)

  P1.3: No Diversity Target
    Verify: No constraint in any Tₙ references edit distance, template,
    or any diversity metric.

  P1.4: Determinism
    Run experiment twice with identical inputs.
    All results must be byte-wise identical.

FAILURE MODES

  F1.1: Diversity Plateau
    diversity_n stabilizes before iteration 5
    Indicates: validity space too small or constraints too tight

  F1.2: Clustering
    Most found sequences share >80% edit similarity
    Indicates: exclusion not sufficient for diversity

  F1.3: Non-Determinism
    Two runs produce different found_sequences
    Indicates: implementation bug (CRITICAL)

NO-SEMANTICS CHECKLIST
  [ ] No "diversity" in any target constraint
  [ ] No "similarity" in any target constraint
  [ ] Edit distance computed post-hoc, not during generation
  [ ] Template extraction is mechanical (token type mapping)
  [ ] No human judgment in pass/fail evaluation

================================================================================
EXPERIMENT 2: FEASIBILITY BOUNDARY EMERGENCE (BISECTION SEARCH)
================================================================================

OBJECTIVE
  Demonstrate that the system discovers a feasibility boundary mechanically
  through bisection, without the boundary being explicitly specified.

SETUP
  Parameterized Target T(x):
    {
      "final_magnitude": f">= {x}",
      "len(steps)": "<= 8"
    }

  Search Space:
    x_low = 1.0 (known feasible: any consonant)
    x_high = 3.0 (known infeasible: exceeds max accumulation)
    precision = 0.01

  Generation Config:
    max_sequence_length: 8
    max_candidates: 5000
    vowel_set: {a, i, u}
    consonant_set: {ka, ga, ta, da, pa, ba}

  Selection Config:
    max_results: 1
    scoring_mode: binary

PROCEDURE
  iteration = 0
  low = x_low
  high = x_high
  history = []

  while high - low > precision and iteration < 20:
    mid = (low + high) / 2
    T = T(mid)
    R = execute_phase7(T, gen_config, sel_config)

    feasible = R.metadata.candidates_satisfying > 0

    history.append({
      iteration: iteration,
      x: mid,
      feasible: feasible,
      candidates_satisfying: R.metadata.candidates_satisfying
    })

    if feasible:
      low = mid
    else:
      high = mid

    iteration += 1

  x_star = low  # converged boundary

METRICS (All Mechanical)

  M2.1: Convergence Value
    x_star = final low value after convergence

  M2.2: Convergence Iterations
    iterations_to_converge = number of iterations until high - low <= precision

  M2.3: Convergence Stability
    Run bisection 3 times with identical inputs.
    x_star_variance = variance([x_star_1, x_star_2, x_star_3])

  M2.4: Theoretical Validation
    Compute theoretical maximum magnitude:
      max_theoretical = 1.0 + (max_length - 1) * max(vowel_deltas)
      For length 8 with vowels {a:0.1, i:0.2, u:0.15}:
      max_theoretical = 1.0 + 7 * 0.2 = 2.4
    Compare: |x_star - max_theoretical| / max_theoretical

PASS CONDITIONS

  P2.1: Convergence
    Bisection converges within 20 iterations

  P2.2: Determinism
    x_star_variance == 0 (identical across runs)

  P2.3: Boundary Accuracy
    |x_star - max_theoretical| / max_theoretical < 0.05
    (Within 5% of theoretical maximum)

  P2.4: Monotonic Feasibility
    For all x < x_star: T(x) is feasible
    For all x > x_star + precision: T(x) is infeasible

FAILURE MODES

  F2.1: Non-Convergence
    high - low > precision after 20 iterations
    Indicates: numerical instability or non-monotonic feasibility

  F2.2: Boundary Drift
    x_star varies across identical runs
    Indicates: non-determinism (CRITICAL)

  F2.3: Incorrect Boundary
    |x_star - max_theoretical| > 0.2
    Indicates: Phase-6 mechanics misunderstood or bug

NO-SEMANTICS CHECKLIST
  [ ] No "boundary" in any target constraint
  [ ] No "maximum" in any target constraint (only >=)
  [ ] Bisection logic is pure arithmetic
  [ ] Feasibility determined only by candidates_satisfying count
  [ ] No interpretation of "what the boundary means"

================================================================================
EXPERIMENT 3: SHAPE TRANSFER GENERALIZATION
================================================================================

OBJECTIVE
  Demonstrate that trajectory shape can be transferred across different
  surface constraints, showing shape as an emergent structural property.

SETUP
  Phase A: Shape Discovery
    Target T_A:
      {
        "final_magnitude": ">= 1.3",
        "len(steps)": "== 5"
      }

    Generation Config:
      max_sequence_length: 5
      max_candidates: 5000

    Selection Config:
      max_results: 10
      scoring_mode: distance (to final_magnitude target)

  Phase B: Shape Transfer
    Extract shape signature from best result R_A.results[0]:
      shape_signature = {
        monotonic: is_monotonic(steps[].magnitude),
        terminal_event: steps[-1].event,
        peak_position: argmax(steps[].magnitude),
        magnitude_range: max(magnitude) - min(magnitude)
      }

    Target T_B (different length, same shape):
      {
        "monotonic_increasing(steps[].magnitude)": shape_signature.monotonic,
        "steps[-1].event": shape_signature.terminal_event,
        "len(steps)": "== 7",  # different from Phase A
        "final_magnitude": ">= 1.3"
      }

PROCEDURE
  # Phase A
  R_A = execute_phase7(T_A, gen_config_A, sel_config)
  best_A = R_A.results[0]
  shape_sig = extract_shape_signature(best_A.trajectory)

  # Phase B
  T_B = construct_shape_target(shape_sig, new_length=7)
  R_B = execute_phase7(T_B, gen_config_B, sel_config)

  # Baseline (random, no shape constraint)
  T_baseline = { "len(steps)": "== 7", "final_magnitude": ">= 1.3" }
  R_baseline = execute_phase7(T_baseline, gen_config_B, sel_config)

METRICS (All Mechanical)

  M3.1: Shape Match Score
    For each result r in R_B:
      shape_score(r) = weighted sum of:
        - monotonicity_match: 1 if matches, 0 otherwise
        - terminal_event_match: 1 if matches, 0 otherwise
        - peak_position_similarity: 1 - |peak_r - peak_sig| / len(steps)

  M3.2: Baseline Shape Scores
    Compute shape_score for each result in R_baseline

  M3.3: Shape Score Distribution Comparison
    Compare distributions:
      mean_shape_B = mean(shape_scores for R_B)
      mean_shape_baseline = mean(shape_scores for R_baseline)
      improvement_ratio = mean_shape_B / mean_shape_baseline

  M3.4: Shape Preservation Rate
    shape_preserved_count = count(r in R_B where shape_score(r) > 0.8)
    preservation_rate = shape_preserved_count / len(R_B.results)

PASS CONDITIONS

  P3.1: Shape Transfer Success
    improvement_ratio > 1.5
    (Shape-constrained results have 50% better shape match than baseline)

  P3.2: Shape Preservation
    preservation_rate > 0.7
    (70% of shape-targeted results preserve the shape)

  P3.3: Generalization
    Shape successfully transfers to different length sequences

  P3.4: No Shape-Specific Mechanics
    Shape is captured entirely by existing Phase-7 constraints
    No new "shape" constraint type invented

FAILURE MODES

  F3.1: No Shape Transfer
    improvement_ratio <= 1.0
    Indicates: shape constraints too weak or not captured correctly

  F3.2: Shape Not Expressible
    Cannot express shape_signature using valid Phase-7 constraints
    Indicates: constraint vocabulary insufficient

  F3.3: Length Coupling
    Shape only transfers to same-length sequences
    Indicates: shape is not generalizable

NO-SEMANTICS CHECKLIST
  [ ] "Shape" is defined purely by mechanical properties
  [ ] No "beautiful shape" or "good shape" criteria
  [ ] Shape signature extracted via arithmetic only
  [ ] Shape matching is numeric comparison
  [ ] No interpretation of what shapes "mean"

================================================================================
EXPERIMENT 4: ADVERSARIAL EMPTY/TRIVIAL TARGET SAFETY
================================================================================

OBJECTIVE
  Verify that Phase-7B does not invent implicit goals or produce unbounded
  behavior when given empty, trivial, or under-specified targets.

SETUP
  Test Cases:

  Case 4.1: Empty Target
    target = {}

  Case 4.2: Trivial Target (Always True)
    target = { "steps[0].event": "reset" }  # Phase-6 invariant

  Case 4.3: Minimal Discrimination
    target = { "len(steps)": "== 4" }  # only length constraint

  Case 4.4: Tautological Bounds
    target = { "final_magnitude": ">= 0.0", "final_magnitude": "<= 1000.0" }

  Generation Config:
    max_sequence_length: 6
    max_candidates: 1000

  Selection Config:
    max_results: 100
    scoring_mode: binary

PROCEDURE
  For each test case:
    try:
      R = execute_phase7(target, gen_config, sel_config)
      record: success, results_count, metadata
    except Phase7Error as e:
      record: error_type, error_message

EXPECTED BEHAVIOR

  Case 4.1: Empty Target
    Expected: Immediate rejection with VACUOUS_TARGET error
    (Per Phase-7 Contract Section 2: EMPTY TARGET PROHIBITION)

  Case 4.2: Trivial Target
    Expected: Either
      (a) Rejection with warning "non-discriminating target", OR
      (b) Acceptance with completeness level 1 (valid but incomplete)
    Output must be bounded and deterministic.

  Case 4.3: Minimal Discrimination
    Expected: Acceptance with completeness level 2
    All length-4 sequences returned, ranked lexicographically.
    Result count must match theoretical count of length-4 sequences.

  Case 4.4: Tautological Bounds
    Expected: Same as Case 4.3 behavior
    Bounds so wide they match everything.

METRICS (All Mechanical)

  M4.1: Error Consistency
    For rejection cases: same error type and message across runs

  M4.2: Output Boundedness
    For acceptance cases: results_count <= max_results
    candidates_generated <= max_candidates

  M4.3: Output Determinism
    Results identical across multiple runs

  M4.4: Completeness Level Accuracy
    Completeness level matches expected level for each case

  M4.5: No Implicit Goals
    For acceptance cases, verify:
      - No preferential ranking (all scores equal in binary mode)
      - Ranking is purely lexicographic
      - No "better" sequences selected by hidden criteria

PASS CONDITIONS

  P4.1: Empty Target Rejected
    Case 4.1 produces VACUOUS_TARGET error

  P4.2: Bounded Output
    All acceptance cases produce bounded results

  P4.3: Deterministic Behavior
    All cases produce identical results across runs

  P4.4: No Hidden Goals
    Accepted results show no evidence of implicit selection criteria

  P4.5: Traceable Behavior
    All outputs explainable by explicit constraints + enumeration order

FAILURE MODES

  F4.1: Empty Target Accepted
    {} produces results instead of error
    Indicates: contract violation (CRITICAL)

  F4.2: Unbounded Output
    Results exceed configured limits
    Indicates: implementation bug (CRITICAL)

  F4.3: Hidden Selection
    Trivial targets produce non-uniform selection
    Indicates: implicit goal injection (CRITICAL)

  F4.4: Non-Determinism
    Different runs produce different results
    Indicates: implementation bug (CRITICAL)

NO-SEMANTICS CHECKLIST
  [ ] No interpretation of "what user wanted"
  [ ] No "helpful" default constraints added
  [ ] No "reasonable" bounds inferred
  [ ] Behavior follows contract literally
  [ ] Rejection is explicit, not silent filtering

================================================================================
EXPERIMENT 5: STABILITY UNDER DERIVATION RULE PERTURBATION
================================================================================

OBJECTIVE
  Demonstrate that emergent properties depend on the validity space structure,
  not on brittle details of the derivation rule.

SETUP
  Fixed Initial Target T₀:
    {
      "final_magnitude": ">= 1.2",
      "len(steps)": "<= 6"
    }

  Generation Config:
    max_sequence_length: 6
    max_candidates: 5000

  Selection Config:
    max_results: 20
    scoring_mode: distance

  Derivation Policy A: Progressive Refinement
    def derive_A(T, R):
      best_mag = R.results[0].trajectory.final_magnitude
      return T + { "final_magnitude": f">= {best_mag * 0.95}" }

  Derivation Policy B: Threshold Escalation
    def derive_B(T, R):
      current_threshold = extract_magnitude_bound(T)
      return { "final_magnitude": f">= {current_threshold + 0.05}",
               "len(steps)": "<= 6" }

  Termination: 10 iterations or infeasibility

PROCEDURE
  # Run with Policy A
  results_A = []
  T = T₀
  for i in range(10):
    R = execute_phase7(T, gen_config, sel_config)
    results_A.append((T, R))
    if not R.metadata.target_feasible:
      break
    T = derive_A(T, R)

  # Run with Policy B
  results_B = []
  T = T₀
  for i in range(10):
    R = execute_phase7(T, gen_config, sel_config)
    results_B.append((T, R))
    if not R.metadata.target_feasible:
      break
    T = derive_B(T, R)

METRICS (All Mechanical)

  M5.1: Final Magnitude Reached
    final_mag_A = max magnitude achieved by Policy A before infeasibility
    final_mag_B = max magnitude achieved by Policy B before infeasibility

  M5.2: Convergence Iterations
    iterations_A = iterations until infeasibility (Policy A)
    iterations_B = iterations until infeasibility (Policy B)

  M5.3: Structural Similarity
    Compare final result sets:
      - template_overlap = |templates_A ∩ templates_B| / |templates_A ∪ templates_B|
      - magnitude_range_overlap = overlap of magnitude distributions

  M5.4: Boundary Agreement
    Both policies should discover similar feasibility boundaries.
    boundary_diff = |final_mag_A - final_mag_B|

PASS CONDITIONS

  P5.1: Comparable Extremes
    |final_mag_A - final_mag_B| / max(final_mag_A, final_mag_B) < 0.1
    (Within 10% of each other)

  P5.2: Structural Overlap
    template_overlap > 0.5
    (Majority of discovered structures shared)

  P5.3: Boundary Agreement
    boundary_diff < 0.1
    Both policies find similar feasibility limits

  P5.4: Policy Independence
    Emergent properties (boundary, structure) are similar despite
    different derivation rules

FAILURE MODES

  F5.1: Divergent Extremes
    |final_mag_A - final_mag_B| > 0.3
    Indicates: emergence depends on derivation details (bad)

  F5.2: No Structural Overlap
    template_overlap < 0.3
    Indicates: discovered structures are artifacts of policy

  F5.3: Policy-Dependent Boundary
    Policies find very different feasibility limits
    Indicates: boundary is not a property of validity space

NO-SEMANTICS CHECKLIST
  [ ] Both policies are mechanical (arithmetic only)
  [ ] No "better" policy judgment
  [ ] Comparison metrics are purely structural
  [ ] No interpretation of why policies differ
  [ ] Policy choice is experimental variable, not optimization

================================================================================
SUMMARY: EXPERIMENT MATRIX
================================================================================

| Exp | Name                      | Tests                          | Key Metric              |
|-----|---------------------------|--------------------------------|-------------------------|
| 1   | Diversity Emergence       | Exclusion chains               | Edit distance growth    |
| 2   | Boundary Emergence        | Bisection search               | x* convergence          |
| 3   | Shape Transfer            | Cross-length shape matching    | Shape score improvement |
| 4   | Trivial Target Safety     | Empty/trivial targets          | No hidden goals         |
| 5   | Derivation Stability      | Policy A vs Policy B           | Structural overlap      |

================================================================================
EXECUTION ORDER
================================================================================

Recommended execution order (by dependency and risk):

1. Experiment 4 (Safety First)
   Must pass before other experiments make sense.
   Verifies contract enforcement.

2. Experiment 2 (Boundary)
   Simple, well-defined emergence.
   Validates bisection pattern.

3. Experiment 5 (Stability)
   Validates that emergence is structural.
   Must pass before trusting Experiments 1 and 3.

4. Experiment 1 (Diversity)
   Tests exclusion chain pattern.
   Requires confidence from Exp 4 and 5.

5. Experiment 3 (Shape Transfer)
   Most complex emergence test.
   Requires all prior experiments to pass.

================================================================================
GLOBAL NO-SEMANTICS ENFORCEMENT
================================================================================

Before each experiment execution, verify:

[ ] All targets contain only Section 2 valid constraints
[ ] No constraint references meaning, emotion, intention
[ ] All metrics are computable from mechanical properties
[ ] Pass/fail conditions are numeric thresholds
[ ] No human judgment required for evaluation
[ ] Results are reproducible (determinism verified)

After each experiment execution, verify:

[ ] No "interpretation" statements in analysis
[ ] No "the system learned" language
[ ] No "the system intended" language
[ ] All observations grounded in measured values
[ ] Conclusions follow directly from metrics

================================================================================
HYPOTHESIS EVALUATION
================================================================================

After all experiments complete:

REJECT H₀ (Null Hypothesis) if:
  - Experiment 1: P1.1 AND P1.2 pass (diversity emerges)
  - Experiment 2: P2.1 AND P2.3 pass (boundary emerges)
  - Experiment 3: P3.1 AND P3.2 pass (shape transfers)
  - Experiment 4: All pass conditions met (safety verified)
  - Experiment 5: P5.1 AND P5.2 pass (stability confirmed)

FAIL TO REJECT H₀ if:
  - Any experiment fails primary pass conditions
  - Emergence can be explained by explicit targeting
  - Results depend on derivation policy details

INCONCLUSIVE if:
  - Safety experiments fail (Exp 4)
  - Stability experiments fail (Exp 5)
  - Cannot distinguish emergence from enumeration artifacts

================================================================================
END OF TEST PLAN
================================================================================
