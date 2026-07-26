"""
Falsification harness: train matched arms, evaluate LM perplexity + long-context tasks,
run causal ablations and Phase-state diagnostics. Writes raw per-run JSON.

Micro-scale by hardware necessity (CPU-only, no GPU): d=128, 4 layers, ctx 256.
Per the investigation protocol this scale CANNOT yield a PROVEN verdict; it can yield
NOT SUPPORTED / FALSIFIED AT TESTED SCALE / PROVISIONALLY SUPPORTED (bounded).
"""
import argparse, json, os, random, time
import torch
import torch.nn.functional as F

import models as M
import tasks as T

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ROOT, '..', '..'))
CORPUS = [os.path.join(REPO, 'bounded_shadow_pilot', 'data', 'natural_pilot_v1', 'corpus.json'),
          os.path.join(REPO, 'evidence_assurance', 'data', 'v1', 'corpus.json')]


def set_seed(s):
    random.seed(s); torch.manual_seed(s)


@torch.no_grad()
def eval_ppl(model, stream, N, n=20, seed=0):
    model.eval(); rng = random.Random(seed); tot, cnt = 0.0, 0
    for _ in range(n):
        x, y, _ = T.lm_batch(stream, 8, N, rng)
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        tot += loss.item(); cnt += 1
    import math
    return math.exp(tot / cnt)


@torch.no_grad()
def eval_task(model, X, pos, tgt, bs=50):
    model.eval(); correct = 0
    for i in range(0, len(X), bs):
        xb = X[i:i+bs]; pb = pos[i:i+bs]; tb = tgt[i:i+bs]
        logits = model(xb)
        pred = logits[torch.arange(len(xb)), pb - 1].argmax(-1)
        correct += (pred == tb).sum().item()
    return correct / len(X)


@torch.no_grad()
def eval_perturb(model, vocab, N, seed=0, n=150):
    """Distant-evidence causal test: build needle, record pred; change the fact's value
    token; fraction where the prediction FOLLOWS the changed distant evidence."""
    model.eval(); rng = random.Random(seed); follow = 0
    S = vocab.stoi
    for _ in range(n):
        e = rng.choice(vocab.ent); v1 = rng.choice(vocab.val)
        v2 = rng.choice([x for x in vocab.val if x != v1])
        dist = rng.choice([16, 48, 96, 160])
        def build(v):
            fact = [S['the'], S['code'], S['for'], e, S['is'], v, S['.']]
            tail = [S['the'], S['code'], S['for'], e, S['is'], v]
            body = N - len(tail); gap = min(dist, body - len(fact))
            before = body - len(fact) - gap
            ids = T._filler(vocab, before, rng) + fact + T._filler(vocab, gap, rng) + tail
            ids = ids[:N]
            while len(ids) < N: ids = [vocab.pad] + ids
            return torch.tensor(ids)[None]
        x2 = build(v2)
        pred = model(x2)[0, N - 2].argmax().item()
        if pred == v2:
            follow += 1
    return follow / n


def train_one(arm, vocab, stream, steps, N, target_params, seed, lr=3e-3, B=16, log=None):
    set_seed(seed)
    model, nparams = M.build_matched(arm, len(vocab), target_params, d=128, h=4, layers=4, max_len=1200, window=64)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.1)
    rng = random.Random(seed * 991 + 7)
    model.train(); t0 = time.time()
    for step in range(steps):
        x, y, mask = T.train_batch(stream, B, N, vocab, rng)
        logits = model(x)
        if mask is None:
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        else:
            sel = mask.reshape(-1)
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1))[sel], y.reshape(-1)[sel])
        opt.zero_grad(); loss.backward()
        gnorm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0).item()
        opt.step(); sched.step()
        if log and step % max(1, steps // 5) == 0:
            log(f"    [{arm} s{seed}] step {step}/{steps} loss {loss.item():.3f} gnorm {gnorm:.2f}")
    train_s = time.time() - t0
    return model, nparams, train_s


def evaluate(model, vocab, stream, arm):
    out = {}
    # A. LM perplexity, in-distribution (256) and extrapolated (512, 1024)
    out['ppl'] = {str(N): eval_ppl(model, stream, N) for N in [256, 512]}
    # B. single-needle by distance (train len 256)
    out['needle_by_dist'] = {}
    for dist in [16, 96, 220]:
        X, P, Tg = T.make_eval_set('needle', 256, vocab, seed=123, n=150, distance=dist)
        out['needle_by_dist'][str(dist)] = eval_task(model, X, P, Tg)
    # C. binding by #entities
    out['binding_by_k'] = {}
    for k in [2, 4, 6]:
        X, P, Tg = T.make_eval_set('binding', 256, vocab, seed=124, n=150, k=k)
        out['binding_by_k'][str(k)] = eval_task(model, X, P, Tg)
    # D. multi-hop integration
    X, P, Tg = T.make_eval_set('multihop', 256, vocab, seed=125, n=150)
    out['multihop'] = eval_task(model, X, P, Tg)
    # E. length generalization (train 256 -> eval 512, 1024) for needle and binding
    out['lengthgen'] = {}
    for N in [256, 512, 1024]:
        Xn, Pn, Tn = T.make_eval_set('needle', N, vocab, seed=126, n=80, distance=N // 2)
        Xb, Pb, Tb = T.make_eval_set('binding', N, vocab, seed=127, n=80, k=4)
        out['lengthgen'][str(N)] = {
            'needle_mid': eval_task(model, Xn, Pn, Tn),
            'binding_k4': eval_task(model, Xb, Pb, Tb),
        }
    # F. distant-evidence causal follow rate
    out['perturb_follow'] = eval_perturb(model, vocab, 256)
    return out


def ablate_phase(model, vocab, arm):
    if arm not in ('P', 'PL'):
        return None
    res = {}
    X, P, Tg = T.make_eval_set('needle', 256, vocab, seed=123, n=200, distance=96)
    Xb, Pb, Tb = T.make_eval_set('binding', 256, vocab, seed=124, n=200, k=4)
    base_n = eval_task(model, X, P, Tg); base_b = eval_task(model, Xb, Pb, Tb)
    for mode in ['zero', 'shuffle_pos', 'no_phase']:
        for pm in model.phase_mixers():
            pm.ablate = mode
        res[mode] = {'needle_d96': eval_task(model, X, P, Tg),
                     'binding_k4': eval_task(model, Xb, Pb, Tb)}
        for pm in model.phase_mixers():
            pm.ablate = None
    res['baseline'] = {'needle_d96': base_n, 'binding_k4': base_b}
    # diagnostics from one forward
    _ = model(X[:8])
    diags = [pm.diag for pm in model.phase_mixers()]
    res['diagnostics'] = diags
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='Q,L,R,P,PL')
    ap.add_argument('--seeds', default='0,1,2')
    ap.add_argument('--steps', type=int, default=2500)
    ap.add_argument('--N', type=int, default=256)
    ap.add_argument('--target_params', type=int, default=2_000_000)
    ap.add_argument('--tag', default='run')
    args = ap.parse_args()

    words = T.load_corpus_words(CORPUS)
    vocab = T.Vocab(words)
    stream = T.corpus_stream(words, vocab)
    logs = []
    def log(m):
        print(m, flush=True); logs.append(m)
    log(f"vocab={len(vocab)} corpus_tokens={len(stream)} steps={args.steps} N={args.N}")

    arms = args.arms.split(','); seeds = [int(s) for s in args.seeds.split(',')]
    allres = {}
    for arm in arms:
        allres[arm] = []
        for seed in seeds:
            t0 = time.time()
            model, nparams, train_s = train_one(arm, vocab, stream, args.steps, args.N,
                                                 args.target_params, seed, log=log)
            ev = evaluate(model, vocab, stream, arm)
            ab = ablate_phase(model, vocab, arm)
            rec = {'arm': arm, 'seed': seed, 'params': nparams, 'train_s': round(train_s, 1),
                   'eval': ev, 'ablation': ab}
            allres[arm].append(rec)
            log(f"  [{arm} s{seed}] params={nparams} ppl256={ev['ppl']['256']:.1f} "
                f"needle96={ev['needle_by_dist']['96']:.2f} bind4={ev['binding_by_k']['4']:.2f} "
                f"mhop={ev['multihop']:.2f} follow={ev['perturb_follow']:.2f} ({time.time()-t0:.0f}s)")
            with open(os.path.join(ROOT, 'results', f'{args.tag}_partial.json'), 'w') as f:
                json.dump(allres, f, indent=2)
    with open(os.path.join(ROOT, 'results', f'{args.tag}.json'), 'w') as f:
        json.dump({'config': vars(args), 'vocab': len(vocab), 'corpus_tokens': len(stream),
                   'results': allres, 'log': logs}, f, indent=2)
    log("DONE")


if __name__ == '__main__':
    main()
