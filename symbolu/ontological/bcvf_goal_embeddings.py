#!/usr/bin/env python3
"""
BCVF Goal Embedding Factory
=============================

Modular factory for constructing goal embeddings used in BCVF decoding.
Each strategy returns a [B, D] embedding tensor suitable for the backward
score computation in :class:`BCVFScoringModule`.

Strategies:

    ``lookahead``
        Oracle: mean-pool hidden states of future ground-truth tokens.
        Only valid for teacher-forced evaluation.

    ``prompt_mean``
        Mean-pool hidden states from the prompt prefix.

    ``random``
        Random Gaussian embedding (control baseline).

    ``instruction_only``
        Encode the instruction/task description and mean-pool.
        For instruction-following benchmarks.

    ``code_problem_only``
        Encode the problem description (docstring + signature) for
        code-generation benchmarks like HumanEval.

    ``retrieval_context``
        Encode a retrieved context passage and mean-pool.
        For retrieval-augmented generation benchmarks.

Usage::

    from symbolu.ontological.bcvf_goal_embeddings import GoalEmbeddingFactory

    factory = GoalEmbeddingFactory(model, tokenizer, device="cuda")
    goal = factory.build("instruction_only", text="Write a Python sort.")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

try:
    import torch
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

import numpy as np


# =========================================================================
# Goal Embedding Factory
# =========================================================================


class GoalEmbeddingFactory:
    """
    Factory that produces [B, D] goal embeddings from various sources.

    All strategies return a detached float32 tensor on the specified device.

    Args:
        model: Transformer model with a forward method returning hidden
               states (``output_hidden_states=True``).
        tokenizer: Corresponding tokenizer with ``.encode()``/``.decode()``.
        device: Torch device string (``"cpu"`` or ``"cuda"``).
    """

    STRATEGIES = (
        "lookahead",
        "prompt_mean",
        "random",
        "instruction_only",
        "code_problem_only",
        "retrieval_context",
    )

    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        device: str = "cpu",
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        strategy: str,
        *,
        # Common kwargs
        hidden_dim: Optional[int] = None,
        batch_size: int = 1,
        # Strategy-specific kwargs
        text: Optional[str] = None,
        hidden_states: Optional[Any] = None,
        future_token_ids: Optional[Any] = None,
        prompt_hidden_states: Optional[Any] = None,
        context_text: Optional[str] = None,
    ) -> Any:
        """
        Build a goal embedding using the specified strategy.

        Args:
            strategy: One of :attr:`STRATEGIES`.
            hidden_dim: Required for ``random``; inferred otherwise.
            batch_size: Batch size for the output tensor.
            text: Text input for ``instruction_only``, ``code_problem_only``.
            hidden_states: Pre-computed hidden states (for ``lookahead``).
            future_token_ids: Token IDs of future tokens (for ``lookahead``).
            prompt_hidden_states: Hidden states from prompt (for ``prompt_mean``).
            context_text: Retrieved passage text (for ``retrieval_context``).

        Returns:
            goal_embedding: [B, D] tensor.
        """
        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Available: {self.STRATEGIES}"
            )

        if strategy == "lookahead":
            return self._build_lookahead(
                hidden_states=hidden_states,
                future_token_ids=future_token_ids,
                batch_size=batch_size,
            )
        elif strategy == "prompt_mean":
            return self._build_prompt_mean(
                prompt_hidden_states=prompt_hidden_states,
                batch_size=batch_size,
            )
        elif strategy == "random":
            return self._build_random(
                hidden_dim=hidden_dim,
                batch_size=batch_size,
            )
        elif strategy == "instruction_only":
            return self._build_from_text(
                text=text,
                batch_size=batch_size,
            )
        elif strategy == "code_problem_only":
            return self._build_from_text(
                text=text,
                batch_size=batch_size,
            )
        elif strategy == "retrieval_context":
            return self._build_from_text(
                text=context_text,
                batch_size=batch_size,
            )
        else:
            raise ValueError(f"Unhandled strategy: {strategy}")

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _build_lookahead(
        self,
        hidden_states: Optional[Any] = None,
        future_token_ids: Optional[Any] = None,
        batch_size: int = 1,
    ) -> Any:
        """
        Oracle lookahead: mean-pool hidden states of future tokens.

        If ``hidden_states`` is provided directly as [B, T, D], mean-pool
        along the time axis.  Otherwise, run the model on ``future_token_ids``
        and pool the last hidden layer.
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        if hidden_states is not None:
            if not isinstance(hidden_states, torch.Tensor):
                hidden_states = torch.tensor(
                    hidden_states, dtype=torch.float32
                )
            if hidden_states.dim() == 3:
                return hidden_states.mean(dim=1).detach().to(self.device)
            elif hidden_states.dim() == 2:
                return hidden_states.detach().to(self.device)
            else:
                raise ValueError(
                    f"Expected 2D or 3D hidden_states, got {hidden_states.dim()}D"
                )

        if future_token_ids is not None and self.model is not None:
            if not isinstance(future_token_ids, torch.Tensor):
                future_token_ids = torch.tensor(
                    [future_token_ids], dtype=torch.long
                )
            if future_token_ids.dim() == 1:
                future_token_ids = future_token_ids.unsqueeze(0)

            future_token_ids = future_token_ids.to(self.device)
            with torch.no_grad():
                outputs = self.model(
                    future_token_ids, output_hidden_states=True
                )
                last_hidden = outputs.hidden_states[-1]  # [B, T, D]
                return last_hidden.mean(dim=1).detach()

        raise ValueError(
            "lookahead requires either hidden_states or "
            "future_token_ids + model"
        )

    def _build_prompt_mean(
        self,
        prompt_hidden_states: Optional[Any] = None,
        batch_size: int = 1,
    ) -> Any:
        """
        Mean-pool hidden states from the prompt prefix.

        ``prompt_hidden_states`` should be [B, T, D] or [T, D].
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        if prompt_hidden_states is None:
            raise ValueError("prompt_mean requires prompt_hidden_states")

        if not isinstance(prompt_hidden_states, torch.Tensor):
            prompt_hidden_states = torch.tensor(
                prompt_hidden_states, dtype=torch.float32
            )

        if prompt_hidden_states.dim() == 2:
            # [T, D] -> [1, D]
            return (
                prompt_hidden_states.mean(dim=0, keepdim=True)
                .detach()
                .to(self.device)
            )
        elif prompt_hidden_states.dim() == 3:
            # [B, T, D] -> [B, D]
            return (
                prompt_hidden_states.mean(dim=1).detach().to(self.device)
            )
        else:
            raise ValueError(
                f"Expected 2D or 3D prompt_hidden_states, "
                f"got {prompt_hidden_states.dim()}D"
            )

    def _build_random(
        self,
        hidden_dim: Optional[int] = None,
        batch_size: int = 1,
    ) -> Any:
        """Random Gaussian embedding (control baseline)."""
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        if hidden_dim is None:
            # Try to infer from model
            if self.model is not None:
                try:
                    hidden_dim = self.model.config.hidden_size
                except AttributeError:
                    pass
            if hidden_dim is None:
                raise ValueError(
                    "random strategy requires hidden_dim or a model "
                    "with config.hidden_size"
                )

        return torch.randn(batch_size, hidden_dim, device=self.device)

    def _build_from_text(
        self,
        text: Optional[str] = None,
        batch_size: int = 1,
    ) -> Any:
        """
        Encode text and mean-pool last hidden states.

        Used by ``instruction_only``, ``code_problem_only``, and
        ``retrieval_context`` strategies.
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        if text is None:
            raise ValueError("This strategy requires a text argument")

        if self.model is None or self.tokenizer is None:
            raise ValueError(
                "Model and tokenizer required for text-based strategies"
            )

        input_ids = self.tokenizer.encode(text, return_tensors="pt")
        if isinstance(input_ids, list):
            input_ids = torch.tensor([input_ids], dtype=torch.long)
        input_ids = input_ids.to(self.device)

        with torch.no_grad():
            outputs = self.model(input_ids, output_hidden_states=True)
            last_hidden = outputs.hidden_states[-1]  # [1, T, D]
            pooled = last_hidden.mean(dim=1)  # [1, D]

        if batch_size > 1:
            pooled = pooled.expand(batch_size, -1)

        return pooled.detach()

    # ------------------------------------------------------------------
    # Convenience: build from pre-computed embedding directly
    # ------------------------------------------------------------------

    @staticmethod
    def from_tensor(embedding: Any, device: str = "cpu") -> Any:
        """
        Wrap an existing embedding tensor, ensuring [B, D] shape.

        Args:
            embedding: Tensor or array-like of shape [D] or [B, D].
            device: Target device.

        Returns:
            [B, D] tensor on the specified device.
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        if not isinstance(embedding, torch.Tensor):
            embedding = torch.tensor(embedding, dtype=torch.float32)
        if embedding.dim() == 1:
            embedding = embedding.unsqueeze(0)
        return embedding.detach().to(device)


# =========================================================================
# Standalone helper: compute goal embedding from text without full factory
# =========================================================================


def compute_text_embedding(
    model: Any,
    tokenizer: Any,
    text: str,
    device: str = "cpu",
) -> Any:
    """
    Encode ``text`` with ``model`` and return mean-pooled [1, D] embedding.

    This is a lightweight helper that does not require instantiating the
    full :class:`GoalEmbeddingFactory`.
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required")

    input_ids = tokenizer.encode(text, return_tensors="pt")
    if isinstance(input_ids, list):
        input_ids = torch.tensor([input_ids], dtype=torch.long)
    input_ids = input_ids.to(device)

    with torch.no_grad():
        outputs = model(input_ids, output_hidden_states=True)
        last_hidden = outputs.hidden_states[-1]
        return last_hidden.mean(dim=1).detach()


# =========================================================================
# Simple cosine-similarity retriever for RAG benchmark
# =========================================================================


class SimpleRetriever:
    """
    Minimal cosine-similarity retriever for the RAG benchmark.

    Pre-computes embeddings for a corpus and retrieves the top-k most
    similar passages given a query embedding.

    Args:
        model: Transformer model for encoding.
        tokenizer: Corresponding tokenizer.
        device: Torch device.
    """

    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        device: str = "cpu",
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self.corpus_texts: List[str] = []
        self.corpus_embeddings: Optional[Any] = None

    def index(self, texts: Sequence[str]) -> None:
        """
        Build the retrieval index from a list of text passages.

        Each passage is encoded and mean-pooled to produce a [1, D]
        embedding.  All embeddings are stacked into [N, D].
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        self.corpus_texts = list(texts)
        embeddings = []

        for text in texts:
            emb = compute_text_embedding(
                self.model, self.tokenizer, text, self.device
            )
            embeddings.append(emb)

        self.corpus_embeddings = torch.cat(embeddings, dim=0)  # [N, D]

    def index_from_embeddings(
        self, texts: Sequence[str], embeddings: Any
    ) -> None:
        """
        Build index from pre-computed embeddings.

        Args:
            texts: List of passage strings.
            embeddings: [N, D] tensor of passage embeddings.
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        self.corpus_texts = list(texts)
        if not isinstance(embeddings, torch.Tensor):
            embeddings = torch.tensor(embeddings, dtype=torch.float32)
        if embeddings.dim() == 1:
            embeddings = embeddings.unsqueeze(0)
        self.corpus_embeddings = embeddings.to(self.device)

    def retrieve(
        self,
        query_embedding: Any,
        top_k: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k passages by cosine similarity.

        Args:
            query_embedding: [1, D] or [D] query tensor.
            top_k: Number of results to return.

        Returns:
            List of dicts with keys ``text``, ``score``, ``index``.
        """
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required")

        if self.corpus_embeddings is None or len(self.corpus_texts) == 0:
            return []

        if not isinstance(query_embedding, torch.Tensor):
            query_embedding = torch.tensor(
                query_embedding, dtype=torch.float32
            )
        if query_embedding.dim() == 1:
            query_embedding = query_embedding.unsqueeze(0)
        query_embedding = query_embedding.to(self.device)

        # Cosine similarity: [1, D] @ [D, N] -> [1, N]
        query_norm = F.normalize(query_embedding, dim=-1)
        corpus_norm = F.normalize(self.corpus_embeddings, dim=-1)
        scores = (query_norm @ corpus_norm.T).squeeze(0)  # [N]

        k = min(top_k, len(self.corpus_texts))
        top_scores, top_indices = torch.topk(scores, k)

        results = []
        for score, idx in zip(
            top_scores.tolist(), top_indices.tolist()
        ):
            results.append({
                "text": self.corpus_texts[idx],
                "score": score,
                "index": idx,
            })

        return results
