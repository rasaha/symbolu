PHASE-8D FORMAL ANALYSIS CONTRACT
Version: 1.0
Status: DRAFT
Date: 2025-12-18

================================================================================
POSITIONING
================================================================================

Phase-8D (Formal Analysis Layer) operates alongside Phase-7 and Phase-8A as an
analytical counterpart. It answers questions about validity spaces WITHOUT
generating sequences. Phase-8D reasons ABOUT Phase-6 mechanics; it does not
RUN them.

Phase relationships:
  Phase-4A → Phase-6 → Phase-7 → Phase-8A
  (ontology)  (compose) (target)  (render)
                  ↑
              Phase-8D (analyzes)

Phase-8D receives:
  - Ontology definition (token sets from Phase-4A)
  - Composition axioms (Phase-6 rules, encoded as logical constraints)
  - Target specifications (Phase-7 constraint format)

Phase-8D produces:
  - Analytical answers about what is possible, necessary, or bounded
  - Proofs or witnesses where applicable
  - Uncertainty bounds where exact answers are infeasible

Phase-8D is NOT:
  - A generator (Phase-7 generates)
  - A simulator (Phase-6 simulates)
  - A renderer (Phase-8A renders)

================================================================================
1. PHASE-8D PURPOSE
================================================================================

Phase-8D provides formal analysis of validity spaces. It answers structural
questions without enumeration:

  "Is this target satisfiable?"        → Reachability analysis
  "What are the bounds on magnitude?"  → Extremal analysis
  "How many sequences satisfy this?"   → Cardinality analysis
  "What must be true for all cases?"   → Invariant derivation
  "Are these constraints equivalent?"  → Equivalence checking

Core principle: ANALYSIS BEFORE ENUMERATION

Phase-8D uses deductive reasoning from Phase-6 axioms. Enumeration is permitted
ONLY as proof-witness after an analytical claim, never as the primary method.

This enables:
  - Feasibility checking before Phase-7 generation (avoid wasted computation)
  - Bounds derivation for constraint design
  - Formal verification of validity space properties
  - Static detection of contradictory or vacuous targets

================================================================================
2. PHASE-6 AXIOM ENCODING
================================================================================

Phase-8D reasons about Phase-6 mechanics via axioms. These axioms are ASSUMED
true; Phase-8D does not verify them (that is Phase-6's responsibility).

GRAMMAR AXIOMS (G1-G4)

  G1: CONSONANT-INITIAL
    Every valid sequence begins with a consonant.
    Formally: steps[0].event == "reset"

  G2: VOWEL-REQUIRES-CONSONANT
    A modulate event cannot occur without a preceding reset event.
    Formally: ∀i, steps[i].event == "modulate" → ∃j < i, steps[j].event == "reset"

  G3: VALID-TOKEN-SET
    Consonants must be from Phase-4A varna set: {ka, ga, ta, da, pa, ba}
    Vowels must be from Phase-6 vowel set: {a, i, u}

  G4: LENGTH-BOUNDS
    len(sequence) >= 1 (non-empty)
    len(steps) == len(sequence) (one step per token)

MAGNITUDE AXIOMS (M1-M5)

  M1: BASELINE
    Magnitude baseline is 1.0.
    After any reset event: magnitude == 1.0

  M2: VOWEL-DELTAS
    Vowel modulation is additive with fixed deltas:
      delta("a") == 0.1
      delta("i") == 0.2
      delta("u") == 0.15

  M3: MINIMUM-MAGNITUDE
    Magnitude never falls below baseline.
    Formally: ∀i, steps[i].magnitude >= 1.0
    Corollary: final_magnitude >= 1.0

  M4: CONSONANT-ONLY-BASELINE
    A sequence with only consonants has final_magnitude == 1.0.
    Formally: (∀t ∈ sequence, t ∈ CONSONANTS) → final_magnitude == 1.0

  M5: MAGNITUDE-ACCUMULATION
    Magnitude at step i equals:
      If steps[i].event == "reset": 1.0
      If steps[i].event == "modulate": steps[i-1].magnitude + delta(token)

DETERMINISM AXIOM (D1)

  D1: PURE-FUNCTION
    Phase-6 composition is a pure function.
    Same sequence always yields identical trajectory.
    No randomness, no external state.

DERIVED BOUNDS (from axioms)

  From M2, M3, M5:
    Maximum magnitude for n vowels after last reset:
      max_magnitude(n) == 1.0 + n * max(delta) == 1.0 + 0.2n

    Minimum magnitude for n vowels after last reset:
      min_magnitude(n) == 1.0 + n * min(delta) == 1.0 + 0.1n

  From G1, G3:
    Minimum sequence length: 1 (single consonant)
    Maximum steps with k consonants: unbounded (vowels between consonants)

================================================================================
3. QUERY TYPES
================================================================================

Phase-8D supports the following query types:

REACHABILITY QUERIES (R)

  R1: TARGET-SATISFIABILITY
    Query: "Can any sequence satisfy these constraints?"
    Input: TargetSpec (Phase-7 format)
    Output: SATISFIABLE | UNSATISFIABLE | UNKNOWN
    Method: Constraint propagation, axiom checking, SMT encoding

  R2: CONFIGURATION-REACHABILITY
    Query: "Can magnitude M be achieved with length L?"
    Input: (target_magnitude: float, target_length: int)
    Output: REACHABLE | UNREACHABLE | UNKNOWN
    Method: Closed-form bounds from M2, M5

  R3: EVENT-PATTERN-REACHABILITY
    Query: "Can event pattern P occur?"
    Input: EventPattern (e.g., "reset, modulate, modulate, reset")
    Output: REACHABLE | UNREACHABLE | UNKNOWN
    Method: Grammar axiom checking (G1, G2)

BOUNDS QUERIES (B)

  B1: MAGNITUDE-BOUNDS
    Query: "What is the min/max final_magnitude for sequences of length L?"
    Input: (length: int, additional_constraints: Optional[TargetSpec])
    Output: (lower_bound: float, upper_bound: float, exact: bool)
    Method: Closed-form derivation from M1-M5

  B2: LENGTH-BOUNDS
    Query: "What sequence lengths can achieve magnitude M?"
    Input: (target_magnitude: float, tolerance: float)
    Output: (min_length: int, max_length: Optional[int])
    Method: Inverse of magnitude accumulation formula

  B3: STEP-COUNT-BOUNDS
    Query: "How many reset/modulate events can occur in length L?"
    Input: (length: int, event_type: "reset" | "modulate")
    Output: (min_count: int, max_count: int)
    Method: Combinatorial analysis with G1, G2

CARDINALITY QUERIES (C)

  C1: EXACT-COUNT
    Query: "How many sequences satisfy these constraints?"
    Input: TargetSpec, GenerationBounds
    Output: count: int | OVERFLOW
    Method: Combinatorial counting, generating functions
    Constraint: Only for small, bounded spaces

  C2: BOUNDED-ESTIMATE
    Query: "Approximately how many sequences satisfy constraints?"
    Input: TargetSpec, GenerationBounds
    Output: (lower_bound: int, upper_bound: int, confidence: float)
    Method: Sampling-free estimation from structure

  C3: RELATIVE-DENSITY
    Query: "What fraction of length-L sequences satisfy constraints?"
    Input: TargetSpec, length: int
    Output: (density: float, exact: bool)
    Method: Ratio of constrained to unconstrained space

INVARIANT QUERIES (I)

  I1: UNIVERSAL-PROPERTY
    Query: "Does property P hold for ALL satisfying sequences?"
    Input: TargetSpec, PropertySpec
    Output: HOLDS | VIOLATED | UNKNOWN
    Method: Proof search, counterexample search

  I2: EXISTENTIAL-PROPERTY
    Query: "Does property P hold for SOME satisfying sequence?"
    Input: TargetSpec, PropertySpec
    Output: EXISTS | NOT_EXISTS | UNKNOWN
    Method: Witness search (analytical first, enumeration as fallback)

  I3: DERIVED-CONSTRAINTS
    Query: "What constraints are implied by these constraints?"
    Input: TargetSpec
    Output: ImpliedConstraints (additional constraints that must hold)
    Method: Constraint propagation, axiom application

EQUIVALENCE QUERIES (E)

  E1: CONSTRAINT-EQUIVALENCE
    Query: "Do constraint sets A and B define the same validity space?"
    Input: (spec_a: TargetSpec, spec_b: TargetSpec)
    Output: EQUIVALENT | NOT_EQUIVALENT | UNKNOWN
    Method: Bidirectional implication check

  E2: CONSTRAINT-SUBSUMPTION
    Query: "Does constraint set A subsume B (A ⊆ B)?"
    Input: (spec_a: TargetSpec, spec_b: TargetSpec)
    Output: SUBSUMES | NOT_SUBSUMES | UNKNOWN
    Method: Unidirectional implication check

  E3: CONSTRAINT-DISJOINTNESS
    Query: "Are constraint sets A and B mutually exclusive?"
    Input: (spec_a: TargetSpec, spec_b: TargetSpec)
    Output: DISJOINT | OVERLAPPING | UNKNOWN
    Method: Intersection satisfiability check

COVERAGE QUERIES (V)

  V1: TOKEN-COVERAGE
    Query: "Which tokens appear in at least one satisfying sequence?"
    Input: TargetSpec
    Output: FrozenSet[str] (tokens that are reachable)
    Method: Per-token reachability analysis

  V2: TOKEN-NECESSITY
    Query: "Which tokens appear in ALL satisfying sequences?"
    Input: TargetSpec
    Output: FrozenSet[str] (tokens that are necessary)
    Method: Per-token necessity proof

  V3: PATTERN-COVERAGE
    Query: "Which subsequence patterns are reachable?"
    Input: TargetSpec, pattern_length: int
    Output: FrozenSet[Tuple[str, ...]] (reachable patterns)
    Method: Pattern-wise reachability

================================================================================
4. INPUT SCHEMA
================================================================================

All queries accept inputs through the AnalysisQuery structure:

ANALYSIS QUERY STRUCTURE

  AnalysisQuery:
    type: frozen dataclass
    fields:
      query_type: QueryType                    # Enum: R1, R2, ..., V3
      target_spec: Optional[TargetSpec]        # Phase-7 constraint format
      parameters: QueryParameters              # Query-specific parameters
      bounds: Optional[AnalysisBounds]         # Limits for analysis
      options: AnalysisOptions                 # Analysis configuration

  QueryType (enum):
    # Reachability
    TARGET_SATISFIABILITY        # R1
    CONFIGURATION_REACHABILITY   # R2
    EVENT_PATTERN_REACHABILITY   # R3
    # Bounds
    MAGNITUDE_BOUNDS             # B1
    LENGTH_BOUNDS                # B2
    STEP_COUNT_BOUNDS            # B3
    # Cardinality
    EXACT_COUNT                  # C1
    BOUNDED_ESTIMATE             # C2
    RELATIVE_DENSITY             # C3
    # Invariants
    UNIVERSAL_PROPERTY           # I1
    EXISTENTIAL_PROPERTY         # I2
    DERIVED_CONSTRAINTS          # I3
    # Equivalence
    CONSTRAINT_EQUIVALENCE       # E1
    CONSTRAINT_SUBSUMPTION       # E2
    CONSTRAINT_DISJOINTNESS      # E3
    # Coverage
    TOKEN_COVERAGE               # V1
    TOKEN_NECESSITY              # V2
    PATTERN_COVERAGE             # V3

  QueryParameters (union by query type):
    ReachabilityParams | BoundsParams | CardinalityParams |
    InvariantParams | EquivalenceParams | CoverageParams

  AnalysisBounds:
    type: frozen dataclass
    fields:
      max_length: int                  # Maximum sequence length to consider
      max_computation_steps: int       # Limit on analytical steps
      timeout_ms: Optional[int]        # Wall-clock timeout

  AnalysisOptions:
    type: frozen dataclass
    fields:
      require_witness: bool            # Must provide example if EXISTS
      require_proof: bool              # Must provide proof trace if HOLDS
      allow_enumeration_fallback: bool # Permit enumeration as last resort
      enumeration_limit: int           # Max sequences to enumerate if fallback

TARGET SPEC (from Phase-7)

  TargetSpec:
    type: frozen dataclass
    fields:
      constraints: FrozenSet[Constraint]

  Phase-8D accepts the same TargetSpec format as Phase-7.
  This enables direct analysis of Phase-7 targets.

PROPERTY SPEC (for invariant queries)

  PropertySpec:
    type: frozen dataclass
    fields:
      property_type: PropertyType
      parameters: PropertyParameters

  PropertyType (enum):
    MAGNITUDE_IN_RANGE           # final_magnitude in [a, b]
    LENGTH_EQUALS                # len(sequence) == n
    CONTAINS_TOKEN               # token t appears in sequence
    EVENT_COUNT_EQUALS           # count(event) == n
    STARTS_WITH                  # sequence starts with pattern
    ENDS_WITH                    # sequence ends with pattern
    MONOTONIC_MAGNITUDE          # magnitude is monotonic
    CUSTOM_PREDICATE             # User-defined predicate (restricted)

================================================================================
5. OUTPUT SCHEMA
================================================================================

All queries produce outputs through the AnalysisResult structure:

ANALYSIS RESULT STRUCTURE

  AnalysisResult:
    type: frozen dataclass
    fields:
      query_type: QueryType              # Echo of input query type
      query_hash: str                    # Deterministic hash of query
      verdict: Verdict                   # Primary answer
      evidence: Optional[Evidence]       # Supporting evidence
      bounds: Optional[ResultBounds]     # Numeric bounds if applicable
      metadata: AnalysisMetadata         # Execution metadata
      error: Optional[AnalysisError]     # Error if analysis failed

  Verdict (enum):
    # For reachability/satisfiability
    SATISFIABLE                  # At least one sequence exists
    UNSATISFIABLE                # Proven no sequence exists
    # For properties
    HOLDS                        # Property true for all/some (as queried)
    VIOLATED                     # Property false
    # For equivalence
    EQUIVALENT                   # Same validity space
    NOT_EQUIVALENT               # Different validity spaces
    SUBSUMES                     # A ⊆ B
    NOT_SUBSUMES                 # A ⊄ B
    DISJOINT                     # A ∩ B = ∅
    OVERLAPPING                  # A ∩ B ≠ ∅
    # For existence
    EXISTS                       # Witness found
    NOT_EXISTS                   # Proven none exists
    # Uncertainty
    UNKNOWN                      # Could not determine
    TIMEOUT                      # Analysis exceeded limits

EVIDENCE STRUCTURE

  Evidence:
    type: frozen dataclass
    fields:
      evidence_type: EvidenceType
      content: EvidenceContent

  EvidenceType (enum):
    WITNESS                      # Example sequence satisfying claim
    COUNTEREXAMPLE               # Example sequence violating claim
    PROOF_TRACE                  # Deductive proof steps
    BOUND_DERIVATION             # How bounds were computed
    NONE                         # No evidence (for UNKNOWN verdicts)

  WitnessEvidence:
    type: frozen dataclass
    fields:
      sequence: Tuple[str, ...]          # Example sequence
      trajectory_summary: TrajectorySummary  # Summary (NOT full simulation)

  CounterexampleEvidence:
    type: frozen dataclass
    fields:
      sequence: Tuple[str, ...]          # Counterexample sequence
      violation: str                     # Which property/constraint violated

  ProofTrace:
    type: frozen dataclass
    fields:
      steps: Tuple[ProofStep, ...]       # Deductive steps
      axioms_used: FrozenSet[str]        # Which axioms were applied

  ProofStep:
    type: frozen dataclass
    fields:
      step_number: int
      statement: str                     # Logical statement
      justification: str                 # Axiom or prior step reference

RESULT BOUNDS (for numeric queries)

  ResultBounds:
    type: frozen dataclass
    fields:
      lower: Optional[float]             # Lower bound (None if unbounded)
      upper: Optional[float]             # Upper bound (None if unbounded)
      exact: bool                        # True if bounds are tight
      count: Optional[int]               # For cardinality queries

ANALYSIS METADATA

  AnalysisMetadata:
    type: frozen dataclass
    fields:
      computation_steps: int             # Analytical steps taken
      enumeration_count: int             # Sequences enumerated (should be 0 ideally)
      method_used: AnalysisMethod        # Which method produced result
      confidence: float                  # 1.0 for proven, <1.0 for estimates
      deterministic: bool                # Always True

  AnalysisMethod (enum):
    AXIOMATIC_DEDUCTION          # Pure axiom application
    CONSTRAINT_PROPAGATION       # Constraint solving
    CLOSED_FORM_DERIVATION       # Mathematical formula
    SMT_SOLVING                  # SAT/SMT solver
    COMBINATORIAL_COUNTING       # Counting argument
    ENUMERATION_WITNESS          # Enumeration as proof-witness only
    ENUMERATION_FALLBACK         # Enumeration as primary (flagged)

================================================================================
6. SOUNDNESS GUARANTEES
================================================================================

Phase-8D provides the following soundness guarantees:

ABSOLUTE SOUNDNESS (S1-S4)

  S1: NO-FALSE-UNSATISFIABLE
    If verdict is UNSATISFIABLE, no satisfying sequence exists.
    Phase-8D will NEVER claim unreachability when a sequence exists.
    Formally: verdict == UNSATISFIABLE → ∀s, ¬satisfies(s, constraints)

  S2: NO-FALSE-HOLDS
    If verdict is HOLDS for universal property, property holds for all.
    Formally: verdict == HOLDS (I1) → ∀s ∈ validity_space, property(s)

  S3: NO-FALSE-NOT-EXISTS
    If verdict is NOT_EXISTS, no witness exists.
    Formally: verdict == NOT_EXISTS → ∀s, ¬(satisfies(s, constraints) ∧ property(s))

  S4: WITNESS-VALIDITY
    If evidence contains a witness, the witness satisfies the claim.
    Formally: evidence.type == WITNESS → satisfies(evidence.sequence, constraints)

CONDITIONAL SOUNDNESS (S5-S7)

  S5: BOUNDS-VALIDITY
    If bounds are returned, actual values lie within bounds.
    Formally: result.bounds.lower <= actual_value <= result.bounds.upper

  S6: EXACT-BOUNDS-TIGHTNESS
    If bounds.exact == True, bounds are achievable.
    There exist sequences achieving both lower and upper bounds.

  S7: COUNT-ACCURACY
    If cardinality is returned as exact (not estimate), count is accurate.
    Formally: result.bounds.count == |{s : satisfies(s, constraints)}|

UNCERTAINTY HONESTY (S8-S10)

  S8: UNKNOWN-ADMISSION
    Phase-8D returns UNKNOWN when it cannot determine the answer.
    It does NOT guess or approximate without explicit uncertainty bounds.

  S9: CONFIDENCE-CALIBRATION
    metadata.confidence reflects actual certainty.
    confidence == 1.0 only for proven results.

  S10: METHOD-TRANSPARENCY
    metadata.method_used accurately reports how result was obtained.
    Enumeration fallback is explicitly flagged, never hidden.

================================================================================
7. COMPLETENESS BOUNDARIES
================================================================================

Phase-8D is not complete for all queries. This section defines where exact
answers are possible versus where approximations are necessary.

EXACT ANSWERS GUARANTEED (Complete)

  MAGNITUDE-BOUNDS (B1):
    Exact for any finite length.
    Closed-form: min = 1.0, max = 1.0 + 0.2 * (length - 1)
    (Assuming constraints don't restrict further)

  CONFIGURATION-REACHABILITY (R2):
    Exact for magnitude/length pairs.
    Closed-form test from axioms M1-M5.

  EVENT-PATTERN-REACHABILITY (R3):
    Exact for any event pattern.
    Grammar axioms G1-G2 decide all patterns.

  STEP-COUNT-BOUNDS (B3):
    Exact for any length.
    Combinatorial formula from grammar.

EXACT ANSWERS CONDITIONAL (Complete with constraints)

  TARGET-SATISFIABILITY (R1):
    Exact for constraints involving only:
      - final_magnitude bounds
      - len(steps) bounds
      - Event count constraints
    MAY return UNKNOWN for complex constraint combinations.

  EXACT-COUNT (C1):
    Exact when:
      - max_length <= 10 (small space)
      - Constraints are conjunctive (no OR)
      - No complex predicates
    Returns OVERFLOW for large spaces.

  CONSTRAINT-EQUIVALENCE (E1):
    Exact for simple constraint sets.
    May return UNKNOWN for complex nested constraints.

APPROXIMATE ANSWERS (Incomplete)

  BOUNDED-ESTIMATE (C2):
    Returns bounds, not exact count.
    Confidence reflects tightness of bounds.

  RELATIVE-DENSITY (C3):
    May be approximate for complex constraints.
    Exact for magnitude-only constraints.

  UNIVERSAL-PROPERTY (I1):
    May return UNKNOWN if property cannot be decided.
    Soundness preserved: never false HOLDS.

UNDECIDABLE REGIONS

  Phase-8D does NOT attempt to decide:
    - Properties requiring semantic interpretation
    - Constraints referencing external state
    - Infinite validity spaces without bounds
    - User-defined predicates with side effects

  For undecidable queries, Phase-8D returns UNKNOWN immediately.

================================================================================
8. INVARIANTS
================================================================================

The following properties MUST hold for all Phase-8D operations:

DETERMINISM INVARIANTS (INV-D)

  INV-D1: Same query produces same result
    For all AnalysisQuery q:
      analyze(q) == analyze(q)

  INV-D2: Result hash matches query hash
    For all AnalysisResult r from query q:
      Deterministic relationship between q and r.query_hash

  INV-D3: No randomness in analysis
    Analysis methods use no random number generation.
    All tie-breaking is deterministic (lexicographic, etc.).

SOUNDNESS INVARIANTS (INV-S)

  INV-S1: Verdicts are never wrong in the "dangerous" direction
    UNSATISFIABLE → truly unsatisfiable
    HOLDS → truly holds
    NOT_EXISTS → truly does not exist

  INV-S2: Evidence is always valid
    Witnesses satisfy constraints.
    Counterexamples violate claimed properties.
    Proof traces use only valid axioms.

  INV-S3: Bounds always contain actual values
    If bounds are provided, they are never violated by any actual sequence.

INDEPENDENCE INVARIANTS (INV-I)

  INV-I1: No Phase-7 dependency
    Phase-8D does not call Phase-7 executor.
    Phase-8D does not invoke scoring or selection.
    Phase-8D reasons ABOUT constraints, not THROUGH Phase-7.

  INV-I2: No Phase-6 simulation
    Phase-8D does not call Phase-6 composition.
    Phase-8D uses axioms ABOUT Phase-6, not Phase-6 itself.
    Exception: Witness verification may use single Phase-6 call for validation.

  INV-I3: No Phase-8A dependency
    Phase-8D does not invoke rendering.
    Analysis is structural, not perceptual.

ANALYSIS-PRIMARY INVARIANT (INV-A)

  INV-A1: Enumeration is never primary method
    metadata.method_used != ENUMERATION_FALLBACK for sound results.
    Or: If ENUMERATION_FALLBACK, explicit warning in result.

  INV-A2: Analytical methods attempted first
    Before any enumeration, constraint propagation and axiom checking occur.
    Enumeration only after analytical methods return UNKNOWN.

  INV-A3: Enumeration bounded
    If enumeration occurs, enumeration_count <= options.enumeration_limit.
    Unbounded enumeration is FORBIDDEN.

NON-SEMANTIC INVARIANT (INV-N)

  INV-N1: No meaning assignment
    Analysis does not interpret sequences.
    No "good", "bad", "optimal" judgments.

  INV-N2: Structural queries only
    All queries are about structural properties.
    No queries about semantic content, emotional valence, or purpose.

================================================================================
9. FORBIDDEN BEHAVIORS
================================================================================

Phase-8D MUST NOT exhibit the following behaviors:

DEPENDENCY VIOLATIONS (F-D)

  F-D1: PHASE-7-INVOCATION
    Calling Phase-7 executor, scorer, or selector.
    Using Phase-7 generation as analysis method.
    Importing Phase-7 modules except type definitions.

  F-D2: PHASE-6-SIMULATION
    Calling Phase-6 composition on sequences.
    Running trajectories to determine properties.
    Exception: Single-sequence verification for witness validation.

  F-D3: EXTERNAL-STATE-ACCESS
    Reading environment variables, time, or system state.
    Network calls or file I/O during analysis.
    Any non-deterministic data source.

ANALYSIS VIOLATIONS (F-A)

  F-A1: ENUMERATION-AS-PRIMARY
    Using enumeration to answer satisfiability without trying axioms first.
    Counting by enumeration when combinatorial formula exists.
    Generating all sequences to find bounds.

  F-A2: UNBOUNDED-ENUMERATION
    Enumerating without limit.
    Enumeration that could exhaust memory.
    Enumeration exceeding enumeration_limit.

  F-A3: UNSOUND-APPROXIMATION
    Returning UNSATISFIABLE without proof.
    Returning HOLDS without verification.
    Guessing when UNKNOWN is appropriate.

SEMANTIC VIOLATIONS (F-S)

  F-S1: MEANING-ASSIGNMENT
    Labeling sequences as "meaningful" or "meaningless".
    Interpreting trajectory shapes symbolically.
    Assigning purpose or intent to validity spaces.

  F-S2: QUALITY-JUDGMENT
    Ranking validity spaces by "quality".
    Declaring some constraints "better" than others.
    Aesthetic or preference-based analysis.

  F-S3: RECOMMENDATION
    Suggesting "better" constraints.
    Proposing target modifications.
    Guiding toward preferred validity spaces.

OUTPUT VIOLATIONS (F-O)

  F-O1: FALSE-CERTAINTY
    confidence == 1.0 for unproven results.
    Omitting UNKNOWN when appropriate.
    Hiding uncertainty in estimates.

  F-O2: HIDDEN-ENUMERATION
    Enumeration without setting metadata.enumeration_count.
    ENUMERATION_FALLBACK without explicit method_used flag.
    Disguising enumeration as "analysis".

  F-O3: INVALID-EVIDENCE
    Witness that doesn't satisfy constraints.
    Counterexample that doesn't violate property.
    Proof trace with invalid steps.

================================================================================
10. EXAMPLE QUERIES (SKETCHED)
================================================================================

EXAMPLE 1: MAGNITUDE REACHABILITY

  Query:
    "Can final_magnitude == 1.5 be achieved with len(steps) == 4?"

  Analysis:
    From axiom M5, magnitude after last reset with n vowels:
      magnitude = 1.0 + sum(deltas)

    For magnitude 1.5 with 4 steps:
      Need sum(deltas) = 0.5
      Possible combinations (after 1 consonant, 3 vowels):
        - 5 * "a" (0.5) - but only 3 vowel slots
        - 2 * "i" + 1 * "a" (0.5) - fits in 3 slots ✓
        - etc.

    Pattern: [C, V, V, V] where C=consonant, V=vowel
    Example: ["ka", "i", "i", "a"] → magnitudes [1.0, 1.2, 1.4, 1.5]

  Result:
    verdict: SATISFIABLE
    evidence: WitnessEvidence(sequence=("ka", "i", "i", "a"), ...)
    metadata.method_used: CLOSED_FORM_DERIVATION

EXAMPLE 2: CONTRADICTION DETECTION

  Query:
    "Is target satisfiable: final_magnitude < 1.0 AND len(steps) >= 1?"

  Analysis:
    From axiom M3: ∀i, steps[i].magnitude >= 1.0
    Therefore: final_magnitude >= 1.0
    Constraint final_magnitude < 1.0 contradicts M3.

  Result:
    verdict: UNSATISFIABLE
    evidence: ProofTrace(
      steps=[
        ProofStep(1, "By axiom M3, final_magnitude >= 1.0", "M3"),
        ProofStep(2, "Constraint requires final_magnitude < 1.0", "given"),
        ProofStep(3, "Contradiction: no sequence can satisfy both", "1,2"),
      ],
      axioms_used={"M3"}
    )
    metadata.method_used: AXIOMATIC_DEDUCTION

EXAMPLE 3: CARDINALITY BOUNDS

  Query:
    "How many sequences of length 3 satisfy final_magnitude >= 1.2?"

  Analysis:
    Length 3 sequences: [C, ?, ?] where first is consonant.
    Positions 2,3 can be any token (6 consonants + 3 vowels = 9 each).
    Total length-3 sequences: 6 * 9 * 9 = 486.

    For final_magnitude >= 1.2:
      If last token is consonant: final = 1.0 (fails constraint)
      If last is vowel after consonant: need sum(vowel deltas) >= 0.2

    Patterns achieving >= 1.2:
      [C, C, V≥0.2]: 6 * 6 * 2 = 72 (V = i or u)
      [C, V, V]: Need sum >= 0.2
        All combinations except [C, a, a]: 6 * (9 - 1) = 48
        Actually: 6 * 9 = 54 total [C,V,V], minus [C,a,a] failing = 6*1 = 6
        So: 54 - 6 = 48 (wait, need to recalculate)
      [C, V, C]: final = 1.0 (fails)

    (Detailed combinatorial analysis required)

  Result:
    verdict: EXISTS (satisfying sequences exist)
    bounds: ResultBounds(lower=48, upper=126, exact=False)
    metadata.method_used: COMBINATORIAL_COUNTING
    metadata.confidence: 0.95

EXAMPLE 4: INVARIANT DERIVATION

  Query:
    "What constraints are implied by: len(steps) == 2 AND steps[1].event == 'modulate'?"

  Analysis:
    Given: len == 2, second event is modulate.
    From G1: steps[0].event == "reset" (always)
    From constraint: steps[1].event == "modulate"

    Therefore sequence is: [consonant, vowel]

    Implied constraints:
      - steps[0].magnitude == 1.0 (from M1)
      - steps[1].magnitude in {1.1, 1.15, 1.2} (from M2)
      - final_magnitude in {1.1, 1.15, 1.2}
      - count(event == "reset") == 1
      - count(event == "modulate") == 1

  Result:
    verdict: HOLDS
    evidence: ImpliedConstraints([...])
    metadata.method_used: CONSTRAINT_PROPAGATION

EXAMPLE 5: EQUIVALENCE CHECK

  Query:
    "Are these constraint sets equivalent?
     A: final_magnitude == 1.0
     B: count(event == 'modulate') == 0"

  Analysis:
    A → B:
      If final_magnitude == 1.0, then from M5, no vowels after last reset.
      If sequence ends with consonant, any prior vowels are reset.
      Therefore magnitude 1.0 implies consonant-only sequence.
      Consonant-only implies zero modulate events. ✓

    B → A:
      If zero modulate events, all tokens are consonants.
      From M4, consonant-only sequence has final_magnitude == 1.0. ✓

    Both implications hold.

  Result:
    verdict: EQUIVALENT
    evidence: ProofTrace(steps=[...])
    metadata.method_used: AXIOMATIC_DEDUCTION

================================================================================
11. COMPOSITION WITH OTHER PHASES
================================================================================

Phase-8D can be used to inform other phases:

WITH PHASE-7 (Before Generation)

  Use case: Feasibility check before expensive generation.
  Pattern:
    1. User specifies target constraints
    2. Phase-8D checks satisfiability
    3. If UNSATISFIABLE, report without generation
    4. If SATISFIABLE, proceed to Phase-7

  Benefit: Avoid enumerating candidates for impossible targets.

WITH PHASE-7 (Constraint Design)

  Use case: Help design achievable constraints.
  Pattern:
    1. User proposes constraint
    2. Phase-8D computes bounds
    3. User adjusts constraint to achievable range

  Benefit: Informed constraint specification.

WITH PHASE-8A (Renderer Validation)

  Use case: Verify renderer preserves structural properties.
  Pattern:
    1. Phase-8D derives invariant for validity space
    2. Phase-8A renders sequences from that space
    3. Verify rendered artifacts preserve invariant structure

  Benefit: Structural consistency across rendering.

STANDALONE ANALYSIS

  Use case: Pure analysis without generation or rendering.
  Pattern:
    1. User queries validity space properties
    2. Phase-8D answers from axioms
    3. No sequences generated, no artifacts rendered

  Benefit: Understanding before action.

================================================================================
12. FREEZE CONDITIONS
================================================================================

Phase-8D Formal Analysis Contract is considered complete and frozen when:

COMPLETENESS CRITERIA
  [ ] All query types fully specified (Section 3)
  [ ] Input schema complete (Section 4)
  [ ] Output schema complete (Section 5)
  [ ] Soundness guarantees enumerated (Section 6)
  [ ] Completeness boundaries defined (Section 7)
  [ ] All invariants stated (Section 8)
  [ ] All forbidden behaviors enumerated (Section 9)
  [ ] Example queries sketched (Section 10)
  [ ] Phase composition defined (Section 11)

SOUNDNESS CRITERIA
  [ ] No false UNSATISFIABLE possible
  [ ] No false HOLDS possible
  [ ] No false NOT_EXISTS possible
  [ ] All evidence types validated
  [ ] Bounds always contain actuals

INDEPENDENCE CRITERIA
  [ ] No Phase-7 invocation in analysis
  [ ] No Phase-6 simulation in analysis (except witness verification)
  [ ] No Phase-8A dependency
  [ ] Analysis-primary invariant enforceable

CONSISTENCY CRITERIA
  [ ] Axiom encoding matches Phase-6 implementation
  [ ] Query types cover all structural questions
  [ ] Output schema handles all verdict types
  [ ] Error handling complete

Once all criteria are satisfied, this contract is FROZEN.
Modifications require a new version number and explicit justification.
Frozen contracts are append-only: new versions do not delete prior guarantees.

================================================================================
END OF CONTRACT
================================================================================
