# QY70 Pattern Name Directory (AH=0x05)

Separate SysEx area that stores pattern slot names, independent of pattern data.

Discovered Session 28 via AH value sweep against live hardware.

## Structure

| Property | Value |
|----------|-------|
| Dump request | `F0 43 20 5F 02 7E 05 F7` |
| Response header | `F0 43 00 5F 02 40 05 00 00` |
| Response size | 331 bytes (9B header + 320B body + 2B trailer) |
| Message count | 1 |
| Body | 20 slots × 16 bytes each |

## Per-slot Layout (16 bytes)

```
Offset  Size  Description
────────────────────────
0x00    8     Pattern name (ASCII, 7-bit)
0x08    8     Metadata (zeros when slot empty)
```

## Slot Naming

The 20 slots correspond to user patterns `U01`-`U20`.

An empty slot is encoded as `2A 2A 2A 2A 2A 2A 2A 2A` (eight ASCII asterisks). This matches the QY70 front-panel rendering where unused slots display `********`.

## Confidence

| Item | Confidence |
|------|------------|
| Slot count = 20 | High (matches QY70 user slot count) |
| Name field = 8 bytes ASCII | High (empty pattern = 8 × 0x2A confirmed) |
| Metadata semantics | Low (always zero in empty capture) |

## Example Dump (empty directory)

```
slot  0  name=[********]  meta=0000000000000000
slot  1  name=[********]  meta=0000000000000000
...
slot 19  name=[********]  meta=0000000000000000
```

## Relationship to Pattern Data

The pattern data at `AH=0x00` (or `0x02 0x00`) is addressed by AM (pattern slot, 0x00-0x3F), while the directory at `AH=0x05` is a single global list.

This suggests the QY70 writes pattern names independently from pattern data. For a faithful round-trip (capture ↔ restore) the directory must be captured and resent alongside the pattern dumps.

## Tool

`midi_tools/decode_pattern_names.py <ah_0x05.syx>` — pretty-prints slot names from a capture.

## Related

- [SysEx Format](sysex-format.md) — full bulk-dump envelope
- [Track Structure](track-structure.md) — AL addressing within pattern data
- [Pattern Backup & Restore](pattern-restore.md) — existing restore workflow
