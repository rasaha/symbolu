#!/usr/bin/env bash
# 04 — KVPro WarmTier validation.
#   1. byte-clean gate (snapshot->restore on the live writer)  [MEASURED PASS/FAIL — must pass first]
#   2. storage systems: bytes/token, encode/reload time, p50/p95 [MEASURED]
#   3. serve-over-restored-KV + cold-vs-reuse TTFT + p95/p99     [needs the serving hook]
#      If the serving hook is incomplete -> FAIL LOUDLY + print the EXACT missing point.
# The byte-gate + storage measure are prefill-only (no int4 decode fork needed); serving needs it.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

RUN="$(kvpro_run_dir)"; SUM="$RUN/SUMMARY_warmtier.md"
VERIFY="$REPO/scripts/verify_kvpro_snapshot_roundtrip.py"
MEASURE="$REPO/scripts/measure_kvpro_warmtier_snapshot.py"
MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"

# Lite gate: byte-gate + storage measure need a GPU + a mask, but NOT the decode fork.
if [[ "$(gpu_count)" -lt 1 ]]; then fail "no GPU — WarmTier byte-gate/storage need a CUDA GPU."; exit 2; fi
if ! mask_path_ok; then print_mask_howto "$MODEL" "/workspace/dev/build-logs/protect_mask.pt"; exit 2; fi

{ echo "# KVPro WarmTier validation (MEASURED this run)"; echo "- run dir: $RUN"; echo "- date(UTC): $(date -u)"; echo; } >"$SUM"

section "1) Byte-clean gate (verify_kvpro_snapshot_roundtrip)"
if run_step "snapshot/restore byte-gate" "$RUN/warmtier_bytegate.log" python3 "$VERIFY" --model "$MODEL"; then
  if grep -q "Phase-0 gate cleared" "$RUN/warmtier_bytegate.log"; then
    ok "BYTE-CLEAN GATE: PASS (MEASURED)"; echo "- **byte-gate: PASS (MEASURED)**" >>"$SUM"; GATE_OK=1
  else
    warn "verify exited 0 but PASS marker not found — treat as inconclusive."; echo "- byte-gate: INCONCLUSIVE (see log)" >>"$SUM"; GATE_OK=0
  fi
else
  fail "BYTE-CLEAN GATE: FAIL — do NOT trust WarmTier reuse. Stopping."
  echo "- **byte-gate: FAIL (MEASURED)** — see warmtier_bytegate.log" >>"$SUM"
  exit 1
fi

section "2) Storage systems (bytes/token, encode/reload, p50/p95)"
run_step "warmtier storage measure" "$RUN/warmtier_storage.log" \
    python3 "$MEASURE" --model "$MODEL" --out "$RUN/warmtier_systems.json" || true
python3 - "$RUN/warmtier_systems.json" "$SUM" <<'PY' || true
import json, sys, os
js, sumf = sys.argv[1:3]
with open(sumf,"a") as f:
    f.write("\n## storage systems (MEASURED)\n")
    if not os.path.exists(js):
        f.write("- NO systems JSON produced (see warmtier_storage.log).\n"); raise SystemExit
    d=json.load(open(js))
    for k in ("all_clean","bytes_per_token","bytes_per_block","encode_MBps","reload_MBps",
              "reload_s_per_1k_tokens","reload_s_p50","reload_s_p95"):
        if k in d: f.write(f"- {k} = **{d[k]}**  (MEASURED)\n")
    f.write(f"- {d.get('quality_note','')}\n")
print("storage parsed OK")
PY

section "3) Serve-over-restored-KV + cold-vs-reuse TTFT + p95/p99 under concurrency"
# These require BOTH the int4 decode fork AND the serving hook to be wired.
SERVING_BUILT="$(python3 - <<'PY'
import sys
sys.path.insert(0, "CTM_plus/KVPolicy")
try:
    from kv_policy import tier5c_warmtier_serving as t5c
    try:
        t5c.serve_with_warmtier_reuse()      # raises NotImplementedError while pod-only
        print("BUILT")                       # (only if someone wired it to accept no-arg probe)
    except NotImplementedError:
        print("NOT_BUILT")
    except TypeError:
        print("BUILT")                       # implemented (needs real args) -> a driver exists
except Exception as e:
    print(f"IMPORT_FAIL:{e}")
PY
)"
if [[ "$SERVING_BUILT" == "NOT_BUILT" ]]; then
  fail "SERVING HOOK INCOMPLETE — serve-over-restored-KV is not built. NOT measuring TTFT/p99 (no fake numbers)."
  fail "EXACT missing integration point:"
  echo  "    File : CTM_plus/KVPolicy/kv_policy/tier5c_warmtier_serving.py"
  echo  "    (a) mark_prefix_computed(seq_group, num_computed_tokens):"
  echo  "        wire to the live vLLM V0 scheduler so the restored prefix counts as"
  echo  "        'already computed' (SequenceData.update_num_computed_tokens) and decode"
  echo  "        proceeds over restored KV instead of recomputing the prefix."
  echo  "    (b) serve_with_warmtier_reuse(...): compose"
  echo  "        plan_reuse -> restore_prefix_into_blocks -> mark_prefix_computed -> generate,"
  echo  "        using the int4 decode kernel (flash_attn_with_int4_kvcache)."
  echo  "    Gate : this 04 byte-gate (above) must PASS first; then measure cold vs reuse"
  echo  "           TTFT and p95/p99 under concurrency in a driver alongside this harness."
  {
    echo
    echo "## serving (INCOMPLETE — NOT MEASURED)"
    echo "- serve-over-restored-KV hook not built; TTFT-vs-cold / p95 / p99 NOT measured (no fabrication)."
    echo "- integration point: tier5c_warmtier_serving.py mark_prefix_computed + serve_with_warmtier_reuse (see stderr)."
  } >>"$SUM"
elif [[ "$SERVING_BUILT" == BUILT* ]]; then
  if ! have_int4_kernel; then
    fail "serving hook present but int4 decode fork missing — build it before serving (see 00)."
  else
    warn "serving hook appears BUILT — run your serving driver to MEASURE cold-vs-reuse TTFT + p95/p99."
    note "This harness does not ship a serving driver; add it and record results into $RUN."
  fi
  echo "## serving: hook reported BUILT — measure via your serving driver (not shipped here)." >>"$SUM"
else
  fail "could not probe serving hook: $SERVING_BUILT"
fi

section "WarmTier validation complete"
ok "Summary: $SUM"
note "bytes/token, reload p50/p95, byte-gate = MEASURED. Serving TTFT/p99 only if the hook is built."
