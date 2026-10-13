"""Check pending registration, approval transactions, isolation, controls, history and chat."""
from pathlib import Path
import tempfile,os,json
from unittest.mock import patch
from thermovolt import storage
with tempfile.TemporaryDirectory() as directory:
    storage.ROOT=Path(directory);(storage.ROOT/'sql').mkdir()
    (storage.ROOT/'sql/sqlite.sql').write_text((Path(__file__).parent/'sql/sqlite.sql').read_text());storage.POSTGRES=''
    os.environ['ADMIN_USERNAME']='admin';os.environ['ADMIN_PASSWORD']='temporary-test-password'
    from app import app
    from thermovolt.fleet import advance_fleet
    from thermovolt.core import CoolingOptimizer
    admin=app.test_client();user=app.test_client()
    assert admin.post('/api/admin/session',json={'username':'admin','password':os.environ['ADMIN_PASSWORD']}).status_code==200
    payload=dict(vehicleId='TV-REQUEST-08',pin='8123',owner='Request Owner',name='Requested EV',model='Test SUV',kind='family',capacity=72,voltage=390,soh=95)
    created=user.post('/api/registration',json=payload);assert created.status_code==201,created.json
    token=created.json['token']
    assert user.post('/api/registration/status',json={'token':token}).json['status']=='pending'
    assert user.post('/api/local-auth',json={'vehicleId':payload['vehicleId'],'pin':'8123'}).status_code==401
    assert not storage.fetch('SELECT * FROM fleet_readings WHERE vehicle_id=?',(payload['vehicleId'],))
    listing=admin.get('/api/admin/requests').json['requests'];req=listing[0]
    assert 'pin_hash' not in json.dumps(listing) and '8123' not in json.dumps(listing)
    assert user.patch('/api/admin/requests',json={'requestId':req['id'],'action':'approve'}).status_code==401
    assert admin.patch('/api/admin/requests',json={'requestId':req['id'],'action':'approve','scenario':'coolant-leak'}).status_code==200
    assert admin.patch('/api/admin/requests',json={'requestId':req['id'],'action':'approve'}).status_code==409
    assert user.post('/api/registration/status',json={'token':token}).json['status']=='approved'
    assert user.post('/api/local-auth',json={'vehicleId':payload['vehicleId'],'pin':'8123'}).status_code==200
    advance_fleet(CoolingOptimizer(),force=True)
    assert user.get('/api/fleet?vehicle='+payload['vehicleId']).json['frame']['driveMode']=='coolant-leak'
    today=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%d')
    path='/api/history?vehicle='+payload['vehicleId']+'&start='+today+'&end='+today
    assert user.get(path).json['history']
    assert b'Timestamp_UTC' in user.get(path+'&format=csv').data
    assert user.get(path.replace(payload['vehicleId'],'TV-URBAN-01')).status_code==401
    with patch('thermovolt.assistant.ask_model',return_value='Cooling flow is below demand.') as mocked:
        chat=user.post('/api/chat',json={'vehicleId':payload['vehicleId'],'messages':[{'role':'user','content':'Explain my alerts'}]})
        assert chat.status_code==200;assert mocked.call_args[0][0]['latest']['vehicleId']==payload['vehicleId']
    assert user.post('/api/chat',json={'vehicleId':'TV-URBAN-01','messages':[{'role':'user','content':'Show data'}]}).status_code==401
    assert admin.patch('/api/admin/accounts',json={'vehicleId':payload['vehicleId'],'action':'toggle'}).status_code==200
    assert user.get('/api/fleet?vehicle='+payload['vehicleId']).status_code==401
    assert user.post('/api/local-auth',json={'vehicleId':payload['vehicleId'],'pin':'8123'}).status_code==403
    admin.patch('/api/admin/accounts',json={'vehicleId':payload['vehicleId'],'action':'toggle'})
    assert admin.patch('/api/admin/accounts',json={'vehicleId':payload['vehicleId'],'action':'reset-pin','pin':'9012'}).status_code==200
    assert user.post('/api/local-auth',json={'vehicleId':payload['vehicleId'],'pin':'8123'}).status_code==401
    assert user.post('/api/local-auth',json={'vehicleId':payload['vehicleId'],'pin':'9012'}).status_code==200
    other=user.post('/api/registration',json={**payload,'vehicleId':'TV-REJECT-09'})
    req=admin.get('/api/admin/requests').json['requests'][0]
    assert admin.patch('/api/admin/requests',json={'requestId':req['id'],'action':'reject','reason':'Missing details'}).status_code==200
    assert user.post('/api/registration/status',json={'token':other.json['token']}).json['status']=='rejected'
    assert len(admin.get('/api/admin/audit').json['events'])>=5
    assert user.get('/api/admin/audit').status_code==401
print('PASS: pending login blocked, approved login/feed, rejection status, private hashed PINs, idempotent approval, own-vehicle history/CSV/chat, suspension, reset and audit.')
