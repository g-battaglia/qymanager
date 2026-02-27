# QY70 SysEx File Format

This document describes the System Exclusive (SysEx) format used by the Yamaha QY70 for pattern/style data transfer.

## Overview

The QY70 uses MIDI System Exclusive messages to transfer bulk data. Pattern/style data is sent as a series of bulk dump messages, each containing a portion of the pattern data.

## Message Structure

### Manufacturer and Model IDs

| Byte | Value | Description |
|------|-------|-------------|
| Manufacturer ID | 0x43 | Yamaha |
| Model ID | 0x5F | QY70 |

### Message Types

| Device Byte | Type | Description |
|-------------|------|-------------|
| 0x0n | Bulk Dump | Transfer block of data |
| 0x1n | Parameter Change | Change single parameter |
| 0x2n | Dump Request | Request data from device |

Where `n` is the device number (0-15).

## Bulk Dump Format

```
F0 43 0n 5F BH BL AH AM AL [data...] CS F7
```

| Field | Size | Description |
|-------|------|-------------|
| F0 | 1 | SysEx Start |
| 43 | 1 | Yamaha Manufacturer ID |
| 0n | 1 | Bulk Dump + Device Number |
| 5F | 1 | QY70 Model ID |
| BH | 1 | Byte Count High (bits 13-7) |
| BL | 1 | Byte Count Low (bits 6-0) |
| AH | 1 | Address High |
| AM | 1 | Address Mid |
| AL | 1 | Address Low |
| data | var | 7-bit encoded payload |
| CS | 1 | Checksum |
| F7 | 1 | SysEx End |

### Byte Count

The byte count indicates the size of the encoded data payload:
```
byte_count = (BH << 7) | BL
```

### Checksum Calculation

The checksum is calculated over the address and data bytes:

```python
def calculate_checksum(address_and_data: bytes) -> int:
    total = sum(address_and_data)
    return (128 - (total & 0x7F)) & 0x7F
```

## 7-Bit Encoding

MIDI SysEx requires all data bytes to have bit 7 clear (values 0-127). The QY70 uses Yamaha's standard 7-bit packing scheme:

### Encoding Process

For every 7 bytes of raw 8-bit data:
1. Extract the high bit (bit 7) from each byte
2. Pack these 7 high bits into a "header" byte
3. Clear the high bits in the original 7 bytes
4. Output: 1 header byte + 7 data bytes = 8 bytes

### Header Byte Layout

```
Header: [b6 b5 b4 b3 b2 b1 b0 0]
         │  │  │  │  │  │  │
         │  │  │  │  │  │  └── Bit 7 of byte 6
         │  │  │  │  │  └───── Bit 7 of byte 5
         │  │  │  │  └──────── Bit 7 of byte 4
         │  │  │  └─────────── Bit 7 of byte 3
         │  │  └────────────── Bit 7 of byte 2
         │  └───────────────── Bit 7 of byte 1
         └──────────────────── Bit 7 of byte 0
```

### Example

Raw data (7 bytes):
```
80 40 20 10 08 04 02
```

High bits: `1 0 0 0 0 0 0` → Header: `0x40`

Encoded (8 bytes):
```
40 00 40 20 10 08 04 02
```

### Decoding Process

```python
def decode_7bit(encoded: bytes) -> bytes:
    result = bytearray()
    for i in range(0, len(encoded), 8):
        header = encoded[i]
        for j in range(1, min(8, len(encoded) - i)):
            high_bit = (header >> (7 - j)) & 1
            result.append(encoded[i + j] | (high_bit << 7))
    return bytes(result)
```

## Address Map

### Style Data (AH=0x02, AM=0x7E)

**CORRECTED (2026-02-26): AL = section_index * 8 + track_index**

There is NO separate "phrase data" region. ALL AL 0x00-0x2F are track data.

| AL Range | Description | Per-track Size |
|----------|-------------|----------------|
| 0x00-0x07 | Section 0 (Intro) tracks 0-7 | 128-768 bytes |
| 0x08-0x0F | Section 1 (Main A) tracks 0-7 | 128-768 bytes |
| 0x10-0x17 | Section 2 (Main B) tracks 0-7 | 128-768 bytes |
| 0x18-0x1F | Section 3 (Fill AB) tracks 0-7 | 128-768 bytes |
| 0x20-0x27 | Section 4 (Fill BA) tracks 0-7 | 128-768 bytes |
| 0x28-0x2F | Section 5 (Ending) tracks 0-7 | 128-768 bytes |
| 0x7F | Header/config | 640 bytes decoded |

Track sizes are always multiples of 128: 128, 256, or 768 bytes.

## Parameter Change Format

```
F0 43 1n 5F AH AM AL DD F7
```

| Field | Description |
|-------|-------------|
| 1n | Parameter Change + Device Number |
| AH AM AL | Parameter address |
| DD | Data value |

## Initialization Message

Before bulk dump, an init message is typically sent:

```
F0 43 10 5F 00 00 00 01 F7
```

This prepares the device to receive the following bulk data.

## Complete Style Transfer

A typical style transfer consists of:

1. Initialization message (Parameter Change: `F0 43 10 5F 00 00 00 01 F7`)
2. Track data blocks for all sections (AL = 0x00-0x2F, where AL = section*8 + track)
3. Header/config block (AL = 0x7F, 5 messages × 128 decoded bytes = 640 bytes)
4. Close message (Parameter Change: `F0 43 10 5F 00 00 00 00 F7`)

Messages are sent in order, and each bulk dump message's checksum is validated by the receiver.
Init/close messages are Parameter Change type (device byte 0x1n) and do NOT have checksums.

## References

- Yamaha QY70 Owner's Manual
- Yamaha QY70 MIDI Implementation Chart
- MIDI 1.0 Specification (System Exclusive)

---

## Detailed Structure Analysis (Reverse Engineered)

This section documents the internal structure of QY70 SysEx data based on reverse engineering.

### Track Names and Channels

The QY70 has 8 tracks (vs 16 in QY700):

| Track | Name | Default Channel | Type |
|-------|------|-----------------|------|
| 1 | RHY1 | 10 | Rhythm (Drums) |
| 2 | RHY2 | 10 | Rhythm (Drums) |
| 3 | BASS | 2 | Bass |
| 4 | CHD1 | 3 | Chord 1 |
| 5 | CHD2 | 4 | Chord 2 |
| 6 | PAD | 5 | Pad |
| 7 | PHR1 | 6 | Phrase 1 |
| 8 | PHR2 | 7 | Phrase 2 |

### Track Data Structure

**CORRECTED (2026-02-26):** Track data uses unified AL addressing for both formats:

```
AL = section_index * 8 + track_index
```

Where:
- section_index = 0-5 (Intro, MainA, MainB, FillAB, FillBA, Ending)
- track_index = 0-7 (D1, D2, PC, BA, C1, C2, C3, C4)

For **Pattern** format, only section 0 is used (AL 0x00-0x07).
For **Style** format, all 6 sections are used (AL 0x00-0x2F).

### Track Data Header (Decoded Bytes)

After 7-bit decoding, each track section has a consistent header structure:

| Offset | Size | Description |
|--------|------|-------------|
| 0-11 | 12 | Common header: `08 04 82 01 00 40 20 08 04 82 01 00` |
| 12-13 | 2 | Constant: `06 1C` |
| 14-15 | 2 | Voice encoding (see below) |
| 16-17 | 2 | Note range (melody) or drum encoding |
| 18-20 | 3 | Unknown (different for drum vs melody) |
| 21 | 1 | Flag byte: 0x41=enabled, 0x00=special |
| 22 | 1 | Pan value (0-127, 64=center) |
| 23 | 1 | Unknown |
| 24+ | var | MIDI sequence data |

### Voice Encoding (Bytes 14-15)

The voice encoding at bytes 14-15 varies by track type:

**Pattern 1: Drum Default (0x40 0x80)**

When bytes 14-15 are `0x40 0x80`, the track uses the default drum kit:

| Track Type | Default Voice | Bank MSB | Program |
|------------|---------------|----------|---------|
| D1, D2, PC | Standard Kit | 127 | 0 |

**Pattern 2: Bass Track Marker (0x00 0x04)**

For BA (Bass) track, bytes 14-15 = `0x00 0x04` is a **fixed marker**, NOT the actual voice.

The bass voice is:
- Program 38 (Synth Bass 1) by default
- Bank LSB stored at **byte 26** (e.g., 0x60 = 96 for "Hammer" variation)

| Byte 26 Value | Bank LSB | Voice |
|---------------|----------|-------|
| 0x00 | 0 | Synth Bass 1 (base) |
| 0x60 | 96 | Synth Bass 1 (var.96) = "Hammer" |

**Pattern 3: Explicit Bank/Program (Chord Tracks)**

For chord/melody tracks (C1-C4), bytes 14-15 contain the XG Bank MSB and Program:

```
Byte 14 = Bank MSB (0 = normal, 4 = variation, 64 = SFX, 127 = drums)
Byte 15 = Program number (0-127)
```

Examples from real files:
- `00 00` = Bank 0, Program 0 = Acoustic Grand Piano
- `04 0B` = Bank 4, Program 11 = Vibraphone (variation)
- `00 0B` = Bank 0, Program 11 = Vibraphone (base)

### Note Range (Bytes 16-17) - Melody Tracks Only

For melody tracks (CHD1, CHD2, PAD, PHR1, PHR2):

```
Byte 16 = Note Low (MIDI note number)
Byte 17 = Note High (MIDI note number)
```

Common values:
- `07 78` = Notes 7-120 (G-1 to C9) - full range
- `17 78` = Notes 23-120 (B0 to C9) - limited low end (PAD track)

For drum tracks (RHY1, RHY2, BASS), bytes 16-17 have different encoding:
- `87 F8` = Drum-specific encoding (not direct note range)

### Pan Value (Byte 22)

The pan value follows XG conventions:

| Value | Pan |
|-------|-----|
| 0 | Random |
| 1-63 | Left (L63-L1) |
| 64 | Center |
| 65-127 | Right (R1-R63) |

**Important:** Byte 21 is a flag:
- `0x41` = Pan value at byte 22 is valid
- `0x00` = Use default pan (64 = center)

### Header Section (AL=0x7F)

The header section contains global pattern/style configuration. The header is split across multiple SysEx messages with sub-address `7E 7F`.

#### Header Message Structure

Each `7E 7F` message payload has the structure:
```
7E 7F [sub2] [tempo_range] [tempo_offset] ... [name bytes] ...
```

The **first** `7E 7F` message contains tempo and name:

| Payload Offset | Size | Description |
|----------------|------|-------------|
| 0-1 | 2 | Sub-address: `7E 7F` |
| 2 | 1 | Tempo range (see formula below) |
| 3 | 1 | Tempo offset (0-127) |
| 4-7 | 4 | Flags: typically `40 00 00 00` or `40 00 00 01` |
| 8-17 | 10 | Style name (encoded, see below) |
| 18+ | var | Other parameters |

#### Tempo Encoding

**Formula:** `tempo_bpm = (range * 95 - 133) + offset`

Where:
- `range` = payload byte 2 (after `7E 7F`)
- `offset` = payload byte 3

| Range | Base BPM | BPM Range |
|-------|----------|-----------|
| 1 | -38 | N/A (invalid) |
| 2 | 57 | 57-184 BPM |
| 3 | 152 | 152-279 BPM |
| 4 | 247 | 247-374 BPM |

**Examples:**
- SUMMER 155 BPM: range=0x03, offset=0x03 → (3×95-133)+3 = 155
- MR.VAIN 133 BPM: range=0x02, offset=0x4C → (2×95-133)+76 = 133

**Inverse function (BPM to bytes):**
```python
def bpm_to_tempo_bytes(bpm: int) -> tuple[int, int]:
    for range_val in range(1, 10):
        base = range_val * 95 - 133
        offset = bpm - base
        if 0 <= offset <= 127:
            return (range_val, offset)
    raise ValueError(f"BPM {bpm} out of range")
```

#### Style Name Encoding

**Session 5 Discovery:** The QY70 does **NOT** store the style name in plain ASCII
in the SysEx bulk dump. Exhaustive testing of direct ASCII, 5-bit, 6-bit, BCD, and
nibble encodings on three files (SGT, captured pattern, NEONGROOVE) found NO readable
name at any header offset.

The name is either:
1. Not stored in the bulk dump at all (only displayed on-device from internal storage)
2. Encoded in a proprietary format within the section pointer bytes (0x006-0x044)
3. Stored in a different SysEx address space not captured in the bulk dump

The header is 640 decoded bytes (5 × 128-byte blocks, 5 × 147-byte encoded messages).

#### Complete Header Structural Map (AL=0x7F, 640 decoded bytes)

**Session 5 Discovery:** Complete byte-by-byte map from deep comparison of SGT style
vs empty pattern. Total: 257 bytes fixed (40%), 383 bytes variable (60%).

```
Offset    Size  Content                              Type
────────────────────────────────────────────────────────────
0x000     1     Tempo/timing byte (decoded[0])       Variable
                SGT=0x5E, CAPTURED=0x2C, NEONGROOVE=0x47
0x001-005 5     Fixed: 00 00 00 00 80                Fixed
0x006-009 4     Section size/pointer data             Variable
0x00A-00B 2     Fixed: 01 00                         Fixed
0x00C-00D 2     Section flags                        Variable
0x00E     1     Fixed: 00                            Fixed
0x00F-044 54    Section pointer/phrase table          Variable
                (7-byte groups, filled with empty-marker when unused)
0x045-07F 59    Section data table                   Variable
                (all zeros when empty)
0x080-084 5     Fixed: 03 01 40 60 30                Fixed
0x085-089 5     Track config block 1                 Variable
0x08A-095 12    Fixed: 7B 7D 7E 00 00 00 00 00 00 00 00 00  Fixed
0x096-0B5 32    Track/voice configuration            Variable
0x0B6-0C5 16    Fixed template bytes                 Fixed
                80 40 10 8F 77 7B 7D 7E 7F 5F EF F0 80 80 80 80
0x0C6-0D2 13    Voice/bank config                    Variable
0x0D3-136 100   Per-track parameters (mixed)         Mixed
0x137-1B8 130   *** LARGE FIXED TEMPLATE ***         Fixed
                (identical in ALL known files)
0x1B9-21B 99    *** MIXER PARAMETERS ***             Variable
                Empty: filled with empty-marker pattern
                Style: actual bit-packed vol/rev/cho data
0x21C-220 5     Fixed: 00 00 00 00 00                Fixed
0x221-229 9     Style/section flags                  Variable
                (0x221=0x01 means "has data")
0x22A-27F 86    Tail data                            Mixed
                (mostly fixed empty markers)
```

#### Empty-Marker Pattern (Session 5 Discovery)

The QY70 uses a distinctive 7-byte "empty/default" marker pattern throughout
the header to signal "use XG default values":

```
BF DF EF F7 FB FD FE
```

Each byte is `0xFF` with exactly one bit (6→0) cleared, descending:
- `0xBF` = 1011 1111 (bit 6 clear)
- `0xDF` = 1101 1111 (bit 5 clear)
- `0xEF` = 1110 1111 (bit 4 clear)
- `0xF7` = 1111 0111 (bit 3 clear)
- `0xFB` = 1111 1011 (bit 2 clear)
- `0xFD` = 1111 1101 (bit 1 clear)
- `0xFE` = 1111 1110 (bit 0 clear)

This is the QY70's equivalent of the Q7P's `0xFE` fill byte.

In raw SysEx payloads (before 7-bit decoding), it appears as:
`7F 3F 5F 6F 77 7B 7D 7E`

A **low variant** (`3F 5F 6F 77 7B 7D 7E`) also exists — same pattern with
bit 7 clear. Bit 7 appears to act as an "active/populated" flag.

**Occurrences:** 29 instances in empty pattern, 11 in SGT style.
The pattern fills every unused mixer parameter slot.

### Section Phrase Data (AL=0x00-0x2F) — CORRECTED

**NOTE:** The previous documentation incorrectly stated AL 0x00-0x05 were "phrase sections".
This is WRONG. ALL AL 0x00-0x2F addresses contain **track data** (24-byte header + MIDI events).

Each track within a section has its own AL address:
```
AL = section_index * 8 + track_index

Section 0 (Intro):   AL 0x00 (D1), 0x01 (D2), ..., 0x07 (C4)
Section 1 (Main A):  AL 0x08 (D1), 0x09 (D2), ..., 0x0F (C4)
...
Section 5 (Ending):  AL 0x28 (D1), 0x29 (D2), ..., 0x2F (C4)
```

**Track Data Size Patterns (decoded bytes):**
- D1 (drums): 768 bytes (6 messages × 128)
- D2 (drums): 256 bytes (2 messages × 128)
- PC (perc):  128 bytes (1 message × 128)
- BA (bass):  256 bytes (2 messages × 128)
- C1-C4:      128-256 bytes (varies by section)

### XG Default Values

The QY70 uses Yamaha XG defaults:

| Parameter | Default Value | Hex |
|-----------|---------------|-----|
| Volume | 100 | 0x64 |
| Pan | 64 (Center) | 0x40 |
| Reverb Send | 40 | 0x28 |
| Chorus Send | 0 | 0x00 |
| Variation Send | 0 | 0x00 |

### Pattern vs Style Detection

A file is classified as:
- **Pattern**: Only 1 section active (typically Intro only)
- **Style**: Multiple sections active (typically all 6)

The type indicator at header byte 0 also distinguishes:
- `0x5E` = Style
- `0x4C` = Pattern

---

## Pattern vs Style SysEx Format (Important Discovery)

**UPDATED (2026-02-26):** Both formats use unified AL addressing `AL = section*8 + track`.
The key difference is that Pattern format only has one section (section 0, AL 0x00-0x07)
while Style format has 6 sections (AL 0x00-0x2F).

### Format Detection

| Format | Header[0] | Track Data AL Range | Detection |
|--------|-----------|---------------------|-----------|
| **Pattern** | < 0x08 (e.g., 0x03, 0x2C) | AL 0x00-0x07 (1 section) | `header[0] < 0x08` |
| **Style** | >= 0x08 (e.g., 0x4C, 0x5E) | AL 0x00-0x2F (6 sections) | `header[0] >= 0x08` |

### Pattern Format (AL 0x00-0x07)

In **Pattern** format:
- Track data is stored in AL addresses 0x00-0x07 (section 0 only)
- Each AL corresponds directly to a track: `AL = track_index`
- The file contains a single "section" (Pattern) rather than 6 style sections

Example AL distribution for Pattern format:
```
AL 0x00 = Track 0 (D1) data
AL 0x03 = Track 3 (BA) data
AL 0x04 = Track 4 (C1) data
AL 0x7F = Header/config
```

### Style Format (AL 0x00-0x2F)

In **Style** format:
- Track data uses all 6 sections: `AL = section_index * 8 + track_index`
- Up to 48 track data blocks (6 sections × 8 tracks)

Example AL distribution for Style format:
```
AL 0x00 = Section 0 (Intro), Track 0 (D1)
AL 0x03 = Section 0 (Intro), Track 3 (BA)
AL 0x08 = Section 1 (Main A), Track 0 (D1)
AL 0x10 = Section 2 (Main B), Track 0 (D1)
...
AL 0x7F = Header/config
```

### Header Byte[0] as Format Indicator

The first byte of the decoded header (AL=0x7F) indicates the format:

| Header[0] Value | Format | Example File |
|-----------------|--------|--------------|
| 0x03 | Pattern | Captured QY70 pattern |
| 0x2C | Pattern | Captured QY70 pattern (confirmed) |
| 0x4C | Style | "P - MR. Vain" |
| 0x5E | Style | "QY70_SGT.syx" (confirmed) |

### Detection Algorithm

```python
def detect_format(header_decoded: bytes, al_addresses: set) -> str:
    # Primary: check header byte[0]
    if header_decoded and len(header_decoded) > 0:
        if header_decoded[0] < 0x08:
            return "pattern"
        else:
            return "style"
    
    # Fallback: count track AL addresses
    track_als = [al for al in al_addresses if al != 0x7F and al <= 0x2F]
    if len(track_als) > 8:
        return "style"
    elif len(track_als) > 0:
        return "pattern"
    return "unknown"
```

### Implications for Parsing

When parsing QY70 SysEx:
1. First detect the format using header[0]
2. For **Pattern** format: look for track data in AL 0x00-0x07
3. For **Style** format: look for track data in AL 0x00-0x2F
4. Both formats use the same track header structure (24 bytes) after decoding
5. **IMPORTANT**: Init/Close messages (Parameter Change at addr 00/00/00) share AL=0x00
   with Section 0 Track 0. Only accumulate data from style data messages (AH=0x02, AM=0x7E).

---

### Track Event Data (Bytes 24+) — Packed Bitstream

**IMPORTANT (confirmed 2026-02-27):** The track event data (bytes 24+) does **NOT** use the
byte-oriented command set found in Q7P files (D0/E0/A0-A7/BE/F2). It is a **proprietary
packed bitstream** — a fundamentally different encoding.

#### Evidence (from exhaustive parser testing — `midi_tools/parse_events.py`)

| Test | Result |
|------|--------|
| Q7P command set coverage | **16.8%** (false positives only) |
| Unique high-bit byte values | **117** (vs ~15 Q7P commands) |
| Shannon entropy | **4.8–6.65** bits/byte (high = no command structure) |
| Bit 7 frequency | **40–61%** (uniform, not ~25% expected for commands) |
| All bit positions | **37–53%** frequency (uniform = bitstream hallmark) |
| Fixed-size event attempts | 2-6 bytes all fail (no alignment) |

#### Structural Observations

- **DC (0xDC)** appears in chord tracks (C1, C3, C4) creating ~41-byte segments,
  but is absent or very rare in drum tracks (D1 has only 1 DC in 744 bytes)
- When DC appears, it is followed by a data byte (e.g., `DC 1F`), suggesting
  a 2-byte construct rather than a standalone delimiter
- **Repeating trigrams**: `E3 71 78`, `8F C7 E3`, `71 78 BE` — likely bit-aligned
  patterns within the packed stream
- D1 track event data is byte-identical across all 6 sections
- Track PC shows 7-byte blocks starting with `0x88` at offset 64+ (possibly setup data)
- Chord track bars repeat identically (CHD2 Bar 1 = Bar 2, 41 bytes each)

#### Comparison with Q7P Event Format

| Aspect | Q7P (QY700) | QY70 (SysEx) |
|--------|-------------|--------------|
| Encoding | Byte-oriented commands | Packed bitstream |
| Command set | D0/E0/A0-A7/BE/BC/DC/F0/F2 | Unknown / proprietary |
| Byte alignment | Commands at byte boundaries | Bit-level packing |
| Bar delimiter | DC (1 byte, standalone) | DC in some tracks (2-byte?) |
| Convertible? | **Not directly** | Requires full bitstream decode |

#### Event Count Estimation

Since the exact format is unknown, a rough event count can be estimated:
- Count non-zero, non-filler bytes (excluding 0x00, 0xFE, 0xF8)
- Divide by 4-6 (approximate bytes per MIDI event)

This gives a relative measure of track "activity" or complexity.

#### Session 6 Discoveries: Event Data Structure

##### 7-Byte Group Alignment (CONFIRMED)

The 7-byte periodicity in decoded data is **real structure**, not an encoding artifact:
- **DC delimiters align to 7-byte group boundaries** in single-message tracks (100%)
- Multi-message tracks (D1 with 6 messages, C1 with 2 messages) show DC at non-aligned
  positions because each SysEx message is independently 7-bit encoded — the 7-byte
  grouping resets at each message boundary
- Within any single SysEx message, DC is always at `offset % 7 == 0`

**Exception:** D1 MSG4 has DC@96 (mod7=5), C1 MSG1 has DC@39 (mod7=4). These are in
continuation messages where the encoding boundary from message 0 doesn't carry over.
The data is a continuous stream split across messages, with events freely crossing
message boundaries but respecting 7-byte group alignment within each message's
independently-decoded payload.

##### Track Event Preamble (4 bytes)

Every track starts event data at byte 24 with `XX XX 60 00`:
- Bytes 2-3 are always `60 00`
- Bytes 0-1 correlate with track type and data length:

| Preamble | Tracks | Decoded Event Length |
|----------|--------|---------------------|
| `1F A3`  | C1, C3, C4 (chord) | 104 bytes |
| `25 43`  | D1 (drums) | 744 bytes |
| `29 CB`  | D2, BASS, C2 | 232 bytes |
| `2B E3`  | PC (perc) | 104 bytes |

Preamble bytes 0-1 are 100% stable across all 6 sections for 7 of 8 tracks.
Only C4/PHR changes preamble between sections.

##### DC (0xDC) Bar Delimiter

DC acts as a bar separator in the event stream:
- Present in chord tracks: C1 (1-3 per message), C2 (3), C3 (2-4), C4 (2-3)
- Absent in: D1 (only 1 DC in 740 event bytes), D2, BASS
- After DC, a 13-byte "bar header" follows, then 7-byte event groups
- Last DC is followed by `0x00` terminator

##### 41-Byte Bar Structure (Chord Tracks)

Bars in C2, C3, C4 consistently use 41 bytes:

```
[13-byte bar header] [7-byte event 0] [7-byte event 1] [7-byte event 2] [7-byte event 3]
```

The 13-byte header varies per bar and encodes bar-level configuration (timing, voicing).
The 4 × 7-byte events encode the actual musical content (notes/chords).

##### 7-Byte Event Bit-7 Pattern

Events in chord tracks show highly consistent bit-7 patterns:

| Pattern | Count | Tracks | Interpretation |
|---------|-------|--------|----------------|
| `1111100` | 27 | C2, C3, C4 | Standard chord event |
| `1111001` | 52 | C2, C3, C4 | Variant chord event |
| `1110001` | 37 | All chord | Bar header fragment |
| `0100000` | 61 | All chord | Bar header / preamble |
| `1010000` | 30 | All chord | Delimiter-adjacent |
| `1011111` | 11 | C2, C3, C4 | Initial bar group |

##### C2 vs C4 Bit-Level Differences (KEY FINDING)

C2 and C4 play similar chord voicings. Comparing their 7-byte events reveals
the **note field shifts position** by ~8 bits per event slot:

```
Event 3: diff at bit positions [9, 14]   — 2 bits in byte 1
Event 2: diff at bit positions [18, 23]  — 2 bits in byte 2
Event 1: diff at bit positions [26, 31]  — 2 bits in byte 3
Event 0: diff at bit positions [35,36,41,42] — 4 bits in bytes 4-5
```

The XOR pattern `0x21` (binary `00100001`) appears consistently: bits 5 and 0 of
the differing byte. This 2-bit difference encodes a single-note transposition between
the C2 and C4 voicings. The shifting position suggests the note field is packed at
a fixed bit offset within each event's conceptual "slot" in the 7-byte group.

Bytes 5-6 of `1111100` events are nearly constant:
- Byte 5: `0x61` (97) or `0x71` (113) — likely timing
- Byte 6: `0x78` (120) — likely gate length

##### 13-Byte Bar Headers

Bar headers after DC delimiters contain bar-level configuration:

| Track | Default Header | Notes |
|-------|---------------|-------|
| C2 | `1F 8F 47 63 71 21 3E 9F 8F C7 62 42 70` | Identical across S0-S2 |
| C4 | `1F 8F 47 63 71 23 3E 9F 8F 47 62 46 60` | 4 bytes differ from C2 |
| C3 S0 | varies per bar | Unique musical data |
| C3 S1-5 | `1F 8F 47 63 71 21 3E 9F 8F C7 62 42 70` | Same as C2 default |

C2 vs C4 header differences at bytes [5, 9, 11, 12] — likely voice/register config.

##### Cross-Section Stability

- **C1**: 100% identical across all 6 sections (every byte)
- **C3**: Section 0 has unique musical data; sections 1-5 use default pattern
- **D1**: Byte-identical across all 6 sections (confirmed)
- **BASS**: Bar 0 identical across all 6 sections

##### D1 Drum Track Structure

D1 has 740 event bytes (6 messages × 128 - 28 header) with only 1 DC delimiter:
- Bar 0: 580 bytes (complex drum pattern)
- Bar 1: 159 bytes (simpler variation or tail)
- Repeating byte pair `28 0F` appears 13 times at intervals of 28-42 bytes
- `28 0F` is likely a structural marker (bar subdivision or beat boundary)
- After `28 0F`: byte 0x8C/0x8D/0x8F (lo7=12/13/15, possibly timing variation)
- `40 78` appears 8 times — another structural pattern

#### Session 7 Discoveries: 9-Bit Rotation and Shift Register Model

##### 9-Bit Barrel Rotation Between Events (DEFINITIVE)

Exhaustive search across all 55 possible rotation values (1-55 bits for 56-bit events)
confirms that **R=9 bits** is the optimal rotation between consecutive chord events:

| Track/Section | R=9 Hamming Distance | Next Best R | Score |
|---------------|---------------------|-------------|-------|
| C2 all bars | 10 bits | R=47 (46 bits) | Best |
| C4 all bars | 10 bits | R=47 (46 bits) | Best |
| C3 S1 (default) | 10 bits | R=47 (46 bits) | Best |
| C3 S0 (unique) | 11-18 bits | Varies | Best |
| C1 | 11-20 bits | Varies | Best |

Aggregate score across all chord tracks: R=9 scores 35 (best of all 55 rotations).

**Meaning:** Each 56-bit (7-byte) event E[i+1] can be obtained by barrel-rotating
E[i] by 9 bits and then XORing with a small correction mask (10-20 bits differ).

##### Shift Register Model — Partially Confirmed

De-rotating events by R=9 produces six 9-bit fields (F0-F5) plus 2 remainder bits:

```
56 bits = [F0: 9 bits][F1: 9 bits][F2: 9 bits][F3: 9 bits][F4: 9 bits][F5: 9 bits][rem: 2 bits]
```

**Field shifting (F1[i]==F0[i-1] and F2[i]==F1[i-1]):**
- **TRUE for C2, C4**: Fields F0→F1→F2 shift perfectly between consecutive events
- **FALSE for C1, C3 S0**: These tracks have genuinely different event data per beat

**Conclusion:** F0-F2 carry "history" (previous beat values shift down), while
F3-F5 encode independent per-beat parameters (note pitch, velocity, gate time).

##### Bar Header 9-Bit Fields = Chord Notes (MAJOR DISCOVERY)

Decoding the 13-byte bar header as 9-bit fields reveals **valid MIDI note numbers**:

```
C2 bar1 header (13 bytes → 104 bits → 11 × 9-bit fields + 5 remainder):
  F0-F4 = [63, 61, 59, 55, 36]
        = D#4, C#4, B3, G3, C2
        = intervals from root: [0, 1, 3, 7, 11] semitones above C2
        = contains minor triad (0, 3, 7)
```

| Track | Bar1 Header F0-F4 | Notes | Interpretation |
|-------|-------------------|-------|----------------|
| C2 | [63, 61, 59, 55, 36] | D#4,C#4,B3,G3,C2 | Chord voicing (5 notes) |
| C4 | [63, 61, 59, 55, 36] | IDENTICAL to C2 | Same chord, different register |
| C3 S0 bar1 | Different per bar | Varies | Unique chord progression |
| C1 | Values >127 | Not simple MIDI notes | Different encoding |

**C4 has identical header chord notes to C2** — the register difference between
C2 and C4 is encoded in the event data (F3/F4), not the header.

##### De-Rotated Event Field Structure

After de-rotation with R=9, the 56-bit events decompose as:

```
C2/C4 default pattern (identical across S0-S2):
E0: F0=381  F1=126  F2=126  F3=88   F4=172  F5=94   rem=00
E1: F0=376  F1=381  F2=126  F3=84   F4=188  F5=110  rem=00
E2: F0=440  F1=376  F2=381  F3=82   F4=188  F5=126  rem=00
E3: F0=504  F1=440  F2=376  F3=337  F4=186  F5=126  rem=00
         ↑       ↑       ↑
    unique   =F0[i-1] =F1[i-1]    (shift register for F0-F2)
```

**Field roles (hypothesis):**
- **F0**: Primary note/chord encoding (unique per beat, >127 = not raw MIDI note)
- **F1**: Copy of previous beat's F0 (history)
- **F2**: Copy of previous beat's F1 (2-beat history)
- **F3**: Note pitch modifier (+1 between C2→C4: 88→89, 84→85)
- **F4**: Note pitch/register (large jumps between C2→C4: +244, -16, +248, +248)
- **F5**: Gate time or velocity (94, 110, 126, 126)
- **rem**: Always 00

##### C2 vs C4 Note Difference Location

After de-rotation, the C2↔C4 difference is concentrated in **F3 and F4**:

| Event | F3 diff | F4 diff | F5 diff |
|-------|---------|---------|---------|
| E0 (bar0) | Large | Large | Large | ← Bar 0 has structural differences |
| E0 (bar1) | +1 | +244 | 0 |
| E1 (bar1) | +1 | -16 | 0 |
| E2 (bar1) | +1 | +248 | 0 |
| E3 (bar1) | 0 | 0 | 0 |

F3 consistently differs by +1 (a single-semitone transposition?).
F4 has large jumps suggesting a different encoding (possibly packed note+octave).

##### Cross-Section F0 Value Analysis

F0 values vary by section, reflecting different musical content:

| Track | Sections | Bar1 F0 values | Interpretation |
|-------|----------|----------------|----------------|
| C2 S0-S2 | Identical | [381, 376, 440, 504] | Default chord pattern |
| C2 S3-S4 | Different | [407, 175, 111, 79] | Fill variation |
| C2 S5 | Different | [431, 237, 27, 16] | Ending variation |
| C1 S0-S5 | All identical | [399, 253] | C1 never changes |

##### Lo7 Bitstream C2/C4 Difference Pattern

Treating the full 41-byte bar as a 7-bit packed stream (287 bits), C2 vs C4
differ at only **13 bits** forming **complementary pairs** of +1/-1:

```
Single-bit diffs: [40], [81], [86], [162], [167], [204], [209], [245], [250]
Two-bit diffs: [121,122], [126,127]
Pattern: alternating +1 then -1, separated by ~5 bit positions
```

This complementary pattern suggests the note encoding uses a balanced code
where changing one note adjusts two fields symmetrically.

### Session 8 Discoveries: Field Decomposition and Universal Rotation

#### R=9 Rotation Confirmed Universal

The 9-bit barrel rotation between consecutive events is **not limited to chord tracks**.
Testing on BASS track data confirms R=9 is optimal there too:

```
BASS: R=9 → avg 16.5 bits differ (next best R=10 → 24.6 bits)
C2:   R=9 → avg 10 bits differ
C4:   R=9 → avg 10 bits differ
C1:   R=9 → avg 11-20 bits differ
C3:   R=9 → avg 11-18 bits differ
```

R=9 is a **format-wide constant** used across all track types (chord, bass, and likely percussion).

#### F3 Field Decomposition: hi2 | mid3 | lo4

The 9-bit F3 field decomposes into three sub-fields:

```
F3 = [2-bit hi2][3-bit mid3][4-bit lo4]
      bits 8-7    bits 6-4    bits 3-0
```

**F3 lo4 = One-Hot Beat Counter** (confirmed for C2, C1):

```
C2 S0 (default): lo4 = 1000 → 0100 → 0010 → 0001  (perfect one-hot, 4 beats)
C1 S1-S5:        lo4 = 1000 → 0100 → 0010 → 0001  (perfect one-hot)
C2 S3 bars 1-4:  lo4 = 0000 → 0000 → 0000 → 0001  (degenerate — only last beat set)
C4:              lo4 sometimes has extra bits (1001, 0101) — NOT strictly one-hot
C3:              lo4 NOT one-hot (1100, 0100, 0010, 1010...) — complex pad track
```

**F3 mid3 = Track/Voice Type Identifier:**

| Track/Context | mid3 value | Binary |
|---------------|------------|--------|
| C2 default sections | 5 | 101 |
| C2 S3 bar0 (fill) | 7 | 111 |
| C4 | 5 or 6 | 101/110 |
| C1 S0 | 5 or 7 | 101/111 |
| C3 | varies 0-7 | variable |

**F3 hi2 = Octave/Register Flag:**

- C2: hi2 = 0 for beats 0-2, hi2 = 2 for beat 3 (last beat in bar)
- C1: hi2 varies across full range (0, 1, 2, 3)

#### F4 Field Decomposition: 5-Bit Chord-Tone Mask + 4-Bit Parameter

F4 decomposes as `[5-bit mask][4-bit param]`:

```
C2 S0 (chord = D#4, C#4, B3, G3, C2):
  E0: 5mask=01010 → selects C#4, G3       → param=12
  E1: 5mask=01011 → selects C#4, G3, C2   → param=12
  E2: 5mask=01011 → selects C#4, G3, C2   → param=12
  E3: 5mask=01011 → selects C#4, G3, C2   → param=10

C2 S3 bar0 (different chord):
  E0: 5mask=01101 → different selection    → param=8
  E1: 5mask=01101 → same selection         → param=0

C2 S5 bar1 (yet another chord):
  E0: 5mask=11011 → selects 4 of 5 tones  → param=0
  E1: 5mask=01010 → selects 2 tones       → param=4
```

The 5-bit mask changes between bars with **different header chords** — consistent with
the mask selecting which chord tones to voice on each beat. Note: some header field
values are >127, suggesting the header may encode chord intervals or relative offsets
rather than absolute MIDI note numbers for fields beyond F0-F4.

#### F5 Field: Timing/Gate Encoding

F5 spacing analysis across all tracks:

```
+16: 38 occurrences (most common — quarter-note spacing)
 +0: 32 occurrences (repeated timing — same beat position)
+32: 19 occurrences (half-note spacing)
 +2: 14 occurrences
 +4: 11 occurrences
-16:  8 occurrences
```

F5 is **monotonically increasing** within bars for default C2/C4 patterns
([94→110→126→126]) but **NOT monotonic** for C1 or C3 (complex rhythmic patterns).
The dominant spacing of 16 suggests **16 ticks = one beat** in 4/4 time.

F5 bit decomposition `[2-bit top2][4-bit mid4][3-bit lo3]`:

| Track | lo3 | mid4 pattern | Notes |
|-------|-----|-------------|-------|
| C2 | 6 (constant) | 11→13→15→15 | Monotonic increment |
| C4 bar0 | 4 | 11→15 | Two-event bar |
| C1 | 1 or 4 (varies) | Non-monotonic | Complex rhythm |

#### D2 Track — No DC Delimiters (Confirmed)

D2 has **zero DC markers** (0xDC). DC delimiters are specific to chord and bass tracks:

| Track | DC count | Notes |
|-------|----------|-------|
| C1 | 1-3 per msg | Chord track |
| C2 | 3 | Chord track |
| C3 | 2-4 | Chord track |
| C4 | 2-3 | Chord track |
| BASS | 4 | Bass track |
| D1 | 1 (at byte 580) | Minimal |
| D2 | 0 | No DC |
| PC | 0 | No DC |

D2 section data: S1-S5 identical to each other, differ from S0 by only 12 bytes (5.3%)
in the tail region. Same preamble as BASS: `29 CB 60 00`.

#### PC (Percussion) Track Structure

- 100 event bytes, NO DC delimiters
- S0=S1 (identical), S2-S5 identical to each other but differ from S0 by 70/100 bytes
- First 28 bytes identical across all sections (track preamble + initial setup)

#### BASS Track — R=9 and DC Structure

- 228 event bytes, DC at positions [70, 100, 139, 184] → 5 segments
- S0=S1=S2=S3=S5 (identical), S4 differs by 59/228 bytes (26%) — "fill" variation
- All 32 seven-byte groups are unique (no repeating patterns)
- R=9 rotation confirmed (avg 16.5 bits differ between consecutive events)

#### Cross-Section Event Comparison (C2)

When the header chord changes between sections, **ALL 6 fields change** (F0-F5):

| Field | Change when chord changes | Change when chord same |
|-------|--------------------------|----------------------|
| F0-F2 | Dramatic (shift register carries different values) | Identical |
| F3 | ±8, ±256 (hi2/lo4 change, mid3 often preserved) | Identical |
| F4 | ±20 to ±260 (different chord-tone mask) | Identical |
| F5 | ±10 to ±185 (different timing/gate) | Identical |

When header chord is the SAME (S0 = S1 = S2), **ALL fields are IDENTICAL**.

Cross-section groupings:
- S0-S2: Completely identical (same chord, same events)
- S3-S4: Identical to each other, 6 bars each, different from S0
- S5: Different from all others, 3 bars
- S3/S4 bar5: Nearly empty (F3=0, F4=1-2, indicating silence/rest)

#### Next Steps for Decoding

1. **Fully decode F3 mid3** — Appears to be a track/voice type identifier.
   Need more data points with different voice assignments.
2. **Validate F4 chord-tone mask** — Header values >127 complicate interpretation.
   Need to determine if the header encodes intervals or something else.
3. **Decode F5 lo3 and mid4 precisely** — lo3 may be gate length, mid4 beat position.
   Need ground-truth patterns with known timing.
4. **Decode D1 drum events** — `28 0F` markers define beats but internal structure unclear.
   Need ground-truth pattern with known simple drum content.
5. **Capture additional .syx files** with known simple patterns (single notes) for
   ground-truth comparison — requires user interaction with QY70 hardware.
6. **Build working bitstream decoder prototype** for chord tracks using the
   confirmed 9-bit rotation, F3 beat counter, and F4 chord-tone mask.
