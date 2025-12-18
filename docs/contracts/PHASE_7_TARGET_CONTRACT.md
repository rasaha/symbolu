PHASE-7 TARGET CONTRACT
Version: 1.1
Status: FROZEN
Date: 2025-12-18
Revision: Adversarial reinforcements applied

================================================================================
POSITIONING
================================================================================

This Phase-7 (Targeted Generation) operates after Phase-6 and is parallel to
the existing Phase-7 Structural Folding Engine. It does not replace, modify,
or extend the folding engine. It operates strictly on varna sequences and
Phase-6 simulation results.

================================================================================
1. PHASE-7 PURPOSE
================================================================================

Phase-7 receives a mechanical target specification and produces ranked varna
sequences whose Phase-6 simulation results satisfy the target constraints.
It treats generation as exhaustive or bounded search within a validity space,
scoring candidates against measurable criteria derived solely from Phase-6
output fields. Phase-7 does not interpret, infer, learn, or assign meaning.
It is a constraint satisfaction engine operating on deterministic simulation
results.

================================================================================
2. VALID TARGET DIMENSIONS
================================================================================

A valid target is a conjunction of zero or more constraints on Phase-6 output
fields. Each constraint must be testable by direct comparison or arithmetic
on the following fields only:

FINAL MAGNITUDE CONSTRAINTS
  - final_magnitude == <value>
  - final_magnitude >= <lower_bound>
  - final_magnitude <= <upper_bound>
  - final_magnitude in [<lower>, <upper>]

TRAJECTORY SHAPE CONSTRAINTS
  - len(steps) == <n>
  - len(steps) >= <min_length>
  - len(steps) <= <max_length>
  - steps[i].magnitude == <value> for specific index i
  - steps[i].magnitude >= <bound> for specific index i
  - steps[i].magnitude <= <bound> for specific index i
  - monotonic_increasing(steps[].magnitude) == true | false
  - monotonic_decreasing(steps[].magnitude) == true | false
  - count(steps where magnitude > <threshold>) == <n>
  - count(steps where magnitude < <threshold>) == <n>

TRAJECTORY DELTA CONSTRAINTS
  - max(steps[].magnitude) - min(steps[].magnitude) <= <range>
  - max(steps[].magnitude) - min(steps[].magnitude) >= <range>
  - steps[i].magnitude - steps[i-1].magnitude == <delta>

EVENT SEQUENCE CONSTRAINTS
  - steps[i].event == "reset" | "modulate" for specific index i
  - steps[-1].event == "reset" | "modulate" (terminal event)
  - count(steps where event == "reset") == <n>
  - count(steps where event == "modulate") == <n>

COMPOUND CONSTRAINTS
  - Logical AND of any valid constraints above
  - Logical OR of any valid constraints above
  - Negation of any valid constraint above

All constraint values must be numeric literals or boolean literals.
No variables, no expressions referencing external state, no computed values
from outside the TrajectoryResult being evaluated.

NUMERIC LITERAL DEFINITION
  Numeric literals must be finite real numbers.
  The following are explicitly rejected:
    - Infinity, -Infinity
    - NaN (Not a Number)
    - Undefined or null values
  Integer indices must be within bounds:
    - Positive indices: 0 <= i < len(steps)
    - Negative indices: -len(steps) <= i < 0
  Index validity is enforced at scoring time against actual sequence length.

WHITELIST EXCLUSIVITY
  Constraint patterns not explicitly listed above are invalid.
  Structural variations are rejected unless explicitly enumerated.
  Examples of rejected variations:
    - steps[i].magnitude - steps[i-2].magnitude (only i-1 allowed)
    - sum(steps[].magnitude) (sum not in allowed operations)
    - steps[i].velocity (velocity not a TrajectoryStep field)
  Unknown constraint patterns trigger error type INVALID_CONSTRAINT_PATTERN.

EMPTY TARGET PROHIBITION
  Empty target specifications (zero constraints) are rejected.
  At least one constraint is required.
  Rationale: Vacuous targets match all sequences without discrimination,
  defeating the purpose of targeted generation.
  Empty targets trigger error type VACUOUS_TARGET.

================================================================================
3. INVALID TARGET DIMENSIONS
================================================================================

The following target types are explicitly forbidden. Phase-7 must reject any
target specification containing these:

SEMANTIC TARGETS
  - "sequence that means X"
  - "sequence expressing Y"
  - "sequence representing Z"
  - any reference to meaning, semantics, or signification

EMOTIONAL TARGETS
  - "sequence that feels X"
  - "sequence evoking Y"
  - "calming sequence"
  - "energizing sequence"
  - any reference to affect, mood, or emotional state

INTENTIONAL TARGETS
  - "sequence intended for X"
  - "sequence that causes Y"
  - "healing sequence"
  - "protective sequence"
  - any reference to purpose, goal, or effect beyond mechanical output

SYMBOLIC TARGETS
  - "sequence symbolizing X"
  - "sequence associated with Y"
  - any reference to cultural, spiritual, or metaphorical association

INTERPRETIVE TARGETS
  - "beautiful sequence"
  - "optimal sequence" (without mechanical definition of optimal)
  - "good sequence"
  - "appropriate sequence"
  - any evaluative term without mechanical grounding

PROXY SEMANTIC TARGETS
  - targets that encode semantic intent through mechanical constraints
  - example: "final_magnitude == 1.5 because 1.5 represents balance"
  - the constraint itself is valid; the justification is not
  - Phase-7 accepts only the constraint, never the rationale

EXTERNAL REFERENCE TARGETS
  - targets referencing data outside TrajectoryResult
  - targets referencing user state
  - targets referencing time, date, or environmental conditions
  - targets referencing other sequences or prior runs

================================================================================
4. PHASE-7 OPERATIONAL STAGES
================================================================================

Phase-7 executes four sequential stages. Each stage has a single responsibility
and produces output consumed by the next stage.

STAGE 1: GENERATE
  Responsibility: Produce candidate varna sequences from the validity space
  Input: Target specification, generation bounds (max length, max candidates)
  Output: Set of candidate varna sequences
  Constraints:
    - Candidates must be valid per Phase-6 grammar (consonant-initial)
    - Candidates must use only tokens from Phase-4A valid varna set
    - Generation is enumeration or bounded sampling, not inference
    - No candidate is preferred over another at this stage

STAGE 2: SIMULATE
  Responsibility: Execute Phase-6 analysis on each candidate sequence
  Input: Set of candidate varna sequences
  Output: Set of (sequence, TrajectoryResult) pairs
  Constraints:
    - Phase-6 is invoked as black box
    - No modification to Phase-6 behavior
    - Simulation is deterministic: same sequence always yields same result
    - Failed simulations (invalid sequences) are discarded with error record

STAGE 3: SCORE
  Responsibility: Evaluate each TrajectoryResult against target constraints
  Input: Set of (sequence, TrajectoryResult) pairs, target specification
  Output: Set of (sequence, TrajectoryResult, score) triples
  Constraints:
    - Score is binary (satisfies/does-not-satisfy) or numeric distance
    - If binary: 1 = all constraints satisfied, 0 = any constraint violated
    - If numeric: sum of constraint violation magnitudes (0 = perfect)
    - Scoring uses only fields present in TrajectoryResult
    - No weighting by semantic importance
    - No learned scoring functions

STAGE 4: SELECT
  Responsibility: Rank and filter scored candidates
  Input: Set of (sequence, TrajectoryResult, score) triples, selection parameters
  Output: Ordered list of (sequence, TrajectoryResult, score) triples
  Constraints:
    - Ordering is deterministic given same input
    - Ties broken by lexicographic sequence order (deterministic)
    - Selection may filter to top-N or threshold
    - No reranking by external criteria
    - No diversity or novelty bonuses

================================================================================
5. INPUTS AND OUTPUTS
================================================================================

INPUTS

Phase-7 accepts the following inputs:

  target_specification:
    type: TargetSpec
    contents: conjunction/disjunction of valid constraints per Section 2
    required: yes
    unknown_fields: rejected (error type UNKNOWN_TARGET_FIELD)

  UNKNOWN FIELD REJECTION
    Target specifications containing fields not defined in Section 2
    are rejected with error type UNKNOWN_TARGET_FIELD.
    No unknown fields are silently ignored.
    Examples of rejected fields:
      - "comment", "name", "description" (metadata smuggling)
      - "harmony_score", "balance" (semantic camouflage)
      - "ontology_layer", "varga" (Phase-4A leakage)
    All field names must match exactly the constraint patterns in Section 2.

  generation_config:
    type: GenerationConfig
    contents:
      max_sequence_length: positive integer
      max_candidates: positive integer or null (exhaustive)
      vowel_set: subset of Phase-6 supported vowels {a, i, u}
      consonant_set: subset of Phase-4A valid consonants
    required: yes

  selection_config:
    type: SelectionConfig
    contents:
      max_results: positive integer
      score_threshold: numeric (for filtering)
      scoring_mode: "binary" | "distance"
    required: yes

OUTPUTS

Phase-7 produces the following outputs:

  results:
    type: List[RankedResult]
    contents: ordered list where each RankedResult contains:
      sequence: List[str] (varna tokens)
      trajectory: TrajectoryResult (from Phase-6)
      score: float (0.0 = perfect satisfaction for distance mode)
      rank: positive integer (1 = best)
    ordering: by score ascending (distance) or descending (binary)

  metadata:
    type: ExecutionMetadata
    contents:
      candidates_generated: integer
      candidates_simulated: integer
      candidates_satisfying: integer
      execution_deterministic: boolean (always true)
      target_feasible: boolean

  errors:
    type: List[ExecutionError]
    contents: any simulation failures or invalid candidates encountered
    each error contains:
      sequence: the failing sequence
      error_type: enumerated error code
      stage: which stage failed

No interpretation strings appear in any output field.
No natural language descriptions of results.
No semantic labels or categories.

================================================================================
6. FAILURE MODES
================================================================================

Phase-7 can fail in the following mechanically detectable ways:

TARGET INFEASIBILITY
  Definition: No sequence in the candidate space satisfies all constraints
  Detection: candidates_satisfying == 0 after exhaustive generation
  Report: metadata.target_feasible = false
  Output: empty results list, populated metadata

CONTRADICTORY CONSTRAINTS
  Definition: Target constraints are logically impossible
  Examples:
    - final_magnitude > 2.0 AND final_magnitude < 1.0
    - len(steps) == 3 AND len(steps) == 5
  Detection: static analysis of constraint conjunction before generation
  Report: error with type CONTRADICTORY_TARGET
  Output: no generation attempted, immediate error return

  PHASE-6 INVARIANT IMPORT
    Static analysis imports Phase-6 grammar constraints as axioms:
      - First token must be consonant: steps[0].event == "reset" always
      - Vowels require preceding consonant: no "modulate" without prior "reset"
      - Only valid varnas from Phase-4A are allowed in sequences
      - Magnitude baseline is 1.0; vowels only add positive deltas
    Targets contradicting these invariants are CONTRADICTORY.
    Examples:
      - steps[0].event == "modulate" (impossible: first is always reset)
      - final_magnitude < 1.0 (impossible: minimum is baseline 1.0)
      - final_magnitude < 0 (impossible: magnitude never negative)

  INDEX BOUND VALIDATION
    Targets specifying steps[i] where i is statically provable to exceed
    len(steps) constraints are CONTRADICTORY.
    Examples:
      - steps[5].magnitude > 1.0 AND len(steps) <= 3 (index 5 unreachable)
      - steps[10].event == "reset" AND len(steps) == 5 (index 10 unreachable)
    Detection requires cross-constraint analysis of index references
    against length bounds.

GENERATION BOUNDS EXCEEDED
  Definition: Candidate space exceeds max_candidates before completion
  Detection: candidate count reaches limit during enumeration
  Report: metadata indicates partial search
  Output: results from evaluated subset, metadata.candidates_generated = max

SIMULATION FAILURE
  Definition: Phase-6 rejects a candidate sequence
  Examples:
    - vowel-initial sequence
    - invalid varna token
    - unsupported vowel
  Detection: Phase-6 raises error
  Report: error recorded in errors list with sequence and error_type
  Output: candidate excluded from scoring, other candidates continue

INVALID TARGET SPECIFICATION
  Definition: Target contains forbidden dimensions per Section 3
  Detection: target validation before generation
  Report: error with type INVALID_TARGET_DIMENSION
  Output: no generation attempted, immediate error return

UNKNOWN TARGET FIELD
  Definition: Target contains field names not in Section 2 whitelist
  Detection: field name validation before generation
  Report: error with type UNKNOWN_TARGET_FIELD
  Output: no generation attempted, field name included in error

INVALID CONSTRAINT PATTERN
  Definition: Target uses constraint syntax not in Section 2 whitelist
  Detection: pattern matching against allowed constraint forms
  Report: error with type INVALID_CONSTRAINT_PATTERN
  Output: no generation attempted, pattern included in error

VACUOUS TARGET
  Definition: Target specification contains zero constraints
  Detection: constraint count check before generation
  Report: error with type VACUOUS_TARGET
  Output: no generation attempted, immediate error return

INVALID NUMERIC LITERAL
  Definition: Target uses Infinity, NaN, or undefined as constraint value
  Detection: numeric literal validation before generation
  Report: error with type INVALID_NUMERIC_LITERAL
  Output: no generation attempted, value included in error

All failure modes produce deterministic, reproducible error reports.
No failure is silent. No failure produces partial results without indication.

================================================================================
7. NON-GOALS
================================================================================

Phase-7 explicitly does NOT:

  - Learn from previous runs
  - Adapt target interpretation based on results
  - Optimize the ontology or Phase-6 mechanics
  - Infer user intent from target specification
  - Generate sequences outside the validity space
  - Produce natural language explanations
  - Assign meaning to sequences or trajectories
  - Rank by aesthetic, cultural, or spiritual criteria
  - Cache results across invocations (unless explicitly configured)
  - Modify Phase-4A frozen data
  - Modify Phase-6 configuration
  - Communicate with phases other than Phase-6 (for simulation)
  - Predict what targets a user might want
  - Suggest alternative targets
  - Smooth or interpolate between constraint boundaries
  - Handle ambiguous or underspecified targets (reject instead)
  - Provide confidence scores (only satisfaction scores)
  - Implement any form of machine learning
  - Use embeddings, vectors, or learned representations
  - Access external data sources
  - Consider temporal or contextual factors

================================================================================
8. FREEZE CONDITIONS
================================================================================

Phase-7 Target Contract is considered complete and frozen when:

COMPLETENESS CRITERIA
  [ ] All valid target dimensions are enumerated (Section 2)
  [ ] All invalid target dimensions are enumerated (Section 3)
  [ ] All operational stages are defined with responsibilities (Section 4)
  [ ] Input and output schemas are fully specified (Section 5)
  [ ] All failure modes are enumerated with detection methods (Section 6)
  [ ] All non-goals are explicitly stated (Section 7)

CONSISTENCY CRITERIA
  [ ] No target dimension references fields outside TrajectoryResult
  [ ] No operational stage requires semantic interpretation
  [ ] No output field contains natural language beyond error codes
  [ ] No failure mode is silent or ambiguous
  [ ] All numeric operations are deterministic

VERIFICATION CRITERIA
  [ ] Contract reviewed for semantic leakage (none found)
  [ ] Contract reviewed for forward assumptions about Phase-8 (none found)
  [ ] Contract reviewed for backward modifications to Phase-6 (none found)
  [ ] Contract reviewed for ontology access outside Phase-4A API (none found)

STABILITY CRITERIA
  [ ] No open questions remain in contract text
  [ ] No "TBD" or "TODO" markers present
  [ ] All constraint examples use only valid syntax
  [ ] All error types are enumerated, not open-ended

Once all criteria are satisfied, this contract is FROZEN.
Modifications require a new version number and explicit justification.
Frozen contracts are append-only: new versions do not delete prior guarantees.

================================================================================
END OF CONTRACT
================================================================================
