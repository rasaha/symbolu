"""Aggregate results/main.json into mean/std/per-seed tables + markdown summary."""
import json, os, math, statistics as st, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
tag = sys.argv[1] if len(sys.argv) > 1 else 'main'
data = json.load(open(os.path.join(ROOT, 'results', f'{tag}.json')))
R = data['results']
ARMS = list(R.keys())
NAME = {'Q': 'Q (softmax)', 'L': 'L (window)', 'R': 'R (gated-lin-rec)', 'P': 'P (phase)', 'PL': 'PL (phase+local)'}


def ms(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return (float('nan'), float('nan'))
    return (st.mean(vals), st.pstdev(vals) if len(vals) > 1 else 0.0)


def col(arm, path):
    out = []
    for rec in R[arm]:
        d = rec['eval']
        for k in path:
            d = d[k]
        out.append(d)
    return out


def fmt(m, s):
    return f"{m:.2f}±{s:.2f}"


lines = []
def P(x=''):
    lines.append(x)


P(f"# Results — {tag}\n")
P(f"Config: {data['config']}  ·  vocab={data['vocab']}  ·  corpus_tokens={data['corpus_tokens']}")
P(f"Params (arm→count): " + ", ".join(f"{a}={R[a][0]['params']}" for a in ARMS))
P(f"Train wall-s/run (mean): " + ", ".join(f"{a}={ms([r['train_s'] for r in R[a]])[0]:.0f}" for a in ARMS))
P()

# Perplexity
P("## Task 1 — LM perplexity (real English corpus), mean±sd over seeds")
P("| arm | ppl@256 (in-dist) | ppl@512 (extrap) |")
P("|---|---|---|")
for a in ARMS:
    P(f"| {NAME[a]} | {fmt(*ms(col(a,['ppl','256'])))} | {fmt(*ms(col(a,['ppl','512'])))} |")
P()

# Needle by distance
P("## Task 2 — single-needle accuracy by distance (chance≈0.02)")
dists = list(R[ARMS[0]][0]['eval']['needle_by_dist'].keys())
P("| arm | " + " | ".join(f"d={d}" for d in dists) + " |")
P("|---|" + "---|"*len(dists))
for a in ARMS:
    P(f"| {NAME[a]} | " + " | ".join(fmt(*ms(col(a,['needle_by_dist',d]))) for d in dists) + " |")
P()

# Binding by k
P("## Task 4 — entity–attribute binding accuracy by #entities (chance≈0.02)")
ks = list(R[ARMS[0]][0]['eval']['binding_by_k'].keys())
P("| arm | " + " | ".join(f"k={k}" for k in ks) + " |")
P("|---|" + "---|"*len(ks))
for a in ARMS:
    P(f"| {NAME[a]} | " + " | ".join(fmt(*ms(col(a,['binding_by_k',k]))) for k in ks) + " |")
P()

# Multihop + perturb
P("## Task 8 — multi-hop integration & distant-evidence causal follow-rate")
P("| arm | multihop acc | perturb-follow (reads distant evidence) |")
P("|---|---|---|")
for a in ARMS:
    P(f"| {NAME[a]} | {fmt(*ms(col(a,['multihop'])))} | {fmt(*ms(col(a,['perturb_follow'])))} |")
P()

# Length generalization
P("## Task (D) — length generalization (train ctx=256 → eval 256/512/1024)")
P("| arm | needle@256 | needle@512 | needle@1024 | bind@256 | bind@512 | bind@1024 |")
P("|---|---|---|---|---|---|---|")
for a in ARMS:
    row = [a]
    cells = []
    for metric in ['needle_mid','binding_k4']:
        for N in ['256','512','1024']:
            cells.append(fmt(*ms(col(a,['lengthgen',N,metric]))))
    P(f"| {NAME[a]} | " + " | ".join(cells) + " |")
P()

# Ablations (P, PL)
P("## Causal ablations on Phase arms (needle@d96 / binding@k4), mean over seeds")
P("| arm | baseline | phase→zero | state shuffle-pos | no-phase (angles=0) |")
P("|---|---|---|---|---|")
for a in ['P','PL']:
    if a not in R: continue
    def ab(mode, task):
        vals=[rec['ablation'][mode][task] for rec in R[a] if rec.get('ablation')]
        return ms(vals)
    bn=ab('baseline','needle_d96'); bz=ab('zero','needle_d96'); bs=ab('shuffle_pos','needle_d96'); bnp=ab('no_phase','needle_d96')
    P(f"| {NAME[a]} needle | {fmt(*bn)} | {fmt(*bz)} | {fmt(*bs)} | {fmt(*bnp)} |")
    bn=ab('baseline','binding_k4'); bz=ab('zero','binding_k4'); bs=ab('shuffle_pos','binding_k4'); bnp=ab('no_phase','binding_k4')
    P(f"| {NAME[a]} binding | {fmt(*bn)} | {fmt(*bz)} | {fmt(*bs)} | {fmt(*bnp)} |")
P()

# Per-seed raw dump (key metrics)
P("## Per-seed raw values (key metrics)")
P("| arm | seed | ppl256 | needle96 | bind4 | mhop | follow | ng@512 |")
P("|---|---|---|---|---|---|---|---|")
for a in ARMS:
    for rec in R[a]:
        e=rec['eval']
        P(f"| {a} | {rec['seed']} | {e['ppl']['256']:.1f} | {e['needle_by_dist']['96']:.2f} | "
          f"{e['binding_by_k']['4']:.2f} | {e['multihop']:.2f} | {e['perturb_follow']:.2f} | "
          f"{e['lengthgen']['512']['needle_mid']:.2f} |")
P()

md = "\n".join(lines)
open(os.path.join(ROOT, 'results', f'{tag}_tables.md'), 'w').write(md)
print(md)
