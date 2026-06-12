#!/usr/bin/env bash
# Restore the original vendored vllm_flash_attn from the Phase 0
# backup. Use if a dev install breaks vLLM and we need to roll back.

set -euo pipefail

# Locate the vendored slot from whichever python actually has vllm (venv or
# system). Override with FA_VENDORED=... if needed.
if [ -z "${FA_VENDORED:-}" ]; then
    for PYBIN in python3 python; do
        FA_VENDORED=$(command -v "$PYBIN" >/dev/null 2>&1 && "$PYBIN" -c \
            'import vllm, os; print(os.path.join(os.path.dirname(vllm.__file__), "vllm_flash_attn"))' \
            2>/dev/null) && [ -n "$FA_VENDORED" ] && break
    done
fi
if [ -z "${FA_VENDORED:-}" ] || [ ! -d "$FA_VENDORED" ]; then
    echo "ERROR: cannot locate the vendored vllm_flash_attn dir. Set FA_VENDORED=..." >&2
    exit 1
fi
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
