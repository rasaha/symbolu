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

## 6 — Proposed ruling CP-1 to CP-5 (five decisions, recommended option first)

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
