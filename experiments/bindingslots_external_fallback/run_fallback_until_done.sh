#!/bin/bash
# Self-healing driver: run calibration + B0 reproduction + M0/T0/F1/V0 evaluation until the terminal
# verdict artifact exists. Resumes from results/_progress/ on any silent process death.
cd /home/user/symbolu/experiments/bindingslots_external_fallback || exit 2
for i in $(seq 1 60); do
  if [ -f results/aggregate_verdict.json ]; then echo "VERDICT PRESENT $(date +%H:%M:%S)"; exit 0; fi
  echo "=== attempt $i $(date +%H:%M:%S) ==="
  python3 run_fallback.py
  if [ -f results/aggregate_verdict.json ]; then echo "VERDICT PRESENT $(date +%H:%M:%S)"; exit 0; fi
  echo "=== exited without verdict; resuming in 5s ($i) ==="
  sleep 5
done
echo "WRAPPER GAVE UP $(date +%H:%M:%S)"; exit 1
