# MEU validation job

**Version:** 0.1.0
**Kind:** `GCP_CLOUD_RUN_JOB` · **Maturity:** `REFERENCE_GRADE_SHADOW_ONLY` · `GENUINE_DISPATCH_IMPLEMENTED = False`

The deployable artifact for the Model Egress Unit commissioning validation. It is a
Cloud Run **Job**: it runs to completion and exits, binds no port and exposes no HTTP
endpoint, so nothing can call it and the operator starts it.

## What this slice can and cannot do

**It can** evaluate every commissioning gate against the canonical records, run the
eighteen-row offline harness over fake components, and write one redacted report. That
run reads no secret, opens no connection and exits zero.

**It cannot** make a provider call. No live Responses transport exists in any installed
distribution and `LIVE_VENDOR_EGRESS` is `False`, so `mode: live` fails closed with exit
2 and says that first. **Issuing an authorization does not unblock it.** The live
transport and the owner-run verifier composition are the next slice.

| Mode | What happens | Exit |
|---|---|---|
| `offline` (default) | every gate evaluated and reported; eighteen-row harness over fakes; redacted report written; no custody adapter composed at all | 0, or 1 on a non-conformant offline row |
| `live` | refused before anything is composed; report records the refusal | 2 |
| any mode, inside a CI runner | refused by the entrypoint before a record is read | 2 |

## The five gates

Every gate is evaluated on every run and all five appear in the report, whether or not
an earlier one blocked, so an operator sees everything outstanding rather than the first
thing. What they *authorize* is ordered: **reading the real credential needs the first
three**, and a genuine call needs all five.

| Gate | Passes when |
|---|---|
| `EXECUTION_POSTURE` | the deployed MEU instance, under its non-human workload identity, through the production-form custody adapter, in a non-production environment, and not a CI runner (LP-8) |
| `STEP8_DESIGNATION` | all seventeen obligations supplied and independently verified (LP-7 ruling 12) |
| `LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION` | the canonical record pins the owner's typed authorization and the supplied record is that one, unrevoked (ADR §0.6) |
| `COMMISSIONING_CEILINGS` | the endpoint is exactly the designated destination and no authorized limit exceeds an LP-5 ceiling |
| `LIVE_TRANSPORT` | **cannot pass in this slice**: no live transport exists and `LIVE_VENDOR_EGRESS` is `False` |

A run that may not call may not read: the authorization gates credential materialization
and not only dispatch, so a lapse in the dispatch path cannot become a credential that
was fetched anyway.

## Configuration

`CONFIG_SCHEMA.json` is the schema; `config.example.json` is a complete example whose
every value is an unmistakable `REPLACE-ME-…` placeholder. The example is **deliberately
not runnable**: its placeholders are refused by the posture gate, so copying it reaches
no credential.

Configuration carries references only. There is no field that may hold a provider key, a
token or a secret payload, a field whose *name* means material is refused whatever its
value, and a value carrying credential material is refused whatever field it arrived in.
`MEU_JOB_CONFIG` names the configuration **file path** and is the only variable the
entrypoint reads besides the CI markers.

---

# Operator runbook

The five phases below are separate. Each ends in an artifact, and the next phase does not
begin until that artifact exists. Phases 2 to 5 are the owner's; phase 1 is the only one
this repository performs.

## Phase 1 — repository build and fake validation

Performed here, in CI and on a developer machine. No Google Cloud account is involved and
no credential exists.

```
# the package suites, sockets refused, no Google SDK installed
pytest packages/integration/model-egress-custody-gcp
pytest deployment/meu-validation-job

# a dry run against the canonical records: prints every gate, writes nothing
python -m meu_validation_job dry-run --config deployment/meu-validation-job/config.example.json

# build the image (context is the repository root)
docker build -f deployment/meu-validation-job/Dockerfile -t meu-validation-job:0.1.0 .
```

**Exit artifact:** a green suite, a dry-run listing showing every gate outstanding, and a
built image. Nothing is deployed.

## Phase 2 — owner-operated GCP provisioning

The owner's, in their own Google Cloud session. **This repository performs none of it and
no script here creates a resource.** There is deliberately no Terraform and no
provisioning script: an infrastructure mutation needs separate authorization.

1. Create the dedicated **non-production** GCP project. Record its ID and its number.
2. Create the dedicated non-human service account for the MEU. Grant it nothing yet.
3. Deploy this image as a **Cloud Run Job** in that project, with that service account
   attached. Do not create a Cloud Run *service*.
4. Create the dedicated Secret Manager secret. Do not add a version yet.
5. Grant `roles/secretmanager.secretAccessor` **on that secret only** to that service
   account. No project-level binding, and no human, CI or other workload.
6. Enable Secret Manager Data Access audit logging and record its configuration and
   retention.
7. Keep the authority to add, disable or destroy versions separate from the authority to
   read them.

**Exit artifact:** the exact resource names, the IAM policy evidence reference and the
audit-log configuration reference. Still no credential.

## Phase 3 — designation acceptance

1. Fill all seventeen obligations in `MEU_LIVE_PROVIDER_DESIGNATION.json`, including the
   full numeric Secret Manager version resource once phase 4 has produced it.
2. Have someone other than the person who provisioned the resources verify each value
   against Google Cloud and OpenAI, and record them in
   `step8_required_values.attestation.independently_checked_by`.
3. Record the deployed instance reference and the workload-identity principal in
   `MEU_LIVE_VALIDATION.json` → `live_execution_posture`.

**Exit artifact:** a complete, attested designation record. `dry-run` now shows
`STEP8_DESIGNATION` passing. `EXECUTION_POSTURE` passes once the real instance reference
and principal replace the placeholders.

## Phase 4 — credential commissioning

1. In the OpenAI console, in the dedicated non-production OpenAI project, create a
   **project service account** key scoped to `api.responses.write` and nothing wider.
2. Add it as a **new version** of the Secret Manager secret. Pipe it in rather than
   writing it to a file, and clear it from shell history.
3. Record the full numeric version resource as obligation 6. `latest` is refused.
4. Never place it in this repository, an environment variable, a CI secret, a container
   layer, a log or an evidence report. The eight-step rotation procedure of LP-2 governs
   every later replacement.

**Exit artifact:** a pinned numeric secret version the designation record names. The job
still cannot read it: the authorization gate is outstanding.

## Phase 5 — separately authorized live synthetic validation

**Not reachable from this slice.** It needs, in addition to phases 2 to 4:

- the owner's typed `LiveSyntheticValidationAuthorization` issued and its digest pinned
  into `MEU_LIVE_VALIDATION.json`;
- the live Responses transport, which does not exist yet;
- the owner-run verifier composition;
- `LIVE_VENDOR_EGRESS` becoming true under its own decision.

Until all of that exists, `mode: live` fails closed and says so.

## Dry run

```
python -m meu_validation_job dry-run --config /etc/meu-validation-job/config.json
```

Validates the configuration and the records, prints every gate with its reason, runs
nothing and writes nothing. Exit 0 when a credential could be materialized, 1 otherwise.
Run this before every first execution after a configuration change.

## Deploying and executing the job

```
# push the image the repository built (the owner's registry and project)
docker tag meu-validation-job:0.1.0 REGION-docker.pkg.dev/PROJECT/REPO/meu-validation-job:0.1.0
docker push REGION-docker.pkg.dev/PROJECT/REPO/meu-validation-job:0.1.0

# create the JOB (not a service), with the dedicated service account attached
gcloud run jobs create meu-validation \
  --project PROJECT --region REGION \
  --image REGION-docker.pkg.dev/PROJECT/REPO/meu-validation-job:0.1.0 \
  --service-account SA_EMAIL \
  --set-env-vars MEU_JOB_CONFIG=/etc/meu-validation-job/config.json \
  --max-retries 0 --task-timeout 10m

gcloud run jobs execute meu-validation --project PROJECT --region REGION --wait
```

Mount the configuration file and the two records at `/etc/meu-validation-job/`. Never
pass a secret with `--set-env-vars` or `--set-secrets`: the job reads its credential
through the custody adapter, from the pinned version, under the attached identity, and
only when the gates permit.

## Rollback and removal

```
# roll back to a previous image; the job is stateless apart from its report
gcloud run jobs update meu-validation --project PROJECT --region REGION \
  --image REGION-docker.pkg.dev/PROJECT/REPO/meu-validation-job:PREVIOUS

# remove the job entirely
gcloud run jobs delete meu-validation --project PROJECT --region REGION

# the credential outlives the job: revoke it separately, in LP-2's order
#   revoke the OpenAI credential, then disable the Secret Manager version.
#   No version is destroyed during initial commissioning.
```

Deleting the job removes no secret, no IAM binding and no audit log. Those are the
owner's to remove, deliberately, because a deployment that could delete its own audit
trail is not an audit trail.

## The report

One JSON document: schema, versions, mode, outcome, the five gates with reasons, the
posture identifiers, `credential_materialized`, `secret_version_accessed`, the call and
accounting counters, the LP-5 ceilings, and the offline harness summary with every row's
`result_in_record` still `null`. It is written through the validation distribution's
secret-shape scanner, so a report that somehow carried a key, a prompt or a response
raises instead of landing.

## Tests

```
pytest deployment/meu-validation-job
```

Sockets are refused inside the suite. The suite never constructs a real Google client:
the one test that exercises the composition root with no injected client asserts the
typed unavailability instead.
