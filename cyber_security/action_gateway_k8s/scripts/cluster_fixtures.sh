#!/usr/bin/env bash
# Create the protected/sandbox namespaces + deterministic test fixtures.
# Idempotent. The apiserver runs no controller-manager, so 'default' service
# accounts are created explicitly here (normally the SA controller does this).
set -euo pipefail
BIN="${K8S_REF_BIN:-/opt/k8s-ref/bin}"
RUN="${K8S_REF_RUN:-/tmp/k8sref}"
KCFG="$RUN/admin.kubeconfig"
k(){ "$BIN/kubectl" --kubeconfig "$KCFG" "$@"; }

apply(){ k apply -f - >/dev/null; }

# namespaces: protected (restricted PSS) + sandbox (baseline)
apply <<'EOF'
apiVersion: v1
kind: Namespace
metadata:
  name: protected
  labels:
    pod-security.kubernetes.io/enforce: restricted
    action-gateway.io/protected: "true"
EOF
apply <<'EOF'
apiVersion: v1
kind: Namespace
metadata:
  name: sandbox
  labels: {pod-security.kubernetes.io/enforce: baseline}
EOF

# default service accounts (no controller-manager to create them)
for ns in protected sandbox default kube-system; do
  k -n "$ns" get serviceaccount default >/dev/null 2>&1 || \
    k -n "$ns" create serviceaccount default >/dev/null
done

# deterministic fixtures in the protected namespace
apply <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata: {namespace: protected, name: app-config}
data: {greeting: hello, tier: prod}
EOF
apply <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata: {namespace: protected, name: web}
spec:
  replicas: 1
  selector: {matchLabels: {app: web}}
  template:
    metadata: {labels: {app: web}}
    spec:
      securityContext: {runAsNonRoot: true, seccompProfile: {type: RuntimeDefault}}
      containers:
      - name: web
        image: registry.example.com/web:1.0.0
        securityContext:
          allowPrivilegeEscalation: false
          capabilities: {drop: [ALL]}
        resources: {requests: {cpu: 50m, memory: 64Mi}, limits: {cpu: 200m, memory: 128Mi}}
EOF
apply <<'EOF'
apiVersion: v1
kind: Service
metadata: {namespace: protected, name: web}
spec: {selector: {app: web}, ports: [{port: 80, targetPort: 80}], type: ClusterIP}
EOF
# a secret that must never be exported through the gateway
apply <<'EOF'
apiVersion: v1
kind: Secret
metadata: {namespace: protected, name: app-secret}
type: Opaque
stringData: {token: do-not-export}
EOF

echo "[fixtures] protected + sandbox namespaces and fixtures ready" >&2
