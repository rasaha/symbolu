#!/bin/bash
# Self-healing driver: run the §7 rank audit (once), then the resumable execution until the terminal
# verdict artifact exists. Survives silent process death (each relaunch resumes from results/_progress).
cd /home/user/symbolu/experiments/bindingslots_address_generalization || exit 2
if [ ! -f results/pre_intervention_rank_audit.json ]; then
  echo "=== rank audit $(date +%H:%M:%S) ==="
  python3 pre_intervention_rank_audit.py
fi
for i in $(seq 1 60); do
  if [ -f results/aggregate_verdict.json ]; then echo "VERDICT PRESENT $(date +%H:%M:%S)"; exit 0; fi
  echo "=== execution attempt $i $(date +%H:%M:%S) ==="
  python3 run_ag_execution.py
  if [ -f results/aggregate_verdict.json ]; then echo "VERDICT PRESENT $(date +%H:%M:%S)"; exit 0; fi
  echo "=== execution exited without verdict; resuming in 5s ($i) ==="
  sleep 5
done
echo "WRAPPER GAVE UP $(date +%H:%M:%S)"; exit 1
