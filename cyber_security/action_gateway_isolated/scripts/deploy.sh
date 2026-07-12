#!/usr/bin/env bash
# Materialize the four isolated protection domains and start the services.
# Idempotent. Requires root (creates users, drops privileges, sets key ownership).
set -euo pipefail

PKG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CS_ROOT="$(cd "$PKG_ROOT/.." && pwd)"
RUN="${AGW_ISO_RUN:-/tmp/agw-iso}"
KREF="${K8S_REF_RUN:-/tmp/k8sref}"
export AGW_ISO_RUN="$RUN"
export PYTHONPATH="$PKG_ROOT:$CS_ROOT/action_gateway:$CS_ROOT/action_gateway_mcp:$CS_ROOT/action_gateway_k8s"
export AGW_SOCK_GROUP=agwsock

log(){ echo "[deploy] $*" >&2; }

# --- users + shared socket group ---
for u in agentu gwu brokeru; do id "$u" >/dev/null 2>&1 || useradd -M -s /usr/sbin/nologin "$u"; done
getent group agwsock >/dev/null || groupadd agwsock
usermod -aG agwsock agentu; usermod -aG agwsock gwu

# --- directories (RUN world-traversable; secrets protected per-file/subdir) ---
mkdir -p "$RUN"/{keys,pub,tls,db,brokerpki,sock}
chown root:root "$RUN"; chmod 0755 "$RUN"
chown gwu:agwsock "$RUN/sock"; chmod 0770 "$RUN/sock"   # gwu creates socket; agentu (agwsock) connects
chmod 0755 "$RUN/keys" "$RUN/pub" "$RUN/tls"
: > "$RUN/broker.log"; chown brokeru:brokeru "$RUN/broker.log"
: > "$RUN/gateway.log"; chown gwu:gwu "$RUN/gateway.log"

# --- Ed25519 keys (generated once) ---
python3 -c "import sys;sys.path.insert(0,'$PKG_ROOT');from action_gateway_isolated import bootstrap;bootstrap.generate_keys()"
# custody: gateway key -> gwu; policy/approver/checkpoint -> root (offline); publics world-readable
chown gwu:gwu "$RUN/keys/gateway.sk"; chmod 0400 "$RUN/keys/gateway.sk"
for k in policy_root "approver__security-lead" "approver__sre-lead" checkpoint; do
  chown root:root "$RUN/keys/$k.sk"; chmod 0400 "$RUN/keys/$k.sk"
done
chmod 0644 "$RUN"/pub/*.pub; chmod 0755 "$RUN/pub"

# --- mTLS PKI (CA, broker server cert, gateway client cert) ---
cd "$RUN/tls"
if [ ! -f ca.crt ]; then
  openssl genrsa -out ca.key 2048 2>/dev/null
  openssl req -x509 -new -nodes -key ca.key -subj "/CN=agw-iso-ca" -days 2 -out ca.crt 2>/dev/null
  # broker server cert (CN=broker, SAN)
  cat > broker.cnf <<'CNF'
[req]
distinguished_name=dn
req_extensions=v3
prompt=no
[dn]
CN=broker
[v3]
subjectAltName=@a
[a]
DNS.1=broker
IP.1=127.0.0.1
CNF
  openssl genrsa -out broker.key 2048 2>/dev/null
  openssl req -new -key broker.key -subj "/CN=broker" -config broker.cnf -out broker.csr 2>/dev/null
  openssl x509 -req -in broker.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out broker.crt -days 2 -extensions v3 -extfile broker.cnf 2>/dev/null
  # gateway client cert (CN=gateway)
  openssl genrsa -out gateway.key 2048 2>/dev/null
  openssl req -new -key gateway.key -subj "/CN=gateway" -out gateway.csr 2>/dev/null
  openssl x509 -req -in gateway.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out gateway.crt -days 2 2>/dev/null
fi
chown brokeru:brokeru broker.key; chmod 0400 broker.key
chown gwu:gwu gateway.key; chmod 0400 gateway.key
chmod 0444 ca.crt broker.crt gateway.crt

# --- broker-only copy of the admin Kubernetes credential ---
cp "$KREF/pki/ca.crt" "$RUN/brokerpki/ca.crt"
cp "$KREF/pki/admin.crt" "$RUN/brokerpki/admin.crt"
cp "$KREF/pki/admin.key" "$RUN/brokerpki/admin.key"
chown -R brokeru:brokeru "$RUN/brokerpki"; chmod 0500 "$RUN/brokerpki"; chmod 0400 "$RUN"/brokerpki/*

# --- durable stores: broker domain only ---
chown brokeru:brokeru "$RUN/db"; chmod 0700 "$RUN/db"

# --- protected-namespace fixtures (backup registry for rollback verification) ---
"$KREF/../../$(basename "$KREF")" >/dev/null 2>&1 || true
KUBECTL=/opt/k8s-ref/bin/kubectl
$KUBECTL --kubeconfig "$KREF/admin.kubeconfig" apply -f - >/dev/null 2>&1 <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata: {name: backup-registry, namespace: protected}
data: {app-config: "backup-baseline"}
EOF

# --- start broker (brokeru) ---
pkill -f action_gateway_isolated.broker_service 2>/dev/null || true
pkill -f action_gateway_isolated.gateway_service 2>/dev/null || true
sleep 1
BROKER_ENV="AGW_ISO_RUN=$RUN PYTHONPATH=$PYTHONPATH AGW_BROKER_CA=$RUN/brokerpki/ca.crt AGW_BROKER_ADMIN_CERT=$RUN/brokerpki/admin.crt AGW_BROKER_ADMIN_KEY=$RUN/brokerpki/admin.key"
setpriv --reuid=brokeru --regid=brokeru --init-groups \
  env $BROKER_ENV python3 -m action_gateway_isolated.broker_service > "$RUN/broker.log" 2>&1 &
log "broker pid $!"
# --- start gateway (gwu) ---
setpriv --reuid=gwu --regid=gwu --init-groups \
  env AGW_ISO_RUN="$RUN" PYTHONPATH="$PYTHONPATH" AGW_SOCK_GROUP=agwsock \
  python3 -m action_gateway_isolated.gateway_service > "$RUN/gateway.log" 2>&1 &
log "gateway pid $!"

# --- wait for readiness ---
ready=0
for i in $(seq 1 30); do
  if [ -S "$RUN/gateway.sock" ] && python3 -c "import socket;socket.create_connection(('127.0.0.1',8443),2)" 2>/dev/null; then
    ready=1; break
  fi
  sleep 1
done
[ "$ready" = 1 ] || { log "services not ready"; tail -5 "$RUN/broker.log" "$RUN/gateway.log" >&2; exit 1; }
log "gateway.sock ready; broker mTLS port up"
echo "$RUN"
