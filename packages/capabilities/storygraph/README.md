# ugence-storygraph

**StoryGraph** — an advisory **sequence-risk analyzer**. ActionGate controls
individual actions; StoryGraph detects when individually-acceptable actions
collectively assemble a prohibited or high-risk *capability* (a "story"), and
emits **advisory evidence** so a downstream authority can escalate.

- **Distribution:** `ugence-storygraph`
- **Namespace:** `ugence_storygraph`
- **Version:** 2.0.0
- **Dependencies:** Python standard library only (no third-party, no other Ugence package)
- **Maturity / ownership:** frozen-but-working reference capability; synthetic-only validation

## Authority boundary (read this first)

StoryGraph is **advisory / evidentiary only**. It emits `OBSERVE` / `ESCALATE` /
`UNAVAILABLE` findings and evidence records classed `ADVISORY` with an
`OBSERVE`/`ESCALATE` **effect ceiling**. It **never** emits
`ALLOW`/`DENY`/`AUTHORIZE`/`BLOCK`/`EXECUTE`/`CLEAR`, and it holds **no**
action-authorization, binding-decision, operational-clearance, or execution
authority. A downstream ActionGate or workflow policy owns any binding
consequence. This boundary is machine-checked
(`tests/compatibility/test_authority_boundary.py`).

## Install

```bash
python -m build packages/capabilities/storygraph        # build the wheel
pip install dist/ugence_storygraph-2.0.0-py3-none-any.whl
```

Installs with **no index required** — StoryGraph declares zero third-party
runtime dependencies. Independent-distribution proof:

```bash
python packages/capabilities/storygraph/verify_storygraph_distribution.py
```

## Supported public API

Import the curated surface from `ugence_storygraph.api` (or the equivalently-
exported top-level `ugence_storygraph`). See
`docs/../../../docs/migrations/storygraph/API_INVENTORY.md` for the full stable
list. Do not import internal modules for new code.

### Minimal usage

```python
from ugence_storygraph import SequenceRiskAnalyzer, DIGITAL_ONTOLOGY

az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY)
for action in admitted_action_stream:      # each already cleared its per-action gate
    for finding in az.observe(action):
        print(finding.signal, finding.explanation)   # OBSERVE / ESCALATE only
```

### Proposed-action simulation (non-mutating)

```python
from ugence_storygraph import ACCOUNT_TAKEOVER_TRANSFER, evaluate_proposed_action
result = evaluate_proposed_action(assembly, proposed_action, ACCOUNT_TAKEOVER_TRANSFER)
result.signal        # "ESCALATE" if the action would complete the harmful story
```

### Policy Pack (policy-as-code)

```python
from ugence_storygraph.policypack import compiler, reference
bundle = compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK)
compiler.graph_freeze_digest(bundle)   # reproduces the frozen graph digest
```

### Historical replay (deterministic)

```python
from ugence_storygraph.policypack import reference, replay
report = replay.run_replay(reference.account_takeover_pack(), records)
report["report_digest"]   # deterministic; stable across runs and installs
```

## Versioning

SemVer on the distribution; internal semantic identifiers (`ctd.storygraph/…`,
`ctd.storygraph.matcher/…`, `ctd.witness.tiebreak/…`, …) are **frozen** and
participate in freeze/replay digests — they are not import paths and do not
change on a physical move.

## Compatibility paths

| Legacy (compatibility period) | Canonical |
|---|---|
| `import composite_threat_detector` | `import ugence_storygraph` |
| `from composite_threat_detector.storygraph import ...` | `from ugence_storygraph.storygraph import ...` |
| — | `from ugence_storygraph.api import ...` (curated) |

Legacy imports resolve to the **same** objects via a logic-free redirect shim at
`cyber_security/composite_threat_detector/` (removal/review target: v3.0.0). See
`MIGRATION.md`.

## Known limitations & scope

- **Synthetic-only validation.** No enterprise data is bundled; the historical-
  replay path ships templates and a synthetic reference fixture only.
- **One implemented harmful graph/domain** (account-takeover transfer, plus a
  digital-exfiltration story); the physical-firearm ontology is retained solely
  as a synthetic illustration.
- **Known-pattern-only scope.** StoryGraph matches *encoded* capability patterns.
  It is **not** an intent-understanding system, **not** a learned anomaly
  detector, and infers **no** malicious intent.
- **No direct enforcement authority.** Advisory findings only.
