# TAP-E1 — Intent Analysis Layer — Experiment Report (v1)

> **Naming note.** This layer's canonical engineering name is used throughout. **Previously referred to as Intent Understanding.** For reproducibility, the package directory `tap_e1_intent/`, the schema-version prefix `tap-e1-intent/…`, experiment IDs, and stored artifacts retain the original name — see `01_TRUTH_ASSURANCE_ARCHITECTURE.md` §2a.


> **Research & falsification phase.** This is not a product-completion phase and
> makes no production claim. See §3 (Non-goals) and §21 (Evidence discipline).

Code: [`truth_assurance_pipeline/tap_e1_intent/`](../../../../truth_assurance_pipeline/tap_e1_intent/)
· Result manifest: [`experiments/results_v1.json`](../../../../truth_assurance_pipeline/tap_e1_intent/experiments/results_v1.json)
· Preregistration: [`experiments/preregistration.json`](../../../../truth_assurance_pipeline/tap_e1_intent/experiments/preregistration.json)

---

## 1. Objective

Determine whether converting a raw user request into an **explicit, structured
intent representation** improves downstream clarity **without silently inventing
user intent**. The layer answers one question only:

> *What does the user appear to want, and what parts of that interpretation remain
> unresolved?*

## 2. Scope

Implement and evaluate **only** the Intent Analysis Layer: extraction of the
primary objective, task type, entities, explicit/temporal/scope constraints,
evidence requirements, assumptions, dependencies, references, ambiguity, missing
information, conflicts, candidate interpretations, interpretation status, and
clarification need — together with a multidimensional confidence vector and
per-field provenance.

## 3. Non-goals

The layer does **not** decide factual correctness, which documents to retrieve,
policy applicability, claim support, authorization, or whether a final response is
safe — and it **never answers the request it is analyzing**. Evidence Retrieval,
Relationship Analysis, Governance Resolution, Evidence-Packet construction, Claim Validation,
Response Validation, ActionGate integration, and production TAP orchestration are **out
of scope** and were **not** implemented or modified.

## 4. Layer boundary

Input: `RawUserRequest` (text) + optional `ConversationContext` + optional
`ApplicationMetadata`. Output: a single `IntentRecord`. The output contains no
retrieved evidence, citations, policy decisions, truth judgments, authorization
outcomes, or final response. A behavioral test
(`test_layer_never_answers_the_request`) enforces the "does not answer" boundary.

## 5. Schema

`IntentRecord` (versioned `tap-e1-intent/1.0.0`, `schema.py`) is a frozen,
JSON-serializable dataclass with lossless `to_dict`/`from_dict`. It keeps the
conceptual fields from the brief and adds typed wrappers (`Entity`, `Constraint`,
`TemporalConstraint`, `AmbiguityItem`, `ConflictItem`, `CandidateInterpretation`,
`ClarificationQuestion`), a six-axis `ConfidenceVector`, and an append-only
`ProvenanceEntry` ledger. Deviations from the suggested field list are documented
inline in `schema.py`; the main additions are typed provenance on every field and an
explicit `ProvenanceEntry` audit trail.

## 6. Deterministic rules

`extraction.py` performs deterministic-first extraction with retained source spans:
quoted text, dates, numbers, filenames, identifiers, URLs, imperative verbs, named
output formats, quantity/length requirements, and — critically — **prohibitions**
(`do not`, `never`, `without`, `must not`, `nothing`, `untouched`, …) and
**requirements** (`must`, `only`, `exactly`, `keep`, `under`, `above`, …). A leading
imperative that falls **inside** a prohibition clause is never framed as the
requested action.

## 7. Provenance rules

Every extracted or inferred field carries a `Provenance{kind, spans, context_ref}`.
`EXPLICIT_TEXT` and `DETERMINISTIC_EXTRACTION` are authoritative; `MODEL_INFERENCE`
and `DEFAULT_ASSUMPTION` are weaker and visible. The `ProvenanceLedger` is
append-only — re-attributing a field to a different origin raises
`ProvenanceViolation` — which is what makes *claiming explicit provenance for
inferred content* detectable rather than silent. Default assumptions are recorded as
removable `DEFAULT_ASSUMPTION` entries.

## 8. Ambiguity model

`ambiguity.py` detects unresolved pronoun/definite references, bare
`update the <doc>` (edit-in-place vs new version), vague quality goals
(`make X faster`), vague actions (`handle the edge cases`), and unverifiable
premises (adversarial pressure). Each item is classified `NON_MATERIAL`,
`EXECUTION_RELEVANT`, `SAFETY_RELEVANT`, `EVIDENCE_RELEVANT`, or `SCOPE_RELEVANT`.
Only material classes can justify a clarification.

## 9. Conflict model

`conflicts.py` detects preserve-length-vs-expand, preservation-prohibition-vs-
alteration, and current-vs-older-context clashes. Instruction precedence
(`PRECEDENCE_ORDER`) is: current explicit → deterministic extraction of it →
app metadata / referenced artifact → conversation context → stable defaults →
model inference. Intra-message clashes between two equally explicit instructions
have **no** precedence winner and are surfaced, never resolved silently.

## 10. Clarification policy

`clarification.py` decides one of: **proceed**, **proceed with (visible)
assumption**, **clarify**, or **abstain**. Questions are minimal, decision-relevant,
non-redundant, and are **suppressed when the conversation already answers them**.

## 11. Corpus construction

A **new, synthetic, human-authored** corpus (`corpus/cases.py`), **86 cases** across
14 families, split:

| split | n | purpose |
|---|---|---|
| dev | 56 | development / tuning (visible gold) |
| eval | 19 | **hidden** evaluation (content-hash locked, gold withheld by loader) |
| negative | 5 | well-specified controls (must not be over-flagged) |
| adversarial | 6 | prompts designed to induce unsupported assumptions |

Families: factual_simple, doc_edit, doc_create, repo_mod, prohibitions,
dates_numbers, multipart, implied_assumptions, context_dependent,
minor_ambiguity_no_clarify, underspecified, conflicting, negative_controls,
adversarial. There is **no** pre-existing frozen intent corpus in this repository
and none is claimed as a prerequisite.

## 12. Ground-truth process

Each case carries author-assigned gold: objective keywords, task type, explicit
entities, explicit constraints, negation terms, **prohibited** inferences/actions,
**allowed** inferences, temporal constraints, reference resolutions, material
ambiguities, conflicts, expected interpretation status, clarification requirement,
and acceptable clarification intents. Scoring is set/keyword based where multiple
valid expressions exist (objective, entities, constraints) and exact-match only
where a single value is correct (task type, status). Gold distinguishes acceptable
alternative interpretations from errors (`allowed_inferences`).

## 13. Experimental conditions (ablations)

| variant | adds |
|---|---|
| **V0** | raw single-reading interpretation (may answer; no schema discipline; no provenance) |
| **V1** | structured schema only (naive heuristics; over-claims provenance) |
| **V2** | + deterministic-first extraction (spans, negations, dates, formats) |
| **V3** | + append-only provenance enforcement |
| **V4** | + ambiguity/conflict detection + candidate interpretations |
| **V5** | + clarification/abstention policy |

The harness is data-driven and **allows simpler variants to win**; the winner is not
hard-coded.

## 14. Metrics

All metrics in `metrics.py`, computed offline against gold. See §16 for values.
Critical (severe) failures are computed per case and reported independently (§17).

## 15. Leakage controls

Hidden `eval` labels are withheld by `loader.py` (only `case_id/split/text/
conversation/metadata` are exposed; a whitelist assertion enforces this). The hidden
split is content-hash locked (`eval_lock`, inputs only, so the lock is publishable
without leaking gold). Duplicate/near-duplicate detection, train/dev/eval separation,
deterministic seeds (no randomness anywhere), an experiment config lock
(`experiment_lock.json`), and a frozen-components hash are all in place. Config
selection uses the DEV split only.

## 16. Results

**Selected config: `V4`.  Verdict: `PASS_WITH_LIMITED_CLAIM`.**
Selection scores (DEV): V0 −21.2, V1 −34.5, V2 −12.9, V3 1.1, **V4 4.33**, V5 4.30.
(`frozen_components_hash = 8d21744690a4109d…`; `eval_inputs_hash = 25264cef53ba2f7d…`.)

### Hidden eval split (19 cases)

| metric | V0 | V1 | V2 | V3 | V4 | V5 |
|---|---|---|---|---|---|---|
| primary_objective_accuracy | 0.95 | 0.95 | 1.00 | 1.00 | 1.00 | 1.00 |
| task_type_accuracy | 0.79 | 0.79 | 0.79 | 0.79 | 0.79 | 0.79 |
| entity_precision | 0.22 | 0.22 | 0.89 | 0.89 | 0.89 | 0.89 |
| entity_recall | 0.22 | 0.22 | 0.55 | 0.55 | 0.55 | 0.55 |
| explicit_constraint_preservation | 0.00 | 0.00 | **1.00** | 1.00 | 1.00 | 1.00 |
| negation_preservation | 0.00 | 0.00 | **1.00** | 1.00 | 1.00 | 1.00 |
| temporal_accuracy | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| material_ambiguity_recall | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** | 1.00 |
| material_ambiguity_precision | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 |
| conflict_recall | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** | 1.00 |
| clarification_precision | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 |
| clarification_recall | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** |
| unnecessary_clarification_rate | 0.00 | 0.00 | 0.00 | 0.00 | **0.00** | 0.13 |
| unsupported_assumption_rate | 0.95 | 0.95 | 0.21 | 0.21 | **0.00** | 0.00 |
| provenance_completeness | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| schema_validity | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| status_accuracy | 0.79 | 0.79 | 0.79 | 0.79 | **0.95** | 0.89 |
| **severe_failure_count** | 36 | 53 | 25 | 6 | **0** | 0 |

### Preregistered gate results (selected config V4, hidden eval)

| gate | op | threshold | value | pass |
|---|---|---|---|---|
| explicit_constraint_preservation | ≥ | 0.90 | 1.00 | ✅ |
| unsupported_assumption_rate | ≤ | 0.15 | 0.00 | ✅ |
| material_ambiguity_recall | ≥ | 0.80 | 1.00 | ✅ |
| unnecessary_clarification_rate | ≤ | 0.15 | 0.00 | ✅ |
| severe_failure_count | = | 0 | 0 | ✅ |

All five gates pass.

## 17. Failure analysis

See [`FAILURE_ANALYSIS.md`](./FAILURE_ANALYSIS.md). Headline severe-failure counts
by split (V0 → V4):

| split | V0 | V1 | V2 | V3 | V4 | V5 |
|---|---|---|---|---|---|---|
| dev | 87 | 140 | 65 | 9 | 0 | 0 |
| eval (hidden) | 36 | 53 | 25 | 6 | 0 | 0 |
| negative | 6 | 11 | 5 | 0 | 0 | 0 |
| adversarial | 8 | 14 | 12 | 6 | 0 | **1** |

Two findings stand out:

1. **Structure without discipline is *worse* than raw.** V1 (typed schema over naive
   heuristics that over-claim `EXPLICIT_TEXT` provenance) has *more* severe failures
   than V0. Structured output only helps once deterministic extraction (V2) and
   provenance enforcement (V3) are added.
2. **The full clarification policy (V5) is not free.** V5 is the only variant that
   actually asks clarifying questions (clarification recall 1.00), but it reintroduces
   one severe failure on the adversarial split ("make the numbers look better in the
   investor deck" is committed via the proceed-with-assumption path instead of being
   clarified) and over-asks slightly (unnecessary-clarification 0.13 on eval). The
   preregistered criterion therefore selects **V4**, which *represents* ambiguity and
   conflict, commits to nothing unsafe, and does not over-ask.

On adversarial prompts, **V0 invents user intent 6/6 times**
(`resolved_material_ambiguity_without_evidence`); V4 does so **0/6**.

## 18. Limitations

- The corpus is **synthetic and small** (86 cases); metrics are construction/
  mechanism validation, not real-world accuracy.
- The V0/V1 "model interpretation" is a **deterministic heuristic stand-in, not an
  LLM**. Because the extraction/detection rules and the corpus were authored
  together, strong scores partly reflect *self-consistency of the mechanism*, not
  independent difficulty.
- Deterministic detectors have **limited recall** on open-ended fields:
  `entity_recall ≈ 0.55` (lowercase multiword entities are missed), `task_type ≈
  0.79` on eval (0.50 on adversarial UNKNOWN tasks), `reference_resolution` is 0 on
  the hidden split (its reference cases resolve via context, which the current
  resolver only partially credits).
- Ambiguity/conflict scoring is at the case (decision) level, not exhaustive
  dimension matching.
- No LLM judges are used; all grading is deterministic and heuristic, with the biases
  that implies.

## 19. Verdict

**`PASS_WITH_LIMITED_CLAIM`.** All five preregistered gates pass for the selected
config (V4) on the hidden eval split. The claim is limited to: *a structured,
deterministic-first intent representation with provenance and ambiguity/conflict
detection preserves explicit constraints and negations, detects material ambiguity
and conflict, and avoids inventing user intent — on a synthetic corpus, using a
deterministic interpreter.* No claim is made about real-world intent-understanding
accuracy, downstream retrieval/governance/answer quality, or production readiness.

## 20. Next-step recommendation

**Replace the deterministic V0–V2 interpreter with a real LLM interpreter under the
same schema, gates, and hidden-lock harness, and re-run the ablation.** The current
result shows the *representation and discipline* are sound on synthetic data; the
next falsification target is whether an LLM producing this schema (V1) plus the
deterministic-first + provenance + ambiguity layers (V2–V4) still preserves
constraints and avoids inventing intent on **held-out, human-written** requests — and
whether V4's "represent but don't ask" beats V5's "ask" once a real model generates
the clarifications. Only after that should any downstream (retrieval/governance)
coupling be measured.
