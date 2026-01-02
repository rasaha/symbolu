#!/usr/bin/env python3
"""
Needle in a Haystack Test for Phase Oscillator Memory

Hypothesis: Standard Transformers (with limited windows) fail to retrieve
information past their window. Decay-based RNNs (Mamba) struggle with
infinite duration. Phase Oscillators should preserve the signal forever
because cos(phi_t - phi_j) doesn't decay with distance.

This script trains a pure Phase model on a simple retrieval task:
- See a "key" token followed by a random "value" token early in the sequence
- Recall that value when seeing the "key" again at the end of the sequence

Success: Phase can hold information over thousands of tokens without decay.
Failure: The gradients vanish or the phase angles drift too much.
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from symbolu.phase_transformer import PhaseAttentionLayer

# --- Configuration ---
SEQ_LEN = 10000      # Length of the "Haystack" (10K stress test)
NEEDLE_POS = 50      # Where we hide the needle (early in sequence)
VOCAB_SIZE = 100     # Small vocab for clean signal
D_MODEL = 128        # Embedding dimension
N_HEADS = 4          # Number of attention heads
BATCH_SIZE = 32
EPOCHS = 10
LR = 1e-3


class HaystackDataset(Dataset):
    """
    Generate sequences with a "needle" (key-value pair) that must be recalled.

    Pattern:
        [noise...] [KEY=1] [VALUE=random] [noise...] [KEY=1] [?]
                                                              ↑
                                                     Predict VALUE here
    """
    def __init__(self, size=5000, seq_len=SEQ_LEN, needle_pos=NEEDLE_POS):
        self.size = size
        self.seq_len = seq_len
        self.needle_pos = needle_pos

    def __len__(self):
        return self.size

    def __getitem__(self, idx):
        # 1. Create Noise (Haystack) - avoid tokens 0, 1 (reserved)
        data = torch.randint(2, VOCAB_SIZE, (self.seq_len,))

        # 2. Insert Needle (The Signal)
        # KEY (Token 1) -> VALUE (random token 2-99)
        key_token = 1
        val_token = torch.randint(2, VOCAB_SIZE, (1,)).item()

        # Place Needle at needle_pos (early in sequence)
        data[self.needle_pos] = key_token
        data[self.needle_pos + 1] = val_token

        # 3. Ask Question at the end
        # Put KEY at second-to-last position, expect VALUE at last
        data[-2] = key_token
        data[-1] = val_token  # This is the target

        return data, val_token


class PurePhaseModel(nn.Module):
    """
    Minimal model with ONLY Phase attention - no quadratic, no windows.

    If this can recall the needle, Phase memory works over infinite distance.
    If this fails, Phase memory has practical limitations.
    """
    def __init__(self, vocab_size=VOCAB_SIZE, d_model=D_MODEL, n_heads=N_HEADS):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model)

        # Stack multiple Phase layers for depth
        self.phase_layers = nn.ModuleList([
            PhaseAttentionLayer(d_model, n_heads, aux_scale=1.0)  # Full scale (not auxiliary)
            for _ in range(3)
        ])

        # Output head
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size)

    def forward(self, x):
        # Embed tokens
        x = self.embed(x)  # [B, T, D]

        # Pure Phase Attention (No Windows, No Quadratic)
        for layer in self.phase_layers:
            x = layer(x)  # Each layer does: output + residual

        # Final norm and project to vocab
        x = self.norm(x)
        return self.head(x)  # [B, T, V]


def train():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    model = PurePhaseModel().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    dataset = HaystackDataset(size=5000)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    criterion = nn.CrossEntropyLoss()

    recall_distance = SEQ_LEN - NEEDLE_POS - 2

    print("=" * 60)
    print("NEEDLE IN A HAYSTACK TEST - Pure Phase Memory")
    print("=" * 60)
    print(f"Sequence Length:    {SEQ_LEN}")
    print(f"Needle Position:    {NEEDLE_POS}")
    print(f"Recall Distance:    {recall_distance} tokens")
    print(f"Model Params:       {sum(p.numel() for p in model.parameters()):,}")
    print(f"Random Baseline:    {100/VOCAB_SIZE:.1f}% (1/{VOCAB_SIZE})")
    print("=" * 60)

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        correct = 0
        total = 0

        for i, (data, target) in enumerate(loader):
            data = data.to(device)
            target = target.to(device)  # [B] - the value token to predict

            # Forward pass
            logits = model(data)  # [B, T, V]
            last_token_logits = logits[:, -1, :]  # [B, V] - predict last token

            loss = criterion(last_token_logits, target)

            optimizer.zero_grad()
            loss.backward()

            # Gradient clipping to prevent explosion
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

            optimizer.step()

            total_loss += loss.item()
            pred = last_token_logits.argmax(dim=-1)
            correct += (pred == target).sum().item()
            total += data.size(0)

            if i % 25 == 0:
                acc = correct / total if total > 0 else 0
                print(f"Epoch {epoch+1}/{EPOCHS} | Step {i:3d}/{len(loader)} | "
                      f"Loss: {loss.item():.4f} | Acc: {acc:.1%}")

        scheduler.step()

        epoch_acc = correct / total
        epoch_loss = total_loss / len(loader)

        print("-" * 60)
        if epoch_acc > 0.9:
            print(f"EPOCH {epoch+1} COMPLETE: Loss={epoch_loss:.4f} | Accuracy={epoch_acc:.1%}")
        elif epoch_acc > 0.5:
            print(f"EPOCH {epoch+1} COMPLETE: Loss={epoch_loss:.4f} | Accuracy={epoch_acc:.1%} (Learning!)")
        else:
            print(f"EPOCH {epoch+1} COMPLETE: Loss={epoch_loss:.4f} | Accuracy={epoch_acc:.1%} (Struggling)")
        print("-" * 60)

    # Final evaluation
    print("\n" + "=" * 60)
    print("FINAL EVALUATION")
    print("=" * 60)

    model.eval()
    correct = 0
    total = 0

    eval_dataset = HaystackDataset(size=1000)  # Fresh data
    eval_loader = DataLoader(eval_dataset, batch_size=BATCH_SIZE)

    with torch.no_grad():
        for data, target in eval_loader:
            data = data.to(device)
            target = target.to(device)

            logits = model(data)
            pred = logits[:, -1, :].argmax(dim=-1)
            correct += (pred == target).sum().item()
            total += data.size(0)

    final_acc = correct / total

    print(f"Recall Distance:    {recall_distance} tokens")
    print(f"Final Accuracy:     {final_acc:.1%}")
    print(f"Random Baseline:    {100/VOCAB_SIZE:.1f}%")
    print()

    if final_acc > 0.9:
        print("PHASE MEMORY WORKS!")
        print("Phase Oscillators successfully recalled information over "
              f"{recall_distance} tokens without decay.")
        print("This proves: 'Infinite-Context Recall in Linear Time'")
    elif final_acc > 0.5:
        print("PARTIAL SUCCESS")
        print(f"Phase shows {final_acc:.0%} recall - better than random but not perfect.")
        print("May need more layers, different initialization, or gradient improvements.")
    else:
        print("PHASE MEMORY FAILED")
        print(f"Accuracy ({final_acc:.1%}) is near random chance ({100/VOCAB_SIZE:.1f}%).")
        print("Possible causes: gradient vanishing, phase drift, or architectural issues.")

    print("=" * 60)

    return final_acc


if __name__ == "__main__":
    train()
