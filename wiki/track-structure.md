# Track Structure

How the [QY70](qy70-device.md) organizes tracks within patterns and styles.

## 8 Track Slots

| Index | Slot Name | Default Channel | Preamble | Encoding |
|-------|-----------|-----------------|----------|----------|
| 0 | RHY1 | 10 | `2543` | [drum_primary](bitstream.md#preambles) |
| 1 | RHY2 | 10 | `29CB` | [general](bitstream.md#preambles) |
| 2 | BASS | 2 | `2BE3` or `29CB` | bass_slot or general |
| 3 | CHD1 | 3 | `29CB` | [general](bitstream.md#preambles) |
| 4 | CHD2 | 4 | `1FA3` | [chord](bitstream.md#preambles) |
| 5 | PAD | 5 | `29CB` | [general](bitstream.md#preambles) |
| 6 | PHR1 | 6 | `1FA3` | [chord](bitstream.md#preambles) |
| 7 | PHR2 | 7 | `1FA3` / `29CB` | chord (switches in fills) |

**Important**: slot names are fixed and do NOT reflect the actual voice assignment. A drum voice can occupy the BASS slot; a bass voice can be on CHD1.

## AL Addressing

```
AL = section_index * 8 + track_index
```

| Section | Index | AL Range |
|---------|-------|----------|
| Intro / Section 0 | 0 | `0x00-0x07` |
| Main A | 1 | `0x08-0x0F` |
| Main B | 2 | `0x10-0x17` |
| Fill AB | 3 | `0x18-0x1F` |
| Fill BA | 4 | `0x20-0x27` |
| Ending | 5 | `0x28-0x2F` |
| Header | — | `0x7F` |

Pattern format uses only section 0 (AL `0x00-0x07`).
Style format uses all 6 sections (AL `0x00-0x2F`).

## Track Data Layout (decoded bytes)

Each track's data has a fixed 24-byte header followed by a 4-byte preamble and the event data.

### 24-Byte Track Header

| Offset | Size | Description |
|--------|------|-------------|
| 0-11 | 12 | Fixed: `08 04 82 01 00 40 20 08 04 82 01 00` |
| 12-13 | 2 | Fixed: `06 1C` |
| 14-15 | 2 | Voice encoding (see below) |
| 16-17 | 2 | Note range (melody) or drum flags |
| 18-20 | 3 | Track type flags |
| 21 | 1 | `0x41` = pan enabled, `0x00` = default pan |
| 22 | 1 | Pan value (0-127, 64=center) |
| 23 | 1 | Unknown |

### Voice Encoding (bytes 14-15)

| Pattern | Bytes | Meaning |
|---------|-------|---------|
| Drum default | `40 80` | Standard Kit (Bank 127, Prg 0) |
| Bass marker | `00 04` | Fixed marker, actual voice via byte 26 |
| Explicit | `BB PP` | Bank MSB = BB, Program = PP |

### Data Sizes

| Track | Decoded Bytes | Messages |
|-------|---------------|----------|
| RHY1 | 768 | 6 × 128 |
| RHY2 | 256 | 2 × 128 |
| BASS | 128 or 256 | 1-2 × 128 |
| CHD1-PHR2 | 128-256 | 1-2 × 128 |

After the 24-byte header and 4-byte preamble, the remaining bytes are [event data](bar-structure.md) organized as bars with [13-byte headers](bar-structure.md#bar-headers) and [7-byte events](event-fields.md).
