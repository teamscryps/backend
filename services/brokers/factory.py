from __future__ import annotations
from .zerodha_adapter import ZerodhaAdapter
from .groww_adapter import GrowwAdapter
from .upstox_adapter import UpstoxAdapter
from .base import BrokerAdapter

def get_adapter(user) -> BrokerAdapter:
    broker = (user.broker or '').lower()
    if broker == 'zerodha':
        return ZerodhaAdapter(user)
    if broker == 'groww':
        return GrowwAdapter(user)
    if broker == 'upstox':
        return UpstoxAdapter(user)
    raise ValueError(f"Unsupported broker {user.broker}")
