#!/usr/bin/env bash
# Self-healing driver: relaunch the resumable V100 characterization until the terminal verdict artifact
# exists. The container can silently restart/preempt during the ~4h CPU reproduction; per-seed progress
# under results/_progress lets each relaunch resume where it left off.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
VERDICT="$HERE/results/aggregate_verdict.json"
LOG="$HERE/results/_progress/run.log"
mkdir -p "$HERE/results/_progress"

for attempt in $(seq 1 200); do
  if [ -f "$VERDICT" ]; then
    echo "[wrapper] verdict present; done." | tee -a "$LOG"
    exit 0
  fi
  echo "[wrapper] attempt $attempt starting $(date -u +%FT%TZ)" | tee -a "$LOG"
  OMP_NUM_THREADS=4 python3 "$HERE/run_v100.py" >>"$LOG" 2>&1
  rc=$?
  echo "[wrapper] python exited rc=$rc" | tee -a "$LOG"
  if [ -f "$VERDICT" ]; then
    echo "[wrapper] verdict present after attempt $attempt; done." | tee -a "$LOG"
    exit 0
  fi
  sleep 3
done
echo "[wrapper] exhausted attempts without verdict" | tee -a "$LOG"
exit 1
