# Yamaha QY700

Workstation sequencer. The larger, more capable sibling of the [QY70](qy70-device.md).

## Specifications

| Property | Value |
|----------|-------|
| Tracks per Pattern | 16 (TR1-TR16) |
| Max Sections | 6 (basic) or 12 (full) |
| Data Format | Binary `.Q7P` files |
| File Size | 3072 bytes (basic) or 5120 bytes (full) |
| Byte Order | Big-endian |
| Header | `YQ7PAT     V1.00` |

## Key Differences from QY70

| Feature | QY70 | QY700 |
|---------|------|-------|
| Tracks | 8 | 16 |
| Data format | SysEx packed bitstream | Byte-oriented binary |
| Event format | 9-bit fields, barrel rotation | D0/E0/A0-A7/BE/F2 commands |
| File format | `.syx` (variable size) | `.Q7P` (fixed 3072 or 5120 bytes) |
| Data transfer | MIDI SysEx bulk dump | Floppy disk or MIDI dump |

## File Format

See [Q7P Format](q7p-format.md) for the complete binary structure.

## Known Issues

- **Bricking risk**: writing to unconfirmed offsets (0x1E6, 0x1F6, 0x206) can corrupt patterns and cause the device to hang. See [Bricking Diagnosis](bricking.md).
- Phrase data format (0x360-0x677) is NOT byte-oriented D0/E0 commands as initially assumed — contains values 0x2D-0x7F without command bytes, suggesting a different encoding.
