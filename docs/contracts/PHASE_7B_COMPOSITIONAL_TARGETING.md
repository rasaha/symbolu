PHASE-7B COMPOSITIONAL TARGETING CONTRACT
Version: 1.0
Status: DRAFT
Date: 2025-12-18
Type: Specification (No Code)

================================================================================
PURPOSE
================================================================================

This document specifies how Phase-7 outputs can constrain subsequent Phase-7
executions, enabling compositional targeting without introducing interpretation,
learning, or semantic content.

Phase-7B is not a new phase. It is a usage pattern for Phase-7 that enables
iteration while preserving mechanical purity.

================================================================================
1. COMPOSITIONAL TARGETING DEFINITION
================================================================================

Compositional targeting is the practice of:
  1. Executing Phase-7 with target T1
  2. Deriving target T2 from Phase-7 results R1
  3. Executing Phase-7 with target T2
  4. Repeating as needed

The key constraint is:
  T2 must be derivable from R1 using only mechanical operations.
  No interpretation of R1 is permitted.
  No learning from R1 is permitted.

================================================================================
2. WHAT PHASE-7 PRODUCES (Review)
================================================================================

Phase-7 output (Phase7Result) contains:

  results: List[RankedResult]
    Each RankedResult contains:
      sequence: tuple of varna tokens
      trajectory: TrajectoryResult
        final_magnitude: float
        steps: List[TrajectoryStep]
          magnitude: float
          event: "reset" | "modulate"
      score: float
      rank: int

  metadata: ExecutionMetadata
    candidates_generated: int
    candidates_simulated: int
    candidates_satisfying: int
    target_feasible: bool

  completeness: CompletenessReport
    level: int (0-3)
    discrimination_ratio: float

All fields are mechanical and measurable.

================================================================================
3. VALID COMPOSITIONAL OPERATIONS
================================================================================

The following operations on Phase-7 results are VALID for deriving new targets:

------------------------------------------------------------------------------
3.1 RESULT FIELD EXTRACTION
------------------------------------------------------------------------------

Extract numeric values from results to use as constraint bounds.

Examples:
  - Use top result's final_magnitude as new target bound
  - Use median magnitude across results as threshold
  - Use result count as length constraint

Valid:
  R1 = execute_phase7(T1)
  best_magnitude = R1.results[0].trajectory.final_magnitude
  T2 = { "final_magnitude": f">= {best_magnitude}" }

Invalid:
  T2 = { "meaning": interpret(R1.results[0].sequence) }  # interpretation

------------------------------------------------------------------------------
3.2 SEQUENCE SET OPERATIONS
------------------------------------------------------------------------------

Use result sequences to constrain candidate space.

Examples:
  - Exclude sequences that appeared in R1
  - Include only sequences sharing prefix with R1 top result
  - Constrain to sequences longer than R1 results

Valid Constraints (new to compositional targeting):
  - sequence NOT IN {seq1, seq2, ...}  (exclusion)
  - sequence STARTS_WITH prefix       (prefix constraint)
  - sequence ENDS_WITH suffix         (suffix constraint)
  - len(sequence) > len(prior_result.sequence)  (length comparison)

These are MECHANICAL operations on token sequences, not interpretations.

------------------------------------------------------------------------------
3.3 TRAJECTORY SHAPE TRANSFER
------------------------------------------------------------------------------

Use trajectory shape from R1 to constrain R2.

Examples:
  - Require R2 trajectories to be monotonic if R1 best was monotonic
  - Require R2 final magnitude to exceed R1 best final magnitude
  - Require R2 to have more modulation events than R1 best

Valid:
  R1 = execute_phase7(T1)
  r1_best = R1.results[0]
  r1_modulate_count = count(r1_best.trajectory.steps where event == "modulate")
  T2 = { "count(steps where event == 'modulate')": f"> {r1_modulate_count}" }

------------------------------------------------------------------------------
3.4 METADATA-DRIVEN CONSTRAINTS
------------------------------------------------------------------------------

Use execution metadata to adjust subsequent targets.

Examples:
  - If discrimination_ratio < 0.5, tighten constraints
  - If candidates_satisfying == 0, relax constraints
  - If candidates_satisfying > 1000, add constraints

Valid:
  R1 = execute_phase7(T1)
  if R1.metadata.candidates_satisfying > 100:
      T2 = T1 + { "len(steps)": "<= 5" }  # add constraint
  else:
      T2 = T1  # keep same

------------------------------------------------------------------------------
3.5 STATISTICAL AGGREGATION
------------------------------------------------------------------------------

Compute statistics over result set to derive constraints.

Permitted aggregations:
  - min, max, mean, median over numeric fields
  - count of results satisfying sub-condition
  - standard deviation (for spread constraints)

Valid:
  R1 = execute_phase7(T1)
  magnitudes = [r.trajectory.final_magnitude for r in R1.results]
  median_mag = median(magnitudes)
  T2 = { "final_magnitude": f">= {median_mag}" }

Invalid:
  T2 = { "quality": rate_quality(R1.results) }  # interpretation

================================================================================
4. INVALID COMPOSITIONAL OPERATIONS
================================================================================

The following operations are FORBIDDEN in compositional targeting:

------------------------------------------------------------------------------
4.1 SEMANTIC INTERPRETATION
------------------------------------------------------------------------------

Forbidden:
  - Assigning meaning to sequences
  - Rating sequences by "quality", "beauty", "appropriateness"
  - Clustering sequences by "similarity" (unless purely edit-distance)
  - Naming or labeling result groups

Examples of violations:
  T2 = { "type": "calming" }  # interpreted from R1
  T2 = { "like": best_sequence }  # similarity is semantic
  T2 = select_target_based_on(user_preference)  # external interpretation

------------------------------------------------------------------------------
4.2 LEARNING FROM RESULTS
------------------------------------------------------------------------------

Forbidden:
  - Training models on R1 to predict good sequences
  - Updating weights or parameters based on R1
  - Building embeddings from result sequences
  - Any operation that "improves" with more data

Examples of violations:
  model.train(R1.results)
  T2 = model.predict_good_target()

------------------------------------------------------------------------------
4.3 EXTERNAL STATE INJECTION
------------------------------------------------------------------------------

Forbidden:
  - Using user feedback to modify T2
  - Using time/date to modify T2
  - Using environmental conditions
  - Referencing results from different sessions

Examples of violations:
  T2 = adjust_for_user(R1, user_profile)
  T2 = adjust_for_time_of_day(R1)

------------------------------------------------------------------------------
4.4 SEQUENCE INTERPRETATION
------------------------------------------------------------------------------

Forbidden:
  - Parsing sequences for "patterns" beyond mechanical structure
  - Identifying "motifs" with assigned meaning
  - Correlating sequences with external ontologies

Examples of violations:
  motif = find_sacred_pattern(R1.results[0].sequence)
  T2 = { "contains_motif": motif }

================================================================================
5. COMPOSITIONAL PATTERNS
================================================================================

The following are canonical compositional patterns:

------------------------------------------------------------------------------
PATTERN 1: PROGRESSIVE REFINEMENT
------------------------------------------------------------------------------

Start broad, progressively narrow based on results.

Iteration 0:
  T0 = { "final_magnitude": "> 1.0" }  # broad
  R0 = execute_phase7(T0)

Iteration 1:
  best_mag = R0.results[0].trajectory.final_magnitude
  T1 = { "final_magnitude": f">= {best_mag * 0.9}" }  # narrower
  R1 = execute_phase7(T1)

Iteration N:
  Continue until candidates_satisfying stabilizes

Termination:
  - candidates_satisfying < threshold
  - discrimination_ratio > threshold
  - max iterations reached

------------------------------------------------------------------------------
PATTERN 2: EXCLUSION CHAINS
------------------------------------------------------------------------------

Repeatedly exclude found sequences to explore diversity.

Iteration 0:
  T0 = { "len(steps)": "== 5" }
  R0 = execute_phase7(T0)
  found = set(R0.results[0:10].sequences)

Iteration 1:
  T1 = T0 + { "sequence NOT IN": found }
  R1 = execute_phase7(T1)
  found = found.union(R1.results[0:10].sequences)

Iteration N:
  Continue until no new sequences found

Result:
  Diverse set of sequences satisfying base constraint

------------------------------------------------------------------------------
PATTERN 3: THRESHOLD ESCALATION
------------------------------------------------------------------------------

Progressively increase target difficulty.

Iteration 0:
  T0 = { "final_magnitude": ">= 1.1" }
  R0 = execute_phase7(T0)

Iteration 1:
  if R0.metadata.candidates_satisfying > 0:
      T1 = { "final_magnitude": ">= 1.2" }
  else:
      STOP  # threshold unreachable
  R1 = execute_phase7(T1)

Iteration N:
  Increment threshold until infeasibility

Result:
  Maximum achievable magnitude discovered

------------------------------------------------------------------------------
PATTERN 4: SHAPE TRANSFER
------------------------------------------------------------------------------

Find sequences matching trajectory shape of prior result.

Iteration 0:
  T0 = { "final_magnitude": ">= 1.5", "len(steps)": "<= 6" }
  R0 = execute_phase7(T0)
  best = R0.results[0]

Iteration 1:
  # Transfer shape constraints
  T1 = {
    "monotonic_increasing(steps[].magnitude)": is_monotonic(best),
    "steps[-1].event": best.trajectory.steps[-1].event,
    "len(steps)": f"== {len(best.trajectory.steps)}",
    "final_magnitude": f">= {best.trajectory.final_magnitude}"
  }
  R1 = execute_phase7(T1)

Result:
  Sequences with same shape as best prior result

------------------------------------------------------------------------------
PATTERN 5: BISECTION SEARCH
------------------------------------------------------------------------------

Binary search for boundary conditions.

low = 1.0
high = 2.0
precision = 0.01

while high - low > precision:
  mid = (low + high) / 2
  T = { "final_magnitude": f">= {mid}" }
  R = execute_phase7(T)

  if R.metadata.candidates_satisfying > 0:
      low = mid  # feasible, try higher
  else:
      high = mid  # infeasible, try lower

Result:
  Maximum feasible magnitude (within precision)

================================================================================
6. COMPOSITIONAL INVARIANTS
================================================================================

The following invariants MUST hold across all compositional patterns:

INVARIANT C1: NO SEMANTIC ACCUMULATION
  Information accumulated across iterations is purely mechanical.
  No iteration adds semantic content to the process.
  Test: All derived constraints pass Section 2 validation.

INVARIANT C2: DETERMINISTIC COMPOSITION
  Given same T0 and same composition function, all iterations produce
  identical results.
  Test: Run composition twice, compare all intermediate results.

INVARIANT C3: NO LEARNING
  Composition function does not change based on accumulated results.
  The rule for T(n) → T(n+1) is fixed before execution.
  Test: Composition function is pure and stateless.

INVARIANT C4: BOUNDED ITERATION
  All compositional patterns must have termination conditions.
  Unbounded iteration is forbidden.
  Test: max_iterations is always specified.

INVARIANT C5: RESULT INDEPENDENCE
  Each Phase-7 execution is independent.
  No hidden state carries between executions.
  Test: Interleave different compositions, verify no interference.

INVARIANT C6: REVERSIBILITY
  Given any T(n), the derivation from T(0) through T(n-1) is recoverable.
  Full audit trail of constraint evolution.
  Test: Log all intermediate targets and results.

================================================================================
7. EMERGENCE DEFINITION
================================================================================

Emergence in compositional targeting is defined as:

  A property P is EMERGENT if:
    1. P is not present in any single Phase-7 execution
    2. P appears only through composition of multiple executions
    3. P is mechanically measurable
    4. P is not explicitly targeted

Examples of emergent properties:

EMERGENT: Sequence Diversity
  Single execution may cluster around similar sequences.
  Exclusion chain pattern produces diverse set.
  Diversity is measurable (edit distance distribution).
  Diversity was not a constraint, but emerged from exclusion.

EMERGENT: Boundary Discovery
  Single execution finds sequences satisfying constraint.
  Bisection pattern discovers feasibility boundary.
  Boundary is a property of the validity space, not targeted directly.

EMERGENT: Shape Families
  Shape transfer across iterations reveals "natural" trajectory shapes.
  Shapes that persist across many sequences are emergent structure.
  Not targeted, discovered through iteration.

NOT EMERGENT (counter-examples):
  - Finding highest magnitude (directly targeted)
  - Finding shortest sequence (directly targeted)
  - Any property explicitly constrained

================================================================================
8. COMPOSITION EXECUTOR SPECIFICATION
================================================================================

A compositional executor wraps Phase-7 and manages iteration.

INPUTS:
  initial_target: TargetSpec
  composition_function: (TargetSpec, Phase7Result) -> TargetSpec
  termination_condition: (Phase7Result, int) -> bool
  max_iterations: int
  generation_config: GenerationConfig
  selection_config: SelectionConfig

OUTPUTS:
  iterations: List[CompositionIteration]
    Each iteration contains:
      iteration_number: int
      target: TargetSpec
      result: Phase7Result
      derived_constraints: List[Constraint]  # what was added/modified

  final_result: Phase7Result  # last iteration's result
  emergent_properties: List[EmergentProperty]  # detected emergence
  audit_trail: CompositionAuditTrail

EXECUTION:
  iteration = 0
  target = initial_target
  results = []

  while iteration < max_iterations:
      result = execute_phase7(target, generation_config, selection_config)
      results.append((iteration, target, result))

      if termination_condition(result, iteration):
          break

      target = composition_function(target, result)
      iteration += 1

  return CompositionResult(results, detect_emergence(results))

================================================================================
9. COMPOSITIONAL TARGETING CONSTRAINTS
================================================================================

NEW CONSTRAINT TYPES (valid only in compositional context):

SEQUENCE EXCLUSION
  Syntax: sequence NOT IN {<seq1>, <seq2>, ...}
  Semantics: Exclude specific sequences from candidates
  Derivation: From prior Phase-7 result sequences

SEQUENCE PREFIX
  Syntax: sequence STARTS_WITH <prefix>
  Semantics: Candidate must begin with given tokens
  Derivation: From prior result sequence prefix

SEQUENCE SUFFIX
  Syntax: sequence ENDS_WITH <suffix>
  Semantics: Candidate must end with given tokens
  Derivation: From prior result sequence suffix

RELATIVE LENGTH
  Syntax: len(sequence) > len(<prior_sequence>)
  Semantics: Candidate must be longer than reference
  Derivation: From prior result sequence

These constraints are ONLY valid when:
  1. Derived from prior Phase-7 result in same composition chain
  2. Prior result is mechanically referenced (not interpreted)
  3. Constraint passes standard validation

================================================================================
10. NON-GOALS OF COMPOSITIONAL TARGETING
================================================================================

Compositional targeting does NOT:
  - Learn optimal targets from results
  - Build models of the validity space
  - Predict which targets will succeed
  - Optimize for any semantic property
  - Adapt to user preferences
  - Remember results across sessions
  - Generalize from specific results
  - Identify "meaning" in patterns
  - Evolve targets through selection pressure
  - Implement genetic algorithms
  - Use gradient-based optimization
  - Build embeddings of sequences

================================================================================
11. VERIFICATION CRITERIA
================================================================================

A compositional targeting implementation is correct if:

[ ] All derived targets pass Phase-7 validation
[ ] Composition function is pure (deterministic, no side effects)
[ ] Termination condition guarantees finite iterations
[ ] All intermediate results are logged
[ ] Emergent properties are mechanically defined
[ ] No semantic content appears in any constraint
[ ] Invariants C1-C6 are satisfied
[ ] Same input produces identical composition trace

================================================================================
12. RELATIONSHIP TO INTELLIGENCE
================================================================================

Compositional targeting explores the hypothesis:

  "Intelligence is constraint satisfaction iterated over a validity space,
   where iteration is guided by mechanical properties of prior results,
   not by interpretation or learning."

If emergent properties appear through composition that:
  - Were not explicitly targeted
  - Are mechanically measurable
  - Exhibit structure beyond random search
  - Arise from validity space geometry

Then compositional targeting demonstrates a form of "mechanical intelligence"
that requires no semantics, no learning, and no interpretation.

This is the hypothesis to test.

================================================================================
END OF CONTRACT
================================================================================
