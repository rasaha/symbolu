#!/usr/bin/env bash
# Runtime hardening + private TLS listener + fail-closed posture verification against
# the RUNNING governed-runtime-worker OCI container (composition-root ADR step 4).
# Reads the live container and /proc, not just the docker run command. Exits nonzero on
# any failed gate. Every DSN handed to a container is checked against its logs.
#
# Two networks, deliberately:
#   * grw-internal (--internal, no off-host route): every startup NEGATIVE, which must
#     fail in preflight before any socket or database is touched;
#   * grw-bridge (a user-defined bridge with a fixed subnet): the POSITIVE run, which
#     needs the runner's PostgreSQL at the bridge gateway and a private address the
#     worker may bind (CR-3 refuses 0.0.0.0, so the container gets a fixed RFC 1918 IP).
# The worker's egress rule is platform configuration (CR-5, EXTERNAL_DEPLOYMENT_EVIDENCE):
# this script OBSERVES whether an external connect succeeds and records it; it does not
# claim enforcement it cannot provide.
set -euo pipefail

IMAGE="${1:?usage: verify_container.sh <image> <certs_dir> <app_dsn> <system_dsn>}"
CERTS="${2:?certs dir with server.crt/server.key}"
APP_DSN="${3:?application database DSN (reachable from the bridge gateway)}"
SYS_DSN="${4:?system database DSN}"
NAME="grw-verify"
SUBNET="10.90.0.0/24"; GATEWAY="10.90.0.1"; BIND="10.90.0.10"; PORT=8444
ISSUER="https://issuer.invalid"   # never fetched at startup; decisions are not exercised here

cleanup() {
  docker rm -f "$NAME" grw-neg grw-probe >/dev/null 2>&1 || true
  docker network rm grw-internal grw-bridge >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
docker network create --internal grw-internal >/dev/null
docker network create --subnet "$SUBNET" --gateway "$GATEWAY" grw-bridge >/dev/null

PROD_ENV=(-e UGENCE_REVIEW_DEPLOYMENT_MODE=production
  -e UGENCE_REVIEW_TENANT_ID=tenant-a -e UGENCE_REVIEW_REQUIRED_ROLE=risk-approver
  -e UGENCE_REVIEW_DEFINITION_DIGEST=shadow-v1 -e UGENCE_REVIEW_BIND_HOST="$BIND"
  -e UGENCE_REVIEW_TLS_CERT_FILE=/run/secrets/tls/server.crt -e UGENCE_REVIEW_TLS_KEY_FILE=/run/secrets/tls/server.key
  -e UGENCE_REVIEW_IDENTITY_ISSUER="$ISSUER" -e UGENCE_REVIEW_IDENTITY_AUDIENCE=ugence-governed-review-service
  -e UGENCE_REVIEW_IDENTITY_JWKS_URL="$ISSUER/jwks.json" -e UGENCE_REVIEW_IDENTITY_TENANT_CLAIM=ugence_tenant
  -e UGENCE_REVIEW_IDENTITY_ACTOR_TYPE_CLAIM=ugence_actor -e UGENCE_REVIEW_IDENTITY_HUMAN_ACTOR_VALUE=human-sign-in)
DSN_ENV=(-e UGENCE_REVIEW_APP_DATABASE_URL="$APP_DSN" -e UGENCE_REVIEW_SYSTEM_DATABASE_URL="$SYS_DSN")

# ---- startup negatives: the posture refuses BEFORE binding or connecting ----------
echo "== startup negative tests (refused in preflight, no socket, no database) =="
neg() { # neg <desc> <expected code> <docker run args...>
  local desc="$1" want="$2"; shift 2
  local out
  if out="$(docker run --rm --name grw-neg --network grw-internal --user 10001:10001 --read-only \
       --tmpfs /tmp --tmpfs /var/lib/ugence-review -v "$CERTS":/run/secrets/tls:ro "$@" 2>&1)"; then
    echo "FAIL startup should have failed: $desc"; exit 1
  fi
  echo "$out" | grep -q "$want" || { echo "FAIL $desc: expected $want, got: $(echo "$out" | tail -n 2)"; exit 1; }
  echo "$out" | grep -Fq "$APP_DSN" && { echo "FAIL $desc: DSN printed"; exit 1; } || true
  echo "OK refused ($want): $desc"
}
neg "public bind 0.0.0.0"        WORKER_CONFIG_INVALID "${PROD_ENV[@]}" "${DSN_ENV[@]}" -e UGENCE_REVIEW_BIND_HOST=0.0.0.0 "$IMAGE"
neg "plain-HTTP listener"        WORKER_CONFIG_INVALID "${PROD_ENV[@]}" "${DSN_ENV[@]}" -e UGENCE_REVIEW_TLS_CERT_FILE= -e UGENCE_REVIEW_TLS_KEY_FILE= "$IMAGE"
neg "http JWKS in production"    WORKER_CONFIG_INVALID "${PROD_ENV[@]}" "${DSN_ENV[@]}" -e UGENCE_REVIEW_IDENTITY_JWKS_URL=http://issuer.invalid/jwks.json "$IMAGE"
neg "no identity port"           WORKER_CONFIG_INVALID "${PROD_ENV[@]}" "${DSN_ENV[@]}" -e UGENCE_REVIEW_IDENTITY_ISSUER= -e UGENCE_REVIEW_IDENTITY_AUDIENCE= -e UGENCE_REVIEW_IDENTITY_JWKS_URL= "$IMAGE"
neg "in-memory store"            WORKER_CONFIG_INVALID "${PROD_ENV[@]}" "${DSN_ENV[@]}" -e UGENCE_REVIEW_DATA_DIR=:memory: "$IMAGE"
neg "missing DSN"                WORKER_CONFIG_INVALID "${PROD_ENV[@]}" -e UGENCE_REVIEW_APP_DATABASE_URL="$APP_DSN" "$IMAGE"
neg "unknown deployment mode"    WORKER_CONFIG_INVALID "${PROD_ENV[@]}" "${DSN_ENV[@]}" -e UGENCE_REVIEW_DEPLOYMENT_MODE=staging "$IMAGE"

# ---- the positive run: hardened, private TLS listener, real PostgreSQL --------------
echo "== hardened positive run =="
docker run -d --name "$NAME" --network grw-bridge --ip "$BIND" \
  --user 10001:10001 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,nodev --tmpfs /var/lib/ugence-review:rw,noexec,nosuid,nodev \
  --pids-limit 256 --memory 1g --cpus 2 \
  "${PROD_ENV[@]}" "${DSN_ENV[@]}" -v "$CERTS":/run/secrets/tls:ro "$IMAGE" >/dev/null
probe() { docker run --rm --name grw-probe --network grw-bridge --entrypoint python "$IMAGE" -c "$1"; }
for _ in $(seq 1 60); do
  probe "import ssl,urllib.request,sys;c=ssl.create_default_context();c.check_hostname=False;c.verify_mode=ssl.CERT_NONE;urllib.request.urlopen('https://$BIND:$PORT/healthz',timeout=3,context=c)" >/dev/null 2>&1 && break
  sleep 1
done
docker inspect --format '{{.State.Status}}' "$NAME" | grep -q running || { echo "FAIL worker not running:"; docker logs "$NAME" | tail -n 20; exit 1; }

echo "== runtime hardening (live /proc) =="
[ "$(docker exec "$NAME" id -u):$(docker exec "$NAME" id -g)" = "10001:10001" ] || { echo FAIL uid/gid; exit 1; }
[ "$(docker exec "$NAME" cat /proc/1/status | awk '/NoNewPrivs/{print $2}')" = "1" ] || { echo FAIL NoNewPrivs; exit 1; }
for f in CapEff CapPrm CapBnd; do
  v="$(docker exec "$NAME" cat /proc/1/status | awk -v k="$f:" '$1==k{print $2}')"
  [ "$v" = "0000000000000000" ] || { echo "FAIL $f=$v"; exit 1; }
done
docker exec "$NAME" sh -c 'echo x > /root-probe' 2>/dev/null && { echo FAIL root fs writable; exit 1; } || true
docker exec "$NAME" sh -c 'echo x > /tmp/probe && echo x > /var/lib/ugence-review/probe' || { echo FAIL approved paths not writable; exit 1; }
docker exec "$NAME" sh -c 'test ! -S /var/run/docker.sock' || { echo FAIL docker socket present; exit 1; }
docker exec "$NAME" sh -c 'ls /var/lib/ugence-review' | grep -q "approvals.sqlite3" || { echo FAIL stores not on the volume; exit 1; }
echo "OK uid/gid=10001:10001 NoNewPrivs=1 Cap{Eff,Prm,Bnd}=0 read-only-root stores-on-volume no-docker-sock"

echo "== private TLS listener (CR-3) =="
docker inspect --format '{{json .NetworkSettings.Ports}}' "$NAME" | grep -q 'null\|{}' || { echo "FAIL a port is published to the host"; exit 1; }
probe "import ssl,urllib.request;c=ssl.create_default_context();c.check_hostname=False;c.verify_mode=ssl.CERT_NONE;c.maximum_version=ssl.TLSVersion.TLSv1_1
try:
    urllib.request.urlopen('https://$BIND:$PORT/healthz',timeout=3,context=c); raise SystemExit('FAIL tls<=1.1 accepted')
except ssl.SSLError: print('OK tls<=1.1 rejected')"
probe "import urllib.request,urllib.error
try:
    urllib.request.urlopen('http://$BIND:$PORT/healthz',timeout=3); raise SystemExit('FAIL plaintext accepted')
except Exception as e: print('OK no plaintext listener:', type(e).__name__)"
probe "import ssl,json,urllib.request;c=ssl.create_default_context();c.check_hostname=False;c.verify_mode=ssl.CERT_NONE
h=json.load(urllib.request.urlopen('https://$BIND:$PORT/healthz',timeout=3,context=c)); assert h['status']=='ok' and h['maturity']=='REFERENCE_GRADE_SHADOW_ONLY', h
q=json.load(urllib.request.urlopen('https://$BIND:$PORT/review/queue',timeout=5,context=c)); assert q['entries']==[] and q['maturity']=='REFERENCE_GRADE_SHADOW_ONLY', q
print('OK healthz + empty queue over TLS on the private address')"

echo "== no DSN in logs or answers =="
LOGS="$(docker logs "$NAME" 2>&1)"
echo "$LOGS" | grep -Fq "$APP_DSN" && { echo FAIL app DSN in logs; exit 1; } || true
echo "$LOGS" | grep -Fq "$SYS_DSN" && { echo FAIL system DSN in logs; exit 1; } || true
echo "$LOGS" | grep -Eiq "postgresql(\+psycopg)?://[^ ]*:[^ @]+@" && { echo FAIL a credentialled DSN in logs; exit 1; } || true
echo "$LOGS" | grep -q "REFERENCE_GRADE_SHADOW_ONLY enforcement_enabled=False mode=production" || { echo FAIL startup line missing or mislabelled; exit 1; }
echo "OK no DSN in logs; startup line carries the maturity labels"

echo "== egress observation (CR-5: enforcement is platform configuration) =="
EXT=false; probe "import socket;socket.setdefaulttimeout(3);socket.create_connection(('1.1.1.1',443))" >/dev/null 2>&1 && EXT=true
python - "$EXT" <<'PY' > /tmp/grw-egress.json
import json,sys
json.dump({"schema":"runtime-egress.v1","deployment":"governed-runtime-worker","network_mode":"user-defined bridge (needed for the runner's PostgreSQL)",
 "enforcement":"NONE IN THIS GATE: the worker's allowlist (JWKS host only) is platform configuration outside the image, recorded as EXTERNAL_DEPLOYMENT_EVIDENCE (CR-5)",
 "observation":{"external_tcp_connect_1.1.1.1_443_succeeded": sys.argv[1]=="true","attempted_destinations":["1.1.1.1:443 (probe)"]},
 "verdict":"OBSERVED_ONLY; not a claim of egress control"}, open("/tmp/grw-egress.json","w"), indent=2)
print("egress observation written")
PY
cp /tmp/grw-egress.json "${EVIDENCE_DIR:?EVIDENCE_DIR must be set}/runtime-egress-report.json"
echo "OK egress observed and recorded as external evidence (external reachable: $EXT)"
echo "ALL WORKER RUNTIME GATES PASSED for $IMAGE"
