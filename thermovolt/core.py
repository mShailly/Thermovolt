"""Educational thermal model. Constants are assumptions, not physical validation."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json,math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
MODEL=json.loads((ROOT/'data/thermal-model.json').read_text())
BOUNDS={'start':(25,55),'heat':(2,14),'inlet':(15,35),'ambient':(20,45),'concentration':(0,3),'target':(35,50),'spreadLimit':(1,8),'fixedFlow':(10,60)}
@dataclass
class Conditions:
    start:float=38
    heat:float=7
    inlet:float=25
    ambient:float=32
    concentration:float=1
    target:float=45
    spreadLimit:float=5
    fixedFlow:float=30
    @classmethod
    def from_dict(cls,data):
        if not isinstance(data,dict):raise ValueError('Enter valid conditions.')
        for k,(low,high) in BOUNDS.items():
            v=data.get(k)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:raise ValueError(f'{k} must be between {low} and {high}.')
        return cls(**{k:data[k] for k in BOUNDS})
class ThermalSurrogate:
    def __init__(self):
        self.powers=np.array(MODEL['powers']);self.weights=np.array(MODEL['weights'])
    def predict(self,c,flow):
        raw=np.array([c.start,c.heat,c.inlet,c.ambient,flow,c.concentration])
        z=2*(raw-np.array(MODEL['lower']))/(np.array(MODEL['upper'])-np.array(MODEL['lower']))-1
        result=np.prod(z**self.powers,axis=1)@self.weights
        return {'temperature':float(result[0]),'spread':max(0,float(result[1]))}
class ThermalSimulator:
    def hydraulic(self,c,flow):
        rho=997*(1-c.concentration/100)+3970*c.concentration/100
        mu=.00089*(1+2.5*c.concentration/100);q=flow*1e-6/60;d=.001;length=.1
        pressure=128*mu*length*q/(math.pi*d**4);power=pressure*q*10/.35
        return {'reynolds':4*rho*q/(math.pi*mu*d),'pressure':pressure,'power':power,'energyWh':power*600/3600}
    def simulate(self,c,flow):
        g=[.015 if flow==0 else (.05+.48*(flow/20)**.55*(1+.04*c.concentration))*(1+.06*(i/9*2-1)) for i in range(10)]
        eq=[(c.heat*(1+.12*(i/9*2-1))+v*c.inlet+.04*c.ambient)/(v+.04) for i,v in enumerate(g)]
        series=[]
        for t in range(0,601,10):
            cells=[eq[i]+(c.start-eq[i])*math.exp(-(v+.04)*t/70) for i,v in enumerate(g)]
            series.append({'time':t,'cells':cells,'max':max(cells),'min':min(cells),'average':sum(cells)/10,'spread':max(cells)-min(cells)})
        return {'flow':flow,'series':series,'end':series[-1],'peak':max(s['max'] for s in series),'secondsAbove':10*sum(s['max']>c.target for s in series[1:]),**self.hydraulic(c,flow)}
class CoolingOptimizer:
    def __init__(self):self.simulator=ThermalSimulator();self.surrogate=ThermalSurrogate()
    def optimize(self,payload):
        c=Conditions.from_dict(payload);flows=[10+i*.5 for i in range(101) if 400<=self.simulator.hydraulic(c,10+i*.5)['reynolds']<=700]
        candidates=[(flow,self.surrogate.predict(c,flow)) for flow in flows]
        best=None
        for flow,p in candidates:
            if p['temperature']<=c.target and p['spread']<=c.spreadLimit:
                s=self.simulator.simulate(c,flow)
                if s['end']['max']<=c.target and s['end']['spread']<=c.spreadLimit:best=s;break
        for flow in flows:
            if best and flow>=best['flow']:break
            s=self.simulator.simulate(c,flow)
            if s['end']['max']<=c.target and s['end']['spread']<=c.spreadLimit:best=s;break
        feasible=best is not None
        if best is None:best=self.simulator.simulate(c,flows[-1])
        fixed=self.simulator.simulate(c,c.fixedFlow)
        return {'conditions':asdict(c),'optimized':best,'fixed':fixed,'off':self.simulator.simulate(c,0),'feasible':feasible,'prediction':self.surrogate.predict(c,best['flow']),'candidateCount':len(flows),'energySaving':(1-best['power']/fixed['power'])*100,'model':MODEL['metrics']}
