# Log

Chronological record of sessions, discoveries, and wiki changes.

## [2026-04-17] session-29 | Pipeline B estesa 6-bar, validator invariant, SGT bitstream density

### DECAY → QY70 tentativo (confermato: converter QY700→QY70 produce bitstream errato)
- `DECAY_qy70.syx` inviato al QY70 (15/15 msg, 0 errori): MIDI comms ok, pattern caricato ma musicalmente rotto
- Diagnosi: encoder bitstream dense non risolto (task #55/#59) → dati validi a livello SysEx (checksum OK), scorretti a livello semantico
- Memory feedback aggiornata: `Converter QY700→QY70 produce dati musicalmente errati`

### Pipeline B 6144B: SGT..Q7P scaffold supportato (task #69)
- `midi_tools/build_q7p_5120.py` generalizzato a scaffold 5120 **e** 6144
- Nuova funzione `build_q7p(pattern, scaffold_path)` auto-detect size via `PHRASE_AREA_END_BY_SIZE`
- `build_5120_q7p()` mantenuto come back-compat alias con guard
- **Layout 6144B validato** (SGT..Q7P): phrase area `0x200-0x13FF` (4608B), trailer `0x1400-0x17FF` (1024B)
- Regressione: SGT S28 capture a 6 bar produce Q7P 6144B con **0 validator warning**

### Validator Q7P: invariant phrase-stream estesi (task #70)
Aggiunti a `validate_q7p()`:
- `len(blocks) ≤ 16` (QY700 track cap)
- Section pointer uniqueness + contiguità (step=9)
- Overlap detection tra phrase blocks (PHRASE_SLOT=0x80 minimum)
- Phrase boundary check dentro `[0x200, phrase_area_end)`
- Max section pointer scala con size (0x400 per 5120, 0x1400 per 6144)

### SGT bitstream density map (task #72 → data-points per task #55)
Ratio byte/note catturato su SGT S28 (151 BPM, 4 bar, 208 note totali):
| Track | Ch | Bitstream | NoteOn | B/note |
|-------|-----|-----------|--------|--------|
| RHY1 | 9 | 771B (6 msg) | 274 | **2.81** (dense) |
| RHY2 | 10 | 257B | 69 | 3.72 |
| BASS | 11 | 128B (1 msg) | 7 | 18.29 (sparse) |
| CHD1 | 12 | 257B | 52 | 4.94 |
| PAD | 14 | 257B | 48 | 5.35 |
| PHR1 | 15 | 257B | 61 | 4.21 |

Correlazione: **RHY1 è l'unico con layout 6-msg/771B** — tutte le altre tracce stanno in 1-2 messaggi (128/256B). Questo conferma la struttura ipotizzata dove drum ch9 ha bitstream esteso (encoding dense per multi-drum-hits), mentre gli altri track usano single-voice encoding.

Ipotesi ricerca: ratio ~2.81 B/note RHY1 = mix di eventi 2B e 3B, dove ~80% sono 3-byte (delta+note+velocity) e ~20% sono 2-byte (delta+note con velocity default).

### Dense encoding breakthrough — beat-position structure (task #55 in progress)

Analizzando Summer ground truth v2 (4 bar × 4 beat × 3-4 drum strikes per event = 61 strikes mappate esattamente):

**Struttura evento 7-byte**:
- Ogni evento 7B = 1 quarter-note beat (4 eventi per bar × 4 bar = 16 eventi per pattern)
- Strikes encoding: 3 drum hits per beat (per RHY1), 2-4 voices per beat (CHD1/PHR2)

**Per-beat position rotation (R) trovata**:
- Beat 0 (P1=kick+2hat): R=0, 32/56 bit costanti tra bar 1/2/4
- Beat 1 (P2=snare+2hat): R=2, 32/56 bit costanti
- Beat 2 (P3=hat+kick+hat): R=1, **44/56 bit costanti** (= pattern ID)
- Beat 3 (variabile): non uniforme

**Bit structure per beat 2 (R=1, 44 bit pattern + 12 bit variable)**:
`1 0001 1001 0100 VVVVVVVV 1111 VVVV 1010 0000 1010 1100 0010 1010 000`
dove V = velocity/groove-humanization variabili

**Bar 3 outlier consistente** → segment 3 = FILL o MAIN B variant

### Cross-track byte sharing (CHD1 vs PHR2, same 257B allocation)
Al livello byte raw (senza rotazione), tra CHD1 (preamble 2D2B) e PHR2 (preamble 303B):
- Beat 1: byte 0 + 5 + 6 SEMPRE uguali (bars 1,2,4)
- Beat 2: byte 4 + 5 + 6 SEMPRE uguali
- Beat 3-4: parzialmente uguali

**Interpretazione**: "beat-template bytes" sono TRACK-INVARIANTI per 2 tracce con encoding diverso. Ciò indica che il groove/timing è encodato in POSITION-FIXED bytes, separati dai "note-content bytes". Ogni track varia solo i byte che codificano contenuto melodico/drum.

### Tests (31 passing, +4 da session 28)
- `test_roundtrip_hardware_capture_s28_6bar_6144` — 6-bar SGT → 6144B Q7P byte-valid
- `test_duplicate_section_pointers_flagged`
- `test_section_pointers_must_step_by_9`
- `test_6144_scaffold_accepts_wider_section_pointers`

### Files modificati
- `midi_tools/build_q7p_5120.py` — `build_q7p()`, `PHRASE_AREA_END_BY_SIZE`, validator extensions
- `tests/test_quantizer.py` — 4 nuovi test (6144B + validator invariants)
- `wiki/conversion-roadmap.md` — Pipeline B ora supporta 4-bar E 6-bar

### Strategic assessment & session closure (2026-04-17)

Utente ha chiesto valutazione realistica. Valutazione condivisa:
- Pipeline B production-ready → ~30-40% obiettivo finale completato
- Pipeline A (decoder dense) **research-blocked** → ~10% di compresione strutturale, 0% output MIDI corretto
- Raccomandazione: costruire editor completo sopra Pipeline B anziché attendere decoder dense
- Stime residue: decoder dense 10-30 sessioni (non garantito); encoder 5-10 post-decoder; editor UI 10-20

Aggiornata documentazione:
- `wiki/decoder-status.md` — nuova sezione "Strategic Assessment" + history 28-29e
- `wiki/conversion-roadmap.md` — Strategic Assessment prima di "What Works Today"
- `wiki/bitstream.md` — nuova sezione "Dense Encoding Structure (29c-e)" con tabelle per-beat R, cross-track sharing, SGT 42B super-cycle
- `wiki/open-questions.md` — aggiunta Session 29d (multi-section map) e 29e (42B period finding)

### SGT RHY1 bulk-dump structural analysis (task #55 continuation)
Decodificato 7-bit `tests/fixtures/QY70_SGT.syx` → 13184 byte 8-bit. Mappato struttura multi-sezione SGT:
- 6 preamble RHY1 (`25 43 60 00`) alle posizioni 24, 2200, 4248, 6296, 8472, 10648
- Preamble identico a Summer (28 byte con `0804820100402008...` ... `2543 6000`)
- Sezioni size: 2176, 2048, 2048, 2176, 2176, 2539 (non uniformi → diverse classi: MAIN/FILL/INTRO/ENDING)
- **Prefix comune 692 byte tra tutte 6 sezioni** — inizio divergence a byte 692 → preamble estesa/init-block condiviso
- **Periodo dominante in pattern data: 42 byte (= 6 × 7-byte events)** — superamente sul 7 e 14

**Sec2 (MAIN B) gruppo 0**: eventi 1/2/3 **byte-identici** (`c7e37178be9f8f`), 4 bit differenza evento 0, eventi 4-5 variano. Conferma: dense encoding è byte-aligned a 7-byte events + super-cycle 42B.

**Cross-section end-markers**:
- Sec1/Sec2/Sec4 hanno identical trailer 16B: `99949786445ec628ae8d093d8e64dc00`
- Sec3/Sec5 hanno identical trailer: `8b85d2f13c128942211048980c060140`
- Sec6 unico (ENDING)

**Implicazione**: SGT dense encoding segue struttura ripetitiva con super-cicli da 6 eventi = 42 byte. Summer (4-beat, 28 byte per bar) potrebbe essere il caso degenere del super-ciclo. Decoder dense dovrebbe lavorare su blocchi di 42 byte, non eventi singoli.

**Apertura**: mappatura dei 42-byte super-cycle a beats/subdivisions MIDI rimane aperta. Da testare: se 42B = 1 bar (6 subdivisions) o 1.5 bar o altro.

---

## [2026-04-16] session-28 | Hardware-in-the-loop Pipeline B validata

### QY70 collegato, hardware I/O completo
Utente ha collegato il QY70 via UR22C Porta 1. Verificato tutto il flusso:
- **Identity reply**: `43 00 41 02 55 00 00 00 01` (Yamaha, XG Family, QY70 member 0x5502)
- **Bulk dump request**: funzionante con Init handshake — pattern slot 0 = 16274B (103 messaggi)
- **MIDI capture**: playback catturato con MIDI Start+Clock (sync External)
- **Style send**: auto_capture_pipeline invia 105 SysEx (SGT) + cattura playback live

### Pipeline B end-to-end con hardware
`auto_capture_pipeline.py tests/fixtures/QY70_SGT.syx -b 151 -n 6 -d 12` esegue:
1. Send 105 SysEx (16292B) → QY70 edit buffer
2. Start MIDI + Clock 151 BPM per 12s
3. Capture 1056 events (511 note-on, 6 canali attivi: 9/10/11/12/14/15)
4. Quantize → 310 note in 6 tracce
5. Build 5120-byte Q7P + SMF + phrases bin

Risultato: `s28_sgt/sgt_5120_4bar.Q7P` → roundtrip 208/208 note (4-bar truncated), validator 0 warnings.

### AM response mapping scoperto
Differenza tra riferimento e dump:
- File `.syx` di reference: header `AM=0x7E` (edit buffer write)
- QY70 dump response: header `AM=0x00` (pattern slot 0)
- AL parameter ignorato in dump response: QY70 restituisce sempre pattern completo (16274B) indipendentemente da AL=0x00-0x07 o 0x7F

### Limite osservato
Phrase area 2048B (0x200-0x9FF) insufficiente per 6 tracks × 6 bar SGT — PHR1 da solo serve 307B. Necessario:
- Ridurre bar (6→4), oppure
- Usare scaffold 6144-byte (SGT..Q7P, phrase area 3072B)

Validator e builder ora segnalano il caso con `ValueError` descrittivo.

### File generati Session 28
- `midi_tools/captured/s28_current_pattern.syx` — dump pattern slot 0 (16274B)
- `midi_tools/captured/s28_sgt/capture.json` — 1056 MIDI events
- `midi_tools/captured/s28_sgt/sgt_5120_4bar.Q7P` — Q7P hardware-verified roundtrip

### AH sweep: nuove aree dumpabili scoperte
Sweep sistematico AH=0x00..0x7F con dump request. Tre nuove aree scoperte oltre a AH=0x00 (pattern body):

| AH | Size | Msg | Contenuto |
|----|------|-----|-----------|
| `0x03` | 48 B | 1 | System meta trailer (37B body) |
| `0x04` | 16322 B | 104 | Full dump = AH=0x00 + AH=0x03 |
| `0x05` | 331 B | 1 | **Pattern name directory** (20×16B) |

**AH=0x05 decodificato completamente**: 20 slot × 16 byte. Primi 8 byte = nome ASCII; restanti 8 byte = metadata. Slot vuoti = `2A 2A 2A 2A 2A 2A 2A 2A` (8 asterischi, come rendering QY70). Confermato U01-U20 user slots.

**AH=0x04 = superset**: prime 103 msgs identiche (con 3 differenze minori nei chunk header/footer) a AH=0x00; l'ultima msg (48B) è byte-identical al dump AH=0x03.

**AL ignorato in dump response**: QY70 restituisce sempre size fisso per area, indipendentemente dal parametro AL della request.

Nuovo decoder: `midi_tools/decode_pattern_names.py`.  Nuova wiki page: [pattern-directory.md](pattern-directory.md).

## [2026-04-16] session-27 | Q7P 5120 cross-pattern validation + phrase block header decoded

### Pipeline B validata cross-pattern
Build + roundtrip verificati su TRE pattern indipendenti:
- **Summer 5120**: 126/126 note, 5 tracks (RHY1/CHD1/CHD2/PHR1) → già validato S26
- **SGT 5120**: 250/250 note, 6 tracks (RHY1/RHY2/BASS/CHD1/PAD/PHR1) — nuovo
- **DECAY self-parse**: 12 blocks, 437 eventi totali, walker byte-identical

Pipeline B robusta su dataset eterogenei (drum+melody, 151BPM e 120BPM, da 5 a 6 tracks).

### Phrase block header: layout completo decodificato
Ogni phrase block ha un header di **26 byte (0x1A)** prima del stream `F0 00 ... F2`:

| Offset | Bytes | Meaning |
|--------|-------|---------|
| +0x00 | 12 | Nome phrase (ASCII, padded con spazi) |
| +0x0C | 2 | Costante `03 1C` — tipo/lunghezza |
| +0x0E | 2 | `00 00` |
| +0x10 | 2 | `00 7F` — chord (7F=none?) |
| +0x12 | 3 | `00 07 90` — params (pan/vol?) |
| +0x15 | 3 | `00 00 00` |
| **+0x18** | **2** | **Tempo BE16 (×10) — es. `04B0` = 120.0 BPM** |
| +0x1A | — | Start F0 00 event stream |

Scoperta: ogni phrase block include la propria BPM (utile se phrase condivise tra pattern con tempi diversi).

### Mappa dimensioni Q7P (parziale)
Le dimensioni Q7P variano per spazio phrase area:

| Size | File | Phrase region | Metadata start |
|------|------|---------------|----------------|
| 3072 | VUOTO.Q7P | — (empty) | 0x876 (compact) |
| 4096 | SUMMEROG/TR4 | 0x200-0x5FF | 0x600 |
| 4608 | WINDY | 0x200-0x79F | 0x780 |
| 5120 | DECAY | 0x200-0x9FF | 0xA00 |
| 5632 | PHONE | 0x200-0xA7F | 0xA80 |
| 6144 | SGT..Q7P | 0x200-0xDFF | 0xE00 |

Metadata layout all'inizio metadata: nome (8B) + tempo BE16 + altri campi. Il formato 3072-byte usa posizioni diverse (legacy compact).

### Nuovi test di regressione
Aggiunti 2 test a `tests/test_quantizer.py`:
- `TestPhraseBlockLayout::test_decay_phrase_headers` — valida tempo @ +0x18 e F0 00 @ +0x1A
- `TestDecayIdentityRoundtrip::test_decay_phrase_bytes_roundtrip` — walker re-emette bytes identici

**22/22 test quantizer pass.** Milestone stabile.

### Limiti confermati
- Hardware testing ancora non eseguito (risk bricking)
- Gate formula `tick_dur // 4` assunta ma non validata contro firmware QY700
- Formato 3072-byte usa layout diverso dai ≥4096-byte

## [2026-04-16] session-26 | Pipeline B end-to-end: 126/126 note roundtrip verified

### Pipeline B completata su Summer
Pipeline cattura-a-Q7P verificata end-to-end con il pattern Summer come input.
Cattura MIDI → quantizzatore → file SMF + Q7P 5120-byte → riconversione MIDI.
Output: **126/126 note note-for-note esatte, durata 8.00s (4 bar @ 120 BPM)**.

### Bug D0/E0 encoder scoperto e fixato
`encode_phrase_events()` scriveva il formato evento sbagliato:
- D0 prima: `D0 [note] [vel] [gate]` → corretto: `D0 [vel] [note] [gate]` (4 byte)
- E0 prima: `E0 [note] [vel] [gate]` (4 byte) → corretto: `E0 [gate] [param] [note] [vel]` (5 byte)

Il formato corretto è stato verificato da DECAY.Q7P (kick: `D0 3C 24 48` = vel=60, GM=36, gate=72; piano pad: `E0 1E 00 37 7F` = gate=30, param=0, G3, vel=127).

Prima del fix: CHD2 perdeva 4/12 note nel roundtrip. Dopo il fix: 12/12.

### Nuovo builder: `midi_tools/build_q7p_5120.py`
Costruisce un Q7P 5120-byte completo usando DECAY.Q7P come scaffold strutturale:
- Sostituisce solo le aree phrase blocks (0x200-0x9FF) e section pointers/configs (0x100-0x1FF)
- Preserva ogni altro byte (header, tabelle parametri, metadata trailing)
- Validatore confronta output vs scaffold: flag su modifiche fuori regione sicura

Output roundtrip-validato: `midi_tools/captured/summer_5120.Q7P` (126 note esatte).

### Fix quantizer
`quantize_capture()` accettava solo capture con chiave "raw". Ora supporta anche "events" (formato della cattura Summer).

### Limiti noti (NON risolti in questa sessione)
- **Hardware testing**: il Q7P 5120-byte generato NON è stato testato su QY700. Regioni sconosciute del formato restano un rischio di bricking. L'utente deve verificare con cautela.
- **Dense decoder**: encoding 2543/2D2B/303B del QY70 resta parzialmente risolto. Pipeline B bypassa completamente il dense decoder usando MIDI capture come source-of-truth.

### Impatto sul roadmap
Completamento gate #3 del conversion-roadmap: QY70 → Q7P 5120-byte con fidelity totale (via MIDI capture). Il converter QY70→QY700 può ora:
1. Ricevere dump SysEx dal QY70
2. Riprodurre il pattern via SysEx e catturare l'audio MIDI
3. Generare Q7P pronto per QY700 (pending hardware validation)

Files: `midi_tools/build_q7p_5120.py`, `midi_tools/capture_to_q7p.py` (fix), `midi_tools/quantizer.py` (fix), `midi_tools/captured/summer_5120.Q7P`.

## [2026-04-16] session-25h | Summer: 4-bar pattern (not 5), cross-track ground truth, groove template

### Major Correction: Summer is 4 bars, NOT 5
Earlier wiki claimed Summer was a 5-bar pattern. Playback capture fingerprint
analysis across all 12.4 bars proves otherwise:
- bar1 fingerprint = bar5 = bar9 (identical drum note sequences)
- bar2 = bar6 = bar10; bar3 = bar7 = bar11; bar4 = bar8 = bar12 (14-note fill)
- **Pattern period: 8 seconds = 4 bars at 120 BPM**

The RHY1 "seg 5" (4 events) is thus NOT a music bar — its content resembles bar 1
with different bytes but identical output. Role: likely alt-fill or unused marker.

### Cross-Track Ground Truth (`summer_ground_truth_v2.json`)
Mapped all 4 active tracks across corrected 4-bar structure:

| Track | AL | ch | MIDI notes | SysEx events (segs 1-4) | Hit rate |
|-------|----|----|------------|--------------------------|----------|
| RHY1  | 0x00 | 9  | 50 | 16 (4 per bar, 3-4 strikes each) | 49/50 |
| CHD1  | 0x03 | 12 | 32 | 15 (4+2+5+4 per bar) | 28/32 |
| CHD2  | 0x04 | 13 | 12 | 12 (1:1 event↔note) | - |
| PHR1  | 0x05 | 14 | 0  | 12 (muted/zero volume) | - |
| PHR2  | 0x06 | 15 | 32 | 15 (same layout as CHD1) | 28/32 |

**Two distinct encoding regimes revealed**:
- **Segmented dense** (RHY1/CHD1/PHR2, preambles 2543/2D2B): multi-event-per-beat, groove template applied
- **Flat sparse-like** (CHD2/PHR1, preamble 303B): 1:1 event-to-note, but ZERO-byte events still produce valid notes

### CHD2 Anomaly: Zero Events Play Notes
CHD2 events 7-11 are ALL `00000000000000` (or nearly) but produce MIDI:
- Bar 3 chord (t=4s): notes 64/67/71 (E minor) — bytes 0x80 0x00 0x00
- Bar 4 chord (t=6s): notes 62/66/69 (D major) — ALL zeros

Since 6 zero events produce 6 distinct notes, the note data MUST come from outside
the event bytes. Likely source: **chord progression stored in header track AL=0x7F**,
with event bytes 0 only signaling "play chord at this beat" (zero = use current chord).

### Groove Template Hypothesis Strengthened
Confirmed that RHY1 bytes encode a pattern+template reference, not raw velocities:
- Bar 1/5 beat 3 have IDENTICAL velocities (118,124,112) but DIFFERENT bytes 1-3
- Bytes 4-6 = `05 61 50` appears across 4 bars with DIFFERENT actual velocities
- Timing is quantized (constant ~25ms MIDI latency, no swing/humanization)

Runtime template applies deterministic velocity modulation based on beat position.

### Files Created
- `midi_tools/summer_ground_truth_full.py` — all 5 tracks initial mapping
- `midi_tools/summer_ground_truth_v2.py` — corrected 4-bar mapping
- `midi_tools/analyze_rhy1_encoding.py` — byte-role pattern analysis
- `midi_tools/rhy1_timing_analysis.py` — micro-timing verification
- `midi_tools/rhy1_bitfield_search.py` — brute-force bitfield position
- `midi_tools/rhy1_rotation_search.py` — rotation schedule search (all fail)
- `midi_tools/rhy1_groove_hypothesis.py` — coarse velocity quantization test
- `midi_tools/chd1_analysis.py` — single-note chord voice analysis
- `midi_tools/captured/summer_ground_truth_v2.json` — corrected test vector

### Pragmatic Path Forward
Dense encoding remains partially unsolved. For product goals:
1. **Converter QY70→QY700**: use MIDI-capture pipeline (Session 21) — bypasses dense
2. **Pattern editor**: use SPARSE encoding (proven R=9×(i+1)) for user-created patterns
3. **Factory preset import**: capture MIDI + rebuild as sparse Q7P

Dense decoding is a long-term research problem requiring QY70 ROM analysis.

## [2026-04-16] session-25g | Summer MIDI ground truth: 20 events → 61 strikes mapped

### Real Ground Truth Found
`midi_tools/captured/summer_playback_s25.json` contains 395 note-on events from live
Summer playback (4 active channels: 9/12/13/15 over 24.75s @ 120 BPM). This IS the
ground truth we needed — captured live from QY70 MIDI OUT during pattern playback.

### Summer Pattern Structure — Confirmed
- **Tempo**: 120 BPM (hi-hat interval = 0.250s = eighth note)
- **Length**: 5 bars stored, looped 2.5 times = 12.4 bars playback
- **RHY1 bitstream layout**:
  - seg0 (si=0): <13 bytes, skipped
  - seg1..seg5 (si=1..5): **4 events each = 20 events** (the actual music)
  - seg6 (si=6): 5 real events + 11 empty-marker events (`bfdfeff7fbfdfe`) = tail padding
  - Total extracted: 36 events, but only 20 encode bar 1-5 music

### One Event = One Quarter Note = 3 Drum Strikes
Each 7-byte event encodes a single quarter-note beat with up to 3 simultaneous strikes
at the 8th-note subdivisions. Bar 1 mapping:

| Event | Beat | Strikes (from MIDI) |
|-------|------|---------------------|
| e0: `1d349706c062aa` | 1 | KICK vel=127 + HAT vel=122 (8th) + HAT vel=116 (8nd) |
| e1: `28ae8d8144c8fc` | 2 | SNARE vel=115 + HAT vel=122 (8th) + HAT vel=117 (8nd) |
| e2: `8ca52785056150` | 3 | HAT vel=118 + KICK vel=124 (8nd) + HAT vel=112 (8nd) |
| e3: `494f8d820c5479` | 4 | SNARE vel=120 + HAT vel=121 (8th) + HAT vel=114 (8nd) |

### Empirical Clue: Byte Positions Carry Note Identity
Cross-bar comparison of e0 (always beat 1, always KICK+2×HAT):
- Bar 1: `1d 34 97 06 c0 62 aa` → K127 H122 H116
- Bar 2: `1f 74 97 06 40 e2 2a` → K127 H119 H115

Bytes 2-3 (`97 06`) are IDENTICAL across bars with same strike pattern →
likely NOTE IDENTITY encoding. Bytes 4-6 differ only in bit 7, possibly carrying
extra velocity bits.

### Byte-Role Map (hypothesis from 20 events)

Grouped the 20 events by strike signature:
- 9 events = SNARE+HAT+HAT (beats 2 & 4)
- 5 events = KICK+HAT+HAT (beat 1)
- 5 events = HAT+KICK+HAT (beat 3) — **byte 0 = 0x8C constant across ALL 5!**
- 1 event = SNARE+HAT+SNARE+HAT (bar 4 beat 4 fill)

**Discovered byte roles**:
- **byte 0**: strike-pattern identifier (0x1?=K+H+H, 0x2?-0x4?=S+H+H, 0x8C=H+K+H)
- **bytes 4-6**: velocity encoding (bar 1 and bar 5 beat 3 have IDENTICAL vels 118/124/112
  → bytes 4-6 = `05 61 50` in both, despite differing bytes 1-3)
- **bytes 1-3**: still unclear — vary within same-velocity events, possibly encode
  microtiming or per-voice modulation not visible in MIDI OUT capture

### Test Vector Saved
`midi_tools/captured/summer_ground_truth.json` — 20 events mapped to 61 expected
drum strikes. Any future decoder hypothesis must reproduce all 61 strikes.

### Files Created This Session
- `midi_tools/analyze_pattern_c_vs_summer.py` — RHY1 event-level PC vs Summer
- `midi_tools/analyze_pc_is_summer.py` — all-tracks byte PC vs Summer
- `midi_tools/analyze_cross_pattern_signatures.py` — cross-pattern prefix
- `midi_tools/summer_ground_truth.py` — SysEx event → MIDI notes linker
- `midi_tools/captured/summer_ground_truth.json` — 20-event test vector

## [2026-04-16] session-25f | Pattern C INVALIDATED — slot U01 contained Summer

### Critical Finding: Pattern C ≠ Ground Truth
Cross-pattern analysis revealed that the "solo kick" capture is actually Summer's data:
- **CHD1, CHD2, PHR1, PHR2**: BYTE-IDENTICAL to Summer (all 4 tracks, 100% match)
- **RHY1**: first 294 bytes identical to Summer (seg1-seg5 complete drum programming)
  - From byte 294 onwards: PC has all zeros, Summer has continuing data
  - Only 1 "unique" event in PC: `288f8f90008000` at seg6 start
- **Header (AL=0x7F)**: 98.1% identical (628/640 bytes), only 12 diff bytes (pattern name area)

### What Actually Happened
The user programmed a kick pattern on QY70 slot U01 and pressed STORE, but:
- Slot U01 already contained Summer (pre-loaded factory demo or prior session)
- The user's kick edit either didn't save, or only affected the trailing bar/segment
- The capture returned Summer's pattern, not the user's "kick only" intent

### Implications
- `ground_truth_C_kick.syx` is UNRELIABLE for decoder validation
- The earlier "lane model R=46" finding actually describes Summer's drums, not a solo kick
- **Cross-pattern prefix `28ae8d81` appearing in 3 patterns** is explained: PC=Summer, so 3 patterns actually = 2 distinct sources (Summer and A_QY70). A_QY70 may also share drum programming with Summer.

### Required Next Steps (New Ground Truth Needed)
1. Factory reset QY70 slot U01 (or use a confirmed-empty slot like U10)
2. Program MINIMAL pattern (single kick) from truly empty state
3. Verify dump differs from any factory preset before declaring it ground truth
4. Alternative: capture Summer's untouched state as reference, then modify ONE known byte

### Analysis Scripts Created
- `midi_tools/analyze_pattern_c_vs_summer.py` — RHY1 event-level comparison
- `midi_tools/analyze_pc_is_summer.py` — all-tracks byte comparison
- `midi_tools/analyze_cross_pattern_signatures.py` — cross-pattern prefix recurrence

## [2026-04-16] session-25e | Ground truth Pattern C captured, restore tool built

### Ground Truth Pattern C: Solo Kick on Beat 1
- User programmed simplest possible drum pattern on QY70: RHY1 with kick (note 36)
  on beat 1 only, 4 bars, 120 BPM, saved to User Pattern slot U01 (AM=0x00)
- Captured via `request_dump.py --all-tracks` (AH=02, AM=00)
- **Key observation**: QY70 ignores AL parameter — returns full pattern (all tracks)
  regardless of which specific track is requested
- Result: 126 messages = 9 redundant copies × 14 unique bulk dumps (2230 bytes unique)

### RHY1 Analysis (`analyze_ground_truth_kick.py`)
Even with a single-instrument, single-beat pattern:
- **4 events per bar** allocated (confirms lane model)
- **R values are bar-dependent**, not event-index-dependent:
  - e0 uses R=46 in bars 1,2,4,5 — but bar 3 has no e0 solution (instrument reorders to e1 at R=24)
  - e2 alternates R=44/49 between bars
  - e3 alternates R=2/53 between bars
- **F1=368 constant** in e0@R=46 across working bars — likely a fixed instrument ID or beat position
- **Some events structurally cannot produce note 36** at any R — same behavior as Summer
- **Spurious data in CHD1/CHD2/PHR1/PHR2**: pattern slot contained template default data
  (user confirmed slot was empty before programming — QY70 auto-fills non-RHY tracks)

### Restore Tool Built
- `midi_tools/restore_pattern.py` — converts a captured dump into a restore-ready .syx
- Deduplicates redundant bulk dumps (keeps one copy of each unique message)
- Adds Init handshake at start and Close message at end (required by QY70 for accept)
- Validates all checksums before writing
- Optional `--slot N` to remap User Pattern slot (rewrites AM byte, recalculates checksum)
- Optional `--send` to transmit directly after building
- Result: `ground_truth_C_kick_restore.syx` (2230 bytes, validated, ready for re-send)

### Files Created
- `midi_tools/captured/ground_truth_C_kick.syx` — raw capture (9× redundant copies)
- `midi_tools/captured/ground_truth_C_kick_restore.syx` — deduplicated + Init/Close
- `midi_tools/analyze_ground_truth_kick.py` — per-event R-analysis for drum tracks
- `midi_tools/restore_pattern.py` — general-purpose dump restore utility

### Why This Matters
- Confirmed: lane model is universal (4 events/bar even for solo-kick patterns)
- Confirmed: R value is NOT a simple function of event index or header
- Disproves "sparse vs dense depends on note density" — even 1-note pattern is dense
- New hypothesis: encoding regime depends on **track type** (all drum tracks are dense)
- Insurance: if QY70 loses memory, can restore original pattern from saved .syx

## [2026-04-16] session-25d | Dense drum encoding elimination, tempo GT verification

### Tempo GT Verification
- Executed `verify_summer_tempo.py` against captured MIDI timing
- **RHY1 inter-note interval = 0.250s** = exactly one 8th note at 120 BPM
- **CHD1 at 120 BPM**: avg deviation from 8th grid = **1.5ms** (near-perfect alignment)
- **Conclusion**: GT capture plays at 120 BPM (external clock default), NOT at 155 BPM (internal)
- This is expected: QY70 in MIDI SYNC=External follows the clock rate, not internal tempo

### Dense Drum Encoding: Comprehensive Model Elimination
Exhaustive computational analysis of Summer RHY1 (4 events/bar, 12 hits/bar GT):

1. **All cumulative R models fail** (tested mult=1-55, global/per-bar/offset):
   - Best global: mult=11, 4/20 hits (20%)
   - Best per-bar: mult=9, 5/20 hits (25%)
   - No multiplier exceeds chance level

2. **Header-derived R fails**: no formula R=f(header_field[k], event_idx) gives 4/4 per bar

3. **Structural impossibility**: note 38 (snare) UNREACHABLE from Seg 2 events at ANY R (0-55)
   - F0[6:0] cannot equal 38 for any rotation of the 56-bit values
   - Yet GT confirms snare plays in every bar (beats 1.0 and 3.0)

4. **8×7-bit beat-pattern model**: moderate correlation (max 0.979) but wrong absolute values
   - Shape preserved (ranking of velocities matches GT), magnitudes unrelated
   - Best correlation requires different R per bar AND per instrument

5. **Instrument reordering**: "stable core" bytes (`ae8d81` = snare) move between event slots
   - Em bar (Seg 3): snare core appears in e3 slot instead of e1
   - Core bytes identify similar events across bars but don't predict decode success

6. **XOR between working bars**: applying Seg1⊕Seg4 key to Seg2 doesn't make note 38 reachable

### Key Conclusions
- **Barrel rotation model is WRONG for dense patterns** — not a matter of finding correct R
- Three encoding regimes confirmed: sparse user (proven), dense user (unsolved), factory style (unsolved)
- **Simple hardware test patterns are the only path forward** — computational analysis exhausted

### Files Created
- `midi_tools/verify_summer_tempo.py` — multi-BPM GT timing verification
- `midi_tools/analyze_summer_seg_failure.py` — per-segment note reachability analysis
- `midi_tools/analyze_summer_beat_pattern.py` — 8×7-bit beat-pattern hypothesis test
- `midi_tools/analyze_summer_cumulative_r.py` — 7 rotation model variants + XOR + stable core

### Wiki Updates
- `wiki/2543-encoding.md` — instrument lane model rewritten with elimination table, structural impossibility
- `wiki/open-questions.md` — updated with Session 25d progress
- `wiki/header-section.md` — tempo confirmed (previous session)
- `wiki/log.md` — this entry

## [2026-04-16] session-25c | Header track deep analysis, chord transposition solver

### Header Track (AL=0x7F) Structure Discovery
- **640 bytes**, 5 SysEx messages, ~76% constant across all patterns
- **Byte 0x000**: format type marker (`0x03`=user pattern, `0x4C`=loaded style, `0x2C`=empty)
- **Byte 0x004**: section index (0=MAIN-A, 1=MAIN-B) — CONFIRMED
- **0x046-0x07C**: per-track data configuration
  - `0x048-0x04B`: [48,32,20,12] correlate with track sizes/8 (RHY1=384/8=48✓, CHD1=256/8=32✓)
- **Walking zero pattern** `BF DF EF F7 FB FD FE`: empty/unused marker (27% of header)
  - Each byte has ONE bit clear (bit 6→bit 0), 7 zero bits in 56-bit value
- **Structural marker** `40 10 88 04 02 01 00`: empty track slot (5-8 occurrences per file)
- **Universal constant** `64 19 8C C6 23 11 C8` at 0x1A2-0x1AF: present in ALL 4 test files

### Cross-File Header Comparison (4 files)
- Summer, MR. Vain, GT_style, GT_A compared
- ~100-113 bytes differ between any pair (~16%)
- GT_A (empty pattern) has all-zero variable positions → clean baseline
- MR_Vain and GT_style share global config (0x006-0x00D) except 1 byte
- Summer has completely different global config (user-created pattern)

### Chord Transposition Solver (8 approaches, all FAILED)
Exhaustive combinatorial search on CHD1 header fields vs GT chord notes:
1. Single field + offset → NO match
2. Field pair operations (add, sub, XOR, avg, mod128) → NO match  
3. Root extraction (pitch class, MIDI note, bass note) → NO match
4. Field differences as intervals → sporadic matches, no consistency
5. Header as lookup key → all 11 fields change, no obvious structure
6. Raw header byte search → no GT notes found in bytes
7. Nibble extraction → coincidental match only (F#4 in bar 3)
8. Changing field pattern with scale factors → NO root diff correlation

### Key Structural Finding: Shared Fields Between Tracks
- **F0, F5**: ALWAYS identical between CHD1 and PHR1 for same bar
  - F0: bar 0=429, bars 1-3=53 (constant after init bar!)
  - F5: bar 0=84, bars 1-2=77 (changes at bar 3)
- **F1, F6, F10**: shared for bars 1-3, different in bar 0
- **F3, F4, F8, F9**: different between tracks AND between bars → per-track pattern data
- Raw header bytes: bars 1-2 share 9/13 bytes (only 4 bytes encode C major→E minor difference)

### Tempo Formula CONFIRMED
- Initial search for 110 BPM (assumed Summer tempo) found nothing
- **CORRECTION**: Summer is actually **155 BPM** (not 110!) — wrong assumption was the blocker
- Formula `BPM = msg.data[0] × 95 - 133 + msg.data[1]` from raw SysEx payload: **VERIFIED**
  - MR. Vain: data[0]=2, data[1]=76 → **133 BPM** ✓ (Culture Beat confirmed)
  - Summer: data[0]=3, data[1]=3 → **155 BPM**
  - GT_style: data[0]=2, data[1]=76 → 133 BPM
  - GT_A (empty): data[0]=2, data[1]=44 → 101 BPM
- data[0] serves dual purpose: 7-bit encoding group header AND tempo range selector

### Files Created
- `midi_tools/analyze_summer_header_track.py` — full hex dump, byte distribution, pattern search
- `midi_tools/analyze_header_deep.py` — walking zero analysis, active regions, cross-file comparison
- `midi_tools/analyze_header_diff.py` — 4-file byte-by-byte diff, variable/constant classification
- `midi_tools/analyze_header_tempo_chord.py` — focused tempo and chord root search
- `midi_tools/solve_chord_transposition.py` — 8-approach combinatorial chord formula solver

## [2026-04-16] session-25b | Dense encoding deep analysis, groove template discovery

### Ground Truth Capture SUCCESS
- Summer MIDI playback captured via `capture_playback.py`: **395 notes** across 4 channels
  - RHY1 (ch9): 156 notes — 3 instruments: HH(42)×~8/bar, Snare(38)×2/bar, Kick(36)×2/bar
  - BASS (ch12): 100 notes
  - CHD1 (ch13): 39 notes
  - PHR1 (ch15): 100 notes
- Pattern repeats with period 4 (13 bars = 3 repeats + partial)
- PATT OUT=9~16 required (physically set on QY70)

### Instrument Lane Model (Partially Confirmed)
- Summer RHY1: **6 segments** after init, each with 4 events (except seg 5: 16 events with 8 padding `bfdfeff7fbfdfe`)
- **Fixed per-position R values** [R=9, R=22, R=12, R=53] decode correctly for segs 3,4 (4/4 instruments)
- Segs 0,1: 3/4 correct (one event fails per bar)
- **Segs 2,5: 0/4 correct** — completely different encoding or structure
- Seg 2 e0: NO R value (0-55) gives target notes 36/38/42 — fundamentally different data
- **Cumulative R=9×(i+1) FAILS on Summer** (1/4 per bar) — lane model is better but not universal

### GROOVE TEMPLATE Discovery (Major Finding)
- **Per-beat velocities are NOT stored in the RHY1 track data**
- GT HH velocities (112-127) NOT found anywhere in 384 bytes, even with ±2 tolerance
- known_pattern: velocities are exact vel_code×8 multiples (127, 119, 95) → no groove
- Summer: velocities deviate ±5-15 from quantized levels → groove template active
- **Conclusion**: QY70 playback engine applies groove quantization on top of stored coarse vel_code
- Bitstream stores: note, beat pattern, coarse velocity (4-bit), gate time
- Fine velocity variation = runtime groove template, NOT in bitstream

### Velocity Decomposition Attempts (All Failed)
- 8×7-bit (56 bits = 8 velocities): No correlation with GT (sum diffs 400+)
- Inverted/shifted: No consistent mapping
- F1-F4 as beat-pairs: No match
- Header fields as velocity source: All values outside GT range (112-127)
- Derotated bytes as velocities: No matches even with tolerance

### Segment Structure Details
- Track-level header: 24 bytes metadata + 4 bytes preamble
- Init segment: 14 bytes (13B header + 1B trailing 0xF4)
- Normal bars: 41-43 bytes (13B header + 28B events + 0-2B trailing)
- Seg 5 (fill?): 127 bytes (13B header + 114B = 16×7B events + 2B trailing)
- Trailing bytes: `1e20`, `1e40` in normal bars; `bfc0` in fill

### Cross-Bar Event Similarity
- e0 position: 2-7 bits differ between bars (stable = HH)
- e2 position: 2-5 bits differ (stable = HH2?)
- e1, e3 positions: 5-25 bits differ (more variable = Snare/Kick)
- Segs 0≈3, 1≈4 (paired structure), segs 2≈5 (different type)

### Multi-Track GT Validation
- **CHD1 (preamble 2D2B, ch13)**: 39 GT notes → chord progression **G - C - Em - D**
  - Bar 0: G4+B4+D5 = G major, Bar 1: G4+C5+E5 = C major
  - Bar 2: E4+G4+B4 = Em, Bar 3: D4+F#4+A4 = D major
  - Decoder header notes WRONG (A2/F0/F#3 vs G/B/D) → transposition layer unresolved
- **PHR1 (preamble 303B, ch15)**: 100 GT notes → same chords ARPEGGIATED (8 notes/bar, all vel=127)
- **BASS auto-generated**: NO BASS track in SysEx (AL=0x02 absent) but ch12 has 100 notes
  - Plays chord roots: G1(31), C2(36), E1(28), D1(26) matching G-C-Em-D progression
  - Implies QY70 auto-generates bass from chord track data
- **CHD2/PAD**: data in SysEx but 0 GT notes → muted or different channel mapping
- **Groove template ONLY on drums**: chord/phrase tracks all vel=127 (no variation)

### QY70→QY700 Converter Audit
- All 3 safety fixes confirmed in place
- Voice writes to 0x1E6/0x1F6/0x206 disabled
- Pan bounds check correct, post-conversion validation active

## [2026-04-16] session-25 | Decoder verification, Summer analysis, converter audit

### Decoder Verification
- **decode_drum_event() on known_pattern: 7/7 CONFIRMED** — all fields (note, velocity, tick, gate) match perfectly
- Previous session's reported failure was an invocation error (wrong indices), not a decoder bug
- R=9×(i+1) cumulative rotation remains PROVEN correct for sparse user patterns

### Blockers Resolved
- PATT OUT enabled physically on QY70 → capture now works
- Summer playback capture completed (see session-25b above)

## [2026-04-16] session-24 | Q7P event format decoded, QY700→QY70 converter built

### Q7P 5120-byte Event Format — FULLY DECODED
- **D0 [vel] [GM_note] [gate]** = 4-byte drum note (GM standard numbering!)
- **E0 [gate] [param] [GM_note] [vel]** = 5-byte melody note (NOT 4 bytes as previously assumed)
- **C1 [note] [vel]** = 3-byte short/arpeggio note
- **Delta time: A(n) dd = (n-0xA0)×128+dd ticks** at ppqn=480
- **BA/BB [value]** = control events with small delta timing
- Chord patterns have no delta events — groups separated by BE (note off)
- Verified on DECAY.Q7P: all drum notes map to correct GM instruments (BD1=36, HH=42/46, Toms=41/47/48, SideStick=37)
- Melody notes confirmed: piano pad = C major (48,52,55) → F major (48,53,57), bass = C2/F2

### QY700→QY70 Converter Built
- `midi_tools/q7p_to_midi.py` — Q7P → standard MIDI file (all 12 phrases, correct timing)
- `midi_tools/q7p_playback.py` — real-time MIDI playback through any connected synth
- `midi_tools/convert_decay.py` — DECAY-specific conversion pipeline (MIDI + QY70 SysEx)
- `qymanager/converters/qy700_to_qy70.py` — fixed: no longer sends incompatible Q7P events to QY70
- Output: DECAY.mid (1906B, 12 tracks) + DECAY_qy70.syx (2072B, 8 tracks with voice headers)

### DECAY Musical Analysis
- 12 phrases: tom, piano pad, bass, rim, hi hats, dream bells, deepnoisetim, kick, piano tik, guitarpaddy, bells, brum noise
- Chord progression: C major → F major (2 chords over 4 bars)
- 120 BPM, 4/4 time
- Mapped to QY70 tracks: RHY1=kick, RHY2=hihats, BASS=bass, CHD1=piano pad, CHD2=guitar, PAD=dream bells, PHR1=piano tik, PHR2=bells

### Wiki Updates
- Updated [q7p-format.md](q7p-format.md) with complete 5120-byte event format documentation
- Added delta time formula, verified note mapping table, chord pattern structure

## [2026-04-16] session-23 | QY700 MIDI protocol, Q7P analysis, QY70 dump structure

### QY700 MIDI Connection
- Connected QY700 via USB Midi Cable (IN-A/OUT-A)
- **Computer → QY700 works**: note on ch1 heard on QY700
- **QY700 → Computer not yet working**: zero data received (even MIDI Clock), cable issue or MIDI Control Out=Off
- Identity Request: no response yet (return path needed)

### QY700 Protocol from PDF (QY700_REFERENCE_LISTING.pdf)
- **Model ID = `4C` (XG)**, NOT `5F` like QY70
- Identity Reply: `F0 7E 0n 06 02 43 00 41 01 19 00 00 00 01 F7`
- Dump Request: `F0 43 2n 4C AH AM AL F7`
- Parameter Change: `F0 43 1n 4C AH AM AL dd F7`
- Section Control: `F0 43 7E 00 ss dd F7` (can trigger pattern sections!)
- Created wiki page: [qy700-midi-protocol.md](qy700-midi-protocol.md)

### QY70 Real Dumps Analyzed (data/qy70_sysx/)
- **"A" dump** (9713B, 65 msgs): ALL dump with 4 patterns + voice data
  - AM=0x00-0x03: 4 saved pattern slots
  - AH=0x01: voice/system data (6 msgs, 882B)
  - AH=0x03: unknown (1 msg, 37B)
- **"P" dumps** (MR.Vain, Summer): single patterns from edit buffer (AM=0x7E)
- **Section encoding in AL**: section_index × 8 + track_index
  - Summer uses AL=0x00-0x06 (Main A), MR.Vain uses AL=0x08-0x0E (Main B)
- **Empty tracks omitted**: only tracks with data appear in dump

### Q7P File Format (Confidence: High)
- **Magic header**: `YQ7PAT     V1.00` (all 7 files confirmed)
- **Variable sizes**: 3072, 4096, 4608, 5120, 5632, 6144 bytes
- **Section pointers at 0x100**: 16-bit BE, 0xFEFE = inactive
- **TXX vs VUOTO diff**: only 102 bytes differ (section pointers, phrase data, track config)
- Name/tempo at fixed offset from end for some files, but not consistent across all sizes
- Track/phrase names embedded as ASCII strings in phrase data area

### New Data Available
- 7 Q7P files from QY700 floppy (VUOTO, TR4, SUMMEROG, WINDY, DECAY, PHONE, SGT)
- 3 QY70 SysEx dumps (A=all, P=MR.Vain, P=Summer)
- QY700 Reference Listing PDF (voice list, MIDI protocol, implementation chart)

## [2026-04-16] session-22 | Pipeline B end-to-end funzionante, drum output confermato

### Pipeline B fix e prima cattura completa
- **Bug fix critico**: `mi.ignore_types(timing=False)` catturava gli echo del MIDI Clock (0xF8), mascherando le note reali. Fix: `timing=True`.
- **SysEx timing conservativo**: Secondo esemplare QY70 richiede 1s init / 300ms tra messaggi (vs 500ms/150ms del primo).
- **Cattura riuscita**: 851 note_on + 851 note_off, 6 canali, 20s a 151 BPM
- **Quantizzazione**: 322 note su 6 tracce, 6 battute — consistente con vecchia cattura (ratio 1.5:1 per durata diversa)
- **Output generati**: SMF (10.1s, 7 tracce), Q7P (3072B metadata), D0/E0 phrases (1746B)

### DRUM OUTPUT FUNZIONA (corregge finding Session 17)
- Ch9 (RHY1): 455 note_on raw → 161 quantizzate
- Ch10 (RHY2): 114 note_on raw → 47 quantizzate
- Il finding Session 17 "drums don't output via PATT OUT" era **FALSO** — causato dal clock echo che mascherava le note, non da mancata emissione.

### Script migliorati
- `auto_capture_pipeline.py`: fix timing bug, fix `args` globale, aggiunto `--skip-send`, diagnostica per-canale, abort se 0 note
- Default SysEx timing portato a 1s/300ms per compatibilità con entrambe le unità QY70

### SCOPERTA CRITICA: Init Handshake per Dump Request
Il QY70 **richiede un Init message** (`F0 43 10 5F 00 00 00 01 F7`) prima di rispondere alle Dump Request. Senza Init: silenzio totale. Con Init: dump completo e immediato.
- Protocollo: Init → 500ms → Dump Request(s) → Close
- Testato: 115 messaggi SysEx, 18170 bytes (tutti 8 track + header)
- **Tutte le sessioni precedenti (1-21) avevano erroneamente concluso "non supportato"**
- Anche XG Parameter Request funziona (`F0 43 30 4C 08 pp xx F7`) senza handshake

### Anche scoperto: XG Parameter Request
- `F0 43 30 4C 08 pp xx F7` → risposta immediata con parametro XG
- Dà accesso a voci, volume, pan, effetti del tone generator
- Ma NON ai dati pattern interni (per quelli serve il Bulk Dump)

### Wiki Changes
- Aggiornato [conversion-roadmap.md](conversion-roadmap.md): drum capture non più bloccato
- Corretto finding drum PATT OUT
- Aggiornato tutti i docs con Init handshake
- Aggiornato README.md con sezione MIDI completa

---

## [2026-04-15] session-21 | Pipeline B: Capture → Quantize → SMF + Q7P + D0/E0

### Capture Quantizer (`quantizer.py`)
- Parses raw MIDI capture data (note_on/note_off pairs with real-time timestamps)
- Quantizes to 16th-note grid at 480 PPQN
- Auto-detects loop length via per-channel pattern matching + LCM
- SGT results: avg quantization error 1.7ms (drums), 100% events under 10ms
- Channel→track mapping: PATT OUT 9~16 → tracks 0-7 (RHY1..PHR2)

### Capture-to-Q7P Pipeline (`capture_to_q7p.py`)
- End-to-end: JSON capture → quantize → SMF + Q7P + D0/E0 phrase data
- **SMF output**: valid Type 1 MIDI file, verified timing (6 bars = 9.5s at 151 BPM)
- **Q7P output**: 3072B with correct metadata (name, tempo), template events preserved
- **D0/E0 phrase data**: drum tracks as `D0 nn vv gg`, melody as `E0 nn vv gg`
- Delta encoding: A0-A7 dd (hypothesized: step×128+value, needs hardware validation)
- SGT capture: 374 notes across 6 tracks, 2004 bytes total phrase data

### SGT Capture Analysis
- Ch 9 (RHY1): 680 note_ons, 6 unique drums, perfect 1-bar loop
- Ch 10 (RHY2): 170 notes, side stick only
- Ch 12 (CHD1=bass voice): 131 bass notes, 2-bar loop
- Ch 14 (PAD): 114 chord notes, 4-bar loop (3-note chords, 2/bar)
- Ch 15 (PHR1): 151 arpeggio notes, 4-bar loop (8th note pattern)
- Gate times: quantize cleanly to 0.5/1.0/1.5 sixteenth notes

### Blocking Issue
- MIDI ports (Steinberg UR22C) show as empty — cannot do fresh captures or hardware testing
- All work done using existing `sgt_full_capture.json` from Session 17

### Wiki Changes
- Updated [conversion-roadmap.md](conversion-roadmap.md): Pipeline B stages 1-3 marked DONE, new file map
- Updated blocking issue #3 (quantization): marked SOLVED

## [2026-04-15] session-20b | QYFiler.exe disassembly, BLK format, Dump Request confirmed unsupported

### QYFiler.exe Reverse Engineering — CRITICAL FINDING

Disassembled Yamaha QY Data Filer (`exe/extracted/English_Files/QYFiler.exe`, PE32, MSVC 6.0, 1.4MB) and `MidiCtrl.dll` (122KB). Full analysis in [qyfiler-reverse-engineering.md](qyfiler-reverse-engineering.md).

**NO barrel rotation, XOR, encryption, or data scrambling anywhere in the binary.** The 7-bit encoding is the ONLY data transformation. This proves:
- The barrel rotation `R=9*(i+1)` is performed **inside the QY70 hardware**
- .syx/.blk files contain data exactly as the QY70 stores it internally
- The QY70 stores events in rotated form, de-rotates during playback

### Key Technical Details from Disassembly

| Component | VA Address | Details |
|-----------|-----------|---------|
| 7-bit encoder | 0x411D70 | 18 iterations x 7 bytes + 2-byte tail. Shift-and-merge, matches our `yamaha_7bit.py` |
| SysEx builder | 0x411E70 | 158-byte messages, checksum over bytes 4-155 |
| Send protocol | 0x40B44D | 20 tracks, 128-byte blocks, + 654-byte system block at track=0x7F |
| Receive protocol | 0x40E0BF | 512-byte block alignment (shl $9), 200ms inter-block delay, 3000ms timeout |
| BLK file loader | 0x40EA40 | Skip 0x560 bytes, read 0xD0 chunks, validate F0 43 xx 5F |
| Template table | 0x434630 | Init, Close, Identity, Dump Request, ACK templates |

### MidiCtrl.dll Exports

14 functions for MIDI I/O: `_ENTRYinOpen/Start/Stop/Close`, `_ENTRYoutOpen/Close/Write/Dump`, `_ENTRYcomGet/SetDeviceID`, `_ENTRYctrlSelectDevice/GetSysCurInstrument`. Thin wrappers around Windows `midiOutLongMsg`/`midiOutShortMsg`.

### SysEx Template Table (at binary offset 0x34630)

Found complete embedded templates:
- Identity Request/Reply (with wildcard matching)
- Init (`F0 43 10 5F 00 00 00 01 F7`) and Close (`...00 F7`)
- Dump Request per song (`F0 43 20 5F 01 FF 00 F7`), per style (`...02 FF...`), system (`...03 00...`)
- Dump Acknowledgment (`F0 43 30 5F 00 00 00 F7`)
- QY70 Identity: Manufacturer 0x43, Family 0x00 0x41, Member 0x02 0x55

### BLK File Format

New wiki page [blk-format.md](blk-format.md). Key finding: `.blk` = raw concatenated SysEx with no proprietary header. First ~0x560 bytes = handshake/system messages, rest = bulk dump data. QYFiler validates: `F0 43 xx 5F`, byte[6] high nibble = `0x0_` for QY70.

### 7-Bit Round-Trip Validation

All 103 SGT messages decoded then re-encoded:
- 92 messages: 1-byte mismatch at byte 144 (unused low bits of final group header)
- 11 messages: byte-for-byte identical
- All 103: **identical decoded data** — mismatch is cosmetic padding bits

### Dump Request Definitively Unsupported (Hardware Test)

QY70 does NOT respond to remote Dump Request (`F0 43 20 5F AH AM AL F7`) for:
- AM=0x7E (edit buffer), AM=0x00 (user pattern 1), all 16 device numbers
- Manual dump from hardware UTILITY menu is the only method
- Created `incremental_dump.py` with `--manual-dump` mode

### Previous Hardware Dumps Consistent

Feb 26 and Apr 14 header captures differ by only 6/640 bytes — confirms QY70 faithfully reproduces data across separate dumps.

### No Public RE of QY70 Pattern Format Exists

Web search confirmed: no one has documented the internal bitstream encoding of QY70 patterns/styles publicly. This project is the most advanced RE effort. Existing tools:
- QY Data Filer (Yamaha): save/load .blk, no format knowledge
- QY100 Explorer (doffu.net): template .syx files, checksum converter QY70/QY100, no bitstream RE
- Joe Orgren FAQ: confirms patterns are "compressed" but format undocumented

### Wiki/Files Updated
- NEW: [qyfiler-reverse-engineering.md](qyfiler-reverse-engineering.md) — full disassembly analysis
- NEW: [blk-format.md](blk-format.md) — BLK file format
- Updated: [sysex-format.md](sysex-format.md) — template table, Dump Ack type, protocol details
- Updated: [7bit-encoding.md](7bit-encoding.md) — QYFiler encoder confirmation, round-trip validation
- Updated: [decoder-status.md](decoder-status.md) — rotation is hardware-side
- Updated: [open-questions.md](open-questions.md) — Dump Request unsupported, rotation location
- Updated: [index.md](index.md) — added new pages
- Updated: [midi-setup.md](midi-setup.md) — Dump Request limitation

## [2026-04-15] session-20 | Exhaustive rotation analysis on CORRECT file, velocity impossibility

### Correct file identified and analyzed

Previous sessions analyzed wrong/corrupted files. Session 20 re-ran ALL analysis on the correct `tests/fixtures/QY70_SGT.syx` (16,292 bytes, 105 messages — same file used for ground truth capture).

- **Full ground truth extraction**: extracted ALL 680 drum notes from `sgt_full_capture.json` raw MIDI data (not just `first_10`). Pattern: exactly 36 notes per bar at 16 time positions, repeating identically across 19 bars.
- **Data integrity confirmed**: all 105 SysEx checksums valid, 7-bit decode verified correct, track headers byte-identical between known_pattern and SGT.
- **Section duplication CORRECTION**: Session 19 claimed all 6 sections have identical data — this is WRONG. Sections have different byte counts per track.

### ALL rotation models exhaustively disproven

| Approach | Best Result | Verdict |
|----------|------------|---------|
| R=9*(i+1) on SGT RHY1 | 0-1% all tracks | FAIL |
| All multipliers a*(i+c) mod 56 | Best 13% (81 events) | Random chance |
| All header sizes 0-20 + all R offsets | Best 20% on 30 events | Not significant |
| XOR with bar header (5 variants) | Max 7% (6/81) | FAIL |
| XOR with KP⊕SGT header difference | 3-5/81 | FAIL |
| Note-index skip (R by note count) | 5/81 | FAIL |
| Reversed 7-bit bit mapping | Doesn't match parser | Invalid |
| Drum map indices (0-5 vs MIDI notes) | Random chance | FAIL |
| Message boundary reset | No correlation | FAIL |
| Absolute byte offset as R | Random chance | FAIL |

### Velocity encoding impossibility (KEY FINDING)

n42 v32 (16 instances per bar in ground truth) requires vel_code ≥ 12, which means F0 = 426 (bit8=1, bit7=1, lo7=42). **Exhaustive search: ZERO events in SGT RHY1 produce F0=426 at ANY rotation.** This proves the barrel rotation + 9-bit field model is fundamentally incomplete for dense data — it's not just wrong rotation values, but structurally cannot encode the required data.

### Sparse vs dense data structural difference

- **known_pattern events**: SPARSE — many zero bytes (33%), events like `[1e0000000ce024]`, `[00000004a0623c]`
- **SGT events**: ALL DENSE — zero bytes 0-2%, no recognizable patterns

### Scripts created/used
- `timing_constrained_solver.py`, `deep_comparison.py`, `xor_key_test.py`, `no_delimiter_test.py`, `message_boundary_analysis.py` — Session 20 analysis scripts
- `rotation_cracker.py` — exhaustive R search across all events
- `incremental_dump.py` — per-message data extraction tool

### Wiki updated
- `decoder-status.md` — velocity impossibility, corrected section duplication claim
- `open-questions.md` — eliminated hypotheses documented

## [2026-04-15] session-19 | Ground truth validation: ALL decoders FAIL on complex styles

### CRITICAL FINDING: Decoder accuracy ~0% on complex styles

Validated all decoders against `sgt_full_capture.json` (2570 MIDI messages captured from QY70 hardware playback of SGT style):

| Track | Captured | Decoder Precision | Verdict |
|-------|---------|------------------|---------|
| RHY1 (2543 drum) | 680 notes, 6 unique [36,38,42,44,54,68] | 8.9% | FAIL |
| CHD2 (1FA3 chord) | 114 notes, 8 unique [65-77] | 0% | FAIL |
| PHR1 (1FA3 chord) | 151 notes, 8 unique [65-77] | 0% | FAIL |
| BASS (2BE3) | 131 notes, 4 unique [29,31,33,38] | 15.4% | FAIL |
| RHY2 (29CB general) | 170 notes, 1 unique [37] | ~random | FAIL |

### Root cause analysis

- **R=9×(i+1) works ONLY for user-created patterns** (known_pattern: 33% zero bytes, sparse). Factory styles have dense data (0-2% zeros) and the rotation model produces random output.
- **All alternative rotation models tested** (R=7*(i+1), R=11*(i+1), R=constant, R=0, etc.) — ALL at random-chance level.
- **Brute-force R search misleading**: P(random hit) ≈ 93% for drum targets, all "matches" were noise.
- **Section data duplication**: ALL 6 style sections have IDENTICAL track data per slot.
- **Previous confidence metrics were false**: 82-100% accuracy was self-consistency (valid note range), NOT ground truth.

### Strategic pivot: capture-based conversion

Since SysEx decoding fails for complex styles, alternative pipeline bypasses decoder:
```
QY70 Hardware → MIDI Playback Capture → Quantize → Q7P
```
This captures actual notes after all transposition/groove processing.

### Scripts created
- `validate_sgt_capture.py` — ground truth validation framework
- `sgt_deep_diagnosis.py` — exhaustive R-value brute force analysis
- `sgt_raw_hex_analysis.py` — hex dump with delimiter marking, multi-encoding search
- `sgt_section0_focused.py` — local vs global R comparison, capture timing
- `sgt_message_structure.py` — SysEx message structure, section duplication discovery
- `sgt_no_delimiters_test.py` — tests 0x9E/0xDC as data bytes hypothesis (rejected)

### Wiki updated
- `decoder-status.md` — downgraded factory style confidence, added ground truth results
- `conversion-roadmap.md` — added Pipeline B (capture-based), reorganized priorities
- `open-questions.md` — added factory encoding as top priority

## [2026-04-15] session-18 | PATT OUT 1~8 test, Q7P sequence events breakthrough

### PATT OUT CH = 1~8 Test
- **PATT OUT 1~8 produces ZERO output** when ECHO BACK = Thru. With Thru enabled, the MIDI OUT port passes through incoming data and the QY70 suppresses PATT OUT note data.
- Clock pass-through works (187/192 expected clocks echoed back), confirming QY70 receives external clock and is running.
- Tested with both known_pattern.syx (19 msgs) and QY70_SGT.syx (105 msgs) — both loaded successfully but zero notes captured on any channel.
- **Solution**: PATT OUT must be **9~16** with **ECHO BACK = Off** (the Session 17 configuration).

### Chord Transposition Analysis
- Decoded CHD1 (29DC encoding) from known_pattern.syx: 3 bars, 11 events. Bar header 9-bit fields do NOT contain [60,64,67] directly.
- CHD2 and PHR1 (1FA3 chord encoding) have **identical data** in known_pattern — same headers, same events.
- Bar header analysis across CHD2 bars 1-5: field 1 (=53) and field 5 (=484) are CONSTANT, fields 2-4 change per bar. These don't form recognizable chords as MIDI notes.
- **Hypothesis**: Bar headers encode chord-RELATIVE templates (voicing patterns), not absolute notes. The QY70 applies real-time substitution based on the user's chord input.
- Created `capture_chord_test.py` for systematic multi-chord comparison (CM, Dm, G7, etc.) when PATT OUT is fixed.

### Q7P 3072-byte Sequence Events — BREAKTHROUGH
- **Actual musical data is at 0x678-0x870** (Sequence Events area), NOT at 0x360-0x677 (Phrase Data).
- 5120-byte D0/E0 command format does NOT apply to 3072-byte files.
- Structure decoded: config header (48B) → 3 velocity LUT blocks (32+64+64 bytes of 0x64=vel100) → event data (128B) → track flags
- Event data = 16 × 8-byte groups: Groups 0-7 = sequence pattern, Groups 8-15 = note table
- Command bytes: `0x83` = note group, `0x84` = timing, `0x88` = section end (distinct from 5120-byte D0/E0)
- Note table (G8-15): 8 instrument slots with per-beat note variants. Primary note repeated with 1-3 alternates per slot.
- Sequence area (G0-7): 7 core drum notes (BD2, SideStk, Snare1, Snare2, HHclose, HHpedal, HHopen)
- Note table has 20 unique notes incl. rides, congas, maracas, shaker — used for fills/variations
- T01.Q7P vs TXX.Q7P: **identical** in phrase data + sequence events. Differ only in section pointers (T01=1 section, TXX=4 sections)
- Created `q7p_sequence_analyzer.py` for structural analysis

### BASS Decoder
- BASS with 2BE3 (SGT): 12 events, confidence 0.25, chaotic field values
- BASS with 29CB (known_pattern): 20 events, confidence 0.31, consistent F4 masks but selected notes in wrong range
- Both encodings remain poorly understood (38% confidence)

### Scripts
- `capture_chord_test.py`: NEW — systematic chord transposition test
- `q7p_sequence_analyzer.py`: NEW — Q7P sequence events structural analysis
- Updated channel maps in `capture_playback.py` and `send_and_capture.py` for both 1~8 and 9~16 PATT OUT

## [2026-04-14] session-17 | End-to-end playback capture, chord transposition discovered

### Bulk Dump Protocol
- **Timing SOLVED**: Init needs **500ms**, bulk messages need **150ms** between each. Wrong timing → QY70 silently ignores everything.
- **All bulk dumps write to AM=0x7E (edit buffer)**: Writing to AM=0x00 (User Pattern 1) is rejected. Edit buffer data IS playable in Pattern mode.
- **Load confirmation**: QY70 responds with ~160 messages (XG params, CCs, Program Changes) on first load. Subsequent loads to same buffer get fewer responses.
- `send_style.py` defaults updated: init_delay 100→500ms, delay 30→150ms.

### Playback Discovery
- **MIDI SYNC must be External**: Without external MIDI Clock, QY70 produces ZERO notes on PATT OUT despite receiving MIDI Start. With external clock (Start + 24ppqn), chord tracks output correctly.
- **Chord playback CAPTURED**: known_pattern CHD1 → ch13: C major [60,64,67], vel=127, ~1070 tick duration, every 5 bars. Same pattern confirmed with SGT and claude_test styles.
- **Drum tracks DO NOT output** via PATT OUT in Pattern mode. All 3 test patterns (known_pattern, claude_test, SGT) show only CHD1 on ch13. No notes on ch9-12 or ch14-16.

### Chord Transposition Discovery
- **Playback notes ≠ decoded bitstream notes**: QY70 outputs [60,64,67] (C major) but decoder extracts [F3, A4, E7, etc.] from the bar headers. The QY70 applies **real-time chord transposition** — the bitstream stores chord-relative patterns, not absolute MIDI notes.
- **CHD1 uses 29DC encoding** in known_pattern (not 1FA3). CHD2/PHR1 have 1FA3 encoding but produce zero output on ch14/ch15.

### Scripts
- `send_style.py`: timing defaults fixed
- `capture_playback.py`: rewritten to use rtmidi (was mido)
- `send_and_capture.py`: NEW — combined send + clock + capture workflow
- Saved: `known_pattern_playback.json` — first chord capture ground truth

## [2026-04-14] session-16 | mido SysEx bug found, rtmidi fix, Identity Reply confirmed

- **ROOT CAUSE FOUND: mido drops SysEx on macOS CoreMIDI**. `sysex_diag.py` loopback test: rtmidi direct sends SysEx correctly (QY70 echoes all messages AND responds to Identity Request), mido sends **nothing** (zero SysEx received on MIDI IN for all message types). Notes work via both methods. The bug is in mido's SysEx serialization on CoreMIDI backend.
- **Identity Request WORKS** (contradicts Session 12f): QY70 responds with `F0 7E 7F 06 02 43 00 41 02 55 00 00 00 01 F7` (Yamaha, Family 0x4100=XG, Model 0x5502). Previous test used mido which silently dropped the SysEx.
- **send_style.py rewritten to use rtmidi directly**: all SysEx now sent via `rtmidi.MidiOut.send_message()` instead of `mido.Message("sysex")`. SGT fixture (105 msgs) and claude_test.syx (17 msgs) both transmitted successfully.
- **Bulk Dump Request limited**: QY70 echoes dump requests on MIDI OUT but only responds to AM=0x00 (User Pattern 1) with `F0 F7` (empty pattern). Other addresses (AM=0x7E, 0x7F, Setup, Song) are echoed without response. Likely requires Pattern mode Standby.
- **List Book analysis complete** (pp.51-64): Sequencer RECEIVE FLOW confirms format `F0 43 00 5F BH BL AH AM AL [data] CS F7`. Table 1-9 SEQUENCER PARAMETER ADDRESS maps all valid addresses. BC=147 confirmed in spec ("data size is fixed at 147 bytes").
- Created: `sysex_diag.py` (loopback SysEx tester), `request_dump.py` (bulk dump requester via rtmidi)
- Updated: `send_style.py` (rtmidi direct), `midi-setup.md`, `open-questions.md`

## [2026-04-14] session-15 | SysEx BC formula discovery, bulk dump transmission

- **SysEx BC formula CORRECTED**: `BC = len(encoded_data)` = 147, NOT `3 + len(encoded)`. Verified against 3 independent QY70 captures (126/126 checksums match). The wrong formula (`bc = 3 + len(encoded)`) in `build_ground_truth_syx.py` caused wrong BH/BL → wrong checksum → QY70 silently discards all messages.
- **Fixed message format**: All QY70 bulk dump messages MUST be exactly 158 bytes (128 decoded → 147 encoded → 158 total). Decoded blocks must be zero-padded to 128 bytes.
- **Fixed builders**: `build_ground_truth_syx.py` corrected. `create_custom_style.py` and `writer.py` already had the correct formula.
- **Corrupted capture detected**: `ground_truth_style.syx` has 2 messages with dropped bytes (140B and 29B instead of 147B). `user_style_live.syx` clean (17/17).
- **Bulk dump transmission investigation**: QY70 receives notes but ignores SysEx bulk dumps from computer via UR22C. Testing: mido, rtmidi direct, alternative ports, different delays, GM/XG parameter SysEx, original captures. Investigation ongoing.
- **Wiki updated**: bitstream.md SysEx format section, checksum.py documentation.

## [2026-04-14] session-14 | R=9×(i+1) PROVEN, per-segment index, new preambles

- **R=9×(i+1) DEFINITIVELY PROVEN**: known_pattern.syx ground truth test — 7/7 events match perfectly on ALL 4 fields (note, velocity, tick, gate). No other rotation model achieves this. This is the definitive proof for 2543 drum encoding rotation.
- **Event index is PER-SEGMENT**: resets to 0 at each DC delimiter. Global index gives 1/36 expected hits vs 6/36 for per-segment. Confirmed on both known_pattern (single segment) and USER-RHY1 (multi-segment).
- **Multi-segment control event interference**: control events at odd positions within segments disrupt cumulative index. Position-specific R {e0:9, e1:22, e2:12, e3:53} gives 100% on USER-RHY1 bars 3-4, but no linear formula exists and SGT-RHY1 needs completely different R values.
- **2D2B/303B = chord encoding variants of 1FA3**: USER style has 0x2D2B (CHD1) and 0x303B (CHD2/PAD/PHR1/PHR2). Deep analysis proved these use IDENTICAL encoding to 1FA3: F4 chord-tone masks `[11101,11101,11101,01101]` and F5 timing `[172,180,188,186]` match exactly between USER-CHD1(2D2B) and SGT-CHD2(1FA3). Preamble value is track-level metadata, not encoding type selector.
- **Extended preamble identified**: first 14 bytes of event_data (before first DC delimiter) are identical between USER and SGT styles — this is extended preamble metadata, not a real bar segment.
- **Playback capture improved**: created capture_playback_json.py (proper JSON with channel mapping, velocity stats). Previous capture_diag.py only printed to terminal.
- **event_decoder.py updated**: removed R=9 constant fallback, added mod 56 to cumulative R, reordered decoder priority chain. Control event detection now uses cumulative R.
- **Model G cascade decoder**: std→skip-ctrl→R=47 achieves 96% USER-RHY1, 94% SGT-RHY1 (vs 84%/85% baseline). After ctrl events, skip-ctrl R correctly decodes Crash1(49), Ride1(51) where std gives garbage.
- **event_decoder.py updated**: decode_drum_event() now accepts note_index parameter for Model G cascade. classify_encoding() recognizes 2D2B/303B as chord encoding.
- Created: analyze_known_pattern.py, analyze_rhy1_*.py (6 scripts), analyze_sgt_rhy1_crossbar.py, validate_rhy1_decoder.py, capture_playback_json.py, analyze_new_preambles.py, analyze_new_preambles_deep.py, analyze_ctrl_skip_index.py, analyze_ctrl_skip_combined.py
- Updated: event_decoder.py, 2543-encoding.md, decoder-status.md, open-questions.md, bitstream.md, log.md

## [2026-04-14] session-13 | First live playback capture, PATT OUT CH

- **PATT OUT CH discovery** (Owner's Manual p.224): UTILITY → MIDI parameter, default Off. Set to "9~16" for D1=ch9..C4=ch16
- **First successful playback capture**: 330 note events on 4 channels (ch9=D1, ch12=BA, ch13=C1, ch14=C2)
- **Track mapping confirmed**: RHY1→D1(ch9), BASS→BA(ch12), CHD1→C1(ch13), CHD2→C2(ch14)
- **External sync works**: MIDI SYNC=External + Start+Clock from computer drives QY70 playback at 120 BPM
- **Captured chord progression**: G→C→Em→D (4 bars, 8s loop). CHD1 plays voice-led triads, BASS plays root, CHD2 plays single-note phrase
- **Drum pattern**: 8-beat (HH42 on every 8th, Kick36 on beats 1/5, Snare38 on beats 3/7). Velocities vary (groove template): HH=112-122, Kick=111-127, Snare=115-123
- **Groove quantization confirmed**: velocity variation in drums matches QY70's groove template feature
- **Silent tracks**: ch10(D2/RHY2), ch11(PC/PAD), ch15(C3/PHR1), ch16(C4/PHR2) — not present in this style
- Created: capture_diag.py (comprehensive MIDI diagnostic), capture_and_save.py (JSON capture)
- Updated: qy70-device.md, midi-setup.md, open-questions.md, log.md

## [2026-04-14] session-12g | PATT OUT CH discovery, wiki audit

- **PATT OUT CH found** (Owner's Manual p.224): UTILITY → MIDI → PATT OUT CH controls style/pattern MIDI output. Default is "Off" (no output). Set to "9~16" to transmit D1=ch9, D2=ch10, PC=ch11, BA=ch12, C1-C4=ch13-16
- **QY70 does NOT use INT/EXT/BOTH**: unlike other Yamaha synths, QY70 has a single PATT OUT parameter (Off/1~8/9~16)
- **MIDI CONTROL parameter**: Off/In/Out/In/Out — must be set to "In" or "In/Out" to accept MIDI Start/Stop from computer
- **Identity Request confirmed NOT supported**: QY70 ignores Universal Identity Request. MIDI bidirectional works (notes, SysEx), just not Identity.
- **Wiki audit completed**: fixed midi-setup.md (added bidirectional validation, PATT OUT setup), qy70-device.md (added MIDI output section, Identity limitation), open-questions.md (marked off-by-one resolved, updated dump request status)
- Updated: qy70-device.md, midi-setup.md, open-questions.md, log.md

## [2026-04-14] session-12f | Unified decoder, 96% global accuracy

- **Unified decoder `decode_drum_event()`**: single decoder for ALL encoding types (2543, 29CB, 29DC, 294B, 1FA3) using priority chain: cumulative R=9×(i+1) → R=9 fallback → ctrl detection → R=47 fallback
- **96% global note accuracy**: 143/149 note events across all 7 tracks. 5 tracks at 100% (RHY2, CHD1, CHD2, PHR1, PAD nearly)
- **Correct control event detection**: lo7 > 87 at R=9 (not F0=0x078 as previously documented — F0 is actually 0x1E0=480)
- **Control events are sub-sequence terminators**: 11/16 are last in segment, ALL at odd positions, F5 encodes type (0x120=intermediate, 0x06C=final, 0x036=BASS-specific)
- **ALL control events end with byte 0x78**: universal marker across all tracks/encodings
- **Trailing bytes analysis**: d878 = last 2 bytes of most common ctrl event; CHD2/PHR1 share identical trails; BASS has zero-padding
- **MIDI connectivity**: QY70 bidirectional confirmed (heard kick sent from computer), but dump request not supported, style playback output blocked by INT track mode
- **known_pattern.syx**: built and sent to QY70, 7 events with 100% round-trip verification
- Updated: decoder-status.md, 2543-encoding.md, event_decoder.py

## [2026-04-14] session-12e | Event type classification, cross-encoding analysis

- **Event types discovered**: 3 types — Note (85%), Control (15%, F0=0x078 at R=9), Null (BASS only, F0=0x000)
- **Control events are structural markers**: byte-identical patterns appear across RHY1 AND PAD tracks. Pattern `280f8d83b0d878` in 4 locations, `3486f2e3e24078` in 2 locations.
- **True accuracy 94%**: mixed model (cumulative + constant R=9 fallback) gives 49/52 valid on NOTE events only. Only 3 note events (~6%) remain unexplained.
- **1FA3 has 0% control events**: chord encoding is purely note-based. 29CB has 11%, 2BE3 has 15% control + 20% null.
- **6-byte header hypothesis REJECTED**: 41% valid vs 85% for 13-byte header. Header bytes 6-12 decode to note=105 (invalid) at R=0 for most segments.
- **R=9×(i+1) confirmed for 1FA3**: 95% valid for CHD2/PHR1 vs 70% with R=9×i (event_decoder.py formula is off-by-one!)
- **Trailing bytes are cross-encoding**: BASS, CHD2, PHR1 share identical trail patterns [1,0,2,0,0,2] and segment sizes [28,41,29,41,41,43]. Format-level feature, not encoding-specific.
- **CHD2 and PHR1 share identical event data**: same raw bytes at same positions, confirming style copies data across tracks
- **Global cumulative index doesn't work**: per-segment index reset confirmed (global gives much worse results)
- Created 4 new analysis scripts: 6byte_header, continuous_stream, failing_events, cross_encoding_failures, event_types

## [2026-04-14] session-12d | 2543 cumulative rotation hypothesis, segment alignment

- **Cumulative rotation R=9×(i+1) gives 77% valid notes** vs 66% for constant R=9 — original "constant rotation proof" was inconclusive (all identical events at e0 position)
- **Segment misalignment discovered**: 50% of segments have (length-13)%7 ≠ 0, with 1-3 trailing bytes before delimiter. Pattern `d878` appears twice.
- **XG drum note range confirmed**: Standard Kit maps notes 13-87 only. Notes 82-87: Shaker, JnglBell, BellTree, Castanets, MuSurdo, OpSurdo. Notes >87 are NOT valid drum sounds.
- **Pattern mode padding**: AL=127 track filled with empty marker `BF DF EF F7 FB FD FE` repeated, confirming padding pattern
- **14 remaining invalid events**: mostly at higher event indices (e4+) where cumulative R exceeds 56 and wraps around. May be non-note events or rotation artifacts.
- Created 5 analysis scripts: anomalies, alignment, event_types, rotation_model, r_sweep_cumulative
- Updated wiki: 2543-encoding.md (rotation model, segment alignment, XG range), decoder-status.md, open-questions.md, bitstream.md

## [2026-04-14] session-12c | 2543 drum encoding decoded, Dump Request corrected

- **2543 uses CONSTANT rotation** (not cumulative like 1FA3): proven by 9 byte-identical events at different positions all decoding identically at R=9
- **F0 = note number** (lo7 = MIDI note): Kick1=36, HHpedal=44, HHopen=46, Ride=51, Crash=57 confirmed from repeated events
- **F1-F4 = position encoding**: simultaneous events share identical F1-F4 (e.g., Kick+HH at beat 1 all have F1=60,F2=82,F3=58,F4=108)
- **F5 = gate time in ticks**: physically reasonable (Kick=412≈332ms, HH=30≈24ms at 155BPM)
- **F0 bits 7-8 = flags**: possibly velocity level (2-bit), not yet confirmed
- **Dump Request IS supported**: List Book section 3-6-3-4, `F0 43 20 5F AH AM AL F7`, AM=00-3F for individual patterns. Previous test used wrong address AM=7E (edit buffer)
- **Pattern mode ALL tracks use 2543**: not just drums — chord tracks (C1-C4) also use this encoding in Pattern mode
- Created wiki page [2543-encoding.md](wiki/2543-encoding.md), updated 6 existing pages
- Joint R optimization: R=34 best for combined drum+beat (35.5%), but R=9 gives best drum note identification (61%) — 2543 doesn't use one-hot beat counter like 1FA3
- **Velocity SOLVED**: 4-bit inverted code `[F0_bit8:F0_bit7:rem]`, 0=fff(127), 15=pppp(7). Same note at different velocities confirmed (MuTriang v2/v8, OpTriang v12-v15)
- **Beat number extracted**: F1 top 2 bits = beat (0-3). Tick 240 = primary beat position in 6/10 segments
- Clock encoding: `((F1 & 0x7F) << 2) | (F2 >> 7)` gives 9-bit clock, 59% monotonicity within segments

## [2026-04-14] wiki-create | Initial wiki from 12 sessions of knowledge

Created wiki from accumulated knowledge across docs/, midi_tools/, and session notes.
Major sources: QY70_FORMAT.md (41K), QY700_FORMAT.md (18K), SESSION_RECAP.md, event_decoder.py.

## [2026-04-14] session-12b | List Book MIDI Data Format analysis

- Analyzed full QY70E2.PDF (QY70 List Book, 64 pages)
- **Table 1-9**: Sequencer addresses — patterns at AH=02, AM=00-3F, songs at AH=01
- **Bulk Dump Request supported**: substatus=0x20 (F0 43 20 5F AH AM AL F7)
- **AM=0x7E = edit buffer** in dump DATA messages (not a pattern slot number)
- **Section Control**: F0 43 7E 00 ss dd F7 — can switch sections via MIDI
- Captured C major pattern on C1 track (AL=0x04) — preamble is 2543 (not 1FA3!)
- Pattern mode uses different preamble encoding than Style mode
- 99 Chord Templates, 100 Groove Templates, 128 Preset Styles documented

## [2026-04-14] session-12 | Delimiters, beat counter fix, R equivalence

- Discovered 0x9E sub-bar delimiter (chord changes within a bar)
- Fixed lo4=0 → beat 0 (was treated as invalid)
- Proved R=9 right-rotate = R=47 left-rotate (same operation on 56 bits)
- Chord confidence: 68% → 82%, beat accuracy: 48% → 90%
- Online search for .syx files: no free downloads found

## [2026-02-26] session-11 | Bricking diagnosis and safety fixes

- Identified bricking cause: voice writes to unconfirmed offsets 0x1E6/0x1F6/0x206
- Disabled _extract_and_apply_voices(), fixed pan bounds check
- Added post-conversion validation

## [2026-02-20] sessions-6-10 | Bitstream reverse engineering

- Discovered R=9 barrel rotation and 9-bit field structure
- Decoded F3 (beat counter), F4 (chord mask), F5 (timing)
- Confirmed preamble-based encoding: 1FA3=chord, 29CB=general, 2BE3=bass, 2543=drum
- Built event_decoder.py (900+ lines)

## [2026-02-10] sessions-3-5 | Core library bug fixes

- Fixed 16 bugs in core library (channel mapping, pan display, time sig, AL schema, checksum, etc.)
- Added voice transfer to both converters
- Created NEONGROOVE.syx custom style
- Documented QY70 empty-marker pattern BF DF EF F7 FB FD FE

## [2026-02-01] sessions-1-2 | Infrastructure and MIDI setup

- Established MIDI connection via Steinberg UR22C
- Captured first bulk dump from QY70 (808 bytes, 7 SysEx messages)
- Created 20+ analysis scripts in midi_tools/
