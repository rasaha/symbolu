PHASE-7 MINIMAL TARGET COMPLETENESS CRITERIA
Version: 1.0
Date: 2025-12-18
Type: Specification

================================================================================
PURPOSE
================================================================================

This document defines what makes a target specification "complete enough"
to be useful, beyond merely being valid per the Phase-7 Target Contract.

A target can be syntactically valid yet practically useless. This specification
establishes minimum completeness thresholds that ensure targets provide
meaningful discrimination within the candidate space.

================================================================================
1. DISTINCTION: VALID VS COMPLETE
================================================================================

VALID TARGET
  - Passes all Section 2 whitelist checks
  - Contains no Section 3 forbidden dimensions
  - Has at least one constraint (non-vacuous)
  - Uses finite numeric literals only
  - All fields are recognized

COMPLETE TARGET
  - Is valid (prerequisite)
  - Provides sufficient discrimination (defined below)
  - Has bounded search space (defined below)
  - Is non-trivial (defined below)

A valid target may not be complete.
An invalid target cannot be complete.

================================================================================
2. COMPLETENESS DIMENSIONS
================================================================================

A target is complete if and only if it satisfies ALL of the following:

------------------------------------------------------------------------------
DIMENSION 1: DISCRIMINATION
------------------------------------------------------------------------------

Definition:
  The target must exclude at least some valid sequences from the result set.

Formal Test:
  Let S = set of all valid sequences up to max_sequence_length
  Let T = set of sequences satisfying target constraints
  Target is discriminating iff |T| < |S|

Practical Test:
  At least one constraint must have a bound that is not satisfied by all
  possible Phase-6 outputs.

Examples of NON-DISCRIMINATING (incomplete):
  { "final_magnitude": ">= 1.0" }
    All sequences have magnitude >= 1.0 (baseline)
    Discrimination: 0%

  { "len(steps)": ">= 1" }
    All valid sequences have at least 1 step
    Discrimination: 0%

  { "steps[0].event": "reset" }
    First event is always reset (Phase-6 invariant)
    Discrimination: 0%

Examples of DISCRIMINATING (contributes to completeness):
  { "final_magnitude": ">= 1.3" }
    Excludes single-consonant and low-vowel sequences
    Discrimination: >0%

  { "len(steps)": "== 5" }
    Excludes all sequences not exactly 5 tokens
    Discrimination: >0%

  { "steps[-1].event": "modulate" }
    Excludes sequences ending in consonant
    Discrimination: >0%

------------------------------------------------------------------------------
DIMENSION 2: SEARCH SPACE BOUNDEDNESS
------------------------------------------------------------------------------

Definition:
  The target must define upper bounds that make exhaustive or bounded
  enumeration tractable.

Required Bounds (at least one must be present):
  - len(steps) <= N for some finite N, OR
  - len(steps) == N for some finite N, OR
  - generation_config.max_sequence_length is specified

Rationale:
  Without length bounds, the candidate space is infinite.
  Phase-7 cannot enumerate infinite spaces.

Examples of UNBOUNDED (incomplete):
  { "final_magnitude": ">= 1.5" }
    No length constraint
    Infinite sequences could satisfy this

  { "monotonic_increasing(steps[].magnitude)": true }
    No length constraint
    Arbitrarily long increasing sequences exist

Examples of BOUNDED (contributes to completeness):
  { "final_magnitude": ">= 1.5", "len(steps)": "<= 10" }
    Finite candidate space

  { "len(steps)": "== 7" }
    Explicit length bound

Note: generation_config.max_sequence_length provides implicit bound
even if target has no explicit length constraint.

------------------------------------------------------------------------------
DIMENSION 3: NON-TRIVIALITY
------------------------------------------------------------------------------

Definition:
  The target must not be satisfiable by only the minimal sequence.

Minimal Sequence:
  Single consonant, e.g., ["ka"]
  Produces: { steps: [{ magnitude: 1.0, event: "reset" }], final_magnitude: 1.0 }

Trivial Target:
  Any target satisfied by ["ka"] alone, with no additional discrimination.

Examples of TRIVIAL (incomplete):
  { "final_magnitude": "== 1.0", "len(steps)": "== 1" }
    Only matches minimal sequences
    No exploration of trajectory space

  { "steps[0].magnitude": "== 1.0" }
    All sequences match (first step is always reset to 1.0)
    Trivially satisfied

Examples of NON-TRIVIAL (contributes to completeness):
  { "final_magnitude": "> 1.0" }
    Requires at least one vowel
    Explores vowel modulation

  { "len(steps)": ">= 3" }
    Requires multi-token sequences
    Explores composition

  { "count(steps where event == 'modulate')": ">= 2" }
    Requires multiple vowels
    Explores accumulation

------------------------------------------------------------------------------
DIMENSION 4: CONSTRAINT CONSISTENCY
------------------------------------------------------------------------------

Definition:
  All constraints must be mutually satisfiable by at least one sequence.

Formal Test:
  There exists at least one sequence S such that Phase-6(S) satisfies
  all constraints in the target.

This is distinct from CONTRADICTORY CONSTRAINTS (Section 6 of contract):
  - Contradictory: statically provable no sequence can satisfy
  - Inconsistent: no sequence happens to satisfy, but not provable statically

Examples of INCONSISTENT (incomplete):
  { "final_magnitude": "== 1.73", "len(steps)": "== 3" }
    1.73 may not be exactly reachable with 3 steps
    (depends on vowel delta arithmetic)
    Not contradictory, but may have zero solutions

  { "steps[1].magnitude": "== 1.15", "steps[0].event": "reset" }
    1.15 may not be reachable after one modulation
    (delta values are 0.1, 0.2, 0.15)
    Closest is 1.1, 1.2, or 1.15 (if "u" follows reset)
    This specific example IS reachable: ["ka", "u"] → 1.15
    But { "steps[1].magnitude": "== 1.17" } would be inconsistent

Detection:
  Inconsistency is detected at runtime (empty result set) not statically.
  Phase-7 reports: target_feasible = false

------------------------------------------------------------------------------
DIMENSION 5: RESULT PLURALITY
------------------------------------------------------------------------------

Definition:
  A complete target should (ideally) admit more than one satisfying sequence,
  unless single-solution targeting is explicitly intended.

Rationale:
  Targets with exactly one solution provide no selection benefit.
  Phase-7's value is in ranking multiple candidates.

Soft Requirement:
  This dimension is advisory, not mandatory for completeness.
  Single-solution targets are valid and complete if other dimensions are met.

Examples:
  { "final_magnitude": "== 1.1", "len(steps)": "== 2", "steps[0].event": "reset" }
    May have very few solutions (only C-V sequences with delta 0.1)
    Still complete, but low utility

  { "final_magnitude": ">= 1.2", "final_magnitude": "<= 1.4", "len(steps)": "<= 5" }
    Likely has multiple solutions
    Higher utility for selection

================================================================================
3. COMPLETENESS LEVELS
================================================================================

LEVEL 0: INVALID
  Fails contract validation
  Cannot proceed to generation

LEVEL 1: VALID BUT INCOMPLETE
  Passes contract validation
  Fails one or more completeness dimensions
  May proceed but with warnings

LEVEL 2: MINIMALLY COMPLETE
  Passes contract validation
  Satisfies: Discrimination, Boundedness, Non-Triviality, Consistency
  May have single or few solutions
  Fully functional

LEVEL 3: OPTIMALLY COMPLETE
  Satisfies Level 2
  Additionally: Result Plurality (multiple solutions expected)
  Ideal for selection/ranking use cases

================================================================================
4. COMPLETENESS CHECKLIST
================================================================================

For a target to be MINIMALLY COMPLETE (Level 2):

[ ] DISCRIMINATION
    At least one constraint excludes some valid sequences
    Not all sequences satisfy the target

[ ] BOUNDEDNESS
    Length is bounded explicitly or via generation_config
    Candidate space is finite

[ ] NON-TRIVIALITY
    Target is not satisfiable by minimal single-consonant sequence alone
    OR target explicitly requires minimal sequences

[ ] CONSISTENCY
    Constraints are mutually satisfiable
    At least one solution exists (verified at runtime)

================================================================================
5. COMPLETENESS VALIDATION STAGE
================================================================================

Completeness validation occurs AFTER contract validation, BEFORE generation.

STAGE: VALIDATE_COMPLETENESS
  Input: valid target specification, generation_config
  Output: completeness_level (0, 1, 2, or 3), warnings list

Checks performed:
  1. Discrimination analysis
     - Identify constraints that are always true (Phase-6 invariants)
     - Warn if all constraints are always-true
     - Compute estimated discrimination ratio if tractable

  2. Boundedness analysis
     - Check for explicit length bounds in target
     - Fall back to generation_config.max_sequence_length
     - Error if no bound exists

  3. Non-triviality analysis
     - Simulate minimal sequence ["ka"] against target
     - Warn if minimal sequence satisfies target AND no other constraints
       force longer sequences

  4. Consistency analysis
     - Deferred to runtime (TARGET INFEASIBILITY detection)
     - Pre-generation heuristics may apply for known delta values

  5. Plurality estimation
     - Estimate solution count based on constraint tightness
     - Advisory only

Output:
  completeness_report:
    level: integer (0-3)
    discrimination_ratio: float (0.0 to 1.0, estimated)
    bounded: boolean
    trivial: boolean
    plurality_estimate: "none" | "single" | "few" | "many"
    warnings: List[string]

================================================================================
6. EXAMPLES OF COMPLETE TARGETS
================================================================================

EXAMPLE 1: Magnitude Range Target
{
  "final_magnitude": ">= 1.3",
  "final_magnitude": "<= 1.5",
  "len(steps)": "<= 8"
}
Completeness Level: 3
  - Discriminating: excludes low and high magnitude sequences
  - Bounded: len <= 8
  - Non-trivial: requires vowels to reach 1.3
  - Consistent: 1.3-1.5 is reachable
  - Plurality: many solutions expected

EXAMPLE 2: Trajectory Shape Target
{
  "monotonic_increasing(steps[].magnitude)": true,
  "len(steps)": "== 5",
  "steps[-1].event": "modulate"
}
Completeness Level: 3
  - Discriminating: shape and terminal event constraints
  - Bounded: len == 5
  - Non-trivial: requires specific structure
  - Consistent: C-V-V-V-V is monotonic and ends in modulate
  - Plurality: multiple consonant choices, vowel orderings

EXAMPLE 3: Event Count Target
{
  "count(steps where event == 'reset')": "== 2",
  "count(steps where event == 'modulate')": ">= 3",
  "len(steps)": "<= 7"
}
Completeness Level: 3
  - Discriminating: specific event distribution
  - Bounded: len <= 7
  - Non-trivial: requires multiple tokens
  - Consistent: C-V-V-C-V (5 steps, 2 reset, 3 modulate)
  - Plurality: many valid orderings

EXAMPLE 4: Minimal Complete Target
{
  "final_magnitude": "> 1.0"
}
Completeness Level: 2
  - Discriminating: excludes consonant-only sequences
  - Bounded: via generation_config.max_sequence_length (required)
  - Non-trivial: requires at least one vowel
  - Consistent: any C-V sequence works
  - Plurality: likely many solutions

EXAMPLE 5: Incomplete Target (for contrast)
{
  "steps[0].event": "reset"
}
Completeness Level: 1 (valid but incomplete)
  - NOT Discriminating: all sequences satisfy this (Phase-6 invariant)
  - Bounded: via generation_config only
  - Trivial: ["ka"] satisfies
  Warning: "Constraint 'steps[0].event == reset' is always true"

================================================================================
7. IMPLEMENTATION NOTES
================================================================================

Completeness validation is ADVISORY, not BLOCKING.

Phase-7 will:
  - Always reject Level 0 (invalid) targets
  - Accept Level 1 targets with warnings
  - Accept Level 2 and 3 targets without warnings

Warnings are included in execution metadata, not in error list.

Rationale:
  Users may intentionally specify weak targets for exploration.
  Completeness validation informs but does not restrict.

================================================================================
END OF SPECIFICATION
================================================================================
