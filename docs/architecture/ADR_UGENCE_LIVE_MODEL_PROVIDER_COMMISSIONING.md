# ADR — Commissioning a live model provider: what AP-3 unblocked, what it did not, and the ballot LP-1 to LP-6

**Status:** ballot, documentation only. Nothing is implemented, configured, credentialed,
composed or activated by this record. Recommended defaults are listed first and apply only
once the owner ratifies them, as the repository's standing practice provides.

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
