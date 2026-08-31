# Ontological Layer Influence Contracts

## Symbol-U / Soulpi Deterministic Substrate
### Design Specification v1.0

---

## 1. Summary: Projection Lenses Over the Same Substrate

1. **Ontological layers are NOT pipeline stages.** They are relational projection lenses that change how influence propagates through the same underlying structural substrate.

2. **The substrate is fixed.** Phases 1b–9 produce immutable structural artifacts (acoustic units, eligibility masks, folds, graphs, rewrite traces). Layers do not modify these artifacts; they project different influence behaviors onto them.

3. **Projection changes relation dominance.** When viewing through a layer, certain structural relations become dominant (propagate influence) while others become suppressed (block or attenuate influence paths).

4. **All layers operate on the same invariant core.** NO_PROBABILITY, NO_LEARNING, NO_SEMANTICS, NO_INTENT inference, NO_EMOTION inference, NO_FREE_FORM generation remain enforced across all projections.

5. **Layer selection is structural, not semantic.** Which layer applies is determined by structural markers (boundary tags, fold states, graph topology), never by content interpretation.

6. **Influence is binary or ternary, never continuous.** Relations either propagate (ACTIVE), block (SUPPRESSED), or defer (NEUTRAL). No weights, scores, or gradients.

7. **Each layer tightens or loosens specific invariants.** Higher layers (toward Absolving) progressively loosen commitment constraints while tightening consistency requirements.

8. **Reversibility is mandatory through layer 9 (Unifying).** Any projection applied can be structurally undone. Absolving is the only layer where reversibility semantics require special treatment.

9. **Observer attachment is the only path to interpretation.** The substrate produces structural outputs; any meaning assignment occurs outside the deterministic core via explicit observer attachment declarations.

10. **Fail-closed is universal.** Any ambiguity, prohibited content detection, or invariant violation causes immediate rejection with no degraded output mode.

11. **Cross-layer consistency is enforced by derivation rules.** No layer may introduce structural fields not derivable from prior artifacts. All projections must be traceable to substrate primitives.

12. **Layers compose but do not nest.** Multiple projections may be applied sequentially (Acting → Tagging → Forming), but a structure cannot simultaneously be viewed through conflicting layers. Layer ordering is total.

---

## 2. Layer-by-Layer Contracts

---

### Layer 1: ACTING

**Purpose:** Projects the substrate to reveal operational execution paths—what structural transformations are immediately applicable.

#### 2.1.1 Influence Transform

- **Dominant Relations:** `ADJACENCY`, `BOUNDARY_CONTACT`, `IMMEDIATE_SUCCESSOR`
- **Suppressed Relations:** `TRANSITIVE_CLOSURE`, `REFLEXIVE`, `HIERARCHICAL_PARENT`
- **Influence Behavior:** Only direct, single-hop structural connections propagate influence. Multi-hop paths are collapsed to their first edge only.

#### 2.1.2 Allowed Structural Degrees of Freedom

- Application of rewrite rules from Phase 9 rule set (pre-validated, confluence-proven)
- Boundary state transitions (OPEN → CLOSED, CLOSED → FROZEN)
- Unit state marking (VISITED, UNVISITED, PROCESSING)
- Sequence cursor advancement
- Partition membership assignment (single partition per unit)

#### 2.1.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Infer "intent" from adjacency patterns | NO_INTENT violation |
| Assign "importance" to execution paths | Implicit scoring |
| Use "frequency of access" as selection criterion | Statistical reasoning |
| Interpret unit content as "action verbs" | NO_SEMANTICS violation |
| Generate new units not in source artifact | NO_GENERATION violation |
| Reference: goal, want, try, should, will, plan | Intent-laden vocabulary |

#### 2.1.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| DETERMINISTIC | **Tightened** | Execution paths must be fully reproducible; same input → same traversal order |
| REVERSIBLE | Unchanged | All state marks are invertible |
| NO_SEMANTICS | Unchanged | Structural traversal only |
| NO_PROBABILITY | Unchanged | No path weighting |
| SINGLE_ACTIVE_PATH | **New/Tightened** | At most one execution cursor active per projection instance |

#### 2.1.5 Layer Output Form

- **Primary:** `execution_trace` — ordered sequence of (unit_id, operation_applied, boundary_state_before, boundary_state_after)
- **Secondary:** `reachability_mask` — binary mask over units indicating single-hop reachability from current cursor
- **Tertiary:** `blocked_set` — set of unit_ids where influence propagation halted

#### 2.1.6 Entry/Exit Conditions

**Entry Requirements:**
- Artifact must have at least one unit with `BOUNDARY_STATE = OPEN`
- No circular dependency in immediate adjacency (validated by Phase 9 acyclicity check)
- All units must have assigned `execution_eligibility` from Phase PO5

**Exit Conditions:**
- All `OPEN` boundaries either transitioned to `CLOSED` or explicitly marked `DEFERRED`
- Execution trace is non-empty OR explicit `NULL_TRACE` marker emitted
- No unit remains in `PROCESSING` state

#### 2.1.7 Failure Mode

- **On prohibited content detection:** Emit `ACTING_VIOLATION` with violating unit_id, halt trace, return partial trace with `INCOMPLETE` flag
- **On ambiguous path (multiple valid next-steps with no deterministic selector):** Emit `ACTING_AMBIGUITY`, freeze all boundaries, require explicit disambiguation input
- **On invariant violation:** Immediate rejection, no partial output, full rollback to pre-projection state

---

### Layer 2: TAGGING

**Purpose:** Projects the substrate to reveal structural annotation points—where markers can attach without altering topology.

#### 2.2.1 Influence Transform

- **Dominant Relations:** `MEMBERSHIP`, `CONTAINMENT`, `LABEL_ATTACHMENT_POINT`
- **Suppressed Relations:** `ADJACENCY`, `CAUSAL_PREDECESSOR`, `TEMPORAL_SEQUENCE`
- **Influence Behavior:** Influence propagates through containment hierarchies and membership sets. Sequential/temporal relations do not carry influence in this projection.

#### 2.2.2 Allowed Structural Degrees of Freedom

- Tag attachment to designated attachment points (predefined in Phase 2 modifier output)
- Tag detachment (symmetric inverse of attachment)
- Tag set union/intersection over units sharing containment
- Partition refinement by tag presence/absence
- Canonicalization of tag ordering within a unit

#### 2.2.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Interpret tag content as "category" or "type" | NO_SEMANTICS violation |
| Use tag count as relevance signal | Implicit scoring |
| Infer "similarity" from shared tags | NO_SIMILARITY violation |
| Create tags not in predefined tag vocabulary | NO_GENERATION violation |
| Reference: meaning, category, type, kind, class, sort | Semantic vocabulary |
| Apply tags based on "pattern recognition" of content | Statistical/learning proxy |

#### 2.2.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| TAG_VOCABULARY_CLOSED | **New/Tightened** | Only predefined structural tags permitted |
| REVERSIBLE | Unchanged | All attachments invertible |
| NO_SEMANTICS | **Reinforced** | Tags are opaque identifiers, not meanings |
| IDEMPOTENT_TAGGING | **New** | Attaching same tag twice = single attachment |

#### 2.2.5 Layer Output Form

- **Primary:** `tag_assignment_map` — relation set of (unit_id, tag_id, attachment_point_id)
- **Secondary:** `containment_projection` — hierarchical structure showing tag inheritance paths
- **Tertiary:** `tag_partition` — partition of units by tag-set equivalence

#### 2.2.6 Entry/Exit Conditions

**Entry Requirements:**
- Artifact must have Phase 2 modifier annotations complete
- All units must have at least one valid `attachment_point`
- Tag vocabulary must be loaded and frozen

**Exit Conditions:**
- Every tag attachment has a corresponding `attachment_point` (no dangling tags)
- Tag assignment map is deterministically ordered
- No `PENDING_TAG` states remain

#### 2.2.7 Failure Mode

- **On unknown tag encountered:** Emit `TAG_VOCABULARY_VIOLATION`, reject entire tagging operation, preserve prior tag state
- **On attachment point not found:** Emit `TAG_ATTACHMENT_INVALID`, skip that tag, continue with warning accumulation, fail if warnings exceed threshold (configurable, default=0)
- **On semantic content detected in tag payload:** Immediate rejection, emit `TAG_SEMANTICS_VIOLATION`

---

### Layer 3: FORMING

**Purpose:** Projects the substrate to reveal shape and boundary structure—how units compose into larger forms.

#### 2.3.1 Influence Transform

- **Dominant Relations:** `BOUNDARY`, `COMPOSITION`, `PART_WHOLE`, `SHAPE_CONTAINMENT`
- **Suppressed Relations:** `TEMPORAL_SEQUENCE`, `CAUSAL`, `LABEL_ATTACHMENT`
- **Influence Behavior:** Influence flows through compositional boundaries. A form's boundary mediates all influence entering or exiting; internal structure is opaque from outside.

#### 2.3.2 Allowed Structural Degrees of Freedom

- Boundary instantiation (create closed boundary around unit set)
- Boundary dissolution (inverse of instantiation)
- Boundary merge (two adjacent boundaries become one)
- Boundary split (one boundary becomes two non-overlapping)
- Form canonicalization (reorder internal units to canonical form)
- Nested form construction (forms containing forms)

#### 2.3.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Assess "complexity" of forms | Implicit measure |
| Infer "gestalt" or "wholeness" properties | Semantic interpretation |
| Use form size as selection criterion | Magnitude comparison |
| Reference: pattern, shape-meaning, structure-significance | Semantic vocabulary |
| Create forms based on "visual similarity" | NO_SIMILARITY violation |
| Assign "natural" vs "artificial" form distinctions | Semantic classification |

#### 2.3.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| BOUNDARY_INTEGRITY | **New/Tightened** | No unit may belong to overlapping non-nested boundaries |
| COMPOSITION_ACYCLIC | **New/Tightened** | Form containment must be a DAG (no form contains itself transitively) |
| REVERSIBLE | Unchanged | All boundary operations invertible |
| NO_SEMANTICS | Unchanged | Forms are structural, not meaningful |

#### 2.3.5 Layer Output Form

- **Primary:** `boundary_graph` — graph where nodes are boundaries, edges are containment/adjacency
- **Secondary:** `form_hierarchy` — tree structure of nested forms
- **Tertiary:** `canonical_form_representation` — normalized representation of each form's internal structure

#### 2.3.6 Entry/Exit Conditions

**Entry Requirements:**
- All units must have boundary eligibility computed (Phase 8 sentinel states)
- No `BOUNDARY_CONFLICT` markers present
- Compositional rules loaded from Phase 7 folding specification

**Exit Conditions:**
- All boundaries are either `CLOSED` or `FROZEN`
- Boundary graph is connected or explicitly partitioned
- No orphan units (every unit inside at least the root boundary)

#### 2.3.7 Failure Mode

- **On boundary overlap detected:** Emit `FORMING_OVERLAP_VIOLATION`, reject merge/split operation, preserve prior boundary state
- **On cyclic containment:** Emit `FORMING_CYCLE_VIOLATION`, immediate rejection, full rollback
- **On unbounded unit set:** Emit `FORMING_ORPHAN_VIOLATION`, require explicit root boundary creation

---

### Layer 4: THINKING

**Purpose:** Projects the substrate to reveal transformation chains—how structures change through rule application.

#### 2.4.1 Influence Transform

- **Dominant Relations:** `TRANSFORMATION`, `RULE_APPLICATION`, `DERIVATION_STEP`
- **Suppressed Relations:** `SPATIAL_ADJACENCY`, `MEMBERSHIP`, `STATIC_CONTAINMENT`
- **Influence Behavior:** Influence flows along derivation chains. Static structural relations do not propagate; only transformation edges carry influence.

#### 2.4.2 Allowed Structural Degrees of Freedom

- Rule application from Phase 9 validated rule set
- Derivation chain construction (sequence of rule applications)
- Transformation composition (chain multiple rules)
- Transformation inversion (apply reverse rule where defined)
- Fixpoint detection (recognize when no further rules apply)
- Derivation branch creation (multiple valid rule sequences from same source)

#### 2.4.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Assess "quality" of transformations | Implicit scoring |
| Prefer "simpler" derivations | Complexity measure |
| Infer "reasoning" or "logic" from chains | NO_SEMANTICS—reasoning is Layer 6 |
| Reference: idea, concept, thought-content, insight | Cognitive/semantic vocabulary |
| Use derivation length as optimality criterion | Magnitude comparison |
| Select rules based on "likelihood" | NO_PROBABILITY violation |

#### 2.4.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| CONFLUENCE | **Enforced** | All derivation branches reaching same target must be joinable |
| TERMINATION | **Enforced** | All rule application sequences must reach fixpoint |
| REVERSIBLE | Unchanged | Derivation chains invertible where inverse rules exist |
| NO_SEMANTICS | Unchanged | Rules are structural rewrite, not logical inference |
| DERIVATION_TRACE_COMPLETE | **New** | Every transformation step must be recorded |

#### 2.4.5 Layer Output Form

- **Primary:** `derivation_dag` — directed acyclic graph of transformation steps
- **Secondary:** `rule_application_trace` — sequence of (source_state, rule_id, target_state)
- **Tertiary:** `fixpoint_certificate` — proof artifact that no further rules apply

#### 2.4.6 Entry/Exit Conditions

**Entry Requirements:**
- Phase 9 rule set loaded with termination proofs
- Source structure must be well-formed per Phase 8 boundary sentinel
- No `TRANSFORMATION_BLOCKED` markers present

**Exit Conditions:**
- Derivation reached fixpoint OR explicit `DERIVATION_LIMIT` reached
- All branches either converged or marked `DIVERGENT`
- Derivation trace non-empty or explicit `NULL_DERIVATION` marker

#### 2.4.7 Failure Mode

- **On non-termination detected:** Emit `THINKING_NONTERMINATION`, halt after step limit, return partial trace with `INCOMPLETE` flag
- **On confluence failure:** Emit `THINKING_CONFLUENCE_VIOLATION`, preserve all branches, require manual resolution
- **On invalid rule application:** Emit `THINKING_RULE_VIOLATION`, reject that step, backtrack to prior state

---

### Layer 5: DIRECTING

**Purpose:** Projects the substrate to reveal control flow and sequencing—which paths are selected when alternatives exist.

#### 2.5.1 Influence Transform

- **Dominant Relations:** `CONTROL_FLOW`, `SELECTION`, `BRANCH_POINT`, `SEQUENCE_ORDER`
- **Suppressed Relations:** `COMPOSITIONAL`, `TRANSFORMATIONAL`, `MEMBERSHIP`
- **Influence Behavior:** Influence follows selected control paths only. Unselected branches do not propagate influence regardless of their structural properties.

#### 2.5.2 Allowed Structural Degrees of Freedom

- Branch selection at branch points (deterministic selector required)
- Sequence ordering enforcement
- Control flow merge (multiple paths rejoin)
- Loop boundary establishment (with termination proof)
- Conditional gate evaluation (structural predicates only)
- Path exclusion marking

#### 2.5.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Select based on "preference" or "priority" | Implicit ranking |
| Infer "intent" behind control flow | NO_INTENT violation |
| Use "heuristics" for branch selection | Statistical proxy |
| Reference: goal, objective, target, aim, direction-meaning | Intent vocabulary |
| Weight branches by "likelihood of success" | NO_PROBABILITY violation |
| Interpret control flow as "planning" | Semantic overlay |

#### 2.5.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| DETERMINISTIC_SELECTION | **New/Tightened** | Branch selection must be deterministic given structural state |
| SINGLE_ACTIVE_BRANCH | **New/Tightened** | At most one branch active at any branch point |
| NO_DEAD_PATHS | **New** | All branches must be reachable or explicitly marked unreachable |
| REVERSIBLE | Unchanged | Selection can be undone by re-enabling suppressed branches |

#### 2.5.5 Layer Output Form

- **Primary:** `control_flow_graph` — graph with branch points, merge points, sequence edges
- **Secondary:** `selected_path_trace` — ordered list of selected branches
- **Tertiary:** `exclusion_set` — set of branch_ids not taken with structural reason

#### 2.5.6 Entry/Exit Conditions

**Entry Requirements:**
- All branch points must have deterministic selectors defined
- Control flow graph must be acyclic or loops must have termination proofs
- Entry point explicitly marked

**Exit Conditions:**
- Exit point reached OR explicit `CONTROL_HALT` state
- All branch selections recorded in trace
- No `PENDING_SELECTION` states remain

#### 2.5.7 Failure Mode

- **On non-deterministic branch point:** Emit `DIRECTING_AMBIGUITY`, halt at branch point, require selector specification
- **On infinite loop detected:** Emit `DIRECTING_LOOP_VIOLATION`, halt after iteration limit, return partial trace
- **On unreachable exit:** Emit `DIRECTING_DEADLOCK`, freeze control flow, require structural modification

---

### Layer 6: REASONING

**Purpose:** Projects the substrate to reveal inferential structure—how conclusions relate to premises through structural rules.

#### 2.6.1 Influence Transform

- **Dominant Relations:** `INFERENCE_STEP`, `PREMISE_CONCLUSION`, `STRUCTURAL_ENTAILMENT`
- **Suppressed Relations:** `TEMPORAL`, `CONTROL_FLOW`, `COMPOSITIONAL`
- **Influence Behavior:** Influence propagates from premises to conclusions through validated inference rules. No influence flows backward (conclusions do not affect premises).

#### 2.6.2 Allowed Structural Degrees of Freedom

- Inference rule application (from validated structural rule set)
- Premise collection (gather structures satisfying rule antecedent)
- Conclusion derivation (produce structure from rule consequent)
- Inference chain construction
- Consistency checking (no contradictory conclusions)
- Inference scope delimitation (which structures participate)

#### 2.6.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Interpret structures as "propositions" or "beliefs" | NO_SEMANTICS violation |
| Apply "logical" rules beyond structural pattern matching | Semantic logic |
| Assess "strength" of inference | Implicit scoring |
| Reference: true, false, valid, sound, belief, knowledge | Logical/epistemic vocabulary |
| Use "common sense" or "background knowledge" | External knowledge |
| Infer "meaning" from structural patterns | NO_SEMANTICS violation |

**CRITICAL DISTINCTION:** This layer handles structural pattern entailment, NOT semantic logical reasoning. "Inference" here means: if structural pattern A is present, structural pattern B may be derived via rule R. No truth values are assigned.

#### 2.6.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| STRUCTURAL_CONSISTENCY | **New/Tightened** | No contradictory structural conclusions from same premises |
| INFERENCE_MONOTONIC | **New** | Adding premises never invalidates prior conclusions (within scope) |
| NO_SEMANTICS | **Reinforced** | Inference is pattern matching, not logical deduction |
| REVERSIBLE | **Loosened slightly** | Inference itself not invertible, but premise state preserved |

#### 2.6.5 Layer Output Form

- **Primary:** `inference_graph` — DAG of premise-sets to conclusions via rule applications
- **Secondary:** `consistency_certificate` — proof artifact of no structural contradictions
- **Tertiary:** `inference_scope_boundary` — which structures were in/out of scope

#### 2.6.6 Entry/Exit Conditions

**Entry Requirements:**
- Structural inference rule set loaded and validated
- Input structures must be in canonical form (Phase 9 normalized)
- Inference scope explicitly delimited

**Exit Conditions:**
- All applicable rules applied to fixpoint within scope
- Consistency check passed
- Inference graph complete and acyclic

#### 2.6.7 Failure Mode

- **On structural contradiction:** Emit `REASONING_CONTRADICTION`, identify conflicting conclusions, halt inference, require scope restriction or rule modification
- **On invalid rule application:** Emit `REASONING_RULE_VIOLATION`, reject that inference, continue with remaining rules
- **On semantic content in rules:** Immediate rejection, emit `REASONING_SEMANTICS_VIOLATION`

---

### Layer 7: PURPOSING

**Purpose:** Projects the substrate to reveal goal-structure alignment—how structures relate to declared purpose markers (NOT inferred intent).

#### 2.7.1 Influence Transform

- **Dominant Relations:** `PURPOSE_MARKER_ATTACHMENT`, `GOAL_STRUCTURE_ALIGNMENT`, `COMPLETION_CRITERION`
- **Suppressed Relations:** `INFERENTIAL`, `TEMPORAL`, `SPATIAL`
- **Influence Behavior:** Influence flows from purpose markers through aligned structures. Structures not connected to any purpose marker receive no influence in this projection.

#### 2.7.2 Allowed Structural Degrees of Freedom

- Purpose marker attachment (from predefined marker vocabulary)
- Alignment verification (structural check that structure satisfies marker criterion)
- Completion status update (INCOMPLETE → COMPLETE, based on structural predicate)
- Purpose scope delimitation
- Marker propagation through containment

#### 2.7.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Infer purpose from structure | NO_INTENT violation—purpose must be explicitly declared |
| Interpret markers as "desires" or "wants" | Psychological vocabulary |
| Assess "importance" of purposes | Implicit ranking |
| Reference: want, desire, wish, hope, intend, mean-to | Intent vocabulary |
| Create purpose markers not in vocabulary | NO_GENERATION violation |
| Evaluate "success" or "failure" beyond structural completion | Semantic evaluation |

**CRITICAL:** Purpose markers are structural tags declared by observer attachment. The substrate does not infer or interpret purpose—it only tracks declared markers and structural completion predicates.

#### 2.7.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| PURPOSE_DECLARED_ONLY | **New/Tightened** | All purpose markers must be explicitly attached, never inferred |
| COMPLETION_STRUCTURAL | **New/Tightened** | Completion criteria are structural predicates only |
| NO_INTENT | **Reinforced** | Purpose is marker, not psychological state |
| REVERSIBLE | Unchanged | Marker attachment/detachment invertible |

#### 2.7.5 Layer Output Form

- **Primary:** `purpose_alignment_map` — relation of (purpose_marker_id, structure_id, alignment_status)
- **Secondary:** `completion_status_set` — set of (purpose_marker_id, COMPLETE|INCOMPLETE)
- **Tertiary:** `unaligned_structure_set` — structures with no purpose marker connection

#### 2.7.6 Entry/Exit Conditions

**Entry Requirements:**
- At least one purpose marker attached (or explicit `NO_PURPOSE` declaration)
- Completion predicates defined for all markers
- Purpose marker vocabulary loaded and frozen

**Exit Conditions:**
- All markers have alignment status computed
- Completion status determined for all markers
- No `PENDING_ALIGNMENT` states

#### 2.7.7 Failure Mode

- **On purpose inference attempted:** Emit `PURPOSING_INFERENCE_VIOLATION`, reject operation, require explicit marker
- **On undefined completion predicate:** Emit `PURPOSING_PREDICATE_MISSING`, marker remains INCOMPLETE, log warning
- **On marker vocabulary violation:** Emit `PURPOSING_VOCABULARY_VIOLATION`, reject attachment

---

### Layer 8: META-OBSERVING

**Purpose:** Projects the substrate to reveal observation structure—how the substrate state is witnessed without modification.

#### 2.8.1 Influence Transform

- **Dominant Relations:** `OBSERVATION_POINT`, `WITNESS_ATTACHMENT`, `SNAPSHOT_BOUNDARY`
- **Suppressed Relations:** ALL modification-capable relations
- **Influence Behavior:** Influence flows FROM structures TO observation points only. Observation points NEVER propagate influence back into structures. This is strictly one-way.

#### 2.8.2 Allowed Structural Degrees of Freedom

- Observation point placement (declare where snapshots are taken)
- Snapshot capture (read-only copy of structure at observation point)
- Observation scope delimitation
- Snapshot comparison (structural diff between snapshots)
- Observation trace construction (sequence of snapshots)
- Witness report generation (structural summary, not interpretation)

#### 2.8.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Modify observed structures | Observation is read-only |
| Interpret observations as "understanding" | NO_SEMANTICS violation |
| Feed observations back as input | Breaks one-way flow |
| Reference: understand, comprehend, realize, perceive-meaning | Cognitive vocabulary |
| Assess observation "quality" or "depth" | Implicit measure |
| Use observations to guide modification | Authority violation |

#### 2.8.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| OBSERVATION_READ_ONLY | **New/Critical** | Observation never modifies substrate |
| ONE_WAY_FLOW | **New/Critical** | Information flows out only, never back in |
| SNAPSHOT_IMMUTABLE | **New** | Captured snapshots cannot be altered |
| NO_AUTHORITY | **Reinforced** | Meta-observation has zero authority |

#### 2.8.5 Layer Output Form

- **Primary:** `observation_trace` — sequence of (observation_point_id, timestamp_structural, snapshot_reference)
- **Secondary:** `structural_diff_set` — set of structural differences between consecutive snapshots
- **Tertiary:** `witness_report` — structural summary (counts, boundary states, marker presence—no interpretation)

#### 2.8.6 Entry/Exit Conditions

**Entry Requirements:**
- At least one observation point defined
- Observation scope delimited
- One-way flow enforcement verified

**Exit Conditions:**
- All observation points have captured at least one snapshot OR explicit `NO_OBSERVATION` marker
- Observation trace complete
- No modification side-effects detected (verified by structural hash comparison)

#### 2.8.7 Failure Mode

- **On modification detected during observation:** Emit `METAOBSERVING_MUTATION_VIOLATION`, invalidate all snapshots from that point, require re-observation
- **On feedback loop detected:** Emit `METAOBSERVING_FEEDBACK_VIOLATION`, immediate rejection, structural quarantine
- **On authority assertion from observation:** Emit `METAOBSERVING_AUTHORITY_VIOLATION`, reject, log for audit

---

### Layer 9: UNIFYING

**Purpose:** Projects the substrate to reveal equivalence and canonical structure—how distinct forms collapse to unified representations.

#### 2.9.1 Influence Transform

- **Dominant Relations:** `EQUIVALENCE`, `CANONICAL_REPRESENTATIVE`, `QUOTIENT_MEMBERSHIP`
- **Suppressed Relations:** `DISTINCTION`, `DIFFERENTIATION`, `INDIVIDUAL_IDENTITY`
- **Influence Behavior:** Influence is shared across equivalence classes. All members of an equivalence class receive identical influence; no member is distinguished from another.

#### 2.9.2 Allowed Structural Degrees of Freedom

- Equivalence class construction (group structures by structural equivalence relation)
- Canonical representative selection (deterministic choice of representative per class)
- Quotient structure construction (replace class members with representative)
- Equivalence relation refinement/coarsening
- Unification operation (merge two structures if equivalent)
- Canonical form normalization

#### 2.9.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Use "similarity" for equivalence | NO_SIMILARITY—equivalence is binary |
| Prefer representatives by "quality" | Implicit ranking |
| Interpret unification as "synthesis" or "integration" | Semantic overlay |
| Reference: same-meaning, identical-concept, unified-understanding | Semantic vocabulary |
| Use frequency to determine representative | Statistical criterion |
| Assess "degree of equivalence" | Equivalence is binary, not graded |

#### 2.9.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| EQUIVALENCE_BINARY | **New/Tightened** | Equivalence is yes/no, never partial |
| CANONICAL_DETERMINISTIC | **New/Tightened** | Same equivalence class always yields same representative |
| REVERSIBLE | Unchanged | Quotient can be expanded back to class members |
| TRANSITIVE_CLOSURE_COMPLETE | **New** | Equivalence relation must be fully closed |

#### 2.9.5 Layer Output Form

- **Primary:** `equivalence_partition` — partition of structures into equivalence classes
- **Secondary:** `canonical_map` — mapping from each structure to its canonical representative
- **Tertiary:** `quotient_structure` — simplified structure with classes replaced by representatives

#### 2.9.6 Entry/Exit Conditions

**Entry Requirements:**
- Equivalence relation defined (reflexive, symmetric, transitive)
- Canonical selection function defined and deterministic
- All structures in normal form (Phase 9 normalized)

**Exit Conditions:**
- Partition is complete (every structure in exactly one class)
- Canonical map is total and deterministic
- Quotient structure constructed OR explicit `NO_QUOTIENT` marker

#### 2.9.7 Failure Mode

- **On non-transitive equivalence detected:** Emit `UNIFYING_TRANSITIVITY_VIOLATION`, reject partition, require relation repair
- **On non-deterministic canonical selection:** Emit `UNIFYING_DETERMINISM_VIOLATION`, halt, require selection function fix
- **On similarity-based criterion detected:** Emit `UNIFYING_SIMILARITY_VIOLATION`, reject, enforce binary equivalence

---

### Layer 10: ABSOLVING

**Purpose:** Projects the substrate to reveal commitment release—how structural obligations can be discharged.

#### 2.10.0 Dual Option Treatment

Absolving requires special treatment due to its potential to affect reversibility. Two options are provided:

---

#### OPTION A: Absolving as Optional Terminal Layer (Within Substrate)

##### 2.10.A.1 Influence Transform

- **Dominant Relations:** `COMMITMENT_RELEASE`, `OBLIGATION_DISCHARGE`, `CONSTRAINT_RELAXATION`
- **Suppressed Relations:** `ALL_CONSTRUCTIVE_RELATIONS` — no new structure can be built
- **Influence Behavior:** Influence flows toward release points. Structures marked for absolution cease to propagate influence but remain structurally present (tombstoned).

##### 2.10.A.2 Allowed Structural Degrees of Freedom

- Commitment marker removal (detach obligation markers)
- Constraint relaxation (loosen but not delete constraints)
- Reference tombstoning (mark structure as "released" without deletion)
- Absolution scope delimitation
- Release trace recording
- Reversibility checkpoint creation (mandatory before any absolution)

##### 2.10.A.3 Hard Prohibitions

| MUST NEVER | Rationale |
|------------|-----------|
| Delete structures permanently | Reversibility violation |
| Interpret absolution as "forgiveness" or "erasure of meaning" | NO_SEMANTICS violation |
| Absolve without reversibility checkpoint | Irreversibility risk |
| Reference: forgive, forget, erase-meaning, let-go-of-significance | Psychological/semantic vocabulary |
| Absolve structures with active influence paths | Would create dangling references |
| Allow absolution to propagate automatically | Must be explicit per-structure |

##### 2.10.A.4 Invariants Tightened/Loosened

| Invariant | Status | Reason |
|-----------|--------|--------|
| REVERSIBILITY_CHECKPOINTED | **New/Critical** | Checkpoint mandatory before any absolution |
| TOMBSTONE_PRESERVES_STRUCTURE | **New** | Released structures remain, just inactive |
| NO_CASCADING_ABSOLUTION | **New** | Absolution is per-structure, not transitive |
| NO_SEMANTICS | Unchanged | Release is structural, not meaningful |
| EXPLICIT_ONLY | **New/Tightened** | Every absolution requires explicit declaration |

##### 2.10.A.5 Layer Output Form

- **Primary:** `absolution_trace` — sequence of (structure_id, commitment_released, checkpoint_reference)
- **Secondary:** `tombstone_set` — set of structure_ids marked as released
- **Tertiary:** `reversibility_checkpoint` — complete snapshot enabling full restoration

##### 2.10.A.6 Entry/Exit Conditions

**Entry Requirements:**
- Reversibility checkpoint created and verified
- No active influence paths to structures marked for absolution
- Absolution scope explicitly delimited
- Observer confirmation required (cannot be automatic)

**Exit Conditions:**
- All targeted structures tombstoned OR absolution explicitly cancelled
- Absolution trace complete
- Checkpoint verified restorable
- No structural integrity violations

##### 2.10.A.7 Failure Mode

- **On checkpoint missing/invalid:** Emit `ABSOLVING_CHECKPOINT_VIOLATION`, reject all absolution operations
- **On active influence path detected:** Emit `ABSOLVING_ACTIVE_PATH_VIOLATION`, reject that structure's absolution
- **On cascading absolution attempted:** Emit `ABSOLVING_CASCADE_VIOLATION`, halt, require explicit per-structure marking

##### 2.10.A.8 What It Does Structurally

Absolving (Option A) creates a "soft delete" mechanism where structures are marked as released from obligations without being removed. The structure remains for audit, the checkpoint enables restoration, but the structure no longer participates in influence propagation.

##### 2.10.A.9 Why It May Be Necessary

- Allows long-running structural processes to release completed obligations
- Prevents unbounded growth of active commitment sets
- Enables "completion" semantics without irreversible deletion
- Supports observer-driven lifecycle management

##### 2.10.A.10 Why It May Be Dangerous

- Creates potential for "zombie" structures (tombstoned but referenced)
- Checkpoint storage may grow unboundedly
- Risk of checkpoint-absolution desynchronization
- Observer confirmation requirement may be bypassed if not enforced

##### 2.10.A.11 Minimal Invariant Set That Must Hold

1. **CHECKPOINT_INTEGRITY:** Checkpoint must be restorable at any time
2. **TOMBSTONE_IMMUTABLE:** Once tombstoned, structure cannot be un-tombstoned without full restoration
3. **EXPLICIT_DECLARATION:** No implicit or automatic absolution
4. **AUDIT_TRAIL:** Complete trace of all absolution operations
5. **NO_DANGLING:** No active references to tombstoned structures

---

#### OPTION B: Absolving as Observer-Only Action (Outside Substrate)

##### 2.10.B.1 Definition

Absolving is NOT a substrate layer. It is an action performed entirely by an external observer on their own records, with no effect on the deterministic substrate.

##### 2.10.B.2 What It Does Structurally

Nothing. The substrate is unmodified. The observer maintains their own shadow state that tracks which substrate structures they consider "absolved" for their purposes. This shadow state has zero authority and zero influence on substrate operations.

##### 2.10.B.3 Observer Attachment Declaration

```
OBSERVER_ABSOLUTION_DECLARATION:
  observer_id: [unique identifier]
  substrate_snapshot_reference: [hash of substrate state]
  absolved_structure_ids: [list of structure_ids]
  observer_rationale: [opaque string, not parsed by substrate]
  timestamp: [observer's timestamp, not substrate time]
```

This declaration is stored OUTSIDE the substrate, in observer-controlled storage.

##### 2.10.B.4 Why It May Be Necessary

- Allows observers to manage their own commitment tracking without substrate modification
- Preserves substrate integrity absolutely
- Enables multiple observers to have different absolution states
- Cleanly separates structural truth from observer interpretation

##### 2.10.B.5 Why It May Be Dangerous

- Observers may desynchronize from substrate state
- "Absolved" structures in observer state may still be active in substrate
- No enforcement mechanism if observer acts on "absolved" assumption
- May create false sense of completion

##### 2.10.B.6 Minimal Invariant Set That Must Hold

1. **SUBSTRATE_UNCHANGED:** Substrate state is bitwise identical before and after observer absolution
2. **ZERO_AUTHORITY:** Observer absolution cannot influence any substrate operation
3. **SNAPSHOT_REFERENCED:** Observer must reference specific substrate snapshot (prevents drift)
4. **OBSERVER_ISOLATED:** Each observer's absolution state is independent

##### 2.10.B.7 Substrate Interface for Option B

The substrate provides only:
- Read-only snapshot capability (same as Layer 8 Meta-Observing)
- Structure_id enumeration
- Hash verification for snapshot references

The substrate does NOT provide:
- Absolution markers
- Release operations
- Tombstoning
- Any write interface for absolution

---

## 3. Cross-Layer Consistency Rules

1. **Derivation Rule:** No layer may introduce structural fields not derivable from Phase 1b-9 artifacts. All fields must trace to: acoustic units, modifiers, boundaries, fold states, graph nodes/edges, or rewrite traces.

2. **Monotonic Restriction:** As layer number increases (Acting → Absolving), the set of modification-capable operations must monotonically decrease. Layer 8+ are read-only except for Option A Absolving's tombstoning.

3. **Influence Dominance Exclusivity:** No two layers may have the same dominant relation set. If layers share a dominant relation, one must suppress what the other dominates.

4. **Prohibition Inheritance:** Hard prohibitions accumulate across layers. A prohibition in Layer 3 remains in effect for Layers 4-10.

5. **Invariant Tightening Direction:** Invariants may only be tightened, never loosened, except for REVERSIBLE which has controlled loosening in Layers 6 and 10A.

6. **Vocabulary Closure:** The combined vocabulary of all layer prohibitions is closed. No layer may add to the prohibited vocabulary of a lower layer.

7. **Output Form Compatibility:** Layer N's output forms must be consumable as Layer N+1's entry conditions. No layer may produce output that subsequent layers cannot structurally validate.

8. **Failure Mode Consistency:** All layers fail closed. No layer may have a "degraded output" mode. Partial results must be explicitly marked.

9. **Observer Attachment Boundary:** Interpretation, meaning assignment, semantic classification, and intent attribution may ONLY occur via explicit observer attachment declarations, never within layer operations.

10. **Determinism Preservation:** No layer may introduce non-determinism. Same input + same projection = bitwise identical output, verified by hash comparison.

11. **Reversibility Chain:** Layers 1-9 must maintain full reversibility chains. For any state S reached through layer projection, there must exist an inverse projection returning to the source state.

12. **Authority Flow:** Authority (ability to affect routing/gating) exists only in authoritative phases (PO1-P21), never in layer projections. Layers are observational/structural only.

13. **No Cross-Layer Influence:** A projection through Layer N cannot influence how Layer M (M ≠ N) operates. Layers are independent lenses on the same substrate.

14. **Checkpoint Synchronization:** Any layer creating checkpoints (especially Layer 10A) must synchronize with the substrate's canonical state hash, not a stale reference.

15. **Audit Completeness:** Every layer transition must produce an audit record containing: source layer, target layer, structural hash before, structural hash after, operation trace.

---

## 4. Audit Plan: Verifying Structural (Non-Semantic) Compliance

### 4.1 Checklist for Each Layer Specification

| Check ID | Question | Pass Criterion | Failure Indicator |
|----------|----------|----------------|-------------------|
| A1 | Does the Influence Transform reference only structural relations? | All relations are graph-theoretic (adjacency, containment, membership, etc.) | Relations include: "meaning", "relevance", "importance", "similarity" |
| A2 | Are Allowed Operations purely structural? | Operations are: partition, fold, tag, boundary, rewrite, canonicalize | Operations include: "interpret", "classify-by-meaning", "score", "rank" |
| A3 | Is the Prohibition list complete and enforceable? | Each prohibition maps to a detectable structural pattern | Prohibitions are vague ("avoid semantics") without detection criteria |
| A4 | Do Invariants have structural definitions? | Each invariant is expressible as a structural predicate | Invariants reference: "correctness", "validity", "truth" |
| A5 | Are Output Forms purely structural types? | Types are: graph, set, relation, sequence, map, partition, trace | Types include: "meaning-vector", "semantic-frame", "interpretation" |
| A6 | Are Entry/Exit Conditions structural checks? | Conditions are: presence/absence of markers, boundary states, hash matches | Conditions include: "well-understood", "meaningful", "coherent" |
| A7 | Does Failure Mode fail closed with structural error? | Errors emit structural codes, halt, no degraded output | Failures produce "best effort" or "partial interpretation" |

### 4.2 Automated Verification Procedures

1. **Vocabulary Scan:** Parse layer specification for prohibited terms. Flag any occurrence of: meaning, semantic, interpret, understand, believe, intend, want, similar, score, weight, probability, likelihood, prefer, importance, relevance, quality.

2. **Relation Type Check:** Extract all relation names from Influence Transform. Verify each relation is defined in the Phase 9 graph schema or is a standard graph-theoretic relation (adjacency, reachability, containment, membership, equivalence).

3. **Operation Signature Check:** Extract all operations from Allowed Degrees of Freedom. Verify each operation has a purely structural signature: input is structural artifact, output is structural artifact, no semantic parameters.

4. **Invariant Formalization:** For each invariant, require a formal predicate in first-order logic over structural terms. If the predicate cannot be written without semantic vocabulary, the invariant fails audit.

5. **Output Type Derivation:** For each output form, trace its fields back to Phase 1b-9 artifacts. Every field must have a derivation path. Underivable fields fail audit.

6. **Cross-Reference Consistency:** Verify that dominant relations in Layer N do not appear in suppressed relations of Layer N-1 unless explicitly justified by layer transition semantics.

7. **Prohibition Coverage:** For each layer's prohibitions, verify that the prohibited vocabulary does not appear in that layer's other sections (Influence Transform, Operations, Output Forms, etc.).

### 4.3 Manual Review Checklist

- [ ] Read each Influence Transform aloud. Does it sound like graph theory or like cognitive science? (Must be graph theory.)
- [ ] For each prohibition, ask: "How would a code reviewer detect violation?" (Must have concrete answer.)
- [ ] For each invariant, ask: "Can this be checked by a deterministic function?" (Must be yes.)
- [ ] For the Failure Mode, ask: "What happens to the user if this fails?" (Must be: operation rejected, no output, explicit error.)
- [ ] For Absolving (either option), ask: "Does this preserve the ability to restore prior state?" (Must be yes for Option A, N/A for Option B.)

### 4.4 Certification Statement

A layer specification is CERTIFIED STRUCTURAL if and only if:
1. All A1-A7 checks pass
2. All automated verification procedures pass
3. Manual review checklist is complete with no semantic leakage detected
4. Specification is signed by at least one reviewer with substrate architecture familiarity

---

## Appendix: Prohibited Vocabulary Master List

The following terms MUST NOT appear in any layer specification except within the Hard Prohibitions section as items being prohibited:

### Semantic/Cognitive Vocabulary
meaning, semantic, interpret, understand, comprehend, realize, know, believe, think (as cognition), perceive (as understanding), concept, idea, insight, reasoning (as logic), logic (as truth-preserving), true, false, valid, sound, correct, incorrect

### Intent/Psychological Vocabulary
intend, intent, want, desire, wish, hope, goal (inferred), aim (inferred), purpose (inferred), plan (as intention), prefer, choose (by preference), decide (by preference), feel, emotion, mood, attitude

### Scoring/Ranking Vocabulary
score, rank, weight, priority, importance, relevance, quality, better, worse, optimal, best, likelihood, probability, frequency, common, rare, typical, similar, different (as degree), distance (as similarity), cluster, centroid, embedding

### Generation Vocabulary
generate, create (de novo), invent, imagine, synthesize (as creation), produce (unconstrained), hallucinate

---

*End of Specification*
