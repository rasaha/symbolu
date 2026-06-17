#!/usr/bin/env bash
# Run ONE live-shadow experiment: inject the matching chaos, drive the matching
# load profile, and run the READ-ONLY controller in shadow for the duration,
# capturing the proof-of-value report.
#
#   bash run_experiment.sh <scenario>
#
# <scenario> is one of the synthetic scenarios that has a real equivalent, e.g.
# sudden_10x_spike, conflicting_signals, cascading_failure, spot_interruption,
# noisy_spikes, feedback_delay_loop, gradual_drift, partial_recovery,
# cold_start_amplification, coherence_oscillation, budget_cap.
#
# Assumes bring_up.sh has run and port-forwards are active:
#   PROM_URL (default http://localhost:9090), FRONTEND_URL (default http://localhost:8080)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SCENARIO="${1:-sudden_10x_spike}"
PROM_URL="${PROM_URL:-http://localhost:9090}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8080}"
CYCLES="${CYCLES:-240}"
OUT="$ROOT/artifacts/cloud_controller_real_validation"
mkdir -p "$OUT"

# Map scenario → chaos manifest (load shapes have no chaos; config scenarios use HPA/config).
declare -A CHAOS=(
  [noisy_spikes]="$HERE/chaos/02_noisy_spikes_cpu_stress.yaml"
  [conflicting_signals]="$HERE/chaos/03_07_upstream_latency.yaml"
  [cascading_failure]="$HERE/chaos/03_07_upstream_latency.yaml"
  [spot_interruption]="$HERE/chaos/08_spot_interruption_podkill.yaml"
  [feedback_delay_loop]="$HERE/chaos/16_feedback_delay_netem.yaml"
)
CHAOS_FILE="${CHAOS[$SCENARIO]:-}"

cleanup() {
  [ -n "$CHAOS_FILE" ] && kubectl delete -f "$CHAOS_FILE" --ignore-not-found >/dev/null 2>&1 || true
  [ -n "${K6_PID:-}" ] && kill "$K6_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> scenario=$SCENARIO  prom=$PROM_URL  cycles=$CYCLES"
if [ -n "$CHAOS_FILE" ]; then
  echo "==> injecting chaos: $(basename "$CHAOS_FILE")"
  kubectl apply -f "$CHAOS_FILE"
fi

if command -v k6 >/dev/null 2>&1; then
  echo "==> driving load profile '$SCENARIO' with k6 (RED metrics → Prometheus remote-write)"
  K6_PROMETHEUS_RW_SERVER_URL="${PROM_URL}/api/v1/write" \
    k6 run -o experimental-prometheus-rw \
      -e BASE_URL="$FRONTEND_URL" -e PROFILE="$SCENARIO" "$HERE/k6-load.js" &
  K6_PID=$!
else
  echo "WARN: k6 not installed — drive load yourself; running shadow on ambient traffic"
fi

echo "==> running READ-ONLY live shadow for $CYCLES cycles"
python "$ROOT/scripts/run_live_shadow.py" \
  --prometheus-url "$PROM_URL" \
  --namespace boutique --deployment frontend \
  --max-cycles "$CYCLES" --poll-interval 15 \
  --period-label "live-shadow: $SCENARIO" \
  --out-dir "$OUT"

echo "==> report written under $OUT (track_a_live_shadow.{md,json})"
