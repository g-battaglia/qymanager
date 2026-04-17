# W3 — Backend MIDI routes (REST + WebSocket)

> **Obiettivo**: 3 endpoint per realtime MIDI, completamente testati con rtmidi mockato.

## Contratti

| Metodo | Path | Body | Risposta |
|--------|------|------|----------|
| GET | `/api/midi/ports` | — | `{outputs: [str], inputs: [str]}` |
| POST | `/api/midi/emit` | `{port: str, edits: {path: value}, device_number?: int}` | `{sysex_hex: str}` |
| WS  | `/api/midi/watch` | query `?port=<name>` | stream `{ah, am, al, value, raw_hex}` |

## Route `routes/midi.py`

```python
from __future__ import annotations
import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from qymanager.editor import realtime as rt
from qymanager.model.device import Device

router = APIRouter(tags=["midi"])


class MidiPortsResponse(BaseModel):
    outputs: list[str]
    inputs: list[str]


class EmitRequest(BaseModel):
    port: str
    edits: dict[str, Any]
    device_number: int = Field(default=0, ge=0, le=15)


class EmitResponse(BaseModel):
    sysex_hex: str


@router.get("/midi/ports", response_model=MidiPortsResponse)
def list_ports() -> MidiPortsResponse:
    try:
        outs = rt.list_output_ports()
        ins = rt.list_input_ports()
    except RuntimeError as e:
        raise HTTPException(503, f"MIDI unavailable: {e}") from e
    return MidiPortsResponse(outputs=outs, inputs=ins)


@router.post("/midi/emit", response_model=EmitResponse)
def emit_edits(req: EmitRequest) -> EmitResponse:
    try:
        session = rt.RealtimeSession.open(req.port, device_number=req.device_number)
    except RuntimeError as e:
        raise HTTPException(503, f"Cannot open port: {e}") from e
    try:
        messages = session.send_udm_edits(req.edits)
        sysex_hex = " ".join(f"{b:02X}" for m in messages for b in m)
    finally:
        session.close()
    return EmitResponse(sysex_hex=sysex_hex)


@router.websocket("/midi/watch")
async def watch_xg(ws: WebSocket, port: str = Query(...)) -> None:
    await ws.accept()
    try:
        session = rt.RealtimeSession.open_input(port)
    except RuntimeError as e:
        await ws.send_json({"error": f"Cannot open input: {e}"})
        await ws.close(code=1011)
        return

    loop = asyncio.get_event_loop()

    async def pump() -> None:
        try:
            async for event in _async_watch(session, loop):
                await ws.send_json(event)
        except asyncio.CancelledError:
            pass

    task = loop.create_task(pump())
    try:
        while True:
            await ws.receive_text()  # client keepalive / drain
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        session.close()


async def _async_watch(session: Any, loop: asyncio.AbstractEventLoop):
    def next_event() -> dict | None:
        try:
            return next(session.watch_xg(timeout_s=0.1))
        except StopIteration:
            return None

    while True:
        ev = await loop.run_in_executor(None, next_event)
        if ev is None:
            await asyncio.sleep(0.01)
            continue
        yield {
            "ah": ev.ah,
            "am": ev.am,
            "al": ev.al,
            "value": ev.value,
            "raw_hex": ev.raw_hex if hasattr(ev, "raw_hex") else None,
        }
```

**Nota**: l'API esatta di `RealtimeSession.watch_xg()` va verificata in
`qymanager/editor/realtime.py` prima della scrittura definitiva. Se è un generator
sincrono o uno stream async-compatibile, adattare `_async_watch`.

## Test con mock rtmidi

`tests/web/test_midi_ports_mock.py`:

```python
import pytest
from unittest.mock import patch


def test_ports_list_ok(client):
    with patch("qymanager.editor.realtime.list_output_ports", return_value=["UR22C Port 1"]), \
         patch("qymanager.editor.realtime.list_input_ports", return_value=["UR22C Port 1"]):
        r = client.get("/api/midi/ports")
    assert r.status_code == 200
    assert r.json() == {"outputs": ["UR22C Port 1"], "inputs": ["UR22C Port 1"]}


def test_ports_rtmidi_unavailable_503(client):
    with patch("qymanager.editor.realtime.list_output_ports",
               side_effect=RuntimeError("no rtmidi")):
        r = client.get("/api/midi/ports")
    assert r.status_code == 503
```

`tests/web/test_midi_emit_mock.py`:

```python
from unittest.mock import MagicMock, patch


def test_emit_ok(client):
    fake_session = MagicMock()
    fake_session.send_udm_edits.return_value = [bytes.fromhex("F043104C0000014AF7")]

    with patch("qymanager.editor.realtime.RealtimeSession.open",
               return_value=fake_session):
        r = client.post("/api/midi/emit", json={
            "port": "UR22C Port 1",
            "edits": {"system.master_volume": 100},
        })

    assert r.status_code == 200
    assert "F0 43 10 4C" in r.json()["sysex_hex"]
    fake_session.close.assert_called_once()
```

`tests/web/test_midi_ws_mock.py`:

```python
from unittest.mock import MagicMock, patch


def test_watch_ws_streams_events(client):
    fake_session = MagicMock()
    events = iter([
        MagicMock(ah=0, am=0, al=0x04, value=100, raw_hex=None),
    ])
    fake_session.watch_xg.return_value = events

    with patch("qymanager.editor.realtime.RealtimeSession.open_input",
               return_value=fake_session):
        with client.websocket_connect("/api/midi/watch?port=X") as ws:
            ev = ws.receive_json()
    assert ev["al"] == 0x04 and ev["value"] == 100
```

(Adattare il mocking se la firma di `watch_xg` differisce.)

## Wire-up

```python
# app.py
from .routes import devices, diff, schema, midi
app.include_router(midi.router, prefix="/api")
```

## Task granulari

1. Leggere `qymanager/editor/realtime.py` per confermare firma `RealtimeSession` + `watch_xg`
2. Creare `web/backend/routes/midi.py` con 3 endpoint
3. Wire router
4. `tests/web/test_midi_ports_mock.py` (2 test)
5. `tests/web/test_midi_emit_mock.py` (2 test — ok + port unavailable)
6. `tests/web/test_midi_ws_mock.py` (1-2 test)
7. Commit: `feat(web-backend): W3 — MIDI REST + WebSocket watch`

## Verifica

```bash
uv run pytest tests/web/test_midi_*.py -v
uv run ruff check web/backend/routes/midi.py
```

## Hardware smoke test (manuale, non in CI)

Con UR22C collegato:
```bash
export QY_HARDWARE=1
uv run python -c "
from fastapi.testclient import TestClient
from web.backend.app import create_app
c = TestClient(create_app())
print(c.get('/api/midi/ports').json())
"
```
