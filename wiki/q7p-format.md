# Q7P File Format

Binary file format for the [QY700](qy700-device.md) pattern files.

## File Properties

| Property | Value |
|----------|-------|
| Extension | `.Q7P` |
| Size | 3072 bytes (basic) or 5120 bytes (full) |
| Encoding | Raw 8-bit binary |
| Byte order | Big-endian |
| Header magic | `YQ7PAT     V1.00` (16 bytes at 0x000) |

## Complete Structure Map

```
Offset    Size    Description                          Status
────────────────────────────────────────────────────────────
0x000     16      Header "YQ7PAT     V1.00"            Verified
0x010     1       Pattern number (slot)                Verified
0x011     1       Pattern flags                        Verified
0x030     2       Size marker (0x0990 = 2448 BE)       Verified
0x100     32      Section pointers (16 × 2B BE)        Verified
0x120     96      Section config entries (9B each)      Verified
0x188     2       Tempo (BE, ÷10 for BPM)              Verified
0x18A     1       Time signature (0x1C = 4/4)          Verified
0x190     16      Channel assignments (16 tracks)      Verified
0x1DC     8       Track numbers (00-07)                Verified
0x1E4     2       Track enable flags (bitmask)         Verified
0x1E6     16      RESERVED — NOT Bank MSB             ⚠ See bricking
0x1F6     16      RESERVED — NOT Program              ⚠ See bricking
0x206     16      RESERVED — NOT Bank LSB             ⚠ See bricking
0x226     16      Volume (16 tracks)                   Verified
0x246     16      Chorus Send (16 tracks)              Verified
0x256     16      Reverb Send (16 tracks)              Verified
0x276     74      Pan data (multi-section)             Verified
0x360     792     Phrase data                          Unknown format
0x678     504     Sequence events                      Unknown format
0x876     10      Pattern name (ASCII)                 Verified
0x9C0     336     Fill area (0xFE bytes)               Verified
0xB10     240     Padding (0xF8 bytes)                 Verified
```

## Section Pointers (0x100)

16 entries of 2-byte big-endian. Effective offset = `pointer_value + 0x100`.
Empty/unused sections use `0xFEFE`.

## Section Config (9 bytes each)

```
F0 00 FB pp 00 tt C0 bb F2
│        │     │     │  └── End marker
│        │     │     └───── Bar count
│        │     └─────────── Track ref
│        └───────────────── Phrase index
└────────────────────────── Start marker
```

## Tempo (0x188)

```python
bpm = struct.unpack(">H", data[0x188:0x18A])[0] / 10.0
```

## Critical Safety Note

Offsets `0x1E6`, `0x1F6`, `0x206` were hypothesized as Bank MSB/Program/Bank LSB but are ALL ZERO in both test files. Writing non-zero values here caused [QY700 bricking](bricking.md). These areas must NOT be written to.

See [Format Mapping](format-mapping.md) for QY70 ↔ QY700 correspondence.
