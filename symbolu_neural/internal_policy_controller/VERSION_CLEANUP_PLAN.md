# Version Cleanup Plan — internal_policy_controller

**Decision requested:** does v3 supersede v1 and v2; what to keep / deprecate /
delete. **Nothing is deleted by this plan.** Only non-destructive markers are
applied now (README + deprecation banners). Destructive deletion waits for explicit
authorization after the v3 real-API run.

## Dependency facts (verified from the repo)

- **v3 does NOT import v1** → v1 is removable without breaking v3.
- **v3 DOES import `v2/data.py`, `v2/llm.py`, `v2/judge.py`** (and runs
  `v2/__init__.py`). These three are **live shared dependencies**, standalone
  (stdlib only), and do **not** import the defective v2 modules.
- The **defective** v2 modules (`v2/symbolu_state.py`, `v2/policy.py`,
  `v2/pilot.py`, `v2/cli.py`, `v2/tests/test_v2.py`) are **not** in v3's import
  chain.
- **Nothing outside `internal_policy_controller/` imports any version.**
- Consequence: **v2 cannot be deleted as a unit** — `data/llm/judge/__init__` must
  survive (or be relocated) for v3 to run.

## File-by-file classification

### v1 (top-level) — superseded, invalid (see `IMPLEMENTATION_FORENSIC_REVIEW.md`)
| file | class |
|---|---|
| `critics.py`, `drafts.py`, `evaluator.py`, `pilot.py`, `reviser.py`, `cli.py`, `__init__.py`, `tests/test_controller.py` | **deprecated — keep for audit history; deletion candidate after v3 API run** (imported by nothing) |
| `README.md` | **keep, updated** to point to v3 as canonical (this commit) |
| `INTERNAL_POLICY_CONTROLLER_REPORT.md` | deprecated — keep for audit history |
| `IMPLEMENTATION_FORENSIC_REVIEW.md` | **canonical audit doc — keep** |

### v2 — split: shared helpers are canonical, defective core is deprecated
| file | class |
|---|---|
| `v2/data.py`, `v2/llm.py`, `v2/judge.py`, `v2/__init__.py` | **canonical (shared helpers) — KEEP; do NOT delete** (live v3 deps). Future: relocate into `v3/` or a `shared/` module so v2 can be retired. |
| `v2/symbolu_state.py`, `v2/policy.py`, `v2/pilot.py`, `v2/cli.py`, `v2/tests/test_v2.py`, `v2/README.md` | **deprecated — keep for audit history; deletion candidate after v3 API run** (defective; not in v3 chain) |
| `INTERNAL_POLICY_CONTROLLER_V2_REPORT.md` | deprecated — keep for audit history |
| `V2_WIRING_AUDIT.md`, `V2_AUDIT_AND_V3_PLAN.md` | **canonical audit docs — keep** |

### v3 — canonical
| file | class |
|---|---|
| `v3/symbolu_state.py`, `v3/policy.py`, `v3/pilot.py`, `v3/cli.py`, `v3/__init__.py`, `v3/README.md`, `v3/tests/test_v3.py` | **canonical** |
| `INTERNAL_POLICY_CONTROLLER_V3_REPORT.md` | **canonical** |

## What can be safely deleted **now**

**Nothing.** Per the keep-for-audit policy and the standing rule (no deletion
without explicit authorization), no file is deleted in this step. Note that v1 is
technically orphaned (imported by nothing) and *could* be deleted with zero
breakage, but it is retained as the documented record of the invalid prototype.

## What must wait until after the v3 API run

1. **Relocate** `v2/{data,llm,judge,__init__}.py` into `v3/` (or a new `shared/`),
   update v3 imports, run `v3/tests/test_v3.py` — **prerequisite** for any v2 deletion.
2. **Then** delete (upon authorization): all v1 files, and the defective v2 modules
   (`symbolu_state.py`, `policy.py`, `pilot.py`, `cli.py`, `tests/test_v2.py`,
   `README.md`).
3. **Archive, not delete**, the audit/report docs (`IMPLEMENTATION_FORENSIC_REVIEW`,
   `V2_WIRING_AUDIT`, `V2_AUDIT_AND_V3_PLAN`, old reports) — e.g. move to `archive/`.

## Recommended cleanup sequence

```
[DONE, non-destructive]  README banner (v3 canonical, v1/v2 historical)
                         deprecation banners printed by v1 + v2 CLIs
                         deprecation notes in v1/v2 READMEs
        │
[DONE]                   relocate v2 shared helpers (data/llm/judge) INTO v3/
                         -> v3 is now SELF-CONTAINED; canonical line no longer
                         depends on deprecated v2. v3 tests 9/9 still pass.
        │
[ON AUTHORIZATION]       delete v1 files + the defective v2 modules (v2 now fully
                         decoupled from the canonical line). Reports/audit .md kept
                         in-tree; deleted code remains in git history.
```

**Status update:** the helper-relocation blocker is **resolved** — v3 carries its
own `data.py`/`llm.py`/`judge.py`. v1 and v2 are now pure orphans w.r.t. the
canonical line; their code can be deleted on an explicit go (the v3 real-API run is
no longer a technical prerequisite for deletion, only a recommended checkpoint).

## Bottom line

**v3 supersedes v1 and v2 as the implementation**, but v2 is **not fully
retireable yet** because v3 borrows its `data/llm/judge` helpers. Recommendation:
**deprecate now (non-destructive), relocate the three shared helpers after the API
run, then delete v1 + the defective v2 core on explicit authorization.** No
scientific conclusions should be drawn from v1 or v2.
