import random, torch, torch.nn.functional as F, sys
import models as M, tasks as T, harness as H
words=T.load_corpus_words(H.CORPUS); vocab=T.Vocab(words)
arm=sys.argv[1] if len(sys.argv)>1 else 'Q'
set_steps=2400
model,npar=M.build_matched(arm,len(vocab),2_000_000,d=128,h=4,layers=4,max_len=1200,window=64)
opt=torch.optim.AdamW(model.parameters(),lr=3e-3,weight_decay=0.01)
rng=random.Random(0); random.seed(0); torch.manual_seed(0)
Xe,Pe,Te=T.make_eval_set('needle',256,vocab,seed=123,n=150,distance=96)
Xb,Pb,Tb=T.make_eval_set('binding',256,vocab,seed=124,n=150,k=4)
def acc(X,P,Tg):
    model.eval()
    with torch.no_grad():
        pr=model(X)[torch.arange(len(X)),P-1].argmax(-1)
    model.train(); return (pr==Tg).float().mean().item()
for step in range(set_steps+1):
    # needle-heavy: 60% needle, 40% binding
    kind='needle' if rng.random()<0.6 else 'binding'
    xs,ys,ms=[],[],[]
    for _ in range(24):
        if kind=='needle': x,pos,tg=T.needle(256,vocab,rng)
        else: x,pos,tg=T.binding(256,vocab,rng,k=rng.choice([2,3,4]))
        y=x.clone(); y[:-1]=x[1:]; m=torch.zeros(256,dtype=torch.bool); m[pos-1]=True
        xs.append(x);ys.append(y);ms.append(m)
    x=torch.stack(xs);y=torch.stack(ys);m=torch.stack(ms)
    lo=model(x); sel=m.reshape(-1)
    loss=F.cross_entropy(lo.reshape(-1,lo.size(-1))[sel],y.reshape(-1)[sel])
    opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
    if step%400==0:
        print(f"{arm} step {step} loss {loss.item():.3f} needle96 {acc(Xe,Pe,Te):.2f} bind4 {acc(Xb,Pb,Tb):.2f}",flush=True)
