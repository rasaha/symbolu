# Live-State Audit — Agent Workforce Composer P2.1

Policy Workflow Compiler `workflow_ir.v2` Compatibility Adapter, Overlay Reduction
and Fingerprint-Preserving Migration. Machine form: `LIVE_STATE.json`.

## Repository state

| Item | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `db10adad0c4f02ecc52f99c820b6419f25b436e5` |
| Working branch | `claude/awc-p2-1-compiler-v2-adapter` (env `claude/` prefix; supersedes suggested `chatgpt/awc-p2-1-compiler-v2-adapter`) |
| Working tree at branch creation | clean |
| Active P2.1 PR already open? | No |

## Prerequisite PRs (verified merged)

| PR | What | Merge commit |
|---|---|---|
| #1308 | AWC P1 | `d1cfad24…` |
| #1310 | AWC P2 | `0f5a461f…` |
| #1312 | Governance Studio P3A | `8f19d17b…` |
| #1314 | Policy Workflow Compiler P2 | `40d19b83` |
| #1316 | PWC P2 version-decoupling correction | `db10adad` (default tip) |

Gate **AWC-P2.1-A1** satisfied. The merged compiler reports **distribution 0.2.0,
product 0.2.0, contracts `workflow_ir.v1` + `workflow_ir.v2`**, with the v1 digest
semantic identity frozen at `0.1.0` independently of the package version.

## Baselines (before change)

| Suite | Result |
|---|---|
| AWC P1/P2 | **158 passed** (→ **203** after, +45 P2.1 tests) |
| Governance Studio P3A | **94 passed** (unchanged; not modified) |
| Policy Workflow Compiler | **153 passed, 1 skipped** (unchanged; not modified) |
| Platform-freeze | **PASS** — digest `d993093570…` |

## What P2.1 changes

- Adds a **new `adapter_v2.py`** (v2 semantic compatibility adapter) and
  **`compatibility.py`** (explicit contract-version dispatch + equivalence harness)
  to the AWC package. The v1 adapter (`adapt_compiled_workflow`) is **byte-frozen**.
- AWC distribution/product version **0.2.0 → 0.2.1** (additive minor). The planning
  contracts **`awc.v1`** and **`awc.composition.v1`** are unchanged; a new
  **`awc.compiler_adapter.v2`** metadata contract version is added for adaptation
  envelopes only (not part of any planning fingerprint).
- Public API **93 → 109** (all P1/P2 names preserved).
- Committed v1/v2 equivalence conformance fixtures for the four P3A scenarios under
  `packages/capabilities/agent-workforce-composer/conformance/governance_studio_v2/`.

## What P2.1 does NOT change

The eligibility, ranking, composition, permission-bounding and fallback algorithms;
the compiler package; the Governance Studio app and its P3A fixtures; runtime / H16
/ H22 / Model Selection; the platform-freeze digest. The AWC compiler adapter reads
the compiler's serialized `workflow_ir.v2` as **data** — it never imports the
compiler package.
