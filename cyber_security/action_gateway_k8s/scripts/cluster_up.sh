#!/usr/bin/env bash
# Provision a disposable, local, REAL Kubernetes control plane (etcd + kube-apiserver).
#
# This is a control-plane-only cluster: it runs the real apiserver and etcd, which
# is sufficient to prove the security thesis (RBAC scoping, TokenRequest-minted
# short-lived credentials, server-side dry-run admission, optimistic-concurrency
# TOCTOU, anonymous/unscoped denial). It runs NO kubelet/scheduler/controller-
# manager, so workloads do not actually schedule; objects are created, validated,
# and admission-controlled by the real apiserver. See README "limitations".
#
# Idempotent: re-running while the apiserver is healthy is a no-op. Never prints
# secrets or tokens.
set -euo pipefail

VERSION="${K8S_REF_VERSION:-v1.31.4}"
ETCD_VERSION="${ETCD_REF_VERSION:-v3.5.16}"
BIN="${K8S_REF_BIN:-/opt/k8s-ref/bin}"
RUN="${K8S_REF_RUN:-/tmp/k8sref}"
ARCH="linux/amd64"
KCFG="$RUN/admin.kubeconfig"

log(){ echo "[cluster_up] $*" >&2; }

# --- 0. already healthy? ---
if [ -f "$KCFG" ] && "$BIN/kubectl" --kubeconfig "$KCFG" get --raw=/healthz >/dev/null 2>&1; then
  log "apiserver already healthy; nothing to do"
  echo "$KCFG"
  exit 0
fi

mkdir -p "$BIN" "$RUN/pki" "$RUN/data"

# --- 1. binaries (download if missing) ---
dl(){ # url dest
  if [ ! -x "$2" ]; then log "downloading $(basename "$2")"; curl -fsSL -o "$2" "$1"; chmod +x "$2"; fi
}
dl "https://dl.k8s.io/release/$VERSION/bin/$ARCH/kubectl" "$BIN/kubectl"
dl "https://dl.k8s.io/release/$VERSION/bin/$ARCH/kube-apiserver" "$BIN/kube-apiserver"
if [ ! -x "$BIN/etcd" ]; then
  log "downloading etcd"
  curl -fsSL -o "$RUN/etcd.tgz" "https://storage.googleapis.com/etcd/$ETCD_VERSION/etcd-$ETCD_VERSION-linux-amd64.tar.gz"
  tar xzf "$RUN/etcd.tgz" -C "$RUN"
  cp "$RUN/etcd-$ETCD_VERSION-linux-amd64/etcd" "$BIN/etcd"; chmod +x "$BIN/etcd"
fi

# --- 2. PKI (CA, apiserver serving cert, SA signing key, admin client cert) ---
cd "$RUN/pki"
if [ ! -f ca.crt ]; then
  log "generating PKI"
  openssl genrsa -out ca.key 2048 2>/dev/null
  openssl req -x509 -new -nodes -key ca.key -subj "/CN=k8s-ref-ca" -days 2 -out ca.crt 2>/dev/null
  openssl genrsa -out sa.key 2048 2>/dev/null
  openssl rsa -in sa.key -pubout -out sa.pub 2>/dev/null
  cat > apiserver.cnf <<'CNF'
[req]
req_extensions = v3_req
distinguished_name = dn
prompt = no
[dn]
CN = kube-apiserver
[v3_req]
subjectAltName = @alt
[alt]
DNS.1 = kubernetes
DNS.2 = kubernetes.default.svc
DNS.3 = localhost
IP.1 = 127.0.0.1
IP.2 = 10.0.0.1
CNF
  openssl genrsa -out apiserver.key 2048 2>/dev/null
  openssl req -new -key apiserver.key -subj "/CN=kube-apiserver" -out apiserver.csr -config apiserver.cnf 2>/dev/null
  openssl x509 -req -in apiserver.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out apiserver.crt -days 2 -extensions v3_req -extfile apiserver.cnf 2>/dev/null
  openssl genrsa -out admin.key 2048 2>/dev/null
  openssl req -new -key admin.key -subj "/CN=admin/O=system:masters" -out admin.csr 2>/dev/null
  openssl x509 -req -in admin.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out admin.crt -days 2 2>/dev/null
fi

# --- 3. admission config: enforce restricted PodSecurity by default ---
cat > "$RUN/admission.yaml" <<'ADM'
apiVersion: apiserver.config.k8s.io/v1
kind: AdmissionConfiguration
plugins:
- name: PodSecurity
  configuration:
    apiVersion: pod-security.admission.config.k8s.io/v1
    kind: PodSecurityConfiguration
    defaults: {enforce: "restricted", enforce-version: "latest"}
    exemptions: {namespaces: [kube-system]}
ADM

# --- 4. start etcd + apiserver ---
if ! pgrep -f "$BIN/etcd" >/dev/null 2>&1; then
  log "starting etcd"
  "$BIN/etcd" --data-dir "$RUN/data" \
    --listen-client-urls http://127.0.0.1:2379 --advertise-client-urls http://127.0.0.1:2379 \
    --listen-peer-urls http://127.0.0.1:2380 > "$RUN/etcd.log" 2>&1 &
  sleep 3
fi
if ! pgrep -f "$BIN/kube-apiserver" >/dev/null 2>&1; then
  log "starting kube-apiserver"
  "$BIN/kube-apiserver" \
    --etcd-servers=http://127.0.0.1:2379 \
    --secure-port=6443 --bind-address=127.0.0.1 --advertise-address=127.0.0.1 \
    --tls-cert-file="$RUN/pki/apiserver.crt" --tls-private-key-file="$RUN/pki/apiserver.key" \
    --client-ca-file="$RUN/pki/ca.crt" \
    --service-account-key-file="$RUN/pki/sa.pub" \
    --service-account-signing-key-file="$RUN/pki/sa.key" \
    --service-account-issuer=https://kubernetes.default.svc \
    --api-audiences=https://kubernetes.default.svc \
    --authorization-mode=RBAC \
    --enable-admission-plugins=PodSecurity,ServiceAccount,NamespaceLifecycle \
    --admission-control-config-file="$RUN/admission.yaml" \
    --allow-privileged=true --service-cluster-ip-range=10.0.0.0/24 \
    > "$RUN/apiserver.log" 2>&1 &
fi

# --- 5. wait for health ---
"$BIN/kubectl" config set-cluster ref --server=https://127.0.0.1:6443 \
  --certificate-authority="$RUN/pki/ca.crt" --embed-certs=true --kubeconfig "$KCFG" >/dev/null
"$BIN/kubectl" config set-credentials admin --client-certificate="$RUN/pki/admin.crt" \
  --client-key="$RUN/pki/admin.key" --embed-certs=true --kubeconfig "$KCFG" >/dev/null
"$BIN/kubectl" config set-context ref --cluster=ref --user=admin --kubeconfig "$KCFG" >/dev/null
"$BIN/kubectl" config use-context ref --kubeconfig "$KCFG" >/dev/null

for i in $(seq 1 30); do
  if "$BIN/kubectl" --kubeconfig "$KCFG" get --raw=/healthz >/dev/null 2>&1; then break; fi
  sleep 1
done
"$BIN/kubectl" --kubeconfig "$KCFG" get --raw=/healthz >/dev/null

log "apiserver healthy"
echo "$KCFG"
