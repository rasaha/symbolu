"""
Real-corpus tokenizer + language-rendered long-context task generators.

Corpus: the repo's enterprise English prose (evidence_assurance/data/v1/corpus.json,
~1 MB) provides real tokens for language-model perplexity and as natural distractor
filler for the evidence tasks. This is deliberately NOT a vocab_size=0 synthetic stream.

Task families are rendered as English word sequences with dedicated ENT*/VAL* symbol
tokens so exact-match retrieval/binding/integration is unambiguous:
  needle    : one fact at a controlled distance, prose distractors, exact-value recall
  binding   : K entity->value pairs (interference), recall one by query
  multihop  : A links B ; B has value V ; recall value reachable from A (2-hop chaining)
"""
import json
import re
import random
import torch

N_ENT = 24
N_VAL = 48
N_SRC = 12


def load_corpus_words(paths, max_words=400000):
    if isinstance(paths, str):
        paths = [paths]
    toks = []
    for path in paths:
        with open(path) as f:
            data = json.load(f)
        arts = data.get('artifacts', data.get('documents', [])) if isinstance(data, dict) else data
        for a in arts:
            if isinstance(a, dict):
                t = ' '.join(str(a.get(k, '')) for k in ('text', 'claim', 'rationale', 'gold_delivery'))
            else:
                t = str(a)
            for w in re.findall(r"[a-z]+|[.,]", t.lower()):
                toks.append(w)
                if len(toks) >= max_words:
                    return toks
    return toks


class Vocab:
    def __init__(self, corpus_words, top_k=1200):
        from collections import Counter
        c = Counter(corpus_words)
        common = [w for w, _ in c.most_common(top_k)]
        specials = ['<pad>', '<unk>']
        struct = ['the', 'code', 'for', 'is', 'vendor', 'limit', 'value', 'of',
                  'links', 'to', 'reachable', 'from', 'question', 'answer', '.', ',',
                  'now', 'current', 'amendment', 'source', 'per']
        ents = [f'ENT{i}' for i in range(N_ENT)]
        vals = [f'VAL{i}' for i in range(N_VAL)]
        srcs = [f'SRC{i}' for i in range(N_SRC)]
        words = []
        seen = set()
        for w in specials + struct + ents + vals + srcs + common:
            if w not in seen:
                seen.add(w); words.append(w)
        self.itos = words
        self.stoi = {w: i for i, w in enumerate(words)}
        self.pad = self.stoi['<pad>']; self.unk = self.stoi['<unk>']
        self.filler = [self.stoi[w] for w in common if w not in ('ENT', 'VAL')][:top_k]
        self.ent = [self.stoi[f'ENT{i}'] for i in range(N_ENT)]
        self.val = [self.stoi[f'VAL{i}'] for i in range(N_VAL)]
        self.src = [self.stoi[f'SRC{i}'] for i in range(N_SRC)]

    def __len__(self):
        return len(self.itos)

    def enc(self, ws):
        return [self.stoi.get(w, self.unk) for w in ws]


def corpus_stream(words, vocab):
    return torch.tensor([vocab.stoi.get(w, vocab.unk) for w in words], dtype=torch.long)


def lm_batch(stream, B, N, rng):
    idx = [rng.randint(0, len(stream) - N - 2) for _ in range(B)]
    x = torch.stack([stream[i:i + N] for i in idx])
    y = torch.stack([stream[i + 1:i + 1 + N] for i in idx])
    return x, y, None  # None -> full-sequence loss, no special answer position


def _filler(vocab, n, rng):
    return [vocab.filler[rng.randrange(len(vocab.filler))] for _ in range(n)]


def _place(seq_tokens, N, vocab, rng, tail):
    """Fill to length N: [filler ... inserted facts ... filler ... tail(query)].
    seq_tokens: list of (fact_token_list) to scatter. tail: query token list ending at
    the answer position. Returns ids[N], answer_pos, target."""
    tail_len = len(tail)
    body = N - tail_len
    # scatter facts among filler within `body`
    facts = list(seq_tokens)
    total_fact = sum(len(f) for f in facts)
    fill_budget = max(0, body - total_fact)
    # random gaps
    gaps = [rng.randrange(fill_budget + 1) for _ in range(len(facts) + 1)]
    s = sum(gaps) or 1
    gaps = [int(g * fill_budget / s) for g in gaps]
    ids = []
    ids += _filler(vocab, gaps[0], rng)
    for i, f in enumerate(facts):
        ids += f
        ids += _filler(vocab, gaps[i + 1], rng)
    ids = ids[:body]
    if len(ids) < body:
        ids += _filler(vocab, body - len(ids), rng)
    ids += tail
    ids = ids[:N]
    while len(ids) < N:
        ids = [vocab.pad] + ids
    answer_pos = N - 1
    target = tail[-1]
    # answer target is the LAST token; model predicts it from position N-2
    return torch.tensor(ids, dtype=torch.long), answer_pos, target


def needle(N, vocab, rng, distance=None):
    e = rng.choice(vocab.ent); v = rng.choice(vocab.val)
    S = vocab.stoi
    fact = [S['the'], S['code'], S['for'], e, S['is'], v, S['.']]
    tail = [S['the'], S['code'], S['for'], e, S['is'], v]  # predict v at end
    if distance is None:
        ids, pos, tgt = _place([fact], N, vocab, rng, tail)
        return ids, pos, tgt
    # distance = tokens between end-of-fact and start-of-tail (controls recall distance)
    body = N - len(tail)
    gap = min(distance, body - len(fact))
    before = body - len(fact) - gap
    ids = _filler(vocab, before, rng) + fact + _filler(vocab, gap, rng) + tail
    ids = ids[:N]
    while len(ids) < N:
        ids = [vocab.pad] + ids
    return torch.tensor(ids, dtype=torch.long), N - 1, tail[-1]


def binding(N, vocab, rng, k=4):
    S = vocab.stoi
    es = rng.sample(vocab.ent, k); vs = rng.sample(vocab.val, k)
    facts = [[S['vendor'], es[i], S['limit'], vs[i], S['.']] for i in range(k)]
    rng.shuffle(facts)
    j = rng.randrange(k)
    tail = [S['vendor'], es[j], S['limit'], vs[j]]
    ids, pos, tgt = _place(facts, N, vocab, rng, tail)
    return ids, pos, tgt


def multihop(N, vocab, rng, distractors=2):
    S = vocab.stoi
    a, b = rng.sample(vocab.ent, 2); v = rng.choice(vocab.val)
    f1 = [a, S['links'], S['to'], b, S['.']]
    f2 = [S['the'], S['value'], S['of'], b, S['is'], v, S['.']]
    facts = [f1, f2]
    # distractor links/values that must NOT be chained
    for _ in range(distractors):
        x, y2 = rng.sample(vocab.ent, 2); vv = rng.choice(vocab.val)
        facts.append([x, S['links'], S['to'], y2, S['.']])
        facts.append([S['the'], S['value'], S['of'], x, S['is'], vv, S['.']])
    rng.shuffle(facts)
    tail = [S['the'], S['value'], S['reachable'], S['from'], a, S['is'], v]
    ids, pos, tgt = _place(facts, N, vocab, rng, tail)
    return ids, pos, tgt


def supersession(N, vocab, rng, distractors=2):
    """Original value then a later amendment supersedes it; query the CURRENT value.
    Stale-version error = predicting the original value."""
    S = vocab.stoi
    e = rng.choice(vocab.ent); v_old, v_new = rng.sample(vocab.val, 2)
    original = [S['the'], S['limit'], S['for'], e, S['is'], v_old, S['.']]
    amend = [S['amendment'], S['the'], S['limit'], S['for'], e, S['is'], S['now'], v_new, S['.']]
    facts = [original, amend]  # keep order-independent via placement; amend is controlling
    for _ in range(distractors):
        e2 = rng.choice([x for x in vocab.ent if x != e]); vv = rng.choice(vocab.val)
        facts.append([S['the'], S['limit'], S['for'], e2, S['is'], vv, S['.']])
    rng.shuffle(facts)
    tail = [S['the'], S['current'], S['limit'], S['for'], e, S['is'], v_new]
    return _place(facts, N, vocab, rng, tail) + (v_old,)  # extra: stale target


def source(N, vocab, rng, distractors=3):
    """Each fact tagged with a source id; query which SOURCE stated a given entity's code."""
    S = vocab.stoi
    e = rng.choice(vocab.ent); v = rng.choice(vocab.val); s = rng.choice(vocab.src)
    fact = [S['per'], s, S['the'], S['code'], S['for'], e, S['is'], v, S['.']]
    facts = [fact]
    for _ in range(distractors):
        e2 = rng.choice([x for x in vocab.ent if x != e]); v2 = rng.choice(vocab.val)
        s2 = rng.choice([x for x in vocab.src if x != s])
        facts.append([S['per'], s2, S['the'], S['code'], S['for'], e2, S['is'], v2, S['.']])
    rng.shuffle(facts)
    tail = [S['the'], S['code'], S['for'], e, S['is'], S['per'], S['source'], s]
    return _place(facts, N, vocab, rng, tail)


def make_eval_set(kind, N, vocab, seed, n=200, **kw):
    """Returns (X, pos, target[, stale]) — stale only for supersession (else None)."""
    rng = random.Random(seed)
    xs, poss, tgts, stales = [], [], [], []
    for _ in range(n):
        stale = None
        if kind == 'needle':
            x, p, t = needle(N, vocab, rng, **kw)
        elif kind == 'binding':
            x, p, t = binding(N, vocab, rng, **kw)
        elif kind == 'multihop':
            x, p, t = multihop(N, vocab, rng, **kw)
        elif kind == 'source':
            x, p, t = source(N, vocab, rng, **kw)
        elif kind == 'supersession':
            x, p, t, stale = supersession(N, vocab, rng, **kw)
        xs.append(x); poss.append(p); tgts.append(t); stales.append(stale if stale is not None else -1)
    st = torch.tensor(stales)
    return torch.stack(xs), torch.tensor(poss), torch.tensor(tgts), (st if kind == 'supersession' else None)


ABC_MIX = (('lm', .2), ('needle', .2), ('binding', .2), ('supersession', .15),
           ('source', .15), ('multihop', .1))


def train_batch(stream, B, N, vocab, rng, mix=ABC_MIX):
    """Returns (x, y, mask). mask=None -> full-sequence LM loss. For task batches, mask
    selects ONLY the answer position (index pos-1) so the retrieval signal is not drowned
    by filler/LM tokens. This is answer-token supervision (a form of L_retrieval/L_binding/
    L_source/L_version), applied identically to every arm."""
    r = rng.random(); acc = 0; kind = 'lm'
    for k, p in mix:
        acc += p
        if r <= acc:
            kind = k; break
    if kind == 'lm':
        return lm_batch(stream, B, N, rng)
    xs, ys, ms = [], [], []
    for _ in range(B):
        if kind == 'needle':
            x, pos, tgt = needle(N, vocab, rng)
        elif kind == 'binding':
            x, pos, tgt = binding(N, vocab, rng, k=rng.choice([2, 3, 4]))
        elif kind == 'supersession':
            x, pos, tgt, _ = supersession(N, vocab, rng)
        elif kind == 'source':
            x, pos, tgt = source(N, vocab, rng)
        else:
            x, pos, tgt = multihop(N, vocab, rng)
        y = x.clone()
        y[:-1] = x[1:]; y[-1] = vocab.pad
        m = torch.zeros(N, dtype=torch.bool)
        m[pos - 1] = True   # supervise the token that predicts the answer value
        xs.append(x); ys.append(y); ms.append(m)
    return torch.stack(xs), torch.stack(ys), torch.stack(ms)
