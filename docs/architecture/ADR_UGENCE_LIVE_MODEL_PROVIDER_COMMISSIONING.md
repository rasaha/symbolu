# ADR — Commissioning a live model provider: what AP-3 unblocked, what it did not, and the ballot LP-1 to LP-6

**Status:** LP-1 to LP-6 **RATIFIED by the owner on 2026-09-11** (§0, verbatim). The ballot
below is retained as put. Nothing here creates a credential, makes a live call, enables
live vendor egress or commissions the provider.

**Date:** 2026-09-11. **Prompted by:** the owner's instruction, after AP-3 was accepted and
merged (`ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §20.7, PR #1748), to configure a live LLM
provider.

**Designations received (owner, 2026-09-11):** vendor **OpenAI** (host `api.openai.com`);
custody store **Google Secret Manager**. Recorded in
`packages/integration/model-egress-unit/MEU_LIVE_PROVIDER_DESIGNATION.json`. They answer
the *names* LP-2 and LP-3 ask for and nothing else: LP-1 to LP-6 are still unruled, the
model, account, terms, region, project, secret name, rotation policy and custody owner
are `UNDESIGNATED`, and two questions the designations raise are added below as LP-2a
and LP-2b. Model Egress Unit 0.2.0 carries the custody port, the ledger-kind schema and
transport protection (`ADR_MODEL_EGRESS_UNIT_REFERENCE_SLICE.md`, addendum); it holds no
credential and reaches nothing.

## 0 — The rulings (owner, 2026-09-11) — **RATIFIED**, recorded verbatim

> **LP-1 — Deployment boundary.** Ratify as recommended. Amend CR-1 to admit the Model
> Egress Unit (MEU) as the second named companion deployment unit. The governed-runtime
> worker retains its existing egress restriction. Only the MEU may contact the designated
> model-provider host. This ruling does not admit arbitrary additional deployment units or
> destinations.
>
> **LP-2 — Credential custody.** Designate Google Cloud Secret Manager as the initial
> external credential-custody system. Custody owner: Rakesh Mohan — Founder, Ugence Labs.
> Requirements: use a dedicated MEU workload identity and least-privilege secret-version
> access; prefer workload identity federation; do not introduce a long-lived Google
> service-account key; never place the provider credential in source code, repository
> files, container layers, environment-variable configuration, GitHub Actions secrets, logs
> or evidence reports; enable and verify Secret Manager Data Access audit logging for
> credential reads; pin the exact secret-version resource used by a deployment, do not
> silently resolve latest during execution; establish rotation at least every 90 days and
> immediately following suspected exposure; record rotation, disablement and destruction
> of superseded versions; keep live invocation blocked until the GCP project ID, workload
> identity, secret resource identifier, IAM binding, audit-log evidence and rotation
> procedure are designated and accepted. Selection of Google Cloud Secret Manager
> authorizes implementation of the custody port and its tests. It does not authorize
> creating, entering, retrieving or exercising a provider credential through Claude or CI.
>
> **LP-3 — First provider designation.** Vendor: OpenAI. Model: gpt-5.4-mini-2026-03-17.
> API host: api.openai.com. Endpoint: /v1/responses. Account scope: a dedicated
> non-production OpenAI API project named ugence-meu-validation. Content scope:
> synthetic, non-sensitive validation content only. The exact OpenAI organization/project
> identifiers must be recorded before the validation run. Never record the API key.
> Permit only the designated host and HTTPS endpoint. Disable provider-hosted tools, web
> search, file retrieval, MCP, code execution and background execution. Set store=false;
> nevertheless, treat the provider as potentially retaining abuse-monitoring data and
> therefore send no genuine enterprise, personal, confidential or credential-bearing
> content. The model snapshot is pinned. The floating gpt-5.4-mini alias is not permitted.
>
> **LP-4 — Validation and acceptance.** Ratify the recommended AP-3-shaped commissioning
> process: machine-readable validation matrix; negative and failure-path tests; owner-run
> verifier that never prints the credential or full request content; redacted evidence
> report; explicit accepting owner; status remains PENDING_VALIDATION until every mandatory
> row passes; status becomes MET only through a separate owner-acceptance statement. A
> successful HTTP response alone is insufficient.
>
> **LP-5 — Cost and request limits.** For the non-production commissioning scope, bind
> these limits into the authorized request and enforce them non-compensatorily: maximum
> input tokens per request 8,192; maximum output tokens per request 1,024; maximum genuine
> validation calls 10; total commissioning budget USD 25; concurrency 1; retries at most 1,
> and only for an explicitly classified transient failure; streaming disabled. Configure
> the narrowest available vendor-project budget or spend control as defense in depth. If
> the vendor control is advisory rather than a true hard stop, the MEU reservation ledger
> must enforce the hard limit before issuing a request. Cost limits cannot be overridden by
> the model adapter.
>
> **LP-6 — Required order.** (1) Record these rulings and amend CR-1. (2) Implement the
> ledger-kind schema and content-bearing-key refusals. (3) Implement TLS-protected database
> and provider transport verification. (4) Implement production role provisioning,
> controlled migrations and tenant-bound database identities. (5) Implement the Google
> Secret Manager custody port using a fake/emulator path only. (6) Implement the OpenAI
> provider as a separate MEU-only distribution; do not place its SDK or networking code in
> an existing socket-prohibited package. (7) Produce the validation matrix, owner-run
> verifier and acceptance-report generator. (8) Stop and request the exact GCP and OpenAI
> project designations. (9) Commission the credential manually through Google Cloud Secret
> Manager. (10) Perform the synthetic validation run only after all prerequisite gates
> pass. (11) Keep genuine enterprise content and production use blocked behind a later,
> separate commissioning record. Throughout, the model response remains untrusted evidence
> under D-1. It receives no decision authority, execution authority or served-write
> capability.
> — owner, 2026-09-11

### 0.1 — Where each ruling now lives

| Ruling | Applied |
|---|---|
| LP-1 | CR-1 amended in `ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md` §5 (2026-09-11); the worker's egress record unchanged; `egress_policy.OPENAI_RESPONSES` is the one destination |
| LP-2 | `MEU_LIVE_PROVIDER_DESIGNATION.json` `custody`; `custody.CustodyIdentity` refuses a service-account key; `custody.is_pinned_secret_version` refuses `latest`; adapters refuse a rotation over 90 days; `PinnedSecretVersionCustodyAdapter` is the fake-path shape (LP-6 step 5); every materialization audited as identifiers and digests |
| LP-3 | `MEU_LIVE_PROVIDER_DESIGNATION.json` `vendor`; `limits.is_pinned_snapshot` refuses the alias; `limits.FORBIDDEN_REQUEST_FEATURES` and `store=false` enforced by `limits.check_request` |
| LP-4 | `MEU_LIVE_VALIDATION.json`: an eighteen-row matrix at `BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS`; verifier and acceptance-report generator are LP-6 step 7 |
| LP-5 | `limits.COMMISSIONING_LIMITS` (constants), `limits.check_request`, `limits.CallBudget` (non-compensatory, before dispatch, concurrency 1, one retry only for `TRANSIENT_BEFORE_DISPATCH`); the durable reservation row in the exchange is unbuilt `[G]` |
| LP-6 | Steps 1, 2, 3 (database side and destination policy), 5 and the matrix of 7: done in Model Egress Unit 0.2.0. Steps 4, 6, the verifier and generator of 7: not started. Steps 8 to 11: the owner's |

### 0.2 — Divergences between these rulings and the merged specifications, named

1. **LP-5's MEU-side hard stop and D-5.** D-5 places the per-vendor reservation counter
   on the authorization side and denies the MEU governance authority; the spec (§7) says
   the MEU "does not calculate concentration, choose policy or update governance limits".
   LP-5 has the MEU refuse a request that would exceed a fixed budget. Read here as a
   fail-closed *ceiling* the MEU enforces on itself, not a policy it chooses: the numbers
   are owner constants the adapter cannot change, and refusal is the MEU's one permitted
   act. Recorded so the owner can say otherwise.
2. **LP-5's single retry and spec §3.5.** §3.5 makes `OUTCOME_UNKNOWN` terminal after a
   possible dispatch and forbids a second billed call. The retry LP-5 allows is therefore
   confined to a failure *known to precede dispatch* (`TRANSIENT_BEFORE_DISPATCH`); a
   timeout after the request left is never retried. `CallBudget.may_retry` encodes that.
3. **LP-6 step 4 and the tenancy ruling.** The tenancy ruling requires tenant-bound
   database identities "before multi-tenancy"; LP-6 requires them before the validation
   run in a single-tenant scope. Stricter than the spec, not contrary to it; followed.
4. **LP-2b, the record contract.** `EgressResult` and the exchange schema
   (`CHECK egress_result_no_genuine_call`) refuse `genuine_call: true`. Admitting it under
   the ratified precondition needs a second exchange migration; #1749's "no
   `exchange.v2`" was about the digest construction and does not forbid a migration that
   changes a constraint, but the owner should confirm that reading before step 6 lands.
   **Confirmed by the owner on 2026-09-11 (§0.3, item 2), under six conditions; migration 2
   of the unit (0.3.0) is that constraint-only migration and §0.3 records each condition
   against it.**
5. **The model snapshot.** `gpt-5.4-mini-2026-03-17` is recorded as designated; nothing
   here verifies that the vendor lists it, and the verifier of step 7 will.

### 0.3 — The owner's confirmation of the recorded interpretations (2026-09-11), verbatim

> Owner confirmation for PR #1750:
>
> 1. LP-5 and D-5
>
> Confirm LP-5 as a two-layer, non-compensatory control:
>
> * The authorization side remains the authoritative policy and reservation authority under D-5.
> * The MEU additionally enforces an independent, fixed, fail-closed safety ceiling before dispatch.
> * The MEU does not select, increase, waive or reinterpret the limits.
> * A request must satisfy both layers; approval by either layer cannot compensate for refusal by the other.
>
> The current in-memory MEU counter is acceptable for unit tests and fake-transport development only. It is not sufficient for a genuine validation call because restart or replica changes could reset or fragment its state. Before genuine_call: true is possible, implement the already identified durable reservation/consumption record with atomic reserve-before-dispatch behavior and no refund after possible dispatch.
>
> 2. Constraint-only exchange migration
>
> Permit a constraint-only database migration that allows the existing genuine_call field to carry true, provided that:
>
> * genuine_call already belongs to the ratified exchange-v1 contract;
> * no canonical field set, digest preimage, serialization, field meaning or wire schema changes;
> * no exchange.v2 is introduced;
> * existing rows and digests remain valid;
> * the migration merely lifts the reference-slice database restriction that forced all calls to remain non-genuine;
> * application and deployment gates continue to refuse genuine calls until commissioning reaches MET.
>
> The "no exchange.v2" ruling in #1749 concerned the request-digest construction. It does not prohibit this narrowly scoped database constraint migration.
>
> If any of those conditions is false, stop before migrating and report the exact contract change that would require a new version.
>
> 3. Other recorded interpretations
>
> Confirm the remaining interpretations with these qualifications:
>
> * Retry is allowed only when the transport can prove that no request bytes were dispatched. Any ambiguous dispatch state receives no automatic retry.
> * Apply tenant-bound identities before the first genuine call, even though the earlier tenancy ruling required them only before multi-tenancy.
> * The model snapshot is designated but remains unverified. Fake-transport tests must not mark vendor availability or any infrastructure-dependent validation row as passed.
>
> 4. Proceed
>
> Proceed on the same branch with LP-6 steps 4 and 6:
>
> * production role provisioning;
> * separate controlled-migration identity;
> * tenant-bound runtime database identities;
> * tests proving runtime roles cannot perform DDL, bypass RLS or assume migration privileges;
> * the OpenAI adapter as a separate MEU-only distribution;
> * injected fake transport only;
> * exact destination and request-shape enforcement;
> * no credential access and no live network path.
>
> Add fresh-install and upgrade-path tests for the constraint migration. Keep the validation matrix at BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS; fake evidence cannot satisfy live rows.
>
> Run all locally available gates and allow the PostgreSQL suites and container gates to complete in CI. Push as a separate commit and update draft PR #1750.
>
> Report:
>
> 1. changed files and commit;
> 2. role and migration-identity boundaries;
> 3. migration compatibility results;
> 4. package-boundary proof for the provider adapter;
> 5. local and CI gate results;
> 6. every remaining step-7 and step-8 blocker.
>
> Do not create or request a credential, make a live call, enable live vendor egress, mark commissioning MET, merge, or begin production use.

#### 0.3.1 — The six conditions of item 2, checked against migration 2 before it was written

| Condition | Holds? | Where |
| --- | --- | --- |
| `genuine_call` already belongs to the ratified exchange-v1 contract | yes | `EgressResult.provenance["genuine_call"]` and the `egress_result.genuine_call` column both exist since migration 1; `CONTRACT_VERSION` unchanged at `model_egress_unit.exchange.v1` |
| no canonical field set, digest preimage, serialization, field meaning or wire schema changes | yes | `canonical.py` and `EgressResult.digest_body()` untouched; the two new columns (`custody_lease_id`, `custody_authority_id`) are outside every digest body; `tests/test_digest_vectors.py` frozen vectors unchanged and passing |
| no `exchange.v2` is introduced | yes | `EXCHANGE_SCHEMA_VERSION` and `MEU_CANONICALIZATION_VERSION` unchanged; migration 2 is `meu_schema_version` row 2 of the same contract |
| existing rows and digests remain valid | yes | `test_the_upgrade_path_keeps_existing_rows_and_digests_valid` seeds rows under migration 1 and reads them back unchanged after migration 2 |
| the migration merely lifts the reference-slice restriction | yes | `CHECK egress_result_no_genuine_call` is dropped and replaced by `CHECK egress_result_genuine_call_requires_custody`: `genuine_call = false OR (custody_lease_id IS NOT NULL AND custody_authority_id IS NOT NULL AND provenance_kind = 'RESPONSE')` |
| application and deployment gates continue to refuse genuine calls until `MET` | yes | `EgressResult.__post_init__` refuses `genuine_call: true` unless `COMMISSIONING_STATUS == "MET"`, a release constant of the unit; the OpenAI adapter refuses a production posture and raises on a transport claiming a genuine response; `MEU_LIVE_VALIDATION.json` stays `BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS` |

No condition was false, so the migration proceeded and no contract version change is required.

#### 0.3.2 — What the same commit delivered against item 4

| Ask | Delivered | Proof |
| --- | --- | --- |
| production role provisioning | `postgres/provision.py`: `identity_statements` emits `CREATE ROLE … LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE … IN ROLE <group>` with **no password**, plus the binding row written as the owner; the group roles stay `NOLOGIN`; executing the statements is an operator's act on a designated cluster | `test_migration_2_identities_and_reservation.py` |
| separate controlled-migration identity | `meu_migrator` (`NOLOGIN NOINHERIT`), a member of the owner that holds nothing until `SET ROLE meu_exchange_owner`; `SELECT, INSERT` on the migration ledger only | `test_the_migrator_holds_nothing_until_it_assumes_the_owner` |
| tenant-bound runtime database identities | `role_tenant_binding` and the `RESTRICTIVE` policy `identity_binding` on every tenant table, keyed on `current_user`; a bound login is refused every other tenant whatever its session setting claims | `test_a_bound_identity_is_refused_every_other_tenant_whatever_its_session_claims` |
| runtime roles cannot DDL, bypass RLS or assume migration privileges | fourteen statements, each `InsufficientPrivilege` from a genuine `LOGIN` probe in each runtime group | `test_a_runtime_identity_cannot_ddl_disable_rls_drop_a_policy_or_assume_a_privileged_role` |
| durable reservation, atomic reserve-before-dispatch, no refund | `commissioning_budget` and `commissioning_reservation`, one `UPDATE … RETURNING` under the LP-5 ceilings, a `BEFORE UPDATE` trigger that raises on any decrement, no `DELETE` grant | `test_the_reservation_is_taken_before_dispatch_and_never_refunded`, `test_a_reservation_is_tenant_scoped` |
| OpenAI adapter as a separate MEU-only distribution, injected fake transport only, exact destination and request shape, no credential access, no live network path | `packages/integration/model-egress-provider-openai` 0.1.0 | its `tests/test_boundaries.py`, `test_transport.py`, `test_provider.py`; the unit's `test_the_unit_never_imports_the_openai_adapter_distribution` |
| fresh-install and upgrade-path tests | both, plus an all-or-nothing upgrade test | `test_a_fresh_install_applies_both_migrations_and_migration_one_is_byte_identical`, `test_the_upgrade_path_keeps_existing_rows_and_digests_valid`, `test_the_upgrade_is_all_or_nothing` |
| validation matrix stays blocked; fake evidence cannot satisfy live rows | every row `result: null`; `FakeTransport` refuses a scripted `genuine` outcome at construction | `test_live_records.py`; `test_the_fake_transport_refuses_to_be_scripted_with_a_genuine_response` |

### 0.4 — LP-7 / Step-8 non-production infrastructure design rulings (owner, 2026-09-11), verbatim

The owner issued an earlier same-day LP-7 draft and superseded it with the text below before
either was committed; only this text is recorded and operative.

> LP-7 / Step-8 Non-Production Infrastructure Design Rulings
>
> These rulings govern the first non-production Model Egress Unit commissioning only. They do not commission or approve a production provider deployment.
>
> 1. GCP project
>
> Use a dedicated non-production GCP project for MEU provider validation. It must not share a project with production, general development, public demonstrations, CI or unrelated Ugence workloads.
>
> A later production GCP project requires a separate owner designation and commissioning record.
>
> 2. GCP workload identity
>
> The MEU must run under a dedicated, nonhuman GCP service account. No human identity, default compute identity, downloadable service-account key or shared runtime identity is permitted.
>
> Record the deployment platform and its identity mechanism:
>
> * If the MEU runs outside Google Cloud, designate the OIDC issuer, audience, subject constraints, Workload Identity Pool, provider and exact principal binding.
> * If it runs on Google Cloud, record the native workload-identity path and evidence that no static service-account key is used.
>
> The workload identity must not have project-wide privileges unrelated to retrieving the designated secret.
>
> 3. Secret resource
>
> Store the OpenAI validation credential in Google Secret Manager under a dedicated MEU secret.
>
> Runtime configuration must reference the full immutable numeric version resource:
>
> projects/<project-number-or-id>/secrets/<secret-name>/versions/<number>
>
> The latest alias and every nonnumeric version reference are prohibited.
>
> Do not record the secret value, a reversible encoding, or a digest that could be used as credential-verification material.
>
> 4. GCP IAM binding
>
> Grant roles/secretmanager.secretAccessor only:
>
> * to the dedicated MEU workload identity;
> * on the designated secret resource;
> * without a project-level accessor grant.
>
> Human users, CI identities, other workloads and the database migrator identity receive no runtime-secret-read authority.
>
> Administrative authority to add, disable or destroy secret versions must remain separate from runtime read authority. No operator receives secret-read permission merely because that operator manages rotation.
>
> 5. Secret Manager audit evidence
>
> Enable and retain Secret Manager Data Access audit logs before any credential materialization.
>
> Commissioning evidence must demonstrate:
>
> * the IAM policy on the exact secret;
> * a successful access event by the designated MEU workload identity;
> * the immutable numeric secret version accessed;
> * within a precisely defined commissioning time window, no secret-access event by an identity outside the approved set;
> * correlation of the access event to the MEU validation attempt using non-secret identifiers, workload identity and bounded timestamps.
>
> Do not claim universal "absence of unauthorized access." Report only what the defined audit query and retention window demonstrate.
>
> The evidence must contain no credential, prompt text or model-response content.
>
> 6. Rotation procedure
>
> Rotation must:
>
> 1. create a new project-scoped OpenAI service-account credential;
> 2. store it as a new Google Secret Manager version;
> 3. designate that immutable numeric version as a candidate;
> 4. run offline/fake-transport conformance checks;
> 5. separately authorize a controlled validation using the candidate;
> 6. accept and activate the candidate version;
> 7. verify successful operation;
> 8. revoke the superseded OpenAI credential and disable the corresponding Secret Manager version.
>
> Rollback to the preceding version is allowed only while both its Secret Manager version and corresponding OpenAI credential remain valid and owner-authorized.
>
> Destruction requires separately retained audit evidence and explicit authorization. No old version may be destroyed during initial commissioning.
>
> The maximum normal rotation interval remains 90 days, with immediate rotation following suspected exposure.
>
> 7. OpenAI tenancy and identity
>
> Use a dedicated non-production OpenAI project within the Ugence OpenAI organization for this commissioning.
>
> Use an OpenAI project-owned service account—not a human user's API key—with:
>
> * a custom project role containing only api.responses.write;
> * an API key scoped only to api.responses.write;
> * access only to the designated model;
> * the previously ratified request and expenditure ceilings.
>
> The credential must be unavailable to browsers, developers, CI jobs, other Ugence services and repository automation.
>
> A separate OpenAI production project and production credential require later owner approval.
>
> 8. Model and endpoint
>
> The designated model remains:
>
> gpt-5.4-mini-2026-03-17
>
> The only permitted vendor destination remains exactly:
>
> https://api.openai.com/v1/responses
>
> No floating model alias, wildcard host, alternate endpoint, redirect, proxy, hosted tool, background operation, fallback model or fallback provider is authorized.
>
> Before live validation, independently verify that the designated snapshot is available to the designated OpenAI project. Recording the model name is not availability evidence.
>
> 9. Spend and data controls
>
> Before live validation, record:
>
> * the configured OpenAI project spend control;
> * whether it is a true enforcement stop or only an alert;
> * evidence that the MEU's durable USD 25 ceiling remains the controlling hard stop;
> * the applicable OpenAI data-processing terms;
> * the approved processing/data-residency region;
> * confirmation that validation content remains synthetic and non-sensitive;
> * confirmation that store=false is enforced.
>
> Vendor-side limits are defense in depth and do not replace the durable authorization-side reservation or MEU safety ceiling.
>
> 10. Provisioning boundary
>
> Infrastructure provisioning, OpenAI service-account creation and credential creation are controlled operator actions outside the application repository.
>
> Repository implementation must not create, retrieve, transmit, display, log or test a real credential. Infrastructure-as-code may describe non-secret identities and policies only if separately authorized and if no credential is placed in configuration, state or output.
>
> 11. Remaining Step 7 work
>
> Offline Step 7 preparation may proceed before the infrastructure values are supplied:
>
> * validation harness;
> * fake-transport cases;
> * negative-test matrix;
> * redacted report generator;
> * drift checks;
> * secret-shape scanning.
>
> This work must not open a network connection or mark an infrastructure-dependent matrix row as passed.
>
> The owner-run live verifier may not execute until every mandatory Step 8 designation is supplied and independently checked.
>
> 12. Commissioning state
>
> Keep the provider at:
>
> BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS
>
> until these exact externally verified values and evidence references are recorded:
>
> * GCP project ID;
> * GCP project number;
> * MEU GCP service-account resource name;
> * deployment-platform identity mechanism;
> * WIF pool/provider and constrained principal binding, or the documented native GCP equivalent;
> * full numeric Secret Manager version resource;
> * secret-level IAM-policy evidence reference;
> * Data Access audit-log configuration and retention reference;
> * approved rotation-runbook reference;
> * OpenAI organization ID;
> * OpenAI project ID;
> * OpenAI project service-account ID;
> * OpenAI role and API-key scope evidence;
> * vendor spend-control evidence and hard-stop/advisory classification;
> * designated-model availability evidence;
> * applicable data-processing-terms reference;
> * approved processing/data-residency region.
>
> These values must not be guessed, synthesized, represented as completed by placeholders or inferred from naming conventions.
>
> Supplying and verifying them closes only the infrastructure-designation blocker. It does not authorize a genuine call.
>
> After all designations pass, stop and return the completed designation record, validation matrix and exact owner-run command. The first live synthetic validation requires a separate, explicit owner authorization. Production use requires another commissioning record.
>
> Record this ruling without creating infrastructure or credentials. Proceed only with the remaining offline Step 7 artifacts. Do not make a live call, enable live vendor egress, mark commissioning MET, or merge any new change without separate instruction.

#### 0.4.1 — Where each LP-7 ruling lives

LP-7 designs the non-production infrastructure and supplies no value. The repository
carries the *shape* each value must have and the refusals that keep a placeholder, an
alias, a forbidden identity, a secret-shaped string or an unverified value from ever being
accepted as a designation (`ugence_model_egress_unit.infrastructure`, unit 0.4.0), and the
offline step-7 artifacts ruling 11 permits (`ugence-model-egress-validation` 0.1.0).
Everything else is an operator's act outside the repository (ruling 10).

| Ruling | Repository mechanism | Outside the repository |
| --- | --- | --- |
| 1 dedicated non-production GCP project | `Step8Designation.environment` must read `non-production`; the project ID and number are required, well-formed, and never judged by name (ruling 12 forbids inference from naming conventions) | the project, and evidence it hosts nothing else; a later production project is a separate designation |
| 2 dedicated non-human service account; recorded identity mechanism | `meu_service_account` must be `projects/<project>/serviceAccounts/<name>@<project>.iam.gserviceaccount.com` in the designated project; the default compute identity, a human principal and a key file are refused; `workload_identity_binding` is either `WorkloadIdentityFederation` (issuer, audience, subject constraints, pool, provider, principal binding, all required) or `NativeGcpWorkloadIdentity` (path plus no-static-key evidence) | the account and binding, with no key ever created; least privilege beyond the secret |
| 3 dedicated secret, immutable numeric version; no secret value, encoding or digest recorded | `secret_version` must satisfy `custody.is_pinned_secret_version` in the designated project (by ID or number); every field of the record is scanned for credential shapes and refused without echoing the value; no field of any record holds a credential digest | the secret and its version |
| 4 secret-scoped accessor grant; no runtime read for humans, CI, other workloads or the migrator; administrative authority separate | `iam_policy_evidence_ref` required; `iam_binding_scope` must read `secret`; migration 2's `meu_migrator` holds only the exchange owner and the ledger, and no Secret Manager binding is expressible in the repository | the IAM policy on the exact secret; the separation of rotation authority from read authority |
| 5 Data Access audit logs before any materialization; five demonstrations; no universal claim | `audit_log_config_and_retention_ref` required; the harness report carries only non-secret identifiers, workload identity and bounded timestamps for correlation and never claims absence beyond a stated query and window (report field `audit_query_window`) | the configuration, retained logs and evidence |
| 6 eight-step rotation; rollback conditions; no destruction during initial commissioning; 90 days | `ROTATION_SEQUENCE` (eight steps in the owner's order) and `check_rotation_plan`; `rollback_permitted` requires both the previous Secret Manager version and OpenAI credential valid and owner-authorized; `MAX_ROTATION_INTERVAL = 90 days`, matching `custody` | the runbook, its approval, each rotation's evidence |
| 7 dedicated non-production OpenAI project; project-owned service account; `api.responses.write` only; designated model only; ratified ceilings | `openai_organization_id` (`org-…`), `openai_project_id` (`proj_…`), `openai_service_account_id` and `openai_role_and_key_scope_evidence_ref` required; `openai_key_scope` must be exactly `api.responses.write`; the adapter's request shape is closed to the one Responses call | the organization, project, service account, role, key scope, model access and limits |
| 8 model and endpoint; availability verified before live validation | already enforced: `limits.is_pinned_snapshot`, `egress_policy.OPENAI_RESPONSES`, the adapter's `PreparedRequest`; `model_availability_evidence_ref` required and refused when it is merely the model name | the availability check against the designated project |
| 9 spend and data controls | `vendor_spend_control_evidence_ref` and `vendor_spend_control_classification` (`hard_stop` or `advisory`) required; `data_processing_terms_ref` and `processing_region` required; the durable USD 25 ceiling stays `commissioning_budget`'s CHECK and the adapter's `CallBudget`; `store=false` is enforced at `PreparedRequest` construction; content stays synthetic by the harness's fixture set | the vendor configuration and its evidence |
| 10 provisioning boundary | no repository code creates, retrieves, transmits, displays, logs or tests a real credential; both boundary suites and the validation package's fail on any import that could; no infrastructure-as-code exists | the operator's acts |
| 11 offline step-7 artifacts | `ugence-model-egress-validation`: harness over the 18 rows with injected fake components, fake-transport cases, negative-test matrix, redacted report generator, drift checks, secret-shape scanning; the suite runs with sockets refused and infrastructure-dependent rows can only be `NOT_EXECUTABLE_OFFLINE` | the owner-run live verifier's execution, after step 8 |
| 12 blocked until seventeen exact values | `STEP8_REQUIRED_VALUES` names them; `check_step8_designation` refuses any missing, placeholder, secret-shaped, mis-shaped or unverified value; `COMMISSIONING_STATUS` unchanged; the `live` verifier command refuses to run and names each undesignated value | the values, their independent check, the separate live-validation authorization, and a further record for production |

#### 0.4.2 — The seventeen values, each `UNDESIGNATED`

| # | Value (ruling 12) | Record field | Shape accepted |
| --- | --- | --- | --- |
| 1 | GCP project ID | `gcp_project_id` | 6–30 chars, lowercase letters, digits, hyphens, starting with a letter |
| 2 | GCP project number | `gcp_project_number` | digits only |
| 3 | MEU GCP service-account resource name | `meu_service_account` | `projects/<project>/serviceAccounts/<name>@<project>.iam.gserviceaccount.com` |
| 4 | deployment-platform identity mechanism | `deployment_platform_identity_mechanism` | `workload_identity_federation` or `native_gcp_workload_identity` |
| 5 | WIF pool/provider and constrained principal binding, or the native equivalent | `workload_identity_binding` | `WorkloadIdentityFederation(oidc_issuer, audience, subject_constraints, pool, provider, principal_binding)` or `NativeGcpWorkloadIdentity(path, no_static_key_evidence_ref)`, matching field 4 |
| 6 | full numeric Secret Manager version resource | `secret_version` | `projects/<project-id-or-number>/secrets/<secret>/versions/<n>`, numeric `<n>` |
| 7 | secret-level IAM-policy evidence reference | `iam_policy_evidence_ref` plus `iam_binding_scope = secret` | non-empty |
| 8 | Data Access audit-log configuration and retention reference | `audit_log_config_and_retention_ref` | non-empty |
| 9 | approved rotation-runbook reference | `rotation_runbook_ref` | non-empty |
| 10 | OpenAI organization ID | `openai_organization_id` | `org-` prefix |
| 11 | OpenAI project ID | `openai_project_id` | `proj_` prefix |
| 12 | OpenAI project service-account ID | `openai_service_account_id` | non-empty |
| 13 | OpenAI role and API-key scope evidence | `openai_role_and_key_scope_evidence_ref` plus `openai_key_scope = api.responses.write` | non-empty; scope exact |
| 14 | vendor spend-control evidence and classification | `vendor_spend_control_evidence_ref`, `vendor_spend_control_classification` | non-empty; `hard_stop` or `advisory` |
| 15 | designated-model availability evidence | `model_availability_evidence_ref` | non-empty and not the model name |
| 16 | applicable data-processing-terms reference | `data_processing_terms_ref` | non-empty |
| 17 | approved processing/data-residency region | `processing_region` | non-empty |

Every field is refused when it carries a placeholder token, whitespace padding or a
credential shape, and the record is refused unless `environment` reads `non-production`
and `verified_by` and `verified_at` name the independent check. Supplying all seventeen
closes only the infrastructure-designation blocker: the first live synthetic validation
needs the owner's separate explicit authorization, and production use another record.

## 1 — The finding that shapes this record

**AP-3 did not gate the live model provider, and its acceptance unblocks none of the
provider's own gates.** AP-3 (`IDP_VALIDATED_FIRST`) gates the authority plane's writes. The
provider is gated by rulings of another family, all ratified 2026-09-10 and all still
standing `[V]`:

| Gate | Ruling | What it says today |
|---|---|---|
| Where the call runs | D-2 `SEPARATE_EGRESS_UNIT` (`OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md` §4) | Outside the worker, in a Model Egress Unit (MEU). CR-5 keeps the worker's egress at the JWKS host, now the designated Cloudflare host and nothing else |
| Whether that unit may exist | CR-1 `SEPARATE_WORKER_UNIT` (`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md`) | Admits **one** companion deployment unit, the worker, by name. The MEU is a second; its boundary is specified and its existence is not `[V]` |
| Whether a credential may exist | D-3 `NO_CREDENTIAL_IN_THIS_DEPLOYMENT` | No provider credential and no genuine call until an external secret-manager integration, a rotation policy, an audit trail and a named custody owner are commissioned; `PLATFORM_ENVIRONMENT_VARIABLE` rejected `[V]` |
| Whether content may cross | D-4 (`SPEC_MODEL_EGRESS_UNIT.md` §4.4) | No genuine customer content or genuine call until exchange tenancy, least-privilege grants, retention and deletion, transport protection and production credential custody are separately verified |

So the honest answer to "configure the live provider now" is: two owner rulings and four
pieces of mechanism stand before the first genuine call, and none of them moved on
2026-09-11. This record puts the rulings to the owner and names the mechanism.

## 2 — What exists, precisely `[V]`

| Component | State |
|---|---|
| `packages/integration/model-egress-unit` 0.1.0 | The exchange (`meu_exchange` schema, three roles, forced RLS, tenant-required sessions), leasing, reconciliation, `OUTCOME_UNKNOWN`, retention and purge with tombstones, a digest-pinned migration runner, tested against PostgreSQL 16 (`ADR_MODEL_EGRESS_UNIT_REFERENCE_SLICE.md`); its one open divergence, what `request_digest` binds, was ratified closed by the owner on 2026-09-11 (`SPEC_MODEL_EGRESS_UNIT.md` §4.4.1, PR #1749: a composed commitment to the exact text through `minimized_context_digest`, the encoder pinned by frozen vectors, no `exchange.v2` authorized). No design question is open on the exchange |
| Its provider seam | `EgressProvider.execute(request, *, now, …)`; two shipped providers: `DeterministicFakeProvider` (labelled, refused in production) and `LiveEgressUnavailableProvider` (refuses `CREDENTIAL_NOT_COMMISSIONED`). `LIVE_VENDOR_EGRESS = False`; `tests/test_boundaries.py` fails the package if any module imports anything that can open a socket, reads the environment or reads a clock |
| A custody-port precedent | `packages/integration/cloud-scaling-credential-broker`: `CredentialBrokerPort` (`broker_authority_id`, `credential_profile`, `is_production_authoritative`, `materialize`) with an inert reference broker refused in production. The shape a provider-credential custody port should mirror |
| The worker's egress record | `deployment/governed-runtime-worker/EXTERNAL_DEPLOYMENT_EVIDENCE.json`: the designated JWKS host only; the MEU and every vendor host are forbidden destinations for the worker |
| Image gating | RW-2: the container gate set halts on `RESOURCE_BLOCKER_MIRROR_UNCONFIGURED` because the mirror coordinates (`registry_host`, `repository_prefix`, `secret_name`) are undesignated `[G]`; no production image of any unit exists. Designating them is an owner act that LP-6's production list depends on and that this ballot does not put, since it belongs to the RW family |
| Transport protection | `sslmode` set on no DSN `[G]` |
| Production role provisioning and a migration identity | Roles exist for a test cluster only; no credential custody for runtime or migration identities `[G]` |
| MEU ledger-kind schema | `LedgerEntry.payload` accepts any canonical dict; the kind-specific refusal of content-bearing keys is unbuilt `[G]` |
| Vendor-mix policy quantity and per-vendor reservation counter | Unbuilt; required before vendor-mix **enforcement** (D-5), not before a single-vendor call |
| Cost, rate and quota governance | Absent `[G]` |

## 3 — The ballot

Six decisions. LP-1 and LP-2 are the two rulings that gate everything; LP-3 to LP-6 shape
the validation slice. Recommended option first.

### LP-1 — CR-1: may the MEU exist as a deployment unit?

| Option | Consequence |
|---|---|
| **`ADMIT_MEU_AS_SECOND_COMPANION_UNIT`** (recommended) | CR-1 amended to admit exactly two companion units, each named: the governed runtime worker and the Model Egress Unit. Each carries its own egress record, image, credentials and gate set. Nothing else is admitted |
| `FOLD_MEU_INTO_WORKER` | Contradicts D-2 and reopens CR-5; refused as written |
| `NO_UNIT_YET` | The provider stays specified and unbuilt |

### LP-2 — D-3: what commissions provider-credential custody?

| Option | Consequence |
|---|---|
| **`CUSTODY_PORT_OVER_A_NAMED_SECRET_MANAGER`** (recommended) | A `ModelCredentialCustodyPort` in the MEU mirroring `CredentialBrokerPort`: `custody_authority_id`, `credential_profile`, `is_production_authoritative`, `materialize(request) -> short-lived handle`. The reference adapter is inert and refused in production. One production adapter, in its own package, against the secret manager the owner names; the MEU never reads a credential from its environment. Rotation policy: maximum credential age and rotation on any suspected exposure, both as fields the port asserts. Audit trail: every materialization appended to the ledger as identifiers and digests, never the secret. Custody owner: a named person |
| `PLATFORM_ENVIRONMENT_VARIABLE` | Rejected by D-3; not reopened here |
| `DEFER_CUSTODY` | No genuine call |

The owner named **Google Secret Manager** on 2026-09-11. The port is in 0.2.0. Two
questions follow from the name and are the owner's:

**LP-2a — how the unit authenticates to Google Secret Manager.** Reading a secret from
Secret Manager needs a Google identity. A long-lived service-account key held on the
hosting platform is itself a credential in the deployment, of exactly the kind D-3
refuses; it would move the problem, not solve it. Options: (recommended)
`WORKLOAD_IDENTITY_FEDERATION`, the unit presents an OIDC identity the hosting platform
issues and exchanges it for a short-lived Google token, which requires the platform to
issue one and a Google Cloud workload identity pool bound to it; `OWNER_OPERATED_HOST`,
the custody adapter runs on a host the owner operates with application-default
credentials, as the AP-3 verifier ran on the owner's machine, acceptable for the
validation call and not for production; `SERVICE_ACCOUNT_KEY_ON_PLATFORM`, refused.

**LP-2b — the record contract.** `EgressResult` refuses any provenance with
`genuine_call` other than `False`, and that refusal is what keeps a fixture from
passing for a provider. The amendment, when ruled: `genuine_call: True` is admitted only
for a result produced under a production posture by a provider adapter holding a
`CredentialLease` whose `is_production_authoritative` is `True`, and the result records
the lease id and the custody authority; every other combination stays refused. This is a
one-line contract change with a ratified precondition, and it is not made before the
ruling.

### LP-3 — Vendor, model and account designation

| Option | Consequence |
|---|---|
| **`ONE_VENDOR_ONE_MODEL_NONPROD_ACCOUNT`** (recommended) | The owner designates exactly one vendor, one model identifier, one API host (the MEU's only vendor destination), one non-production account with a hard spending cap set at the vendor, the data-processing terms accepted, and the region. Recorded in `packages/integration/model-egress-unit/MEU_LIVE_PROVIDER_DESIGNATION.json` (beside the package rather than under `deployment/`, because no MEU deployment unit exists to hold it), the way AP-3's designation was recorded. **Vendor designated 2026-09-11: OpenAI, `api.openai.com`.** The model identifier, account, terms and region are still `UNDESIGNATED` |
| `SEVERAL_VENDORS_AT_ONCE` | Requires D-5's policy quantity and reservation counter first; deferred |

### LP-4 — The validation protocol before the first genuine call (`MEU_LIVE_STATUS`)

| Option | Consequence |
|---|---|
| **`MATRIX_THEN_OWNER_ACCEPTANCE`** (recommended) | The AP-3 pattern: a status field `MEU_LIVE_STATUS` in `BLOCKED_PENDING_OWNER_RULINGS → PENDING_VALIDATION → MET / NOT_MET`; a fixed matrix, each row with a required result, executed on the owner's machine by a verifier that prints only redacted evidence; an acceptance report rendered from the record; `MET` only by the owner's statement. Rows: custody absent → `CREDENTIAL_NOT_COMMISSIONED`; credential never in any log, ledger row, exchange row or answer; egress to any host but the designated one refused; request digest binds the minimized context and a substituted prompt fails; the live answer carries `genuine_call: true` and `trust: UNTRUSTED_EVIDENCE`; TAP verifies the answer and an `INDETERMINATE` is a typed refusal, not a degraded result; purge replaces content with a tombstone on schedule; lease expiry after dispatch is `OUTCOME_UNKNOWN` and never a second billed call; a request over the token ceiling is refused before dispatch; a vendor error, timeout and malformed answer are typed outcomes |
| `FIRST_CALL_THEN_RECORD` | Refused: it is the shape D-3's last paragraph forbids |

### LP-5 — Cost and quota governance before the first call

| Option | Consequence |
|---|---|
| **`VENDOR_CAP_PLUS_BOUND_CEILING`** (recommended) | For the validation slice: the vendor account's hard spending cap, plus a per-request token ceiling bound into the authorized request (§4.1 inference parameters) that the MEU refuses to exceed. The durable per-vendor reservation counter of D-5 stays a production prerequisite, not a validation one |
| `FULL_D5_COUNTER_FIRST` | Correct for production; blocks validation on a design Policy Authority has not yet produced |

### LP-6 — What must be built before the validation call, and what only before production

| Option | Consequence |
|---|---|
| **`TRANSPORT_AND_LEDGER_KIND_FIRST`** (recommended) | Before the validation call: `sslmode=verify-full` on both MEU DSNs (content crosses the wire), and the MEU ledger-kind schema that refuses content-bearing keys. Before production, additionally: role provisioning and the migration identity under real custody, tenant-bound database identities if multi-tenant, the RW-2 mirror and a gated MEU image, and the D-5 counter. The validation call runs on a dedicated non-production database provisioned by the slice's own migration runner |
| `EVERYTHING_BEFORE_ANY_CALL` | Safer and slower; the owner may prefer it |

## 4 — Sequence, once LP-1 to LP-6 are ruled

1. **Records first.** CR-1 amendment text in the composition-root ADR (waits on LP-1); `MEU_LIVE_PROVIDER_DESIGNATION.json` (**done in part**, 2026-09-11); `MEU_LIVE_VALIDATION.json` at `BLOCKED_PENDING_OWNER_RULINGS` (**done**).
2. **Custody port and audit** in the MEU, with the inert reference adapter, tests that the port never surfaces a secret, and the ledger-kind schema (**done**, 0.2.0).
3. **Transport protection** on the MEU DSNs (**done** as a policy, 0.2.0; composed by no deployment yet).
4. **The vendor adapter**, in its own distribution (`packages/integration/model-egress-provider-<vendor>`), because the MEU's boundary tests rightly refuse sockets in the MEU itself; it implements `EgressProvider`, takes its credential only from the custody port, sends only the minimized context, and labels every answer untrusted. Its own boundary tests pin the single permitted host.
5. **The production custody adapter** for the named secret manager, in its own distribution.
6. **The verifier and the matrix run** on the owner's machine, then the acceptance report and the owner's statement, exactly as AP-3 was closed.
7. **Production** only after LP-6's second list is closed and each unit's gate set is green.

## 5 — What this record does not authorize

No credential anywhere, no environment variable, no fixture; no vendor SDK in any existing
package; no change to CR-5's worker clause; no change to the MEU's `LIVE_VENDOR_EGRESS`;
no served write on the authority plane (AP-3 `MET` did not serve one either); no AX-1, AX-2,
AX-3 or AX-5; nothing on the studio. A ratification implements nothing; the mechanism is
listed in §4 so that "ratified" and "built" stay different sentences.

## 6 — Next step

The owner rules LP-1 to LP-6, names the secret manager, the vendor, the model, the host,
the account and the custody owner, and the slice of §4 opens on its own branch with its own
record.
