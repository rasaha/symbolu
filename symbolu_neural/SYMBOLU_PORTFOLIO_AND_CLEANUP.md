# Symbol-U Implementations — Portfolio & Repo-Wide Cleanup Map

Extends `internal_policy_controller/VERSION_CLEANUP_PLAN.md` to **every** Symbol-U
patent-implementation attempt under `symbolu_neural/`. **Nothing is deleted here.**

## Key correction up front

These are **not one supersession chain.** Each directory tested a **different
hypothesis** about the patent and recorded an honest verdict. So, unlike
internal_policy_controller v1→v2→v3 (a true lineage where v3 supersedes v1/v2),
the *other* implementations are mostly **the scientific record** (completed
falsification experiments) plus **shared helpers live code depends on** — **not**
dead code to delete. Deleting them would erase the evidence trail that justifies
the project's conclusions.

## Dependency facts (verified)

Cross-directory imports:
```
clean_softmax              -> modules
stage1                     -> modules
controllability_pilot      -> complementarity_probe.backends
internal_policy_controller -> complementarity_probe.backends   (v1 critics, v2, v3)
internal_policy_controller -> api_control_protocol.llm         (v1 reviser only)
```
Shared helpers (imported by ≥1 other dir): **`complementarity_probe.backends`**,
**`modules/`**, **`api_control_protocol.llm`** (v1-only). The skeleton **root**
files (`backbone.py`, `model.py`, `config.py`, `losses.py`, `ablations.py`,
`smoke_test.py`) are imported by **nothing**. Nothing outside `symbolu_neural/`
imports any of this.

## Portfolio inventory & classification

| dir | hypothesis tested | verdict (see its report) | dep role | **status** |
|---|---|---|---|---|
| `symbolu_neural/` root (backbone/model/config/losses/ablations/smoke_test) | Symbol-U as trainable nn.Module skeleton | interface-only, never trained | **orphaned** (imported by nothing) | **superseded → deletion candidate (after authorization)** |
| `modules/` | per-EQ neural modules (typed heads, memory, refinement) | feeds the skeleton/clean_softmax | **shared helper** (clean_softmax, stage1) | **keep** (live dep) |
| `stage1/` | frozen-backbone grounding harness | grounding failed to generalize | leaf (uses modules) | **completed experiment — keep for record** |
| `clean_softmax/` | token/sentence-level heads, fusion, steering, capacity studies | **no advantage at equal compute** (the core negative) | leaf | **completed experiment — keep for record** (bulk of falsification evidence) |
| `complementarity_probe/` | does U add info beyond E? + the `backends.py` Symbol-U vector engine | U phonological, not complementary | **CANONICAL shared helper** (`backends.py`) + experiment | **keep (canonical)** |
| `controllability_pilot/` | does U steer better than matched controls? | no (beaten by random/sentiment) | leaf (uses backends) | **completed experiment — keep for record** |
| `api_control_protocol/` | U as external API control packet + `llm.py` clients | ontology inert, ~4× tokens | `llm.py` used by v1 reviser only | **completed experiment — keep for record** |
| `internal_policy_controller/v3/` | draft→policy→final, full state | structurally sound; **quality UNTESTED** (no API) | active | **CANONICAL (current active line)** |
| `internal_policy_controller/` v1, v2-core | (same lineage, earlier) | invalid (v1) / defective (v2) | v2/{data,llm,judge} are v3 deps | **deprecated → deletion candidate after v3 API run** (see VERSION_CLEANUP_PLAN.md) |

## What is genuinely deletable (beyond v1/v2) — and what is NOT

**Additional deletion candidates (orphaned, superseded):**
- The skeleton **root** files `symbolu_neural/{backbone,model,config,losses,ablations,smoke_test}.py`
  — imported by nothing; superseded by `clean_softmax`. *Candidate only; keep for
  audit until authorized.* (Note: `modules/` is **not** in this set — clean_softmax
  and stage1 import it.)

**NOT deletion targets (do not propose deleting):**
- `complementarity_probe/` — canonical Symbol-U vector engine (`backends.py`) that
  controllability_pilot and v2/v3 all import.
- `modules/` — live dependency of clean_softmax + stage1.
- `clean_softmax/`, `controllability_pilot/`, `api_control_protocol/`, `stage1/` —
  **completed experiments = the scientific record.** Each has an honest report and a
  distinct verdict; together they are the falsification trail. Archive, never delete.
- `docs/SYMBOL_U_TECHNICAL_RESEARCH_SPECIFICATION.md` and all `*REPORT*.md` /
  audit docs — the documented record. Keep.

**Out of scope (the user's pre-existing code, not my experiments):**
`symbolu_core/` (formulas — *canonical*, v3 depends on `symbolu_core.formulas`),
and the Hybrid-Phase / Sovereign / JEPA training code. Do not touch.

## Recommended sequence (non-destructive now)

```
[NOW]   top-level index (symbolu_neural/README.md) labels every dir's status;
        skeleton root marked superseded; this portfolio doc committed.
[AFTER v3 API run]  relocate v2/{data,llm,judge} into v3; re-test.
[ON AUTHORIZATION]  delete: internal_policy_controller v1 + v2-core, and the
        orphaned skeleton root files. Archive (not delete) all completed-experiment
        dirs + reports into an `archive/` if desired.
```

## Bottom line

The only directories that behave like deletable "superseded code" are
**internal_policy_controller v1/v2-core** and the **orphaned skeleton root files**.
The other Symbol-U implementations are either **shared canonical helpers** or the
**experimental record** and should be **kept** (archived at most). No Symbol-U
implementation should be run for scientific conclusions except the canonical line
(`v3`, once API-tested) — every other dir's report already states its own verdict.
No deletions performed; awaiting explicit authorization.
