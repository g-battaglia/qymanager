# QY700 Q7P File Format

This document describes the binary file format used by the Yamaha QY700 for pattern files (.Q7P).

## Overview

Q7P files are fixed-size binary files containing a single pattern with all its sections and track data. Unlike the QY70's SysEx format, Q7P files use raw 8-bit data without compression.

## File Specifications

| Property | Value |
|----------|-------|
| File Extension | .Q7P |
| File Size | 3072 bytes (fixed) |
| Encoding | Raw binary (8-bit) |
| Byte Order | Big-endian |

## File Structure

### Overall Layout

```
Offset  Size    Description
------  ------  -----------
0x000   16      Header "YQ7PAT     V1.00"
0x010   32      Pattern info (number, flags)
0x030   2       Size marker
0x040   192     Reserved/padding
0x100   32      Track pointers
0x120   96      Section data (encoded)
0x180   16      Tempo/timing
0x190   8       Channel assignments
0x198   8       Reserved
0x1A0   60      Pattern name/spaces
0x1DC   8       Track numbering (0-7)
0x1E4   60      Reserved
0x220   320     Volume/velocity tables
0x360   792     Phrase/pattern data
0x678   504     Sequence events
0x870   16      Template name
0x880   128     Reserved
0x900   192     Pattern mappings
0x9C0   336     Fill area (0xFE bytes)
0xB10   240     Padding (0xF8 bytes)
```

## Header Structure (0x000 - 0x0FF)

### Magic Header (0x000)

```
Offset  Size  Value              Description
------  ----  -----------------  -----------
0x000   16    "YQ7PAT     V1.00" File type and version
```

### Pattern Info (0x010)

```
Offset  Size  Description
------  ----  -----------
0x010   1     Pattern number (slot)
0x011   1     Flags (0x01 or 0x02 typical)
0x012   14    Reserved (zeros)
```

### Size Marker (0x030)

```
Offset  Size  Format      Description
------  ----  ----------  -----------
0x030   2     Big-endian  Size marker (typically 0x0990 = 2448)
```

## Section Data (0x100 - 0x1FF)

### Track Pointers (0x100)

The track pointer area contains offsets or flags for each track:

```
Offset  Size  Description
------  ----  -----------
0x100   1     First offset byte
0x101   1     Unused marker (0x20 = space)
0x102-0x11F  30  Section reference flags (0xFE = empty)
```

### Section Encoded Data (0x120)

Pattern section information is encoded here:

```
Offset  Size  Description
------  ----  -----------
0x120   2     Section header (0xF0 0x00)
0x122   1     Section type flags (0xFB)
0x123   ...   Section-specific data
```

### Tempo/Timing (0x180)

```
Offset  Size  Description
------  ----  -----------
0x180   8     Reserved/spaces (0x20)
0x188   2     Tempo value (needs decoding)
0x18A   2     Time signature data
0x18C   4     Additional timing flags
```

### Channel Assignments (0x190)

```
Offset  Size  Description
------  ----  -----------
0x190   8     Channel assignment for tracks 1-8
              (typical value: 0x03 for each)
```

### Track Numbering (0x1DC)

```
Offset  Size  Value           Description
------  ----  --------------  -----------
0x1DC   8     00 01 02...07   Sequential track numbers
0x1E4   2     Track enable flags
```

## Volume Tables (0x220 - 0x35F)

### Per-Section Volume Data

Each section has volume/velocity values for its 8 tracks:

```
Offset      Description
------      -----------
0x220-0x22F Intro volumes (16 tracks × value)
0x230-0x23F Main A volumes
0x240-0x24F Main B volumes
...and so on...
```

Default volume value is 0x64 (100).

## Pattern Data (0x360 - 0x677)

### Phrase Mappings

This area contains the phrase references and pattern sequence data:

```
Offset  Description
------  -----------
0x360   Phrase data start
0x3B0   Pattern velocity data
0x400   Additional phrase settings
```

## Sequence Events (0x678 - 0x86F)

### Event Data Structure

```
Offset  Size  Description
------  ----  -----------
0x678   2     Event count/flags
0x67A   ...   Event data (timing, program changes)
```

### Tempo Location

The main tempo value appears to be stored at:

```
Offset  Description
------  -----------
0x688   Tempo-related value
0x68C   Time signature encoding
```

## Template Name (0x870 - 0x87F)

### Name String

```
Offset  Size  Description
------  ----  -----------
0x870   10    Template/pattern name (ASCII, space-padded)
0x87A   6     Reserved
```

Example: "USER TMPL " (10 characters, space-padded)

## Pattern Mappings (0x900 - 0x9BF)

### Section Enable Flags

```
Offset  Size  Value    Description
------  ----  -------  -----------
0x900   64    00 01... Pattern enable/repeat mapping
0x940   64    00 01... Additional mapping data
```

Typical pattern: alternating 0x00 0x01 bytes.

## Fill Areas

### FE Fill (0x9C0 - 0xA8F)

Unused space filled with 0xFE bytes.

```
for offset in range(0x9C0, 0xA90):
    data[offset] = 0xFE
```

### F8 Padding (0xB10 - 0xBFF)

End-of-file padding with 0xF8 bytes.

```
for offset in range(0xB10, 0xC00):
    data[offset] = 0xF8
```

## Reading a Q7P File

### Python Example

```python
def read_q7p(filepath: str) -> dict:
    with open(filepath, 'rb') as f:
        data = f.read()
    
    if len(data) != 3072:
        raise ValueError("Invalid file size")
    
    if data[:16] != b"YQ7PAT     V1.00":
        raise ValueError("Invalid header")
    
    return {
        'pattern_number': data[0x10],
        'flags': data[0x11],
        'template_name': data[0x870:0x87A].decode('ascii').strip(),
        'channels': list(data[0x190:0x198]),
    }
```

## Writing a Q7P File

### Template-Based Writing

The safest way to create Q7P files is to use an existing file as a template and modify specific fields:

```python
def write_q7p_from_template(template_path, output_path, pattern_name):
    with open(template_path, 'rb') as f:
        data = bytearray(f.read())
    
    # Update pattern name
    name = pattern_name[:10].upper().ljust(10)
    data[0x870:0x87A] = name.encode('ascii')
    
    with open(output_path, 'wb') as f:
        f.write(data)
```

## Differences from QY70

| Aspect | QY70 | QY700 |
|--------|------|-------|
| Format | SysEx | Binary |
| Size | Variable | Fixed 3072 bytes |
| Encoding | 7-bit packed | Raw 8-bit |
| Checksum | Per-message | None |
| Sections | 6 | 6+ (more patterns) |

## References

- Yamaha QY700 Owner's Manual
- QY Data Filer documentation
- Reverse engineering of sample files
