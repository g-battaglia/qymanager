# PLAN — Web GUI editor QYConv v1.0

> **Obiettivo**: GUI web completa per importare, modificare, esportare file QY70/QY700
> (`.syx / .q7p / .blk / .mid`) + confronto diff + conversione lossy + realtime MIDI.
>
> Il backend Python è **già pronto** (F1→F12 completati, 428 test verdi). Questo piano
> costruisce un thin HTTP wrapper + SPA React sopra l'API esistente.

---

## Stack

| Area | Tech |
|------|------|
| Backend | FastAPI + uvicorn + python-multipart + websockets |
| Frontend | React 18 + Vite 5 + TypeScript 5 (strict) + Tailwind 3 + shadcn/ui + TanStack Query v5 |
| Realtime | WebSocket (`/api/midi/watch`) + REST (`/api/midi/emit`) |
| Packaging | Comando `qymanager serve` → FastAPI serve API + static mount build Vite |
| Electron | **Rinviato a v2.0** — stack già compatibile |

---

## Architettura

```
┌──────────────────── qymanager serve ────────────────────┐
│                                                         │
│  ┌─── FastAPI (web/backend/) ───┐   ┌─ static mount ─┐ │
│  │ /api/devices/*               │   │ web/frontend/   │ │
│  │ /api/diff                    │   │ dist/           │ │
│  │ /api/midi/* (REST + WS)      │   └─────────────────┘ │
│  │ /api/schema                  │                        │
│  └──────────┬───────────────────┘                        │
│             │ thin wrapper                               │
│             ▼                                            │
│  qymanager.formats.io / editor.ops / editor.realtime /   │
│  converters.udm_convert  (codice esistente — riuso puro) │
└──────────────────────────────────────────────────────────┘
                          ▲
                          │ HTTP + WS
                          │
┌──── Frontend (React + Vite + TS + shadcn) ────┐
│  Router: / /device/:id /diff /realtime        │
│  TanStack Query (cache API)                   │
│  Zustand (solo sessione MIDI se serve)        │
│  Schema-driven form (GET /api/schema)         │
└────────────────────────────────────────────────┘
```

**Principio guida**: il frontend è "dumb" sui range/enum dei campi XG — li scopre da
`GET /api/schema`. Aggiungere un campo UDM o una `Range` in `editor/schema.py` fa sì
che la UI lo renda automaticamente senza modifiche JS.

---

## Struttura directory (post W9)

```
qyconv/
├── PLAN/                      # questo piano (9 fasi W1-W9 + verification)
├── PROGRESS.md                # checklist esecutiva per ralph loop
├── PROMPT.md                  # prompt del ralph loop
├── opencode.jsonc             # default agent = qyconv-web
├── .opencode/
│   └── agents/
│       └── qyconv-web.md      # agente ralph loop
│
├── web/
│   ├── backend/               # FastAPI thin wrapper
│   │   ├── __init__.py
│   │   ├── app.py             # create_app(frontend_dir)
│   │   ├── session.py         # in-memory Device cache (uuid → Device)
│   │   ├── schemas.py         # pydantic I/O models
│   │   └── routes/
│   │       ├── devices.py     # POST/GET/PATCH/DELETE + validate + export
│   │       ├── diff.py        # POST /diff
│   │       ├── midi.py        # ports + emit + WS watch
│   │       └── schema.py      # GET /schema
│   │
│   └── frontend/              # React + Vite + TS
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.ts
│       ├── components.json    # shadcn config
│       ├── index.html
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           ├── lib/
│           │   ├── api.ts
│           │   ├── queries.ts
│           │   └── types.ts
│           ├── components/
│           │   ├── ui/        # shadcn primitives
│           │   ├── Uploader.tsx
│           │   ├── UDMTree.tsx
│           │   ├── FieldEditor.tsx
│           │   ├── ExportDialog.tsx
│           │   ├── DiffView.tsx
│           │   ├── RealtimePanel.tsx
│           │   └── WarningList.tsx
│           └── routes/
│               ├── Dashboard.tsx
│               ├── DeviceView.tsx
│               ├── DiffRoute.tsx
│               └── RealtimeRoute.tsx
│
├── cli/
│   ├── app.py                 # aggiunta: app.command("serve")(serve)
│   └── commands/
│       └── serve.py           # nuovo comando
│
└── tests/
    └── web/                   # pytest TestClient + mocked rtmidi
        ├── test_devices.py
        ├── test_diff.py
        ├── test_midi_ports_mock.py
        ├── test_midi_emit_mock.py
        ├── test_midi_ws_mock.py
        ├── test_schema_endpoint.py
        └── test_serve_integration.py
```

---

## Timeline fasi

| Fase | Titolo | File dettaglio | Stima task |
|------|--------|----------------|------------|
| **W1** | Backend devices routes (upload/get/patch/delete/validate/export) | `W1-backend-devices.md` | 8-10 |
| **W2** | Backend diff + schema + export + convert | `W2-diff-schema-export.md` | 5-7 |
| **W3** | Backend MIDI REST + WebSocket watch | `W3-midi-routes.md` | 5-7 |
| **W4** | Frontend scaffold (Vite+TS+Tailwind+shadcn+Router+Query) + Uploader + UDMTree | `W4-frontend-scaffold.md` | 8-10 |
| **W5** | FieldEditor schema-driven + PATCH wiring + validation | `W5-field-editor.md` | 5-7 |
| **W6** | ExportDialog + converter lossy + download | `W6-export-dialog.md` | 4-6 |
| **W7** | DiffRoute + DiffView component | `W7-diff-view.md` | 3-4 |
| **W8** | RealtimePanel (emit + watch WS) + Zustand MIDI session | `W8-realtime-panel.md` | 5-7 |
| **W9** | `qymanager serve` + static mount + docs + polish | `W9-serve-integration.md` | 4-6 |

**Totale**: ~50-65 task granulari in `PROGRESS.md`.

---

## Funzioni backend riusate (zero duplicazione)

| Endpoint | Funzione riusata |
|----------|------------------|
| `POST /api/devices` | `qymanager.formats.io.load_device(path)` dopo salvataggio tempfile |
| `GET /api/devices/{id}` | cache in `web.backend.session` |
| `PATCH /api/devices/{id}/field` | `qymanager.editor.ops.set_field(device, path, value)` |
| `POST /api/devices/{id}/validate` | `device.validate()` |
| `POST /api/devices/{id}/export` | `qymanager.converters.udm_convert.convert_file` + `save_device` |
| `DELETE /api/devices/{id}` | cache remove |
| `POST /api/diff` | iterazione su `udm_to_dict(device_a)` vs `udm_to_dict(device_b)` |
| `GET /api/midi/ports` | `qymanager.editor.realtime.list_output_ports/list_input_ports` |
| `POST /api/midi/emit` | `RealtimeSession.open(port).send_udm_edits(edits)` |
| `WS /api/midi/watch` | `RealtimeSession.open_input(port).watch_xg()` |
| `GET /api/schema` | introspezione `_FIXED_SPECS`, `_MULTI_PART_SPECS`, `_DRUM_NOTE_SPECS` |

**Nessun refactor** richiesto in `qymanager/` core.

---

## Criteri di successo v1.0

- [ ] `uv sync --extra web && cd web/frontend && npm install && npm run build` OK
- [ ] `qymanager serve` avvia e serve la UI su `http://127.0.0.1:8000`
- [ ] Drag-and-drop SGT.syx → UI mostra tree UDM completo
- [ ] Modifica `system.master_volume` con slider → valore persiste al refresh
- [ ] Export → `.q7p` download che riapre identico
- [ ] Converter tab → QY70→QY700 con `--drop fill-cc-dd` mostra warnings in tabella
- [ ] Realtime → list-ports mostra `UR22C Port 1`, emit slider volume verso device
- [ ] Realtime watch → muovo fader sul QY70 e vedo XG eventi live nella UI
- [ ] Backend: `pytest tests/web/` > 15 test verdi
- [ ] Frontend: `npm test` > 10 test Vitest verdi

---

## Out of scope v1.0 (rinviati)

- **Piano roll editor** per pattern note → v1.1
- **Chord timeline editor** con drag-drop chord changes → v1.1
- **Phrase library browser** con preview audio (dipende da P4b RE) → v1.2
- **Voice browser** con 519 XG voices preview → v1.2
- **Electron wrap + auto-updater** → v2.0 (architettura già compatibile)
- **Multi-user / auth** → fuori scope (tool desktop personale)
- **E2E test Playwright** → v1.1

---

## Rischi e mitigazioni

| Rischio | Mitigazione |
|---------|-------------|
| shadcn update breaking changes | Pin versione in `package.json` + commit lockfile |
| rtmidi non disponibile in ambiente server | WS `/midi/watch` ritorna 503 con messaggio chiaro se `_import_rtmidi()` fallisce; UI mostra banner "MIDI not available" |
| Upload file troppo grandi | Limit FastAPI `max_upload_size=5MB` (Q7P massimo ~6KB, margine ampio) |
| CORS in dev | Configurare `allow_origins=["http://localhost:5173"]` solo se `reload=True` |
| Sincronia cache server vs client | TanStack Query invalida `['device', id]` dopo ogni PATCH |
| Electron packaging futuro richiede IPC | Architettura HTTP già compatibile — Electron main process spawna uvicorn come child, renderer usa fetch verso `localhost:<random>` — zero refactoring lato React |

---

## Verifica end-to-end

Dettagliato in `PLAN/verification.md`.

```bash
# 1. Install
export UV_LINK_MODE=copy
uv sync --all-extras --group dev
cd web/frontend && npm install && npm run build && cd ../..

# 2. Test
uv run pytest tests/web/ -v
cd web/frontend && npm test && cd ../..

# 3. Boot
uv run qymanager serve --port 8000
# → apri http://127.0.0.1:8000

# 4. Smoke manuale
# Vedi PLAN/verification.md
```

---

Riferimenti:
- [`W1-backend-devices.md`](W1-backend-devices.md)
- [`W2-diff-schema-export.md`](W2-diff-schema-export.md)
- [`W3-midi-routes.md`](W3-midi-routes.md)
- [`W4-frontend-scaffold.md`](W4-frontend-scaffold.md)
- [`W5-field-editor.md`](W5-field-editor.md)
- [`W6-export-dialog.md`](W6-export-dialog.md)
- [`W7-diff-view.md`](W7-diff-view.md)
- [`W8-realtime-panel.md`](W8-realtime-panel.md)
- [`W9-serve-integration.md`](W9-serve-integration.md)
- [`verification.md`](verification.md)
