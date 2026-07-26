import random, torch, torch.nn.functional as F, sys, json
import models as M, tasks as T, harness as H
words=T.load_corpus_words(H.CORPUS); vocab=T.Vocab(words)
arm=sys.argv[1]; steps=int(sys.argv[2])
random.seed(2); torch.manual_seed(2)
model,npar=M.build_matched(arm,len(vocab),2_000_000,d=128,h=4,layers=4,max_len=1200,window=64)
opt=torch.optim.AdamW(model.parameters(),lr=2e-3,weight_decay=0.01)
rng=random.Random(2)
Xe,Pe,Te=T.make_eval_set('needle',160,vocab,seed=123,n=150,distance=96)
def acc():
    model.eval()
    with torch.no_grad(): pr=model(Xe)[torch.arange(len(Xe)),Pe-1].argmax(-1)
    model.train(); return (pr==Te).float().mean().item()
for s in range(steps+1):
    kind='needle' if rng.random()<0.55 else 'binding'
    xs,ys,ms=[],[],[]
    for _ in range(24):
        if kind=='needle': x,pos,tg=T.needle(160,vocab,rng)
        else: x,pos,tg=T.binding(160,vocab,rng,k=rng.choice([2,3,4]))
        y=x.clone();y[:-1]=x[1:];m=torch.zeros(160,dtype=torch.bool);m[pos-1]=True
        xs.append(x);ys.append(y);ms.append(m)
    x=torch.stack(xs);y=torch.stack(ys);m=torch.stack(ms)
    lo=model(x);sel=m.reshape(-1)
    loss=F.cross_entropy(lo.reshape(-1,lo.size(-1))[sel],y.reshape(-1)[sel])
    opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
    if s%500==0: print(f"{arm} step {s} loss {loss.item():.3f} needle96 {acc():.2f}",flush=True)
