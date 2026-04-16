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

## Cross-Track Field Analysis (Session 25c)

Comparing CHD1 and PHR1 bar headers in Summer reveals which 9-bit fields encode **chord info** vs **pattern-specific data**.

### Fields SHARED between CHD1 and PHR1 (same bar)

These fields are always identical between both chord tracks for the same bar, so they encode **chord/harmony information**:

| Field | Bar 0 | Bars 1-3 | Notes |
|-------|-------|----------|-------|
| F0 | 429 | 53 | Changes only at bar 0 (init bar) |
| F5 | 84 | 77 (bars 1-2), 502 (bar 3) | Changes per chord |

F1 is also shared for bars 1-3 (=85) but differs in bar 0 (CHD1=17, PHR1=32).

### Fields that DIFFER between CHD1 and PHR1

These encode **pattern-specific voicing/articulation data**:

| Field | Behavior |
|-------|----------|
| F2 | CHD1≈8, PHR1≈17 (track type indicator?) |
| F3 | Different per track AND per bar |
| F4 | Different per track AND per bar |
| F7-F9 | Highly variable between tracks |

### Raw Header Byte Similarity

Summer CHD1 raw headers:
```
Bar 0: D6 84 46 C5 05 61 51 09 8B 3A 8B C3 22  (init bar)
Bar 1: 1A 95 41 11 3B 21 34 AB 82 A3 12 42 70  (C major)
Bar 2: 1A 95 41 25 61 21 34 AB 82 CB 3A 42 70  (E minor)
Bar 3: 1A 95 41 05 5B 0F D8 3A 95 41 05 53 21  (D major)
```

Bars 1-2 share **9 of 13 bytes** — only 4 bytes encode the C→Em chord change (bytes 3, 4, 9, 10).

### Unsolved: Chord Transposition Formula

8 combinatorial approaches tested (Session 25c): single field+offset, field pair operations, root extraction, intervals, scale factors, nibble packing, raw byte matching, scale factor search. **ALL FAILED**. No consistent formula maps header fields to GT chord notes across 4 bars.

The QY70 likely uses a runtime voice-leading algorithm with chord table lookup, not a simple arithmetic transposition. See [Open Questions](open-questions.md).

See [Event Fields](event-fields.md) for how the 7-byte events decode, and [Bitstream](bitstream.md) for the rotation scheme.
