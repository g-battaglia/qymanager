# Bar Structure

How musical bars are organized within [track data](track-structure.md).

## Layout

After the 24-byte track header and 4-byte [preamble](bitstream.md#preambles), the event data is organized as a sequence of bars:

```
[bar_header: 13 bytes][event_0: 7 bytes][event_1: 7 bytes]...[delimiter]...
```

## Delimiters

Two delimiter bytes separate structural units:

### DC (0xDC) — Bar Delimiter

Separates major bars. Found in chord tracks (multiple per message) and bass tracks with general encoding. After DC, a new 13-byte bar header follows.

### 9E (0x9E) — Sub-Bar Chord Change Delimiter

Separates **chord changes within a single bar**. When a bar contains multiple chords, each chord change gets its own sub-bar with a fresh 13-byte header.

**Example**: A bar with 3 chord changes produces:
```
[header_A][4 events]  9E  [header_B][4 events]  9E  [header_C][4 events]
```

**Hierarchy**: DC (bar boundary) > 9E (chord change within bar).

## 13-Byte Bar Headers

Each bar (or sub-bar) starts with a 13-byte header (104 bits).

### 9-Bit Field Decomposition

The header can be decomposed into 11 fields of 9 bits + 5 remainder bits.

For the SGT style, the first 5 fields were valid MIDI note numbers (chord voicing):
```
SGT C2: [63, 61, 59, 55, 36] = D#4, C#4, B3, G3, C2 (minor voicing)
```

For other patterns, fields 3-4 can be > 127 (bit 8 set), indicating an extended encoding not yet fully decoded.

### Byte-Level Structure (bars starting with 0x1A)

Bars 1+ in chord tracks show a consistent byte pattern:

| Byte | Value | Description |
|------|-------|-------------|
| 0 | `0x1A` | Bar header marker |
| 1-3 | varies | Chord/voicing info |
| 4 | `0x7F` | Fixed |
| 5 | `0x20-0x21` | Near-fixed |
| 6 | `0x34` | Fixed |
| 7-10 | varies | Additional chord data |
| 11 | `0x42` or `0x40` | Near-fixed |
| 12 | `0x70` or `0x78` | Near-fixed |

The first bar (bar 0) has a different header (starting with `0xDE` in captured data) — likely an initialization bar.

## Standard Bar Size

The most common bar structure is **41 bytes**:
```
13 bytes (header) + 4 × 7 bytes (events) = 41 bytes
```

Bars can also have 2 events (28 bytes + remainder) or more than 4 events.

## Padding

The last segment may contain zero-filled events (all bytes = 0x00), indicating unused/padding data.

See [Event Fields](event-fields.md) for how the 7-byte events decode, and [Bitstream](bitstream.md) for the rotation scheme.
