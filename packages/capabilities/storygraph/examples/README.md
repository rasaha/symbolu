# StoryGraph Examples

Small, deterministic, synthetic examples that use **only** the canonical
`ugence_storygraph` public API. They run against the installed wheel.

| Example | Shows |
|---|---|
| [`minimal_story_evaluation.py`](./minimal_story_evaluation.py) | Advisory `SequenceRiskAnalyzer` over an admitted-action stream (harmful escalates, benign does not) |
| [`proposed_action_evaluation.py`](./proposed_action_evaluation.py) | Non-mutating `evaluate_proposed_action` against the frozen account-takeover story |
| [`policy_pack_compilation.py`](./policy_pack_compilation.py) | Compiling the reference Policy Pack; reproduces the frozen graph digest |
| [`replay_smoke.py`](./replay_smoke.py) | Deterministic historical replay over the bundled synthetic fixture |

## Run

```bash
pip install packages/capabilities/storygraph        # or the built wheel
python packages/capabilities/storygraph/examples/minimal_story_evaluation.py
python packages/capabilities/storygraph/examples/proposed_action_evaluation.py
python packages/capabilities/storygraph/examples/policy_pack_compilation.py
python packages/capabilities/storygraph/examples/replay_smoke.py
```

Each prints a short summary and exits non-zero on failure. They are executed
automatically by `tests/examples/test_examples_run.py` (in-repo) and by
`verify_storygraph_distribution.py` (against the isolated installed wheel).

## Boundaries

- **Advisory only.** StoryGraph emits `OBSERVE` / `ESCALATE` / `UNAVAILABLE` and
  advisory evidence — never `ALLOW` / `DENY` / `AUTHORIZE` / `BLOCK` / `EXECUTE`.
- **Synthetic only.** No enterprise data; no production-accuracy claim; no
  inference of malicious intent. See [`../docs/limitations/KNOWN_LIMITATIONS.md`](../docs/limitations/KNOWN_LIMITATIONS.md).
- **Public API only.** No internal implementation imports beyond the documented
  `ugence_storygraph` / `ugence_storygraph.policypack` / `ugence_storygraph.demos`
  surfaces.
