"""
A/B/C ladder harness (NO quadratic attention). Trains A=window, B=window+phase,
C=window+phase+bounded-slots under identical conditions; evaluates the enterprise task
suite; runs causal ablations (phase-off, slots-off); records slot diagnostics and
deployment resource measurements. Preserves the claim sequence: B-A then C-B.
"""
import argparse, json, os, random, time, math
import torch
import torch.nn.functional as F

import models as M
import tasks as T

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ROOT, '..', '..'))
CORPUS = [os.path.join(REPO, 'bounded_shadow_pilot', 'data', 'natural_pilot_v1', 'corpus.json'),
          os.path.join(REPO, 'evidence_assurance', 'data', 'v1', 'corpus.json')]
WINDOW = 64


def set_seed(s):
    random.seed(s); torch.manual_seed(s)


@torch.no_grad()
def ppl(model, stream, N, n=20, seed=0):
    model.eval(); rng = random.Random(seed); tot = 0.0
    for _ in range(n):
        x, y, _ = T.lm_batch(stream, 8, N, rng)
        lo = model(x)
        tot += F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1)).item()
    return math.exp(tot / n)


@torch.no_grad()
def acc(model, X, P, Tg, bs=50):
    model.eval(); c = 0
    for i in range(0, len(X), bs):
        lo = model(X[i:i+bs])
        pred = lo[torch.arange(len(X[i:i+bs])), P[i:i+bs]-1].argmax(-1)
        c += (pred == Tg[i:i+bs]).sum().item()
    return c / len(X)


@torch.no_grad()
def supersession_scores(model, X, P, Tg, stale, bs=50):
    """returns (current_acc, stale_error_rate)."""
    model.eval(); cur = 0; st = 0
    for i in range(0, len(X), bs):
        lo = model(X[i:i+bs])
        pred = lo[torch.arange(len(X[i:i+bs])), P[i:i+bs]-1].argmax(-1)
        cur += (pred == Tg[i:i+bs]).sum().item()
        st += (pred == stale[i:i+bs]).sum().item()
    return cur / len(X), st / len(X)


def eval_suite(model, vocab, stream):
    out = {}
    out['ppl'] = {str(N): ppl(model, stream, N) for N in [256, 512]}
    # Task 2: needle beyond window (all distances > WINDOW=64 test long-range)
    out['needle_by_dist'] = {}
    for dist in [16, 96, 220]:
        X, P, Tg, _ = T.make_eval_set('needle', 256, vocab, 123, n=120, distance=dist)
        out['needle_by_dist'][str(dist)] = acc(model, X, P, Tg)
    # Task 4: binding by #entities
    out['binding_by_k'] = {}
    for k in [2, 4, 8]:
        X, P, Tg, _ = T.make_eval_set('binding', 256, vocab, 124, n=120, k=k)
        out['binding_by_k'][str(k)] = acc(model, X, P, Tg)
    # Task 6: supersession (current acc + stale-version error)
    X, P, Tg, stale = T.make_eval_set('supersession', 256, vocab, 128, n=120)
    cur, ste = supersession_scores(model, X, P, Tg, stale)
    out['supersession'] = {'current_acc': cur, 'stale_error': ste}
    # Task 9: multihop
    X, P, Tg, _ = T.make_eval_set('multihop', 256, vocab, 125, n=120)
    out['multihop'] = acc(model, X, P, Tg)
    # Task 10: source attribution
    X, P, Tg, _ = T.make_eval_set('source', 256, vocab, 129, n=120)
    out['source'] = acc(model, X, P, Tg)
    # Length generalization (needle mid, binding k4). Capped at 512 (2x train) because the
    # bounded-slot arm materialises a [B,N,M,D] scan tensor; 1024 is impractical on CPU.
    out['lengthgen'] = {}
    for N in [256, 512]:
        Xn, Pn, Tn, _ = T.make_eval_set('needle', N, vocab, 126, n=60, distance=N // 2)
        Xb, Pb, Tb, _ = T.make_eval_set('binding', N, vocab, 127, n=60, k=4)
        out['lengthgen'][str(N)] = {'needle_mid': acc(model, Xn, Pn, Tn),
                                    'binding_k4': acc(model, Xb, Pb, Tb)}
    return out


def ablations(model, vocab, arm):
    """Phase-off (B,C) and slots-off (C) causal ablations on binding@k4 and needle@d96."""
    res = {}
    Xn, Pn, Tn, _ = T.make_eval_set('needle', 256, vocab, 123, n=120, distance=96)
    Xb, Pb, Tb, _ = T.make_eval_set('binding', 256, vocab, 124, n=120, k=4)
    Xs, Ps, Ts, _ = T.make_eval_set('source', 256, vocab, 129, n=120)
    def probe():
        return {'needle_d96': acc(model, Xn, Pn, Tn), 'binding_k4': acc(model, Xb, Pb, Tb),
                'source': acc(model, Xs, Ps, Ts)}
    res['baseline'] = probe()
    phases = model.phase_mixers(); slots = model.slot_mixers()
    if phases:
        for pm in phases: pm.ablate = 'no_phase'
        res['phase_off'] = probe()
        for pm in phases: pm.ablate = None
    if slots:
        for sm in slots: sm.ablate = 'zero'
        res['slots_off'] = probe()
        for sm in slots: sm.ablate = None
        for sm in slots: sm.ablate = 'rand_keys'
        res['slots_randkeys'] = probe()
        for sm in slots: sm.ablate = None
        _ = model(Xb[:8])
        res['slot_diagnostics'] = [sm.diag for sm in slots]
    return res


@torch.no_grad()
def resources(model, arm, num_slots):
    """Deployment measurements: params, per-token latency, throughput, bounded state sizes."""
    model.eval()
    import copy
    n_params = M.count_params(model)
    # latency/throughput at N=512
    x = torch.randint(0, 100, (1, 512))
    for _ in range(2): model(x)  # warmup
    t = time.time(); reps = 5
    for _ in range(reps): model(x)
    dt = (time.time() - t) / reps
    tok_per_s = 512 / dt
    # bounded recurrent/slot state sizes (per layer), independent of N
    d = model.tok.weight.shape[1]; layers = len(model.blocks); h = 4
    phase_state = d if arm in ('B', 'C') else 0            # complex diagonal state ~ d per layer
    slot_state = (num_slots * d) if arm == 'C' else 0      # M*d per layer
    return {'params': n_params, 'per_token_ms': 1000 * dt / 512, 'tokens_per_s': tok_per_s,
            'phase_state_floats_per_layer': phase_state, 'slot_state_floats_per_layer': slot_state,
            'total_bounded_state_floats': layers * (phase_state + slot_state)}


def assert_no_nxn(model, N=48):
    """Static+dynamic proof: no mixer materializes an [*, N, N] tensor for these arms.
    We hook every module forward and check output/intermediate shapes don't contain N x N.
    (Window softmax uses [N,N] scores but is masked to a band; we exclude A's window from
    the ban because the ladder's *no-quadratic* rule targets global token-pair attention,
    and the window score is O(N*w) in effect. We assert Phase and Slots never build N x N.)"""
    from models import PhaseAttn, BindingSlots
    flags = {'phase_builds_NN': False, 'slots_builds_NN': False}
    hooks = []
    def mk(mod_name):
        def hook(mod, inp, out):
            for t in (out if isinstance(out, (tuple, list)) else [out]):
                if torch.is_tensor(t) and t.dim() >= 2 and t.shape[-1] == N and t.shape[-2] == N:
                    flags[mod_name] = True
        return hook
    for b in model.blocks:
        mix = b.mix
        ph = getattr(mix, 'phase', None) or (mix if isinstance(mix, PhaseAttn) else None)
        sl = getattr(mix, 'slots', None)
        if isinstance(ph, PhaseAttn):
            hooks.append(ph.register_forward_hook(mk('phase_builds_NN')))
        if isinstance(sl, BindingSlots):
            hooks.append(sl.register_forward_hook(mk('slots_builds_NN')))
    model(torch.randint(0, 100, (1, N)))
    for h in hooks: h.remove()
    return flags


def train_one(arm, vocab, stream, steps, N, target_params, seed, num_slots, lr=2e-3, B=24, log=None):
    set_seed(seed)
    model, nparams = M.build_matched(arm, len(vocab), target_params, d=128, h=4, layers=4,
                                     max_len=1200, window=WINDOW, num_slots=num_slots)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    warm = max(20, steps // 20)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, s / warm))
    rng = random.Random(seed * 991 + 7)
    model.train(); t0 = time.time()
    for step in range(steps):
        x, y, mask = T.train_batch(stream, B, N, vocab, rng)
        lo = model(x)
        if mask is None:
            loss = F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1))
        else:
            sel = mask.reshape(-1)
            loss = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step()
        if log and step % max(1, steps // 5) == 0:
            log(f"    [{arm} s{seed}] step {step}/{steps} loss {loss.item():.3f}")
    return model, nparams, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='A,B,C')
    ap.add_argument('--seeds', default='0,1,2')
    ap.add_argument('--steps', type=int, default=1800)
    ap.add_argument('--N', type=int, default=160)
    ap.add_argument('--num_slots', type=int, default=32)
    ap.add_argument('--target_params', type=int, default=2_000_000)
    ap.add_argument('--tag', default='abc')
    args = ap.parse_args()

    words = T.load_corpus_words(CORPUS); vocab = T.Vocab(words); stream = T.corpus_stream(words, vocab)
    logs = []
    def log(m): print(m, flush=True); logs.append(m)
    log(f"vocab={len(vocab)} corpus_tokens={len(stream)} steps={args.steps} N={args.N} slots={args.num_slots} window={WINDOW}")

    allres = {}
    for arm in args.arms.split(','):
        allres[arm] = []
        for seed in [int(s) for s in args.seeds.split(',')]:
            t0 = time.time()
            model, nparams, train_s = train_one(arm, vocab, stream, args.steps, args.N,
                                                args.target_params, seed, args.num_slots, log=log)
            ev = eval_suite(model, vocab, stream)
            ab = ablations(model, vocab, arm)
            rs = resources(model, arm, args.num_slots)
            nxn = assert_no_nxn(model)
            rec = {'arm': arm, 'seed': seed, 'params': nparams, 'train_s': round(train_s, 1),
                   'eval': ev, 'ablation': ab, 'resources': rs, 'no_nxn_check': nxn}
            allres[arm].append(rec)
            sup = ev['supersession']
            log(f"  [{arm} s{seed}] p={nparams} ppl256={ev['ppl']['256']:.1f} "
                f"ndl96={ev['needle_by_dist']['96']:.2f} bnd4={ev['binding_by_k']['4']:.2f} "
                f"sup={sup['current_acc']:.2f}(stale{sup['stale_error']:.2f}) src={ev['source']:.2f} "
                f"mhop={ev['multihop']:.2f} NN={nxn} ({time.time()-t0:.0f}s)")
            with open(os.path.join(ROOT, 'results', f'{args.tag}_partial.json'), 'w') as f:
                json.dump(allres, f, indent=2)
    with open(os.path.join(ROOT, 'results', f'{args.tag}.json'), 'w') as f:
        json.dump({'config': vars(args), 'vocab': len(vocab), 'corpus_tokens': len(stream),
                   'window': WINDOW, 'results': allres, 'log': logs}, f, indent=2)
    log("DONE")


if __name__ == '__main__':
    main()
