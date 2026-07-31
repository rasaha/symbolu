# Composite-Threat Detector

An **advisory, escalate-only** security layer that watches a stream of
*individually admissible* actions, extracts the capability "fragments" each one
quietly contributes, and reconstructs the composite offensive capability — the
**story** — that a sequence of innocuous steps is assembling.

> The illustration from the original prompt: a steel rod, a piston, and a trigger
> mechanism are each harmless to acquire. Assembled, they are a firearm. This
> layer is the algorithm that notices the assembly across the sequence and asks a
> human to look — before the last part is fitted.

It complements the per-action [Action Gate](../ACTION_GATE_SPECIFICATION.md),
which decides one action at a time. This detector adds the **sequence axis** the
gate reserves via the `correlation_id` / `sequence_id` envelope fields, and does
so as classed *advisory* evidence: its strongest possible output is
`ESCALATE_TO_HUMAN`. It never admits, denies, or approves. See
[`../COMPOSITE_THREAT_DETECTION_SPEC.md`](../COMPOSITE_THREAT_DETECTION_SPEC.md).

## Design properties

- **Deterministic** — same event stream → identical findings and finding
  digests. No wall-clock, no randomness.
- **Escalate-only** — the output alphabet is `{OBSERVE, ESCALATE}`; there is no
  `ALLOW`/`DENY`. Removing this layer changes no per-action gate decision.
- **Domain-agnostic engine** — all domain knowledge is an `Ontology` (fragments +
  recipes + a pure extractor). Two ship: `ctd.digital.actiongate` and
  `ctd.physical.firearm`.
- **Windowed** — bounds assembly to a recent span per correlation, so a
  low-and-slow adversary can't hide the barrel 10,000 actions before the trigger.
- **Predictive** — a partial finding names the **missing** fragment: the next
  action that would complete the capability.

## Requirements

Python 3.11+, standard library only. `pytest` (dev-only) to run the tests.

## Run

```bash
cd cyber_security/composite_threat_detector

python3 -m pytest -q                                          # test suite

python3 -m composite_threat_detector.cli demo firearm         # the prompt, runnable
python3 -m composite_threat_detector.cli demo exfiltration    # digital analogue
python3 -m composite_threat_detector.cli ontologies           # list recipes
python3 -m composite_threat_detector.cli run events.jsonl \
        --ontology ctd.digital.actiongate --window 200        # your own stream
```

`run` reads one JSON event per line. Exit code is non-zero when any `ESCALATE`
finding is produced.

## Library

```python
from composite_threat_detector import (
    CompositeThreatMonitor, DIGITAL_ONTOLOGY, to_advisory_evidence,
)

mon = CompositeThreatMonitor(DIGITAL_ONTOLOGY, window_actions=200)

for action in admitted_action_stream:        # each already cleared the per-action gate
    for finding in mon.observe(action):       # findings whose concern rose on this step
        print(finding.signal, finding.story["headline"])
        if finding.signal == "ESCALATE":
            # attach as advisory evidence bound to the triggering action's hash
            ev = to_advisory_evidence(
                finding, bound_to=action_hash, generated_at=now_rfc3339)
```

## Layout

| Path | Purpose |
|------|---------|
| `composite_threat_detector/model.py` | `Fragment`, `Recipe`, `Ontology`, `FragmentInstance` |
| `composite_threat_detector/fragments.py` | per-event extractors (digital + firearm) |
| `composite_threat_detector/recipes.py` | shipped ontologies (the recipe libraries) |
| `composite_threat_detector/signals.py` | the escalate-only signal ladder |
| `composite_threat_detector/monitor.py` | the accumulator + recipe matcher (the engine) |
| `composite_threat_detector/narrative.py` | deterministic story reconstruction |
| `composite_threat_detector/evidence.py` | Finding → Action-Gate advisory evidence |
| `composite_threat_detector/cli.py` | JSON CLI |
| `demos/scenarios.py` | firearm + exfiltration scenarios |
| `tests/` | 14 behavioural + invariant tests |
