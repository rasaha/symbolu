#!/usr/bin/env python3
"""T1 trainer scaffold — C×R×S LoRA/QLoRA SFT on Mistral. Pre-reg: docs/CG_TRAINING_CRS_MISTRAL_PREREG.md.

CPU-SAFE: `--dry-run` (default when no GPU) validates the config + dataset and prints the training plan
WITHOUT loading the model. Actual training requires `--execute` + a CUDA GPU + the cu121 stack
(transformers/peft/trl/bitsandbytes). The 32-D CG symbolic head is SCAFFOLDED but DISABLED (loss weight 0,
not instantiated) — enabling it requires a separate pre-registration (asserted in `t1_config`).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class T1Config:
    base_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    method: str = "qlora"                 # lora | qlora (4-bit)
    load_in_4bit: bool = True
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: tuple = ("q_proj", "k_proj", "v_proj", "o_proj")
    max_seq_len: int = 1024
    lr: float = 2e-4
    epochs: int = 3
    batch_size: int = 4
    grad_accum: int = 8
    seed: int = 0
    output_dir: str = "runs/cg_training/crs_lora"
    # --- T1 boundary flags (must stay False/0 — separate pre-reg required to change) ---
    enable_symbolic_head_32d: bool = False
    lambda_bhava: float = 0.0
    lambda_guna: float = 0.0
    lambda_vritti: float = 0.0
    lambda_kosha: float = 0.0

    def assert_t1_boundaries(self):
        assert not self.enable_symbolic_head_32d, "T1: 32-D symbolic head must be DISABLED"
        assert self.lambda_bhava == 0.0, "T1: no Bhava loss"
        assert self.lambda_guna == self.lambda_vritti == self.lambda_kosha == 0.0, \
            "T1: no Guna/Vritti/Kosha losses"


def t1_config(**over) -> T1Config:
    cfg = T1Config(**over)
    cfg.assert_t1_boundaries()
    return cfg


def _count_jsonl(p: Path) -> int:
    return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip()) if p.exists() else 0


def gpu_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:                                     # noqa: BLE001
        return False


_TRAIN_DEPS = ("transformers", "peft", "trl", "datasets", "accelerate", "bitsandbytes")


def missing_training_deps() -> list:
    import importlib.util
    return [m for m in _TRAIN_DEPS if importlib.util.find_spec(m) is None]


_INSTALL_HINT = ("pip install -r requirements-cg-training.txt   "
                 "# (after scripts/setup_runpod_phase2b.sh; do NOT reinstall torch)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="C×R×S LoRA SFT on Mistral (T1).")
    ap.add_argument("--data-dir", default="runs/cg_training/crs_sft")
    ap.add_argument("--output-dir", default="runs/cg_training/crs_lora")
    ap.add_argument("--base-model", default="mistralai/Mistral-7B-Instruct-v0.3")
    ap.add_argument("--method", choices=("lora", "qlora"), default="qlora")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--execute", action="store_true", help="actually train (needs CUDA + cu121 stack)")
    args = ap.parse_args(argv)

    cfg = t1_config(base_model=args.base_model, method=args.method, epochs=args.epochs,
                    output_dir=args.output_dir)
    data = Path(args.data_dir)
    n_train, n_val = _count_jsonl(data / "train.jsonl"), _count_jsonl(data / "val.jsonl")
    plan = {"config": asdict(cfg), "n_train": n_train, "n_val": n_val, "gpu": gpu_available()}

    if n_train < 2:
        print("CG_TRAINING_INSUFFICIENT_DATA"); return 1
    if not args.execute or not gpu_available():
        print("DRY-RUN (no training). " + ("GPU not available." if not gpu_available() else
              "pass --execute to train."))
        print(json.dumps(plan, indent=2))
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        (Path(args.output_dir) / "train_plan.json").write_text(json.dumps(plan, indent=2))
        return 0

    missing = missing_training_deps()
    if missing:                                           # clean stop, not a traceback mid-run
        print(f"CG_TRAINING_ENV_UNAVAILABLE: missing training deps {missing}")
        print(f"  fix: {_INSTALL_HINT}")
        return 1

    # ---- real training path (pod only) ----
    import torch  # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
    from peft import LoraConfig, get_peft_model
    from trl import SFTTrainer
    from datasets import load_dataset

    tok = AutoTokenizer.from_pretrained(cfg.base_model)
    if tok.pad_token is None:                              # Mistral has no pad token -> reuse EOS
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"                             # avoid half-precision overflow warning
    model_kw = {"load_in_4bit": True} if cfg.method == "qlora" else {}
    model = AutoModelForCausalLM.from_pretrained(cfg.base_model, device_map="auto", **model_kw)
    peft_cfg = LoraConfig(r=cfg.lora_r, lora_alpha=cfg.lora_alpha, lora_dropout=cfg.lora_dropout,
                          target_modules=list(cfg.target_modules), task_type="CAUSAL_LM")
    model = get_peft_model(model, peft_cfg)
    ds = load_dataset("json", data_files={"train": str(data / "train.jsonl"),
                                          "val": str(data / "val.jsonl")})

    def fmt(ex):
        return {"text": f"<s>[INST] {ex['prompt']} [/INST] {ex['target_answer']}</s>"}
    ds = ds.map(fmt)
    targs = TrainingArguments(output_dir=cfg.output_dir, num_train_epochs=cfg.epochs,
                              per_device_train_batch_size=cfg.batch_size,
                              gradient_accumulation_steps=cfg.grad_accum, learning_rate=cfg.lr,
                              bf16=True, logging_steps=10, save_strategy="epoch", seed=cfg.seed)
    SFTTrainer(model=model, tokenizer=tok, args=targs, train_dataset=ds["train"],
               eval_dataset=ds["val"], dataset_text_field="text",
               max_seq_length=cfg.max_seq_len).train()
    model.save_pretrained(cfg.output_dir)
    tok.save_pretrained(cfg.output_dir)
    print(f"crs-lora checkpoint -> {cfg.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
