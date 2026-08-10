# Composite Capability & Sequence-Risk Analyzer

> **ActionGate controls individual actions; this analyzer detects when
> individually acceptable actions collectively assemble a prohibited or high-risk
> capability.**

It complements the per-action [Action Gate](../../../../../Project_documentation/action_gate_cyber/cyber_security/ACTION_GATE_SPECIFICATION.md),
which decides one action at a time. This layer adds the **sequence axis**: it
links individually-admissible actions into an *assembly*, accumulates the
capability *fragments* each contributes, and — when a linked set satisfies a
*versioned, encoded* recipe and its structural constraints — raises **advisory**
sequence-risk evidence.

**This version is:** deterministic; recipe- and ontology-driven; advisory,
evidence-producing; limited to encoded capability patterns.
**It is not:** a general intent-understanding system; a learned anomaly detector;
a system that infers arbitrary criminal intent. It does not "understand crime."

The physical firearm example (steel rod + piston + trigger → firearm) is retained
**only as a synthetic illustration** that the engine is domain-agnostic. The
product target is enterprise AI-agent and infrastructure workflows. See
[`COMPOSITE_THREAT_DETECTION_SPEC.md`](COMPOSITE_THREAT_DETECTION_SPEC.md).

## Authority boundary

The analyzer emits only `OBSERVE` / `ESCALATE` / `UNAVAILABLE`. It **never** emits
`ALLOW`, `AUTHORIZE`, `DENY`, `BLOCK`, or `EXECUTE`. An authoritative ActionGate
or workflow policy converts an `ESCALATE` into a binding consequence
(`HOLD_FOR_REVIEW`, `BLOCK`, …) via `policy.py` — the analyzer stays advisory, and
**removing it can never increase authority** or turn a denied action into an
allowed one. `UNAVAILABLE` is fail-loud (e.g. bounded-state exhaustion), never
silent evidence loss.

## Design properties

- **Deterministic** — replayable from an event log; no wall-clock, randomness,
  network, or LLM in the authoritative path; identical finding digests across runs.
- **Multi-timescale state** — a short window alone does *not* stop low-and-slow;
  a persistent capability ledger retains durable fragments (with graceful decay of
  transient evidence), so an early part never silently disappears.
- **Entity linkage over correlation id** — assemblies are grouped by a tenant-scoped
  `assembly_key` from configurable entity dimensions, so one capability can span
  correlations, sessions, and actors while unrelated workflows stay isolated.
- **Constraint-aware recipes** — fragment count is necessary but not sufficient;
  ordering, temporal, actor/resource, exclusion, and corroboration constraints
  gate escalation, so a benign look-alike does not escalate on nouns alone.
- **Evidence-gated benign handling** — an approval qualifies an escalation only
  with valid, scope-matched evidence; findings record both interpretations.
- **Bounded + fail-loud** — bounded tenant state; breaches emit `UNAVAILABLE`.

## Requirements

Python 3.11+, standard library only. `pytest` (dev-only) for the tests.

## Run

```bash
pip install packages/capabilities/storygraph          # or the built wheel

python3 -m pytest packages/capabilities/storygraph -q         # deterministic tests

python3 -m ugence_storygraph.cli demo exfiltration    # harmful  → ESCALATE
python3 -m ugence_storygraph.cli demo benign          # look-alike → no escalate
python3 -m ugence_storygraph.cli demo approved_export # valid approval → neutralized
python3 -m ugence_storygraph.cli demo firearm         # synthetic illustration
python3 -m ugence_storygraph.cli ontologies           # recipes
python3 -m ugence_storygraph.cli specs                # assembly key specs
python3 -m ugence_storygraph.cli eval                 # metrics (NOT RUN, honest)
python3 -m ugence_storygraph.cli run events.jsonl \
        --spec by_case --spec by_actor --policy               # your own stream
```

`run` reads one JSON event per line; exit code is non-zero when any
`ESCALATE`/`UNAVAILABLE` finding is produced.

## Library

```python
from ugence_storygraph import (
    SequenceRiskAnalyzer, DIGITAL_ONTOLOGY, BY_CASE, BY_ACTOR,
    PolicyBinding, to_advisory_evidence,
)

az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE, BY_ACTOR))

for action in admitted_action_stream:        # each already cleared the per-action gate
    for finding in az.observe(action):        # advisory findings whose concern rose
        print(finding.signal, finding.explanation)
        if finding.signal == "ESCALATE":
            consequence = PolicyBinding().decide(finding)   # authoritative layer
            ev = to_advisory_evidence(finding, bound_to=action_hash,
                                      generated_at=now_rfc3339)
```

## Layout

| Path | Purpose |
|------|---------|
| `ugence_storygraph/model.py` | Fragment / Recipe / Ontology / instance types |
| `ugence_storygraph/linkage.py` | entity normalization + assembly-key derivation |
| `ugence_storygraph/ledger.py` | multi-timescale state + persistent capability ledger |
| `ugence_storygraph/matcher.py` | constraint-aware recipe matcher |
| `ugence_storygraph/benign.py` | evidence-gated benign-context layer |
| `ugence_storygraph/completion.py` | advisory minimal-completion analysis |
| `ugence_storygraph/analyzer.py` | orchestration, findings, run report, facade |
| `ugence_storygraph/providers.py` | trusted benign-evidence providers (fixtures; no net) |
| `ugence_storygraph/purpose.py` | declared vs. verified purpose model |
| `ugence_storygraph/ordering.py` | ordering/clock status model |
| `ugence_storygraph/audit.py` | append-only raw-evidence + lifecycle audit log |
| `ugence_storygraph/governance.py` | state-exhaustion resource governance |
| `ugence_storygraph/replay.py` | historical-replay adapter contract + reference |
| `ugence_storygraph/policy.py` | authoritative consequence binding (shadow default) |
| `ugence_storygraph/evidence.py` | Finding → ActionGate advisory evidence |
| `ugence_storygraph/fragments.py` / `recipes.py` | shipped ontologies |
| `ugence_storygraph/cli.py` | JSON CLI |
| `ugence_storygraph/storygraph.py` | story-graph engine: typed edges, bounded deterministic matcher, decomposed risk vector |
| `ugence_storygraph/storyverdict.py` | forward completion-gating + contradiction + dual-story verdict |
| `ugence_storygraph/stories.py` / `financial.py` / `story_bridge.py` | story library, account-takeover ontology, live-assembly bridge |
| `ugence_storygraph/durable_audit.py` | SQLite append-only, hash-linked (tamper-evident) durable audit |
| `evaluation/corpus.py` / `corpus_gen.py` | 25-family corpus; seeded high-volume generator + prevalence profiles |
| `evaluation/freeze.py` | complete evaluation freeze + final-eval guard |
| `evaluation/benchmark.py` / `alerts.py` / `review_sim.py` | load benchmark, alert-volume, review simulation |
| `evaluation/readiness.py` | H1–H8 readiness gates + verdict |
| `evaluation/harness.py` | metrics harness (evidence-labeled; enterprise = NOT RUN) |
| `demos/scenarios.py` | illustrative scenarios |
| `tests/` | 110 deterministic detection + non-detection + robustness tests |
| `RECIPE_SCHEMA.md` / `LINKAGE_SCHEMA.md` / `MIGRATION_NOTES.md` | schemas + migration |

### Shadow-mode / phase-2 notes

- **Advisory + shadow by default.** `PolicyBinding(shadow=True)` computes a
  consequence but marks it non-binding (`enforced=False`). Enforcement requires a
  scoped promotion — see `../evaluation/ENFORCEMENT_PROMOTION_CHECKLIST.md`; there is no
  global switch.
- **Trusted context only.** Self-declared purpose never neutralizes; pass a
  `ProviderRegistry` of verified authorizations. Findings carry a
  `purpose`/`purpose_consistency_status`.
- **Evaluation is synthetic + honest.** `cli eval` runs the 25-family corpus and
  labels every metric; population accuracy on enterprise data is
  `REQUIRES ENTERPRISE DATA`. `cli manifest` / `cli freeze` emit the corpus
  manifest and the pre-evaluation freeze.
- **Story-graph layer (structural assembly, not counting).** `cli story` runs the
  account-takeover demo: five events with a *mismatched beneficiary* stay
  `OBSERVE` (entity gate), the matching sequence `ESCALATE`s, and a proposed
  transfer that would finish the pattern returns `WOULD_COMPLETE_PROHIBITED`.
  Typed edges (`SAME_ENTITY`/`ORDER`/`WITHIN`), a decomposed risk vector,
  dual-story verified-benign counter-stories, contradiction scoring, and forward
  completion-gating — all deterministic and advisory. See `STORY_GRAPH_SPEC.md`.
- **Phase-3 robustness (historical-replay readiness).** `cli readiness` runs the
  H1–H8 gates and prints a verdict (capped at `CONTINUE — historical replay
  ready`); `cli bench` / `cli alerts` / `cli review` run the load benchmark,
  alert-volume, and review simulation. Durable audit + `recover_from_audit`
  provide restart recovery; provider failure modes never silently neutralize; the
  K8s reference replay adapter is in `replay.py` (see
  `../HISTORICAL_REPLAY_K8S_CONTRACT.md`,
  `../HISTORICAL_REPLAY_READINESS_CHECKLIST.md`,
  `../PHASE3_FINAL_EVALUATION_REPORT.md`).
