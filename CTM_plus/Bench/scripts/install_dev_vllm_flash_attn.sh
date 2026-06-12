#!/usr/bin/env bash
# Install a freshly-built vllm_flash_attn wheel into venv-vllm's
# vendored slot at site-packages/vllm/vllm_flash_attn/.
#
# vLLM doesn't pip-install vllm_flash_attn — it vendors it inside
# the vllm package. So we extract the .so + .py files from the
# built wheel and copy them OVER the vendored copy.
#
# Backup of the original vendored copy must already exist at
# /workspace/dev/build-logs/vllm_flash_attn_vendored_backup (Phase 0
# creates this). If anything breaks, restore via the companion
# script restore_vendored_vllm_flash_attn.sh.
#
# Usage:
#     bash install_dev_vllm_flash_attn.sh [WHEEL_PATH]
#
# If WHEEL_PATH is omitted, picks the newest .whl in
# /workspace/dev/vllm-flash-attn-dev/dist/.

set -euo pipefail

WHEEL_PATH="${1:-}"
if [ -z "$WHEEL_PATH" ]; then
    WHEEL_PATH=$(ls -t /workspace/dev/vllm-flash-attn-dev/dist/*.whl 2>/dev/null | head -1)
fi
if [ -z "$WHEEL_PATH" ] || [ ! -f "$WHEEL_PATH" ]; then
    echo "ERROR: no wheel at $WHEEL_PATH" >&2
    exit 1
fi

# Locate the vendored slot from whichever python actually has vllm — venv OR
# system install (fresh pods may have no /workspace/venv-vllm at all). Override
# with FA_VENDORED=... if needed.
if [ -z "${FA_VENDORED:-}" ]; then
    for PYBIN in python3 python; do
        FA_VENDORED=$(command -v "$PYBIN" >/dev/null 2>&1 && "$PYBIN" -c \
            'import vllm, os; print(os.path.join(os.path.dirname(vllm.__file__), "vllm_flash_attn"))' \
            2>/dev/null) && [ -n "$FA_VENDORED" ] && break
    done
fi
if [ -z "${FA_VENDORED:-}" ] || [ ! -d "$FA_VENDORED" ]; then
    echo "ERROR: cannot locate the vendored vllm_flash_attn dir (is vllm importable" >&2
    echo "       from python3/python?). Set FA_VENDORED=... explicitly." >&2
    exit 1
fi
BACKUP_DIR=/workspace/dev/build-logs/vllm_flash_attn_vendored_backup
if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: backup dir $BACKUP_DIR missing — refuse to install without backup" >&2
    exit 1
fi

WORK=$(mktemp -d)
echo "Wheel:    $WHEEL_PATH"
echo "Vendored: $FA_VENDORED"
echo "Backup:   $BACKUP_DIR (exists)"
echo "Workdir:  $WORK"

unzip -q "$WHEEL_PATH" -d "$WORK"
echo ""
echo "=== wheel contents ==="
find "$WORK/vllm_flash_attn" -maxdepth 2 -type f | sort

# Sanity: the wheel must have both .so files + the Python wrapper.
for f in _vllm_fa2_C.abi3.so flash_attn_interface.py; do
    if [ ! -f "$WORK/vllm_flash_attn/$f" ]; then
        echo "ERROR: missing $f in wheel" >&2
        exit 1
    fi
done

echo ""
echo "=== sizes (new vs vendored) ==="
for f in _vllm_fa2_C.abi3.so _vllm_fa3_C.abi3.so flash_attn_interface.py __init__.py; do
    new_size=$(stat -c%s "$WORK/vllm_flash_attn/$f" 2>/dev/null || echo "MISSING")
    old_size=$(stat -c%s "$FA_VENDORED/$f" 2>/dev/null || echo "MISSING")
    printf "  %-32s new=%s vendored=%s\n" "$f" "$new_size" "$old_size"
done

echo ""
echo "=== copying into vendored dir ==="
for f in _vllm_fa2_C.abi3.so _vllm_fa3_C.abi3.so flash_attn_interface.py __init__.py; do
    if [ -f "$WORK/vllm_flash_attn/$f" ]; then
        cp -v "$WORK/vllm_flash_attn/$f" "$FA_VENDORED/$f"
    fi
done

# Drop stale .pyc files so Python doesn't pick up a cached interface.
rm -f "$FA_VENDORED/__pycache__"/*.pyc

echo ""
echo "=== verify install ==="
python3 -c "
import vllm.vllm_flash_attn as m
print('  module:', m.__file__)
print('  exported:', sorted(n for n in dir(m) if not n.startswith('_')))
"

echo ""
echo "Install complete. Run smoke tests next:"
echo "  bash smoke_test_fa_install.sh"

rm -rf "$WORK"
