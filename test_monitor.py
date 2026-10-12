"""Exercise the standalone monitoring workflow with disposable storage."""
from pathlib import Path
import tempfile
from thermovolt import storage
with tempfile.TemporaryDirectory() as directory:
    storage.ROOT=Path(directory);(storage.ROOT/'sql').mkdir();(storage.ROOT/'sql/sqlite.sql').write_text((Path(__file__).parent/'sql/sqlite.sql').read_text());storage.POSTGRES=''
    from app import app
    owner=app.test_client();other=app.test_client();sender=app.test_client()
    frame=dict(source='demo',temperature=48,cells=[47,48],soc=72,voltage=350,current=-80,ambient=30,flow=25,inlet=24,heat=7,pump=25,elapsed=20,scenario='test',coolingMode='auto')
    for _ in range(2):assert owner.post('/api/monitor',json={'frame':frame,'runId':'run'}).status_code==200
    result=owner.get('/api/alerts').json;assert len(result['history'])==2;assert len(result['alerts'])==1
    identity=result['alerts'][0]['id'];assert result['alerts'][0]['status']=='active'
    assert other.get('/api/alerts').json['history']==[]
    other.patch('/api/alerts',json={'id':identity});assert owner.get('/api/alerts').json['alerts'][0]['status']=='active'
    owner.patch('/api/alerts',json={'id':identity});owner.post('/api/monitor',json={'frame':frame,'runId':'run'});assert owner.get('/api/alerts').json['alerts'][0]['status']=='acknowledged'
    owner.post('/api/monitor',json={'frame':dict(frame,temperature=35,cells=[35,34]),'runId':'run'});assert owner.get('/api/alerts').json['alerts'][0]['status']=='resolved'
    payload=dict(temperature=38,soc=72,voltage=350,current=-80,ambient=30,cells=[37,38],flow=0,pump=25)
    assert sender.post('/api/monitor',json=payload).status_code==401
    token=owner.post('/api/connection').json['token'];headers={'Authorization':'Bearer '+token}
    assert sender.post('/api/monitor',json=payload,headers=headers).status_code==200
    assert owner.get('/api/monitor').json['frame']['forecast'] is None
    assert other.get('/api/monitor').json['frame'] is None
    assert sender.post('/api/monitor',json=dict(payload,soc=110),headers=headers).status_code==400
    owner.post('/api/connection');assert sender.post('/api/monitor',json=payload,headers=headers).status_code==401
print('PASS: Python model monitoring, alert lifecycle, workspace isolation, gateway validation, token rotation.')
