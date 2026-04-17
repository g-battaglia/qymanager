# Pattern Editor (Pipeline B)

CLI editor che opera sopra [Pipeline B](conversion-roadmap.md#pipeline-b-capture-based-new-session-19--recommended--validated) per modificare pattern catturati dal QY70 e rigenerare Q7P + SMF.

**Status**: Prototipo funzionante (Session 29f, 2026-04-17) — 15 test verdi.

## Workflow

```
QY70 hardware → capture_playback.py → capture.json
                                         ↓
                                   pattern_editor export
                                         ↓
                                    pattern.json ← edit (CLI operations)
                                         ↓
                                   pattern_editor build
                                         ↓
                                    output.Q7P + output.mid
```

## Comandi CLI

Entry point: `python3 -m midi_tools.pattern_editor <command>`

| Comando | Descrizione | Esempio |
|---------|-------------|---------|
| `export` | Capture JSON → editable JSON | `export capture.json -o pattern.json` |
| `summary` | Sommario pattern | `summary pattern.json` |
| `list-notes` | Lista note (filtri: `--track`, `--bar`) | `list-notes pattern.json --track 3` |
| `add-note` | Aggiunge una nota | `add-note pattern.json --track 5 --bar 0 --beat 0 --note 60 --velocity 100` |
| `remove-note` | Rimuove note (filtri: `--bar`, `--beat`, `--note`) | `remove-note pattern.json --track 0 --bar 2 --note 36` |
| `transpose` | Sposta note di N semitoni (solo melody, drum rifiutato) | `transpose pattern.json --track 3 --semitones 2` |
| `shift-time` | Sposta note di N ticks (overflow droppato) | `shift-time pattern.json --track 3 --ticks 120` |
| `copy-bar` | Copia contenuto bar (`--append` per merge) | `copy-bar pattern.json --track 0 --src 0 --dst 2` |
| `clear-bar` | Rimuove tutte le note di un bar | `clear-bar pattern.json --track 0 --bar 3` |
| `kit-remap` | Rimappa nota drum-kit (es. 36→38) | `kit-remap pattern.json --track 0 --src 36 --dst 38` |
| `humanize` | Random ±N velocity (seed opzionale) | `humanize pattern.json --track 0 --amount 8 --seed 42` |
| `set-velocity` | Modifica velocity (filtri: `--bar`, `--note`) | `set-velocity pattern.json --track 0 --velocity 90 --bar 0` |
| `set-tempo` | Cambia BPM | `set-tempo pattern.json 120` |
| `set-name` | Cambia nome pattern | `set-name pattern.json MYEDIT01` |
| `build` | Rigenera .Q7P + .mid | `build pattern.json -o out --scaffold data/q7p/DECAY.Q7P` |

## Invariant & Safety

- **Drum transpose bloccato**: trasposizione rifiutata per tracce drum (remapping kit pieces rischioso)
- **Range check**: note `0-127`, velocity `1-127`, bar/beat dentro limiti pattern
- **Validator**: `build` chiama `validate_q7p` prima di scrivere; 0 warnings richiesto (override con `--force`)
- **Sort-on-edit**: dopo ogni add, le note sono riordinate per `(bar, tick_on, note)` → phrase encoding deterministico

## JSON Format (editable)

Stesso formato emesso da `quantizer.export_json()`:

```json
{
  "bpm": 151.0,
  "ppqn": 480,
  "time_sig": [4, 4],
  "bar_count": 4,
  "name": "QY70_SGT.syx",
  "tracks": {
    "0": {
      "name": "RHY1",
      "channel": 9,
      "is_drum": true,
      "note_count": 125,
      "notes": [
        {"note": 36, "vel": 100, "bar": 0, "beat": 0, "sub": 0, "tick_on": 0, "tick_dur": 60}
      ]
    }
  }
}
```

Editabile a mano in qualsiasi editor di testo; il file può essere ricaricato via `load_pattern()` o `load_quantized_json()`.

## Scaffolds supportati

| Scaffold | Size | Max bar | Uso |
|----------|------|---------|-----|
| `data/q7p/DECAY.Q7P` | 5120 B | 4 | Default, testato su SGT/Summer/DECAY |
| `data/q7p/SGT..Q7P` | 6144 B | 6+ | Per pattern lunghi (6-bar SGT) |

Selezione con `--scaffold`.

## Implementazione

File principali:

| File | Ruolo |
|------|-------|
| `midi_tools/pattern_editor.py` | CLI + operazioni pure (`op_add_note`, `op_transpose`, …) |
| `midi_tools/quantizer.py` | `dict_to_pattern` / `pattern_to_dict` / `load_quantized_json` |
| `midi_tools/build_q7p_5120.py` | Costruzione Q7P da pattern |
| `midi_tools/capture_to_q7p.py` | SMF writer + D0/E0 encoder |
| `tests/test_pattern_editor.py` | 15 test: roundtrip, ciascuna op, CLI end-to-end, Q7P build |

## Limitazioni prototipo

- **No undo/redo**: le operazioni modificano il file in place (tenere backup)
- **No GUI**: solo CLI (si può pilotare da script/Makefile)
- **Drum track uneditabile via transpose**: usare `kit-remap` per rimappare singole note
- **Hardware loopback non testato**: output Q7P non caricato su QY700 reale ancora (Session 29f)
- **No humanize timing**: solo velocity per ora (timing humanize richiede rebuild tick_on)

## Prossimi step (priorità)

1. **Hardware test**: caricare `sgt_edited.Q7P` su QY700 con `safe_q7p_tester.py`, verificare playback
2. **Multi-track ops**: `shift-time --all-tracks`, `humanize --all`
3. **Pattern merge**: combinare due capture in uno
4. **Humanize timing**: randomize tick_on entro ±N ticks
5. **Velocity curves**: crescendo/decrescendo invece di random
6. **GUI**: prototipo TUI (textual) o web (Flask+D3) dopo consolidamento CLI
