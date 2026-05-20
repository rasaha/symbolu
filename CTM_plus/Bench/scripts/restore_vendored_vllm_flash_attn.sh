#!/usr/bin/env bash
# Restore the original vendored vllm_flash_attn from the Phase 0
# backup. Use if a dev install breaks vLLM and we need to roll back.

set -euo pipefail

FA_VENDORED=/workspace/venv-vllm/lib/python3.12/site-packages/vllm/vllm_flash_attn
BACKUP_DIR=/workspace/dev/build-logs/vllm_flash_attn_vendored_backup

if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: backup dir $BACKUP_DIR missing" >&2
    exit 1
fi

echo "Restoring from $BACKUP_DIR -> $FA_VENDORED"
for f in _vllm_fa2_C.abi3.so _vllm_fa3_C.abi3.so flash_attn_interface.py __init__.py; do
    if [ -f "$BACKUP_DIR/$f" ]; then
        cp -v "$BACKUP_DIR/$f" "$FA_VENDORED/$f"
    fi
done

rm -f "$FA_VENDORED/__pycache__"/*.pyc

echo ""
echo "Restore complete. Verify with:"
echo "  python3 -c 'import vllm.vllm_flash_attn as m; print(m.__file__)'"
