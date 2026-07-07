import threading
import time
from collections import defaultdict, deque

_events = defaultdict(deque)
_lock = threading.Lock()


def allow(key, limit, window_seconds):
    now = time.monotonic()
    with _lock:
        q = _events[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def reset_for_tests():
    with _lock:
        _events.clear()
