# QY70 SysEx Format

The [QY70](qy70-device.md) uses MIDI System Exclusive messages for bulk data transfer.

## Message Structure

```
F0 43 0n 5F BH BL AH AM AL [data...] CS F7
```

| Field | Size | Description |
|-------|------|-------------|
| `F0` | 1 | SysEx Start |
| `43` | 1 | Yamaha Manufacturer ID |
| `0n` | 1 | Message type + device number (n=0-15) |
| `5F` | 1 | QY70 Sequencer Model ID |
| `BH BL` | 2 | Byte count: `(BH << 7) \| BL` |
| `AH AM AL` | 3 | Address (AH=0x02, AM=0x7E for style data) |
| data | var | [7-bit encoded](7bit-encoding.md) payload |
| `CS` | 1 | Checksum |
| `F7` | 1 | SysEx End |

## Message Types

| Device Byte | Type | Description |
|-------------|------|-------------|
| `0x0n` | Bulk Dump | Data transfer block |
| `0x1n` | Parameter Change | Single parameter (no checksum) |
| `0x2n` | Dump Request | Request data from QY70 |
| `0x3n` | Dump Acknowledgment | ACK from QY70 (found in [QYFiler templates](qyfiler-reverse-engineering.md#sysex-command-template-table-at-va-0x434630)) |

**Dump Request** works for user pattern slots (AM=0x00-0x3F). Format: `F0 43 20 5F AH AM AL F7`. Does NOT work for edit buffer (AM=0x7E). Session 16 received `F0 F7` from AM=0x00 (valid empty-pattern response). [QYFiler.exe](qyfiler-reverse-engineering.md) also uses AM=0xFF in templates (possibly "all slots" wildcard). See [MIDI Setup](midi-setup.md).

## Checksum

```python
def calculate_checksum(address_and_data: bytes) -> int:
    return (128 - (sum(address_and_data) & 0x7F)) & 0x7F
```

## Address Map (AH=0x02, AM=0x7E)

| AL Range | Description |
|----------|-------------|
| `0x00-0x07` | Section 0 tracks 0-7 |
| `0x08-0x0F` | Section 1 tracks 0-7 |
| ... | ... |
| `0x28-0x2F` | Section 5 tracks 0-7 |
| `0x7F` | [Header/config](header-section.md) (640 decoded bytes) |

**Addressing**: `AL = section_index * 8 + track_index`

See [Track Structure](track-structure.md) for section/track layout.

## Complete Transfer Sequence

1. **Init**: `F0 43 10 5F 00 00 00 01 F7` (Parameter Change)
2. **Track data**: Bulk Dump messages for each active track (AL 0x00-0x2F)
3. **Header**: Bulk Dump messages at AL=0x7F (5 × 128 decoded bytes)
4. **Close**: `F0 43 10 5F 00 00 00 00 F7` (Parameter Change)

## Track Data Sizes (decoded bytes)

| Track | Size | Messages |
|-------|------|----------|
| RHY1 (D1) | 768 | 6 × 128 |
| RHY2 (D2) | 256 | 2 × 128 |
| BASS (PC) | 128 | 1 × 128 |
| CHD1-PHR2 | 128-256 | 1-2 × 128 |

Each message carries up to 128 decoded bytes (147 encoded bytes after [7-bit packing](7bit-encoding.md)).

## QYFiler Command Templates (Session 20)

[QYFiler.exe disassembly](qyfiler-reverse-engineering.md) revealed a complete template table at VA 0x434630:

| Template | Purpose |
|----------|---------|
| `F0 7E 7F 06 01 F7` | Identity Request |
| `F0 7E 7F 06 02 43 00 41 02 55 FF FF FF FF F7` | Identity Reply match (FF=wildcards) |
| `F0 43 10 5F 00 00 00 01 F7` | Init (start transfer) |
| `F0 43 10 5F 00 00 00 00 F7` | Close (end transfer) |
| `F0 43 30 5F 00 00 00 F7` | Dump acknowledgment |
| `F0 43 20 5F 01 FF 00 F7` | Dump Request song slot |
| `F0 43 20 5F 02 FF 00 F7` | Dump Request style slot |
| `F0 43 20 5F 03 00 00 F7` | Dump Request system data |

**Send protocol**: 20 tracks in a loop, each chunked into 128-byte blocks, 7-bit encoded, SysEx wrapped, then a 654-byte system block at track=0x7F.

**Receive protocol**: 512-byte block alignment in destination buffer (128 decoded bytes placed 512 apart). 200ms inter-block delay. 3000ms timeout.

**No data transformation**: [QYFiler performs NO rotation or scrambling](qyfiler-reverse-engineering.md#critical-finding-no-rotation-or-scrambling) -- the barrel rotation is applied by the QY70 hardware internally.

## Also See

- [BLK Format](blk-format.md) — QY Data Filer file format (.blk = raw SysEx)
- [QYFiler RE](qyfiler-reverse-engineering.md) — Full disassembly analysis
