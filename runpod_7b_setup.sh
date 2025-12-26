#!/bin/bash
# =============================================================================
# SymbolU 7B - RunPod Setup Script
# =============================================================================
#
# HARDWARE REQUIREMENTS:
#   Minimum: 1x A100 80GB ($1.89/hour on RunPod)
#   Recommended: 1x H100 80GB ($3.89/hour on RunPod)
#
# COST ESTIMATES:
#   Quick test (100 steps):  ~30 min = ~$1-2
#   Short training (1000 steps): ~4 hours = ~$8-15
#   Full training (50K steps): ~200 hours = ~$400-800
#
# USAGE:
#   1. Create RunPod pod with A100 80GB or H100 80GB
#   2. Clone repo: git clone https://github.com/rasaha/symbolu.git
#   3. Run: bash runpod_7b_setup.sh
#
# =============================================================================

set -e

echo "=============================================="
echo "   SymbolU 7B - RunPod Setup"
echo "=============================================="

# Check GPU
echo ""
echo "Checking GPU..."
nvidia-smi --query-gpu=name,memory.total --format=csv
echo ""

# Check if we have enough memory (need 80GB for 7B)
GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
echo "GPU Memory: ${GPU_MEM} MB"

if [ "$GPU_MEM" -lt 70000 ]; then
    echo ""
    echo "WARNING: GPU has less than 70GB memory!"
    echo "7B model requires A100 80GB or H100 80GB"
    echo "Continuing anyway (may OOM)..."
    echo ""
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers datasets tokenizers accelerate
pip install numpy tqdm

# Verify PyTorch
echo ""
echo "Verifying PyTorch CUDA..."
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"

# Create workspace
echo ""
echo "Setting up workspace..."
mkdir -p /workspace/checkpoints_7b
mkdir -p /workspace/logs

# Navigate to repo
cd /workspace
if [ ! -d "symbolu" ]; then
    echo "Cloning SymbolU repo..."
    git clone https://github.com/rasaha/symbolu.git
fi
cd symbolu

# Checkout the correct branch
git fetch origin claude/validate-phase-attention-dq2A5
git checkout claude/validate-phase-attention-dq2A5

echo ""
echo "=============================================="
echo "   Setup Complete!"
echo "=============================================="
echo ""
echo "QUICK COMMANDS:"
echo ""
echo "  # Quick test (100 steps, ~30 min, ~\$1-2)"
echo "  python train_7b.py --quick_test 2>&1 | tee /workspace/logs/7b_quick.log"
echo ""
echo "  # Short training (1000 steps, ~4 hours, ~\$8-15)"
echo "  python train_7b.py --steps 1000 --checkpoint_dir /workspace/checkpoints_7b 2>&1 | tee /workspace/logs/7b_1000.log"
echo ""
echo "  # With real data (WikiText)"
echo "  python train_7b.py --steps 1000 --dataset wikitext --checkpoint_dir /workspace/checkpoints_7b 2>&1 | tee /workspace/logs/7b_wiki.log"
echo ""
echo "=============================================="
echo ""
echo "MODEL INFO:"
echo "  - Parameters: ~7B"
echo "  - Architecture: SymbolU Unified"
echo "  - Phase Attention: O(n)"
echo "  - Bhava: 12x12 (144D)"
echo "  - BCVF: Trustworthiness"
echo ""
echo "GPU MEMORY USAGE (estimated):"
echo "  - Model: ~14GB (bf16)"
echo "  - Activations: ~20-40GB (with gradient checkpointing)"
echo "  - Optimizer: ~14GB"
echo "  - Total: ~50-70GB"
echo ""
