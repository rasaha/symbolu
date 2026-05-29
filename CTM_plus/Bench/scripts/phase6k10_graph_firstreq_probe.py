#!/usr/bin/env python3
# Phase 6K.10 — localize the CUDA-graph FIRST-REQUEST collapse (protected).
#
# 6K.9 (post eager-fix) matrix: protected eager = 0.0 (fixed), but protected
# GRAPH = 0.6 with A_1st=0, h1=0.8 -> h2=0.4 (FRONT-LOADED, self-heals),
# accum=False. So it's a capture-time init bug, NOT the stale-state one.
#
# Leading hypothesis: vLLM captures decode graphs at init with SYNTHETIC inputs
# (block_tables=0 -> seq_id=0 -> slot 0 consumed by a phantom SeqState). That
# synthetic state lingers in the writer pools after capture; the first real
# decodes read the residue until real data overwrites it (front-loaded +
# self-healing). My prefill evict_sequence fix can't undo it because the
# phantom seq_id is never the one being prefilled.
#
# Discriminating test (one process, graph mode, protected, fix ON):
#   * dump the writer pool state right AFTER load (capture done) — synthetic
#     residue should be visible (slot 0 allocated / nonzero seq_pos).
#   * POSTCAP_RESET=1 -> do ONE full writer reset (clear SeqStates, restore all
#     free slots, zero pools) BEFORE the first real request; POSTCAP_RESET=0 ->
#     baseline. Run the same prompts, log per-request collapse.
#   * also count how often _sync_pool_counters_from_states fires (sentinel).
#
# Interpretation:
#   POSTCAP_RESET=1 first-request collapse << POSTCAP_RESET=0  -> FIX = reset
#     writer state once after capture (synthetic-residue leak). Cheap, safe.
#   No difference -> the captured GRAPH itself is state-poisoned; pool resets
#     can't help (would need re-capture with clean state / state-independent
#     capture) -> recommend eager for int4 until that's addressed.
#
# Usage (run BOTH and compare the first few requests):
#   POSTCAP_RESET=0 python CTM_plus/Bench/scripts/phase6k10_graph_firstreq_probe.py
#   POSTCAP_RESET=1 python CTM_plus/Bench/scripts/phase6k10_graph_firstreq_probe.py

import os

os.environ.setdefault("PHASE6E_FUSED_WRITER", "1")
os.environ.pop("PHASE6B3_FORCE_EAGER", None)   # we WANT graph mode here

PROMPTS = [
    "List three primary colors and their names.",
    "What is the capital of France? Answer in one sentence.",
    "In one sentence, explain what photosynthesis is and why it matters.",
    "Give me a one-line definition of machine learning in plain English.",
    "Summarize the water cycle in one short sentence for a child.",
    "Who wrote Romeo and Juliet? Answer in one sentence.",
    "Explain gravity in one simple sentence.",
    "Write a one-sentence description of the ocean.",
]


def _collapsed(text):
    w = text.split()
    if len(w) < 6:
        return False
    longest = cur = 1
    for a, b in zip(w, w[1:]):
        cur = cur + 1 if a == b else 1
        longest = max(longest, cur)
    return len(set(w)) / len(w) < 0.4 or longest >= 4 or max(w.count(x) for x in set(w)) >= 6


def _locate_writers(llm):
    writers = {}
    try:
        model = llm.llm_engine.model_executor.driver_worker.model_runner.model
    except Exception:
        return writers
    for mod in model.modules():
        impl = getattr(getattr(mod, "attn", None), "impl", None) or getattr(mod, "impl", None)
        if impl is None or type(impl).__name__ != "Int4ProtectedAttentionImpl":
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is not None and getattr(w, "_allocated", False):
            writers.setdefault(getattr(w, "layer_idx", len(writers)), w)
    return writers


def _pool_dump(writers, label):
    if not writers:
        print(f"  [{label}] (no writers located)")
        return
    w = writers[min(writers)]
    import torch  # noqa
    bid = w._k_stage_block_id_pool
    print(f"  [{label}] layer0: active_slots={int((bid != -1).sum()) if bid is not None else -1} "
          f"max_seq_pos={int(w._seq_pos_pool.max()) if w._seq_pos_pool is not None else -1} "
          f"max_count={int(w._k_stage_count_pool.max()) if w._k_stage_count_pool is not None else -1} "
          f"seq_states={len(getattr(w, '_seq_states', {}))} "
          f"free_slots={len(getattr(w, '_free_slots', []))}")


def _full_reset(writers):
    import torch
    n = 0
    for w in writers.values():
        try:
            w._seq_states.clear()
            if hasattr(w, "_slot_map"):
                w._slot_map.clear()
            if hasattr(w, "_free_slots"):
                w._free_slots = list(range(getattr(w, "_max_active_slots", 8)))
            with torch.inference_mode():
                if w._seq_pos_pool is not None:
                    w._seq_pos_pool.zero_()
                if w._k_stage_count_pool is not None:
                    w._k_stage_count_pool.zero_()
                if w._k_stage_block_id_pool is not None:
                    w._k_stage_block_id_pool.fill_(-1)
                if w._k_stage_pool is not None:
                    w._k_stage_pool.zero_()
            n += 1
        except Exception as e:
            print(f"  reset warn (layer {getattr(w,'layer_idx','?')}): {type(e).__name__}: {e}")
    return n


SYNC_FIRES = {"n": 0}


def _instrument_sync():
    try:
        from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
        orig = PagedKVWriter._sync_pool_counters_from_states

        def wrapped(self, slot_idx_list):
            SYNC_FIRES["n"] += 1
            return orig(self, slot_idx_list)
        PagedKVWriter._sync_pool_counters_from_states = wrapped
    except Exception as e:
        print(f"[6k10] could not instrument sync: {e}")


def main():
    postcap_reset = os.environ.get("POSTCAP_RESET", "0").strip() in ("1", "true", "yes")
    _instrument_sync()
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    print(f"\n[6k10] GRAPH mode, protected, fix ON, POSTCAP_RESET={postcap_reset}", flush=True)
    llm = Int4ProtectedLLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=8192,
        gpu_memory_utilization=0.5, max_num_seqs=8, enforce_eager=False,
    )
    sp = SamplingParams(temperature=0.0, max_tokens=24)

    writers = _locate_writers(llm)
    print(f"\n[6k10] writers located: {len(writers)}  (sync fired {SYNC_FIRES['n']}x during capture)")
    _pool_dump(writers, "AFTER-CAPTURE")

    if postcap_reset:
        nreset = _full_reset(writers)
        print(f"[6k10] POST-CAPTURE full reset applied to {nreset} writers")
        _pool_dump(writers, "AFTER-RESET")

    print("\n--- requests (watch req#0..2; collapse there = first-request bug) ---")
    n_collapse = 0
    for i, p in enumerate(PROMPTS):
        before = SYNC_FIRES["n"]
        out = llm.generate([p], sp)[0]
        text = out.outputs[0].text
        c = _collapsed(text)
        n_collapse += c
        print(f"  req#{i} N={len(out.prompt_token_ids):>3} sync+{SYNC_FIRES['n']-before} "
              f"[{'COLLAPSE' if c else 'ok':8s}] {text[:62]!r}", flush=True)

    print(f"\n[6k10] POSTCAP_RESET={postcap_reset}  collapse={n_collapse}/{len(PROMPTS)}  "
          f"first-req collapsed={_collapsed(llm.generate([PROMPTS[0]], sp)[0].outputs[0].text)}")
    print("  Compare POSTCAP_RESET=0 vs =1 on req#0..2:")
    print("   * reset kills the early collapse  -> FIX = reset writer pools once after capture.")
    print("   * no change                       -> captured graph is state-poisoned (harder; prefer eager).\n", flush=True)


if __name__ == "__main__":
    main()
