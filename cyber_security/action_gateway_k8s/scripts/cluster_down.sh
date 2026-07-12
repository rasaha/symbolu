#!/usr/bin/env bash
# Tear down the disposable control plane and wipe its state. Idempotent.
set -uo pipefail
BIN="${K8S_REF_BIN:-/opt/k8s-ref/bin}"
RUN="${K8S_REF_RUN:-/tmp/k8sref}"
pkill -f "$BIN/kube-apiserver" 2>/dev/null || true
pkill -f "$BIN/etcd" 2>/dev/null || true
sleep 1
rm -rf "$RUN/data" "$RUN/admin.kubeconfig"
echo "[cluster_down] stopped apiserver + etcd; wiped state" >&2
