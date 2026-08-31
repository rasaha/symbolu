#!/bin/bash
# Self-healing driver: relaunch the resumable diagnosis batch until the final verdict artifact
# exists. Protects against silent process death/preemption (each relaunch resumes from results/_progress).
cd /home/user/symbolu/experiments/bindingslots_value_path_diagnosis || exit 2
for i in $(seq 1 40); do
  if [ -f results/aggregate_conclusion.json ]; then
    echo "AGGREGATE PRESENT at attempt $i $(date +%H:%M:%S) - done"
    exit 0
  fi
  echo "=== launch attempt $i $(date +%H:%M:%S) ==="
  python3 run_diagnosis.py
  if [ -f results/aggregate_conclusion.json ]; then
    echo "AGGREGATE PRESENT after attempt $i $(date +%H:%M:%S) - done"
    exit 0
  fi
  echo "=== run_diagnosis exited WITHOUT aggregate; resuming in 5s (attempt $i) ==="
  sleep 5
done
echo "WRAPPER GAVE UP after 40 attempts $(date +%H:%M:%S)"
exit 1
