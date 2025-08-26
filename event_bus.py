"""Simple in-process event bus (Phase 1 placeholder).

Future: replace with Redis pub/sub or WebSocket broadcaster.
"""
from collections import defaultdict
from typing import Callable, Any, Dict, List
import threading

_lock = threading.Lock()
_subscribers: Dict[str, List[Callable[[dict], None]]] = defaultdict(list)

def subscribe(event_type: str, callback: Callable[[dict], None]):
    with _lock:
        _subscribers[event_type].append(callback)

def publish(event_type: str, payload: dict):
    # Copy to avoid mutation while iterating
    with _lock:
        subs = list(_subscribers.get(event_type, []))
        subs_all = list(_subscribers.get("*", []))
    for cb in subs + subs_all:
        try:
            cb({"type": event_type, **payload})
        except Exception:
            # Silently ignore for now; can add logging hook
            pass
