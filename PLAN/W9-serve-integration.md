# W9 — `qymanager serve` + static mount + docs

> **Obiettivo**: comando CLI `qymanager serve` che avvia uvicorn con FastAPI + serve il
> build React statico. Documentazione finale in `wiki/web-gui.md`, `README.md`, `STATUS.md`.

## Comando `cli/commands/serve.py`

```python
from __future__ import annotations
from pathlib import Path
from typing import Optional

import typer


def serve(
    host: str = typer.Option("127.0.0.1", help="Host interface"),
    port: int = typer.Option(8000, help="Port"),
    reload: bool = typer.Option(False, help="Enable auto-reload (dev)"),
    frontend_dir: Optional[Path] = typer.Option(
        None, help="Directory containing built frontend (default: web/frontend/dist)"
    ),
) -> None:
    """Start the QYConv web GUI server (FastAPI + React build)."""
    import uvicorn
    from web.backend.app import create_app

    default_dir = Path(__file__).resolve().parents[2] / "web" / "frontend" / "dist"
    effective_dir = frontend_dir if frontend_dir is not None else default_dir

    if not effective_dir.exists():
        typer.echo(
            f"Frontend build not found at {effective_dir}. "
            "Run 'cd web/frontend && npm run build' first, or start Vite dev server "
            "separately on :5173 and this server on :8000 (proxy configured).",
            err=True,
        )
        effective_dir = None  # type: ignore[assignment]

    app = create_app(frontend_dir=effective_dir, dev=reload)
    uvicorn.run(app, host=host, port=port, reload=reload)
```

## Wire in `cli/app.py`

Trovare la linea di registrazione comandi (pattern: `app.command(...)`) e aggiungere:

```python
from cli.commands.serve import serve
app.command(name="serve")(serve)
```

## Update `web/backend/app.py`

Verificare che `create_app` accetti `frontend_dir` e monti `StaticFiles(..., html=True)`
come già definito in W1.

### Fallback SPA routing

FastAPI `StaticFiles(html=True)` serve `index.html` per 404. Se la SPA ha rotte `/diff`,
`/realtime`, al refresh diretto serve il fallback.

## Aggiornare documentazione

### Nuova pagina `wiki/web-gui.md`

```markdown
# Web GUI v1.0

**Status**: production (W1-W9 delivered).

GUI web per editing offline/realtime dei device QY70/QY700. Thin wrapper HTTP + SPA
sopra l'UDM.

## Architettura

Vedi [PLAN/00-overview.md](../PLAN/00-overview.md) per dettaglio.

## Quickstart

```bash
export UV_LINK_MODE=copy
uv sync --all-extras --group dev
cd web/frontend && npm install && npm run build && cd ../..
uv run qymanager serve
# → http://127.0.0.1:8000
```

## Dev mode (hot reload)

```bash
# Terminal 1 — backend
uv run qymanager serve --port 8000 --reload

# Terminal 2 — frontend Vite dev server con proxy /api
cd web/frontend && npm run dev
# → http://127.0.0.1:5173
```

## Endpoint API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/devices` | Upload `.syx / .q7p / .blk / .mid` |
| GET | `/api/devices/{id}` | Get UDM |
| PATCH | `/api/devices/{id}/field` | Update single field via path |
| POST | `/api/devices/{id}/validate` | Run device.validate() |
| POST | `/api/devices/{id}/export` | Export in any format (+ lossy conversion) |
| DELETE | `/api/devices/{id}` | Remove from session |
| POST | `/api/diff` | Diff two devices |
| GET | `/api/schema` | UDM field specs (for UI auto-form) |
| GET | `/api/midi/ports` | List MIDI in/out |
| POST | `/api/midi/emit` | Send XG Parameter Change |
| WS | `/api/midi/watch` | Stream incoming XG events |

## Testing

```bash
uv run pytest tests/web/ -v                    # backend
cd web/frontend && npm test && cd ../..        # frontend Vitest
```

## Riferimenti

- [udm.md](udm.md) — modello dati
- [xg-parameters.md](xg-parameters.md) — XG SysEx
- [../PLAN/00-overview.md](../PLAN/00-overview.md) — piano dettagliato
```

### `wiki/index.md` — aggiunta

Aggiungi nella sezione "Infrastructure":

```markdown
- [Web GUI](web-gui.md) — FastAPI + React editor (v1.0)
```

### `README.md` — sezione "Web GUI"

Aggiungi dopo "CLI":

```markdown
## Web GUI

A full browser-based editor ships as part of QYConv v1.0:

```bash
uv sync --all-extras --group dev
cd web/frontend && npm install && npm run build && cd ../..
uv run qymanager serve
# Open http://127.0.0.1:8000
```

Features:

- Drag-and-drop upload of `.syx / .q7p / .blk / .mid`
- Schema-driven field editor with live validation
- Export to any supported format with lossy conversion (drop/keep granular)
- Side-by-side diff of two devices
- Realtime MIDI: send XG Parameter Change live, watch incoming events

See [wiki/web-gui.md](wiki/web-gui.md) for full docs.
```

### `STATUS.md` — update

Aggiorna:

```markdown
Ultimo aggiornamento: 2026-04-17 (W9 web GUI v1.0 shipped)
```

Aggiungi riga nella tabella "Valutazione generale":

```markdown
| Web GUI v1.0 | ✅ production | FastAPI + React, tutti gli endpoint + realtime MIDI |
```

## Smoke test

```bash
# 1. Build completo
cd web/frontend && npm run build && cd ../..

# 2. Serve
uv run qymanager serve --port 8123 &
SERVER_PID=$!
sleep 2

# 3. Verifica
curl -s http://127.0.0.1:8123/ | grep -q "<!doctype html>" && echo "OK static"
curl -s http://127.0.0.1:8123/api/schema | python -c "import json, sys; print(len(json.load(sys.stdin)['paths']))"

kill $SERVER_PID
```

## Task granulari

1. Creare `cli/commands/serve.py` con typer wrapper
2. Wire `serve` in `cli/app.py`
3. Verificare `web/backend/app.py::create_app` monta static
4. Creare `wiki/web-gui.md`
5. Aggiornare `wiki/index.md` con link a `web-gui.md`
6. Aggiungere sezione "Web GUI" in `README.md`
7. Aggiornare `STATUS.md` con v1.0 GUI shipped
8. Smoke test: `uv run qymanager serve --port 8123` + curl checks
9. Commit finale: `docs(web): W9 — qymanager serve + web GUI v1.0 shipped`

## Verifica

```bash
uv run pytest tests/web/ -v
cd web/frontend && npm test && npm run build && cd ../..
uv run qymanager serve --help

# Smoke: boot + curl (vedi sopra)
```
