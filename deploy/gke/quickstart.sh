#!/usr/bin/env bash
# =========================================================================
# Neural Cloud Controller — GKE Quickstart
#
# Creates a GKE cluster, installs Prometheus, deploys a demo workload,
# and runs the controller in dry-run mode. Total cost: ~$1-3 for a
# 2-hour test session.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - kubectl installed
#   - helm installed (for kube-prometheus-stack)
#   - A GCP project with billing enabled
#
# Usage:
#   ./quickstart.sh                     # Full setup + deploy
#   ./quickstart.sh --teardown          # Delete everything
#   ./quickstart.sh --deploy-only       # Skip cluster creation (already exists)
#   ./quickstart.sh --live              # Enable live scaling (scale_patch mode)
#   ./quickstart.sh --shadow            # Shadow mode (compare with HPA)
#
# =========================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit these for your environment
# ---------------------------------------------------------------------------
PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GKE_REGION:-us-central1}"
ZONE="${GKE_ZONE:-us-central1-a}"
CLUSTER_NAME="${GKE_CLUSTER:-ncc-test}"
MACHINE_TYPE="${GKE_MACHINE_TYPE:-e2-small}"
NUM_NODES="${GKE_NUM_NODES:-3}"
PREEMPTIBLE="${GKE_PREEMPTIBLE:-true}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Flags
TEARDOWN=false
DEPLOY_ONLY=false
LIVE_MODE=false
SHADOW_MODE=false

for arg in "$@"; do
    case "$arg" in
        --teardown)   TEARDOWN=true ;;
        --deploy-only) DEPLOY_ONLY=true ;;
        --live)       LIVE_MODE=true ;;
        --shadow)     SHADOW_MODE=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[NCC]${NC} $*"; }
warn() { echo -e "${YELLOW}[NCC]${NC} $*"; }
err()  { echo -e "${RED}[NCC]${NC} $*" >&2; }
step() { echo -e "\n${BLUE}=== $* ===${NC}"; }

# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
if $TEARDOWN; then
    step "Tearing down GKE cluster"
    log "Deleting cluster '$CLUSTER_NAME' in $ZONE..."
    gcloud container clusters delete "$CLUSTER_NAME" \
        --zone="$ZONE" --project="$PROJECT" --quiet || true
    log "Teardown complete. Cluster deleted."
    exit 0
fi

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
step "Preflight checks"

for cmd in gcloud kubectl helm; do
    if ! command -v "$cmd" &>/dev/null; then
        err "$cmd not found. Install it first."
        exit 1
    fi
done

if [ -z "$PROJECT" ]; then
    err "No GCP project set. Run: gcloud config set project YOUR_PROJECT"
    exit 1
fi
log "Project: $PROJECT"
log "Zone:    $ZONE"
log "Cluster: $CLUSTER_NAME"

# ---------------------------------------------------------------------------
# 1. Create GKE cluster
# ---------------------------------------------------------------------------
if ! $DEPLOY_ONLY; then
    step "1/6 Creating GKE cluster ($NUM_NODES x $MACHINE_TYPE)"

    PREEMPTIBLE_FLAG=""
    if $PREEMPTIBLE; then
        PREEMPTIBLE_FLAG="--preemptible"
        log "Using preemptible VMs (~80% cheaper)"
    fi

    if gcloud container clusters describe "$CLUSTER_NAME" \
        --zone="$ZONE" --project="$PROJECT" &>/dev/null; then
        warn "Cluster '$CLUSTER_NAME' already exists, reusing"
    else
        gcloud container clusters create "$CLUSTER_NAME" \
            --zone="$ZONE" \
            --project="$PROJECT" \
            --num-nodes="$NUM_NODES" \
            --machine-type="$MACHINE_TYPE" \
            --disk-size=20 \
            --enable-autoscaling --min-nodes=1 --max-nodes=6 \
            --scopes="https://www.googleapis.com/auth/monitoring.read" \
            $PREEMPTIBLE_FLAG \
            --no-enable-basic-auth \
            --metadata disable-legacy-endpoints=true
        log "Cluster created"
    fi

    # Get credentials
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --zone="$ZONE" --project="$PROJECT"
    log "kubectl context set to $CLUSTER_NAME"

    # ---------------------------------------------------------------------------
    # 2. Install Prometheus (kube-prometheus-stack)
    # ---------------------------------------------------------------------------
    step "2/6 Installing Prometheus via kube-prometheus-stack"

    helm repo add prometheus-community \
        https://prometheus-community.github.io/helm-charts 2>/dev/null || true
    helm repo update

    if helm status prometheus -n monitoring &>/dev/null; then
        warn "kube-prometheus-stack already installed, skipping"
    else
        kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
        helm install prometheus prometheus-community/kube-prometheus-stack \
            --namespace monitoring \
            --set grafana.enabled=true \
            --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
            --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
            --wait --timeout 5m
        log "Prometheus + Grafana installed in 'monitoring' namespace"
    fi

else
    log "Skipping cluster creation (--deploy-only)"
fi

# ---------------------------------------------------------------------------
# 3. Deploy demo workload
# ---------------------------------------------------------------------------
step "3/6 Deploying demo workload"

kubectl apply -f "$SCRIPT_DIR/demo-app.yaml"
kubectl rollout status deployment/demo-app -n default --timeout=120s
log "Demo app running (3 replicas)"

# ---------------------------------------------------------------------------
# 4. Deploy NCC controller
# ---------------------------------------------------------------------------
step "4/6 Deploying Neural Cloud Controller"

# Apply namespace and RBAC
kubectl apply -f "$SCRIPT_DIR/namespace.yaml"
kubectl apply -f "$SCRIPT_DIR/rbac.yaml"

# Patch configmap for live mode if requested
if $LIVE_MODE; then
    warn "LIVE MODE: actuator set to scale_patch — controller WILL scale pods"
    sed 's/mode: dry_run/mode: scale_patch/' "$SCRIPT_DIR/configmap.yaml" | \
        sed 's/auto_approve_threshold: null/auto_approve_threshold: high/' | \
        kubectl apply -f -
else
    log "DRY-RUN MODE: controller will log decisions but not scale"
    kubectl apply -f "$SCRIPT_DIR/configmap.yaml"
fi

kubectl apply -f "$SCRIPT_DIR/deployment.yaml"
kubectl apply -f "$SCRIPT_DIR/service.yaml"

kubectl rollout status deployment/ncc-controller -n ncc --timeout=120s
log "Controller deployed"

# ---------------------------------------------------------------------------
# 5. Verify
# ---------------------------------------------------------------------------
step "5/6 Verifying deployment"

echo ""
log "Pods:"
kubectl get pods -n ncc -o wide
echo ""
log "Demo app:"
kubectl get pods -n default -l app=demo-app
echo ""

# Wait for metrics endpoint
log "Waiting for /healthz..."
for i in $(seq 1 30); do
    if kubectl exec -n ncc deploy/ncc-controller -- \
        wget -q -O- http://localhost:8080/healthz 2>/dev/null | grep -q ok; then
        log "Health check passed"
        break
    fi
    sleep 2
done

# ---------------------------------------------------------------------------
# 6. Print access instructions
# ---------------------------------------------------------------------------
step "6/6 Access Information"

echo ""
log "Controller logs:"
echo "    kubectl logs -f -n ncc deploy/ncc-controller"
echo ""
log "Controller metrics:"
echo "    kubectl port-forward -n ncc svc/ncc-controller 8080:8080"
echo "    curl http://localhost:8080/metrics"
echo ""
log "Prometheus UI:"
echo "    kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "    open http://localhost:9090"
echo ""
log "Grafana:"
echo "    kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80"
echo "    open http://localhost:3000  (admin / prom-operator)"
echo ""

if $SHADOW_MODE; then
    log "Shadow mode: starting controller in shadow mode..."
    echo "    kubectl exec -it -n ncc deploy/ncc-controller -- python -m symbolu.cloud_controller.main --shadow"
fi

echo ""
log "Generate load to trigger scaling decisions:"
echo "    kubectl run loadgen --image=busybox --restart=Never -- /bin/sh -c \\"
echo "      'while true; do wget -q -O- http://demo-app.default.svc/; done'"
echo ""

if $LIVE_MODE; then
    warn "LIVE MODE is active. The controller will scale demo-app pods."
    warn "Watch: kubectl get pods -n default -w"
else
    log "To enable live scaling, redeploy with: ./quickstart.sh --deploy-only --live"
fi

echo ""
log "To tear down and stop billing:"
echo "    ./quickstart.sh --teardown"
echo ""
log "Quickstart complete."
