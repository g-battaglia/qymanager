# QY700 Menu Tree — Mappa completa della navigazione

Mappa gerarchica **completa e integrale** dei menu del Yamaha QY700, dalla pressione di un tasto MODE fino a ogni parametro editabile. Sorgenti: `manual/QY700/QY700_MANUAL/*.txt` (capitoli 1-7) + `QY700_REFERENCE_LISTING.pdf`.

Convenzioni:
- Nomi display/parametri in **inglese** (come riportati sul pannello QY700).
- Descrizioni in **italiano**.
- Range/Default/Note nelle tabelle (default segnati come `—` quando non documentati nel manuale).
- Cross-link alle pagine wiki esistenti dove applicabile.

Indice generale:
1. [Controlli globali pannello](#0-controlli-globali-pannello)
2. [SONG Mode](#1-song-mode)
3. [PATTERN Mode](#2-pattern-mode)
4. [VOICE Mode](#3-voice-mode)
5. [EFFECT Mode](#4-effect-mode)
6. [UTILITY Mode](#5-utility-mode)
7. [DISK Mode](#6-disk-mode)
8. [Song Jobs (25)](#7-song-jobs)
9. [Pattern Jobs (31)](#8-pattern-jobs)

---

## 0. Controlli globali pannello

Ref: `QY700_MANUAL/03_SETUP.txt`.

### Tasti MODE (ingresso ai modi principali)

| Tasto | Modo | Note |
|---|---|---|
| `[SONG]` | Song Mode | Torna sempre alla schermata SONG PLAY |
| `[PATTERN]` | Pattern Mode | Torna sempre alla schermata PATCH |
| `[VOICE]` | Voice Mode | Torna all'ultima pagina visitata (Mixer/Tune/VoicEdit/DrSEdit) |
| `[EFFECT]` | Effect Mode | Torna all'ultima pagina (Connect/Reverb/Chorus/Vari.) |
| `[UTILITY]` | Utility Mode | Ultima pagina visitata |
| `[DISK]` | Disk Mode | Pagina Save/Load/Rename/Delete/Format |

### Tasti funzione e direct

| Tasto | Funzione |
|---|---|
| `[F1]`–`[F6]` | Sottomenu contestuali (il ruolo cambia per modo/schermata) |
| `[D1]`–`[D5]` | Direct cursor keys: spostano il cursore su sezioni della schermata / selezione tipo dato in DISK |
| `[SHIFT]` | Modificatore per combinazioni (es. `SHIFT+SOLO` = multi-SOLO, `SHIFT+UNDO/REDO` shortcut) |
| `[OCT UP]` / `[OCT DOWN]` | Ottava della microkeyboard |
| `[MUTE]` / `[SOLO]` | Mute/Solo track (vale anche come REST/TIE in step record) |
| `[TRACK UP]` / `[TRACK DOWN]` | Selezione traccia |
| `[RECORDING]` | Ingresso in Recording Standby |
| `[JOB]` | Ingresso menu Job (Song Jobs o Pattern Jobs a seconda del modo) |
| `[EDIT]` | Ingresso Song Edit / Phrase Edit |
| `[PLAY]` / `[STOP]` / `[TOP]` / `[REWIND]` / `[FORWARD]` | Trasporto sequencer |
| `[ENTER]` | Conferma valore/esegui job |
| `[EXIT]` | Torna alla schermata precedente |
| Data dial / shuttle dial / `[Increment]` / `[Decrement]` / keypad numerico | Edit valore |

### Connettori pannello posteriore
- `FOOT SW`: funzione configurabile (vedi `UTILITY → System → Footswitch`).
- `MIDI IN-A/B`, `MIDI OUT-A/B`, `MIDI THRU`.
- `SUSTAIN` (separato dal foot switch programmabile).
- `PHONES`, `L/R OUT`.

---

## 1. SONG Mode

Ref: `QY700_MANUAL/06_2_1SongMode.txt`, `07_2_2SongMode.txt`. Link correlato: [qy700-song-mode.md](qy700-song-mode.md).

Struttura: 20 songs, ciascuna con 32 sequence tracks + PATTERN / CHORD / TEMPO tracks.

```
[SONG]
  ├─ SONG PLAY (top page)              ← mixer/transport principale
  ├─ [F1] Play Effects
  │    ├─ [F1] Groove Quantize (Song Play Effects)
  │    ├─ [F2] Clock Shift / Gate Time / Velocity
  │    └─ [F3] Transpose / Drum Table
  ├─ [F2] Track View
  ├─ [F3] Output Channels
  ├─ [F4] Drum Table Edit
  │    ├─ Replacement list
  │    └─ Velocity rate
  ├─ [RECORDING] Recording Standby
  │    ├─ [F4] Replace (realtime)
  │    ├─ [F5] Overdub (realtime)
  │    └─ [F6] Step
  ├─ [EDIT] Song Edit
  │    ├─ [F1] Graphic / Event list (toggle)
  │    ├─ [F2] XG View
  │    ├─ [F3] Track Name
  │    ├─ [F4] View Filter
  │    ├─ [F5] Delete
  │    └─ [F6] Insert
  └─ [JOB] Song Job menu (25 jobs)    ← vedi sezione 7
```

### 1.1 SONG PLAY (top page)

| # | Parameter | Range | Default | Note |
|---|---|---|---|---|
| 1 | Song number | 01–20 | 01 | Seleziona la song corrente |
| 2 | Song name | fino a 12 char | `********` | Assegnato con Song Job 25 |
| 3 | Tempo | 30.0–300.0 | 120.0 | BPM con un decimale |
| 4 | Location | 001:1 a 999:8 | 001:1 | Measure:beat (clicca con D-pad) |
| 5 | Volume | 0–127 | 100 | Master song volume |
| 6 | Meter | 1/16–32/16, 1/8–32/8, 1/4–16/4 | 4/4 | Time signature |
| 7 | Click | Off / Rec / Play / All | Rec | Metronomo |
| 8 | Count | 0–8 | 1 | Battute di pre-count in rec |
| 9 | Track level | 0–127 | — | Per-track (32) |
| 10 | Track mute / solo | M / S / blank | blank | — |
| 11 | Pattern setup switch | On / Off | On | Se On applica Pattern voice in SONG |
| 12 | Fingered Chord | Off / FINGRD | Off | Collega a `UTILITY → FngZone` |
| 13 | Song loop | Off / On | Off | Ripetizione della song |

Cross-link: see [Chord Track](qy700-chord-types.md), [Groove Templates](qy700-groove-templates.md).

### 1.2 Play Effects

#### [F1] Groove Quantize (14 parametri)

| # | Parameter | Range | Default | Note |
|---|---|---|---|---|
| 1 | Track | 1–32 | 1 | — |
| 2 | Groove template | 001–100 (preset) + user | 001 | 100 preset; vedi [groove templates](qy700-groove-templates.md) |
| 3 | Timing | 0–200% | 100% | Intensità quantizzazione timing |
| 4 | Velocity | 0–200% | 100% | Intensità quantizzazione velocity |
| 5 | Gate time | 0–200% | 100% | Scala durata note |
| 6 | Swing rate | 50–83% (varia con valore q) | 50% | Dipende da quantizing value |
| 7 | Strength | 0–100% | 100% | Forza del quantize |
| 8 | Sensitivity | −100 / +000 / +100% | 0 | Soglia nota quantizzata |
| 9 | Swing gate | 0–200% | 100% | Durata su note swing |
| 10 | Swing velocity | 0–200% | 100% | Velocity su note swing |
| 11 | Quantizing value | 32nd–1/4, con triplets e combinati | 16th | Base quantize |
| 12 | Template source | Preset / User | Preset | — |
| 13 | Apply range | measure:beat – measure:beat | song intera | — |
| 14 | Bypass | Off / On | Off | Disabilita groove senza perdere setting |

#### [F2] Clock Shift / Gate Time / Velocity

| # | Parameter | Range | Default |
|---|---|---|---|
| 15 | Clock Shift | −9999 … +9999 clock (480/beat) | 0 |
| 16 | Gate Time offset | 0–200% (rate) + −9999…+9999 (offset) | 100% / 0 |
| 17 | Velocity offset | 0–200% (rate) + −99…+99 (offset) | 100% / 0 |
| 18 | Track target | 1–32 / All | All |

#### [F3] Transpose + Drum Table

| # | Parameter | Range | Default |
|---|---|---|---|
| 19 | Drum Table switch | Off / On | Off |
| 20 | Transpose | −99…+99 semitones | 0 |

### 1.3 Track View / Output Channels

```
[SONG] / [F2] Track View
  └─ visual mute/solo/voice/level 32 tracce + PATTERN/CHORD/TEMPO
[SONG] / [F3] Output Channels
  ├─ TO TG         (per traccia: Off, 1–32)
  ├─ MIDI OUT-A    (Off, 1–16)
  └─ MIDI OUT-B    (Off, 1–16)
```

### 1.4 Drum Table Edit

| # | Parameter | Range | Note |
|---|---|---|---|
| 21 | Replacement list | up to 8 entries: Source note → Destination note | C-2…G8 |
| 22 | Velocity rate | 0–200% per ogni entry | 100% |

### 1.5 Recording Standby

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | Track | 1–32 / PATTERN / CHORD / TEMPO | 1 |
| 2 | Type (realtime) | Replace / Overdub | Replace |
| 3 | Mode | Realtime / Step / Punch | Realtime |
| 4 | Punch In/Out points | measure:beat | — |
| 5 | Count | 0–8 | 1 |
| 6 | Click | Off/Rec/Play/All | Rec |
| 7 | Tempo | 30.0–300.0 | 120.0 |
| 8 | Meter | vedi SONG PLAY | 4/4 |

Step recording (tasti dedicati):
- `[D1]` location, `[D2]` step time, `[D3]` velocity, `[D4]` gate time
- Keypad: `0` rest, `1` 32nd, `2` 16th-trip, `3` 16th, `4` 8th-trip, `5` 8th, `6` 1/4-trip, `7` 1/4, `8` 1/2, `9` whole + dots/ties
- `[F5] BkDelete`, `[F6] Delete`
- `[MUTE]`=REST, `[SOLO]`=TIE

### 1.6 Song Edit

| Tasto | Funzione |
|---|---|
| `[F1]` | Toggle Graphic / Event List |
| `[F2] XG View` | Visualizzazione/edit di parametri XG (system, part, drum, effects) come eventi editabili |
| `[F3] TrName` | Assegna nome 12 char alla traccia |
| `[F4] View Filter` | Filtra per tipo evento: Note, PB, PC, CC(n), CAT, PAT, Excl, Tmp |
| `[F5] Delete` | Cancella eventi selezionati |
| `[F6] Insert` | Inserisce evento (tipo + argomenti + time) |

Event types editabili (event list):
`Note` (pitch C-2–G8, velocity 1–127, gate 0000–9999), `Bend` (−8192…+8191), `PC` (0–127), `CC` (0–127 / 0–127), `ChAT` (0–127), `KeyAT` (C-2–G8 / 0–127), `Excl`, `Tmp` (30.0–300.0).

### 1.7 Output Channels — assegnazione dettagliata

Per ciascuna delle 32 tracce: `TO TG` (tone generator interno, 1–32 o Off), `MIDI OUT-A` (1–16 o Off), `MIDI OUT-B` (1–16 o Off). Usato anche in PATTERN voice setup (il Pattern Setup switch riusa questi valori).

---

## 2. PATTERN Mode

Ref: `QY700_MANUAL/10_5_1PatternMode.txt`, `11_5_2PatternMode.txt`. Link: [qy700-pattern-mode.md](qy700-pattern-mode.md), [qy700-phrase-lists.md](qy700-phrase-lists.md).

Struttura: **64 styles × 8 sections (A–H) = 512 pattern**, 16 tracks ciascuno, 3876 preset phrases + 99 user phrases per style.

```
[PATTERN]
  ├─ PATCH (top page)
  │    ├─ [F1] Phrase Table
  │    ├─ [F2] Voice
  │    │     ├─ [F1] Mixer
  │    │     ├─ [F2] Voice Edit
  │    │     └─ [F3] Drum Setup-3 Edit
  │    ├─ [F3] Pattern Effects
  │    │     ├─ [F1] Connection
  │    │     ├─ [F2] Reverb Edit
  │    │     ├─ [F3] Chorus Edit
  │    │     └─ [F4] Variation Edit
  │    ├─ [F4] Play Effects
  │    │     ├─ [F1] Groove Quantize
  │    │     ├─ [F2] Clock Shift / Gate / Vel
  │    │     └─ [F3] Transpose (+ Inversion Transposition, Open Harmony)
  │    └─ [F5/F6] switch tra sottomodi
  ├─ [RECORDING] Phrase Recording Standby
  │    ├─ [F4] Replace
  │    ├─ [F5] Overdub
  │    └─ [F6] Step
  ├─ [EDIT] Phrase Edit
  │    ├─ [F1] Graphic / Event List toggle
  │    ├─ [F2] XG View
  │    ├─ [F4] View Filter
  │    ├─ [F5] Delete
  │    └─ [F6] Insert
  └─ [JOB] Pattern Job menu (31 jobs 00–30) ← vedi sezione 8
```

### 2.1 PATCH (top page) — 15 parametri

| # | Parameter | Range | Default | Note |
|---|---|---|---|---|
| 1 | Style | 01–64 | 01 | — |
| 2 | Section | A–H | A | Main A/B, Intro, Ending, Fill In (variabile per style) |
| 3 | Section Connection | Pattern Chain (A→B, ecc.) | — | Auto-accomp routing |
| 4 | Chord | root C…B + type (29 tipi inclusi THRU) | C M | Vedi [chord types](qy700-chord-types.md) |
| 5 | Fingered switch | Off / On | Off | Abilita chord detection da keyboard |
| 6 | Measure | 001–pattern length | 001 | — |
| 7 | Length | 001–256 | 4 | Lunghezza pattern (max 256) |
| 8 | Tempo | 30.0–300.0 | 120.0 | — |
| 9 | Meter | come SONG | 4/4 | — |
| 10 | Click | Off/Rec/Play/All | Rec | — |
| 11 | Track/Measure matrix | 16 × length | — | Box display |
| 12 | Scale time | 50–200% | 100% | Time stretch pattern |
| 13 | Beat shift | −1919…+1919 clock | 0 | Offset temporale globale |
| 14 | Phrase number | 00001–ultimo preset + US01–US99 | — | Preset 3876 + 99 user |
| 15 | Phrase category / beat | categoria + meter della phrase | — | Filtro selezione phrase |

### 2.2 Phrase Table (8 parametri)

| # | Parameter | Range | Default | Note |
|---|---|---|---|---|
| 1 | Phrase Type | Mldy1, Mldy2, Chrd1, Chrd2, Bass, Bypas, Para | Mldy1 | Converte la phrase secondo accordo |
| 2 | Retrigger | Off / On | Off | Se On: mantiene phrase al cambio accordo |
| 3 | Low limit | C-2…G8 | C-2 | Range pitch dopo transpose |
| 4 | High limit | C-1…G8 | G8 | — |
| 5 | High key | C…B | B | Upper root cap (Mldy1/Chrd1/Bass) |
| 6 | Voice category | Normal / SFX Voice / SFX Kit / Drum / DrumSetup-1 / DrumSetup-2 | Normal | — |
| 7 | Voice program+bank | PC 001–128, LSB 000–127 | — | Nome visualizzato |
| 8 | Source chord | Root C–B + type (29) | C M | Accordo sorgente della phrase |

### 2.3 Pattern Voice submode — `[F2] Voice`

#### [F1] Mixer (13 parametri per track)

| # | Parameter | Range | Note |
|---|---|---|---|
| 1 | Data display | view-only | Mostra voice / valore parametro |
| 2 | Location | 001–256 | Measure corrente |
| 3 | Track number | 1–16 | Evidenziata |
| 4 | Track status | M / S / blank | Mute/Solo |
| 5 | Voice select | Phr / Pat | Phrase-voice o Pattern-voice |
| 6 | Voice category | Normal / SFX / SFX Kit / Drum / DrumSetup-1 / DrumSetup-2 | — |
| 7 | Program # | 001–128 | — |
| 8 | Bank # | 000–101 (valori validi variabili) | Solo per Normal |
| 9 | Reverb send | 0–127 | — |
| 10 | Chorus send | 0–127 | — |
| 11 | Variation switch / send | On/Off (Insertion) oppure 0–127 (System) | Dipende da Variation Mode |
| 12 | Pan | Random, L63–C–R63 | — |
| 13 | Volume | 0–127 | — |

Shortcut: `[SHIFT]+dial/num` = stessa variazione/valore su tutti i part.

#### [F2] Voice Edit (5 parametri offset, per track)

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | Filter Cutoff | −64…+63 | 0 |
| 2 | Filter Resonance | −64…+63 | 0 |
| 3 | EG Attack | −64…+63 | 0 |
| 4 | EG Decay | −64…+63 | 0 |
| 5 | EG Release | −64…+63 | 0 |

#### [F3] Drum Setup-3 Edit (13 parametri per nota, disponibile se categoria=DrumSetup-3)

| # | Parameter | Range | Note |
|---|---|---|---|
| 1 | Data display | voice name + program# | view-only |
| 2 | Location | 001–pattern length | — |
| 3 | Note | C-1–C5 | Selezione instrument |
| 4 | Drum Kit | 001 StandKit, 002 Stnd2Kit, 009 Room, 017 Rock, 025 ElectKit, 026 AnalgKit, 033 Jazz, 041 BrushKit, 049 ClascKit, 001 SFX1 Kit, 002 SFX2 Kit | — |
| 5 | Reverb send | 0–127 | — |
| 6 | Chorus send | 0–127 | — |
| 7 | Variation send | 0–127 | — |
| 8 | Pan | Random, L63–C–R63 | — |
| 9 | Level | 0–127 | — |
| 10 | Pitch fine | −64…+63 | 1 cent step |
| 11 | Pitch coarse | −64…+63 | semitone step |
| 12 | Filter Cutoff / Resonance | −64…+63 | offset |
| 13 | EG Attack / Decay-1 / Decay-2 | −64…+63 | offset |

### 2.4 Pattern Effects — `[F3] Effect`

Identica struttura a EFFECT Mode (vedi §4). Differenza: si applica per style (tutte le 8 sections condividono le impostazioni del style).

#### [F1] Connection (14 parametri)

| # | Parameter | Range |
|---|---|---|
| 1 | Data display | view-only |
| 2 | Variation Mode | Insertion / System |
| 3 | Reverb Type | 11 tipi (vedi §4.1) |
| 4 | Reverb Return | 0–127 |
| 5 | Reverb Pan | L63–C–R63 |
| 6 | Chorus Type | 11 tipi |
| 7 | Chorus Return | 0–127 |
| 8 | Chorus Pan | L63–C–R63 |
| 9 | Chorus→Reverb send | 0–127 |
| 10 | Variation Type | 43 tipi |
| 11 | Variation Return | 0–127 (solo System) |
| 12 | Variation Pan | L63–C–R63 (solo System) |
| 13 | Variation→Chorus | 0–127 (solo System) |
| 14 | Variation→Reverb | 0–127 |

#### [F2]/[F3]/[F4] Reverb / Chorus / Variation Edit

| # | Parameter | Range | Note |
|---|---|---|---|
| 1 | Data display | view-only | — |
| 2 | Effect type | vedi elenchi §4 | — |
| 3 | Effect parameters | ≤ 16 param variabili per type | vedi [xg-effects.md](xg-effects.md) |
| 4 | Dry/Wet | D63>W … D=W … D<W63 | Solo Variation in Insertion |
| 5 | Controllable param marker | view-only | AC1 target (Insertion) |
| 6 | AC1 control depth | −64…+63 | Solo Insertion |

### 2.5 Pattern Play Effects — `[F4] Play Effects`

Stessi 3 sottogruppi di SONG Play Effects (Groove, Clock/Gate/Vel, Transpose) ma con 2 parametri addizionali nel Transpose:

| # | Parameter | Range | Note |
|---|---|---|---|
| 21 | Inversion Transposition | Off / On | Inverte accordo nel transpose |
| 22 | Open Harmony | Off / On | Apre voicing accordo |

### 2.6 Phrase Recording (Standby) — 9 parametri

| # | Parameter | Range |
|---|---|---|
| 1 | Phrase number/name | US01–US99 (user) |
| 2 | Length | 001–256 (≤ pattern length) |
| 3 | Phrase Type | Mldy1/Mldy2/Chrd1/Chrd2/Bass/Bypas/Para |
| 4 | Retrigger | Off/On |
| 5 | Low / High limits | C-2–G8 / C-1–G8 |
| 6 | High key | C–B |
| 7 | Voice (cat / prog / bank / name) | vedi §2.3 |
| 8 | Source chord | root + type (29) |
| 9 | Recording mode | `[F4]`=Replace, `[F5]`=Overdub, `[F6]`=Step |

### 2.7 Phrase Edit

Identica a Song Edit (event types: Note, Bend, PC, CC, ChAT, KeyAT, Excl, Tmp). Restrizioni: singola track, length ≤ pattern length, niente tempo events.

---

## 3. VOICE Mode

Ref: `QY700_MANUAL/08_3VoiceMode.txt`. Link: [qy700-voice-mode.md](qy700-voice-mode.md), [qy70-drum-kits.md](qy70-drum-kits.md).

Struttura: 32 part del tone generator XG.

```
[VOICE]
  ├─ [F1] Mixer
  ├─ [F2] Tune
  ├─ [F3] Voice Edit
  ├─ [F4] Drum Setup-1 Edit
  └─ [F5] Drum Setup-2 Edit
```

### 3.1 Mixer (13 parametri per part)

| # | Parameter | Range |
|---|---|---|
| 1 | Data display | view-only |
| 2 | Part number | 1–32 |
| 3 | Part status | M/S |
| 4 | Voice category | Normal / SFX Voice / SFX Kit / Drum / DrumSetup-1 / DrumSetup-2 |
| 5 | Program # | 001–128 |
| 6 | Bank # | 000–101 |
| 7 | Reverb send | 0–127 |
| 8 | Chorus send | 0–127 |
| 9 | Variation switch/send | Off/On oppure 0–127 |
| 10 | Dry level | 0–127 |
| 11 | Pan | Random, L63–C–R63 |
| 12 | Volume | 0–127 |
| 13 | Mono/Poly | Mono / Poly |

### 3.2 Tune (10 parametri per part)

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | Detune | −12.8 … +12.7 Hz | 0.0 |
| 2 | Note shift | −24 … +24 semitones | 0 |
| 3 | Transpose | −24 … +24 semitones | 0 |
| 4 | Pitch Bend range | 0 – +24 semitones | 2 |
| 5 | Scale tuning C–B | −64 … +63 cent | 0 |
| 6 | Portamento switch | Off / On | Off |
| 7 | Portamento time | 0–127 | 0 |
| 8 | Portamento mode | Fingered / Full time | Fingered |
| 9 | Velocity depth | 0–127 | 64 |
| 10 | Velocity offset | 0–127 | 64 |

### 3.3 Voice Edit (13 parametri per part)

| # | Parameter | Range |
|---|---|---|
| 1 | Mono/Poly | Mono / Poly |
| 2 | Element Reserve | 0–32 |
| 3 | Velocity Sensitivity Depth | 0–127 |
| 4 | Velocity Sensitivity Offset | 0–127 |
| 5 | Portamento (switch / time / mode) | vedi Tune |
| 6 | MW LFO (pitch/filter/amp) | 0–127 ciascuno |
| 7 | Filter Cutoff | −64…+63 |
| 8 | Filter Resonance | −64…+63 |
| 9 | EG Attack | −64…+63 |
| 10 | EG Decay | −64…+63 |
| 11 | EG Release | −64…+63 |
| 12 | Vibrato (rate/depth/delay) | −64…+63 |
| 13 | Pitch Bend Control / Dry level | −24…+24 / 0–127 |

### 3.4 Drum Setup-1 / Drum Setup-2 Edit (16 parametri per nota)

Disponibili se la part è configurata su Drum Setup 1 o 2 (due kit editabili indipendenti globali XG).

| # | Parameter | Range | Note |
|---|---|---|---|
| 1 | Data display | voice name + program# | view-only |
| 2 | Drum Kit | 11 kit (vedi lista §2.3-F3) | — |
| 3 | Note | C-1–C5 | microkeyboard |
| 4 | Reverb send | 0–127 | — |
| 5 | Chorus send | 0–127 | — |
| 6 | Variation send | 0–127 | — |
| 7 | Pan | Random, L63–C–R63 | — |
| 8 | Level | 0–127 | — |
| 9 | Pitch fine | −64…+63 (1 cent) | — |
| 10 | Pitch coarse | −64…+63 (semitone) | — |
| 11 | Alternate group | Off, 1–127 | Cut group (hi-hat open/close) |
| 12 | Key assign | Single / Multi | — |
| 13 | Receive note off | Off / On | — |
| 14 | Filter Cutoff / Resonance | −64…+63 | offset |
| 15 | EG Attack | −64…+63 | offset |
| 16 | EG Decay-1 / Decay-2 | −64…+63 | offset |

Vedi anche [xg-drum-setup.md](xg-drum-setup.md).

---

## 4. EFFECT Mode

Ref: `QY700_MANUAL/09_4EffectMode.txt`. Link: [qy700-effect-mode.md](qy700-effect-mode.md), [xg-effects.md](xg-effects.md).

Architettura XG: un Insertion effect (Variation in mode=Insertion) oppure 3 system effects paralleli (Reverb + Chorus + Variation in mode=System).

```
[EFFECT]
  ├─ [F1] Connection
  ├─ [F2] Reverb Edit
  ├─ [F3] Chorus Edit
  └─ [F4] Variation Edit
```

### 4.1 Connection (14 parametri)

Identici a Pattern Effects Connection (§2.4-F1).

**Reverb types (11)**: `NO EFFECT, HALL 1, HALL 2, ROOM 1, ROOM 2, ROOM 3, STAGE 1, STAGE 2, PLATE, WHITE ROOM, TUNNEL, BASEMENT`.

**Chorus types (11)**: `NO EFFECT, CHORUS 1–4, CELESTE 1–4, FLANGER 1–3`.

**Variation types (43)**: `NO EFFECT, HALL 1, HALL 2, ROOM 1, ROOM 2, ROOM 3, STAGE 1, STAGE 2, PLATE, DELAY LCR, DELAY L,R, ECHO, CROSSDELAY, ER1, ER2, GATE REV, REVRS GATE, KARAOKE 1, KARAOKE 2, KARAOKE 3, THRU, CHORUS 1, CHORUS 2, CHORUS 3, CHORUS 4, CELESTE 1, CELESTE 2, CELESTE 3, CELESTE 4, FLANGER 1, FLANGER 2, FLANGER 3, SYMPHONIC, ROTARY SP, TREMOLO, AUTO PAN, PHASER 1, PHASER 2, DISTORTION, OVERDRIVE, AMP SIM, 3-BAND EQ, 2-BAND EQ, AUTO WAH`.

### 4.2 Reverb / Chorus / Variation Edit

| # | Parameter | Range |
|---|---|---|
| 1 | Data display | view-only |
| 2 | Effect type | vedi elenchi sopra |
| 3 | Effect parameters | variabili per type (fino a 16 parametri per type; ref: `QY700_REFERENCE_LISTING.pdf`) |
| 4 | Dry/Wet | D63>W … D=W … D<W63 (solo Variation + Insertion) |
| 5 | Controllable parameter marker | view-only (AC1 target) |
| 6 | AC1 control depth | −64…+63 |

---

## 5. UTILITY Mode

Ref: `QY700_MANUAL/12_6UtilityMode.txt`. Link: [qy700-utility-mode.md](qy700-utility-mode.md).

I valori sono backed-up da batteria interna.

```
[UTILITY]
  ├─ [F1] System
  ├─ [F2] MIDI
  ├─ [F3] MIDI Filter
  ├─ [F4] Sequencer
  ├─ [F5] Click
  └─ [F6] Fingered Chord Zone
```

### 5.1 [F1] System (4 parametri)

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | Master Tune | −102.4 … +102.3 (0.1 cent) | 0.0 |
| 2 | Backlite Saver | Off, 1–8 Hours | Off |
| 3 | Footswitch | Start/Stop, Section, Sustain, Sostenuto | Start/Stop |
| 4 | Pitch Bend Wheel | Off, P.B., Ctrl#001–119 (no 032), CAT, VEL, TMP | P.B. |
| 5 | Assignable Wheel | stesso set di Pitch Bend Wheel | Ctrl#001 |

### 5.2 [F2] MIDI (5 parametri)

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | MIDI Sync | Internal, MIDI-A, MIDI-B, MTC:MIDI-A, MTC:MIDI-B | Internal |
| 2 | MIDI Control In | Off, In-A, In-B, In-A,B | In-A,B |
| 3 | MIDI Control Out | Off, Out-A, Out-B, Out-A,B | Off |
| 4 | XG Parameter Out | Off, Out-A, Out-B, Out-A,B | Off |
| 5 | MIDI Echo Back In-A | Off, Thru A, Thru B, Thru A,B, RecMonitor | Off |
| 6 | MIDI Echo Back In-B | stessi valori | Off |
| 7 | MTC Start Offset | hh:mm:ss:ff (00–23 / 00–59 / 00–59 / 00–29) | 00:00:00:00 |

### 5.3 [F3] MIDI Filter (7 check per-direzione)

Ciascun evento: `Pass` (check) / `Cut` (blank). Si applica su recording e playback del sequencer, non sul tone generator.

| # | Event | Default |
|---|---|---|
| 1 | Note (On/Off) | Pass |
| 2 | Pitch Bend | Pass |
| 3 | Control Change | Pass |
| 4 | Program Change (+ Bank MSB/LSB) | Pass |
| 5 | Polyphonic Aftertouch | Pass |
| 6 | Channel Aftertouch | Pass |
| 7 | System Exclusive | Pass |

### 5.4 [F4] Sequencer (3 parametri)

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | Mute tracks level | Off, 01–99% | Off |
| 2 | Event Chase | Off, PC, PC,PB,Ctrl, ALL | PC,PB,Ctrl |
| 3 | Interval time | 0–9 × 100 ms | 0 |

### 5.5 [F5] Click (3 gruppi)

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | Channel TG | Off, 01–32 | 10 (drum) |
| 2 | Channel MIDI A | Off, 01–16 | Off |
| 3 | Channel MIDI B | Off, 01–16 | Off |
| 4 | Accent note | C-2–G8 | — |
| 5 | Accent level | 0–127 | — |
| 6 | Normal note | C-2–G8 | — |
| 7 | Normal level | 0–127 | — |

### 5.6 [F6] Fingered Chord Zone (3 parametri)

| # | Parameter | Range | Default |
|---|---|---|---|
| 1 | Fingered Chord | Off / FINGRD | Off |
| 2 | Zone Low | C-2–G8 | C2 |
| 3 | Zone High | C-2–G8 | B4 |
| 4 | MIDI Port | In-A, In-B, In-A,B | In-A,B |
| 5 | MIDI Channel | ALL, 01–16 | ALL |

---

## 6. DISK Mode

Ref: `QY700_MANUAL/13_7DiskMode.txt`. Link: [qy700-disk-mode.md](qy700-disk-mode.md), [q7p-format.md](q7p-format.md).

Floppy 3.5" 2HD (1.44 MB, 18 settori) o 2DD (720 KB, 9 settori), MS-DOS format.

```
[DISK]
  ├─ [F1] Save
  │    ├─ [D1] All Data      (.Q7A)
  │    ├─ [D2] Style          (.Q7P)
  │    ├─ [D3] Song           (.Q7S)
  │    ├─ [D4] Song ESEQ      (.ESQ)   + [F4] XG HEADR toggle
  │    └─ [D5] Song SMF       (.MID)   + [F4] XG HEADR + [F1]/[F2] Format 0/1
  ├─ [F2] Load
  │    ├─ [D1] All Data
  │    ├─ [D2] Style
  │    └─ [D3] Song  (legge anche .ESQ e .MID)     [F6] Preplay (solo SMF fmt 0)
  ├─ [F4] Rename
  │    ├─ [D1] All Data
  │    ├─ [D2] Style
  │    └─ [D3] Song
  ├─ [F5] Delete
  │    ├─ [D1] All Data
  │    ├─ [D2] Style
  │    └─ [D3] Song
  └─ [F6] Format    (2HD 1.44 MB / 2DD 720 KB)
```

### 6.1 Tipi di file

| Tipo | Ext | Contenuto |
|---|---|---|
| All Data | `.Q7A` | 20 song + 64 style + system setup (tutto) |
| Style | `.Q7P` | 8 pattern (una sezione ciascuno) + 99 user phrases + play effect + pattern voice + pattern effect |
| Song | `.Q7S` | musical data + pattern/chord/tempo track + play effect + out channels + voice mode + effect mode |
| Song ESEQ | `.ESQ` | solo TR1–16 + tempo track, formato Yamaha |
| Song SMF | `.MID` | Format 0 (TR1–16 + tempo) o Format 1 (TR1–32 + tempo) |

### 6.2 Parametri per operazione

Save (per tipo):

| Tipo | Parameters |
|---|---|
| All Data | filename |
| Style | style 01–64 + filename |
| Song | song 01–20 + filename |
| Song ESEQ | song 01–20 + XG Header on/off + filename |
| Song SMF | song 01–20 + XG Header on/off + Format 0/1 + filename |

Caratteri filename: `0–9, a–z, A–Z, " ' ^ ( ) < = > @ | \ _ ! ? # $ % & * + - / , . : ; space`. Vietati: `* ?`.

Shortcut: `[F6] DeflName` copia il nome della song/style come filename.

Load: stesse scelte, solo numero di destinazione (01–20 song / 01–64 style). Per All Data: nessun numero (sovrascrive tutto).

Rename: stessi tipi, `Song` ammette anche .ESQ e .MID.

Delete: idem Rename.

Format: conferma con `[ENTER]` + `[Increment]`.

Cross-link: [pattern-restore.md](pattern-restore.md), [bricking.md](bricking.md).

---

## 7. Song Jobs

Ref: `QY700_MANUAL/06_2_1SongMode.txt`, `07_2_2SongMode.txt`. 25 job (00–24) + Song Name (indice 25).

Struttura menu Job: direct keys scelgono il gruppo (`[D1]` Event / `[D2]` Track / `[D3]` Song). Function keys `[F1]–[F6]` riassegnabili via `SHIFT + Fn`.

| # | Job | Purpose | Parametri chiave |
|---|---|---|---|
| 00 | Undo / Redo | Annulla o ripristina ultima operazione | nessun param (usa SHIFT+UNDO/REDO) |
| 01 | Quantize | Quantizza note | Track 1–32, segment, note range, q-value (32nd…1/4 + triplet), Strength 0–100%, Sensitivity ±100%, Swing rate 50–83%, Swing gate 0–200%, Swing velocity 0–200% |
| 02 | Modify Velocity | Cambia velocity | Track, segment, note range, SetAll Off/1–127, Rate 0–200%, Offset −99…+99 |
| 03 | Modify Gate Time | Cambia durata note | Track, segment, note range, SetAll Off/0001–9999, Rate 0–200%, Offset −9999…+9999 |
| 04 | Crescendo | Velocity ramp | Track, segment, note range, Range −99…+99 |
| 05 | Transpose | Semitone shift | Track, segment, note range, Transpose −99…+99 |
| 06 | Shift Note | Sostituisce un pitch | Track, segment, Source C-2–G8, Destination C-2–G8 |
| 07 | Shift Clock | Time shift per clock | Track, segment, Clock −9999…+9999 |
| 08 | Chord Sort | Ordina note simultanee | Track, segment, Type (Normal/Reverse) |
| 09 | Chord Separate | Apre accordo con delay | Track, segment, Clock 01–99 |
| 10 | Shift Event | Cambia tipo evento | Track, segment, Source event, Destination event (CC/CAT/PB/Note) |
| 11 | Copy Event | Copia segmento | Source track+segment, Dest track+start, Iterations 1–99 |
| 12 | Erase Event | Cancella e inserisce rest | Track, segment |
| 13 | Extract Event | Sposta eventi tra track | Source track+segment, Spot clock 0–3840, Dest track (Off/01–32), Event type (Note/PC/PB/CC/CAT/PAT/EXC), Argument range |
| 14 | Thin Out | Riduce eventi ravvicinati | Track, segment, Event type (PB/CC/CAT/PAT) |
| 15 | Time Stretch | Espande/comprime timing | Track, segment, Time 50–200% |
| 16 | Create Measure | Inserisce misure vuote | Track, position, count 1–999 |
| 17 | Delete Measure | Rimuove misure | Track, segment |
| 18 | Copy Track | Duplica track | Source track, Dest track |
| 19 | Mix Tracks | Fonde due track | Source track → Dest track |
| 20 | Clear Track | Cancella track | Track 01–32 / All + data type checkboxes |
| 21 | Expand Backing | Converte pattern in eventi su track | Song, pattern track → destination tracks |
| 22 | Normalize Play Effects | Fissa i play effect come eventi reali | Track |
| 23 | Copy Song | Duplica song | Source song, Dest song |
| 24 | Clear Song | Cancella song | Song 01–20 |
| 25 | Song Name | Assegna nome | Song 01–20, name ≤ 12 char |

---

## 8. Pattern Jobs

Ref: `QY700_MANUAL/11_5_2PatternMode.txt`. 31 job (00–30). Gruppi via direct keys: `[D1]` Event, `[D2]` Phrase, `[D3]` Track, `[D4]` Pattern.

| # | Job | Purpose | Parametri chiave |
|---|---|---|---|
| 00 | Undo / Redo | Annulla/ripristina | SHIFT+UNDO/REDO shortcut |
| 01 | Quantize | Quantizza phrase | Phrase 01–99, segment 001:1–256:8, note range, q-value, Strength, Sensitivity, Swing {rate, gate, velocity} |
| 02 | Modify Velocity | Cambia velocity | Phrase, segment, note range, SetAll, Rate, Offset (come Song Job 02) |
| 03 | Modify Gate Time | Cambia gate time | Phrase, segment, note range, SetAll, Rate, Offset |
| 04 | Crescendo | Velocity ramp | Phrase, segment, note range, Range −99…+99 |
| 05 | Transpose | Semitone shift | Phrase, segment, note range, Transpose −99…+99 |
| 06 | Shift Note | Cambia pitch | Phrase, segment, Source, Destination |
| 07 | Shift Clock | Time shift | Phrase, segment, Clock −9999…+9999 |
| 08 | Chord Sort | Normal/Reverse | Phrase, segment, Type |
| 09 | Chord Separate | Delay tra note | Phrase, segment, Clock 01–99 |
| 10 | Shift Event | Cambia tipo evento | Phrase, segment, Source/Dest event |
| 11 | Copy Event | Copia segmento | Style, Phrase, src segment, dest start, Iterations |
| 12 | Erase Event | Svuota con rest | Phrase, segment |
| 13 | Extract Event | Sposta tra phrase | Src phrase+segment, Spot clock, Dest phrase (Off/01–99), Event type, Argument range |
| 14 | Thin Out | Riduce eventi | Phrase, segment, Event (PB/CC/CAT/PAT) |
| 15 | Time Stretch | Espande/comprime | Phrase, segment, Time 50–200% |
| 16 | Copy Phrase | Duplica phrase | Src style+phrase → Dest style+phrase, Data type (Event/Phrase Table) |
| 17 | Mix Phrase | Fonde phrase | Src style+phrase-a, Dest style+phrase-b, Phrase table source (a/b) |
| 18 | Append Phrase | Accoda a→b | Src style+phrase-a, Dest style+phrase-b, Phrase table source |
| 19 | Split Phrase | Divide phrase | Src style+phrase, split point, Dest style+phrase |
| 20 | Get Phrase | Crea phrase da song | Source song 01–20, track 01–32, segment, Dest style+phrase |
| 21 | Put Phrase | Copia phrase in song | Src style+phrase, Dest song+track, start measure |
| 22 | Clear Phrase | Cancella phrase | Phrase 01–99 |
| 23 | Phrase Name | Assegna nome | Phrase 01–99 (non vuota), name ≤ 12 char |
| 24 | Clear Track | Cancella track + settings | Track 01–16/All + data type (Patch/Play Effect/Voice) |
| 25 | Copy Pattern | Copia pattern | Src style+section+track → Dest style+section+track, Data type (Patch/User Phrase/Play Effect/Voice) |
| 26 | Append Pattern | Accoda pattern | Src style+section, Dest style+section, Play Effect a/b, Pattern Voice a/b |
| 27 | Split Pattern | Divide pattern | Src style+section, split point, Dest style+section, Play Effect+Pattern Voice copy |
| 28 | Clear Pattern | Cancella pattern | Style 01–64/All, Section A–H/All (All+All non è UNDOable) |
| 29 | Pattern Name | Rinomina style+section | Style name ≤ 8 char, Section A–H, Pattern name ≤ 8 char |
| 30 | Style Icon | Icona style | 160 icone selezionabili |

---

## Note finali

- **Default**: quando il manuale non dichiara un default esplicito, è indicato con `—`. Molti default dipendono dal contesto (es. Track Level varia per-track).
- **Voice bank / program lists** complete (519 XG Normal + 20 drum kits): vedi `QY700_REFERENCE_LISTING.pdf` e [qy70-voice-list.md](qy70-voice-list.md), [qy70-drum-kits.md](qy70-drum-kits.md).
- **Effect parameter tables** complete per ogni type (Reverb×11, Chorus×11, Variation×43): vedi `QY700_REFERENCE_LISTING.pdf` e [xg-effects.md](xg-effects.md).
- **Groove Quantize**: 100 preset template, parametri TIMING/VELOC 0–200%: vedi [qy700-groove-templates.md](qy700-groove-templates.md).
- **Chord types / root**: 12 root × 29 type (inclusi THRU): vedi [qy700-chord-types.md](qy700-chord-types.md).
- **Preset phrase numbering** (3876 preset): vedi [qy700-phrase-lists.md](qy700-phrase-lists.md).
- **Troubleshooting** e messaggi errori comuni: vedi [qy700-troubleshooting.md](qy700-troubleshooting.md).
