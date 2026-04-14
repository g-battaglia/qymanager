# Yamaha QY70

Portable sequencer and style player. Part of the Yamaha QY series.

## Specifications

| Property | Value |
|----------|-------|
| Tracks | 8 (RHY1, RHY2, BASS, CHD1, CHD2, PAD, PHR1, PHR2) |
| Sections | 6 (Intro, Main A, Main B, Fill AB, Fill BA, Ending) |
| Tone Generator | Yamaha XG (Model ID `0x4C`) |
| Sequencer Model ID | `0x5F` |
| MIDI Identity | Family `0x4100`, Member `0x5502` |
| Data Format | SysEx bulk dump (`.syx`) |
| Style Format | Packed [bitstream](bitstream.md) with [7-bit encoding](7bit-encoding.md) |

## MIDI Communication

- **Identity Reply**: `F0 7E 7F 06 02 43 00 41 02 55 00 00 00 01 F7`
- **Bulk Dump**: can also be triggered manually via UTILITY → MIDI → Bulk Dump → Style
- **Dump Request**: supported for individual patterns (substatus `0x20`):
  - Format: `F0 43 20 5F AH AM AL F7`
  - AM=`00`-`3F` = individual user patterns (Table 1-9 shows Req=O)
  - AM=`7E` = edit buffer (used in DATA messages, NOT valid for requests)
  - AM=`7F` = "all patterns" bulk request — NOT supported (Table 1-9 shows Req=X)
  - Source: QY70 List Book (QY70E2.PDF), Section 3-6-3-4, Table 1-9
- **XG Parameters**: Model ID `0x4C` for tone generator (voices, effects)
- **Sequencer Data**: Model ID `0x5F` for pattern/style data

## Track Slots

Slot names are fixed and do NOT indicate the actual voice assignment. A drum voice can be on the BASS slot, a bass voice on CHD1, etc.

| Slot | Name | Default Channel | Typical Voice |
|------|------|-----------------|---------------|
| 0 | RHY1 | 10 | Drums (primary) |
| 1 | RHY2 | 10 | Drums (secondary) |
| 2 | BASS | 2 | Bass |
| 3 | CHD1 | 3 | Chord 1 |
| 4 | CHD2 | 4 | Chord 2 |
| 5 | PAD | 5 | Pad |
| 6 | PHR1 | 6 | Phrase 1 |
| 7 | PHR2 | 7 | Phrase 2 |

See [Track Structure](track-structure.md) for full details on encoding per slot.

## Pattern vs Style

| Format | Header[0] | Sections | AL Range |
|--------|-----------|----------|----------|
| Pattern | `0x4C` | 1 (section 0 only) | `0x00-0x07` |
| Style | `0x5E` | 6 | `0x00-0x2F` |

See [SysEx Format](sysex-format.md) and [Header Section](header-section.md).

## MIDI Output for Pattern/Style Playback

By default, pattern playback data is **NOT transmitted** via MIDI OUT. To enable:

**UTILITY → MIDI → PATT OUT CH** (default: Off)

| Setting | Effect |
|---------|--------|
| **Off** | No pattern data on MIDI OUT (default) |
| **1~8** | Pattern tracks → MIDI ch 1-8 |
| **9~16** | Pattern tracks → MIDI ch 9-16 |

Channel mapping (Style track → Pattern track → MIDI ch):

| Style Track | Pattern Track | 1~8 | 9~16 | **Confirmed** |
|-------------|---------------|-----|------|---------------|
| RHY1 (slot 0) | D1 (Drum 1) | ch 1 | ch 9 | **Yes** (Session 13) |
| RHY2 (slot 1) | D2 (Drum 2) | ch 2 | ch 10 | — |
| PAD (slot 5) | PC (Percussion) | ch 3 | ch 11 | — |
| BASS (slot 2) | BA (Bass) | ch 4 | ch 12 | **Yes** (Session 13) |
| CHD1 (slot 3) | C1 (Chord 1) | ch 5 | ch 13 | **Yes** (Session 13) |
| CHD2 (slot 4) | C2 (Chord 2) | ch 6 | ch 14 | **Yes** (Session 13) |
| PHR1 (slot 6) | C3 (Chord 3) | ch 7 | ch 15 | — |
| PHR2 (slot 7) | C4 (Chord 4) | ch 8 | ch 16 | — |

Note: PAD→PC and PHR1/PHR2→C3/C4 mapping is inferred from position order, not yet hardware-confirmed.

Related MIDI parameters (same UTILITY → MIDI screen):
- **MIDI SYNC**: Internal/External — set to Internal for standalone operation
- **MIDI CONTROL**: Off/In/Out/In/Out — set to "In" or "In/Out" to accept MIDI Start/Stop from computer
- **ECHO BACK**: Off/Thru/RecMontr — controls MIDI IN→OUT echo
- **XG PARM OUT**: Off/On — transmit XG voice/effect parameters on song/pattern change

Source: QY70 Owner's Manual, page 222-224.

## Known Limitations

- Style name is NOT stored in ASCII in the bulk dump (proprietary encoding or not stored)
- Dump Request for "all patterns" (AM=7F) is not supported — use individual addresses AM=00-3F
- Cross-device .syx files (QY100 → QY70) require checksum modification
- ~~**Identity Request**~~: QY70 **DOES** respond correctly (Session 16). Previous "no response" finding was caused by mido SysEx bug on macOS. Reply: `F0 7E 7F 06 02 43 00 41 02 55 00 00 00 01 F7`.
- **mido SysEx bug**: mido silently drops ALL SysEx messages on macOS CoreMIDI. Use `rtmidi` directly for all SysEx communication.
- **Style track output**: defaults to internal only — must set PATT OUT CH to 1~8 or 9~16 to capture playback via MIDI
