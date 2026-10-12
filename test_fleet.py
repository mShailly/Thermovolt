"""Check automatic scenarios, autonomous writes, login and vehicle isolation."""
from pathlib import Path
import tempfile,time,json
from thermovolt import storage
from thermovolt.core import CoolingOptimizer
from thermovolt.fleet import derive,PROFILES,AUTOMATIC,advance_fleet,start_fleet_stream
with tempfile.TemporaryDirectory() as directory:
    storage.ROOT=Path(directory);(storage.ROOT/'sql').mkdir()
    (storage.ROOT/'sql/sqlite.sql').write_text((Path(__file__).parent/'sql/sqlite.sql').read_text());storage.POSTGRES=''
    from app import app
    advance_fleet(CoolingOptimizer(),force=True)
    credentials=[('TV-URBAN-01','1842'),('TV-FAMILY-02','2764'),('TV-SPORT-03','3907'),('TV-TRACK-04','4518'),('TV-FLEET-05','5683')]
    clients=[];alerting=0
    assert app.test_client().post('/api/local-auth',json={'vehicleId':'TV-URBAN-01','pin':'0000'}).status_code==401
    for vehicle_id,pin in credentials:
        client=app.test_client();assert client.post('/api/local-auth',json={'vehicleId':vehicle_id,'pin':pin}).status_code==200
        result=client.get('/api/fleet?vehicle='+vehicle_id);assert result.status_code==200
        frame=result.json['frame'];assert frame['driveMode']==AUTOMATIC[vehicle_id]
        alerting+=bool(frame['alerts']);clients.append(client)
        if vehicle_id=='TV-URBAN-01':assert not frame['alerts']
    assert alerting>=3
    assert clients[0].get('/api/fleet?vehicle=TV-FAMILY-02').status_code==401
    assert clients[0].post('/api/fleet',json={'vehicleId':'TV-URBAN-01','mode':'coolant-leak'}).status_code==405
    before=storage.fetch('SELECT vehicle_id,COUNT(*) AS n FROM fleet_readings GROUP BY vehicle_id')
    # No HTTP requests: a background thread must advance every vehicle.
    start_fleet_stream(app);time.sleep(3.5);app.extensions['fleet_stream'].set()
    after=storage.fetch('SELECT vehicle_id,COUNT(*) AS n FROM fleet_readings GROUP BY vehicle_id')
    counts={r['vehicle_id']:r['n'] for r in before}
    assert all(r['n']>counts[r['vehicle_id']] for r in after)
    assert len(after)==5
    optimizer=CoolingOptimizer()
    for vehicle_id,p in PROFILES.items():
        frame=None
        for _ in range(70):frame=derive({**p,'id':vehicle_id},frame,'auto',optimizer)
        if vehicle_id=='TV-URBAN-01':assert not frame['alerts']
        else:assert frame['alerts'],vehicle_id
    assert clients[0].delete('/api/local-auth').status_code==200
    assert clients[0].get('/api/fleet?vehicle=TV-URBAN-01').status_code==401
print('PASS: five assigned automatic scenarios, healthy city vehicle, four alerting vehicles, background writes without requests, login/isolation, sustained alerts.')
