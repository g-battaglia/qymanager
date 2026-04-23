# Web GUI v1.0

**Status**: production (MVP-1 — W1+W2+W4+W5+W6+W9 shipped).

Browser-based editor for QY70/QY700 device files. Thin HTTP wrapper + SPA
over the Unified Data Model (UDM).

## Quickstart

```bash
export UV_LINK_MODE=copy
uv sync --all-extras --group dev
cd web/frontend && npm install && npm run build && cd ../..
uv run qymanager serve
# Open http://127.0.0.1:8000
```

## Dev mode (hot reload)

```bash
# Unified launcher (recommended)
bash web/dev.sh start              # start both backend + frontend
bash web/dev.sh status             # show running services
bash web/dev.sh logs backend       # tail backend logs
bash web/dev.sh stop               # stop all

# Manual (separate terminals)
uv run qymanager serve --port 8000 --reload   # terminal 1
cd web/frontend && npm run dev                 # terminal 2
# Open http://127.0.0.1:5173
```

The dev launcher manages PID tracking and logs under `web/.dev/`.
Run `bash web/dev.sh help` for all commands.

## Endpoint API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/devices` | Upload `.syx / .q7p / .blk / .mid` |
| GET | `/api/devices/{id}` | Get UDM as JSON |
| PATCH | `/api/devices/{id}/field` | Update single field via path |
| POST | `/api/devices/{id}/validate` | Run device.validate() |
| POST | `/api/devices/{id}/export` | Export in any format (+ lossy conversion) |
| DELETE | `/api/devices/{id}` | Remove from session |
| POST | `/api/diff` | Diff two devices |
| GET | `/api/schema` | UDM field specs (for schema-driven UI) |

## Testing

```bash
uv run pytest tests/web/ -v              # backend (18 tests)
cd web/frontend && npm test && cd ../..   # frontend Vitest (6 tests)
```

## What works (MVP-1)

- Drag-and-drop upload of `.syx / .q7p / .blk / .mid`
- Recursive tree view of the entire UDM
- Schema-driven field editor (Slider for ranges, Select for enums)
- Export to any supported format with lossy conversion warnings
- Side-by-side diff of two devices (API ready, frontend deferred)
- `qymanager serve` serves backend + frontend build

## What's deferred (post-MVP)

- **Realtime MIDI** (W3/W8): MIDI port listing, XG emit, WebSocket watch
- **Diff view** (W7): Side-by-side UI component (backend endpoint ready)

## Riferimenti

- [udm.md](udm.md) — data model
- [xg-parameters.md](xg-parameters.md) — XG SysEx
- [../PLAN/00-overview.md](../PLAN/00-overview.md) — full plan
