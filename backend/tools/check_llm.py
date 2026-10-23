"""Live check of Groq and Gemini with YOUR keys (run from the backend folder):

    python tools/check_llm.py            # tests every provider that has a key
    python tools/check_llm.py groq       # or just one

Makes one small real request per provider, prints the model used, latency and any error.
Never prints a key."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from llm import provider  # noqa: E402

wanted = sys.argv[1:] or list(provider.REGISTRY)
bad = 0
for pid in wanted:
    r = provider.test_connection(pid)
    if r['ok']:
        print(f"[OK]   {r['label']}: model {r['model']}, {r['latency_ms']} ms, reply {r['sample']!r}")
    else:
        bad += 1
        print(f"[FAIL] {r['label']}: {r['error']['kind']} - {r['error']['message']}")
sys.exit(1 if bad else 0)
