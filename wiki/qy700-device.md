# Yamaha QY700

Workstation sequencer. The larger, more capable sibling of the [QY70](qy70-device.md).

## Key Differences from QY70

| Feature | QY70 | QY700 |
|---------|------|-------|
| Tracks | 8 | 16 (TR1-TR16) per pattern / 32 (TR1-TR32) per song |
| Data format | SysEx packed bitstream | Byte-oriented binary |
| Event format | 9-bit fields, barrel rotation | D0/E0/A0-A7/BE/F2 commands |
| File format | `.syx` (variable size) | `.Q7P` (3072 basic / 5120 full) |
| Data transfer | MIDI SysEx bulk dump | Floppy disk + MIDI XG SysEx |
| MIDI Ports | 1 IN, 1 OUT | 2 IN (A,B), 2 OUT (A,B) |
| Disk | — | Floppy 3.5" 2HD/2DD |

## Specifications (da `14_Specifications.txt` + MIDI Impl Chart)

### Sequencer block

| Property | Value |
|----------|-------|
| Data capacity | ~110,000 notes (memoria condivisa fra tutti song + phrase) |
| Note resolution | 480 clock/quarter |
| Polyphony (sequencer) | 64 voci (logiche) |
| Tempo range | 25.0–300.0 BPM |
| Record modes | Realtime, Punch, Step |
| Tracks | Song: 35 (TR1-TR32 + Pattern + Chord + Tempo); Pattern: 16 (TR1-TR16) |
| Songs | 20 |
| Patterns | 64 user styles × 8 sections = 512 user patterns |
| Phrases | 3,876 preset + fino a 99 user/style |
| Chord Presets | 12 roots × 28 types (incl. THRU) |
| Edit sub-modes | Voice edit, Drum Setup edit, Song edit, Phrase edit |
| Song Jobs | 25 |
| Pattern Jobs | 30 |
| Play effects | Groove Quantize, Clock Shift/Gate/Velocity, Transpose |
| File formats | QY700 native (.Q7A/.Q7S/.Q7P), ESEQ (.ESQ), SMF Format 0/1 (.MID) |

### Tone generator block

| Property | Value |
|----------|-------|
| Engine | AWM2 |
| Max polyphony | 32 note (elementi!) |
| Multi-timbral | 32 timbri (con DVA — Dynamic Voice Allocation) |
| Preset voices | 480 normal + 11 drum = **491 totali** |
| Effects | 3 systems: Reverb + Chorus + Variation |
| Reverb types | 11 |
| Chorus types | 11 |
| Variation types | 43 |

**Priorità DVA** (quali voci vengono rubate per prime quando si supera 32):
`Part 10 (drum) → 1 → 2..9 → 11..16 → 26 → 17..25 → 27..32`
Part 10 (drum) ha SEMPRE la massima priorità. `Element Reserve` per-parte (SysEx `08 nn 00`) permette di riservare voci a priori.

### Controlli

- Power ON/OFF, VOLUME analog
- **PITCH wheel** (return-to-center; assignable a PB/CC#1-119)
- **ASSIGNABLE wheel** (detented; stesso range di assegnazione)
- **Shuttle dial** + **Data dial**
- **Mode keys**: SONG, PATTERN, UTILITY, VOICE, EFFECT, DISK
- **Sub-mode keys**: EDIT, JOB
- **Function keys**: F1–F6
- **Direct keys**: D1–D5
- 2× SHIFT, 1× EXIT
- **CONTRAST control** (analog)
- **Sequencer**: Recording, Stop, Play, Top, Rewind, Forward
- **Locate keys**: LOC1, LOC2
- **Track keys**: TRACK UP/DOWN, MUTE, SOLO
- **Data entry**: Decrement, Increment
- **Cursor**: up/down/left/right
- **Numeric keypad**: 0–9, -, ENTER
- **Octave keys**: 2× OCT DOWN, 2× OCT UP
- **Microkeyboard**: E2–F4 (chord zone usabile in Fingered Chord)

### Display

LCD grafico **320×240** con backlight CFL e contrasto regolabile.

### LED

- 6 × MODE (verde)
- 1 × REC (rosso)
- 1 × PLAY (verde)
- MIDI IN-A (rosso), MIDI IN-B (rosso)
- MIDI OUT-A (verde), MIDI OUT-B (verde) — normalmente lampeggiano perché il sequencer trasmette Timing Clock

### Connettori

- **PHONES** stereo phone jack — output nominale +7.0 ±2 dBm (impedenza 33 Ω)
- **OUTPUT** 2× phone jack (L/MONO, R) — output +6.5 ±2 dBm (impedenza 1 kΩ)
- **FOOT SWITCH** (function assignable: Start/Stop, Section change, Sustain, Sostenuto)
- **DC IN** (PA-5B AC adaptor)
- **MIDI × 4**: IN-A, IN-B, OUT-A, OUT-B

### Floppy disk drive

- Tipo fisico: **3.5" 2HD (1.44 MB)** oppure **2DD (720 KB)**
- Formato logico: **MS-DOS** (compatibile PC)
- Vedi [QY700 Disk Mode](qy700-disk-mode.md)

### Alimentazione & fisico

- Adattatore esterno **PA-5B**
- Dimensioni: 353 W × 305 D × 90 H (mm)
- Peso: 3.5 kg

### Firmware

- Prima versione pubblica: **V1.00, 22-MAR-1996** (MIDI Implementation Chart)

## File Format

See [Q7P Format](q7p-format.md) for the complete binary structure.

## Mode Summary (6 sub-modi, 1 per mode key)

- [SONG](qy700-song-mode.md) — 20 songs, 32 sequence track + Pattern/Chord/Tempo
- [PATTERN](qy700-pattern-mode.md) — 64 style × 8 section + phrases
- [UTILITY](qy700-utility-mode.md) — System/MIDI/Filter/Sequencer/Click/Fingered
- [VOICE](qy700-voice-mode.md) — Mixer, Tune, Voice Edit, Drum Setup 1/2
- [EFFECT](qy700-effect-mode.md) — Reverb, Chorus, Variation (System o Insertion)
- [DISK](qy700-disk-mode.md) — Save/Load/Rename/Delete/Format (floppy)

## MIDI

See [QY700 MIDI Protocol](qy700-midi-protocol.md) for full SysEx format and XG parameter tables.

## Notes for qyconv

- **XG Header** flag salvataggio SMF: aggiunge 1-2 misure di setup all'inizio del file (SysEx Voice/Effect). Utile per rendering su altri tone generator XG, causa piccolo lag tempo nelle prime misure.
- **Expand Backing** (Song Job 21): converte Pattern+Chord track → MIDI data su TR17-32. Trasforma un song con pattern in un SMF standard senza dipendenza dal QY700.
- Meter (time signature) è **per-style** (condiviso fra le 8 sezioni), non per-pattern.
- Patterns/phrase dal **QY300/QS300 NON sono caricabili** (struttura incompatibile). Altrettanto vale per SMF→Q7P: serve conversione custom.

## Known Issues

- **Bricking risk**: writing to unconfirmed offsets (0x1E6, 0x1F6, 0x206) can corrupt patterns and cause the device to hang. See [Bricking Diagnosis](bricking.md).
- Phrase data format (0x360-0x677) is NOT byte-oriented D0/E0 commands as initially assumed — contains values 0x2D-0x7F without command bytes, suggesting a different encoding.
