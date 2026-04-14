# Header Section (AL=0x7F)

The global pattern/style configuration block. Transmitted as 5 × 128-byte decoded blocks (640 bytes total).

## Tempo Encoding

**Formula**: `BPM = (range × 95 - 133) + offset`

| Range | BPM Range | Example |
|-------|-----------|---------|
| 2 | 57-184 | MR.VAIN: range=2, offset=76 → 133 BPM |
| 3 | 152-279 | SUMMER: range=3, offset=3 → 155 BPM |
| 4 | 247-374 | (fast styles) |

```python
def bpm_to_tempo_bytes(bpm: int) -> tuple[int, int]:
    for range_val in range(1, 10):
        base = range_val * 95 - 133
        offset = bpm - base
        if 0 <= offset <= 127:
            return (range_val, offset)
```

## Style Name

**NOT stored in ASCII** in the bulk dump. Exhaustive testing of ASCII, 5-bit, 6-bit, BCD, and nibble encodings found no readable name. The name is either:
1. Not in the bulk dump (displayed from device internal storage)
2. Encoded in a proprietary format in the section pointer bytes (0x006-0x044)

## Complete Structural Map (640 decoded bytes)

```
Offset    Size  Content                              Type
────────────────────────────────────────────────────────────
0x000     1     Tempo/timing byte (decoded[0])       Variable
0x001-005 5     Fixed: 00 00 00 00 80                Fixed
0x006-009 4     Section size/pointer data             Variable
0x00A-00B 2     Fixed: 01 00                         Fixed
0x00C-00D 2     Section flags                        Variable
0x00F-044 54    Section pointer/phrase table          Variable
                (7-byte groups, empty-marker when unused)
0x045-07F 59    Section data table                   Variable
0x080-084 5     Fixed: 03 01 40 60 30                Fixed
0x085-089 5     Track config block 1                 Variable
0x096-0B5 32    Track/voice configuration            Variable
0x0C6-0D2 13    Voice/bank config                    Variable
0x0D3-136 100   Per-track parameters (mixed)         Mixed
0x137-1B8 130   *** LARGE FIXED TEMPLATE ***         Fixed
0x1B9-21B 99    *** MIXER PARAMETERS ***             Variable
                (empty-marker when unused, bit-packed vol/rev/cho when active)
0x221-229 9     Style/section flags                  Variable
```

40% fixed bytes, 60% variable across known files.

## Empty-Marker Pattern

Unused parameter slots are filled with:
```
BF DF EF F7 FB FD FE
```

Each byte is `0xFF` with one bit cleared (6→0), descending. In raw SysEx: `7F 3F 5F 6F 77 7B 7D 7E`.

A "low variant" (`3F 5F 6F 77 7B 7D 7E`) also exists with bit 7 clear — bit 7 acts as an "active/populated" flag.

See [Track Structure](track-structure.md), [SysEx Format](sysex-format.md).
