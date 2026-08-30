# Reference evidence (not run output)

Committed status and reference records from the P3E deployment pass. Several of
them record `"result": "NOT_EXECUTED"` — they document that a gate did **not**
run, with the reason.

These files are **not** evidence produced by any CI run and must never be read as
such. Runtime evidence is written to a fresh, run-scoped directory under
`RUNNER_TEMP`, outside the checked-out repository, and is hashed into the
evidence manifest only when the current run's producer step actually created it.
See `../ci/build_evidence_manifest.py`.

`deployment/governance-studio/artifacts/` is reserved for runtime output and is
git-ignored so a run's output can never be committed and later mistaken for
current evidence.
