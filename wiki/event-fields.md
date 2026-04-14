# Event Fields

After [de-rotation](bitstream.md), each 7-byte (56-bit) event decomposes into 6 fields of 9 bits each, plus 2 remainder bits.

## Field Map

| Field | Bits | Purpose | Confidence |
|-------|------|---------|------------|
| F0 | 55-47 | Shift register (history from 2 beats ago) | High |
| F1 | 46-38 | Shift register (history from 1 beat ago) | High |
| F2 | 37-29 | Shift register (current beat echo) | High |
| F3 | 28-20 | Beat counter + track type | High |
| F4 | 19-11 | Chord-tone mask + parameter | Medium |
| F5 | 10-2 | Timing/gate | Medium |
| R | 1-0 | Remainder (unknown) | Low |

## F3: Beat Counter

F3 decomposes as: `[hi2: 2 bits][mid3: 3 bits][lo4: 4 bits]`

### lo4 — Beat Position

| lo4 | Binary | Beat |
|-----|--------|------|
| 0 | `0000` | Beat 0 (or sustain from previous bar) |
| 8 | `1000` | Beat 0 (one-hot form) |
| 4 | `0100` | Beat 1 |
| 2 | `0010` | Beat 2 |
| 1 | `0001` | Beat 3 |

Beat accuracy: **90%** for chord tracks, **100%** for bass tracks.

### mid3 — Track Type Indicator

The value `101` (5) appears consistently in bars 1+ of chord tracks. Other values observed but not yet classified.

### hi2 — Unknown

Varies: `11`, `01`, `00` observed. Possibly voicing register or articulation flag.

## F4: Chord-Tone Mask

F4 decomposes as: `[mask5: 5 bits][param4: 4 bits]`

### mask5 — Note Selection

A 5-bit mask selecting which of the 5 [bar header](bar-structure.md) chord notes to play:

| Mask | Binary | Notes Selected |
|------|--------|----------------|
| `01011` | bits 0,1,3 | Notes 1, 2, 4 (most common: 3-note voicing) |
| `01010` | bits 1,3 | Notes 2, 4 (2-note voicing) |
| `01101` | bits 0,2,3 | Notes 1, 3, 4 |
| `11001` | bits 0,3,4 | Notes 1, 4, 5 |
| `00010` | bit 1 | Note 2 only (single note) |

### param4 — Event Parameter

Common values: `0100`, `1000`, `1010`, `1100`. Likely velocity, gate length, or articulation. Not yet decoded.

## F5: Timing

F5 decomposes as: `[top2: 2 bits][mid4: 4 bits][lo3: 3 bits]`

Observed values cluster around 84-147 for normal events, 261-311 for initialization bar events.

In normal bars, `lo3` is consistently 4 and `top2` is 0, with `mid4` varying: 10, 12, 13, 14. This suggests mid4 encodes the sub-beat position within the bar.

The "+16 per beat" hypothesis from earlier sessions is approximate — actual spacing is more nuanced with 8th-note resolution possible.

## F0-F2: Shift Register

These three fields carry values from the previous 2 events (shift register / history). When the chord is the same, F0-F2 are identical between events at the same position across sections. When the chord changes, F0-F2 change dramatically.

E0 (first event in a bar) always has a high F0 value (~0x119), suggesting initialization of the shift register.

See [Bitstream](bitstream.md) for the rotation scheme, [Bar Structure](bar-structure.md) for overall organization.
