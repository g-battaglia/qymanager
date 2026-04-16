# Header Section (AL=0x7F)

The global pattern/style configuration block. Transmitted as 5 × 128-byte decoded blocks (640 bytes total).

## Tempo Encoding — CONFIRMED (Session 25c)

**Formula**: `BPM = msg.data[0] × 95 - 133 + msg.data[1]`

Where `msg.data[0]` and `msg.data[1]` are the first two bytes of the **raw** (7-bit encoded) payload of the first header SysEx message. These are the 7-bit group header byte and first data byte respectively.

| msg.data[0] | BPM Range | Verified Examples |
|-------------|-----------|-------------------|
| 1 | -38 to 89 | (slow patterns) |
| 2 | 57–184 | MR.VAIN: offset=76 → **133 BPM** ✓, GT_A: offset=44 → **101 BPM** |
| 3 | 152–279 | SUMMER: offset=3 → **155 BPM** |
| 4 | 247–374 | (fast patterns) |

**Note**: `msg.data[0]` is also the 7-bit encoding group header (MSBs for decoded bytes 0-6). Bits 0-1 determine the BPM range, while bits 2-6 provide MSBs for decoded data. This dual-use is a Yamaha packing optimization.

```python
def bpm_to_tempo_bytes(bpm: int) -> tuple[int, int]:
    for range_val in range(1, 10):
        base = range_val * 95 - 133
        offset = bpm - base
        if 0 <= offset <= 127:
            return (range_val, offset)
```

## Style Name

**NOT stored in ASCII** in the bulk dump. The name is either stored in device internal storage or encoded in a proprietary format.

## Verified Structural Map (640 decoded bytes, Session 25c)

Based on 4-file cross-comparison (Summer, MR. Vain, GT_style, GT_A empty):

```
Offset    Size  Content                              Confidence
──────────────────────────────────────────────────────────────────
0x000     1     Format type marker                   HIGH
                  0x03=user pattern, 0x4C=loaded style, 0x2C=empty
0x001     1     Active flag (0x40=has data, 0x00=empty)  HIGH
0x002-003 2     Fixed: 00 00                         HIGH
0x004     1     Section index (0=MAIN-A, 1=MAIN-B)   HIGH
0x005-00D 9     Global config (packed bitfields)      Medium
                  MR_Vain≈GT_style (differ 1 byte), Summer different
0x00E     1     Fixed: 00                            HIGH
0x00F-014 6     Timing/mode flags                    Low
0x015-045 49    Section pointer table                 Low
                  (7-byte groups, empty-marker when unused)
0x046-07C 55    Per-track data config                 Medium
                  0x048-04B: track sizes in /8 units
                  (RHY1=384→48✓, CHD1=256→32✓)
                  0x052-053: shared config [0x1A, 0x0E]
0x080-084 5     Fixed: 03 01 40 60 30                HIGH (all 4 files)
0x085-089 5     Track config block 1                 Medium
0x088     1     Active tracks flag? (0x0F when data exists)  Medium
0x096-0B5 32    Track/voice configuration            Medium
0x0AA-0B0 7     Voice parameters (all 4 files differ) Medium
0x0C6-0D2 13    Voice/bank config                    Low
0x0D3-136 100   Per-track parameters (mixed)         Low
                  Contains repeating `10 88 04 02 01` structural markers
0x137-1B8 130   *** LARGE FIXED TEMPLATE ***         HIGH
0x1A2-1B0 14    Universal constant block              HIGH
                  `64 19 8C C6 23 11 C8` × 2 (all files!)
0x1B9-21B 99    *** MIXER PARAMETERS ***             Medium
                  empty-marker when unused
0x221-229 9     Section presence flags                Medium
                  Bit 7 in padding = "populated" flag
0x22A-27F 86    Padding (empty-marker pattern)        HIGH
```

76% constant bytes across all patterns, 24% variable.

## Empty-Marker Pattern

Unused parameter slots are filled with:
```
BF DF EF F7 FB FD FE
```

Each byte is `0xFF` with one bit cleared (6→0), descending. In raw SysEx: `7F 3F 5F 6F 77 7B 7D 7E`.

A "low variant" (`3F 5F 6F 77 7B 7D 7E`) also exists with bit 7 clear — bit 7 acts as an "active/populated" flag.

See [Track Structure](track-structure.md), [SysEx Format](sysex-format.md).
