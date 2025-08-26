from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from security import get_current_user
from models.user import User as UserModel
from realtime import manager
from event_bus import subscribe
from typing import Any, Dict
import asyncio

router = APIRouter()

CLIENT_EVENT_TYPES = {"order.new", "order.fill", "order.cancel"}

# In-memory subscription registry to avoid duplicate subscription per process
_subscribed = False
_queue_map: Dict[int, asyncio.Queue] = {}

def _ensure_subscription():
    global _subscribed
    if _subscribed:
        return
    # Single wildcard subscriber then route per user_id
    def _handler(ev: Dict[str, Any]):
        user_id = ev.get("user_id")
        if not user_id:
            return
        q = _queue_map.get(user_id)
        if q:
            try:
                q.put_nowait(ev)
            except Exception:
                pass
    subscribe("*", _handler)
    _subscribed = True


@router.websocket("/ws/client/{client_id}")
async def client_ws(websocket: WebSocket, client_id: int, current_user: UserModel = Depends(get_current_user)):
    if current_user.id != client_id and current_user.role != 'trader':
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    _ensure_subscription()
    queue: asyncio.Queue = _queue_map.get(client_id) or asyncio.Queue()
    _queue_map[client_id] = queue
    await manager.connect(client_id, websocket)
    await manager.broadcast(client_id, {"event": "connection_ack", "client_id": client_id})
    try:
        while True:
            # Race: client messages (ignored for now) or queued events
            done, pending = await asyncio.wait(
                [asyncio.create_task(websocket.receive_text()), asyncio.create_task(queue.get())],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=30.0,
            )
            for task in done:
                if task.cancelled():
                    continue
                if task.exception():
                    # If receive_text closed, break
                    if isinstance(task.exception(), Exception):
                        pass
                result = task.result()
                if isinstance(result, str):
                    # Optional ping/pong logic
                    if result == 'ping':
                        await websocket.send_json({"event": "pong"})
                elif isinstance(result, dict):
                    etype = result.get("type")
                    # Normalize event names
                    if etype in CLIENT_EVENT_TYPES:
                        payload = result.copy()
                        payload["event"] = etype
                        await manager.broadcast(client_id, payload)
            # Clean up pending tasks (timeout path)
            for p in pending:
                p.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(client_id, websocket)
        # If no more connections, drop queue
        if client_id not in getattr(manager, '_client_conns', {}):  # type: ignore
            _queue_map.pop(client_id, None)
