# BLK File Format

The `.blk` format is used by Yamaha's **QY Data Filer** (Windows/Mac) to save complete bulk dumps of [QY70](qy70-device.md) data.

**Confidence: HIGH** -- confirmed by [QYFiler.exe disassembly](qyfiler-reverse-engineering.md) and Yamaha Data Filer manual.

See also: [SysEx Format](sysex-format.md), [QYFiler RE](qyfiler-reverse-engineering.md)

## File Structure

The `.blk` file is **raw concatenated SysEx messages** with no proprietary header or wrapper.

```
[System/handshake SysEx messages]    ~1376 bytes (0x560)
[Track data SysEx messages]          variable
[Header SysEx messages]              variable
[Close message]                      9 bytes
```

### Layout

| Offset | Content | Size |
|--------|---------|------|
| 0x000 | Handshake/system SysEx (Init, Identity, XG params) | ~0x560 (1376 bytes) |
| 0x560+ | Bulk Dump data messages | Variable |
| End-9 | Close message `F0 43 10 5F 00 00 00 00 F7` | 9 bytes |

Each bulk dump message is exactly **158 bytes** (see [SysEx Format](sysex-format.md)).

### Validation Rules (from QYFiler.exe)

1. **Minimum size**: file must be > 0x560 (1376) bytes
2. **SysEx header**: messages must start with `F0 43 xx 5F` (Yamaha, QY70 model ID `5F`)
3. **Model check**: byte[6] high nibble must be `0x0_` (QY70). Value `0x1_` = wrong model -> error: "This bulk file is not for QY70"

### Reading Procedure (from disassembly at VA 0x40EA40)

1. Open file, seek to end, get file size
2. If size <= 0x560: error
3. Seek to offset 0x560 (skip handshake)
4. Read in 0xD0 (208) byte chunks
5. Scan for SysEx headers (`F0 43`)
6. Validate and extract each message
7. 7-bit decode each payload

## Relationship to .syx

A `.blk` file is functionally identical to a `.syx` file -- both contain raw SysEx messages. The differences:

| Aspect | .blk | .syx |
|--------|------|------|
| Creator | QY Data Filer | Generic MIDI tools (capture_dump.py, etc.) |
| Header region | First ~0x560 bytes = system SysEx | May or may not include system messages |
| Content | Full device backup (all patterns + system) | Usually one pattern/style |
| Validation | QYFiler checks model ID in byte[6] | No standard validation |

**Interconversion**: to extract pattern data from a .blk file, skip the first 0x560 bytes and treat the rest as standard .syx data. To create a .blk from a .syx, prepend the system/handshake messages.

## Data Flow

```
QY70 Internal Memory (rotated data)
        │
        ▼ [MIDI SysEx Bulk Dump -- no transformation]
        │
QY Data Filer (QYFiler.exe)
        │
        ▼ [Raw write -- no transformation]
        │
    .blk file (raw SysEx, data still rotated)
```

The QYFiler performs NO data transformation beyond the standard [7-bit encoding](7bit-encoding.md)/decoding. The barrel rotation is applied by the QY70 hardware before transmission. See [QYFiler RE: Critical Finding](qyfiler-reverse-engineering.md#critical-finding-no-rotation-or-scrambling).

## External Documentation

- [QY70 Data Filer Manual (PDF)](https://www.deepsonic.ch/deep/docs_manuals/yamaha_qy70_datafiler_manual.pdf) -- Yamaha official manual
- The manual describes: "All data in the QY70 can be saved to the computer as QY Bulk Files" via MIDI bulk dump transfer

## QY70 vs QY100 Compatibility

The only confirmed difference between QY70 and QY100 `.syx` files:
- **AH (Address High)**: `0x02` for QY70, different for QY100
- **Checksum**: recalculated accordingly
- A Python script at qy100.doffu.net automates this conversion

No public RE of the internal pattern bitstream has been done by anyone other than this project.
