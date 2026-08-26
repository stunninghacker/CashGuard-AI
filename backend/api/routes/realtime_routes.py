"""
Webhooks, mock I4C inbox, realtime WS, and live-stream ingestion.

POST /mock-i4c-inbox        -> local receiver for the REAL outbound webhook path
                                (dispatch + CFCFRMS stubs). Stores + displays intel.
GET  /mock-i4c-inbox        -> received intel list (I4C Inbox panel)
WS   /ws/alerts             -> live push of alerts / status / recovery events
POST /ingest/stream/start   -> StreamSimulatorAdapter: drip new complaints+withdrawals
POST /ingest/stream/stop

The webhook path is REAL (httpx -> this endpoint); the inbox is local and mock.
KafkaAdapter (true scale vs ~8,000 complaints/day) is a Tier 2 stub.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ... import repositories as repo, services
from ...database import SessionLocal, get_db
from ...realtime import manager
from ...security import require_auth

router = APIRouter(tags=["realtime"])


# ------------------------------ Mock I4C inbox ------------------------------
@router.post("/mock-i4c-inbox")
async def mock_i4c_inbox(request: Request, db: Session = Depends(get_db)):
    """Receives REAL webhook POSTs (dispatch + CFCFRMS stub) and stores them."""
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": "unparseable"}
    channel = payload.get("channel", "unknown")
    stored = repo.store_inbox_message(db, channel, payload)
    return {"received": True, "id": stored.id, "channel": channel}


@router.get("/mock-i4c-inbox")
def inbox_list(user=Depends(require_auth("I4C_ADMIN", "POLICE_STATE", "POLICE_DISTRICT")), db: Session = Depends(get_db)):
    messages = repo.list_inbox_messages(db, limit=100)
    return [
        {"id": m.id, "received_at": m.received_at.isoformat(), "channel": m.channel,
         "payload": json.loads(m.payload)}
        for m in messages
    ]


# ------------------------------ WebSocket live push --------------------------
@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ------------------------------ Live-stream ingestion -------------------------
class _StreamState:
    task: asyncio.Task | None = None


_stream = _StreamState()


@router.post("/ingest/stream/start")
async def ingest_stream_start(user=Depends(require_auth("I4C_ADMIN")), db: Session = Depends(get_db)):
    """StreamSimulatorAdapter — drips new synthetic complaints/withdrawals into the
    DB in real time so the map + risk update live. KafkaAdapter = Tier 2 stub."""
    if _stream.task is not None and not _stream.task.done():
        return {"status": "already_running"}

    async def _drip():
        from ...data.synthetic_data import load_calibration_config
        import random

        cfg = load_calibration_config()
        rng = random.Random()
        while True:
            session = SessionLocal()
            try:
                created = services.drip_ingest(session, rng, cfg)
                if created:
                    await manager.broadcast("ingest", {"event": "stream_drip", "items": created})
            except Exception as exc:
                # log, don't silently swallow — a drip failure must be visible
                print(f"[stream] drip failed: {exc}", flush=True)
            finally:
                session.close()
            await asyncio.sleep(3)

    _stream.task = asyncio.create_task(_drip())
    return {"status": "streaming", "note": "StreamSimulatorAdapter — one drip every ~3s (mock live NCRP feed)"}


@router.post("/ingest/stream/stop")
async def ingest_stream_stop(user=Depends(require_auth("I4C_ADMIN"))):
    if _stream.task is not None:
        _stream.task.cancel()
        _stream.task = None
    return {"status": "stopped"}