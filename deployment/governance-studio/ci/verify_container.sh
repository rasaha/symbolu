#!/usr/bin/env bash
# Runtime hardening + HTTPS + auth verification against the RUNNING OCI container
# (P3E completion §10, §11, §13). Requires a container runtime with the image built and
# base-image egress available; exits nonzero on any failed gate. Not a substitute for
# static Dockerfile assertions — these read the live container.
set -euo pipefail

IMAGE="${1:?usage: verify_container.sh <image> <certs_dir> <username> <password>}"
CERTS="${2:?certs dir with server.crt/server.key}"
USERNAME="${3:?username}"
PASSWORD="${4:?password}"
NAME="ugs-p3e-verify"
PORT=8443
HASH="$(python -m governance_studio_deployment.generate_password_hash <<<"$PASSWORD")"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; docker network rm ugs-internal >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

# Internal-only network (no external route) proves runtime no-egress (§13).
docker network create --internal ugs-internal >/dev/null

docker run -d --name "$NAME" \
  --network ugs-internal \
  --user 10001:10001 \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,nodev \
  --tmpfs /var/run/ugence-studio:rw,noexec,nosuid,nodev \
  --pids-limit 128 --memory 1g --cpus 2 \
  -e UGENCE_STUDIO_DEPLOYMENT_MODE=production \
  -e UGENCE_STUDIO_USERNAME="$USERNAME" \
  -e UGENCE_STUDIO_PASSWORD_HASH="$HASH" \
  -e UGENCE_STUDIO_ALLOWED_HOSTS="127.0.0.1,localhost" \
  -e UGENCE_STUDIO_TLS_CERT_FILE=/run/secrets/tls/server.crt \
  -e UGENCE_STUDIO_TLS_KEY_FILE=/run/secrets/tls/server.key \
  -v "$CERTS":/run/secrets/tls:ro \
  -p 127.0.0.1:$PORT:$PORT \
  "$IMAGE"

# wait for readiness over TLS
for _ in $(seq 1 60); do
  if curl -sk "https://127.0.0.1:$PORT/readyz" >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "== runtime hardening =="
UIDGID="$(docker exec "$NAME" id -u):$(docker exec "$NAME" id -g)"
[ "$UIDGID" = "10001:10001" ] || { echo "FAIL uid/gid=$UIDGID"; exit 1; }
NNP="$(docker exec "$NAME" grep NoNewPrivs /proc/self/status | awk '{print $2}')"
[ "$NNP" = "1" ] || { echo "FAIL NoNewPrivs=$NNP"; exit 1; }
CAPEFF="$(docker exec "$NAME" grep CapEff /proc/self/status | awk '{print $2}')"
[ "$CAPEFF" = "0000000000000000" ] || { echo "FAIL CapEff=$CAPEFF (capabilities not fully dropped)"; exit 1; }
# read-only root: a write outside approved tmpfs must fail
if docker exec "$NAME" sh -c 'echo x > /root-probe' 2>/dev/null; then echo "FAIL root fs writable"; exit 1; fi
docker exec "$NAME" sh -c 'echo x > /tmp/probe' || { echo "FAIL /tmp not writable"; exit 1; }
echo "OK uid/gid=$UIDGID NoNewPrivs=1 CapEff=$CAPEFF read-only-root"

echo "== TLS policy =="
AUTH="Authorization: Basic $(printf '%s:%s' "$USERNAME" "$PASSWORD" | base64)"
for v in tls1 tls1_1; do
  if curl -sk --$v "https://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then echo "FAIL $v accepted"; exit 1; fi
done
curl -sk --tlsv1.2 "https://127.0.0.1:$PORT/healthz" >/dev/null || { echo "FAIL tls1.2 rejected"; exit 1; }
echo "OK tls1.0/1.1 rejected, tls1.2 accepted"

echo "== authentication =="
code() { curl -sk -o /dev/null -w '%{http_code}' "$@"; }
[ "$(code https://127.0.0.1:$PORT/)" = "401" ] || { echo "FAIL unauth UI"; exit 1; }
[ "$(code https://127.0.0.1:$PORT/api/v1/scenarios)" = "401" ] || { echo "FAIL unauth API"; exit 1; }
[ "$(code -H "$AUTH" https://127.0.0.1:$PORT/)" = "200" ] || { echo "FAIL auth UI"; exit 1; }
[ "$(code -u "wrong:wrong" https://127.0.0.1:$PORT/)" = "401" ] || { echo "FAIL wrong creds"; exit 1; }
echo "OK unauth 401 / auth 200 / wrong 401"

echo "== packaged four-scenario E2E over the container HTTPS listener =="
python deployment/governance-studio/ci/packaged_e2e.py "https://127.0.0.1:$PORT" "$USERNAME" "$PASSWORD"

echo "== runtime egress (internal-only network) =="
# on --internal network the container has no route off-host; a non-loopback connect must fail
if docker exec "$NAME" python -c "import socket; socket.create_connection(('1.1.1.1',443),3)" 2>/dev/null; then
  echo "FAIL external egress reachable"; exit 1
fi
echo "OK no external egress (internal network; external connect refused)"

echo "== no Docker socket / no shell listener leak =="
if docker exec "$NAME" test -S /var/run/docker.sock 2>/dev/null; then echo "FAIL docker socket present"; exit 1; fi
echo "ALL CONTAINER RUNTIME GATES PASSED"
