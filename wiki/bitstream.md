# Bitstream Encoding

The [QY70](qy70-device.md) stores musical events as a packed bitstream, fundamentally different from the [QY700](qy700-device.md)'s byte-oriented commands.

## Core Mechanism

Each 7-byte event (56 bits) is **barrel-rotated** before storage. Consecutive events within a bar are rotated by increasing multiples of 9 bits.

### Rotation

```python
def derotate(raw_bytes: bytes, event_index: int) -> int:
    val = int.from_bytes(raw_bytes, "big")  # 56-bit value
    shift = (event_index * 9) % 56
    return ((val >> shift) | (val << (56 - shift))) & ((1 << 56) - 1)
```

**R=9 right-rotate = R=47 left-rotate** (because 56 - 47 = 9). Both are the same operation. All encoding types use this rotation.

### 9-Bit Field Extraction

After de-rotation, the 56 bits decompose into **6 fields of 9 bits** + 2 remainder bits:

```
[F0: 9 bits][F1: 9 bits][F2: 9 bits][F3: 9 bits][F4: 9 bits][F5: 9 bits][R: 2 bits]
  bits 55-47   bits 46-38   bits 37-29   bits 28-20   bits 19-11   bits 10-2    bits 1-0
```

See [Event Fields](event-fields.md) for the meaning of each field.

## Preambles

Each track's data (after the 24-byte track header) starts with a 4-byte preamble. The first 2 bytes determine the encoding type:

| Preamble | Encoding | Tracks | Confidence |
|----------|----------|--------|------------|
| `1FA3` | chord | CHD2, PHR1, PHR2 | 82% |
| `29CB` | general | RHY2, CHD1, PAD (and sometimes BASS) | 38% |
| `2BE3` | bass_slot | BASS (when bass voice) | 38% |
| `2543` | drum_primary | RHY1 | 61% |

Preambles are **slot-based** (fixed per track index), NOT voice-based. The encoding type is independent of the voice assignment.

**Exception**: PHR2 (slot 7) switches from `1FA3` to `29CB` in fill sections.

## Shift Register (F0-F2)

Fields F0, F1, F2 carry "history" — they contain values from previous events (shift register pattern). When the chord is the same across beats, F0-F2 are identical. When the chord changes, ALL fields change dramatically.

## Cross-Section Behavior

When sections share the same chord, ALL 6 fields are IDENTICAL across sections. Sections with different chords produce completely different event data.

## Empty-Marker Pattern

The QY70 marks empty/default data with a distinctive 7-byte pattern:
```
BF DF EF F7 FB FD FE
```

Each byte is `0xFF` with one bit (6→0) cleared in descending order. This fills unused mixer slots and track data areas.

See also: [Bar Structure](bar-structure.md), [Event Fields](event-fields.md), [Decoder Status](decoder-status.md).
