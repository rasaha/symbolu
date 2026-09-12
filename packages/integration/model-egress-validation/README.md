# Ugence Model Egress Validation

**Version:** 0.2.1
**Maturity:** `REFERENCE_GRADE_SHADOW_ONLY` · `ENFORCEMENT_ENABLED = False` · `LIVE_VENDOR_EGRESS = False`
**Ruling basis:** LP-4 (the matrix), LP-7 ruling 11 (the offline step-7 artifacts), LP-7 ruling 12 (`live` refuses) — `docs/architecture/ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md` §0.4

The offline step-7 artifacts for commissioning a live model provider behind the Model
Egress Unit: the eighteen-row validation harness over injected fake components, the
fake-transport cases, the negative-test matrix, a redacted report generator, drift
checks between the records beside the unit and the code, and secret-shape scanning.

## This distribution opens no network connection and holds no credential

No HTTP client, no vendor SDK, no credential reader, no live transport. The adapter it
drives is `ugence-model-egress-provider-openai` with that adapter's own `FakeTransport`;
custody is an in-memory marker this run generates, registers as a known secret, and
never writes anywhere. `tests/test_boundaries.py` refuses every network, vendor,
driver, environment and clock import outside `cli.py`, and the whole test suite runs
with socket connections patched to raise.

**It marks no infrastructure-dependent row as passed.** A row's status here is one of
`OFFLINE_CONFORMANT`, `OFFLINE_NONCONFORMANT` or `NOT_EXECUTABLE_OFFLINE`; there is no
`PASS`. Rows 12 (the live answer's provenance) and 18 (the Secret Manager audit log)
are infrastructure-dependent and are never executed here; rows 13, 14 and 15 need the
deployment unit or the exchange and say so. The report never edits
`MEU_LIVE_VALIDATION.json`, which is written only by the owner-run live verifier after
step 8 and the separate live-validation authorization.

## Commands

```
cd packages/integration/model-egress-validation
PYTHONPATH=src:../model-egress-unit/src:../model-egress-provider-openai/src \
  python -m ugence_model_egress_validation offline --report /tmp/meu-offline-report.json
```

Runs every offline-executable row, checks the records for drift, writes the redacted
report and exits non-zero on any non-conformant row or any drift.

```
python -m ugence_model_egress_validation live
```

Refuses (exit 2) before any custody port, budget, transport or harness is touched, stating "17 mandatory designation obligations represented by 23 checked fields" and naming every undesignated obligation, then the independent-check attestation separately: no live transport exists in
any distribution, and LP-7 ruling 12 keeps the owner-run verifier from executing until
every designation is supplied and independently checked.

LP-8 (that ADR's §0.7) adds the first refusal of all: when any CI environment marker is
set (`ugence_model_egress_unit.CI_ENVIRONMENT_MARKERS`) the process is a CI runner, which
may not possess or exercise the credential, and `live` exits 2 before reading a record.
That is the one environment read in this distribution, and it reads exactly the marker
names, never a key, a DSN or any other variable; the boundary tests hold `cli.py` to that
single expression and keep every other module free of environment reads.
The refusal text names the only permitted execution posture, the deployed MEU instance,
and the five holders LP-8 forbids. The drift checks require the validation record's
`live_execution_posture` to match the unit's constants and row 12 to require execution by
the deployed MEU instance.

## The report

Statuses, refusal names, counts, digests and versions only. The generator refuses to
produce a report that carries the synthetic prompt, the leased marker, the fake
response marker, or any credential-shaped string (`secret_shapes.scan`). It records
`live_pass_claimed: false`, `network_opened: false`, `credential_present: false` and
`audit_query_window: null`; only the live verifier will fill the last.

## Locating the records

The two records are located by exactly one rule or refused: beside the unit when it is imported from a source checkout, or in the git checkout that contains the working directory. When both exist they must be the same directory; when they differ, or neither exists, `RecordsNotLocated` is raised and `--records <dir>` names the intended one. A parent, sibling or unrelated checkout is never consulted, and a directory whose designation record is not of the live-provider schema is refused. Reads are read-only; the offline command never writes to either record.

## The validation plan digest

`validation_plan_digest()` digests this distribution's row table and the three distribution versions. The owner's typed `LiveSyntheticValidationAuthorization` (ADR §0.6) binds it as `validation_plan_digest`; an authorization issued for one plan admits no call under another. The offline report records it.

## Drift checks

The designation record's limits, host, endpoint and model against
`COMMISSIONING_LIMITS`, `OPENAI_RESPONSES` and `DESIGNATED_MODEL`; the matrix rows and
required outcomes against this distribution's row table; `meu_live_status` against
`COMMISSIONING_STATUS` and the record's own vocabulary; and, while any step-8 value is
`UNDESIGNATED`, that the status is `BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS`, every
row's result is `null` and no evidence is recorded.

## Dependency direction

```
ugence-model-egress-unit >= 0.5.0        ugence-model-egress-provider-openai >= 0.2.0
                    ▲                                     ▲
                    └──── ugence-model-egress-validation ─┘
```

Neither the unit nor the adapter imports this distribution.

## Tests

```
PYTHONPATH=src:../model-egress-unit/src:../model-egress-provider-openai/src python -m pytest
```
