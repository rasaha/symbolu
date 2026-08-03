# expected_outputs/

Frozen canonical outputs of the **real** AWC P1/P2 pipeline over `../demo_data/`.
Per scenario: `adaptation.json`, `eligibility.json`, `ranking.json`,
`composition.json`, `agent_team_plan.json`, `replay_record.json`,
`fingerprints.json`. `MANIFEST.json` records sha256 of every input and output plus
the AWC version and contract versions.

These are a regression oracle: loading the committed fixtures and running the engine
must reproduce these bytes exactly (see `../tests/test_determinism.py`).
