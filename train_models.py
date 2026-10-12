from pathlib import Path
import json,itertools
import numpy as np
ROOT=Path(__file__).resolve().parent
# Train a polynomial surrogate on a held-out, explicitly synthetic thermal dataset.
rng=np.random.default_rng(42)
lo=np.array([25,2,15,20,10,0.]);hi=np.array([55,14,35,45,60,3.]);x=rng.uniform(lo,hi,(10000,6));start,heat,inlet,ambient,flow,conc=x.T
factor=np.linspace(-1,1,10)
g=.05+.48*(flow[:,None]/20)**.55*(1+.04*conc[:,None])*(1+.06*factor)
h=heat[:,None]*(1+.12*factor)
G=g+.04;eq=(h+g*inlet[:,None]+.04*ambient[:,None])/G
end=eq+(start[:,None]-eq)*np.exp(-G*600/70)
y=np.c_[end.max(axis=1),np.ptp(end,axis=1)]
powers=[p for p in itertools.product(range(5),repeat=6) if sum(p)<=4]
z=2*(x-lo)/(hi-lo)-1
X=np.stack([np.prod(z**p,axis=1) for p in powers],axis=1)
w=np.linalg.lstsq(X[:8000],y[:8000],rcond=None)[0];pred=X[8000:]@w;err=pred-y[8000:]
metrics={'maeTemperature':float(np.abs(err[:,0]).mean()),'rmseTemperature':float(np.sqrt(np.mean(err[:,0]**2))),'maeSpread':float(np.abs(err[:,1]).mean()),'p99TemperatureError':float(np.quantile(np.abs(err[:,0]),.99)),'trainRows':8000,'testRows':2000,'r2Temperature':float(1-np.sum(err[:,0]**2)/np.sum((y[8000:,0]-y[8000:,0].mean())**2))}
model={'name':'Polynomial thermal surrogate','degree':4,'features':['start','heat','inlet','ambient','flow','concentration'],'lower':lo.tolist(),'upper':hi.tolist(),'powers':powers,'weights':w.tolist(),'metrics':metrics,'seed':42,'provenance':'Synthetic first-order ten-cell thermal model, 600-second horizon. Held-out simulation results; no physical validation.'}
json.dump(model,open(ROOT/'data/thermal-model.json','w'))
print(json.dumps({'model':metrics}))
