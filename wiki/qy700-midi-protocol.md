# QY700 MIDI Protocol

Reference: `QY700_REFERENCE_LISTING.pdf`, pagine 33-42, e `manual/QY700/QY700_MANUAL/12_6UtilityMode.txt`.

## Key Difference from QY70

| Property | QY70 | QY700 |
|----------|------|-------|
| Model ID | `5F` | `4C` (XG) |
| Identity Family | `0x4100` | `0x4100` |
| Identity Member | `0x5502` | `0x7901` (PDF dice `0x1901` — **errato, typo**, vedi sotto) |
| Bulk Dump Init | Required (`F0 43 10 5F 00 00 00 01 F7`) | NOT required |
| Dump Request | `F0 43 20 5F AH AM AL F7` | `F0 43 2n 4C AH AM AL F7` |
| MIDI Ports | 1 IN, 1 OUT | 2 IN (A,B), 2 OUT (A,B) |
| Data Exchange | MIDI SysEx bulk dump | Floppy disk + MIDI XG SysEx |

## Identity

```
Request (received, Omni): F0 7E 7F 06 01 F7
Reply (transmitted):      F0 7E 0n 06 02 43 00 41 01 79 00 00 00 01 F7
                                                   ^^ ^^ = QY700 device code
```

Device number `n` = 0-15, default 0.

**VERIFIED on hardware** (Session 23, via Steinberg UR22C):
```
Reply: F0 7E 7F 06 02 43 00 41 01 79 00 00 00 01 F7
       Member = 0x7901 (PDF said 0x1901 — typo in PDF)
```
Note: cheap USB MIDI Cable had broken IN connector. Steinberg UR22C works perfectly.

## XG Bulk Dump

Format: `F0 43 0n 4C ByteCountH ByteCountL AH AM AL data... checksum F7`

- `n` = device number (0)
- ByteCount = number of data bytes (7-bit encoded, 2 bytes)
- Checksum = `(0 - sum(bH, bL, AH, AM, AL, data_bytes)) & 0x7F`
- Data > 512 bytes: split into 512-byte packets, with **≥120ms interval** tra chunk
- `Interval Time` setting (UTILITY → F4 Sequencer) regola la pausa tra blocchi 1KB durante TX: 0-9 × 100ms selezionabile

### Dump Request

`F0 43 2n 4C AH AM AL F7`

Available types (from PDF):

| Address (AH AM AL) | Type | Scope |
|---------------------|------|-------|
| `00 00 00` | XG System | Global system params |
| `02 01 00` | Multi Effect | Reverb/Chorus/Variation |
| `08 nn 00` | Multi Part | Part nn (00-1F = parts 1-32) |
| `30 18 00` | Drum Setup 1 | Drum kit parameters |
| `31 18 00` | Drum Setup 2 | Drum kit parameters |
| `01 00 00` | System Information | Model name, version (response only) |

## Parameter Change

`F0 43 1n 4C AH AM AL dd [dd2 [dd3 dd4]] F7`

Per parametri a 2 byte o 4 byte (es. Detune, Master Tune) l'argomento `dd` contiene più byte dati consecutivi.

**Nota**: i Parameter Change NON hanno checksum (solo i Bulk Dump). Questo li rende molto più leggeri per modifiche atomiche.

## Parameter Request

`F0 43 3n 4C AH AM AL F7`

Restituisce il valore corrente via Parameter Change message.

## Parameter Base Addresses (Table 1-1)

| Address | Description |
|---------|-------------|
| `00 00 00` | System |
| `00 00 7D` | Drum Setup Reset |
| `00 00 7E` | XG System On |
| `00 00 7F` | All Parameter Reset |
| `01 00 00` | System Information |
| `02 01 00` | Effect 1 (Reverb/Chorus/Variation) |
| `02 40 00` | Reserved |
| `08 00 00` | Multi Part 1 |
| `08 0F 00` | Multi Part 16 |
| `08 10 00` | Multi Part 17 (QY700 extension) |
| `08 1F 00` | Multi Part 32 |
| `30 18 00` | Drum Setup 1 |
| `31 18 00` | Drum Setup 2 |

## Multi Part Parameters (Table 1-5, completa)

Indirizzo: `08 nn XX` (con `nn` = part 0..0x1F, `XX` = offset). Totale **0x3F (63 byte)** per parte.

| Offset | Size | Parameter | Default | Range |
|--------|------|-----------|---------|-------|
| `00` | 1 | Element Reserve | 2 (Part10=0) | 0..32 |
| `01` | 1 | Bank Select MSB | 0 (Part10=7F) | 0..127 |
| `02` | 1 | Bank Select LSB | 0 | 0..127 |
| `03` | 1 | Program Number | 0 | 1..128 |
| `04` | 1 | Rcv Channel | 0..0F | 0F,7F |
| `05` | 1 | Mono/Poly Mode | off | mono,poly |
| `06` | 1 | Same Note Number | 01 | single,multi |
| `07` | 1 | Part Mode | 0 | normal,drum1-3 |
| `08` | 1 | Note Shift | 40 | -24..+24 semitones |
| `09` | 2 | Detune | 0 | -12.8..+12.7 Hz |
| `0B` | 1 | Volume | 64 | 0..127 |
| `0C` | 1 | Velocity Sense Depth | 40 | 0..127 |
| `0D` | 1 | Velocity Sense Offset | 40 | 0..127 |
| `0E` | 1 | Pan | 40 | 0=random, L..R |
| `0F` | 1 | Note Limit Low | 0 | C-2..G8 |
| `10` | 1 | Note Limit High | 7F | C-2..G8 |
| `11` | 1 | Dry Level | 0 | 0..127 |
| `12` | 1 | Chorus Send | 0 | 0..127 |
| `13` | 1 | Reverb Send | 28 | 0..127 |
| `14` | 1 | Variation Send | 0 | 0..127 |
| `15` | 1 | Vibrato Rate | 40 | -64..+63 |
| `16` | 1 | Vibrato Depth | 40 | -64..+63 |
| `17` | 1 | Vibrato Delay | 40 | -64..+63 |
| `18` | 1 | Filter Cutoff Freq | 40 | -64..+63 |
| `19` | 1 | Filter Resonance | 40 | -64..+63 |
| `1A` | 1 | EG Attack Time | 40 | -64..+63 |
| `1B` | 1 | EG Decay Time | 40 | -64..+63 |
| `1C` | 1 | EG Release Time | 40 | -64..+63 |
| `1D` | 1 | MW Pitch Control | 40 | -24..+24 semi |
| `1E` | 1 | MW Filter Control | 40 | -9600..+9450 cent |
| `1F` | 1 | MW Amp Control | 40 | -100..+100 % |
| `20` | 1 | MW LFO PMod Depth | 0A | 0..127 |
| `21` | 1 | MW LFO FMod Depth | 0 | 0..127 |
| `22` | 1 | MW LFO AMod Depth | 0 | 0..127 |
| `23` | 1 | Bend Pitch Control | 42 | -24..+24 semi |
| `24` | 1 | Bend Filter Control | 40 | -9600..+9450 cent |
| `25` | 1 | Bend Amp Control | 40 | -100..+100 % |
| `26` | 1 | Bend LFO PMod Depth | 0 | 0..127 |
| `27` | 1 | Bend LFO FMod Depth | 0 | 0..127 |
| `28` | 1 | Bend LFO AMod Depth | 0 | 0..127 |
| `4D` | 1 | Ch AT Pitch Control | 40 | -24..+24 semi |
| `4E` | 1 | Ch AT Filter Control | 40 | -9600..+9450 cent |
| `4F` | 1 | Ch AT Amp Control | 40 | -100..+100 % |
| `50` | 1 | Ch AT LFO PMod Depth | 0 | 0..127 |
| `51` | 1 | Ch AT LFO FMod Depth | 0 | 0..127 |
| `52` | 1 | Ch AT LFO AMod Depth | 0 | 0..127 |
| `5A` | 1 | Poly AT Pitch Control | 40 | -24..+24 semi |
| `5B` | 1 | Poly AT Filter Control | 40 | -9600..+9450 cent |
| `5C` | 1 | Poly AT Amp Control | 40 | -100..+100 % |
| `5D` | 1 | Poly AT LFO PMod Depth | 0 | 0..127 |
| `5E` | 1 | Poly AT LFO FMod Depth | 0 | 0..127 |
| `5F` | 1 | Poly AT LFO AMod Depth | 0 | 0..127 |
| `60-64` | 5 | Scale Tuning C..E (5 note) | 40 | -64..+63 cent |
| `65-6B` | 7 | Scale Tuning F..B (7 note) | 40 | -64..+63 cent |
| `67` | 1 | Portamento Switch | 0 | off/on |
| `68` | 1 | Portamento Time | 0 | 0..127 |
| `69` | 1 | Pitch EG Initial Level | 40 | -64..+63 |
| `6A` | 1 | Pitch EG Attack Time | 40 | -64..+63 |
| `6B` | 1 | Pitch EG Release Level | 40 | -64..+63 |
| `6C` | 1 | Pitch EG Release Time | 40 | -64..+63 |

## Drum Setup (Table 1-6)

Indirizzo: `3n rr XX` dove `n` = Drum Setup Number - 1 (0 o 1), `rr` = MIDI note number 0x0D..0x5B. Totale **0x10 (16 byte)** per nota.

| Offset | Parameter | Range |
|--------|-----------|-------|
| `00` | Pitch Coarse | -64..+63 semi |
| `01` | Pitch Fine | -64..+63 cent |
| `02` | Level | 0..127 |
| `03` | Alternate Group | 0..127 |
| `04` | Pan | 0=random, L..R |
| `05` | Reverb Send | 0..127 |
| `06` | Chorus Send | 0..127 |
| `07` | Variation Send | 0..127 |
| `08` | Key Assign | single, multi |
| `09` | Rcv Note Off | off, on |
| `0A` | Rcv Note On | off, on |
| `0B` | Filter Cutoff | -64..+63 |
| `0C` | Filter Resonance | -64..+63 |
| `0D` | EG Attack Rate | -64..+63 |
| `0E` | EG Decay1 Rate | -64..+63 |
| `0F` | EG Decay2 Rate | -64..+63 |

## XG Bulk Dump Request (address summary)

`F0 43 2n 4C AH AM AL F7` con le sub-addresses:

| Address | Description |
|---------|-------------|
| `00 00 00` | XG System |
| `02 01 00` | Multi Effect |
| `08 nn 00` | Multi Part (nn=part 0..0x1F) |
| `30 18 00` | Drum Setup 1 |
| `31 18 00` | Drum Setup 2 |

## Section Control (Pattern Mode)

```
F0 43 7E 00 ss dd F7
```

- `ss` = Style number (0-127)
- `dd` = Section byte: on/off

**Important**: "If System Software h = 0EH-0FH, dd=ON is received, the Pattern will be converted into QY700 sections A-H respectively."

Condizione `System Software h = 0E-0F` non chiarita nel PDF (probabilmente mode byte del trasmettitore — richiede test).

## Test Entry / LCD Hard Copy (ricezione)

Utili per screenshot o debug:
```
F0 43 10 7E 5A 01 F7    # Test Entry
F0 43 10 7E 5A 02 F7    # LCD Hard Copy
```

## MIDI Machine Control (MMC) — ricevuti se MIDI Sync = MTC

| Command | SysEx |
|---------|-------|
| STOP | `F0 7F 7F 06 01 F7` |
| DEFERRED PLAY | `F0 7F 7F 06 03 F7` |
| LOCATE | `F0 7F 7F 06 44 06 01 hr mn sc fr ff F7` (HH:MM:SS:FF + subframe) |

## System Realtime (TX dal sequencer part)

| Status | Name |
|--------|------|
| `F8` | Timing Clock |
| `FA` | Start |
| `FB` | Continue |
| `FC` | Stop |
| `F2 ll hh` | Song Position Pointer |
| `F1 dd` | MTC Quarter Frame |

## Active Sensing

- **TX**: intervallo 200ms
- **RX**: timeout 350ms → clear buffer + All Notes Off + All Sustain Off

## Control Changes (ricevuti)

| # | Parameter |
|---|-----------|
| 0 | Bank Select MSB |
| 1 | Modulation |
| 5 | Portamento Time |
| 6 | Data Entry MSB |
| 7 | Volume |
| 10 | Pan |
| 11 | Expression |
| 16 | AC1 controller |
| 32 | Bank Select LSB |
| 38 | Data Entry LSB |
| 64 | Sustain |
| 65 | Portamento Switch |
| 66 | Sostenuto |
| 67 | Soft Pedal |
| 71 | Harmonic Content |
| 72 | Release Time |
| 73 | Attack Time |
| 74 | Brightness |
| 84 | Portamento Control |
| 91 | Effect Send Level 1 (Reverb) |
| 93 | Effect Send Level 3 (Chorus) |
| 94 | Effect Send Level 4 (Variation, **solo se Variation Mode = System**) |
| 96 / 97 | Data Inc / Dec |
| 98 / 99 | NRPN LSB / MSB |
| 100 / 101 | RPN LSB / MSB |
| 120 | All Sound Off |
| 121 | Reset All Controllers |
| 123-127 | All Notes Off / Omni Off / Omni On / Mono On / Poly On |

## RPN

| LSB/MSB | Parameter | Range |
|---------|-----------|-------|
| 00 / 00 | Pitch Bend Sensitivity | 0..24 semi |
| 00 / 01 | Master Fine Tune | ±100 cent |
| 00 / 02 | Master Coarse Tune | ±24 semi |
| 7F / 7F | RPN Reset | — |

## NRPN — Drum Instrument Params (valido solo su canale Drum Set)

MSB range `14H..1FH`, LSB = numero nota drum. Consente di modificare parametri drum per-nota al volo senza Drum Setup SysEx.

| MSB | Parameter |
|-----|-----------|
| 14 | Filter Cutoff Freq |
| 15 | Filter Resonance |
| 16 | EG Attack Rate |
| 17 | EG Decay Rate |
| 18 | Pitch Coarse |
| 19 | Pitch Fine |
| 1A | Level |
| 1C | Panpot (0=random, 01..7F) |
| 1D | Reverb Send |
| 1E | Chorus Send |
| 1F | Variation Send |

## MIDI Implementation Chart (sintesi)

**TX**: Note On/Off (9n), Pitch Bend (En), Assignable Wheel, Foot SW, CH AT (Dn), PC (Cn) con Bank MSB+LSB (CC 0, 32), tutti i CC 0-121, SysEx (bulk/param change), Master Volume universal, Identity Reply, Active Sensing.

**TX (sequencer part)**: aggiungi System Realtime F8/FA/FB/FC e SPP F2.

**RX**: tutti i CC 0-121, Poly AT (ricevuto ma NON trasmesso), Mono/Poly mode (Mode 3 default, 1-4 supportati), MMC (se MTC sync).

## MIDI Utility Settings

On QY700: `UTILITY → F2 (MIDI)`. Vedi [QY700 Utility Mode](qy700-utility-mode.md) per il dettaglio completo.

| Setting | Options | Per il nostro uso |
|---------|---------|-------------|
| MIDI Sync | Internal, MIDI-A, MIDI-B, MTC:A, MTC:B | **Internal** |
| MIDI Control In | Off, In-A, In-B, In-A,B | **In-A** |
| MIDI Control Out | Off, Out-A, Out-B, Out-A,B | **Out-A** |
| XG Parameter Out | Off, Out-A, Out-B, Out-A,B | Out-A se serve |
| Echo Back In-A | Off, Thru A/B/A,B, RecMonitor | **Off** |

**SysEx > 128 byte NON è mai echoed back** (hardcoded).

## Hardware Notes

- 4 MIDI connectors: IN-A, IN-B, OUT-A, OUT-B
- LED indicators per ogni porta (blink on data activity)
- OUT-A/B LEDs blinkano normalmente (MIDI Clock trasmesso)
- Floppy disk drive per scambio file Q7P/Q7S/Q7A

## Connection Diagram

```
Computer USB MIDI Cable                  QY700
  MIDI OUT (cable label) ────────> MIDI IN-A
  MIDI IN  (cable label) <──────── MIDI OUT-A
```

## Verified (Session 23)

- [x] Identity Reply: `F0 7E 7F 06 02 43 00 41 01 79 00 00 00 01 F7` (Member=0x7901)
- [x] XG Dump Request works for all types: System, SystemInfo, Effect, MultiPart, DrumSetup
- [x] SystemInfo returns model name "QY700" (16 bytes at addr 01/00/00)
- [x] Device number = 0 (default)
- [x] USB MIDI Cable IN connector broken — use Steinberg UR22C instead

## Open Questions

- [ ] Can we load pattern data via XG bulk dump? Or only floppy disk?
- [ ] Section Control: qual è il byte `System Software h` (0E-0F) che abilita A-H? Test necessario.
- [ ] Read all 32 Multi Part configurations for voice mapping
