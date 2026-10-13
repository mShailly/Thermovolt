"""Password-protected administration and persistent vehicle registration."""
from datetime import datetime,timezone
import hashlib,hmac,json,os,re,secrets,time
from urllib.parse import urlparse
from flask import request,jsonify
from .storage import connection,execute,fetch
from .registry import all_profiles,get_profile,public_profile

def admin_allowed():
    rows=fetch('SELECT expires_at FROM fleet_admin_sessions WHERE id=?',(request.cookies.get('tv_admin_session',''),))
    return bool(rows and rows[0]['expires_at']>time.time())

def register_admin(app):
    def same_origin():
        origin=request.headers.get('Origin')
        return not origin or urlparse(origin).netloc==request.host

    @app.route('/api/admin/session',methods=['GET','POST','DELETE'])
    def session():
        if request.method=='GET':return (jsonify(ok=True,username=os.environ.get('ADMIN_USERNAME','admin')) if admin_allowed() else (jsonify(error='Admin login required.'),401))
        if not same_origin():return jsonify(error='Request origin is not allowed.'),403
        if request.method=='DELETE':
            with connection() as conn:execute(conn,'DELETE FROM fleet_admin_sessions WHERE id=?',(request.cookies.get('tv_admin_session',''),))
            response=jsonify(ok=True);response.delete_cookie('tv_admin_session');return response
        secret=os.environ.get('ADMIN_PASSWORD','')
        if len(secret)<10:return jsonify(error='Admin access is not configured. Set ADMIN_PASSWORD to at least 10 characters in server settings.'),503
        p=request.get_json(silent=True) or {}
        if not hmac.compare_digest(str(p.get('username','')).encode(),os.environ.get('ADMIN_USERNAME','admin').encode()) or not hmac.compare_digest(str(p.get('password','')).encode(),secret.encode()):return jsonify(error='Admin username or password is incorrect.'),401
        token=secrets.token_urlsafe(32);now=datetime.now(timezone.utc).isoformat()
        with connection() as conn:
            execute(conn,'DELETE FROM fleet_admin_sessions WHERE expires_at<?',(time.time(),))
            execute(conn,'INSERT INTO fleet_admin_sessions VALUES(?,?,?)',(token,time.time()+28800,now))
        response=jsonify(ok=True);response.set_cookie('tv_admin_session',token,max_age=28800,httponly=True,samesite='Strict',secure=request.is_secure or bool(os.environ.get('RENDER')));return response

    @app.route('/api/admin/vehicles',methods=['GET','POST'])
    def vehicles():
        if not admin_allowed():return jsonify(error='Admin login required.'),401
        if request.method=='GET':
            latest=fetch('SELECT vehicle_id,payload FROM fleet_readings r WHERE observed_at=(SELECT MAX(observed_at) FROM fleet_readings WHERE vehicle_id=r.vehicle_id)')
            frames={r['vehicle_id']:json.loads(r['payload']) for r in latest}
            counts={r['vehicle_id']:r['n'] for r in fetch('SELECT vehicle_id,COUNT(*) AS n FROM fleet_readings GROUP BY vehicle_id')}
            alerts=fetch("SELECT * FROM fleet_alerts WHERE status!='resolved' ORDER BY updated_at DESC")
            result=[]
            for p in all_profiles():result.append(dict(vehicle=public_profile(p),frame=frames.get(p['id']),readings=counts.get(p['id'],0),alerts=[a for a in alerts if a['vehicle_id']==p['id']]))
            return jsonify(vehicles=result,total=len(result),activeAlerts=sum(a['status']=='active' for a in alerts))
        if not same_origin():return jsonify(error='Request origin is not allowed.'),403
        p=request.get_json(silent=True) or {};identity=str(p.get('vehicleId','')).strip().upper()
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,39}',identity):return jsonify(error='Vehicle ID must be 3-40 letters, numbers, hyphens or underscores.'),400
        pin=str(p.get('pin',''))
        if not re.fullmatch(r'\d{4}',pin):return jsonify(error='Enter a four-digit vehicle PIN.'),400
        text={key:str(p.get(key,'')).strip() for key in ['name','model','owner']}
        if any(not v or len(v)>80 for v in text.values()):return jsonify(error='Owner, vehicle name and model are required (maximum 80 characters each).'),400
        templates={'city':('Compact city EV',42,135,31,.94),'family':('Family SUV',58,185,33,1.08),'sport':('Electric sports coupe',76,255,35,1.28),'track':('Track performance EV',94,305,37,1.48),'van':('Electric delivery van',48,150,34,1.14)}
        kind=p.get('kind','city');scenario=p.get('scenario','normal')
        if kind not in templates or scenario not in ['normal','hard-acceleration','high-speed','hot-weather','high-load','cell-hotspot','coolant-leak']:return jsonify(error='Choose a valid vehicle type and automatic condition.'),400
        numbers={}
        for key,lo,hi in [('capacity',10,200),('voltage',100,1000),('soh',40,100)]:
            try:value=float(p.get(key))
            except (TypeError,ValueError):return jsonify(error='Enter valid battery capacity, voltage and health.'),400
            if not lo<=value<=hi:return jsonify(error=f'{key} must be between {lo} and {hi}.'),400
            numbers[key]=value
        if get_profile(identity):return jsonify(error='This vehicle ID is already registered.'),409
        if fetch('SELECT id FROM fleet_requests WHERE vehicle_id=?',(identity,)):return jsonify(error='This ID has a registration request. Review it in the approval panel.'),409
        class_name,speed,max_speed,temp,cooling=templates[kind]
        profile=dict(id=identity,**text,**numbers,className=class_name,base_speed=speed,max_speed=max_speed,base_temp=temp,cooling=cooling,accent='#0b88a1',scenario=scenario)
        salt=os.urandom(16);digest=hashlib.pbkdf2_hmac('sha256',pin.encode(),salt,200000);now=datetime.now(timezone.utc).isoformat()
        try:
            with connection() as conn:
                execute(conn,'INSERT INTO fleet_users VALUES(?,?,?,?)',(identity,salt.hex(),digest.hex(),now))
                execute(conn,'INSERT INTO fleet_profiles VALUES(?,?,?)',(identity,json.dumps(profile),now))
                from .registration import audit
                audit(conn,'direct-registration',identity,scenario)
        except Exception:
            if get_profile(identity):return jsonify(error='This vehicle ID is already registered.'),409
            raise
        return jsonify(vehicle=public_profile(profile),message='Vehicle registered. Automatic readings start on the next worker cycle.'),201
