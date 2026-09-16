import os
from flask import Flask,jsonify,request
from dotenv import load_dotenv
load_dotenv()
from models.scenarios import list_scenarios
from llm.provider import status as llm_status
from engine import negotiation_engine
app=Flask(__name__)
@app.after_request
def cors(r):
 r.headers['Access-Control-Allow-Origin']='*';r.headers['Access-Control-Allow-Methods']='GET,POST,OPTIONS';r.headers['Access-Control-Allow-Headers']='Content-Type';return r
@app.route('/api/<path:x>',methods=['OPTIONS'])
def options(x):return ('',204)
@app.get('/api/health')
def health():return jsonify({'status':'ok','llm':llm_status()})
@app.get('/api/scenarios')
def scenarios():return jsonify(list_scenarios())
@app.post('/api/negotiations')
def create():
 d=request.get_json(silent=True) or {}; missing=[x for x in ('scenario_id','personality_a','personality_b') if x not in d]
 if missing:return jsonify({'error':'Missing fields: '+', '.join(missing)}),400
 try:st=negotiation_engine.create_negotiation(d['scenario_id'],d['personality_a'],d['personality_b'],d.get('mode','mock'),int(d.get('max_rounds') or 8),d.get('workflow_mode','simulation'))
 except (KeyError,ValueError) as e:return jsonify({'error':str(e)}),400
 return jsonify(st.to_dict()),201
@app.get('/api/negotiations')
def history():return jsonify(negotiation_engine.list_negotiations())
@app.get('/api/dashboard')
def dashboard():return jsonify(negotiation_engine.dashboard_stats())
@app.get('/api/llm/status')
def llm():return jsonify(llm_status())
@app.get('/api/negotiations/<i>')
def get(i):
 st=negotiation_engine.get_negotiation(i)
 return (jsonify(st.to_dict()),200) if st else (jsonify({'error':'negotiation not found'}),404)
@app.post('/api/negotiations/<i>/step')
def step(i):
 try:return jsonify(negotiation_engine.step_negotiation(i).to_dict())
 except KeyError as e:return jsonify({'error':str(e)}),404
 except Exception as e:return jsonify({'error':str(e)}),500
@app.post('/api/negotiations/<i>/run')
def run(i):
 try:return jsonify(negotiation_engine.run_negotiation(i).to_dict())
 except KeyError as e:return jsonify({'error':str(e)}),404
 except Exception as e:return jsonify({'error':str(e)}),500
@app.post('/api/negotiations/<i>/human-action')
def human(i):
 d=request.get_json(silent=True) or {}
 try:return jsonify(negotiation_engine.human_action(i,d.get('action','counter'),d.get('value'),d.get('rationale','Human participant submitted this proposal.'),d.get('message','')).to_dict())
 except (KeyError,ValueError) as e:return jsonify({'error':str(e)}),400
@app.get('/api/negotiations/<i>/report')
def report(i):
 try:return jsonify(negotiation_engine.build_report(i))
 except KeyError as e:return jsonify({'error':str(e)}),404
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=os.getenv('FLASK_DEBUG','1')=='1')
