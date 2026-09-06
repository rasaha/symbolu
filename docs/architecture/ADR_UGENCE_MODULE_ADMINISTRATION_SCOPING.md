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
| **MA-2** | **`ONE_READ_ONLY_STATUS_PANEL`.** One studio panel over the nine static registry rows and the six seam states the startup integrity report already computes. Its cost is one v2 read operation, added as a contract amendment in the shape v2-A1 to v2-A6 established. No new package, no new SD-1 entry, no write, no live-availability probe. |
| **MA-3** | **`TWO_DEPLOYABLES_UNCHANGED`.** The studio and `apps/console` remain the two deployables CP-1 ruled. No third front end is built, and the two independently frozen contracts are not merged. |
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
