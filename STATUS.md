# Project Status — qyconv

> Single-source north-star del progetto QY70 ↔ QY700 reverse engineering.
> Aggiornato a ogni chiusura di sessione.

**Ultimo aggiornamento**: 2026-04-17 (Session 30 — QY70 SysEx protocol validato + syx_edit.py byte-level editor applicato su hardware con successo)
**Obiettivo finale**: Editor completo pattern + conversione bidirezionale QY700 ↔ QY70

---

## Valutazione generale

| Area | Stato | % completato |
|------|-------|---------------|
| Conversione QY70 → QY700 (Pipeline B capture-based) | **Production-ready** | 100% |
| Conversione QY70 → QY700 (Pipeline A SysEx decode) | Research-blocked | 10% |
| Conversione QY700 → QY70 (metadata only) | Parziale (musicalmente errato) | 30% |
| Editor pattern (CLI prototipo) | **In progress** | ~35% |
| **Obiettivo finale complessivo** | In progress | **~43-53%** |

---

## Cosa funziona (alta confidenza)

- **Pipeline B**: capture QY70 → quantize → Q7P 5120/6144B. Roundtrip byte-valid verificato su hardware: 208/208 note SGT, 126/126 Summer, DECAY self-parse byte-identical
- **Metadata converter** (`qy70_to_qy700.py`): tempo, nome, volume, pan, chorus/reverb
- **Decoder sparse** (user patterns): 100% su 7/7 casi noti (rotation R=9×(i+1))
- **Q7P format**: read + write + validator con invariant phrase-stream (0 warnings)
- **Hardware I/O**: Init handshake, bulk dump, send style, capture playback tutti funzionanti. **Coordinate SysEx confermate (Session 30)**: Model=0x5F, device=0, AM=0x7E (solo edit buffer; slot User rifiutato)
- **Editor CLI prototipo** (`midi_tools/pattern_editor.py` + `cli/commands/edit.py`): **21 sub-command** — export, summary, list-notes, new-empty, add-note, remove-note, transpose, shift-time, copy-bar, clear-bar, kit-remap, humanize, humanize-timing, velocity-curve, set-velocity, set-tempo, set-name, resize, diff, merge (overlay/append), build. **5 comandi multi-track** (`--all-tracks`): `shift-time`, `humanize`, `humanize-timing`, `velocity-curve`, `set-velocity`. Accessibile via modulo (`python3 -m midi_tools.pattern_editor`) **e** CLI principale (`qymanager edit`). Test roundtrip bijective JSON ↔ QuantizedPattern
- **Test suite**: **131 test** regression verdi (59 editor + 31 pipeline + 8 syx_edit + 33 altri)
- **syx_edit.py** (Session 30): byte-level tempo editor per .syx QY70; bypass bitstream encoder rotto. **Verificato su hardware**: `syx_edit.py SGT.syx --tempo 120 -o out.syx` → send → dump QY70 conferma decoded[0]=0x3F, BPM=120

Dettagli: [wiki/conversion-roadmap.md](wiki/conversion-roadmap.md), [wiki/decoder-status.md](wiki/decoder-status.md)

---

## Cosa è bloccato (research)

- **Decoder dense** (factory styles): struttura parzialmente compresa (per-beat rotation, 42B super-cycle SGT, 692B shared prefix) ma **nessun output MIDI corretto** prodotto. Structural impossibility provata su velocity encoding (Session 20). Stima: 10-30 sessioni residue, non garantito (forse serve firmware dump)
- **Encoder dense** (Q7P → SysEx): dipende dal decoder, 0% fatto. **Session 30 conferma**: converter `QY700ToQY70Converter.convert_bytes()` produce bulk che il QY70 riceve ma interpreta come "svuota edit buffer" invece di "carica pattern" — bitstream encoding non valido
- **Chord transposition layer**: non decodificato — bar headers memorizzano chord-relative templates
- **Voice writes al QY700**: offset reali sconosciuti (0x1E6/0x1F6/0x206 causavano bricking, ora disabilitati)

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

---

## Prossimi passi prioritari

Ordine suggerito (ciascuno = 1+ sessione):

1. **Editor hardware test**: caricare Q7P editato sul QY700 con `safe_q7p_tester.py`, verificare playback
2. **Editor features**: undo/redo via snapshot, batch command file
3. **Hardware**: catturare ground truth patterns A/B/C/D (chord semplici) per validare chord decoder dense
4. **Editor GUI**: opzionale, dopo consolidamento CLI
5. **Decoder dense** (parallelo, long-term): mappare 42B super-cycle SGT → MIDI note

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

- **[wiki/conversion-roadmap.md](wiki/conversion-roadmap.md)** — pipeline details, blocking issues
- **[wiki/decoder-status.md](wiki/decoder-status.md)** — per-encoding confidence, history sessioni
- **[wiki/bitstream.md](wiki/bitstream.md)** — dense encoding structure
- **[wiki/open-questions.md](wiki/open-questions.md)** — hypotheses aperte
- **[wiki/log.md](wiki/log.md)** — log cronologico sessione-per-sessione
- **[CLAUDE.md](CLAUDE.md)** — istruzioni di progetto per AI agents
