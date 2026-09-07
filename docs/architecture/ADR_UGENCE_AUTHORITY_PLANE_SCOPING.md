# Ugence authority plane — scoping audit and ruling

**Status:** audit and ruling, 2026-09-06. Documentation only: this record amends no
package, route, test, contract, manifest or deployment artifact, and activates no
seam. It answers one product question and records the owner's ruling on the ballot
AP-1 to AP-5 that the question forces. It supersedes one earlier ruling, MA-3, in the
one respect §11 states, and reopens nothing else.

The question, as raised: developers reach the modules through the Governance Studio.
Should administrators have a separate web surface for the modules that must be
configured, and what would such a surface require?

Evidence labels: `[V]` verified against this repository at `f6d8d96f`, `[I]`
inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question, and the answer

**Yes to a second surface, and it is the authority plane: the place where the acts the
studio is ruled never to perform are performed.** Most of that plane is already built
and already composed. The role-grant directory, the approval state machine and the
approver-identity adapter exist as stores with durable backends, and one deployment
composes all three. What is missing is a verified identity in front of them, and a
surface through which an administrator loads or revokes a grant, because today that is
a Python call with a free-text `loaded_by` and no route, no command and no screen.

Module composition is not on this plane, and neither is the console's module registry:
both were ruled elsewhere (MA-1, MS-1) and are not reopened here.

## 2 — What exists `[V]`

| Package | Version, maturity | What it holds |
|---|---|---|
| `packages/integration/authority-directory` | 0.1.0, `REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED = False` | `SqliteAuthorityDirectory` with `put_grant` and `revoke_grant` over an append-only event ledger of `GRANTED` and `REVOKED` (`grants.py:189-195`; `sqlite.py:211-225`); one-hop delegation; committee reports; `DirectoryApproverEligibility`. Its own ADR records the gap this plane fills: "a grant is what an administrator loaded" and nothing proves it should exist (`ADR_UGENCE_AUTHORITY_DIRECTORY_SCOPING.md:126-130`). |
| `packages/integration/approval-workflow` | 0.2.0, same labels | The approval state machine, `ReviewDecision.GRANT / REJECT / REQUEST_CHANGES` (`states.py:54-59`), a sqlite store with hash-linked events, once-only consumption. Ruled never to approve, authenticate, mint authority or execute (`ADR_UGENCE_APPROVAL_WORKFLOW_SCOPING.md:169-171`). |
| `packages/integration/approver-identity-jwt` | 0.1.0, `ISSUER_VALIDATION = IN_PROCESS_ISSUER_ONLY` | Local RFC 9068 token validation under IA-1 to IA-5. Validation against a real enterprise issuer is unproven (`ADR_UGENCE_APPROVER_IDENTITY_ADAPTER_SCOPING.md:100-104`). |
| `deployment/governed-runtime-worker` | composition root | Composes the sqlite directory, the sqlite approval store and the JWT adapter (`composition.py:34-36,206`); `preflight` refuses a fixture identity or fixture eligibility in production posture (`:149-156`). The adapter ADR's sentence that "no deployment composes the review service" predates this and is stale `[I]`. |

## 3 — What a human decision does today `[V]`

The review service does not grant a permission. `submit_decision`
(`governed-review-service/.../service.py:591-626`) resolves the proof through the
identity port, binds it to the presented approver, checks eligibility through the
directory, and records `GRANT` or `REJECT` on one pending approval. The runtime's
input source consumes a `GRANTED` approval once, for one execution quantum
(`governed-review/.../source.py:216-218`), and the service appends an HE-1 linkage to
the audit ledger (`linkage.py:1-25`). No access, credential or kernel permission
changes: Decision Authority's `AccessGrant` is the only permission store, by ruling
(`ADR_UGENCE_AUTHORITY_DIRECTORY_SCOPING.md`, D-5).

**The approver.** With the JWT adapter configured the decision is `IDP_AUTHENTICATED`;
with the static adapter, or none, it is `PRESENTED_UNPROVEN`
(`identity.py:73-76,163-176`). The tenant comes from a verified claim (ID-4);
assurance is recorded and never enforced (ID-5); the studio relays the operator's
proof header unread (ID-1).

**The grants the eligibility check depends on.** Loaded by nobody through any
surface `[G]`. `put_grant` and `revoke_grant` are calls on the store with a
`loaded_by` or `actor` string. No route, no command, no screen.

## 4 — What SD-2 and MA-3 settle, and what a superseding ruling must say `[V]`

SD-2 forbids the studio from naming issue, activate, revoke, grant, authorize, clear
or execute in any operation id, path or summary (`test_v2_operation_ids.py:24-26`),
and from calling the named authority entry points (`test_architecture.py:129-135`).
The studio already relays a `GRANT` decision lawfully: the verb sits in the body of
`v2_review_submit_decision`, not in its name. SD-2 is untouched by this record.

MA-3 (`ADR_UGENCE_MODULE_ADMINISTRATION_SCOPING.md` §11) ruled two deployables and no
third front end. An admin plane is a third deployable. A ruling that admits one must
say which verbs it may name, where its backend lives, what identity gates its writes,
and that the studio's boundary is unchanged. §11 says those four things.

## 5 — Which verb each administrative operation names `[I]`

| Operation | Verb | Where it acts |
|---|---|---|
| Load a role grant | grant | `SqliteAuthorityDirectory.put_grant` |
| Revoke a role grant | revoke | `revoke_grant` |
| Decide an approval | grant (in the body) | the review service; already relayed by the studio |
| Activate a constitution | activate | `agent-constitution-activation`, permanently outside the studio |
| Issue a policy or constitution | issue | `policy-authority`, `agent-constitution-activation` |
| Tenant emergency stop | none of the seven | Risk Authority's own administrative path |
| Authorize, clear, execute | those three | ActionGate, the Autonomous Control Plane, the runtime: runtime authority, not administration |

## 6 — Where the other configuration lives, and stays `[V]`

- **Module composition** (providers, hooks, seam files): environment variables read
  once before the port binds, attested by the integrity gate and shown read-only by
  the Status panel (MA-2 as amended). Not this plane.
- **The console's nine module rows**: reach the studio by no ruled path (MS-1). Not
  this plane.
- **Governed content** (policy packs, constitutions, registrations, declarations):
  the studio's canvas and intake screens. Not this plane.

## 7 — Ballot AP-1 to AP-5 (five decisions, recommended option first; ruled in §11)

| # | Decision | Options |
|---|---|---|
| **AP-1** | Scope of the plane | **`AUTHORITY_PLANE_ONLY`**: role grants, approval decisions, constitution activation and issuance. `ADMIN_CONSOLE_WITH_SETTINGS`: also module composition and registry rows. `NO_ADMIN_PLANE`. |
| **AP-2** | Where the backend lives | **`ADMIN_ROUTES_ON_THE_WORKER`**: administrative routes on the governed runtime worker's review service, which already owns the sqlite stores, with the admin front end as its own deployable. `FOURTH_SERVICE`: a new Python service holding a second connection to the same single-node stores. |
| **AP-3** | Entry gate for writes | **`IDP_VALIDATED_FIRST`**: no administrative write ships until the JWT adapter is validated against a real issuer and `loaded_by` and `actor` are issuer-qualified subjects. `SHADOW_ADMIN_WITH_PRESENTED_ADMIN`: writes under `PRESENTED_UNPROVEN`. |
| **AP-4** | Verbs the plane may name | **`GRANT_REVOKE_ACTIVATE_ISSUE_ONLY`**, enforced by a test in the shape of SD-2 with the sense reversed: authorize, clear and execute fail its build. `ALL_SEVEN`. |
| **AP-5** | Reads before writes | **`READS_FIRST`**: grants, holders, committee reports and the approval queue may be served and displayed before AP-3 is met, labelled `PRESENTED_UNPROVEN`. `NOTHING_BEFORE_IDP`. |

**Why the recommended options.** AP-1 keeps the two rulings already made (MA-1, MS-1)
intact and gives the plane one coherent content: the acts. AP-2 follows where the
stores already are; a second writer process against single-node sqlite is the Posture
B problem the repository has refused before. AP-3 is the directory ADR's own warning
made into a gate: a grant nobody proved is not a grant, it is a typed string. AP-4
keeps runtime authority with the runtime: an admin plane that could authorize, clear
or execute would be the control plane under another name. AP-5 lets the plane exist
and be looked at before any identity provider exists, without recording anything.

## 8 — Ruling AP-1 to AP-5 (owner, 2026-09-06)

The recommended option is ratified in every case, under the owner's standing direction
that recommended defaults apply and the sequence proceeds without interruption.

| # | Ruling |
|---|---|
| **AP-1** | **`AUTHORITY_PLANE_ONLY`.** The plane's content is role grants, approval decisions, constitution activation and issuance, and nothing else. Module composition and the console's module registry are not on it. |
| **AP-2** | **`ADMIN_ROUTES_ON_THE_WORKER`.** Administrative routes live on the governed runtime worker's review service, which owns the stores. The admin front end is a separate deployable with its own address, contract and approved-operation set. |
| **AP-3** | **`IDP_VALIDATED_FIRST`.** No administrative write ships until the approver-identity adapter has been validated against a real enterprise issuer, and every `loaded_by` and `actor` recorded by the plane is an issuer-qualified subject. A write reached without an `IDP_AUTHENTICATED` subject is refused, not recorded as presented. |
| **AP-4** | **`GRANT_REVOKE_ACTIVATE_ISSUE_ONLY`.** The plane may name grant, revoke, activate and issue. A test in the shape of `test_v2_operation_ids.py` fails its build if any operation id, path or summary names authorize, clear or execute. |
| **AP-5** | **`READS_FIRST`.** Reads of grants, holders, committee reports and the approval queue may ship before AP-3 is met, each answer labelled with the identity proof the deployment can actually give. |

## 9 — What this record supersedes, and what it does not reopen

**Superseded.** MA-3 `TWO_DEPLOYABLES_UNCHANGED`, in one respect only: a third
deployable is admitted, and it is the authority plane's front end under AP-2. MA-3's
refusal of a third front end for module administration stands; the plane is not that.

**Not reopened.** SD-2 and the studio's allowlist, in every respect. MA-1, MA-2 as
amended, MA-4, MA-5, MS-1 to MS-5. CP-1 to CP-5 and the console's served and withheld
sets. HR-1 to HR-5, HE-1 to HE-5, ID-1 to ID-5, IA-1 to IA-5. The directory's D-5:
`AccessGrant` stays the only kernel permission store, and an organizational role never
becomes an API permission.

## 10 — What ratifying does not authorize

This ruling is documentation. No file outside this record changes under it.

- **No write before the identity gate.** AP-3 is the entry condition for every
  administrative write. Until the adapter is validated against a real issuer, the
  plane may serve reads only, and nothing it serves may be described as a grant
  anyone proved.
- **No settings screen.** The plane does not set providers, hooks, seam files or any
  environment variable, and it does not show the console's module rows. Those stay
  where MA-1, MA-2 and MS-1 put them.
- **No runtime authority.** Nothing on the plane authorizes an action, clears one or
  executes one. ActionGate, the Autonomous Control Plane and the runtime keep those
  three verbs, and the plane's own test refuses them.
- **No second writer.** No new service opens the worker's sqlite stores. Routes are
  added to the process that owns them.
- **No implementation begins here.** The next steps are, in order: the plane's
  contract and verb test; the worker's read routes under AP-5; the front-end shell over
  those reads; then, only after issuer validation, the write routes under AP-3. Each is
  its own slice with its own record.

## 11 — Sequence and ceiling

1. **Contract and verb test** for the plane, on the worker: documentation of the
   operations, and the reversed SD-2 test. Nothing served yet.
2. **Reads (AP-5):** grants for a principal, holders of a role, committee reports, the
   approval queue. Every answer carries `identity_proof`.
3. **Front-end shell** over the reads, its own deployable, its own approved-operation
   manifest and boundary verifier, in the studio's pattern.
4. **Issuer validation (AI-C, fact 10)** against a real enterprise identity provider,
   once the owner provisions one. This is the gate, and nothing in this repository
   can satisfy it alone.
5. **Writes (AP-3):** load and revoke role grants, activate and issue, each refusing a
   subject that is not `IDP_AUTHENTICATED`.

**Ceiling.** Every package on this plane is `REFERENCE_GRADE_SHADOW_ONLY` with
enforcement off, and every decision the repository can record today is
`PRESENTED_UNPROVEN`. Steps 1 to 3 do not change that and must say so on every answer.
Step 5 is the first point at which the platform could hold a grant that somebody
verifiably made, and it is behind a gate that only an identity provider outside this
repository can open.

## 12 — Implementation record, step 1 (2026-09-06)

Shipped on `deployment/governed-runtime-worker`, serving nothing. What the rulings
became, and where each claim is checked:

| Ruling | What landed | Where it is checked |
|---|---|---|
| AP-2 | `src/governed_runtime_worker/authority_plane.py`: the plane's contract as a frozen enumeration of eight `PlaneOperation`s under `/authority/`, and `authority-plane-contract.json`, its committed rendering. The worker's version is unchanged: no behaviour changed. | `tests/test_authority_plane_contract.py::test_the_committed_contract_is_the_module_rendered_without_drift` |
| AP-5 | Four reads: grants for a principal, holders of a role, a committee report, a grant's event history. Each carries the `PRESENTED_UNPROVEN` label until AI-C is validated. The approval queue is listed as a reuse of the review service's existing `review_list_queue`, not duplicated. | `::test_every_write_carries_the_identity_gate_and_every_read_the_proof_label`; `::test_nothing_is_served_and_no_plane_path_overlaps_the_review_routes` |
| AP-3 | Four writes: load a grant, revoke a grant, activate a constitution, issue a record. Each carries the gate: an `IDP_AUTHENTICATED` subject, else refused, never recorded as presented. | the same tests |
| AP-4 | `PERMITTED_VERBS` and `REFUSED_VERBS` partition SD-2's seven exactly. `verb_violations` scans every operation id, path and summary for authorize, clear and execute; the test fails the build on any hit. A self-check proves the scan catches a violation in each of the three scanned fields, and the dataclass refuses a write that names no permitted verb. | `::test_no_operation_id_path_or_summary_names_a_refused_verb`; `::test_the_verb_scan_actually_catches_a_violation`; `::test_the_permitted_and_refused_sets_partition_the_seven_sd2_verbs` |
| serves nothing | No plane path appears in the review service's `ROUTES`; every plane path is under `/authority/` and every served path is not; neither `composition.py`, `server.py`, `starter.py`, `workload.py` nor `__init__.py` imports the module. | `::test_neither_the_composition_nor_the_server_imports_the_plane` |

**Verified, not asserted.**

| Check | Result |
|---|---|
| `tests/test_authority_plane_contract.py` | 10 passed |
| worker CI suites (`test_config`, `test_preflight`, `test_maturity_and_boundaries`) | 46 passed |
| worker remaining suites | 13 passed, 4 skipped (the real-PostgreSQL end-to-end test, as it skips without a cluster) |
| review service `test_boundaries.py` and `test_http.py` | pass; the served surface is still exactly its seven routes |
| `scripts/check_package_import_boundaries.py` | 70 packages, no violation |

**What did not change.** No route is served. The review service, its `ROUTES`, the
studio, the console, every contract and every allowlist are as they were. The worker's
version stays 0.3.0 because nothing it does changed.

**One decision recorded rather than made quietly.** The approval queue is a reuse, not
a new operation. AP-5 names it as a read of the plane, and the review service already
serves it as `review_list_queue`; a second route for the same rows would be a second
account of the same queue. The contract lists it under `reused_existing`.

Steps 2 to 5 remain unimplemented. Step 4, issuer validation, cannot be taken inside
this repository.

## 13 — Implementation record, step 2 (2026-09-06)

Shipped as `governed-runtime-worker` 0.4.0: the four AP-5 reads, served; nothing
else of the plane. What the ruling became, and where each claim is checked:

| Ruling | What landed | Where it is checked |
|---|---|---|
| AP-5 reads | `src/governed_runtime_worker/authority_reads.py`: a router built from the contract's four read operations, mounted by `composition.py` beside `/healthz` over the `SqliteAuthorityDirectory` the composition already opened, for the worker's own tenant, at the injected clock. Grants for a principal, holders of a role in a scope, a committee report with its quorum, and a grant's append-only event history. | `tests/test_authority_reads.py` (12 tests); `tests/test_authority_plane_contract.py::test_reads_are_served_*` asserts the served surface is exactly the four contract reads by method, path, operation id and summary |
| AP-5 label | Every answer carries `read_authenticated: false`, `decision_identity_proof` (`IDP_AUTHENTICATED` when an identity port is composed, `PRESENTED_UNPROVEN` otherwise), the adapter's `issuer_validation` label, and the directory's provenance sentence. | `test_authority_reads.py::test_the_decision_proof_label_follows_*`; every `_ok` assertion |
| tenant and typing | No tenant, instant, proof or credential is taken from the caller. A foreign tenant's grants are not expressible and its grant ids read as unknown. An untyped identifier is refused before the directory is asked; a missing committee or grant is a typed not-found, never an empty success. | `::test_a_foreign_tenants_grant_id_*`; `::test_an_untyped_identifier_*`; `::test_a_missing_committee_*`; `::test_no_proof_or_credential_*` |
| AP-3 unchanged | No write is served. The contract now carries `served` per operation, reads true and writes false; no module of the worker names a write path or a write method outside the contract; the composition imports the reads module and nothing else of the plane. | `test_authority_plane_contract.py::test_no_module_of_the_worker_names_a_write_path_*`; `::test_the_composition_mounts_the_reads_*`; the drift test over the regenerated `authority-plane-contract.json` |
| version | 0.3.0 → 0.4.0 at every pinned site: `version.py`, the Dockerfile label, `EXTERNAL_DEPLOYMENT_EVIDENCE.json` (version and the routes sentence), the package docstring. | `test_container_artifacts.py` and `test_maturity_and_boundaries.py` compare the evidence file to `__version__` |

**Verified, not asserted.**

| Check | Result |
|---|---|
| `test_authority_plane_contract.py` and `test_authority_reads.py` | 22 passed |
| worker's other suites (`test_config`, `test_preflight`, `test_maturity_and_boundaries`, `test_container_artifacts`, `test_ledger_read`, `test_start_relay`, `test_end_to_end`) | 70 passed, 4 skipped (the real-PostgreSQL end-to-end test) |
| `scripts/check_package_import_boundaries.py` | clean |

**What did not change.** The review service and its seven `ROUTES`; the studio, whose
review client still reaches exactly those seven and cannot reach `/authority/`; every
contract and allowlist elsewhere. `ENFORCEMENT_ENABLED` stays false and every label
stays `REFERENCE_GRADE_SHADOW_ONLY`.

**Two decisions recorded rather than made quietly.**

- **The composition mounting is untested by a running composition here.** `compose()`
  needs PostgreSQL, which this environment lacks, so the mount is proven three ways
  short of that: the router is built and exercised over a real sqlite directory, the
  composition's import of it is asserted structurally, and the end-to-end test that
  composes for real will exercise it in CI, where it runs against a cluster. Closed
  in §15: that test now exists and ran over a real PostgreSQL 16.
- **The label names decisions, not reads.** A field called `identity_proof` on an
  unauthenticated read would imply the read was proven. The answer says
  `read_authenticated: false` and `decision_identity_proof`, so what the deployment
  can prove about a decision is stated without being borrowed by the read.

Steps 3 to 5 remain unimplemented. Step 4, issuer validation, cannot be taken inside
this repository.

## 14 — Implementation record, step 3 (2026-09-06)

Shipped as `apps/authority-plane` 0.1.0, the third front end, under AP-2. A read-only
shell over the four AP-5 reads, in the studio's boundary pattern. What the ruling
became, and where each claim is checked:

| Ruling | What landed | Where it is checked |
|---|---|---|
| AP-2, its own deployable | A Vite and React app with its own address (dev port 3200), proxying `/api` to the worker's private TLS listener. It shares no code with the studio or the console. | `apps/authority-plane/package.json`, `vite.config.ts`; the CI workflow `authority-plane-frontend-ci.yml` |
| AP-5, the four reads | Four screens: Grants by principal, Holders of a role in a scope, a Committee report counted against its quorum, and a grant's event history; a grant row links to its events with one further GET. | `tests/screens.test.tsx` (4 tests) |
| AP-5, the label | Every answer is rendered under an identity banner repeating the worker's own words: the read was not authenticated; the decision proof the deployment can give; the adapter's issuer validation; the directory's provenance sentence. The app's header, its standing notice and its footer say the plane reads only, that the writes wait on the identity gate, that nothing on it authorizes, clears or executes, and that no identity provider is provisioned. | `screens.test.tsx::says on its face what it cannot do`; the banner assertions in every read test |
| the boundary | `security/approved-operations.json` names the four reads it may consume and the four writes it may not, and binds itself to the worker's committed contract by sha256. `scripts/verify-boundary.mjs` checks the manifest against that contract (an approved id must be a served read; the forbidden set must equal the contract's unserved writes), the client's real call sites, and that no file but `src/api/client.ts` opens an HTTP connection. | `npm run verify:boundary`; `tests/boundary.test.ts` (7 tests), including that the verifier can fail on a sneaky fetch, a revoke path and a write method |
| honest empties | An empty list, a typed refusal and an unreachable worker are rendered differently, and the app issues GETs only. | `screens.test.tsx::an empty list is shown as empty…`; the method assertions on every recorded call |

**Verified, not asserted.**

| Check | Result |
|---|---|
| `npm run verify:boundary` | OK, 4 reads consumed, contract `9dd18a74…` |
| `npm run type-check` | exit 0 |
| vitest | 2 files, 11 passed |
| `vite build` | exit 0 |

**What did not change.** The worker, its contract and its tests; the studio, the
console, and every other contract and allowlist. The plane's client has no method
that could name a write, so AP-3 is not touched by this step.

**Two decisions recorded rather than made quietly.**

- **The verifier does not scan prose for the three refused verbs.** The app's own
  copy says it never authorizes, clears or executes, which a verb scan over source
  would flag. The AP-4 rule is enforced where it belongs, on the contract, by the
  worker's test; this app's verifier enforces paths, operation ids and methods.
- **A lockfile is committed.** This is a new app with its own CI, and the studio's
  precedent is a committed lockfile with `npm ci`; the console's absence of one was
  left alone under MA-4 because adding it was not that ruling's to make.

**Not proven here.** The app was not driven against a live worker in this
environment, because composing the worker needs PostgreSQL. Its screens are proven
against the worker's answer shapes as `authority_reads.py` produces them; the
end-to-end that joins the two is a later step's work once a cluster and an issuer
exist.

Steps 4 and 5 remain unimplemented. Step 4, issuer validation, cannot be taken inside
this repository, and step 5's writes wait on it.

## 15 — Verification addendum, step 2 over the real composition (2026-09-07)

§13 recorded one thing it could not do: exercise the read mount on a composed worker,
because `compose()` needs PostgreSQL. This addendum closes that gap and changes nothing
else. No source file of the worker, the plane app, the studio or any contract moved.

**What landed.** One end-to-end test,
`deployment/governed-runtime-worker/tests/test_end_to_end.py::test_the_authority_reads_are_served_by_the_composed_worker_and_no_write_is`,
in the suite CI runs over a real PostgreSQL 16 with the in-process issuer, whose
"skipped is not passed" step already refuses a run without a server. Over the worker
`compose()` built, not a hand-built router, it proves:

| Claim | How |
|---|---|
| the four AP-5 reads answer from the directory the composition opened, for its tenant, at its clock | grants for a principal, holders of a role, a committee report and a grant's event history, each read after the clock is advanced and each `as_of` equal to the composition's clock |
| the label is the composed one | with an identity port composed every answer says `decision_identity_proof: IDP_AUTHENTICATED`, `read_authenticated: false`, `issuer_validation: IN_PROCESS_ISSUER_ONLY` |
| the reads show the grant the decision route consumes | a signed `GRANT` through `/review/decisions` records `IDP_AUTHENTICATED`; the grant it was eligible by is the grant the read returns before and after |
| a proof header is neither required nor read | the same read with and without the proof header returns the same body |
| a revocation is visible | the event history reads `GRANTED, REVOKED`; the revoked holder drops out of the holders list; a missing grant is `NOT_FOUND`; an untyped identifier is `REFUSED_UNTYPED` |
| no AP-3 write answers | the contract's four write operations, driven from `PLANE_OPERATIONS`, each meet the framework's 404 or 405 on the composed app |
| row 8 | neither DSN nor the token appears in any answer |

**Verified, not asserted.**

| Check | Result |
|---|---|
| worker suite over PostgreSQL 16.13, `UGENCE_DE_TEST_PG` set | 97 passed, 0 skipped |
| the new test with the read mount removed from `composition.py` | fails, `404 == 200` on the first read; the mount restored afterwards |

**What this does not change.** The maturity of every package on the plane, the
`PRESENTED_UNPROVEN` ceiling on every decision the repository can record, and §14's
"not proven here": the plane app was still not driven against a live worker, since its
screens are proven against the worker's answer shapes and the join of the two waits on
a cluster and an issuer together. Steps 4 and 5 remain as §14 left them.
