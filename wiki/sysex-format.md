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
| `0x2n` | Dump Request | Request data (NOT supported by QY70) |

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
