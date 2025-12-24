PHASE-8A RENDERING CONTRACT
Version: 1.0
Status: DRAFT
Date: 2025-12-18

================================================================================
POSITIONING
================================================================================

Phase-8A (Rendering Layer) operates after Phase-7 (Targeted Generation). It is
a one-way projection layer that transforms Phase-7 outputs into human-perceivable
artifacts. Phase-8A does not modify, score, or feed back into any prior phase.
It is strictly terminal in the pipeline.

Phase relationships:
  Phase-4A → Phase-6 → Phase-7 → Phase-8A
  (ontology)  (compose) (target)  (render)

Phase-8A receives ranked results from Phase-7 and produces rendered artifacts.
Multiple renderers may exist simultaneously. Each renderer produces a different
modality (phonetic, acoustic, visual, etc.) but all operate on the same input
and follow the same contract.

================================================================================
1. PHASE-8A PURPOSE
================================================================================

Phase-8A receives Phase-7 outputs (sequences with trajectories) and produces
deterministic renderings in specified modalities. It assigns perceivable form
to mechanical outputs without assigning meaning, preference, or interpretation.

Core function: Transform (sequence, trajectory) → rendered artifact

Rendering is:
  - Deterministic: same input always yields same output
  - Non-semantic: form is assigned, meaning is not
  - One-way: no information flows back to earlier phases
  - Non-selective: rendering does not score, rank, or filter
  - Modality-specific: each renderer targets one output modality

Phase-8A is NOT:
  - An interpreter (no meaning extraction)
  - A selector (no ranking or filtering)
  - A feedback mechanism (no upstream influence)
  - A learning system (no adaptation across invocations)

================================================================================
2. VALID INPUT SCHEMA
================================================================================

Phase-8A accepts a single input type: RenderInput

RENDER INPUT STRUCTURE

  RenderInput:
    type: frozen dataclass
    fields:
      ranked_result: RankedResult (required)
      renderer_id: str (required)
      renderer_config: RendererConfig (optional)

  RankedResult (from Phase-7):
    type: frozen dataclass
    fields:
      sequence: Tuple[str, ...]      # Immutable varna token sequence
      trajectory: TrajectoryResult   # Phase-6 simulation result
      score: float                   # Constraint satisfaction score
      rank: int                      # Ranking position (informational only)

  TrajectoryResult (from Phase-6):
    type: frozen dataclass
    fields:
      sequence: Tuple[str, ...]           # Same as RankedResult.sequence
      steps: Tuple[TrajectoryStep, ...]   # Trajectory steps
      final_magnitude: float              # Terminal magnitude value

  TrajectoryStep (from Phase-6):
    type: frozen dataclass
    fields:
      idx: int           # Index in sequence
      token: str         # Varna token at this step
      token_type: str    # Token classification ("consonant" | "vowel")
      magnitude: float   # Magnitude at this step
      event: str         # "reset" | "modulate"
      notes: str         # Optional annotations (ignored by renderers)

  RendererConfig:
    type: frozen dataclass
    fields:
      output_format: str               # Modality-specific format identifier
      precision: Optional[int]         # Numeric precision for applicable outputs
      include_metadata: bool           # Whether to include trajectory metadata
      custom_params: FrozenDict        # Renderer-specific parameters (frozen)

ACCESSIBLE INPUT FIELDS

Renderers may access ONLY the following fields for rendering decisions:

  FROM sequence:
    - sequence[i]: individual token at index i
    - len(sequence): sequence length
    - token membership: token in sequence

  FROM trajectory:
    - final_magnitude: terminal magnitude value
    - len(steps): number of trajectory steps
    - steps[i].magnitude: magnitude at step i
    - steps[i].event: event type at step i ("reset" | "modulate")
    - steps[i].token: token at step i
    - steps[i].token_type: token type at step i

  FROM config:
    - output_format: requested output format
    - precision: numeric precision
    - include_metadata: metadata inclusion flag
    - custom_params: renderer-specific parameters

INACCESSIBLE FIELDS

Renderers MUST NOT access or use:

  - score: Constraint satisfaction score (selection data, not rendering data)
  - rank: Ranking position (selection data, not rendering data)
  - notes: Annotation strings (may contain semantic content)
  - Any field not explicitly listed above

Rationale: score and rank are Phase-7 selection outputs, not trajectory
properties. Rendering based on score would constitute feedback/selection.

================================================================================
3. VALID OUTPUT TYPES
================================================================================

Phase-8A produces outputs conforming to the RenderOutput structure:

RENDER OUTPUT STRUCTURE

  RenderOutput:
    type: frozen dataclass
    fields:
      renderer_id: str                    # Identifier of renderer that produced this
      input_hash: str                     # Deterministic hash of input (for verification)
      modality: RenderModality            # Output modality enum
      artifact: RenderArtifact            # The rendered artifact
      metadata: Optional[RenderMetadata]  # Trajectory metadata if requested

  RenderModality (enum):
    PHONETIC    # IPA or phonetic transcription
    ACOUSTIC    # Audio parameters or waveform specification
    VISUAL      # Graphical representation specification
    SYMBOLIC    # Abstract symbol sequence
    NUMERIC     # Numeric encoding

  RenderArtifact (union type):
    PhoneticArtifact | AcousticArtifact | VisualArtifact | SymbolicArtifact | NumericArtifact

PHONETIC ARTIFACT

  PhoneticArtifact:
    type: frozen dataclass
    fields:
      transcription: Tuple[str, ...]   # IPA symbols per token
      syllable_breaks: Tuple[int, ...]  # Indices where syllables break
      stress_pattern: Tuple[int, ...]   # Stress markers (0=unstressed, 1=stressed)

  Phonetic mapping source: Deterministic mapping from varna tokens to IPA
  Stress derivation: From trajectory magnitude (threshold-based, deterministic)
  Syllable breaks: From event sequence (reset events mark breaks)

ACOUSTIC ARTIFACT

  AcousticArtifact:
    type: frozen dataclass
    fields:
      sample_rate: int                           # Samples per second
      duration_ms: Tuple[int, ...]               # Duration per token in milliseconds
      frequency_hz: Tuple[float, ...]            # Base frequency per token
      amplitude: Tuple[float, ...]               # Amplitude per token (from magnitude)
      waveform_type: str                         # "sine" | "square" | "sawtooth" | "triangle"

  Frequency derivation: Deterministic mapping from token → base frequency
  Amplitude derivation: Direct mapping from steps[i].magnitude
  Duration derivation: From token_type (consonants vs vowels have different durations)

VISUAL ARTIFACT

  VisualArtifact:
    type: frozen dataclass
    fields:
      width: int                                 # Canvas width in units
      height: int                                # Canvas height in units
      elements: Tuple[VisualElement, ...]        # Ordered visual elements

  VisualElement:
    type: frozen dataclass
    fields:
      element_type: str                          # "circle" | "line" | "rectangle" | "arc"
      x: float                                   # X position
      y: float                                   # Y position
      size: float                                # Size (from magnitude)
      color_index: int                           # Index into deterministic palette
      rotation: float                            # Rotation in degrees

  Element derivation: One element per trajectory step
  Position derivation: Sequential layout (x from index, y from magnitude)
  Size derivation: Direct mapping from steps[i].magnitude
  Color derivation: Deterministic mapping from event type

SYMBOLIC ARTIFACT

  SymbolicArtifact:
    type: frozen dataclass
    fields:
      symbols: Tuple[str, ...]                   # Abstract symbol per token
      groupings: Tuple[Tuple[int, ...], ...]     # Symbol grouping indices
      connectors: Tuple[str, ...]                # Connector types between groups

  Symbol derivation: Deterministic mapping from token → symbol
  Grouping derivation: From event sequence (reset events start new groups)
  Connector derivation: From magnitude delta between groups

NUMERIC ARTIFACT

  NumericArtifact:
    type: frozen dataclass
    fields:
      encoding: Tuple[float, ...]                # Numeric encoding per token
      checksum: int                              # Deterministic checksum of encoding

  Encoding derivation: Deterministic function of (token, magnitude, event)
  Checksum: CRC32 or similar deterministic checksum

RENDER METADATA

  RenderMetadata:
    type: frozen dataclass
    fields:
      sequence_length: int                       # len(sequence)
      step_count: int                            # len(steps)
      final_magnitude: float                     # trajectory.final_magnitude
      event_counts: FrozenDict[str, int]         # {"reset": n, "modulate": m}
      magnitude_range: Tuple[float, float]       # (min, max) magnitude

  Metadata contains ONLY mechanical trajectory properties.
  No interpretive labels, no semantic descriptions.

================================================================================
4. RENDERER INTERFACE
================================================================================

All renderers must implement the Renderer protocol:

RENDERER PROTOCOL

  class Renderer(Protocol):

    @property
    def renderer_id(self) -> str:
      """Unique identifier for this renderer. Immutable."""

    @property
    def modality(self) -> RenderModality:
      """Output modality this renderer produces. Immutable."""

    @property
    def supported_formats(self) -> FrozenSet[str]:
      """Set of output_format values this renderer accepts. Immutable."""

    def validate_config(self, config: RendererConfig) -> ValidationResult:
      """
      Validate renderer configuration before rendering.
      Returns ValidationResult with is_valid and error details.
      Must be deterministic: same config → same validation result.
      Must not have side effects.
      """

    def render(self, input: RenderInput) -> RenderOutput:
      """
      Transform input into rendered artifact.
      Must be deterministic: same input → same output.
      Must not access score or rank fields.
      Must not have side effects beyond producing output.
      Must not raise exceptions for valid input (return error in output).
      """

    def compute_input_hash(self, input: RenderInput) -> str:
      """
      Compute deterministic hash of input for verification.
      Must use only accessible fields (not score/rank).
      Must be deterministic: same input → same hash.
      """

VALIDATION RESULT

  ValidationResult:
    type: frozen dataclass
    fields:
      is_valid: bool                             # Whether config is valid
      error_type: Optional[RenderErrorType]      # Error type if invalid
      error_details: Optional[str]               # Specific error message

DETERMINISM REQUIREMENT

  For any renderer R and any valid input I:
    R.render(I) == R.render(I)  # Always true
    R.compute_input_hash(I) == R.compute_input_hash(I)  # Always true
    R.validate_config(C) == R.validate_config(C)  # Always true

  Determinism is enforced by:
    - No random number generation
    - No time-dependent operations
    - No external state access
    - No floating-point operations with platform-dependent results
    - Ordered iteration over all collections

STATELESSNESS REQUIREMENT

  Renderers must be stateless between invocations:
    - No instance variables modified by render()
    - No caching that affects output
    - No learning or adaptation
    - No accumulation across calls

  Each render() call is independent. Prior calls do not influence output.

================================================================================
5. INVARIANTS
================================================================================

The following properties MUST hold for all renderers, all inputs, all outputs:

DETERMINISM INVARIANT

  INV-1: Same input produces same output
    For all valid RenderInput i, Renderer r:
      r.render(i) == r.render(i)

  INV-2: Output hash matches input hash
    For all RenderOutput o produced by Renderer r from RenderInput i:
      o.input_hash == r.compute_input_hash(i)

  INV-3: Modality matches renderer declaration
    For all RenderOutput o produced by Renderer r:
      o.modality == r.modality

ISOLATION INVARIANT

  INV-4: No upstream influence
    Rendering produces output only. No renderer may:
      - Modify the input RenderInput
      - Send signals to Phase-7 or earlier
      - Write to shared state read by earlier phases
      - Influence future Phase-7 generation

  INV-5: No cross-renderer influence
    For all Renderers r1, r2 and RenderInput i:
      r1.render(i) does not affect r2.render(i)
    Renderers are independent. Order of invocation does not matter.

NON-SELECTION INVARIANT

  INV-6: Score and rank are not accessed
    For all Renderer r:
      r.render() implementation does not read input.ranked_result.score
      r.render() implementation does not read input.ranked_result.rank

  INV-7: Output does not encode preference
    RenderOutput contains no field indicating:
      - Quality of the sequence
      - Preference over other sequences
      - Fitness for any purpose
      - Recommendation or suggestion

NON-SEMANTIC INVARIANT

  INV-8: No meaning assignment
    RenderOutput contains no field encoding:
      - Semantic content
      - Interpretation
      - Symbolism
      - Emotional valence
      - Cultural association

  INV-9: Rendering is form, not content
    The artifact represents the sequence/trajectory structure
    in perceivable form. It does not represent what the sequence
    "means" or "is for" because sequences have no meaning or purpose.

COMPLETENESS INVARIANT

  INV-10: All valid inputs produce output
    For all valid RenderInput i and Renderer r:
      r.render(i) produces RenderOutput (not exception)

  INV-11: Invalid inputs produce error output
    For all invalid RenderInput i and Renderer r:
      r.render(i) produces RenderOutput with error field populated

REVERSIBILITY PROHIBITION

  INV-12: Rendering is not invertible
    There exists no function f such that:
      f(r.render(i)) == i for all i
    Rendering may be lossy. Multiple inputs may produce same output.
    This is acceptable: rendering projects, it does not encode.

================================================================================
6. FORBIDDEN BEHAVIORS
================================================================================

Renderers MUST NOT exhibit the following behaviors:

FEEDBACK BEHAVIORS (F-1 through F-4)

  F-1: UPSTREAM MODIFICATION
    Modifying any Phase-7, Phase-6, or Phase-4A state
    Modifying the input RenderInput object
    Writing to any location read by earlier phases

  F-2: SELECTION FEEDBACK
    Using score or rank to influence rendering
    Producing output that encodes selection preference
    Communicating quality judgments through artifacts

  F-3: LEARNING
    Storing information from one render() call for use in another
    Adapting rendering based on prior inputs
    Building models of input distributions
    Caching that changes output for repeated inputs

  F-4: EXTERNAL INFLUENCE
    Reading external state (time, environment, user state)
    Using random number generators
    Depending on network or filesystem state
    Producing different output based on execution context

SEMANTIC BEHAVIORS (F-5 through F-8)

  F-5: MEANING ASSIGNMENT
    Including interpretation in output
    Adding semantic labels to artifacts
    Translating sequences to natural language
    Associating sequences with concepts

  F-6: EMOTIONAL ENCODING
    Mapping sequences to emotional states
    Using "mood" or "feel" in artifact specification
    Choosing colors/sounds based on emotional association
    Labeling outputs as "calming", "energizing", etc.

  F-7: SYMBOLIC INTERPRETATION
    Treating sequences as representing something
    Assigning cultural or spiritual significance
    Interpreting trajectory patterns as meaningful shapes
    Finding "hidden messages" in magnitude sequences

  F-8: AESTHETIC JUDGMENT
    Labeling outputs as "beautiful" or "ugly"
    Applying aesthetic rules to rendering
    Optimizing for perceived quality
    Filtering based on subjective criteria

SELECTION BEHAVIORS (F-9 through F-11)

  F-9: RANKING
    Ordering multiple outputs by quality
    Assigning scores to rendered artifacts
    Comparing artifacts against each other
    Producing "best" rendering

  F-10: FILTERING
    Refusing to render certain inputs
    Producing null output for valid input
    Silently dropping inputs
    Selective rendering based on input properties

  F-11: RECOMMENDATION
    Suggesting alternative sequences
    Proposing modifications to input
    Indicating that another sequence would render "better"
    Guiding toward preferred inputs

IMPLEMENTATION BEHAVIORS (F-12 through F-14)

  F-12: NON-DETERMINISM
    Using random numbers
    Depending on time or date
    Using hash functions with non-deterministic seeds
    Platform-dependent floating point operations

  F-13: SIDE EFFECTS
    File I/O during rendering
    Network operations during rendering
    Logging that affects state
    Resource allocation that persists

  F-14: EXCEPTION THROWING
    Raising exceptions for valid input
    Crashing on edge cases
    Undefined behavior for boundary values
    Partial output on failure

================================================================================
7. EXAMPLE RENDERERS (SKETCHED)
================================================================================

The following renderer sketches illustrate valid implementations.
These are specifications, not code.

PHONETIC RENDERER (phonetic_v1)

  Purpose: Transform sequence → IPA transcription with prosodic markers

  Token → IPA mapping (deterministic, from Phase-4A definitions):
    ka → /kə/    ga → /gə/    ta → /tə/
    da → /də/    pa → /pə/    ba → /bə/
    a  → /aː/    i  → /iː/    u  → /uː/

  Stress derivation (from magnitude):
    magnitude >= 1.5 → stressed (1)
    magnitude < 1.5  → unstressed (0)

  Syllable breaks (from events):
    event == "reset" → syllable boundary

  Example:
    Input: sequence=("ba", "a", "i", "ka", "u")
           steps=[{mag:1.0, event:reset}, {mag:1.2, event:modulate},
                  {mag:1.8, event:modulate}, {mag:1.0, event:reset},
                  {mag:1.3, event:modulate}]

    Output: PhoneticArtifact(
              transcription=("/bə/", "/aː/", "/iː/", "/kə/", "/uː/"),
              syllable_breaks=(0, 3),
              stress_pattern=(0, 0, 1, 0, 0)
            )

ACOUSTIC RENDERER (acoustic_v1)

  Purpose: Transform sequence → audio parameter specification

  Token → frequency mapping (deterministic):
    ka → 440.0 Hz   ga → 392.0 Hz   ta → 349.2 Hz
    da → 329.6 Hz   pa → 293.7 Hz   ba → 261.6 Hz
    a  → 523.3 Hz   i  → 587.3 Hz   u  → 659.3 Hz

  Amplitude derivation (from magnitude):
    amplitude = magnitude / 3.0  # Normalized to [0.33, 1.0] range

  Duration derivation (from token_type):
    consonant → 100 ms
    vowel     → 200 ms

  Example:
    Input: sequence=("ba", "a", "ka")
           steps=[{mag:1.0, event:reset, token_type:consonant},
                  {mag:1.5, event:modulate, token_type:vowel},
                  {mag:1.0, event:reset, token_type:consonant}]

    Output: AcousticArtifact(
              sample_rate=44100,
              duration_ms=(100, 200, 100),
              frequency_hz=(261.6, 523.3, 440.0),
              amplitude=(0.333, 0.5, 0.333),
              waveform_type="sine"
            )

VISUAL RENDERER (visual_v1)

  Purpose: Transform trajectory → geometric visualization

  Element derivation (one per step):
    event == "reset"    → circle
    event == "modulate" → rectangle

  Position derivation:
    x = step.idx * 50  # Horizontal spacing
    y = step.magnitude * 100  # Vertical position from magnitude

  Size derivation:
    size = step.magnitude * 20

  Color derivation:
    event == "reset"    → color_index 0 (e.g., blue)
    event == "modulate" → color_index 1 (e.g., orange)

  Example:
    Input: steps=[{idx:0, mag:1.0, event:reset},
                  {idx:1, mag:1.5, event:modulate},
                  {idx:2, mag:1.2, event:modulate}]

    Output: VisualArtifact(
              width=150,
              height=200,
              elements=(
                VisualElement(type="circle", x=0, y=100, size=20, color_index=0, rotation=0),
                VisualElement(type="rectangle", x=50, y=150, size=30, color_index=1, rotation=0),
                VisualElement(type="rectangle", x=100, y=120, size=24, color_index=1, rotation=0)
              )
            )

SYMBOLIC RENDERER (symbolic_v1)

  Purpose: Transform sequence → abstract symbol sequence

  Token → symbol mapping (arbitrary but deterministic):
    ka → "◆"    ga → "◇"    ta → "▲"
    da → "△"    pa → "●"    ba → "○"
    a  → "─"    i  → "│"    u  → "┼"

  Grouping derivation:
    Reset events start new groups

  Connector derivation (from magnitude delta):
    delta > 0.3  → "→"
    delta < -0.3 → "←"
    otherwise    → "·"

  Example:
    Input: sequence=("ba", "a", "ka", "i")
           steps with resets at indices 0 and 2

    Output: SymbolicArtifact(
              symbols=("○", "─", "◆", "│"),
              groupings=((0, 1), (2, 3)),
              connectors=("·",)
            )

================================================================================
8. FAILURE MODES
================================================================================

Phase-8A can fail in the following mechanically detectable ways:

INVALID INPUT ERRORS

  UNKNOWN_RENDERER
    Definition: renderer_id does not match any registered renderer
    Detection: Lookup in renderer registry fails
    Report: RenderErrorType.UNKNOWN_RENDERER
    Output: RenderOutput with error field, no artifact

  INVALID_CONFIG
    Definition: renderer_config fails validation
    Detection: renderer.validate_config() returns is_valid=false
    Report: RenderErrorType.INVALID_CONFIG with details
    Output: RenderOutput with error field, no artifact

  UNSUPPORTED_FORMAT
    Definition: output_format not in renderer.supported_formats
    Detection: Format membership check fails
    Report: RenderErrorType.UNSUPPORTED_FORMAT
    Output: RenderOutput with error field, no artifact

  MALFORMED_INPUT
    Definition: RenderInput missing required fields or has invalid types
    Detection: Schema validation fails
    Report: RenderErrorType.MALFORMED_INPUT
    Output: RenderOutput with error field, no artifact

TRAJECTORY ERRORS

  EMPTY_SEQUENCE
    Definition: sequence has length 0
    Detection: len(sequence) == 0
    Report: RenderErrorType.EMPTY_SEQUENCE
    Output: RenderOutput with error field, no artifact

  EMPTY_TRAJECTORY
    Definition: steps has length 0
    Detection: len(steps) == 0
    Report: RenderErrorType.EMPTY_TRAJECTORY
    Output: RenderOutput with error field, no artifact

  SEQUENCE_TRAJECTORY_MISMATCH
    Definition: sequence and steps have different lengths
    Detection: len(sequence) != len(steps)
    Report: RenderErrorType.SEQUENCE_TRAJECTORY_MISMATCH
    Output: RenderOutput with error field, no artifact

  INVALID_TOKEN
    Definition: sequence contains token not in Phase-4A varna set
    Detection: Token not in valid token set
    Report: RenderErrorType.INVALID_TOKEN with token value
    Output: RenderOutput with error field, no artifact

RENDER ERROR OUTPUT STRUCTURE

  RenderOutput (error case):
    renderer_id: str                    # Renderer that encountered error
    input_hash: str                     # Hash of input (if computable)
    modality: RenderModality            # Renderer's declared modality
    artifact: None                      # No artifact produced
    metadata: None                      # No metadata produced
    error: RenderError                  # Error details

  RenderError:
    type: frozen dataclass
    fields:
      error_type: RenderErrorType       # Enumerated error type
      error_message: str                # Specific error details
      recoverable: bool                 # Whether retry might succeed (always false)

  RenderErrorType (enum):
    UNKNOWN_RENDERER
    INVALID_CONFIG
    UNSUPPORTED_FORMAT
    MALFORMED_INPUT
    EMPTY_SEQUENCE
    EMPTY_TRAJECTORY
    SEQUENCE_TRAJECTORY_MISMATCH
    INVALID_TOKEN
    INTERNAL_ERROR                      # Catch-all for unexpected failures

All failure modes produce deterministic, reproducible error outputs.
No failure is silent. No failure produces partial artifacts.
Errors are informational only; they do not guide correction.

================================================================================
9. NON-GOALS
================================================================================

Phase-8A explicitly does NOT:

  - Interpret sequences (no meaning extraction)
  - Rank sequences (no quality assessment)
  - Filter sequences (no selection)
  - Recommend sequences (no suggestions)
  - Learn from sequences (no adaptation)
  - Optimize renderings (no quality metrics)
  - Modify upstream phases (no feedback)
  - Cache across invocations (no state)
  - Provide confidence scores (no uncertainty)
  - Generate alternative sequences (no suggestion)
  - Evaluate aesthetic quality (no judgment)
  - Assign emotional valence (no affect)
  - Detect patterns (no analysis beyond rendering)
  - Predict user preferences (no personalization)
  - Smooth or interpolate trajectories (no modification)
  - Enhance or improve input (no transformation beyond rendering)
  - Validate constraint satisfaction (Phase-7's job)
  - Access Phase-4A ontology directly (use trajectory data only)
  - Communicate with external systems
  - Persist state between invocations
  - Use machine learning in any form
  - Produce natural language descriptions
  - Handle ambiguous input (reject or render deterministically)

================================================================================
10. COMPOSITION RULES
================================================================================

Multiple renderers may process the same input:

PARALLEL RENDERING

  For RenderInput i and Renderers r1, r2, ..., rn:
    Outputs o1 = r1.render(i)
             o2 = r2.render(i)
             ...
             on = rn.render(i)
    are independent and may be computed in any order.

  All outputs are equally valid. None is preferred.

MULTI-MODAL OUTPUT

  A sequence may be rendered to multiple modalities simultaneously:
    - Phonetic transcription
    - Acoustic specification
    - Visual representation
    - Symbolic encoding

  All modalities represent the same input. None is canonical.
  Users may consume any or all modalities.

NO RENDERING COMPOSITION

  Renderers do not compose:
    - r2.render(r1.render(i)) is not valid (artifact is not RenderInput)
    - Renderers are terminal transformations

  Chaining is forbidden. Each render is a projection from Phase-7 output
  to perceivable artifact. The artifact is not further processable by
  the rendering layer.

BATCH RENDERING

  RenderBatch:
    type: frozen dataclass
    fields:
      inputs: Tuple[RenderInput, ...]        # Multiple inputs
      renderer_ids: FrozenSet[str]           # Renderers to apply

  BatchRenderOutput:
    type: frozen dataclass
    fields:
      outputs: Tuple[Tuple[RenderOutput, ...], ...]  # outputs[i][j] = renderer j on input i

  Batch rendering is syntactic convenience. Each output is independent.
  Order does not affect results.

================================================================================
11. FREEZE CONDITIONS
================================================================================

Phase-8A Rendering Contract is considered complete and frozen when:

COMPLETENESS CRITERIA
  [ ] Valid input schema fully specified (Section 2)
  [ ] Valid output types enumerated (Section 3)
  [ ] Renderer interface fully defined (Section 4)
  [ ] All invariants stated (Section 5)
  [ ] All forbidden behaviors enumerated (Section 6)
  [ ] Example renderers sketched (Section 7)
  [ ] All failure modes enumerated (Section 8)
  [ ] All non-goals stated (Section 9)
  [ ] Composition rules defined (Section 10)

CONSISTENCY CRITERIA
  [ ] No input field references data outside Phase-7 output
  [ ] No output field contains semantic content
  [ ] No invariant requires semantic interpretation
  [ ] No failure mode is silent or ambiguous
  [ ] All rendering operations are deterministic

ISOLATION CRITERIA
  [ ] No mechanism for upstream feedback exists
  [ ] No mechanism for cross-renderer influence exists
  [ ] No mechanism for learning or adaptation exists
  [ ] No mechanism for selection or ranking exists

VERIFICATION CRITERIA
  [ ] Contract reviewed for semantic leakage (none found)
  [ ] Contract reviewed for selection behavior (none found)
  [ ] Contract reviewed for feedback mechanisms (none found)
  [ ] Contract reviewed for non-determinism (none found)

STABILITY CRITERIA
  [ ] No open questions remain in contract text
  [ ] No "TBD" or "TODO" markers present
  [ ] All artifact types fully specified
  [ ] All error types enumerated, not open-ended

Once all criteria are satisfied, this contract is FROZEN.
Modifications require a new version number and explicit justification.
Frozen contracts are append-only: new versions do not delete prior guarantees.

================================================================================
END OF CONTRACT
================================================================================
