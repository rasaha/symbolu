# Ugence module administration — scoping audit

**Status:** audit and ruling, 2026-09-06. Documentation only: this record amends no
package, route, test, contract, manifest or deployment artifact, and activates no
seam. It answers one product question and records the owner's ruling on the ballot
MA-1 to MA-5 that the question forces.

The question, as raised: should there be an admin screen for each module, and should
the Ugence Governance Studio be an independent web address, separate from those
screens and appearing as a link in their navigation?

Evidence labels: `[V]` verified against this repository at `19a6b04f`, `[I]`
inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question, and the answer

**The modules that would need an admin screen may not have one, and the modules that
may have one do not need administering.** Most module administration on this platform
is an authority act — issuing, activating, authorizing, clearing, executing — which
the studio is ruled never to perform. The remainder is deployment composition, fixed
before the process binds its port. What is unbuilt is one read-only status panel.
What is missing otherwise is not software; it is rulings that the owner has, so far,
deliberately declined to give.

## 2 — What the repository enumerates as a module `[V]`

The question arrived framed as "15 modules (M0–M14) over ~66 packages". Neither figure
is the repository's `[G]`:

- No `M0–M14` map exists. "15 modules" occurs twice and is neither the programme:
  `products/dilchat/docs/DILCHAT_BACKEND_ARCHITECTURE.md:175` describes a different
  product's backend, and `ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md:32` counts the
  fifteen Python files inside `ugence_console_api`.
- The repository's own enumeration is **nine** modules, at
  `packages/integration/console-api/src/ugence_console_api/capabilities/registry.py:21-66`,
  with two AI-Infrastructure modules (KVPro, Cloud Scaling Controller) excluded by
  the module's own docstring (`:3-5`) because they are frozen and never govern.
- Distributions under `packages/` number **70**, counted by `pyproject.toml`.

Every finding below uses the nine. Where the front-door ADR's ten outline screens
(`ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` §3) group them differently, both readings
lead to the same answer.

## 3 — What "configuration" means per module, against SD-2 `[V]`

SD-2 (`NON_AUTHORITY_STUDIO`) is enforced by
`apps/ugence-governance-studio/backend/tests/test_v2_operation_ids.py`. It names seven
verbs — issue, activate, revoke, grant, authorize, clear, execute — matched as
case-insensitive substrings (`:24-26`), and scans every v2 **operation id** (`:41-51`)
and every **path** (`:54-62`). A companion scan in `test_architecture.py:302-313`
refuses five named entry points as *calls*, with docstrings and comments stripped
first so that explaining the boundary does not trip it (`:277-299`).

Two consequences shape the answer.

**The ratchet is narrower than its reputation.** An operation named
`v2_module_update_configuration` at `/api/v2/modules/{key}/config` passes both scans.
SD-2 is a naming ratchet on seven authority words, not a general prohibition on
administration. The prohibition on administration comes from elsewhere: from the SD-1
allowlist (§4) and from composition (§5).

**One gap between prose and test.** The module docstring claims the scan covers
"operation id, path or summary" (`:6-7`). No test reads `summary` `[G]`. Checked
against the committed contract: no current summary would fail, so the gap is latent.
It is MA-5 below.

Per module, what configuring would mean and where it lands:

| Module (registry key) | "Configure" would mean | Crosses SD-2? | Where the act lives today |
|---|---|---|---|
| `actiongate` | authorize an exact action, set its policy refs | **yes** — *authorize* | `/v1/actions/authorize`, withheld by CP-3 and refused by the studio's client before a connection opens (`clients/console.py:39-44`; `test_v2_operation_ids.py:128-152`) |
| `autonomous_control_plane` | clear or hold an action against live signals | **yes** — *clear* | `/v1/actions/clear`, the same two refusals |
| `agent_runtime` | execute, pick providers, set the governance hook | **yes** — *execute*; hook and provider registry are composition (`config.py:80-84`) | the governed runtime worker; the studio relays a start of the worker's own shadow run only (`REVIEW_ALLOWED_ROUTES`, `clients/review.py:8-20`) |
| constitution and policy issuance | issue, activate, revoke | **yes** — three of the seven | `_PERMANENTLY_EXCLUDED`, `test_architecture.py:129-135` |
| `tap` | evidence thresholds, coverage policy | no verb | the provider's own contract; imports no Ugence types; not on SD-1 |
| `context_minimization` | protected units, redundancy policy | no verb | as above |
| `model_selection` | eligible model set, routing policy | no verb | as above; research-only labels in the front-door map |
| `hybrid_llm`, `steering_controller` | model, frame and audit thresholds | no verb | as above; `wiring="read-only"` in the registry |

Four of nine are authority acts by name. The other five are configurable in
principle, but by nothing the studio owns.

## 4 — What admitting a module's packages costs `[V]`

The SD-1 public-entry-point allowlist (`test_architecture.py:69-124`) holds **eleven**
entries; the retention guard asserts at least six (`:336`).

CE-6 is the worked example of adding one. Ruled `ONE_ENTRY_EXPORT_PACKAGE`
(`ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md:284`), it required a scoping ADR, a ballot,
an owner ruling, a purpose-built **contracts-only** package because neither the
evaluator nor the receipt store may be admitted, one allowlist line, a sha256-chained
v2 contract amendment, a regenerated client, a P3E freeze update, and a deployment
seam test. The ruling then closes the door behind itself: admitting a second package
later "is a new owner decision, not a follow-on" (`:328-330`). Even the route's name
was bent by the ratchet — `exports`, not `clearances`, because `clear` is a substring
(`:354-358`).

An admin screen per module is therefore nine such ballots, four of which §3 refuses
before they are put `[I]`.

## 5 — Configuration versus composition `[V]`

`deployment/governance-studio/src/governance_studio_deployment/config.py` defines
**25 settings** on `DeploymentConfig` (`:47-96`), **21 of them environment
variables**. The dataclass is frozen (`:46`) and read once, by `run()`
(`server.py:36`). `run_startup_integrity` executes **before the port binds**
(`server.py:38-52`; `startup_integrity.py:1-5`) and fails closed on the OpenAPI hash,
the seventeen-operation approved manifest (`startup_integrity.py:175-185`), the
synthetic bundle hash, TLS material and the writability of each seam file.

A running web application changing any of these would defeat four things at once:

1. the fail-closed gate, which has already passed by the time a request arrives;
2. the frozen dataclass;
3. `read_only_root_filesystem: true`, with only `/tmp` and `/var/run/ugence-studio`
   writable (`deployment/governance-studio/approved-runtime-config.json`);
4. the `frozen{}` pins and the evidence manifest built over them.

The seams are handed to `build_studio_context(...)` at startup and nowhere else
(`config.py:69-96`). They are **composition**, not configuration. A screen that sets
a registry path or enables the simulation provider is asking the process to
re-compose itself after its integrity was attested.

## 6 — What packaging already settled about a second front end `[V]`

CP-1 ruled `SERVICE_ONLY` (`ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md:125`):
`apps/console/` is a separate deployable, as the studio's frontend and backend are
separate units. The packaged console serves **five** routes and withholds **six**
(`packages/integration/console-api/src/ugence_console_api/app.py:50-68`), asserted
against the running application object rather than the source
(`tests/test_served_surface.py:40-68`), with an independent second reading that
nothing served names authorize, clear, grant, execute, credential or enforce
(`:71-75`). Every answer, errors included, carries `X-Ugence-Audit-Ceiling` from a
single constant shared with the two decision-trail bodies (`app.py:71,91-96`;
`models.py:23-26`; `tests/test_audit_ceiling.py:29-36`).

The decisive fact is what the split has already cost. `apps/console/src/api.ts:85-86`
calls `/v1/modules` and `/v1/scenarios` — two of the six withheld routes. The
packaging record says so at `:166-169` and leaves the remedy open: "what it should
show instead is a product decision, not a packaging one." A second front end exists
today and is stranded on routes no ruling serves.

Against that, the studio's v2 contract is one frozen document of 26 operations,
amended only through `contracts/openapi_v2.amendments.json`, whose entries chain by
sha256 from the original freeze. Its frontend consumes a closed approved set, frozen
independently of v1's seventeen.

## 7 — What a read-only module-status surface could show `[V]`

From data that already exists, and with no new package or allowlist entry:

- the nine `ModuleInfo` rows — key, name, layer, capability, maturity **verbatim**
  from the evidence discipline, wiring, question (`registry.py:21-66`;
  `models.py:173-180`);
- the six seam states the startup report already computes — constitution registry,
  authority reads, simulation provider, system registry, data-use declarations,
  vendor declarations — each `configured`, `unset` or `unwritable`
  (`startup_integrity.py:230-235`).

What it could not show without a further ruling: live module availability. The
console's `/health` computes it (`app.py:103-115`), but `/health` is not in
`CONSOLE_ALLOWED_ROUTES`, `/v1/modules` is withheld, and the deployment's `/readyz`
carries no seam state (`governance_studio_deployment/app.py:165-170`).

The honest cost of the panel is therefore **one v2 read operation** to reach the
studio's own startup report — one contract amendment, in the shape v2-A1 to v2-A6
already established `[I]`.

## 8 — The two answers

**(a) Which modules admit an admin screen: none, as an admin screen** `[I]`. Four are
refused by SD-2 at the verb and again at the client allowlist. The other five are not
on the SD-1 allowlist, and their configuration is a model-and-threshold choice no
studio route owns. What is admissible is what has already shipped: typed **intake**
screens whose one write records what an administrator asserted and confers nothing,
and read-only display. The front-door record drew this line before the question was
asked: "A typed registration form over `ai-system-registry` is admissible"
(`ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md:53`), against "Suspend, contain, recover as
buttons would claim execution control that no package exercises" (`:54`) `[V]`.

**(b) One deployable or two: two already exist; keep two, add no third** `[I]`. The
studio (P3E, one process, its own frozen v1 and v2 contracts) and `apps/console` with
`ugence-console-api` are separately packaged under CP-1 and CP-2. Making the studio an
independent address linked from per-module navigation means a third front end whose
links point at routes no ruling serves — the condition `apps/console` is in now. Nine
such front ends would be nine copies of that condition.

## 9 — Proposed ballot MA-1 to MA-5 (five decisions, recommended option first; ruled in §11)

| # | Decision | Options |
|---|---|---|
| **MA-1** | Per-module admin screens | **`NO_PER_MODULE_ADMIN`**: no module gains an administration screen; typed intake and read-only display remain the only admissible screen shapes. `ADMIN_FOR_ADVISORY_MODULES_ONLY`: screens for the five modules SD-2 does not name, each requiring its own SD-1 entry. `ADMIN_PER_MODULE`: nine screens, nine ballots. |
| **MA-2** | What replaces them | **`ONE_READ_ONLY_STATUS_PANEL`**: one studio panel over the nine static registry rows and the six seam states the startup report computes; one v2 read amendment; no new package, no new SD-1 entry, no write. `NO_PANEL_YET`: record the finding, build nothing. `PANEL_PER_MODULE`. |
| **MA-3** | Number of front ends | **`TWO_DEPLOYABLES_UNCHANGED`**: the studio and `apps/console` stay the two deployables CP-1 ruled; no third front end. `THIRD_FRONT_END`: a module-navigation shell that links to the studio. `MERGE_CONSOLE_INTO_STUDIO`: one deployable, reopening two independently frozen contracts. |
| **MA-4** | `apps/console`'s two withheld calls | **`RETIRE_THE_TWO_CALLS`**: the React app stops calling `/v1/modules` and `/v1/scenarios`; MA-2's panel supersedes what the first was for. `RULE_TWO_INTROSPECTION_ROUTES`: serve them from the packaged console under a new CP ruling. `LEAVE_AS_IS`. |
| **MA-5** | The SD-2 summary gap | **`SCAN_SUMMARY_TOO`**: add the summary scan the docstring already claims; one test, no contract change. `CORRECT_THE_DOCSTRING`. `LEAVE_AS_IS`. |

**Why the recommended options.** MA-1: four of nine modules are refused at the verb
and the allowlist, and the other five have nothing a studio route owns; the
alternative is nine CE-6-sized ballots for screens that may not act. MA-2: it is the
cheapest thing that can work, and it uses only data the deployment already computes
about itself. MA-3: CP-1 already ruled the split, and `apps/console` is the
demonstration of what a front end pointing at unruled routes costs. MA-4: the
packaging record left this open as a product decision; retiring the calls is the only
option that adds no served surface. MA-5: the docstring claims it, no current summary
would fail, and the file's own principle is that a prohibition which is only prose
drifts.

## 10 — What this record does not decide

- **The seven withheld and prohibited surfaces.** CP-3's six withheld console routes,
  and SD-2's seven verbs, are untouched. MA-4's recommended option removes a caller;
  it serves nothing.
- **Any new SD-1 entry.** None is proposed. A status panel under MA-2 reads the
  studio's own startup report, not a governance package.
- **Result egress, the governed hook via the worker, a durable decision store, and
  every seam the front-door record sequenced after seam 9.** Their own rulings hold.
- **`REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED = False`, `LIVE` absent from
  `SIMULATION_MODES`, the frozen v1 and v2 contracts, every `FROM` line and ratified
  digest, and every credential prohibition** — all preserved.

## 11 — Ruling MA-1 to MA-5 (owner, 2026-09-06)

The recommended option is ratified in every case. The ruling was given by the owner
directing that the ratification prompt closing the audit be run as written; this
section records it in the form the CE and CP records use.

| # | Ruling |
|---|---|
| **MA-1** | **`NO_PER_MODULE_ADMIN`.** No module gains an administration screen. Typed intake — one write that records what an administrator asserted and confers nothing — and read-only display remain the only admissible screen shapes. `ADMIN_FOR_ADVISORY_MODULES_ONLY` and `ADMIN_PER_MODULE` are refused. |
| **MA-2** | **`ONE_READ_ONLY_STATUS_PANEL`.** One studio panel over the nine static registry rows and the six seam states the startup integrity report already computes. Its cost is one v2 read operation, added as a contract amendment in the shape v2-A1 to v2-A6 established. No new package, no new SD-1 entry, no write, no live-availability probe. *Amended by §15 (MS-1): the nine registry rows are struck; the panel shows the seam states, checks and pins only.* |
| **MA-3** | **`TWO_DEPLOYABLES_UNCHANGED`.** The studio and `apps/console` remain the two deployables CP-1 ruled. No third front end is built, and the two independently frozen contracts are not merged. *Superseded in one respect by `ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` AP-2: a third deployable is admitted as the authority plane's front end. The refusal of a third front end for module administration stands.* |
| **MA-4** | **`RETIRE_THE_TWO_CALLS`.** `apps/console` stops calling `/v1/modules` and `/v1/scenarios`. Neither route is served; MA-2's panel supersedes the first. `RULE_TWO_INTROSPECTION_ROUTES` is refused as a new served surface without a CP ruling; `LEAVE_AS_IS` is refused because a front end that calls what nothing serves is the failure this record exists to name. |
| **MA-5** | **`SCAN_SUMMARY_TOO`.** `test_v2_operation_ids.py` gains the summary scan its docstring already claims. One test; no contract, route or client changes. |

## 12 — What ratifying does not authorize

This ruling is documentation. No file outside this record changes under it.

- **No implementation begins here.** MA-2's contract amendment, MA-4's removal of two
  client calls, and MA-5's one test are three separate slices, each to be scoped on
  its own and none started by this record. MA-2 in particular is a v2 amendment and
  follows the amendment discipline — a sha256-chained entry, a regenerated client, a
  frozen approved-operation set — rather than an added route.
- **No per-module screen, under any name.** A "status" panel that accepts input, a
  "settings" view that writes a seam path, or a "diagnostics" screen that probes a
  module's availability over a route the studio's client does not allow is a
  per-module admin screen in a different coat, and MA-1 refuses it.
- **No new SD-1 entry, no new console route, no loosening of SD-2.** The eleven
  allowlist entries, the five served console routes and the seven prohibited verbs are
  exactly as they were. Admitting any package or serving any withheld route remains a
  new owner decision.
- **No third deployable.** Linking the studio from another application's navigation
  is not authorized, because no such application is.
- **No claim about live modules.** The panel MA-2 authorizes reports what the
  deployment attested about itself at startup. It says nothing about whether ActionGate
  or any other module is reachable now, and an implementation may not infer that from
  a seam being `configured`.

## 13 — Implementation record, MA-5 (2026-09-06)

Shipped as one test in
`apps/ugence-governance-studio/backend/tests/test_v2_operation_ids.py`. What the
ruling became, and where the claim is checked:

| Ruling | What landed | Where it is checked |
|---|---|---|
| MA-5 `SCAN_SUMMARY_TOO` | `test_no_v2_summary_names_an_authority_act` scans every v2 operation's `summary` for the seven `PROHIBITED_VERBS`, in the same shape as the operation-id and path scans. The docstring's claim at `:6-7` is now true of the file. | the test itself, against the committed `contracts/openapi_v2.json` through `canonical_v2_openapi_bytes()` |
| self-check | `test_the_prohibition_test_actually_catches_a_violation` now holds two fake routes: one that offends in all three scanned places, and one that offends in the summary alone. The second is the proof that the summary scan reads the summary and does not fall back to the operation id. | the same test, asserting the id, path and summary scans each catch exactly the routes they should |

**Verified, not asserted.** The file passed at 10 tests before the change and 11
after; the full studio backend suite passed at 351. A mutation check against the
committed contract — one real summary rewritten in memory to read "Clear and export
the receipt" — failed the new test with `GET /api/v2/exports/{receipt_id} ->
'Clear and export the receipt' (clear)`, which is the message a future violation
would produce.

**What did not change.** No contract byte: `openapi_v2.json`, its amendment chain
and both approved-operation manifests are untouched, and
`test_v2_document_is_committed_and_free_of_drift` still passes against the same
bytes. No route, client, allowlist entry, or `PROHIBITED_VERBS` member. No current
summary needed rewording; the gap was latent, as §3 found, and is now closed rather
than relied on.

MA-2 and MA-4 remain unimplemented and separately scoped, as §12 requires.

## 14 — Implementation record, MA-4 (2026-09-06)

Shipped as a change to `apps/console/` only: the client, the two views that read
the withheld routes, one new typed-gap component, and the README. What the ruling
became, and where the claim is checked:

| Ruling | What landed | Where it is checked |
|---|---|---|
| MA-4 `RETIRE_THE_TWO_CALLS` | `src/api.ts` no longer defines `modules()` or `scenarios()`, nor the `ModuleInfo` and `ScenarioSummary` types that existed only for them. The client's four remaining calls — `/health`, the scenario run, and the two audit reads — are each in `SERVED_ROUTES`; the fifth served route, the raw shadow write, was never called by this app and still is not. | a parse of every `get<…>(…)`/`post<…>(…)` path in `api.ts` against `SERVED_ROUTES` and `WITHHELD_ROUTES` in `app.py`: four calls, all served, none withheld |
| typed gap, not empty result | `src/views/TypedGap.tsx`: a code (`CONSOLE_ROUTE_WITHHELD`), the source that is not served, and the two rulings, in the shape the studio's screens use for an unset seam. | rendered by both views below; `role="status"` |
| Modules view | Reads `/health` only. Renders the service's availability probes under the keys it returns and its declared audit ceiling (CP-4), and the nine-row registry as a typed gap. No name, layer, maturity or wiring is hardcoded: that would be the withheld route re-implemented in the browser. | `src/views/Modules.tsx` |
| Governed Loop view | Keeps the served run route. The scenario id is typed, the pattern the Audit view already uses for a correlation id; the catalogue is a typed gap, and an id the service does not hold is its own 404, shown verbatim. No scenario list is kept client-side, for the same reason. | `src/views/GovernedLoop.tsx` |
| README | The Views section describes the two views as they now behave, and a new Served-surface section names the five routes and the two rulings. | `apps/console/README.md` |

**Verified, not asserted.** The app defines two checks, `type-check` and `build`,
and no lint or test. Both passed after the change: `tsc --noEmit` exit 0; `vite build`
exit 0, 1365 modules transformed. The served-set proof above passed: every client call
in `SERVED_ROUTES`, no client call in `WITHHELD_ROUTES`. The new `Health.audit_ceiling`
field mirrors what `app.py:112` already returns; nothing was added to the service.

**What did not change.** No route: `SERVED_ROUTES` and `WITHHELD_ROUTES` are as CP-3
left them, and `test_served_surface.py` is untouched. No contract, no package, no
dependency: `package.json` is unchanged, and the lockfile `npm install` generated
during verification was removed rather than committed, since adding one is not this
ruling's to make. The `dist/` build output is ignored and was not committed.

**The one judgment call, recorded.** Typing the scenario id keeps the served run route
usable; the alternative was to disable the run entirely once its picker lost its
source. The typed form was chosen because it adds no data the service does not
return and mirrors an existing view. If the owner would rather the run be disabled
until a catalogue route is ruled, that is a one-line change and a new ruling is not
needed for it.

MA-2 remains unimplemented and separately scoped, as §12 requires.

## 15 — MA-2 scoping, and ruling MS-1 to MS-5 (owner, 2026-09-06)

Scoped before implementation, as §12 required, at `ac2703a0`. The scoping found that
MA-2 as ruled could not be implemented honestly: it promises two things, of which one
has a lawful source and the other has none.

### 15.1 — The corrected premise `[V]`

- **The six seam states can reach the studio.** They are fields of the startup
  integrity report (`startup_integrity.py:230-235`), which exists in memory in `run()`
  (`server.py:38`) before `build_app` is called (`:52`). Every existing seam reaches
  the backend as a keyword argument to `build_studio_context(...)` (`app_v2.py:64-81`)
  wrapped in a service that returns the typed `unavailable` shape when absent
  (`studio_v2.py:129-136`). The report is a dict, not a package: no SD-1 entry is
  involved. What is missing is that `build_app` (`app.py:184`) and `_build_backend`
  (`:186`) take no report `[G]`.
- **The nine `ModuleInfo` rows cannot.** `ugence_console_api` is not in
  `_PROHIBITED_IMPORTS`; it is refused by
  `test_no_package_outside_the_allowlist_is_imported` (`test_architecture.py:232-248`),
  which rejects any `ugence_*` root not allowlisted. The deployment cannot hand the
  rows in either: it depends on starlette, uvicorn and argon2 only
  (`deployment/governance-studio/pyproject.toml:10-14`) and its image installs no
  `console-api` (`Dockerfile:31-61`); installing it would bring the console's four
  platform packages (`console-api/tests/test_packaging.py:30-35`) into the studio
  image. Reaching the rows over HTTP needs `/v1/modules`, withheld by CP-3, and a fifth
  entry in the closed `CONSOLE_ALLOWED_ROUTES` (`clients/console.py:36-38`). Copying
  them into a fixture is a second registry that drifts.
- **The amendment precedent is finer than MA-2.** v2-A1 to v2-A6 each cite a ruling
  that names the operation, its source and its labelling separately. MA-2 named the
  panel and the cost only.

### 15.2 — Ballot MS-1 to MS-5 (recommended option first)

| # | Decision | Options |
|---|---|---|
| **MS-1** | What the panel shows | **`SEAM_STATES_ONLY`**: amend MA-2 to strike the nine rows. `ADMIT_ROWS_VIA_CONSOLE_ROUTE`: reopen `/v1/modules` under a new CP ruling and widen the studio's console allowlist, revisiting SD-2. `FIXTURE_COPY`: ship the rows as a deployment fixture. |
| **MS-2** | Source of the status | **`IN_MEMORY_RESULT_AT_COMPOSITION`**: `run()` hands `result.report` through `build_app` into `build_studio_context`. `READ_FILE_FROM_RUNTIME_DIR`: the route reads the best-effort copy on the writable volume. |
| **MS-3** | The operation | **`OBSERVE_DEPLOYMENT_ONE_READ`**: `v2_observe_deployment` at `GET /api/v2/observe/deployment`, amendment v2-A7, the v2-A3 shape. `NEW_STATUS_NAMESPACE`: `/api/v2/status`. |
| **MS-4** | The field set | **`SEAM_STATES_CHECKS_AND_PINS`**: the six seam states, the `checks` map, `result`, `failure_code`, and the version and hash fields. `WHOLE_REPORT`: also `cert_subject` and `cert_expiry`. |
| **MS-5** | Where it lives | **`SEPARATE_STATUS_PANEL`** at `/studio/status`. `THIRD_SOURCE_ON_OBSERVE`: a third labelled source on the Observe screen. |

**Why the recommended options.** MS-1 is the only option that costs nothing already
refused. MS-2 reads the attested fact, not its mutable copy. MS-3 keeps one route in
an existing family, exactly as A3 did. MS-4 omits two operator facts no screen uses.
MS-5 leaves FD-11.4 `TWO_LABELLED_SOURCES` untouched; a third source would change the
count that ruling names, which is that ruling to reopen.

### 15.3 — Ruling MS-1 to MS-5 (owner, 2026-09-06)

The recommended option is ratified in every case, under the owner's standing direction
that recommended defaults apply and the sequence proceeds without interruption.

| # | Ruling |
|---|---|
| **MS-1** | **`SEAM_STATES_ONLY`.** MA-2 is amended: the nine registry rows are struck. The panel shows what the deployment attested about itself at startup and nothing about the console's module registry. `ADMIT_ROWS_VIA_CONSOLE_ROUTE` and `FIXTURE_COPY` are refused. |
| **MS-2** | **`IN_MEMORY_RESULT_AT_COMPOSITION`.** The integrity report reaches the studio as one composition argument, handed once at startup; no route reads a file. |
| **MS-3** | **`OBSERVE_DEPLOYMENT_ONE_READ`.** One read, `v2_observe_deployment` at `GET /api/v2/observe/deployment`, contract amendment v2-A7 chaining from v2-A6. |
| **MS-4** | **`SEAM_STATES_CHECKS_AND_PINS`.** The six seam states, the `checks` map, `result`, `failure_code`, and the deployment, frontend, backend, contract and hash fields. `cert_subject` and `cert_expiry` do not travel. |
| **MS-5** | **`SEPARATE_STATUS_PANEL`.** A panel at `/studio/status`; the Observe screen keeps its two sources. |

**MA-2 as amended now reads:** one read-only studio panel at `/studio/status` over the
startup integrity report's seam states, checks and pins, handed to the studio at
composition; one v2 read operation, `v2_observe_deployment`, added as amendment v2-A7;
no new package, no new SD-1 entry, no write, no live-availability probe, and no
registry rows.

### 15.4 — What ratifying does not authorize

- **No registry rows by any route.** The three refused paths stay refused; a later
  request to show the nine rows is a new ruling under CP-3 and SD-2, not this one.
- **No live probe.** The panel reports what the gate attested before the port bound.
  A `configured` seam is not a reachable engine, and the screen must say so.
- **No second read, no write, no file read.** One operation; the report is handed
  once and is immutable in the process, as the config it describes is.
- **No SD-1 entry, no console route, no reopening of FD-11.4.**

## 16 — Implementation record, MA-2 as amended (2026-09-06)

Shipped as `governance-studio-deployment` 0.12.0 and studio contract amendment v2-A7.
What each ruling became, and where the claim is checked:

| Ruling | What landed | Where it is checked |
|---|---|---|
| MS-1 `SEAM_STATES_ONLY` | `DeploymentStatusService` (`services/studio_v2.py`) returns the six seam states, the `checks` map, `result`, `failure_code` and the pins, and has no field that could carry a registry row. | `backend/tests/test_deployment_status.py::test_ms1_*`; `deployment/.../tests/test_deployment_status_seam.py::test_ms1_*`; `frontend/tests/status-screen.test.tsx` ("shows no registry row") |
| MS-2 `IN_MEMORY_RESULT_AT_COMPOSITION` | `server.run()` hands `result.report` to `build_app(deployment_report=…)`, which hands it to `_build_backend` and on to `build_studio_context(deployment_report=…)`; the service deep-copies it at construction and returns copies. `startup-integrity.json` is still written for the operator and is read by no route. | `test_deployment_status_seam.py::test_ms2_*`: the file corrupted, then deleted, then the handed dict mutated, and four identical answers; `test_deployment_status.py::test_ms2_*` |
| MS-3 `OBSERVE_DEPLOYMENT_ONE_READ` | `GET /api/v2/observe/deployment`, operation `v2_observe_deployment`, summary "Deployment Status", in the observe router. Amendment v2-A7 chains from v2-A6 (`f42472ab…` → `c6785b26…`); the generated client and its hash were regenerated with `npm run generate:api-v2`. | `test_v2_operation_ids.py` (id, path and summary scans, drift); `test_publish_pin.py`; `verify_openapi_v2.py`; `verify:openapi-v2` and `verify:v2-api-boundary`; `test_deployment_status_seam.py::test_the_seventh_amendment_*` |
| MS-4 `SEAM_STATES_CHECKS_AND_PINS` | `SEAM_STATE_FIELDS` and `PIN_FIELDS` name the field set; `cert_subject` and `cert_expiry` are named in `excluded_fields` and never in the result. | `test_deployment_status.py::test_ms4_*`; `test_deployment_status_seam.py::test_ms4_*`, against the real gate's certificate facts |
| MS-5 `SEPARATE_STATUS_PANEL` | `StatusScreen` at `/studio/status`, a "Status" entry in the studio nav; the Observe screen is untouched. | `status-screen.test.tsx` (four tests); the a11y suite's new entry; `observe-two-sources.test.tsx` unchanged and passing |
| frontend boundary | `approved-v2-api-operations.json`: 25 → 26 operations, 22 → 23 paths, new `openapi_sha256`; `V2_OPERATIONS` and `REQUIRED_V2_OPERATIONS` each gained one line. `v2_export_read` stays deliberately unapproved. | `studio-security.test.ts`; `verify:v2-api-boundary` ("26 operations consumed") |
| P3E freeze | `approved-runtime-config.json`: version 0.12.0, `frozen.openapi_v2_sha256`, the amendment string led by v2-A7, and a `deployment_status` block. `configuration_added` stays at eight, `first_party_packages_in_image` at seventeen, `front_door_seams.handed_to_build_studio_context` at eight: the report is not a front-door seam and needs no variable or package. | `test_deployment_status_seam.py::test_the_runtime_config_records_the_seam_and_nothing_else_moved`; `test_container_artifacts.py` |
| composition record | `composition-record.json` is the seam-11 registration (`reg_8dd15380…`, digest `f65c1ae4…`), superseding the clearance-export record kept byte-for-byte as `composition-record.seam-10.json`; `seams_handed_to_build_studio_context` ends in `deployment_report`. The two prior seam tests that pinned the head were re-pointed in the pattern every seam used. | `test_constitution_seam.py` (the chain, seam 10 added and the head moved); `test_clearance_export_seam.py`; `test_deployment_status_seam.py::test_the_composition_record_*` |

**Verified, not asserted.**

| Check | Result |
|---|---|
| studio backend suite | 359 passed |
| `backend/scripts/verify_openapi_v2.py` | in sync, `c6785b26…` |
| studio frontend: vitest | 26 files, 259 passed, the four status-screen tests and the a11y entry among them |
| studio frontend: lint, type-check, build, `verify:openapi-v2`, `verify:v2-api-boundary` | all exit 0 |
| deployment suite | 329 passed, 1 skipped; packaged end-to-end 9 passed |
| `platform_freeze.verify`, `verify_ratified_pins.py`, `verify_gate_identifiers.py` | all pass |

**What did not change.** The v1 contract (`dc309eab…`). The SD-1 allowlist (eleven
entries; `sd1_entries_added` is `[]`). The console's served and withheld sets and the
studio's four-route console allowlist. No environment variable, no image package, no
credential, no egress destination; the review relay stays the one destination with
seven routes. The Observe screen's two labelled sources.

**Three decisions the implementation made, recorded rather than made quietly.**

- **The composition record documents its context digest.** Prior records carry a
  `context_digest` whose derivation is not written down. This one derives it from a
  named string and records that string in `context_digest_of`, so the next seam can
  reproduce it instead of inheriting an opaque value.
- **A non-GET on the route is the framework's 405.** No write handler exists to refuse
  with a typed reason; the absence is structural, as the export route's is, and the
  tests assert it.
- **The operator's file is still written.** MS-2 moves the panel's source into memory;
  it does not remove the report from the volume, where the container gate and an
  operator still read it. The tests prove the panel does not.

MA-1, MA-3, MA-4 and MA-5 were implemented or recorded in §13 and §14. With this record
every ruling in §11 and §15 is implemented, and nothing in §12 or §15.4 is authorized
beyond it.
