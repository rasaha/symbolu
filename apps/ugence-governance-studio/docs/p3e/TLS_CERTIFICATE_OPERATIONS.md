# TLS Certificate Operations (P3E)

Operator supplies `UGENCE_STUDIO_TLS_CERT_FILE` and `UGENCE_STUDIO_TLS_KEY_FILE`. The
key must be readable by UID 10001 and mounted **read-only**; it is never copied into the
image. Startup fails closed on a missing/unreadable/mismatched/expired certificate.
TLS 1.2 is the minimum (1.0/1.1 disabled; 1.3 enabled). Subject and expiry are reported
in the startup log (no private material).

**Rotation**: place the new `server.crt`/`server.key` in the mounted TLS directory and
restart the container (`docker compose … up -d`). The integrity gate re-validates the new
material before binding. Keep overlapping validity windows to avoid downtime.
