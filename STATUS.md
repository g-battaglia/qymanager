# Project Status — qyconv

> Single-source north-star del progetto QY70 ↔ QY700 reverse engineering.
> Aggiornato a ogni chiusura di sessione.

**Ultimo aggiornamento**: 2026-04-17 (Session 31a+31b — ralph loop avviato su branch `task/agent`. **F1 P1.1 Unified Data Model** completato: `qymanager/model/` con 15 dataclasses + 12 enum + serializzazione JSON + 67 unit test. **F1 P1.2a Q7P reader UDM-aware**: `parse_q7p_to_udm()` produce `Device` con un `Pattern` da bytes Q7P validi + 23 integration test. Test suite: **254 test verdi** (+90 vs 164 baseline pre-ralph). Codice ralph pulito per ruff/black/mypy)
**Obiettivo finale**: Editor completo pattern + conversione bidirezionale QY700 ↔ QY70

---

## Valutazione generale

| Area | Stato | % completato |
|------|-------|---------------|
| Conversione QY70 → QY700 (Pipeline B capture-based) | **Production-ready** | 100% |
| Conversione QY70 → QY700 (Pipeline A SysEx decode) | Research-blocked | 10% |
| Conversione QY700 → QY70 (metadata only) | Parziale (musicalmente errato) | 30% |
| Editor pattern (CLI prototipo) | **In progress** | ~35% |
| Unified Data Model (UDM) — fondamenta architetturali | **In progress** | ~30% (schema+Q7P-parse; manca Q7P-emit, .syx, SMF, XG bulk) |
| **Obiettivo finale complessivo** | In progress | **~43-53%** |

---

## Cosa funziona (alta confidenza)

- **Pipeline B**: capture QY70 → quantize → Q7P 5120/6144B. Roundtrip byte-valid verificato su hardware: 208/208 note SGT, 126/126 Summer, DECAY self-parse byte-identical
- **Metadata converter** (`qy70_to_qy700.py`): tempo, nome, volume, pan, chorus/reverb
- **Decoder sparse** (user patterns): 100% su 7/7 casi noti (rotation R=9×(i+1))
- **Q7P format**: read + write + validator con invariant phrase-stream (0 warnings)
- **Hardware I/O**: Init handshake, bulk dump, send style, capture playback tutti funzionanti. **Coordinate SysEx confermate (Session 30)**: Model=0x5F, device=0, AM=0x7E (solo edit buffer; slot User rifiutato)
- **Editor CLI prototipo** (`midi_tools/pattern_editor.py` + `cli/commands/edit.py`): **21 sub-command** — export, summary, list-notes, new-empty, add-note, remove-note, transpose, shift-time, copy-bar, clear-bar, kit-remap, humanize, humanize-timing, velocity-curve, set-velocity, set-tempo, set-name, resize, diff, merge (overlay/append), build. **5 comandi multi-track** (`--all-tracks`): `shift-time`, `humanize`, `humanize-timing`, `velocity-curve`, `set-velocity`. Accessibile via modulo (`python3 -m midi_tools.pattern_editor`) **e** CLI principale (`qymanager edit`). Test roundtrip bijective JSON ↔ QuantizedPattern
- **Unified Data Model (F1 P1.1 — session 31a)**: `qymanager/model/` con 15 dataclass (`Device`, `Pattern`, `Section`, `PatternTrack`, `Voice`, `DrumSetup`, `Effects`, `Reverb`, `Chorus`, `Variation`, `Song`, `MultiPart`, `Phrase`, `GrooveTemplate`, `System`, `FingeredZone`) + 12 enum + `TimeSig` frozen + JSON serializer + `.validate()` ricorsiva. **67 unit test verdi** (`tests/test_udm_schema.py`). Device-in-the-loop: `_raw_passthrough` preserva i bytes originali per roundtrip.
- **Q7P reader UDM-aware (F1 P1.2a — session 31b)**: `qymanager/formats/qy700/reader.py::parse_q7p_to_udm(data) → Device` produce `Device(model=QY700, patterns=[Pattern])` popolando nome/tempo/time-sig/8 sezioni/16 tracce con Voice (Bank MSB+LSB+Program) + volume/pan/reverb-send/chorus-send via `Q7PAnalyzer`. **23 integration test verdi** (`tests/test_q7p_to_udm.py`) su fixture SGT/Summer/DECAY.
- **Test suite**: **254 test verdi** (164 baseline pre-ralph + 67 UDM schema + 23 Q7P→UDM; +90 totali). Ralph branch `task/agent` 4 commit avanti a `main`.
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

Ordine suggerito — ralph loop in corso su `task/agent`, continua da F1 P1.2b:

1. **F1 P1.2b — Q7P writer UDM-aware**: `writer.py::emit_udm_to_q7p(device) → bytes` + roundtrip property test `parse(emit(device)) == device`
2. **F1 P1.2c/d — `.syx` sparse reader/writer UDM-aware**: migrare `qy70/syx_parser.py` su UDM
3. **F1 P1.3 — SMF parse side + XG bulk parser UDM-aware** (`xg_bulk.py` nuovo)
4. **F2 → F3 — Editor offline (System/Part/Drum/Effect CLI)** sopra UDM
5. **Editor hardware test**: caricare Q7P editato sul QY700 con `safe_q7p_tester.py`
6. **Decoder dense** (parallelo, long-term): mappare 42B super-cycle SGT → MIDI note

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
