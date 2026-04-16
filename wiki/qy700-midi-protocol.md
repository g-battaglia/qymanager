# QY700 MIDI Protocol

Reference: QY700_REFERENCE_LISTING.pdf, pages 33-42.

## Key Difference from QY70

| Property | QY70 | QY700 |
|----------|------|-------|
| Model ID | `5F` | `4C` (XG) |
| Identity Family | `0x4100` | `0x4100` |
| Identity Member | `0x5502` | `0x1901` |
| Bulk Dump Init | Required (`F0 43 10 5F 00 00 00 01 F7`) | NOT required |
| Dump Request | `F0 43 20 5F AH AM AL F7` | `F0 43 2n 4C AH AM AL F7` |
| MIDI Ports | 1 IN, 1 OUT | 2 IN (A,B), 2 OUT (A,B) |
| Data Exchange | MIDI SysEx bulk dump | Floppy disk + MIDI XG SysEx |

## Identity

```
Request (received, Omni): F0 7E 7F 06 01 F7
Reply (transmitted):      F0 7E 0n 06 02 43 00 41 01 19 00 00 00 01 F7
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
- Checksum = lower 7 bits of `(0 - sum(AH, AM, AL, data_bytes))`
- Data > 512 bytes: split into 512-byte packets, with 120ms+ interval

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

### XG Bulk Dump Request (alternative)

`F0 43 2n 4C AH AM AL F7` with subset addresses:

| Address | Description |
|---------|-------------|
| `00 00 00` | XG System |
| `02 01 00` | Multi Effect |
| `08 nn 00` | Multi Part (nn=part) |
| `30 18 00` | Drum Setup |

## Parameter Change

`F0 43 1n 4C AH AM AL dd F7`

For 2-4 byte params, corresponding extra data bytes are added.

## Parameter Request

`F0 43 3n 4C AH AM AL F7`

Returns the current value via Parameter Change message.

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
| `08 10 00` | Multi Part 17 (QY700 extension?) |
| `30 18 00` | Drum Setup 1 |
| `31 18 00` | Drum Setup 2 |

## Multi Part Parameters (Table 1-5)

Key offsets within a part (address `08 nn XX`):

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

## Section Control (Pattern Mode)

```
F0 43 7E 00 ss dd F7
```

- `ss` = Style number (0-127)
- `dd` = Section byte: on/off

**Important**: "If System Software h = 0EH-0FH, dd=ON is received, the Pattern will be converted into QY700 sections A-H respectively."

This means we can potentially trigger section changes on the QY700 via MIDI.

## System Information (Table 1-3)

| Address | Size | Parameter | Default |
|---------|------|-----------|---------|
| `01 00 00 0E` | 20 | Model Name | "QY700" |
| `0F 01 00` | 1 | XG Support Level | 0..127 |

## MIDI Utility Settings

On QY700: `UTILITY → F2 (MIDI)`

| Setting | Options | For our use |
|---------|---------|-------------|
| MIDI Sync | Internal, MIDI-A, MIDI-B, MTC:A, MTC:B | **Internal** |
| MIDI Control In | Off, In-A, In-B, In-A,B | **In-A** (receive from PC) |
| MIDI Control Out | Off, Out-A, Out-B, Out-A,B | **Out-A** (send to PC) |
| XG Parameter Out | Off, Out-A, Out-B, Out-A,B | Out-A if needed |
| Echo Back In-A | Off, Thru A/B/A,B, RecMonitor | **Off** (avoid loops) |

## Hardware Notes

- 4 MIDI connectors: IN-A, IN-B, OUT-A, OUT-B
- LED indicators for each port (blink on data activity)
- OUT-A/B LEDs normally blink (MIDI Clock transmitted)
- Floppy disk drive for Q7P file exchange
- SysEx > 128 bytes NOT echoed back

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
- [ ] Section Control: does this work for loading converted patterns?
- [ ] Read all 32 Multi Part configurations for voice mapping
