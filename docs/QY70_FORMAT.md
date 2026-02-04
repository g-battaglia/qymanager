# QY70 SysEx File Format

This document describes the System Exclusive (SysEx) format used by the Yamaha QY70 for pattern/style data transfer.

## Overview

The QY70 uses MIDI System Exclusive messages to transfer bulk data. Pattern/style data is sent as a series of bulk dump messages, each containing a portion of the pattern data.

## Message Structure

### Manufacturer and Model IDs

| Byte | Value | Description |
|------|-------|-------------|
| Manufacturer ID | 0x43 | Yamaha |
| Model ID | 0x5F | QY70 |

### Message Types

| Device Byte | Type | Description |
|-------------|------|-------------|
| 0x0n | Bulk Dump | Transfer block of data |
| 0x1n | Parameter Change | Change single parameter |
| 0x2n | Dump Request | Request data from device |

Where `n` is the device number (0-15).

## Bulk Dump Format

```
F0 43 0n 5F BH BL AH AM AL [data...] CS F7
```

| Field | Size | Description |
|-------|------|-------------|
| F0 | 1 | SysEx Start |
| 43 | 1 | Yamaha Manufacturer ID |
| 0n | 1 | Bulk Dump + Device Number |
| 5F | 1 | QY70 Model ID |
| BH | 1 | Byte Count High (bits 13-7) |
| BL | 1 | Byte Count Low (bits 6-0) |
| AH | 1 | Address High |
| AM | 1 | Address Mid |
| AL | 1 | Address Low |
| data | var | 7-bit encoded payload |
| CS | 1 | Checksum |
| F7 | 1 | SysEx End |

### Byte Count

The byte count indicates the size of the encoded data payload:
```
byte_count = (BH << 7) | BL
```

### Checksum Calculation

The checksum is calculated over the address and data bytes:

```python
def calculate_checksum(address_and_data: bytes) -> int:
    total = sum(address_and_data)
    return (128 - (total & 0x7F)) & 0x7F
```

## 7-Bit Encoding

MIDI SysEx requires all data bytes to have bit 7 clear (values 0-127). The QY70 uses Yamaha's standard 7-bit packing scheme:

### Encoding Process

For every 7 bytes of raw 8-bit data:
1. Extract the high bit (bit 7) from each byte
2. Pack these 7 high bits into a "header" byte
3. Clear the high bits in the original 7 bytes
4. Output: 1 header byte + 7 data bytes = 8 bytes

### Header Byte Layout

```
Header: [b6 b5 b4 b3 b2 b1 b0 0]
         │  │  │  │  │  │  │
         │  │  │  │  │  │  └── Bit 7 of byte 6
         │  │  │  │  │  └───── Bit 7 of byte 5
         │  │  │  │  └──────── Bit 7 of byte 4
         │  │  │  └─────────── Bit 7 of byte 3
         │  │  └────────────── Bit 7 of byte 2
         │  └───────────────── Bit 7 of byte 1
         └──────────────────── Bit 7 of byte 0
```

### Example

Raw data (7 bytes):
```
80 40 20 10 08 04 02
```

High bits: `1 0 0 0 0 0 0` → Header: `0x40`

Encoded (8 bytes):
```
40 00 40 20 10 08 04 02
```

### Decoding Process

```python
def decode_7bit(encoded: bytes) -> bytes:
    result = bytearray()
    for i in range(0, len(encoded), 8):
        header = encoded[i]
        for j in range(1, min(8, len(encoded) - i)):
            high_bit = (header >> (7 - j)) & 1
            result.append(encoded[i + j] | (high_bit << 7))
    return bytes(result)
```

## Address Map

### Style Data (AH=0x02, AM=0x7E)

| AL Value | Description | Typical Size |
|----------|-------------|--------------|
| 0x00 | Intro section | 882 bytes |
| 0x01 | Main A section | 294 bytes |
| 0x02 | Main B section | 147 bytes |
| 0x03 | Fill AB section | 294 bytes |
| 0x04 | Fill BA section | 147 bytes |
| 0x05 | Ending section | 294 bytes |
| 0x06-0x2F | Track data blocks | varies |
| 0x7F | Header/config | 735 bytes |

## Parameter Change Format

```
F0 43 1n 5F AH AM AL DD F7
```

| Field | Description |
|-------|-------------|
| 1n | Parameter Change + Device Number |
| AH AM AL | Parameter address |
| DD | Data value |

## Initialization Message

Before bulk dump, an init message is typically sent:

```
F0 43 10 5F 00 00 00 01 F7
```

This prepares the device to receive the following bulk data.

## Complete Style Transfer

A typical style transfer consists of:

1. Initialization message
2. Multiple bulk dump messages for section data (AL = 0x00-0x05)
3. Track data blocks (AL = 0x08-0x2F)
4. Header/config block (AL = 0x7F)

Messages are sent in order, and each message's checksum is validated by the receiver.

## References

- Yamaha QY70 Owner's Manual
- Yamaha QY70 MIDI Implementation Chart
- MIDI 1.0 Specification (System Exclusive)
