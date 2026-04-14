# Format Mapping QY70 ↔ QY700

Cross-format field correspondence between [QY70 SysEx](sysex-format.md) and [QY700 Q7P](q7p-format.md).

## Global Parameters

| Parameter | QY70 (SysEx) | QY700 (Q7P) | Status |
|-----------|-------------|-------------|--------|
| Tempo | Header decoded[0] + formula | `0x188` (BE, ÷10) | Mapped |
| Name | NOT in ASCII (proprietary) | `0x876` (10 ASCII bytes) | QY70→QY700 only |
| Time Sig | Header flags | `0x18A` (lookup table) | Partial |
| Sections | Header 0x221 flags | `0x100` pointers (0xFEFE=empty) | Conceptual |

## Track Mapping

| QY70 (8 tracks) | QY700 (16 tracks) | Notes |
|-----------------|-------------------|-------|
| RHY1 (slot 0) | TR1 (ch 10) | Drum primary |
| RHY2 (slot 1) | TR2 (ch 10) | Drum secondary |
| BASS (slot 2) | TR3 (ch 2) | Bass |
| CHD1 (slot 3) | TR4 (ch 3) | Chord 1 |
| CHD2 (slot 4) | TR5 (ch 4) | Chord 2 |
| PAD (slot 5) | TR6 (ch 5) | Pad |
| PHR1 (slot 6) | TR7 (ch 6) | Phrase 1 |
| PHR2 (slot 7) | TR8 (ch 7) | Phrase 2 |
| — | TR9-TR16 | Not used in conversion |

## Per-Track Parameters

| Parameter | QY70 Track Header | QY700 Offset | Status |
|-----------|------------------|-------------|--------|
| Channel | Default per slot | `0x190 + track` | Mapped |
| Volume | [Header section](header-section.md) mixer area | `0x226 + track` | Mapped |
| Pan | Track header byte 22 | `0x276 + track` | Mapped (fixed bounds) |
| Reverb | Header mixer area | `0x256 + track` | Mapped |
| Chorus | Header mixer area | `0x246 + track` | Mapped |
| Voice (Bank/Prg) | Track header bytes 14-15 | `0x1E6/0x1F6/0x206` | **DISABLED** — see [bricking](bricking.md) |

## Event Data — NOT YET MAPPED

The musical event formats are completely different:

| Aspect | QY70 | QY700 |
|--------|------|-------|
| Encoding | [Packed bitstream](bitstream.md) (9-bit fields, barrel rotation) | Byte-oriented commands |
| Note events | Chord-tone [mask](event-fields.md#f4-chord-tone-mask) | `E0 nn vv` (note, velocity) |
| Timing | [F5 field](event-fields.md#f5-timing) with sub-beat encoding | `A0-A7` delta time commands |
| Bar markers | [DC/9E delimiters](bar-structure.md#delimiters) | `F2` end-of-phrase |
| Chord info | [13-byte bar header](bar-structure.md#13-byte-bar-headers) | Explicit note events |

Event conversion is the #1 blocker for full format conversion. Current state: 0% implemented.

See [Decoder Status](decoder-status.md) for progress on QY70 event decoding.
