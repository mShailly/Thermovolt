"""Pending public registration, admin approval and account activity records."""
import json,secrets,hashlib,os,re,uuid
from datetime import datetime,timezone
from flask import request,jsonify
from .storage import connection,execute,fetch,POSTGRES
from .registry import get_profile
from .admin import admin_allowed
def audit(conn,action,vehicle_id,detail=''):
    execute(conn,'INSERT INTO fleet_audit VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),os.environ.get('ADMIN_USERNAME','admin'),action,vehicle_id,detail,datetime.now(timezone.utc).isoformat()))
def prepare(p):
    identity=str(p.get('vehicleId','')).strip().upper();pin=str(p.get('pin',''))
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,39}',identity):raise ValueError('Use a vehicle ID with 3-40 letters, numbers, hyphens or underscores.')
    if not re.fullmatch(r'\d{4}',pin):raise ValueError('Choose a four-digit PIN.')
    text={key:str(p.get(key,'')).strip() for key in ['owner','name','model']}
    if any(not v or len(v)>80 for v in text.values()):raise ValueError('Owner, vehicle name and model are required, up to 80 characters each.')
    types={'city':('Compact city EV',42,135,31,.94),'family':('Family SUV',58,185,33,1.08),'sport':('Electric sports coupe',76,255,35,1.28),'track':('Track performance EV',94,305,37,1.48),'van':('Electric delivery van',48,150,34,1.14)}
    kind=p.get('kind','city')
    if kind not in types:raise ValueError('Choose a valid vehicle type.')
    nums={}
    for key,lo,hi in [('capacity',10,200),('voltage',100,1000),('soh',40,100)]:
        try:v=float(p.get(key))
        except (TypeError,ValueError):raise ValueError('Enter valid battery details.')
        if not lo<=v<=hi:raise ValueError(key+' is outside the allowed range.')
        nums[key]=v
    cl,speed,maxspeed,temp,cool=types[kind];salt=os.urandom(16)
    return dict(id=identity,**text,**nums,className=cl,base_speed=speed,max_speed=maxspeed,base_temp=temp,cooling=cool,accent='#0b88a1',scenario='normal',active=True),salt.hex(),hashlib.pbkdf2_hmac('sha256',pin.encode(),salt,200000).hex()
def register_registration(app):
    @app.post('/api/registration')
    def submit():
        p=request.get_json(silent=True) or {};profile,salt,digest=prepare(p)
        if get_profile(profile['id']) or fetch('SELECT id FROM fleet_requests WHERE vehicle_id=?',(profile['id'],)):return jsonify(error='This ID already has an account or registration request. Choose another ID.'),409
        token=secrets.token_urlsafe(32);now=datetime.now(timezone.utc).isoformat()
        try:
            with connection() as conn:execute(conn,'INSERT INTO fleet_requests VALUES(?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),profile['id'],json.dumps(profile),salt,digest,hashlib.sha256(token.encode()).hexdigest(),'pending','',now,None,None))
        except Exception:
            if fetch('SELECT id FROM fleet_requests WHERE vehicle_id=?',(profile['id'],)):return jsonify(error='This ID already has a request.'),409
            raise
        return jsonify(token=token,vehicleId=profile['id'],status='pending',message='Request submitted. Your login activates after administrator approval.'),201
    @app.post('/api/registration/status')
    def status():
        token=str((request.get_json(silent=True) or {}).get('token',''))
        rows=fetch('SELECT vehicle_id,status,reason,created_at,reviewed_at FROM fleet_requests WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
        return jsonify(rows[0]) if rows else (jsonify(error='Tracking code not found.'),404)
    @app.route('/api/admin/requests',methods=['GET','PATCH'])
    def requests():
        if not admin_allowed():return jsonify(error='Admin login required.'),401
        if request.method=='GET':
            rows=fetch('SELECT id,vehicle_id,profile,status,reason,created_at,reviewed_at FROM fleet_requests ORDER BY created_at DESC LIMIT 200')
            for row in rows:row['profile']=json.loads(row['profile'])
            return jsonify(requests=rows)
        p=request.get_json(silent=True) or {};action=p.get('action');scenario=p.get('scenario','normal')
        if action not in ['approve','reject']:raise ValueError('Choose approve or reject.')
        if scenario not in ['normal','hard-acceleration','high-speed','hot-weather','high-load','cell-hotspot','coolant-leak']:raise ValueError('Choose a valid automatic scenario.')
        reason=str(p.get('reason','')).strip()[:500]
        if action=='reject' and not reason:raise ValueError('Enter a rejection reason.')
        with connection() as conn:
            if not POSTGRES:conn.execute('BEGIN IMMEDIATE')
            row=execute(conn,'SELECT * FROM fleet_requests WHERE id=?'+(' FOR UPDATE' if POSTGRES else ''),(p.get('requestId',''),)).fetchone()
            if not row:return jsonify(error='Request not found.'),404
            if row['status']!='pending':return jsonify(error='This request was already reviewed.'),409
            now=datetime.now(timezone.utc).isoformat()
            if action=='approve':
                if execute(conn,'SELECT vehicle_id FROM fleet_users WHERE vehicle_id=?',(row['vehicle_id'],)).fetchone():return jsonify(error='This vehicle account already exists.'),409
                profile=json.loads(row['profile']);profile['scenario']=scenario
                execute(conn,'INSERT INTO fleet_users VALUES(?,?,?,?)',(row['vehicle_id'],row['pin_salt'],row['pin_hash'],now))
                execute(conn,'INSERT INTO fleet_profiles VALUES(?,?,?)',(row['vehicle_id'],json.dumps(profile),now))
                execute(conn,'UPDATE fleet_requests SET profile=? WHERE id=?',(json.dumps(profile),row['id']))
            execute(conn,'UPDATE fleet_requests SET status=?,reason=?,reviewed_at=?,reviewed_by=? WHERE id=?',('approved' if action=='approve' else 'rejected',reason,now,os.environ.get('ADMIN_USERNAME','admin'),row['id']))
            audit(conn,action,row['vehicle_id'],reason or scenario)
        return jsonify(ok=True)
    @app.route('/api/admin/accounts',methods=['PATCH'])
    def accounts():
        if not admin_allowed():return jsonify(error='Admin login required.'),401
        p=request.get_json(silent=True) or {};identity=str(p.get('vehicleId','')).upper();action=p.get('action')
        with connection() as conn:
            if not POSTGRES:conn.execute('BEGIN IMMEDIATE')
            row=execute(conn,'SELECT profile FROM fleet_profiles WHERE vehicle_id=?'+(' FOR UPDATE' if POSTGRES else ''),(identity,)).fetchone()
            if not row:return jsonify(error='Vehicle not found.'),404
            profile=json.loads(row['profile'])
            if action=='toggle':
                profile['active']=not profile.get('active',True);execute(conn,'UPDATE fleet_profiles SET profile=? WHERE vehicle_id=?',(json.dumps(profile),identity));label='reactivate' if profile['active'] else 'suspend'
            elif action=='reset-pin':
                pin=str(p.get('pin',''))
                if not re.fullmatch(r'\d{4}',pin):raise ValueError('Use a four-digit PIN.')
                salt=os.urandom(16);digest=hashlib.pbkdf2_hmac('sha256',pin.encode(),salt,200000).hex();execute(conn,'UPDATE fleet_users SET pin_salt=?,pin_hash=? WHERE vehicle_id=?',(salt.hex(),digest,identity));label='reset-pin'
            else:raise ValueError('Choose a valid account action.')
            execute(conn,'DELETE FROM fleet_sessions WHERE vehicle_id=?',(identity,));audit(conn,label,identity)
        return jsonify(ok=True)
    @app.get('/api/admin/audit')
    def activity():
        if not admin_allowed():return jsonify(error='Admin login required.'),401
        return jsonify(events=fetch('SELECT * FROM fleet_audit ORDER BY created_at DESC LIMIT 100'))
