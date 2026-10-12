"""Five-vehicle telemetry stream, local authentication and alert persistence."""
from datetime import datetime,timezone
import hashlib,hmac,json,math,os,secrets,time,uuid,threading
from flask import request,jsonify
from .core import Conditions,CoolingOptimizer
from .storage import connection,execute,fetch

PROFILES={
 'TV-URBAN-01':dict(name='Urban One',model='Eon City',capacity=45,voltage=330,soh=96,base_speed=42,max_speed=135,base_temp=31,cooling=.94,pin='1842'),
 'TV-FAMILY-02':dict(name='Family Prime',model='Aster X7',capacity=72,voltage=390,soh=93,base_speed=58,max_speed=185,base_temp=33,cooling=1.08,pin='2764'),
 'TV-SPORT-03':dict(name='Volt GT',model='Veloce S',capacity=88,voltage=720,soh=91,base_speed=76,max_speed=255,base_temp=35,cooling=1.28,pin='3907'),
 'TV-TRACK-04':dict(name='Apex R',model='Ion R9',capacity=92,voltage=800,soh=89,base_speed=94,max_speed=305,base_temp=37,cooling=1.48,pin='4518'),
 'TV-FLEET-05':dict(name='Metro Van',model='Carry E5',capacity=105,voltage=610,soh=86,base_speed=48,max_speed=150,base_temp=34,cooling=1.14,pin='5683')}
MODES=['normal','hard-acceleration','normal','high-speed','hot-weather','high-load','normal','cell-hotspot','normal','coolant-leak']
AUTOMATIC={'TV-URBAN-01':'normal','TV-FAMILY-02':'hot-weather','TV-SPORT-03':'high-load','TV-TRACK-04':'cell-hotspot','TV-FLEET-05':'coolant-leak'}
STREAM_LOCK=threading.Lock()
LABELS={'normal':'Steady driving','hard-acceleration':'Rapid acceleration','high-speed':'Sustained high speed','hot-weather':'Hot ambient conditions','high-load':'High battery load','cell-hotspot':'Cell hotspot','coolant-leak':'Coolant-flow loss'}
def clamp(v,a,b):return min(b,max(a,v))
def derive(profile,previous,requested,optimizer):
    elapsed=(previous.get('elapsed',-20) if previous else -20)+20;mode=AUTOMATIC[profile['id']] if requested=='auto' else requested
    phase=elapsed/25;speed=profile['base_speed']+math.sin(phase)*7;acceleration=.4+math.sin(phase*.8)*.45;ambient=29;current=-(58+profile['capacity']*.32);inlet=24
    if mode=='hard-acceleration':acceleration=4.1;speed=clamp((previous.get('speed',profile['base_speed']) if previous else profile['base_speed'])+18,0,profile['max_speed']*.82);current=-(170+profile['capacity']*.7)
    elif mode=='high-speed':speed=profile['max_speed']*.84;acceleration=.8;current=-(155+profile['capacity']*.55)
    elif mode=='hot-weather':ambient=43;inlet=33;speed=profile['base_speed']*1.12;current=-(95+profile['capacity']*.4)
    elif mode=='high-load':speed=profile['base_speed']*.9;acceleration=2.1;current=-(205+profile['capacity']*.65)
    elif mode=='cell-hotspot':current=-(105+profile['capacity']*.4)
    elif mode=='coolant-leak':speed=profile['base_speed']*.95;current=-(115+profile['capacity']*.4)
    heat=clamp(3.1+abs(current)/43+max(0,acceleration-1)*.72+max(0,speed-115)*.024+max(0,ambient-34)*.11,2,14)
    initial=profile['base_temp'] if mode=='normal' else 44 if mode in ['hot-weather','high-load'] else 40 if mode=='cell-hotspot' else 39
    cells=previous.get('cells') if previous and len(previous.get('cells',[]))==10 else [initial+(i-4.5)*.07+(8 if mode=='cell-hotspot' and i==6 else 0) for i in range(10)];average=sum(cells)/10
    payload=dict(start=clamp(average,25,55),heat=heat,inlet=inlet,ambient=ambient,concentration=1,target=45,spreadLimit=5,fixedFlow=30);result=optimizer.optimize(payload);recommendation=result['optimized']['flow'];pump=recommendation*profile['cooling'];flow=pump*.28 if mode=='coolant-leak' else pump
    next_cells=[]
    for i,temperature in enumerate(cells):
        offset=i/9*2-1;g=.015 if flow<1 else (.05+.48*(max(flow,1)/20)**.55*1.04)*(1+.06*offset)*profile['cooling'];eq=(heat*(1+.12*offset)+g*inlet+.04*ambient)/(g+.04);value=eq+(temperature-eq)*math.exp(-(g+.04)*20/70)
        if mode=='cell-hotspot' and i==6:value+=1.15
        next_cells.append(value)
    temperature=max(next_cells);average=sum(next_cells)/10;spread=temperature-min(next_cells);forecast=optimizer.surrogate.predict(Conditions.from_dict({**payload,'start':clamp(temperature,25,55)}),flow)['temperature'] if 10<=flow<=60 and 25<=temperature<=55 else None
    soc=clamp((previous.get('soc',76-profile['capacity']%9) if previous else 76-profile['capacity']%9)-abs(profile['voltage']*current)*20/3600000/profile['capacity']*100,4,100);power=abs(profile['voltage']*current);contributors=[]
    def add(code,label,level,evidence,detail):contributors.append(dict(code=code,label=label,level=level,evidence=evidence,detail=detail))
    if acceleration>2.5:add('acceleration','Rapid acceleration','high' if acceleration>3.6 else 'moderate',f'{acceleration:.1f} m/s² acceleration','Higher torque demand is increasing battery current and heat generation.')
    if speed>120:add('speed','Sustained high speed','high' if speed>profile['max_speed']*.8 else 'moderate',f'{speed:.0f} km/h vehicle speed','Sustained propulsion demand is adding thermal load.')
    if abs(current)>190:add('load','High battery load','high' if abs(current)>235 else 'moderate',f'{abs(current):.0f} A discharge current','High current is the strongest present electrical heating contributor.')
    if ambient>38:add('weather','Hot weather','high' if ambient>42 else 'moderate',f'{ambient:.0f}°C ambient temperature','Hot surroundings reduce the temperature difference available for heat rejection.')
    if flow<recommendation*.6:add('coolant','Reduced coolant flow','high',f'{flow:.1f} of {recommendation:.1f} mL/min requested','Cooling delivery is below the present thermal recommendation.')
    if spread>=4 or mode=='cell-hotspot':add('hotspot','Cell hotspot','high' if spread>=5 else 'moderate',f'{spread:.1f}°C cell spread','One area of the pack is warming faster than the rest.')
    alerts=[]
    likely=', '.join(x['label'] for x in contributors[:3])
    def alert(code,severity,title,message,action):alerts.append(dict(code=code,severity=severity,title=title,message=message,action=action))
    if mode=='high-load' and abs(current)>235:alert('load','warning','Sustained high discharge load',f'Battery discharge is {abs(current):.0f} A. Elevated electrical demand is increasing heat generation.','Reduce sustained load and monitor the cooling response.')
    if mode=='hot-weather' and ambient>=42:alert('ambient','warning','High ambient thermal stress',f'Ambient temperature is {ambient:.0f}°C, reducing available heat rejection.','Monitor pack temperature and keep the cooling circuit operating.')
    if flow<recommendation*.6:alert('coolant','critical','Cooling flow below demand',f'Reported flow is {flow:.1f} mL/min while {recommendation:.1f} mL/min is requested.','Inspect the coolant circuit and pump response.')
    if temperature>=50:alert('temperature','critical','Battery temperature critical',f'Hottest cell is {temperature:.1f}°C.','Reduce load and follow the vehicle thermal-protection procedure.')
    elif temperature>45:alert('temperature','warning','Battery temperature above target',f'Hottest cell is {temperature:.1f}°C.'+(f' Likely contributors: {likely}.' if likely else ''),'Review the listed heating contributors and cooling response.')
    elif temperature>=43 and contributors:alert('margin','warning','Thermal margin reducing',f'Hottest cell is {temperature:.1f}°C and trending near the 45°C target. Likely contributors: {likely}.','Reduce the strongest present contributor and confirm temperature begins to stabilise.')
    elif forecast and forecast>45:alert('forecast','warning','Temperature approaching limit',f'Projected temperature is {forecast:.1f}°C.','Reduce the strongest present load factor and monitor the next readings.')
    if spread>=5:alert('spread','warning','Uneven cell temperatures',f'Cell spread has reached {spread:.1f}°C.','Inspect the hottest cell area and coolant distribution.')
    return dict(time=datetime.now(timezone.utc).isoformat(),elapsed=elapsed,vehicleId=profile['id'],driveMode=mode,condition=LABELS[mode],temperature=temperature,averageTemperature=average,cells=next_cells,soc=soc,soh=profile['soh'],voltage=profile['voltage'],current=current,ambient=ambient,motorTemp=45+abs(current)*.18,motorTorque=abs(current)*.72,rpm=1800+speed*42,speed=speed,acceleration=acceleration,distance=(previous.get('distance',12540) if previous else 12540)+speed*20/3600,cycles=190+(100-profile['soh'])*9,idle=(previous.get('idle',0)+20 if previous and speed<2 else 0),power=power,regen=68 if mode=='normal' else 56,flow=flow,inlet=inlet,heat=heat,pressure=result['optimized']['pressure'],recommendation=recommendation,forecast=forecast,spread=spread,feasible=result['feasible'],pump=pump,contributors=contributors,alerts=alerts)

def advance_fleet(optimizer,force=False):
    """One writer advances all vehicles; readers never generate extra samples."""
    with STREAM_LOCK:
        frames=[]
        for vehicle_id,p in PROFILES.items():
            rows=fetch('SELECT payload FROM fleet_readings WHERE vehicle_id=? ORDER BY observed_at DESC LIMIT 1',(vehicle_id,))
            previous=json.loads(rows[0]['payload']) if rows else None
            if previous and not force and time.time()-datetime.fromisoformat(previous['time']).timestamp()<2.8:continue
            if previous and previous.get('driveMode')!=AUTOMATIC[vehicle_id]:previous=None
            frame=derive({**p,'id':vehicle_id},previous,'auto',optimizer);now=frame['time']
            with connection() as conn:
                execute(conn,'INSERT INTO fleet_readings VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),vehicle_id,now,frame['temperature'],frame['speed'],frame['driveMode'],json.dumps(frame)))
                for a in frame['alerts']:execute(conn,"INSERT INTO fleet_alerts VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(vehicle_id,code) DO UPDATE SET severity=excluded.severity,title=excluded.title,message=excluded.message,action=excluded.action,updated_at=excluded.updated_at,status=CASE WHEN fleet_alerts.status='resolved' THEN 'active' ELSE fleet_alerts.status END",(str(uuid.uuid4()),vehicle_id,a['code'],a['severity'],a['title'],a['message'],a['action'],'active',now,now))
                codes=[a['code'] for a in frame['alerts']];clause=' AND code NOT IN ('+','.join('?' for _ in codes)+')' if codes else ''
                execute(conn,"UPDATE fleet_alerts SET status='resolved',updated_at=? WHERE vehicle_id=? AND status!='resolved'"+clause,(now,vehicle_id,*codes))
            frames.append(frame)
        return frames

def start_fleet_stream(app):
    """Run once in a dedicated process or the single-process local server."""
    if app.extensions.get('fleet_stream'):return
    stop=threading.Event();app.extensions['fleet_stream']=stop
    optimizer=CoolingOptimizer();advance_fleet(optimizer)
    def run():
        while not stop.wait(3):
            try:advance_fleet(optimizer)
            except Exception:app.logger.exception('Fleet feed could not write readings')
    threading.Thread(target=run,name='fleet-telemetry',daemon=True).start()

def register_fleet(app):
    optimizer=CoolingOptimizer()
    with connection() as conn:
        for vehicle_id,p in PROFILES.items():
            salt=os.urandom(16);digest=hashlib.pbkdf2_hmac('sha256',p['pin'].encode(),salt,200000)
            execute(conn,'INSERT INTO fleet_users(vehicle_id,pin_salt,pin_hash,created_at) VALUES(?,?,?,?) ON CONFLICT(vehicle_id) DO NOTHING',(vehicle_id,salt.hex(),digest.hex(),datetime.now(timezone.utc).isoformat()))
    def allowed(vehicle_id):
        token=request.cookies.get('tv_local_session');rows=fetch('SELECT vehicle_id,expires_at FROM fleet_sessions WHERE id=?',(token or '',))
        return bool(rows and rows[0]['vehicle_id']==vehicle_id and rows[0]['expires_at']>time.time())
    @app.route('/api/local-auth',methods=['POST','DELETE'])
    def local_auth():
        if request.method=='DELETE':
            with connection() as conn:execute(conn,'DELETE FROM fleet_sessions WHERE id=?',(request.cookies.get('tv_local_session',''),))
            r=jsonify(ok=True);r.delete_cookie('tv_local_session');return r
        p=request.get_json() or {};vehicle_id=str(p.get('vehicleId','')).upper();pin=str(p.get('pin',''));rows=fetch('SELECT pin_salt,pin_hash FROM fleet_users WHERE vehicle_id=?',(vehicle_id,))
        if not rows:return jsonify(error='Vehicle ID or PIN is incorrect.'),401
        digest=hashlib.pbkdf2_hmac('sha256',pin.encode(),bytes.fromhex(rows[0]['pin_salt']),200000).hex()
        if not hmac.compare_digest(digest,rows[0]['pin_hash']):return jsonify(error='Vehicle ID or PIN is incorrect.'),401
        token=secrets.token_urlsafe(32);expiry=time.time()+28800
        with connection() as conn:execute(conn,'INSERT INTO fleet_sessions(id,vehicle_id,expires_at,created_at) VALUES(?,?,?,?)',(token,vehicle_id,expiry,datetime.now(timezone.utc).isoformat()))
        r=jsonify(ok=True);r.set_cookie('tv_local_session',token,max_age=28800,httponly=True,samesite='Lax',secure=request.is_secure);return r
    @app.route('/api/fleet',methods=['GET','POST','PATCH'])
    def fleet_route():
        vehicle_id=(request.args.get('vehicle') if request.method=='GET' else (request.get_json() or {}).get('vehicleId','')).upper()
        if vehicle_id not in PROFILES:return jsonify(error='Vehicle ID not found.'),404
        if not allowed(vehicle_id):return jsonify(error='Vehicle session expired. Sign in again.'),401
        if request.method=='GET':
            latest=fetch('SELECT payload FROM fleet_readings WHERE vehicle_id=? ORDER BY observed_at DESC LIMIT 1',(vehicle_id,));history=fetch('SELECT observed_at,temperature,speed,drive_mode,payload FROM fleet_readings WHERE vehicle_id=? ORDER BY observed_at DESC LIMIT 120',(vehicle_id,));alerts=fetch('SELECT * FROM fleet_alerts WHERE vehicle_id=? ORDER BY updated_at DESC LIMIT 100',(vehicle_id,))
            for row in history:row['payload']=json.loads(row['payload'])
            return jsonify(frame=json.loads(latest[0]['payload']) if latest else None,history=history,alerts=alerts)
        p=request.get_json() or {}
        if request.method=='PATCH':
            with connection() as conn:execute(conn,"UPDATE fleet_alerts SET status='acknowledged',updated_at=? WHERE id=? AND vehicle_id=? AND status='active'",(datetime.now(timezone.utc).isoformat(),p.get('alertId'),vehicle_id))
            return jsonify(ok=True)
        return jsonify(error='Driving conditions are assigned automatically. Read /api/fleet to monitor this vehicle.'),405
