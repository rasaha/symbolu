# Composite Capability & Sequence-Risk Analyzer

> **ActionGate controls individual actions; this analyzer detects when
> individually acceptable actions collectively assemble a prohibited or high-risk
> capability.**

It complements the per-action [Action Gate](../ACTION_GATE_SPECIFICATION.md),
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
[`../COMPOSITE_THREAT_DETECTION_SPEC.md`](../COMPOSITE_THREAT_DETECTION_SPEC.md).

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
cd cyber_security/composite_threat_detector

python3 -m pytest -q                                          # deterministic tests

python3 -m composite_threat_detector.cli demo exfiltration    # harmful  → ESCALATE
python3 -m composite_threat_detector.cli demo benign          # look-alike → no escalate
python3 -m composite_threat_detector.cli demo approved_export # valid approval → neutralized
python3 -m composite_threat_detector.cli demo firearm         # synthetic illustration
python3 -m composite_threat_detector.cli ontologies           # recipes
python3 -m composite_threat_detector.cli specs                # assembly key specs
python3 -m composite_threat_detector.cli eval                 # metrics (NOT RUN, honest)
python3 -m composite_threat_detector.cli run events.jsonl \
        --spec by_case --spec by_actor --policy               # your own stream
```

`run` reads one JSON event per line; exit code is non-zero when any
`ESCALATE`/`UNAVAILABLE` finding is produced.

## Library

```python
from composite_threat_detector import (
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
| `composite_threat_detector/model.py` | Fragment / Recipe / Ontology / instance types |
| `composite_threat_detector/linkage.py` | entity normalization + assembly-key derivation |
| `composite_threat_detector/ledger.py` | multi-timescale state + persistent capability ledger |
| `composite_threat_detector/matcher.py` | constraint-aware recipe matcher |
| `composite_threat_detector/benign.py` | evidence-gated benign-context layer |
| `composite_threat_detector/completion.py` | advisory minimal-completion analysis |
| `composite_threat_detector/analyzer.py` | orchestration, findings, run report, facade |
| `composite_threat_detector/policy.py` | authoritative consequence binding |
| `composite_threat_detector/evidence.py` | Finding → ActionGate advisory evidence |
| `composite_threat_detector/fragments.py` / `recipes.py` | shipped ontologies |
| `composite_threat_detector/cli.py` | JSON CLI |
| `evaluation/` | evaluation harness + results template (NOT RUN) |
| `demos/scenarios.py` | illustrative scenarios |
| `tests/` | 35 deterministic detection + non-detection tests |
| `RECIPE_SCHEMA.md` / `LINKAGE_SCHEMA.md` / `MIGRATION_NOTES.md` | schemas + migration |
