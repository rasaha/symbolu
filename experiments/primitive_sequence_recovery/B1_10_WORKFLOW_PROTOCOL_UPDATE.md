# B1.10 — Workflow Protocol Update: single final evidence freeze (docs-only)

**Authoritative statement of the B1.10 evidence-freeze workflow. Supersedes the "freeze every context version before
the packet-aware audit" language in the earlier B1.10 docs (see §5).** Documentation-only: the experimental design,
packets, contexts, judges, and experiment numbering are unchanged. Resonance / phonetic-fidelity refinement only —
**no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege claim.** B1.4b′
remains `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

---

## 1. The change

The B1.10 **context files are development artifacts**. They are version-controlled by Git but are **not individually
evidence-frozen**. Intermediate context versions (v2, v3, …) remain ordinary, editable repository files under normal
Git history.

**Old workflow (retired):** generate → **freeze contexts** → packet audit → judges.

**New workflow (in force):**
```
generate
  → surface validation
  → packet-aware audit               (performed directly on the current Git-tracked development context file)
  → regenerate if necessary          (only the failing word-pair, via a fresh packet-naive author)
  → repeat until all items approved
  → real judge run
  → freeze ONE final evidence package
```

## 2. Rationale

- B1.10 is still an evolving experimental design.
- Intermediate context versions should stay editable through normal Git history.
- We do not want multiple evidence freezes for development iterations.
- Only the evidence supporting the **final reported experiment** should become immutable.

## 3. Operational rules

1. **No per-version context freeze.** There is no requirement to freeze an accepted context set before the
   packet-aware audit. Do not create per-version evidence-freeze artifacts for v2 / v3 / … context sets.
2. **Audit on the live file.** The packet-aware audit (context-independence → Tier-3 echo → Tier-1/Tier-2 fairness →
   word decisions) is performed **directly on the current Git-tracked development context file**.
3. **Per-word regenerate loop.** If a word fails:
   - regenerate **only that word-pair** — via a **fresh packet-naive author** (never a packet-aware edit of the
     sentence),
   - update the development file (ordinary Git commit),
   - re-run the packet-aware audit,
   - continue until **all** items pass.
4. **Single final evidence freeze.** Only **after** all items pass, the context set is approved, the official judges
   complete the real run, and statistics are computed, create **exactly one** evidence package (§4). Development
   versions are never individually frozen.

## 4. The one final evidence package

Created once, after the real run + statistics. It is the immutable record supporting the published result and
contains:
- the **final context file actually used**,
- **Tier-1** packets, **Tier-2** packets, **Tier-3** packets,
- the **control hierarchy**,
- the **judge-panel specification**,
- the **prompts**,
- the **seeds**,
- **provenance** (context-author identity + blindness attestation; model IDs/revisions; generation settings),
- **raw judge outputs**,
- **parsed scores**,
- **computed statistics**,
- **sha256 hashes of every artifact** above,
- the **final report**.

The evidence-freeze **declaration** that gates the real judge run (the runner still refuses a real run without one —
anti-circularity) is created **once**, for the final approved inputs, immediately before judging, and is **part of
this single package** — it is not a per-context-version freeze. Its pinned input hashes are what make the results
attributable to exactly the approved inputs (no post-hoc input swap).

## 5. What this supersedes (documentation reconciliation)

The following sections are updated to the single-final-freeze model (edited in place; the guardrails they carried are
preserved):
- `B1_10_INDEPENDENT_CONTEXT_GENERATION_PROTOCOL.md` §6 (was "Freeze procedure BEFORE any packet comparison"), §7
  (review "ONLY after freeze"), §8 (echo handling "Repeat the freeze").
- `B1_10_NONCLAUDE_AUTHOR_HANDOFF.md` §6 ("Freeze BEFORE any packet-aware audit"), §7.
- `B1_10_CONTEXTS_V2_INTAKE_VERIFICATION.md` §5 ("freeze it before any packet comparison").
- `B1_10_OFFICIAL_JUDGE_PANEL_SPEC.md` §8 (pre-run evidence-freeze note).

Where those docs previously said "freeze the context set, then audit," they now say "audit the Git-tracked
development file directly; regenerate failing word-pairs via a fresh blind author; a single evidence freeze is
created only at the end."

## 6. Guardrails preserved (unchanged)

The freeze-model change does **not** relax any scientific guardrail:
- **Blind authoring** — official contexts authored by a packet-naive party (non-Claude; disjoint from the Tier-3
  paraphrase author and the Llama/Gemma judge panel), given only the author packet.
- **Packet-aware audit** — still mandatory (context-independence, Tier-3 echo, Tier-1/Tier-2 fairness); now run on
  the live development file.
- **No post-hoc packet editing; no context tailoring** — packets are never edited to fit results; a context that
  fails the echo audit is **regenerated by a fresh blind author**, never edited by a packet-aware party.
- **Independent judges** — the frozen J0/J1/J2 Llama/Gemma panel; same panel for all three tiers; no Claude judge.
- **Provenance & reproducibility** — author identity + blindness attestation, model IDs/revisions, generation
  settings, prompts, seeds, and per-artifact hashes are all captured in the single final package.
- **Anti-circularity** — the run-gating evidence-freeze declaration still pins the exact approved inputs *before*
  judging; results are interpreted only against those pinned inputs.

## 7. Unchanged

Experimental design, Tier-1/Tier-2/Tier-3 packets, contexts, judge panel, and experiment numbering are **not**
changed by this update. This is a documentation-only protocol change to the freeze workflow.

## 8. Guardrails
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth /
ontology / Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**
