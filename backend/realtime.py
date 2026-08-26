"""
Realtime push (Phase 5 — dashboard channel of the notification system).

WS /ws/alerts broadcasts alert + recovery events to connected Police/Bank/I4C
dashboards. The broadcast is role-scoped client-side (the frontend renders what
its role may see); server-side row-level protection remains the authoritative
control for REST reads.
"""
from __future__ import annotations

import json

from fastapi import WebSocket

class ConnectionManager:
    def __init__(self) -> None:
        self._sockets: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._sockets.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._sockets:
            self._sockets.remove(ws)

    async def broadcast(self, event_type: str, payload: dict) -> None:
        message = json.dumps({"event": event_type, "payload": payload}, default=str)
        dead: list[WebSocket] = []
        for ws in self._sockets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def enqueue_broadcast(event_type: str, payload: dict) -> None:
    """Fire-and-forget push from synchronous code (scheduler/services)."""
    import asyncio

    try:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast(event_type, payload), _get_loop()
        )
    except Exception:
        pass  # no connected clients / no loop — non-fatal


_loop = None


def bind_loop(loop) -> None:
    global _loop
    _loop = loop


def _get_loop():
    import asyncio

    return _loop or asyncio.get_event_loop()