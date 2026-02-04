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

| AL Value | Description | Typical Size |
|----------|-------------|--------------|
| 0x00 | Intro section | 882 bytes |
| 0x01 | Main A section | 294 bytes |
| 0x02 | Main B section | 147 bytes |
| 0x03 | Fill AB section | 294 bytes |
| 0x04 | Fill BA section | 147 bytes |
| 0x05 | Ending section | 294 bytes |
| 0x06-0x2F | Track data blocks | varies |
| 0x7F | Header/config | 735 bytes |

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

1. Initialization message
2. Multiple bulk dump messages for section data (AL = 0x00-0x05)
3. Track data blocks (AL = 0x08-0x2F)
4. Header/config block (AL = 0x7F)

Messages are sent in order, and each message's checksum is validated by the receiver.

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

Track data is stored at AL addresses 0x08-0x2F. The formula for calculating AL:

```
AL = 0x08 + (section_index * 8) + track_index
```

Where:
- section_index = 0-5 (Intro, MainA, MainB, FillAB, FillBA, Ending)
- track_index = 0-7 (RHY1, RHY2, BASS, CHD1, CHD2, PAD, PHR1, PHR2)

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

**Pattern 1: Default Voice (0x40 0x80)**

When bytes 14-15 are `0x40 0x80`, the track uses the QY70 default voice for its type:

| Track Type | Default Voice | Bank | Program |
|------------|---------------|------|---------|
| RHY1, RHY2 | Standard Kit | 127 | 0 |
| BASS | Acoustic Bass | 0 | 32 |
| CHD1, CHD2 | Acoustic Grand Piano | 0 | 0 |
| PAD | Pad 1 (New Age) | 0 | 88 |
| PHR1, PHR2 | Acoustic Grand Piano | 0 | 0 |

**Pattern 2: Explicit Bank/Program**

Otherwise, bytes 14-15 contain the XG Bank MSB and Program number:

```
Byte 14 = Bank MSB (0 = normal, 4 = variation, 64 = SFX, 127 = drums)
Byte 15 = Program number (0-127)
```

Examples from real files:
- `00 04` = Bank 0, Program 4 = Electric Piano 1
- `04 0B` = Bank 4, Program 11 = Vibraphone (variation)
- `00 00` = Bank 0, Program 0 = Acoustic Grand Piano

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

The header section contains global pattern/style configuration.

| Offset | Description |
|--------|-------------|
| 0 | Type indicator: 0x5E=Style, 0x4C=Pattern |
| 0x0C | Tempo (if valid range 40-240) |
| 0x40-0x4F | Possible track configuration area |

The header is typically 640 bytes encoded (128 bytes decoded after 7-bit expansion).

### Section Phrase Data (AL=0x00-0x05)

Phrase sections contain the actual MIDI sequence data for each style section:

| AL | Section |
|----|---------|
| 0x00 | Intro |
| 0x01 | Main A |
| 0x02 | Main B |
| 0x03 | Fill AB |
| 0x04 | Fill BA |
| 0x05 | Ending |

**Bar Count Estimation:**

Phrase data size correlates roughly with section length:
- ~32 bytes per bar (approximate)
- Intro (770 bytes) ≈ 24 bars
- Main sections (256 bytes) ≈ 8 bars
- Fill sections (128 bytes) ≈ 4 bars

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

### MIDI Event Estimation

Track sequence data (bytes 24+) contains MIDI events. A rough event count can be estimated:
- Count non-zero, non-filler bytes (excluding 0x00, 0xFE, 0xF8)
- Divide by 4-6 (approximate bytes per MIDI event)

This gives a relative measure of track "activity" or complexity.
