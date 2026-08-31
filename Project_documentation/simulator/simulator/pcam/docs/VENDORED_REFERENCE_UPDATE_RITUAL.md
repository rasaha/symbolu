# Vendored CTM+ Reference — Update Ritual

**Scope:** `simulator/pcam/reference/attention_evictor_vendored.py`
**Contract:** [`ADR-0001`](../../../../repository/docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Phase:** 0 — Conformance foundation

---

## What the vendored file is

`simulator/pcam/reference/attention_evictor_vendored.py` is an in-tree,
read-only copy of the canonical CTM+ KV-cache eviction reference at
`CTM_plus/KVPolicy/kv_policy/attention_evictor.py`.

It is a **specification reference**, not the runtime policy. The
runtime policy is `simulator/pcam/kv_policy.py::KVCachePolicy`, which
is a bit-parity port of the vendored file.

The vendored file exists so that:

1. `simulator.pcam` is importable without `CTM_plus/KVPolicy` on
   `sys.path`. End users who `pip install` the PCAM package do not
   need to clone or install the upstream CTM+ repository.
2. The PCAM parity harness has a stable, release-safe oracle that
   does not drift silently when upstream changes.
3. The PCAM package can be versioned independently and pinned against
   a specific upstream commit.

## When to run the ritual

Run the ritual whenever **any** of the following happens upstream at
`CTM_plus/KVPolicy/kv_policy/attention_evictor.py`:

- A change to `FrequencySketch` (seeds, depth, width formula, counter
  saturation, halving trigger or semantics, hash function).
- A change to `KVCachePolicy` scoring (`score_block`, `select_victims`,
  `PHASE_WEIGHTS`, the entity bonus, the filler fast path, the
  sampled-path RNG contract).
- A change to the classification helpers (`classify_block_importance`,
  `compute_adaptive_threshold`).
- Any new field on `BlockState`, `SequenceState`, or `PhaseWeights`.
- A rename or removal of a public symbol that PCAM's parity harness
  or runtime policy consumes (`FrequencySketch`, `KVCachePolicy`,
  `InferencePhase`, `PositionClass`).

Do **not** run the ritual for upstream changes that do not affect
behavior or the public symbol surface (docstring edits, type-hint
cleanups, unrelated helpers, formatting).

## The ritual

Six steps. Do them in order. Do not skip any.

### 1. Identify the upstream commit

```bash
git log -1 --format='%H %ai' -- CTM_plus/KVPolicy/kv_policy/attention_evictor.py
```

Copy the full 40-character commit hash and the ISO date.

### 2. Replace the vendored file

```bash
cp CTM_plus/KVPolicy/kv_policy/attention_evictor.py \
   simulator/pcam/reference/attention_evictor_vendored.py
```

### 3. Re-apply the vendoring header

The `cp` in step 2 overwrites the header. Open
`simulator/pcam/reference/attention_evictor_vendored.py` and re-apply
the `VENDORED CTM+ KV-Cache Eviction Reference — DO NOT EDIT FOR
BEHAVIOR` docstring block at the top, updating:

- **Pinned commit:** paste the hash from step 1
- **Pinned date:** paste the date from step 1

The rest of the header is invariant. The original upstream docstring
follows the header block and is preserved verbatim.

### 4. Run the parity harness

```bash
python -m pytest simulator/pcam/tests/test_sketch_conformance.py \
                 simulator/pcam/tests/test_attention_evictor_parity.py -q
```

**Expected:** `20 passed, 0 failed, 0 skipped`.

### 5. Interpret the result

- **If the harness is green:** the upstream change is compatible with
  the PCAM port. No runtime code change is needed. Commit the
  vendored file and the header update, bump the PCAM patch version
  (e.g. `0.3.0 → 0.3.1`) in whatever version file the package uses,
  and ship.

- **If the harness is red:** the upstream change is a real behavioral
  diff against the PCAM runtime port. **Do not modify the tests to
  make them pass.** Instead:
    1. Read the failing assertion — it tells you which invariant
       broke (sketch saturation, halving, scoring, victim ordering).
    2. Update `simulator/pcam/kv_policy.py::KVCachePolicy` (the
       runtime port) to match the vendored reference's new behavior.
    3. Re-run the harness. Expect 20 passed.
    4. If the upstream change is large enough to require an ADR
       amendment (e.g. a new scoring signal, a changed weight table,
       reintroduction of a dropped term), write the amendment before
       merging.

- **If the harness fails to import:** the upstream change renamed or
  removed a public symbol. Update the runtime `kv_policy.py`
  re-exports and the test imports together, then re-run.

### 6. Commit and record

One commit for the vendoring bump:

```
kv_policy: bump vendored CTM+ reference to <short-hash>

Upstream commit: <full hash>
Upstream date:   <ISO date>
Behavioral diff: <none | describe>

Parity harness: 20 passed, 0 failed, 0 skipped.
```

If any runtime changes were required, include them in the same commit
(so the vendored bump and the runtime port always land together) or
in a follow-up commit on the same branch.

## What not to do

- **Do not edit the vendored file's behavior.** It is read-only
  modulo the header and whitespace required to fit the header.
- **Do not skip the header update.** The pinned commit hash is how
  future maintainers know what upstream state the port is matched
  against.
- **Do not weaken parity tests to make the harness green.** The
  harness exists to detect drift; defeating it defeats the purpose
  of vendoring.
- **Do not introduce a runtime dependency on `CTM_plus`.** The
  whole point of Phase 0 is that `simulator.pcam` imports only from
  its own package tree.
- **Do not vendor partial files.** Always copy the full upstream
  module. Partial vendoring creates subtle incompatibilities when
  upstream adds cross-references between symbols.

## Quick reference

| Command | Purpose |
|---|---|
| `git log -1 --format='%H %ai' -- CTM_plus/KVPolicy/kv_policy/attention_evictor.py` | Find pinned commit |
| `cp CTM_plus/KVPolicy/kv_policy/attention_evictor.py simulator/pcam/reference/attention_evictor_vendored.py` | Replace vendored file |
| `pytest simulator/pcam/tests/test_sketch_conformance.py simulator/pcam/tests/test_attention_evictor_parity.py -q` | Run parity harness |
| `grep -n "Pinned commit" simulator/pcam/reference/attention_evictor_vendored.py` | Check current pinned state |
