# QY70 ↔ QY700 Header Field Mapping

This document maps equivalent fields between the QY70 SysEx format and QY700 Q7P format.

## Overview

| Aspect | QY70 (.syx) | QY700 (.Q7P) |
|--------|-------------|--------------|
| Format | SysEx messages | Binary file |
| Size | Variable (~16KB style) | Fixed 3072/5120 bytes |
| Encoding | 7-bit packed per message | Raw 8-bit |
| Tracks | 8 (D1,D2,PC,BA,C1-C4) | 16 (TR1-TR16) |
| Sections | 6 (Intro,MainA,MainB,FillAB,FillBA,Ending) | 6 or 12 |

## Global Header Fields

| Field | QY70 Offset | QY700 Offset | Encoding | Notes |
|-------|-------------|--------------|----------|-------|
| Format marker | 0x000 | 0x000 | 1 byte | QY70: 0x5E=style, 0x2C=pattern; QY700: "YQ7PAT" |
| Tempo | RAW msg[2:4] | 0x188-0x189 | See below | QY70: `(range*95-133)+offset`; QY700: big-endian ÷10 |
| Time signature | 0x00C? | 0x18A | Lookup | Both use table mapping |
| Pattern name | Not stored | 0x876-0x87F | ASCII | QY70 doesn't store name in bulk dump |

### Tempo Encoding

**QY70:**
```
tempo_bpm = (range_byte * 95 - 133) + offset_byte
range = raw_payload[0]  (after address, before 7-bit decode)
offset = raw_payload[1]
```

**QY700:**
```
tempo_bpm = struct.unpack(">H", data[0x188:0x18A])[0] / 10.0
```

## Track Mapping

QY70 has 8 tracks, QY700 has 16. The mapping is:

| QY70 Track | Default Ch | QY700 Track | Notes |
|------------|------------|-------------|-------|
| D1 (Drum 1) | 10 | TR1, TR2 (RHY) | Drums share channel 10 |
| D2 (Drum 2) | 10 | TR1, TR2 (RHY) | Secondary drum pattern |
| PC (Perc/Chord) | 3 | TR8+ | Percussion or chord pad |
| BA (Bass) | 2 | TR3 (BASS) | Bass line |
| C1 (Chord 1) | 4 | TR4 (CHD1) | Chord track 1 |
| C2 (Chord 2) | 5 | TR5 (CHD2) | Chord track 2 |
| C3 (Chord 3) | 6 | TR6 (PAD) | Pad/atmosphere |
| C4 (Chord 4) | 7 | TR7 (PHR) | Phrase/melody |

## Track Settings Offsets

### QY70 Track Header (24 bytes, per track per section)

Located at decoded track data bytes 0-23 (before event data):

| Offset | Size | Content | Notes |
|--------|------|---------|-------|
| 0-11 | 12 | Fixed prefix | `08 04 82 01 00 40 20 08 04 82 01 00` |
| 12-13 | 2 | Constants | `06 1C` |
| 14 | 1 | Bank MSB / Voice flag | 0x40=drum default, N=bank_msb |
| 15 | 1 | Program / Voice flag | 0x80=drum, 0x04=bass marker, N=program |
| 16 | 1 | Note low | 0x87=drum, else MIDI note |
| 17 | 1 | Note high | 0xF8=drum, else MIDI note |
| 18-20 | 3 | Track type flags | 0x80 0x8E 0x83=drum, varies for melody |
| 21 | 1 | Pan flag | 0x41=valid, 0x00=use default |
| 22 | 1 | Pan value | 0-127 (64=center) |
| 23 | 1 | Reserved | Always 0x00 |

### QY700 Track Settings

| Setting | Offset | Size | Notes |
|---------|--------|------|-------|
| Volume | 0x226+ | 1 per track | 0-127, default 100 (0x64) |
| Unknown CC#74? | 0x236+ | 1 per track | 0-127, default 64 (0x40) — Session 5 |
| Chorus Send | 0x246+ | 1 per track | 0-127, default 0 — **Session 5 confirmed** |
| Reverb Send | 0x256+ | 1 per track | 0-127, default 40 (0x28) |
| Pan | 0x276+ | 1 per track | 0-127, default 64 (0x40=center) |
| Channel | 0x190+ | 1 per track | 0x00=Ch10, else value+1 |
| Bank MSB | 0x1E6+ | 1 per track | 0-127 — ⚠ UNCONFIRMED |
| Program | 0x1F6+ | 1 per track | 0-127 — ⚠ UNCONFIRMED |
| Bank LSB | 0x206+ | 1 per track | 0-127 — ⚠ UNCONFIRMED |

### Q7P Section Config (0x120+)

**Session 5 discovery:** Section config entries are 9-byte records:

```
F0 00 FB pp 00 tt C0 bb F2
```

| Field | Description |
|-------|-------------|
| pp | Phrase index |
| tt | Track reference |
| bb | Bar count (after C0 prefix) |

Section pointers at 0x100+ are 2-byte BE offsets relative to 0x100.
`0xFEFE` = empty section.

### Q7P F1 Record (Session 5)

Optional inline parameter overrides at 0x129+ (87 bytes in T01.Q7P).
Contains per-section volume/reverb/pan overrides. Absent in empty templates.

## AL Address Mapping (QY70)

**CORRECTED SCHEME (2026-02-26):**

```
AL = section_index * 8 + track_index

Section 0 (Intro):   AL 0x00-0x07 (8 tracks)
Section 1 (Main A):  AL 0x08-0x0F
Section 2 (Main B):  AL 0x10-0x17
Section 3 (Fill AB): AL 0x18-0x1F
Section 4 (Fill BA): AL 0x20-0x27
Section 5 (Ending):  AL 0x28-0x2F
Header:              AL 0x7F (640 bytes decoded)
```

**There is NO separate "phrase data" region.** All AL 0x00-0x2F addresses contain track data.

## Track Data Sizes

Typical sizes per track (decoded):

| Track | Size | Messages | Notes |
|-------|------|----------|-------|
| D1 | 768 bytes | 6 × 128 | Main drum pattern |
| D2 | 256 bytes | 2 × 128 | Secondary drums |
| PC | 128 bytes | 1 × 128 | Percussion/chord |
| BA | 256 bytes | 2 × 128 | Bass line |
| C1-C4 | 128-256 bytes | 1-2 × 128 | Chord tracks |

## Voice Encoding Differences

### QY70

- Drum tracks: bytes 14-15 = `0x40 0x80` (use default kit)
- Bass track: bytes 14-15 = `0x00 0x04` (marker, actual voice elsewhere)
- Chord tracks: bytes 14-15 = Bank MSB + Program directly

### QY700

- All tracks: Voice stored in separate voice assignment area (TBD offset)

## Event Data Format

### QY700 (Q7P)

Uses byte-oriented command set with fixed-size opcodes:
- `D0 nn vv xx` = Drum note (4 bytes)
- `E0 nn vv xx` = Melody note (4 bytes)
- `A0-A7 dd` = Delta time (2 bytes)
- `BE xx` = Note off (2 bytes)
- `BC xx` = Control change (2 bytes)
- `DC` = Bar delimiter (1 byte)
- `F0 00` = MIDI data start (2 bytes)
- `F2` = End of phrase (1 byte)
- `00` = Terminator (1 byte)

### QY70

**DEFINITIVELY NOT the same format as Q7P.** (Confirmed 2026-02-27 by
`midi_tools/parse_events.py` — exhaustive parser testing across all 8 tracks,
offsets 24-28, yielded only **16.8% coverage** with the Q7P command set.)

The QY70 uses a **proprietary packed bitstream**, NOT a byte-oriented command set:

**Evidence:**
- 117 unique high-bit byte values appear in event data (Q7P has ~15 commands)
- Shannon entropy: 4.8–6.65 bits/byte (high, no clear command structure)
- Bit 7 frequency: 40–61% (in byte-command format, expect ~25%)
- All 8 bit positions have roughly uniform frequency (37–53%) — hallmark of bitstream
- Same "status" bytes appear with 0, 1, 2, 3, 5, 6 trailing data bytes — no fixed sizes
- Q7P command matches are statistical noise (0x00 padding, A0-A7 appearing as data)

**Structural observations:**
- `DC` (0xDC) appears in chord tracks (C1, C3, C4) as a possible delimiter with
  consistent ~41-byte bar segments, but is absent or rare in drum tracks
- When DC appears, it is followed by a data byte (e.g., `1F`, `1A`), suggesting
  a 2-byte construct rather than a 1-byte delimiter
- Repeating trigrams: `E3 71 78`, `8F C7 E3`, `71 78 BE` — likely bit patterns
  within the packed stream
- Cross-section D1 data is byte-identical across all 6 sections
- Track PC (offset 64+) shows 7-byte blocks starting with `0x88` — possibly
  a configuration/setup region distinct from note events

**Session 7 Bitstream Structural Discoveries:**

The QY70 packed bitstream has been partially decoded:

1. **9-bit barrel rotation**: Consecutive 7-byte (56-bit) events are related by a 9-bit
   barrel rotation. R=9 is definitively optimal across all chord tracks.

2. **De-rotated field structure** (56 bits = 6 × 9-bit fields + 2 remainder bits):
   ```
   [F0: 9b][F1: 9b][F2: 9b][F3: 9b][F4: 9b][F5: 9b][rem: 2b]
   ```
   - F0: Primary note/chord encoding (unique per beat)
   - F1: Copy of F0 from previous beat (shift register)
   - F2: Copy of F1 from previous beat (2-beat history)
   - F3: Note pitch modifier (C2→C4 differs by +1)
   - F4: Note pitch/register encoding (large jumps between C2/C4)
   - F5: Gate time or velocity
   - rem: Always 00

3. **Bar headers encode chord notes**: 13-byte bar header decoded as 9-bit fields
   produces valid MIDI note numbers (e.g., [63,61,59,55,36] = minor chord voicing).

4. **41-byte bar structure**: [13-byte header] + 4 × [7-byte event] for chord tracks.

5. **DC (0xDC) bar delimiter**: Present in chord and bass tracks, absent in drum/PC tracks.

6. **R=9 rotation is universal**: Works for ALL track types (chord, bass, percussion).
   BASS confirmed at avg 16.5 bits differ. This is a format-wide constant.

7. **F3 = hi2|mid3|lo4 decomposition**:
   - lo4: One-hot beat counter (1000→0100→0010→0001) — confirmed C2, C1
   - mid3: Track/voice type identifier (5=default chord, 7=fill)
   - hi2: Octave/register flag

8. **F4 = 5-bit chord-tone mask + 4-bit parameter**:
   - The 5-bit mask selects which header chord tones to voice on each beat
   - Mask changes between bars with different header chords
   - Partially validated; header values >127 complicate interpretation

9. **F5 = timing/gate encoding**:
   - Dominant spacing +16 = one beat in 4/4 time
   - Decomposition: top2|mid4|lo3 (lo3 constant per bar, mid4 increments)
   - Monotonic within bars for default patterns, non-monotonic for complex rhythms

10. **Cross-section behavior**: When header chord is the SAME across sections,
    ALL event fields are IDENTICAL. When chord changes, ALL 6 fields change.

**Status:** Substantially decoded for chord tracks. F3 beat counter and F4 chord-tone
mask are the strongest findings. F5 timing, drum track encoding, and F3 mid3/hi2
semantics still require further reverse engineering.

### Format Comparison

| Aspect | QY700 (Q7P) | QY70 (SysEx) |
|--------|-------------|--------------|
| Event encoding | Byte-oriented commands | Packed bitstream (9-bit fields) |
| Command set | D0/E0/A0-A7/BE/BC/DC/F0/F2 | 6×9-bit fields + 2-bit remainder |
| Byte alignment | Commands aligned to byte boundaries | 7-byte groups, bit-level packing |
| Bar delimiter | DC (1 byte, standalone) | DC in chord/bass tracks only |
| Beat encoding | Explicit note-on/off events | F3 lo4 one-hot beat counter |
| Chord voicing | Individual note events | F4 5-bit chord-tone mask from header |
| Timing | Delta-time commands (A0-A7) | F5 field (+16 per beat) |
| Inter-event relation | Independent events | 9-bit barrel rotation (R=9) |
| Shared format? | **NO** — 16.8% false-positive coverage | **NO** |

## Conversion Considerations

When converting QY70 ↔ QY700:

1. **Track count**: Map 8 QY70 tracks to appropriate QY700 tracks
2. **Voice data**: Extract from QY70 track headers, place in QY700 voice area
3. **Event data**: **Requires full format conversion** — QY70 uses packed bitstream
   with 9-bit rotating fields, QY700 uses byte-oriented commands. These are
   fundamentally different encodings. Current decoding progress:
   - Chord tracks: ~70% decoded (F3 beat counter, F4 chord mask, F5 timing confirmed)
   - Bass tracks: Structure known (DC delimiters, R=9), field semantics pending
   - Drum tracks: Minimal (D1 markers found, D2/PC no DC, internal format unknown)
4. **Channel assignments**: QY70 has fixed defaults, QY700 allows per-track config
5. **AL addressing**: QY70 uses `section*8 + track`, not `0x08 + section*8 + track`
6. **Bar headers**: QY70 encodes chord information in 13-byte bar headers; QY700
   has no equivalent — chord notes are inline events

## References

- `docs/QY70_FORMAT.md` - QY70 format documentation
- `docs/QY700_FORMAT.md` - QY700 format documentation
- `docs/MIDI_REVERSE_ENGINEERING.md` - Live analysis notes
