# Hybrid LLM vNext — Live Repository State

**Audit date:** 2026-08-03
**Auditor:** Automated audit (Claude Code), branch `claude/hybrid-llm-vnext-algorithm-audit-l8d74o`
**Phase:** Algorithm-identification / evidence audit / external SOTA comparison / architecture selection.
**Packaging status:** NOT AUTHORIZED in this phase.

> This document records the exact live state from which the audit begins so that
> every downstream finding is anchored to a verifiable commit. It is descriptive,
> not a decision document.

---

## 1. Default branch and HEAD

| Field | Value |
|---|---|
| Repository | `rasaha/symbolu` |
| Default branch (remote `HEAD`) | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default-branch HEAD commit | `69b3bb946e1d540f4e22380b48b9d7a8b463af20` |
| HEAD subject | `Merge pull request #1293 from rasaha/claude/context-minimization-v012-timestamp-hardening` |
| Audit branch | `claude/hybrid-llm-vnext-algorithm-audit-l8d74o` |
| Audit branch base | `69b3bb94` (0 commits ahead of default at audit start) |
| Working tree at start | Clean |

The audit branch was cut from the exact default HEAD and contained no commits of its
own at audit start (`git rev-list --count origin/<default>..HEAD` = 0). All audit
commits are additive documentation under `docs/audits/hybrid_llm/` plus scoped
verification scripts.

## 2. Prior-merge verification (Context Minimization)

The prompt's "expected prior merge" is Context Minimization v0.1.2 or its latest live
equivalent. Verified live via the GitHub API:

| PR | Title | State | Merged at (UTC) | Merge commit |
|---|---|---|---|---|
| #1291 | feat: package Context Minimization independently | MERGED | 2026-08-03T01:56:58Z | `b28c38d2` |
| #1292 | fix: harden Context Minimization oracle and result contracts | MERGED | 2026-08-03T02:34:31Z | `f884c18b` |
| #1293 | fix: validate Context Minimization timestamps and fingerprints | MERGED | 2026-08-03T03:09:31Z | `69b3bb94` (= default HEAD) |

- **PR #1292 status: MERGED**, merge commit `f884c18b`, base `claude/setup-symbolu-monorepo-…`. It moved the `ugence-context-minimization` leaf package `0.1.0 → 0.1.1` (contract `1.0.0 → 1.0.1`).
- **Latest merged Context Minimization = v0.1.2** (contract `1.0.2`), delivered by PR #1293 whose merge commit **is** the current default HEAD. This satisfies the "Context Minimization v0.1.2 or latest live equivalent" precondition.
- Both PRs explicitly state, in their own descriptions: *"H22 not implemented; Hybrid LLM packaging not started."* No Hybrid LLM packaging exists on the default branch.

## 3. CI status at HEAD

Combined check runs for the default-branch HEAD (`69b3bb94`, observed via PR #1293
check runs): **11 checks, all `success`.** Named checks include:

- `Context Minimization package suite (source)` — success
- `Wheel + sdist build + isolated installation + demo` — success
- `Migrated Console structural parity` — success
- `Platform-freeze verification` — success
- `Safety case + SBOM + traceability` — success
- `API stability registry` — success
- `terminology` — success

CI workflows present in `.github/workflows/` (14 total): `agent-runtime-ci.yml`,
`backbone-ci.yml`, `bcvf-autonomous-ci.yml`, `context-minimization-ci.yml`,
`core-rag-ci.yml`, `formula-drift-ci.yml`, `governance-contracts-ci.yml`,
`ontology-freeze-ci.yml`, `pipeline-ci.yml`, `renderer-ci.yml`,
`telemetry-audit-ci.yml`, `temporal-ci.yml`, `terminology-ci.yml`.

**Note:** There is **no** Hybrid-LLM / Phase / model-architecture CI workflow. The
model code (Phase transformer, binding cache, slots, hybrid training scripts) is
**not** covered by any CI gate on the default branch. `backbone-ci.yml` exercises a
different backbone surface, not the Phase/Hybrid model family (confirmed in the
implementation inventory).

## 4. Branch landscape (search for hidden experimental work)

Full remote branch enumeration (`git branch -r`):

```
origin/claude/hybrid-llm-vnext-algorithm-audit-l8d74o   (this audit branch)
origin/claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF   (default)
```

**There are exactly two remote branches, and no separate experimental Hybrid-LLM,
Phase, binding-memory, token/event-attention, or handover branch exists.** All such
work has already been merged into (or committed directly on) the default branch and
must be read from its history rather than from a live side-branch. Consequently, the
default branch contains both the latest *packaging* work (Context Minimization) **and**
the latest *experimental* model work — but these are unrelated systems that happen to
share the repository. The prompt's warning ("do not assume the default branch contains
the latest experimental result merely because it contains the latest packaging work")
is handled here by dating each model file from `git log` (see the lineage document),
not by assuming recency of the merge tip implies recency of the model code.

## 5. Known frozen artifacts

Freeze/immutability surfaces discovered (relevant to reproducibility, not all
model-related):

- `platform/PLATFORM_FREEZE_V1.json` — platform freeze manifest (digest `d4ad77e1…`, verified in CI; **unchanged** by this audit).
- `platform/api-snapshots/` — API stability registry snapshots.
- `SYMBOL_U_THEORY_V1_FREEZE.md`, `ONTOLOGY_FREEZE_CONTRACT.md` — theory/ontology freezes.
- `execution_gate/frozen/`, `evidence_assurance/verify_frozen.py`, `claim_integrity/verify_frozen.py`, `governed_inference_pilot/verify_frozen.py` — governance/evidence freeze verifiers (unrelated to the model family).
- `Project_documentation/control_plane/acp/ACP_V1_FREEZE.md`, `cer_v0_2/…`, `cer_v0_3/…` — protocol/baseline freezes.

The Hybrid LLM / Phase model family has **no dedicated freeze manifest** — its
checkpoints and saved metrics are ordinary tracked files, catalogued in the
implementation inventory and evidence ledger.

## 6. Repository scale

- Tracked files: **14,055**. Working-tree size ≈ **243 MB**.
- The words "hybrid", "phase", "attention", "memory", "handover", and "LLM" appear
  across many unrelated subsystems (governance, robotics, trading, control-plane,
  agent runtime). The implementation inventory disambiguates every model-relevant
  meaning; this scale is the reason a name-based match is insufficient and each
  component is classified individually.

## 7. Audit starting point (recorded)

```
repo            = rasaha/symbolu
default_branch  = claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF
head_commit     = 69b3bb946e1d540f4e22380b48b9d7a8b463af20
audit_branch    = claude/hybrid-llm-vnext-algorithm-audit-l8d74o
audit_base      = 69b3bb946e1d540f4e22380b48b9d7a8b463af20
working_tree    = clean
ci_at_head      = 11/11 checks success
pr_1292         = MERGED  f884c18b
pr_1293         = MERGED  69b3bb94  (= default HEAD, Context Minimization v0.1.2)
model_ci        = NONE (no Phase/Hybrid model CI workflow exists)
experimental_branches = NONE (all model work is in default-branch history)
```

This state is the baseline for the implementation inventory, evidence ledger,
external SOTA review, and architecture decision that follow.
