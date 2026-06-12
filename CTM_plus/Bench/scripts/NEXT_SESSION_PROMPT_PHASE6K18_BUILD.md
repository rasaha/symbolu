# NEXT SESSION PROMPT — Phase 6K.18 build (chunked prefill for int4_protected)

You are continuing work on int4_protected (the quality-preserving 4-bit
KV-cache backend for vLLM 0.7.3 V0). Be the honest engineer — no rosy
numbers, gate every change. git pull first; commit+push your work.

THE TASK — implement Phase 6K.18 exactly as specified in
CTM_plus/Bench/scripts/PHASE6K18_CHUNKED_PREFILL_DESIGN.md (READ IT
FIRST — locked decisions D1-D4, all touch points with line refs, the
probe-first requirement, and the gate checklist). One-paragraph summary:

- Enable vLLM V0 chunked prefill behind the factory:
  `Int4ProtectedLLM(enable_chunked_prefill=True)` becomes supported;
  DEFAULT STAYS False (no behavior change for existing deploys).
- The only new math is D1: chunk 2+'s context rebuild handles
  non-block-aligned ctx_len — full blocks via the existing dequant
  (incl. 6N prot-int8), the trailing ctx_len % 32 K rows spliced EXACT
  from that sequence's staging buffer (V/protect tail rows are already
  per-token in the sidecars). Identity = the 6K.16c rid stash (C-ID
  contract extended: refuse loudly without it).
- The write path is expected to need ZERO changes (staging already spans
  write() calls) — verify, don't assume.

ORDER OF WORK (from the design doc):
1. PROBES FIRST (pod, ~30 min): P1 confirms the gap empirically on
   current code; P2 bounds the PRIZE on stock bf16 (does chunking
   restore util 0.85 at 100K?). If P2 says no — STOP and re-scope; do
   not build on an unmeasured prize.
2. Build D1-D3 (touch-point table in the design doc).
3. CPU tests: tail-splice selftest section in phase6k16_prefix_prefill
   + keep every existing 6K.17 default-off guard test passing verbatim.
4. Pod gates 1-6 from the design doc, in order. Gate 2 (S1-chunked
   byte-gate: finalized blocks byte-identical monolithic vs chunked) is
   the machinery gate — if it is red, the build is wrong, full stop.

POD REALITIES: read CTM_plus/Bench/scripts/NEXT_POD_SESSION_INT4_GPU_RUNS.md
(preamble, venv/import check, PROTECT_MASK_PATH; artifacts for
Llama/Qwen/Mistral are per-pod — recalibrate if absent, it is cheap and
deterministic). Known traps already documented there: 6k12 needs
--model AND --protect-mask; the savings probe runs eager/capped;
sidecars live OUTSIDE gpu_memory_utilization.

RULES: factory default for chunked prefill stays OFF until every gate
passes; if any gate fails, fix or revert — never ship red; measure
before claiming; a win on corrupted output never counts. Don't put the
model id in commits/docs. Update the 6K.18 design-doc status + the
ledger (NEXT_POD_SESSION_INT4_GPU_RUNS.md) + the VC brief/DESIGN
long-context paragraphs ONLY after gates pass — and only with the
measured numbers (P2/gate-4 peak-memory + util numbers are the
headline; TTFT-fairness numbers from gate 5 are secondary).

CONTEXT BANKED LAST SESSION (Phase 6N, all gates green, for orientation):
prot-int8 shipped behind INT4_PROTECTED_PROT_INT8 (default OFF) —
sidecars -0.953/-0.991/-1.015 GiB byte-exact on Llama/Qwen/Mistral,
demo 1.78x net, greedy 18/18 bit-identical, S1 13/13, 6k12 protected ==
bf16 both flag states. 6K.18 interacts with it only at the gate level
(one chunked+prot-int8 cell required).
