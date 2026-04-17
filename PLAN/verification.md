# Verification — end-to-end

> **Obiettivo**: checklist di verifica integrale della web GUI v1.0. Da eseguire dopo W9.

## Build + install

```bash
cd /Volumes/Data/DK/XG/T700/qyconv
export UV_LINK_MODE=copy

uv sync --all-extras --group dev
cd web/frontend && npm install && npm run build && cd ../..

# Expected:
# - web/frontend/dist/ presente
# - dist/index.html + dist/assets/*.js + *.css
```

## Unit + integration tests

```bash
# Backend full regression (428 core + web nuovi)
uv run pytest -v

# Solo web
uv run pytest tests/web/ -v

# Frontend
cd web/frontend && npm test && cd ../..
```

**Criteri**:
- [ ] 428 test core verdi (baseline, no regressioni)
- [ ] >= 15 test `tests/web/` verdi
- [ ] >= 10 test Vitest verdi

## Lint + typecheck

```bash
uv run ruff check web/backend qymanager cli tests/web
uv run black --check web/backend tests/web
uv run mypy web/backend

cd web/frontend
npm run lint
npm run typecheck
cd ../..
```

**Criteri**:
- [ ] ruff clean
- [ ] black no-diff
- [ ] mypy no errors
- [ ] eslint clean
- [ ] tsc clean

## Smoke test — endpoint API

```bash
uv run qymanager serve --port 8123 &
SERVER_PID=$!
sleep 2

# 1. Static
curl -fsS http://127.0.0.1:8123/ > /dev/null && echo "✅ static serve"

# 2. API schema
SCHEMA_COUNT=$(curl -fsS http://127.0.0.1:8123/api/schema \
    | python -c "import json,sys; print(len(json.load(sys.stdin)['paths']))")
echo "schema paths: $SCHEMA_COUNT"  # atteso > 50

# 3. API midi/ports
curl -fsS http://127.0.0.1:8123/api/midi/ports

# 4. Upload fixture
DID=$(curl -fsS -X POST -F "file=@tests/fixtures/QY70_SGT.syx" \
    http://127.0.0.1:8123/api/devices | python -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "uploaded device: $DID"

# 5. Get
curl -fsS http://127.0.0.1:8123/api/devices/$DID | python -c "
import json,sys
d = json.load(sys.stdin)['device']
print('model:', d['model'])
print('parts:', len(d['multi_part']))
"

# 6. PATCH field
curl -fsS -X PATCH -H 'content-type: application/json' \
    -d '{"path":"system.master_volume","value":100}' \
    http://127.0.0.1:8123/api/devices/$DID/field > /dev/null && echo "✅ patch"

# 7. Validate
curl -fsS -X POST http://127.0.0.1:8123/api/devices/$DID/validate

# 8. Export syx
curl -fsS -X POST -H 'content-type: application/json' \
    -d '{"format":"syx"}' \
    http://127.0.0.1:8123/api/devices/$DID/export \
    -o /tmp/roundtrip.syx
ls -la /tmp/roundtrip.syx

# 9. Delete
curl -fsS -X DELETE http://127.0.0.1:8123/api/devices/$DID && echo "✅ delete"

kill $SERVER_PID
```

## Smoke test — UI manuale

Con backend running su :8000 e frontend built:

```bash
uv run qymanager serve --port 8000
# Apri http://127.0.0.1:8000 in Chrome/Firefox
```

**Checklist UI** (spunta manualmente):
- [ ] Landing page con Uploader visibile
- [ ] Drag-and-drop di `tests/fixtures/QY70_SGT.syx` → redirect a `/device/<id>`
- [ ] UDMTree a sinistra con System / MultiPart / DrumSetup / Effects / ...
- [ ] Click `system.master_volume` → FieldEditor mostra Slider + Input
- [ ] Muovi slider → verifica che chiamata PATCH va a buon fine (Network tab)
- [ ] Refresh pagina → valore modificato persiste
- [ ] Bottone "Export..." → dialog si apre con formato + target + drop groups
- [ ] Export syx → file scaricato
- [ ] Nav "/diff" → 2 slot upload, compare button disabled
- [ ] Upload 2 file (stesso SGT 2 volte, uno con PATCH diverso) → Compare → tabella differenze
- [ ] Nav "/realtime" → tab Send + Watch
- [ ] Send tab → Select mostra porte (anche vuoto se no hardware — no crash)
- [ ] Watch tab → Start/Stop button (con fake port non connette ma non crasha)

## Smoke test — hardware (opzionale)

Se UR22C + QY70 collegati:

```bash
export QY_HARDWARE=1

# Server running. Nel browser:
# 1. /realtime → Send → port "UR22C Port 1" → edit system.master_volume=80 → Emit
#    → Verifica audio/display QY70 reagisce
# 2. /realtime → Watch → port "UR22C Port 1" → Start
#    → Muovi un fader/knob sul QY70 → Verifica eventi appaiono nella tabella
```

## Criteri di accettazione v1.0

- [ ] Tutti i test verdi (backend + frontend)
- [ ] `uv run qymanager serve` avvia senza errori
- [ ] UI manuale: tutti i punti della checklist OK
- [ ] Hardware smoke (se disponibile): emit + watch funzionano
- [ ] Docs `wiki/web-gui.md`, `README.md`, `STATUS.md` aggiornate
- [ ] Commit `docs(web): W9 — qymanager serve + web GUI v1.0 shipped` presente
- [ ] Nessun file temporaneo, nessun `.DS_Store`, nessun `node_modules/` committato
- [ ] `PROGRESS.md` tutti i task `[x]` o `[~]`

## Out of scope (NON da verificare in v1.0)

- ~~Piano roll editor~~
- ~~Chord timeline drag-drop~~
- ~~Phrase library audio preview~~
- ~~Voice browser con preview~~
- ~~Electron packaging~~
- ~~E2E Playwright~~
- ~~Multi-user auth~~
