"""Meaningful numerical, integration and database checks. Uses a disposable DB."""
import json,math,os,tempfile,random
from pathlib import Path
from dataclasses import asdict
from thermovolt.core import Conditions,CoolingOptimizer,ThermalSimulator
from thermovolt.segment import CSegmentTree
from thermovolt import storage
optimizer=CoolingOptimizer();defaults=asdict(Conditions());result=optimizer.optimize(defaults)
assert result['feasible'];assert 400<=result['optimized']['reynolds']<=700
s=result['optimized'];assert s['end']['max']<=defaults['target'];assert s['end']['spread']<=defaults['spreadLimit']
# Every smaller permitted flow must fail at least one constraint.
c=Conditions();sim=ThermalSimulator()
for i in range(101):
 flow=10+i*.5
 if flow>=s['flow']:break
 if not 400<=sim.hydraulic(c,flow)['reynolds']<=700:continue
 lower=sim.simulate(c,flow);assert lower['end']['max']>c.target or lower['end']['spread']>c.spreadLimit
assert not optimizer.optimize({**defaults,'heat':14,'inlet':35,'ambient':45,'target':35})['feasible']
for bad in [{**defaults,'heat':float('nan')},{**defaults,'start':70},{**defaults,'target':True}]:
 try:optimizer.optimize(bad)
 except ValueError:pass
 else:raise AssertionError('Invalid input was accepted')
values=[random.Random(i).uniform(-20,70) for i in range(113)];tree=CSegmentTree(values)
for a,b in [(0,112),(0,0),(112,112),(3,57),(24,87)]:
 q=tree.query(a,b);selected=values[a:b+1];assert math.isclose(q['sum'],sum(selected));assert q['min']==min(selected);assert q['max']==max(selected);assert q['count']==len(selected)
try:tree.query(8,4)
except ValueError:pass
else:raise AssertionError('Bad C interval accepted')
tree.close()
with tempfile.TemporaryDirectory() as folder:
 storage.ROOT=Path(folder);(storage.ROOT/'sql').mkdir();(storage.ROOT/'sql/sqlite.sql').write_text((Path(__file__).parent/'sql/sqlite.sql').read_text());storage.POSTGRES=''
 import app as server
 client=server.app.test_client()
 assert client.get('/').status_code==200
 response=client.post('/api/optimize',json=defaults);assert response.status_code==200
 response=client.post('/api/interval',json={'start':0,'end':59});assert response.status_code==200;assert response.json['runtime'].startswith('C')
 assert client.post('/api/interval',json={'start':20,'end':3}).status_code==400
 eid=client.post('/api/experiments',json={'name':'Numerical test','conditions':defaults}).json['id']
 mid=client.post('/api/maintenance',json={'experimentId':eid,'title':'Inspect cooling','notes':'A test action'}).json['id']
 assert client.delete('/api/experiments',json={'id':eid}).status_code==409
 assert client.patch('/api/maintenance',json={'id':mid,'status':'closed'}).status_code==200
 assert client.patch('/api/maintenance',json={'id':mid,'status':'invalid'}).status_code==400
 assert client.get('/api/maintenance').json['maintenance'][0]['experiment_name']=='Numerical test'
 assert client.get('/api/database').json['summary']['total']==1
 try:
  with storage.connection() as conn:storage.execute(conn,"INSERT INTO experiments VALUES(?,?,?,?,?)",('rollback','Rollback','{}','{}','now'));raise ValueError('Intentional rollback')
 except ValueError:pass
 assert storage.fetch("SELECT COUNT(*) AS n FROM experiments WHERE id='rollback'")[0]['n']==0
 assert client.delete('/api/maintenance',json={'id':mid}).status_code==200
 assert client.delete('/api/experiments',json={'id':eid}).status_code==200
 assert client.get('/api/experiments').json['experiments']==[]
print(json.dumps({'status':'passed','checks':['thermal feasibility and optimal grid flow','infeasible and invalid inputs','C interval queries against direct results','Flask web and API routes','CRUD joins FK status constraint transaction rollback'],'defaultFlow':s['flow'],'defaultFinalMax':s['end']['max']}))
