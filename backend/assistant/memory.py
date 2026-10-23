"""Conversation memory for the Assistant: one short transcript per (user, login session),
kept in server memory and completely separate from negotiation state. A user can only
ever reach their own key, so conversations are never visible across users or sessions."""
import threading
import time
from collections import deque

MAX_TURNS = 24            # messages kept per conversation
MAX_CONVERSATIONS = 500   # oldest are dropped beyond this
RATE_LIMIT = 30           # messages per user per minute (protects the shared LLM key)

_lock = threading.Lock()
_conversations = {}       # (user_id, session_id) -> {'messages': deque, 'touched': ts}
_recent = {}              # user_id -> deque of timestamps


def _key(user_id, session_id):
    return (str(user_id), str(session_id))


def history(user_id, session_id):
    with _lock:
        c = _conversations.get(_key(user_id, session_id))
        return [dict(m) for m in c['messages']] if c else []


def append(user_id, session_id, role, content, **extra):
    with _lock:
        c = _conversations.setdefault(_key(user_id, session_id), {'messages': deque(maxlen=MAX_TURNS), 'touched': 0})
        c['messages'].append({'role': role, 'content': content, **extra})
        c['touched'] = time.time()
        if len(_conversations) > MAX_CONVERSATIONS:
            oldest = min(_conversations, key=lambda k: _conversations[k]['touched'])
            _conversations.pop(oldest, None)


def reset(user_id, session_id):
    with _lock:
        _conversations.pop(_key(user_id, session_id), None)


def allow(user_id, now=None, limit=None):
    """Sliding one-minute rate limit per user."""
    now = time.time() if now is None else now
    with _lock:
        q = _recent.setdefault(str(user_id), deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= (limit or RATE_LIMIT):
            return False
        q.append(now)
        return True


def clear_all():
    with _lock:
        _conversations.clear()
        _recent.clear()
