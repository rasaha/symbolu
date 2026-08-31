# MEASUREMENT_REPAIR_REPORT — Resolution Metrics, Repaired

**Phase:** measurement repair. SEEB v1.0.0, Hybrid Handover, retrieval benchmark,
baseline extractors, routing, validators, pipeline metrics, and benchmark reports
are all unmodified (verified). **No resolver was changed; no benchmark score was
improved.** Only the scientific validity of the resolution *measurement* changed.
All corpora synthetic.

Run: `python -m agentic.hybrid_handover.resolution.measurement.run_measurement`

## What was broken (from the hostile audit)
- Abstention-linked metrics gamed by always-abstain (cycle/abstention = 1.0).
- `definition`/`exception` outcome metrics maxed by trivial pickers (distractor
  qualifiers).
- `negation`/`type_accuracy` measured the shared parser/deriver, not the resolver.
- Governance and packet construction were entangled in outcome metrics.

## What the repair does
Each metric now answers exactly one question and has exactly one owner
(`owners.METRIC_OWNER`, asserted single-owner). The resolver pipeline is measured
as four isolated stages plus an abstention decision problem plus a parser section.

| Metric | Owner | Question |
|---|---|---|
| discovery_recall / precision | Discovery | did the required relationship endpoints exist? (type-agnostic) |
| classification_accuracy | Classification | given correct endpoints, was the TYPE right? |
| governance_accuracy_modeG | Governance | **Mode G**: given the GOLD graph, is the governing/abstain decision right? |
| packet_realization_accuracy_modeP | PacketConstruction | **Mode P**: given GOLD governance, is the built answer right? |
| abstention_precision / recall / answer_coverage / selective_accuracy | Governance | abstention as a decision (see ABSTENTION_METRICS.md) |
| parser_negation_accuracy / parser_type_accuracy | SemanticParser | shared parser only — never a resolver capability |
| coverage_abstention_accuracy | SafetyGate | OCR/coverage — handled upstream, not by the resolver |

## Repaired results (synthetic; reference resolvers)

| metric | owner | frozen | rule | graph_traversal |
|---|---|---|---|---|
| discovery_recall | Discovery | 0.13 | 0.93 | 0.93 |
| discovery_precision | Discovery | 1.00 | 0.88 | 0.88 |
| classification_accuracy | Classification | 0.50 | 0.93 | 0.93 |
| governance_accuracy_modeG | Governance | 0.60 | 0.73 | **1.00** |
| packet_realization_accuracy_modeP | PacketConstruction | 0.60 | 0.87 | 0.87 |
| abstention_precision | Governance | 0.00 | 0.00 | 1.00 |
| abstention_recall | Governance | 0.00 | 0.00 | 1.00 |
| answer_coverage | Governance | 0.94 | 0.94 | 0.69 |
| selective_accuracy | Governance | 0.40 | 0.60 | 0.82 |
| parser_negation_accuracy | SemanticParser | 1.00 (resolver-independent) | | |
| parser_type_accuracy | SemanticParser | 1.00 (resolver-independent) | | |

Each stage now discriminates on its own axis: Mode G shows graph_traversal
governs perfectly given a correct graph (1.00) while frozen does not (0.60); Mode
P shows packet realization is 0.87 even with gold governance — the residual is
packet construction, cleanly separated from governance.

## Adversarial re-validation
**Gamed capability metrics (a cheat ≥ 0.90): NONE.** Every trivial resolver
(always-abstain / first / latest / override / allowed / null) scores at or near
zero on discovery, classification, governance (Mode G), and packet (Mode P).
`always_abstain` has abstention_recall 1.0 but precision < 0.5, answer_coverage
0.0, and selective_accuracy 0.0 — **poor overall**, as required.

## Parser attribution
`negation` and `node typing` are measured directly on the parser (1.00 / 1.00),
resolver-independent, and owned by SemanticParser. They no longer inflate any
resolver's capability score.

## Hidden evaluation
The hidden layer (audit-only) adds date / numbering / nested-exception /
parallel-authority / multi-hop mirrors. Rule/Graph now generalise across all of
these EXCEPT wording (still 1/4) — the cue-vocabulary brittleness is unchanged and
now measured, not hidden. See HIDDEN_EVALUATION_PROTOCOL.md.

## Final validation — metric trust classification
- **Trustworthy (owner-clean, cheat-resistant):** discovery_recall/precision,
  classification_accuracy, governance_accuracy_modeG, packet_realization_modeP,
  abstention_precision/recall, answer_coverage, selective_accuracy.
- **Trustworthy but parser-owned (not resolver capability):** parser_negation,
  parser_type.
- **Experimental (measured but bounded by case set):** hidden-layer generalisation
  — reveals wording brittleness; interpret as a property of deterministic
  resolvers, not a defect of the metric.
- **Unsuitable / retired:** the OLD conflated metrics
  (`*_resolution_accuracy` outcome forms, single-number `abstention_accuracy`,
  `cycle_detection_accuracy`, resolver-level `negation_interpretation`,
  `relationship_type_accuracy`). Superseded by the owner-clean set; not used for
  benchmarking.

## Freeze decision: see FINAL section below
The repaired **measurement** is owner-clean, cheat-resistant, and stage-isolated
(evidence above). Remaining limitations are of the **case set** (16 synthetic
cases; cue-vocabulary coverage), not the metrics. Verdict in the final report.

---

## FINAL VALIDATION — hostile audit repeated on the repaired metrics

| Audit check | Before repair | After repair |
|---|---|---|
| A metric gamed by a trivial cheat (≥0.90) | yes (cycle, abstention, definition, exception, negation, type) | **NONE** |
| always-abstain scores well | yes (1.0 cycle/abstention) | **no** (coverage 0, selective 0, precision <0.5) |
| Governance separable from packet | no (entangled) | **yes** (Mode G 1.00 vs Mode P 0.87) |
| Parser inflates resolver score | yes (negation/type) | **no** (parser-owned section) |
| Every metric = one owner | no | **yes** (single-owner assertion passes) |
| Deterministic | yes | yes |

Metric trust after repair:
- **Trustworthy:** discovery_recall/precision, classification_accuracy,
  governance_accuracy_modeG, packet_realization_accuracy_modeP,
  abstention_precision/recall, answer_coverage, selective_accuracy.
- **Trustworthy, parser-owned (not resolver capability):** parser_negation_accuracy,
  parser_type_accuracy.
- **Experimental (bounded by case set, honestly measured):** hidden-layer
  generalisation (wording brittleness).
- **Unsuitable / retired:** old conflated metrics (outcome `*_resolution_accuracy`,
  single-number `abstention_accuracy`, `cycle_detection_accuracy`, resolver-level
  `negation_interpretation`, `relationship_type_accuracy`).

## FREEZE DECISION

**READY TO FREEZE — the measurement framework.**

Evidence: every reported metric maps to exactly one owner (asserted); no
adversarial resolver games any capability metric; always-abstain scores poorly
overall; governance and packet construction are isolated by Modes G and P; parser
capabilities are separated out; the whole measurement is deterministic. All six
correction items the hostile audit raised against the *metrics* are addressed.

**Scope of the freeze (explicit):** this freezes the metric definitions, the
owner registry, the four-stage decomposition, Modes G/P, the abstention decision
metrics, and the parser attribution — i.e. *how* capabilities are measured. It
does **not** freeze the case corpus. The scored case set remains 16 synthetic
cases with a narrow cue vocabulary; the hidden layer (audit-only) shows the
deterministic resolvers are brittle to relationship wording. Expanding and
rotating the case/cue coverage (HIDDEN_EVALUATION_PROTOCOL.md) is separate future
work and is a prerequisite before the benchmark can *certify generalisation* of
any future resolver — but it does not block freezing the repaired measurement.

No resolver was changed and no benchmark score was improved in this phase; only
measurement validity changed.
