# StoryGraph Canonical-Package Migration — Baseline

**Phase:** StoryGraph canonical-package migration (zero semantic change, complete
backward compatibility).
**Purpose of this document:** record the exact, independently-verified pre-migration
state so that semantic equivalence, test equivalence, digest stability, and evidence
preservation can be proven after the move. This is gate **S1** (exact baseline).

Machine-readable companion: [`BASELINE_manifest.json`](./BASELINE_manifest.json).
Deduplicated test-ID manifest: [`BASELINE_test_manifest.txt`](./BASELINE_test_manifest.txt).

---

## 1. Branch and commit

| Item | Value |
|---|---|
| Source branch (prescribed) | `claude/ugence-modularity-audit-uujl0h` |
| Source commit (prescribed) | `c10f21f48e55212f80704dbc2a6c1749777a76e0` |
| Implementation branch | `claude/storygraph-canonical-package-migration-m25c2i` |
| Baseline HEAD | `6a49634e614120cd46beda395d993cb4c6590383` |
| Relationship | `c10f21f` is an ancestor of HEAD; `git diff c10f21f HEAD` is **empty** — the working tree is byte-identical to the prescribed source commit. Migration proceeds from this verified-equivalent tree on the designated branch. |

Independently verified — the "289 tests" figure from the prior audit was **re-run**, not
assumed (see §3).

---

## 2. Canonical StoryGraph location (verified)

StoryGraph's single canonical implementation lives under one directory:

```
cyber_security/composite_threat_detector/
├── composite_threat_detector/     # core package (41 .py) — relative imports internally
│   └── policypack/                # Policy Pack subpackage (+ schemas/, fixtures/)
├── evaluation/                    # evaluation infrastructure (15 .py, + fixtures/, results/)
├── demos/                         # demo scenarios (2 .py)
├── replay_intake/                 # replay intake schema + templates (JSON/MD)
├── tests/                         # 24 test files → 289 tests
├── conftest.py                    # puts the ctd root on sys.path
└── *.md                           # 13 capability documents
```

**External consumers:** a repo-wide grep for `composite_threat_detector` outside this
directory returns **zero** Python importers. StoryGraph is fully self-contained.
**Packaging:** there is **no** `packaging/` entry and **no** `pyproject.toml` for
StoryGraph at baseline — no wheel exists to build. (Confirmed by inspecting
`packaging/`, which contains only decision-governance / provider / benchmark units.)

---

## 3. Test baseline (independently re-run)

Runner: `pytest 9.1.1`, CPython 3.11.15, invoked from the `composite_threat_detector/`
root directory (its `conftest.py` puts the three sibling packages on `sys.path`).

| Metric | Count |
|---|---|
| **Collected** | **289** |
| **Passed** | **289** |
| **Failed** | **0** |
| **Skipped** | **0** |
| **Deselected** | **0** |
| **Errors** | **0** |
| Unique test IDs (deduplicated) | **289** |

Collected == unique == passed == 289 (no duplicates, no parametrization collisions).
The full deduplicated `file::test` manifest is in `BASELINE_test_manifest.txt`.

**Infrastructure requirements:** none beyond CPython ≥3.10 and `pytest`. No network,
no GPU, no database server, no credentials, no live cluster. The suite is deterministic
(no wall-clock / randomness / network / LLM in the authoritative path). Total runtime
≈6.4s. Zero infrastructure-dependent or GPU-gated tests exist in this suite.

---

## 4. Versions (frozen semantic identifiers)

These strings are **semantic freeze identifiers**, not import paths. They embed a
historical `ctd.` prefix and **must not change** during a physical move — they
participate in freeze/replay digests.

| Constant | Value |
|---|---|
| Package `__version__` | `2.0.0` |
| `STORYGRAPH_SCHEMA_VERSION` | `ctd.storygraph/1.1.0` |
| `MATCHER_SEMANTICS_VERSION` | `ctd.storygraph.matcher/2.0.0` |
| `PARTIAL_ESCALATION_POLICY_VERSION` | `ctd.partial_escalation/1.0.0` |
| `TIE_BREAK_RULE_VERSION` | `ctd.witness.tiebreak/2.0.0` |
| `MINIMALITY_BASIS` | `SEMANTIC_EQUIVALENCE_CLASS` |
| `COMPILER_VERSION` (policypack) | `ctd.policypack.compiler/1.0.0` |
| `SCHEMA_VERSION` (policypack) | `ctd.storypolicypack/1.0.0` |
| `EVENT_MAPPING_SCHEMA_VERSION` | `ctd.event_mapping/1.0.0` |
| `PROVIDER_MAPPING_SCHEMA_VERSION` | `ctd.provider_mapping/1.0.0` |
| `EVIDENCE_CHAIN_VERSION` | `ctd.evidence_chain/1.0.0` |
| `LINKAGE_SCHEMA_VERSION` | `ctd.linkage/1.0.0` |
| `SCHEMA_VERSION` (durable audit) | `ctd.audit/1.0.0` |

---

## 5. Digest anchors (semantic-equivalence proof surface)

All digests are computed by `canonical.digest()` over **canonical content**, never over
module/file paths. A pure physical move therefore leaves every value below **unchanged**;
any drift signals an accidental semantic change and must halt the phase (gate S3).

| Anchor | Value |
|---|---|
| Frozen `ACCOUNT_TAKEOVER_TRANSFER@1.0.0` | `sha-256:6a77b8997263c40f2b6d791c9391ae562dfb51ba6e7ae04ce5da5f775cc081a8` |
| Frozen `DIGITAL_EXFILTRATION_STORY@1.0.0` | `sha-256:a8bce84705439cc449fb36ce15ce2a9b54cdea23fb5cc4a6a7b715134668d9e1` |
| Reference pack compiled graph freeze digest | `sha-256:6a77b8997263c40f2b6d791c9391ae562dfb51ba6e7ae04ce5da5f775cc081a8` (== frozen ATO — pack changes no semantics) |
| Reference pack bundle digest | `sha-256:f6323c9275e125be0766fbc3986683aae3ece8009cad80df08278f8114896a1e` |
| Deterministic replay report digest (bundled ATO fixture) | `sha-256:0dcf2bc4730bf12a89e5e5e6b54b8a9442b59b105dc068659d8035033977923b` |
| Replay pre-registration digest | `sha-256:1f026c7a95ee64bb9d2d8398941f84d75ff38f6414b7429b42eba76a736422d4` |
| `storypolicypack.schema.json` (bytes) | `sha-256:24bc416ee4d54967264e5f86d7f959bd458bd2d5f6a3d0696c8af074d8070779` |
| `replay_record.schema.json` (bytes) | `sha-256:…` (see manifest) |

---

## 6. Public API (before)

`composite_threat_detector.__all__` exposes **75** public symbols (full list in the
manifest). The curated *stable* subset that will become `ugence_storygraph.api` is
defined in [`API_INVENTORY.md`](API_INVENTORY.md). Key public entrypoints:
`SequenceRiskAnalyzer`, `CompositeThreatMonitor`, `StoryGraph`, `story_match`,
`story_evaluate`, `evaluate_proposed_action`, `completion_witness`,
`to_advisory_evidence`, `DIGITAL_ONTOLOGY`, `FINANCIAL_ONTOLOGY`, `PolicyBinding`,
`ProviderRegistry`, `OBSERVE`/`ESCALATE`/`UNAVAILABLE`, and the reference stories
`ACCOUNT_TAKEOVER_TRANSFER`, `ACCOUNT_RECOVERY_STORY`, `BANK_ASSISTED_TRANSFER_STORY`.

---

## 7. Dependency graph (before)

```
composite_threat_detector (core)  →  Python standard library ONLY
evaluation                        →  composite_threat_detector (+ demos), stdlib
demos                             →  composite_threat_detector, stdlib
```

**Third-party dependencies: NONE.** **Ugence-package dependencies: NONE.**
Standard-library modules used: `argparse, dataclasses, datetime, fnmatch, hashlib,
json, os, platform, random, re, sqlite3, sys, time, tracemalloc, types, typing`.

This is the strongest possible starting point for gate S5 (independent packaging) and
S7 (dependency compliance): StoryGraph imports **zero** ActionGate / ACP / Decision
Governance / Agent Runtime / console / research code, and no prohibited edge exists to
remove — only to *keep absent*.

---

## 8. Governance path couplings (must relocate coordinately)

Four repo-relative **governance path globs** in `evaluation/evidence_chain.py`
(`APPROVED_EVIDENCE_PATHS`) and two test inputs in `tests/test_policypack.py` hardcode
the old physical location `cyber_security/composite_threat_detector/...`. These are
**not** import paths and **not** digest inputs — they declare which files an
evidence-only commit may touch. They are relocated to the new canonical location as a
coordinated mechanical change (source + test together), preserving the check's
semantics. No sealed evidence records exist at baseline (`evaluation/` contains only a
results *template*), so the globs are forward-looking infrastructure.

---

## 9. Baseline reproduction procedure

```bash
git checkout claude/storygraph-canonical-package-migration-m25c2i   # tree == c10f21f
pip install pytest
cd cyber_security/composite_threat_detector && python -m pytest      # 289 passed
```
Digests/versions: `python docs/migrations/storygraph/../../../` helpers reproduce the
values in §4–§5 (see `BASELINE_manifest.json`, regenerated post-move for comparison).
