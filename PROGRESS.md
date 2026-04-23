# PROGRESS.md — Web GUI v1.0 task checklist

> **Uso**: l'agente `qyconv-web` marca `[x]` ogni task completato. Legge questa lista in
> ordine e lavora UN task per iterazione. Stop quando tutti `[x]` / `[~]`.
>
> Legenda: `[ ]` todo · `[x]` done · `[~]` skipped (con nota) · `[!]` blocked (con nota)

---

## Setup pre-W1 (una volta)

- [x] **S0.1** Aggiungere `[project.optional-dependencies].web` in `pyproject.toml`
- [x] **S0.2** `export UV_LINK_MODE=copy && uv sync --all-extras --group dev`
- [x] **S0.3** Commit: `chore(deps): add web optional group`

---

## W1 — Backend devices routes

- [x] **W1.1** Creare directory `web/` + `web/backend/__init__.py`
- [x] **W1.2** Creare `web/backend/session.py` (DeviceSession in-memory cache)
- [x] **W1.3** Creare `web/backend/schemas.py` (pydantic I/O models)
- [x] **W1.4** Creare `web/backend/app.py` con `create_app(frontend_dir, dev)`
- [x] **W1.5** Creare `web/backend/routes/__init__.py`
- [x] **W1.6** `routes/devices.py` POST /devices (upload + load_device)
- [x] **W1.7** GET /devices/{id} (cache lookup + udm_to_dict)
- [x] **W1.8** PATCH /devices/{id}/field (set_field in-place)
- [x] **W1.9** POST /devices/{id}/validate (device.validate())
- [x] **W1.10** POST /devices/{id}/export (save_device + apply_policy + X-Warnings header)
- [x] **W1.11** DELETE /devices/{id}
- [x] **W1.12** `tests/web/conftest.py` (fixtures client + clean_session)
- [x] **W1.13-W1.15** `tests/web/test_devices.py` 11 test
- [x] **W1.16** `uv run pytest tests/web/ -v` → tutti verdi
- [x] **W1.17** Commit: `feat(web-backend): S0+W1+W2 — FastAPI backend`

---

## W2 — Backend diff + schema endpoints

- [x] **W2.1** Ispezionato `qymanager/editor/schema.py` → _FIXED_SPECS, _MULTI_PART_SPECS, _DRUM_NOTE_SPECS
- [x] **W2.2** `web/backend/routes/diff.py` con POST /diff
- [x] **W2.3** `web/backend/routes/schema.py` con GET /schema
- [x] **W2.4** Wire routers diff + schema in app.py
- [x] **W2.5** `tests/web/test_diff.py` (3 test)
- [x] **W2.6** `tests/web/test_schema.py` (2 test)
- [x] **W2.7** `uv run pytest tests/web/ -v` verde
- [x] **W2.8** Commit: included in W1+W2 combined commit

---

## W3 — Backend MIDI routes (REST + WebSocket)

> **MVP-1 NOTE**: Skipped — deferred to post-MVP. Realtime MIDI not needed for
> upload/edit/export workflow.

- [~] **W3.1-W3.10** Skipped — deferred to post-MVP (realtime MIDI)

---

## W4 — Frontend scaffold + Uploader + UDMTree

- [x] **W4.1** `npm create vite@latest . -- --template react-ts`
- [x] **W4.2** `npm install` + react-router-dom + @tanstack/react-query
- [x] **W4.3** Tailwind v4 + @tailwindcss/vite
- [x] **W4.4** `npx shadcn@latest init -d` (base-ui, Slate)
- [x] **W4.5** `npx shadcn@latest add` button/input/label/slider/select/checkbox/dialog/table/sonner/scroll-area/tooltip
- [x] **W4.6** `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`
- [x] **W4.7** Config vite.config.ts (alias @, proxy /api, tailwindcss plugin)
- [x] **W4.8** Config tsconfig (strict, paths, ignoreDeprecations)
- [x] **W4.9** vitest.config.ts + src/test/setup.ts
- [x] **W4.10** `src/lib/types.ts`, `api.ts`, `queries.ts`, `path.ts`
- [x] **W4.11** `src/App.tsx` (BrowserRouter + QueryClientProvider + Toaster)
- [x] **W4.12** `src/components/Uploader.tsx` (drag-and-drop)
- [x] **W4.13** `src/components/UDMTree.tsx` (recursive tree)
- [x] **W4.14** `src/routes/Dashboard.tsx`, `DeviceView.tsx`
- [x] **W4.15** Test: UDMTree.test.tsx, api.test.ts, path.test.ts (6 test)
- [x] **W4.16** `npm run build` verde
- [x] **W4.17** Commit: included in W4+W5+W6 combined commit

---

## W5 — FieldEditor schema-driven + PATCH

- [x] **W5.1** `src/components/FieldEditor.tsx` (matchSchema + range/enum/raw)
- [x] **W5.2** Integrated FieldEditor in DeviceView (selected state + getByPath)
- [x] **W5.3** Sonner toast for validation errors
- [x] **W5.4** Commit: included in W4+W5+W6 combined commit

---

## W6 — ExportDialog + WarningList + download

- [x] **W6.1** `src/lib/api.ts` exportDevice reads X-Warnings header
- [x] **W6.2** `src/components/WarningList.tsx`
- [x] **W6.3** `src/components/ExportDialog.tsx` (format + target + drop groups)
- [x] **W6.4** Integrated ExportDialog in DeviceView header
- [x] **W6.5** Commit: included in W4+W5+W6 combined commit

---

## W7 — DiffRoute + DiffView

> **MVP-1 NOTE**: Backend `/api/diff` endpoint is ready. Frontend UI deferred.

- [~] **W7.1-W7.8** Skipped — deferred to post-MVP (diff view UI)

---

## W8 — RealtimePanel (emit + watch WS)

> **MVP-1 NOTE**: Skipped — deferred to post-MVP (realtime MIDI).

- [~] **W8.1-W8.10** Skipped — deferred to post-MVP (realtime MIDI)

---

## W9 — `qymanager serve` + static mount + docs

- [x] **W9.1** `cli/commands/serve.py` (typer + uvicorn)
- [x] **W9.2** Wire `serve` in `cli/app.py`
- [x] **W9.3** `web/backend/app.py` monta StaticFiles(html=True) quando frontend_dir esiste
- [x] **W9.4** `tests/web/test_serve.py` (2 test: static mount + API routes)
- [x] **W9.5** Build frontend: `npm run build` → web/frontend/dist/
- [x] **W9.6** Smoke test: serve + curl / + curl /api/schema + upload
- [x] **W9.7** `wiki/web-gui.md` (architettura + quickstart + endpoint table)
- [x] **W9.8** `wiki/index.md` link to web-gui.md
- [x] **W9.9** Commit: `feat(web): W9 — qymanager serve integration`

---

## Verifica finale (post MVP-1)

- [x] **V.1** `uv run pytest` → 478 passed, 3 skipped
- [x] **V.2** `cd web/frontend && npm test` → 6 passed
- [x] **V.3** `cd web/frontend && npm run build` → verde
- [x] **V.4** Smoke: `uv run qymanager serve --port 8123` → / and /api/schema OK
- [ ] **V.5** Hardware smoke (non richiesto per MVP-1)
- [x] **V.6** Task sopra tutti [x] o [~]

---

## Post-MVP extras

- [x] **dev launcher** — `web/dev.sh` (start/stop/restart/status/logs, PID + log tracking under `web/.dev/`)
- [x] **serve --reload fix** — `cli/commands/serve.py` uses import-string factory when reload=True

---

## Post-MVP UX improvements

- [x] **UX.1** Serialization fix: `_convert_value()` handles list/dict recursion for full UDM JSON
- [x] **UX.2** Enum key fix: dict keys with Enum values serialize as `.value` (e.g. `Main_A` not `SectionName.MAIN_A`)
- [x] **UX.3** DeviceOverview component: stat cards, import context notes, editable scope summary
- [x] **UX.4** SelectionPanel component: focused node inspector with schema badge, preview grid, raw JSON
- [x] **UX.5** UDMTree rewrite: search/filter, expand/collapse, humanized labels, selected state highlighting
- [x] **UX.6** FieldEditor improvements: boolean support, humanized labels, raw value editor
- [x] **UX.7** DeviceView rewrite: sidebar navigator + overview/selection layout, meta pills
- [x] **UX.8** UDM utility library (`lib/udm.ts`): humanizeKey, getNodeSummary, formatPathLabel, etc.
- [x] **UX.9** SPA route fallback in backend (non-API routes serve index.html)
- [x] **UX.10** PatternOverview component: mixer-style track strips per section, rhythm/melodic separation
- [x] **UX.11** Dashboard redesign: clean landing with format badges
- [x] **UX.12** Track extraction helpers + tests (14 frontend tests total, 479 backend tests)
- [x] **UX.13** Multi Part overview panel (when multi_part has data)
- [x] **UX.14** Effects overview panel (reverb/chorus/variation type + level)
- [ ] **UX.15** Drum Setup overview panel (when drum_setup has data)

---

## Note

- **Core modification**: `qymanager/model/serialization.py` — fixed `_convert_value()` to handle list/dict recursion and enum dict keys. Required for full UDM JSON serialization.
- **Adattamento API**: `set_field` muta Device in-place e ritorna il valore, non il Device. `convert_file` prende file path, non Device — export usa `apply_policy` + `save_device` direttamente.
- **shadcn v4** usa `@base-ui/react` (non Radix) — API diversa (no asChild, `onValueCommitted`, etc.)
- **Tailwind v4** usa CSS-based config con `@tailwindcss/vite` plugin.
- **TypeScript 6** richiede `ignoreDeprecations: "6.0"` per `baseUrl`/`paths`.
