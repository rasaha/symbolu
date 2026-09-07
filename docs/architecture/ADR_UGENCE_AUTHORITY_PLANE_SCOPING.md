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

## 16 — Scoping audit: the administrative writes (2026-09-07)

**The question.** Can the plane's administrative screens, the ones on which an
administrator loads and revokes role grants, ship before an enterprise identity
provider has been validated, which AP-3 `IDP_VALIDATED_FIRST` and §11 step 4 put ahead
of every write?

**The answer.** Two of the four writes can, and two cannot, for reasons that have
nothing to do with each other.

- **Grant and revoke** act on `SqliteAuthorityDirectory`, which this worker composes
  and already exposes to the four reads `[V]` (`composition.py`, `authority_reads.py`).
  The identity gate they need already exists in this process: the decision route
  refuses a proof that does not authenticate a human subject, fails closed when the
  port cannot answer, and records the issuer-qualified subject `[V]`
  (`ugence_governed_review_service.service.ReviewService._resolve_identity`;
  `tests/test_end_to_end.py`, `IDP_AUTHENTICATED`). What step 4 adds is not code: the
  adapter's JWKS URL, issuer and audience are configuration, and its validation against
  a real issuer is evidence the owner supplies. The label the adapter puts on every
  answer, `issuer_validation: IN_PROCESS_ISSUER_ONLY`, already says which evidence
  exists `[V]` (`ugence_approver_identity_jwt.version.ISSUER_VALIDATION`).
- **Activate and issue** act on `ugence_agent_constitution_activation` and
  `ugence_policy_authority`, which this worker does not compose `[V]` (`composition.py`
  imports neither). Serving them would mean either a second composition root for those
  stores, which §10 refuses as a second writer, or composing them into the worker,
  which is its own scoping.

**What AP-3 actually guards, read again `[I]`.** Its sentence has two clauses: no write
ships before issuer validation, and a write without an `IDP_AUTHENTICATED` subject is
refused, never recorded as presented. The second clause is the invariant; the first was
sequencing chosen when no gate code existed. The gate now exists and is proven over a
real PostgreSQL with a signed proof (§15). A write behind that gate, with no
`PRESENTED_UNPROVEN` path at all, keeps the invariant. What it cannot claim is that the
subject was proven by a real issuer, and the answer must say so on its face.

**What the screens need that the reads did not `[G]`.** A proof. The plane app holds
no credential today and forwards none (§14). A write needs the operator's issuer token
on the same header the decision route reads, `X-Ugence-Approver-Proof`, and nothing
else: the app has no login of its own, because the identity provider is the login.

### 16.1 — Ballot AW-1 to AW-5 (five decisions, recommended option first)

| # | Decision | Options |
|---|---|---|
| **AW-1** | Writes before issuer validation | **`GATED_WRITES_BEFORE_ISSUER_VALIDATION`**: the grant and revoke writes ship now behind the identity gate; every write answer carries `identity_proof`, the subject reference and `issuer_validation`; supersedes AP-3 in its sequencing clause only. `WAIT_FOR_IDP`: build nothing until the owner provisions an issuer. |
| **AW-2** | Which writes this step | **`DIRECTORY_WRITES_ONLY`**: grant and revoke; activate and issue stay unserved because the worker composes neither store. `COMPOSE_ACTIVATION_INTO_THE_WORKER`: widen the worker now. |
| **AW-3** | How the app carries the proof | **`PROOF_PRESENTED_PER_WRITE_NEVER_STORED`**: the operator presents the issuer token in a session-only panel; it is sent on writes only, never on reads, never persisted, and the app has no login flow. `APP_OIDC_FLOW`: the app performs the browser login itself, which needs the issuer that does not exist. |
| **AW-4** | The intake shape | **`TYPED_INTAKE_DERIVED_ID`**: the load form takes `RoleGrant`'s typed fields and nothing else (principal id, kind, display reference, quorum; role; scope; issued and expiry instants; authority reference; committee membership), the worker derives `grant_id` by `grant_id_for`, and a replayed identical load answers `ALREADY_LOADED` with the standing grant. Revoke takes a reason. Delegated grants are not on the form this step. `FREE_JSON_BODY`. |
| **AW-5** | The gate on writes | **`STRICTER_THAN_DECISIONS`**: no proof, an unauthenticated proof, a non-human actor, an expired proof, a missing, ambiguous or foreign tenant claim, or a port that cannot answer is refused with a typed reason, and a worker composed without an identity port refuses every write (`REFUSED_NO_IDENTITY_PORT`); there is no presented-approver fallback as the decision route has. `SAME_AS_DECISIONS`: allow the configured-tenant fallback. |

**Why the recommended options.** AW-1 keeps AP-3's invariant and drops only the
ordering it imposed when nothing enforced it. AW-2 follows where the stores are, as
AP-2 did. AW-3 is the only honest way to carry a proof before an issuer exists: the app
never mints, stores or refreshes one. AW-4 makes the load a typed intake in the studio's
FD-4 sense, with the id derived so a replayed file is one grant, not two. AW-5 is
stricter than the decision route because a grant is the basis of a decision: a decision
under a configured tenant is auditable against its grant; a grant under a configured
tenant has nothing behind it.

### 16.2 — Ruling AW-1 to AW-5 (2026-09-07; AW-1 reversed by the owner the same day, §18)

The recommended option was applied in every case, on the owner's instruction to scope
and build the plane's administrative screens, under the standing direction that
recommended defaults apply. **AW-1 supersedes AP-3 in one respect:** the grant and
revoke writes may ship before the adapter is validated against a real issuer. Every
other word of AP-3 stands, and §10's "no write before the identity gate" now reads as
what it always meant: no write is recorded without an `IDP_AUTHENTICATED` subject.
§11 steps 4 and 5 are reordered for these two writes; activate and issue keep the
original order.

**Reversed.** On the same day, asked which of these decisions needed the owner's own
word, the owner ruled AW-1 `NO — REVERSE` and AP-3 controlling (§18). AW-2 to AW-5
stand. The paragraph above is kept as the record of what was applied and for how long.

**What ratifying does not authorize.** No activation or issuance route. No login flow,
token storage or refresh in the app. No settings screen, no runtime verb (AP-4 stands),
no second writer, no change to SD-2 or the studio. No claim, on any screen or in any
answer, that a subject was validated by a real issuer while `issuer_validation` says
otherwise.

## 17 — Implementation record, the two gated writes (2026-09-07; served for one merge, then unserved under §18)

Shipped as `governed-runtime-worker` 0.5.0 and `apps/authority-plane` 0.2.0 in PR
#1697, merged at `db055f3c`. The owner's reversal of AW-1 (§18) took the two writes out
of service in the next change; this section stands as the record of what was built and
proven, all of which remains in the worker. What each ruling became, and where it was
checked at the time:

| Ruling | What landed | Where it is checked |
|---|---|---|
| AW-1, the two writes | `authority_writes.py` serves `POST /authority/grants` and `POST /authority/grants/{grant_id}/revoke`, built from the contract's operations, mounted by `composition.py` beside the reads. Every recorded answer carries `identity_proof: IDP_AUTHENTICATED`, the subject reference, the authentication reference and `issuer_validation`. The contract's `served` set is now the four reads plus these two; `SERVED_WRITES` replaces the all-or-nothing flag. | `tests/test_authority_writes.py` (36 tests); `test_authority_plane_contract.py`, updated for the served set, the drift-tested rendering (sha256 `fcda3520…`) and the rule that only `authority_writes.py` names the directory's write methods |
| AW-2, directory writes only | Activate and issue stay unserved and answer 404 or 405 on the composed app; the plane app's manifest names them forbidden and its client cannot name them. | `test_authority_plane_contract.py::test_reads_and_the_two_directory_writes_are_served…`; `apps/authority-plane/tests/boundary.test.ts` |
| AW-3, the proof per write | A session panel takes the issuer token, held in React state only, sent on the two writes on `X-Ugence-Approver-Proof`, never on a read, never persisted; without one every write control is disabled and the client sends nothing. | `tests/screens.test.tsx`: the read-carries-no-header assertions, the disabled-form test, the header assertions on the load and the revoke |
| AW-4, the typed intake | The load body is `RoleGrant`'s typed fields and nothing else; unknown keys, untyped tokens, naive or unparsable instants, a bad kind and a negative quorum are refused before the directory is asked; the worker derives `grant_id` and an identical replay is `ALREADY_LOADED` with the standing grant; a second revoke is `ALREADY_REVOKED`; a foreign tenant's grant reads as unknown. | `test_authority_writes.py`: the intake parametrisation, the replay test, the revoke tests |
| AW-5, the gate | No identity port, no proof, a proof that authenticates nobody, a `PRESENTED_UNPROVEN` identity, a non-human actor, an expired proof, a port that cannot answer, a missing, ambiguous or foreign tenant claim: each a typed 409 and nothing recorded. The static fixture adapter, which relabels everything presented, cannot satisfy the gate; the tests prove that too. | `test_authority_writes.py::test_the_gate_refuses…` (nine cases), `::test_a_worker_without_an_identity_port…`, `::test_a_port_that_cannot_answer_fails_closed` |
| the loop, end to end | Over the real composition with the in-process issuer, a load with a signed admin proof is recorded under the admin's subject; the grant it loaded is the grant a signed decision is then eligible by; the revoke appends its event under the admin's subject. | `test_end_to_end.py::test_an_administrator_loads_a_grant_through_the_gated_write…` |

**Verified, not asserted.**

| Check | Result |
|---|---|
| worker suite over PostgreSQL 16.13, `UGENCE_DE_TEST_PG` set | 126 passed, 0 skipped |
| the end-to-end write test with the write mount removed from `composition.py` | fails, `405 == 409` on the first write; the mount restored afterwards |
| plane app: `npm run verify:boundary`, `npm run type-check`, vitest, `vite build` | OK with 6 operations consumed, exit 0, 16 passed, exit 0 |
| studio SD-2 verb test, package import boundaries, directory package suite | 11 passed; OK; passed |
| the plane app driven against the composed worker 0.5.0 with a signed token, by hand | a load recorded under `https%3A%2F%2Fissuer.test\|root-admin`, a revoke recorded, both shown on the screens as captured for the explainer |

**What did not change.** The studio, the console, SD-1 and SD-2, the review service's
seven routes, the directory package and the identity adapter. No environment variable
was added: the writes ride on the identity port the worker already composes from
`UGENCE_REVIEW_IDENTITY_*`.

**Three decisions recorded rather than made quietly.**

- **The revoke box stays open after a recorded revoke.** The screen re-reads the list so
  the revoked grant drops out, and keeps the recorded answer visible where the operator
  acted; closing it is the operator's act.
- **A load's window is validated by `Validity` alone.** The worker refuses a window that
  ends before it starts because the contract type does; it does not refuse a window in
  the past or far future, since a directory that records history may be loaded with one.
- **The proof label is checked, not only the `authenticated` flag.** A port answering an
  authenticated identity labelled `PRESENTED_UNPROVEN` is refused, so a fixture adapter
  composed in test mode can never make a write record.

**Not proven here.** The adapter against a real enterprise issuer: `issuer_validation`
still reads `IN_PROCESS_ISSUER_ONLY` on every write answer, and the maturity of every
package on the plane is unchanged. Step 4 of §11 remains the owner's.

## 18 — Owner ruling: AW-1 reversed, AP-3 controlling (owner, 2026-09-07)

Asked which of the §16 decisions needed the owner's own word rather than a standing
default, the owner ruled on AW-1 alone. The ruling, in the owner's terms:

> **AW-1 = NO — REVERSE. AP-3 remains controlling.** The load and revoke grant-write
> implementations may remain in the codebase, but they must not remain live or served
> before the identity adapter has been validated end to end against at least one real
> enterprise identity issuer. Until that validation is completed: load and revoke remain
> unserved in the worker contract; the corresponding application controls remain
> unavailable; attempts against those routes return the repository-defined unserved
> response, currently 405; the existing in-process issuer evidence establishes
> implementation and conformance only and must not be represented as enterprise
> identity validation. Validation against the real issuer must cover, at minimum,
> issuer, audience, JWKS trust, tenant claim, actor-type claim, and the worker's refusal
> behaviour for invalid or mismatched identity assertions. Once that validation is
> recorded, the two already-built writes may be re-served without reopening their
> functional design unless the validation exposes a contract incompatibility. AW-1
> reverses only the temporary sequencing change that allowed these writes to ship before
> issuer validation. It does not repeal or otherwise modify AW-2 through AW-5.

### 18.1 — What the reversal became

Shipped as `governed-runtime-worker` 0.5.1 and `apps/authority-plane` 0.2.1.

| Term of the ruling | What landed | Where it is checked |
|---|---|---|
| unserved in the worker contract | `authority_plane.SERVED_WRITES` is empty; `IMPLEMENTED_WRITES` names load and revoke; the committed contract renders `served.writes: []`, the two as `implemented_unserved_writes`, and a note that the in-process evidence is conformance only (sha256 `a0227d16…`). | `test_authority_plane_contract.py::test_no_write_is_served_under_ap3_while_two_are_implemented`, `::test_the_committed_contract_says_what_is_not_on_the_plane` |
| implementation remains, not live | `authority_writes.py` is unchanged in behaviour; its router registers only the writes the contract names served, so the composed worker registers none. The `serve` parameter exists so tests can exercise the implementation explicitly. | `test_authority_writes.py::test_by_default_the_router_registers_nothing…`; every other test in that file builds the router with `serve=IMPLEMENTED_WRITES` |
| the unserved response | on the composed worker `POST /authority/grants` answers 405 (a read shares the path) and `POST /authority/grants/{grant_id}/revoke` answers 404, proof or not, and nothing is recorded | `test_authority_plane_contract.py::test_reads_are_served_no_write_is…`; `test_end_to_end.py::test_the_composed_worker_serves_no_write_while_the_implementation_conforms_over_the_real_adapter` |
| application controls unavailable | the plane app's token panel, Load grant screen and revoke action are removed from the built app; its client names no write, sends no proof header, and its manifest forbids all four writes, bound to the new contract hash. The removed files remain in history at `c3b1ad8c`. | `apps/authority-plane/tests/screens.test.tsx`, `boundary.test.ts`; `npm run verify:boundary` |
| in-process evidence is conformance only | the contract, the worker README, the app's standing notice and every relevant docstring say so in those words; the end-to-end test that exercised the writes over the real composition now runs them on a conformance harness beside the composed worker, never through it | the same tests; `deployment/governed-runtime-worker/README.md` |

### 18.2 — Verification of the reversal

| Check | Result |
|---|---|
| worker suite over PostgreSQL 16.13, `UGENCE_DE_TEST_PG` set | 128 passed, 0 skipped |
| the contract with `SERVED_WRITES` set back to the two writes, everything else unchanged | the drift test and the served-set tests fail; restored afterwards |
| plane app: `npm run verify:boundary`, `npm run type-check`, vitest, `vite build` | OK with 4 reads consumed against contract `a0227d16…`, exit 0, 11 passed, exit 0 |
| studio SD-2 verb test; package import boundaries | 11 passed; OK |

### 18.3 — What re-serving requires

When the owner records the validation the ruling names (issuer, audience, JWKS trust,
tenant claim, actor-type claim, and the worker's refusal behaviour for invalid or
mismatched assertions, against at least one real enterprise issuer), re-serving is:
`SERVED_WRITES = IMPLEMENTED_WRITES` in `authority_plane.py`, the contract regenerated,
the plane app's manifest re-bound to the new hash with the two writes approved, and the
app-side controls restored from `c3b1ad8c`. The functional design is not reopened
unless that validation exposes a contract incompatibility.

## 19 — Owner ruling AX-1 to AX-5: where the five pending acts execute (owner, 2026-09-07)

This ruling is documentation. No file outside this record changes under it, and
nothing here is implemented before AP-3 is met.

### 19.1 — The audit it answers

Asked where the plane's five pending acts should execute, the audit established, from
the repository: activate and issue act on the `SqlitePolicyRegistry` that the studio
deployment opens once with deny-all verifiers and a refusing signer, a store with a
process owner that SD-2 forbids from naming either act `[V]`; tenant emergency stop is
implemented as `AuthorityLifecycleService.emergency_stop` under the capability
`authority.lifecycle.emergency_stop`, over an RA-6 authority store that no deployable
composes `[V]`; agent suspension is a targeted RA-6 subject revocation over the same
store, since execution assurance emits `EXECUTION_EFFECT_MISMATCH` into the RA-6 intake
and RA-6 owns authority consequences `[V]`; credential grants are single-use with a
lifetime of at most fifteen minutes, held in memory, with no revocation operation and
no deployable composing the broker `[V]`; and only the governed runtime worker composes
the identity adapter `[V]`.

### 19.2 — The ruling

| # | Ruling |
|---|---|
| **AX-1** | **`COMPOSE_STATUS_STORE_IN_THE_WORKER`.** No deployable owns the RA-6 status store, so composing it into the worker establishes the first operational writer rather than duplicating one. The worker may then host tenant emergency stop, targeted agent or subject suspension, authority epoch advancement, and the status reads required before governed operations. Agent suspension is a targeted RA-6 authority revocation, not a new independent governance capability. A separate Risk Authority service would add a deployment and a network boundary without solving an ownership conflict. |
| **AX-2** | **`MOVE_REGISTRY_TO_THE_WORKER`, with an atomic no-dual-owner cutover.** The studio must not remain the physical owner of an authoritative policy registry while forbidden from exposing its writes. After the move the worker owns the one registry instance and the activation and issuance composition; the studio uses read-only relay routes and never opens or writes the registry file; no second registry copy is created. **A transition period in which both processes open the registry independently is prohibited.** Sequence: (1) add worker-owned registry composition; (2) add an authenticated read relay; (3) move the studio's reads to the relay; (4) remove the studio's registry opening; (5) only then commission activation or issuance routes. |
| **AX-3** | **`OWNER_PROVISIONED_SIGNER_PORT`.** A file key is unsuitable: repository, image, filesystem and rotation risk. The signer port must be capable of being backed by AWS KMS, Google Cloud KMS, Azure Key Vault, HashiCorp Vault, or an enterprise HSM or signing service. The worker receives only a signer interface and a key reference, never exportable private-key material. Issuance stays unavailable when no signer is configured, the key reference is invalid, the signer cannot establish its issuer identity, the requested tenant is outside the configured key scope, the key is disabled or expired, or AP-3 identity validation has not succeeded. This is fail-closed configuration, not a fallback to an internal key. |
| **AX-4** | **`NO_PLATFORM_CREDENTIAL_REVOCATION_ACT_IN_THIS_PHASE`.** Ugence does not build a provider-independent credential-revocation act in this phase. Single-use grants, bounded lifetime and authority-epoch advancement stop future issuance and replay. Revocation of an already issued provider credential remains the responsibility of the external credential provider or a later provider-specific adapter. What is not proven, and must not be claimed: that epoch advancement revokes a credential an external provider has already materialized, cancels an active cloud session, or revokes a downstream token whose lifetime and custody are outside the broker. |
| **AX-5** | **`VERIFIED_PRINCIPAL_PLUS_DIRECTORY_GRANT`.** The chain is: enterprise identity provider authenticates the human; the AP-3 identity adapter verifies issuer and principal; the authority directory verifies a scoped grant; the `WriterAuthorizer` admits the exact capability; the RA-6 lifecycle write proceeds. The worker receives a verified principal context from the identity adapter and then requires a directory grant for the exact tenant, the exact authority role, the exact capability, a permitted target scope, an effective time window, and a non-revoked delegation. For emergency stop, a write is allowed only when identity is verified, the issuer is trusted, the directory grant is active, the tenant matches and the capability matches. A platform administrator role alone never implies emergency-stop authority. |

### 19.3 — What this ruling supersedes

- The studio deployment's ownership of the authoritative policy-registry process
  (`deployment/governance-studio/.../activation.py`, `app.py`), and §5's placement of
  activation "permanently outside the studio" without a named home.
- Any assumption that the studio may write activation or issuance state.
- The absence of a deployable owner for RA-6 lifecycle state, and §5's row placing the
  tenant emergency stop on "Risk Authority's own administrative path" without a process.
- Any implication that emergency stop requires a separate Risk Authority service.
- Any requirement for generic credential revocation in the present phase.
- Any reading of a presented human reference as authenticated authority.

AP-1 to AP-5, AW-2 to AW-5, §18 (AP-3 controlling), §10's "no second writer", SD-1,
SD-2, D-5 and CR-3 are not reopened.

### 19.4 — What this ruling does not authorize

- Implementation before AP-3 is met.
- Any unauthenticated authority-plane write.
- Activation or issuance merely because the registry moved.
- Issuance without an owner-provisioned signer.
- Private keys in the repository, the image, an environment file or a SQLite database.
- Direct studio writes to either authority store.
- A second policy registry or a second RA-6 store.
- LIVE execution.
- Credential issuance or custody.
- Provider-side credential revocation.
- Broad tenant suspension from a subject-targeted revocation.
- Treating identity-provider authentication as organizational authority.
- Treating a directory grant as proof of human identity.

### 19.5 — Sequence behind AP-3

Nothing below starts before the enterprise issuer validation §18 requires is recorded.

1. **AX-1, composition:** the worker composes the RA-6 authority store and lifecycle
   service; the plane's contract gains the emergency-stop, epoch-advance and targeted
   subject-revocation operations, unserved; the `WriterAuthorizer` is composed per AX-5
   over the identity port and the directory.
2. **AX-2, cutover, in the ruled order:** worker-owned registry composition; the
   authenticated read relay; the studio's Authority and Constitution reads moved to it
   under a v2 amendment; the studio's registry opening removed; only then activation
   and issuance routes commissioned, unserved.
3. **AX-3, signer:** the signer port composed from configuration, fail closed on every
   condition in AX-3; issuance served only when the port answers and AP-3 is met.
4. **Re-serving:** each act is named served in the contract only with its own record,
   after AP-3, under AX-5's condition; the two grant writes follow §18.3.

In one sentence, the owner's own: the studio displays and requests; the authority-plane
worker authenticates, authorizes and writes; each authoritative store has one process
owner; external custody remains external.

## 20 — AP-3 validation protocol, and its status (owner, 2026-09-07)

This section is documentation. It fixes what "validated end to end against at least
one real enterprise identity issuer" (§18) means in evidence, so that AP-3 cannot be
declared met by choosing an identity provider, writing an OIDC adapter, or running a
fixture. Its current status line is the only status the repository may claim.

**AP-3 status: `BLOCKED_PENDING_OWNER-PROVISIONED_ENTERPRISE_IDP_TEST_TENANT`.**

No real enterprise issuer has been designated. The in-process issuer used by the
worker's tests is implementation and conformance evidence only (§18). A self-signed
fixture or a local mock is not a substitute and must never be recorded as satisfying
this gate.

### 20.1 — What the owner supplies

Configuration, not secrets. The issuer URL, audience and claim names are
configuration; client secrets, private keys and test tokens remain in the identity
provider, the CI secret store or approved runtime custody. The committed record is
`deployment/governed-runtime-worker/AP3_ENTERPRISE_ISSUER_VALIDATION.json`, whose
fields are:

| Field | Meaning |
|---|---|
| `ap3_enterprise_issuer` | issuer product and non-production test tenant (Entra ID, Okta, Google Workspace, or another OIDC issuer) |
| `issuer` | the expected issuer identifier |
| `audience` | the Ugence authority-plane API audience |
| `jwks_trust` | OIDC discovery or the approved JWKS endpoint |
| `tenant_claim` | the claim carrying the enterprise tenant identity |
| `principal_claim` | a stable human identifier, never a mutable display name |
| `actor_type_claim_or_mapping` | how a human is distinguished from a workload identity |
| `allowed_actor_type` | `HUMAN` |
| `directory_binding` | how the verified principal maps to an Authority Directory subject |
| `failure_behaviour` | `FAIL_CLOSED` |
| `jwks_rotation_behaviour` | refresh and bounded retry policy |
| `validation_environment` | `NON_PRODUCTION` |
| `ap3_status` | `PENDING_VALIDATION` once designated; `MET` or `NOT_MET` after the matrix |

### 20.2 — The validation matrix

AP-3 becomes `MET` only after the worker proves every row against the real issuer,
with no row skipped.

| Scenario | Required result |
|---|---|
| Correct issuer, audience, tenant and human actor | Accepted |
| Wrong issuer | Refused |
| Wrong audience | Refused |
| Wrong tenant | Refused |
| Missing tenant claim | Refused |
| Workload identity presented as human | Refused |
| Missing actor-type evidence | Refused |
| Expired or not-yet-valid token | Refused |
| Invalid signature | Refused |
| Unknown signing-key id | Refused |
| Malformed token | Refused |
| JWKS unavailable with no safely cached key | Refused |
| Signing-key rotation | New valid key accepted after controlled refresh |
| Valid identity without a directory grant | Authenticated but unauthorized |
| Valid identity with a wrong-tenant grant | Unauthorized |
| Valid identity with the correct scoped grant | `WriterAuthorizer` permits only the named capability |

The last three rows are the point of the exercise: a valid token proves identity and
grants no authority.

### 20.3 — Evidence the record must hold, and must not

The record contains no live token. It records the identity-provider and test-tenant
classification; the issuer and audience configuration; the claim-mapping decisions;
the test timestamp; token fingerprints or redacted fixture identifiers; JWKS and key
identifiers, never private keys; the acceptance or refusal result for every row; the
CI run or a signed validation report; the named owner who accepts the mapping; and
the limitations of the validation environment.

### 20.4 — The owner's instruction for the validation slice

Authorized only once an issuer is designated in the record above, and then in the
owner's words: AP-3 is authorized for validation, not yet declared met. Use the
owner-designated non-production enterprise OIDC issuer. Validate the issuer, audience,
signature through approved JWKS trust, tenant claim, stable principal claim and explicit
human actor-type mapping. Bind the verified principal to the Authority Directory only
after cryptographic identity validation. Run the complete matrix of §20.2 against the
real issuer. Fail closed. Store no token, client secret or private key in the
repository, fixtures, image, logs or report; record only configuration identifiers,
redacted evidence and results. Open a documentation-and-validation PR and do not
implement AX-1 or AX-2 in that PR. Declare AP-3 `MET` only if every mandatory row
executes without skips and passes; otherwise report `NOT_MET` and stop.

### 20.5 — Order of implementation once AP-3 is met

1. Compose the RA-6 status store into the worker with writes still unserved (AX-1).
2. Move policy-registry process ownership to the worker (AX-2, steps 1 and 2).
3. Introduce authenticated read relays and remove the studio's direct file access
   (AX-2, steps 3 and 4).
4. Compose verified-principal plus directory-grant authorization (AX-5).
5. Add owner-provisioned signer configuration (AX-3).
6. Serve each write capability through its separately authorized route, each with its
   own record.

Identity validation stays ahead of every authority-plane mutation, as §19 intends.

## 21 — Ruling on the two questions raised by the enterprise-readiness evaluation (2026-09-07)

This section is documentation. Nothing is implemented under it, and nothing here
changes §18, §19 or §20.

### 21.1 — What was evaluated

An external evaluation of enterprise readiness was read against the repository. Its
four-way split (governance decides; identity proves; infrastructure bounds; the broker
releases last) is already the repository's law `[V]` (SD-2, AP-4, AP-3, AX-5, CR-3,
D-4), and its "most urgent path" is the sequence already ratified in §19.5 and §20.5.
It is behind the code in one respect: the composed worker already refuses a decision
without an issuer proof when an identity port is present and records
`IDP_AUTHENTICATED`; what is missing is evidence against a real issuer, which is why
AP-3 reads BLOCKED (§20). It names real gaps `[G]`: cryptographic workload identity for
agents, monetary approval limits and jurisdiction on grants, provisioning-driven
deprovisioning, KMS or vault backing for the broker, a tenant hierarchy, backup and
outbox, suspension propagating to queues and connectors, a governed connector model.
These are later phases, not corrections, and none is scoped by this record.

Two of its recommendations touch rulings already made, and only those two are ruled
here.

### 21.2 — The ruling

Applied under the owner's standing direction that recommended defaults apply, and
recorded as such: either may be reversed by the owner's word, as AW-1 was (§18).

| # | Question | Ruling |
|---|---|---|
| **EN-1** | Where guided enterprise configuration lives (organization setup, identity-provider connection, owner and authority mapping, environment promotion, incident dashboard) | **`AUTHORITY_PLANE_NOT_STUDIO`.** Guided configuration is added to the authority plane, screen by screen, each under the same identity gate as every other act of the plane, and each with its own record. The Studio keeps typed intake and display: MA-1, MS-1 and §19's sentence stand, composition stays deployment environment attested at startup and shown read-only on the Studio's Status panel, and an evaluation that makes the Studio "the configuration and onboarding plane" is refused as written. A fourth administrative surface is not admitted; the plane is that surface. |
| **EN-2** | Whether incident and remediation orchestration is a new capability | **`RA6_CONSEQUENCE_PROPAGATION`.** It is not a new capability. Suspending an agent, stopping pending executions, revoking its credentials, disabling a connector and freezing a policy domain are consequences of RA-6 lifecycle writes (targeted subject revocation, epoch advance, emergency stop) propagating outward. It is scoped under AX-1 when the RA-6 store is composed into the worker, as propagation seams from that store to the runtime, the broker, the queues and the connectors, each fail-closed. A separate orchestrator that could suspend without an RA-6 write would be a second authority, and is refused. |

### 21.3 — What this ruling supersedes, and what it does not authorize

**Supersedes** nothing already ruled. It refuses two readings of the evaluation and
keeps MA-1, MS-1, MA-2 as amended, AP-1 to AP-5, AW-2 to AW-5, AX-1 to AX-5 and §18 to
§20 as they stand.

**Does not authorize:** any configuration screen on the authority plane before AP-3 is
`MET` (§20); any write on any surface before AP-3 is `MET`; any propagation seam before
AX-1's composition; any change to the Studio's allowlist or contract; a tenant
hierarchy, workload identity, provisioning integration, connector model or persistence
change, each of which needs its own scoping and ballot; LIVE execution.

### 21.4 — Sequence

Unchanged: §20.5 in full, then, after AX-1's composition, the propagation seams of
EN-2; and, after the first authority-plane write is served with its own record, the
first guided-configuration screen of EN-1, each screen its own slice.

---

## 22 — Owner ruling BW-1 to BW-5: Bring Your Workflow, a read-only Workflow IR inspector (owner, 2026-09-07)

**Status:** ratified by the owner in their own words on 2026-09-07 ("Ratify BW-1
through BW-5 as recommended ... confirm the BW-2 figures, and confirm that the
ratification supersedes the 'no arbitrary JSON / fixture-upload input' sentences in
the studio frontend README and P3D_SECURITY.md"), and implemented in the same slice.

### 22.1 — The question, and what the repository settled before the ballot

The Studio had no way for an operator to bring a workflow of their own: the scenario
catalog is a fixed tuple, the Simulate screen sends one hard-coded sample, and the
front end's README and `P3D_SECURITY.md` said "no arbitrary JSON / fixture-upload
input". The owner's direction was to add the second customer entry path ("bring an
existing workflow to Ugence for governance") in a tightly bounded first form: a
read-only Workflow IR inspector, not an agent uploader.

Settled by the repository before the ballot `[V]`:

- The frozen `governance_studio.api.v1` OpenAPI document already carried
  `validate_workflow`, `adapt_workflow` and `compare_adaptations`
  (`apps/ugence-governance-studio/backend/src/ugence_governance_studio_api/api/workflows.py`),
  each accepting a workflow document in the request body and failing closed on any
  declared version outside `workflow_ir.v1` / `workflow_ir.v2`. The front end's
  manifest listed the three by name as forbidden.
- The only limit on such a document was the 2 MiB body middleware; nothing bounded
  its structure.
- Workflow IR is the policy compiler's output (nodes, edges, dispositions, human
  review and authority requirements, capability and tool refs, provenance,
  fingerprint); it has no agents or tasks, and no customer can produce it today
  except through Ugence's own compiler. Phase 1 therefore proves the surface;
  converters make the path real, and they are a later phase `[G]`.
- The "no arbitrary input" boundary was prose in two documents, not a numbered
  ruling.

### 22.2 — The ruling

| # | Question | Ruling |
|---|---|---|
| **BW-1** | The surface | **`READ_ONLY_WORKFLOW_IR_INSPECTOR`** at `/bring-your-workflow` on the v1 contract, a sibling of the scenario catalog, named "Bring Your Workflow", tagline "Validate and adapt an existing agentic workflow for Ugence governance." A general agent uploader is refused; "Import Agent" is not a name this surface may carry. |
| **BW-2** | Input and limits | **`PASTE_OR_LOCAL_FILE_BODY_ONLY`**: Workflow IR JSON pasted into the screen or read from a local file in the browser. Figures confirmed by the owner: 1 MiB, nesting depth 32, 200 nodes, 400 edges (and 50 000 values to bound the walk). The browser gate and the server enforce the same figures; the server's refusal is the typed 422 `workflow_too_complex`. The gate also refuses YAML, code, archives, a JSON value that is not an object, an undeclared or unsupported version (never guessed from field presence), a credential-shaped key or value, and a remote reference. |
| **BW-3** | Backend operations | **`VALIDATE_ADAPT_COMPARE_ONLY`**. The three operations move from the front end's forbidden list to its approved list; no route, schema or status code is added to the frozen OpenAPI document, whose hash is unchanged; one contract-neutral structural guard (`workflow_limits.py`) runs before any adapter. |
| **BW-4** | Persistence and output | **`EPHEMERAL_NO_SERVER_STORAGE`**. No server write exists for the document and no browser storage is touched; results live in component state, are cleared by any edit, and leave only as a local download of the report (the server's own envelopes, request ids included) and of the adapted envelope. Provenance shown: the client's canonical digest, computed by the backend's own encoding rule, and the server's computed digest, with match or mismatch stated. |
| **BW-5** | Name and maturity | **"Bring Your Workflow"**, `REFERENCE_GRADE`, with the disclaimer verbatim on the screen: "Accepts Ugence Workflow IR JSON. It does not execute, publish or persist the submitted workflow." LangGraph, CrewAI, AutoGen, n8n and BPMN conversion is deferred to a separately scoped phase. |

Execution, scenario-catalog mutation and remote fetch are forbidden under every
option and were not balloted.

### 22.3 — What this ruling supersedes, and what it does not authorize

**Supersedes**, for this one surface, the sentences "accepts no arbitrary JSON /
policy / URL / code / fixture-upload input" in
`apps/ugence-governance-studio/frontend/README.md` and "no arbitrary JSON/policy/URL/
code ... no plan or replay-record upload from local files" in
`apps/ugence-governance-studio/docs/P3D_SECURITY.md`; both documents now say so in
place. The original boundary was correct for the synthetic Studio and is not a
permanent product principle; changing it through a versioned, fail-closed feature
with its own tests is the intended way to move it. The GAS-4/5 "v1 surface
byte-identical" check is not weakened: the OpenAPI document, the generated client
and its hash are unchanged; only the manifest moved, and by this ruling.

**Does not authorize:** any framework converter (phase 2, its own scoping); saving an
uploaded workflow as a draft, assigning an owner or tenant, versioning, linking a
policy or constitution, or submitting for approval (phase 3, only after tenant
identity, IAM and the Portfolio Registry exist, each its own ballot); compiling,
simulating, approving, publishing, issuing clearance or exporting an uploaded
workflow to a runtime (phase 4, only after the authority plane serves writes under
AP-3 `MET`); any overlay, scenario id or URL on the screen's requests; any change to
the v2 contract; LIVE execution.

### 22.4 — Verification recorded with the slice `[V]`

- Backend: `tests/test_workflow_limits.py` (nine tests: figures, measures, refusal
  by measure on each route, acceptance at the limit, the byte cap answering below
  the middleware, the element cap ending the walk); the whole studio backend suite
  passes with the guard in place and the OpenAPI freeze test unchanged.
- Front end: `tests/bring-gate.test.ts` (twenty-six: every refusal code, both real
  documents pass, the declared-version rule, and the client's canonical digest of
  the guided example equal to the digest the real backend computed for it);
  `tests/bring-screen.test.tsx` (fifteen: disclaimer verbatim, axe clean empty and
  loaded, refusals with no request sent, local file read in the browser, the exact
  bodies of the three requests, the server's typed refusal shown, only the three
  operations ever reached, results cleared on edit, the report and envelope
  downloads equal to the server's records, and a source scan for browser storage,
  raw connections and forbidden operations); the allowlist verifier reports twenty
  consumed operations equal to the manifest; every CI verifier, the full vitest
  suite and the production build pass.

### 22.5 — Sequence

This slice ships phase 1. Phase 2 (converters) needs its own read-only scoping
audit and ballot before any code. Phases 3 and 4 wait, in that order, on the
prerequisites named in §22.3 and on §20.5 as it stands. Nothing in §18 to §21
moves.
