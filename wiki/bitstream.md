# Bitstream Encoding

The [QY70](qy70-device.md) stores musical events as a packed bitstream, fundamentally different from the [QY700](qy700-device.md)'s byte-oriented commands.

## Core Mechanism

Each 7-byte event (56 bits) is **barrel-rotated** before storage. Consecutive events within a bar are rotated by increasing multiples of 9 bits.

### Rotation

**R=9 right-rotate = R=47 left-rotate** (because 56 - 47 = 9). Both are the same operation.

All encoding types appear to use **cumulative** rotation:

| Preambles | Shift Amount | Confidence |
|-----------|-------------|------------|
| `1FA3`, `2D2B`, `303B`, `29CB`, `2BE3` | `(event_index + 1) × 9` | **Proven** (1FA3, 2543), High (others) |
| `2543` | `(event_index + 1) × 9` | **Proven** (7/7 known_pattern.syx) |

```python
# Cumulative rotation (all encodings)
def derotate(raw_bytes: bytes, event_index: int) -> int:
    val = int.from_bytes(raw_bytes, "big")
    shift = ((event_index + 1) * 9) % 56
    return ((val >> shift) | (val << (56 - shift))) & ((1 << 56) - 1)
```

**2543 PROVEN** (Session 14): R=9×(i+1) definitively proven with known_pattern.syx — 7/7 events match perfectly on all fields (note, velocity, tick, gate). Event index resets per segment at DC delimiter. See [2543 Encoding](2543-encoding.md#rotation--proven-cumulative-r9i1).

**2D2B/303B = chord variants** (Session 14): preambles 2D2B and 303B use identical encoding as 1FA3 — same F4 chord masks, F5 timing, and event similarity patterns. The preamble value encodes track-level metadata, not a different data format.

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
| `2543` | [drum_primary](2543-encoding.md) | RHY1 (+ all Pattern mode tracks) | 77% |

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

## Dense Encoding Structure (Sessions 29c-e)

Il modello cumulativo R=9×(i+1) funziona SOLO su pattern sparse (utente). Per pattern dense (stili factory come Summer e SGT) la struttura è diversa:

### Per-beat rotation (Session 29c, ground truth Summer)

Eventi 7-byte (56 bit), uno per quarter-note beat. **Rotazione ottimale DIVERSA per beat position**:

| Beat | Strike pattern | R ottimale | Bit constanti (bars 1/2/4) |
|------|----------------|------------|-------------------------------|
| 0 | (36@0,42@0,42@1) | 0 | 32/56 |
| 1 | (38@0,42@0,42@1) | 2 | 32/56 |
| 2 | (42@0,36@1,42@1) | 1 | **44/56** |
| 3 | (42@0,42@1) | 0 | — |

**Bar 3 è outlier CONSISTENT** → segment 3 diverso da bars 1/2/4 (MAIN B o FILL).

### Cross-track byte sharing (Session 29c)

Byte-template invarianti tra tracce diverse (CHD1 `2D2B` e PHR2 `303B`):

| Beat | Byte condivisi CHD1/PHR2 |
|------|--------------------------|
| 1 | byte 0, 5, 6 |
| 2 | byte 4, 5, 6 |
| 3 | byte 5 |

I "beat-template bytes" codificano GROOVE/TIMING invariante rispetto al tipo di track.

### SGT super-cycle 42B (Session 29d-e)

Decodificato `QY70_SGT.syx` → 13184 byte 8-bit. Struttura multi-sezione:

- **6 preamble RHY1** (`25 43 60 00`) a offset 24, 2200, 4248, 6296, 8472, 10648
- **Preamble identico a Summer** (28 byte terminating `00 00 00 25 43 60 00`)
- **692-byte shared prefix** tra tutte 6 sezioni → divergenza inizia a byte 692 (non byte 28)
- **Section sizes asimmetriche**: 2176, 2048, 2048, 2176, 2176, 2539 (MAIN/FILL/INTRO/ENDING)
- **Periodo 42 byte (6 × 7-byte events)** dominante in autocorrelazione byte-by-byte
- **Sec2 MAIN B**: eventi 1/2/3 byte-identici (`c7e37178be9f8f`) → dense encoding byte-aligned
- **Trailer 16B** condiviso tra Sec1/Sec2/Sec4 e tra Sec3/Sec5

### Open problems

- Mappatura 44-bit "pattern ID" (beat 2 Summer) → MIDI strike (note 36/38/42)
- Interpretazione 12-24 variable bit (velocity? groove humanization?)
- Mappatura 42B super-cycle SGT → beats/subdivisions MIDI
- Confronto SGT/Summer: Summer = 28B period (4 beats), SGT = 42B period (6 events) — stesso encoding con granularità diversa?

Vedi [Open Questions](open-questions.md) Session 29c/29d/29e.

## SysEx Bulk Dump Format

QY70 style data is transmitted as Yamaha SysEx bulk dump messages:

```
F0 43 0n 5F BH BL AH AM AL [encoded_data] CS F7
```

**Key rules** (discovered Session 15, verified against all captures):

| Field | Value | Notes |
|-------|-------|-------|
| BC = BH<<7 \| BL | `len(encoded_data)` = **147** | NOT 3+len(encoded). Does not include AH AM AL |
| Decoded block size | **128 bytes** always | Last block zero-padded |
| Message total | **158 bytes** always | 9 header + 147 payload + 1 checksum + 1 F7 |
| Checksum region | BH BL AH AM AL + encoded | `(128 - (sum & 0x7F)) & 0x7F` |
| AH AM | `0x02 0x7E` | Style edit buffer |
| AL | `section*8 + track` | 0x00-0x37 for tracks, 0x7F for header |

**Confidence**: High — verified against `user_style_live.syx` (17/17 checksums), `QY70_SGT.syx` (103/103 checksums), `qy70_dump_20260414_114506.syx` (6/6 checksums). Only `ground_truth_style.syx` has 2 corrupted messages from capture errors.

See also: [Bar Structure](bar-structure.md), [Event Fields](event-fields.md), [Decoder Status](decoder-status.md).
