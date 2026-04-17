# PROMPT.md — Ralph loop instruction per qyconv-web

> **Come usare**: questo file contiene il prompt da passare al comando `ralph` per
> invocare iterativamente l'agente `qyconv-web` (definito in `.opencode/agents/qyconv-web.md`)
> fino al completamento integrale della web GUI v1.0.
>
> **Modello**: `zai-coding-plan/glm-5.1` (GLM 5.1).
>
> **Comando**:
> ```bash
> ralph --agent qyconv-web --prompt "$(cat PROMPT.md)"
> ```
>
> Ogni iterazione esegue UN task granulare (tipicamente 1 task di `PROGRESS.md`, con
> test + commit atomico). Il loop continua finché tutti i task sono `[x]` / `[~]`.

---

## Prompt

Sei l'**executor del web GUI editor** del progetto QYConv. Costruisci la web GUI v1.0 sopra
il core Python già pronto (UDM + parser + editor + converter + realtime, 428 test verdi).

Il tuo compito è **avanzare `PROGRESS.md` di un task alla volta**, commit atomico, test
verdi, fino a completamento. Il loop ralph ti richiama automaticamente.

### Contesto

Il core Python è completo:
- `qymanager.formats.io.load_device` / `save_device`
- `qymanager.editor.ops.set_field` / `apply_edits` / `make_xg_messages`
- `qymanager.editor.schema.validate` / `encode_xg` + `_FIXED_SPECS` / `_MULTI_PART_SPECS` / `_DRUM_NOTE_SPECS`
- `qymanager.editor.realtime.RealtimeSession`
- `qymanager.converters.udm_convert.convert_file`
- `qymanager.converters.lossy_policy.apply_policy`
- `qymanager.model.serialization.udm_to_dict` / `device_to_json`
- `Device.validate()`

La GUI web è un **thin HTTP wrapper** (FastAPI) + **SPA React** (Vite + TS + shadcn +
TanStack Query) + comando `qymanager serve` integrato.

Il piano è in `PLAN/` (overview + 9 fasi W1-W9 + verification). I task granulari sono in
`PROGRESS.md`.

### Istruzioni per ogni iterazione

**Step 1 — Orientati** (SEMPRE prima cosa):

```bash
cd /Volumes/Data/DK/XG/T700/qyconv
export UV_LINK_MODE=copy

cat PROGRESS.md
ls PLAN/
cat PLAN/00-overview.md | head -100
git log --oneline -15
git status
```

**Step 2 — Identifica il prossimo task**:

- Primo `[ ]` sequenziale in `PROGRESS.md`
- Identifica la fase corrente (W1..W9)
- Leggi il file `PLAN/W<N>-*.md` della fase corrente per dettagli implementativi

**Step 3 — Implementa UN task** (non più):

- Scrivi codice seguendo il template nel `PLAN/W<N>-*.md`
- Aggiungi test (backend: pytest + TestClient; frontend: Vitest + RTL)
- Verifica:
  ```bash
  uv run pytest tests/web/ -v              # backend test nuovi
  uv run pytest                            # full regression (428 baseline + nuovi)
  uv run ruff check web/backend tests/web
  uv run black --check web/backend tests/web
  # (dopo W4 in poi)
  cd web/frontend && npm test && npm run typecheck && cd ../..
  ```

**Step 4 — Aggiorna progresso**:

- Marca il task `[x]` in `PROGRESS.md`
- Se scopri un sotto-task nuovo: aggiungilo con `[ ]` + note
- Se un task diventa obsoleto: marcalo `[~]` con nota "skipped — <ragione>"

**Step 5 — Commit atomico**:

```bash
git add <file_elencati>
git commit -m "$(cat <<'EOF'
<scope>: <task title>

<body con why se non ovvio>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Scope convention:
- `feat(web-backend): ...` — nuovo endpoint/modulo backend
- `feat(web-frontend): ...` — nuovo componente/route frontend
- `feat(cli): ...` — `qymanager serve` o estensioni CLI
- `test(web): ...` — solo test (se separati)
- `docs(web): ...` — documentazione finale W9
- `chore(deps): ...` — aggiunta dipendenze

### Regole critiche (vedi anche `.opencode/agents/qyconv-web.md`)

1. **NON modificare `qymanager/` core** salvo bug bloccante documentato. Il backend è
   un thin wrapper.
2. **428 test baseline devono sempre essere verdi**. Niente `--no-verify`.
3. **UN task per iterazione**. Se un task è grande (>200 LOC cambiate), spezzalo e
   aggiorna `PROGRESS.md` con i sotto-task.
4. **No scope creep**: solo task in `PROGRESS.md`. Piano roll, chord timeline, voice
   browser, Electron = **v1.1+**, fuori scope.
5. **Italiano per report/output, inglese per codice/commit subject**.
6. **UV_LINK_MODE=copy** sempre.

### Quando fermarti

Il loop termina quando:
- Tutti i task di `PROGRESS.md` sono `[x]` o `[~]`
- `uv run pytest` tutto verde (428 + nuovi)
- `cd web/frontend && npm test && npm run build` verdi
- `uv run qymanager serve` avvia e serve `/` con HTML
- `curl http://127.0.0.1:8000/api/schema` ritorna JSON
- Commit finale `docs(web): W9 — qymanager serve + web GUI v1.0 shipped` presente

In quel momento stampa il report finale e termina senza aprire nuovi task.

### Report finale di ogni iterazione

```
## Iterazione completata

**Fase**: W<N> — <nome>
**Task**: <titolo>

**Fatto**:
- <file creati/modificati>
- <test aggiunti>
- Test totali: <N>/<N> verdi
- Commit: <scope>: <title>

**Next**:
- <prossimo task da PROGRESS.md>

**Blocchi**:
- <se presenti, altrimenti "nessuno">
```

### Quickstart

```bash
cd /Volumes/Data/DK/XG/T700/qyconv
export UV_LINK_MODE=copy

# 1. Orient
cat PROGRESS.md
ls PLAN/
git log --oneline -10

# 2. Pick next task (primo `[ ]`)
# 3. Leggi PLAN/W<N>-*.md corrispondente
# 4. Implement + test + commit + mark [x]
```

Sii preciso, thin wrapper sopra core esistente, non toccare `qymanager/`.
Buon lavoro.
