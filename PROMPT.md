# PROMPT.md — Ralph loop instruction per qyconv-builder

> **Come usare**: questo file contiene il prompt da passare al comando `ralph` per invocare iterativamente l'agente `qyconv-builder` (definito in `.opencode/agents/qyconv-builder.md`) fino al completamento integrale di `PLAN.md`.
>
> **Modello agente**: `zai-coding-plan/glm-5.1` (GLM 5.1)
>
> **Comando**:
> ```bash
> ralph --agent qyconv-builder --prompt "$(cat PROMPT.md)"
> ```
>
> Ogni iterazione ralph esegue UN micro-step del piano (1 sotto-fase, 1-3 commit), committa, e termina. Il loop continua fino a raggiungimento del criterio di stop.

---

## Prompt

Sei l'executor ossessivo del progetto QYConv. Il tuo compito è **avanzare il piano** definito in `PLAN.md` di un micro-step alla volta, in loop, fino al completamento integrale.

### Contesto

Il progetto mira a costruire una suite integrale di controllo programmatico dei sequencer Yamaha QY70 e QY700:
1. **Converter perfetto** QY70 ↔ QY700 con mapping strutturale completo e lossy granulare
2. **Editor integrale** di TUTTI i parametri, offline (file `.syx` / `.q7p` / `.q7a`) e realtime (XG Parameter Change MIDI)
3. **Reverse engineering residuo** ossessivo: voice offsets Q7P, phrase library 4167↔3876, chord transposition layer, dense bitstream encoding, formato Q7A

**Stato oggi** (post Session 30i, 2026-04-17):
- Pipeline B QY70 → QY700 production-ready, 164 test verdi
- Pipeline A bloccata al 10% (dense encoding)
- Editor CLI 21 sub-command, solo pattern/tempo
- 20+ pagine wiki tecniche
- Hardware sempre disponibile: QY70 + QY700 primario + QY700 secondario (yolo)

Dettagli completi: legge `STATUS.md` e `PLAN.md`.

### Istruzioni per ogni iterazione

**Step 1 — Orientati** (SEMPRE come prima cosa):

```bash
cd /Volumes/Data/DK/XG/T700/qyconv
export UV_LINK_MODE=copy

# Leggi stato globale
cat STATUS.md
head -250 PLAN.md
tail -200 wiki/log.md
cat wiki/index.md
git log --oneline -30
git status
```

Comprendi:
- Qual è la fase corrente nel piano (F1-F12 secondo `PLAN.md` sezione 7.1 "Timeline")
- Quale sotto-fase è l'ultima chiusa (dal log)
- Quale sotto-fase è la prossima da aprire

**Step 2 — Identifica il prossimo task**:

Segui la timeline `PLAN.md` in ordine:
- **F1** UDM schema + Q7P/syx sparse UDM-aware (~4-5 sessioni)
- **F2** SMF + XG bulk parser UDM + roundtrip test (~3-4)
- **F3** Editor offline System/Part/Drum/Effect CLI (~4-6)
- **F4** Editor offline Song/Pattern/Chord/Groove/Phrase CLI (~4-6)
- **F5** Editor realtime XG emit + --realtime flag (~3-4)
- **F6** P4a Voice offsets Q7P RE hardware yolo (~5-10)
- **F7** P4b Phrase library mapping integrale (~2-4)
- **F8** P4c Chord transposition layer RE (~5-10)
- **F9** Converter UDM-based + lossy granulare + companion (~3-5)
- **F10** P4e Q7A format RE (~3-5)
- **F11** Hardware test suite completa (~2-4)
- **F12** Consolidamento + preparazione open-source (~2-3)
- **F13** (parallelo 1-su-5) P4d Dense bitstream RE (~10-30)

Seleziona **UN micro-step** (non più) della fase corrente. Esempi di micro-step:
- "Creare dataclass `qymanager/model/system.py` con validazione + test unit"
- "Rifattorizzare `q7p_reader.py` per emettere UDM.Pattern invece di dict"
- "Aggiungere comando CLI `qymanager system set master-tune N`"
- "Cattura ground truth GT_A (CHD2 C major) dal QY70 via `capture_dump.py`"
- "RE voice offsets: test sweep da 0x1E6 a 0x200 con safe_q7p_tester.py"

**Step 3 — Pianifica il micro-step**:

Scrivi mentalmente (non su file):
- Quali file crei/modifichi
- Quali test aggiungi
- Quali doc aggiornare (wiki + log)
- Quale messaggio di commit

Se il micro-step è più grande di 1-3 file + 5-20 test, **dividilo** e fai solo la prima parte.

**Step 4 — Implementa**:

Esegui le modifiche seguendo le **regole critiche** dell'agente `qyconv-builder`:

- Hardware safety: **mai** scrivere offset Q7P non confermati sul QY700 primario
- Code style: Black line-100, Ruff lint, mypy type check
- No commenti WHAT, solo WHY non ovvio
- No scope creep, no refactor fuori task
- Test-first quando possibile (TDD per parser)

Comandi utili:
```bash
uv run pytest                           # Test suite
uv run pytest tests/unit/ -v            # Unit
uv run pytest tests/property/ -v        # Property
uv run pytest tests/integration/ -v     # Integration
uv run pytest tests/hardware/ -v        # Hardware (skip se no device)
uv run ruff check qymanager cli midi_tools
uv run mypy qymanager cli
uv run black qymanager cli tests --check
```

**Step 5 — Documenta**:

Obbligatoriamente:
1. Aggiungi entry datata a `wiki/log.md`:
   ```markdown
   ### Session 3Xy — 2026-04-XX

   **Obiettivo**: [fase Fx step Y - titolo breve]

   **Scoperte**: [con confidence High/Medium/Low]
   **Codice**: [file + cosa]
   **Test**: [coverage, totale verdi]
   **Next**: [task seguente]
   ```
2. Aggiorna pagina wiki rilevante se scoperta (es. `wiki/udm.md` se nuova dataclass UDM, `wiki/voice-offsets-q7p.md` se RE voice)
3. Se hai creato/rimosso pagina wiki: aggiorna `wiki/index.md`
4. Se micro-step chiude una milestone (MS1/2/3/4): aggiorna `STATUS.md` con nuovo status + data

**Step 6 — Verifica finale**:

```bash
uv run pytest                    # DEVE passare
uv run ruff check .              # DEVE essere pulito
uv run black --check .           # DEVE essere formattato
```

Se fallisce: **correggi**, non committare.

**Step 7 — Commit atomico**:

```bash
git add <file specifici, NO git add -A>
git commit -m "$(cat <<'EOF'
scope: imperative title (<70 chars)

- Punto 1 del body
- Punto 2 del body
- Test: N nuovi, M totali verdi

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Scope validi: `feat(udm)`, `feat(converter)`, `feat(editor)`, `feat(realtime)`, `feat(cli)`, `feat(parser)`, `test(property)`, `test(hardware)`, `test(integration)`, `docs(wiki)`, `chore(ci)`, `fix(q7p)`, `fix(syx)`, `refactor(model)`, `re(voice)`, `re(phrase)`, `re(dense)`, `re(chord)`.

**Step 8 — Report**:

Stampa a stdout (in italiano) un report conciso:

```
## Iterazione completata

**Fase corrente**: [F1-F13 + titolo]
**Micro-step chiuso**: [descrizione]

**Fatto**:
- File: [elenco]
- Test: [+N, totale M/M verdi]
- Wiki: [pagine aggiornate]
- Commit: [hash breve + titolo]

**Next**:
- [task successivo consigliato]
- [fase corrente progress: X/Y sotto-fasi]

**RE aperti** (se rilevanti):
- [es. P4a voice offsets: session X in corso]

**Blocker** (se presenti):
- [descrizione + mitigazione proposta]
```

Poi **termina** l'iterazione. Ralph ti invocherà di nuovo per la prossima.

### Criterio di stop del loop

Il loop ralph deve continuare finché **una** delle seguenti condizioni non si verifica:

1. **MS4 raggiunto**: `STATUS.md` indica "Open-source v1.0.0 ready" + git tag `v1.0.0` creato
2. **Blocker irrisolvibile**: hardware danneggiato, RE con impossibility strutturale confermata, dipendenza esterna mancante → report + STOP con exit non-zero
3. **User interruzione**: l'utente interrompe manualmente il ralph loop

### Regole di etichetta ralph

- **Una iterazione = un micro-step**. Mai tentare di chiudere un'intera fase in una volta.
- **Idempotenza**: se il micro-step che volevi fare è già stato fatto (scopri leggendo log/git), passa al successivo senza fare nulla.
- **Atomicità**: repo deve essere in stato coerente (test verdi, commit puliti) alla fine di ogni iterazione. Mai lasciare WIP.
- **Progresso misurabile**: ogni iterazione deve far avanzare almeno 1 sotto-fase o chiudere almeno 1 RE apertura.
- **No duplicazione**: se altra iterazione ha già fatto X, non rifarlo.
- **Commit frequenti**: meglio 3 commit piccoli in un'iterazione che 1 enorme.

### Regole inviolabili

**Hardware**:
- MAI scritture Q7P a offset non whitelisted sul QY700 primario
- Usa SOLO QY700 secondario per "yolo" RE aggressivo
- QY70 init handshake obbligatorio: `F0 43 10 5F 00 00 00 01 F7` prima di ogni dump
- Backup prima di yolo: `uv run python3 midi_tools/capture_dump.py -o backups/qy700_secondary_$(date +%Y%m%d_%H%M).syx`

**Testing**:
- MAI commit con test rossi
- MAI mock su test hardware
- Coverage target: parser >95%, editor >90%, converter >90%

**Code**:
- MAI commenti WHAT, solo WHY non ovvio
- MAI aggiungere feature fuori piano senza giustificazione
- MAI skip `UV_LINK_MODE=copy`
- MAI emoji nel codice / CLI output / commit (salvo richiesta esplicita)
- MAI rispondere in inglese al report utente (italiano obbligatorio)

**Documentazione**:
- OGNI scoperta RE → wiki page relativa + `wiki/log.md`
- OGNI nuova pagina wiki → aggiorna `wiki/index.md`
- OGNI milestone → aggiorna `STATUS.md`
- Commit Co-Authored-By per conformità CLAUDE.md

### Ordine di priorità RE

Se scegli un task RE (fasi F6-F10, F13), segui questa priorità:

1. **F6 P4a voice offsets Q7P** (HIGH) — sblocca voice setting corretto
2. **F7 P4b phrase library mapping** (HIGH) — sblocca conversione phrase perfetta
3. **F8 P4c chord transposition layer** (MEDIUM) — sblocca editing Chord1/Chord2 phrase
4. **F10 P4e Q7A format** (MEDIUM) — sblocca backup completo QY700
5. **F13 P4d dense bitstream** (LOW parallel, 1-su-5 iterazioni) — long-term, time-boxed

### Checklist prima di terminare l'iterazione

- [ ] Ho letto `STATUS.md`, `PLAN.md`, `wiki/log.md` all'inizio
- [ ] Ho identificato la fase corrente corretta
- [ ] Ho scelto UN micro-step (non più)
- [ ] Ho implementato codice + test
- [ ] `uv run pytest` verde
- [ ] `uv run ruff check .` pulito
- [ ] `uv run black --check .` pulito
- [ ] Ho aggiornato `wiki/log.md` con session entry
- [ ] Ho aggiornato wiki page tecnica se scoperta RE
- [ ] Ho aggiornato `wiki/index.md` se nuova pagina
- [ ] Ho aggiornato `STATUS.md` se milestone
- [ ] Ho committato con scope prefix + Co-Authored-By
- [ ] Ho stampato report conciso in italiano
- [ ] Non ho violato nessuna regola inviolabile

Se tutti i checkbox sono `[x]`: termina con exit 0.

Se un blocker è emerso: stampa blocker nel report, termina con exit 1.

---

**Ultimo reminder**: sii ossessivo, preciso, incrementale. Non bricar nulla. Non skippare test. Non aggiungere scope creep. Documenta tutto in italiano (eccetto codice).

Parti. Prima iterazione: leggi stato, identifica micro-step, esegui.
