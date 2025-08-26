"""WebSocket real-time broadcasting utilities.

Phase 1: In-process only. For multi-process scale-out, replace the internal
publish/broadcast mechanism with Redis pub/sub or Postgres LISTEN/NOTIFY.
"""
from __future__ import annotations
from typing import Dict, Set, Any, Callable
from fastapi import WebSocket
import asyncio
from collections import defaultdict

class ConnectionManager:
    def __init__(self) -> None:
        # Map client_id -> set of websockets
        self._client_conns: Dict[int, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, client_id: int, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._client_conns[client_id].add(websocket)

    async def disconnect(self, client_id: int, websocket: WebSocket):
        async with self._lock:
            conns = self._client_conns.get(client_id)
            if conns and websocket in conns:
                conns.remove(websocket)
                if not conns:
                    self._client_conns.pop(client_id, None)

    async def broadcast(self, client_id: int, message: dict):
        # Snapshot without holding lock during network sends
        async with self._lock:
            targets = list(self._client_conns.get(client_id, []))
        if not targets:
            return
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                conns = self._client_conns.get(client_id)
                if conns:
                    for d in dead:
                        conns.discard(d)
                    if not conns:
                        self._client_conns.pop(client_id, None)

manager = ConnectionManager()
