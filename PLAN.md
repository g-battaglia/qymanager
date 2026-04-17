# PLAN.md — Piano integrale QYConv: Converter perfetto + Editor completo QY70/QY700

> **Documento di pianificazione master** per il prossimo stadio del progetto. Definisce obiettivi, architettura, milestones e dettagli tecnici per trasformare QYConv da tool di conversione parziale + editor CLI minimale in **suite completa di controllo programmatico** dei due sequencer Yamaha QY70 e QY700.
>
> **Non è una roadmap vincolante ma un master-plan di lavoro**. Dettagli operativi vengono raffinati ad ogni sessione. Aggiornare `STATUS.md` a ogni milestone superato.
>
> **Versione**: 1.0 — 2026-04-17
> **Autore**: Session 30j planning
> **Dipendenze lette**: `STATUS.md`, `wiki/*` (20+ pagine), `CLAUDE.md`, sessioni log 1-30i

---

## Sommario

1. [Contesto del progetto](#1-contesto-del-progetto)
2. [Cosa sappiamo oggi (dopo 30 sessioni)](#2-cosa-sappiamo-oggi)
3. [Obiettivi e decisioni confermate](#3-obiettivi-e-decisioni-confermate)
4. [Architettura proposta: Unified Data Model](#4-architettura-proposta-unified-data-model-udm)
5. [Pilastri di lavoro](#5-pilastri-di-lavoro)
6. [Reverse engineering residuo](#6-reverse-engineering-residuo)
7. [Timeline e milestone](#7-timeline-e-milestone)
8. [Test strategy](#8-test-strategy)
9. [Rischi e mitigazioni](#9-rischi-e-mitigazioni)
10. [File e struttura progetto](#10-file-e-struttura-progetto)
11. [Appendici tecniche](#11-appendici-tecniche)

---

## 1. Contesto del progetto

### 1.1 I due strumenti

**Yamaha QY70** (1997) — sequencer portatile "music workstation tascabile":
- Tone generator XG compliant (Model ID SysEx `0x4C`)
- Sequencer proprietario (Model ID SysEx `0x5F`)
- **519 voci XG Normal** + 20 Drum Kit
- **Sezioni pattern**: 6 (Main A-D + Fill AA + Fill BB)
- **8 tracce per sezione** (drum + bass + chord1 + chord2 + phrase1 + phrase2 + rhythm1 + rhythm2)
- **4167 preset phrases** organizzate in 12 categorie + **384 user phrase slots**
- **20 song slots** × 8 tracce
- **100 Groove Templates** (preset, TIMING 0-200, VELOC 0-200 per step 16esimo)
- **Fingered Zone** per chord detection live
- I/O: MIDI IN/OUT/THRU, no floppy, backup solo via MIDI bulk dump
- Effetti: **Reverb + Chorus** (no Variation)
- Display LCD 2 righe × 20 caratteri, navigazione F-key (F1-F5)

**Yamaha QY700** (1997) — sequencer da tavolo "music workstation":
- Stesso tone generator XG core, ma con **Dynamic Voice Allocation** (32 parti vs 16 del QY70)
- Sequencer proprietario (Model ID SysEx `0x4D`? da confermare — bulk dump usa XG standard)
- **491 voci XG Normal** + 11 Drum Kit (set leggermente ridotto vs QY70)
- **Sezioni pattern**: 8 (Main A-D + Fill AA/BB/CC/DD)
- **16 tracce per sezione**
- **3876 preset phrases** + **256 user slots**
- **20 song slots** × 35 tracce (1-16 = seq, 17-32 = seq2, chord, tempo, scene, pattern, control, beat, click, meta...)
- Stessi 100 Groove Templates preset
- I/O: MIDI IN/OUT/THRU, **floppy disk drive** (720 KB MF2DD, formati `.Q7P .Q7S .Q7A .ESQ .MID`)
- Effetti: **Reverb + Chorus + Variation** (Variation è 43 parametri in più)
- Display grafico 240×64 LCD, jog-wheel, 16 buttons, 16 LED
- Pattern Chain come track dedicato in Song mode (QY70 non ce l'ha)

### 1.2 Il progetto QYConv

**Obiettivo dichiarato da sempre** (dal primo commit):
1. Convertire bidirezionalmente QY70 ↔ QY700 preservando contenuto musicale.
2. Permettere editing programmatico di entrambi i device.
3. Funzionare nativamente su macOS/Linux senza Wine/VM (il Data Filer Yamaha è Windows only).

**Perché è difficile**:
- I formati `.syx` del QY70 usano bitstream **proprietario** con rotazione barrel R=9 (hardware-internal, confermato Session 23 RE di QYFiler)
- I formati `.q7p` del QY700 sono **parzialmente documentati** dal manuale ma con blob binari opachi per phrase/events
- Nessuna documentazione ufficiale pubblica: tutto è reverse engineering
- Il firmware non è pubblicamente disponibile
- Hardware rarissimo (QY70 1997, QY700 1997 — entrambi discontinued, eBay-only)

### 1.3 Stato dell'arte al 2026-04-17

**30+ sessioni di lavoro** hanno prodotto:
- **Conversione Pipeline B** (capture-based) production-ready per QY70 → QY700
- **Conversione Pipeline A** (SysEx decode) bloccata al 10% per limiti RE su dense encoding factory styles
- **Metadata converter** funzionante (tempo, nome, volume, pan, chorus, reverb)
- **Editor CLI prototipo** con 21 sub-command (note, tempo, diff, merge)
- **Q7P reader + writer + validator** completi con invariant phrase-stream
- **Hardware I/O completo** (init handshake, bulk dump, send, capture, restore)
- **20+ pagine wiki** + **164 test** verdi + **RE integrale Data Filer Windows** (disassembly)
- Menu tree completo QY70 (803 righe, ~280 parametri) e QY700 (760 righe, ~240 parametri)
- **Bricking risolto**: voice offsets ignoti disabilitati, causa diagnosticata (scrittura a 0x1E6/0x1F6/0x206)

**Cosa manca ancora** (gap tra stato attuale e obiettivo integrale):
- Editor NON copre: System, Multi Part, Drum Setup, Effect, Song, Chord track, Groove template, Phrase library
- Converter genera `.q7p` solo da capture; genera `.syx` QY70 da `.q7p` con bitstream rotto (QY70 interpreta come "svuota edit buffer")
- Dense encoding irrisolto → factory styles QY70 non decodificabili senza hardware capture
- Formato `.q7a` (backup totale QY700) non implementato
- Phrase library mapping 4167 ↔ 3876 inesistente
- Editor realtime via XG Parameter Change: parser+emit esistono, CLI non integrata
- Voice offsets Q7P per Bank/Program reali non confermati (0x1E6 sospetti, brick risk)

---

## 2. Cosa sappiamo oggi

### 2.1 Protocolli confermati

**MIDI SysEx QY70**:
- **Init handshake obbligatorio**: `F0 43 10 5F 00 00 00 01 F7` prima di qualunque dump request
- **Dump request**: `F0 43 20 5F 02 AM AL F7` con AM=tipo dato, AL=slot
- **Close**: `F0 43 10 5F 00 00 00 00 F7` a fine
- **Device ID**: 0 (fisso, non configurabile su questo esemplare)
- **Model SysEx** per sequencer: `0x5F`
- **Model XG**: `0x4C` (parameter change real-time)
- **AM=0x7E**: solo edit buffer pattern; slot User rifiutato → serve STORE manuale
- **Timing**: inter-SysEx gap minimo ~150ms, post-init 500ms

**MIDI SysEx QY700**:
- Non richiede init handshake (standard XG)
- Dump request XG standard
- Device ID configurabile (UTILITY menu)
- Accetta bulk diretto su slot (no STORE manuale richiesto per Q7P)
- Interval Time 3-5ms in UTILITY F4 previene "MIDI Buffer Full" su bulk grossi

**XG Parameter Change** (entrambi i device):
- Formato: `F0 43 1n 4C [AH] [AM] [AL] [data...] F7` dove n = device ID 0-15
- Blocchi principali:
  - `AH=0x00` System (master tune, volume, transpose, XG on, all reset)
  - `AH=0x08` Multi Part per-part setup (voice bank/prog, volume, pan, effect sends)
  - `AH=0x02` Effect (Reverb, Chorus, Variation)
  - `AH=0x30+` Drum Setup per-note
- **Persistenza**:
  - XG Param Change esterno = RUNTIME (non salvato nel pattern)
  - XG events inseriti via Event Edit QY70 = SALVATI nel pattern
  - Bulk dump Model 5F NON contiene XG params (verificato Session 30e)

### 2.2 Formati file

| Estensione | Device | Stato parser | Stato writer | Note |
|------------|--------|--------------|--------------|------|
| `.syx` sparse | QY70 | ✓ OK | ✓ OK | User patterns, R=9×(i+1), 100% on 7/7 |
| `.syx` dense | QY70 | ✗ broken | ✗ broken | Factory styles, bitstream irrisolto |
| `.blk` | QY70 | ✓ wrapper | ✓ wrapper | = raw SysEx stream multi-message |
| `.q7p` | QY700 | ✓ OK | ✓ OK | 3072/5120/6144 byte, phrase blob opaco |
| `.q7s` | QY700 | ✗ | ✗ | Song format, mai RE |
| `.q7a` | QY700 | ✗ | ✗ | All-data backup, mai RE |
| `.esq` | QY700 | ✗ | ✗ | Sequence format, mai RE |
| `.mid` (SMF) | both | output-only | ✓ (mido) | Conversione input mancante |

### 2.3 Encoding bitstream QY70 (stato RE)

**Sparse (user pattern)** — **proven**:
- Rotazione barrel R=9×(i+1) dove i = indice evento
- Field layout: F0=note, F1-F3=timing/velocity, F5=gate, F4=chord-tone mask
- Validato su 7/7 pattern (100% roundtrip byte-identical)

**Dense (factory style)** — **blocked**:
- 42B super-cycle identificato in SGT (Session 29e)
- 692B shared prefix cross-track SGT (Session 29e)
- Per-beat rotation variabile R=0/2/1/0 (Session 29c)
- 44/56 bit constant per pattern ID beat 2
- **Structural impossibility** provata su velocity encoding Session 20: non esiste field layout lineare che possa rappresentare le 790 note MIDI osservate in Summer
- Ipotesi residue: reference-based (phrase ID + delta), pattern reuse cross-section, firmware-dependent lookup table

**Decodifica per encoding type**:
- `2543` (drum/pattern) — R=9×(i+1) proven, F0=note, F5=gate
- `2BE3` (bass) — parziale
- `29CB` (general) — parziale
- `303B`, `2D2B` (preambles) — RE-mapped Session 22

### 2.4 Q7P binary layout (confidence alta)

| Offset | Campo | Note |
|--------|-------|------|
| 0x000-0x00F | Magic + size | Header fisso |
| 0x010-0x0FF | Reserved | TBD |
| 0x100-0x11F | Section pointers | Critici, brick se corrotti |
| 0x188-0x189 | Tempo | 2 byte BE |
| 0x1E6 / 0x1F6 / 0x206 | **Voice?** | **BRICK RISK**, mai confermati |
| 0x226 | Volume | Offset sospetto |
| 0x276 | Pan | Offset sospetto |
| 0x246 | Chorus table | Parziale |
| 0x360-0x677 | Phrase blob | Opaco, 12 phrase × ~66 byte |
| 0x876-0x87F | Nome pattern | 10 byte ASCII |
| 0x9C0-0xB0F | Fill area | Critico |
| 0xB10-0xBFF | Pad area | Critico |
| 0xC00+ | Phrase data | Bitstream phrase |

### 2.5 Tool esistenti

**CLI principale** (`qymanager`):
- `convert` — QY70 ↔ QY700 metadata only
- `edit` — 21 sub-command editor pattern
- `xg` — parse/summary/diff XG bulk/stream
- `validate` — Q7P invariants

**Standalone tool** (`midi_tools/`):
- `capture_playback.py`, `capture_dump.py`, `capture_xg_stream.py`
- `request_dump.py`, `restore_pattern.py`, `send_style.py`
- `pattern_editor.py` (=`qymanager edit`)
- `syx_edit.py` — byte-level tempo editor (bypass bitstream encoder rotto)
- `xg_param.py` — parse + emit XG Parameter Change (emit non in CLI)

**Utilità Python**:
- `qymanager/formats/qy70/` — syx parser (sparse)
- `qymanager/formats/qy700/q7p_reader.py` + `q7p_writer.py`
- `qymanager/formats/seven_bit_codec.py` — 7-bit pack/unpack
- `qymanager/converters/qy70_to_qy700.py` — metadata converter
- `qymanager/converters/qy700_to_qy70.py` — stub con SysEx init/close corretto

---

## 3. Obiettivi e decisioni confermate

### 3.1 Obiettivi macro (utente, verbatim)

> "Creare un convertitore perfetto, che può adeguare quello che serve chiaramente date le differenze di numero di tracce ecc, tra qy70 ↔ qy700."
>
> "Creare degli editor completi ed integrali per entrambi i tool che permettono di modificare TUTTI i parametri sia di un dump sysex o q7p sia via comandi midi da inviare."
>
> "Dobbiamo costruire un set di tool per poter avere pieno controllo programmatico di questi strumenti."
>
> "Il piano deve essere ampio e completo ed integrale, dobbiamo lavorare tantissimo per scoprire tutto."

### 3.2 Decisioni di scope (risposte al questionnaire 2026-04-17)

| # | Area | Scelta | Rationale |
|---|------|--------|-----------|
| 1 | **Approccio** | Unified Data Model first, poi tutto sopra | Robustezza: evita rework quando converter ed editor lavorano sullo stesso modello |
| 2 | **Scope editor** | Tutto XG + menu tree + dense bitstream | Massima ambizione. Dense bitstream resta RE long-term in background |
| 3 | **Dense encoding** | RE parallelo low-priority (1 su 5 sessioni) | Non blocca progresso. Se irrisolto dopo 30 sessioni totali → pivot permanente a Pipeline B |
| 4 | **Interfaccia finale** | CLI + libreria ora, TUI + GUI dopo consolidamento | Stepped release: MS4 = CLI completa, TUI+GUI sono milestone successivi |
| 5 | **Device priority** | QY70 prima (RE più noto) | Progresso rapido iniziale, QY700 eredita UDM già consolidato |
| 6 | **Hardware** | Sempre disponibile | Abilita hardware-in-the-loop test continui + "yolo" su QY700 secondario |
| 7 | **Lossy policy** | `--keep` / `--drop` flag granulari | Utente sceglie cosa perdere, report dettagliato `.warnings.json` |
| 8 | **Phrase library** | RE integrale 4167 ↔ 3876 con tabella deterministica | No approssimazione; investimento 2-4 sessioni dedicate |
| 9 | **Formati legacy** | Q7P + Q7A (no Q7S/ESQ per ora) | Q7A per backup totale è utile; Q7S/ESQ on-demand |
| 10 | **Target** | Privato ora, open-source dopo MS4 | Zero overhead CI/packaging fino a stabilità |
| 11 | **Realtime vs offline** | Simultanei, stesso comando + `--realtime` | Unified API, zero duplicazione |
| 12 | **Safety hardware** | Full yolo su QY700 secondario | RE aggressivo su voice offsets, brick recoverable via factory reset |

### 3.3 Criterio di "integrale"

Il progetto si considera **integrale** quando:

- [ ] Ogni parametro documentato in `wiki/xg-parameters.md`, `wiki/qy70-menu-tree.md`, `wiki/qy700-menu-tree.md` è **editabile via CLI**
- [ ] Ogni parametro XG è **emettibile via realtime Parameter Change**
- [ ] Formati supportati con parse + emit UDM-aware: `.syx`, `.blk`, `.q7p`, `.q7a`, `.mid`
- [ ] Converter QY70 ↔ QY700 emette `.warnings.json` esplicito e supporta `--keep/--drop`
- [ ] Phrase library mapping 4167 ↔ 3876 copertura >95%
- [ ] Round-trip QY70 → QY700 → QY70 (con companion `.warnings.json`) byte-identical
- [ ] Test suite >300 test verdi (164 attuali + ~150 nuovi)
- [ ] Zero brick in hardware test suite su QY700 primario

---

## 4. Architettura proposta: Unified Data Model (UDM)

### 4.1 Motivazione architetturale

**Problema attuale**: parser e converter lavorano direttamente sui byte. `qy70_to_qy700.py` è template-based (parte da TXX.Q7P e modifica offset). Editor CLI opera su `QuantizedPattern` (midi_tools) che è a sua volta una forma parziale. Tre modelli dati differenti + conversioni byte-to-byte custom → bug di formato, scope limitato, test difficili.

**Soluzione**: un **modello dati unico** in memoria che rappresenta stato musicale completo + sound engine di uno strumento QY. Lingua comune.

```
Byte file  →  Parser  →  UDM  →  Editor ops  →  UDM'  →  Emitter  →  Byte file
                          ↓                       ↓
                       Converter ←——————————— Converter
                          (QY70 → QY700 o viceversa, opera su UDM)
                          
MIDI port  →  Capture  →  UDM  (realtime observe)
              Emit    ←  UDM  (realtime send XG Param Change)
```

### 4.2 Struttura del modello

**Top-level**:

```python
@dataclass
class Device:
    model: DeviceModel  # QY70 | QY700
    system: System
    multi_part: list[MultiPart]         # 16 | 32 entries
    drum_setup: list[DrumSetup]         # 1 | 2 (QY700 ha 2 kit editabili)
    effects: Effects
    songs: list[Song]                   # 20
    patterns: list[Pattern]             # 64
    phrases_user: list[Phrase]          # 384 | 256
    groove_templates: list[GrooveTemplate]  # 100
    fingered_zone: FingeredZone
    utility: UtilityFlags
```

**Sub-model principali** (range nei commenti):

```python
@dataclass
class System:
    master_tune: int       # -100 .. +100 cents
    master_volume: int     # 0 .. 127
    transpose: int         # -24 .. +24 semitones
    midi_sync: MidiSync    # Internal | External | Auto
    device_id: int         # 0 .. 15 (fixed 0 su QY70 esemplare utente)
    echo_back: bool
    local_on: bool         # QY700 only
    filters: MidiFilters   # per-message filter
    # ... (vedi wiki/xg-system.md)

@dataclass
class MultiPart:
    part_index: int        # 0 .. 15 (QY70) | 0 .. 31 (QY700)
    rx_channel: int        # 0 .. 15 | 16=off
    voice: Voice           # Bank MSB + LSB + Program
    volume: int            # 0 .. 127
    pan: int               # 0..127 (64=center)
    reverb_send: int       # 0 .. 127
    chorus_send: int       # 0 .. 127
    variation_send: int    # 0 .. 127 (QY700 only)
    cutoff: int            # -64 .. +63
    resonance: int         # -64 .. +63
    eg_attack: int         # -64 .. +63
    eg_decay: int
    eg_release: int
    mono_poly: MonoPoly
    key_on_assign: KeyOnAssign
    # ... (~70 campi, vedi wiki/xg-multi-part.md)

@dataclass
class DrumSetup:
    kit_index: int
    notes: dict[int, DrumNote]  # key = MIDI note (13..84), value = params
    
@dataclass
class DrumNote:
    pitch_coarse: int      # -64 .. +63
    pitch_fine: int
    level: int
    pan: int               # Random | 0..127
    reverb_send: int
    chorus_send: int
    variation_send: int    # QY700
    filter_cutoff: int
    filter_resonance: int
    eg_attack: int
    eg_decay1: int
    eg_decay2: int
    alt_group: int         # 0..127 (notes in same group cut each other)
    note_off_mode: NoteOffMode
    # ... (vedi wiki/xg-drum-setup.md)

@dataclass
class Effects:
    reverb: ReverbBlock    # type + ~11 params
    chorus: ChorusBlock    # type + ~11 params
    variation: VariationBlock | None  # QY700 only, type + ~43 params
    # connection type, return levels, parameters 1-16 (sense varia per type)

@dataclass
class Pattern:
    index: int
    name: str              # 8 (QY70) | 10 (QY700) char ASCII
    tempo_bpm: float       # 30.0 .. 300.0
    measures: int
    time_sig: TimeSig
    sections: list[Section]  # 6 (QY70) | 8 (QY700)
    chord_track: ChordTrack
    groove_ref: int | None   # None = Groove Off

@dataclass
class Section:
    name: SectionName      # Main_A/B/C/D | Fill_AA/BB/CC/DD (QY700 has 8)
    tracks: list[PatternTrack]  # 8 (QY70) | 16 (QY700)

@dataclass
class PatternTrack:
    phrase_ref: PhraseRef  # either preset ID or user ID
    midi_channel: int
    transpose_rule: TransposeRule  # Bypass | Bass | Chord1 | Chord2 | Parallel
    mute: bool
    pan: int
    volume: int

@dataclass
class Phrase:
    index: int
    name: str
    category: PhraseCategory  # Da, Db, Fa, Fb, PC, Ba, Bb, Ga, Gb, GR, KC, KR, PD, BR, SE
    beats: int
    time_sig: TimeSig
    events: list[MidiEvent]  # note_on, note_off, cc, pb, nrpn, ... con tick
    phrase_type: PhraseType  # Bypass | Bass | Chord1 | Chord2 | Parallel

@dataclass
class MidiEvent:
    tick: int
    channel: int
    kind: EventKind  # NoteOn | NoteOff | CC | ProgChange | PB | NRPN | SysEx
    data1: int
    data2: int
    # ... per NRPN/SysEx campi extra

@dataclass
class Song:
    index: int
    name: str
    tempo_bpm: float
    time_sig: TimeSig
    tracks: list[SongTrack]  # 8 (QY70) | 35 (QY700)
    pattern_chain: PatternChain | None  # QY700 only

@dataclass
class SongTrack:
    index: int
    kind: SongTrackKind  # Seq | Chord | Tempo | Scene | Pattern | Control | Beat | Click | Meta
    events: list[MidiEvent]
    midi_channel: int | None
    mute: bool

@dataclass
class GrooveTemplate:
    index: int
    name: str
    steps: list[GrooveStep]  # 16 step
    
@dataclass
class GrooveStep:
    timing_offset: int     # 0 .. 200 (100 = zero offset)
    velocity_scale: int    # 0 .. 200 (100 = no change)
    gate_scale: int        # 0 .. 200
```

### 4.3 Proprietà del modello

- **Byte-perfect roundtrip**: `parse(emit(udm)) == udm` garantito da property test
- **Format-agnostic**: stesso UDM serializzabile a `.syx`, `.q7p`, `.mid`, XG bulk SysEx
- **Validatable**: ogni campo ha range/enum; schema check prima di emit
- **Version-tagged**: `udm_version: str` in Device permette migrazioni future
- **Serializable**: JSON dump per editing manuale + snapshot diff

### 4.4 Relazione con `QuantizedPattern` esistente

`midi_tools/pattern_editor.py` usa `QuantizedPattern` come modello per pattern editing. **Non lo buttiamo via**: diventa un **adapter** che legge da UDM ed espone view editing-friendly. Tutte le CLI attuali restano back-compat.

---

## 5. Pilastri di lavoro

### P1 — Unified Data Model + Reversible Parsers

Fondamenta tutto poggia sopra.

**Sub-fasi**:

**P1.1 Schema UDM** (1 sessione):
- Definire tutte le dataclass in `qymanager/model/`
- Range/enum validators (pydantic v2 o dataclass + custom `validate()`)
- JSON serialization round-trip test

**P1.2 Q7P ↔ UDM** (1-2 sessioni):
- Rifattorizzare `q7p_reader.py` → `parse(bytes) → Device(QY700)`
- Rifattorizzare `q7p_writer.py` → `emit(device) → bytes`
- Property test: 100 Q7P random → parse → emit → byte-identical
- **Blocker**: phrase blob 0x360-0x677 → passthrough opaco con marker, completare P4c (chord layer) per editing nota-per-nota

**P1.3 `.syx` sparse ↔ UDM** (1-2 sessioni):
- `qymanager/formats/qy70/syx_parser.py` → `parse(bytes) → Device(QY70)`
- `qymanager/formats/qy70/syx_writer.py` → `emit(device) → bytes`
- Property test su 7 user patterns noti

**P1.4 XG bulk dump ↔ UDM** (1 sessione):
- Parser per blocchi XG completi (System/Multi/Drum/Eff) ricevuti via bulk dump
- Integra `xg_param.py::parse_all_events` come base
- Output: `System, list[MultiPart], list[DrumSetup], Effects`

**P1.5 SMF ↔ UDM** (1 sessione):
- `qymanager/formats/smf.py::parse(path) → Song(tracks=...)`
- Emit già esiste via mido
- Property test: SMF round-trip

**P1.6 `.blk` wrapper** (0.5 sessione):
- `.blk` = raw SysEx stream multi-message, già noto (RE Data Filer)
- Wrapper parser: itera messaggi, route a parser appropriato per Model ID

**File creati/modificati P1**:
```
qymanager/model/
  __init__.py
  device.py
  system.py
  multi_part.py
  drum_setup.py
  effects.py
  pattern.py
  section.py
  phrase.py
  song.py
  groove.py
  event.py
  fingered_zone.py
  utility.py
  voice.py
  phrase_category.py
qymanager/formats/xg_bulk.py        (NEW)
qymanager/formats/smf.py            (modify: add parse)
qymanager/formats/qy700/q7p_reader.py  (rewrite UDM-aware)
qymanager/formats/qy700/q7p_writer.py  (rewrite UDM-aware)
qymanager/formats/qy70/syx_parser.py   (rewrite UDM-aware)
qymanager/formats/qy70/syx_writer.py   (NEW)
qymanager/formats/blk.py            (NEW)
tests/property/test_udm_roundtrip.py   (NEW)
tests/property/test_q7p_roundtrip.py   (NEW)
tests/property/test_syx_sparse_roundtrip.py (NEW)
```

**Deliverable**: MS1 (Milestone 1) — parser+emitter per 5 formati, UDM validato

---

### P2 — Editor Completo (offline + realtime simultanei)

Ogni comando CLI accetta `--realtime` per emettere XG Param Change live invece di scrivere file. Stessa API Python.

**Architettura CLI**:

```
qymanager <category> <action> <target> [params] [--in file] [--out file] [--realtime] [--port NAME]
```

**Tabella comandi completa** (target ~60 sub-command):

| Categoria | Comando | Target UDM | Range/note |
|-----------|---------|-----------|------------|
| **System** | `system show` | `UDM.system` | Stampa stato |
| | `system set master-tune N` | `System.master_tune` | -100 .. +100 |
| | `system set master-vol N` | `System.master_volume` | 0 .. 127 |
| | `system set transpose N` | `System.transpose` | -24 .. +24 |
| | `system set midi-sync MODE` | `System.midi_sync` | internal/external/auto |
| | `system set filter MSG bool` | `System.filters` | note/cc/pb/sysex |
| | `system xg-on` | — | Invia `F0 43 10 4C 00 00 7E 00 F7` |
| | `system all-reset` | — | Invia All Parameter Reset |
| **Multi Part** | `part show N` | `UDM.multi_part[N]` | Stampa part setup |
| | `part set N voice=NAME` | `MultiPart.voice` | Lookup voce per nome |
| | `part set N bank-msb=X bank-lsb=Y prog=Z` | `MultiPart.voice` | Bank/prog raw |
| | `part set N volume=V pan=P` | | 0..127 |
| | `part set N rev=V cho=V var=V` | | effect sends |
| | `part set N cutoff=V reso=V` | | -64..+63 |
| | `part set N eg-attack=V eg-decay=V eg-release=V` | | |
| | `part set N mono-poly=M` | | mono/poly |
| | `part list-voices [--search PAT]` | — | 519/491 voces database |
| **Drum Setup** | `drum show KIT` | `UDM.drum_setup[KIT]` | |
| | `drum set KIT NOTE level=V` | `DrumNote.level` | 0..127 |
| | `drum set KIT NOTE pan=V pitch=V rev=V cho=V` | | |
| | `drum set KIT NOTE eg-attack=V eg-decay1=V eg-decay2=V` | | |
| | `drum set KIT NOTE alt-group=G note-off-mode=M` | | |
| | `drum copy KIT1 KIT2` | | Duplica kit |
| | `drum reset KIT` | | Reset a factory default |
| **Effect** | `effect show` | `UDM.effects` | |
| | `effect reverb TYPE [P1=V1 P2=V2 ...]` | `Effects.reverb` | 11 reverb types |
| | `effect chorus TYPE [P1=V1 ...]` | `Effects.chorus` | 11 chorus types |
| | `effect variation TYPE [P1=V1 ...]` | `Effects.variation` | 43 variation types (QY700) |
| | `effect set-return TYPE V` | | reverb/chorus/variation return |
| **Song** | `song list` | `UDM.songs` | List 20 song slot |
| | `song new INDEX NAME` | | Crea song empty |
| | `song rename INDEX NAME` | | |
| | `song set-tempo INDEX BPM` | | |
| | `song set-tsig INDEX N/D` | | |
| | `song track-mute INDEX TRACK bool` | | |
| | `song play-effect-ref INDEX GROOVE_ID` | | |
| | `song copy SRC DST` | | |
| **Pattern** | `pattern list` | `UDM.patterns` | |
| | `pattern new INDEX NAME` | | |
| | `pattern set-tempo INDEX BPM` | | |
| | `pattern resize INDEX BARS` | | |
| | `section copy SRC DST` | | |
| | `section clear INDEX SECTION TRACK` | | |
| | `section phrase-set INDEX SECTION TRACK PHRASE_ID [--type TYPE]` | | Bypass/Bass/Chord1/Chord2/Parallel |
| **Chord track** | `chord list PATTERN` | `Pattern.chord_track` | |
| | `chord set PATTERN BAR:BEAT ROOT TYPE` | | 12 root × 28 type |
| | `chord shift PATTERN SEMITONES` | | |
| | `chord clear PATTERN BAR` | | |
| **Groove** | `groove list` | `UDM.groove_templates` | |
| | `groove show INDEX` | | Render step table |
| | `groove set INDEX STEP timing=V velocity=V gate=V` | | |
| | `groove new INDEX NAME --copy-from SRC` | | |
| **Phrase** | `phrase list [--category CAT]` | `UDM.phrases_user` | |
| | `phrase extract INDEX --out FILE.mid` | | Export user phrase → MIDI |
| | `phrase import FILE.mid INDEX [--type TYPE]` | | Import MIDI → user phrase |
| | `phrase set-type INDEX TYPE` | `Phrase.phrase_type` | Bypass/Bass/Chord1/Chord2/Parallel |
| | `phrase rename INDEX NAME` | | |
| | `phrase delete INDEX` | | |
| **Pattern editor** (esistente, 21 cmd) | `edit export/build/add-note/transpose/...` | `Pattern.sections.tracks.phrases.events` | Mantenuti back-compat |
| **Fingered Zone** | `zone show` | `UDM.fingered_zone` | |
| | `zone set LOW HIGH` | | MIDI note range |
| **Realtime** | `realtime connect [--port NAME] [--device MODEL]` | — | Apre connessione |
| | `realtime watch` | — | Log parameter changes ricevuti |
| | `realtime snapshot --out FILE` | — | Dump stato device → UDM JSON |
| | `realtime apply FILE` | — | Emit tutti i param da UDM JSON |
| | `realtime disconnect` | — | |

**Implementazione comune**:

```python
# qymanager/editor/offline.py
def apply_op(udm: Device, op: EditorOp) -> tuple[Device, list[Warning]]:
    """Applica operazione editor al modello UDM, restituisce UDM modificato."""
    ...

# qymanager/editor/realtime.py  
def emit_op(port, op: EditorOp, device_id=0) -> list[bytes]:
    """Traduce operazione editor in SysEx Parameter Change e invia."""
    address = address_map.lookup(op.target_field)
    payload = encode_value(op.value, op.target_field)
    sysex = build_xg_param_change(device_id, address.ah, address.am, address.al, payload)
    port.send_sysex(sysex)
    return [sysex]

# cli/commands/part.py
def part_set(ctx, part_index, **kwargs):
    op = EditorOp(target=f"multi_part[{part_index}]", **kwargs)
    if ctx.realtime:
        emit_op(ctx.port, op, device_id=ctx.device_id)
    else:
        udm = load(ctx.input_file)
        udm, warnings = apply_op(udm, op)
        save(udm, ctx.output_file)
        log_warnings(warnings)
```

**File creati/modificati P2**:
```
qymanager/editor/
  offline.py         (NEW, apply_op logic)
  realtime.py        (NEW, wrap xg_param.emit)
  schema.py          (NEW, validate op + values)
  address_map.py     (NEW, UDM field → XG AH/AM/AL)
  ops.py             (NEW, EditorOp dataclass + all op types)
qymanager/editor/voice_db.py  (NEW, voice name lookup)
qymanager/editor/drum_kit_db.py (NEW, kit/note defaults)
cli/commands/
  system.py          (NEW)
  part.py            (NEW)
  drum.py            (NEW)
  effect.py          (NEW)
  song.py            (NEW)
  pattern.py         (NEW)
  chord.py           (NEW)
  groove.py          (NEW)
  phrase.py          (NEW)
  realtime.py        (NEW)
  zone.py            (NEW)
cli/commands/edit.py     (extend, migrate to UDM)
cli/commands/xg.py       (add emit/apply subcommands)
midi_tools/xg_param.py   (expose emit API for realtime.py)
midi_tools/pattern_editor.py  (migrate to UDM, keep CLI back-compat)
tests/integration/test_editor_chain.py  (NEW)
tests/integration/test_realtime_echo.py (NEW)
tests/hardware/test_realtime_apply.py   (NEW)
```

**Deliverable**: MS2 (Milestone 2) — editor completo offline + realtime, tutti i parametri editabili

---

### P3 — Converter Perfetto con lossy granulare

Opera su UDM. Mappa strutturale tra QY70 e QY700.

**Mapping principali**:

| Campo | QY70 | QY700 | Mapping |
|-------|------|-------|---------|
| Parts | 16 | 32 | Forward: copy 1-16, restanti default off. Reverse: drop 17-32 (warning) |
| Voices | 519 XG Normal | 491 XG Normal | LUT voice_map per programma; XG core identico, fallback Bank 0 |
| Drum Kits | 20 | 11 | LUT kit_map; fallback "Standard Kit" se mancante |
| Effects | Reverb+Chorus | Reverb+Chorus+Variation | Forward: Variation default Thru. Reverse: drop Variation (warning) |
| Sections | 6 (A-D + Fill AA/BB) | 8 (A-D + Fill AA-DD) | Forward: CC copia AA, DD copia BB. Reverse: CC/DD warn+drop o merge AA/BB |
| Tracks/section | 8 | 16 | Forward: tracks 9-16 default empty. Reverse: drop 9-16 se non empty (warning) |
| Phrase library | 4167 preset + 384 user | 3876 preset + 256 user | LUT phrase_map (P4b) + user 1:1 fino a 256 |
| Phrase types | Bypass/Bass/Chord1/Chord2 | + Parallel | Forward: Parallel resta QY700-only. Reverse: Parallel warn+drop |
| Song tracks | 8 | 35 | Forward: Tr1-4 + Chord/Tempo/Scene pass-through. Reverse: usa solo Tr1-4 |
| Groove templates | 100 preset | 100 preset | Assumiamo identici (da verificare P4f) |
| Fingered Zone | yes | yes | Pass-through |
| Pattern Chain | no | yes | Forward: skip. Reverse: drop (warning) |

**Lossy policy CLI**:

```bash
# Conversione "preserve all I can" con warning
qymanager convert SGT.syx --to qy700 --out SGT.q7p \
    --warn-file SGT.warnings.json

# Specifica esplicitamente cosa tenere/droppare
qymanager convert big.q7p --to qy70 --out small.syx \
    --keep tempo,name,tr1-4,reverb,chorus \
    --drop variation,parts-17-32,fill-cc-dd \
    --warn-file small.warnings.json

# Modalità strict: rifiuta se drop non-esplicito
qymanager convert big.q7p --to qy70 --strict

# Round-trip con companion file lossless
qymanager convert SGT.syx --to qy700 --out SGT.q7p \
    --companion SGT.companion.json  # salva TUTTO ciò che non entra nel Q7P
qymanager convert SGT.q7p --to qy70 --companion SGT.companion.json \
    --out SGT_back.syx
# SGT.syx == SGT_back.syx byte-identical (round-trip lossless)
```

**Formato `.warnings.json`**:
```json
{
  "source_format": "qy70_syx",
  "target_format": "q7p",
  "timestamp": "2026-04-17T15:30:00Z",
  "lossy_operations": [
    {"field": "sections.Fill_CC", "action": "copied_from", "source": "Fill_AA"},
    {"field": "sections.Fill_DD", "action": "copied_from", "source": "Fill_BB"},
    {"field": "parts[17-31]", "action": "defaulted_off", "reason": "QY70 has 16 parts"}
  ],
  "preserved_in_companion": {
    "groove_user_edits": [...],
    "xg_extras": [...]
  }
}
```

**File creati/modificati P3**:
```
qymanager/converters/
  qy70_to_qy700.py   (rewrite UDM-based)
  qy700_to_qy70.py   (rewrite UDM-based)
  mapping_tables.py  (NEW, voice/kit/phrase LUTs)
  lossy_policy.py    (NEW, --keep/--drop parser + warn emitter)
  companion.py       (NEW, save/load companion file)
  section_mapper.py  (NEW, 6↔8 section logic)
  track_mapper.py    (NEW, 8↔16 track logic)
cli/commands/convert.py  (rewrite, UDM-based, lossy flags)
tests/integration/test_converter_roundtrip.py (NEW)
tests/integration/test_lossy_policy.py        (NEW)
tests/integration/test_companion_roundtrip.py (NEW)
```

**Deliverable**: MS3 (Milestone 3) — converter perfetto con lossy granulare + companion

---

### P4 — Reverse Engineering residuo

Priorità per robustezza del converter:

**P4a — Voice offsets Q7P** (HIGH, 5-10 sessioni, confidence alta):

**Problema**: offset 0x1E6/0x1F6/0x206 sospettati di essere Bank MSB/Program/Bank LSB per-track, ma scrittura lì ha brickato il QY700 (Session 1-10). Veri offset sconosciuti.

**Approccio**:
1. Creare `midi_tools/safe_q7p_tester.py` come da piano originale Session 11
2. Genera Q7P con 1 byte variato per volta partendo da TXX.Q7P baseline
3. Load su QY700 secondario (yolo), capture XG OUT, confronta voce renderata
4. Bisezione su zona 0x100-0x260 con voci note programmate manualmente
5. Validation: "expected drum kit Bank 127 Prg 0, actual from XG OUT = X"

**Output atteso**: tabella offset → campo, confidence High. Documentata in `wiki/q7p-format.md` + `wiki/voice-offsets-q7p.md` (nuova pagina).

**P4b — Phrase library mapping integrale** (HIGH, 2-4 sessioni):

**Problema**: 4167 preset phrases QY70 vs 3876 QY700. Nessuna tabella nota di corrispondenza. Quando un pattern QY700 usa preset 500, come mappiamo a QY70?

**Approccio**:
1. BULK ALL dump QY70 → estrai tutte preset phrase
2. Per ogni phrase: categoria, nome, beat count, time signature, **fingerprint note content** (hash delle prime N note + velocity)
3. Stesso per QY700
4. Build `mapping_tables.py::PHRASE_QY70_TO_QY700 = dict[int, int]` con match esatto su fingerprint, fallback su nome+categoria+beat
5. Validation: convertire pattern noto, load QY70, confronta playback

**Output atteso**: `mapping_tables.py` con dict completo + `wiki/phrase-library-mapping.md`.

**P4c — Chord transposition layer** (HIGH, 5-10 sessioni):

**Problema**: phrase Chord1/Chord2 memorizzano note **chord-relative** (offset da root). Quando chord track cambia da C a Am, la phrase viene trasposta/alterata dal QY firmware. Senza capire la formula, non possiamo editare phrase Chord1/Chord2 correttamente.

**Approccio**:
1. Capture phrase Chord1 nota (es. preset C01) con chord C major → note rendered MIDI
2. Cambia chord track a Am, capture di nuovo → note rendered MIDI
3. Deduci formula: ogni nota ha un template `(degree, octave_offset, voicing_rule)`
4. Valida su 10 preset phrase diverse
5. Aggiungi a UDM `PhraseNote.chord_template` invece di MIDI note raw

**Output atteso**: `wiki/chord-transposition.md` + editor supporta editing chord-relative per Chord1/Chord2.

**P4d — Dense bitstream encoding** (LOW priority, parallel, 10-30 sessioni):

**Approccio "1 su 5"**: ogni 5 sessioni regolari, dedichiamo 1 sessione al dense RE. Continuiamo Session 29 findings (42B super-cycle, per-beat rotation).

**Tentativi futuri**:
1. Ground truth pattern A/B/C/D (#29 pending) — chord semplici con 1 nota per beat
2. Constraint satisfaction: mappa beat MIDI note → bit position tramite SMT solver (Z3)
3. Reference-based hypothesis: forse dense = phrase ID + transform delta
4. Firmware dump come ultima spiaggia (QY70 service mode, JTAG, ...)

**Time-box**: se dopo 30 sessioni totali niente breakthrough, pivot permanente a Pipeline B only, documenta impossibility in `wiki/bitstream.md`.

**P4e — Q7A format** (MEDIUM, 3-5 sessioni):

**Problema**: Q7A = All-Data backup QY700. Layout sconosciuto.

**Approccio**:
1. Hardware dump: salva tutto QY700 come Q7A via floppy emulator
2. Hexdump, confronta con Q7P noto + Q7S noto
3. Struttura probabile: `[header][pointers][Q7P × 64][Q7S × 20][system/effects/groove]`
4. Validation: load back su QY700 secondario, verifica stato identico

**Output atteso**: parser in `qymanager/formats/qy700/q7a_parser.py` + `wiki/q7a-format.md`.

**P4f — Groove template internals** (LOW, 2-3 sessioni):

Verificare che user groove modificato viene salvato in pattern o resta device-local. Capire se 100 groove preset QY70 e QY700 sono byte-identici o differiscono.

**P4g — Song format Q7S** (LOW, on-demand, 3-5 sessioni):

Se qualcuno chiede support Q7S, RE da hardware dumps. Layout probabile simile a Q7P + pattern chain + 35 tracks.

---

### P5 — Test & Validation

**Strategia a 4 livelli**:

**L1 Unit** (~150 test esistenti + ~50 nuovi):
- Parser byte-per-byte per ogni formato
- UDM dataclass validation
- Singoli editor ops

**L2 Property** (~30 test nuovi, `hypothesis`):
- `parse(emit(udm)) == udm` per ogni formato
- Converter: `convert_back(convert(udm, companion)) == udm`
- Editor: sequenze random di ops su UDM, verifica consistenza

**L3 Integration** (~50 test nuovi):
- UDM → converter → UDM' con warnings expected
- Editor chain: load → N ops → save → reload → equal
- CLI end-to-end: subprocess invoke + file diff

**L4 Hardware** (~30 test nuovi, skip se no device):
- `test_q7p_load_qy700.py` — carica Q7P generati, verifica no-brick + playback match
- `test_realtime_xg_echo.py` — emit param, capture XG OUT, verifica eco
- `test_capture_playback_match.py` — QY70 programmato → capture → UDM → Pipeline B → QY700 capture → compare
- `test_offset_sweep.py` — driver per safe_q7p_tester (scoperta offset voice)
- `test_brick_recovery.py` — load Q7P invalido, factory reset, verifica recupero

**Infrastruttura**:
- `conftest.py` fixture per rtmidi port auto-detection
- `pytest --hardware` flag per eseguire L4
- `pytest --slow` flag per property test lunghi
- Report coverage tramite `pytest-cov` (target >85%)

---

### P6 — Documentation & Wiki

Mantenimento continuo (CLAUDE.md rules):

**Nuove pagine wiki**:
- `wiki/udm.md` — schema UDM, diagrammi, esempi JSON
- `wiki/converter-architecture.md` — flow QY70 ↔ UDM ↔ QY700, lossy
- `wiki/editor-architecture.md` — offline/realtime unified API
- `wiki/phrase-library-mapping.md` — tabella integrale (post P4b)
- `wiki/q7a-format.md` — layout binario Q7A (post P4e)
- `wiki/voice-offsets-q7p.md` — offset confermati Q7P (post P4a)
- `wiki/chord-transposition.md` — formula chord-relative (post P4c)

**Pagine da aggiornare**:
- `STATUS.md` a ogni milestone
- `wiki/log.md` ogni sessione
- `wiki/decoder-status.md` a ogni RE avanzamento
- `wiki/open-questions.md` chiusura issue
- `wiki/q7p-format.md` con offset voice confermati
- `wiki/conversion-roadmap.md` nuovo flow UDM-based

**Preparazione open-source** (post MS4):
- `README.md` user-facing con quickstart
- `CONTRIBUTING.md` stile codice + workflow RE
- `CHANGELOG.md` versione-per-versione
- GitHub Actions CI (pytest + ruff + type check)
- Release tags semver (v0.1.0 = MS1, v1.0.0 = MS4)
- PyPI packaging (`pyproject.toml` già presente)
- Issue templates + PR templates

---

## 6. Reverse engineering residuo — dettaglio operativo

### 6.1 Ordinamento priorità

```
Priorità  Task                              Sblocca                         Sessioni
─────────────────────────────────────────────────────────────────────────────────
1 (HIGH)  P4a Voice offsets Q7P            Voice setting corretto nel Q7P  5-10
2 (HIGH)  P4b Phrase library mapping       Conversione phrase QY70↔QY700   2-4
3 (MED)   P4c Chord transposition layer    Editing phrase Chord1/Chord2    5-10
4 (MED)   P4e Q7A format                   Backup totale QY700             3-5
5 (LOW)   P4d Dense bitstream encoding     Pipeline A (factory styles)     10-30 (parallel)
6 (LOW)   P4f Groove template internals    Groove cross-device             2-3
7 (LOW)   P4g Q7S format                   Song file QY700                 3-5 (on demand)
```

### 6.2 Ground truth pattern da catturare

Issue #29 (pending da Session 11) riassunta:

| Pattern | Sezione | Contenuto | Scopo RE |
|---------|---------|-----------|----------|
| GT_A | Main A | CHD2, C major, 4 bar 4/4, 120 BPM | Valida chord decoder |
| GT_B | Main A | CHD2, Am, 4 bar 4/4, 120 BPM | Chord transposition formula |
| GT_C | Main A | RHY1, kick nota 36 beat 1 only | Drum decoder minimal |
| GT_D | Main A+B | CHD2 C, Main B CHD2 G | Cross-section chord |
| GT_E | Main A | BASS, C3 E3 G3 pattern | Bass encoding |
| GT_F | Main A | PHR1, Parallel type | Parallel phrase type test |

Procedura:
1. Programmare pattern sul QY70 manualmente (UI hardware)
2. Save: `python3 midi_tools/capture_dump.py -o midi_tools/captured/GT_A.syx`
3. Simultaneo: `python3 midi_tools/capture_playback.py -o midi_tools/captured/GT_A.mid` per reference MIDI
4. Analyze: `python3 midi_tools/ground_truth_analyzer.py GT_A.syx GT_A.mid`
5. Update `wiki/decoder-status.md` con confidence

---

## 7. Timeline e milestone

### 7.1 Fasi

| Fase | Deliverable | Sessioni | Cumulativo |
|------|-------------|----------|------------|
| **F1** | UDM schema + Q7P/syx sparse UDM-aware | 4-5 | 4-5 |
| **F2** | SMF + XG bulk parser UDM + roundtrip test | 3-4 | 7-9 |
| **F3** | Editor offline: System/Part/Drum/Effect CLI + Schema validation | 4-6 | 11-15 |
| **F4** | Editor offline: Song/Pattern/Chord/Groove/Phrase CLI | 4-6 | 15-21 |
| **F5** | Editor realtime: XG emit integrato, --realtime flag, address_map | 3-4 | 18-25 |
| **F6** | P4a Voice offsets Q7P RE (hardware yolo) | 5-10 | 23-35 |
| **F7** | P4b Phrase library mapping integrale | 2-4 | 25-39 |
| **F8** | P4c Chord transposition layer RE | 5-10 | 30-49 |
| **F9** | Converter UDM-based + lossy granulare + companion | 3-5 | 33-54 |
| **F10** | P4e Q7A format RE + parser | 3-5 | 36-59 |
| **F11** | Hardware test suite completa | 2-4 | 38-63 |
| **F12** | Consolidamento + preparazione open-source | 2-3 | 40-66 |
| **F13** (parallel, 1 su 5) | P4d Dense bitstream RE | 10-30 | +0 effettivo |
| **F14** (post MS4) | TUI (textual) | 5-10 | |
| **F15** (post MS4) | GUI desktop | 10-20 | |

**Totale CLI + converter integrale (F1-F12)**: **~40-65 sessioni**.

### 7.2 Milestone

| MS | Dopo fase | Deliverable tangibile | Release |
|----|-----------|-----------------------|---------|
| **MS1** | F2 | Parser+emitter UDM per 5 formati, 300+ test verdi | Internal |
| **MS2** | F5 | Editor completo offline + realtime, tutti parametri XG editabili | Internal |
| **MS3** | F9 | Converter perfetto con lossy granulare + companion, phrase mapping | Internal beta |
| **MS4** | F12 | Stabile, hardware validation, zero brick, docs user-facing | **Open-source v1.0.0** |
| MS5 | F14 | TUI textual | Open-source v1.1.0 |
| MS6 | F15 | GUI desktop | Open-source v2.0.0 |

### 7.3 Velocity stimata

Sessioni recenti (27-30i) hanno prodotto in media ~2-3 feature/discovery per sessione. Con `--resume` session-to-session, `uv sync` + test in <30s, ~40-65 sessioni corrispondono a **3-6 mesi calendar** (2-3 sessioni/settimana). Estendibile.

---

## 8. Test strategy

### 8.1 Piramide test

```
         /\
        /L4\       Hardware-in-the-loop (~30 test)
       /____\      Pytest --hardware, skip se no device
      /      \
     /   L3   \    Integration (~50 test)
    /          \   CLI end-to-end, converter roundtrip
   /____________\
  /              \ Property (~30 test)
 /      L2        \ Hypothesis, UDM invariants, roundtrip
/__________________\
  L1 Unit (~200 test, esistenti + nuovi)
```

### 8.2 Esempi chiave

**L1 Unit**:
```python
def test_q7p_header_parse():
    raw = b"\x00\x20\x00\x00" + ...  # 3072 byte Q7P mock
    header = parse_q7p_header(raw)
    assert header.size == 3072
    assert header.tempo == 120.0
```

**L2 Property**:
```python
@given(udm=udm_device_strategy(DeviceModel.QY700))
def test_q7p_roundtrip(udm):
    raw = emit_q7p(udm)
    udm2 = parse_q7p(raw)
    assert udm == udm2
```

**L3 Integration**:
```python
def test_convert_qy70_to_qy700_preserves_tempo():
    udm_in = parse_syx(fixture("SGT.syx"))
    udm_out, warnings = convert(udm_in, target=DeviceModel.QY700)
    assert udm_out.patterns[0].tempo_bpm == udm_in.patterns[0].tempo_bpm
    assert "parts[17-31]" not in [w.field for w in warnings]  # not emitted forward
```

**L4 Hardware**:
```python
@pytest.mark.hardware
def test_realtime_xg_echo(qy700_port):
    emit_part_voice(qy700_port, part=0, voice="Grand Pno")
    time.sleep(0.2)
    echo = capture_xg_out(qy700_port, duration=0.5)
    assert any(is_program_change_1(msg) for msg in echo)
```

### 8.3 Coverage target

- Parser: >95% line coverage
- Editor: >90% line coverage, 100% branch coverage su validation
- Converter: >90% line coverage, 100% lossy policy paths
- CLI: >80% line coverage (entry points)

### 8.4 CI (post MS4)

`.github/workflows/ci.yml`:
```yaml
- ruff check
- pytest tests/property/ tests/integration/ tests/unit/
- mypy qymanager/
- coverage >85%
```

Hardware tests: local-only (skip in CI).

---

## 9. Rischi e mitigazioni

| # | Rischio | Probabilità | Impatto | Mitigazione |
|---|---------|-------------|---------|-------------|
| R1 | Dense bitstream non si risolve mai | Alta | Medio | Pipeline B già prod-ready; Pipeline A resta STUB, non blocca |
| R2 | Voice offsets Q7P causano brick su QY700 primario | Media | Alto | `full yolo` solo su QY700 secondario; baseline TXX.Q7P recovery |
| R3 | Phrase library RE più lunga di 4 sessioni | Media | Medio | Fallback "best match by name+category" accettabile per v1 |
| R4 | UDM schema cambia dopo F3 → rework parser | Bassa | Alto | Property test cattura regressioni; version tag in UDM; migration helpers |
| R5 | Hardware disponibilità cambia | Bassa | Medio | Skip automatico L4, mock UDM per sviluppo offline |
| R6 | Chord transposition RE richiede firmware dump | Media | Alto | Fallback: editor per Chord1/Chord2 read-only, solo Bypass editabile nota-per-nota |
| R7 | Timeline 40-65 sessioni scoraggia | Certa | Basso | Milestone MS1 (dopo 7-9 sessioni) già dà editor usabile; rilasci incrementali |
| R8 | Regressioni sulle 164 test attuali | Media | Medio | Commit granulari, test pre-commit hook obbligatorio |
| R9 | QY70 "transmitting freeze" quirk complica hardware test | Certa | Basso | Documentato Session 30c, uso 1 edit + 1 send + power cycle |
| R10 | Voice database QY70/QY700 non identico → mapping voci | Alta | Basso | LUT fallback a Bank 0 XG core, warning esplicito |
| R11 | Q7A format troppo opaco per RE | Media | Medio | Time-box 5 sessioni, se niente → documenta struttura parziale, fallback "raw blob" |
| R12 | Formato `.warnings.json` instabile → utente confuso | Bassa | Basso | Versioning del formato, migration script |

---

## 10. File e struttura progetto

### 10.1 Layout proposto post-piano

```
qyconv/
├── STATUS.md                    # north-star (esistente)
├── PLAN.md                      # questo file
├── CLAUDE.md                    # istruzioni AI (esistente)
├── README.md                    # user-facing (da scrivere post MS4)
├── CONTRIBUTING.md              # post MS4
├── CHANGELOG.md                 # post MS4
├── pyproject.toml               # esistente
├── uv.lock                      # esistente
│
├── qymanager/                   # pacchetto Python principale
│   ├── __init__.py
│   ├── model/                   # NEW: Unified Data Model
│   │   ├── __init__.py
│   │   ├── device.py
│   │   ├── system.py
│   │   ├── multi_part.py
│   │   ├── drum_setup.py
│   │   ├── effects.py
│   │   ├── pattern.py
│   │   ├── section.py
│   │   ├── phrase.py
│   │   ├── song.py
│   │   ├── groove.py
│   │   ├── event.py
│   │   ├── voice.py
│   │   ├── fingered_zone.py
│   │   ├── utility.py
│   │   ├── phrase_category.py
│   │   └── version.py
│   ├── formats/
│   │   ├── __init__.py
│   │   ├── seven_bit_codec.py  # esistente
│   │   ├── xg_bulk.py           # NEW
│   │   ├── smf.py               # esistente, aggiunge parse
│   │   ├── blk.py               # NEW (wrapper)
│   │   ├── qy70/
│   │   │   ├── __init__.py
│   │   │   ├── syx_parser.py    # rewrite UDM-aware
│   │   │   ├── syx_writer.py    # NEW
│   │   │   ├── sparse_codec.py  # RE scoperto
│   │   │   └── dense_codec.py   # STUB, WIP
│   │   └── qy700/
│   │       ├── __init__.py
│   │       ├── q7p_reader.py    # rewrite UDM-aware
│   │       ├── q7p_writer.py    # rewrite UDM-aware
│   │       ├── q7a_parser.py    # NEW (post P4e)
│   │       ├── q7s_parser.py    # NEW on-demand
│   │       └── esq_parser.py    # NEW on-demand
│   ├── editor/                  # NEW
│   │   ├── __init__.py
│   │   ├── ops.py               # EditorOp dataclass + op types
│   │   ├── offline.py           # apply_op su UDM
│   │   ├── realtime.py          # emit_op via XG Param Change
│   │   ├── schema.py            # validate op + values
│   │   ├── address_map.py       # UDM field → XG AH/AM/AL
│   │   ├── voice_db.py          # voice name lookup
│   │   └── drum_kit_db.py       # kit/note defaults
│   ├── converters/
│   │   ├── __init__.py
│   │   ├── qy70_to_qy700.py    # rewrite UDM-based
│   │   ├── qy700_to_qy70.py    # rewrite UDM-based
│   │   ├── mapping_tables.py    # NEW, voice/kit/phrase LUTs
│   │   ├── lossy_policy.py      # NEW, keep/drop parser
│   │   ├── companion.py         # NEW, save/load companion
│   │   ├── section_mapper.py    # NEW, 6↔8 section logic
│   │   └── track_mapper.py      # NEW, 8↔16 track logic
│   ├── pipeline_b/              # existing capture-based
│   │   ├── __init__.py
│   │   └── ... (move from midi_tools)
│   └── validation/
│       ├── __init__.py
│       └── q7p_invariants.py    # esistente
│
├── cli/
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── convert.py           # rewrite UDM-based
│   │   ├── edit.py              # estendere
│   │   ├── xg.py                # aggiunge emit/apply
│   │   ├── validate.py          # esistente
│   │   ├── system.py            # NEW
│   │   ├── part.py              # NEW
│   │   ├── drum.py              # NEW
│   │   ├── effect.py            # NEW
│   │   ├── song.py              # NEW
│   │   ├── pattern.py           # NEW
│   │   ├── chord.py             # NEW
│   │   ├── groove.py            # NEW
│   │   ├── phrase.py            # NEW
│   │   ├── realtime.py          # NEW
│   │   └── zone.py              # NEW
│   └── __init__.py
│
├── midi_tools/                  # standalone scripts
│   ├── capture_playback.py      # esistente
│   ├── capture_dump.py          # esistente
│   ├── capture_xg_stream.py     # esistente
│   ├── request_dump.py          # esistente
│   ├── restore_pattern.py       # esistente
│   ├── send_style.py            # esistente
│   ├── syx_edit.py              # esistente
│   ├── xg_param.py              # esistente, expose emit API
│   ├── pattern_editor.py        # esistente, migrate to UDM
│   ├── safe_q7p_tester.py       # NEW (post P4a start)
│   ├── phrase_library_mapper.py # NEW (post P4b start)
│   └── ground_truth_analyzer.py # NEW (post GT capture)
│
├── tests/
│   ├── unit/                    # esistenti (~200 target)
│   │   ├── test_q7p_reader.py
│   │   ├── test_xg_param.py
│   │   └── ...
│   ├── property/                # NEW
│   │   ├── test_udm_roundtrip.py
│   │   ├── test_q7p_roundtrip.py
│   │   ├── test_syx_sparse_roundtrip.py
│   │   └── test_converter_roundtrip.py
│   ├── integration/             # NEW
│   │   ├── test_editor_chain.py
│   │   ├── test_converter_lossy.py
│   │   ├── test_companion_roundtrip.py
│   │   └── test_cli_end_to_end.py
│   ├── hardware/                # NEW
│   │   ├── conftest.py          # fixture rtmidi port
│   │   ├── test_q7p_load_qy700.py
│   │   ├── test_realtime_xg_echo.py
│   │   ├── test_capture_playback_match.py
│   │   ├── test_offset_sweep.py
│   │   └── test_brick_recovery.py
│   └── fixtures/                # esistente
│       └── ...
│
├── wiki/                        # esistente (20+ pagine)
│   ├── index.md
│   ├── log.md
│   ├── STATUS.md -> ../STATUS.md
│   ├── udm.md                   # NEW
│   ├── converter-architecture.md # NEW
│   ├── editor-architecture.md   # NEW
│   ├── phrase-library-mapping.md # NEW (post P4b)
│   ├── q7a-format.md            # NEW (post P4e)
│   ├── voice-offsets-q7p.md     # NEW (post P4a)
│   ├── chord-transposition.md   # NEW (post P4c)
│   └── ... (esistenti)
│
├── docs/                        # legacy detailed format docs
│   └── ... (esistenti, non toccati)
│
├── exe/                         # QYFiler.exe extracted (esistente)
│
└── manual/                      # manuali Yamaha originali (esistente)
    ├── QY70/
    └── QY700/
```

### 10.2 Script CLI top-level

`qymanager` subcommand tree target:

```
qymanager
├── convert <source> --to <target> [--keep] [--drop] [--warn-file] [--companion]
├── edit <subcommand>          # pattern editor esistente
├── system <subcommand>        # NEW
├── part <subcommand>          # NEW
├── drum <subcommand>          # NEW
├── effect <subcommand>        # NEW
├── song <subcommand>          # NEW
├── pattern <subcommand>       # NEW
├── chord <subcommand>         # NEW
├── groove <subcommand>        # NEW
├── phrase <subcommand>        # NEW
├── zone <subcommand>          # NEW
├── realtime <subcommand>      # NEW
├── xg <subcommand>            # esistente, estendere
└── validate <file>            # esistente
```

---

## 11. Appendici tecniche

### 11.1 Glossario

| Termine | Significato |
|---------|-------------|
| **UDM** | Unified Data Model — modello dati format-agnostic |
| **Q7P** | QY700 Pattern file binary |
| **Q7A** | QY700 All-Data backup file |
| **Q7S** | QY700 Song file |
| **ESQ** | QY700 Sequence file |
| **BLK** | QY70 bulk dump file (= raw SysEx stream) |
| **SMF** | Standard MIDI File |
| **XG** | Yamaha Extended General MIDI standard |
| **DVA** | Dynamic Voice Allocation (QY700 32-parts) |
| **AH/AM/AL** | XG SysEx address bytes: High/Mid/Low |
| **Model 5F** | QY70 Sequencer SysEx Model ID |
| **Model 4C** | XG SysEx Model ID (entrambi i device) |
| **Pipeline A** | QY70 → QY700 via SysEx decode (blocked) |
| **Pipeline B** | QY70 → QY700 via MIDI capture (prod) |
| **Sparse encoding** | User pattern bitstream (R=9×(i+1), proven) |
| **Dense encoding** | Factory style bitstream (unresolved) |
| **Chord1/Chord2** | Phrase types con chord-relative transposition |
| **Groove template** | Play Effect 16-step timing/velocity alteration |
| **Fingered Zone** | MIDI note range per chord detection live |
| **Edit buffer** | Slot RAM temporaneo (AM=0x7E), volatile |

### 11.2 XG Parameter Change reference

**Formato**: `F0 43 1n 4C [AH] [AM] [AL] [data...] F7`

Esempi:
```
F0 43 10 4C 00 00 00 02 F7        # XG On
F0 43 10 4C 00 00 7E 00 F7        # All Parameter Reset
F0 43 10 4C 00 00 04 PART_N VOL F7 # Part Volume
F0 43 10 4C 02 01 00 TYPE F7      # Reverb Type
F0 43 10 4C 08 PART_N 01 BANK F7  # Part Bank MSB
F0 43 10 4C 08 PART_N 02 BANK F7  # Part Bank LSB
F0 43 10 4C 08 PART_N 03 PROG F7  # Part Program
```

Vedi `wiki/xg-parameters.md` per tabella completa.

### 11.3 Bibliografia tecnica

- `manual/QY70/*` — Yamaha QY70 Owner's Manual (originale)
- `manual/QY700/*` — Yamaha QY700 Owner's Manual (originale)
- `wiki/xg-parameters.md` — XG protocol hub (13 pagine wiki)
- `wiki/qyfiler-reverse-engineering.md` — RE integrale Data Filer
- studio4all.de XG Library (referenziato Session 27)
- Yamaha XG Reference Manual (extract, 1994)

### 11.4 Hardware setup utente

Dalla memoria persistente:
- QY70 collegato a Steinberg UR22C Porta 1 (NON "USB Midi Cable")
- QY700 secondario disponibile per "yolo" testing
- QY70 settings: PATT OUT=9~16, MIDI SYNC=External, ECHO BACK=Off
- QY70 non ha Memory Protect né Device No settings
- Collegamento bidirezionale MIDI IN/OUT

### 11.5 Comandi di verifica finale

Post MS4, il progetto deve superare:

```bash
export UV_LINK_MODE=copy

# Unit + property + integration
uv run pytest tests/unit tests/property tests/integration -v

# Hardware (con device connessi)
uv run pytest tests/hardware -v \
    --qy70-port="UR22C Port 1" \
    --qy700-port="UR22C Port 2"

# Coverage >85%
uv run pytest --cov=qymanager --cov-report=term

# Type check
uv run mypy qymanager/

# Lint
uv run ruff check qymanager/ cli/ midi_tools/

# CLI smoke test
uv run qymanager --help
uv run qymanager edit --help
uv run qymanager convert SGT.syx --to qy700 --out /tmp/SGT.q7p --dry-run
uv run qymanager part set 1 voice=Grand-Pno --in /tmp/SGT.q7p --dry-run

# Realtime smoke test (con QY70 connesso)
uv run qymanager realtime connect --port "UR22C Port 1"
uv run qymanager part set 1 voice=Grand-Pno --realtime
uv run qymanager realtime snapshot --out /tmp/qy70_state.json
```

Tutti i comandi devono ritornare exit code 0 e output coerente.

---

## 12. Summary visiva

```
                    ┌─────────────────────────────────────┐
                    │      OBIETTIVO: Suite integrale     │
                    │   controllo programmatico QY70/700  │
                    └──────────────────┬──────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          ▼                            ▼                            ▼
  ┌───────────────┐          ┌─────────────────┐          ┌──────────────────┐
  │ CONVERTER     │          │ EDITOR          │          │ REVERSE ENGINEER │
  │ QY70 ↔ QY700  │          │ Offline+Realtime│          │ (parallel)       │
  │ lossy granular│          │ ~60 sub-command │          │                  │
  └───────┬───────┘          └────────┬────────┘          └────────┬─────────┘
          │                           │                            │
          └───────────┬───────────────┘                            │
                      ▼                                            │
          ┌─────────────────────────┐                              │
          │  UNIFIED DATA MODEL     │  ◄──── P4a Voice offsets     │
          │  (UDM)                  │  ◄──── P4b Phrase map        │
          │  format-agnostic        │  ◄──── P4c Chord transpose   │
          │  parse ↔ emit           │  ◄──── P4d Dense bitstream   │
          │  round-trip garantito   │  ◄──── P4e Q7A format        │
          └──┬───────────────────┬──┘                              │
             │                   │                                 │
    ┌────────┴──┐         ┌──────┴───────┐                         │
    ▼           ▼         ▼              ▼                         │
  ┌─────┐   ┌─────┐   ┌─────┐        ┌─────┐                       │
  │.syx │   │.q7p │   │.mid │        │ XG  │   ... raw SysEx ─────┘
  │ QY70│   │QY700│   │ SMF │        │param│   bulk dump
  └─────┘   └─────┘   └─────┘        └─────┘   realtime
```

---

## 13. Next step operativo

Quando si riprende il lavoro (prossima sessione post-piano):

1. **Review** di questo `PLAN.md` con l'utente
2. **Aggiornamento** `STATUS.md` con link a PLAN.md
3. **Kick-off F1**: creare `qymanager/model/device.py` + `system.py` come primi file UDM
4. **Task tracker**: nuovi task per ogni sub-fase F1-F12
5. **Commit iniziale**: "feat: bootstrap PLAN.md + UDM skeleton"

---

*Fine PLAN.md.*
