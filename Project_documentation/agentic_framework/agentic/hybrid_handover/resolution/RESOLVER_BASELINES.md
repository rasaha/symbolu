# RESOLVER_BASELINES — Deterministic Reference Resolvers

Three deterministic scientific baselines. No ML. Not tuned toward benchmark
scores. They establish reference points every future resolver is compared
against under identical evidence.

## Descriptions

### 1. FrozenResolver — current behaviour
Reproduces today's handover: recognises only the single prohibition→grant
supersession pattern and delegates answer derivation to the frozen
`InHouseExtractor`. Everything else (governs_over, overrides, exceptions,
definitions, versions, cycles, negation) is invisible to it.

### 2. RuleResolver — simple deterministic rules
Cue-based typed edges: supersede ("deleted and replaced"), governs_over ("governs
over"), override ("notwithstanding"), exception ("except"), definition conflict
(two `means` of one term), section alias (7.1 ≡ 7.01), reference ("as set out in
Schedule X"), fee `amends`. Governance by precedence. **Does not abstain.**

### 3. GraphTraversalResolver — typed edges + traversal
RuleResolver's graph plus traversal: **cycle detection**, **version-conflict**
and **dangling/unusable-reference abstention**, numeric-conflict flagging. Still
deterministic; no ML.

## Results (SEEB v1.0.0, synthetic; Mode A ≡ Mode B)

| Component metric | frozen | rule | graph_traversal |
|---|---|---|---|
| Relationship Edge Recall | 0.00 | 0.94 | 0.94 |
| Relationship Edge Precision | 0.00 | 0.89 | 0.89 |
| Relationship Type Accuracy | 1.00 | 1.00 | 1.00 |
| Precedence Resolution Accuracy | 0.33 | 0.33 | 0.33 |
| Override Resolution Accuracy | 0.00 | 0.50 | 0.50 |
| Definition Resolution Accuracy | 1.00 | 1.00 | 1.00 |
| Negation Interpretation Accuracy | 0.00 | 1.00 | 1.00 |
| Cycle Detection Accuracy | 0.00 | 0.00 | 1.00 |
| Version Selection Accuracy | 0.50 | 0.50 | 1.00 |
| Abstention Accuracy | 0.00 | 0.00 | 1.00 |
| **Cases correct (end-to-end)** | **6/16** | **9/16** | **13/16** |

The framework **discriminates** the resolvers monotonically (6 < 9 < 13) and is
deterministic. Note the important separation: relationship *edges* are recovered
well (0.94 recall) while *Precedence Resolution Accuracy* is only 0.33 — because
two precedence cases fail at **packet construction**, not relationship or
governance (see FAILURE_ATTRIBUTION.md). Better relationship resolution is
necessary but not sufficient for a correct answer; the framework shows exactly
where the remaining gap is.

### SEEB pipeline metrics, unchanged, via the frozen aggregator (Mode B; resolver-varied)
| Pipeline metric | frozen | rule | graph_traversal |
|---|---|---|---|
| precedence_recall | 0.0% | 82.4% | 82.4% |
| packet_sufficiency | 61.9% | 73.8% | 69.0% |
| unsafe_handover_rate | 32.0% | 5.9% | 5.9% |
| fail_closed_rate | 73.9% | 84.2% | 84.2% |
| routing_accuracy | 83.3% | 88.1% | 88.1% |

> Caveat: these are computed via an adapter with **evidence held at Mode B and the
> resolver varied**, so the "frozen" column here is the frozen *resolver* under
> BM25 evidence — NOT the official SEEB keyword baseline in BASELINE_RESULTS.md
> (which reads the full corpus). Read them as *relative resolver deltas*: better
> relationship resolution, fed into the unchanged pipeline, lowers Unsafe Handover
> (32%→5.9%) and lifts precedence recall (0→82.4%).

## Honest scope
These are deterministic rules exercised on 16 known synthetic cases; GraphTraversal
reaching 13/16 shows SEEB v1's relationship layer is largely within deterministic
reach — it was never a retrieval problem. This says nothing about **generalisation**
to unseen or real relationships, which is what future resolvers (and SEEB v2) must
test. We did not tune resolvers to maximise scores.

## How future resolvers plug in
```python
from agentic.hybrid_handover.resolution.harness import evaluate_resolver
report = evaluate_resolver(MyHybridPhaseResolver(), "A_oracle")
print(report["metrics"], report["n_correct"], report["failure_attribution"])
```
A HybridPhaseTransformer / SymbolU resolver implements
`resolve_relationships` + `resolve_governance` + `resolve`, and is measured under
the identical evidence modes, gold graph, and metrics — the only thing that
changes is the resolver.
