# Ugence console packaging — scoping audit

**Status:** audit, 2026-09-06. Documentation only: this record amends no package,
port, test, manifest or deployment artifact, and activates no seam. It answers the
question FD-8.3 left open and proposes one ruling, CP-1 to CP-5, for the owner.

Ordered by `ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` FD-8.3 `PACKAGE_FIRST`:
"before the console may enter deployment, it must become a bounded, installable and
tested package or deployment unit with explicit public API, configuration,
persistence boundary, authentication boundary, maturity label and import
restrictions. Packaging is a separately scoped future body of work; it does not
begin here."

Evidence labels: `[V]` verified against this repository at `98cb4325`, `[I]`
inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question, and the answer

Is console packaging scopable now? **Yes — and unlike result egress, which was
audited on the same day and found not scopable, everything the work needs already
exists.** There is a running prototype with a real HTTP surface, real capability
adapters over the platform's own packages, a ruling that already names the six
required properties, and a studio that has been waiting on it since FD-8.1. What is
missing is not knowledge; it is five owner decisions and the work itself.

## 2 — What the console actually is `[V]`

Two distinct artifacts, and a correction to how they have been described.

| Artifact | What it is |
|---|---|
| `ugence_console_api/` (repository **root**) | the Python service FD-8.3 names: 15 modules, ~1,116 lines, FastAPI, `__version__ = "0.1.0"` |
| `apps/console/` | a separate Vite + React + TypeScript web app that talks to it |

`ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` §15.2 described "the root prototype at
`apps/console/`". That conflates the two: the root prototype is
`ugence_console_api/`, and `apps/console/` is its frontend, itself not at the
repository root. Corrected there alongside this record.

## 3 — FD-8.1's four defects, each still present `[V]`

FD-8.1 refused the console entry on four grounds. All four hold today:

| Defect named in FD-8.1 | Verified state |
|---|---|
| root-level prototype | `ugence_console_api/` sits at the repository root with **no `pyproject.toml` and no `setup.py`** — it is not a distribution and cannot be installed |
| unauthenticated HTTP listener | `__main__.py:14` binds `host="0.0.0.0"` with no TLS, and `app.py` declares no `Depends`, `HTTPBasic` or `Authorization` on any route |
| in-memory audit store | `audit.py`'s `AuditStore` is a `Dict[str, AuditChain]` behind a lock; its own docstring calls it "deliberately a prototype seam" |
| absent from both container images | neither `Dockerfile` copies or installs it |

## 4 — What is better than FD-8.1 implies `[V]`

Two findings that make the work smaller than the defect list suggests, and one that
makes it larger. Stating all three, because a packaging estimate built only on §3
would be wrong in both directions.

- **The capability adapters are real.** `capabilities/context_gateway.py`,
  `action_control.py` and `truth_evidence.py` import the platform's own
  distributions (`ugence_context_minimization.api` and others) through their public
  API surfaces, not through internal modules or `sys.path` hacks — a migration the
  gateway adapter's own docstring records as already done.
- **Degradation fails closed, not open.** Each adapter guards its import with a
  fail-safe `try` and an `_available` flag, so a missing dependency does not crash
  the app. But the *call* path refuses: `action_control.authorize` raises
  `RuntimeError(f"actiongate unavailable: {_reason}")` rather than returning a
  permissive verdict. The console cannot silently authorize.
- **The same pattern is the packaging problem.** Three modules degrade on a missing
  import, which means the service has **no declared dependency set**: it starts, and
  serves, in a configuration where the governance it advertises is absent. A
  distribution must state its dependencies and fail at install time instead `[G]`.

## 5 — The surface to be bounded `[V]`

Eleven routes exist. The studio's frozen allowlist reaches four of them:

```
POST /v1/governed-loop/shadow
POST /v1/governed-loop/scenario/{scenario_id}
GET  /v1/audit
GET  /v1/audit/{correlation_id}
```

The other seven — `/health`, `/v1/modules`, `/v1/scenarios`,
`/v1/gateway/minimize`, `/v1/assertions/evaluate`, `/v1/actions/authorize`,
`/v1/actions/clear` — are reachable by anything that can open a socket to the
listener, and three of them (`authorize`, `clear`, `evaluate`) are the governance
verbs themselves. Bounding the public API is therefore not a documentation exercise:
it decides which of eleven routes a packaged console still exposes, and to whom.

Test coverage today is one file, `tests/test_governed_loop.py` `[V]`.

## 6 — Proposed ruling CP-1 to CP-5 (five decisions, recommended option first; ruled in §8)

| # | Decision | Options |
|---|---|---|
| **CP-1** | Scope of the first package | **`SERVICE_ONLY`**: package `ugence_console_api` alone; `apps/console/` stays a separate frontend, packaged later or never, exactly as the studio's frontend and backend are separate units. `SERVICE_AND_FRONTEND`: one deployment unit carrying both. |
| **CP-2** | Location and identity | **`PACKAGES_INTEGRATION`**: `packages/integration/console-api`, distribution `ugence-console-api`, namespace unchanged so no import in the tree moves. `DEPLOYMENT_UNIT_ONLY`: leave the module at the root and package only a deployment image, on the P3E precedent. |
| **CP-3** | The route surface | **`ALLOWLIST_THE_FOUR`**: the packaged service exposes the four routes the studio's frozen allowlist already names, plus `/health`; the three governance verbs and the three read-only introspection routes are not served by the packaged unit until separately ruled. `SERVE_ALL_ELEVEN`: package the surface as it stands. |
| **CP-4** | The audit store | **`DECLARE_THE_CEILING`**: keep the in-memory store, and make the package state on every answer that its audit is one process's view, lost on restart — the honest position FD-8.5 already ruled for the studio's Observe screen. `DURABLE_FIRST`: no packaging until a durable, hash-chained store replaces it (note: `control-plane-root` 0.2.0 is exactly that store, and the worker already uses it). |
| **CP-5** | The dependency posture | **`DECLARE_AND_FAIL_AT_INSTALL`**: the distribution declares every platform package its adapters import; the fail-safe `try` guards stay for development but a missing dependency becomes an install-time failure, not a runtime degradation. `KEEP_DEGRADING`. |

**What a ruling would authorize.** Documentation only, again: CP-1 to CP-5 settle
the shape, and the packaging itself would then be its own implementation step —
`pyproject.toml`, the bounded route surface, an authentication boundary, a maturity
label, boundary tests, and a test suite worth the name. Seam 4 stays absent under
FD-8.1 until that step completes **and** FD-8.4's second-destination ruling is taken;
this record does not enter it.

## 7 — What this record does not decide

- **Seam 4 itself.** FD-8.1 holds. Packaging is a prerequisite, not an entry.
- **The second egress destination.** FD-8.4 governs it and is untouched here.
- **TLS and gate mechanics.** The P3E deployment already solves both for the studio;
  reusing that shape is an implementation question, not a ruling.
- **`REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED = False`, the frozen v1 and
  v2 contracts, every `FROM` line and ratified digest, and every credential and LIVE
  prohibition** — all preserved.

## 8 — Ruling CP-1 to CP-5 (owner, 2026-09-06)

The recommended option is ratified in every case.

| # | Ruling |
|---|---|
| **CP-1** | **`SERVICE_ONLY`.** Package `ugence_console_api` alone. `apps/console/` stays an independently deployable React app, exactly as the studio's frontend and backend are separate units. |
| **CP-2** | **`PACKAGES_INTEGRATION`.** The service becomes `packages/integration/console-api`, distribution `ugence-console-api`, with its namespace unchanged so no import in the tree moves. |
| **CP-3** | **`ALLOWLIST_THE_FOUR`.** The packaged service exposes the four routes the studio's frozen allowlist already names, plus `/health`. The three governance verbs (`/v1/actions/authorize`, `/v1/actions/clear`, `/v1/assertions/evaluate`) and the three introspection routes are not served by the packaged unit until separately ruled. **A capability does not become public API because the underlying function exists**; each new external surface is separately authorized. |
| **CP-4** | **`DECLARE_THE_CEILING`.** The in-memory audit store is retained for this reference-grade, shadow-only stage, and the package discloses on every answer that its audit is one process's view, lost on restart. `control-plane-root` 0.2.0 remains the durable alternative for a later ruling. |
| **CP-5** | **`DECLARE_AND_FAIL_AT_INSTALL`.** Every platform package the adapters import becomes a declared distribution dependency. The fail-safe `try` guards may remain for development, but a missing governance dependency is an install-time failure, never a runtime degradation that serves while the governance it advertises is absent. |

**What the ruling authorizes.** Documentation only. No package moves, no route
changes, no dependency metadata and no code changes. **Packaging implementation does
not begin yet:** by owner direction the clearance-export seam is audited first
(`ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md`), so that the service is not packaged and
then immediately reopened to widen its public API. The sequence is CP rulings →
clearance-export audit and ruling → packaging implementation → export implementation.

CP-3 is the principle the export audit inherits: exporting a clearance is a **new
external capability** and must be separately authorized rather than appearing because
a compiler or a receipt type already exists.

## 9 — Implementation record (2026-09-06)

Shipped as `ugence-console-api` 0.2.0 at `packages/integration/console-api`. What each
ruling became, and where the claim is checked:

| # | Implementation | Checked by |
|---|---|---|
| CP-1 | The service alone moved. `apps/console/` is untouched and ships in no distribution. | `tests/test_packaging.py::test_the_react_app_is_not_part_of_this_distribution`; proof 1 of the distribution script |
| CP-2 | `packages/integration/console-api/src/ugence_console_api/`, distribution `ugence-console-api`. The namespace did not move, so all fourteen boundary tests that forbid `ugence_console_api` forbid the same name and none was edited. | `tests/test_packaging.py` (CP-2 group); `tests/boundaries/test_package_import_boundaries.py` |
| CP-3 | `create_app()` registers five routes. `app.SERVED_ROUTES` and `app.WITHHELD_ROUTES` name both sets; the four capability functions remain and the loop still runs all four in order. | `tests/test_served_surface.py`; proof 4 of the distribution script, which asserts each withheld route answers 404 from the *installed* application |
| CP-4 | `models.AUDIT_CEILING` — one constant — rides on every answer as the `X-Ugence-Audit-Ceiling` header (errors included) and inside `/health`, `GovernedLoopResult` and `AuditChain`. `control-plane-root` is deliberately not a dependency. | `tests/test_audit_ceiling.py`; proof 4 of the distribution script |
| CP-5 | Four platform distributions declared as required dependencies, none parked in an extra. | `tests/test_packaging.py` (CP-5 group); proof 2 of the distribution script |

**One forced consequence of CP-5, recorded because it changed source.** The adapters
imported the legacy root namespaces `governance_providers`, `actiongate_provider` and
`tap_provider`. Those are logic-free compatibility surfaces that ship in **no**
distribution, so a dependency declared on them could never be installed and the
fail-safe guards would have degraded every isolated install to "unavailable" — exactly
the runtime degradation CP-5 forbids. The adapters now import the canonical
distributions the shims alias (`ugence_actiongate_provider`, `ugence_tap_provider`,
`ugence_governance_provider_framework`). The shims preserve object identity by
construction, so behaviour, serialization and fingerprints are unchanged; this is the
only way to make CP-5's declaration true, not a reinterpretation of it.

**Known consequence for `apps/console/`.** The React app calls `/v1/modules` and
`/v1/scenarios`, two of the six routes CP-3 withheld. Under CP-1 that app is a separate
unit and is out of this slice; what it should show instead is a product decision, not a
packaging one, and it is not made here.

**Verified against the built artifact, not the source tree.**
`scripts/verify_console_api_distribution.py` builds the wheel, installs it into a clean
`--no-index` virtual environment, and interrogates the installed package — including the
one proof no source-tree test can make: that withholding `ugence-actiongate-provider`
makes the install **fail** rather than succeed and serve. 22 checks, all passing, run in
CI by the `console-api-distribution` job.
