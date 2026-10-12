"""Browser-scoped telemetry intake, automatic alert lifecycle and gateway authentication."""
from datetime import datetime,timezone
from dataclasses import asdict
import uuid,hashlib,secrets,math
from flask import request,jsonify
from .storage import connection,execute,fetch
from .core import Conditions,CoolingOptimizer

def parse(p):
    if not isinstance(p,dict):raise ValueError('Send a JSON telemetry object.')
    def value(key,low,high,optional=False):
        v=p.get(key)
        if optional and v is None:return None
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:raise ValueError(f'{key} must be a number between {low} and {high}.')
        return v
    t=value('temperature',-40,120);cells=p.get('cells',[])
    if not isinstance(cells,list) or len(cells)>200 or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not -40<=v<=120 for v in cells):raise ValueError('Use up to 200 finite cell temperatures.')
    now=datetime.now(timezone.utc);time=p.get('time',now.isoformat())
    try:stamp=datetime.fromisoformat(time.replace('Z','+00:00'))
    except (AttributeError,ValueError):raise ValueError('Use a valid timestamp.')
    if stamp.tzinfo is None or (stamp-now).total_seconds()>60:raise ValueError('Use a timestamp with a timezone that is not in the future.')
    frame=dict(time=time,source='gateway',temperature=max(cells) if cells else t,cells=cells,soc=value('soc',0,100),voltage=value('voltage',0,1000),current=value('current',-1000,1000),ambient=value('ambient',-40,80),flow=value('flow',0,1000,True),inlet=value('inlet',-20,80,True),heat=value('heat',0,100,True),pump=value('pump',0,1000,True) or 0,pressure=value('pressure',0,1e7,True),regen=value('regen',0,100,True))
    for key,low,high in [('soh',0,100),('motorTemp',-40,200),('motorTorque',-3000,3000),('rpm',0,50000),('speed',0,300),('distance',0,1e7),('cycles',0,1e5),('idle',0,1e7)]:frame[key]=value(key,low,high,True)
    frame.update(power=abs(frame['voltage']*frame['current']),elapsed=0,concentration=1,recommendation=None,forecast=None,spread=max(cells)-min(cells) if cells else None,feasible=None,coolingMode='manual',scenario='connected vehicle',quality=[] if cells else ['Cell temperatures are not supplied; cell uniformity cannot be assessed.'])
    return frame

def assess(f):
    result=[]
    def add(code,severity,title,message,action):result.append(dict(code=code,severity=severity,title=title,message=message,action=action))
    t=f['temperature']
    if f['source']=='gateway' and (datetime.now(timezone.utc)-datetime.fromisoformat(f['time'].replace('Z','+00:00'))).total_seconds()>30:add('stale','warning','Vehicle data is stale','No fresh reading has arrived for over 30 seconds.','Check the vehicle gateway connection. Do not rely on old temperatures.')
    if f['flow'] is not None and f['flow']<2 and f['pump']>0:add('coolant','critical','Coolant flow has stopped','Cooling is requested, but reported flow is below 2 mL/min per channel.','Inspect the coolant circuit and pump. A vehicle controller must enforce its own protective response.')
    if t>=50:add('temperature-critical','critical','Battery temperature is critical',f'The hottest reported cell or pack reading is {t:.1f}°C.','Urgent thermal-system inspection. Follow the vehicle manufacturer’s instructions.')
    elif t>45:add('temperature-high','warning','Battery is above the temperature target',f'Temperature is {t:.1f}°C; the project target is 15–45°C.','Increase cooling where supported and check that temperature starts falling.')
    if t<15:add('temperature-low','warning','Battery is below the project operating range','Temperature is below 15°C.','Follow the vehicle’s battery-heating guidance.')
    if f['forecast'] is not None and f['forecast']>45 and t<=45:add('forecast','warning','Heating risk predicted ahead',f'The synthetic model estimates {f["forecast"]:.1f}°C at its 10-minute horizon.','Review the cooling recommendation before the target is exceeded.')
    if f['spread'] is not None and f['spread']>=5:add('spread','warning','Cell temperatures are uneven',f'Cell difference is {f["spread"]:.1f}°C; the target is below 5°C.','Inspect flow distribution and the warmest cells.')
    if f['feasible'] is False:add('capacity','warning','Cooling target cannot be met','No verified setting within Reynolds 400–700 meets both final targets.','Reduce thermal load or coolant inlet temperature in the demo; review capacity in a real installation.')
    if f['quality']:add('quality','warning','Some telemetry is unavailable',' '.join(f['quality']),'Check source measurements. Missing values are not replaced with invented readings.')
    return result

def register_monitor(app):
    optimizer=CoolingOptimizer()
    def session_id():
        try:return str(uuid.UUID(request.cookies.get('tv_session','')))
        except ValueError:return str(uuid.uuid4())
    def response(payload,sid,status=200):
        r=jsonify(payload);r.status_code=status;r.headers['Cache-Control']='no-store';r.set_cookie('tv_session',sid,max_age=2592000,httponly=True,samesite='Lax',secure=request.is_secure);return r
    @app.route('/api/monitor',methods=['GET','POST'])
    def monitor():
        sid=session_id()
        if request.method=='GET':
            rows=fetch("SELECT payload FROM telemetry_readings WHERE session_id=? AND source='gateway' ORDER BY observed_at DESC LIMIT 1",(sid,))
            import json
            return response({'frame':json.loads(rows[0]['payload']) if rows else None},sid)
        import json
        auth=request.headers.get('Authorization');p=request.get_json()
        if auth:
            digest=hashlib.sha256(auth.removeprefix('Bearer ').encode()).hexdigest();rows=fetch('SELECT session_id FROM vehicle_connections WHERE token_hash=?',(digest,))
            if not rows:return jsonify(error='Invalid vehicle token.'),401
            sid=rows[0]['session_id'];frame=parse(p);run='gateway'
        else:
            if not isinstance(p,dict) or p.get('frame',{}).get('source')!='demo':return response({'error':'Gateway telemetry requires a Bearer token.'},sid,401)
            original=p['frame'];frame=parse(original);frame.update(source='demo',elapsed=original.get('elapsed',0),scenario=str(original.get('scenario','demo'))[:50],quality=[],coolingMode='auto' if original.get('coolingMode')=='auto' else 'manual')
            # Execute the shared Python simulator/surrogate for local operational frames.
            if frame['heat'] is None or frame['inlet'] is None:raise ValueError('Demo cooling conditions are required.')
            conditions={**asdict(Conditions()),'start':min(55,max(25,frame['temperature'])),'heat':frame['heat'],'inlet':frame['inlet'],'ambient':frame['ambient']}
            result=optimizer.optimize(conditions);frame['recommendation']=result['optimized']['flow'];frame['feasible']=result['feasible']
            frame['forecast']=optimizer.surrogate.predict(Conditions.from_dict(conditions),frame['flow'])['temperature'] if frame['flow'] is not None and 10<=frame['flow']<=60 and 25<=frame['temperature']<=55 else None
            run=p.get('runId','demo')
            if not isinstance(run,str) or len(run)>100:raise ValueError('Invalid run identifier.')
        alerts=assess(frame);now=datetime.now(timezone.utc).isoformat()
        with connection() as conn:
            execute(conn,'INSERT INTO telemetry_readings VALUES(?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),sid,run,frame['source'],now,frame['temperature'],frame['soc'],frame['voltage'],frame['current'],frame['flow'],json.dumps(frame,allow_nan=False)))
            for a in alerts:execute(conn,"INSERT INTO thermal_alerts VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(session_id,run_id,code) DO UPDATE SET message=excluded.message,updated_at=excluded.updated_at,status=CASE WHEN thermal_alerts.status='resolved' THEN 'active' ELSE thermal_alerts.status END",(str(uuid.uuid4()),sid,run,a['code'],a['severity'],a['title'],a['message'],a['action'],'active',now,now))
            codes=[a['code'] for a in alerts];clause=' AND code NOT IN ('+','.join('?' for _ in codes)+')' if codes else ''
            execute(conn,"UPDATE thermal_alerts SET status='resolved',updated_at=? WHERE session_id=? AND run_id=? AND status!='resolved'"+clause,(now,sid,run,*codes))
            if not auth:execute(conn,"UPDATE thermal_alerts SET status='resolved',updated_at=? WHERE session_id=? AND run_id!=? AND run_id!='gateway' AND status!='resolved'",(now,sid,run))
            execute(conn,'DELETE FROM telemetry_readings WHERE session_id=? AND id NOT IN (SELECT id FROM telemetry_readings WHERE session_id=? ORDER BY observed_at DESC LIMIT 500)',(sid,sid))
        return response({'ok':True,'alerts':alerts},sid)
    @app.route('/api/alerts',methods=['GET','PATCH'])
    def alerts_route():
        sid=session_id()
        if request.method=='PATCH':
            identity=request.get_json().get('id')
            if not isinstance(identity,str):raise ValueError('Choose an alert.')
            with connection() as conn:execute(conn,"UPDATE thermal_alerts SET status='acknowledged' WHERE id=? AND session_id=? AND status='active'",(identity,sid))
            return response({'ok':True},sid)
        return response({'alerts':fetch('SELECT * FROM thermal_alerts WHERE session_id=? ORDER BY created_at DESC LIMIT 100',(sid,)),'history':fetch('SELECT observed_at,temperature,soc,flow,source FROM telemetry_readings WHERE session_id=? ORDER BY observed_at DESC LIMIT 120',(sid,))},sid)
    @app.post('/api/connection')
    def connection_route():
        sid=session_id();token=secrets.token_hex(36);digest=hashlib.sha256(token.encode()).hexdigest()
        with connection() as conn:execute(conn,'INSERT INTO vehicle_connections VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE SET token_hash=excluded.token_hash,created_at=excluded.created_at',(sid,digest,datetime.now(timezone.utc).isoformat()))
        return response({'token':token,'endpoint':request.url_root.rstrip('/')+'/api/monitor'},sid)
