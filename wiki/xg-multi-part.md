# XG Multi Part Parameters

Parametri per-parte del tone generator XG. Il QY70 ha 16 parti (NN = 00h-0Fh), il QY700 ne ha 32 (NN = 00h-1Fh). Riferimento: [xg-parameters.md](xg-parameters.md).

**Formato**: `F0 43 10 4C 08 NN [AL] XX F7` (NN = part number)

## Part count

| Device | Parts | Range NN |
|--------|-------|----------|
| QY70 | 16 | 00h-0Fh |
| QY700 | 32 (DVA) | 00h-1Fh |
| MU50/MU80/MU90/MU100/SW1000XG | 32 | 00h-1Fh |

Il QY700 supporta fino a 32 timbres simultanei con Dynamic Voice Allocation (DVA). Parts 17-32 (NN=10h-1Fh) **non** esistono sul QY70.

## Part Mode & Channel

| AL | Parametro | Range | Default | Note |
|----|-----------|-------|---------|------|
| 00 | Element Reserve | 00-20 | Part 10: 00, altri: 02 | Riserva note |
| 01 | Bank Select MSB | 00-7F | Part 10: 7F, altri: 00 | |
| 02 | Bank Select LSB | 00-7F | 00 | |
| 03 | Program Number | 00-7F | 00 | Voice select (1-128) |
| 04 | Receive MIDI Channel | 00-0F, 7F | Part number | 7F=OFF |
| 05 | Mono/Poly Mode | 00-01 | 01 | 0=Mono, 1=Poly |
| 06 | Same Note Key On Assign | 00-02 | 01 | 0=Single, 1=Multi, 2=Inst (Drum) |
| 07 | **Part Mode** | 00-03 | Part 10: 02, altri: 00 | 0=Normal, 1=Drum, 2=DrumSetup1, 3=DrumSetup2 |
| 08 | Note Shift | 28-58 | 40 | -24..+24 semitoni |
| 09-0A | Detune (2 byte) | 00,00-0F,0F | 08,00 | -12.8..+12.7 Hz |

## Volume, Pan, Effect Send

| AL | Parametro | Range | Default | Note |
|----|-----------|-------|---------|------|
| 0B | Volume | 00-7F | 64 | |
| 0C | Velocity Sense Depth | 00-7F | 40 | -64..+63 |
| 0D | Velocity Sense Offset | 00-7F | 40 | -64..+63 |
| 0E | Pan | 00-7F | 40 | 0=Random, 1..64..127=L..C..R |
| 0F | Note Limit Low | 00-7F | 00 | |
| 10 | Note Limit High | 00-7F | 7F | |
| 11 | Dry Level | 00-7F | 7F | Direct out (se Variation=Insertion) |
| 12 | Chorus Send | 00-7F | 00 | |
| 13 | Reverb Send | 00-7F | 28 | |
| 14 | Variation Send | 00-7F | 00 | Solo modo System |

## LFO & EG

| AL | Parametro | Range | Default |
|----|-----------|-------|---------|
| 15 | Vibrato Rate | 00-7F | 40 |
| 16 | Vibrato Depth | 00-7F | 40 |
| 17 | Vibrato Delay | 00-7F | 40 |
| 18 | Filter Cutoff Frequency | 00-7F | 40 |
| 19 | Filter Resonance | 00-7F | 40 |
| 1A | EG Attack Time | 00-7F | 40 |
| 1B | EG Decay Time | 00-7F | 40 |
| 1C | EG Release Time | 00-7F | 40 |

## MW (Modulation Wheel) Control

| AL | Parametro | Range | Default |
|----|-----------|-------|---------|
| 1D | MW Pitch Control | 28-58 | 40 (-24..+24 semi) |
| 1E | MW Filter Control | 00-7F | 40 (-9600..+9450 cent) |
| 1F | MW Amplitude Control | 00-7F | 40 |
| 20 | MW LFO Pitch Mod Depth | 00-7F | 0A |
| 21 | MW LFO Filter Mod Depth | 00-7F | 00 |
| 22 | MW LFO Amplitude Mod Depth | 00-7F | 00 |

## Bend (Pitch Bend) Control

| AL | Parametro | Range | Default |
|----|-----------|-------|---------|
| 23 | Bend Pitch Control | 28-58 | 42 (+2 semitoni) |
| 24 | Bend Filter Control | 00-7F | 40 |
| 25 | Bend Amplitude Control | 00-7F | 40 |
| 26 | Bend LFO Pitch Mod Depth | 00-7F | 40 |
| 27 | Bend LFO Filter Mod Depth | 00-7F | 40 |
| 28 | Bend LFO Amplitude Mod Depth | 00-7F | 40 |

## Receive Switches

| AL | Parametro | Default | Note |
|----|-----------|---------|------|
| 30 | Rx Pitch Bend | 01 | |
| 31 | Rx Channel After Touch | 01 | |
| 32 | Rx Program Change | 01 | |
| 33 | Rx Control Change | 01 | |
| 34 | Rx Poly After Touch | 01 | |
| 35 | Rx Note Messages | 01 | |
| 36 | Rx RPN | 01 | |
| 37 | Rx NRPN | XG:01, GM:00 | |
| 38 | Rx Modulation Wheel | 01 | |
| 39 | Rx Volume | 01 | |
| 3A | Rx Pan | 01 | |
| 3B | Rx Expression | 01 | |
| 3C | Rx Hold Pedal | 01 | |
| 3D | Rx Portamento | 01 | |
| 3E | Rx Sostenuto | 01 | |
| 3F | Rx Soft Pedal | 01 | |
| 40 | Rx Bank Select | XG:01, GM:00 | |

## Scale Tuning (12 note)

`AL = 41..4C` → C, C#, D, D#, E, F, F#, G, G#, A, A#, B. Range 00-7F default 40 (-64..+63 cent per nota).

## CAT (Channel After Touch) Control

| AL | Parametro | Range | Default |
|----|-----------|-------|---------|
| 4D | CAT Pitch Control | 28-58 | 40 |
| 4E | CAT Filter Control | 00-7F | 40 |
| 4F | CAT Amplitude Control | 00-7F | 40 |
| 50 | CAT LFO Pitch Mod Depth | 00-7F | 00 |
| 51 | CAT LFO Filter Mod Depth | 00-7F | 00 |
| 52 | CAT LFO Amplitude Mod Depth | 00-7F | 00 |

## PAT (Polyphonic After Touch) Control

| AL | Parametro | Range | Default |
|----|-----------|-------|---------|
| 53 | PAT Pitch Control | 28-58 | 40 |
| 54 | PAT Filter Control | 00-7F | 40 |
| 55 | PAT Amplitude Control | 00-7F | 40 |
| 56 | PAT LFO Pitch Mod Depth | 00-7F | 00 |
| 57 | PAT LFO Filter Mod Depth | 00-7F | 00 |
| 58 | PAT LFO Amplitude Mod Depth | 00-7F | 00 |

## AC1/AC2 (Assignable Controllers)

| AL | Parametro AC1 | AL | Parametro AC2 | Range | Default |
|----|---------------|----|---------------|-------|---------|
| 59 | AC1 CC Number | 60 | AC2 CC Number | 00-5F | AC1: 10, AC2: 11 |
| 5A | AC1 Pitch Control | 61 | AC2 Pitch Control | 28-58 | 40 |
| 5B | AC1 Filter Control | 62 | AC2 Filter Control | 00-7F | 40 |
| 5C | AC1 Amplitude Control | 63 | AC2 Amplitude Control | 00-7F | 40 |
| 5D | AC1 LFO Pitch | 64 | AC2 LFO Pitch | 00-7F | 00 |
| 5E | AC1 LFO Filter | 65 | AC2 LFO Filter | 00-7F | 00 |
| 5F | AC1 LFO Amplitude | 66 | AC2 LFO Amplitude | 00-7F | 00 |

## Portamento & Pitch EG

| AL | Parametro | Range | Default |
|----|-----------|-------|---------|
| 67 | Portamento Switch | 00-01 | 00 |
| 68 | Portamento Time | 00-7F | 00 |
| 69 | Pitch EG Initial Level | 00-7F | 40 |
| 6A | Pitch EG Attack Time | 00-7F | 40 |
| 6B | Pitch EG Release Level | 00-7F | 40 |
| 6C | Pitch EG Release Time | 00-7F | 40 |
| 6D | Velocity Limit Low | 01-7F | 01 |
| 6E | Velocity Limit High | 01-7F | 7F |

## Part EQ (MU90/MU100/SW1000XG only — non QY70)

| AL | Parametro |
|----|-----------|
| 72 | EQ Bass Gain |
| 73 | EQ Treble Gain |
| 76 | EQ Bass Frequency |
| 77 | EQ Treble Frequency |

## Note Drum Part

Per la parte Drum (Part 10 di default, o qualsiasi parte con Part Mode ≠ 0), questi parametri NON hanno effetto:
- Bank Select LSB
- Portamento
- Soft Pedal
- Mono/Poly
- Scale Tuning
- Pitch EG

## Implementation Status (Session 34, 2026-04-27)

**100% coverage** — all ~70 parameters AL 0x00-0x6E implemented in:
- `address_map.py _MULTI_PART_AL` — UDM path → (AH, AM, AL)
- `schema.py _MULTI_PART_SPECS` — validation + XG encoding
- `xg_bulk.py _apply_multi_part()` — XG parse → UDM
- `syx_analyzer.py _parse_xg_multi_part()` — analysis display
- `multi_part.py MultiPart` — dataclass with ~70 fields
- `xg_multi_part.py MultiPartInfo` — 41-byte bulk dump decode
- `ops.py make_xg_messages()` — UDM → XG emit (incl. detune 2-byte)

| Block | AL Range | Fields | Status |
|-------|----------|--------|--------|
| Voice/Mode/Mixer | 0x00-0x14 | 21 | DONE |
| Vibrato + Filter/EG | 0x15-0x1C | 8 | DONE |
| MW Control | 0x1D-0x22 | 6 | DONE |
| Bend Control | 0x23-0x28 | 6 | DONE |
| Rx Switches | 0x30-0x40 | 17 | DONE |
| Scale Tuning | 0x41-0x4C | 12 | DONE |
| CAT Control | 0x4D-0x52 | 6 | DONE |
| PAT Control | 0x53-0x58 | 6 | DONE |
| AC1/AC2 | 0x59-0x66 | 14 | DONE |
| Portamento/Pitch EG | 0x67-0x6E | 8 | DONE |

## Source

- [studio4all.de main92.html](http://www.studio4all.de/htmle/main92.html)
- `manual/QY70/QY70_LIST_BOOK.PDF` pag. 59-61 Table 1-6
