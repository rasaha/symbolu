#!/usr/bin/env bash
# Stand up the full live-shadow stack on a local kind cluster.
# Reproducible from a Docker host. ~10-15 min on first run (image pulls).
#
# Prereqs (the script checks): docker, kind, kubectl, helm.
# Optional: k6 (for load), the controller deps (pip install -r requirements-controller.txt).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

need() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING: $1 — install it first"; exit 1; }; }
need docker; need kind; need kubectl; need helm

echo "==> [1/5] kind cluster"
kind get clusters 2>/dev/null | grep -qx ncc-shadow || kind create cluster --config "$HERE/kind-cluster.yaml"

echo "==> [2/5] kube-prometheus-stack (Prometheus + node-exporter + kube-state-metrics)"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set prometheus.prometheusSpec.enableRemoteWriteReceiver=true \
  --set prometheus.prometheusSpec.maximumStartupDurationSeconds=300 \
  --wait --timeout 8m

echo "==> [3/5] Online Boutique (real multi-service app with genuine gRPC deps)"
kubectl create namespace boutique --dry-run=client -o yaml | kubectl apply -f -
# Upstream release manifest (11 microservices). For the lighter subset, see README.
kubectl -n boutique apply -f \
  https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml
# A real HPA on the frontend so there is a genuine autoscaler to shadow.
kubectl -n boutique apply -f "$HERE/frontend-hpa.yaml"

echo "==> [4/5] Chaos Mesh (fault injection)"
helm repo add chaos-mesh https://charts.chaos-mesh.org >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --wait --timeout 6m

echo "==> [5/5] wait for Boutique to be ready"
kubectl -n boutique rollout status deploy/frontend --timeout=5m

cat <<EOF

Stack is up. Next:
  # 1. expose Prometheus + frontend
  kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090 &
  kubectl -n boutique   port-forward svc/frontend 8080:80 &

  # 2. run one experiment (chaos + load + read-only shadow), e.g.:
  bash $HERE/run_experiment.sh sudden_10x_spike

  # 3. or run the read-only shadow directly for N cycles:
  python scripts/run_live_shadow.py --prometheus-url http://localhost:9090 \\
      --namespace boutique --deployment frontend --max-cycles 240
EOF
