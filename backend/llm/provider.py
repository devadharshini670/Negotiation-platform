import os
from llm.mock_provider import decide as mock_decide
from llm.real_provider import decide as real_decide, available as real_available

def configured(): return real_available()
def status():
    live=real_available()
    return {'configured':live,'provider':'Anthropic' if live else 'Mock / Rule-Based','model':os.getenv('LLM_MODEL','claude-3-5-haiku-latest') if live else 'Deterministic negotiation engine'}
def reason(inp, mode):
    if mode=='llm' and real_available(): return real_decide(inp)
    return mock_decide(inp)
