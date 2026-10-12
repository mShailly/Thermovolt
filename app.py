from pathlib import Path
from datetime import datetime,timezone
import json,uuid,os
from flask import Flask,request,jsonify,send_from_directory
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent/'.env')
from thermovolt.core import CoolingOptimizer
from thermovolt.segment import CSegmentTree
from thermovolt.storage import initialize,connection,execute,fetch,POSTGRES
ROOT=Path(__file__).resolve().parent
app=Flask(__name__,static_folder=None)
optimizer=CoolingOptimizer();initialize()
telemetry=json.loads((ROOT/'web/data/telemetry.json').read_text())
tree=CSegmentTree([r['Battery_Temperature'] for r in telemetry])
@app.errorhandler(ValueError)
def invalid(error):return jsonify(error=str(error)),400
@app.errorhandler(Exception)
def unexpected(error):
    app.logger.exception('Request failed')
    return jsonify(error='Operation failed. Check the database connection and retry.'),500
@app.post('/api/optimize')
def optimize():return jsonify(optimizer.optimize(request.get_json()))
@app.post('/api/interval')
def interval():
    p=request.get_json();return jsonify(tree.query(p.get('start'),p.get('end')))
@app.route('/api/experiments',methods=['GET','POST','DELETE'])
def experiments():
    if request.method=='GET':return jsonify(experiments=fetch('SELECT e.*,COUNT(m.id) AS maintenance_count FROM experiments e LEFT JOIN maintenance m ON e.id=m.experiment_id GROUP BY e.id ORDER BY e.created_at DESC LIMIT 100'))
    p=request.get_json()
    if request.method=='POST':
        name=p.get('name','')
        if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise ValueError('Use a name between 1 and 100 characters.')
        r=optimizer.optimize(p.get('conditions'));s=r['optimized'];identity=str(uuid.uuid4())
        results={'flow':s['flow'],'finalMax':s['end']['max'],'spread':s['end']['spread'],'energyWh':s['energyWh'],'feasible':r['feasible']}
        with connection() as conn:execute(conn,'INSERT INTO experiments VALUES(?,?,?,?,?)',(identity,name.strip(),json.dumps(r['conditions']),json.dumps(results),datetime.now(timezone.utc).isoformat()))
        return jsonify(id=identity),201
    identity=p.get('id')
    if not isinstance(identity,str):raise ValueError('Choose an experiment.')
    with connection() as conn:
        count=execute(conn,'SELECT COUNT(*) AS n FROM maintenance WHERE experiment_id=?',(identity,)).fetchone()['n']
        if count:return jsonify(error='Remove linked maintenance records before deleting this experiment.'),409
        execute(conn,'DELETE FROM experiments WHERE id=?',(identity,))
    return jsonify(ok=True)
@app.route('/api/maintenance',methods=['GET','POST','PATCH','DELETE'])
def maintenance():
    if request.method=='GET':return jsonify(maintenance=fetch('SELECT m.*,e.name AS experiment_name FROM maintenance m JOIN experiments e ON m.experiment_id=e.id ORDER BY m.created_at DESC LIMIT 200'))
    p=request.get_json()
    with connection() as conn:
        if request.method=='POST':
            title=p.get('title','');notes=p.get('notes','');eid=p.get('experimentId')
            if not isinstance(eid,str) or not isinstance(title,str) or not 1<=len(title.strip())<=100 or not isinstance(notes,str) or len(notes)>1000:raise ValueError('Choose an experiment and enter a valid title and notes.')
            if not execute(conn,'SELECT id FROM experiments WHERE id=?',(eid,)).fetchone():raise ValueError('The selected experiment no longer exists.')
            identity=str(uuid.uuid4());execute(conn,'INSERT INTO maintenance VALUES(?,?,?,?,?,?)',(identity,eid,title.strip(),notes,'open',datetime.now(timezone.utc).isoformat()));return jsonify(id=identity),201
        identity=p.get('id')
        if not isinstance(identity,str):raise ValueError('Choose a record.')
        if request.method=='PATCH':
            status=p.get('status')
            if status not in ['open','reviewed','closed']:raise ValueError('Choose a valid status.')
            execute(conn,'UPDATE maintenance SET status=? WHERE id=?',(status,identity))
        else:execute(conn,'DELETE FROM maintenance WHERE id=?',(identity,))
    return jsonify(ok=True)
@app.get('/api/database')
def database():
    result_expr="CAST(results::json->>'finalMax' AS DOUBLE PRECISION)" if POSTGRES else "CAST(json_extract(results,'$.finalMax') AS REAL)"
    summary=fetch(f'SELECT COUNT(*) AS total,AVG({result_expr}) AS average_temperature FROM experiments')[0]
    statuses=fetch('SELECT status,COUNT(*) AS count FROM maintenance GROUP BY status')
    plan=fetch(('EXPLAIN SELECT * FROM maintenance WHERE experiment_id=?' if POSTGRES else 'EXPLAIN QUERY PLAN SELECT * FROM maintenance WHERE experiment_id=?'),('example',))
    if POSTGRES:plan=[{'detail':r['QUERY PLAN']} for r in plan]
    return jsonify(summary=summary,statuses=statuses,plan=plan)
@app.get('/api/runtime')
def runtime():return jsonify(runtime='python',backend='Python/Flask',database='PostgreSQL' if POSTGRES else 'SQLite')
@app.get('/')
def home():return send_from_directory(ROOT/'web','index.html')
@app.get('/<path:path>')
def static_asset(path):return send_from_directory(ROOT/'web',path)
from thermovolt.monitor import register_monitor
register_monitor(app)
from thermovolt.fleet import register_fleet,start_fleet_stream
register_fleet(app)
if __name__=='__main__':
    start_fleet_stream(app)
    print('ThermoVolt: open http://127.0.0.1:5050 · '+('PostgreSQL' if POSTGRES else 'SQLite demo database'))
    app.run(host=os.environ.get('HOST','127.0.0.1'),port=int(os.environ.get('PORT','5050')),debug=False)
