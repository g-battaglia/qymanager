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
- **Bulk Dump**: triggered manually via UTILITY → MIDI → Bulk Dump → Style
- **Dump Request**: NOT supported remotely — device does not respond to `F0 43 2n 5F AH AM AL F7`
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

## Known Limitations

- Style name is NOT stored in ASCII in the bulk dump (proprietary encoding or not stored)
- Dump Request is not supported — bulk dump must be triggered from the device menu
- Cross-device .syx files (QY100 → QY70) require checksum modification
