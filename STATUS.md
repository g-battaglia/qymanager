# Project Status — qyconv

> Single-source north-star del progetto QY70 ↔ QY700 reverse engineering.
> Aggiornato a ogni chiusura di sessione.

**Ultimo aggiornamento**: 2026-04-17 (Session 31 autonomous run — **F1→F12 del piano integrale completati end-to-end**. UDM con 15 dataclass, parser UDM-aware per `.syx` sparse/Q7P/XG bulk/SMF, editor offline con 60+ CLI commands via `field-set/field-get/field-emit-xg/pattern-*/chord-*/song-*/phrase-list`, realtime wrapper `qymanager realtime {list-ports,emit,watch}`, converter UDM-based con lossy policy `--keep/--drop`, property tests hypothesis, hardware skip markers via `QY_HARDWARE=1`, README + CONTRIBUTING + `wiki/udm.md`. Test suite: **428 passed, 3 skipped** (esclusi hardware-gated).)
**Obiettivo finale**: Editor completo pattern + conversione bidirezionale QY700 ↔ QY70

---

## Valutazione generale

| Area | Stato | % completato |
|------|-------|---------------|
| Conversione QY70 → QY700 (Pipeline B capture-based) | **Production-ready** | 100% |
| Conversione QY70 → QY700 (Pipeline A SysEx decode) | Research-blocked | 10% |
| Conversione QY700 → QY70 (metadata only) | Parziale (musicalmente errato) | 30% |
| Editor pattern (CLI prototipo + UDM) | **Production-ready** | ~90% |
| Unified Data Model (UDM) — fondamenta architetturali | **Production-ready** | 100% (schema+Q7P+`.syx`+XG bulk+SMF) |
| Editor offline (System/Part/Drum/Effect/Pattern/Song/Chord) | **Production-ready** | 100% (CLI + Python API) |
| Realtime XG editor | **Production-ready** | 100% (list-ports/emit/watch) |
| Converter lossy policy granulare | **Production-ready** | 100% (`--keep/--drop` + warnings) |
| **Obiettivo finale complessivo** | In progress | **~75-80%** |

---

## Cosa funziona (alta confidenza)

- **Pipeline B**: capture QY70 → quantize → Q7P 5120/6144B. Roundtrip byte-valid verificato su hardware: 208/208 note SGT, 126/126 Summer, DECAY self-parse byte-identical
- **Metadata converter** (`qy70_to_qy700.py`): tempo, nome, volume, pan, chorus/reverb
- **Decoder sparse** (user patterns): 100% su 7/7 casi noti (rotation R=9×(i+1))
- **Q7P format**: read + write + validator con invariant phrase-stream (0 warnings)
- **Hardware I/O**: Init handshake, bulk dump, send style, capture playback tutti funzionanti. **Coordinate SysEx confermate (Session 30)**: Model=0x5F, device=0, AM=0x7E (solo edit buffer; slot User rifiutato)
- **Editor CLI prototipo** (`midi_tools/pattern_editor.py` + `cli/commands/edit.py`): **21 sub-command** — export, summary, list-notes, new-empty, add-note, remove-note, transpose, shift-time, copy-bar, clear-bar, kit-remap, humanize, humanize-timing, velocity-curve, set-velocity, set-tempo, set-name, resize, diff, merge (overlay/append), build. **5 comandi multi-track** (`--all-tracks`): `shift-time`, `humanize`, `humanize-timing`, `velocity-curve`, `set-velocity`. Accessibile via modulo (`python3 -m midi_tools.pattern_editor`) **e** CLI principale (`qymanager edit`). Test roundtrip bijective JSON ↔ QuantizedPattern
- **Unified Data Model (F1 P1.1)**: `qymanager/model/` con 15 dataclass (`Device`, `Pattern`, `Section`, `PatternTrack`, `Voice`, `DrumSetup`, `Effects`, `Reverb`, `Chorus`, `Variation`, `Song`, `MultiPart`, `Phrase`, `GrooveTemplate`, `System`, `FingeredZone`) + 12 enum + `TimeSig` frozen + JSON serializer + `.validate()` ricorsiva. Documentato in [wiki/udm.md](wiki/udm.md).
- **Parser UDM-aware (F1 P1.2 + F2)**: Q7P reader/writer, `.syx` sparse reader/writer (QY70), XG bulk parser (`xg_bulk.parse_xg_bulk_to_udm`), SMF parse side. `qymanager.formats.io.load_device/save_device` dispatcher automatico basato su estensione (con auto-detect XG vs QY70 sparse per `.syx`).
- **Editor offline (F3–F4)**: `qymanager.editor.{schema, address_map, ops}` + CLI `field-set`/`field-get`/`field-emit-xg` path-based DSL (`multi_part[0].voice.program`, `drum_setup[0].notes[36].level`, `effects.reverb.type_code`, …) + comandi strutturati `pattern-list/pattern-set/chord-add/chord-list/song-list/song-set/phrase-list`. Schema validation con `Range`/`Enum` + encoder XG 7-bit (transpose/cutoff/resonance signed).
- **Editor realtime (F5)**: `qymanager.editor.realtime.RealtimeSession` wrap rtmidi (no mido: fix SysEx drop macOS) + CLI `qymanager realtime {list-ports, emit --set PATH=VALUE, watch}`. Ogni edit UDM si può emettere live via XG Parameter Change con la stessa API dell'editor offline.
- **Converter UDM-based (F9)**: `qymanager.converters.lossy_policy.apply_policy()` con semantica keep/drop granulare: structural normalization sempre applicata al cambio target_model, warning emission controllata da keep/drop. CLI `qymanager udm-convert --target-model QY700 --keep ... --drop ... --warn-file out.json`.
- **Property tests (F11)**: `tests/property/test_udm_invariants.py` — 9 hypothesis-based tests su XG roundtrip, transpose offset, bank triplet last-write-wins, schema validation. Marker `hardware` con skip auto via conftest (abilita con `QY_HARDWARE=1`).
- **Test suite**: **428 passed, 3 skipped** (inclusi 9 property + hardware-gated). Full run: `uv run pytest -q` in ~2.4s.
- **syx_edit.py** (Session 30): byte-level tempo editor per .syx QY70; bypass bitstream encoder rotto. **Verificato su hardware** (single cycle, session 30b): `syx_edit.py SGT.syx --tempo 120 -o out.syx` → send → dump QY70 conferma decoded[0]=0x3F, BPM=120. **Quirk confermato** (session 30c): QY70 entra in "transmitting freeze" su bulk successivi, power-cycle non sufficiente — uso normale è 1 edit + 1 send per power cycle

Dettagli: [wiki/conversion-roadmap.md](wiki/conversion-roadmap.md), [wiki/decoder-status.md](wiki/decoder-status.md)

---

## Cosa è bloccato (research)

- **Decoder dense** (factory styles): struttura parzialmente compresa (per-beat rotation, 42B super-cycle SGT, 692B shared prefix) ma **nessun output MIDI corretto** prodotto. Structural impossibility provata su velocity encoding (Session 20). Stima: 10-30 sessioni residue, non garantito (forse serve firmware dump)
- **Encoder dense** (Q7P → SysEx): dipende dal decoder, 0% fatto. **Session 30 conferma**: converter `QY700ToQY70Converter.convert_bytes()` produce bulk che il QY70 riceve ma interpreta come "svuota edit buffer" invece di "carica pattern" — bitstream encoding non valido
- **Chord transposition layer**: non decodificato — bar headers memorizzano chord-relative templates
- **Voice writes al QY700**: offset reali sconosciuti (0x1E6/0x1F6/0x206 causavano bricking, ora disabilitati). **Alternativa identificata (Session 30e)**: usare XG Param Change runtime per Bank/Program/Voice invece di scrivere a offset Q7P ignoti

Dettagli: [wiki/open-questions.md](wiki/open-questions.md), [wiki/bitstream.md](wiki/bitstream.md)

---

## Cosa non è ancora iniziato

- **Editor GUI**: nessuna interfaccia grafica (solo CLI)
- **Batch conversion**: conversione multipli file
- **Conversione chord tracks completa** (QY70 → QY700)
- **Hardware roundtrip edit**: caricare Q7P editato sul QY700 e riprodurre (richiede safe_q7p_tester)

---

## Raccomandazione strategica

**Costruire editor completo sopra Pipeline B** anziché attendere decoder dense.

Workflow (Session 29h, prototipo esteso):
1. Utente suona/registra pattern sul QY70 **oppure** parte da zero con `new-empty`
2. Sistema cattura MIDI playback via `capture_playback.py`
3. `qymanager edit export` / `new-empty` → JSON editabile
4. `qymanager edit transpose / add-note / resize / diff / set-velocity / ...` → modifiche
5. `qymanager edit build` → Q7P per QY700 + SMF standard

Pro: consegna prodotto funzionante molto prima, bypassa decoder dense irrisolto.
Contro: meno "puro" — serve QY70 hardware connesso per catturare.

Vedi [wiki/pattern-editor.md](wiki/pattern-editor.md) per comandi e workflow dettagliati.

### XG Protocol (Session 30e–30f) — fonte complementare

Il QY70 è un tone generator XG completo ([wiki/xg-parameters.md](wiki/xg-parameters.md)). Con XG PARM OUT attivo, al cambio pattern emette via MIDI lo stato XG (Multi Part, Effect, Drum Setup). **Persistenza**:
- XG Param Change esterno via MIDI IN = RUNTIME (non salvato nel pattern)
- XG events inseriti via Event Edit del QY70 = SALVATI nel pattern
- Pattern dump Model 5F NON contiene XG (verificato su ground_truth_C_kick.syx: 0 messaggi XG)

**⚠️ Limite XG PARM OUT (Session 30f)**: del blocco Multi Part (`AH=0x08`) vengono emessi solo `AL=07` Part Mode, `AL=11` Dry Level, `AL=23` Bend Pitch. Mai Bank/Program (AL=01/02/03). Le voci programma viaggiano come eventi canale MIDI standard (`Bn 00 MSB`, `Bn 20 LSB`, `Cn PROG`), che `capture_xg_stream.py` pre-fix filtrava. Uso corretto: `capture_xg_stream.py --all -o out.syx`, poi `xg_param.parse_all_events(path)` → `(xg_msgs, channel_events)`.

Tool: `qymanager xg` / `midi_tools/xg_param.py` (parse/summary/diff/emit + `parse_all_events` misto).

---

## Prossimi passi prioritari

F1→F12 del piano integrale completati. Ordine suggerito per continuare:

1. **F6 — P4a Voice offsets Q7P (hardware yolo)**: `safe_q7p_tester.py` + offset sweep 0x100–0x260 su QY700 secondario. Critico per voice writes affidabili in Pipeline B.
2. **F7 — P4b Phrase library mapping integrale**: dump BULK ALL QY70 + QY700 → tabella 4167↔3876 deterministica in `mapping_tables.py`.
3. **F8 — P4c Chord transposition layer**: bar header chord mask + formula transpose (critico per Chord1/Chord2 phrase conversion).
4. **F10 — P4e Q7A format**: parser per aggregato QY700 (backup totale).
5. **F13 — P4d Dense bitstream** (background, long-term): 42B super-cycle SGT → MIDI note.
6. **Hardware test suite reale**: scrivere test con `QY_HARDWARE=1` su offset sweep e realtime echo.

---

## Stime residue (sessioni simili alle recenti)

| Task | Stima | Confidenza |
|------|-------|------------|
| Decoder dense completo | 10-30 sessioni | Bassa |
| Encoder dense Q7P→SysEx | 5-10 sessioni | Media (post-decoder) |
| Editor CLI funzionalità complete | 5-10 sessioni | Alta (prototipo base pronto) |
| Editor GUI | +10-20 sessioni | Media |
| Hardware-validate editor output | 1-2 sessioni | Alta |

---

## File di riferimento

- **[PLAN.md](PLAN.md)** — piano integrale F1→F14 (ralph roadmap)
- **[qymanager/model/](qymanager/model/)** — Unified Data Model (F1 P1.1)
- **[wiki/conversion-roadmap.md](wiki/conversion-roadmap.md)** — pipeline details, blocking issues
- **[wiki/decoder-status.md](wiki/decoder-status.md)** — per-encoding confidence, history sessioni
- **[wiki/bitstream.md](wiki/bitstream.md)** — dense encoding structure
- **[wiki/open-questions.md](wiki/open-questions.md)** — hypotheses aperte
- **[wiki/log.md](wiki/log.md)** — log cronologico sessione-per-sessione
- **[CLAUDE.md](CLAUDE.md)** — istruzioni di progetto per AI agents
