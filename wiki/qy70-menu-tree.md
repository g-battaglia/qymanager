# QY70 Menu Tree

Mappa completa e integrale della navigazione del Yamaha QY70 per tutte le 7 modalità principali e le sotto-modalità contestuali. I nomi dei parametri sono riportati esattamente come appaiono sul display del QY70; le descrizioni sono in italiano.

Riferimenti:
- `manual/QY70/QY70_OWNERS_MANUAL.PDF` (OM) — paginatura indicata per sezione
- `manual/QY70/QY70_LIST_BOOK.PDF` (LB) — liste voci/drum/phrase/template
- [qy70-modes.md](qy70-modes.md) — overview dei 7 modi

## Indice

1. [Navigazione globale e controlli](#1-navigazione-globale-e-controlli)
2. [SONG mode](#2-song-mode)
3. [PATTERN mode](#3-pattern-mode)
4. [VOICE mode](#4-voice-mode)
5. [EFFECT mode](#5-effect-mode)
6. [UTILITY mode](#6-utility-mode)
7. [JOB mode](#7-job-mode)
8. [EDIT mode](#8-edit-mode)
9. [Sotto-modalità trasversali](#9-sotto-modalità-trasversali)

---

## 1. Navigazione globale e controlli

### Tasti hardware principali

| Tasto | Funzione |
|-------|----------|
| `MODE` | Cambia modalità operativa (ciclo Song → Pattern → Voice → Effect → Utility) |
| `JOB` | Entra in Job mode (operazioni batch sulla modalità corrente) |
| `EDIT` | Entra in Event Edit mode (editing puntuale eventi) |
| `STORE` | Salva a memoria interna il dato corrente |
| `REC` | Abilita record mode |
| `PLAY` | Avvia playback |
| `STOP` | Ferma playback/record |
| `TOP` | Torna all'inizio della song/pattern |
| `PUNCH IN/OUT` | Autopunch record |
| `F1..F4` | Function keys contestuali (cambiano per pagina) |
| `NO/YES` | Conferma / annulla in dialoghi |
| `+1/-1`, `+10/-10` | Incrementi valore |
| `ENTER` | Apre selezione / conferma |
| `EXIT` | Torna al livello superiore |
| `SHIFT` | Modifier per funzioni secondarie |
| Cursori, Jog Dial | Navigazione lista / edit valore |

Ref: OM pag 3-12 (panoramica hardware).

---

## 2. SONG mode

### 2.1 Pagina principale (PLAY)

Display top-level durante playback/stop di una song. Mostra:
- Song number (01-20 user, 21-23 demo)
- Misura corrente (M)
- Beat corrente
- Tempo (BPM)
- Time signature
- Track status (Track 1-16 + Pt/Cd/Tm)

Tracce disponibili:
- 16 sequencer tracks (1-16)
- **Pt** (Pattern track) — riferimenti a style
- **Cd** (Chord track) — chord changes per styles
- **Tm** (Tempo track) — tempo changes

Ref: OM pag 30-38 (Song playback), 86-88 (Song track structure).

### 2.2 Function keys in Song PLAY

| F-key | Funzione | Note |
|-------|----------|------|
| `F1` | Track Mute/Solo toggle | Seleziona stato per track |
| `F2` | Voice selector | Apre lista voci per track selezionata |
| `F3` | Effect Send | Ingresso pagina Reverb/Chorus/Variation send |
| `F4` | Play Effects | Groove/Drum Table per-track |

### 2.3 Song Record (REC)

Premere `REC` in Song mode apre il dialog di record setup.

#### Record Setup parameters

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TRACK** | 1-16 | - | Track da registrare |
| **TYPE** | REPL / OVER / STEP / PUNCH | REPL | REPL=sovrascrive, OVER=merge, STEP=step record, PUNCH=autopunch |
| **METRONOME** | Off / Rec / Rec&Play / Always | Rec | Metronomo attivo in record |
| **Q.TIZE** (Record Quantize) | Off / 1/32 / 1/24 / 1/16 / 1/12 / 1/8 / 1/6 / 1/4 | Off | Quantizza in input |
| **PUNCH IN M** | 001-999 | - | Misura start punch-in |
| **PUNCH OUT M** | 001-999 | - | Misura end punch-out |

Ref: OM pag 67-78 (Realtime Recording), 81-85 (Step Recording).

#### Step Record display

In STEP record: cursore posizionato sul clock corrente, mostra:
- **CLOCK** (1-480 per quarto)
- **STEP TIME** (durata step)
- **GATE TIME** (durata nota in clock)
- **VELOCITY** (1-127)
- **NOTE** (C-2 to G8)

### 2.4 Pattern track (Pt) entry

Display dedicato per inserire style references. Ref: OM pag 43-50 ("Easy Accompaniment" / Pattern track).

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **STYLE** | Preset Pop/Rock/Ballad/Dance/World + U01-U64 | - | Numero style |
| **SECTION** | INTRO / MAIN A / MAIN B / FILL AB / FILL BA / ENDING | MAIN A | Sezione pattern |
| **TEMPO OVERRIDE** | 30-250 BPM | - | Tempo per il segmento |
| **MEASURE** | 001-999 | - | Misura start |

### 2.5 Chord track (Cd) entry

Display per chord changes. Ref: OM pag 39-46 (Chord entry).

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **ROOT** | C, C#, D, D#, E, F, F#, G, G#, A, A#, B | C | Root nota |
| **TYPE** | 28 tipi (M / M7 / M7(9) / 6 / add9 / 7 / 7(9) / 7(#11) / 7(13) / 7(♭9) / 7(♭13) / 7(#9) / 7sus4 / 7(#5) / m / m6 / m7 / m7(9) / m7(11) / m7(♭5) / mM7 / m_add9 / aug / dim / sus4 / --- / THRU) | M | Tipo chord |
| **ON BASS** | C-B | - | Bass inversion opzionale |
| **MEASURE:BEAT** | 001-999:1-n | - | Posizione chord change |

### 2.6 Tempo track (Tm) entry

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TEMPO** | 30-250 | 120 | BPM |
| **MEASURE:BEAT** | 001-999:1-n | - | Posizione tempo change |

Ref: OM pag 89-91.

---

## 3. PATTERN mode

### 3.1 Pagina principale

Mostra:
- Style number (Preset o U01-U64)
- Section corrente (INTRO/MAIN A/B/FILL AB/BA/ENDING)
- Pattern length (1-8 misure)
- Time signature (`1..16/16`, `1..16/8`, `1..8/4`)
- Tempo
- Track status 8 track (D1/D2/PC/BA/C1/C2/C3/C4)

Ref: OM pag 137-150 (Pattern mode overview).

### 3.2 Track mapping

| Slot pattern | Slot style | Channel PATT OUT 1~8 | Channel 9~16 |
|--------------|------------|----------------------|--------------|
| **D1** | RHY1 | 1 | 9 |
| **D2** | RHY2 | 2 | 10 |
| **PC** | PAD | 3 | 11 |
| **BA** | BASS | 4 | 12 |
| **C1** | CHD1 | 5 | 13 |
| **C2** | CHD2 | 6 | 14 |
| **C3** | PHR1 | 7 | 15 |
| **C4** | PHR2 | 8 | 16 |

Vedi [qy70-modes.md](qy70-modes.md).

### 3.3 Phrase selection

Premere `ENTER` su una track apre la phrase selection list.

#### Categorie phrase (12 tipi + filtri)

| Code | Descrizione | Track tipico |
|------|-------------|--------------|
| `Da` | Drum-a (Pop & Rock) | D1 |
| `Db` | Drum-b (Specific) | D2 |
| `Fa` | Drum Fill-a | D1/D2 FILL |
| `Fb` | Drum Fill-b | D1/D2 FILL |
| `PC` | Percussion | PC |
| `Ba` | Bass-a (Pop & Rock) | BA |
| `Bb` | Bass-b (Specific) | BA |
| `Ga` | Guitar Chord-a | C1/C2 |
| `Gb` | Guitar Chord-b | C1/C2 |
| `GR` | Guitar Riff | C3/C4 |
| `KC` | Keyboard Chord | C1/C2 |
| `KR` | Keyboard Riff | C3/C4 |
| `PD` | Pad | C2/C3 |
| `BR` | Brass | C3/C4 |
| `SE` | Sound Effects | C4 |

Totali: **4167 preset phrases** + **384 user phrase slots**. Ref: [qy70-preset-phrases.md](qy70-preset-phrases.md), OM pag 137-143, LB pag 14-39.

#### Phrase attributes (per slot pattern)

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **PHRASE NUMBER** | 0001-4167 (preset) / Us--001..Us--048 (user) | - | Ref alla phrase |
| **KEY** | C-B | C | Root per transposition |
| **TYPE** | Bypass / Bass / Chord 1 / Chord 2 / Parallel | - | Behavior con chord change |

Phrase Types: determinano re-armonizzazione con i chord changes. Vedi [qy70-preset-phrases.md](qy70-preset-phrases.md).

### 3.4 Pattern Record

Premere `REC` in Pattern mode.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TRACK** | D1/D2/PC/BA/C1/C2/C3/C4 | - | Track da registrare |
| **TYPE** | REPL / OVER / STEP | REPL | Modalità record |
| **Q.TIZE** | Off / 1/32 / 1/24 / 1/16 / 1/12 / 1/8 / 1/6 / 1/4 | Off | Record quantize |
| **METRONOME** | Off / Rec / Rec&Play / Always | Rec | - |

Ref: OM pag 145-150.

### 3.5 Pattern Length e Time Signature

Accessibile da Pattern main page.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **LENGTH** (INTRO) | 1-8 bar | 2 | Lunghezza sezione INTRO |
| **LENGTH** (MAIN A/B) | 1-8 bar | 2 | Lunghezza MAIN |
| **LENGTH** (FILL AB/BA) | 1 bar | 1 | Fill (fissato a 1 bar) |
| **LENGTH** (ENDING) | 1-8 bar | 2 | Lunghezza ENDING |
| **TIME SIG** | 1..16/16, 1..16/8, 1..8/4 | 4/4 | Time signature |

Ref: [qy70-modes.md](qy70-modes.md), OM pag 138.

### 3.6 Copy Section / Clear Section

Accessibile via `JOB` in Pattern mode (vedi [§7 Pattern Jobs](#72-pattern-jobs)).

---

## 4. VOICE mode

### 4.1 Voice mode in SONG

#### Mixer display (pag 59)

Display mixer on-screen per 16 track + master:

| Controllo | Range | Default | Note |
|-----------|-------|---------|------|
| **MUTE** (per track) | On/Off | Off | Mute track |
| **SOLO** (per track) | On/Off | Off | Solo isolato |
| **VOICE** (per track) | 519 voci XG + 20 drum kit | Piano 1 | Program/Bank select |
| **PAN** (per track) | L63..C..R63 | C (center) | Pan |
| **VOLUME** (per track) | 0-127 | 100 | Volume fader |
| **mst** (Master) | 0-127 | 127 | Master volume |
| **pat** (Pattern) | 0-127 | 100 | Pattern output level |

Ref: OM pag 59-66.

#### Voice selection list

Premere `ENTER` su voice slot.

**Categorie voci (21)**:

| Code | Categoria |
|------|-----------|
| `Pf` | Piano |
| `Cp` | Chromatic Percussion |
| `Or` | Organ |
| `Gt` | Guitar |
| `Ba` | Bass |
| `St` | Strings |
| `En` | Ensemble |
| `Br` | Brass |
| `Rd` | Reed |
| `Pi` | Pipe |
| `Ld` | Synth Lead |
| `Pd` | Synth Pad |
| `Fx` | Synth Effects |
| `Et` | Ethnic |
| `Pc` | Percussive |
| `Se` | Sound Effects |
| `Sfx` | XG SFX Kit |
| `Sfk` | SFX Kit |
| `Dr` | Drums |
| `Ds1` | Drum Kit 1 |
| `Ds2` | Drum Kit 2 |

Totale: **519 XG Normal + 20 Drum Kits**. Ref: [qy70-voice-list.md](qy70-voice-list.md), LB pag 3-9.

### 4.2 Voice Editing (normal voice)

Premere `EDIT` su voce selezionata.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **PB** (Pitch Bend Range) | -24 / +24 semitoni | +2 | Range pitch bend |
| **CUT** (Filter Cutoff) | -64 / +63 | 0 | Offset cutoff |
| **RES** (Filter Resonance) | -64 / +63 | 0 | Offset resonance |
| **A** (Attack) | -64 / +63 | 0 | EG attack rate offset |
| **D** (Decay) | -64 / +63 | 0 | EG decay rate offset |
| **R** (Release) | -64 / +63 | 0 | EG release rate offset |

Ref: OM pag 61-63.

### 4.3 Drum Edit (drum kit voice)

Attivo quando la track è drum (Ds1/Ds2/Ds3). Edit per-drum-note.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **NOTE** | 13-91 (0x0D-0x5B) | - | Nota drum selezionata |
| **PITCH** | -64 / +63 | 0 | Coarse pitch offset |
| **REV** (Reverb Send) | 0-127 | 40 | Reverb send per note |
| **VAR** (Variation Send) | 0-127 | 0 | Variation send per note |
| **PAN** | L63..C..R63 | C | Pan per note |
| **LVL** (Level) | 0-127 | 100 | Livello per note |
| **CUT** | -64 / +63 | 0 | Filter cutoff offset |
| **RES** | -64 / +63 | 0 | Filter resonance offset |
| **DECAY** | -64 / +63 | 0 | Decay offset |

Ref: OM pag 64-66, [qy70-drum-kits.md](qy70-drum-kits.md), [xg-drum-setup.md](xg-drum-setup.md).

### 4.4 Voice mode in PATTERN

Display mixer dedicato per pattern tracks D1/D2/PC/BA/C1-C4. **Senza master/pattern faders** (non applicabili in pattern context).

| Controllo | Range | Default | Note |
|-----------|-------|---------|------|
| **MUTE/SOLO** | On/Off | Off | Per ogni track |
| **VOICE** | 519 voci + 20 kit (Ds3 disponibile in Pattern) | - | Program/Bank |
| **PAN** | L63..C..R63 | C | Pan |
| **VOLUME** | 0-127 | 100 | Volume |

Effect Send display separato (REVERB/CHORUS/VARI./DRY) per track.

Ref: OM pag 151-154.

---

## 5. EFFECT mode

### 5.1 Effect blocks

3 blocchi effetto disponibili:

| Blocco | Scope | Editabile in PATTERN? |
|--------|-------|------------------------|
| **Reverb** | System (tutti i channel) | No (solo Song) |
| **Chorus** | System (tutti i channel) | No (solo Song) |
| **Variation** | System o Insertion | Si (in Pattern solo Variation) |

Ref: OM pag 32-35, [xg-effects.md](xg-effects.md).

### 5.2 Reverb settings

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TYPE** | Hall 1/2, Room 1/2/3, Stage 1/2, Plate, White Room, Tunnel, Canyon, Basement, Delay LCR, Delay LR, Echo, Cross Delay, Delay L/Delay R, Karaoke 1/2/3, Off | Hall 1 | Tipo reverb |
| **TIME** | 0-127 | 64 | Decay time |
| **DIFF** (Diffusion) | 0-10 | 8 | - |
| **INIT DLY** | 0-127 | 8 | Initial delay |
| **HPF CUT** | Thru / 22Hz-8kHz | Thru | HPF cutoff |
| **LPF CUT** | 1kHz-Thru | Thru | LPF cutoff |
| **RETURN** | 0-127 | 64 | Reverb return |
| **PAN** | L63..C..R63 | C | Reverb pan |
| **REV DELAY** | 0-127 | 0 | Pre-delay |
| **DENSITY** | 0-3 | 3 | Reflection density |
| **ER/REV BAL** | 0-127 | 64 | Early reflections vs reverb balance |
| **HI DAMP** | 0.1-1.0 | 1.0 | High frequency damp |
| **FB LEVEL** | -63..+63 | 0 | Feedback (echo types) |

Ref: OM pag 32-33, [xg-effects.md](xg-effects.md).

### 5.3 Chorus settings

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TYPE** | Chorus 1/2/3/4, Celeste 1/2/3/4, Flanger 1/2/3, Symphonic, Phaser 1/2, Off | Chorus 1 | Tipo chorus |
| **LFO FREQ** | 0-127 | - | Frequenza LFO |
| **LFO DEPTH** | 0-127 | - | Profondità LFO |
| **FEEDBACK** | 0-127 | - | - |
| **DELAY OFFSET** | 0-127 | - | - |
| **EQ LOW FREQ** | 32Hz-2kHz | - | EQ bassi |
| **EQ LOW GAIN** | -12..+12 dB | 0 | - |
| **EQ HIGH FREQ** | 500Hz-16kHz | - | EQ alti |
| **EQ HIGH GAIN** | -12..+12 dB | 0 | - |
| **DRY/WET** | D63..D=W..W63 | - | Balance |
| **RETURN** | 0-127 | 64 | - |
| **PAN** | L63..C..R63 | C | - |
| **SEND CHO TO REV** | 0-127 | 0 | Chorus → Reverb send |

Ref: OM pag 33-34.

### 5.4 Variation settings

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TYPE** | 43 tipi (Delay, Reverb Hall 1, Phaser 1, ecc.) | Delay LCR | Tipo variation |
| **CONNECT** | System / Insertion | System | Collegamento |
| **RETURN** | 0-127 | 64 | Return level |
| **PAN** | L63..C..R63 | C | Pan |
| **SEND VAR TO REV** | 0-127 | 0 | Var → Reverb send |
| **SEND VAR TO CHO** | 0-127 | 0 | Var → Chorus send |

Ref: OM pag 34-35, [xg-effects.md](xg-effects.md).

### 5.5 Effect Send display (per track)

Accessibile via `F3` in Voice mode.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **REVERB SEND** | 0-127 | 40 | - |
| **CHORUS SEND** | 0-127 | 0 | - |
| **VARI. SEND** | 0-127 | 0 | - |
| **DRY LEVEL** | 0-127 | 127 | - |

---

## 6. UTILITY mode

Utility mode ha 4 sub-sezioni `F1-F4`. Ref: OM pag 179-195, [qy700-utility-mode.md](qy700-utility-mode.md) (analogo).

### 6.1 F1 — System

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **Master Tune** | -102.4..+102.3 cent | 0 | Tuning globale |
| **Transpose** | -24..+24 semitoni | 0 | Transpose globale |
| **Master Volume** | 0-127 | 127 | - |
| **Contrast** | 1-8 | 4 | Contrasto display |
| **Click Out** | Int / Int+Midi / Midi | Int | Destinazione metronomo |
| **Click Vol** | 0-127 | 100 | Volume metronomo |
| **Beep** | Off / On | On | Beep tasti |
| **Battery** | - | - | Indicatore livello batteria |

### 6.2 F2 — MIDI

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **Device Number** | 1-16, All, Off | All | Device ID per SysEx |
| **MIDI Sync** | Internal / External / Auto / MIDI | Internal | Sync MIDI clock |
| **Echo Back** | Off / On | On | Thru MIDI IN → OUT |
| **Local** | Off / On | On | Local control |
| **SysEx RX** | Off / On | On | Ricezione SysEx |
| **Bulk RX** | Off / On | On | Ricezione bulk dump |
| **Bulk Protect** | Off / On | Off | Protezione bulk |
| **PATT OUT 1..8** | 1-16 | 1-8 | Channel per pattern track 1-8 (D1-C4) |
| **MULTI REC** | Off / 1-16 | Off | Multi-channel record enable |
| **Receive Ch** | 1-16 / Off | Off | Ricezione per track (Song mode) |

**Tabella defaults PATT OUT** (vedi [qy70-modes.md](qy70-modes.md)):
- PATT OUT 1~8: D1=1, D2=2, PC=3, BA=4, C1=5, C2=6, C3=7, C4=8
- PATT OUT 9~16: D1=9, D2=10, PC=11, BA=12, C1=13, C2=14, C3=15, C4=16

Ref: OM pag 182-188, [midi-setup.md](midi-setup.md).

### 6.3 F3 — Filter (MIDI Filter)

Filtri RX/TX per tipologia di messaggio MIDI.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **Note RX/TX** | On/Off | On | Filtra Note On/Off |
| **PB RX/TX** | On/Off | On | Pitch Bend |
| **CC RX/TX** | On/Off | On | Control Change |
| **PC RX/TX** | On/Off | On | Program Change |
| **AT RX/TX** | On/Off | On | Aftertouch |
| **Excl RX/TX** | On/Off | On | System Exclusive |
| **Common RX/TX** | On/Off | On | System Common |
| **Realtime RX/TX** | On/Off | On | System Realtime |

### 6.4 F4 — Fingered Zone / Bulk

#### Fingered Zone (split key per chord detect)

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **Fingered Zone Lower** | C-2..G8 | C-2 | Nota inferiore range chord detect |
| **Fingered Zone Upper** | C-2..G8 | B2 | Nota superiore range chord detect |

#### Bulk Dump sub-menu

| Voce | Note |
|------|------|
| **All Bulk Dump** | Dump tutti i dati interni |
| **Song Bulk Dump** | Dump singola song |
| **Pattern Bulk Dump** | Dump singolo pattern (AL=0x7E edit buffer, 0x00-0x3F slot user) |
| **Voice Bulk Dump** | Dump voice edit data |
| **System Bulk Dump** | Dump settings sistema |

Sequenza SysEx richiesta (vedi [CLAUDE.md](../CLAUDE.md) e [qy70-bulk-dump.md](qy70-bulk-dump.md)):
1. Init: `F0 43 10 5F 00 00 00 01 F7`
2. Dump request: `F0 43 20 5F 02 7E AL F7`
3. Close: `F0 43 10 5F 00 00 00 00 F7`

Ref: OM pag 189-195.

---

## 7. JOB mode

### 7.1 Song Jobs (25 totali, Job 00-24)

Accessibili via `JOB` in Song mode. Organizzati in 4 categorie.

#### Event Jobs

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **00** | Undo / Redo | - | Annulla/ripeti ultima operazione |
| **01** | Quantize | TR, FROM M, TO M, Note Range, VALUE (1/32..1/4 + swing), STRENGTH (0-100%), SWING (50-75%), GATE TIME (0-200%), VELOCITY (0-200%) | Quantize puntuale |
| **02** | Modify Velocity | TR, FROM M, TO M, Note Range, RATE (0-200%), OFFSET (-99..+99) | Modifica velocity |
| **03** | Modify Gate Time | TR, FROM M, TO M, Note Range, RATE (0-200%), OFFSET (-9999..+9999 clock) | Modifica gate |
| **04** | Crescendo | TR, FROM M, TO M, Note Range, RANGE (-99..+99) | Crescendo/decrescendo velocity |
| **05** | Transpose | TR, FROM M, TO M, Note Range, VALUE (-127..+127 semitoni) | Transpose note |
| **06** | Shift Clock | TR, FROM M, TO M, VALUE (-9999..+9999 clock) | Sposta tutti gli eventi |
| **07** | Chord Sort | TR, FROM M, TO M | Ordina note chord per pitch |
| **08** | Chord Separate | TR, FROM M, TO M, VALUE (0-999 clock) | Separa note chord |
| **09** | Copy Event | SRC TR, DST TR, FROM M, TO M, TO M DST | Copia eventi tra track |
| **10** | Erase Event | TR, FROM M, TO M, Event Type | Cancella eventi per tipo |
| **11** | Extract Event | SRC TR, DST TR, FROM M, TO M, Event Type | Estrai eventi specifici |
| **12** | Create Continuous | TR, FROM M, TO M, Event Type, START VALUE, END VALUE, CLOCK STEP | Crea eventi continui (es. volume fade) |
| **13** | Thin Out | TR, FROM M, TO M, Event Type, STEP (clock) | Decima eventi |
| **14** | Time Stretch | TR, FROM M, TO M, RATE (25-400%) | Stretch temporale |

Ref: OM pag 89-108.

#### Measure Jobs

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **15** | Create Measure | FROM M, COUNT, METER | Inserisce misure vuote |
| **16** | Delete Measure | FROM M, COUNT | Rimuove misure |

#### Track Jobs

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **17** | Copy Track | SRC TR, DST TR | Copia track completa |
| **18** | Mix Track | SRC TR, DST TR | Merge eventi track |
| **19** | Clear Track | TR | Svuota track |
| **20** | Expand Backing | SRC TR (Pt/Cd), DST TR | Espande pattern track in eventi note su track normale |
| **21** | Normalize | TR | Rende Play Effects (groove/drum table) permanenti |

#### Song Jobs

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **22** | Copy Song | SRC, DST | Duplica song |
| **23** | Clear Song | SONG | Cancella song intera |
| **24** | Song Name | 10 caratteri | Nome song |

### 7.2 Pattern Jobs (24 totali, Job 00-23)

Accessibili via `JOB` in Pattern mode. Organizzati in 4 categorie.

#### Event Jobs (per Phrase)

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **00** | Undo / Redo | - | Annulla/ripeti |
| **01** | Quantize | TR, FROM M, TO M, Note Range, VALUE, STRENGTH, SWING, GATE TIME, VELOCITY | Come Song Job 01 |
| **02** | Modify Velocity | TR, FROM M, TO M, Note Range, RATE, OFFSET | Come Song Job 02 |
| **03** | Modify Gate Time | TR, FROM M, TO M, Note Range, RATE, OFFSET | Come Song Job 03 |
| **04** | Crescendo | TR, FROM M, TO M, Note Range, RANGE | Come Song Job 04 |
| **05** | Transpose | TR, FROM M, TO M, Note Range, VALUE | Come Song Job 05 |
| **06** | Shift Clock | TR, FROM M, TO M, VALUE | Come Song Job 06 |
| **07** | Chord Sort | TR, FROM M, TO M | Come Song Job 07 |
| **08** | Chord Separate | TR, FROM M, TO M, VALUE | Come Song Job 08 |
| **09** | Copy Event | SRC, DST, FROM M, TO M | Come Song Job 09 |
| **10** | Erase Event | TR, FROM M, TO M, Event Type | Come Song Job 10 |
| **11** | Extract Event | SRC, DST, FROM M, TO M, Event Type | Come Song Job 11 |
| **12** | Create Continuous | TR, FROM M, TO M, Event Type, START, END, STEP | Come Song Job 12 |
| **13** | Thin Out | TR, FROM M, TO M, Event Type, STEP | Come Song Job 13 |
| **14** | Time Stretch | TR, FROM M, TO M, RATE | Come Song Job 14 |

Ref: OM pag 159-166.

#### Phrase Jobs

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **15** | Copy Phrase | SRC (pattern+section+track), DST | Copia phrase |
| **16** | Get Phrase | PRESET/USER NUMBER, DST SLOT | Carica phrase da library |
| **17** | Put Phrase | SRC SLOT, USER SLOT DST | Salva phrase in user slot |

#### Track Jobs

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **18** | Copy Track | SRC TR, DST TR | Copia track pattern |
| **19** | Mix Track | SRC, DST | Merge track |
| **20** | Clear Track | TR | Svuota track |

#### Pattern Jobs

| # | Nome | Parametri | Note |
|---|------|-----------|------|
| **21** | Copy Pattern | SRC STYLE, DST STYLE | Duplica style |
| **22** | Clear Pattern | STYLE, SECTION (o All) | Svuota style/section |
| **23** | Style Name | 8 caratteri | Nome user style |

Ref: OM pag 157-175.

### 7.3 Voice Jobs (contestuali in Voice mode)

| Job | Note |
|-----|------|
| **Initialize Voice** | Resetta voice edit a default |
| **Copy Voice** | Copia voice edit tra slot |

### 7.4 Effect Jobs (contestuali in Effect mode)

| Job | Note |
|-----|------|
| **Initialize Effect** | Reset a default |
| **Copy Effect** | Copia settings effect |

---

## 8. EDIT mode

Event Edit: editing nota-per-nota degli eventi di una track. Premere `EDIT`.

### 8.1 Event list display

Mostra eventi ordinati per timestamp:

| Colonna | Range | Note |
|---------|-------|------|
| **MEAS:BEAT:CLOCK** | 001:1:000..999:n:479 | Timestamp evento |
| **EVENT TYPE** | Note / CC / PC / PB / AT / Excl / Sy(sEx) / Tempo / Chord / PatRef | Tipo evento |
| **VALUE 1** | Event-dep | Nota, CC#, PC#, ecc. |
| **VALUE 2** | Event-dep | Velocity, CC value, ecc. |
| **GATE / DUR** | 0-9999 clock | Durata (per note) |

### 8.2 Event types editabili

| Type | Fields | Note |
|------|--------|------|
| **Note** | Note (C-2..G8), Velocity (1-127), Gate (0-9999) | Nota MIDI |
| **CC** | Controller # (0-127), Value (0-127) | Control Change |
| **PC** | Program # (1-128) + Bank MSB/LSB | Program Change |
| **PB** | Value (-8192..+8191) | Pitch Bend |
| **AT** | Value (0-127) | Aftertouch (channel o poly) |
| **Excl** | Raw hex dump | System Exclusive custom |
| **RPN/NRPN** | MSB (0-127), LSB (0-127), Data MSB/LSB | Registered/Non-Registered Parameters |
| **Tempo** (Tm track) | BPM (30-250) | Tempo change |
| **Chord** (Cd track) | Root, Type, On Bass | Chord change |
| **PatRef** (Pt track) | Style, Section | Pattern reference |

### 8.3 Function keys Edit mode

| F-key | Funzione |
|-------|----------|
| `F1` | INSERT — inserisci nuovo evento |
| `F2` | DELETE — cancella evento corrente |
| `F3` | COPY / CUT — copia/taglia selezione |
| `F4` | PASTE — incolla nel clipboard event |

Ref: OM pag 109-122 (Event Edit in Song), 167-170 (Event Edit in Pattern).

---

## 9. Sotto-modalità trasversali

### 9.1 Play Effects (runtime, non-persistent)

Applicabili sia in Song che Pattern mode via `F4`.

#### Groove Quantization

**100 preset templates** (Preset 001-100). Ref: [qy70-groove-templates.md](qy70-groove-templates.md), OM pag 96-98, 155-156.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TEMPLATE** | 001-100 | 001 | Template number |
| **TIMING** | 000-200 | 100 | 100=originale, <100=relaxed, >100=pushed |
| **VELOC** | 000-200 | 100 | 100=originale, <100=smorza, >100=enfatizza |

**Persistenza**: solo via Song Job 21 (Normalize). Non inclusi nel dump SysEx.

#### Drum Table Remapping

**24 opzioni** in **6 categorie** (preset).

| Categoria | Opzioni tipiche |
|-----------|-----------------|
| **Snare** | Soft Snare, Medium Snare, Hard Snare, Rim Shot, Brush Snare |
| **Kick** | Soft Kick, Medium Kick, Hard Kick, Mute Kick |
| **Hi-Hat** | Closed/Open mix variants |
| **Cymbal** | Crash 1/2, Ride 1/2, China variants |
| **Tom** | Tom 1-4 variants |
| **Percussion** | Claps, Cowbell, Tamburine variants |

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **TABLE** | 01-24 | - | Tabella drum remap |
| **TRACK** | D1/D2/PC | - | Track target |

Ref: [qy70-groove-templates.md](qy70-groove-templates.md) (sez. Drum Table Remapping), OM pag 99-100, 156.

### 9.2 Punch In/Out record

Accessibile via `REC + SHIFT` o da Record Setup dialog con `TYPE=PUNCH`.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **PUNCH IN M:B** | 001:1..999:n | - | Punto start record |
| **PUNCH OUT M:B** | 001:1..999:n | - | Punto stop record |
| **REHEARSAL** | On/Off | Off | Rehearsal mode (no write) |

Ref: OM pag 78-81.

### 9.3 Step Record

Attivato con `REC` + `TYPE=STEP`.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **STEP TIME** | 1/32..1/1, dotted, triplets | 1/16 | Durata step |
| **GATE TIME** | 1-100% | 80% | Durata nota relativa a step |
| **VELOCITY** | 1-127, Off (playing vel) | 100 | Velocity input |
| **REST** | F-key | - | Inserisce pausa |
| **TIE** | F-key | - | Lega nota precedente |
| **CLEAR** | F-key | - | Cancella step |

Ref: OM pag 81-85.

### 9.4 Multi Record (MIDI input multi-canale)

Config in Utility F2 `MULTI REC`. Quando attivo in Song mode record, ogni channel MIDI viene separato su track corrispondente (1→Track 1, 2→Track 2, ecc.).

Ref: OM pag 76-78, 186.

### 9.5 Demo Playback

Premere `DEMO` o selezionare song 21-23.

| Demo | Title |
|------|-------|
| **21** | Demo Song 1 |
| **22** | Demo Song 2 |
| **23** | Demo Song 3 |

Ref: OM pag 14-16.

### 9.6 Chain Play (Song concatenation)

Riproduzione sequenziale di più song.

| Parametro | Range | Default | Note |
|-----------|-------|---------|------|
| **CHAIN** | Off / 01-20 sequence | Off | Lista song in chain |
| **REPEAT** | On/Off | Off | Loop chain |

Ref: OM pag 36-38.

---

## Cross-references

- [qy70-device.md](qy70-device.md) — hardware specs
- [qy70-modes.md](qy70-modes.md) — overview dei 7 modi (parent doc)
- [qy70-voice-list.md](qy70-voice-list.md) — 519 voci XG architecture
- [qy70-drum-kits.md](qy70-drum-kits.md) — 20 drum kit, mapping note 13-91
- [qy70-preset-phrases.md](qy70-preset-phrases.md) — 4167 preset + 384 user phrase, 12 categorie
- [qy70-groove-templates.md](qy70-groove-templates.md) — 100 template groove quantize + drum table
- [qy70-bulk-dump.md](qy70-bulk-dump.md) — procedura bulk dump SysEx
- [midi-setup.md](midi-setup.md) — PATT OUT channel assignment
- [xg-system.md](xg-system.md), [xg-multi-part.md](xg-multi-part.md), [xg-effects.md](xg-effects.md), [xg-drum-setup.md](xg-drum-setup.md) — XG protocol per tone generator
- [pattern-editor.md](pattern-editor.md) — CLI editor Pipeline B

## Riferimenti manuale

- **QY70_OWNERS_MANUAL.PDF**:
  - Panoramica modi: pag 3-12
  - Demo: pag 14-16
  - Song playback / Chain: pag 30-38, 36-38
  - Easy Accompaniment (Chord entry): pag 39-46
  - Pattern track entry in Song: pag 43-50
  - Voice mode (Song): pag 59-66
  - Voice Editing / Drum Edit: pag 61-66
  - Realtime Record: pag 67-78
  - Punch In/Out: pag 78-81
  - Step Record: pag 81-85
  - Song track structure / Tempo track: pag 86-91
  - Song Jobs: pag 89-108
  - Event Edit (Song): pag 109-122
  - Pattern mode overview / phrase selection: pag 137-150
  - Pattern record: pag 145-150
  - Pattern Voice / Effect Send / Voice Edit: pag 151-156
  - Pattern Play Effects: pag 155-156
  - Pattern Jobs: pag 157-175
  - Event Edit (Pattern): pag 167-170
  - Utility mode: pag 179-195
  - Groove templates / Drum Table: pag 96-100, 133, 155-156
  - Phrase Types: pag 147

- **QY70_LIST_BOOK.PDF**:
  - Voice list: pag 3-9
  - Drum kits: pag 10-14
  - Preset phrases: pag 14-39
