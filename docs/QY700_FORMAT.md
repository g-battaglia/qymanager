# QY700 Q7P File Format

This document describes the binary file format used by the Yamaha QY700 for pattern files (.Q7P).

## Overview

Q7P files are fixed-size binary files containing a single pattern with all its sections and track data. Unlike the QY70's SysEx format, Q7P files use raw 8-bit data without compression.

The QY700 follows the **Yamaha XG specification** for MIDI parameters.

## File Specifications

| Property | Value |
|----------|-------|
| File Extension | .Q7P |
| File Size | **3072 bytes** (basic) or **5120 bytes** (full) |
| Encoding | Raw binary (8-bit) |
| Byte Order | Big-endian |
| Max Sections | 6 (3072-byte) or 12 (5120-byte) |
| Tracks per Pattern | **16** (TR1-TR16) |

### File Size Variants

The QY700 uses two file formats:

| Format | Size | Sections | Description |
|--------|------|----------|-------------|
| Basic | 3072 bytes | 6 | Template/simplified patterns |
| Full | 5120 bytes | 12 | Complete patterns with all sections |

The header and section pointer area (0x000-0x11F) are identical between formats. Key data offsets differ in the second half of the file.

## Complete File Structure Map

```
Offset    Size    Description                          Status
──────────────────────────────────────────────────────────────
0x000     16      Header "YQ7PAT     V1.00"            ✓ Verified
0x010     1       Pattern number (slot)                ✓ Verified
0x011     1       Pattern flags                        ✓ Verified
0x012     30      Reserved (zeros)                     
0x030     2       Size marker (0x0990 = 2448)          ✓ Verified
0x032     206     Reserved/padding                     
0x100     32      Section pointers                     ✓ Verified
0x120     96      Section encoded data                 Partial
0x180     8       Padding (0x20 spaces)                ✓ Verified
0x188     2       Tempo (big-endian, ÷10 for BPM)      ✓ Verified
0x18A     1       Time signature                       ✓ Lookup table
0x18B     1       Time signature (denominator?)        Needs verify
0x18C     4       Additional timing flags              
0x190     8       Channel assignments                  ✓ Mapped
0x198     8       Reserved                             
0x1A0     60      Reserved/spaces                      
0x1DC     8       Track numbers (00-07)                ✓ Verified
0x1E4     2       Track enable flags (bitmask)         ✓ Verified
0x1E6     26      Reserved                             
0x200     32      Reserved                             
0x220     6       Volume table header                  
0x226     16      Volume data (8 tracks × 2?)          ✓ Verified
0x236     26      Volume continued                     
0x250     6       Reverb send table header             
0x256     16      Reverb send data (8 tracks)          ✓ NEW - Verified
0x266     10      Reserved                             
0x270     6       Pan table header                     
0x276     48      Pan data (8 tracks × sections)       ✓ FIXED offset
0x2C0     160     Table 3 (unknown - effects?)         Needs research
0x360     792     Phrase data                          Needs parsing
0x678     504     Sequence events                      Needs parsing
0x870     6       Template padding                     
0x876     10      Pattern name (ASCII)                 ✓ Verified
0x880     128     Reserved                             
0x900     192     Pattern mappings                     
0x9C0     336     Fill area (0xFE bytes)               ✓ Verified
0xB10     240     Padding (0xF8 bytes)                 ✓ Verified
```

## Header Structure (0x000 - 0x02F)

### Magic Header (0x000)

```
Offset  Size  Value              Description
------  ----  -----------------  -----------
0x000   16    "YQ7PAT     V1.00" File type and version identifier
```

### Pattern Info (0x010)

```
Offset  Size  Description
------  ----  -----------
0x010   1     Pattern number (1-based slot number)
0x011   1     Flags (typical values: 0x00, 0x01, 0x02)
0x012   30    Reserved (zeros)
```

### Size Marker (0x030)

```
Offset  Size  Format      Description
------  ----  ----------  -----------
0x030   2     Big-endian  Size marker: 0x0990 = 2448 decimal
```

## Section Pointers (0x100 - 0x11F)

The section pointer area contains 16 two-byte entries for section references:

```
Offset  Size  Description
------  ----  -----------
0x100   2     Section 0 (Intro) pointer
0x102   2     Section 1 (Main A) pointer
0x104   2     Section 2 (Main B) pointer
0x106   2     Section 3 (Fill AB) pointer
0x108   2     Section 4 (Fill BA) pointer
0x10A   2     Section 5 (Ending) pointer
0x10C   20    Reserved section pointers
```

**Special values:**
- `0xFEFE` = Section is empty/unused

## Timing Configuration (0x180 - 0x18F)

### Tempo (0x188)

```
Offset  Size  Format      Description
------  ----  ----------  -----------
0x188   2     Big-endian  Tempo × 10 (e.g., 0x04B0 = 1200 = 120.0 BPM)
```

**Conversion:**
```python
bpm = struct.unpack(">H", data[0x188:0x18A])[0] / 10.0
```

### Time Signature (0x18A)

The time signature encoding uses a lookup table. Known values:

| Raw Byte | Time Signature | Notes |
|----------|----------------|-------|
| 0x1C (28) | 4/4 | **Confirmed** |
| 0x14 (20) | 3/4 | Hypothesis |
| 0x22 (34) | 6/8 | Hypothesis |
| 0x0C (12) | 2/4 | Hypothesis |

**Note:** Other time signatures need hardware verification.

## Channel Assignments (0x190 - 0x197)

8 bytes for MIDI channel assignments per track:

```
Offset  Track   Description
------  ------  -----------
0x190   RHY1    Rhythm 1 channel
0x191   RHY2    Rhythm 2 channel
0x192   BASS    Bass channel
0x193   CHD1    Chord 1 channel
0x194   CHD2    Chord 2 channel
0x195   CHD3    Chord 3 channel
0x196   CHD4    Chord 4 channel
0x197   CHD5    Chord 5 channel
```

**Encoding (observed):**
- `0x00` = Channel 10 (drums) - used for RHY1/RHY2
- `0x01-0x0F` = Channel 2-16 (value + 1)

**Example from T01.Q7P:**
```
00 00 00 00 03 03 03 03
→ Ch10, Ch10, Ch10, Ch10, Ch4, Ch4, Ch4, Ch4
```

## Track Configuration (0x1DC - 0x1E5)

### Track Numbers (0x1DC)

```
Offset  Size  Value           Description
------  ----  --------------  -----------
0x1DC   8     00 01 02...07   Sequential track indices (0-based)
```

### Track Enable Flags (0x1E4)

```
Offset  Size  Format  Description
------  ----  ------  -----------
0x1E4   2     Word    Bitmask: bit N = track N enabled
```

**Example:**
- `0x0001` = Only track 1 enabled
- `0x001F` = Tracks 1-5 enabled
- `0x00FF` = All 8 tracks enabled

## Volume Table (0x220 - 0x26F)

### Structure

```
Offset  Size  Description
------  ----  -----------
0x220   6     Header/reserved (zeros)
0x226   16    Volume values per track/section
0x236   26    Additional volume data
...
```

**XG Default Volume:** 100 (0x64)

## Reverb Send Table (0x250 - 0x26F)

**NEW - Discovered from XG analysis**

```
Offset  Size  Description
------  ----  -----------
0x250   6     Header/reserved
0x256   16    Reverb send values per track
```

**XG Default Reverb Send:** 40 (0x28)

## Pan Table (0x270 - 0x2BF)

**FIXED - Correct offset is 0x276, not 0x270**

```
Offset  Size  Description
------  ----  -----------
0x270   6     Header/reserved
0x276   48    Pan values per track/section
```

### XG Pan Encoding

| Value | Meaning |
|-------|---------|
| 0 | Random |
| 1-63 | Left (L63-L1) |
| 64 | Center |
| 65-127 | Right (R1-R63) |

**XG Default Pan:** 64 (Center)

## Template/Pattern Name (0x876)

```
Offset  Size  Description
------  ----  -----------
0x876   10    ASCII pattern name, space-padded
```

**Example:** `"USER TMPL "` (10 characters)

## Phrase Data Format (5120-byte files)

**DISCOVERED:** In 5120-byte Q7P files, phrase data is stored inline starting at offset 0x200.

### Phrase Block Structure

Each phrase block has this structure:

```
Offset  Size  Description
------  ----  -----------
0-11    12    Phrase name (ASCII, space-padded)
12-13   2     Marker: 0x03 0x1C
14-17   4     Note range: 0x00 0x00 0x00 0x7F
18-19   2     Track flags: 0x00 0x07
20-23   4     MIDI setup: 0x90 0x00 0x00 0x00
24-25   2     Tempo × 10 (big-endian, e.g., 0x04B0 = 120 BPM)
26-27   2     MIDI start marker: 0xF0 0x00
28+     var   MIDI events
...     1     End marker: 0xF2
...     var   Padding: 0x40 bytes
```

### MIDI Event Format (Yamaha QY Series)

**KEY DISCOVERY:** QY70 and QY700 use the **same proprietary MIDI event format**!

```
D0 nn vv xx   = Drum note on (note, velocity, next-byte)
E0 nn vv xx   = Melody note on (note, velocity, next-byte)
C1 nn pp      = Alternate note encoding (note, param)
A0-A7 dd      = Delta time (step type 0-7, duration)
BE xx         = Note off / reset
BC xx         = Control change
F0 00         = Start of MIDI data
F2            = End of phrase
0x40          = Padding byte
```

### Delta Time Encoding

The delta bytes (A0-A7) encode timing:
- A0 = smallest step (high resolution)
- A5 = larger step (lower resolution)
- The second byte is the duration value

### Example: Parsing a Drum Pattern

```python
# Hi-hat pattern from DECAY.Q7P
# D0 1E 2A 58 A0 78 D0 1E 2A 58 A0 78 D0 1E 2E 58 A1 70
#
# Decoded:
#   DrumNote 30 vel=42, Delta step=0 val=120
#   DrumNote 30 vel=42, Delta step=0 val=120
#   DrumNote 30 vel=46, Delta step=1 val=112
```

## Section Config Area (0x120)

In 5120-byte files, this area contains phrase references:

```
Format: F0 00 FB phrase_idx 00 track_ref C0 04 F2
```

Each entry is 9 bytes, mapping sections to phrase indices.

## Phrase Data Area (0x360 - 0x677) - 3072-byte files

792 bytes containing phrase reference data for 3072-byte files.
This format uses a different encoding than 5120-byte files.

## Sequence Events Area (0x678 - 0x86F)

504 bytes containing:
- Tempo changes
- Program changes (possibly)
- Other automation events

## Fill Areas

### FE Fill (0x9C0 - 0xB0F)

336 bytes filled with `0xFE` (unused space marker)

### F8 Padding (0xB10 - 0xBFF)

240 bytes filled with `0xF8` (end padding)

## XG Standard Values Reference

Based on [studio4all.de XG documentation](https://www.studio4all.de/htmle/main92.html):

| Parameter | Default | Hex | Range |
|-----------|---------|-----|-------|
| Volume | 100 | 0x64 | 0-127 |
| Pan | 64 (Center) | 0x40 | 0-127 |
| Reverb Send | 40 | 0x28 | 0-127 |
| Chorus Send | 0 | 0x00 | 0-127 |
| Variation Send | 0 | 0x00 | 0-127 |
| Bank MSB (Normal) | 0 | 0x00 | 0-127 |
| Bank MSB (Drums) | 127 | 0x7F | 0-127 |
| Bank LSB | 0 | 0x00 | 0-127 |
| Program | 0 | 0x00 | 0-127 |

## Reading a Q7P File

### Python Example

```python
import struct
from pathlib import Path

def read_q7p(filepath: str) -> dict:
    with open(filepath, 'rb') as f:
        data = f.read()
    
    if len(data) != 3072:
        raise ValueError("Invalid file size")
    
    if data[:16] != b"YQ7PAT     V1.00":
        raise ValueError("Invalid header")
    
    # Extract tempo (big-endian, divide by 10)
    tempo_raw = struct.unpack(">H", data[0x188:0x18A])[0]
    tempo = tempo_raw / 10.0
    
    # Extract pattern name
    name = data[0x876:0x880].decode('ascii').rstrip('\x00 ')
    
    # Extract volumes (offset 0x226)
    volumes = list(data[0x226:0x22E])
    
    # Extract pans (offset 0x276 - CORRECTED)
    pans = list(data[0x276:0x27E])
    
    # Extract reverb sends (offset 0x256)
    reverb_sends = list(data[0x256:0x25E])
    
    return {
        'pattern_number': data[0x10],
        'pattern_name': name,
        'tempo': tempo,
        'volumes': volumes,
        'pans': pans,
        'reverb_sends': reverb_sends,
    }
```

## Writing a Q7P File

### Template-Based Writing

The safest way to create Q7P files is to use an existing file as a template and modify specific fields:

```python
def write_q7p_from_template(template_path, output_path, pattern_name):
    with open(template_path, 'rb') as f:
        data = bytearray(f.read())
    
    # Update pattern name (offset 0x876, 10 chars)
    name = pattern_name[:10].upper().ljust(10)
    data[0x876:0x880] = name.encode('ascii')
    
    with open(output_path, 'wb') as f:
        f.write(data)
```

## Differences from QY70

| Aspect | QY70 | QY700 |
|--------|------|-------|
| Format | SysEx (.syx) | Binary (.Q7P) |
| Size | Variable | Fixed 3072 or 5120 bytes |
| Encoding | 7-bit packed | Raw 8-bit |
| Checksum | Per-message | None |
| Sections | 6 | 6 (basic) or 12 (full) |
| Tracks | 8 | 8 (same names) |

## Section Names

The QY700 supports up to 12 sections:

| Index | Name | Description |
|-------|------|-------------|
| 0 | Intro | Introduction section |
| 1 | Main A | Primary main pattern |
| 2 | Main B | Secondary main pattern |
| 3 | Fill AB | Fill from A to B |
| 4 | Fill BA | Fill from B to A |
| 5 | Ending | Ending section |
| 6 | Fill AA | Fill within A |
| 7 | Fill BB | Fill within B |
| 8 | Intro 2 | Secondary intro |
| 9 | Main C | Third main pattern |
| 10 | Main D | Fourth main pattern |
| 11 | Ending 2 | Secondary ending |
| Size | Variable | Fixed 3072 or 5120 bytes |
| Encoding | 7-bit packed | Raw 8-bit |
| Checksum | Per-message | None |
| Sections | 6 | 6 (basic) or 12 (full) |
| Tracks | 8 | **16** (TR1-TR16) |

## Unknown/Reserved Areas

These areas need further research:

| Offset | Size | Observed Content | Hypothesis |
|--------|------|------------------|------------|
| 0x2C0-0x35F | 160 | 0x40, 0x7F patterns | Effects settings? |
| 0x360-0x677 | 792 | Variable | Phrase MIDI data |
| 0x678-0x86F | 504 | Variable | Sequence events |
| 0x900-0x9BF | 192 | 0x00, 0x01 pattern | Section mapping |

## Tools

Use the `qymanager` CLI tool to analyze Q7P files:

```bash
# Basic pattern info
qymanager info pattern.Q7P

# Complete extended analysis with bar graphics
qymanager info pattern.Q7P --full

# Visual file structure map
qymanager map pattern.Q7P

# Annotated hex dump
qymanager dump pattern.Q7P
qymanager dump pattern.Q7P --region PHRASE
qymanager dump pattern.Q7P --region TEMPO

# Detailed track info with bar graphics
qymanager tracks pattern.Q7P
qymanager tracks pattern.Q7P --track 1

# Section details
qymanager sections pattern.Q7P
qymanager sections pattern.Q7P --active

# Phrase/sequence analysis with MIDI event detection
qymanager phrase pattern.Q7P
qymanager phrase pattern.Q7P --heatmap

# Compare two files
qymanager diff pattern1.Q7P pattern2.Q7P

# Validate structure
qymanager validate pattern.Q7P

# Convert from QY70 format
qymanager convert style.syx -o pattern.Q7P -t template.Q7P
```

### Available Dump Regions

`HEADER`, `PAT_INFO`, `SECT_PTR`, `SECT_DATA`, `TEMPO`, `CHANNELS`,
`TRK_CFG`, `VOLUMES`, `REVERB`, `PAN`, `PHRASE`, `SEQUENCE`, `TMPL_NAME`,
`PAT_MAP`, `FILL`, `PAD`

## References

- Yamaha QY700 Owner's Manual
- Yamaha XG Specification
- [studio4all.de XG Programming](https://www.studio4all.de/htmle/main92.html)
- Reverse engineering of sample files
