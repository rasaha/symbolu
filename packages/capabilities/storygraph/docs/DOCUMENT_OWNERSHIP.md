# StoryGraph — Document Ownership Manifest

Every StoryGraph-related document, its canonical location, category, whether it
ships in the wheel, whether it is historical or current, and its owner. Also lists
cross-product documents that *mention* StoryGraph but are owned elsewhere.

Paths are relative to `packages/capabilities/storygraph/` unless noted. "Ships in
wheel" reflects the package-data policy proven by `verify_storygraph_distribution.py`.

## StoryGraph-owned — canonical documentation (`docs/`, repository-only)

| Document | Canonical location | Category | Ships in wheel | Historical/current | Owner |
|---|---|---|---|---|---|
| Documentation index | `docs/README.md` | Index | No | Current | StoryGraph |
| This manifest | `docs/DOCUMENT_OWNERSHIP.md` | Ownership | No | Current | StoryGraph |
| CAPABILITY_OVERVIEW.md | `docs/architecture/` | Architecture | No | Current | StoryGraph |
| COMPOSITE_THREAT_DETECTION_SPEC.md | `docs/architecture/` | Architecture / spec | No | Current | StoryGraph |
| STORY_GRAPH_SPEC.md | `docs/architecture/` | Architecture / spec | No | Current | StoryGraph |
| STORY_GRAPH_PARTIAL_MATCH_SPEC.md | `docs/architecture/` | Architecture / spec | No | Current | StoryGraph |
| LINKAGE_SCHEMA.md | `docs/architecture/` | Architecture / schema | No | Current | StoryGraph |
| RECIPE_SCHEMA.md | `docs/architecture/` | Architecture / schema | No | Current | StoryGraph |
| api/README.md | `docs/api/` | Public API | No | Current | StoryGraph |
| ENTERPRISE_STORY_POLICY_PACK.md | `docs/policy-packs/` | Policy Pack | No | Current | StoryGraph |
| HISTORICAL_REPLAY_K8S_CONTRACT.md | `docs/replay/` | Replay | No | Current | StoryGraph |
| HISTORICAL_REPLAY_READINESS_CHECKLIST.md | `docs/replay/` | Replay | No | Current | StoryGraph |
| SANITIZED_ENTERPRISE_REPLAY_REPORT.md | `docs/replay/` | Replay / evidence | No | Historical | StoryGraph |
| COMPOSITE_SEQUENCE_RISK_EVALUATION_PLAN.md | `docs/evaluation/` | Evaluation plan | No | Current | StoryGraph |
| ENFORCEMENT_PROMOTION_CHECKLIST.md | `docs/evaluation/` | Enforcement-promotion gate | No | Current | StoryGraph |
| SHADOW_PILOT_REPORT_TEMPLATE.md | `docs/evaluation/` | Evaluation template | No | Current | StoryGraph |
| STORY_GRAPH_FINAL_SPLIT_AUDIT.md | `docs/evaluation/` | Evaluation / evidence | No | Historical | StoryGraph |
| STORY_GRAPH_EVIDENCE_LEDGER.md | `docs/evaluation/` | Evidence ledger | No | Historical | StoryGraph |
| PHASE3_FINAL_EVALUATION_REPORT.md | `docs/evaluation/historical/` | Evaluation report | No | Historical | StoryGraph |
| STORY_GRAPH_PARTIAL_MATCH_VALIDATION.md | `docs/validation/` | Validation | No | Historical | StoryGraph |
| STORY_GRAPH_ADVERSARIAL_VALIDATION.md | `docs/validation/` | Validation | No | Historical | StoryGraph |
| STORY_GRAPH_VERIFICATION_VALIDATION.md | `docs/validation/` | Validation | No | Historical | StoryGraph |
| MIGRATION_NOTES.md | `docs/reference/` | Reference / history | No | Historical | StoryGraph |
| KNOWN_LIMITATIONS.md | `docs/limitations/` | Limitations | No | Current | StoryGraph |

## StoryGraph-owned — front-matter & runtime (package, ships in wheel where noted)

| Document / data | Location | Category | Ships in wheel | Owner |
|---|---|---|---|---|
| README.md | `./` | Package overview | **Yes** (readme metadata) | StoryGraph |
| CHANGELOG.md | `./` | Changelog | No | StoryGraph |
| MIGRATION.md | `./` | Migration guide | No | StoryGraph |
| examples/*.py + examples/README.md | `examples/` | Examples | No (repo-only; run against the wheel) | StoryGraph |
| replay_intake/README.md, policy_gap_report.template.md, *.template.json, replay_record.schema.json | `src/ugence_storygraph/replay_intake/` | Replay intake (runtime) | **Yes** | StoryGraph |
| policypack/schemas/storypolicypack.schema.json | `src/ugence_storygraph/policypack/schemas/` | Runtime schema | **Yes** | StoryGraph |
| policypack/fixtures/account_takeover_replay.json | `src/ugence_storygraph/policypack/fixtures/` | Runtime fixture | **Yes** | StoryGraph |
| evaluation/fixtures/k8s_replay_example.jsonl | `src/ugence_storygraph/evaluation/fixtures/` | Runtime fixture | **Yes** | StoryGraph |

## StoryGraph migration evidence (repository-level, not in package)

| Document | Location | Category | Ships in wheel | Owner |
|---|---|---|---|---|
| BASELINE.md, BASELINE_manifest.json, BASELINE_test_manifest.txt, API_INVENTORY.md, FILE_MAP.md, IMPORT_GRAPH.md, POST_MOVE_manifest.json, STORYGRAPH_CANONICAL_PACKAGE_MIGRATION_REPORT.md, STORYGRAPH_DOCUMENTATION_CANONICALIZATION_REPORT.md | `docs/migrations/storygraph/` (repo root) | Migration evidence | No | StoryGraph (repository) |

## Legacy compatibility documentation

| Document | Location | Category | Owner |
|---|---|---|---|
| README.md ("moved" pointer) | `cyber_security/composite_threat_detector/` | Legacy compatibility | StoryGraph (compat) |

## Cross-product documents that mention StoryGraph but are owned elsewhere

| Document | Location | Owner | Note |
|---|---|---|---|
| artifact_story_policy.schema.json | `cyber_security/action_gate_policy_schemas/` | **ActionGate** | ActionGate package artifact that *consumes* StoryGraph as evidence |
| ACTION_GATE_SPECIFICATION.md and other ActionGate specs | `cyber_security/` | **ActionGate** | Cross-referenced by StoryGraph's `signals.py`; not StoryGraph-owned |
| UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md, UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md, UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md | repo root | **Platform** | Repo-wide audits that discuss StoryGraph as one module |
| UGENCE_PLATFORM_OVERVIEW.md, VC briefs, `acp/`, `agent_runtime_*`, `platform/PLATFORM_FREEZE_V1.json` | repo-wide | **Platform / Product** | Reference StoryGraph in passing; StoryGraph is not in the platform freeze |

**Rule:** an ActionGate/platform/product document is **not** moved merely because
it mentions StoryGraph. Only genuinely StoryGraph-owned documents live under
`packages/capabilities/storygraph/`.
