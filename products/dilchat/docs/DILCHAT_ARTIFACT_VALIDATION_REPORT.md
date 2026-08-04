# DilChat — Machine-Readable Artifact Validation Report

**Audit type:** Independent pre-implementation verification (reproduced from primary evidence).
**Branch:** `claude/dilchat-backend-design-e0douc`
**HEAD at audit start:** `9bedde0af81ef35d62924b44d5f51dd714250fcd`
**Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` (tip `379a6366`)
**Working tree at audit start:** clean; branch 1 commit ahead of default, 0 behind.
**Toolchain:** Python 3.11.15 · `openapi-spec-validator` 0.9.0 · `PyYAML` 6.0.1 · `jsonschema` 4.26.0 · `@mermaid-js/mermaid-cli` 11 (Chromium `chromium-1194`).

> All commands below were run from the repository root and their outputs are reproduced verbatim (trimmed only for length). This report is evidence; it does not rely on any prior completion claim.

---

## 0. Repository integrity

| Check | Command | Result |
|-------|---------|--------|
| Branch | `git rev-parse --abbrev-ref HEAD` | `claude/dilchat-backend-design-e0douc` |
| HEAD | `git rev-parse HEAD` | `9bedde0a…` |
| Default tip | `git rev-parse origin/claude/setup-symbolu-monorepo-…` | `379a6366…` |
| Ahead/behind | `git rev-list --left-right --count <default>...HEAD` | `0  1` (0 behind, 1 ahead) |
| Working tree | `git status --porcelain` | clean |
| Files under `products/dilchat/` | `find … -type f` | **24** |
| Design docs (`docs/*.md`) | | **10** |
| OpenAPI (`docs/openapi/*.yaml`) | | **1** |
| Rule-pack files (`rules/…/*`) | | **12** (11 JSON + 1 README) |

**Production-code scan (expected: none):**

```
$ find products/dilchat -type f \( -name '*.py' -o -name '*.sql' -o -name 'Dockerfile*' \
    -o -name '*.tf' -o -name '*.toml' -o -name '*.cfg' -o -name '*.sh' -o -name '*.ts' \
    -o -name '*.js' -o -name 'alembic*' -o -name '*.service' \) -o -type d -name migrations
NONE FOUND

$ find products/dilchat -type f | sed 's/.*\.//' | sort | uniq -c
     11 json
     12 md
      1 yaml

$ find products/dilchat -type f -perm -u+x
(none)
```

**Verdict — Repository integrity: PASS.** No production source, migrations, ORM models,
executable services, or deployment manifests were added. Only Markdown, JSON, and one
YAML file are present. No executable bits set.

---

## 1. OpenAPI 3.1 specification

```
$ python3 -c "from openapi_spec_validator import validate; \
  from openapi_spec_validator.readers import read_from_filename; \
  spec,_=read_from_filename('docs/openapi/dilchat.openapi.yaml'); validate(spec); \
  print('openapi', spec['openapi'], '| paths', len(spec['paths']), '| schemas', len(spec['components']['schemas']))"
openapi 3.1.0 | paths 34 | schemas 28
OPENAPI: VALID
```

**Verdict: PASS.** `openapi: 3.1.0`, 34 paths, 28 component schemas, validator raised no errors.

---

## 2. YAML syntax + duplicate-key check (OpenAPI)

A strict loader that rejects duplicate mapping keys at every level was used:

```
$ python3 <strict-dup-key loader over dilchat.openapi.yaml>
YAML: parsed OK, no duplicate keys at any level
info.version: 1.0.0
```

**Verdict: PASS.**

---

## 3. JSON rule-pack files — parse + duplicate-key check

```
$ for f in rules/ashtakoota_lahiri_classical_v1/*.json; do json.load(f, object_pairs_hook=<reject-dups>); done
OK   bhakoot.json
OK   exceptions.json
OK   gana_matrix.json
OK   graha_maitri_matrix.json
OK   manifest.json
OK   nadi.json
OK   sources.json
OK   tara.json
OK   varna.json
OK   vashya.json
OK   yoni_matrix.json
```

**Verdict: PASS.** All 11 JSON files parse; no duplicate keys.

---

## 4. Rule-pack internal cross-references & maximum-score consistency

An independent validator (`scripts snapshot in the audit trail`) checked manifest↔component
references, index coverage, distributions, matrix structure, and the score maxima.

### 4.1 Maximum-score consistency (required invariant)

| Koota | Required max | manifest | component file | Match |
|-------|-------------|----------|----------------|-------|
| Varna | 1 | 1 | 1 | ✅ |
| Vashya | 2 | 2 | 2 | ✅ |
| Tara | 3 | 3 | 3 | ✅ |
| Yoni | 4 | 4 | 4 | ✅ |
| Graha Maitri | 5 | 5 | 5 | ✅ |
| Gana | 6 | 6 | 6 | ✅ |
| Bhakoot | 7 | 7 | 7 | ✅ |
| Nadi | 8 | 8 | 8 | ✅ |
| **Total** | **36** | `total_max: 36` = Σ = 36 | | ✅ |

### 4.2 Cross-reference validator output (43 checks, 0 errors)

```
DILCHAT RULE-PACK CROSS-REFERENCE VALIDATION
PASS (43): [selected]
  [OK] manifest component maxima match classical spec (Varna1…Nadi8)
  [OK] total_max == 36 == sum(component maxima)
  [OK] every component file max consistent with manifest (8/8)
  [OK] manifest nakshatras cover 0..26 (27); rashis cover 0..11 (12); names distinct
  [OK] varna rashi_to_varna covers 0..11; distribution 3/3/3/3
  [OK] vashya rashi_to_vashya covers 0..11; group matrix diagonal==2; symmetric
  [OK] tara: 9 taras numbered 1..9; auspicious set == {2,4,6,8,9}
  [OK] gana nakshatra_to_gana covers 0..26; distribution 9/9/9; diagonal==6
  [OK] nadi nakshatra_to_nadi covers 0..26; distribution 9/9/9; scoring 0/8; DEC-021 constraint present
  [OK] bhakoot penalized pairs == {2/12, 5/9, 6/8}
  [OK] graha_maitri lords ⊆ 7 planets; every planet related to other 6; compound endpoints 5..0
  [OK] yoni: 14 yonis; nakshatra_to_yoni covers 0..26
  [OK] exceptions: all 7 rules disabled by default; no_silent_cancellation == true
  [OK] sources: 9/9 citations unverified (draft honesty)
  [OK] manifest draft:true & review_required:true
WARN (1):
  [WARN] yoni compatibility matrix key auto-detection (resolved manually — see 4.3)
ERRORS (0)
RESULT: PASS-WITH-WARNINGS
```

### 4.3 Yoni matrix (manual deep-check, resolving the WARN)

```
matrix index coverage 0..13: True
diagonal all==4: True
symmetric: True
value set: [0, 2, 4]
mortal_enemy_pairs count: 7  → all 7 map to 0 in matrix (7/7)
scale: {4: same, 3: friendly, 2: neutral, 1: unfriendly, 0: mortal enemy}
```

The 14×14 yoni matrix is structurally sound (symmetric, diagonal 4, 7 mortal-enemy pairs = 0).
**Note (domain-completeness, not a structural error):** only values `{0, 2, 4}` are populated —
the friendly(3) and unfriendly(1) gradations are defaulted to neutral(2), exactly as the manifest
and `sources.json` disclose. This is tracked as `BLOCKED_DOMAIN_SOURCE` in the Guna traceability
audit, not a validation failure.

**Verdict — Rule-pack machine consistency: PASS.** Maxima sum to 36; all indices covered; all
matrices structurally valid; no duplicate identifiers; no missing required fields; no exception
enabled by default.

---

## 5. JSON Schema files

There are **no standalone `.json` JSON-Schema files** in the artifact set. JSON Schemas exist as
**embedded fenced blocks** inside `DILCHAT_AI_INTEGRATION_SPEC.md` (per-task input/output schemas,
draft 2020-12) and `DILCHAT_API_SPEC.md`. These are design contracts, not yet standalone files; a
Phase-B action item is to extract them to `schemas/*.schema.json` and add them to CI schema-lint.
**Verdict: PASS (with a tracked extraction action).**

---

## 6. Mermaid diagrams — actual render validation

All fenced `mermaid` blocks were extracted (16 total) and rendered headless with
`@mermaid-js/mermaid-cli` v11 against the pre-installed Chromium.

### 6.1 First pass (found 2 defects)

```
MERMAID RENDER: pass=14 fail=2
FAILED: 04_ARCHITECTURE (sequenceDiagram)  05_ARCHITECTURE (sequenceDiagram)
Parse error: Expecting 'NEWLINE'/arrow tokens, got 'INVALID'
```

**Root cause (isolated by bisection):** a literal **semicolon `;`** inside `sequenceDiagram`
note/message text is interpreted by the Mermaid sequence grammar as a statement separator.
Minimal repro: `Note over A,B: a;b` → parse error; `Note over A,B: a b` → OK. (The semicolons in
blocks 14/15 are legitimate `classDef`/`class` terminators in flowchart syntax and rendered fine.)

### 6.2 Correction applied (documentation-only)

Two lines in `DILCHAT_BACKEND_ARCHITECTURE.md` were edited, replacing the in-text `;` with `—`:

| Block | Before | After |
|-------|--------|-------|
| Pairing seq. | `…returns active;<br/>SHARED…` | `…returns active —<br/>SHARED…` |
| Scorecard seq. | `…score family only; AI may later explain)` | `…score family only — AI may later explain)` |

### 6.3 Re-render (clean)

```
MERMAID RE-RENDER: pass=16 fail=0
ALL 16 MERMAID BLOCKS RENDER CLEANLY
```

**Verdict — Mermaid: PASS** (after 2 corrections). 16/16 render.

---

## 7. Summary

| Artifact class | Checks | Result |
|----------------|--------|--------|
| Repository integrity / no code | file scan, exec-bit scan | **PASS** |
| OpenAPI 3.1 | spec validator | **PASS** (34 paths, 28 schemas) |
| YAML syntax + dup keys | strict loader | **PASS** |
| JSON rule-pack (11) + dup keys | strict loader | **PASS** |
| Rule-pack cross-references | 43 checks | **PASS** (0 errors) |
| Maximum-score consistency | 8 koota + total | **PASS** (Σ = 36) |
| JSON Schema files | presence | **PASS** (embedded; extraction tracked) |
| Mermaid (16 blocks) | headless render | **PASS** (after 2 fixes) |

**Corrections made by this audit:** 2 Mermaid semicolon fixes in
`DILCHAT_BACKEND_ARCHITECTURE.md`. No other machine-readable defects found.

**Overall machine-readable artifact validity: PASS.**
Domain-content correctness of the rule pack is **out of scope for this report** and is assessed in
`DILCHAT_GUNA_RULE_TRACEABILITY_AUDIT.md`.
