#!/usr/bin/env bash
# Fetch REAL public production traces for the cloud-controller Track-B replay.
#
# Writes full traces into data/cloud_traces/ (gitignored). Re-runnable; skips
# files already present. Only uses tools available in a minimal environment
# (git, gzip). The `.rar` Azure Functions trace is intentionally skipped (needs
# unrar, which is not assumed present).
#
# Sources (all public, citable):
#   - Azure Public Dataset  (CC-BY-4.0)  — github.com/Azure/AzurePublicDataset
#       * AzureLLMInferenceTrace_{conv,code}.csv  — real LLM inference arrivals
#       * vm-noise-data/*.csv                     — real noisy-neighbor throughput
#   - Alibaba / Google traces are NOT auto-fetched here: their data lives on
#     blob storage / GCS behind hosts that a locked-down egress policy blocks,
#     and the files are 10s-100s of GB. The adapters document how to obtain them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/data/cloud_traces"
mkdir -p "$DEST"

echo "==> Fetching Azure Public Dataset (shallow clone)…"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 --quiet https://github.com/Azure/AzurePublicDataset "$TMP/azure"

echo "==> Copying real LLM inference arrival traces…"
mkdir -p "$DEST/azure_llm"
for f in AzureLLMInferenceTrace_conv.csv AzureLLMInferenceTrace_code.csv; do
  if [ -f "$TMP/azure/data/$f" ]; then
    cp "$TMP/azure/data/$f" "$DEST/azure_llm/$f"
    echo "    $f  ($(wc -l < "$DEST/azure_llm/$f") rows)"
  fi
done
# Multimodal trace is gzipped (~8.5MB) — extract if gzip is available.
if [ -f "$TMP/azure/data/AzureLMMInferenceTrace_multimodal.csv.gz" ]; then
  gzip -dc "$TMP/azure/data/AzureLMMInferenceTrace_multimodal.csv.gz" \
    > "$DEST/azure_llm/AzureLMMInferenceTrace_multimodal.csv" 2>/dev/null \
    && echo "    AzureLMMInferenceTrace_multimodal.csv ($(wc -l < "$DEST/azure_llm/AzureLMMInferenceTrace_multimodal.csv") rows)" \
    || echo "    (skipped multimodal — gzip extract failed)"
fi

echo "==> Copying a sample of real VM-noise (noisy-neighbor) throughput series…"
mkdir -p "$DEST/azure_vm_noise"
# Copy up to 20 representative throughput CSVs (keeps the local set small).
find "$TMP/azure/vm-noise-data" -name '*.csv' | head -20 | while read -r vf; do
  base="$(echo "$vf" | sed 's#.*/vm-noise-data/##; s#/#__#g')"
  cp "$vf" "$DEST/azure_vm_noise/$base"
done
echo "    $(find "$DEST/azure_vm_noise" -name '*.csv' | wc -l) VM-noise CSVs"

echo ""
echo "Done. Real traces in: $DEST"
echo "Alibaba/Google traces (optional, large, gated egress):"
echo "  Alibaba microservices v2021: github.com/alibaba/clusterdata  (data on Alibaba cloud storage)"
echo "  Google Borg 2011/2019:       github.com/google/cluster-data  (data on GCS via gsutil)"
echo "Place them under $DEST/alibaba/ and $DEST/google/ to use those adapters."
