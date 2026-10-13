"""Verify admin authorization, dynamic registration, automatic feed and legacy accounts."""
from pathlib import Path
import tempfile,os,time,json
from thermovolt import storage
with tempfile.TemporaryDirectory() as directory:
    storage.ROOT=Path(directory);(storage.ROOT/'sql').mkdir()
    (storage.ROOT/'sql/sqlite.sql').write_text((Path(__file__).parent/'sql/sqlite.sql').read_text())
    storage.POSTGRES=''
    os.environ['ADMIN_USERNAME']='admin'
    os.environ['ADMIN_PASSWORD']='temporary-test-password'
    from app import app
    from thermovolt.fleet import start_fleet_stream
    admin=app.test_client();user=app.test_client()
    assert admin.get('/api/admin/vehicles').status_code==401
    assert admin.post('/api/admin/session',json={'username':'admin','password':'wrong'}).status_code==401
    assert admin.post('/api/admin/session',json={'username':'admin','password':os.environ['ADMIN_PASSWORD']}).status_code==200
    assert admin.get('/api/admin/vehicles').json['total']==5
    assert user.post('/api/local-auth',json={'vehicleId':'TV-URBAN-01','pin':'1842'}).status_code==200
    assert user.get('/api/admin/vehicles').status_code==401
    payload=dict(vehicleId='TV-NEW-06',pin='6732',owner='New Owner',name='City Two',model='Test EV',kind='family',scenario='coolant-leak',capacity=60,voltage=400,soh=95)
    assert user.post('/api/admin/vehicles',json=payload).status_code==401
    assert admin.post('/api/admin/vehicles',json=payload,headers={'Origin':'https://other.example'}).status_code==403
    created=admin.post('/api/admin/vehicles',json=payload);assert created.status_code==201,created.json
    assert created.json['vehicle']['id']=='TV-NEW-06'
    assert admin.post('/api/admin/vehicles',json=payload).status_code==409
    assert admin.post('/api/admin/vehicles',json={**payload,'vehicleId':'TV-BAD-07','capacity':-1}).status_code==400
    assert admin.get('/api/admin/vehicles').json['total']==6
    new=app.test_client()
    result=new.post('/api/local-auth',json={'vehicleId':'TV-NEW-06','pin':'6732'})
    assert result.status_code==200 and result.json['vehicle']['owner']=='New Owner'
    assert new.get('/api/fleet?vehicle=TV-URBAN-01').status_code==401
    start_fleet_stream(app);time.sleep(3.6);app.extensions['fleet_stream'].set()
    result=new.get('/api/fleet?vehicle=TV-NEW-06');assert result.status_code==200
    assert len(result.json['history'])>=2
    assert result.json['frame']['driveMode']=='coolant-leak'
    assert any(a['code']=='coolant' for a in result.json['alerts'])
    assert admin.get('/api/fleet?vehicle=TV-NEW-06').status_code==200
    listing=admin.get('/api/admin/vehicles').json
    assert all(r['readings']>=2 for r in listing['vehicles'])
    assert 'pin_hash' not in json.dumps(listing) and '6732' not in json.dumps(listing)
    with storage.connection() as conn:
        rows=storage.execute(conn,'SELECT pin_hash FROM fleet_users WHERE vehicle_id=?',('TV-NEW-06',)).fetchone()
        assert rows['pin_hash']!='6732'
    assert user.post('/api/local-auth',json={'vehicleId':'TV-URBAN-01','pin':'1842'}).status_code==200
    assert admin.delete('/api/admin/session').status_code==200
    assert admin.get('/api/admin/vehicles').status_code==401
print('PASS: admin password and authorization, original five accounts, atomic registration, duplicate/invalid input, six autonomous streams, new vehicle login/isolation, protected details, logout.')
