#!/usr/bin/env bash
# Stop the isolated services and wipe runtime state (keys, certs, sockets, DBs).
# Does not remove users (harmless to keep). Idempotent.
set -uo pipefail
RUN="${AGW_ISO_RUN:-/tmp/agw-iso}"
pkill -f action_gateway_isolated.broker_service 2>/dev/null || true
pkill -f action_gateway_isolated.gateway_service 2>/dev/null || true
sleep 1
rm -rf "$RUN"
echo "[teardown] services stopped; $RUN wiped" >&2
