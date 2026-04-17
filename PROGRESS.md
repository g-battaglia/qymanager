# PROGRESS.md — Web GUI v1.0 task checklist

> **Uso**: l'agente `qyconv-web` marca `[x]` ogni task completato. Legge questa lista in
> ordine e lavora UN task per iterazione. Stop quando tutti `[x]` / `[~]`.
>
> Legenda: `[ ]` todo · `[x]` done · `[~]` skipped (con nota) · `[!]` blocked (con nota)

---

## Setup pre-W1 (una volta)

- [ ] **S0.1** Aggiungere `[project.optional-dependencies].web` in `pyproject.toml`:
  ```toml
  web = [
      "fastapi>=0.110",
      "uvicorn[standard]>=0.27",
      "python-multipart>=0.0.9",
      "websockets>=12",
  ]
  ```
- [ ] **S0.2** `export UV_LINK_MODE=copy && uv sync --all-extras --group dev` (verifica fastapi installato)
- [ ] **S0.3** Commit: `chore(deps): add web optional group (fastapi + uvicorn + websockets)`

---

## W1 — Backend devices routes

Dettaglio: [`PLAN/W1-backend-devices.md`](PLAN/W1-backend-devices.md)

- [ ] **W1.1** Creare directory `web/` + `web/__init__.py` + `web/backend/__init__.py`
- [ ] **W1.2** Creare `web/backend/session.py` (DeviceSession in-memory cache con RLock, `get_session()` singleton)
- [ ] **W1.3** Creare `web/backend/schemas.py` (pydantic I/O models)
- [ ] **W1.4** Creare `web/backend/app.py` con `create_app(frontend_dir=None, dev=False)` + CORS dev
- [ ] **W1.5** Creare `web/backend/routes/__init__.py`
- [ ] **W1.6** Creare `web/backend/routes/devices.py` con `POST /devices` (upload multipart + tempfile + load_device)
- [ ] **W1.7** Aggiungere `GET /devices/{id}` (cache lookup + udm_to_dict)
- [ ] **W1.8** Aggiungere `PATCH /devices/{id}/field` (set_field + errors array)
- [ ] **W1.9** Aggiungere `POST /devices/{id}/validate` (device.validate())
- [ ] **W1.10** Aggiungere `POST /devices/{id}/export` (save_device o convert_file + Response binario + X-Warnings header)
- [ ] **W1.11** Aggiungere `DELETE /devices/{id}`
- [ ] **W1.12** Creare `tests/web/__init__.py` + `tests/web/conftest.py` (fixtures client + clean_session)
- [ ] **W1.13** Creare `tests/web/test_devices.py` con test 1-4 (upload syx ok, upload q7p ok, upload invalid 400, upload too large 413)
- [ ] **W1.14** Estendere `tests/web/test_devices.py` con test 5-7 (get 404, patch ok, patch out-of-range)
- [ ] **W1.15** Estendere `tests/web/test_devices.py` con test 8-11 (validate, export syx roundtrip, export convert qy70→qy700, delete)
- [ ] **W1.16** Verificare `uv run pytest tests/web/ -v` → tutti verdi; `uv run pytest` → 428+nuovi verdi
- [ ] **W1.17** Commit: `feat(web-backend): W1 — FastAPI devices routes with TestClient coverage`

---

## W2 — Backend diff + schema endpoints

Dettaglio: [`PLAN/W2-diff-schema-export.md`](PLAN/W2-diff-schema-export.md)

- [ ] **W2.1** Ispezionare `qymanager/editor/schema.py` per confermare nomi esatti delle mappe spec (`_FIXED_SPECS` / `_MULTI_PART_SPECS` / `_DRUM_NOTE_SPECS`)
- [ ] **W2.2** Creare `web/backend/routes/diff.py` con `_flatten` helper + `POST /diff`
- [ ] **W2.3** Creare `web/backend/routes/schema.py` con `GET /schema` (introspezione)
- [ ] **W2.4** Wire routers diff + schema in `web/backend/app.py`
- [ ] **W2.5** Creare `tests/web/test_diff.py` con 3 test (identical, after-patch, not-found)
- [ ] **W2.6** Creare `tests/web/test_schema.py` con 2 test (paths non vuoti, multi_part pattern presente)
- [ ] **W2.7** Verificare `uv run pytest tests/web/ -v` verde
- [ ] **W2.8** Commit: `feat(web-backend): W2 — diff + schema endpoints`

---

## W3 — Backend MIDI routes (REST + WebSocket)

Dettaglio: [`PLAN/W3-midi-routes.md`](PLAN/W3-midi-routes.md)

- [ ] **W3.1** Ispezionare `qymanager/editor/realtime.py` per confermare API `RealtimeSession.open`, `open_input`, `send_udm_edits`, `watch_xg`, `list_output_ports`, `list_input_ports`
- [ ] **W3.2** Creare `web/backend/routes/midi.py` con `GET /midi/ports`
- [ ] **W3.3** Aggiungere `POST /midi/emit` con RealtimeSession.open + send_udm_edits + close
- [ ] **W3.4** Aggiungere `WS /midi/watch` con asyncio bridge verso watch_xg generator
- [ ] **W3.5** Wire router midi in `app.py`
- [ ] **W3.6** Creare `tests/web/test_midi_ports_mock.py` con 2 test (ports ok, ports 503)
- [ ] **W3.7** Creare `tests/web/test_midi_emit_mock.py` con 2 test (emit ok, emit port unavailable)
- [ ] **W3.8** Creare `tests/web/test_midi_ws_mock.py` con 1 test (WS streams 1 event)
- [ ] **W3.9** Verificare `uv run pytest tests/web/ -v` verde
- [ ] **W3.10** Commit: `feat(web-backend): W3 — MIDI REST + WebSocket watch`

---

## W4 — Frontend scaffold + Uploader + UDMTree

Dettaglio: [`PLAN/W4-frontend-scaffold.md`](PLAN/W4-frontend-scaffold.md)

- [ ] **W4.1** `mkdir -p web/frontend && cd web/frontend && npm create vite@latest . -- --template react-ts` (confermare overwrite)
- [ ] **W4.2** `npm install` dipendenze base
- [ ] **W4.3** `npm install react-router-dom @tanstack/react-query`
- [ ] **W4.4** `npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`
- [ ] **W4.5** `npx shadcn@latest init -d` (style: Default, base color: Slate)
- [ ] **W4.6** `npx shadcn@latest add button input label slider select checkbox dialog tabs table scroll-area tooltip toast`
- [ ] **W4.7** `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom` + `vitest.config.ts` + `src/test/setup.ts`
- [ ] **W4.8** Configurare `vite.config.ts` (alias `@`, proxy `/api` → `http://127.0.0.1:8000`, WS proxy)
- [ ] **W4.9** Configurare `tsconfig.json` (strict, `paths: {"@/*": ["./src/*"]}`)
- [ ] **W4.10** Aggiungere npm scripts (`dev`, `build`, `lint`, `typecheck`, `test`)
- [ ] **W4.11** Creare `src/lib/types.ts` (UdmDevice, UploadResponse, FieldPatch, SchemaEntry, DiffChange)
- [ ] **W4.12** Creare `src/lib/api.ts` (fetch wrapper tipizzato — upload, get, patch, delete, schema, diff, midi, export)
- [ ] **W4.13** Creare `src/lib/queries.ts` (useDevice, useSchema, useMidiPorts, usePatchField)
- [ ] **W4.14** Aggiornare `src/App.tsx` con BrowserRouter + QueryClientProvider + Toaster + routes
- [ ] **W4.15** Creare `src/components/Uploader.tsx` (drag-and-drop + browse button)
- [ ] **W4.16** Creare `src/components/UDMTree.tsx` (rendering ricorsivo con espansione)
- [ ] **W4.17** Creare `src/routes/Dashboard.tsx` (Uploader + nav link)
- [ ] **W4.18** Creare `src/routes/DeviceView.tsx` (grid tree+main panel, useDevice, selected state)
- [ ] **W4.19** Creare `src/test/__tests__/Uploader.test.tsx`
- [ ] **W4.20** Creare `src/test/__tests__/UDMTree.test.tsx`
- [ ] **W4.21** Creare `src/test/__tests__/api.test.ts`
- [ ] **W4.22** Verificare `npm run typecheck && npm test && npm run build` tutto verde
- [ ] **W4.23** Commit: `feat(web-frontend): W4 — scaffold React+Vite+TS+shadcn + Uploader + UDMTree`

---

## W5 — FieldEditor schema-driven + PATCH

Dettaglio: [`PLAN/W5-field-editor.md`](PLAN/W5-field-editor.md)

- [ ] **W5.1** Verificare componenti shadcn needed (toast, slider, select, input, label)
- [ ] **W5.2** Creare `src/lib/path.ts` con `getByPath(obj, path)`
- [ ] **W5.3** Creare `src/components/FieldEditor.tsx` con matchSchema + range/enum/raw rendering
- [ ] **W5.4** Integrare FieldEditor in `src/routes/DeviceView.tsx` (selected state + getByPath)
- [ ] **W5.5** Aggiungere `<Toaster />` in `App.tsx`
- [ ] **W5.6** Creare `src/test/__tests__/FieldEditor.test.tsx` con 4 test (slider render, select render, PATCH call, toast on error)
- [ ] **W5.7** Creare `src/test/__tests__/path.test.ts` con 2 test
- [ ] **W5.8** Verificare `npm run typecheck && npm test && npm run build` verde
- [ ] **W5.9** Commit: `feat(web-frontend): W5 — FieldEditor schema-driven with PATCH and toast`

---

## W6 — ExportDialog + WarningList + download

Dettaglio: [`PLAN/W6-export-dialog.md`](PLAN/W6-export-dialog.md)

- [ ] **W6.1** Verificare shadcn dialog/table/checkbox/label presenti
- [ ] **W6.2** Aggiornare `src/lib/api.ts` `exportDevice` per leggere header `X-Warnings` e ritornare `{blob, warnings}`
- [ ] **W6.3** Creare `src/components/WarningList.tsx`
- [ ] **W6.4** Creare `src/components/ExportDialog.tsx` (format select + target + drop groups + download)
- [ ] **W6.5** Integrare ExportDialog in header di `src/routes/DeviceView.tsx`
- [ ] **W6.6** Creare `src/test/__tests__/ExportDialog.test.tsx` (3 test)
- [ ] **W6.7** Creare `src/test/__tests__/WarningList.test.tsx` (2 test)
- [ ] **W6.8** Verificare `npm run typecheck && npm test && npm run build` verde
- [ ] **W6.9** Commit: `feat(web-frontend): W6 — ExportDialog + WarningList + lossy conversion`

---

## W7 — DiffRoute + DiffView

Dettaglio: [`PLAN/W7-diff-view.md`](PLAN/W7-diff-view.md)

- [ ] **W7.1** Creare `src/components/DiffView.tsx` (tabella side-by-side)
- [ ] **W7.2** Creare `src/routes/DiffRoute.tsx` (2 UploadSlot + compare button)
- [ ] **W7.3** Registrare `<Route path="/diff">` in `App.tsx`
- [ ] **W7.4** Aggiungere nav link `/diff` in Dashboard
- [ ] **W7.5** Creare `src/test/__tests__/DiffView.test.tsx` (3 test)
- [ ] **W7.6** Creare `src/test/__tests__/DiffRoute.test.tsx` (1 test)
- [ ] **W7.7** Verificare `npm run typecheck && npm test && npm run build` verde
- [ ] **W7.8** Commit: `feat(web-frontend): W7 — DiffRoute + DiffView side-by-side`

---

## W8 — RealtimePanel (emit + watch WS)

Dettaglio: [`PLAN/W8-realtime-panel.md`](PLAN/W8-realtime-panel.md)

- [ ] **W8.1** Verificare shadcn scroll-area + tabs presenti
- [ ] **W8.2** Creare directory `src/components/realtime/`
- [ ] **W8.3** Creare `src/components/realtime/SendPanel.tsx` (port select + edits list + emit)
- [ ] **W8.4** Creare `src/components/realtime/WatchPanel.tsx` (port select + WS client + events table)
- [ ] **W8.5** Creare `src/routes/RealtimeRoute.tsx` (Tabs Send/Watch)
- [ ] **W8.6** Registrare `<Route path="/realtime">` in `App.tsx` + nav link
- [ ] **W8.7** Creare `src/test/__tests__/SendPanel.test.tsx` (2 test)
- [ ] **W8.8** Creare `src/test/__tests__/WatchPanel.test.tsx` (2 test con MockWebSocket stub globale)
- [ ] **W8.9** Verificare `npm run typecheck && npm test && npm run build` verde
- [ ] **W8.10** Commit: `feat(web-frontend): W8 — RealtimePanel send + watch WebSocket`

---

## W9 — `qymanager serve` + static mount + docs finali

Dettaglio: [`PLAN/W9-serve-integration.md`](PLAN/W9-serve-integration.md)

- [ ] **W9.1** Creare `cli/commands/serve.py` con typer + uvicorn.run(create_app)
- [ ] **W9.2** Wire `serve` in `cli/app.py` (`app.command("serve")(serve)`)
- [ ] **W9.3** Verificare `web/backend/app.py::create_app` monta `StaticFiles(..., html=True)` quando `frontend_dir` esiste
- [ ] **W9.4** Creare `tests/web/test_serve_integration.py` (smoke: TestClient + static mount OK con dir temp)
- [ ] **W9.5** Build frontend: `cd web/frontend && npm run build && cd ../..`
- [ ] **W9.6** Smoke test: `uv run qymanager serve --port 8123 &` + `curl /` + `curl /api/schema` + kill
- [ ] **W9.7** Creare `wiki/web-gui.md` con architettura + quickstart + endpoint table
- [ ] **W9.8** Aggiornare `wiki/index.md` con link a `web-gui.md` in sezione Infrastructure
- [ ] **W9.9** Aggiungere sezione "Web GUI" in `README.md`
- [ ] **W9.10** Aggiornare `STATUS.md` con data + riga tabella "Web GUI v1.0 ✅ production"
- [ ] **W9.11** Aggiungere entry `wiki/log.md` datata "Session 32 — Web GUI v1.0 shipped"
- [ ] **W9.12** Verificare `uv run pytest` (428 + web) + `cd web/frontend && npm test && npm run build` tutto verde
- [ ] **W9.13** Verificare checklist `PLAN/verification.md` smoke test API (endpoint by endpoint)
- [ ] **W9.14** Commit finale: `docs(web): W9 — qymanager serve + web GUI v1.0 shipped`

---

## Verifica finale (post W9)

Seguire [`PLAN/verification.md`](PLAN/verification.md) end-to-end:

- [ ] **V.1** Build pulita da zero: `rm -rf web/frontend/node_modules web/frontend/dist && npm install && npm run build`
- [ ] **V.2** Full test: `uv run pytest -v` + `cd web/frontend && npm test` tutto verde
- [ ] **V.3** Lint/type: `ruff check` + `black --check` + `mypy` + `npm run lint` + `npm run typecheck` puliti
- [ ] **V.4** UI smoke manuale (checklist in verification.md)
- [ ] **V.5** Hardware smoke (se UR22C + QY70): emit + watch funzionano
- [ ] **V.6** Verifica: tutti i task sopra `[x]`/`[~]`

---

## Note

- **Non toccare `qymanager/` core** salvo bug bloccante. Il backend è thin wrapper.
- Se un task backend richiede firma `qymanager` leggermente diversa da quella prevista in `PLAN/W<N>-*.md`: leggi il modulo reale, adatta il codice del route, NON modificare `qymanager/`.
- Dipendenze nuove: solo in `pyproject.toml [project.optional-dependencies].web` e `web/frontend/package.json`.
- Se incontri un task da spezzare: aggiungi sotto-task qui con indentazione `  - [ ] W<N>.<i>.a ...`.
- Se scopri che un task è obsoleto: `[~]` + nota "skipped — <motivo>".
