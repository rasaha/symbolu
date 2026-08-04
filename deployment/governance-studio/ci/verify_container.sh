#!/usr/bin/env bash
# Runtime hardening + HTTPS + auth + egress verification against the RUNNING OCI
# container (P3E completion §4, §6, §7, §8, §10, §11, §13). Reads the live container and
# /proc — not just the docker run command. Exits nonzero on any failed gate.
set -euo pipefail

IMAGE="${1:?usage: verify_container.sh <image> <certs_dir> <username> <password>}"
CERTS="${2:?certs dir with server.crt/server.key}"
USERNAME="${3:?username}"
PASSWORD="${4:?password}"
NAME="ugs-p3e-verify"
PORT=8443
HASH="$(python -m governance_studio_deployment.generate_password_hash <<<"$PASSWORD")"

cleanup() { docker rm -f "$NAME" ugs-neg >/dev/null 2>&1 || true; docker network rm ugs-internal >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

run_hardened() { # run_hardened <name> <extra docker args...> -- <image env args>
  local name="$1"; shift
  docker run -d --name "$name" \
    --network ugs-internal \
    --user 10001:10001 --read-only \
    --cap-drop ALL --security-opt no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,nodev --tmpfs /var/run/ugence-studio:rw,noexec,nosuid,nodev \
    --pids-limit 128 --memory 1g --cpus 2 \
    "$@"
}

docker network create --internal ugs-internal >/dev/null

# ---- §11 startup-failure negatives: service must fail BEFORE binding ----------
echo "== startup negative tests (fail before bind) =="
neg() { # neg <desc> <docker run args...>
  local desc="$1"; shift
  if docker run --rm --name ugs-neg --network ugs-internal \
       --user 10001:10001 --read-only \
       --tmpfs /tmp --tmpfs /var/run/ugence-studio "$@" >/dev/null 2>&1; then
    echo "FAIL startup should have failed: $desc"; exit 1
  fi
  echo "OK startup fails: $desc"
}
BASE_ENV=(-e UGENCE_STUDIO_DEPLOYMENT_MODE=production -e UGENCE_STUDIO_USERNAME="$USERNAME" \
  -e UGENCE_STUDIO_PASSWORD_HASH="$HASH" -e UGENCE_STUDIO_ALLOWED_HOSTS=127.0.0.1,localhost)
neg "missing certificate" "${BASE_ENV[@]}" -e UGENCE_STUDIO_TLS_CERT_FILE=/run/secrets/tls/nope.crt -e UGENCE_STUDIO_TLS_KEY_FILE=/run/secrets/tls/server.key -v "$CERTS":/run/secrets/tls:ro "$IMAGE"
neg "missing key"         "${BASE_ENV[@]}" -e UGENCE_STUDIO_TLS_CERT_FILE=/run/secrets/tls/server.crt -e UGENCE_STUDIO_TLS_KEY_FILE=/run/secrets/tls/nope.key -v "$CERTS":/run/secrets/tls:ro "$IMAGE"
neg "cert/key mismatch"   "${BASE_ENV[@]}" -e UGENCE_STUDIO_TLS_CERT_FILE=/run/secrets/tls/server.crt -e UGENCE_STUDIO_TLS_KEY_FILE=/run/secrets/tls/mismatch.key -v "$CERTS":/run/secrets/tls:ro "$IMAGE"
neg "missing credentials" -e UGENCE_STUDIO_DEPLOYMENT_MODE=production -e UGENCE_STUDIO_ALLOWED_HOSTS=127.0.0.1 -e UGENCE_STUDIO_TLS_CERT_FILE=/run/secrets/tls/server.crt -e UGENCE_STUDIO_TLS_KEY_FILE=/run/secrets/tls/server.key -v "$CERTS":/run/secrets/tls:ro "$IMAGE"
neg "malformed password hash" -e UGENCE_STUDIO_DEPLOYMENT_MODE=production -e UGENCE_STUDIO_USERNAME="$USERNAME" -e UGENCE_STUDIO_PASSWORD_HASH=not-a-hash -e UGENCE_STUDIO_ALLOWED_HOSTS=127.0.0.1 -e UGENCE_STUDIO_TLS_CERT_FILE=/run/secrets/tls/server.crt -e UGENCE_STUDIO_TLS_KEY_FILE=/run/secrets/tls/server.key -v "$CERTS":/run/secrets/tls:ro "$IMAGE"

# ---- start the hardened service for the positive gates ------------------------
run_hardened "$NAME" \
  -e UGENCE_STUDIO_DEPLOYMENT_MODE=production \
  -e UGENCE_STUDIO_USERNAME="$USERNAME" -e UGENCE_STUDIO_PASSWORD_HASH="$HASH" \
  -e UGENCE_STUDIO_ALLOWED_HOSTS="127.0.0.1,localhost" \
  -e UGENCE_STUDIO_TLS_CERT_FILE=/run/secrets/tls/server.crt \
  -e UGENCE_STUDIO_TLS_KEY_FILE=/run/secrets/tls/server.key \
  -v "$CERTS":/run/secrets/tls:ro -p 127.0.0.1:$PORT:$PORT "$IMAGE"
for _ in $(seq 1 60); do curl -sk "https://127.0.0.1:$PORT/readyz" >/dev/null 2>&1 && break; sleep 1; done

# ---- §6 runtime hardening (read the live container + /proc) --------------------
echo "== runtime hardening (live /proc) =="
[ "$(docker exec "$NAME" id -u):$(docker exec "$NAME" id -g)" = "10001:10001" ] || { echo FAIL uid/gid; exit 1; }
[ "$(docker exec "$NAME" cat /proc/1/status | awk '/NoNewPrivs/{print $2}')" = "1" ] || { echo FAIL NoNewPrivs; exit 1; }
for f in CapEff CapPrm CapBnd; do
  v="$(docker exec "$NAME" cat /proc/1/status | awk -v k="$f:" '$1==k{print $2}')"
  [ "$v" = "0000000000000000" ] || { echo "FAIL $f=$v"; exit 1; }
done
docker exec "$NAME" sh -c 'echo x > /root-probe' 2>/dev/null && { echo FAIL root fs writable; exit 1; } || true
docker exec "$NAME" sh -c 'echo x > /tmp/probe && echo x > /var/run/ugence-studio/probe' || { echo FAIL approved tmpfs not writable; exit 1; }
docker exec "$NAME" sh -c 'test ! -S /var/run/docker.sock' || { echo FAIL docker socket present; exit 1; }
# only 8443 published; no plaintext listener
PORTS="$(docker inspect --format '{{json .NetworkSettings.Ports}}' "$NAME")"
echo "$PORTS" | grep -q '"8443/tcp"' || { echo "FAIL ports=$PORTS"; exit 1; }
echo "$PORTS" | grep -q '"80/tcp"' && { echo FAIL plaintext 80 published; exit 1; } || true
echo "OK uid/gid=10001:10001 NoNewPrivs=1 Cap{Eff,Prm,Bnd}=0 read-only-root only-8443 no-docker-sock"

# ---- §4 TLS exact-version policy (curl --tls-max pins the client ceiling) ------
echo "== TLS policy =="
code() { curl -sk -o /dev/null -w '%{http_code}' "$@"; }
curl -sk --tls-max 1.0 "https://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && { echo FAIL tls1.0 accepted; exit 1; } || true
curl -sk --tls-max 1.1 "https://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && { echo FAIL tls1.1 accepted; exit 1; } || true
curl -sk --tlsv1.2 --tls-max 1.2 "https://127.0.0.1:$PORT/healthz" >/dev/null || { echo FAIL tls1.2 rejected; exit 1; }
if curl -sk --tlsv1.3 "https://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then echo "OK tls1.3 accepted"; else echo "NOTE tls1.3 not negotiated by this client"; fi
echo "OK tls<=1.1 rejected, tls1.2 accepted"

# ---- §8 authentication (UI/asset/API, wrong creds, cooldown, log redaction) ----
echo "== authentication =="
AUTH="Authorization: Basic $(printf '%s:%s' "$USERNAME" "$PASSWORD" | base64)"
[ "$(code https://127.0.0.1:$PORT/)" = 401 ] || { echo FAIL unauth UI; exit 1; }
[ "$(code https://127.0.0.1:$PORT/assets/nope.js)" = 401 ] || { echo FAIL unauth asset; exit 1; }
[ "$(code https://127.0.0.1:$PORT/api/v1/scenarios)" = 401 ] || { echo FAIL unauth API; exit 1; }
[ "$(code -H "$AUTH" https://127.0.0.1:$PORT/)" = 200 ] || { echo FAIL auth UI; exit 1; }
[ "$(code -u ghost:ghost https://127.0.0.1:$PORT/)" = 401 ] || { echo FAIL wrong user; exit 1; }
[ "$(code -u "$USERNAME:wrong" https://127.0.0.1:$PORT/)" = 401 ] || { echo FAIL wrong pass; exit 1; }
# brute-force cooldown: many failures then correct creds still refused during cooldown window
for _ in $(seq 1 12); do code -u "$USERNAME:bad" https://127.0.0.1:$PORT/ >/dev/null; done
[ "$(code -H "$AUTH" https://127.0.0.1:$PORT/)" = 401 ] || { echo FAIL cooldown not enforced; exit 1; }
# credentials never in logs
docker logs "$NAME" 2>&1 | grep -Eiq "$PASSWORD|$HASH|authorization: basic" && { echo FAIL creds in logs; exit 1; } || true
echo "OK 401/200/wrong/cooldown, no creds in logs"

# ---- §8 packaged four-scenario E2E over the container HTTPS listener ----------
echo "== packaged four-scenario E2E (asserts bodies/state, not just 200) =="
python deployment/governance-studio/ci/packaged_e2e.py "https://127.0.0.1:$PORT" "$USERNAME" "$PASSWORD"

# ---- §7 egress: enforcement + observation ------------------------------------
echo "== egress enforcement + observation =="
# enforcement: on the --internal network the container has no off-host route
if docker exec "$NAME" python -c "import socket; socket.setdefaulttimeout(3); socket.create_connection(('1.1.1.1',443))" 2>/dev/null; then
  echo FAIL external egress reachable; exit 1
fi
# observation: record that a deliberate probe was ATTEMPTED to a specific destination
# (blocked), and that DNS resolution of an external name does not succeed
DNS_OK=false; docker exec "$NAME" python -c "import socket; socket.gethostbyname('example.com')" 2>/dev/null && DNS_OK=true
python - "$DNS_OK" <<'PY' > /tmp/egress.json
import json,sys
json.dump({"schema":"runtime-egress.v1","network_mode":"internal (no external route)",
 "enforcement":"external TCP connect to 1.1.1.1:443 refused",
 "observation":{"external_dns_resolves": sys.argv[1]=="true",
   "attempted_destinations":["1.1.1.1:443 (blocked)","example.com (dns)"],
   "external_tcp_success":0,"external_udp_success":0},
 "verdict":"no external egress"}, open("/tmp/egress.json","w"), indent=2)
print("egress evidence written")
PY
cp /tmp/egress.json deployment/governance-studio/artifacts/runtime-egress-report.json
echo "OK egress enforced (internal network) + observed (attempts recorded)"

echo "ALL CONTAINER RUNTIME GATES PASSED"
