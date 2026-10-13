"""Database-backed vehicle profiles, shared by web workers and telemetry writer."""
import json
from datetime import datetime,timezone
from .storage import connection,execute,fetch

def seed_profiles(profiles,conditions):
    with connection() as conn:
        for identity,p in profiles.items():
            item={k:v for k,v in p.items() if k!='pin'}
            item.update(id=identity,owner=p['name'],scenario=conditions[identity],className={'TV-URBAN-01':'Compact city EV','TV-FAMILY-02':'Family SUV','TV-SPORT-03':'Electric sports coupe','TV-TRACK-04':'Track performance EV','TV-FLEET-05':'Electric delivery van'}[identity],accent='#0b88a1')
            execute(conn,'INSERT INTO fleet_profiles(vehicle_id,profile,created_at) VALUES(?,?,?) ON CONFLICT(vehicle_id) DO NOTHING',(identity,json.dumps(item),datetime.now(timezone.utc).isoformat()))

def all_profiles():return [json.loads(r['profile']) for r in fetch('SELECT profile FROM fleet_profiles ORDER BY created_at,vehicle_id')]
def get_profile(identity):
    rows=fetch('SELECT profile FROM fleet_profiles WHERE vehicle_id=?',(identity,))
    return json.loads(rows[0]['profile']) if rows else None
def public_profile(p):
    return dict(id=p['id'],name=p['name'],owner=p.get('owner',''),model=p['model'],className=p.get('className','Electric vehicle'),capacity=p['capacity'],nominalVoltage=p['voltage'],soh=p['soh'],baseSpeed=p['base_speed'],maxSpeed=p['max_speed'],baseTemp=p['base_temp'],cooling=p['cooling'],accent=p.get('accent','#0b88a1'),scenario=p['scenario'],active=p.get('active',True))
