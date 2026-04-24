"""§4.4 HuggingFaceSource — real-model scaffold.

**Status.** Scaffold only. The class body is structurally complete
and reflects §2.3.4's KV-cache amortization and §2.7.2's fp32
boundary, but it has NOT been executed against a real model in
this environment (torch / transformers are not installed, and V1
targets Llama 3.1 8B which requires GPU). End-to-end verification
against an actual HuggingFace model is Phase 2's closing task and
is hard-gated on §0.6 rule 1 (autonomy N=26 confirmation) before
§6 benchmark execution.

**Design per §2.3.2 / §2.3.4.**

Initialization:
  1. Tokenize the prompt; push through `model.__call__` to obtain
     the prompt-final hidden state + KV cache.
  2. Run L-1 greedy speculative steps forward, accumulating logits
     and extending the KV cache, to seed the initial L-step
     lookahead window.

Per outer step (amortized, two forward passes):
  1. Call `commit(token_id)` with the token decided by the blend
     — not necessarily the source's own greedy argmax. Append to
     committed prefix; run one forward pass to advance the KV
     cache to the new "current position."
  2. Run one forward pass from the advanced position to extend
     the lookahead frontier by one, producing the new L-th
     speculative logit. The other L-1 speculative positions
     were already computed and remain in the KV cache.
  3. Stack the L positions into a (L, V) logit array; upcast to
     fp32; softmax along V; return `(probs, valid_mask)`.

Per §2.7.2, softmax + subsequent BCVF operations need fp32 for
the 2nd-difference cancellation; the forward pass runs in
fp16/bf16 and the boundary upcast happens inside `lookahead()`.

**What this class does NOT do** (by design):
  - No token sampling. §1.3 locked greedy; any temperature/top-k
    is out of scope for V1.
  - No cross-source KV sharing. Each HuggingFaceSource owns its
    own cache. Sharing across paraphrase variants is a V2
    optimization (§9).
  - No batching across outer steps. V1 streaming = T=1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

from .base import stable_softmax, truncating_valid_mask

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    import torch
    from transformers import PreTrainedModel, PreTrainedTokenizerBase


class HuggingFaceSource:
    """Wraps a HuggingFace causal LM into the §4.2 Source protocol.

    Import-level torch/transformers dependency is deferred to
    `__init__` so callers that only use `MockSource` never pay
    the ML-framework import cost, matching §2.8.1's discipline.
    """

    L: int
    vocab_size: int
    eos_token_id: Optional[int]

    def __init__(
        self,
        model: "PreTrainedModel",
        tokenizer: "PreTrainedTokenizerBase",
        prompt: str,
        L: int = 5,
        device: Optional[str] = None,
        max_vocab_size: Optional[int] = None,
    ) -> None:
        try:
            import torch  # noqa: F401 — runtime-only import
        except ImportError as exc:  # pragma: no cover — environment-dependent
            raise RuntimeError(
                "HuggingFaceSource requires `torch` and `transformers`. "
                "Install them or use MockSource for testing. "
                "See docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md §4.4."
            ) from exc

        if L < 3:
            raise ValueError("L >= 3 required for BCVF 2nd-difference stencil")

        self._model = model
        self._tokenizer = tokenizer
        self.L = L
        # config.vocab_size may be padded (e.g. Qwen-2.5-7B pads from
        # 151936 tokenizer vocab to 152064 model vocab — a multiple of
        # 128). max_vocab_size lets callers cap the effective V for
        # cross-model kernel compatibility (e.g. spec-dec's
        # target+draft pair where each model pads differently).
        config_vocab = int(getattr(model.config, "vocab_size", 0)) or (
            len(tokenizer)
        )
        if max_vocab_size is not None:
            if max_vocab_size < 1:
                raise ValueError("max_vocab_size must be >= 1")
            if max_vocab_size > config_vocab:
                raise ValueError(
                    f"max_vocab_size={max_vocab_size} exceeds model "
                    f"config.vocab_size={config_vocab}"
                )
            self.vocab_size = int(max_vocab_size)
            self._slice_vocab = (self.vocab_size < config_vocab)
        else:
            self.vocab_size = config_vocab
            self._slice_vocab = False
        self._full_vocab_size = config_vocab
        self.eos_token_id = getattr(tokenizer, "eos_token_id", None)
        self._device = device or str(next(model.parameters()).device)

        # State: KV cache + committed prefix + current L-step lookahead
        # logits. Initialized lazily on first `lookahead()` call so the
        # constructor is cheap and side-effect-free w.r.t. the model.
        self._committed_prefix_ids: List[int] = list(
            tokenizer.encode(prompt, add_special_tokens=True)
        )
        self._past_key_values = None
        self._lookahead_logits: Optional[np.ndarray] = None  # (L, V)
        self._lookahead_token_ids: Optional[np.ndarray] = None  # (L,)
        self._initialized = False

    # §4.2 protocol ------------------------------------------------- #

    def lookahead(self) -> Tuple[np.ndarray, np.ndarray]:
        if not self._initialized:
            self._initialize_lookahead()
        assert self._lookahead_logits is not None
        assert self._lookahead_token_ids is not None
        probs = stable_softmax(self._lookahead_logits, axis=-1)
        if self._slice_vocab:
            probs = probs[:, : self.vocab_size]
            # Renormalize per row so each position sums to 1 after
            # dropping the padded-tail dims. Numerically safe because
            # padded entries have near-zero mass (model rarely predicts
            # padded token IDs).
            probs = probs / probs.sum(axis=-1, keepdims=True)
        mask = truncating_valid_mask(
            self._lookahead_token_ids, self.eos_token_id, self.L
        )
        return probs, mask

    def commit(self, token_id: int) -> None:
        if not self._initialized:
            self._initialize_lookahead()
        self._committed_prefix_ids.append(int(token_id))
        # Amortization step 1: advance KV cache by the committed token
        # (one forward pass). Step 2: extend the lookahead frontier by
        # one position from the new position (one more forward pass).
        self._advance_one(int(token_id))
        self._extend_frontier()

    # Internal ------------------------------------------------------ #

    def _initialize_lookahead(self) -> None:
        """Prime the L-step lookahead from the prompt. See §4.4 docstring."""
        import torch  # local import per §2.8.1 discipline

        input_ids = torch.tensor(
            [self._committed_prefix_ids], device=self._device
        )
        with torch.inference_mode():
            out = self._model(input_ids=input_ids, use_cache=True)
        self._past_key_values = out.past_key_values
        # Start with the prompt-final logits at position 0 of the lookahead.
        step0_logits = out.logits[0, -1, :].to(torch.float32).cpu().numpy()
        # Internal storage uses the MODEL'S vocab (config.vocab_size),
        # which may exceed the effective `self.vocab_size` when a cap
        # is set. Slicing happens on output in `lookahead()`.
        self._lookahead_logits = np.zeros(
            (self.L, self._full_vocab_size), dtype=np.float32
        )
        self._lookahead_logits[0, :] = step0_logits
        self._lookahead_token_ids = np.zeros(self.L, dtype=np.int64)
        self._lookahead_token_ids[0] = int(np.argmax(step0_logits))

        # Greedy-extend L-1 more speculative positions.
        for i in range(1, self.L):
            self._greedy_step(i)

        self._initialized = True

    def _greedy_step(self, slot: int) -> None:
        """Run one greedy forward pass from `_past_key_values`, placing
        the resulting logits at `_lookahead_logits[slot]`."""
        import torch

        prev_token = int(self._lookahead_token_ids[slot - 1])
        input_ids = torch.tensor([[prev_token]], device=self._device)
        with torch.inference_mode():
            out = self._model(
                input_ids=input_ids,
                past_key_values=self._past_key_values,
                use_cache=True,
            )
        self._past_key_values = out.past_key_values
        logits = out.logits[0, -1, :].to(torch.float32).cpu().numpy()
        self._lookahead_logits[slot, :] = logits
        self._lookahead_token_ids[slot] = int(np.argmax(logits))

    def _advance_one(self, token_id: int) -> None:
        """Commit `token_id` into the KV cache (one forward pass)."""
        import torch

        input_ids = torch.tensor([[int(token_id)]], device=self._device)
        with torch.inference_mode():
            out = self._model(
                input_ids=input_ids,
                past_key_values=self._past_key_values,
                use_cache=True,
            )
        self._past_key_values = out.past_key_values
        # Shift the lookahead window left by one: positions 1..L-1 become
        # 0..L-2. The new frontier slot L-1 is filled by _extend_frontier.
        self._lookahead_logits = np.roll(self._lookahead_logits, -1, axis=0)
        self._lookahead_token_ids = np.roll(self._lookahead_token_ids, -1)
        # Replace the (now-stale) last row with the freshly-emitted-token
        # logits from the advance pass, which become the new position 0.
        new_step0 = out.logits[0, -1, :].to(torch.float32).cpu().numpy()
        self._lookahead_logits[0, :] = new_step0
        self._lookahead_token_ids[0] = int(np.argmax(new_step0))

    def _extend_frontier(self) -> None:
        """Fill the new frontier slot (L-1) by greedy-stepping from slot L-2."""
        self._greedy_step(self.L - 1)

    # §6.2 Phase 2 batched scoring ---------------------------------- #

    def score_teacher_forced(
        self, target_tokens  # np.ndarray | list[int]
    ) -> np.ndarray:
        """Single forward pass over (committed_prefix ⊕ target_tokens);
        return per-position probabilities for each target token.

        Returns: shape (K, V) fp64 where K = len(target_tokens).
            row k = p(· | committed_prefix ⊕ target[:k])

        This bypasses `lookahead()` + `commit()` entirely for the common
        case of scoring a fixed target sequence (§6.3 teacher-forcing).
        Cost: 1 forward pass, not K × (2 + speculation). ~15× speedup on
        scoring-dominated workloads.

        State: the source's `_committed_prefix_ids` is NOT mutated —
        caller's state is preserved. Useful for re-using one source
        across multiple candidate choices from the same prompt context.
        """
        import torch

        tgt = list(int(t) for t in target_tokens)
        if len(tgt) == 0:
            return np.zeros((0, self.vocab_size), dtype=np.float64)

        full_ids = list(self._committed_prefix_ids) + tgt
        input_ids = torch.tensor([full_ids], device=self._device)
        with torch.inference_mode():
            out = self._model(input_ids=input_ids, use_cache=False)
        # out.logits: (1, len(full_ids), V)
        # Position i's logits predict token i+1. For the k-th target
        # token (lives at index len(committed) + k in full_ids), the
        # predictive logits are at position len(committed) + k - 1.
        prompt_len = len(self._committed_prefix_ids)
        K = len(tgt)
        # Slice logits that predict target positions: indices
        # [prompt_len - 1, prompt_len - 1 + K) — K rows.
        start = prompt_len - 1
        assert start >= 0, (
            f"prompt_len={prompt_len}; source has no committed context. "
            "score_teacher_forced requires at least one prompt token."
        )
        logits_slice = out.logits[0, start : start + K, :].to(torch.float64)
        # Stable softmax → probabilities.
        shifted = logits_slice - logits_slice.amax(dim=-1, keepdim=True)
        exp = torch.exp(shifted)
        probs = exp / exp.sum(dim=-1, keepdim=True)
        probs_np = probs.cpu().numpy()
        if self._slice_vocab:
            probs_np = probs_np[:, : self.vocab_size]
            probs_np = probs_np / probs_np.sum(axis=-1, keepdims=True)
        return probs_np

    # §12.5 cross-layer logit-lens ----------------------------------- #

    def layer_lookahead(self) -> np.ndarray:
        """Per-layer next-token distributions at the current position.

        Runs one forward pass on the committed prefix with
        `output_hidden_states=True`. Each layer's hidden state at the
        last input position is projected through the output embedding
        matrix (logit lens; Nostalgebraist 2020), softmax-normalized,
        returning an ``(N_layers, V)`` array.

        Shape: ``N_layers = n_hidden_layers + 1`` in HuggingFace —
        entry 0 is the embedding layer, entries 1..N are transformer
        blocks. All share vocab size V.

        Cost: one full forward pass (no KV-cache reuse), so probe-time
        only — not for decoding hot paths.
        """
        import torch

        input_ids = torch.tensor(
            [self._committed_prefix_ids], device=self._device
        )
        with torch.inference_mode():
            out = self._model(
                input_ids=input_ids,
                output_hidden_states=True,
                use_cache=False,
            )

        # Output projection matrix (V, hidden_dim).
        lm_head = self._model.get_output_embeddings()
        W = lm_head.weight.to(torch.float32)

        per_layer = []
        for h in out.hidden_states:
            # h: (1, seq_len, hidden_dim). Last position's hidden state.
            h_last = h[0, -1, :].to(torch.float32)
            logits = (h_last @ W.t()).cpu().numpy()
            # Stable softmax
            shifted = logits - logits.max()
            exp = np.exp(shifted)
            per_layer.append(exp / exp.sum())
        arr = np.stack(per_layer, axis=0)  # (N_layers, full_vocab)
        if self._slice_vocab:
            arr = arr[:, : self.vocab_size]
            arr = arr / arr.sum(axis=-1, keepdims=True)
        return arr
