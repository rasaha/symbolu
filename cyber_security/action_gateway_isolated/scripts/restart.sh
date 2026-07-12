#!/usr/bin/env bash
# Restart broker + gateway (keys/certs/stores persist). Proves durable replay
# survives process restart. Idempotent.
set -uo pipefail
PKG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CS_ROOT="$(cd "$PKG_ROOT/.." && pwd)"
RUN="${AGW_ISO_RUN:-/tmp/agw-iso}"
export AGW_ISO_RUN="$RUN"
export PYTHONPATH="$PKG_ROOT:$CS_ROOT/action_gateway:$CS_ROOT/action_gateway_mcp:$CS_ROOT/action_gateway_k8s"

pkill -f action_gateway_isolated.broker_service 2>/dev/null || true
pkill -f action_gateway_isolated.gateway_service 2>/dev/null || true
sleep 1

BE="AGW_ISO_RUN=$RUN PYTHONPATH=$PYTHONPATH AGW_BROKER_CA=$RUN/brokerpki/ca.crt AGW_BROKER_ADMIN_CERT=$RUN/brokerpki/admin.crt AGW_BROKER_ADMIN_KEY=$RUN/brokerpki/admin.key"
setpriv --reuid=brokeru --regid=brokeru --init-groups \
  env $BE python3 -m action_gateway_isolated.broker_service >> "$RUN/broker.log" 2>&1 &
setpriv --reuid=gwu --regid=gwu --init-groups \
  env AGW_ISO_RUN="$RUN" PYTHONPATH="$PYTHONPATH" AGW_SOCK_GROUP=agwsock \
  python3 -m action_gateway_isolated.gateway_service >> "$RUN/gateway.log" 2>&1 &

for i in $(seq 1 30); do
  [ -S "$RUN/sock/gateway.sock" ] && python3 -c "import socket;socket.create_connection(('127.0.0.1',8443),2)" 2>/dev/null && break
  sleep 1
done
echo "[restart] services restarted" >&2
