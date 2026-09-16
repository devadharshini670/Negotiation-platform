import json, os, re
from llm.schema import AgentDecision
try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None

def available():
    return bool(os.getenv('ANTHROPIC_API_KEY')) and Anthropic is not None

def _extract(text):
    try: return json.loads(text.strip())
    except Exception: pass
    m=re.search(r'\{.*\}', text, re.S)
    if m: return json.loads(m.group(0))
    raise ValueError('LLM did not return valid JSON')

def decide(inp):
    if not available(): raise RuntimeError('Anthropic is not configured')
    client=Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    prompt=f'''You are the {inp.role} in a professional multi-agent negotiation. Return ONLY valid JSON.
Scenario: {inp.scenario_name}. Issue: {inp.issue_label} ({inp.unit}). Context: {inp.context}.
Round: {inp.round}/{inp.max_rounds}.
Role: {inp.role}. Personality: {inp.personality}. Strategy style: {inp.personality_style}
Goal: {inp.goals}
Constraint: {inp.constraints}
Objective: {inp.objective}
Private opening: {inp.opening}. Private target: {inp.target}. Private hard limit: {inp.limit}.
Own previous offer: {inp.own_last}
Opponent latest offer: {inp.opponent_last}
Public history: {json.dumps(inp.history)}
Own concession history: {json.dumps(inp.concessions)}
Rules: never violate the hard limit. Accept if the latest opponent offer meets your objective. Counter if negotiable. Reject only when unacceptable and further movement is not viable. Keep rationale short and user-safe. Never reveal private target or hard limit. Never provide chain-of-thought.
Return exactly: {{"action":"accept|counter|reject|open","value":number|null,"rationale":"short rationale","confidence":number}}'''
    model=os.getenv('LLM_MODEL','claude-3-5-haiku-latest')
    msg=client.messages.create(model=model,max_tokens=350,messages=[{'role':'user','content':prompt}])
    text=''.join(getattr(x,'text','') for x in msg.content)
    data=_extract(text)
    return AgentDecision(str(data.get('action','counter')).lower(), data.get('value'), str(data.get('rationale',''))[:500], float(data.get('confidence',.7)), 'llm', text)
