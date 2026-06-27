"""Critics: draft -> diagnosed flaw -> revision policy.

Every arm is the SAME pipeline (featurize draft -> fitted flaw classifier ->
policy) differing only in the FEATURIZER — isolating critic *content* from the
critique machinery. The classifier is a small logistic regression fit on a train
split of labeled drafts; diagnostic accuracy is measured on held-out drafts.

Featurizers (the arms):
  generic     — bag-of-words over the draft. Reads ALL content words; the strongest
                proxy for "LLM critiques itself" (semantic access). = generic
                self-refinement baseline.
  sentiment   — affect/style lexicon counts (escalation + speculation words).
  symbolu     — the real Symbol-U/PSE state vector of the draft (phonological).
  shuffled    — Symbol-U vectors with draft<->vector correspondence broken.
  relabeled   — Symbol-U vectors with dimensions permuted (ontology relabeling;
                a linear classifier is invariant to this -> should tie symbolu).
  random      — random feature vector (matched dim).

A correct diagnosis -> a policy that targets the real flaw; a wrong diagnosis ->
a mistargeted policy -> the reviser cannot fix the draft.
"""
from __future__ import annotations

from typing import Callable, Dict, List

import numpy as np

from .drafts import FLAWS, flaw_lexicons
from symbolu_neural.complementarity_probe.backends import get_backend

CRITICS = ["generic", "sentiment", "symbolu", "shuffled", "relabeled", "random"]

# flaw -> corrective policy flag the reviser understands
FLAW_TO_POLICY = {
    "speculative": "reduce_speculation",
    "escalated": "de_escalate",
    "verbose": "be_concise",
    "vague": "be_direct",
    "none": "noop",
}


# --------------------------------------------------------------------------- #
# Featurizers
# --------------------------------------------------------------------------- #
def _bow_featurizer(drafts: List[str]):
    vocab = sorted({w for d in drafts for w in d.lower().split()})
    idx = {w: i for i, w in enumerate(vocab)}

    def f(text: str) -> np.ndarray:
        v = np.zeros(len(vocab))
        for w in text.lower().split():
            if w in idx:
                v[idx[w]] += 1.0
        n = v.sum()
        return v / n if n else v
    return f, len(vocab)


def _sentiment_featurizer():
    lex = flaw_lexicons()
    keys = list(lex.keys())

    def f(text: str) -> np.ndarray:
        t = text.lower()
        v = np.array([sum(1 for w in lex[k] if w in t) for k in keys], dtype=float)
        n = v.sum()
        return v / n if n else v
    return f, len(keys)


def _symbolu_featurizer(u_backend: str = "pse_meaning"):
    b = get_backend(u_backend)
    return (lambda text: np.asarray(b.encode(text), dtype=float)), b.dim


# --------------------------------------------------------------------------- #
# Tiny multinomial logistic regression (no sklearn)
# --------------------------------------------------------------------------- #
class _LogReg:
    def __init__(self, n_classes: int, l2: float = 1e-2):
        self.n_classes, self.l2 = n_classes, l2
        self.W = self.b = None

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 300):
        import torch
        Xt = torch.tensor(X, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.long)
        W = torch.zeros(X.shape[1], self.n_classes, requires_grad=True)
        b = torch.zeros(self.n_classes, requires_grad=True)
        opt = torch.optim.LBFGS([W, b], lr=0.5, max_iter=epochs, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            loss = torch.nn.functional.cross_entropy(Xt @ W + b, yt) + self.l2 * (W * W).sum()
            loss.backward()
            return loss
        opt.step(closure)
        self.W, self.b = W.detach().numpy(), b.detach().numpy()
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (X @ self.W + self.b).argmax(1)


# --------------------------------------------------------------------------- #
# Critic = featurizer + fitted classifier, producing a policy per draft
# --------------------------------------------------------------------------- #
class Critic:
    def __init__(self, name: str, feats: np.ndarray, labels: np.ndarray):
        self.name = name
        self.clf = _LogReg(len(FLAWS)).fit(feats, labels)

    def diagnose(self, feat_row: np.ndarray) -> str:
        return FLAWS[int(self.clf.predict(feat_row[None, :])[0])]

    def policy(self, feat_row: np.ndarray) -> str:
        return FLAW_TO_POLICY[self.diagnose(feat_row)]


def build_feature_matrix(name: str, drafts: List[str], seed: int = 0):
    """Return (feature_matrix, featurizer_fn-or-None) for arm `name`."""
    rng = np.random.default_rng(seed)
    if name in ("generic",):
        f, _ = _bow_featurizer(drafts)
        return np.stack([f(d) for d in drafts]), f
    if name == "sentiment":
        f, _ = _sentiment_featurizer()
        return np.stack([f(d) for d in drafts]), f
    if name in ("symbolu", "shuffled", "relabeled"):
        f, dim = _symbolu_featurizer()
        M = np.stack([f(d) for d in drafts])
        if name == "shuffled":
            M = M[rng.permutation(len(M))]            # break draft<->vector link
            return M, None
        if name == "relabeled":
            p = rng.permutation(M.shape[1])
            return M[:, p], (lambda t, p=p, f=f: f(t)[p])
        return M, f
    if name == "random":
        dim = 16
        return rng.standard_normal((len(drafts), dim)), (lambda t, rng=rng: rng.standard_normal(dim))
    raise ValueError(name)
